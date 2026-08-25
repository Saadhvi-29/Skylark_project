Skylark BI Agent
A conversational business-intelligence agent that answers founder-level questions over two live monday.com boards — Deals (sales pipeline) and Work Orders (project execution) — with no cached or hardcoded data. Every query hits the monday.com GraphQL API directly.
Live app: [https://skylarkproject-c2lhfvckmqfzpvpde7pfm8.streamlit.app]

Architecture Overview
User question (Streamlit chat)
        │
        ▼
intent_extractor.py   — LLM (Groq/Llama) turns free text into structured intent JSON:
                         metric, target board(s), time range, hard filters, fuzzy terms,
                         null-check column, or a clarification request.
        │
        ▼
query_planner.py      — Deterministic logic (pandas, no LLM) that:
                         • resolves which board to query
                         • builds a concrete filter plan from intent
                         • applies filters + time-range logic (with fallback if a
                           period has no data)
                         • computes the requested metric (sum / count / average /
                           probability-weighted / null-count)
                         • attaches explicit data-quality caveats to every result
        │
        ▼
fuzzy_matcher.py       — Resolves ambiguous free-text terms two ways:
                         • resolve_fuzzy_term(): matches a term against real
                           categorical VALUES in the data (e.g. "energy" → "Energy"
                           in Sector), using sentence-transformer embeddings + cosine
                           similarity, so filters are validated against what's
                           actually in the sheet — never guessed.
                         • resolve_column_name(): matches a term against actual
                           COLUMN NAMES, used for "missing X" / null-check queries.
        │
        ▼
monday_client.py       — Data layer. Pulls all items from a board via the
                         monday.com GraphQL API (paginated), flattens into a
                         pandas DataFrame keyed by column title, and cleans a
                         known import artifact (stray header values leaking into
                         cells) at the source.
        │
        ▼
agent.py                — Orchestrator + answer synthesis. Chains the above steps,
                         then calls the LLM one more time to turn the computed
                         JSON payload into a founder-facing answer — the LLM only
                         narrates numbers that are already computed; it never
                         calculates anything itself.
        │
        ▼
streamlit_app.py        — Chat UI. Bridges Streamlit Cloud secrets into env vars,
                         renders conversation history, and exposes a "Leadership
                         update mode" toggle that reformats answers as short
                         bullet points instead of prose.

Design principle: the LLM is used only for (1) turning natural language into structured intent, and (2) turning structured results back into natural language. All filtering, aggregation, and math is done in plain pandas — this keeps every number traceable and auditable, and means the agent can never "hallucinate" a statistic.
Files
File
Responsibility
streamlit_app.py
Chat UI, entrypoint for the deployed app
agent.py
Top-level orchestration + answer synthesis (LLM call #2)
intent_extractor.py
Natural language → structured intent JSON (LLM call #1)
query_planner.py
Filter/metric execution logic (pandas, deterministic)
fuzzy_matcher.py
Semantic matching of free-text terms to real column names/values
monday_client.py
monday.com GraphQL API client + DataFrame construction
requirements.txt
Python dependencies


Tech Stack
Frontend: Streamlit (chat interface, session state, sidebar controls)
LLM: Groq-hosted Llama (openai/gpt-oss-20b by default, overridable via GROQ_MODEL) — chosen over a locally-hosted model so the app has no local-inference dependency and can run fully on Streamlit Cloud
Data layer: monday.com GraphQL API v2, queried live via requests — no CSV or cached data
Data processing: pandas
Semantic matching: sentence-transformers (all-MiniLM-L6-v2) for fuzzy term/column resolution
See the Decision Log for the reasoning behind these choices.
monday.com Setup
This project expects one workspace with two boards:
Deals — imported from the Deal Funnel CSV/XLSX
Work Orders — imported from the Work Order Tracker CSV/XLSX
Import steps:
In monday.com, create a new board for each dataset and import the corresponding file directly (Board → Import → CSV/Excel).
I manually set the data type for each column (text, status, date, number) from the source data — no manual cleaning or null-handling was done at import time, so the agent is tested against the data's real messiness (missing values, inconsistent formatting) rather than pre-cleaned data.
Note each board's Board ID from its URL: https://rvu636908.monday.com/boards/5030844104
https://rvu636908.monday.com/boards/5030843285.
Generate a personal API token: your avatar → Developers → My Access Tokens.


Environment Variables

DEALS_BOARD_ID - 5030843285
WORK_ORDERS_BOARD_ID - 5030844104
GROQ_MODEL - openai/gpt-oss-20b


Running Locally
git clone https://github.com/Saadhvi-29/Skylark_project.git
cd Skylark_project
pip install -r requirements.txt

Set environment variables (PowerShell example):
$env:MONDAY_API_KEY="your_token"
$env:DEALS_BOARD_ID="your_deals_board_id"
$env:WORK_ORDERS_BOARD_ID="your_work_orders_board_id"
$env:GROQ_API_KEY="your_groq_key"

Run the app:
streamlit run streamlit_app.py


Deploying (Streamlit Community Cloud)
Push this repo to GitHub.
Go to share.streamlit.io → Create app → deploy from this repo, main file streamlit_app.py.
Under Advanced settings → Secrets, add the four environment variables above in TOML format.
Deploy. Streamlit Cloud auto-redeploys on every push to main.

Known Limitations
Each query targets a single board; true cross-board comparison queries aren't supported yet.
Metric routing is keyword-based on free text rather than a fixed enum — see the Decision Log for reasoning.
No caching layer — every query is a live monday.com API round-trip.

