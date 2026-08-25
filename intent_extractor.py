"""
Intent extraction — splits a founder's natural-language question into
hard filters (stated exactly) and fuzzy terms (need embedding resolution
downstream). Uses Groq's hosted Llama so the whole app is deployable
without a local model server (see Decision Log re: Ollama vs hosted).
"""
import os
import json

from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Check Groq's current model list before deploying — hosted model names
# change over time. An 8B/70B Llama instruction-tuned model works well here;
# override with GROQ_MODEL if the default below is deprecated.
MODEL_NAME = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

SYSTEM_PROMPT = """You are an intent-extraction module for a business intelligence agent \
over two monday.com boards: "Deals" (sales pipeline) and "Work Orders" (project execution).

Given a founder's question, return ONLY a JSON object with this exact shape:
{
  "metric": "<what they want to know, e.g. 'pipeline value', 'deal count', 'completion rate'>",
  "boards": ["Deals" and/or "Work Orders"],
  "time_range": "<explicit period if stated, else null>",
  "hard_filters": {"<column-like term>": "<exact value as stated>"},
  "fuzzy_terms": ["<ambiguous phrase 1>", "<ambiguous phrase 2>"],
  "null_check_column": "<column-like term if the question asks about missing/blank/null values in a specific field, else null>",
  "needs_clarification": false,
  "clarification_question": null
}

Rules:
- hard_filters: only include values the user stated precisely (an exact quarter, an exact status word).
- fuzzy_terms: fuzzy_terms should catch sector/stage/status/region/client-name references by default
- null_check_column: set this when the question asks "how many X are missing Y" or "which records don't have Z" \
  — put the column-like term for Y/Z here (e.g. "start date", "owner"), NOT in fuzzy_terms or hard_filters.
- If the question is too vague to act on (no metric, no scope), set needs_clarification true and write \
  a single short clarification_question instead of guessing.
- Return nothing but the JSON object. No prose, no markdown fences.
"""


def extract_intent(user_query: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "needs_clarification": True,
            "clarification_question": "I couldn't parse that question — could you rephrase it?",
        }


if __name__ == "__main__":
    test_q = "How's our pipeline looking for energy sector this quarter?"
    print(json.dumps(extract_intent(test_q), indent=2))