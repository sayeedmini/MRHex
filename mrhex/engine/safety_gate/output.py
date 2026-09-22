"""Output contract formatting for deterministic-v2.

Ensures:
  - report_text[start:end] == evidence_span.text for every span
  - deterministic_state is null when routing_decision is ROUTE_TO_LLM
  - All required fields are present
"""
from __future__ import annotations

from typing import Optional

from mrhex.engine.types import (
    ArchitectureStage,
    ClassificationResult,
    EvidenceState,
    EvidenceUnit,
    RoutingDecision,
)


def validate_evidence_spans(
    report_text: str,
    evidence_units: list[EvidenceUnit],
) -> list[str]:
    """Validate that all evidence spans are exact substrings of report text.

    Returns list of validation error messages (empty = all valid).
    """
    errors: list[str] = []
    for i, eu in enumerate(evidence_units):
        if eu.start < 0 or eu.end > len(report_text):
            errors.append(f"Span {i}: offsets [{eu.start}:{eu.end}] outside report bounds [0:{len(report_text)}]")
            continue
        actual = report_text[eu.start:eu.end]
        if actual != eu.text:
            errors.append(
                f"Span {i}: report_text[{eu.start}:{eu.end}] = {actual!r} != span.text = {eu.text!r}"
            )
    return errors


def format_output(
    case_id: str,
    source_mode: str,
    target_pathology: str,
    deterministic_state: Optional[EvidenceState],
    routing_decision: RoutingDecision,
    reason_codes: list[str],
    evidence_units: list[EvidenceUnit],
    architecture_stage_resolved: ArchitectureStage,
    rule_family_id: Optional[str],
    technical_status: str,
    report_text: str = "",
    routing_trigger_ids: Optional[list[str]] = None,
) -> ClassificationResult:
    """Format the final classification output per v2 contract.

    Enforces the invariant:
        if routing_decision == ROUTE_TO_LLM: deterministic_state MUST be None
    """
    triggers = list(routing_trigger_ids or [])

    # Enforce routing invariant
    if routing_decision == RoutingDecision.ROUTE_TO_LLM:
        deterministic_state = None
        rule_family_id = None
        is_placeholder = True
        primary_evaluable = False
        prediction_status = "ABSTAINED"
    elif deterministic_state == EvidenceState.NEI:
        is_placeholder = True
        primary_evaluable = False
        prediction_status = "NON_EVALUABLE"
    else:
        is_placeholder = False
        primary_evaluable = True
        prediction_status = "RESOLVED"

    # Format evidence spans
    evidence_spans = [eu.to_span_dict() for eu in evidence_units]

    # Validate evidence spans if report text is available
    if report_text:
        errors = validate_evidence_spans(report_text, evidence_units)
        if errors:
            technical_status = f"EVIDENCE_VALIDATION_FAILURE: {'; '.join(errors[:3])}"

    return ClassificationResult(
        case_id=case_id,
        source_mode=source_mode,
        target_pathology=target_pathology,
        deterministic_state=deterministic_state,
        routing_decision=routing_decision,
        reason_codes=reason_codes,
        evidence_spans=evidence_spans,
        architecture_stage_resolved=architecture_stage_resolved,
        rule_family_id=rule_family_id,
        technical_status=technical_status,
        routing_trigger_ids=triggers,
        is_placeholder_decision=is_placeholder,
        primary_evaluable=primary_evaluable,
        prediction_status=prediction_status,
    )


def to_runner_dict(result: ClassificationResult) -> dict:
    """Convert ClassificationResult to the runner-compatible output dict.

    Policy Conformance (Tasks 10, 11):
    - When routing_decision == ROUTE_TO_LLM:
      Deterministic prediction is ABSTAINED/UNRESOLVED.
      deterministic_state MUST remain null.
      Runner placeholder binary_decision is 'WEAK_SUPPORT' (to satisfy legacy runner validation),
      marked explicitly with is_placeholder_decision=True, primary_evaluable=False,
      prediction_status='ABSTAINED', and exposed routing_trigger_ids.
    - When deterministic_state == NEI:
      Primary binary analysis must exclude it.
      binary_decision is 'NON_EVALUABLE', support_category is 'NEI',
      primary_evaluable=False.
    - When deterministic_state == S:
      binary_decision is 'SUPPORTED', primary_evaluable=True.
    - When deterministic_state in {U, C, UC, H}:
      binary_decision is 'WEAK_SUPPORT', primary_evaluable=True.
    """
    d = result.to_dict()

    state = result.deterministic_state
    if result.routing_decision == RoutingDecision.ROUTE_TO_LLM:
        # Legacy runner validation requires binary_decision in BINARY_LABELS
        binary_decision = "WEAK_SUPPORT"
        primary_evaluable = False
        is_placeholder = True
        prediction_status = "ABSTAINED"
    elif state == EvidenceState.NEI:
        # Legacy runner validate_system_output explicitly allows NON_EVALUABLE for NEI
        binary_decision = "NON_EVALUABLE"
        primary_evaluable = False
        is_placeholder = True
        prediction_status = "NON_EVALUABLE"
    elif state == EvidenceState.S:
        binary_decision = "SUPPORTED"
        primary_evaluable = True
        is_placeholder = False
        prediction_status = "RESOLVED"
    else:
        binary_decision = "WEAK_SUPPORT"
        primary_evaluable = True
        is_placeholder = False
        prediction_status = "RESOLVED"

    d["system"] = "mrhex.engine"
    d["version"] = "0.2.7a-pineal-composition-dev"
    d["binary_decision"] = binary_decision
    d["deterministic_binary"] = binary_decision if not is_placeholder else None
    d["is_placeholder_decision"] = is_placeholder
    d["primary_evaluable"] = primary_evaluable
    d["prediction_status"] = prediction_status
    d["review_recommended"] = result.routing_decision == RoutingDecision.ROUTE_TO_LLM
    d["ambiguous"] = result.routing_decision == RoutingDecision.ROUTE_TO_LLM
    d["resolved_by_rules"] = result.routing_decision == RoutingDecision.SAFE_RULE
    d["sent_to_llm"] = result.routing_decision == RoutingDecision.ROUTE_TO_LLM
    d["support_category"] = state.value if state else None
    d["routing_reasons"] = result.reason_codes if result.routing_decision == RoutingDecision.ROUTE_TO_LLM else []
    d["routing_trigger_ids"] = result.routing_trigger_ids
    d["reason_category"] = result.reason_codes[0] if result.reason_codes else ""
    d["reason_categories"] = result.reason_codes
    d["report_sections_present"] = []  # Filled by caller

    return d
