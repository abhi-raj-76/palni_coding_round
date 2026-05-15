"""LLM: extract structured fields from the request."""
import json
from typing import Any

from app.ollama_client import chat_completion, parse_json_loose

SYSTEM = """Extract factual details from the business request. Do not invent values.
Reply with ONLY valid JSON with these keys (use null if missing):
{
  "customer_name": string|null,
  "organization": string|null,
  "customer_id": string|null,
  "invoice_or_reference_ids": string[]|[],
  "payment_reference": string|null,
  "amounts": [{"currency": string|null, "value": string|null}]|[],
  "dates_mentioned": string[],
  "contact_email": string|null,
  "subject_or_intent": string|null,
  "freeform_notes": string|null
}
amounts: only amounts explicitly stated. dates_mentioned as written (e.g. "10-May-2026").
freeform_notes: at most 2 short sentences on ambiguity or missing context."""


async def extract_information(text: str) -> dict[str, Any]:
    raw = await chat_completion(SYSTEM, text[:12000], json_mode=True)
    data = parse_json_loose(raw)
    # normalize shapes
    out: dict[str, Any] = {
        "customer_name": data.get("customer_name"),
        "organization": data.get("organization"),
        "customer_id": data.get("customer_id"),
        "invoice_or_reference_ids": data.get("invoice_or_reference_ids") or [],
        "payment_reference": data.get("payment_reference"),
        "amounts": data.get("amounts") or [],
        "dates_mentioned": data.get("dates_mentioned") or [],
        "contact_email": data.get("contact_email"),
        "subject_or_intent": data.get("subject_or_intent"),
        "freeform_notes": data.get("freeform_notes"),
    }
    if not isinstance(out["invoice_or_reference_ids"], list):
        out["invoice_or_reference_ids"] = []
    if not isinstance(out["amounts"], list):
        out["amounts"] = []
    if not isinstance(out["dates_mentioned"], list):
        out["dates_mentioned"] = []
    return {**out, "raw_model_output": raw[:4000]}
