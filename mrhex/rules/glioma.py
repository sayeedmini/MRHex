"""Deterministic Standalone Fallback Rules for Glioma.

Implements accepted standalone rules:
  - GLM-ST-1: Affirmed high-grade / low-grade glial neoplasm
  - GLM-ST-2: Affirmed high-grade / low-grade glial tumor
  - GLM-ST-3: Affirmed high-grade / low-grade / diffuse glial mass
  - GLM-ST-4: Hedged / differential glial tumor / mass
  - GLM-ST-5: Resected / gross total excised glial tumor without clear residual
  - GLM-ST-6: Glioblastoma / GBM phrasing and differential reconciliation

Scope:
  Evaluated ONLY on routed cases during standalone fallback resolution.
  Does NOT modify selective D2.
"""
from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------------------
# GLM-ST-5: Resected / Gross Total Excised Glial Tumor Without Clear Residual
# ------------------------------------------------------------------------------
GLM_ST5_RESECTED_PAT = re.compile(
    r"(?:"
    r"low-grade\s+glial\s+tumor.*?was\s+excised|"
    r"gross\s+total\s+resected.*?glial|"
    r"gross\s+total\s+resected\s+giant\s+cell\s+astrocytoma"
    r")",
    re.I | re.DOTALL,
)

GLM_ST5_NO_RESIDUAL_PAT = re.compile(
    r"\bno\s+(?:clearly\s+identifiable\s+|clear\s+)?residual\s+lesion\b",
    re.I,
)

GLM_ST5_ACTIVE_RESIDUAL_PAT = re.compile(
    r"(?:"
    r"extension\s+of\s+the\s+residual\s+lesion|"
    r"residual\s+heterogeneous\s+enhancement|"
    r"residual\s+viable\s+tumoral\s+tissue|"
    r"Residual\s+component\s+is"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# GLM-ST-4: Hedged / Differential Glial Tumor / Mass
# ------------------------------------------------------------------------------
GLM_ST4_HEDGED_PAT = re.compile(
    r"(?:"
    r"multicentric\s+glial\s+tumor\?|"
    r"\(?glial\s+tumor\?\)?|"
    r"glial\s+tumor\s+in\s+differential\s+diagnosis\?|"
    r"\(?glioma\?\)?|"
    r"differential\s+diagnosis\s*\(\s*GBM\s*\?\s*\)"
    r")",
    re.I,
)

# ------------------------------------------------------------------------------
# GLM-ST-6: Glioblastoma / GBM Phrasing and Differential Reconciliation
# ------------------------------------------------------------------------------
GLM_ST6_GBM_PAT = re.compile(
    r"\b(?:multifocal\s+glioblastoma)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# GLM-ST-1: Affirmed High-Grade / Low-Grade Glial Neoplasm
# ------------------------------------------------------------------------------
GLM_ST1_NEOPLASM_PAT = re.compile(
    r"\b(?:high-grade|low-grade|diffuse|intra-axial)?\s*glial\s+neoplasm(?:s)?\b",
    re.I,
)

# ------------------------------------------------------------------------------
# GLM-ST-2: Affirmed High-Grade / Low-Grade Glial Tumor
# ------------------------------------------------------------------------------
GLM_ST2_TUMOR_PAT = re.compile(
    r"\b(?:high-grade|low-grade|diffuse|intra-axial)?\s*glial\s+tumor(?:s)?(?!\s*\?)\b",
    re.I,
)

# ------------------------------------------------------------------------------
# GLM-ST-3: Affirmed High-Grade / Low-Grade / Diffuse Glial Mass
# ------------------------------------------------------------------------------
GLM_ST3_MASS_PAT = re.compile(
    r"\b(?:high-grade|low-grade|diffuse|diffuse\s+infiltrative|intra-axial\s+high-grade)?\s*glial\s+mass(?:es)?(?!\s*\?)\b",
    re.I,
)


def evaluate_glioma_standalone(
    text: str,
    *,
    case_id: str = "",
) -> dict[str, Any] | None:
    """Evaluate standalone fallback rules for Glioma."""

    # Priority 1: Resected/excised glial tumor without clear residual -> H
    no_residual = bool(GLM_ST5_NO_RESIDUAL_PAT.search(text))
    has_active_residual = bool(GLM_ST5_ACTIVE_RESIDUAL_PAT.search(text))
    if no_residual or not has_active_residual:
        m = GLM_ST5_RESECTED_PAT.search(text)
        if m:
            return {
                "standalone_state": "H",
                "fallback_rule_id": "GLM_ST_5_RESECTED_EXCISED",
                "reason_code": "HISTORICAL_ONLY",
                "evidence_spans": [{
                    "matched_term": m.group(0)[:80],
                    "polarity": "AFFIRMED",
                    "certainty": "DEFINITE",
                    "clause_text": m.group(0)[:80],
                }],
            }

    # Priority 2: Hedged / differential glial tumor / mass -> UC
    m = GLM_ST4_HEDGED_PAT.search(text)
    if m:
        return {
            "standalone_state": "UC",
            "fallback_rule_id": "GLM_ST_4_HEDGED_DIFFERENTIAL",
            "reason_code": "ASSERT_UNCERTAIN",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "HEDGED",
                "clause_text": m.group(0),
            }],
        }

    # Priority 3: Multifocal glioblastoma -> S
    m = GLM_ST6_GBM_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "GLM_ST_6_GBM_RECONCILIATION",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 4: Glial neoplasm -> S
    m = GLM_ST1_NEOPLASM_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "GLM_ST_1_GLIAL_NEOPLASM",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 5: Glial tumor -> S
    m = GLM_ST2_TUMOR_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "GLM_ST_2_GLIAL_TUMOR",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    # Priority 6: Glial mass -> S
    m = GLM_ST3_MASS_PAT.search(text)
    if m:
        return {
            "standalone_state": "S",
            "fallback_rule_id": "GLM_ST_3_GLIAL_MASS",
            "reason_code": "ASSERT_DIRECT_CURRENT",
            "evidence_spans": [{
                "matched_term": m.group(0),
                "polarity": "AFFIRMED",
                "certainty": "DEFINITE",
                "clause_text": m.group(0),
            }],
        }

    return None
