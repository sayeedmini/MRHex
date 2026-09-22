"""Deterministic Standalone Fallback Rules for Intracranial Aneurysm.

Implements accepted standalone rules:
  - AN-ST-1: Direct lexical variants (fusiform, saccular, blister-like aneurysmal dilation/dilatation/widening)
  - AN-ST-2: Vessel-specific expressions (ACom/AComA, MCA bifurcation, ICA, basilar, vertebral aneurysm)
  - AN-ST-3: Treated/coiled/clipped aneurysm (residual lumen -> S; surgical material/operated without residual -> H)
  - AN-ST-4: Uncertain aneurysm language (suspicious aneurysm, aneurysmal appearance, in favor of aneurysm, aneurysm?) -> UC
  - AN-ST-5: Strict infundibulum / vascular variant / extracranial exclusions

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Does NOT modify selective D2.
"""
from __future__ import annotations

import re
from typing import Any

# Shared assertion cues
NEGATION_CUE = re.compile(
    r"\b(?:no\b|without|denies|negative\s+for|ruled\s+out|no\s+evidence\s+of|no\s+significant|is\s+not\s+observed|not\s+detected)\b",
    re.I,
)
HEDGING_CUE = re.compile(
    r"\b(?:questionable|equivocal|possible|possibly|cannot\s+exclude|could\s+represent|"
    r"may\s+represent|in\s+favor\s+of|favoring|thought\s+to\s+be|suspicious\s+for|suspicious\s+appearance|"
    r"creating\s+suspicion|raises\s+suspicion|could\s+be)\b|\?",
    re.I,
)

# ------------------------------------------------------------------------------
# AN-ST-3: Treated / Historical Surgery Patterns
# ------------------------------------------------------------------------------
AN_ST3_HISTORICAL_PAT = re.compile(
    r"\b(?:operated\s+aneurysm|aneurysm\s+treatment)\b",
    re.I,
)
AN_ST3_RESIDUAL_PAT = re.compile(
    r"\b(?:"
    r"(?:coil[\-\s]stent|coiled|embolized|clipped|treated)\s+(?:appearances?\s+within\s+the\s+)?aneurysm\b[\s\S]{0,120}?\b(?:residual\s+lumen|residual\s+(?:aneurysm\s+)?filling|recurrent\s+(?:aneurysm\s+)?filling)\b|"
    r"(?:residual\s+lumen|residual\s+(?:aneurysm\s+)?filling|recurrent\s+(?:aneurysm\s+)?filling)\b[\s\S]{0,120}?\b(?:coil[\-\s]stent|coiled|embolized|clipped|treated)\s+aneurysm\b|"
    r"residual\s+lumen\s+dimensions\s+are\s+stable"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# AN-ST-4: Uncertain Aneurysm Phrasing (Evaluated with high priority before affirmative)
# ------------------------------------------------------------------------------
AN_ST4_UNCERTAIN_PAT = re.compile(
    r"(?:\b(?:"
    r"suspicious\s+(?:appearance\s+)?for\s+(?:an?\s+)?aneurysm|"
    r"suspicious\s+aneurysm(?:\s+appearance)?|"
    r"suspicious\s+aneurysmal\s+(?:dilation|dilatation)(?:\s+appearance)?|"
    r"creating\s+suspicion\s+of\s+(?:an?\s+)?(?:\d+mm\s+diameter\s+)?aneurysm|"
    r"evaluated\s+in\s+favor\s+of\s+aneurysm|"
    r"view\s+favoring\s+aneurysm|"
    r"aneurysmal\s+appearance"
    r")\b|\baneurysm\?)",
    re.I,
)

# ------------------------------------------------------------------------------
# AN-ST-1: Direct Lexical Variants
# ------------------------------------------------------------------------------
AN_ST1_PAT = re.compile(
    r"\b(?:"
    r"(?:fusiform|saccular|blister[\-\s]like)\s+aneurysmat\w*\s+dilatat\w*|"
    r"(?:fusiform|saccular|blister[\-\s]like)\s+aneurysmal\s+(?:dilation|dilatation|widening)|"
    r"(?:fusiform|saccular|blister[\-\s]like)\s+aneurysm\w*|"
    r"fusiform\s+aneurysmatic\s+dilatat\w*|"
    r"aneurysmatic\s+dilatat\w*|"
    r"saccular\s+aneurysmal\s+dilation|"
    r"blister[\-\s]like\s+aneurysmal\s+dilation|"
    r"fusiform\s+aneurysmal\s+(?:dilation|dilatation|widening)"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# AN-ST-2: Vessel-Specific Aneurysm Expressions
# ------------------------------------------------------------------------------
AN_ST2_PAT = re.compile(
    r"\b(?:"
    r"(?:AComA?|ACOM|anterior\s+communicating|MCA|middle\s+cerebral|ICA|internal\s+carotid|"
    r"basilar(?:\s+apex|\s+tip)?|vertebral(?:\s+artery)?|AICA|PICA|PCA)\s+(?:artery\s+)?(?:bifurcation\s+)?"
    r"(?:localization\s+|level\s+|location\s+)?(?:compatible\s+with\s+(?:an?\s+)?)?(?:thrombosed\s+)?aneurysm|"
    r"(?:stable\s+)?aneurysm\b[\s\S]{0,80}?\b(?:at|in|at\s+the\s+level\s+of)\s+(?:the\s+)?(?:right\s+|left\s+|bilateral\s+)?"
    r"(?:AComA?|ACOM|anterior\s+communicating|MCA(?:\s+bifurcation)?|middle\s+cerebral|ICA|internal\s+carotid|"
    r"basilar(?:\s+apex|\s+tip)?|vertebral(?:\s+artery)?|AICA|PICA|PCA)\b|"
    r"aneurysm\s+(?:measuring\s+[\d\.\sx]+\s+mm\s+)?(?:at|in)\s+(?:the\s+)?(?:right\s+|left\s+)?"
    r"(?:AComA?|ACOM|anterior\s+communicating|MCA(?:\s+bifurcation)?|middle\s+cerebral|ICA|internal\s+carotid|"
    r"basilar|vertebral|AICA|PICA|PCA)\b|"
    r"(?:AComA?|ACOM)\s+aneurysm|"
    r"(?:right\s+|left\s+)?middle\s+cerebral\s+artery\s+thrombosed\s+aneurysm"
    r")\b",
    re.I,
)

# AN-ST-5: Strict Exclusions (Extracranial arterial sites, pseudoaneurysm)
AN_ST_EXCLUSIONS = re.compile(
    r"\b(?:aorta|aortic|thoracic|abdominal|femoral|popliteal|pseudoaneurysm)\b",
    re.I,
)


def evaluate_aneurysm_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Intracranial Aneurysm."""
    clean_text = text.replace("\r", " ")

    # Priority 1: AN-ST-3 Historical / Operated without active residual lumen
    for line in clean_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if AN_ST3_HISTORICAL_PAT.search(line_clean):
            if not AN_ST3_RESIDUAL_PAT.search(clean_text):
                return {
                    "standalone_state": "H",
                    "fallback_rule_id": "FALLBACK_AN_ST3_TREATED_SURGICAL_H",
                    "reason_code": "HISTORICAL_ONLY",
                    "reason_codes": ["HISTORICAL_ONLY", "TREATED_OPERATED_ANEURYSM_NO_RESIDUAL"],
                    "evidence_spans": [],
                }

    # Priority 2: AN-ST-4 Uncertain language (before affirmative matching)
    for line in clean_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m4 = AN_ST4_UNCERTAIN_PAT.search(line_clean)
        if m4:
            matched = m4.group(0)
            prefix = line_clean[:m4.start()]
            suffix = line_clean[m4.end():]
            window = prefix[-60:] + " " + matched + " " + suffix[:60]
            if NEGATION_CUE.search(window):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_AN_ST4_UNCERTAIN_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED"],
                    "evidence_spans": [],
                }
            return {
                "standalone_state": "UC",
                "fallback_rule_id": "FALLBACK_AN_ST4_UNCERTAIN_UC",
                "reason_code": "ASSERT_HEDGED",
                "reason_codes": ["ASSERT_HEDGED", "UNCERTAIN_ANEURYSM_EXPRESSION"],
                "evidence_spans": [],
            }

    # Priority 3: AN-ST-3 Treated aneurysm with documented residual lumen
    for line in clean_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m3 = AN_ST3_RESIDUAL_PAT.search(line_clean)
        if m3:
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_AN_ST3_TREATED_RESIDUAL_S",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "TREATED_ANEURYSM_RESIDUAL_LUMEN_PRESENT"],
                "evidence_spans": [],
            }

    # Priority 4: AN-ST-1 Direct lexical variants
    for line in clean_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m1 = AN_ST1_PAT.search(line_clean)
        if m1:
            if AN_ST_EXCLUSIONS.search(line_clean):
                continue
            matched = m1.group(0)
            prefix = line_clean[:m1.start()]
            suffix = line_clean[m1.end():]
            window = prefix[-60:] + " " + matched + " " + suffix[:60]
            if NEGATION_CUE.search(window):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_AN_ST1_DIRECT_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED"],
                    "evidence_spans": [],
                }
            if HEDGING_CUE.search(window):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_AN_ST1_DIRECT_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED"],
                    "evidence_spans": [],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_AN_ST1_DIRECT_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "DIRECT_ANEURYSM_LEXICAL_VARIANT"],
                "evidence_spans": [],
            }

    # Priority 5: AN-ST-2 Vessel-specific expressions
    for line in clean_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        m2 = AN_ST2_PAT.search(line_clean)
        if m2:
            if AN_ST_EXCLUSIONS.search(line_clean):
                continue
            matched = m2.group(0)
            prefix = line_clean[:m2.start()]
            suffix = line_clean[m2.end():]
            window = prefix[-60:] + " " + matched + " " + suffix[:60]
            if NEGATION_CUE.search(window):
                return {
                    "standalone_state": "C",
                    "fallback_rule_id": "FALLBACK_AN_ST2_VESSEL_NEGATED",
                    "reason_code": "ASSERT_TARGET_NEGATED",
                    "reason_codes": ["ASSERT_TARGET_NEGATED"],
                    "evidence_spans": [],
                }
            if HEDGING_CUE.search(window):
                return {
                    "standalone_state": "UC",
                    "fallback_rule_id": "FALLBACK_AN_ST2_VESSEL_HEDGED",
                    "reason_code": "ASSERT_HEDGED",
                    "reason_codes": ["ASSERT_HEDGED"],
                    "evidence_spans": [],
                }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_AN_ST2_VESSEL_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "VESSEL_SPECIFIC_ANEURYSM_EXPRESSION"],
                "evidence_spans": [],
            }

    return None
