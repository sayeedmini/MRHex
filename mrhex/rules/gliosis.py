"""Deterministic Standalone Fallback Rules for Gliosis.

Implements accepted standalone rules:
  - G-ST-1: Hyphenated compounds (ischemic-gliotic, cystic-gliotic, sequel-gliotic, etc.)
  - G-ST-2: Sequel / scar terminology (gliotic scar, post-traumatic gliosis, gliotic sequelae/sequel/sequalae)
  - G-ST-3: Morphologic / chronic phrase variants (chronic gliotic foci, nonspecific gliotic foci, ischemic gliotic changes)

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# Assertion helpers
NEGATION_CUE = re.compile(
    r"\b(?:no\b|without|denies|negative\s+for|ruled\s+out|no\s+evidence\s+of|no\s+significant)\b",
    re.I,
)
HEDGING_CUE = re.compile(
    r"\b(?:questionable|equivocal|possible|possibly|cannot\s+exclude|could\s+represent|"
    r"may\s+represent|in\s+favor\s+of|favoring|thought\s+to\s+be)\b|\?",
    re.I,
)

# ------------------------------------------------------------------------------
# G-ST-1: Hyphenated Compounds
# ------------------------------------------------------------------------------
GST1_PAT = re.compile(
    r"\b(?:ischemic-gliotic|gliotic-ischemic|cystic-gliotic|encephalomalacic-gliotic|"
    r"gliotic-hemorrhagic|sequel-gliotic)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# G-ST-2: Sequel / Scar Terminology
# ------------------------------------------------------------------------------
GST2_PAT = re.compile(
    r"\b(?:"
    r"gliotic\s+scar(?:ring)?|"
    r"glial\s+scar(?:ring)?|"
    r"gliosis\s+scar(?:ring)?|"
    r"post[\-\s]?traumatic\s+glio\w*|"
    r"gliotic\s+sequel\w*|"
    r"sequel\w*\s+gliotic|"
    r"sequelae\s+gliotic"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# G-ST-3: Morphologic / Chronic Phrase Variants
# ------------------------------------------------------------------------------
GST3_PAT = re.compile(
    r"\b(?:"
    r"(?:stable\s+)?chronic\s+gliotic\s+foc(?:us|i)|"
    r"non[\-\s]?specific\s+(?:appearing\s+)?gliotic\s+(?:sequel\w*\s+)?foc(?:us|i)|"
    r"non[\-\s]?specific[,\s]+gliotic[,\s]+hyperintense|"
    r"ischemic\s+gliotic\s+(?:foc(?:us|i)|changes?)|"
    r"gliotic\s+change\s+secondary\s+to\s+remote\s+insult|"
    r"gliotic\s+tissues?|"
    r"gliotic\s+edematous\s+changes?|"
    r"is\s+gliotic"
    r")\b",
    re.I,
)


def evaluate_gliosis_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone rules G-ST-1, G-ST-2, and G-ST-3 for Gliosis.

    Returns a dict with standalone_state, fallback_rule_id, reason_code, evidence_spans
    if a candidate rule matches, or None to continue with standard fallback.
    """
    # 1. Rule G-ST-1: Hyphenated compounds
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = GST1_PAT.search(line_clean)
        if m:
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            if NEGATION_CUE.search(prefix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_GST1_HYPHENATED_COMPOUND_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "GST1_HYPHENATED_COMPOUND"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix) or HEDGING_CUE.search(line_clean):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_GST1_HYPHENATED_COMPOUND_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "GST1_HYPHENATED_COMPOUND"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_GST1_HYPHENATED_COMPOUND_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "GST1_HYPHENATED_COMPOUND"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    # 2. Rule G-ST-2: Sequel / scar terminology
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = GST2_PAT.search(line_clean)
        if m:
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            if NEGATION_CUE.search(prefix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_GST2_SEQUEL_SCAR_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "GST2_SEQUEL_SCAR"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix) or HEDGING_CUE.search(line_clean):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_GST2_SEQUEL_SCAR_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "GST2_SEQUEL_SCAR"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_GST2_SEQUEL_SCAR_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "GST2_SEQUEL_SCAR"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    # 3. Rule G-ST-3: Morphologic / chronic phrase variants
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = GST3_PAT.search(line_clean)
        if m:
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            if NEGATION_CUE.search(prefix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_GST3_CHRONIC_PHRASE_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "GST3_CHRONIC_PHRASE"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_GST3_CHRONIC_PHRASE_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "GST3_CHRONIC_PHRASE"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_GST3_CHRONIC_PHRASE_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "GST3_CHRONIC_PHRASE"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    return None
