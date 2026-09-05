"""Evidence packaging layer.

Creates a compact, auditable evidence packet for Gemini and for the UI.
"""
from __future__ import annotations
from typing import Any
import json


def _clean(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    return value


def build_evidence_packet(
    *,
    question: str,
    intent: str,
    period_days: int,
    records: list[dict[str, Any]] | None = None,
    alerts: list[dict[str, Any]] | None = None,
    recommendation: dict[str, Any] | None = None,
    data_limitations: list[str] | None = None,
) -> dict[str, Any]:
    packet = {
        "question": question,
        "intent": intent,
        "period_days": period_days,
        "evidence_records": records or [],
        "alerts": alerts or [],
        "recommendation": recommendation,
        "data_limitations": data_limitations or [],
        "grounding_rule": (
            "Every factual number in the answer must be traceable to this packet. "
            "If the packet does not contain enough evidence, say that the data is insufficient."
        ),
    }
    return packet


def compact_json(packet: dict[str, Any]) -> str:
    return json.dumps(packet, ensure_ascii=False, default=str, indent=2)
