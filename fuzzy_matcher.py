"""
Fuzzy term resolution — takes the fuzzy_terms list from intent_extractor.py
and matches each one against the REAL unique values in your monday.com
boards (pulled via monday_client.py), not guessed column names.

This is what turns "energy sector" into either a real match ("Mining"?
no) or a clean "that's not a category we track" signal — instead of
silently filtering on a string that doesn't exist and returning zero
rows with no explanation.
"""
import os
from typing import Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

MODEL = SentenceTransformer("all-MiniLM-L6-v2")  # same model used in Nomos

# Columns worth fuzzy-matching against, per board. Adjust to your real
# column names — run deals.columns.tolist() / work_orders.columns.tolist()
# to confirm these first.
CATEGORICAL_COLUMNS = {
    "Deals": ["Sector/service", "Deal Stage", "Deal Status", "Product deal"],
    "Work Orders": ["Sector", "Execution Status", "Type of Work", "Nature of Work", "Document Type"],
}

MATCH_THRESHOLD = 0.45  # cosine similarity; below this -> no confident match


def build_value_pool(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Returns a DataFrame of (column, value) pairs — every unique, non-null
    value seen in the given categorical columns. This is the pool fuzzy
    terms get matched against.
    """
    rows = []
    for col in columns:
        if col not in df.columns:
            continue
        for val in df[col].dropna().unique():
            val = str(val).strip()
            # Skip empty strings and rows where the value is just the
            # column header leaking in (a real data-quality issue we saw
            # in the Deals board — document this in the Decision Log).
            if val and val.lower() != col.lower():
                rows.append({"column": col, "value": val})
    return pd.DataFrame(rows).drop_duplicates()


def resolve_fuzzy_term(term: str, value_pool: pd.DataFrame, top_k: int = 3) -> Optional[dict]:
    """
    Embeds `term` and every value in value_pool, returns the best match
    plus the top_k candidates (for visibility/debugging) — or None if
    nothing clears MATCH_THRESHOLD.
    """
    if value_pool.empty:
        return None

    term_emb = MODEL.encode([term])[0]
    value_embs = MODEL.encode(value_pool["value"].tolist())

    # cosine similarity
    sims = value_embs @ term_emb / (
        np.linalg.norm(value_embs, axis=1) * np.linalg.norm(term_emb) + 1e-8
    )
    ranked_idx = np.argsort(sims)[::-1][:top_k]
    candidates = [
        {
            "column": value_pool.iloc[i]["column"],
            "value": value_pool.iloc[i]["value"],
            "score": round(float(sims[i]), 3),
        }
        for i in ranked_idx
    ]

    best = candidates[0]
    if best["score"] < MATCH_THRESHOLD:
        return None

    return {
        "term": term,
        "matched_column": best["column"],
        "matched_value": best["value"],
        "score": best["score"],
        "candidates": candidates,
    }

def resolve_column_name(term: str, df: pd.DataFrame, top_k: int = 3) -> Optional[dict]:
    """
    Matches a free-text term (e.g. "start date") against this board's
    actual COLUMN NAMES — not cell values. Used for null-check queries
    like "missing start dates", where the term refers to a field, not
    a category. Deliberately separate from resolve_fuzzy_term, which
    matches against values and would never find a column name since
    CATEGORICAL_COLUMNS only lists categorical fields, not every column.
    """
    columns = list(df.columns)
    if not columns:
        return None

    term_emb = MODEL.encode([term])[0]
    col_embs = MODEL.encode(columns)
    sims = col_embs @ term_emb / (
        np.linalg.norm(col_embs, axis=1) * np.linalg.norm(term_emb) + 1e-8
    )
    ranked_idx = np.argsort(sims)[::-1][:top_k]
    candidates = [
        {"column": columns[i], "score": round(float(sims[i]), 3)}
        for i in ranked_idx
    ]
    best = candidates[0]
    if best["score"] < MATCH_THRESHOLD:
        return None
    return {"term": term, "matched_column": best["column"], "score": best["score"], "candidates": candidates}


def resolve_all(fuzzy_terms: list[str], df: pd.DataFrame, board: str) -> dict:
    """
    Resolves every fuzzy term for a given board's DataFrame.
    Returns {"resolved": [...], "unresolved": [...]} — unresolved terms
    are exactly what should trigger a clarification question upstream.
    """
    columns = CATEGORICAL_COLUMNS.get(board, [])
    value_pool = build_value_pool(df, columns)

    resolved, unresolved = [], []
    for term in fuzzy_terms:
        match = resolve_fuzzy_term(term, value_pool)
        if match:
            resolved.append(match)
        else:
            unresolved.append(term)

    return {"resolved": resolved, "unresolved": unresolved}


if __name__ == "__main__":
    from monday_client import get_deals_df

    deals = get_deals_df()
    result = resolve_all(["energy sector"], deals, "Deals")
    print(result)
    print("\nActual Sector/service values in your data:")
    print(deals["Sector/service"].dropna().unique())