"""Pure scope-compatibility comparison for D1 migration checkpoint 2B.

This module is intentionally not imported by production aggregation in
checkpoint 2B. It defines the comparison semantics first, so they can be
tested independently before receiving decision authority.
"""
from __future__ import annotations

from mrhex.engine.types import (
    AssertionPolarity,
    ConflictDisposition,
    EvidenceUnit,
    NegationExtent,
    ScopeLaterality,
    TargetDomain,
)


_ALLOWED_PRESENCE_SEMANTICS = {"ANY_IN_SCOPE"}


def _laterality_disjoint(
    positive: ScopeLaterality,
    negative: ScopeLaterality,
) -> bool:
    """Return True only when laterality is explicitly non-overlapping."""
    if ScopeLaterality.UNSPECIFIED in {positive, negative}:
        return False
    if ScopeLaterality.BILATERAL in {positive, negative}:
        return False
    return positive != negative


def compare_scope_compatibility(
    positive: EvidenceUnit,
    negative: EvidenceUnit,
    *,
    presence_semantics: str,
) -> ConflictDisposition:
    """Compare one positive and one negative evidence scope conservatively.

    This function answers only whether the two evidence units can be treated as
    a material scope conflict under the requested presence semantics. It does
    not aggregate a report and does not assign a final MR-RATE state.

    Unknown material overlap returns ROUTE_UNKNOWN rather than being guessed.
    """
    if presence_semantics not in _ALLOWED_PRESENCE_SEMANTICS:
        raise ValueError(
            f"Unsupported presence semantics: {presence_semantics!r}"
        )

    if positive.target_pathology != negative.target_pathology:
        return ConflictDisposition.NOT_COMPARABLE

    if positive.assertion_polarity not in {
        AssertionPolarity.AFFIRMED,
        AssertionPolarity.NEGATED_MODIFIER,
    }:
        return ConflictDisposition.NOT_COMPARABLE

    if negative.assertion_polarity != AssertionPolarity.NEGATED:
        return ConflictDisposition.NOT_COMPARABLE

    if negative.negation_extent in {
        NegationExtent.QUALIFIED_SUBSET,
        NegationExtent.MODIFIER_ONLY,
        NegationExtent.PRIOR_EXAM_ABSENCE,
        NegationExtent.OUT_OF_TARGET_ANATOMY,
    }:
        return ConflictDisposition.NON_CONFLICT

    if negative.scope.target_domain == TargetDomain.OUT_OF_TARGET:
        return ConflictDisposition.NON_CONFLICT

    if negative.negation_extent == NegationExtent.UNKNOWN_SCOPE:
        return ConflictDisposition.ROUTE_UNKNOWN

    if negative.negation_extent == NegationExtent.WHOLE_TARGET:
        if positive.scope.target_domain == TargetDomain.OUT_OF_TARGET:
            return ConflictDisposition.NON_CONFLICT
        if positive.scope.target_domain == TargetDomain.UNKNOWN:
            return ConflictDisposition.ROUTE_UNKNOWN
        return ConflictDisposition.TRUE_CONFLICT

    if negative.negation_extent != NegationExtent.LOCAL_TARGET:
        return ConflictDisposition.NOT_COMPARABLE

    # A local negative with unknown target-domain identity cannot safely be
    # treated as either overlapping or disjoint.
    if negative.scope.target_domain == TargetDomain.UNKNOWN:
        return ConflictDisposition.ROUTE_UNKNOWN

    if positive.scope.target_domain == TargetDomain.OUT_OF_TARGET:
        return ConflictDisposition.NON_CONFLICT
    if positive.scope.target_domain == TargetDomain.UNKNOWN:
        return ConflictDisposition.ROUTE_UNKNOWN

    # Named spinal level is the strongest local identity when both are known.
    p_levels = positive.scope.spinal_levels
    n_levels = negative.scope.spinal_levels
    if p_levels and n_levels:
        if p_levels.isdisjoint(n_levels):
            return ConflictDisposition.NON_CONFLICT
        if _laterality_disjoint(
            positive.scope.laterality,
            negative.scope.laterality,
        ):
            return ConflictDisposition.NON_CONFLICT
        return ConflictDisposition.TRUE_CONFLICT

    # Spinal region can establish non-overlap. If only one side has a named
    # level within the same region, exact overlap remains unresolved.
    p_regions = positive.scope.spinal_regions
    n_regions = negative.scope.spinal_regions
    if p_regions and n_regions:
        if p_regions.isdisjoint(n_regions):
            return ConflictDisposition.NON_CONFLICT
        if bool(p_levels) != bool(n_levels):
            return ConflictDisposition.ROUTE_UNKNOWN
        if _laterality_disjoint(
            positive.scope.laterality,
            negative.scope.laterality,
        ):
            return ConflictDisposition.NON_CONFLICT
        return ConflictDisposition.TRUE_CONFLICT

    # Non-spinal anatomical subregion identity is next strongest.
    p_sub = positive.scope.anatomic_subregions
    n_sub = negative.scope.anatomic_subregions
    if p_sub and n_sub:
        if p_sub.isdisjoint(n_sub):
            return ConflictDisposition.NON_CONFLICT
        if _laterality_disjoint(
            positive.scope.laterality,
            negative.scope.laterality,
        ):
            return ConflictDisposition.NON_CONFLICT
        return ConflictDisposition.TRUE_CONFLICT

    # Explicit opposite laterality alone is sufficient to prove disjointness.
    if _laterality_disjoint(
        positive.scope.laterality,
        negative.scope.laterality,
    ):
        return ConflictDisposition.NON_CONFLICT

    # Local scope exists but cannot be identified strongly enough to determine
    # overlap. Route rather than assuming conflict or non-conflict.
    return ConflictDisposition.ROUTE_UNKNOWN
