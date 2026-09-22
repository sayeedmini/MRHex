"""Deterministic Standalone Fallback Rules for Empty Sella Syndrome.

Implements accepted standalone rules:
  - ES-ST-1: Direct lexical forms with Impression section priority (overrides equivocal finding phrases)
  - ES-ST-2: Dual-feature sellar morphology (suprasellar cistern herniation/expansion + pituitary flattening/compression)
  - ES-ST-3: Rejection of isolated reduced pituitary height (without sellar CSF expansion)
  - ES-ST-4: Equivalence of partial and complete empty sella
  - ES-ST-5: Strict handling of differential / hedged phrasing -> UC

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
# ES-ST-1: Direct Lexical Patterns in Impression
# ------------------------------------------------------------------------------
ES_ST1_PAT = re.compile(
    r"\bempty\s+sella(?:\s+syndrome|\s+turcica)?\b",
    re.I,
)

# ------------------------------------------------------------------------------
# ES-ST-2: Dual-Feature Morphology (CSF Extension + Pituitary Compression)
# ------------------------------------------------------------------------------
ES_ST2_CSF = re.compile(
    r"\b(?:"
    r"suprasellar\s+cistern\w*\s+appears\s+(?:mildly\s+)?herniated\s+into\s+the\s+sella|"
    r"suprasellar\s+cistern\w*\s+appears\s+to\s+herniate\s+into\s+the\s+(?:sella|sellar\s+fossa)|"
    r"suprasellar\s+cistern\w*\s+(?:herniation\s+(?:appearance\s+)?into\s+(?:the\s+)?sella|herniation\s+into\s+the\s+sella)|"
    r"suprasellar\s+cistern\w*\s+extends\s+into\s+the\s+sella|"
    r"suprasellar\s+cistern\w*\s+appears\s+dilated|"
    r"suprasellar\s+cistern\w*\s+is\s+widened|"
    r"suprasellar\s+cistern\w*\s+is\s+prominent\s+wide|"
    r"suprasellar\s+cisterna?\s+appears\s+mildly\s+widened|"
    r"suprasellar\s+cistern\w*\s+is\s+enlarged"
    r")\b",
    re.I,
)

ES_ST2_PIT = re.compile(
    r"\b(?:"
    r"pituitary(?:\s+gland)?\s+height\s+is\s+(?:markedly\s+|significantly\s+|diffusely\s+|mildly\s+)?decreased|"
    r"decrease\s+in\s+pituitary(?:\s+gland)?\s+height|"
    r"height\s+of\s+(?:the\s+)?pituitary(?:\s+gland)?\s+is\s+(?:significantly\s+|markedly\s+)?decreased|"
    r"pituitary(?:\s+gland)?\s+appears\s+compressed|"
    r"pituitary(?:\s+gland)?\s+is\s+compressed|"
    r"adenohypophysis(?:\s+gland)?\s+is\s+thinned|"
    r"pituitary(?:\s+gland)?\s+measured\s+approximately\s+[\d\.]+\s+mm|"
    r"gland\s+height\s+is\s+[\d\.]+\s+mm"
    r")\b",
    re.I,
)

# Explicit Exclusions: postoperative sellar cavities, germinoma, adenoma
ES_ST2_EXCLUSIONS = re.compile(
    r"\b(?:operated|transsphenoidal|germinoma|adenoma|resection\s+cavity)\b",
    re.I,
)


def evaluate_empty_sella_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Empty Sella Syndrome."""
    clean_text = text.replace("\r", " ")

    # Priority 1: ES-ST-1 Direct Impression Section Diagnosis
    in_impression = False
    for line in clean_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if re.search(r'\b(?:impression|sonuç)\b', line_clean, re.I):
            in_impression = True
        if in_impression:
            m = ES_ST1_PAT.search(line_clean)
            if m:
                prefix = line_clean[:m.start()]
                suffix = line_clean[m.end():]
                window = prefix[-40:] + " " + m.group(0) + " " + suffix[:40]
                if NEGATION_CUE.search(window):
                    return {
                        "standalone_state": "C",
                        "fallback_rule_id": "FALLBACK_ES_ST1_IMPRESSION_NEGATED",
                        "reason_code": "ASSERT_TARGET_NEGATED",
                        "reason_codes": ["ASSERT_TARGET_NEGATED"],
                        "evidence_spans": [],
                    }
                if HEDGING_CUE.search(window):
                    return {
                        "standalone_state": "UC",
                        "fallback_rule_id": "FALLBACK_ES_ST1_IMPRESSION_HEDGED",
                        "reason_code": "ASSERT_HEDGED",
                        "reason_codes": ["ASSERT_HEDGED"],
                        "evidence_spans": [],
                    }
                return {
                    "standalone_state": "S",
                    "fallback_rule_id": "FALLBACK_ES_ST1_IMPRESSION_AFFIRMED",
                    "reason_code": "ASSERT_DIRECT_CURRENT",
                    "reason_codes": ["ASSERT_DIRECT_CURRENT", "EMPTY_SELLA_IMPRESSION_AFFIRMED"],
                    "evidence_spans": [],
                }

    # Priority 2: ES-ST-2 Dual-Feature Sellar Morphology (CSF Extension + Pituitary Compression)
    if not ES_ST2_EXCLUSIONS.search(clean_text):
        has_csf = bool(ES_ST2_CSF.search(clean_text))
        has_pit = bool(ES_ST2_PIT.search(clean_text))
        if has_csf and has_pit:
            # Check for sentence-level hedging in the sellar finding
            for sent in re.split(r'[.\n]', clean_text):
                if (ES_ST2_CSF.search(sent) or ES_ST2_PIT.search(sent)) and HEDGING_CUE.search(sent):
                    return {
                        "standalone_state": "UC",
                        "fallback_rule_id": "FALLBACK_ES_ST2_CSF_PITUITARY_HEDGED",
                        "reason_code": "ASSERT_HEDGED",
                        "reason_codes": ["ASSERT_HEDGED", "DUAL_FEATURE_SELLAR_MORPHOLOGY_HEDGED"],
                        "evidence_spans": [],
                    }
            return {
                "standalone_state": "S",
                "fallback_rule_id": "FALLBACK_ES_ST2_CSF_PITUITARY_AFFIRMED",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "reason_codes": ["ASSERT_DIRECT_CURRENT", "DUAL_FEATURE_SELLAR_MORPHOLOGY_AFFIRMED"],
                "evidence_spans": [],
            }

    return None
