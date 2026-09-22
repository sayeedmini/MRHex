"""R09 / R10 / R12 — Evidence Aggregation.

R09: Specific-Positive vs Broad-Normal Aggregation
R10: Cross-Section Consistency Aggregation
R12: Modality / Sequence Provenance and Discordance

Policy:
  - No broad-normality => C shortcut (PROHIBIT_BROAD_NORMAL_TO_C).
  - No impression-over-findings precedence (PROHIBIT_IMPRESSION_PRECEDENCE).
  - No findings-over-impression precedence (PROHIBIT_FINDINGS_PRECEDENCE).
  - Material discrepancies in certainty, laterality, location, subtype → ROUTE_TO_LLM.
  - Normal multi-sequence coexistence is NOT discordance.
  - Only explicit report-stated materially incompatible interpretations → MODALITY_DISCORDANCE.
"""
from __future__ import annotations

import re
from typing import Optional

from mrhex.engine.types import (
    AlignmentStatus,
    AssertionPolarity,
    CertaintyLevel,
    ConflictDisposition,
    EvidenceState,
    EvidenceUnit,
    ReasonCode,
    RoutingDecision,
    Section,
    TemporalityClass,
)
from mrhex.engine.aggregation.scope_compatibility import (
    compare_scope_compatibility,
)
from mrhex.engine.aggregation.scoped import resolve_any_in_scope


# ---------------------------------------------------------------------------
# R09 — Specific Positive vs Broad Normal
# ---------------------------------------------------------------------------

# Global whole-study / whole-brain broad normality patterns.
# Strictly excludes local organ statements (e.g. 'Normal ventricles' or 'Pons is normal').
BROAD_NORMAL_GLOBAL_PATTERNS = [
    re.compile(r"\b(?:normal|unremarkable)\s+(?:brain|cranial|head|cerebral|spine|study|examination|mri|mra|ct|scan)\b", re.I),
    re.compile(r"\b(?:entirely\s+normal|completely\s+normal)\s+(?:brain|spine|study|examination|mri|scan)\b", re.I),
    re.compile(r"\b(?:no\s+acute\s+intracranial\s+(?:abnormality|pathology|process))\b", re.I),
    re.compile(r"\b(?:no\s+focal\s+intracranial\s+abnormality)\b", re.I),
    re.compile(r"\b(?:no\s+evidence\s+of\s+acute\s+intracranial\s+(?:pathology|abnormality|process))\b", re.I),
    re.compile(r"\b(?:negative\s+(?:study|examination|mri|scan))\b", re.I),
    re.compile(r"(?im)^\s*(?:impression|conclusion)\s*:\s*(?:no\s+acute\s+intracranial\s+(?:abnormality|pathology)|normal\s+mri|unremarkable\s+mri|within\s+normal\s+limits|normal\s+study|unremarkable\s+study|normal\s+spine(?:\s+mri)?|unremarkable\s+spine(?:\s+mri)?)\.?\s*"),
]


def has_broad_normal_statement(text: str) -> bool:
    """Check if text contains a genuine global broad normality statement.
    
    Policy R09: Local organ normality (e.g. 'normal ventricles') is NOT broad normality.
    """
    return any(p.search(text) for p in BROAD_NORMAL_GLOBAL_PATTERNS)


def check_specific_vs_broad_normal(
    evidence_units: list[EvidenceUnit],
    report_text: str,
    target_pathology: str = "",
) -> tuple[Optional[ReasonCode], bool]:
    """R09: Check for specific-positive vs broad-normal tension.

    Returns:
        (reason_code or None, requires_routing)
    """
    specific_positives = [
        eu for eu in evidence_units
        if eu.assertion_polarity in (AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER)
        and eu.certainty in (CertaintyLevel.DEFINITE, CertaintyLevel.HEDGED)
        and eu.temporality not in (TemporalityClass.RESOLVED, TemporalityClass.CLINICAL_INDICATION)
    ]

    if not specific_positives:
        return None, False

    target = target_pathology or (evidence_units[0].target_pathology if evidence_units else "")
    if target == "Spinal cord compression":
        # Target-anatomy aware: Intracranial/brain normality statements do NOT conflict
        # with spinal cord compression. Only genuine whole-study or spinal normal statements conflict.
        whole_study_or_spinal_patterns = [
            re.compile(r"\b(?:normal|unremarkable)\s+(?:study|examination|scan|spine)\b", re.I),
            re.compile(r"\b(?:entirely\s+normal|completely\s+normal)\s+(?:study|examination|scan|spine)\b", re.I),
            re.compile(r"\b(?:negative\s+(?:study|examination|mri|scan))\b", re.I),
            re.compile(r"\b(?:normal|unremarkable)\s+spine(?:\s+mri)?\b", re.I),
            re.compile(r"(?im)^\s*(?:impression|conclusion)\s*:\s*(?:within\s+normal\s+limits|normal\s+study|unremarkable\s+study|normal\s+spine(?:\s+mri)?|unremarkable\s+spine(?:\s+mri)?)\.?\s*"),
        ]
        if any(p.search(report_text) for p in whole_study_or_spinal_patterns):
            return ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT, True
        return None, False

    # Check if report contains a global broad normal statement
    if not has_broad_normal_statement(report_text):
        return None, False

    return ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT, True


# ---------------------------------------------------------------------------
# R10 — Cross-Section Consistency
# ---------------------------------------------------------------------------

_ANATOMIC_REGIONS = [
    ("frontal", re.compile(r"\bfrontal\b", re.I)),
    ("temporal", re.compile(r"\btemporal\b", re.I)),
    ("parietal", re.compile(r"\bparietal\b", re.I)),
    ("occipital", re.compile(r"\boccipital\b", re.I)),
    ("posterior_fossa", re.compile(r"\b(?:cerebell(?:ar|um)|posterior\s+fossa|brainstem|pons|medulla)\b", re.I)),
    ("sellar", re.compile(r"\b(?:sella|sellar|suprasellar|pituitary)\b", re.I)),
    ("intraventricular", re.compile(r"\b(?:ventricle|ventricular|intraventricular)\b", re.I)),
]


def _extract_region(text: str) -> set[str]:
    """Extract named neuroanatomical compartments from context text."""
    regions = set()
    for name, pattern in _ANATOMIC_REGIONS:
        if pattern.search(text):
            regions.add(name)
    return regions


def check_cross_section_consistency(
    evidence_units: list[EvidenceUnit],
    *,
    presence_semantics: str | None = None,
) -> tuple[list[ReasonCode], bool]:
    """R10: Check for material discrepancies across report sections.

    Checks for:
    - Certainty shift (hedged in one section, definite in another)
    - Location mismatch across sections (anatomic region or laterality)
    - Presence/absence disagreement across sections

    Returns:
        (list of reason codes, requires_routing)
    """
    reasons: list[ReasonCode] = []

    # Group evidence by section
    by_section: dict[Section, list[EvidenceUnit]] = {}
    for eu in evidence_units:
        by_section.setdefault(eu.section, []).append(eu)

    findings_units = by_section.get(Section.FINDINGS, [])
    impression_units = by_section.get(Section.IMPRESSION, [])

    if not findings_units or not impression_units:
        return reasons, False

    # 1. Check certainty shift
    findings_certainties = {eu.certainty for eu in findings_units}
    impression_certainties = {eu.certainty for eu in impression_units}

    if (CertaintyLevel.DEFINITE in findings_certainties and
            CertaintyLevel.HEDGED in impression_certainties) or \
       (CertaintyLevel.HEDGED in findings_certainties and
            CertaintyLevel.DEFINITE in impression_certainties):
        reasons.append(ReasonCode.SECTION_CERTAINTY_SHIFT)

    # 2. Check polarity disagreement (affirmed vs negated across sections)
    if presence_semantics == "ANY_IN_SCOPE":
        resolution = resolve_any_in_scope(evidence_units)
        cross_pairs = []
        for positive_section, negative_section in (
            (findings_units, impression_units),
            (impression_units, findings_units),
        ):
            positives = [
                eu
                for eu in positive_section
                if eu.assertion_polarity
                in {AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER}
                and eu.certainty == CertaintyLevel.DEFINITE
            ]
            negatives = [
                eu
                for eu in negative_section
                if eu.assertion_polarity == AssertionPolarity.NEGATED
            ]
            for positive in positives:
                for negative in negatives:
                    cross_pairs.append(
                        compare_scope_compatibility(
                            positive,
                            negative,
                            presence_semantics=presence_semantics,
                        )
                    )

        # Pairwise uncertainty from redundant evidence must not override an
        # independently safe ANY_IN_SCOPE positive. Only a report-level routed
        # resolution may contribute a scoped cross-section routing reason.
        if resolution.requires_routing:
            if ConflictDisposition.TRUE_CONFLICT in cross_pairs:
                if ReasonCode.SECTION_CERTAINTY_SHIFT not in reasons:
                    reasons.append(ReasonCode.SECTION_CERTAINTY_SHIFT)
            elif ConflictDisposition.ROUTE_UNKNOWN in cross_pairs:
                if ReasonCode.MALFORMED_OR_COMPLEX_SCOPE not in reasons:
                    reasons.append(ReasonCode.MALFORMED_OR_COMPLEX_SCOPE)
    else:
        findings_polarities = {eu.assertion_polarity for eu in findings_units}
        impression_polarities = {eu.assertion_polarity for eu in impression_units}

        affirmed_polarities = {AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER}
        negated_polarities = {AssertionPolarity.NEGATED}

        findings_has_affirmed = bool(findings_polarities & affirmed_polarities)
        findings_has_negated = bool(findings_polarities & negated_polarities)
        impression_has_affirmed = bool(impression_polarities & affirmed_polarities)
        impression_has_negated = bool(impression_polarities & negated_polarities)

        # Clinician Round 3 & Brain Metastasis Policy:
        # If report has affirmed brain metastasis (Route A or Route B),
        # absence of separate focal parenchymal metastases or exclusionary scoping phrases
        # ("no other parenchymal metastases", "no additional metastases", "apart from")
        # does NOT negate or conflict with the documented metastasis across sections.
        has_affirmed_metastasis = any(
            eu.target_pathology and "metastat" in eu.target_pathology.lower() and "brain" in eu.target_pathology.lower()
            and eu.assertion_polarity in affirmed_polarities
            and eu.certainty == CertaintyLevel.DEFINITE
            for eu in evidence_units
        )
        if has_affirmed_metastasis:
            exclusionary_neg_pattern = re.compile(
                r'\b(?:no\s+other|no\s+additional|no\s+further|focal|apart\s+from|except\s+for|except|with\s+the\s+exception\s+of|other\s+than)\b',
                re.I,
            )
            findings_has_negated = any(
                eu.assertion_polarity == AssertionPolarity.NEGATED
                and not exclusionary_neg_pattern.search(eu.clause_text or eu.text)
                for eu in findings_units
            )
            impression_has_negated = any(
                eu.assertion_polarity == AssertionPolarity.NEGATED
                and not exclusionary_neg_pattern.search(eu.clause_text or eu.text)
                for eu in impression_units
            )

        if (findings_has_affirmed and impression_has_negated) or \
           (findings_has_negated and impression_has_affirmed):
            if ReasonCode.SECTION_CERTAINTY_SHIFT not in reasons:
                reasons.append(ReasonCode.SECTION_CERTAINTY_SHIFT)

    # 3/4. Legacy location/laterality mismatch checks.
    # Under explicit ANY_IN_SCOPE semantics, disjoint local locations are not
    # inherently contradictory; polarity-bearing scope overlap above is the
    # material comparison.
    if presence_semantics != "ANY_IN_SCOPE":
        findings_regions = set()
        for eu in findings_units:
            findings_regions |= _extract_region(f"{eu.clause_text} {eu.sentence_text}")

        impression_regions = set()
        for eu in impression_units:
            impression_regions |= _extract_region(f"{eu.clause_text} {eu.sentence_text}")

        if findings_regions and impression_regions and findings_regions.isdisjoint(impression_regions):
            reasons.append(ReasonCode.SECTION_LOCATION_MISMATCH)

        from mrhex.engine.alignment.anatomy import detect_laterality
        findings_lats = {detect_laterality(eu.clause_text) for eu in findings_units} - {None}
        impression_lats = {detect_laterality(eu.clause_text) for eu in impression_units} - {None}

        if findings_lats and impression_lats and findings_lats.isdisjoint(impression_lats):
            if "bilateral" not in findings_lats and "bilateral" not in impression_lats:
                if ReasonCode.SECTION_LOCATION_MISMATCH not in reasons:
                    reasons.append(ReasonCode.SECTION_LOCATION_MISMATCH)
                if ReasonCode.LATERALITY_CONFLICT not in reasons:
                    reasons.append(ReasonCode.LATERALITY_CONFLICT)

    requires_routing = bool(reasons)
    return reasons, requires_routing


# ---------------------------------------------------------------------------
# R12 — Modality / Sequence Discordance
# ---------------------------------------------------------------------------

# Patterns indicating explicit sequence/modality-level interpretation in report text
SEQUENCE_PATTERNS = re.compile(
    r"\b(DWI|diffusion|FLAIR|T1|T2|T2\*|SWI|GRE|ADC|post-contrast|pre-contrast|"
    r"CT|MRI|MRA|CTA|ultrasound|angiography)\b",
    re.IGNORECASE,
)


def check_modality_discordance(
    evidence_units: list[EvidenceUnit],
) -> tuple[Optional[ReasonCode], bool]:
    """R12: Check for materially incompatible target-relevant interpretations
    explicitly stated across sequences or modalities.

    Normal multi-sequence coexistence (e.g., DWI acute + T2 chronic features)
    is NOT discordance.

    Only triggers when the report TEXT itself contains materially incompatible
    target-relevant interpretations.

    Returns:
        (reason_code or None, requires_routing)
    """
    if len(evidence_units) < 2:
        return None, False

    # Group evidence by sequence/modality mentioned in their context
    sequenced_units: dict[str, list[EvidenceUnit]] = {}
    for eu in evidence_units:
        context = eu.clause_text or eu.sentence_text or eu.text
        sequences_found = SEQUENCE_PATTERNS.findall(context)
        for seq in sequences_found:
            sequenced_units.setdefault(seq.upper(), []).append(eu)

    if len(sequenced_units) < 2:
        return None, False

    # Check for materially incompatible interpretations across sequences
    sequence_polarities: dict[str, set[AssertionPolarity]] = {}
    for seq, units in sequenced_units.items():
        sequence_polarities[seq] = {eu.assertion_polarity for eu in units}

    # If one sequence says AFFIRMED and another says NEGATED for the same target,
    # that's a material discordance
    all_seqs = list(sequence_polarities.keys())
    for i in range(len(all_seqs)):
        for j in range(i + 1, len(all_seqs)):
            pols_i = sequence_polarities[all_seqs[i]]
            pols_j = sequence_polarities[all_seqs[j]]
            affirmed_i = pols_i & {AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER}
            negated_i = pols_i & {AssertionPolarity.NEGATED}
            affirmed_j = pols_j & {AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER}
            negated_j = pols_j & {AssertionPolarity.NEGATED}

            if (affirmed_i and negated_j) or (negated_i and affirmed_j):
                return ReasonCode.MODALITY_DISCORDANCE, True

    return None, False


# ---------------------------------------------------------------------------
# Multi-mention conflict detection (fixes v1 bug: missing UC in conflict check)
# ---------------------------------------------------------------------------

def check_evidence_conflicts(
    evidence_units: list[EvidenceUnit],
    *,
    presence_semantics: str | None = None,
) -> tuple[list[ReasonCode], bool]:
    """Detect material conflicts across multiple evidence mentions.

    Fixes the v1 bug where S vs UC was not detected as a conflict.

    Returns:
        (list of reason codes, requires_routing)
    """
    reasons: list[ReasonCode] = []

    if len(evidence_units) < 2:
        return reasons, False

    if presence_semantics == "ANY_IN_SCOPE":
        positives = [
            eu
            for eu in evidence_units
            if eu.assertion_polarity
            in {AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER}
            and eu.certainty == CertaintyLevel.DEFINITE
            and eu.temporality
            not in {
                TemporalityClass.RESOLVED,
                TemporalityClass.CLINICAL_INDICATION,
                TemporalityClass.HISTORICAL_ONLY,
            }
            and eu.section != Section.CLINICAL_HISTORY
        ]
        negatives = [
            eu
            for eu in evidence_units
            if eu.assertion_polarity == AssertionPolarity.NEGATED
            and eu.section != Section.CLINICAL_HISTORY
        ]

        dispositions = [
            compare_scope_compatibility(
                positive,
                negative,
                presence_semantics=presence_semantics,
            )
            for positive in positives
            for negative in negatives
        ]
        resolution = resolve_any_in_scope(evidence_units)
        if resolution.requires_routing:
            if ConflictDisposition.TRUE_CONFLICT in dispositions:
                reasons.append(ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT)
            elif ConflictDisposition.ROUTE_UNKNOWN in dispositions:
                reasons.append(ReasonCode.MALFORMED_OR_COMPLEX_SCOPE)
    else:
        # Collect per-unit candidate states
        has_affirmed = any(
            eu.assertion_polarity in (AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER)
            and eu.certainty == CertaintyLevel.DEFINITE
            and eu.temporality not in (TemporalityClass.RESOLVED, TemporalityClass.CLINICAL_INDICATION, TemporalityClass.HISTORICAL_ONLY)
            and eu.section != Section.CLINICAL_HISTORY
            for eu in evidence_units
        )
        has_negated = any(
            eu.assertion_polarity == AssertionPolarity.NEGATED
            and eu.section != Section.CLINICAL_HISTORY
            for eu in evidence_units
        )

        # Clinician Round 3 & Brain Metastasis Policy:
        # If report has affirmed brain metastasis (Route A or Route B),
        # explicit exclusionary scoping ("no other parenchymal metastases", "no additional metastases", "apart from", "except", "focal")
        # does NOT conflict with S.
        has_affirmed_metastasis = any(
            eu.target_pathology and "metastat" in eu.target_pathology.lower() and "brain" in eu.target_pathology.lower()
            and eu.assertion_polarity in (AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER)
            and eu.certainty == CertaintyLevel.DEFINITE
            for eu in evidence_units
        )
        if has_affirmed_metastasis:
            exclusionary_neg_pattern = re.compile(
                r'\b(?:no\s+other|no\s+additional|no\s+further|focal|apart\s+from|except\s+for|except|with\s+the\s+exception\s+of|other\s+than)\b',
                re.I,
            )
            has_negated = any(
                eu.assertion_polarity == AssertionPolarity.NEGATED
                and eu.section != Section.CLINICAL_HISTORY
                and not exclusionary_neg_pattern.search(eu.clause_text or eu.text)
                for eu in evidence_units
            )
        has_hedged = any(
            eu.certainty in (CertaintyLevel.HEDGED, CertaintyLevel.DIFFERENTIAL)
            and eu.temporality != TemporalityClass.CLINICAL_INDICATION
            and eu.section != Section.CLINICAL_HISTORY
            for eu in evidence_units
        )

        if has_affirmed and has_negated:
            reasons.append(ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT)

        if has_affirmed and has_hedged:
            reasons.append(ReasonCode.LESION_SPECIFIC_CERTAINTY)

    requires_routing = bool(reasons)
    return reasons, requires_routing
