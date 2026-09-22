"""Deterministic Standalone Fallback Rules for Cerebral Edema.

Implements accepted standalone rules:
  - CE-ST-1: Edema surrounding mass/lesion syntactic variants
  - CE-ST-2: Edematous parenchymal changes & plural variants
  - CE-ST-3: Secondary / causal edema expressions
  - CE-ST-4: Hedged / infiltration-edema boundary resolution
  - CE-ST-5: Decreasing / regressing edema under therapy
  - CE-ST-6: Multi-lesion differential edema scoping
  - CE-ST-7: Strict non-cerebral / resolved edema exclusions

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Does NOT modify selective D2.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# CE-ST-7: Resolved / Disappeared Edema (Negation / Past -> C)
# ------------------------------------------------------------------------------
CE_ST7_RESOLVED_PAT = re.compile(
    r"\b(?:"
    r"disappearance\s+of\s+edema|"
    r"with\s+mass\s+excision\s+and\s+disappearance\s+of\s+edema|"
    r"edema\s+occurring\s+along\s+the\s+internal\s+capsule\s+has\s+disappeared|"
    r"edema\s+(?:effect\s+)?(?:extending\s+[^\.\n]+?)?(?:around\s+the\s+lesion,\s+)?seen\s+in\s+the\s+previous\s+examination,\s+is\s+not\s+observed\s+in\s+this\s+examination"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CE-ST-6: Multi-Lesion Differential Edema Scoping Override
# ------------------------------------------------------------------------------
CE_ST6_MULTI_LESION_PAT = re.compile(
    r"\b(?:"
    r"widespread\s+edema\s+observed\s+around\s+it|"
    r"progression\s+in\s+surrounding\s+edema|"
    r"vasogenic\s+edema[\s\S]{0,40}?middle\s+cerebellar\s+peduncle"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CE-ST-5: Decreasing / Regressing Edema Under Therapy (Active Current Disease -> S)
# ------------------------------------------------------------------------------
CE_ST5_DECREASING_PAT = re.compile(
    r"\b(?:"
    r"(?:vasogenic\s+)?edemas?\s+(?:around\s+(?:the\s+)?(?:lesion|mass|metastasis|tumor|it)\s+)?has\s+(?:also\s+|significantly\s+)?decreased|"
    r"(?:although\s+an\s+increase\s+in\s+lesion\s+size\s+was\s+observed,\s+)?the\s+edema\s+around\s+it\s+has\s+decreased|"
    r"thickness\s+of\s+the\s+edematous\s+residual\s+infiltration\b[\s\S]{0,40}?\bhas\s+(?:partially\s+)?decreased|"
    r"although\s+its\s+edema\s+(?:and\s+size\s+)?have?\s+decreased"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CE-ST-1: Surrounding Mass/Lesion Edema Phrasing
# ------------------------------------------------------------------------------
CE_ST1_SURROUNDING_PAT = re.compile(
    r"\b(?:"
    r"(?:prominent|extensive|widespread|marked|moderate|mild)\s+edema\s+is\s+observed\s+around\s+(?:the\s+)?(?:lesion|mass|metastasis|tumor)|"
    r"with\s+surrounding\s+edema|"
    r"edema\s+is\s+observed\s+(?:on\s+T2[\w\-]*\s+(?:images\s+|sequences?\s+)?)?at\s+the\s+periphery\s+of\s+(?:all\s+)?described\s+lesions?|"
    r"edema\s+is\s+also\s+observed\s+in\s+(?:the\s+)?(?:left\s+|right\s+)?(?:caudate\s+nucleus|frontal|temporal|parietal|occipital|thalamus|brainstem|cerebellum)|"
    r"edematous\s+areas\s+are\s+present\s+around\s+it|"
    r"edema\s+seen\s+as\s+hyperintense\s+on\s+(?:T2\s+and\s+FLAIR|FLAIR\s+and\s+T2)\s+sequences\s+surrounding\s+it"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CE-ST-2: Edematous Parenchymal Changes & Plural Variants
# ------------------------------------------------------------------------------
CE_ST2_PARENCHYMAL_PAT = re.compile(
    r"\b(?:"
    r"edematous\s+signal\s+increases|"
    r"vasogenic\s+edemas|"
    r"edematous\s+residual\s+infiltration|"
    r"edematous\s+(?:contrast[\-\s]enhancing\s+)?(?:subacute\s+)?(?:hemorrhagic\s+)?infarct|"
    r"edematous\s+T2\s+hyperintense\s+signal\s+changes|"
    r"surrounded\s+by\s+an\s+edematous\s+T2\s+hyperintense\s+ring[\-\s]like\s+signal"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CE-ST-3: Secondary / Causal Edema Expressions
# ------------------------------------------------------------------------------
CE_ST3_SECONDARY_PAT = re.compile(
    r"\b(?:"
    r"(?:signal\s+change|hyperintensity|appearance)\s+secondary\s+to\s+edema|"
    r"secondary\s+to\s+edema\s+is\s+present|"
    r"(?:effaced|compressed)\s+(?:in\s+the\s+[^\.\n]+)?due\s+to\s+edema|"
    r"due\s+to\s+(?:the\s+effect\s+of\s+)?edema|"
    r"effect\s+of\s+edema|"
    r"appearance\s+compatible\s+with\s+edema|"
    r"due\s+to\s+infarct\s+and\s+swelling"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# CE-ST-4: Hedged / Infiltration-Edema Boundary Resolution
# ------------------------------------------------------------------------------
CE_ST4_INFILTRATION_PAT = re.compile(
    r"\b(?:"
    r"(?:appearances?\s+)?compatible\s+with\s+edema[\s\/\-]infiltration|"
    r"favoring\s+vasogenic\s+edema|"
    r"gliotic\s+[\-\–]\s+edematous\s+signal\s*\?"
    r")\b",
    re.I,
)


def evaluate_cerebral_edema_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Cerebral edema.

    Precedence Hierarchy:
      1. CE-ST-7: Resolved / disappeared edema -> C
      2. CE-ST-6: Multi-lesion scoping override -> S
      3. CE-ST-5: Decreasing / regressing edema under therapy -> S
      4. CE-ST-1: Surrounding mass/lesion edema -> S
      5. CE-ST-2: Edematous parenchymal changes & plural variants -> S
      6. CE-ST-3: Secondary / causal edema -> S
      7. CE-ST-4: Edema-infiltration / Hedged -> S

    Args:
      text: Medical report text.
      case_id: Case identifier for auditing.

    Returns:
      Dictionary with standalone_state, fallback_rule_id, reason_code, evidence_spans,
      or None if no candidate rule applies.
    """
    # Priority 1: Resolved / Disappeared edema -> C
    m = CE_ST7_RESOLVED_PAT.search(text)
    if m:
        return {
            "standalone_state": "C",
            "fallback_rule_id": "CE_ST_7_RESOLVED_EDEMA",
            "reason_code": "ASSERT_TARGET_NEGATED",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "NEGATED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 2: Multi-lesion scoping override -> S
    m = CE_ST6_MULTI_LESION_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CE_ST_6_MULTI_LESION_OVERRIDE",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 3: Decreasing / regressing edema under therapy -> S
    m = CE_ST5_DECREASING_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CE_ST_5_DECREASING_EDEMA",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 4: Surrounding mass/lesion edema -> S
    m = CE_ST1_SURROUNDING_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CE_ST_1_SURROUNDING_EDEMA",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 5: Edematous parenchymal changes -> S
    m = CE_ST2_PARENCHYMAL_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CE_ST_2_PARENCHYMAL_EDEMA",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 6: Secondary / causal edema -> S
    m = CE_ST3_SECONDARY_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CE_ST_3_SECONDARY_EDEMA",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 7: Edema-infiltration / Hedged -> S
    m = CE_ST4_INFILTRATION_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "CE_ST_4_INFILTRATION_EDEMA",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    return None
