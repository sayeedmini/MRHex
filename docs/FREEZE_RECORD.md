# MRHex v1.0.0 Freeze Record

- **Model**: MRHex
- **Version**: v1.0.0
- **Status**: Frozen
- **Freeze Date**: 2026-09-22
- **Pre-freeze preparation commit**: `84f19c5ab82119d25bdbf845da33131be9fe2103`
- **Freeze commit**: `e73fdb457b221db6cb9e8baf5fe7b8181907ff8a`

---

## Artifact & Corpus Specifications

- **Development Corpus**: 8,937 report–pathology pairs
- **Official Pathologies**: 32
- **Output States**: `S` / `U` / `C` / `UC` / `H` / `NEI`
- **Validation dataset status at freeze**:
  Sealed and not accessed during model development.

---

## Verified Performance & Invariants

- **Verified Reference-Ensemble Agreement**:
  * 4/4 Unanimous: 7,534 / 7,905 = 95.307%
  * Exact-3/4: 491 / 702 = 69.943%
- **Canonical Parity**: 8,937 / 8,937 (0 state diffs, 0 source diffs, 0 rule diffs, 0 reason diffs)
- **CORE_RULE** (formerly `D2_SAFE`):
  * 6,655 cases
  * 0 state drift
  * 0 provenance drift
- **Regression Tests**: 251 passed, 0 failed, 0 skipped
- **Runtime**: Fully offline, zero external network or socket dependencies
- **External LLM/API Calls**: 0

---

## Post-Freeze Nomenclature Normalization

> Post-freeze nomenclature normalization changed only internal/public identifiers and provenance labels. Classification logic, rule behavior, predictions, reason codes, and model states were unchanged. Exact prediction parity was verified against the frozen MRHex v1.0.0 implementation.

---

## Immutability Guarantee

```text
MRHex v1.0.0 is the immutable version designated for all subsequent validation, baseline comparison, and supervisor testing. Any future modification requires a new version number.
```
