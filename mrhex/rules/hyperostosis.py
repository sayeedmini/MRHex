"""Deterministic Standalone Fallback Rules for Hyperostosis of Skull.

Implements accepted standalone rules:
  - HY-ST-1: Direct skull bone & calvarial hyperostosis phrasing
  - HY-ST-2: Mass/meningioma-associated adjacent bone hyperostosis
  - HY-ST-3: Diffuse calvarial / cranial bone thickening
  - HY-ST-4: Hedged / uncertain hyperostosis
  - HY-ST-5: Normal variant / incidental conflict resolution

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# HY-ST-4: Hedged / Uncertain Skull Hyperostosis (Evaluated first)
# ------------------------------------------------------------------------------
HY_ST4_UNCERTAIN_PAT = re.compile(
    r"(?:\b(?:"
    r"minimal\s+hyperostosis\s+of\s+the\s+inner\s+table|"
    r"benign\s+cortical\s+variant\s*\/\s*minimal\s+hyperostosis"
    r")\b|\(hyperostosis\?\))",
    re.I,
)

# ------------------------------------------------------------------------------
# HY-ST-5: Normal Variant / Incidental Negation Conflict Override
# ------------------------------------------------------------------------------
HY_ST5_NORMAL_VARIANT_PAT = re.compile(
    r"\bother\s+than\s+normal\s+variant\s+hyperostosis\s+frontalis\s+interna\b",
    re.I,
)

# ------------------------------------------------------------------------------
# HY-ST-1: Direct Skull Bone & Calvarial Hyperostosis Phrasing
# ------------------------------------------------------------------------------
HY_ST1_DIRECT_PAT = re.compile(
    r"\b(?:"
    r"hyperostosis\s+(?:is\s+observed\s+)?in\s+(?:the\s+)?(?:(?:right|left|bilateral)\s+)?(?:frontal|parietal|occipital|calvarial|cranial)\s+bone(?:s)?|"
    r"hyperostosis\s+in\s+(?:the\s+)?(?:right|left|bilateral)?\s*frontal\s+and\s+parietal\s+bone(?:s)?|"
    r"hyperostosis\s+of\s+the\s+cranial\s+bones|"
    r"hyperostosis\s+in\s+the\s+cranium|"
    r"compatible\s+with\s+(?:Type\s+[A-Z]\s+)?hyperostosis\s+interna|"
    r"compatible\s+with\s+(?:mild\s+)?hyperostosis(?:\s+(?:of|in)\s+the\s+frontal\s+bone)?|"
    r"appearance\s+is\s+evaluated\s+as\s+compatible\s+with\s+hyperostosis|"
    r"^hyperostosis\."
    r")\b",
    re.I | re.M,
)

# ------------------------------------------------------------------------------
# HY-ST-2: Mass/Meningioma-Associated Adjacent Bone Hyperostosis
# ------------------------------------------------------------------------------
HY_ST2_ADJACENT_PAT = re.compile(
    r"\b(?:"
    r"(?:causing|creates?|producing)\s+hyperostosis\s+in\s+(?:the\s+)?adjacent\s+(?:bony\s+structure|bones?|bone)|"
    r"(?:causing|creates?)\s+hyperostosis\s+in\s+(?:the\s+)?(?:adjacent\s+)?(?:left\s+|right\s+)?(?:adjacent\s+)?(?:occipital\s+condyle|anterior\s+clinoid(?:\s+process)?|sphenoid\s+(?:wing|ridge)|petrous\s+apex)|"
    r"hyperostosis\s+(?:is\s+present\s+)?(?:in\s+the\s+vicinity\s+of\s+the\s+mass\s+)?at\s+the\s+(?:left\s+|right\s+)?petrous\s+apex|"
    r"hyperostosis\s+in\s+the\s+(?:left\s+|right\s+)?greater\s+sphenoid\s+wing|"
    r"hyperostosis\s+(?:and\s+cystic\s+degenerative\s+changes\s+)?at\s+the\s+clivus\s+and\s+sphenoid\s+base|"
    r"hyperostotic\s+frontal\s+sinus|"
    r"causing\s+hyperostosis\s+and\s+hyperaeration|"
    r"sclerosis[\-\s]hyperostosis\s+(?:is\s+present\s+)?(?:in\s+the\s+vicinity\s+of\s+the\s+mass\s+)?at\s+the\s+(?:left\s+|right\s+)?petrous\s+apex|"
    r"diffuse\s+thickening\s+and\s+hyperostosis\s+remain\s+residually\s+in\s+the\s+sphenoid\s+sinus\s+walls"
    r")\b",
    re.I,
)

# ------------------------------------------------------------------------------
# HY-ST-3: Diffuse Calvarial / Cranial Bone Thickening
# ------------------------------------------------------------------------------
HY_ST3_DIFFUSE_PAT = re.compile(
    r"\b(?:"
    r"diffuse\s+thickening\s+in\s+(?:the\s+)?calvarial\s+bone|"
    r"diffuse\s+thickening\s+and\s+hyperostosis\s+of\s+the\s+cranial\s+bones"
    r")\b",
    re.I,
)


def evaluate_hyperostosis_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone candidate rules for Hyperostosis of skull.

    Precedence Hierarchy:
      1. HY-ST-4: Hedged / uncertain hyperostosis -> UC
      2. HY-ST-5: Normal variant conflict override -> S
      3. HY-ST-1: Direct skull bone & calvarial phrasing -> S
      4. HY-ST-2: Mass/meningioma-associated adjacent bone hyperostosis -> S
      5. HY-ST-3: Diffuse calvarial bone thickening -> S

    Args:
      text: Medical report text.
      case_id: Case identifier for auditing.

    Returns:
      Dictionary with standalone_state, fallback_rule_id, reason_code, evidence_spans,
      or None if no candidate rule applies.
    """
    # Priority 1: Hedged / Uncertain
    m = HY_ST4_UNCERTAIN_PAT.search(text)
    if m:
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "HY_ST_4_UNCERTAIN",
            "reason_code": "ASSERT_HEDGED",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "HEDGED",
                "clause_text": m.group(0),
            }],
        }

    # Priority 2: Normal variant conflict resolution
    m = HY_ST5_NORMAL_VARIANT_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "HY_ST_5_NORMAL_VARIANT_OVERRIDE",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 3: Direct phrasing
    m = HY_ST1_DIRECT_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "HY_ST_1_DIRECT_PHRASING",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 4: Adjacent / Mass-associated
    m = HY_ST2_ADJACENT_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "HY_ST_2_ADJACENT_BONE",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 5: Diffuse thickening
    m = HY_ST3_DIFFUSE_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "HY_ST_3_DIFFUSE_THICKENING",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    return None
