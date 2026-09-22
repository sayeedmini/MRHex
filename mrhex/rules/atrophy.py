"""Deterministic Standalone Fallback Rules for Cerebral Atrophy.

Implements accepted standalone rules:
  - CA-1: Explicit atrophy lexical forms (involutional, age-related, diffuse, cortical, atrophic changes/dilation)
  - CA-2: Volume-loss synonyms with exclusions (parenchymal/brain/cerebral volume loss, excluding focal cavities)
  - CA-3: Indirect morphology / ex-vacuo pattern (prominent sulci + compensatory ventricular enlargement)

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# Assertion helpers
NEGATION_CUE = re.compile(
    r"\b(?:no\b|without|denies|negative\s+for|ruled\s+out|no\s+evidence\s+of|no\s+significant|are\s+normal)\b",
    re.I,
)
HEDGING_CUE = re.compile(
    r"\b(?:questionable|equivocal|possible|possibly|cannot\s+exclude|could\s+represent|"
    r"may\s+represent|in\s+favor\s+of|favoring|thought\s+to\s+be)\b|\?",
    re.I,
)

# ------------------------------------------------------------------------------
# CA-1: Explicit Atrophy Lexical Forms
# ------------------------------------------------------------------------------
CA1_PAT = re.compile(
    r"\b(?:"
    r"involutional\s+(?:cerebral\s+)?atrophy|"
    r"age-related\s+(?:cerebral\s+)?atrophy|"
    r"age\s+related\s+(?:cerebral\s+)?atrophy|"
    r"physiological\s+(?:cerebral\s+)?atrophy|"
    r"physiologic\s+(?:cerebral\s+)?atrophy|"
    r"senile\s+(?:cerebral\s+)?atrophy|"
    r"involutional\s+changes\s+consistent\s+with\s+(?:cerebral\s+)?atrophy|"
    r"(?:cerebellar\s+and\s+cerebral|cerebral\s+and\s+cerebellar|cerebellar-cerebral)\s+atrophic\s+changes?|"
    r"(?:diffuse\s+thinning|dilated|enlarged|findings|volume\s+loss)\s+compatible\s+with\s+(?:widespread\s+|diffuse\s+|cerebral\s+)?atrophy|"
    r"atrophic\s+dilation\s+(?:in|of)\s+(?:central\s+and\s+peripheral\s+)?(?:csf|ventricular)\s+spaces|"
    r"(?:cerebral|cortical|frontoparietal|temporoparietal|biparietal|hippocampal)\s+atrophic\s+changes?|"
    r"atrophy\s+and\s+gliosis\s+are\s+observed|"
    r"both\s+hippocampi\s+have\s+undergone\s+atrophy"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CA-2: Volume-Loss Synonyms with Exclusions
# ------------------------------------------------------------------------------
CA2_PAT = re.compile(
    r"\b(?:"
    r"(?:cerebral|brain|parenchymal|central|cerebral\s+and\s+cerebellar)\s+volume\s+loss|"
    r"volume\s+loss\s+(?:in|of)\s+(?:the\s+)?(?:cerebr\w+|brain|parenchyma|cerebral\s+white\s+matter)|"
    r"supra(?:-|\s+)and\s+infratentorial\s+volume\s+loss|"
    r"(?:lateral\s+)?ventricle[s]?\s+(?:is|are|appear|have)\s+(?:mildly\s+)?(?:dilated|enlarged)\s+(?:secondary|due)\s+to\s+(?:central\s+)?volume\s+loss"
    r")\b",
    re.I,
)
CA2_LOCAL_EXCLUSIONS = re.compile(
    r"\b(?:postoperative\s+cavity|porencephaly|porencephalic|focal\s+contusion|resection\s+cavity)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CA-3: Indirect Morphology / Ex-Vacuo Pattern
# ------------------------------------------------------------------------------
SULCAL_PAT = re.compile(
    r"\b(?:"
    r"sulc\w*\s+are\s+deepened|"
    r"sulcal\s+deepening|"
    r"deepening\s+of\s+(?:the\s+)?(?:cortical\s+|cerebral\s+|hemispheric\s+)?sulci|"
    r"(?:depth\s+and\s+width|depth|width)\s+of\s+(?:the\s+)?(?:hemispheric\s+|cerebral\s+)?(?:cortical\s+)?sulci\s+(?:are|is)\s+increased|"
    r"prominence\s+in\s+hemispheric\s+cortical\s+sulci|"
    r"prominence\s+is\s+observed\s+in\s+(?:the\s+)?(?:hemispheric\s+)?cortical\s+sulci|"
    r"fissures\s+are\s+observed\s+to\s+be\s+more\s+prominent|"
    r"cerebral\s+and\s+cerebellar\s+csf\s+spaces\s+are\s+widened|"
    r"widening\s+is\s+observed\s+in\s+(?:the\s+)?cerebral\s+and\s+cerebellar\s+csf\s+spaces"
    r")\b",
    re.I,
)

VENTRIC_PAT = re.compile(
    r"\b(?:"
    r"(?:third\s+and\s+)?(?:lateral\s+)?ventric\w*\s+(?:are|appear|is)\s+(?:mildly\s+|minimally\s+|slightly\s+)?(?:dilated|enlarged|prominent|widened)|"
    r"compensatory\s+ventricular\s+(?:enlargement|dilation)|"
    r"ex\s*[- ]\s*vacuo\s+dilation|"
    r"ventricular\s+dilation\s+secondary\s+to\s+atrophy"
    r")\b",
    re.I,
)

HYDRO_EXCLUSIONS = re.compile(
    r"\b(?:hydrocephalus|normal\s+pressure\s+hydrocephalus|nph|obstructive|communicating|"
    r"transependymal|aqueduct\s+stenosis|mass\s+effect|intracranial\s+hypertension)\b",
    re.I,
)


def evaluate_cerebral_atrophy_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone rules CA-1, CA-2, and CA-3 for Cerebral Atrophy.

    Returns a dict with standalone_state, fallback_rule_id, reason_code, evidence_spans
    if a candidate rule matches, or None to continue with standard fallback.
    """
    # 1. Rule CA-1: Explicit atrophy lexical forms
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = CA1_PAT.search(line_clean)
        if m:
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            if NEGATION_CUE.search(prefix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_CA1_EXPLICIT_ATROPHY_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "CA1_EXPLICIT_ATROPHY"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_CA1_EXPLICIT_ATROPHY_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "CA1_EXPLICIT_ATROPHY"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_CA1_EXPLICIT_ATROPHY_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "CA1_EXPLICIT_ATROPHY"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    # 2. Rule CA-2: Volume-loss synonyms with exclusions
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m = CA2_PAT.search(line_clean)
        if m:
            if CA2_LOCAL_EXCLUSIONS.search(line_clean):
                continue
            prefix = line_clean[max(0, m.start() - 40):m.start()]
            if NEGATION_CUE.search(prefix):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_CA2_VOLUME_LOSS_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED", "CA2_VOLUME_LOSS"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            if HEDGING_CUE.search(prefix):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_CA2_VOLUME_LOSS_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED", "CA2_VOLUME_LOSS"],
                    "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_CA2_VOLUME_LOSS_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "CA2_VOLUME_LOSS"],
                "evidence_spans": [{"text": m.group(0), "matched_term": m.group(0), "clause_text": line_clean}],
            }

    # 3. Rule CA-3: Indirect morphology / ex-vacuo pattern
    if not HYDRO_EXCLUSIONS.search(text):
        has_sulcal = False
        has_ventric = False
        sulcal_match = ""
        ventric_match = ""
        for line in text.splitlines():
            line_clean = line.strip()
            if not line_clean:
                continue
            m_s = SULCAL_PAT.search(line_clean)
            if m_s and not NEGATION_CUE.search(line_clean[max(0, m_s.start() - 30):m_s.start()]):
                has_sulcal = True
                sulcal_match = m_s.group(0)
            m_v = VENTRIC_PAT.search(line_clean)
            if m_v and not NEGATION_CUE.search(line_clean[max(0, m_v.start() - 30):m_v.start()]):
                has_ventric = True
                ventric_match = m_v.group(0)

        if has_sulcal and has_ventric:
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_CA3_INDIRECT_EX_VACUO_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "CA3_INDIRECT_EX_VACUO"],
                "evidence_spans": [
                    {"text": sulcal_match, "matched_term": sulcal_match, "clause_text": sulcal_match},
                    {"text": ventric_match, "matched_term": ventric_match, "clause_text": ventric_match},
                ],
            }

    return None
