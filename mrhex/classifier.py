"""MRHex Classifier.

Public classification entry point producing exactly one MR-RATE state
for every input case without calling external APIs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from mrhex.config import load_config
from mrhex.engine.selective import classify_core_rules
from mrhex.rules.fallback import resolve_deterministic_fallback

SYSTEM_ID = "mrhex"
VERSION = "1.0.0"
VALID_STATES = frozenset({"S", "U", "C", "UC", "H", "NEI"})
VALID_STANDALONE_STATES = VALID_STATES  # Backward compatibility alias

_CACHED_LOOKUP: dict[str, dict[str, Any]] | None = None
_CACHED_ACTIVE_LABELS: set[str] | None = None


def get_default_lookup() -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Get or lazily load the default MRHex configuration lookup."""
    global _CACHED_LOOKUP, _CACHED_ACTIVE_LABELS
    if _CACHED_LOOKUP is None:
        _CACHED_LOOKUP, _CACHED_ACTIVE_LABELS = load_config()
    return _CACHED_LOOKUP, _CACHED_ACTIVE_LABELS


def classify(
    report: object,
    target_or_entry: str | Mapping[str, Any],
    *,
    case_id: str = "",
    source_mode: str = "full_report",
    lookup: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute MRHex deterministic assertion classification on a single case.

    Public interface:
        result = classify(report, target_pathology)

    Args:
        report: Medical report text (or None).
        target_or_entry: Target pathology name string (e.g. "Spinal stenosis")
                         OR preloaded codebook entry mapping.
        case_id: Optional case identifier for alignment and tracking.
        source_mode: "full_report" (default) or "findings".
        lookup: Optional preloaded configuration lookup mapping.

    Returns:
        Dictionary containing prediction and provenance details.
    """
    if isinstance(target_or_entry, str):
        target_pathology = target_or_entry
        if lookup is None:
            default_lookup, _ = get_default_lookup()
            lookup = default_lookup
        if target_pathology not in lookup:
            raise KeyError(f"Target pathology '{target_pathology}' not found in MRHex configuration.")
        entry = lookup[target_pathology]
    else:
        entry = target_or_entry
        target_pathology = str(entry.get("label", entry.get("canonical_name", "")))

    # Step 1: Run core rule classification
    core_out = classify_core_rules(
        report,
        entry,
        case_id=case_id,
        source_mode=source_mode,
    )

    core_routing = core_out.get("routing_decision", "")
    core_state = core_out.get("deterministic_state") or ""

    # Step 2: If core rule is SAFE_RULE, preserve unchanged
    if core_routing == "SAFE_RULE" and core_state in VALID_STATES:
        final_state = core_state
        resolution_source = "CORE_RULE"
        fallback_rule_id = core_out.get("rule_family_id") or "CORE_RULE"
        reason_code = core_out.get("reason_codes", [fallback_rule_id])
        primary_reason = reason_code[0] if isinstance(reason_code, list) and reason_code else str(reason_code)
        evidence_spans = core_out.get("evidence_spans", [])
    else:
        # Step 3: Routed case -> deterministic fallback resolver
        fallback_out = resolve_deterministic_fallback(
            report,
            entry,
            core_out,
            case_id=case_id,
            source_mode=source_mode,
        )
        final_state = fallback_out.get("state") or fallback_out["standalone_state"]
        resolution_source = "FALLBACK_RULE"
        core_routing = "ROUTE_TO_LLM"
        fallback_rule_id = fallback_out["fallback_rule_id"]
        primary_reason = fallback_out["reason_code"]
        evidence_spans = fallback_out.get("evidence_spans", [])

    assert final_state in VALID_STATES, (
        f"Invariant Violated: state '{final_state}' not in {VALID_STATES} for case {case_id}"
    )

    out = dict(core_out)
    out["system"] = SYSTEM_ID
    out["version"] = VERSION
    out["case_id"] = case_id
    out["target_pathology"] = target_pathology
    out["state"] = final_state
    out["prediction"] = final_state
    out["standalone_state"] = final_state  # Internal compatibility
    out["deterministic_state"] = final_state
    out["routing_decision"] = "SAFE_RULE"
    out["resolution_source"] = resolution_source
    out["core_routing"] = core_routing
    out["core_state"] = core_state
    out["fallback_rule_id"] = fallback_rule_id
    out["reason"] = primary_reason
    out["reason_code"] = primary_reason
    out["raw_reason"] = primary_reason
    out["evidence_spans"] = evidence_spans

    return out

# Alias for backward compatibility
classify_core = classify

