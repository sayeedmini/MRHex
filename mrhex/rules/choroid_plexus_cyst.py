"""Deterministic Standalone Resolver for Choroid plexus cyst (Batch 10)."""
from __future__ import annotations

import re
from typing import Any

# Confounders to strictly exclude
_CONFOUNDER_EXCLUDE = re.compile(
    r"\b(?:papilloma|carcinoma|tumou?r|neoplasm)\b",
    re.I,
)
_XANTHO_ONLY = re.compile(
    r"\bfavoring\s+xanthogranuloma\b|\bxanthogranuloma\s+in\s+the\s+choroid\b",
    re.I,
)

# Negation
_NEG = re.compile(
    r"\b(?:no|without|absent|negative\s+for|free\s+of)\s+(?:evidence\s+of\s+)?(?:choroid(?:al)?\s+plexus\s+cysts?|cysts?\s+(?:in|of)\s+(?:the\s+)?choroid\s+plexus)\b"
    r"|\bchoroid(?:al)?\s+plexus\s+cysts?\s+is\s+not\s+(?:seen|observed|detected|identified)\b"
    r"|\bchoroid\s+plexus\s+(?:is\s+)?normal\s+without\s+cyst\b",
    re.I,
)

# Historical
_HIST = re.compile(
    r"\b(?:history\s+of|status\s+post|prior|resolved|previous)\s+choroid(?:al)?\s+plexus\s+cysts?\b",
    re.I,
)

# Target mention
_TARGET = re.compile(
    r"\b(?:choroid(?:al)?\s+plexus\s+cysts?|cysts?\s+in\s+(?:(?:both|either|the)\s+)?choroid\s+plexus(?:\s+glomeruli)?)\b"
    r"|\bcystic\s+(?:lesion|focus|foci)\w*[^.\n]{0,60}choroid\s+plexus\w*"
    r"|\bchoroid\s+plexus\w*[^.\n]{0,60}cystic\s+(?:lesion|focus|foci)\w*",
    re.I,
)

# Hedging
_HEDGE = re.compile(
    r"\b(?:possible|possibly|probable|probably|likely|compatible\s+with|suggestive\s+of|differential|uncertain|cannot\s+(?:rule\s+out|exclude))\b|\?",
    re.I,
)
_CYST_XANTHO_DIFF = re.compile(
    r"choroid(?:al)?\s+plexus\s+cyst\s*[-/]\s*xanthogranuloma",
    re.I,
)


def evaluate_choroid_plexus_cyst_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Choroid plexus cyst."""
    # Safety: Exclude tumors / non-cyst neoplasms
    if _CONFOUNDER_EXCLUDE.search(text):
        return None

    # Safety: Pure xanthogranuloma without cyst affirmation
    if _XANTHO_ONLY.search(text) and not re.search(r"\bchoroid(?:al)?\s+plexus\s+cyst", text, re.I):
        return None

    # 1. Negation
    if _NEG.search(text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "CPC_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    # 2. Historical
    if _HIST.search(text):
        # If there is no separate current affirmative sentence, return H
        non_hist_sentences = [
            s for s in re.split(r"[.\n]+", text)
            if _TARGET.search(s) and not _HIST.search(s) and not re.search(r"\bresolved\b", s, re.I)
        ]
        if not non_hist_sentences:
            return {
                "standalone_state": "H",
                "fallback_rule_id": "CPC_HISTORICAL_H",
                "reason_code": "HISTORICAL_ONLY",
            }

    # 3. Check for target mention
    if not _TARGET.search(text):
        return None

    # Find the specific sentence containing the target
    local_sentence = next(
        (s for s in re.split(r"[.\n]+", text) if _TARGET.search(s)),
        text,
    )

    # 4. Hedging
    if _CYST_XANTHO_DIFF.search(text) or _HEDGE.search(local_sentence):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "CPC_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    # 5. Affirmative
    return {
        "standalone_state": "S",
        "fallback_rule_id": "CPC_CURRENT_AFFIRMATIVE_S",
        "reason_code": "ASSERT_DIRECT_CURRENT",
    }
