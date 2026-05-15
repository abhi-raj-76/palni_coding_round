"""Orchestrate workflow steps with a simple trace."""
from typing import Any

from app.workflow.classify import classify_request
from app.workflow.extract import extract_information
from app.workflow.recommend import recommend_next_action
from app.workflow.risk import assess_risk
from app.workflow.validate import validate


async def run_pipeline(request_text: str) -> dict[str, Any]:
    trace: list[dict[str, str]] = []

    trace.append({"step": "classify", "detail": "Calling Ollama for request type + summary"})
    classification = await classify_request(request_text)
    class_raw = classification.pop("raw_model_output", None)
    trace.append({"step": "classify", "detail": "Done"})

    trace.append({"step": "extract", "detail": "Calling Ollama for structured fields"})
    extracted = await extract_information(request_text)
    extract_raw = extracted.pop("raw_model_output", None)
    extracted_display = dict(extracted)
    trace.append({"step": "extract", "detail": "Done"})

    trace.append({"step": "validate", "detail": "Rule-based checklist for request type"})
    validation = validate(classification["request_type"], extracted_display)
    trace.append({"step": "validate", "detail": validation["explanation"]})

    trace.append({"step": "risk", "detail": "Heuristic priority from language + completeness"})
    risk = assess_risk(request_text, classification["request_type"], validation)
    trace.append({"step": "risk", "detail": f"{risk['risk_level']} / {risk['priority']}"})

    trace.append({"step": "recommend", "detail": "Rule-based routing suggestion"})
    recommendation = recommend_next_action(
        classification["request_type"], validation, risk
    )
    trace.append({"step": "recommend", "detail": "Done"})

    return {
        "request_type": classification["request_type"],
        "type_summary": classification.get("summary_one_line", ""),
        "extracted": extracted_display,
        "validation": validation,
        "risk": risk,
        "recommendation": recommendation,
        "trace": trace,
        "debug": {"classification_raw": class_raw, "extraction_raw": extract_raw},
    }
