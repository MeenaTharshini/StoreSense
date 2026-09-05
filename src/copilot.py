"""
StoreSense Copilot

Python calculates and verifies all business facts.
Gemini converts verified evidence into a concise manager-level insight.

Design goal:
    Question
        ↓
    Understand intent
        ↓
    Gather verified evidence
        ↓
    Explain what is happening
        ↓
    Recommend the next best action
        ↓
    State assumptions / limitations
"""

from __future__ import annotations

import os
import re
from typing import Any

from google import genai

from .analytics import RetailAnalytics
from .evidence import build_evidence_packet, compact_json
from .intent import classify_query, QueryIntent
from .recommendations import action_for_alert


UNSUPPORTED_RULES = {
    "profit": "profit or margin data",
    "margin": "profit or margin data",
    "cost": "product cost data",
    "supplier": "supplier information",
    "vendor": "supplier information",
    "competitor": "competitor pricing/data",
    "competition": "competitor pricing/data",
    "return": "returns data",
    "returns": "returns data",
}


class StoreSenseCopilot:

    def __init__(self, analytics: RetailAnalytics):
        self.analytics = analytics

        self.product_names = (
            self.analytics.data.products["product_name"]
            .dropna()
            .astype(str)
            .tolist()
        )

        self.store_names = (
            self.analytics.data.stores["store_name"]
            .dropna()
            .astype(str)
            .tolist()
        )

        self.api_key = os.getenv(
            "GEMINI_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.6-flash"
        )

        self.client = (
            genai.Client(api_key=self.api_key)
            if self.api_key
            else None
        )

    # ============================================================
    # DATA LIMITATIONS
    # ============================================================

    def _limitation(
        self,
        question: str
    ) -> str | None:

        q = question.casefold()

        for word, missing in UNSUPPORTED_RULES.items():

            if word in q:
                return (
                    "I can't answer that reliably from the available "
                    "data because "
                    f"{missing} is not provided."
                )

        return None

    # ============================================================
    # CLEAN GEMINI OUTPUT
    # ============================================================

    def _clean_response(
        self,
        text: str
    ) -> str:

        if not text:
            return text

        # Remove markdown bold / italic markers.
        text = text.replace("**", "")
        text = text.replace("__", "")

        # Remove markdown heading markers.
        text = re.sub(
            r"(?m)^\s*#{1,6}\s*",
            "",
            text
        )

        # Convert markdown bullet symbols into clean bullets.
        text = re.sub(
            r"(?m)^\s*[-*]\s+",
            "• ",
            text
        )

        # Remove markdown code fences.
        text = text.replace("```", "")

        # Remove unnecessary repeated blank lines.
        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        return text.strip()

    # ============================================================
    # DETERMINISTIC FALLBACK
    # ============================================================

    def _fallback(
        self,
        packet: dict[str, Any],
        intent: QueryIntent
    ) -> str:

        alerts = packet.get("alerts", [])
        recommendation = packet.get("recommendation")
        records = packet.get(
            "evidence_records",
            []
        )

        # --------------------------------------------------------
        # STOCK-OUT
        # --------------------------------------------------------

        if intent.name == "STOCKOUT_RISK":

            if not alerts:
                return (
                    "No immediate stock-out risk was found.\n\n"
                    "Next step\n"
                    "Continue monitoring inventory and recent demand."
                )

            alert = alerts[0]

            metrics = (
                alert.get("metrics")
                or alert.get("evidence")
                or {}
            )

            action = (
                recommendation["action"]
                if recommendation
                else "Review replenishment."
            )

            return (
                "Stock-out risk\n\n"
                f"{alert['product_name']} at "
                f"{alert['store_name']} is the highest-priority "
                "risk.\n\n"
                "Evidence\n"
                f"• {metrics['current_stock']:.0f} units remain.\n"
                f"• About {metrics['days_of_inventory']:.1f} "
                "days of inventory remain.\n"
                f"• Recent demand is "
                f"{metrics['daily_demand']:.2f} units/day.\n\n"
                "Recommended next step\n"
                f"{action}"
            )

        # --------------------------------------------------------
        # SLOW MOVING
        # --------------------------------------------------------

        if intent.name == "SLOW_MOVING":

            if not alerts:
                return (
                    "No slow-moving stock was identified "
                    "from the available data."
                )

            alert = alerts[0]

            action = (
                recommendation["action"]
                if recommendation
                else (
                    "Consider a promotion, bundle, stock transfer, "
                    "or markdown before purchasing more."
                )
            )

            return (
                "Slow-moving stock\n\n"
                f"{alert['product_name']} at "
                f"{alert['store_name']} is moving slowly.\n\n"
                f"{alert['reason']}\n\n"
                "Recommended next step\n"
                f"{action}"
            )

        # --------------------------------------------------------
        # SALES DROP
        # --------------------------------------------------------

        if intent.name == "SALES_DROP":

            if not alerts:
                return (
                    "No significant sales drop was identified "
                    "from the available data."
                )

            alert = alerts[0]

            action = (
                recommendation["action"]
                if recommendation
                else (
                    "Review recent demand and check whether "
                    "inventory availability changed."
                )
            )

            return (
                "Sales decline\n\n"
                f"{alert['title']}.\n\n"
                f"{alert['reason']}\n\n"
                "Recommended next step\n"
                f"{action}"
            )

        # --------------------------------------------------------
        # SALES SPIKE
        # --------------------------------------------------------

        if intent.name == "SALES_SPIKE":

            if not alerts:
                return (
                    "No significant sales spike was identified "
                    "from the available data."
                )

            alert = alerts[0]

            action = (
                recommendation["action"]
                if recommendation
                else (
                    "Check whether inventory can support the "
                    "increased demand and investigate the cause."
                )
            )

            return (
                "Sales spike\n\n"
                f"{alert['title']}.\n\n"
                f"{alert['reason']}\n\n"
                "Recommended next step\n"
                f"{action}"
            )

        # --------------------------------------------------------
        # PRODUCT PERFORMANCE
        # --------------------------------------------------------

        if (
            intent.name == "PRODUCT_PERFORMANCE"
            and records
        ):

            record = records[0]

            if "recent_units" in record:

                change = record.get(
                    "pct_change"
                )

                change_text = (
                    f"{change:+.1f}%"
                    if change is not None
                    else "not available"
                )

                return (
                    "Product performance\n\n"
                    f"{record['product_name']} at "
                    f"{record['store_name']} sold "
                    f"{record['recent_units']:.0f} units "
                    "in the recent period.\n\n"
                    "Comparison\n"
                    f"• Previous period: "
                    f"{record['previous_units']:.0f} units.\n"
                    f"• Change: {change_text}.\n\n"
                    "Recommended next step\n"
                    "Use the recent demand signal when planning "
                    "inventory and promotions."
                )

        # --------------------------------------------------------
        # GENERAL ALERT
        # --------------------------------------------------------

        if alerts:

            alert = alerts[0]

            action = (
                recommendation["action"]
                if recommendation
                else (
                    "Review this item and take action based on "
                    "the available evidence."
                )
            )

            return (
                "Priority insight\n\n"
                f"{alert['title']}.\n\n"
                f"{alert['reason']}\n\n"
                "Recommended next step\n"
                f"{action}"
            )

        return (
            "I couldn't find a relevant evidence-backed result "
            "in the available data.\n\n"
            "Next step\n"
            "Try asking about stock-out risk, slow-moving stock, "
            "sales changes, product performance, or store performance."
        )

    # ============================================================
    # BUILD VERIFIED EVIDENCE
    # ============================================================

    def _build_packet(
        self,
        question: str,
        intent: QueryIntent
    ) -> dict[str, Any]:

        limitations = [
            "Sales and inventory data are available.",
            "Supplier lead time, purchase cost, profit margin, "
            "promotions, and competitor data are not available.",
        ]

        # ========================================================
        # ALERT QUESTIONS
        # ========================================================

        if intent.name in {
            "STOCKOUT_RISK",
            "SLOW_MOVING",
            "SALES_DROP",
            "SALES_SPIKE",
            "TOP_PRIORITIES",
        }:

            alerts = self.analytics.attention(
                intent.period_days
            )

            if intent.name == "STOCKOUT_RISK":

                alerts = [
                    a for a in alerts
                    if a["type"] == "stockout"
                ]

            elif intent.name == "SLOW_MOVING":

                alerts = [
                    a for a in alerts
                    if a["type"] == "slow_moving"
                ]

            elif intent.name == "SALES_DROP":

                alerts = [
                    a for a in alerts
                    if a["type"] == "sales_drop"
                ]

            elif intent.name == "SALES_SPIKE":

                alerts = [
                    a for a in alerts
                    if a["type"] == "sales_spike"
                ]

            elif intent.name == "TOP_PRIORITIES":

                alerts = self.analytics.top_priorities(
                    intent.period_days,
                    limit=5
                )

            # Product filter
            if intent.product_name:

                alerts = [
                    a for a in alerts
                    if a["product_name"].casefold()
                    == intent.product_name.casefold()
                ]

            # Store filter
            if intent.store_name:

                alerts = [
                    a for a in alerts
                    if a["store_name"].casefold()
                    == intent.store_name.casefold()
                ]

            recommendation = (
                action_for_alert(alerts[0])
                if len(alerts) == 1
                else None
            )

            return build_evidence_packet(
                question=question,
                intent=intent.name,
                period_days=intent.period_days,
                alerts=alerts[:10],
                recommendation=recommendation,
                data_limitations=limitations,
            )

        # ========================================================
        # REPLENISHMENT
        # ========================================================

        if intent.name == "REPLENISHMENT":

            risks = self.analytics.stockout_risks(
                intent.period_days
            )

            if intent.product_name:

                risks = [
                    r for r in risks
                    if r["product_name"].casefold()
                    == intent.product_name.casefold()
                ]

            if intent.store_name:

                risks = [
                    r for r in risks
                    if r["store_name"].casefold()
                    == intent.store_name.casefold()
                ]

            alerts = []

            for r in risks[:10]:

                alerts.append({
                    "type": "stockout",
                    "product_id": str(
                        r["product_id"]
                    ),
                    "store_id": str(
                        r["store_id"]
                    ),
                    "product_name": str(
                        r["product_name"]
                    ),
                    "store_name": str(
                        r["store_name"]
                    ),
                    "severity": r["severity"],
                    "reason": r["reason"],
                    "metrics": {
                        "current_stock": float(
                            r["stock"]
                        ),
                        "daily_demand": float(
                            r["daily_demand"]
                        ),
                        "days_of_inventory": float(
                            r["days_of_inventory"]
                        ),
                        "recent_units": float(
                            r["recent_units"]
                        ),
                        "previous_units": float(
                            r["previous_units"]
                        ),
                        "pct_change": r.get(
                            "pct_change"
                        ),
                    },
                })

            recommendation = (
                action_for_alert(alerts[0])
                if len(alerts) == 1
                else None
            )

            return build_evidence_packet(
                question=question,
                intent=intent.name,
                period_days=intent.period_days,
                alerts=alerts,
                recommendation=recommendation,
                data_limitations=limitations,
            )

        # ========================================================
        # PRODUCT PERFORMANCE
        # ========================================================

        if intent.name == "PRODUCT_PERFORMANCE":

            if not intent.product_name:

                return build_evidence_packet(
                    question=question,
                    intent=intent.name,
                    period_days=intent.period_days,
                    data_limitations=[
                        "A specific product name was not "
                        "found in the question."
                    ],
                )

            result = self.analytics.product_performance(
                intent.product_name,
                intent.store_name,
                intent.period_days,
            )

            extra_limitations = []

            if not result.get("found"):

                extra_limitations.append(
                    result.get(
                        "message",
                        "Product was not found."
                    )
                )

            return build_evidence_packet(
                question=question,
                intent=intent.name,
                period_days=intent.period_days,
                records=result.get(
                    "store_breakdown",
                    []
                ),
                data_limitations=(
                    limitations
                    + extra_limitations
                ),
            )

        # ========================================================
        # STORE PERFORMANCE
        # ========================================================

        if intent.name == "STORE_PERFORMANCE":

            if not intent.store_name:

                return build_evidence_packet(
                    question=question,
                    intent=intent.name,
                    period_days=intent.period_days,
                    data_limitations=[
                        "A specific store name was not "
                        "found in the question."
                    ],
                )

            records = []

            for product in self.product_names:

                rows = self.analytics.evidence(
                    product_name=product,
                    store_name=intent.store_name,
                    days=intent.period_days,
                )

                records.extend(
                    r.to_dict()
                    for r in rows
                )

            return build_evidence_packet(
                question=question,
                intent=intent.name,
                period_days=intent.period_days,
                records=records[:50],
                data_limitations=limitations,
            )

        # ========================================================
        # STORE COMPARISON
        # ========================================================

        if intent.name == "STORE_COMPARISON":

            summary = []

            for store in self.store_names:

                rows = self.analytics.evidence(
                    store_name=store,
                    days=intent.period_days,
                )

                summary.append({
                    "store_name": store,
                    "recent_units": sum(
                        r.recent_units
                        for r in rows
                    ),
                    "previous_units": sum(
                        r.previous_units
                        for r in rows
                    ),
                    "revenue": sum(
                        (r.revenue or 0)
                        for r in rows
                    ),
                    "product_count": len(rows),
                })

            return build_evidence_packet(
                question=question,
                intent=intent.name,
                period_days=intent.period_days,
                records=summary,
                data_limitations=limitations,
            )

        # ========================================================
        # GENERAL
        # ========================================================

        alerts = self.analytics.top_priorities(
            intent.period_days,
            limit=5
        )

        return build_evidence_packet(
            question=question,
            intent=intent.name,
            period_days=intent.period_days,
            alerts=alerts,
            data_limitations=limitations,
        )

    # ============================================================
    # GEMINI
    # ============================================================

    def _gemini_answer(
        self,
        packet: dict[str, Any]
    ) -> str:

        prompt = f"""
You are StoreSense, a startup-grade retail intelligence
copilot for store managers.

The manager has asked a business question.

Your job is NOT simply to repeat the evidence.

You must:

1. Understand what the manager is actually asking.
2. Identify the most important business insight.
3. Explain the evidence using only verified numbers.
4. Tell the manager what they should do next.
5. Mention assumptions when the recommendation depends on them.
6. If the data is insufficient, say that clearly.
7. Never invent missing information.
8. Never invent causes for sales changes.
9. Never invent supplier information, costs, margins,
   promotions, competitors, or external facts.
10. Prioritize HIGH severity issues before MEDIUM.
11. If several issues exist, focus on the most important
    one or summarize the top few.
12. Do not blindly repeat the same answer if the manager's
    question asks something different.

VERY IMPORTANT:

The answer must be specific to the manager's question.

For example:

If the question is:
"What is running out?"

Focus on stock-out risks.

If the question is:
"What should I do today?"

Focus on the highest-priority actions.

If the question is:
"Which products are selling well?"

Focus on product sales evidence.

If the question is:
"What is overstocked?"

Focus on inventory versus recent demand.

If the question is:
"Why did sales drop?"

Only describe the measured drop.
Do NOT invent a cause.

OUTPUT FORMAT:

Use exactly these sections when evidence exists:

Conclusion

Evidence

Recommended next step

Assumptions

Do NOT use Markdown bold.
Do NOT use # headings.
Do NOT use **.
Do NOT use tables.
Use simple text headings and bullet points.

Keep the answer concise enough for a busy manager.

VERIFIED EVIDENCE:

{compact_json(packet)}
""".strip()

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        text = getattr(
            response,
            "text",
            None
        )

        if not text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return self._clean_response(
            text
        )

    # ============================================================
    # PUBLIC ANSWER
    # ============================================================

    def answer(
        self,
        question: str
    ) -> dict[str, Any]:

        question = " ".join(
            question.strip().split()
        )

        if not question:

            return {
                "ok": False,
                "answer": "Please enter a question.",
                "evidence": None,
            }

        # --------------------------------------------------------
        # UNSUPPORTED DATA
        # --------------------------------------------------------

        limitation = self._limitation(
            question
        )

        if limitation:

            return {
                "ok": True,
                "answer": limitation,
                "intent": "UNSUPPORTED",
                "evidence": {
                    "data_limitations": [
                        limitation
                    ]
                },
                "source": "deterministic_guardrail",
            }

        # --------------------------------------------------------
        # UNDERSTAND QUESTION
        # --------------------------------------------------------

        intent = classify_query(
            question,
            self.product_names,
            self.store_names,
        )

        # --------------------------------------------------------
        # BUILD FRESH EVIDENCE FOR THIS QUESTION
        # --------------------------------------------------------

        packet = self._build_packet(
            question,
            intent
        )

        # --------------------------------------------------------
        # REFUSE WHEN EVIDENCE DOES NOT EXIST
        # --------------------------------------------------------

        if (
            not packet.get("alerts")
            and not packet.get("evidence_records")
            and intent.name not in {"GENERAL"}
        ):

            answer = (
                "I don't have enough matching evidence in the "
                "available sales and inventory data to answer "
                "that reliably.\n\n"
                "Recommended next step\n"
                "Add more relevant sales or inventory data, "
                "or ask about a metric that StoreSense currently "
                "tracks."
            )

            return {
                "ok": True,
                "answer": answer,
                "intent": intent.name,
                "confidence": intent.confidence,
                "evidence": packet,
                "source": "deterministic_refusal",
            }

        # --------------------------------------------------------
        # GEMINI
        # --------------------------------------------------------

        if self.client:

            try:

                answer = self._gemini_answer(
                    packet
                )

                source = "gemini_grounded"

            except Exception as exc:

                answer = self._fallback(
                    packet,
                    intent
                )

                source = (
                    "deterministic_fallback:"
                    f"{type(exc).__name__}"
                )

        else:

            answer = self._fallback(
                packet,
                intent
            )

            source = "deterministic_fallback"

        return {
            "ok": True,
            "answer": answer,
            "intent": intent.name,
            "confidence": intent.confidence,
            "entities": {
                "product": intent.product_name,
                "store": intent.store_name,
                "period_days": intent.period_days,
            },
            "evidence": packet,
            "source": source,
        }