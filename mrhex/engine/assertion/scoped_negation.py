"""Gated scoped-negation helpers for D1 migration checkpoint 1.

These helpers are deliberately not wired into the production classifier yet.
They provide typed, testable parsing primitives for a later scope-enabled
checkpoint while preserving the current legacy assertion path.
"""
from __future__ import annotations

import re

from mrhex.engine.types import (
    AssertionPolarity,
    NegationExtent,
    TargetDomain,
)


_ABSENCE_VERBS = (
    r"observed|seen|detected|identified|noted|found|demonstrated|"
    r"visuali[sz]ed|present|evident|appreciated"
)
_POST_TARGET_ABSENCE = re.compile(
    rf"\b(?:was|were|is|are|has\s+been|have\s+been)\s+not\s+(?:{_ABSENCE_VERBS})\b",
    re.I,
)
_MODAL_POST_TARGET_ABSENCE = re.compile(
    rf"\b(?:could\s+not|cannot|can\s+not)\s+be\s+(?:{_ABSENCE_VERBS})\b",
    re.I,
)
_PLAIN_POST_TARGET_ABSENCE = re.compile(
    rf"\bnot\s+(?:{_ABSENCE_VERBS})\b",
    re.I,
)
_PRIOR_EXAM = re.compile(
    r"\b(?:previous|prior|earlier)\s+(?:examinations?|exams?|stud(?:y|ies)|scans?|mris?|cts?)\b",
    re.I,
)
_QUALIFIED_TARGET = re.compile(
    r"\b(?:new|newly\s+developed|new\s+developing|additional|further|other|significant)\b",
    re.I,
)
_MODIFIER_SUBJECT = re.compile(
    r"\b(?:contrast\s+enhancement|enhancement|mass\s+effect|edema|"
    r"diffusion\s+restriction|compression)\b.{0,100}\b(?:of|around|adjacent\s+to)\b",
    re.I,
)
_POST_TARGET_MODIFIER_NOUN = re.compile(
    r"\b(?:contrast\s+enhancement|enhancement|mass\s+effect|"
    r"diffusion\s+restriction|compression)\b[^.;:]{0,80}$",
    re.I,
)


def classify_post_target_negation_extent(
    clause: str,
    target_start: int,
    target_end: int,
    *,
    has_explicit_locality: bool = False,
) -> NegationExtent:
    """Classify an audited post-target absence construction conservatively.

    This function does not determine final polarity and does not mutate evidence.
    It is intended for a later explicitly gated integration checkpoint.

    Returns NONE when the audited post-target absence family is not present.
    """
    text = str(clause or "")
    if target_start < 0 or target_end < target_start or target_end > len(text):
        return NegationExtent.UNKNOWN_SCOPE

    after_target = text[target_end:]
    absence_matches = [
        match
        for match in (
            _POST_TARGET_ABSENCE.search(after_target),
            _MODAL_POST_TARGET_ABSENCE.search(after_target),
            _PLAIN_POST_TARGET_ABSENCE.search(after_target),
        )
        if match is not None
    ]
    if not absence_matches:
        return NegationExtent.NONE

    first_absence = min(absence_matches, key=lambda match: match.start())

    # A later modifier/property can become the grammatical subject of the
    # negative predicate. Example:
    #   "disc protrusion, ... compression was not observed"
    # The absence applies to compression, not to the earlier disc protrusion.
    between_target_and_absence = after_target[: first_absence.start()]
    if _POST_TARGET_MODIFIER_NOUN.search(between_target_and_absence):
        return NegationExtent.MODIFIER_ONLY

    local_window = text[max(0, target_start - 140): min(len(text), target_end + 180)]

    if _PRIOR_EXAM.search(local_window):
        return NegationExtent.PRIOR_EXAM_ABSENCE

    before_target = text[max(0, target_start - 120):target_start]
    if _MODIFIER_SUBJECT.search(before_target):
        return NegationExtent.MODIFIER_ONLY

    qualifier_window = text[max(0, target_start - 55):target_start]
    if _QUALIFIED_TARGET.search(qualifier_window):
        return NegationExtent.QUALIFIED_SUBSET

    if has_explicit_locality:
        return NegationExtent.LOCAL_TARGET

    return NegationExtent.WHOLE_TARGET


def classify_negation_extent(
    clause: str,
    target_start: int,
    target_end: int,
    *,
    legacy_polarity: AssertionPolarity,
    target_domain: TargetDomain = TargetDomain.UNKNOWN,
    has_explicit_locality: bool = False,
) -> NegationExtent:
    """Annotate negation extent without changing legacy assertion polarity.

    The legacy polarity remains the production decision input in checkpoint 2A.
    This helper records only internal metadata for later audited aggregation work.
    """
    text = str(clause or "")

    post_target = classify_post_target_negation_extent(
        text,
        target_start,
        target_end,
        has_explicit_locality=has_explicit_locality,
    )
    if post_target != NegationExtent.NONE:
        if (
            target_domain == TargetDomain.OUT_OF_TARGET
            and post_target
            not in {
                NegationExtent.PRIOR_EXAM_ABSENCE,
                NegationExtent.MODIFIER_ONLY,
            }
        ):
            return NegationExtent.OUT_OF_TARGET_ANATOMY
        return post_target

    if legacy_polarity == AssertionPolarity.NEGATED_MODIFIER:
        return NegationExtent.MODIFIER_ONLY

    if legacy_polarity != AssertionPolarity.NEGATED:
        return NegationExtent.NONE

    local_window = text[max(0, target_start - 140): min(len(text), target_end + 180)]
    if _PRIOR_EXAM.search(local_window):
        return NegationExtent.PRIOR_EXAM_ABSENCE

    if target_domain == TargetDomain.OUT_OF_TARGET:
        return NegationExtent.OUT_OF_TARGET_ANATOMY

    qualifier_window = text[max(0, target_start - 70): min(len(text), target_end + 30)]
    if _QUALIFIED_TARGET.search(qualifier_window):
        return NegationExtent.QUALIFIED_SUBSET

    if has_explicit_locality:
        return NegationExtent.LOCAL_TARGET

    if target_domain == TargetDomain.IN_TARGET:
        return NegationExtent.WHOLE_TARGET

    return NegationExtent.UNKNOWN_SCOPE
