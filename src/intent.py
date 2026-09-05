"""Deterministic intent detection for StoreSense.

Gemini is deliberately NOT used to decide the business intent.  This keeps
routing predictable and makes the application safe when the LLM is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional


@dataclass
class QueryIntent:
    name: str
    product_name: Optional[str] = None
    store_name: Optional[str] = None
    period_days: int = 30
    compare_previous: bool = False
    confidence: float = 0.0
    matched_terms: list[str] = field(default_factory=list)


INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("STOCKOUT_RISK", [
        r"\brunning out\b", r"\brun out\b", r"\bstock[- ]?out\b",
        r"\blow stock\b", r"\babout to (?:run )?out\b",
        r"\bhow many days.*stock\b", r"\bdays of inventory\b",
    ]),
    ("REPLENISHMENT", [
        r"\breorder\b", r"\breplenish\b", r"\brestock\b",
        r"\border\b.*\b(?:units|stock|product)\b", r"\bwhat should i buy\b",
        r"\bwhat should i order\b", r"\bwhat to order\b",
    ]),
    ("SLOW_MOVING", [
        r"\bslow[- ]moving\b", r"\bnot selling\b", r"\bnot moving\b",
        r"\bdead stock\b", r"\bexcess stock\b", r"\boverstock(?:ed)?\b",
    ]),
    ("SALES_DROP", [
        r"\bsales? (?:drop|dropped|declin|fall|fell)\b",
        r"\bdrop(?:ped)?\b.*\bsales\b", r"\bdeclin(?:e|ed|ing)\b",
        r"\bsales.*down\b",
    ]),
    ("SALES_SPIKE", [
        r"\bsales? (?:spike|spiked|surge|surged|jump|jumped)\b",
        r"\bsales.*up\b", r"\bselling.*(?:well|fast)\b",
        r"\bhigh demand\b",
    ]),
    ("TOP_PRIORITIES", [
        r"\bwhat needs attention\b", r"\battention today\b",
        r"\btop priorities\b", r"\bwhat should i focus on\b",
        r"\bpriorit(?:y|ies)\b", r"\bmost urgent\b",
    ]),
    ("STORE_COMPARISON", [
        r"\bcompare\b.*\bstores?\b", r"\bwhich store\b",
        r"\bbest store\b", r"\bworst store\b", r"\bstores? perform\b",
    ]),
    ("STORE_PERFORMANCE", [
        r"\bhow is\b.*\bstore\b", r"\bstore performance\b",
        r"\bperformance of\b.*\bstore\b",
    ]),
    ("PRODUCT_PERFORMANCE", [
        r"\bhow is\b", r"\bperformance of\b", r"\bperforming\b",
        r"\bhow did\b.*\bperform\b", r"\bproduct performance\b",
    ]),
]


def _best_match(text: str) -> tuple[str, float, list[str]]:
    scores: list[tuple[str, float, list[str]]] = []
    for intent, patterns in INTENT_PATTERNS:
        matched = [p for p in patterns if re.search(p, text, re.I)]
        if matched:
            # Multiple matches increase confidence, but cap it.
            confidence = min(0.55 + 0.12 * len(matched), 0.95)
            scores.append((intent, confidence, matched))
    if not scores:
        return "GENERAL", 0.25, []
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[0]


def _extract_period(text: str) -> tuple[int, bool]:
    m = re.search(r"\b(\d+)\s*days?\b", text, re.I)
    if m:
        return max(1, min(int(m.group(1)), 365)), True
    if re.search(r"\b(week|weekly)\b", text, re.I):
        return 7, True
    if re.search(r"\b(month|monthly)\b", text, re.I):
        return 30, True
    return 30, False


def extract_entities(text: str, product_names: list[str], store_names: list[str]) -> tuple[Optional[str], Optional[str]]:
    """Find known product/store names without allowing arbitrary user text to become a filter."""
    lower = text.casefold()

    product = None
    for name in sorted(product_names, key=len, reverse=True):
        if name.casefold() in lower:
            product = name
            break

    store = None
    for name in sorted(store_names, key=len, reverse=True):
        if name.casefold() in lower:
            store = name
            break

    return product, store


def classify_query(
    text: str,
    product_names: Optional[list[str]] = None,
    store_names: Optional[list[str]] = None,
) -> QueryIntent:
    product_names = product_names or []
    store_names = store_names or []

    cleaned = " ".join(text.strip().split())
    intent, confidence, matched = _best_match(cleaned)
    period_days, explicit_period = _extract_period(cleaned)
    product, store = extract_entities(cleaned, product_names, store_names)

    # Explicit product questions should default to product performance.
    if intent == "GENERAL" and product:
        intent = "PRODUCT_PERFORMANCE"
        confidence = 0.65

    # "What is running out?" is the canonical stockout question.
    if re.search(r"\bwhat is running out\b|\bwhat's running out\b", cleaned, re.I):
        intent = "STOCKOUT_RISK"
        confidence = 0.98

    compare_previous = (
        intent in {"PRODUCT_PERFORMANCE", "STORE_PERFORMANCE", "SALES_DROP", "SALES_SPIKE"}
        or bool(re.search(r"\bcompare|previous|last period|vs\b", cleaned, re.I))
    )

    return QueryIntent(
        name=intent,
        product_name=product,
        store_name=store,
        period_days=period_days,
        compare_previous=compare_previous,
        confidence=confidence,
        matched_terms=matched,
    )
