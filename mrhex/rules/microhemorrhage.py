"""Deterministic Standalone Fallback Rules for Silent Micro-Hemorrhage of Brain.

Implements accepted standalone rules:
  - MH-ST-1: Direct microhemorrhagic phrasing
  - MH-ST-2: Punctate hemorrhagic & petechial phrasing
  - MH-ST-3: Millimetric hemorrhagic & hemosiderin foci on SWI/gradient
  - MH-ST-4: Hypointense on gradient / SWI sequence considered hemorrhagic
  - MH-ST-5: Punctate susceptibility artifacts without prior hemorrhage
  - MH-ST-6: Hedged / uncertain microhemorrhage

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Preserves core rule invariance.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# MH-ST-1 Override: Affirmed multiple/numerous microhemorrhagic foci
# ------------------------------------------------------------------------------
MH_ST1_NUMEROUS_PAT = re.compile(
    r"\bnumerous\s+(?:hypointense\s+)?microhemorrhagic\s+foci\b",
    re.I,
)

# ------------------------------------------------------------------------------
# MH-ST-6: Hedged / Uncertain Microhemorrhage
# ------------------------------------------------------------------------------
MH_ST6_UNCERTAIN_PAT = re.compile(
    r"(?:"
    r"findings\s+secondary\s+to\s+contusion\s+or\s+microhemorrhage\?|"
    r"foci\s+of\s+microangiopathy\?|"
    r"microhemorrhagic\s+focus\?,\s*cavernoma\?|"
    r"susceptibility\s+artifacts\s+which\s+may\s+be\s+compatible\s+with\s+microhemorrhage|"
    r"subacute-chronic\s+hemorrhagic\s+infarct\?"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# MH-ST-1: Direct Microhemorrhagic Phrasing
# ------------------------------------------------------------------------------
MH_ST1_DIRECT_PAT = re.compile(
    r"(?:"
    r"hypointense\s+microhemorrhagic\s+foci|"
    r"\bmicrohemorrhagic\s+foci\b|"
    r"\bmicrohemorrhagic\s+focus\b|"
    r"microhemorrhage\s+becoming\s+prominent\s+on\s+SWI"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# MH-ST-2: Punctate Hemorrhagic & Petechial Phrasing
# ------------------------------------------------------------------------------
MH_ST2_PUNCTATE_PAT = re.compile(
    r"(?:"
    r"punctate\s+hemorrhagic\s+foc(?:us|i)|"
    r"punctate\s+petechial\s+hemorrhages"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# MH-ST-3: Millimetric Hemorrhagic & Hemosiderin Foci on SWI/Gradient
# ------------------------------------------------------------------------------
MH_ST3_MILLIMETRIC_PAT = re.compile(
    r"(?:"
    r"(?:millimeter|millimetric)(?:-|\s+)sized\s+hemorrhagic\s+foc(?:us|i)|"
    r"hemorrhagic\s+signal\s+of\s+millimetric\s+size|"
    r"scattered\s+millimetric\s+chronic\s+hemorrhages|"
    r"millimetric(?:\s+sized)?\s+hypointense\s+hemosiderin\s+areas|"
    r"punctate\s+hemosiderin-containing\b|"
    r"linear\s+hemorrhage\s+sequela|"
    r"millimetric\s+hypointense\s+foci.*?SWI|"
    r"hypointense\s+millimetric\s+lesions.*?SWI|"
    r"millimetric\s+T2A\s+hypointense\s+signal\s+findings.*?SWI"
    r")",
    re.I | re.DOTALL,
)

# ------------------------------------------------------------------------------
# MH-ST-4: Hypointense on Gradient / SWI Sequence Considered Hemorrhagic
# ------------------------------------------------------------------------------
MH_ST4_GRADIENT_PAT = re.compile(
    r"(?:"
    r"hypointense\s+(?:appearance\s+)?on\s+(?:the\s+)?gradient\s+sequence\s+(?:and\s+)?is\s+considered\s+hemorrhagic|"
    r"hypointense\s+chronic\s+hemorrhagic\s+signal\s+changes"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# MH-ST-5: Punctate Susceptibility Artifacts with Explicit Attribution
# Enforces safety boundaries:
# 1. Must have punctate susceptibility artifacts in parenchymal distribution
# 2. Must be accompanied by explicit cerebral amyloid angiopathy / microangiopathy /
#    microbleed / hemorrhage attribution
# 3. Must NOT be attributed to calcification/mineralization, cavernoma alone,
#    radiation necrosis, postoperative/metallic material, or vessel flow artifact
# ------------------------------------------------------------------------------
MH_ST5_SUSCEPTIBILITY_PAT = re.compile(
    r"\bpunctate\s+susceptibility\s+artifacts?\b",
    re.I,
)
MH_ST5_ATTRIBUTION_PAT = re.compile(
    r"\b(?:"
    r"amyloid\s+angiopathy|"
    r"microangiopath\w*|"
    r"microhemorrhag\w*|"
    r"microbleed\w*|"
    r"hemosiderin\w*|"
    r"chronic\s+hemorrhag\w*"
    r")\b",
    re.I,
)
MH_ST5_COMPETING_EXCLUSION_PAT = re.compile(
    r"\b(?:"
    r"radiation\s+necrosis|"
    r"radionecrosis|"
    r"rt\s+necrosis|"
    r"cavernoma\w*|"
    r"cavernous\s+(?:malformation\w*|angioma\w*|hemangioma\w*)|"
    r"calcif\w*|"
    r"mineraliz\w*|"
    r"post-?operat\w*|"
    r"metallic|"
    r"foreign\s+body|"
    r"clip\w*|"
    r"shunt|"
    r"flow\s+artifact|"
    r"pulsation\s+artifact"
    r")\b",
    re.I,
)


def evaluate_microhemorrhage_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Silent micro-hemorrhage of brain."""

    # Priority 1: Direct affirmed numerous microhemorrhagic foci override
    m = MH_ST1_NUMEROUS_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "MH_ST_1_DIRECT_PHRASING",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 2: Hedged / uncertain microhemorrhage -> UC
    m_uc = MH_ST6_UNCERTAIN_PAT.search(text)
    if m_uc:
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "MH_ST_6_HEDGED_UNCERTAIN",
            "reason_code": "ASSERT_UNCERTAIN",
            "evidence_spans": [{
                "matched_term": m_uc.group(0),
                "polarity": "AFFIRMED",
                "certainty": "HEDGED",
                "clause_text": m_uc.group(0),
            }],
        }

    # Priority 3: Direct microhemorrhagic phrasing -> S
    m = MH_ST1_DIRECT_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "MH_ST_1_DIRECT_PHRASING",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 4: Punctate hemorrhagic & petechial phrasing -> S
    m = MH_ST2_PUNCTATE_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "MH_ST_2_PUNCTATE_HEMORRHAGIC",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 5: Millimetric SWI / gradient foci -> S
    m = MH_ST3_MILLIMETRIC_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "MH_ST_3_MILLIMETRIC_SWI",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0)[:80],
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0)[:80],
            }],
        }

    # Priority 6: Gradient / SWI considered hemorrhagic -> S
    m = MH_ST4_GRADIENT_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "MH_ST_4_GRADIENT_CONSIDERED",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 7: Punctate susceptibility artifacts with explicit attribution -> S
    m = MH_ST5_SUSCEPTIBILITY_PAT.search(text)
    if m:
        # Enforce safety boundaries: exclude non-hemorrhagic causes and require attribution
        if not MH_ST5_COMPETING_EXCLUSION_PAT.search(text) and MH_ST5_ATTRIBUTION_PAT.search(text):
            return {
                "standalone_state": "S",
                "fallback_rule_id": "MH_ST_5_SUSCEPTIBILITY_ARTIFACT",
                "reason_code": "ASSERT_DIRECT_CURRENT",
                "evidence_spans": [{
                    "matched_term": m.group(0),
                    "polarity": "AFFIRMED",
                    "certainty": "DEFINITE",
                    "clause_text": m.group(0),
                }],
            }

    return None
