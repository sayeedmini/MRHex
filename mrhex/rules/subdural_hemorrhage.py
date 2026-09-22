"""Deterministic Standalone Fallback Rules for Subdural Intracranial Hemorrhage.

Implements accepted standalone rules:
  - SDH-ST-1: Explicit negation of subdural hematoma/hemorrhage -> C
  - SDH-ST-2: Hedged or equivocal subdural collection -> UC
  - SDH-ST-3: Affirmed subdural hematoma, hemorrhage, or hemorrhagic/dense collection -> S

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
SUBDURAL_ANCHOR = re.compile(
    r"\b(?:subdural|extra-axial)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# SDH-ST-1: Explicit Negation -> C
# ------------------------------------------------------------------------------
SDH_ST1_NEGATION = re.compile(
    r"(?:"
    r"\bno\s+(?:evidence\s+of\s+)?(?:acute\s+|chronic\s+|subacute\s+)?subdural\s+(?:hematomas?|haematomas?|hemorrhages?|haemorrhages?|collections?)\b|"
    r"\bsubdural\s+(?:hematomas?|haematomas?|hemorrhages?|haemorrhages?)\s+is\s+not\s+(?:seen|observed|detected)\b|"
    r"\bno\s+(?:extra-axial\s+)?(?:or\s+intra-axial\s+)?collections?\s+or\s+hemorrhages?\b"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# SDH-ST-2: Hedged / Equivocal / Question Mark -> UC
# ------------------------------------------------------------------------------
SDH_ST2_HEDGED = re.compile(
    r"(?:"
    r"subdural\s+(?:hematomas?|haematomas?|hemorrhages?|haemorrhages?)\s*\?|"
    r"\(\s*subdural\s+(?:hematomas?|haematomas?|hemorrhages?|haemorrhages?)\s*\?\s*\)|"
    r"suspicious\s+for\s+(?:acute\s+|subacute\s+|chronic\s+)?subdural\s+(?:hematomas?|haematomas?|hemorrhages?|haemorrhages?)|"
    r"possible\s+(?:acute\s+|subacute\s+|chronic\s+)?subdural\s+(?:hematomas?|haematomas?|hemorrhages?|haemorrhages?)"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# SDH-ST-3: Affirmed Subdural Hematoma / Hemorrhage / Collection -> S
# ------------------------------------------------------------------------------
SDH_ST3_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\b(?:acute|subacute|chronic|early\s+subacute|late\s+subacute|linear|focal|right|left|bilateral)?\s*subdural\s+(?:and\s+subarachnoid\s+)?(?:linear\s+|focal\s+)?(?:hematomas?|haematomas?|hemorrhages?|haemorrhages?)\b|"
    r"\bhemorrhagic\s+subdural\s+collections?\b|"
    r"\bsubdural\s+(?:fluid\s+)?collections?\b[^.;\n]{0,80}\b(?:containing\s+blood(?:\s+elements)?|dense\s+content|blood\s+elements)\b|"
    r"\b(?:postoperative\s+)?collections?\b[^.;\n]{0,80}\b(?:with\s+dense\s+content\b[^.;\n]{0,40})?\bin\s+(?:the\s+)?subdural\s+space\b|"
    r"\bsubdural\s+space\s+of\s+the\s+[^.;\n]+(?:subdural\s+)?(?:and\s+intraparenchymal\s+)?hemorrhage\b"
    r")",
    re.I,
)


def evaluate_subdural_hemorrhage_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Subdural intracranial hemorrhage."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    if not SUBDURAL_ANCHOR.search(clean_text):
        return None

    # 1. Hedged -> UC
    if SDH_ST2_HEDGED.search(clean_text) and not SDH_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "SDH_ST2_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "SUBDURAL_HEMORRHAGE_HEDGED"],
            "evidence_spans": [{"text": "hedged subdural hemorrhage", "rule": "SDH-ST-2"}],
        }

    # 2. Affirmed current subdural hematoma/hemorrhage -> S
    if SDH_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "SDH_ST3_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "SUBDURAL_HEMORRHAGE_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed subdural hemorrhage", "rule": "SDH-ST-3"}],
        }

    # 3. Explicit Negation -> C
    if SDH_ST1_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "SDH_ST1_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "SUBDURAL_HEMORRHAGE_NEGATED"],
            "evidence_spans": [{"text": "no subdural hemorrhage", "rule": "SDH-ST-1"}],
        }

    return None
