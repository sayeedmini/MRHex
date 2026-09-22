"""Feature-gated scoped aggregation primitives for D1 migration checkpoint 2D.

These helpers are production-located but behaviorally inert unless an explicit
scope_policy enables ANY_IN_SCOPE semantics. They reuse the checkpoint-2B pure
scope comparator and preserve legacy behavior when the flag is absent.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from typing import Iterable

from mrhex.engine.aggregation.scope_compatibility import (
    compare_scope_compatibility,
)
from mrhex.engine.types import (
    AssertionPolarity,
    CertaintyLevel,
    ConflictDisposition,
    EvidenceState,
    EvidenceUnit,
    NegationExtent,
    ReasonCode,
    Section,
    TargetDomain,
    TemporalityClass,
)


@dataclass(frozen=True)
class ScopedAggregationResolution:
    candidate_state: EvidenceState | None
    requires_routing: bool
    reason: str
    decision_evidence_units: tuple[EvidenceUnit, ...]
    comparisons: tuple[tuple[int, int, ConflictDisposition], ...] = ()
    routing_reason: ReasonCode | None = None


_SEMANTIC_NEGATIVE_EXTENTS = {
    NegationExtent.WHOLE_TARGET,
    NegationExtent.LOCAL_TARGET,
    NegationExtent.QUALIFIED_SUBSET,
    NegationExtent.OUT_OF_TARGET_ANATOMY,
    NegationExtent.UNKNOWN_SCOPE,
}


def is_current_scope_unit(unit: EvidenceUnit) -> bool:
    return (
        unit.temporality
        not in {
            TemporalityClass.RESOLVED,
            TemporalityClass.CLINICAL_INDICATION,
            TemporalityClass.HISTORICAL_ONLY,
        }
        and unit.section != Section.CLINICAL_HISTORY
    )


def semantic_role(unit: EvidenceUnit) -> str:
    """Interpret scoped semantic role without mutating the source EvidenceUnit."""
    if unit.negation_extent in _SEMANTIC_NEGATIVE_EXTENTS:
        return "NEGATIVE"
    if unit.negation_extent in {
        NegationExtent.MODIFIER_ONLY,
        NegationExtent.PRIOR_EXAM_ABSENCE,
    }:
        return "POSITIVE"
    if unit.assertion_polarity in {
        AssertionPolarity.AFFIRMED,
        AssertionPolarity.NEGATED_MODIFIER,
    }:
        return "POSITIVE"
    if unit.assertion_polarity == AssertionPolarity.NEGATED:
        return "NEGATIVE"
    return "OTHER"


def semantic_projection(
    evidence_units: Iterable[EvidenceUnit],
) -> list[EvidenceUnit]:
    """Create shallow copies with scoped semantic polarity for gated aggregation.

    External evidence serialization continues to use the untouched source units.
    """
    projected: list[EvidenceUnit] = []
    for unit in evidence_units:
        clone = copy(unit)
        role = semantic_role(unit)
        if role == "NEGATIVE":
            clone.assertion_polarity = AssertionPolarity.NEGATED
        elif role == "POSITIVE":
            clone.assertion_polarity = AssertionPolarity.AFFIRMED
        projected.append(clone)
    return projected


def resolve_any_in_scope(
    evidence_units: Iterable[EvidenceUnit],
) -> ScopedAggregationResolution:
    """Resolve report-level ANY_IN_SCOPE candidate semantics conservatively."""
    projected = semantic_projection(evidence_units)
    items = [unit for unit in projected if is_current_scope_unit(unit)]

    positives = [
        unit
        for unit in items
        if unit.assertion_polarity
        in {AssertionPolarity.AFFIRMED, AssertionPolarity.NEGATED_MODIFIER}
        and unit.certainty == CertaintyLevel.DEFINITE
        and unit.scope.target_domain != TargetDomain.OUT_OF_TARGET
    ]
    negatives = [
        unit for unit in items if unit.assertion_polarity == AssertionPolarity.NEGATED
    ]
    unresolved_current = [
        unit
        for unit in items
        if unit.certainty
        in {CertaintyLevel.HEDGED, CertaintyLevel.DIFFERENTIAL}
        and unit.scope.target_domain != TargetDomain.OUT_OF_TARGET
    ]

    comparisons: list[tuple[int, int, ConflictDisposition]] = []
    safe_positive_indices: set[int] = set()
    has_unknown_comparison = False

    for pi, positive in enumerate(positives):
        dispositions: list[ConflictDisposition] = []
        for ni, negative in enumerate(negatives):
            disposition = compare_scope_compatibility(
                positive,
                negative,
                presence_semantics="ANY_IN_SCOPE",
            )
            comparisons.append((pi, ni, disposition))
            dispositions.append(disposition)
            if disposition == ConflictDisposition.TRUE_CONFLICT:
                return ScopedAggregationResolution(
                    candidate_state=None,
                    requires_routing=True,
                    reason=ConflictDisposition.TRUE_CONFLICT.value,
                    decision_evidence_units=tuple(projected),
                    comparisons=tuple(comparisons),
                    routing_reason=ReasonCode.SPECIFIC_VS_GLOBAL_CONFLICT,
                )
            if disposition == ConflictDisposition.ROUTE_UNKNOWN:
                has_unknown_comparison = True

        if not dispositions or all(
            disposition
            in {
                ConflictDisposition.NON_CONFLICT,
                ConflictDisposition.NOT_COMPARABLE,
            }
            for disposition in dispositions
        ):
            safe_positive_indices.add(pi)

    if positives and safe_positive_indices:
        safe_positives = tuple(
            positive
            for index, positive in enumerate(positives)
            if index in safe_positive_indices
        )
        return ScopedAggregationResolution(
            candidate_state=EvidenceState.S,
            requires_routing=False,
            reason="DEFINITE_IN_SCOPE_POSITIVE_WITHOUT_OVERLAPPING_NEGATIVE",
            decision_evidence_units=safe_positives,
            comparisons=tuple(comparisons),
        )

    if positives and has_unknown_comparison:
        return ScopedAggregationResolution(
            candidate_state=None,
            requires_routing=True,
            reason=ConflictDisposition.ROUTE_UNKNOWN.value,
            decision_evidence_units=tuple(projected),
            comparisons=tuple(comparisons),
            routing_reason=ReasonCode.MALFORMED_OR_COMPLEX_SCOPE,
        )

    if unresolved_current:
        # Uncertain-only target evidence is a valid UC state, not by itself a
        # mixed-certainty failure. Complex/differential scope remains subject
        # to the inherited safety triggers before UC can be emitted.
        return ScopedAggregationResolution(
            candidate_state=EvidenceState.UC,
            requires_routing=False,
            reason="CURRENT_UNCERTAIN_IN_SCOPE_EVIDENCE",
            decision_evidence_units=tuple(unresolved_current),
            comparisons=tuple(comparisons),
        )

    whole_negatives = tuple(
        unit
        for unit in negatives
        if unit.negation_extent == NegationExtent.WHOLE_TARGET
        and unit.scope.target_domain == TargetDomain.IN_TARGET
    )
    if whole_negatives:
        return ScopedAggregationResolution(
            candidate_state=EvidenceState.C,
            requires_routing=False,
            reason="WHOLE_TARGET_CURRENT_NEGATION",
            decision_evidence_units=whole_negatives,
            comparisons=tuple(comparisons),
        )

    if negatives:
        return ScopedAggregationResolution(
            candidate_state=None,
            requires_routing=True,
            reason="NEGATIVE_SCOPE_INSUFFICIENT_FOR_GLOBAL_ABSENCE",
            decision_evidence_units=tuple(projected),
            comparisons=tuple(comparisons),
            routing_reason=ReasonCode.MALFORMED_OR_COMPLEX_SCOPE,
        )

    return ScopedAggregationResolution(
        candidate_state=None,
        requires_routing=True,
        reason="NO_USABLE_CURRENT_TARGET_EVIDENCE",
        decision_evidence_units=tuple(projected),
        comparisons=tuple(comparisons),
        routing_reason=ReasonCode.MALFORMED_OR_COMPLEX_SCOPE,
    )
