"""Rule-based risk / priority from text + type + validation."""
import re
from typing import Any


_URGENT = re.compile(
    r"\b(urgent|asap|immediately|legal|lawsuit|escalat|outage|down|security|breach)\b",
    re.I,
)


def assess_risk(request_text: str, request_type: str, validation: dict[str, Any]) -> dict[str, Any]:
    text = request_text or ""
    urgent = bool(_URGENT.search(text))
    incomplete = not validation.get("complete", False)

    if request_type in ("contract_or_legal",):
        base = "high"
    elif request_type == "refund_or_payment" and urgent:
        base = "medium-high"
    elif urgent or incomplete:
        base = "medium"
    else:
        base = "low"

    priority = "P1" if base.startswith("high") or (urgent and incomplete) else "P2" if urgent or incomplete else "P3"

    return {
        "risk_level": base,
        "priority": priority,
        "signals": {
            "urgency_language": urgent,
            "incomplete_intake": incomplete,
            "request_type": request_type,
        },
    }
