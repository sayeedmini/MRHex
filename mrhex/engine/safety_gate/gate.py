"""R13 — Conservative Final-State Gate.

All 14 mandatory routing triggers from the v2 policy specification.
Evaluates whether aggregated evidence satisfies all conservative safety
criteria for SAFE_RULE emission.

INVARIANT: if routing_decision == ROUTE_TO_LLM: deterministic_state MUST be null.

Coverage is SECONDARY to safety.
"""
from __future__ import annotations

import re
from typing import Optional

from mrhex.engine.types import (
    AlignmentStatus,
    ArchitectureStage,
    AssertionPolarity,
    CertaintyLevel,
    EvidenceState,
    EvidenceUnit,
    ReasonCode,
    RoutingDecision,
    Section,
    TemporalityClass,
)


# ---------------------------------------------------------------------------
# Mandatory Routing Triggers (14 from policy spec)
# ---------------------------------------------------------------------------

def evaluate_routing_triggers(
    evidence_units: list[EvidenceUnit],
    aggregation_reasons: list[ReasonCode],
) -> tuple[list[str], list[ReasonCode]]:
    """Evaluate all 14 mandatory routing triggers.

    Returns:
        (list of trigger IDs that fired, combined reason codes)
    """
    fired_triggers: list[str] = []
    all_reasons: list[ReasonCode] = list(aggregation_reasons)

    # Collect all reason codes from evidence units
    unit_reasons: set[ReasonCode] = set()
    in_compartment_units = [
        eu for eu in evidence_units
        if eu.anatomy_status != AlignmentStatus.CONFIRMED_MISMATCH
        and eu.subtype_status != AlignmentStatus.CONFIRMED_MISMATCH
    ]
    for eu in in_compartment_units:
        unit_reasons.update(eu.reason_codes)
    unit_reasons.update(aggregation_reasons)

    # TRG_EXPLICIT_CONFLICT
    if ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT in unit_reasons:
        fired_triggers.append("TRG_EXPLICIT_CONFLICT")

    # TRG_SPECIFIC_VS_BROAD_NORMAL
    if (ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT in unit_reasons and
            ReasonCode.BROAD_NORMAL_SCOPE in unit_reasons):
        fired_triggers.append("TRG_SPECIFIC_VS_BROAD_NORMAL")

    # TRG_SECTION_DISCREPANCY
    if (ReasonCode.SECTION_CERTAINTY_SHIFT in unit_reasons or
            ReasonCode.SECTION_LOCATION_MISMATCH in unit_reasons):
        fired_triggers.append("TRG_SECTION_DISCREPANCY")

    # TRG_MODALITY_DISCORDANCE
    if ReasonCode.MODALITY_DISCORDANCE in unit_reasons:
        fired_triggers.append("TRG_MODALITY_DISCORDANCE")

    # TRG_ANATOMY_MISMATCH (only for UNRESOLVED, not CONFIRMED)
    has_unresolved_anatomy = any(
        eu.anatomy_status == AlignmentStatus.UNRESOLVED for eu in evidence_units
    )
    if has_unresolved_anatomy:
        fired_triggers.append("TRG_ANATOMY_MISMATCH")
        if ReasonCode.ANATOMY_OR_COMPARTMENT_MISMATCH not in all_reasons:
            all_reasons.append(ReasonCode.ANATOMY_OR_COMPARTMENT_MISMATCH)

    # TRG_LATERALITY_MISMATCH
    if ReasonCode.LATERALITY_CONFLICT in unit_reasons:
        fired_triggers.append("TRG_LATERALITY_MISMATCH")

    # TRG_SUBTYPE_LINEAGE (only for UNRESOLVED, not CONFIRMED)
    has_unresolved_subtype = any(
        eu.subtype_status == AlignmentStatus.UNRESOLVED for eu in evidence_units
    )
    if (has_unresolved_subtype or
            ReasonCode.LINEAGE_UNESTABLISHED in unit_reasons or
            ReasonCode.CHRONICITY_UNESTABLISHED in unit_reasons or
            ReasonCode.UNVALIDATED_EQUIVALENCE in unit_reasons):
        fired_triggers.append("TRG_SUBTYPE_LINEAGE")

    # TRG_MIXED_HISTORICAL_CURRENT
    has_historical = any(
        eu.temporality in (TemporalityClass.HISTORICAL_ONLY, TemporalityClass.RESOLVED)
        for eu in evidence_units
    )
    has_definite_current = any(
        eu.temporality in (TemporalityClass.CURRENT, TemporalityClass.CHRONIC_CURRENT,
                          TemporalityClass.STABLE_CURRENT)
        and eu.assertion_polarity in (AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER)
        and eu.certainty == CertaintyLevel.DEFINITE
        for eu in evidence_units
    )
    has_ambiguous_or_unresolved = any(
        eu.temporality == TemporalityClass.AMBIGUOUS
        or eu.temporality in (TemporalityClass.RESIDUAL, TemporalityClass.REGRESSING)
        or (eu.temporality in (TemporalityClass.CURRENT, TemporalityClass.CHRONIC_CURRENT, TemporalityClass.STABLE_CURRENT)
            and eu.certainty != CertaintyLevel.DEFINITE)
        for eu in evidence_units
    )
    # Approved codebook policy: "Concurrent definite present X takes S."
    # TRG_MIXED_HISTORICAL_CURRENT fires when historical disease coexists with ambiguous
    # current residual, sequela, or recurrence where current status is unresolved.
    if has_historical and has_ambiguous_or_unresolved and not has_definite_current:
        fired_triggers.append("TRG_MIXED_HISTORICAL_CURRENT")
        if ReasonCode.CURRENT_RESIDUAL_OR_SEQUELA not in all_reasons:
            all_reasons.append(ReasonCode.CURRENT_RESIDUAL_OR_SEQUELA)

    # TRG_COMPLEX_UNCERTAINTY_SCOPE
    if (ReasonCode.MALFORMED_OR_COMPLEX_SCOPE in unit_reasons or
            ReasonCode.DIFFERENTIAL_OR_ALTERNATIVE in unit_reasons):
        # Check if there are multiple hedged units (complex scope)
        hedged_count = sum(1 for eu in evidence_units if eu.certainty in
                          (CertaintyLevel.HEDGED, CertaintyLevel.DIFFERENTIAL))
        if hedged_count > 1 or ReasonCode.MALFORMED_OR_COMPLEX_SCOPE in unit_reasons:
            fired_triggers.append("TRG_COMPLEX_UNCERTAINTY_SCOPE")

    # TRG_MULTI_LESION_MIXED_CERTAINTY
    if ReasonCode.LESION_SPECIFIC_CERTAINTY in unit_reasons:
        fired_triggers.append("TRG_MULTI_LESION_MIXED_CERTAINTY")

    # TRG_LIMITED_COVERAGE
    if ReasonCode.LIMITED_EXAM_OR_COVERAGE in unit_reasons:
        fired_triggers.append("TRG_LIMITED_COVERAGE")

    # TRG_MALFORMED_SCOPE
    has_ambiguous_polarity = any(
        eu.assertion_polarity == AssertionPolarity.AMBIGUOUS for eu in evidence_units
    )
    if has_ambiguous_polarity or ReasonCode.MALFORMED_OR_COMPLEX_SCOPE in unit_reasons:
        if "TRG_COMPLEX_UNCERTAINTY_SCOPE" not in fired_triggers and "TRG_MALFORMED_SCOPE" not in fired_triggers:
            fired_triggers.append("TRG_MALFORMED_SCOPE")

    # TRG_CLINICAL_ONLY_PROVENANCE
    # Fires only when target evidence is clinical indication/question without current radiologic assertion
    if ReasonCode.CLINICAL_ONLY_PROVENANCE in unit_reasons:
        has_radiologic_evidence = any(
            eu.section in (Section.FINDINGS, Section.IMPRESSION) for eu in evidence_units
        )
        if not has_radiologic_evidence:
            fired_triggers.append("TRG_CLINICAL_ONLY_PROVENANCE")

    # TRG_UNCERTAIN_EVIDENCE_ADEQUACY
    # (Handled via fallback module, not evidence-unit level)

    return fired_triggers, all_reasons


# ---------------------------------------------------------------------------
# Determine final evidence state from evidence units
# ---------------------------------------------------------------------------

def determine_candidate_state(
    evidence_units: list[EvidenceUnit],
) -> tuple[Optional[EvidenceState], str]:
    """Determine the candidate evidence state from processed evidence units.

    Returns:
        (candidate_state, primary_rule_family_id)
    """
    if not evidence_units:
        return None, ""

    # If any unit has ambiguous polarity, cannot determine state cleanly
    if any(eu.assertion_polarity == AssertionPolarity.AMBIGUOUS for eu in evidence_units):
        return None, ""

    # Classify each unit into state candidates
    s_candidates = []
    c_candidates = []
    uc_candidates = []
    h_candidates = []
    u_candidates = []

    has_radiologic_units = any(eu.section in (Section.FINDINGS, Section.IMPRESSION) for eu in evidence_units)

    for eu in evidence_units:
        # Skip units with confirmed mismatch (these support U)
        if (eu.anatomy_status == AlignmentStatus.CONFIRMED_MISMATCH or
                eu.subtype_status == AlignmentStatus.CONFIRMED_MISMATCH):
            u_candidates.append(eu)
            continue

        # If radiologic evidence is present in Findings/Impression, clinical indication in CLINICAL_HISTORY is overridden
        if has_radiologic_units and eu.section == Section.CLINICAL_HISTORY:
            continue

        if eu.assertion_polarity == AssertionPolarity.NEGATED:
            c_candidates.append(eu)
        elif eu.temporality in (TemporalityClass.HISTORICAL_ONLY, TemporalityClass.RESOLVED):
            # Past/resolved without current = H
            h_candidates.append(eu)
        elif eu.temporality == TemporalityClass.CLINICAL_INDICATION:
            # Clinical indication is not imaging evidence
            continue
        elif eu.certainty in (CertaintyLevel.HEDGED, CertaintyLevel.DIFFERENTIAL):
            uc_candidates.append(eu)
        elif eu.assertion_polarity in (AssertionPolarity.AFFIRMED,
                                       AssertionPolarity.NEGATED_MODIFIER):
            s_candidates.append(eu)
        else:
            u_candidates.append(eu)

    # Clinician Round 3 & Brain Metastasis Policy:
    # If report has affirmed brain metastasis (Route A or Route B),
    # an explicit exclusionary scoping negation ("no other parenchymal metastases", "no additional metastases", "apart from", "except", "focal")
    # does NOT negate the documented metastasis.
    if s_candidates and c_candidates:
        has_affirmed_metastasis = any(
            eu.target_pathology and "metastat" in eu.target_pathology.lower() and "brain" in eu.target_pathology.lower()
            for eu in s_candidates
        )
        is_exclusionary_negation = all(
            bool(re.search(r'\b(?:focal|other|additional|further)\b', eu.clause_text or eu.text, re.I)) or
            bool(re.search(r'\b(?:apart\s+from|except\s+for|except|with\s+the\s+exception\s+of|other\s+than|no\s+other|no\s+additional|no\s+further)\b', eu.clause_text or "", re.I))
            for eu in c_candidates
        )
        if has_affirmed_metastasis and is_exclusionary_negation:
            c_candidates = []

    # Determine state according to approved clinical codebook precedence:
    # "Concurrent definite present X takes S" -> S takes precedence over H
    if s_candidates and not c_candidates and not uc_candidates:
        return EvidenceState.S, "R13"
    # Codebook: "Past/resolved X without present X = H. Resolution does not become C merely because current absence is stated."
    if h_candidates and not s_candidates and not uc_candidates:
        return EvidenceState.H, "R13"
    if c_candidates and not s_candidates and not uc_candidates and not h_candidates:
        # If all c_candidates have exception clauses, negation is qualified/excepted -> route to review
        if any(bool(re.search(r'\b(?:apart\s+from|except\s+for|except|with\s+the\s+exception\s+of|other\s+than)\b', eu.clause_text or "", re.I)) for eu in c_candidates):
            return None, ""
        return EvidenceState.C, "R13"
    if uc_candidates and not s_candidates and not c_candidates:
        return EvidenceState.UC, "R13"
    if u_candidates and not s_candidates and not c_candidates and not uc_candidates and not h_candidates:
        return EvidenceState.U, "R13"

    # Mixed states — cannot determine without conflicts
    return None, ""


# ---------------------------------------------------------------------------
# Final Safety Gate
# ---------------------------------------------------------------------------

def apply_safety_gate(
    evidence_units: list[EvidenceUnit],
    aggregation_reasons: list[ReasonCode],
    fallback_state: Optional[EvidenceState] = None,
    fallback_routing: Optional[RoutingDecision] = None,
    fallback_reasons: Optional[list[str]] = None,
    fallback_triggers: Optional[list[str]] = None,
) -> tuple[Optional[EvidenceState], RoutingDecision, list[str], ArchitectureStage, Optional[str], list[str]]:
    """Apply the R13 conservative final-state gate.

    Args:
        evidence_units: All processed evidence units.
        aggregation_reasons: Reason codes from aggregation stage.
        fallback_state: State from fallback logic (when no evidence found).
        fallback_routing: Routing from fallback logic.
        fallback_reasons: Reasons from fallback logic.
        fallback_triggers: Triggers from fallback logic.

    Returns:
        (deterministic_state, routing_decision, reason_code_strings,
         architecture_stage_resolved, rule_family_id, fired_triggers)
    """
    # If no evidence was found, use fallback
    if not evidence_units:
        reasons = [str(r) for r in (fallback_reasons or [])]
        triggers = list(fallback_triggers or [])
        if fallback_routing == RoutingDecision.ROUTE_TO_LLM:
            return (None, RoutingDecision.ROUTE_TO_LLM, reasons,
                    ArchitectureStage.SAFETY_VALIDITY_GATE, None, triggers)
        return (fallback_state, fallback_routing or RoutingDecision.SAFE_RULE,
                reasons, ArchitectureStage.SAFETY_VALIDITY_GATE, "R13", [])

    # Evaluate all mandatory routing triggers
    fired_triggers, all_agg_reasons = evaluate_routing_triggers(
        evidence_units, aggregation_reasons
    )

    # Collect all reason codes
    all_reason_codes: set[str] = set()
    for eu in evidence_units:
        for rc in eu.reason_codes:
            all_reason_codes.add(rc.value if hasattr(rc, "value") else str(rc))
    for rc in all_agg_reasons:
        all_reason_codes.add(rc.value if hasattr(rc, "value") else str(rc))

    # If any mandatory trigger fired → ROUTE_TO_LLM with null state
    if fired_triggers:
        return (None, RoutingDecision.ROUTE_TO_LLM,
                sorted(all_reason_codes),
                ArchitectureStage.SAFETY_VALIDITY_GATE, None, fired_triggers)

    # Determine candidate state
    candidate_state, rule_family = determine_candidate_state(evidence_units)

    if candidate_state is None:
        # Could not determine state cleanly → route
        return (None, RoutingDecision.ROUTE_TO_LLM,
                sorted(all_reason_codes),
                ArchitectureStage.SAFETY_VALIDITY_GATE, None, ["TRG_MULTI_LESION_MIXED_CERTAINTY"])

    # Add the primary reason code for the determined state
    if candidate_state == EvidenceState.S:
        all_reason_codes.add(ReasonCode.ASSERT_DIRECT_CURRENT.value)
    elif candidate_state == EvidenceState.C:
        all_reason_codes.add(ReasonCode.ASSERT_TARGET_NEGATED.value)
    elif candidate_state == EvidenceState.UC:
        all_reason_codes.add(ReasonCode.ASSERT_HEDGED.value)
    elif candidate_state == EvidenceState.H:
        all_reason_codes.add(ReasonCode.HISTORICAL_ONLY.value)

    # SAFE_RULE: emit state
    return (candidate_state, RoutingDecision.SAFE_RULE,
            sorted(all_reason_codes),
            ArchitectureStage.SAFETY_VALIDITY_GATE, rule_family, [])

