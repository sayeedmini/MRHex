"""Deterministic Standalone Fallback Rules for Encephalomalacia.

Implements accepted standalone rules:
  - EN-ST-1: Direct adjectival/derived forms (encephalomalacic, ischemic encephalomalacia, post-infarct encephalomalacia)
  - EN-ST-2: Combined gliotic/encephalomalacic expressions (encephalomalacic-gliotic, cystic encephalomalacia, encephalomalacia with gliosis)
  - EN-ST-3: Chronic/post-infarct descriptors (chronic encephalomalacic, converted to cystic encephalomalacia, encephalomalacic sequela)
  - EN-ST-4: Morphology-only candidates (cavitary tissue loss, parenchymal defect area, liquefactive parenchyma) with strict exclusions

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# Assertion helpers
NEGATION_CUE = re.compile(
    r"\b(?:no\b|without|denies|negative\s+for|ruled\s+out|no\s+evidence\s+of|no\s+significant|is\s+not\s+observed|not\s+detected)\b",
    re.I,
)
HEDGING_CUE = re.compile(
    r"\b(?:questionable|equivocal|possible|possibly|cannot\s+exclude|could\s+represent|"
    r"may\s+represent|in\s+favor\s+of|favoring|thought\s+to\s+be|suspicious\s+for|raises\s+suspicion)\b|\?",
    re.I,
)

# ------------------------------------------------------------------------------
# EN-ST-1: Direct adjectival/derived forms
# ------------------------------------------------------------------------------
EN_ST1_PAT = re.compile(
    r"\b(?:"
    r"encephalomalac\w*|"
    r"ischemic\s+encephalomalac\w*|"
    r"post[\-\s]?infarct\s+encephalomalac\w*"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# EN-ST-2: Combined gliotic/encephalomalacic expressions
# ------------------------------------------------------------------------------
EN_ST2_PAT = re.compile(
    r"\b(?:"
    r"encephalomalacic[\-\s]gliotic|"
    r"gliotic[\-\s]encephalomalacic|"
    r"encephalomalacia[\-\s]gliotic|"
    r"cystic\s+encephalomalacic|"
    r"cystic\s+encephalomalacia|"
    r"encephalomalacia\s+(?:with|and)\s+gliosis|"
    r"gliosis\s+and\s+encephalomalacia"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# EN-ST-3: Chronic/post-infarct descriptors with encephalomalacia
# ------------------------------------------------------------------------------
EN_ST3_PAT = re.compile(
    r"\b(?:"
    r"chronic\s+encephalomalacic|"
    r"old\s+infarct\s+(?:with\s+)?encephalomalac\w*|"
    r"converted\s+to\s+cystic\s+encephalomalacia|"
    r"encephalomalacic\s+parenchyma|"
    r"encephalomalacic\s+sequela\w*"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# EN-ST-4: Morphology-only candidates (High Risk with Strict Exclusions)
# ------------------------------------------------------------------------------
EN_ST4_PAT = re.compile(
    r"\b(?:"
    r"cavitary\s+tissue\s+loss|"
    r"focal\s+cystic\s+parenchymal\s+defect|"
    r"parenchymal\s+defect\s+area|parenchymal\s+defective\s+area|"
    r"parenchyma\s+is\s+liquefactive"
    r")\b",
    re.I,
)
EN_ST4_EXCLUSIONS = re.compile(
    r"\b(?:postoperative\s+cavity|resection\s+cavity|craniotomy|porencephalic\s+cyst|arachnoid\s+cyst)\b",
    re.I,
)


def evaluate_encephalomalacia_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Encephalomalacia."""
    # 1. Rule EN-ST-1: Direct adjectival/derived forms
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = EN_ST1_PAT.search(line_clean)
        if m:
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            suffix = line_clean[m.end():min(len(line_clean), m.end() + 40)]
            if NEGATION_CUE.search(prefix) or NEGATION_CUE.search(suffix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_EN_ST1_DIRECT_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "EN_ST1_DIRECT"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix) or HEDGING_CUE.search(suffix):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_EN_ST1_DIRECT_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "EN_ST1_DIRECT"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_EN_ST1_DIRECT_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "EN_ST1_DIRECT"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    # 2. Rule EN-ST-2: Combined gliotic/encephalomalacic expressions
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = EN_ST2_PAT.search(line_clean)
        if m:
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            suffix = line_clean[m.end():min(len(line_clean), m.end() + 40)]
            if NEGATION_CUE.search(prefix) or NEGATION_CUE.search(suffix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_EN_ST2_COMBINED_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "EN_ST2_COMBINED"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix) or HEDGING_CUE.search(suffix):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_EN_ST2_COMBINED_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "EN_ST2_COMBINED"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_EN_ST2_COMBINED_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "EN_ST2_COMBINED"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    # 3. Rule EN-ST-3: Chronic/post-infarct descriptors with encephalomalacia
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = EN_ST3_PAT.search(line_clean)
        if m:
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            suffix = line_clean[m.end():min(len(line_clean), m.end() + 40)]
            if NEGATION_CUE.search(prefix) or NEGATION_CUE.search(suffix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_EN_ST3_CHRONIC_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "EN_ST3_CHRONIC"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix) or HEDGING_CUE.search(suffix):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_EN_ST3_CHRONIC_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "EN_ST3_CHRONIC"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_EN_ST3_CHRONIC_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "EN_ST3_CHRONIC"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    # 4. Rule EN-ST-4: Morphology-only candidates (High Risk with Strict Exclusions)
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = EN_ST4_PAT.search(line_clean)
        if m:
            if EN_ST4_EXCLUSIONS.search(line_clean):
                continue
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            suffix = line_clean[m.end():min(len(line_clean), m.end() + 40)]
            if NEGATION_CUE.search(prefix) or NEGATION_CUE.search(suffix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_EN_ST4_MORPHOLOGY_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "EN_ST4_MORPHOLOGY"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix) or HEDGING_CUE.search(suffix):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_EN_ST4_MORPHOLOGY_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "EN_ST4_MORPHOLOGY"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_EN_ST4_MORPHOLOGY_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "EN_ST4_MORPHOLOGY"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    return None
