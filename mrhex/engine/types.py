"""Deterministic-v2 typed evidence model and contract definitions.

All structures follow the v2 policy specification (v0.1.1-dev).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EvidenceState(str, Enum):
    """Six top-level evidence states (unchanged from v1 taxonomy)."""
    S = "S"       # Supported
    U = "U"       # Unsupported
    C = "C"       # Contradicted
    UC = "UC"     # Uncertain / Hedged
    H = "H"       # Historical Only
    NEI = "NEI"   # Not Enough Information


class RoutingDecision(str, Enum):
    """Safety routing outcome."""
    SAFE_RULE = "SAFE_RULE"
    ROUTE_TO_LLM = "ROUTE_TO_LLM"


class ArchitectureStage(str, Enum):
    """Five architecture stages of the v2 pipeline."""
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    LOCAL_ASSERTION_INTERPRETATION = "LOCAL_ASSERTION_INTERPRETATION"
    TARGET_ALIGNMENT = "TARGET_ALIGNMENT"
    EVIDENCE_AGGREGATION = "EVIDENCE_AGGREGATION"
    SAFETY_VALIDITY_GATE = "SAFETY_VALIDITY_GATE"


class Section(str, Enum):
    """Report section identifiers (v2 extends v1 with TECHNIQUE)."""
    FINDINGS = "FINDINGS"
    IMPRESSION = "IMPRESSION"
    CLINICAL_HISTORY = "CLINICAL_HISTORY"
    COMPARISON = "COMPARISON"
    RECOMMENDATION = "RECOMMENDATION"
    TECHNIQUE = "TECHNIQUE"
    OTHER = "OTHER"
    NONE = "NONE"


class AssertionPolarity(str, Enum):
    """Assertion polarity for an evidence mention."""
    AFFIRMED = "AFFIRMED"
    NEGATED = "NEGATED"
    NEGATED_MODIFIER = "NEGATED_MODIFIER"   # modifier negated, target affirmed
    AMBIGUOUS = "AMBIGUOUS"


class CertaintyLevel(str, Enum):
    """Certainty classification for an evidence mention."""
    DEFINITE = "DEFINITE"
    HEDGED = "HEDGED"
    DIFFERENTIAL = "DIFFERENTIAL"
    AMBIGUOUS = "AMBIGUOUS"


class TemporalityClass(str, Enum):
    """Temporality classification for an evidence mention."""
    CURRENT = "CURRENT"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    CHRONIC_CURRENT = "CHRONIC_CURRENT"
    STABLE_CURRENT = "STABLE_CURRENT"
    REGRESSING = "REGRESSING"
    RESIDUAL = "RESIDUAL"
    RESOLVED = "RESOLVED"
    CLINICAL_INDICATION = "CLINICAL_INDICATION"
    AMBIGUOUS = "AMBIGUOUS"


class AlignmentStatus(str, Enum):
    """Alignment status for anatomy, laterality, or subtype."""
    ALIGNED = "ALIGNED"
    CONFIRMED_MISMATCH = "CONFIRMED_MISMATCH"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class NegationExtent(str, Enum):
    """Semantic extent of a negative assertion.

    Migration-checkpoint-1 plumbing only. Existing production logic does not
    consume this field unless a later, explicitly gated checkpoint enables it.
    """
    NONE = "NONE"
    WHOLE_TARGET = "WHOLE_TARGET"
    LOCAL_TARGET = "LOCAL_TARGET"
    QUALIFIED_SUBSET = "QUALIFIED_SUBSET"
    MODIFIER_ONLY = "MODIFIER_ONLY"
    PRIOR_EXAM_ABSENCE = "PRIOR_EXAM_ABSENCE"
    OUT_OF_TARGET_ANATOMY = "OUT_OF_TARGET_ANATOMY"
    UNKNOWN_SCOPE = "UNKNOWN_SCOPE"


class TargetDomain(str, Enum):
    """Whether evidence lies inside the codebook target domain."""
    IN_TARGET = "IN_TARGET"
    OUT_OF_TARGET = "OUT_OF_TARGET"
    UNKNOWN = "UNKNOWN"


class SpinalRegion(str, Enum):
    """Normalized spinal region for scoped evidence."""
    CERVICAL = "CERVICAL"
    THORACIC = "THORACIC"
    LUMBAR = "LUMBAR"


class ScopeLaterality(str, Enum):
    """Normalized laterality used only for scope compatibility."""
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    BILATERAL = "BILATERAL"
    UNSPECIFIED = "UNSPECIFIED"


class ConflictDisposition(str, Enum):
    """Pure scope-comparison result for future gated aggregation."""
    TRUE_CONFLICT = "TRUE_CONFLICT"
    NON_CONFLICT = "NON_CONFLICT"
    ROUTE_UNKNOWN = "ROUTE_UNKNOWN"
    NOT_COMPARABLE = "NOT_COMPARABLE"


# ---------------------------------------------------------------------------
# Reason Codes — All 26 from the policy spec
# ---------------------------------------------------------------------------

class ReasonCode(str, Enum):
    """Orthogonal reason codes from v2 policy spec (v0.1.1-dev).

    Each code is tagged with its architecture stage and whether it
    may support SAFE_RULE emission or requires mandatory routing.
    """
    # Stage 2: LOCAL_ASSERTION_INTERPRETATION
    ASSERT_DIRECT_CURRENT = "ASSERT_DIRECT_CURRENT"
    ASSERT_TARGET_NEGATED = "ASSERT_TARGET_NEGATED"
    ASSERT_HEDGED = "ASSERT_HEDGED"
    DIFFERENTIAL_OR_ALTERNATIVE = "DIFFERENTIAL_OR_ALTERNATIVE"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    CURRENT_RESIDUAL_OR_SEQUELA = "CURRENT_RESIDUAL_OR_SEQUELA"
    TEMPORAL_REGRESSION_NOT_RESOLUTION = "TEMPORAL_REGRESSION_NOT_RESOLUTION"
    NEGATED_MODIFIER_NOT_TARGET = "NEGATED_MODIFIER_NOT_TARGET"
    MALFORMED_OR_COMPLEX_SCOPE = "MALFORMED_OR_COMPLEX_SCOPE"

    # Stage 1: EVIDENCE_RETRIEVAL
    BROAD_NORMAL_SCOPE = "BROAD_NORMAL_SCOPE"
    CLINICAL_ONLY_PROVENANCE = "CLINICAL_ONLY_PROVENANCE"
    LIMITED_EXAM_OR_COVERAGE = "LIMITED_EXAM_OR_COVERAGE"
    TARGET_RETRIEVAL_INCOMPLETE = "TARGET_RETRIEVAL_INCOMPLETE"

    # Stage 3: TARGET_ALIGNMENT
    ANATOMY_OR_COMPARTMENT_MISMATCH = "ANATOMY_OR_COMPARTMENT_MISMATCH"
    LATERALITY_CONFLICT = "LATERALITY_CONFLICT"
    SUBTYPE_MISMATCH = "SUBTYPE_MISMATCH"
    LINEAGE_UNESTABLISHED = "LINEAGE_UNESTABLISHED"
    CHRONICITY_UNESTABLISHED = "CHRONICITY_UNESTABLISHED"
    UNVALIDATED_EQUIVALENCE = "UNVALIDATED_EQUIVALENCE"
    RELATED_NON_EQUIVALENT_FINDING = "RELATED_NON_EQUIVALENT_FINDING"
    INDIRECT_SUPPORT = "INDIRECT_SUPPORT"
    THRESHOLD_BOUNDARY = "THRESHOLD_BOUNDARY"

    # Stage 4: EVIDENCE_AGGREGATION
    SPECIFIC_VS_GLOBAL_CONFLICT = "SPECIFIC_VS_GLOBAL_CONFLICT"
    SECTION_CERTAINTY_SHIFT = "SECTION_CERTAINTY_SHIFT"
    SECTION_LOCATION_MISMATCH = "SECTION_LOCATION_MISMATCH"
    LESION_SPECIFIC_CERTAINTY = "LESION_SPECIFIC_CERTAINTY"
    MODALITY_DISCORDANCE = "MODALITY_DISCORDANCE"


# Metadata per reason code
REASON_CODE_META: dict[str, dict] = {
    "ASSERT_DIRECT_CURRENT":            {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "ASSERT_TARGET_NEGATED":            {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "ASSERT_HEDGED":                    {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "DIFFERENTIAL_OR_ALTERNATIVE":      {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "HISTORICAL_ONLY":                  {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "CURRENT_RESIDUAL_OR_SEQUELA":      {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "TEMPORAL_REGRESSION_NOT_RESOLUTION": {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "NEGATED_MODIFIER_NOT_TARGET":       {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": True,  "requires_routing": False},
    "MALFORMED_OR_COMPLEX_SCOPE":       {"stage": ArchitectureStage.LOCAL_ASSERTION_INTERPRETATION, "may_support_safe_rule": False, "requires_routing": True},
    "BROAD_NORMAL_SCOPE":               {"stage": ArchitectureStage.EVIDENCE_RETRIEVAL,             "may_support_safe_rule": False, "requires_routing": False},
    "CLINICAL_ONLY_PROVENANCE":         {"stage": ArchitectureStage.EVIDENCE_RETRIEVAL,             "may_support_safe_rule": False, "requires_routing": True},
    "LIMITED_EXAM_OR_COVERAGE":         {"stage": ArchitectureStage.EVIDENCE_RETRIEVAL,             "may_support_safe_rule": True,  "requires_routing": False},
    "TARGET_RETRIEVAL_INCOMPLETE":      {"stage": ArchitectureStage.EVIDENCE_RETRIEVAL,             "may_support_safe_rule": False, "requires_routing": True},
    "ANATOMY_OR_COMPARTMENT_MISMATCH":  {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": True,  "requires_routing": False},
    "LATERALITY_CONFLICT":              {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": False, "requires_routing": True},
    "SUBTYPE_MISMATCH":                 {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": True,  "requires_routing": False},
    "LINEAGE_UNESTABLISHED":            {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": False, "requires_routing": True},
    "CHRONICITY_UNESTABLISHED":         {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": False, "requires_routing": True},
    "UNVALIDATED_EQUIVALENCE":          {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": False, "requires_routing": True},
    "RELATED_NON_EQUIVALENT_FINDING":   {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": True,  "requires_routing": False},
    "INDIRECT_SUPPORT":                 {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": False, "requires_routing": True},
    "THRESHOLD_BOUNDARY":               {"stage": ArchitectureStage.TARGET_ALIGNMENT,               "may_support_safe_rule": False, "requires_routing": True},
    "SPECIFIC_VS_GLOBAL_CONFLICT":      {"stage": ArchitectureStage.EVIDENCE_AGGREGATION,           "may_support_safe_rule": False, "requires_routing": True},
    "SECTION_CERTAINTY_SHIFT":          {"stage": ArchitectureStage.EVIDENCE_AGGREGATION,           "may_support_safe_rule": False, "requires_routing": True},
    "SECTION_LOCATION_MISMATCH":        {"stage": ArchitectureStage.EVIDENCE_AGGREGATION,           "may_support_safe_rule": False, "requires_routing": True},
    "LESION_SPECIFIC_CERTAINTY":        {"stage": ArchitectureStage.EVIDENCE_AGGREGATION,           "may_support_safe_rule": False, "requires_routing": True},
    "MODALITY_DISCORDANCE":             {"stage": ArchitectureStage.EVIDENCE_AGGREGATION,           "may_support_safe_rule": False, "requires_routing": True},
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SectionSpan:
    """A contiguous section of report text with provenance."""
    section: Section
    start: int
    end: int
    text: str
    raw_header: str = ""  # The literal header text matched, empty for OTHER/NONE


@dataclass(frozen=True)
class ScopeIdentity:
    """Normalized evidence scope for future gated conflict comparison.

    Defaults intentionally encode "unknown / not supplied" so adding this
    structure cannot change legacy D1 behavior by itself.
    """
    target_domain: TargetDomain = TargetDomain.UNKNOWN
    spinal_regions: frozenset[SpinalRegion] = field(default_factory=frozenset)
    spinal_levels: frozenset[str] = field(default_factory=frozenset)
    anatomic_subregions: frozenset[str] = field(default_factory=frozenset)
    laterality: ScopeLaterality = ScopeLaterality.UNSPECIFIED
    explicit_locality: bool = False


@dataclass
class EvidenceUnit:
    """A single evidence mention extracted from the report.

    Carries all per-mention attributes through the 5-stage pipeline.
    """
    text: str                                          # exact substring of source report
    start: int                                         # character offset (inclusive)
    end: int                                           # character offset (exclusive)
    section: Section                                   # section provenance
    matched_term: str                                  # the vocabulary term that matched
    target_pathology: str = ""                         # which target this evidence relates to

    # Stage 2 outputs
    assertion_polarity: AssertionPolarity = AssertionPolarity.AFFIRMED
    certainty: CertaintyLevel = CertaintyLevel.DEFINITE
    temporality: TemporalityClass = TemporalityClass.CURRENT

    # Stage 3 outputs
    anatomy_status: AlignmentStatus = AlignmentStatus.NOT_APPLICABLE
    laterality_status: AlignmentStatus = AlignmentStatus.NOT_APPLICABLE
    subtype_status: AlignmentStatus = AlignmentStatus.NOT_APPLICABLE

    # Accumulated reason codes
    reason_codes: list[ReasonCode] = field(default_factory=list)

    # Contextual metadata
    sentence_text: str = ""
    sentence_start: int = 0
    sentence_end: int = 0
    clause_text: str = ""
    clause_start: int = 0
    clause_end: int = 0

    # Migration checkpoint 1: internal-only scoped-evidence plumbing.
    # Defaults preserve all legacy behavior. These fields are intentionally not
    # serialized by to_span_dict() in this checkpoint.
    negation_extent: NegationExtent = NegationExtent.NONE
    scope: ScopeIdentity = field(default_factory=ScopeIdentity)

    def to_span_dict(self) -> dict:
        """Format for output contract evidence_spans list."""
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "section": self.section.value,
            "polarity": self.assertion_polarity.value,
            "matched_term": self.matched_term,
            "certainty": self.certainty.value,
            "temporality": self.temporality.value,
        }



@dataclass
class ClassificationResult:
    """Output of the deterministic-v2 classifier, matching the v2 output contract."""
    case_id: str
    source_mode: str                                    # "findings" or "full_report"
    target_pathology: str
    deterministic_state: Optional[EvidenceState]        # MUST be None when routing
    routing_decision: RoutingDecision
    reason_codes: list[str]                             # list of ReasonCode values
    evidence_spans: list[dict]                          # list of span dicts
    architecture_stage_resolved: ArchitectureStage
    rule_family_id: Optional[str]                       # e.g. "R13" if SAFE_RULE
    technical_status: str                               # "SUCCESS", "PARSE_ERROR", etc.
    routing_trigger_ids: list[str] = field(default_factory=list)  # Trigger IDs causing ROUTE_TO_LLM
    is_placeholder_decision: bool = False               # True if binary_decision is runner placeholder
    primary_evaluable: bool = True                      # False if excluded from primary binary analysis
    prediction_status: str = "RESOLVED"                 # "RESOLVED", "ABSTAINED", "NON_EVALUABLE"

    def to_dict(self) -> dict:
        """Serialize to the v2 output contract dictionary."""
        return {
            "case_id": self.case_id,
            "source_mode": self.source_mode,
            "target_pathology": self.target_pathology,
            "deterministic_state": self.deterministic_state.value if self.deterministic_state else None,
            "routing_decision": self.routing_decision.value,
            "reason_codes": self.reason_codes,
            "evidence_spans": self.evidence_spans,
            "architecture_stage_resolved": self.architecture_stage_resolved.value,
            "rule_family_id": self.rule_family_id,
            "technical_status": self.technical_status,
            "routing_trigger_ids": self.routing_trigger_ids,
            "is_placeholder_decision": self.is_placeholder_decision,
            "primary_evaluable": self.primary_evaluable,
            "prediction_status": self.prediction_status,
        }

