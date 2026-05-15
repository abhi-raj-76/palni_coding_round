# Business Request Intake — AI Workflow

A small web application that automates **first-level intake** for inbound business requests (emails, tickets, portal messages). It classifies the request, pulls out structured details, checks quality and risk, and suggests **who should handle it next** — with guardrails so automation does not run blindly on messy or adversarial input.

---

## The problem (why this exists)

Teams constantly receive messages such as refund disputes, invoice questions, access issues, or contract reviews. A human normally has to:

1. Read the whole thread  
2. Decide what kind of request it is  
3. Copy out names, IDs, amounts, dates, and contact details  
4. Judge whether anything important is missing or inconsistent  
5. Decide urgency and whether Legal, Finance, or Support should own it  

That work is repetitive, easy to do inconsistently across people, and **risky** if someone misses fraud patterns, contradictions, or “prompt injection” style text buried in the email.

This project **models that first pass** in software: one place to paste the request, one structured outcome for routing and audit — with a **real local LLM** for understanding and extraction, and **deterministic rules** for policy-style checks (priority thresholds, validation, escalation).

---

## What the application does

1. **You** paste the full request text (subject + body).  
2. The **LLM (Ollama)** returns strict JSON: request type, confidence, short summary, sentiment, contradiction hint, and structured fields (customer, company, IDs, amounts, email, issue description, etc.) — with instructions **not to invent** values that are not in the text.  
3. A **rules engine** layers on: priority (HIGH / MEDIUM / LOW), risk level and reasons, email/amount checks, missing critical fields, prompt-injection / suspicious patterns, contradiction checks, whether **human review** is required, suggested information to ask the customer for, recommended next action, and recommended **escalation department**.  
4. The **UI** shows the outcome; the same payload is available via **HTTP API** for integration tests or other systems.

---

## Tech stack

| Layer | Technology |
|--------|------------|
| **Language** | Python 3.11+ |
| **Web framework** | [FastAPI](https://fastapi.tiangolo.com/) |
| **Server** | [Uvicorn](https://www.uvicorn.org/) (ASGI) |
| **HTTP client** | [httpx](https://www.python-httpx.org/) (async calls to Ollama) |
| **Config** | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) + [python-dotenv](https://pypi.org/project/python-dotenv/) (`.env`) |
| **LLM** | [Ollama](https://ollama.com/) local API (`/api/chat`, JSON mode) — **no API keys** in the app by default |
| **Frontend** | Static HTML, CSS, and vanilla JavaScript (no React/Angular build step) |

---

## Repository layout

```
assessment_palni/
├── app/
│   ├── main.py              # FastAPI routes, static files, lifespan
│   ├── config.py            # Settings from environment
│   ├── ollama_client.py     # Ollama HTTP + model auto-pick if missing
│   └── workflow/
│       ├── pipeline.py      # Wires LLM → rules → response
│       ├── llm_intake.py    # Single structured LLM call
│       └── rules_engine.py  # Priority, risk, validation, escalation, etc.
├── static/
│   ├── index.html
│   └── style.css
├── requirements.txt
├── .env.example
└── README.md
```

---

## Features

### Baseline (assignment-aligned)

- **Simple UI**: paste text, submit, read structured outcome.  
- **Real LLM usage**: classification and field extraction are performed in **one** Ollama JSON response (strict schema).  
- **Separated workflow steps**: `llm_intake.py` vs `rules_engine.py` vs `pipeline.py`.  
- **Structured JSON** response from `POST /api/run`.  
- **Basic error handling**: connection/model errors surface as HTTP 502 with a readable `detail` message.  
- **Secrets**: no keys in code; use `.env` (see `.env.example`).

### Extra capabilities (beyond minimal classify/extract)

| Feature | Where it lives | What it does |
|--------|----------------|--------------|
| **Professional summary** | LLM | Short factual summary of the request. |
| **Classification confidence** | LLM (0–100) | Used with rules to drive human review. |
| **Sentiment** | LLM + light rule | Positive / Neutral / Negative / Angry-Urgent; urgent wording can bump neutral model output. |
| **Priority** | Rules | HIGH for urgent language or large refund amounts (over 50,000 in detected currency units); MEDIUM when critical fields missing; LOW for generic cases. |
| **Risk assessment** | Rules | Combines financial / legal / fraud-suspicion / missing-info style reasons into `risk_level` and `risk_reason`. |
| **Human review flag** | Rules | True when confidence is low, validation fails, contradictions, suspicious patterns, or prompt-injection phrases are detected. |
| **Contradiction detection** | LLM + rules | Model flag plus regex/heuristic checks (e.g. conflicting refund vs failure language; diverging large amounts in text). |
| **Validation engine** | Rules | Critical missing fields by request type; email format; numeric amount sanity; cross-check that invoice/payment strings appear in the original text when provided. |
| **Prompt injection handling** | Rules + LLM system prompt | Known manipulation phrases set suspicious / human review; system prompt tells the model to ignore embedded “override” instructions. |
| **Escalation recommendation** | Rules | Suggests **Finance**, **Legal**, **Technical Support**, or **Customer Success** and whether escalation is required. |
| **Missing information suggestions** | Rules | Concrete bullets for what to ask the customer next. |
| **Suspicious / duplicate patterns** | Rules | Very high amounts, repeated reference tokens, injection-like content. |
| **Issue description fallback** | LLM prompt + code | If the model omits `issue_description`, a substantive line from the email (keywords, not fabricated) is used. |
| **Ollama model fallback** | `ollama_client.py` | If `OLLAMA_MODEL` is not installed, the first model from `ollama list` is used and a warning is logged. |

---

## Prerequisites

- **Python 3.11+**  
- **Ollama** installed and running locally, with at least one model pulled (`ollama pull …`). Larger models usually follow the JSON contract more reliably than very small ones.

---

## Setup

**Windows (PowerShell)**

```powershell
cd path\to\assessment_palni
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux**

```bash
cd assessment_palni
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Environment variables (`.env`)

| Variable | Meaning |
|----------|---------|
| `OLLAMA_BASE_URL` | Ollama HTTP base URL (default `http://127.0.0.1:11434`) |
| `OLLAMA_MODEL` | Model name exactly as in `ollama list`. If that name is **not** installed, the app picks the **first** reported model and logs a warning. |

Do **not** commit `.env` or put API keys in the repository. This project targets **local Ollama** by default.

---

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in a browser, paste a request, and click **Run workflow**.

---

## API

**`POST /api/run`**

- **Body:** `{ "text": "<full request, 5–50000 chars>" }`  
- **Success:** `200` with a JSON document containing (among others):

  - `request_type`, `confidence_score`, `summary`, `sentiment`  
  - `priority`, `risk_level`, `risk_reason`  
  - `human_review_required`, `contradiction_detected`, `suspicious_request`  
  - `extracted_information` (nested object)  
  - `validation` (`status`, `missing_fields`, `validation_issues`, `suggested_information_to_collect`)  
  - `recommended_action`  
  - `escalation_recommendation` (`required`, `department`)  
  - `workflow_trace` (high-level steps with status)

- **Failure:** `502` if Ollama is unreachable, the model is missing, or the model returns unparseable JSON — `detail` explains the error.

Example with `curl` (single line; works in PowerShell and bash):

```bash
curl -s -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d "{\"text\": \"Subject: Refund\\nWe need a refund for INV-1. Email: user@example.com\"}"
```

---

## Limitations and tips

- The LLM can still make mistakes; **rules** exist to flag **human review**, not to guarantee correctness.  
- If you often see invalid JSON from Ollama, use a stronger model or reduce input size.  
- Amount and currency parsing are best-effort and tuned for common patterns (INR, USD, symbols, etc.).

---

## License / submission

Built as a coding assessment sample. Adapt license as needed for your own fork or submission requirements.
