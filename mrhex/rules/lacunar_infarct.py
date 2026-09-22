"""Deterministic Standalone Fallback Rules for Lacunar Infarct.

Implements accepted standalone rules:
  - LAC-ST-1: Historical-only old lacunar infarcts -> H
  - LAC-ST-2: Hedged or question-marked lacunar infarct / lacune -> UC
  - LAC-ST-3: Affirmed lacune, lacunes, lacunar formation, or deep punctate/millimetric infarct -> S
  - LAC-ST-4: Explicit negation of lacunar infarct / lacunes -> C

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# LAC-ST-1: Historical-Only -> H
# ------------------------------------------------------------------------------
LAC_ST1_HISTORICAL = re.compile(
    r"(?:"
    r"\bold\s+lacunar\s+formations?\b|"
    r"past\s+cerebrovascular\s+event[^.;\n]*\bold\s+lacunar\s+formations\b|"
    r"history\s+of\s+(?:prior\s+)?lacunar\s+infarcts?"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# LAC-ST-2: Hedged / Equivocal / Question Mark -> UC
# ------------------------------------------------------------------------------
LAC_ST2_HEDGED = re.compile(
    r"(?:"
    r"lacunes?\s*\?|"
    r"\(\s*lacunes?\s*\?\s*\)|"
    r"lacunar\s+infarcts?\s*\?|"
    r"\(\s*lacunar\s+infarcts?\s*\?\s*\)|"
    r"probable\s+lacunar\s+infarct"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# LAC-ST-3: Affirmed Lacune or Small Deep Infarct -> S
# ------------------------------------------------------------------------------
LAC_ST3_AFFIRMATIVE = re.compile(
    r"(?:"
    r"\b(?:acute|subacute|chronic|cystic|ischemic|old)?\s*lacunar\s+(?:and\s+cortical\s+)?(?:cystic\s+)?infarcts?\b|"
    r"\blacunar\s+(?:cystic\s+)?infarctions?\b|"
    r"\blacunar\s+formations?\b|"
    r"\b(?:cystic\s+)?lacunes?\s+(?:is|are|was|were)\s+(?:seen|observed|present|noted)\b|"
    r"\b(?:millimetric(?:\s+size|\s+sized)?|small)?\s*(?:cystic\s+)?lacunes?\b[^.;\n]{0,50}\bin\s+(?:the\s+)?(?:brainstem|pons|centrum\s+semiovale|cerebral\s+peduncle|thalamus|basal\s+ganglia|putamen|internal\s+capsule)\b|"
    r"\b(?:focal\s+)?punctate\s+(?:subacute|acute)?\s*infarct\b[^.;\n]{0,50}\bin\s+(?:the\s+)?(?:posterior\s+)?(?:right|left)?\s*(?:putamen|thalamus|pons|brainstem|lentiform)\b|"
    r"\bchronic\s+infarct\s+foci\b[^.;\n]{0,50}\bin\s+(?:the\s+)?(?:bilateral\s+)?lentiform\s+nuclei\b|"
    r"\bacute-subacute\s+millimetric\s+infarct\s+foci\b|"
    r"\bdiffusion-restricted\s+acute\s+infarct\s+with\s+a\s+diameter\s+of\s+\d+\s+mm\b[^.;\n]{0,50}\bin\s+(?:the\s+)?(?:left|right)?\s*hemisphere\s+of\s+the\s+pons\b|"
    r"\bmillimetric\s+acute\s+ischemic\s+lesions?\s+(?:is\s+|are\s+)?observed\s+at\s+the\s+level\s+of\s+the\s+head\s+of\s+the\s+(?:right\s+|left\s+)?caudate\s+nucleus\b"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# LAC-ST-4: Explicit Negation -> C
# ------------------------------------------------------------------------------
LAC_ST4_NEGATION = re.compile(
    r"(?:"
    r"\bno\s+(?:evidence\s+of\s+)?(?:acute\s+or\s+chronic\s+)?lacunar\s+infarcts?\b|"
    r"\bno\s+lacunes?\b|"
    r"\blacunar\s+infarct\s+is\s+not\s+(?:seen|observed|detected)\b"
    r")",
    re.I,
)


def evaluate_lacunar_infarct_standalone(text: str, *, case_id: str = "") -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Lacunar infarct."""
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    # 1. Historical-only old lacunar infarcts -> H
    # Only if not accompanied by acute/current active lesion
    if LAC_ST1_HISTORICAL.search(clean_text) and not re.search(r"\bacute\s+infarct\b", clean_text, re.I):
        return {
            "standalone_state": "H",
            "fallback_rule_id": "LAC_ST1_HISTORICAL_ONLY_H",
            "reason_code": "HISTORICAL_ONLY",
            "reason_codes": ["HISTORICAL_ONLY", "LACUNAR_HISTORICAL"],
            "evidence_spans": [{"text": "historical lacunar infarct", "rule": "LAC-ST-1"}],
        }

    # 2. Hedged / question-marked -> UC
    if LAC_ST2_HEDGED.search(clean_text):
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "LAC_ST2_HEDGED_EQUIVOCAL_UC",
            "reason_code": "ASSERT_HEDGED",
            "reason_codes": ["ASSERT_HEDGED", "LACUNAR_QUESTION_OR_EQUIVOCAL"],
            "evidence_spans": [{"text": "hedged lacunar", "rule": "LAC-ST-2"}],
        }

    # 3. Explicit Negation -> C
    if LAC_ST4_NEGATION.search(clean_text):
        return {
            "standalone_state": "C",
            "fallback_rule_id": "LAC_ST4_EXPLICIT_NEGATION_C",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "reason_codes": ["ASSERT_TARGET_NEGATED", "LACUNAR_NEGATED"],
            "evidence_spans": [{"text": "no lacunar infarct", "rule": "LAC-ST-4"}],
        }

    # 4. Affirmed current lacune / small deep infarct -> S
    if LAC_ST3_AFFIRMATIVE.search(clean_text):
        return {
            "standalone_state": "S",
            "fallback_rule_id": "LAC_ST3_AFFIRMATIVE_S",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "reason_codes": ["ASSERT_DIRECT_CURRENT", "LACUNAR_AFFIRMED"],
            "evidence_spans": [{"text": "affirmed lacunar", "rule": "LAC-ST-3"}],
        }

    return None
