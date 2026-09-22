"""Internal scope-normalization helpers for D1 migration checkpoint 1.

This module is not imported by the production classifier in checkpoint 1.
It only establishes typed, deterministic normalization primitives for later
feature-gated scope-aware assertion/aggregation work.
"""
from __future__ import annotations

import re

from mrhex.engine.types import (
    AlignmentStatus,
    EvidenceUnit,
    ScopeIdentity,
    ScopeLaterality,
    SpinalRegion,
    TargetDomain,
)


_SPINAL_LEVEL = re.compile(
    r"\b([CTL])\s*(\d{1,2})\s*[-–—/]\s*([CTL])?\s*(\d{1,2})\b",
    re.I,
)

_REGION_PATTERNS: tuple[tuple[SpinalRegion, re.Pattern[str]], ...] = (
    (SpinalRegion.CERVICAL, re.compile(r"\bcervical\b", re.I)),
    (SpinalRegion.THORACIC, re.compile(r"\bthoracic\b", re.I)),
    (SpinalRegion.LUMBAR, re.compile(r"\blumbar\b", re.I)),
)

_GENERIC_SUBREGIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("brainstem", re.compile(r"\bbrainstem\b", re.I)),
    ("infratentorial", re.compile(r"\binfratentorial\b", re.I)),
    ("supratentorial", re.compile(r"\bsupratentorial\b", re.I)),
    ("cerebellar", re.compile(r"\b(?:cerebellum|cerebellar)\b", re.I)),
    ("frontal", re.compile(r"\bfrontal\b", re.I)),
    ("parietal", re.compile(r"\bparietal\b", re.I)),
    ("temporal", re.compile(r"\btemporal\b", re.I)),
    ("occipital", re.compile(r"\boccipital\b", re.I)),
)


_CRANIAL_FORAMINA = re.compile(
    r"\b(?:foramen\s+magnum|foramen\s+of\s+monro|jugular\s+foramen|"
    r"optic\s+foramen|mental\s+foramen|infraorbital\s+foramen)\b",
    re.I,
)

_OUT_OF_BRAIN_METASTASIS = re.compile(
    r"\b(?:bony\s+structures?\s+of\s+the\s+cranium|cranial\s+bones?|"
    r"calvarium|calvarial|skull|bone\s+metasta(?:sis|ses)|"
    r"vertebr\w*|paravertebral|epidural\s+space|spinal|"
    r"leptomeningeal|meningeal|dural)\b",
    re.I,
)


def target_uses_spinal_scope(target_pathology: str) -> bool:
    """Return whether level/region identity is meaningful for this target."""
    target = str(target_pathology or "").casefold()
    return bool(
        "spinal" in target
        or "vertebral" in target
        or "foraminal" in target
        or "herniation of nucleus pulposus" in target
    )


def _region_from_prefix(prefix: str) -> SpinalRegion:
    p = prefix.upper()
    if p == "C":
        return SpinalRegion.CERVICAL
    if p == "T":
        return SpinalRegion.THORACIC
    return SpinalRegion.LUMBAR


def extract_spinal_levels(text: str) -> frozenset[str]:
    levels: set[str] = set()
    for match in _SPINAL_LEVEL.finditer(str(text or "")):
        p1, n1, p2, n2 = match.groups()
        p1 = p1.upper()
        p2 = (p2 or p1).upper()
        levels.add(f"{p1}{int(n1)}-{p2}{int(n2)}")
    return frozenset(levels)


def extract_spinal_regions(text: str) -> frozenset[SpinalRegion]:
    value = str(text or "")
    regions: set[SpinalRegion] = set()
    for region, pattern in _REGION_PATTERNS:
        if pattern.search(value):
            regions.add(region)
    for match in _SPINAL_LEVEL.finditer(value):
        p1, _, p2, _ = match.groups()
        regions.add(_region_from_prefix(p1))
        if p2:
            regions.add(_region_from_prefix(p2))
    return frozenset(regions)


def extract_scope_laterality(text: str) -> ScopeLaterality:
    value = str(text or "")
    if re.search(r"\b(?:bilateral|both\s+(?:sides?|foramina|neural\s+foramina))\b", value, re.I):
        return ScopeLaterality.BILATERAL
    left = bool(re.search(r"\bleft\b", value, re.I))
    right = bool(re.search(r"\bright\b", value, re.I))
    if left and right:
        return ScopeLaterality.BILATERAL
    if left:
        return ScopeLaterality.LEFT
    if right:
        return ScopeLaterality.RIGHT
    return ScopeLaterality.UNSPECIFIED


def extract_anatomic_subregions(text: str) -> frozenset[str]:
    value = str(text or "")
    return frozenset(
        name for name, pattern in _GENERIC_SUBREGIONS if pattern.search(value)
    )


def build_scope_identity(
    text: str,
    *,
    target_domain: TargetDomain = TargetDomain.UNKNOWN,
) -> ScopeIdentity:
    """Build normalized scope metadata without changing any classifier state."""
    levels = extract_spinal_levels(text)
    regions = extract_spinal_regions(text)
    subregions = extract_anatomic_subregions(text)
    laterality = extract_scope_laterality(text)
    explicit_locality = bool(levels or regions or subregions or laterality != ScopeLaterality.UNSPECIFIED)
    return ScopeIdentity(
        target_domain=target_domain,
        spinal_regions=regions,
        spinal_levels=levels,
        anatomic_subregions=subregions,
        laterality=laterality,
        explicit_locality=explicit_locality,
    )


def infer_target_domain(
    text: str,
    target_pathology: str,
    *,
    anatomy_status: AlignmentStatus = AlignmentStatus.NOT_APPLICABLE,
) -> TargetDomain:
    """Infer target-domain membership conservatively for annotation only.

    Existing production anatomy alignment remains authoritative for decisions.
    This helper only records internal scope metadata.
    """
    value = str(text or "")
    target = str(target_pathology or "").casefold()

    if anatomy_status == AlignmentStatus.CONFIRMED_MISMATCH:
        return TargetDomain.OUT_OF_TARGET

    if "foraminal" in target and "stenosis" in target:
        if _CRANIAL_FORAMINA.search(value):
            return TargetDomain.OUT_OF_TARGET
        if re.search(
            r"\b(?:foraminal|neuroforaminal|neural\s+foram(?:en|ina))\b",
            value,
            re.I,
        ):
            return TargetDomain.IN_TARGET

    if "metastatic" in target and "brain" in target:
        if re.search(
            r"\b(?:parenchymal|cerebral\s+parenchymal|intra-axial)\b",
            value,
            re.I,
        ):
            return TargetDomain.IN_TARGET
        if _OUT_OF_BRAIN_METASTASIS.search(value):
            return TargetDomain.OUT_OF_TARGET
        if re.search(
            r"\b(?:brain|intracranial|supratentorial|infratentorial|brainstem|"
            r"cerebell\w*|frontal|parietal|temporal|occipital|cortex|cortical)\b",
            value,
            re.I,
        ):
            return TargetDomain.IN_TARGET

    if anatomy_status == AlignmentStatus.ALIGNED:
        return TargetDomain.IN_TARGET

    return TargetDomain.UNKNOWN


def nearest_preceding_spinal_levels(
    report: str,
    position: int,
    *,
    max_distance: int = 180,
) -> frozenset[str]:
    """Return the nearest explicit preceding spinal level within a tight window."""
    window_start = max(0, position - max_distance)
    window = str(report or "")[window_start:position]
    matches = list(_SPINAL_LEVEL.finditer(window))
    if not matches:
        return frozenset()
    last = matches[-1]
    p1, n1, p2, n2 = last.groups()
    p1 = p1.upper()
    p2 = (p2 or p1).upper()
    return frozenset({f"{p1}{int(n1)}-{p2}{int(n2)}"})


def nearest_preceding_spinal_region(
    report: str,
    position: int,
    *,
    max_distance: int = 1600,
) -> SpinalRegion | None:
    """Return the nearest explicit preceding spinal-region word."""
    window_start = max(0, position - max_distance)
    window = str(report or "")[window_start:position]
    best: tuple[int, SpinalRegion] | None = None
    for region, pattern in _REGION_PATTERNS:
        for match in pattern.finditer(window):
            absolute = window_start + match.start()
            if best is None or absolute > best[0]:
                best = (absolute, region)
    return best[1] if best else None


def annotate_evidence_scope(
    evidence: EvidenceUnit,
    report_text: str,
    target_pathology: str,
) -> ScopeIdentity:
    """Attach normalized internal scope metadata to one existing EvidenceUnit.

    This function does not alter assertion polarity, certainty, temporality,
    reason codes, alignment status, aggregation, or final classification.
    """
    context = evidence.clause_text or evidence.sentence_text or evidence.text
    levels = extract_spinal_levels(context)
    regions = set(extract_spinal_regions(context))

    is_spinal_target = target_uses_spinal_scope(target_pathology)
    if is_spinal_target and not levels:
        levels = nearest_preceding_spinal_levels(report_text, evidence.start)
    if is_spinal_target and not regions:
        for level in levels:
            prefix = level[0] if level else ""
            if prefix in {"C", "T", "L"}:
                regions.add(_region_from_prefix(prefix))
    if is_spinal_target and not levels and not regions:
        inherited_region = nearest_preceding_spinal_region(
            report_text, evidence.start
        )
        if inherited_region is not None:
            regions.add(inherited_region)

    combined_context = " ".join(
        part for part in (evidence.sentence_text, evidence.clause_text) if part
    ) or context
    domain = infer_target_domain(
        combined_context,
        target_pathology,
        anatomy_status=evidence.anatomy_status,
    )
    subregions = extract_anatomic_subregions(combined_context)
    laterality = extract_scope_laterality(combined_context)
    explicit_locality = bool(
        levels
        or regions
        or subregions
        or laterality != ScopeLaterality.UNSPECIFIED
    )

    scope = ScopeIdentity(
        target_domain=domain,
        spinal_regions=frozenset(regions),
        spinal_levels=levels,
        anatomic_subregions=subregions,
        laterality=laterality,
        explicit_locality=explicit_locality,
    )
    evidence.scope = scope
    return scope
