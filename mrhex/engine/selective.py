"""MRHex Core Rule Classifier.

Executes the MRHex core rule layer.
Applies audited, pathology-specific rules for:
1. Gliosis
2. Arachnoid cyst
"""
from __future__ import annotations

from typing import Any, Mapping
import re

from mrhex.engine.types import (
    ArchitectureStage,
    RoutingDecision,
    CertaintyLevel,
    TemporalityClass,
    ReasonCode,
    Section,
    EvidenceState,
    AssertionPolarity,
)
from mrhex.engine import classify_deterministic_v2
from mrhex.engine.assertion.hedging import UNCERTAINTY_CUES, COMPATIBLE_WITH_CUES, POST_TARGET_CUES
from mrhex.engine.assertion.temporality import (
    HISTORY_CUES, CHRONIC_CUES, OLD_CUES, RESIDUAL_CUES,
    CLINICAL_INDICATION_CUES, DELIMITER_RE
)

SYSTEM_ID = "mrhex_core"
VERSION = "1.0.0"


def _adjust_gliosis_assertion(eu, clause_text: str, target_in_clause: int, target_end_in_clause: int, text: str):
    """Audited core assertion adjustment for Gliosis."""
    prefix = clause_text[:target_in_clause]
    suffix = clause_text[target_end_in_clause:]
    matched = eu.matched_term.lower()

    # G1: "evaluated in favor of" / "in favor of" chronic ischemic-gliotic
    # When modifying chronic ischemic-gliotic / gliotic changes without a competing differential diagnosis or nonspecific phrasing,
    # this is an affirmed diagnostic finding, not a hedged differential.
    if eu.certainty == CertaintyLevel.HEDGED:
        in_favor = bool(re.search(r'\b(?:evaluated\s+primarily\s+in\s+favor\s+of|evaluated\s+in\s+favor\s+of|in\s+favor\s+of)\s*(?:an?\s+)?$', prefix, re.I))
        surrounding = text[max(0, eu.start - 300):min(len(text), eu.end + 300)]
        has_competing = bool(re.search(r'\b(?:versus|vs\.?|differential|demyelinat\w*|ms|vasculit\w*|infection\w*|tumor\w*|neoplasm\w*|metast\w*|atypical|nonspecific)\b', surrounding, re.I))
        has_or_alt = bool(re.search(r'\bor\b', suffix, re.I) and not re.search(r'\bor\s+(?:subcortical|periventricular|deep|white\s+matter|gliosis|gliotic)\b', suffix, re.I))
        
        is_ischemic_phrasing = bool(re.search(r'\b(?:chronic\s+)?ischemic\b', matched + " " + suffix[:30], re.I))

        if in_favor and is_ischemic_phrasing and not (has_competing or has_or_alt):
            eu.certainty = CertaintyLevel.DEFINITE
            eu.reason_codes = [r for r in eu.reason_codes if r != ReasonCode.ASSERT_HEDGED]
            if ReasonCode.ASSERT_DIRECT_CURRENT not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_DIRECT_CURRENT)

    # G2: Currently visualized stable/sequela gliosis on comparison study
    # When gliosis is described as stable, present, or a current sequela focus on comparison study,
    # it is CURRENT/CHRONIC_CURRENT, not HISTORICAL_ONLY.
    if eu.temporality == TemporalityClass.HISTORICAL_ONLY:
        is_currently_observed = bool(re.search(
            r'\b(?:stable|present|remained|appeared|observed|seen|detected|persists?|noted)\b',
            clause_text,
            re.I
        ))
        if is_currently_observed and eu.section != Section.CLINICAL_HISTORY:
            eu.temporality = TemporalityClass.CHRONIC_CURRENT
            eu.reason_codes = [r for r in eu.reason_codes if r != ReasonCode.HISTORICAL_ONLY]
            if ReasonCode.ASSERT_DIRECT_CURRENT not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_DIRECT_CURRENT)

    # G3: Coordination boundary fix (e.g. "Gliosis is present, and recurrence is absent")
    if eu.assertion_polarity != AssertionPolarity.AFFIRMED:
        if re.search(r'\b(?:present|observed|noted)\s*,\s*and\b', prefix + suffix, re.I) and re.search(r'\b(?:absent|not\s+seen|negative)\b', suffix, re.I):
            eu.assertion_polarity = AssertionPolarity.AFFIRMED
            eu.reason_codes = [r for r in eu.reason_codes if r not in (ReasonCode.ASSERT_TARGET_NEGATED, ReasonCode.NEGATED_MODIFIER_NOT_TARGET)]
            if ReasonCode.ASSERT_DIRECT_CURRENT not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_DIRECT_CURRENT)


def _adjust_arachnoid_assertion(eu, clause_text: str, target_in_clause: int, target_end_in_clause: int, text: str):
    """Audited core assertion adjustment for Arachnoid cyst."""
    prefix = clause_text[:target_in_clause]
    suffix = clause_text[target_end_in_clause:]

    # A1: "favoring arachnoid cyst" / "evaluated in favor of arachnoid cyst" without competing differential
    if eu.certainty == CertaintyLevel.HEDGED:
        in_favor = bool(re.search(r'\b(?:evaluated\s+in\s+favor\s+of|evaluated\s+primarily\s+in\s+favor\s+of|in\s+favor\s+of|favoring)\s*(?:an?\s+)?$', prefix, re.I))
        has_competing = bool(re.search(r'\b(?:versus|vs\.?|differential|or\s+epidermoid|epidermoid|neoplasm|tumor|mega\s+cisterna)\b', eu.sentence_text, re.I))
        has_question_mark_anywhere = bool(re.search(r'arachnoid\s+cyst[s]?\s*\?', text, re.I))
        if in_favor and not (has_competing or has_question_mark_anywhere):
            eu.certainty = CertaintyLevel.DEFINITE
            eu.reason_codes = [r for r in eu.reason_codes if r != ReasonCode.ASSERT_HEDGED]
            if ReasonCode.ASSERT_DIRECT_CURRENT not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_DIRECT_CURRENT)

    # A2: "suspicious [size/modifier] arachnoid cyst" should be HEDGED (UC)
    if eu.certainty == CertaintyLevel.DEFINITE:
        if re.search(r'\b(?:suspicious|suspected|questionable)\s+(?:(?:millimetric|subcentimetric|small|large)\s+)?$', prefix, re.I):
            eu.certainty = CertaintyLevel.HEDGED
            eu.reason_codes.append(ReasonCode.ASSERT_HEDGED)


def _adjust_meningioma_assertion(eu, clause_text: str, target_in_clause: int, target_end_in_clause: int, text: str):
    """Audited core assertion adjustment for Intracranial meningioma."""
    prefix = clause_text[:target_in_clause]
    suffix = clause_text[target_end_in_clause:]
    clause_and_sent = clause_text + " " + eu.sentence_text

    # IM-2: Excised / Post-surgical meningioma with no residual tumor
    is_excised = bool(re.search(r'\b(?:preoperative\s+examination\s*,\s*)?has\s+been\s+excised\b|\b(?:completely|totally)\s+(?:excised|resected|removed)\b', clause_and_sent, re.I))
    is_post_surgical_no_residual = bool(
        re.search(r'\b(?:post-?surgical|operated)\b', text, re.I) and
        re.search(r'\bresidual\s*(?:[-–—]|and|or)?\s*recurrent\s+mass\b[^\.\;\n]*\b(?:not\s+detected|absent|not\s+seen|no\b)', text, re.I)
    )
    has_active_residual_phrase = bool(re.search(r'\b(?:residual|recurrent)\s+(?:intracranial\s+)?meningioma\b|\bfocal\s+residual\b', text, re.I))

    if (is_excised or is_post_surgical_no_residual) and not has_active_residual_phrase:
        eu.temporality = TemporalityClass.HISTORICAL_ONLY
        eu.reason_codes = [r for r in eu.reason_codes if r != ReasonCode.ASSERT_DIRECT_CURRENT]
        if ReasonCode.HISTORICAL_ONLY not in eu.reason_codes:
            eu.reason_codes.append(ReasonCode.HISTORICAL_ONLY)
        return

    # IM-1: Affirmative diagnostic favoring of meningioma
    if eu.certainty == CertaintyLevel.HEDGED:
        in_favor = bool(re.search(
            r'\b(?:evaluated\s+(?:primarily\s+)?in\s+favor\s+of|in\s+favor\s+of|primarily\s+(?:compatible|consistent)\s+with|(?:compatible|consistent)\s+with\s+(?:\w+\s+)?meningioma\s+primarily)\b',
            prefix + " " + suffix[:40],
            re.I
        ) or re.search(r'\(evaluated\s+in\s+favor\s+of\s+meningioma\)', clause_and_sent, re.I))

        has_competing = bool(re.search(r'\b(?:versus|vs\.?|differential|schwannoma|metast\w*|chordoma|solitary\s+fibrous|hemangiopericytoma)\b', clause_and_sent, re.I))
        has_question_mark = bool(re.search(r'meningioma[s]?\s*\?', text, re.I))
        has_malignancy_context = bool(re.search(r'\b(?:breast\s+ca|cancer|carcinoma|primary\s+malignan\w*)\b', text, re.I))
        has_tentative = bool(re.search(r'\binitially\b', prefix + " " + suffix[:40], re.I))
        has_contrast_or_tail = bool(re.search(r'\b(?:contrast|enhanc\w*|dural\s+tail)\b', clause_and_sent, re.I) or re.search(r'\b(?:post-?contrast|contrast\s+agent)\b', text, re.I))
        is_explicit_non_contrast = bool(re.search(r'\bnon-?contrast\s+examination\b', clause_and_sent, re.I))

        if in_favor and has_contrast_or_tail and not (has_competing or has_question_mark or has_malignancy_context or has_tentative or is_explicit_non_contrast):
            eu.certainty = CertaintyLevel.DEFINITE
            eu.reason_codes = [r for r in eu.reason_codes if r != ReasonCode.ASSERT_HEDGED]
            if ReasonCode.ASSERT_DIRECT_CURRENT not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_DIRECT_CURRENT)


def _adjust_demyelinating_assertion(eu, clause_text: str, target_in_clause: int, target_end_in_clause: int, text: str):
    """Audited core assertion adjustment for Demyelinating disease of central nervous system."""
    prefix = clause_text[:target_in_clause]
    suffix = clause_text[target_end_in_clause:]
    clause_and_sent = clause_text + " " + eu.sentence_text
    surrounding = text[max(0, eu.start - 300):min(len(text), eu.end + 300)]

    # DM-2: Inactive / old / stable demyelinating plaques currently seen on brain/cord MRI are S (not H)
    if eu.temporality == TemporalityClass.HISTORICAL_ONLY and eu.section != Section.CLINICAL_HISTORY:
        is_visualized = bool(re.search(
            r'\b(?:old|chronic|inactive|stable)\b',
            prefix + " " + eu.matched_term,
            re.I
        ) or re.search(r'\b(?:observed|seen|detected|noted|present)\b', clause_and_sent, re.I))
        if is_visualized:
            eu.temporality = TemporalityClass.CHRONIC_CURRENT
            eu.reason_codes = [r for r in eu.reason_codes if r != ReasonCode.HISTORICAL_ONLY]
            if ReasonCode.ASSERT_DIRECT_CURRENT not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_DIRECT_CURRENT)

    # DM-1: Affirmative diagnostic favoring of demyelinating process / MS plaques
    if eu.certainty == CertaintyLevel.HEDGED:
        in_favor = bool(re.search(
            r'\b(?:evaluated\s+(?:primarily\s+)?in\s+favor\s+of|in\s+favor\s+of|primarily\s+(?:compatible|consistent)\s+with|(?:compatible|consistent)\s+with\s+(?:a\s+)?demyelinat\w*\s+(?:process|disease)\s+primarily)\b',
            prefix + " " + suffix[:40],
            re.I
        ) or re.search(r'\(evaluated\s+in\s+favor\s+of\s+(?:MS\s+)?demyelinat\w*\s+plaques', clause_and_sent, re.I)
          or re.search(r'evaluated\s+in\s+favor\s+of\s+a\s+demyelinating\s+process', clause_and_sent, re.I)
          or re.search(r'primarily\s+compatible\s+with\s+a\s+demyelinating\s+process', clause_and_sent, re.I))

        has_competing = bool(re.search(r'\b(?:versus|vs\.?|differential\s+(?:is|includes|with)?|ischemi\w*|infarct\w*|small[- ]vessel|glioma|tumor|neoplasm|metast\w*|infection|vasculit\w*)\b', surrounding, re.I))
        has_question_mark = bool(re.search(r'demyelinat\w*\s*\?|plaques?\s*\?|\(demyelinat\w*\?\)', clause_and_sent, re.I))

        if in_favor and not (has_competing or has_question_mark):
            eu.certainty = CertaintyLevel.DEFINITE
            eu.reason_codes = [r for r in eu.reason_codes if r != ReasonCode.ASSERT_HEDGED]
            if ReasonCode.ASSERT_DIRECT_CURRENT not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_DIRECT_CURRENT)

    # DM-3: Explicitly hedged "cannot exclude" / "exclusion of ... is recommended" / "suggestive" / "?" demyelinating
    if eu.certainty == CertaintyLevel.DEFINITE:
        is_hedged_cue = bool(
            re.search(r'\b(?:not\s+possible\s+to\s+exclude|cannot\s+exclude|could\s+represent|differential|suggestive)\b', prefix + " " + suffix[:30], re.I)
            or re.search(r'\b(?:exclu(?:de|sion)\s+of|to\s+exclude)\s+(?:\w+\s+)?(?:demyelinat\w*|ms)\b', clause_and_sent, re.I)
            or re.search(r'\(demyelinat\w*\?\)|demyelinat\w*\s*\?', clause_and_sent, re.I)
            or re.search(r'demyelinating\s+plaque\s+suggestive', clause_and_sent, re.I)
            or re.search(r'\bglial\s+tumor\s*\?', text, re.I)
        )
        if is_hedged_cue:
            eu.certainty = CertaintyLevel.HEDGED
            if ReasonCode.ASSERT_HEDGED not in eu.reason_codes:
                eu.reason_codes.append(ReasonCode.ASSERT_HEDGED)


def classify_core_rules(
    report: object,
    entry: Mapping[str, Any],
    *,
    case_id: str = "",
    source_mode: str = "full_report",
) -> dict[str, Any]:
    """Classify one case under MRHex core rules."""
    # First run base classification
    base_out = classify_deterministic_v2(
        report,
        entry,
        case_id=case_id,
        source_mode=source_mode,
    )
    
    target_pathology = str(entry.get("label", entry.get("canonical_name", "")))
    
    # Active core rule pathologies
    active_core_pathologies = (
        "Gliosis",
        "Arachnoid cyst",
        "Intracranial meningioma",
        "Demyelinating disease of central nervous system",
    )
    if target_pathology not in active_core_pathologies:
        base_out["system"] = SYSTEM_ID
        base_out["version"] = VERSION
        base_out["core_active_label"] = bool(entry.get("_d1_active", False))
        return base_out

    # Re-evaluate evidence units if target is an active core pathology
    text = "" if report is None else str(report)
    from mrhex.engine.retrieval.matcher import extract_evidence
    evidence_units = extract_evidence(text, entry, target_pathology, source_mode=source_mode)

    if not evidence_units:
        base_out["system"] = SYSTEM_ID
        base_out["version"] = VERSION
        base_out["core_active_label"] = True
        return base_out

    from mrhex.engine.segmentation.sentences import sentence_for_offset
    from mrhex.engine.segmentation.clauses import clause_for_offset, is_coordination_ambiguous
    from mrhex.engine.assertion.negation import analyze_negation
    from mrhex.engine.assertion.hedging import analyze_hedging
    from mrhex.engine.assertion.temporality import analyze_temporality
    from mrhex.engine.alignment.anatomy import check_anatomy_alignment, check_laterality_across_evidence
    from mrhex.engine.alignment.subtype import check_lineage_established, check_lineage_unestablished, check_subtype_alignment
    from mrhex.engine.aggregation.conflict import check_cross_section_consistency, check_evidence_conflicts, check_modality_discordance, check_specific_vs_broad_normal
    from mrhex.engine.safety_gate.gate import apply_safety_gate
    from mrhex.engine.safety_gate.output import format_output, to_runner_dict

    machine = entry.get("machine_rules", {})
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

        target_in_sent_start = eu.start - sent_start
        target_in_sent_end = eu.end - sent_start
        if is_coordination_ambiguous(sent_text, target_in_sent_start, target_in_sent_end):
            eu.reason_codes.append(ReasonCode.MALFORMED_OR_COMPLEX_SCOPE)

        target_in_clause = eu.start - clause_start
        target_end_in_clause = eu.end - clause_start

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

        polarity, neg_reasons = analyze_negation(
            clause_text,
            target_in_clause,
            target_end_in_clause,
            eu.matched_term,
            chronicity_constraint=chronicity,
        )
        eu.assertion_polarity = polarity
        eu.reason_codes.extend(neg_reasons)

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

        # APPLY CORE ADJUSTMENTS
        if target_pathology == "Gliosis":
            _adjust_gliosis_assertion(eu, clause_text, target_in_clause, target_end_in_clause, text)
        elif target_pathology == "Arachnoid cyst":
            _adjust_arachnoid_assertion(eu, clause_text, target_in_clause, target_end_in_clause, text)
        elif target_pathology == "Intracranial meningioma":
            _adjust_meningioma_assertion(eu, clause_text, target_in_clause, target_end_in_clause, text)
        elif target_pathology == "Demyelinating disease of central nervous system":
            _adjust_demyelinating_assertion(eu, clause_text, target_in_clause, target_end_in_clause, text)

    # Alignment and aggregation
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

        is_est, est_reasons = check_lineage_established(eu.matched_term, positive_terms)
        if not is_est:
            eu.subtype_status = ReasonCode.SUBTYPE_OUT_OF_SCOPE
            eu.reason_codes.extend(est_reasons)

        is_broad, broad_reasons = check_lineage_unestablished(eu.matched_term, eu.clause_text, insufficient_terms)
        if is_broad:
            eu.subtype_status = ReasonCode.SUBTYPE_OUT_OF_SCOPE
            eu.reason_codes.extend(broad_reasons)

    lat_status, lat_reasons = check_laterality_across_evidence(evidence_units)
    aggregation_reasons = list(lat_reasons)

    broad_reason, broad_routes = check_specific_vs_broad_normal(
        evidence_units, text, target_pathology=target_pathology
    )
    if broad_reason:
        aggregation_reasons.append(broad_reason)

    section_reasons, section_routes = check_cross_section_consistency(evidence_units)
    aggregation_reasons.extend(section_reasons)

    mod_reason, mod_routes = check_modality_discordance(evidence_units)
    if mod_reason:
        aggregation_reasons.append(mod_reason)

    conflict_reasons, conflict_routes = check_evidence_conflicts(evidence_units)
    aggregation_reasons.extend(conflict_reasons)

    (
        deterministic_state,
        routing_decision,
        reason_codes,
        stage_resolved,
        rule_family_id,
        fired_triggers,
    ) = apply_safety_gate(evidence_units, aggregation_reasons)

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

    out = to_runner_dict(result)
    out["system"] = SYSTEM_ID
    out["version"] = VERSION
    out["core_active_label"] = True
    return out

