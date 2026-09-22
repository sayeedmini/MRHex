"""Authoritative primary binary evaluation for deterministic-v2.

This module intentionally maps the six-state policy directly, rather than
reusing runner placeholders.  Routed rows are not deterministic predictions
and NEI is excluded from the primary binary denominator.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping


PRIMARY_BINARY_POLICY = {
    "S": "SUPPORTED",
    "U": "WEAK_SUPPORT",
    "C": "WEAK_SUPPORT",
    "UC": "WEAK_SUPPORT",
    "H": "WEAK_SUPPORT",
    "NEI": None,
}


def primary_binary_from_state(state: str | None) -> str | None:
    """Return the policy-defined primary binary label, or ``None`` for NEI.

    ``None`` is also retained for a routed/no deterministic state; this avoids
    treating a legacy runner placeholder as a scored WEAK_SUPPORT prediction.
    """
    if state is None:
        return None
    try:
        return PRIMARY_BINARY_POLICY[str(state)]
    except KeyError as exc:
        raise ValueError(f"Unknown deterministic evidence state: {state!r}") from exc


def evaluate_primary_binary(rows: Iterable[Mapping[str, object]], reference_key: str) -> dict[str, object]:
    """Score evaluable deterministic rows against a six-state reference column.

    The returned denominator excludes routed rows and rows whose prediction or
    reference is NEI.  It is deliberately reference-column agnostic so the
    sealed prediction file can be joined only after sealing.
    """
    total = correct = false_clears = false_alarms = 0
    state_distribution: Counter[str] = Counter()
    for row in rows:
        predicted = primary_binary_from_state(row.get("deterministic_state"))
        reference = primary_binary_from_state(row.get(reference_key))
        if predicted is None or reference is None:
            continue
        total += 1
        state_distribution[str(row.get("deterministic_state"))] += 1
        if predicted == reference:
            correct += 1
        elif predicted == "SUPPORTED":
            false_clears += 1
        else:
            false_alarms += 1
    return {
        "primary_evaluable_n": total,
        "correct": correct,
        "accuracy": (correct / total) if total else None,
        "false_clears": false_clears,
        "false_alarms": false_alarms,
        "predicted_state_distribution": dict(state_distribution),
        "policy": PRIMARY_BINARY_POLICY.copy(),
    }
