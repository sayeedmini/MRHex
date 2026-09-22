"""MR-RATE Deterministic-v2 Selective-Routing Classifier (P1).

Post-primary, developmental, derived after inspection of Study-1 and Dev500.
NOT the original prospective deterministic comparator.
NOT independently validated yet.

Five-stage pipeline architecture:
  Stage 1: EVIDENCE_RETRIEVAL — Section parsing, vocabulary matching
  Stage 2: LOCAL_ASSERTION_INTERPRETATION — Negation, hedging, temporality
  Stage 3: TARGET_ALIGNMENT — Anatomy, laterality, subtype
  Stage 4: EVIDENCE_AGGREGATION — Cross-section, broad-normal, modality
  Stage 5: SAFETY_VALIDITY_GATE — 14-trigger routing gate, final state

System identifier: mrhex.engine
Status: DEVELOPMENT (NOT FROZEN)
"""
from __future__ import annotations

__version__ = "0.2.7a-pineal-composition-dev"

from typing import Any, Mapping

from mrhex.engine.types import (
    AlignmentStatus,
    ArchitectureStage,
    AssertionPolarity,
    CertaintyLevel,
    ClassificationResult,
    EvidenceState,
    EvidenceUnit,
    ReasonCode,
    RoutingDecision,
    Section,
    TemporalityClass,
)

# Stage 1: Evidence Retrieval
from mrhex.engine.retrieval.sections import (
    all_sections_present,
    section_for_offsets,
    split_report_sections,
)
from mrhex.engine.retrieval.matcher import extract_evidence

# Stage 2: Local Assertion Interpretation
from mrhex.engine.segmentation.sentences import sentence_for_offset
from mrhex.engine.segmentation.clauses import (
    clause_for_offset,
    is_coordination_ambiguous,
)
from mrhex.engine.assertion.negation import analyze_negation
from mrhex.engine.assertion.scoped_negation import classify_negation_extent
from mrhex.engine.assertion.hedging import analyze_hedging
from mrhex.engine.assertion.temporality import analyze_temporality

# Stage 3: Target Alignment
from mrhex.engine.alignment.anatomy import (
    check_anatomy_alignment,
    check_laterality_across_evidence,
)
from mrhex.engine.alignment.subtype import (
    check_lineage_established,
    check_lineage_unestablished,
    check_subtype_alignment,
)
from mrhex.engine.alignment.scope import annotate_evidence_scope

# Stage 4: Evidence Aggregation
from mrhex.engine.aggregation.conflict import (
    check_cross_section_consistency,
    check_evidence_conflicts,
    check_modality_discordance,
    check_specific_vs_broad_normal,
)
from mrhex.engine.aggregation.scoped import (
    resolve_any_in_scope,
    semantic_projection,
)
from mrhex.engine.aggregation.fallback import classify_no_match

# Stage 5: Safety & Validity Gate
from mrhex.engine.safety_gate.gate import (
    apply_safety_gate,
    evaluate_routing_triggers,
)
from mrhex.engine.safety_gate.output import (
    format_output,
    to_runner_dict,
)


__all__ = ["classify_deterministic_v2", ]

SYSTEM_ID = "mrhex.engine"
VERSION = "0.2.6.2-r3-metastatic-policy-dev"


def classify_deterministic_v2(
    report: object,
    entry: Mapping[str, Any],
    *,
    case_id: str = "",
    source_mode: str = "findings",
) -> dict[str, Any]:
    """Execute the deterministic-v2 P1 selective-routing classifier.

    Five-stage pipeline:
      1. EVIDENCE_RETRIEVAL
      2. LOCAL_ASSERTION_INTERPRETATION
      3. TARGET_ALIGNMENT
      4. EVIDENCE_AGGREGATION
      5. SAFETY_VALIDITY_GATE

    Args:
        report: Report text (str or None).
        entry: Codebook entry with machine_rules configuration.
        case_id: Unique case identifier.
        source_mode: "findings" or "full_report".

    Returns:
        Dictionary matching the v2 output contract (and runner-compatible fields).
    """
    text = "" if report is None else str(report)
    target_pathology = str(entry.get("label", entry.get("canonical_name", "")))
    machine = entry.get("machine_rules", {})
    if not isinstance(machine, Mapping):
        machine = {}

    scope_policy = machine.get("scope_policy", {})
    scope_annotation_enabled = bool(
        isinstance(scope_policy, Mapping) and scope_policy.get("enabled", False)
    )
    scope_presence_semantics = (
        str(scope_policy.get("presence_semantics", ""))
        if scope_annotation_enabled
        else ""
    )

    # ===================================================================
    # Stage 1: EVIDENCE_RETRIEVAL (R01)
    # ===================================================================
    sections_present = all_sections_present(text, source_mode=source_mode)
    evidence_units = extract_evidence(text, entry, target_pathology, source_mode=source_mode)

    # If no evidence found, use fallback logic
    if not evidence_units:
        related_non_equiv = machine.get("related_non_equivalent_patterns", [])
        fallback_state, fallback_routing, fallback_reasons, fallback_triggers = classify_no_match(
            text,
            sections_present,
            target_pathology,
            source_mode=source_mode,
            related_non_equivalent_patterns=related_non_equiv,
        )
        if fallback_state == EvidenceState.U and ReasonCode.RELATED_NON_EQUIVALENT_FINDING.value in fallback_reasons:
            fallback_stage = ArchitectureStage.TARGET_ALIGNMENT
            fallback_rule_family = "R07"
        elif fallback_routing == RoutingDecision.SAFE_RULE:
            fallback_stage = ArchitectureStage.EVIDENCE_RETRIEVAL
            fallback_rule_family = "R01"
        else:
            fallback_stage = ArchitectureStage.EVIDENCE_RETRIEVAL
            fallback_rule_family = None

        result = format_output(
            case_id=case_id,
            source_mode=source_mode,
            target_pathology=target_pathology,
            deterministic_state=fallback_state,
            routing_decision=fallback_routing,
            reason_codes=fallback_reasons,
            evidence_units=[],
            architecture_stage_resolved=fallback_stage,
            rule_family_id=fallback_rule_family,
            technical_status="SUCCESS",
            report_text=text,
            routing_trigger_ids=fallback_triggers,
        )
        d = to_runner_dict(result)
        d["report_sections_present"] = sorted(s.value for s in sections_present)
        return d

    # ===================================================================
    # Stage 2: LOCAL_ASSERTION_INTERPRETATION (R02, R03, R04, R05)
    # ===================================================================
    chronicity = str(machine.get("required_chronicity", ""))
    assertion_target_terms = tuple(
        str(term)
        for term in (
            list(machine.get("positive_terms", []))
            + list(machine.get("surface_forms", []))
            + [target_pathology]
        )
        if str(term).strip()
    )

    for eu in evidence_units:
        # R02: Scope parsing — get sentence and clause context
        sent_text, sent_start, sent_end = sentence_for_offset(text, eu.start)
        eu.sentence_text = sent_text
        eu.sentence_start = sent_start
        eu.sentence_end = sent_end

        clause_text, clause_start, clause_end = clause_for_offset(
            sent_text, sent_start, eu.start
        )
        eu.clause_text = clause_text
        eu.clause_start = clause_start
        eu.clause_end = clause_end

        # Target-local coordination ambiguity check (Task 3)
        target_in_sent_start = eu.start - sent_start
        target_in_sent_end = eu.end - sent_start
        if is_coordination_ambiguous(sent_text, target_in_sent_start, target_in_sent_end):
            eu.reason_codes.append(ReasonCode.MALFORMED_OR_COMPLEX_SCOPE)

        # Compute target position relative to clause
        target_in_clause = eu.start - clause_start
        target_end_in_clause = eu.end - clause_start

        # R05: Temporality (check first, as it affects interpretation)
        label_overrides = machine.get("label_policy_overrides", {})
        global_overrides = machine.get("global_policy_overrides", {})
        temp_class, temp_reasons = analyze_temporality(
            clause_text,
            eu.section,
            target_in_clause,
            target_end_in_clause,
            target_pathology=target_pathology,
            label_overrides=label_overrides,
            global_overrides=global_overrides,
        )
        eu.temporality = temp_class
        eu.reason_codes.extend(temp_reasons)

        # R03: Negation / target vs modifier polarity (Task 4)
        polarity, neg_reasons = analyze_negation(
            clause_text,
            target_in_clause,
            target_end_in_clause,
            eu.matched_term,
            chronicity_constraint=chronicity,
        )
        eu.assertion_polarity = polarity
        eu.reason_codes.extend(neg_reasons)

        # R04: Hedging / uncertainty (Task 5)
        if polarity != AssertionPolarity.NEGATED:
            certainty, hedge_reasons = analyze_hedging(
                clause_text,
                target_in_clause,
                target_end_in_clause,
                eu.matched_term,
                global_overrides=global_overrides,
                target_pathology=target_pathology,
                target_terms=assertion_target_terms,
            )
            eu.certainty = certainty
            eu.reason_codes.extend(hedge_reasons)

    # ===================================================================
    # Stage 3: TARGET_ALIGNMENT (R06, R07)
    # ===================================================================
    excluded_anatomy = machine.get("excluded_anatomy", [])
    required_anatomy = machine.get("required_anatomy", [])
    excluded_subtypes = machine.get("subtype_excluded_terms", machine.get("excluded_subtypes", []))
    excluded_terms = machine.get("excluded_terms", [])
    positive_terms = list(machine.get("positive_terms", []))
    positive_terms.extend(machine.get("surface_forms", []))
    for comp in machine.get("compositional_patterns", []):
        if "pattern_id" in comp:
            positive_terms.append(comp["pattern_id"])
    if target_pathology:
        positive_terms.append(target_pathology)
    insufficient_terms = machine.get("insufficient_evidence_terms", entry.get("insufficient_evidence", []))

    for eu in evidence_units:
        # R06: Anatomy alignment
        anat_status, anat_reasons = check_anatomy_alignment(
            eu.clause_text,
            excluded_anatomy,
            required_anatomy,
            sentence_context=eu.sentence_text,
            report_text=text,
            target_pathology=target_pathology,
        )
        eu.anatomy_status = anat_status
        eu.reason_codes.extend(anat_reasons)

        # R07: Subtype alignment (Task 7)
        sub_status, sub_reasons = check_subtype_alignment(
            eu.clause_text,
            excluded_subtypes,
            excluded_terms,
            sentence_context=eu.sentence_text,
            target_pathology=target_pathology,
            matched_term=eu.matched_term,
        )
        eu.subtype_status = sub_status
        eu.reason_codes.extend(sub_reasons)

        # R07: Lineage established check
        is_est, est_reasons = check_lineage_established(eu.matched_term, positive_terms)
        if not is_est:
            eu.subtype_status = AlignmentStatus.UNRESOLVED
            eu.reason_codes.extend(est_reasons)

        # R07: Broad category lineage check
        is_broad, broad_reasons = check_lineage_unestablished(eu.matched_term, eu.clause_text, insufficient_terms)
        if is_broad:
            eu.subtype_status = AlignmentStatus.UNRESOLVED
            eu.reason_codes.extend(broad_reasons)

        # Migration checkpoint 2A: internal scope annotation only.
        # This is explicitly feature-gated and does not alter legacy polarity,
        # reason codes, aggregation inputs, safety routing, or serialization.
        if scope_annotation_enabled:
            annotate_evidence_scope(eu, text, target_pathology)
            target_in_clause = eu.start - eu.clause_start
            target_end_in_clause = eu.end - eu.clause_start
            eu.negation_extent = classify_negation_extent(
                eu.clause_text,
                target_in_clause,
                target_end_in_clause,
                legacy_polarity=eu.assertion_polarity,
                target_domain=eu.scope.target_domain,
                has_explicit_locality=eu.scope.explicit_locality,
            )

    # R06: Laterality across evidence
    # Under explicit ANY_IN_SCOPE semantics, laterality is compared locally by
    # the scoped compatibility helper rather than as a report-global mismatch.
    if scope_annotation_enabled and scope_presence_semantics == "ANY_IN_SCOPE":
        aggregation_reasons: list[ReasonCode] = []
        aggregation_units = semantic_projection(evidence_units)
        scope_resolution = resolve_any_in_scope(evidence_units)
    else:
        lat_status, lat_reasons = check_laterality_across_evidence(evidence_units)
        aggregation_reasons = list(lat_reasons)
        aggregation_units = evidence_units
        scope_resolution = None

    # ===================================================================
    # Stage 4: EVIDENCE_AGGREGATION (R09, R10, R12)
    # ===================================================================
    # R09: Specific positive vs broad normal (Task 9)
    broad_reason, broad_routes = check_specific_vs_broad_normal(
        aggregation_units, text, target_pathology=target_pathology
    )
    if broad_reason:
        aggregation_reasons.append(broad_reason)

    # R10: Cross-section consistency (Task 8)
    section_reasons, section_routes = check_cross_section_consistency(
        aggregation_units,
        presence_semantics=(
            scope_presence_semantics
            if scope_annotation_enabled
            else None
        ),
    )
    aggregation_reasons.extend(section_reasons)

    # R12: Modality discordance
    mod_reason, mod_routes = check_modality_discordance(aggregation_units)
    if mod_reason:
        aggregation_reasons.append(mod_reason)

    # Multi-mention conflict detection
    conflict_reasons, conflict_routes = check_evidence_conflicts(
        aggregation_units,
        presence_semantics=(
            scope_presence_semantics
            if scope_annotation_enabled
            else None
        ),
    )
    aggregation_reasons.extend(conflict_reasons)

    if scope_resolution is not None and scope_resolution.routing_reason is not None:
        if scope_resolution.routing_reason not in aggregation_reasons:
            aggregation_reasons.append(scope_resolution.routing_reason)

    # ===================================================================
    # Stage 5: SAFETY_VALIDITY_GATE (R13)
    # ===================================================================
    gate_evidence_units = aggregation_units
    if scope_resolution is not None and not scope_resolution.requires_routing:
        # Preserve all mandatory safety triggers from the complete scoped view.
        # Only when none fire may the inherited final-state gate consume the
        # resolution-selected evidence subset.
        full_scope_triggers, _ = evaluate_routing_triggers(
            aggregation_units,
            aggregation_reasons,
        )
        if not full_scope_triggers and scope_resolution.decision_evidence_units:
            gate_evidence_units = list(scope_resolution.decision_evidence_units)

    (
        deterministic_state,
        routing_decision,
        reason_codes,
        stage_resolved,
        rule_family_id,
        fired_triggers,
    ) = apply_safety_gate(gate_evidence_units, aggregation_reasons)

    result = format_output(
        case_id=case_id,
        source_mode=source_mode,
        target_pathology=target_pathology,
        deterministic_state=deterministic_state,
        routing_decision=routing_decision,
        reason_codes=reason_codes,
        evidence_units=evidence_units,
        architecture_stage_resolved=stage_resolved,
        rule_family_id=rule_family_id,
        technical_status="SUCCESS",
        report_text=text,
        routing_trigger_ids=fired_triggers,
    )

    d = to_runner_dict(result)
    d["report_sections_present"] = sorted(s.value for s in sections_present)
    return d



