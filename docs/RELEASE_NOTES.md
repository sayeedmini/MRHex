# MRHex v1.0.0 Release Notes

MRHex is a deterministic six-state MRI report assertion classification pipeline.

- **Official MR-RATE target pathologies**: 32
- **Output states**: `S` / `U` / `C` / `UC` / `H` / `NEI`

---

## Development

- **Development corpus**: 8,937 report–pathology pairs used for development
- **Execution**: Fully offline, zero external LLM/API dependencies
- **Canonical development reproducibility**: 8,937 / 8,937 (100.0%)

---

## Validation Status

Validation status: Internal validation completed on 2,978 report–pathology pairs.

### Validation Cohorts:
- **Four-model unanimous reference cohort**: N = 2,647
- **Exact three-of-four reference cohort**: N = 234
- **Full validation dataset**: N = 2,978

MRHex v1.0.0 is frozen and reproducible across all validation cases.
