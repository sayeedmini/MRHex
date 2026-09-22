"""MRHex Configuration Loader."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import yaml

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CODEBOOK_PATH = _PACKAGE_ROOT / "configs" / "final_pathology_codebook.yaml"
_DEFAULT_BASE_RULES_PATH = _PACKAGE_ROOT / "configs" / "final_deterministic_rules_v2.yaml"
_DEFAULT_OVERLAY_PATH = _PACKAGE_ROOT / "configs" / "mrhex_label_configuration.yaml"

REQUIRED_ACTIVE_POLICY_FIELDS = {
    "label",
    "canonical_name",
    "operational_definition",
    "anatomical_scope",
    "accepted_equivalents",
    "insufficient_evidence",
    "subtype_rules",
}


ALLOWED_SCOPE_PRESENCE_SEMANTICS = {"ANY_IN_SCOPE"}
ALLOWED_SCOPE_POLICY_FIELDS = {"enabled", "presence_semantics"}


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected mapping in {path}")
    return data


def _index_codebook(codebook: dict[str, Any]) -> dict[str, dict[str, Any]]:
    labels = codebook.get("labels")
    if not isinstance(labels, list):
        raise RuntimeError("Codebook must contain a labels list")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in labels:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        if not label:
            continue
        if label in indexed:
            raise RuntimeError(f"Duplicate codebook label: {label}")
        indexed[str(label)] = deepcopy(entry)
    return indexed


def _validate_active_entry(label: str, entry: dict[str, Any]) -> None:
    missing = [
        field for field in sorted(REQUIRED_ACTIVE_POLICY_FIELDS)
        if field not in entry or entry[field] in (None, "")
    ]
    if missing:
        raise RuntimeError(f"Active D1 label {label} missing policy fields: {missing}")
    if not isinstance(entry.get("accepted_equivalents"), list):
        raise RuntimeError(f"Active D1 label {label}: accepted_equivalents must be a list")
    if not isinstance(entry.get("insufficient_evidence"), list):
        raise RuntimeError(f"Active D1 label {label}: insufficient_evidence must be a list")


def _validate_scope_policy(label: str, raw: Any) -> dict[str, Any] | None:
    """Validate an optional, explicitly audited scoped-evidence policy.

    Migration checkpoint 1 only parses and carries the policy. The production
    classifier does not consume it yet.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise RuntimeError(f"Active D1 label {label}: scope_policy must be a mapping")

    unknown = set(raw) - ALLOWED_SCOPE_POLICY_FIELDS
    if unknown:
        raise RuntimeError(
            f"Active D1 label {label}: unknown scope_policy fields: {sorted(unknown)}"
        )

    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise RuntimeError(
            f"Active D1 label {label}: scope_policy.enabled must be Boolean"
        )

    semantics = raw.get("presence_semantics")
    if semantics is not None and semantics not in ALLOWED_SCOPE_PRESENCE_SEMANTICS:
        raise RuntimeError(
            f"Active D1 label {label}: unsupported scope presence_semantics: {semantics}"
        )
    if enabled and semantics is None:
        raise RuntimeError(
            f"Active D1 label {label}: enabled scope_policy requires presence_semantics"
        )

    return deepcopy(raw)


def load_d1_lookup(
    codebook_path: str | Path,
    base_rules_path: str | Path,
    overlay_path: str | Path,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Build a fail-closed D1 lookup from audited label overlays."""
    codebook = _load_yaml(codebook_path)
    base_rules = _load_yaml(base_rules_path)
    overlay = _load_yaml(overlay_path)

    codebook_lookup = _index_codebook(codebook)
    mappings = base_rules.get("mappings", {})
    if not isinstance(mappings, dict):
        raise RuntimeError("Base deterministic rules must contain mappings")

    active_labels = set(overlay.get("active_labels", []))
    label_overlays = overlay.get("labels", {})
    if not active_labels:
        raise RuntimeError("D1 overlay must activate at least one audited label")
    if set(label_overlays) != active_labels:
        raise RuntimeError("D1 overlay labels must exactly equal active_labels")

    missing_codebook = active_labels - set(codebook_lookup)
    if missing_codebook:
        raise RuntimeError(f"Active D1 labels absent from codebook: {sorted(missing_codebook)}")
    overlay_provided_rules = {
        l for l, data in label_overlays.items()
        if isinstance(data, dict) and ("machine_rules" in data or "base_mapping" in data)
    }
    missing_rules = active_labels - (set(mappings) | overlay_provided_rules)
    if missing_rules:
        raise RuntimeError(f"Active D1 labels absent from v2 rule mapping: {sorted(missing_rules)}")

    global_overrides = deepcopy(base_rules.get("global_policy_overrides", {}))
    root_label_overrides = deepcopy(base_rules.get("label_policy_overrides", {}))

    lookup: dict[str, dict[str, Any]] = {}
    for label, original in codebook_lookup.items():
        entry = deepcopy(original)
        entry["_d1_active"] = label in active_labels
        entry["_d1_overlay_id"] = overlay.get("mapping_id", "")

        if label in active_labels:
            codebook_basis = label_overlays[label].get("codebook_basis", {})
            if isinstance(codebook_basis, dict):
                entry.update(deepcopy(codebook_basis))
            _validate_active_entry(label, entry)

            if label in mappings:
                machine = deepcopy(mappings[label])
            elif "machine_rules" in label_overlays[label]:
                machine = deepcopy(label_overlays[label]["machine_rules"])
            elif "base_mapping" in label_overlays[label]:
                machine = deepcopy(label_overlays[label]["base_mapping"])
            else:
                raise RuntimeError(f"Active D1 label absent from v2 rule mapping: {label}")

            # Scope policy is D1-overlay-owned and opt-in. Strip any inherited
            # value so legacy/v2 configuration can never silently activate it.
            machine.pop("scope_policy", None)
            scope_policy = _validate_scope_policy(
                label, label_overlays[label].get("scope_policy")
            )
            if scope_policy is not None:
                machine["scope_policy"] = scope_policy

            machine["global_policy_overrides"] = global_overrides
            machine["label_policy_overrides"] = {
                **deepcopy(root_label_overrides.get(label, {})),
                **deepcopy(machine.get("label_policy_overrides", {})),
                **deepcopy(label_overlays[label].get("label_policy_overrides", {})),
            }

            patterns = list(machine.get("compositional_patterns", []))
            existing_ids = {
                p.get("pattern_id") for p in patterns if isinstance(p, dict)
            }
            additions = label_overlays[label].get("add_compositional_patterns", [])
            for pattern in additions:
                pid = pattern.get("pattern_id")
                if not pid or pid in existing_ids:
                    raise RuntimeError(
                        f"Duplicate or missing D1 pattern_id for {label}: {pid}"
                    )
                patterns.append(deepcopy(pattern))
                existing_ids.add(pid)

            machine["compositional_patterns"] = patterns

            surface_forms = list(machine.get("surface_forms", []))
            seen_surface_forms = {str(x).casefold() for x in surface_forms}
            for term in label_overlays[label].get("add_surface_forms", []):
                cleaned = " ".join(str(term).split())
                if not cleaned:
                    raise RuntimeError(f"Blank D1 surface form for {label}")
                key = cleaned.casefold()
                if key in seen_surface_forms:
                    raise RuntimeError(
                        f"Duplicate D1 surface form for {label}: {cleaned}"
                    )
                surface_forms.append(cleaned)
                seen_surface_forms.add(key)
            machine["surface_forms"] = surface_forms

            excluded_anatomy = list(machine.get("excluded_anatomy", []))
            seen_excluded_anatomy = {str(x).casefold() for x in excluded_anatomy}
            for term in label_overlays[label].get("add_excluded_anatomy", []):
                cleaned = " ".join(str(term).split())
                if not cleaned:
                    raise RuntimeError(f"Blank D1 excluded anatomy for {label}")
                key = cleaned.casefold()
                if key in seen_excluded_anatomy:
                    raise RuntimeError(
                        f"Duplicate D1 excluded anatomy for {label}: {cleaned}"
                    )
                excluded_anatomy.append(cleaned)
                seen_excluded_anatomy.add(key)
            machine["excluded_anatomy"] = excluded_anatomy

            entry["machine_rules"] = machine
            entry["_d1_inheritance_status"] = label_overlays[label].get(
                "inheritance_status"
            )
        else:
            entry.pop("machine_rules", None)

        lookup[label] = entry

    return lookup, active_labels


def load_v2_entry_for_label(
    codebook_path: str | Path,
    base_rules_path: str | Path,
    label: str,
) -> dict[str, Any]:
    """Reconstruct one D0/v2 label entry without whole-codebook validation."""
    codebook = _load_yaml(codebook_path)
    base_rules = _load_yaml(base_rules_path)
    codebook_lookup = _index_codebook(codebook)
    mappings = base_rules.get("mappings", {})

    if label not in codebook_lookup:
        raise RuntimeError(f"D0 label absent from codebook: {label}")

    entry = deepcopy(codebook_lookup[label])
    if isinstance(mappings, dict) and label in mappings:
        machine = deepcopy(mappings[label])
        machine["global_policy_overrides"] = deepcopy(
            base_rules.get("global_policy_overrides", {})
        )
        machine["label_policy_overrides"] = {
            **deepcopy(base_rules.get("label_policy_overrides", {}).get(label, {})),
            **deepcopy(machine.get("label_policy_overrides", {})),
        }
        entry["machine_rules"] = machine
    return entry


def load_config(
    codebook_path: str | Path | None = None,
    base_rules_path: str | Path | None = None,
    overlay_path: str | Path | None = None,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Load and index the fail-closed MRHex label lookup."""
    cb = Path(codebook_path) if codebook_path is not None else _DEFAULT_CODEBOOK_PATH
    br = Path(base_rules_path) if base_rules_path is not None else _DEFAULT_BASE_RULES_PATH
    ov = Path(overlay_path) if overlay_path is not None else _DEFAULT_OVERLAY_PATH
    return load_d1_lookup(cb, br, ov)

# Aliases for backward compatibility
load_d2_lookup = load_config
load_lookup = load_config
