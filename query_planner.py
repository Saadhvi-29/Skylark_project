"""
Query planner + exact execution — takes the intent JSON (intent_extractor.py)
and the resolved fuzzy terms (fuzzy_matcher.py), builds a concrete filter
plan, runs it against the live DataFrame with pandas (never the LLM), and
returns a result with explicit data-quality caveats.

Supports both boards via BOARD_CONFIG below — same filter/aggregate logic,
different column mappings per board.

ASSUMPTIONS (move these into your Decision Log):
1. Deals: "pipeline value" = sum of deal value over deals NOT marked
   Dead/Won (confirmed from real Deal Status values: Open, On Hold, Dead, Won).
2. Work Orders: value column = "Amount Receivable (Masked)" — chosen over
   the ~7 other amount/billing columns because "receivable" best matches
   generic revenue/value questions; a real system would let the user pick
   which billing stage they mean. "Active" work orders = Execution Status
   not "Completed" (Not Started / Ongoing / Partial Completed / etc. all
   count as active/in-progress).
3. Relative time terms ("this quarter", "this year") resolve against the
   REAL current date. If sample data is historical, exact-period queries
   may legitimately return zero rows; the planner falls back to reporting
   the most recent period that DOES have data rather than failing silently.
4. Metric routing (value / count / average / weighted / active-scoped) is
   keyword-based on the free-text "metric" field, not a fixed enum — a
   deliberate simplification given the time constraint.
5. Each query targets ONE board (whichever intent_extractor identifies
   first). Cross-board queries (e.g. "compare Deals pipeline to Work
   Orders billing") are NOT supported — documented as a known limitation.
"""
import re
from datetime import datetime
from typing import Optional

import pandas as pd

from fuzzy_matcher import resolve_all, resolve_column_name

BOARD_CONFIG = {
    "Deals": {
        "value_column": "Masked Deal value",
        "probability_column": "Closure Probability",
        "date_column": "Created Date",  # swap to "Close Date (A)" for closed-business questions
        "status_column": "Deal Status",
        "closed_status_values": {"dead", "won"},
        "active_keywords": {"pipeline", "active", "open"},
    },
    "Work Orders": {
        "value_column": "Amount Receivable (Masked)",
        "probability_column": None,
        "date_column": "Data Delivery Date",
        "status_column": "Execution Status",
        "closed_status_values": {"completed"},
        "active_keywords": {"active", "ongoing", "in progress", "pending"},
    },
}


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _parse_time_range(time_range: Optional[str]) -> Optional[tuple]:
    """
    Returns (start, end) as pandas Timestamps, or None if time_range is
    null/unparseable (in which case no date filter is applied).
    """
    if not time_range:
        return None

    now = pd.Timestamp(datetime.now())
    text = time_range.lower()

    if "this quarter" in text:
        return (now.to_period("Q").start_time, now.to_period("Q").end_time)
    if "last quarter" in text:
        last_q = now.to_period("Q") - 1
        return (last_q.start_time, last_q.end_time)
    if "this year" in text:
        return (pd.Timestamp(year=now.year, month=1, day=1), pd.Timestamp(year=now.year, month=12, day=31))

    match = re.search(r"q([1-4])\s*(\d{4})", text)
    if match:
        q, year = int(match.group(1)), int(match.group(2))
        period = pd.Period(f"{year}Q{q}", freq="Q")
        return (period.start_time, period.end_time)

    return None  # unparseable — leave unfiltered, note as a caveat


def resolve_board(intent: dict) -> str:
    """Picks the target board from intent['boards'], defaulting to Deals."""
    boards = intent.get("boards") or []
    for b in boards:
        if b in BOARD_CONFIG:
            return b
    return "Deals"


def build_filter_plan(intent: dict, df: pd.DataFrame, board: str) -> dict:
    """
    Combines hard_filters with resolved fuzzy_terms into one filter plan.
    Defensive step: if a "hard" filter's column doesn't actually exist on
    this board, re-route its value into fuzzy resolution instead of
    silently dropping the filter — makes the plan robust to LLM output
    variance rather than trusting the classification blindly.
    Returns {"filters": {column: value}, "unresolved_terms": [...]}
    """
    hard_filters = dict(intent.get("hard_filters", {}))
    fuzzy_terms = list(intent.get("fuzzy_terms", []))

    confirmed_hard = {}
    for col, val in hard_filters.items():
        if col in df.columns:
            confirmed_hard[col] = val
        else:
            fuzzy_terms.append(str(val))

    filters = dict(confirmed_hard)
    if fuzzy_terms:
        match_result = resolve_all(fuzzy_terms, df, board=board)
        for match in match_result["resolved"]:
            filters[match["matched_column"]] = match["matched_value"]
        unresolved = match_result["unresolved"]
    else:
        unresolved = []

    return {"filters": filters, "unresolved_terms": unresolved}


def apply_filters(df: pd.DataFrame, filters: dict, time_range: Optional[str], date_column: str) -> dict:
    """
    Applies column filters (case-insensitive exact match) and an optional
    date range on `date_column`. Returns the filtered df plus a caveats
    list, including a fallback if the exact time window is empty.
    """
    caveats = []
    filtered = df.copy()

    for col, val in filters.items():
        if col not in filtered.columns:
            caveats.append(f"Requested filter column '{col}' doesn't exist on this board — skipped.")
            continue
        before = len(filtered)
        filtered = filtered[filtered[col].astype(str).str.strip().str.lower() == str(val).strip().lower()]
        caveats.append(f"Filtered {col} = '{val}': {before} -> {len(filtered)} rows.")

    date_bounds = _parse_time_range(time_range)
    if time_range and date_bounds is None:
        caveats.append(f"Could not interpret time range '{time_range}' precisely — no date filter applied.")
    elif date_bounds and date_column in filtered.columns:
        start, end = date_bounds
        dates = pd.to_datetime(filtered[date_column], errors="coerce")
        in_range = filtered[(dates >= start) & (dates <= end)]

        if in_range.empty and not filtered.empty:
            latest_date = pd.to_datetime(filtered[date_column], errors="coerce").max()
            if pd.notna(latest_date):
                fallback_q = latest_date.to_period("Q")
                fb_start, fb_end = fallback_q.start_time, fallback_q.end_time
                filtered = filtered[(dates >= fb_start) & (dates <= fb_end)]
                caveats.append(
                    f"No rows fell in '{time_range}' (based on today's date). "
                    f"Showing the most recent period with data instead: {fallback_q}."
                )
            else:
                caveats.append(f"No rows fell in '{time_range}', and no valid dates found to fall back on.")
        else:
            filtered = in_range

    return {"filtered_df": filtered, "caveats": caveats}


def compute_metric(filtered_df: pd.DataFrame, metric: str, config: dict) -> dict:
    """
    Keyword-routes the free-text metric to a concrete pandas computation
    using this board's column config. Scopes to "active" rows (excludes
    each board's closed_status_values) when the metric implies that —
    e.g. "pipeline"/"open" for Deals, "ongoing"/"pending" for Work Orders.
    Always reports null-rate on the value column, and explicitly notes
    when scoping changes the row count so a $0 result comes with a reason.
    """
    metric_l = (metric or "").lower()
    status_col = config["status_column"]
    value_col = config["value_column"]
    prob_col = config["probability_column"]

    scope_df = filtered_df
    scope_note = None
    if any(kw in metric_l for kw in config["active_keywords"]) and status_col in filtered_df.columns:
        statuses = filtered_df[status_col].astype(str).str.strip().str.lower()
        scope_df = filtered_df[~statuses.isin(config["closed_status_values"])]
        if len(scope_df) != len(filtered_df):
            scope_note = (
                f"Scoped to active rows only (excluded {sorted(config['closed_status_values'])}): "
                f"{len(filtered_df)} -> {len(scope_df)} rows."
            )

    values = _to_numeric(scope_df.get(value_col, pd.Series(dtype=float)))
    null_rate = values.isna().mean() if len(values) else 0.0

    if "count" in metric_l:
        result = {"result": len(scope_df), "unit": "records", "value_column_null_rate": None}
    elif prob_col and ("weighted" in metric_l or "probable" in metric_l or "probability" in metric_l):
        probs = _to_numeric(scope_df.get(prob_col, pd.Series(dtype=float))) / 100
        weighted = (values.fillna(0) * probs.fillna(0)).sum()
        result = {"result": float(weighted), "unit": "probability-weighted value", "value_column_null_rate": round(null_rate, 3)}
    elif "average" in metric_l or "avg" in metric_l:
        avg = values.mean()
        result = {"result": float(avg) if pd.notna(avg) else None, "unit": f"average {value_col}", "value_column_null_rate": round(null_rate, 3)}
    else:
        result = {"result": float(values.sum()), "unit": f"sum of {value_col}", "value_column_null_rate": round(null_rate, 3)}

    if scope_note:
        result["scope_note"] = scope_note
    if len(scope_df) < 5:
        result["small_sample_warning"] = f"Only {len(scope_df)} records matched — treat this number as low-confidence."

    return result

def run_null_check(intent: dict, df: pd.DataFrame, board: str, null_check_term: str) -> dict:
    """
    Handles "how many X are missing Y" style questions — resolves the
    column via fuzzy matching (reusing the same resolver as normal filters,
    since founders won't say exact column names), then counts nulls/blanks.
    Applies any hard_filters/time_range first so the count is scoped
    correctly (e.g. "missing start dates in mining sector").
    """
    config = BOARD_CONFIG[board]
    plan = build_filter_plan({"hard_filters": intent.get("hard_filters", {}), "fuzzy_terms": []}, df, board)
    applied = apply_filters(df, plan["filters"], intent.get("time_range"), config["date_column"])
    scoped_df = applied["filtered_df"]

    match = resolve_column_name(null_check_term, scoped_df)
    if not match:
        return {
            "needs_clarification": True,
            "clarification_question": (
                f"I couldn't find a column matching '{null_check_term}' on the {board} board. "
                f"Could you clarify which field you mean?"
            ),
        }

    target_col = match["matched_column"]
    series = scoped_df[target_col].astype(str).str.strip()
    is_blank = series.isna() | series.eq("") | series.str.lower().eq("nan") | series.str.lower().eq("none")
    missing_count = int(is_blank.sum())

    caveats = list(applied["caveats"])
    caveats.append(f"Counted blank/null values in '{target_col}' across {len(scoped_df)} scoped rows.")
    if len(scoped_df) < 5:
        caveats.append(f"Only {len(scoped_df)} records in scope — treat this count as low-confidence.")

    return {
        "needs_clarification": False,
        "board": board,
        "filters_applied": plan["filters"],
        "row_count": len(scoped_df),
        "metric_result": {"result": missing_count, "unit": f"records missing {target_col}", "value_column_null_rate": None},
        "caveats": caveats,
    }


def run_query_plan(intent: dict, board_dfs: dict) -> dict:
    """
    Full orchestration: pick the target board -> build filter plan ->
    apply -> compute metric -> return one result dict ready for answer
    synthesis. `board_dfs` = {"Deals": deals_df, "Work Orders": wo_df}
    (only the needed one strictly has to be populated).
    """
    board = resolve_board(intent)
    df = board_dfs.get(board)

    if df is None:
        return {
            "needs_clarification": True,
            "clarification_question": f"I don't have data loaded for the '{board}' board — could you rephrase which board you mean?",
        }
    null_check_term = intent.get("null_check_column")
    if null_check_term:
        return run_null_check(intent, df, board, null_check_term)
    
    config = BOARD_CONFIG[board]
    plan = build_filter_plan(intent, df, board)

    if plan["unresolved_terms"]:
        return {
            "needs_clarification": True,
            "clarification_question": (
                f"I couldn't confidently match {plan['unresolved_terms']} to anything in the {board} data. "
                f"Could you clarify or pick from the closest categories I found?"
            ),
        }

    applied = apply_filters(df, plan["filters"], intent.get("time_range"), config["date_column"])
    metric_result = compute_metric(applied["filtered_df"], intent.get("metric", ""), config)

    caveats = list(applied["caveats"])
    if "scope_note" in metric_result:
        caveats.append(metric_result.pop("scope_note"))
    if "small_sample_warning" in metric_result:
        caveats.append(metric_result.pop("small_sample_warning"))

    return {
        "needs_clarification": False,
        "board": board,
        "filters_applied": plan["filters"],
        "row_count": len(applied["filtered_df"]),
        "metric_result": metric_result,
        "caveats": caveats,
    }


if __name__ == "__main__":
    from monday_client import get_deals_df, get_work_orders_df
    from intent_extractor import extract_intent

    board_dfs = {"Deals": get_deals_df(), "Work Orders": get_work_orders_df()}

    for q in [
        "How's our pipeline looking for energy sector this quarter?",
        "How many work orders are ongoing in the mining sector?",
    ]:
        intent = extract_intent(q)
        result = run_query_plan(intent, board_dfs)
        import json
        print(f"\n=== {q} ===")
        print(json.dumps(result, indent=2, default=str))