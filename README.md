# Skylark Agent

> A conversational business-intelligence agent that answers founder-level questions over **live monday.com Deals and Work Orders boards** using real-time data from the monday.com GraphQL API.

**Live App:** [Skylark Agent](https://skylarkproject-c2lhfvckmqfzpvpde7pfm8.streamlit.app?utm_source=chatgpt.com)
**Repository:** [GitHub Repository]([https://github.com/Saadhvi-29/Skylark_project.git](https://github.com/Saadhvi-29/Skylark_project))

---

## Overview

**Skylark Agent** is a conversational BI system designed to answer business and operational questions using live data stored in monday.com.

Instead of relying on a static CSV, database snapshot, or pre-computed metrics, every user query retrieves the latest data directly from the monday.com GraphQL API.

The system is designed around a key principle:

> **The LLM understands and communicates; deterministic Python code retrieves, filters, aggregates, and calculates.**

This ensures that numerical answers are **traceable, reproducible, and auditable**, while minimizing the possibility of LLM-generated statistical hallucinations.

The agent currently works with two monday.com boards:

* **Deals** — sales pipeline and deal information
* **Work Orders** — project execution and operational information

---

## Key Features

* Conversational founder-level BI interface
* Live monday.com data retrieval
* Natural-language query understanding
* Deterministic pandas-based calculations
* LLM-powered intent extraction
* Semantic fuzzy matching for columns and categorical values
* Explicit data-quality caveats
* No hardcoded business metrics
* No cached analytical results
* Supports sum, count, average, probability-weighted metrics, and null counts
* Time-range filtering with fallback handling
* Streamlit chat interface
* Leadership Update mode for concise executive summaries
* Deployable on Streamlit Community Cloud

---

# Architecture

```text
                         ┌──────────────────────┐
                         │   Streamlit Chat UI  │
                         │  streamlit_app.py    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  Intent Extraction   │
                         │ intent_extractor.py  │
                         │                      │
                         │ LLM: Groq / Llama    │
                         └──────────┬───────────┘
                                    │
                           Structured Intent JSON
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Query Planner     │
                         │  query_planner.py    │
                         │                      │
                         │ Deterministic pandas │
                         └──────────┬───────────┘
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                         ▼                     ▼
                ┌─────────────────┐   ┌──────────────────┐
                │ Fuzzy Matcher   │   │  Monday Client   │
                │fuzzy_matcher.py │   │ monday_client.py │
                │                 │   │                  │
                │ Values / Column │   │ GraphQL API      │
                │ Resolution      │   │ Live Retrieval   │
                └─────────────────┘   └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │ monday.com Boards │
                                      │                  │
                                      │ Deals             │
                                      │ Work Orders       │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      Pandas DataFrame
                                               │
                                               ▼
                                    Deterministic Metric
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │      Agent       │
                                      │    agent.py      │
                                      │                  │
                                      │ Answer Synthesis │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      Founder-facing Answer
```

---

# Query Flow

A typical query goes through the following pipeline:

### 1. User asks a question

Example:

```text
How much is the weighted pipeline for energy-sector deals?
```

The question is entered through the Streamlit chat interface.

### 2. Intent extraction

`intent_extractor.py` sends the natural-language question to the LLM.

The LLM converts the question into structured intent containing information such as:

* Requested metric
* Target board
* Time range
* Hard filters
* Fuzzy terms
* Null-check column
* Clarification requirements

The LLM **does not calculate the answer**.

### 3. Query planning

`query_planner.py` receives the structured intent and deterministically:

1. Resolves the target board.
2. Builds the required filter plan.
3. Applies categorical filters.
4. Applies time-range filters.
5. Handles empty periods using the configured fallback logic.
6. Calculates the requested metric.
7. Generates data-quality caveats.

All numerical computation happens using pandas.

### 4. Fuzzy term resolution

`fuzzy_matcher.py` handles ambiguous terms.

For example:

```text
energy
```

may be matched against actual values in the dataset:

```text
Energy
```

The matcher uses:

* `all-MiniLM-L6-v2`
* Sentence embeddings
* Cosine similarity

This means the system resolves user language against **values that actually exist in the live dataset**, rather than inventing or guessing categories.

Column names can also be resolved.

For example:

```text
Which deals are missing a close date?
```

can resolve:

```text
close date
```

against the actual column names in the board.

### 5. Live monday.com retrieval

`monday_client.py` queries the monday.com GraphQL API.

The client:

* Retrieves board items
* Handles API pagination
* Extracts column values
* Flattens the response into a pandas DataFrame
* Uses column titles as DataFrame keys
* Cleans known import artifacts at the data-source layer

There is no CSV or cached analytical dataset used at query time.

### 6. Deterministic calculation

The query planner calculates the requested metric.

Supported calculations include:

* Sum
* Count
* Average
* Probability-weighted value
* Null/missing-value count

For example:

```text
Weighted Pipeline =
Σ (Deal Value × Closure Probability)
```

The calculation is performed by Python/pandas rather than the LLM.

### 7. Answer synthesis

`agent.py` sends the computed result to the LLM for final response generation.

At this stage, the LLM is only responsible for turning structured results into a readable founder-facing answer.

It does **not** recalculate or invent the statistics.

---

# Project Structure

```text
Skylark_project/
│
├── streamlit_app.py
│   └── Streamlit chat UI and application entrypoint
│
├── agent.py
│   └── Top-level orchestration and final answer synthesis
│
├── intent_extractor.py
│   └── Natural language → structured intent JSON
│
├── query_planner.py
│   └── Deterministic filtering, aggregation and metric calculation
│
├── fuzzy_matcher.py
│   └── Semantic matching of user terms to real columns and values
│
├── monday_client.py
│   └── monday.com GraphQL API client and DataFrame construction
│
├── requirements.txt
│   └── Python dependencies
│
└── README.md
    └── Project documentation
```

---

# Technology Stack

| Component         | Technology                | Purpose                                 |
| ----------------- | ------------------------- | --------------------------------------- |
| Frontend          | Streamlit                 | Conversational BI interface             |
| LLM               | Groq + Llama / GPT-OSS    | Intent extraction and answer synthesis  |
| API               | monday.com GraphQL API v2 | Live business data retrieval            |
| Data Processing   | pandas                    | Filtering, aggregation and calculations |
| Semantic Matching | Sentence Transformers     | Fuzzy column/value resolution           |
| Embedding Model   | `all-MiniLM-L6-v2`        | Semantic similarity                     |
| Deployment        | Streamlit Community Cloud | Cloud deployment                        |
| Language          | Python                    | Application implementation              |

---

# LLM Design

The LLM is deliberately restricted to two responsibilities.

## LLM Call #1 — Intent Extraction

```text
Natural Language Question
          ↓
       LLM
          ↓
Structured Intent JSON
```

For example:

```json
{
  "metric": "probability_weighted_value",
  "board": "Deals",
  "filters": {
    "sector": "Energy"
  },
  "time_range": null
}
```

The output is then interpreted by deterministic Python logic.

---

## LLM Call #2 — Answer Synthesis

```text
Computed Result JSON
        ↓
       LLM
        ↓
Founder-facing Answer
```

The LLM receives already-computed values and formats them into a natural-language response.

This separation ensures:

> **LLM for language. Python for logic and mathematics.**

---

# monday.com Setup

The project expects a monday.com workspace containing two boards.

## 1. Deals Board

The Deals board should be imported from the provided Deal Funnel CSV/XLSX dataset.

## 2. Work Orders Board

The Work Orders board should be imported from the provided Work Order Tracker CSV/XLSX dataset.

### Importing the datasets

In monday.com:

```text
Board
  ↓
Import
  ↓
CSV / Excel
  ↓
Select dataset
  ↓
Create board
```

Column data types should then be set appropriately:

* Text
* Status
* Date
* Number

### Important

The datasets are intentionally **not manually cleaned** before being queried.

This allows the BI agent to operate against realistic business data containing:

* Missing values
* Inconsistent formatting
* Import artifacts
* Incomplete fields

The agent is therefore evaluated on the actual messiness of the source data rather than a manually cleaned version.

---

# Board IDs

Configure the two boards using their monday.com Board IDs.

```text
DEALS_BOARD_ID=5030843285
WORK_ORDERS_BOARD_ID=5030844104
```

The Board ID can be obtained from the board URL.

---

# monday.com API Token

Generate a personal monday.com API token from:

```text
Avatar
  ↓
Developers
  ↓
My Access Tokens
```

The token is required for the application to query the GraphQL API.

**Do not commit the API token to GitHub.**

---

# Environment Variables

The application requires the following environment variables:

```text
MONDAY_API_KEY
DEALS_BOARD_ID
WORK_ORDERS_BOARD_ID
GROQ_API_KEY
GROQ_MODEL
```

Example:

```text
MONDAY_API_KEY=your_monday_token
DEALS_BOARD_ID=5030843285
WORK_ORDERS_BOARD_ID=5030844104
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

`GROQ_MODEL` can be changed to another supported Groq model if required.

---

# Running Locally

## 1. Clone the repository

```bash
git clone https://github.com/Saadhvi-29/Skylark_project.git
cd Skylark_project
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Configure environment variables

### PowerShell

```powershell
$env:MONDAY_API_KEY="your_token"
$env:DEALS_BOARD_ID="your_deals_board_id"
$env:WORK_ORDERS_BOARD_ID="your_work_orders_board_id"
$env:GROQ_API_KEY="your_groq_key"
$env:GROQ_MODEL="openai/gpt-oss-20b"
```

### Linux / macOS

```bash
export MONDAY_API_KEY="your_token"
export DEALS_BOARD_ID="your_deals_board_id"
export WORK_ORDERS_BOARD_ID="your_work_orders_board_id"
export GROQ_API_KEY="your_groq_key"
export GROQ_MODEL="openai/gpt-oss-20b"
```

## 4. Start Streamlit

```bash
streamlit run streamlit_app.py
```

The application will then be available through the local Streamlit URL displayed in the terminal.

---

# Streamlit Cloud Deployment

The application can be deployed using **Streamlit Community Cloud**.

## Steps

### 1. Push the repository to GitHub

Ensure the repository contains:

```text
streamlit_app.py
requirements.txt
agent.py
intent_extractor.py
query_planner.py
fuzzy_matcher.py
monday_client.py
```

### 2. Create the Streamlit application

Open Streamlit Community Cloud and select:

```text
Create app
```

Choose:

* GitHub repository
* Branch: `main`
* Main file: `streamlit_app.py`

### 3. Configure secrets

Under:

```text
Advanced settings → Secrets
```

add:

```toml
MONDAY_API_KEY = "your_monday_token"
DEALS_BOARD_ID = "your_deals_board_id"
WORK_ORDERS_BOARD_ID = "your_work_orders_board_id"
GROQ_API_KEY = "your_groq_key"
GROQ_MODEL = "openai/gpt-oss-20b"
```

### 4. Deploy

Streamlit Cloud installs the dependencies from `requirements.txt` and launches the application.

Future pushes to the `main` branch can trigger automatic redeployment.

---

# Leadership Update Mode

The Streamlit interface includes a **Leadership Update Mode** toggle.

### Normal mode

Produces a conversational founder-facing response.

### Leadership Update mode

Reformats the same computed result into concise executive bullet points.

For example:

```text
• Weighted pipeline: ₹X Cr
• Active deals: XX
• Highest contribution: Energy sector
• Data caveat: X deals have missing probability values
```

The underlying calculation remains unchanged.

Only the presentation format changes.

---

# Data Quality

A major design goal of Skylark is to make data quality visible rather than silently hiding it.

Every result can include explicit caveats relating to issues such as:

* Missing values
* Invalid dates
* Missing probabilities
* Empty filter results
* Inconsistent categorical values
* Import artifacts

For example:

```text
Weighted pipeline: ₹12.4 Cr

Data quality note:
3 deals have missing closure probabilities and were excluded
from the probability-weighted calculation.
```

This makes the output more useful for decision-making and auditing.

---

# Why No Cached Data?

Skylark intentionally does not maintain a cached analytical dataset.

For every user query:

```text
User Question
     ↓
Intent Extraction
     ↓
monday.com GraphQL API
     ↓
Latest Board Data
     ↓
Pandas Calculation
     ↓
Answer
```

This ensures that the agent operates on the **current state of the monday.com boards**.

The trade-off is that every query requires a live API round trip.

---

# Why Deterministic Pandas?

A conventional LLM-based BI system could ask an LLM to interpret data and perform calculations.

That creates a risk of:

* Arithmetic errors
* Hallucinated values
* Incorrect filtering
* Inconsistent calculations
* Poor auditability

Skylark instead uses:

```text
LLM
↓
"What does the user want?"

Python
↓
"Filter the actual data and calculate it."

LLM
↓
"Explain the computed result."
```

This separation provides a much clearer audit trail.

---

# Fuzzy Matching

Natural-language business questions rarely use exactly the same terminology as the dataset.

For example:

```text
Show me energy deals
```

The dataset may contain:

```text
Energy
```

`fuzzy_matcher.py` uses sentence-transformer embeddings and cosine similarity to resolve the user's term against actual categorical values.

Similarly:

```text
Which deals are missing their close date?
```

can resolve:

```text
close date
```

against the real column names.

This prevents the system from inventing categories or column names that do not exist in the source data.

---

# Security and Privacy Considerations

The application uses external services for:

* monday.com API access
* Groq-hosted LLM inference

The application does **not** require a locally hosted LLM.

API credentials should be stored using environment variables or Streamlit Secrets rather than committed to source control.

Never commit:

```text
MONDAY_API_KEY
GROQ_API_KEY
```

to the repository.

---

# Design Decisions

The architecture intentionally separates language understanding from business logic.

| Responsibility               | Component             | Approach                       |
| ---------------------------- | --------------------- | ------------------------------ |
| Understand user question     | `intent_extractor.py` | LLM                            |
| Resolve board                | `query_planner.py`    | Deterministic                  |
| Resolve fuzzy values         | `fuzzy_matcher.py`    | Embeddings + cosine similarity |
| Resolve columns              | `fuzzy_matcher.py`    | Semantic matching              |
| Retrieve data                | `monday_client.py`    | monday.com GraphQL             |
| Filter data                  | `query_planner.py`    | pandas                         |
| Calculate metrics            | `query_planner.py`    | pandas                         |
| Identify data-quality issues | `query_planner.py`    | Deterministic                  |
| Generate final response      | `agent.py`            | LLM                            |
| Display results              | `streamlit_app.py`    | Streamlit                      |

---

# Limitations

### Single-board queries

Currently, each query targets a single board.

True cross-board analytical questions such as:

```text
Compare the Deals pipeline with Work Order execution.
```

are not yet supported.

### Keyword-based metric routing

Metric routing currently relies on keyword-based logic rather than a strict metric enum.

### No caching

Every query makes a live monday.com API request.

This provides fresh data but introduces API latency and dependency on monday.com's availability.

### Fuzzy matching limitations

Semantic matching improves natural-language flexibility but can still produce ambiguous matches when categorical values are very similar.

---

# Future Improvements

Potential future enhancements include:

* Cross-board analytical queries
* More sophisticated metric routing
* Automatic anomaly detection
* Trend and time-series analysis
* Founder dashboards
* Visualization generation
* Query history and saved questions
* More advanced data-quality profiling
* Role-based access control
* Additional monday.com boards
* Automated KPI monitoring
* Alerting for pipeline or execution anomalies

---

# Example Questions

The agent is designed to answer questions such as:

```text
What is the total value of the current sales pipeline?

How much is the probability-weighted pipeline?

How many deals are currently open?

What is the average deal value?

How many deals are missing a closure probability?

Show me deals in the energy sector.

What is the pipeline for deals closing this month?

How many work orders are currently active?

How many work orders have missing completion dates?

Give me a leadership update on the current pipeline.
```

---

# Core Design Principle

Skylark follows a simple architectural rule:

```text
┌─────────────────────────────────────────┐
│                  LLM                    │
│                                         │
│  Understand language → Explain results  │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│           DETERMINISTIC LAYER           │
│                                         │
│  Retrieve → Filter → Aggregate → Math   │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│             monday.com                  │
│                                         │
│          Live business data             │
└─────────────────────────────────────────┘
```

**The LLM never becomes the source of truth for the numbers.**

The monday.com boards are the source of truth, and pandas performs the calculations.

---

# License

This project is intended as a project/assignment implementation for demonstrating a live conversational BI architecture using monday.com, LLMs, deterministic data processing, and Streamlit.
