"""Rule-based priority, risk, validation, injection/suspicious signals, escalation — no LLM."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Labels + TLD so single-letter TLDs (e.g. .c) are captured for validation
_EMAIL_LOOSE = re.compile(
    r"(?<![A-Za-z0-9.@])[A-Za-z0-9][A-Za-z0-9._%+-]*@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])\.)+[A-Za-z]{1,63}\b"
)
_INV_RE = re.compile(r"\b(?:INV|Invoice)[\s#:.-]*([A-Za-z0-9-]+)\b", re.I)
_PAY_RE = re.compile(r"\b(?:PAY|Payment ref|Payment Reference)[\s#:.-]*([A-Za-z0-9-]+)\b", re.I)
_MONEY_RE = re.compile(
    r"(?:INR|Rs\.?|₹|USD|\$|EUR|GBP)\s*([\d]{1,3}(?:,\d{3})*|\d+(?:\.\d+)?)",
    re.I,
)

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|prior)\s+instructions?", re.I),
    re.compile(r"disregard\s+(the\s+)?(above|prior|previous)", re.I),
    re.compile(r"approve\s+this\s+automatically", re.I),
    re.compile(r"mark\s+as\s+low\s+risk", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"override\s+(policy|rules)", re.I),
]

_URGENT_HIGH = re.compile(
    r"\b(urgent|asap|as\s*soon\s*as\s*possible|immediately|right\s+away|legal\s+action)\b",
    re.I,
)

_CONTRA_RULES: list[tuple[re.Pattern[str], re.Pattern[str]]] = [
    (
        re.compile(r"\b(refund|refunded)\b.*\b(received|processed|completed)\b", re.I),
        re.compile(r"\b(failed|not\s+received|did\s+not\s+arrive|still\s+deducted)\b", re.I),
    ),
    (
        re.compile(r"\bpayment\s+failed\b", re.I),
        re.compile(r"\b(already\s+)?refunded\b", re.I),
    ),
]


def _parse_amount_numeric(s: str | None) -> float | None:
    if not s:
        return None
    t = str(s).replace(",", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def _amounts_from_text(text: str) -> list[float]:
    out: list[float] = []
    for m in _MONEY_RE.finditer(text or ""):
        v = _parse_amount_numeric(m.group(1))
        if v is not None and v > 0:
            out.append(v)
    return out


def _detect_injection(text: str) -> bool:
    return any(p.search(text or "") for p in _INJECTION_PATTERNS)


def _rule_contradictions(text: str) -> bool:
    t = text or ""
    for a, b in _CONTRA_RULES:
        if a.search(t) and b.search(t):
            return True
    amounts = _amounts_from_text(t)
    if len(amounts) >= 2:
        mx, mn = max(amounts), min(amounts)
        if mn > 0 and (mx - mn) / mn > 0.25 and mx > 10000:
            return True
    return False


def _duplicate_refs(text: str) -> bool:
    tokens = re.findall(r"\b(?:PAY|INV|CUST|TCK|TKT)[-#]?[A-Za-z0-9]+\b", text or "", re.I)
    if not tokens:
        return False
    c = Counter(x.upper() for x in tokens)
    return any(n >= 4 for n in c.values())


def _email_valid(email: str | None) -> bool:
    if not email or not isinstance(email, str):
        return False
    e = email.strip()
    return bool(_EMAIL_RE.fullmatch(e))


def _emails_found_in_text(text: str) -> list[str]:
    """Return unique @… tokens from the raw message (trim trailing punctuation)."""
    if not text:
        return []
    seen: list[str] = []
    for m in _EMAIL_LOOSE.finditer(text):
        addr = m.group(0).rstrip(".,);:]\"'")
        if addr not in seen:
            seen.append(addr)
    return seen


def _invalid_emails_in_raw_text(text: str) -> list[str]:
    return [a for a in _emails_found_in_text(text) if not _email_valid(a)]


def _critical_missing(request_type: str, ext: dict[str, Any]) -> list[str]:
    miss: list[str] = []
    if not ext.get("email"):
        miss.append("email")

    if request_type == "refund_or_payment":
        if not (ext.get("payment_reference") or ext.get("invoice_number")):
            miss.append("payment_reference_or_invoice_number")
        if not ext.get("amount"):
            miss.append("amount")
    elif request_type == "invoice_or_billing":
        if not ext.get("invoice_number"):
            miss.append("invoice_number")
    elif request_type == "support_or_technical":
        if not ext.get("issue_description"):
            miss.append("issue_description")
    elif request_type == "contract_or_legal":
        if not ext.get("company"):
            miss.append("company_or_counterparty")
    elif request_type == "account_or_access":
        if not (ext.get("customer_id") or ext.get("email")):
            miss.append("customer_id_or_email")

    return miss


def _validation_issues(text: str, ext: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    raw = text or ""

    for bad in _invalid_emails_in_raw_text(raw):
        issues.append(f"invalid_email_in_message_body:{bad}")

    em = ext.get("email")
    if em:
        es = str(em).strip()
        if not _email_valid(es):
            if "invalid_email_format" not in issues:
                issues.append("invalid_email_format")
        elif es.lower() not in raw.lower():
            issues.append("extracted_email_not_found_verbatim_in_message")

    if ext.get("amount"):
        if _parse_amount_numeric(str(ext["amount"])) is None:
            issues.append("amount_not_numeric")
    for label, pat in (("invoice_number", _INV_RE), ("payment_reference", _PAY_RE)):
        v = ext.get(label)
        if isinstance(v, str) and v.strip():
            if not pat.search(text or "") and v not in (text or ""):
                issues.append(f"{label}_not_found_verbatim_in_text")
    return issues


def _suggested_collect(missing: list[str], issues: list[str]) -> list[str]:
    sug: list[str] = []
    mapping = {
        "email": "Ask for a valid contact email we can reply to.",
        "payment_reference_or_invoice_number": "Ask for the payment reference or invoice number as shown on the bank/app.",
        "amount": "Ask for the exact amount and currency that was charged or expected.",
        "invoice_number": "Ask for the invoice number or billing document ID.",
        "issue_description": "Ask for what broke, when it started, and any error message or screenshot.",
        "company_or_counterparty": "Ask for the legal entity or counterparty name on the agreement.",
        "customer_id_or_email": "Ask for the customer or account ID, or confirm the registered email.",
    }
    for m in missing:
        if m in mapping:
            sug.append(mapping[m])
    if "invalid_email_format" in issues:
        sug.append("Ask the customer to resend the email address using standard name@domain format.")
    for i in issues:
        s = str(i)
        if s.startswith("invalid_email_in_message_body"):
            sug.append(
                "The contact email in the message looks invalid (e.g. incomplete domain). "
                "Ask the customer to confirm the correct address."
            )
            break
    for i in issues:
        if str(i).startswith("extracted_email_not_found_verbatim"):
            sug.append(
                "Extracted email does not appear verbatim in the message (possible model correction). "
                "Confirm the exact address with the customer."
            )
            break
    return list(dict.fromkeys(sug))


def _max_claimed_amount(ext: dict[str, Any], text: str) -> float | None:
    a = _parse_amount_numeric(str(ext.get("amount") or ""))
    vals = _amounts_from_text(text)
    mx = max(vals) if vals else None
    if a is None:
        return mx
    if mx is None:
        return a
    return max(a, mx)


def _priority(text: str, request_type: str, ext: dict[str, Any], critical_missing: list[str]) -> str:
    t = text or ""
    if _URGENT_HIGH.search(t):
        return "HIGH"
    amt = _max_claimed_amount(ext, t)
    if request_type == "refund_or_payment" and amt is not None and amt > 50000:
        return "HIGH"
    if critical_missing:
        return "MEDIUM"
    if request_type == "other":
        return "LOW"
    return "LOW"


def _risk_bundle(
    text: str,
    request_type: str,
    ext: dict[str, Any],
    injection: bool,
    suspicious: bool,
    contradiction: bool,
    critical_missing: list[str],
    issues: list[str],
) -> tuple[str, str]:
    reasons: list[str] = []
    score = 0

    if request_type == "refund_or_payment":
        reasons.append("Financial risk: payment/refund dispute context.")
        score += 2
    if request_type == "contract_or_legal" or re.search(r"\blegal\b", text or "", re.I):
        reasons.append("Legal risk: contract or legal language present.")
        score += 3
    if injection or suspicious:
        reasons.append("Fraud suspicion: manipulation language or anomalous pattern.")
        score += 3
    if contradiction:
        reasons.append("Contradiction risk: conflicting statements detected.")
        score += 2
    if critical_missing:
        reasons.append("Missing information risk: required fields incomplete.")
        score += 1
    if any("email" in i for i in issues):
        reasons.append("Data quality: email failed validation or does not match the source text.")
        score += 1

    if score >= 5:
        lvl = "HIGH"
    elif score >= 2:
        lvl = "MEDIUM"
    else:
        lvl = "LOW"

    risk_reason = "; ".join(reasons) if reasons else "No elevated risk signals from rules."
    return lvl, risk_reason


def _escalation(
    request_type: str, priority: str, risk_level: str, human_review: bool
) -> dict[str, Any]:
    if request_type == "contract_or_legal":
        dept = "Legal Team"
    elif request_type in ("refund_or_payment", "invoice_or_billing"):
        dept = "Finance Team"
    elif request_type == "support_or_technical":
        dept = "Technical Support"
    else:
        dept = "Customer Success"

    required = (
        human_review or priority == "HIGH" or risk_level == "HIGH" or request_type == "contract_or_legal"
    )
    return {"required": bool(required), "department": dept}


def _recommended_action(
    human_review: bool,
    injection: bool,
    request_type: str,
    missing: list[str],
    dept: str,
) -> str:
    if injection:
        return (
            "Do not auto-route. Treat as potential prompt abuse: have a human review the thread, "
            "verify sender identity, then proceed with standard intake."
        )
    if human_review:
        return (
            "Pause automated decisions. A human reviewer should confirm facts, resolve contradictions, "
            f"then route to {dept}."
        )
    if missing:
        return (
            "Reply once with a concise checklist of missing items; after receipt, route to the appropriate team."
        )
    if request_type == "refund_or_payment":
        return "Verify payment references in Finance tooling, then process or escalate per policy."
    if request_type == "support_or_technical":
        return "Open a support ticket with the extracted details and link to monitoring if applicable."
    if request_type == "contract_or_legal":
        return "Forward to Legal without committing to obligations in email."
    return f"Route to {dept} using the structured fields captured above."


def build_envelope(
    user_text: str,
    llm: dict[str, Any],
) -> dict[str, Any]:
    ext = dict(llm.get("extracted_information") or {})
    injection = _detect_injection(user_text)
    dup_refs = _duplicate_refs(user_text)
    amt_val = _parse_amount_numeric(str(ext.get("amount") or "")) or 0.0
    from_text_amt = max(_amounts_from_text(user_text), default=0.0)
    big_spend = amt_val > 2_000_000 or from_text_amt > 2_000_000

    suspicious = injection or dup_refs or big_spend

    contra_llm = bool(llm.get("contradiction_detected"))
    contra_rule = _rule_contradictions(user_text)
    contradiction = contra_llm or contra_rule

    conf = int(llm.get("confidence_score") or 0)
    critical_missing = _critical_missing(str(llm.get("request_type")), ext)
    issues = _validation_issues(user_text, ext)
    complete = len(critical_missing) == 0 and len(issues) == 0

    status = "valid" if complete else ("invalid" if issues else "incomplete")

    priority = _priority(user_text, str(llm.get("request_type")), ext, critical_missing)
    risk_level, risk_reason = _risk_bundle(
        user_text,
        str(llm.get("request_type")),
        ext,
        injection,
        suspicious,
        contradiction,
        critical_missing,
        issues,
    )

    human_review = (
        conf < 60
        or not complete
        or contradiction
        or suspicious
        or injection
        or bool(issues)
    )

    esc = _escalation(str(llm.get("request_type")), priority, risk_level, human_review)
    rec = _recommended_action(human_review, injection, str(llm.get("request_type")), critical_missing, esc["department"])

    wf = [
        {"step": "Classification", "status": "completed"},
        {"step": "Information Extraction", "status": "completed"},
        {"step": "Validation", "status": "completed"},
        {"step": "Risk Assessment", "status": "completed"},
        {"step": "Recommendation Generation", "status": "completed"},
    ]

    sent = str(llm.get("sentiment") or "Neutral")
    if _URGENT_HIGH.search(user_text) and sent == "Neutral":
        sent = "Angry/Urgent"

    return {
        "request_type": str(llm.get("request_type") or "other"),
        "confidence_score": conf,
        "summary": str(llm.get("summary") or ""),
        "sentiment": sent,
        "priority": priority,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "human_review_required": human_review,
        "contradiction_detected": contradiction,
        "suspicious_request": suspicious,
        "extracted_information": ext,
        "validation": {
            "status": status,
            "missing_fields": critical_missing,
            "validation_issues": issues,
            "suggested_information_to_collect": _suggested_collect(critical_missing, issues),
        },
        "recommended_action": rec,
        "escalation_recommendation": esc,
        "workflow_trace": wf,
    }
