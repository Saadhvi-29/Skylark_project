"""
Answer synthesis + top-level orchestrator.

`answer()` is the single entrypoint your conversational interface (step 7)
should call: user question in, founder-facing text out. It chains
intent_extractor -> query_planner -> this synthesis step, and only fetches
whichever board the question actually needs.

Key rule: the LLM only narrates numbers that are already in the payload.
It never computes anything — that's query_planner's job.
"""
import json
import os

from groq import Groq

from monday_client import get_deals_df, get_work_orders_df
from intent_extractor import extract_intent
from query_planner import run_query_plan, resolve_board

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL_NAME = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

SYNTHESIS_SYSTEM_PROMPT = """You are a business intelligence assistant summarizing monday.com data \
for a founder, across two boards: "Deals" (sales pipeline) and "Work Orders" (project execution). \
You will be given a JSON payload with a computed metric, the filters that were applied, and \
data-quality caveats.

Rules:
- Use ONLY the numbers in the payload. Never compute, estimate, or invent a number that isn't there.
- Lead with the direct answer to the founder's question in one sentence.
- Then give brief context: what was filtered, and any caveats that affect how much to trust the number \
  (small sample size, fallback time period used, excluded closed records, etc). Don't hide caveats — a \
  founder needs to know when a number is low-confidence.
- Keep it tight: 3-5 sentences for a normal answer. No headers, no bullet lists unless leadership_update \
  mode is on.
- If leadership_update mode is on: format as 2-3 short bullet points suitable for pasting into a status \
  update, still fully grounded in the payload, still surfacing caveats.
"""


def synthesize_answer(user_query: str, plan_result: dict, leadership_update: bool = False) -> str:
    if plan_result.get("needs_clarification"):
        return plan_result["clarification_question"]

    mode_note = "leadership_update mode: ON — format as bullets." if leadership_update else "leadership_update mode: OFF."
    payload = json.dumps(plan_result, default=str)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user", "content": f"Founder's question: {user_query}\n{mode_note}\nComputed payload:\n{payload}"},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


def answer(user_query: str, leadership_update: bool = False) -> str:
    """
    Full pipeline, single call: extracts intent first (to know which board
    is needed), pulls only that board's live data, runs the query plan,
    and returns the founder-facing answer text.
    """
    intent = extract_intent(user_query)

    if intent.get("needs_clarification"):
        return intent["clarification_question"]

    board = resolve_board(intent)
    if board == "Work Orders":
        board_dfs = {"Work Orders": get_work_orders_df()}
    else:
        board_dfs = {"Deals": get_deals_df()}

    plan_result = run_query_plan(intent, board_dfs)
    return synthesize_answer(user_query, plan_result, leadership_update)


if __name__ == "__main__":
    print(answer("How's our pipeline looking for energy sector this quarter?"))
    print()
    print(answer("How many work orders are ongoing in the mining sector?"))