"""LLM: classify request into one of a fixed set of types."""
from typing import Any

from app.ollama_client import chat_completion, parse_json_loose

ALLOWED_TYPES = (
    "refund_or_payment",
    "invoice_or_billing",
    "support_or_technical",
    "contract_or_legal",
    "account_or_access",
    "other",
)

SYSTEM = f"""You classify short business emails/requests.
Reply with ONLY valid JSON: {{"request_type": "<one_of>", "summary_one_line": "<string>"}}
request_type must be exactly one of: {", ".join(ALLOWED_TYPES)}
- refund_or_payment: refunds, failed payments, double charges
- invoice_or_billing: invoices, statements, payment terms
- support_or_technical: bugs, outages, how-to, product issues
- contract_or_legal: NDAs, agreements, legal review
- account_or_access: login, permissions, user/account changes
- other: does not fit above
summary_one_line: max 120 characters, plain English."""


async def classify_request(text: str) -> dict[str, Any]:
    raw = await chat_completion(SYSTEM, text[:12000], json_mode=True)
    data = parse_json_loose(raw)
    rt = str(data.get("request_type", "other")).strip()
    if rt not in ALLOWED_TYPES:
        rt = "other"
    return {
        "request_type": rt,
        "summary_one_line": str(data.get("summary_one_line", ""))[:200],
        "raw_model_output": raw[:2000],
    }
