# Request intake workflow

Small web app for first-line business request intake: **classify** and **extract** with **Ollama** (real LLM calls); **validate**, **risk/priority**, and **next action** are rule-based.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) running locally, with a model pulled (e.g. `ollama pull llama3.2`)

## Setup

```bash
cd assessment_palni
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` if needed:

- `OLLAMA_BASE_URL` — default `http://127.0.0.1:11434`
- `OLLAMA_MODEL` — must match a model you have (`ollama list`). If that name is not installed, the app **falls back to the first model** Ollama reports (and logs a warning in the server console).

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 — paste a request, click **Run workflow**.

## API

`POST /api/run` with JSON body `{ "text": "..." }` returns structured JSON (type, extracted fields, validation, risk, recommendation, trace).

## Notes

- Do not commit `.env` or API keys. This project uses **local Ollama only** by default.
- If the model returns invalid JSON, the server responds with an error; retry or use a stronger model.
