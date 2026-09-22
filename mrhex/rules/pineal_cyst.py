"""Deterministic Standalone Fallback Rules for Cyst of pineal gland.

Implements accepted standalone rules:
  - PC-ST-1: Hedged or question-marked pineal cyst or cystic variant -> UC
  - PC-ST-2: Affirmed pineal cyst, cystic variant, or cystic lesion in pineal gland -> S
  - PC-ST-3: Explicit negation of pineal cyst -> C

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
PINEAL_ANCHOR = re.compile(r"\b(?:pineal|epithalamus)\b", re.I)
PINEAL_TUMOR_EXCLUSION = re.compile(r"\b(?:pineocytoma|pineoblastoma|germinoma|teratoma)\b", re.I)

# ------------------------------------------------------------------------------
# PC-ST-1: Hedged / Equivocal / Question Mark -> UC
# ------------------------------------------------------------------------------
PC_ST1_HEDGED = re.compile(
    r"(?:"
    r"pineal\s+(?:gland\s+)?cysts?\s*\?|"
    r"\(\s*pineal\s+(?:gland\s+)?cysts?\s*\?\s*\)|"
    r"variant\s+cystic\s+pineal\s+gland\s*\?|"
    r"pineal\s+gland\s+cyst\s+with\s+dense\s+content[^.;\n]*\?"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# PC-ST-2: Affirmed Pineal Cyst or Cystic Variant -> S
# ------------------------------------------------------------------------------
PC_ST2_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\b(?:benign\s+)?pineal\s+(?:gland\s+)?cysts?\b|"
    r"\b(?:pineal\s+gland\s+)?cystic\s+variant\s+(?:of\s+(?:the\s+)?pineal\s+gland)?\b|"
    r"\bcystic\s+areas?\s+(?:were|was|is|are)\s+observed\s+in\s+the\s+pineal\s+gland\b|"
    r"\bpineal\s+gland\s+is\s+cystic\s+in\s+form\b|"
    r"\b(?:simple\s+)?cysts?\b(?:(?!\.\s+[A-Z])[^;\n]){0,160}\b(?:in|of|formed\s+in)\s+the\s+pineal\s+(?:gland\s+)?(?:region|area)?\b|"
    r"\bin\s+the\s+pineal\s+(?:gland\s+)?(?:region|area)?\b(?:(?!\.\s+[A-Z])[^;\n]){0,160}\b(?:simple\s+)?cysts?\b|"
    r"\bcystic\s+structures?\b(?:(?!\.\s+[A-Z])[^;\n]){0,160}\b(?:in|formed\s+in)\s+the\s+pineal\s+gland\b|"
    r"\bcompatible\s+with\s+a\s+pineal\s+gland\s+cyst\b"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# PC-ST-3: Explicit Negation -> C
# ------------------------------------------------------------------------------
PC_ST3_NEGATION = re.compile(
    r"(?:"
    r"\bno\s+(?:evidence\s+of\s+)?(?:a\s+)?pineal\s+(?:gland\s+)?cysts?\b|"
    r"\bpineal\s+(?:gland\s+)?cyst\s+is\s+not\s+(?:seen|observed|detected)\b"
    r")",
    re.I,
)


def evaluate_pineal_cyst_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Cyst of pineal gland."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    if not PINEAL_ANCHOR.search(clean_text):
        return None

    # Exclude solid pineal neoplasms without cystic finding
    if PINEAL_TUMOR_EXCLUSION.search(clean_text) and not re.search(r"\bcyst\b", clean_text, re.I):
        return None

    # 1. Hedged / Question mark -> UC
    if PC_ST1_HEDGED.search(clean_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "PC_ST1_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "PINEAL_CYST_QUESTION_OR_EQUIVOCAL"],
            "evidence_spans": [{"text": "hedged pineal cyst", "rule": "PC-ST-1"}],
        }

    # 2. Explicit Negation -> C
    if PC_ST3_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "PC_ST3_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "PINEAL_CYST_NEGATED"],
            "evidence_spans": [{"text": "no pineal cyst", "rule": "PC-ST-3"}],
        }

    # 3. Affirmed Pineal Cyst -> S
    if PC_ST2_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "PC_ST2_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "PINEAL_CYST_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed pineal cyst", "rule": "PC-ST-2"}],
        }

    return None
