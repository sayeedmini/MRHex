"""Deterministic Standalone Resolver for Herniation of nucleus pulposus (Batch 10)."""
from __future__ import annotations

import re
from typing import Any

# Target patterns: explicit herniation, extrusion, protrusion in disc context
_TARGET = re.compile(
    r"\b(?:(?:central|paracentral|focal|broad-based|subligamentous|extruded|protruded|migrated|sequestered)?\s*(?:disc|discal|disk|intervertebral\s+disc)\s+(?:herniation|protrusion|extrusion|sequestration)s?)\b"
    r"|\b(?:(?:intervertebral\s+)?discs?\s+is\s+herniated)\b"
    r"|\b(?:herniated|extruded|protruded)\s+(?:nucleus\s+pulposus|intervertebral\s+disc|disc|disk)\b"
    r"|\b(?:presence\s+of\s+a\s+)?(?:central\s+)?protruded\s+herniation\b"
    r"|\b(?:minimal\s+)?herniations?\b[^.\n]{0,90}\bdis[ck]s?\b"
    r"|\bdis[ck]s?\b[^.\n]{0,90}\bherniations?\b"
    r"|\bherniated\s+nucleus\s+pulposus\b"
    r"|\bHNP\b",
    re.I,
)

# Negation patterns (both pre-target and post-target)
_NEG = re.compile(
    r"\b(?:no|without|absent|negative\s+for|free\s+of)\s+(?:evidence\s+of\s+)?(?:significant\s+)?(?:disc|discal|disk|intervertebral\s+disc)?\s*(?:herniation|protrusion|extrusion|sequestration)s?\b"
    r"|\b(?:disc|discal|disk|intervertebral\s+disc)?\s*(?:herniation|protrusion|extrusion)\s+(?:is|are|was|were)?\s*not\s+(?:observed|seen|detected|identified)\b"
    r"|\bno\s+herniation\s+(?:finding\s+is\s+detected|is\s+present)\b"
    r"|\bno\s+(?:significant\s+)?protrusion\s+(?:was|is)?\s*(?:observed|seen|detected)\b"
    r"|\bwithout\s+herniation\s+or\s+protrusion\b",
    re.I,
)

# Historical / Post-operative
_HIST = re.compile(
    r"\b(?:status\s+post|s/p|prior|history\s+of|hx\s+of)\s+[^.\n]{0,60}(?:discectomy|disc\s+surgery|herniation\s+repair|herniated\s+(?:nucleus\s+pulposus|disc))\b"
    r"|\b(?:discectomy|disc\s+surgery|herniation\s+repair)\b",
    re.I,
)

# Hedging
_HEDGE = re.compile(
    r"\b(?:possible|possibly|probable|probably|likely|compatible\s+with|suggestive\s+of|suspicious\s+(?:for|of)|differential|uncertain)\b|\?",
    re.I,
)


# Exclusionary negation of remaining/other discs
_NEG_OTHER = re.compile(
    r"\b(?:other|remaining)\s+(?:[\w-]+\s+){0,3}dis[ck]s?\b",
    re.I,
)


def evaluate_herniation_nucleus_pulposus_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Herniation of nucleus pulposus."""
    sentences = [s.strip() for s in re.split(r"[.\n]+", text) if s.strip()]

    # Collect negated, historical, and affirmative sentences
    neg_sentences = [
        s for s in sentences
        if _NEG.search(s) and not _NEG_OTHER.search(s)
    ]
    hist_sentences = [s for s in sentences if _HIST.search(s)]
    target_sentences = [
        s for s in sentences
        if _TARGET.search(s) and not _NEG.search(s) and not _HIST.search(s)
    ]

    # 1. Historical-only
    if hist_sentences and not target_sentences:
        return {
            "standalone_state": "H",
            "fallback_rule_id": "HNP_POSTOP_HISTORICAL_H",
            "reason_code": "HISTORICAL_ONLY",
        }

    # 2. Explicit negation without unnegated target findings
    if neg_sentences and not target_sentences:
        return {
            "standalone_state": "C",
            "fallback_rule_id": "HNP_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
        }

    # 3. If no target mention found, return None (preserve default fallback)
    if not target_sentences:
        return None

    # 4. Check for hedging among target sentences
    hedged_sentences = [s for s in target_sentences if _HEDGE.search(s)]
    if len(hedged_sentences) == len(target_sentences):
        # All target mentions are hedged
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "HNP_HEDGED_UC",
            "reason_code": "ASSERT_HEDGED",
        }

    # 5. Affirmative current finding
    return {
        "standalone_state": "S",
        "fallback_rule_id": "HNP_CURRENT_AFFIRMATIVE_S",
        "reason_code": "ASSERT_DIRECT_CURRENT",
    }
