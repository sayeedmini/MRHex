"""Deterministic Standalone Resolver for Mega cisterna magna (Batch 10)."""
from __future__ import annotations

import re
from typing import Any

# Confounders to strictly exclude
_PROMINENCE_WITHOUT_DIAGNOSIS = re.compile(
    r"\b(?:cisterna\s+magna\s+is\s+prominent|prominent\s+cisterna\s+magna|enlarged\s+cisterna\s+magna)\b",
    re.I,
)

# Negation
_NEG = re.compile(
    r"\b(?:no|without|absent|negative\s+for|free\s+of|ruled\s+out)\s+(?:evidence\s+of\s+)?(?:(?:posterior\s+fossa\s+)?(?:mega\s*cisterna\s+magna|mega\s+cistern))\b"
    r"|\b(?:mega\s*cisterna\s+magna|mega\s+cistern)\s+is\s+(?:not\s+(?:seen|observed|identified|detected)|ruled\s+out)\b"
    r"|\bcisterna\s+magna\s+is\s+normal\s+without\s+mega\s*cisterna\b",
    re.I,
)

# Target mention
_TARGET = re.compile(
    r"\b(?:mega\s*cisterna\s+magna|mega\s+cistern(?:\s+configuration)?)\b",
    re.I,
)

# Hedging & Differential
_HEDGE = re.compile(
    r"\b(?:possible|possibly|probable|probably|likely|compatible\s+with|suggestive\s+of|suggests?|differential|uncertain|thought\s+to\s+be|suspected)\b|\?",
    re.I,
)
_DIFFERENTIAL = re.compile(
    r"\b(?:arachnoid\s+cyst\s+(?:in\s+the\s+)?differential|differential\s+diagnosis[^.\n]{0,50}arachnoid|arachnoid\s+cyst\s+or\s+(?:retrocerebellar\s+)?mega\s*cisterna\s+magna|mega\s*cisterna\s+magna\s+or\s+arachnoid\s+cyst)\b"
    r"|\bthought\s+to\s+be\s+related\s+to[^.\n]{0,80}mega\s*cisterna\s+magna"
    r"|\bmega\s*cisterna\s+magna\s+versus\s+arachnoid\s+cyst\b",
    re.I,
)


def evaluate_mega_cisterna_magna_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Mega cisterna magna."""
    # Safety: Exclude non-specific prominence without explicit mega cisterna magna diagnosis
    if _PROMINENCE_WITHOUT_DIAGNOSIS.search(text) and not _TARGET.search(text):
        return None

    # 1. Negation
    if _NEG.search(text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "MCM_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    # 2. Check for target mention
    if not _TARGET.search(text):
        return None

    # 3. Differential / Hedging
    target_sentences = [s for s in re.split(r"[.\n]+", text) if _TARGET.search(s)]
    if _DIFFERENTIAL.search(text) or any(_HEDGE.search(s) for s in target_sentences):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "MCM_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    # 4. Affirmative
    return {
        "standalone_state": "S",
        "fallback_rule_id": "MCM_CURRENT_AFFIRMATIVE_S",
        "reason_code": "ASSERT_DIRECT_CURRENT",
    }
