"""Deterministic Standalone Fallback Rules for Intracranial Meningioma.

Implements accepted standalone rules:
  - MEN-ST-1: Postoperative / completely excised meningioma without residual -> H
  - MEN-ST-2: Hedged, equivocal, differential, or question-marked meningioma -> UC
  - MEN-ST-3: Affirmed current intracranial meningioma (singular, plural, calcified, dural tail) -> S
  - MEN-ST-4: Explicit negation of meningioma -> C

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Does NOT modify selective D2 (Invariant 4 preserved).
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# Anatomical / Pathological Exclusions
# ------------------------------------------------------------------------------
EXTRACRANIAL_SPINAL_EXCLUSION = re.compile(
    r"\b(?:spinal|spine|thoracic|lumbar|sacral|cervical\s+spine|intraspinal)\s+meningioma\b",
    re.I,
)

# ------------------------------------------------------------------------------
# MEN-ST-1: Postoperative Resection Without Residual -> H
# ------------------------------------------------------------------------------
MEN_ST1_POSTOP_RESECTION = re.compile(
    r"(?:"
    r"totally\s+excised\s+(?:[a-z\s-]{0,30})?meningioma|"
    r"grossly\s+totally\s+removed\s+and\s+there\s+is\s+no\s+enhancement\s+corresponding\s+to\s+residual|"
    r"meningioma\s+excision|"
    r"status\s+post\s+(?:intracranial\s+)?meningioma\s+resection|"
    r"previously\s+operated\s+meningioma\s+without\s+residual"
    r")",
    re.I | re.DOTALL,
)

# ------------------------------------------------------------------------------
# MEN-ST-2: Hedged / Equivocal / Question-Mark -> UC
# ------------------------------------------------------------------------------
MEN_ST2_QUESTION_OR_EQUIVOCAL = re.compile(
    r"(?:"
    r"meningiomas?\s*\?|"
    r"\(\s*meningiomas?\s*\?\s*\)|"
    r"\(\s*(?:calvarial\s+)?meningioma(?:\s+in\s+this\s+patient[^\)]*)?\?\s*\)|"
    r"probable\s+(?:calcified\s+)?meningiomas?|"
    r"meningioma\s+is\s+possible|"
    r"suggestive\s+of\s+(?:a\s+)?meningioma|"
    r"primarily\s+considered\s+meningioma[;,]?\s+(?:the\s+)?possibility\s+of\s+metastasis\s+[^.;\n]+cannot\s+be\s+(?:definitively\s+)?excluded|"
    r"initially\s+evaluated\s+as\s+favoring\s+meningioma[;.,]?\s+however[^\n;]*\bmetastasis\b|"
    r"evaluated\s+primarily\s+as\s+suggestive\s+of\s+meningioma"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# MEN-ST-3: Affirmed Current Intracranial Meningioma -> S
# ------------------------------------------------------------------------------
MEN_ST3_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\b(?:two|multiple|\d+)?\s*meningiomas?\b|"
    r"\bcalcified\s+meningiomas?\b|"
    r"\bconsistent\s+with\s+meningioma\b|"
    r"\bcompatible\s+with\s+meningioma\b|"
    r"\bin\s+favor\s+of\s+(?:calcified\s+)?meningioma\b|"
    r"\bmass\s+lesion\s+compatible\s+with\s+the\s+meninges\b[^.;\n]*(?:dural-based|dural\s+tail)"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# MEN-ST-4: Explicit Negation -> C
# ------------------------------------------------------------------------------
MEN_ST4_NEGATION = re.compile(
    r"(?:"
    r"\bno\s+(?:evidence\s+of\s+)?(?:intracranial\s+)?meningiomas?\b|"
    r"\bmeningioma\s+is\s+not\s+(?:seen|observed|detected)\b"
    r")",
    re.I,
)


def evaluate_meningioma_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Intracranial meningioma."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    # Exclude purely extracranial spinal meningiomas
    if EXTRACRANIAL_SPINAL_EXCLUSION.search(clean_text) and not any(
        w in clean_text.lower() for w in ("cranial", "brain", "vertex", "parasagittal", "falx", "tentorium", "sphenoid")
    ):
        return None

    # 1. Postoperative without residual -> H
    if MEN_ST1_POSTOP_RESECTION.search(clean_text):
        return {
            "standalone_state": "H",
            "fallback_rule_id": "MEN_ST1_POSTOP_RESECTION_H",
            "reason_code": "HISTORICAL_ONLY",
            "reason_codes": ["HISTORICAL_ONLY", "MENINGIOMA_FULLY_RESECTED"],
            "evidence_spans": [{"text": "meningioma postop resected", "rule": "MEN-ST-1"}],
        }

    # 2. Hedged / equivocal / question mark -> UC
    # Strip clinical indication/question headers so referring physician questions do not hedge radiologist findings
    radiologic_text_lines = [
        line for line in clean_text.splitlines()
        if not re.match(r"^\s*(?:clinical\s+information|indication|pre-diagnosis|preliminary\s+diagnosis)\s*:", line, re.I)
    ]
    radiologic_text = "\n".join(radiologic_text_lines)

    if MEN_ST2_QUESTION_OR_EQUIVOCAL.search(radiologic_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "MEN_ST2_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "MENINGIOMA_QUESTION_OR_EQUIVOCAL"],
            "evidence_spans": [{"text": "hedged meningioma", "rule": "MEN-ST-2"}],
        }

    # 3. Explicit Negation -> C
    if MEN_ST4_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "MEN_ST4_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "MENINGIOMA_NEGATED"],
            "evidence_spans": [{"text": "no meningioma", "rule": "MEN-ST-4"}],
        }

    # 4. Affirmed current meningioma -> S
    if MEN_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "MEN_ST3_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "MENINGIOMA_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed meningioma", "rule": "MEN-ST-3"}],
        }

    return None
