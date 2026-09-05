"""High-level intelligence service used by the API/UI."""
from __future__ import annotations
from typing import Any

from .analytics import RetailAnalytics
from .recommendations import action_for_alert


class IntelligenceService:
    def __init__(self, analytics: RetailAnalytics):
        self.analytics = analytics

    def attention_with_actions(self, days: int = 30) -> list[dict[str, Any]]:
        result = []
        for alert in self.analytics.attention(days):
            item = dict(alert)
            item["recommendation"] = action_for_alert(alert)
            result.append(item)
        return result

    def evidence_for_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        recommendation = action_for_alert(alert)
        return {
            "alert": alert,
            "recommendation": recommendation,
            "evidence": alert.get("metrics", {}),
            "trace": [
                "Source data: sales + latest inventory",
                "Analytics: deterministic Python calculations",
                "Recommendation: deterministic formula/rules",
                "Gemini: explanation only; no source facts are invented",
            ],
        }
