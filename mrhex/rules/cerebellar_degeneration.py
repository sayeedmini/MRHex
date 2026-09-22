"""Deterministic Standalone Fallback Rules for Cerebellar Degeneration.

Implements accepted standalone rules:
  - CD-ST-1: Hedged or equivocal cerebellar volume changes (e.g. widened folia without explicit atrophy) -> UC
  - CD-ST-2: Affirmed cerebellar atrophy, vermian atrophy, or atrophic cerebellum -> S
  - CD-ST-3: Explicit negation of cerebellar atrophy -> C

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Does NOT modify selective D2 (Invariant 4 preserved).
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# Anchors and Exclusions
# ------------------------------------------------------------------------------
CEREBELLAR_ANCHOR = re.compile(r"\b(?:cerebell\w*|vermis|vermian|posterior\s+fossa)\b", re.I)

# ------------------------------------------------------------------------------
# CD-ST-1: Hedged / Equivocal -> UC
# ------------------------------------------------------------------------------
CD_ST1_HEDGED = re.compile(
    r"(?:"
    r"cerebellar\s+(?:atrophy|degeneration)\s*\?|"
    r"\(\s*cerebellar\s+(?:atrophy|degeneration)\s*\?\s*\)|"
    r"\bcerebellar\s+folia\s+are\s+widened\b(?!\s+(?:secondary\s+to|compatible\s+with|consistent\s+with)\s+atrophy)"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# CD-ST-2: Affirmed Cerebellar Atrophy / Degeneration -> S
# ------------------------------------------------------------------------------
CD_ST2_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\b(?:superior\s+)?cerebellar\s+(?:and\s+vermis\s+)?atrophy\b|"
    r"\bvermi(?:s|an)\s+atrophy\b|"
    r"\bcerebellar\s+(?:parenchymal\s+signal\s+is\s+normal[;,]?\s+but\s+)?atrophy\s+is\s+present\b|"
    r"\batrophic\s+changes\s+(?:are\s+observed|have\s+been\s+noted)\s+in\s+(?:both\s+)?cerebellar\s+hemispheres\b|"
    r"\batrophic\s+changes\s+are\s+observed\s+in\s+both\s+cerebral\s+and\s+cerebellar\s+hemispheres\b|"
    r"\bthere\s+is\s+severe\s+atrophy\s+present\s+in\s+the\s+cerebellum\b|"
    r"\bthe\s+cerebellum\s+is\s+atrophic\b|"
    r"\bcerebellar\s+folia\s+are\s+widened\s+secondary\s+to\s+atrophy\b|"
    r"\bwidening\s+compatible\s+with\s+atrophy\s+was\s+observed\s+in\s+the\s+cerebellar\s+folia\b|"
    r"\bcerebellar\s+folia\s+were\s+observed\s+dilated[;,]?\s+suggestive\s+of\s+cerebellar\s+atrophy\b|"
    r"\bwidening\s+of\s+the\s+cerebellar\s+folia\s+is\s+observed\b|"
    r"\bcerebellar\s+and\s+cerebral\s+atrophy\b|"
    r"\bcerebral\s+and\s+cerebellar\s+atrophy\b"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# CD-ST-3: Explicit Negation -> C
# ------------------------------------------------------------------------------
CD_ST3_NEGATION = re.compile(
    r"(?:"
    r"\bno\s+(?:evidence\s+of\s+)?cerebellar\s+(?:atrophy|degeneration)\b|"
    r"\bcerebellar\s+atrophy\s+is\s+not\s+(?:seen|observed|detected)\b"
    r")",
    re.I,
)


def evaluate_cerebellar_degeneration_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Cerebellar degeneration."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    if not CEREBELLAR_ANCHOR.search(clean_text):
        return None

    # 1. Hedged / Equivocal -> UC
    if CD_ST1_HEDGED.search(clean_text) and not CD_ST2_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "CD_ST1_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "CEREBELLAR_DEGENERATION_HEDGED"],
            "evidence_spans": [{"text": "hedged cerebellar degeneration", "rule": "CD-ST-1"}],
        }

    # 2. Explicit Negation -> C
    if CD_ST3_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "CD_ST3_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "CEREBELLAR_DEGENERATION_NEGATED"],
            "evidence_spans": [{"text": "no cerebellar atrophy", "rule": "CD-ST-3"}],
        }

    # 3. Affirmed Cerebellar Atrophy / Degeneration -> S
    if CD_ST2_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CD_ST2_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "CEREBELLAR_DEGENERATION_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed cerebellar atrophy", "rule": "CD-ST-2"}],
        }

    return None
