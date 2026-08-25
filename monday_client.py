"""
monday.com data layer — pulls Deals and Work Orders boards into pandas DataFrames.
No CSV data is hardcoded; every call hits the live monday.com API.
"""
import os
from typing import Optional

import requests
import pandas as pd

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_KEY = os.environ.get("MONDAY_API_KEY")

HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json",
}

BOARD_QUERY = """
query ($boardId: [ID!]) {
  boards(ids: $boardId) {
    id
    name
    columns {
      id
      title
      type
    }
    items_page(limit: 500) {
      cursor
      items {
        id
        name
        column_values {
          id
          text
          value
        }
      }
    }
  }
}
"""

NEXT_ITEMS_QUERY = """
query ($cursor: String!) {
  next_items_page(cursor: $cursor, limit: 500) {
    cursor
    items {
      id
      name
      column_values {
        id
        text
        value
      }
    }
  }
}
"""


def _run_query(query: str, variables: dict) -> dict:
    if not MONDAY_API_KEY:
        raise RuntimeError("MONDAY_API_KEY environment variable is not set.")
    resp = requests.post(
        MONDAY_API_URL,
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"monday.com API error: {data['errors']}")
    return data["data"]


def get_board_items(board_id: str) -> pd.DataFrame:
    """
    Pulls every item from a monday.com board (handling pagination) and
    returns a flat pandas DataFrame — one row per item, one column per
    monday.com column (keyed by column title, not internal id).
    """
    data = _run_query(BOARD_QUERY, {"boardId": [board_id]})
    board = data["boards"][0]
    column_titles = {c["id"]: c["title"] for c in board["columns"]}

    items = board["items_page"]["items"]
    cursor = board["items_page"]["cursor"]

    # Paginate until cursor is exhausted — boards over 500 items need this.
    while cursor:
        page = _run_query(NEXT_ITEMS_QUERY, {"cursor": cursor})["next_items_page"]
        items.extend(page["items"])
        cursor = page["cursor"]

    rows = []
    for item in items:
        row = {"item_id": item["id"], "item_name": item["name"]}
        for cv in item["column_values"]:
            col_title = column_titles.get(cv["id"], cv["id"])
            row[col_title] = cv["text"]
        rows.append(row)

    result = pd.DataFrame(rows)

    # Data-quality fix: the CSV->monday.com import left stray header rows
    # leaking into the data (e.g. "Sector/service" appearing as a VALUE in
    # the Sector/service column). Blank those out at the source so every
    # downstream consumer sees clean data instead of re-detecting this bug.
    for col in result.columns:
        leaked = result[col].astype(str).str.strip().str.lower() == col.strip().lower()
        result.loc[leaked, col] = pd.NA

    return result


def get_deals_df(board_id: Optional[str] = None) -> pd.DataFrame:
    board_id = board_id or os.environ["DEALS_BOARD_ID"]
    return get_board_items(board_id)


def get_work_orders_df(board_id: Optional[str] = None) -> pd.DataFrame:
    board_id = board_id or os.environ["WORK_ORDERS_BOARD_ID"]
    return get_board_items(board_id)


if __name__ == "__main__":
    # Quick manual test — run `python monday_client.py` after setting env vars.
    deals = get_deals_df()
    print(deals.head())
    print(f"\nPulled {len(deals)} deals with columns: {list(deals.columns)}")