"""Rule-based completeness check (depends on request type + extracted fields)."""
from typing import Any


def _non_empty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return True


def validate(request_type: str, extracted: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    warnings: list[str] = []

    if not _non_empty(extracted.get("contact_email")):
        missing.append("contact_email")

    if request_type == "refund_or_payment":
        if not _non_empty(extracted.get("payment_reference")) and not _non_empty(
            extracted.get("invoice_or_reference_ids")
        ):
            missing.append("payment_or_invoice_reference")
        if not extracted.get("amounts"):
            missing.append("amount")
    elif request_type == "invoice_or_billing":
        if not _non_empty(extracted.get("invoice_or_reference_ids")):
            missing.append("invoice_or_document_reference")
    elif request_type == "support_or_technical":
        if not _non_empty(extracted.get("subject_or_intent")):
            missing.append("problem_description")
    elif request_type == "contract_or_legal":
        if not _non_empty(extracted.get("organization")):
            missing.append("counterparty_or_org")
    elif request_type == "account_or_access":
        if not _non_empty(extracted.get("customer_id")) and not _non_empty(
            extracted.get("contact_email")
        ):
            missing.append("account_identifier")

    if extracted.get("freeform_notes"):
        warnings.append(str(extracted["freeform_notes"])[:300])

    complete = len(missing) == 0
    return {
        "complete": complete,
        "missing_fields": missing,
        "warnings": warnings,
        "explanation": (
            "Enough structured detail for first-line routing."
            if complete
            else "Some typical fields are missing for this request type; agent may need a reply."
        ),
    }
