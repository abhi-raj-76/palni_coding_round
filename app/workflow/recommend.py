"""Rule-based next action from type, validation, and risk."""
from typing import Any


def recommend_next_action(
    request_type: str,
    validation: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    complete = validation.get("complete", False)
    priority = risk.get("priority", "P3")

    if not complete:
        action = "Send a short reply asking only for the missing fields; do not process yet."
        owner = "Front desk / shared inbox"
    elif request_type == "refund_or_payment":
        action = "Route to Finance / Payments with invoice and bank trace references."
        owner = "Finance"
    elif request_type == "invoice_or_billing":
        action = "Route to AR / Billing for statement lookup and copy of invoice."
        owner = "Billing"
    elif request_type == "support_or_technical":
        action = "Open ticket in support queue with extracted environment and error text."
        owner = "Support L1"
    elif request_type == "contract_or_legal":
        action = "Route to Legal for review; avoid committing to terms in email."
        owner = "Legal"
    elif request_type == "account_or_access":
        action = "Route to IT / IAM with user id and requested change scoped."
        owner = "IT / IAM"
    else:
        action = "Manual triage: assign to appropriate owner based on summary."
        owner = "Intake lead"

    if priority == "P1":
        action = f"[{priority}] " + action

    return {"recommended_action": action, "suggested_owner": owner, "method": "rules"}
