"""Orchestrate LLM intake + rule engine into the enterprise JSON contract."""
from typing import Any

from app.workflow.llm_intake import run_llm_intake
from app.workflow.rules_engine import build_envelope


async def run_pipeline(request_text: str) -> dict[str, Any]:
    llm_part, _raw = await run_llm_intake(request_text)
    return build_envelope(request_text, llm_part)
