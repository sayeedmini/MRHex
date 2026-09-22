"""Deterministic Standalone Fallback Rules for Watershed Infarct.

Implements accepted standalone rules:
  - WI-ST-1: Explicit negation of watershed/border-zone infarct -> C
  - WI-ST-2: Hedged or suggestive watershed infarct -> UC
  - WI-ST-3: Affirmed watershed or border-zone infarct / ischemia -> S

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# Anchors and Exclusions
# ------------------------------------------------------------------------------
WATERSHED_ANCHOR = re.compile(
    r"\b(?:watershed|\"?watershed\"?|border-?zones?|border\s+zones?)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# WI-ST-1: Explicit Negation -> C
# ------------------------------------------------------------------------------
WI_ST1_NEGATION = re.compile(
    r"(?:"
    r"\bno\s+(?:evidence\s+of\s+)?(?:acute\s+)?(?:watershed|border-?zone)\s+(?:infarcts?|infarctions?|ischemia)\b|"
    r"\b(?:watershed|border-?zone)\s+infarct\s+is\s+not\s+(?:seen|observed|detected)\b"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# WI-ST-2: Hedged / Suggestive -> UC
# ------------------------------------------------------------------------------
WI_ST2_HEDGED = re.compile(
    r"(?:"
    r"(?:watershed|border-?zone)\s+(?:infarcts?|infarctions?)\s*\?|"
    r"\(\s*(?:watershed|border-?zone)\s+(?:infarcts?|infarctions?)\s*\?\s*\)|"
    r"(?:consistent\s+with\s+a\s+)?watershed\s+zone\b[^.;\n]{0,100}\bsuggestive\s+of\b|"
    r"suspicious\s+for\s+(?:watershed|border-?zone)\s+(?:infarct|infarction)"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# WI-ST-3: Affirmed Watershed / Border-Zone Infarct -> S
# ------------------------------------------------------------------------------
WI_ST3_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\b(?:acute|subacute|chronic)?\s*(?:watershed|border-?zone)\s+(?:infarcts?|infarctions?|ischemi[ac]|lesions?)\b|"
    r"\b(?:infarcts?|infarctions?|ischemi[ac]|lesions?)\b[^.;\n]{0,60}\bin\s+(?:the\s+)?(?:bilateral\s+)?(?:anterior\s+and\s+deep\s+|deep\s+)?(?:\"?watershed\"?\s+)+areas?\b|"
    r"\b(?:infarcts?|infarctions?|ischemi[ac]|lesions?)\b[^.;\n]{0,120}\bin\s+(?:the\s+)?(?:[A-Z]{3}-[A-Z]{3}\s+)?watershed\s+perfusion\s+area\b|"
    r"\bfollowing\s+(?:the\s+)?(?:right\s+|left\s+)?(?:posterior\s+and\s+anterior\s+)?(?:\"?watershed\"?\s+)+areas?\b|"
    r"\b(?:in\s+)?(?:both\s+)?posterior\s+border\s+zones\b|"
    r"\bwatershed\s+perfusion\s+area\b|"
    r"\bwatershed\s+distribution\b"
    r")",
    re.I,
)


def evaluate_watershed_infarct_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Watershed infarct."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    if not WATERSHED_ANCHOR.search(clean_text):
        return None

    # 1. Hedged / suggestive -> UC
    if WI_ST2_HEDGED.search(clean_text) and not WI_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "WI_ST2_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "WATERSHED_INFARCT_HEDGED"],
            "evidence_spans": [{"text": "hedged watershed infarct", "rule": "WI-ST-2"}],
        }

    # 2. Affirmed current watershed infarct -> S
    if WI_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "WI_ST3_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "WATERSHED_INFARCT_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed watershed infarct", "rule": "WI-ST-3"}],
        }

    # 3. Explicit Negation -> C
    if WI_ST1_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "WI_ST1_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "WATERSHED_INFARCT_NEGATED"],
            "evidence_spans": [{"text": "no watershed infarct", "rule": "WI-ST-1"}],
        }

    return None
