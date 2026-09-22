# MRHex v1.0.0 — Clinical Report Assertion Classifier & Validation Benchmark

A clean, fully reproducible distribution for the frozen **MRHex v1.0.0** clinical report assertion classification pipeline and baseline comparison on the sealed held-out validation dataset.

---

## 1. Overview

**MRHex** is a deterministic six-state MRI report assertion classifier. Given:
1. **Medical report text** (brain and spine MRI findings or full impression)
2. **Target pathology** (from the 32 official active MR-RATE target pathologies)

MRHex deterministically produces exactly one of six exhaustive assertion states:
- **S** — Supported (definite current finding present)
- **U** — Unsupported (target absent / unmentioned)
- **C** — Contradicted (target explicitly negated or ruled out)
- **UC** — Uncertain (hedged, differential diagnosis, or equivocal finding)
- **H** — Historical (prior history or resolved condition)
- **NEI** — Not Enough Information (conflicting or unresolvable multi-evidence)

### Validation Benchmark Scope
- **Sealed Held-Out Validation Corpus**: $N = 2,978$ clinical report–pathology pairs across 32 pathologies was strictly isolated and sealed during MRHex rule development.
- **Frozen Reference Ensemble**: Four reference model outputs (`deepseek_v4_1_flash`, `agnes_3_0_flash`, `mercury_2_5`, `atria_dawn_preview`) provide held-out evaluation targets.
- **Zero LLM / External API Calls**: MRHex and all baseline adapters run 100% offline with zero external network calls or cloud dependencies.
- **Comparative Baseline Evaluation**: Evaluates MRHex against three clinical NLP baseline adapters:
  - **NegEx** (Chapman et al., 2001)
  - **pyConTextNLP / ConText** (Chapman et al., 2011)
  - **medspaCy** (Eyre et al., 2021)
  using a shared frozen MR-RATE concept dictionary for fair comparison.

---

## 2. Reproduction Environment

Recommended:
- Python 3.11
- Windows 10/11 or equivalent Python environment

Install:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Then verify environment and baseline runtime readiness:

```bash
python verify_installation.py
```

Expected terminal output:
```text
============================================
MRHex v1.0.0 Production Package
INSTALLATION VERIFICATION PASSED
============================================
```

### Prediction Execution

To run MRHex inference on the validation input (or any CSV containing `report` and `target_pathology`):

```bash
python run_mrhex.py
```

Outputs are written to:
```text
outputs/mrhex_predictions.csv
```

### Reproduce Full Held-Out Validation & Baseline Comparison

To execute the complete evaluation across MRHex and all three baselines live:

```bash
python run_validation.py
```

All evaluation artifacts and comparison tables appear under `outputs/`.

---

## 3. Package Directory Structure

```text
MRHex_v1.0.0_Validation_Package/
│
├── README.md                          # Package documentation
├── VERSION.txt                        # Release version & commit metadata
├── requirements.txt                   # Dependency specification (Python 3.11 recommended)
├── run_mrhex.py                       # MRHex prediction runner
├── run_validation.py                  # Full held-out validation pipeline runner
├── verify_installation.py             # Package installation verification & smoke tests
├── PACKAGE_MANIFEST.json              # File manifest with SHA256 checksums
│
├── mrhex/                             # MRHex deterministic classification package
│   ├── __init__.py                    # Public exports: classify, load_config
│   ├── classifier.py                  # Orchestrator & classification entry point
│   ├── config.py                      # YAML configuration loader & validator
│   ├── engine/                        # Core parsing, assertion, alignment & rules engine
│   └── rules/                         # 30 pathology rule modules + fallback resolver
│
├── configs/                           # Frozen configuration files
│   ├── final_pathology_codebook.yaml
│   ├── final_deterministic_rules_v2.yaml
│   ├── mrhex_label_configuration.yaml
│   └── official_mrrate_32_labels.yaml
│
├── baselines/                         # Frozen baseline NLP implementations
│   ├── negex/                         # Chapman NegEx baseline
│   ├── pycontext/                     # pyConTextNLP baseline & modifier rules
│   ├── medspacy/                      # medspaCy TargetMatcher + ConText pipeline
│   └── mappings/                      # Shared canonical concept dictionary for baselines
│
├── data/
│   └── validation_data/
│       ├── validation_input.csv       # Sealed validation input (N = 2,978 cases)
│       ├── reference_outputs.csv      # Frozen 4-model reference outputs (evaluation only)
│       └── README.md                  # Validation data documentation
│
├── evaluation/
│   ├── semantic_affinity_matrix.csv  # Frozen 6x6 semantic affinity matrix
│   └── baseline_state_mapping.md      # Frozen 6-state baseline mapping policy
│
├── outputs/                           # Generated evaluation results and tables
│   ├── METHOD_COMPARISON.csv          # Comprehensive metric comparison table
│   ├── SUPERVISOR_COMPARISON.csv      # Formatted summary comparison table
│   ├── SC_CASC_COMPARISON.csv         # Semantic Concordance & CASC results
│   ├── SC_CASC_SENSITIVITY.csv        # Matrix perturbation sensitivity analysis
│   ├── mrhex/                         # MRHex predictions, JSONs, and confusion matrices
│   ├── negex/                         # NegEx predictions, JSONs, and confusion matrices
│   ├── context/                       # ConText predictions, JSONs, and confusion matrices
│   └── medspacy/                      # medspaCy predictions, JSONs, and confusion matrices
│
└── docs/
    ├── FREEZE_RECORD.md               # Historical freeze record & commit metadata
    ├── RELEASE_NOTES.md               # Production release notes
    └── VALIDATION_PROTOCOL.md         # Detailed held-out validation protocol
```

---

## 4. Architectural Notes

### 31-vs-32 Label Architecture

MRHex supports 32 official MR-RATE target pathologies.

The core rule configuration contains 31 active labels.

The remaining target:
`Metastatic malignant neoplasm to brain`

is handled by the deterministic fallback rule layer.

Therefore the complete MRHex system supports all 32 target pathologies.

### Two-Layer Deterministic Architecture

MRHex operates strictly as a two-layer deterministic architecture:
1. **Core rule layer**: High-confidence deterministic rules (`CORE_RULE`).
2. **Deterministic fallback rule layer**: Resolves routed cases into exact assertion states (`FALLBACK_RULE`).

All 32 official target pathologies are fully supported without any external LLM or API dependencies.

---

## 5. Evaluation Cohorts & Metrics

The validation set comprises $N = 2,978$ clinical report–pathology pairs across 32 official MR-RATE pathologies:

1. **Cohort A — Four-Model Unanimous Agreement ($N = 2,647$, 88.89%)**:
   - All 4 reference models agree on the identical assertion state.
   - Evaluated using conventional classification metrics (Exact Agreement, 95% Wilson CI, Macro F1, Weighted F1, Six-State Macro Recall, Cohen's $\kappa$, Multiclass MCC, Per-State F1).

2. **Cohort B — Exact Three-of-Four Agreement ($N = 234$, 7.86%)**:
   - Exactly 3 of 4 reference models agree on the majority state.
   - Evaluated separately to assess robustness under moderate reference ambiguity.

3. **Cohort C — Full Ensemble Distribution ($N = 2,978$, 100.0%)**:
   - Evaluates all cases, including tied distributions (43 2–2 ties, 50 2–1–1 splits, 4 1–1–1–1 splits).
   - Evaluated via continuous, distribution-aware metrics:
     - **Semantic Concordance (SC)**
     - **Consensus-Aware Semantic Concordance (CASC)**

> **Metric Definition — Six-State Macro Recall**: Six-State Macro Recall is the arithmetic mean of per-state recall across the fixed MR-RATE state ontology S/U/C/UC/H/NEI. States with zero reference support in a cohort contribute recall = 0. This metric is intentionally distinct from standard library implementations of multiclass balanced accuracy that average only over classes represented in the reference labels. In per-method JSON metrics artifacts, the key `"balanced_accuracy"` is retained strictly as an explicitly documented deprecated compatibility key for `"six_state_macro_recall"`.

---

## 6. Reproduction Targets

Running `run_validation.py` reproduces these frozen validation results:

### Cohort A (Four-Model Unanimous, $N = 2,647$)

| Method | Exact Agreement | 95% Wilson CI | Macro F1 | Weighted F1 | Six-State Macro Recall | Cohen's $\kappa$ | MCC |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **MRHex v1.0.0** | **92.671%** (2453/2647) | [0.91615, 0.93603] | **0.45225** | **0.94094** | **0.53987** | **0.65052** | **0.67398** |
| NegEx | 80.808% | [0.79264, 0.82264] | 0.19281 | 0.82441 | 0.30987 | 0.17747 | 0.19534 |
| ConText | 80.582% | [0.79031, 0.82044] | 0.23142 | 0.83262 | 0.34899 | 0.21326 | 0.23776 |
| medspaCy | 79.940% | [0.78371, 0.81421] | 0.21029 | 0.82759 | 0.31814 | 0.20132 | 0.22633 |

### Cohort B (Exact Three-of-Four, $N = 234$)

| Method | Exact Agreement | 95% Wilson CI | Macro F1 | Weighted F1 | Six-State Macro Recall | Cohen's $\kappa$ | MCC |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **MRHex v1.0.0** | **68.376%** (160/234) | [0.62162, 0.73996] | **0.34068** | **0.68025** | **0.37879** | **0.50201** | **0.53485** |
| NegEx | 53.846% | [0.47448, 0.60120] | 0.19690 | 0.49134 | 0.25887 | 0.24613 | 0.28200 |
| ConText | 57.692% | [0.51288, 0.63848] | 0.27978 | 0.57764 | 0.30937 | 0.34350 | 0.39319 |
| medspaCy | 55.128% | [0.48724, 0.61367] | 0.23636 | 0.53064 | 0.27902 | 0.28615 | 0.32711 |

### Full Ensemble ($N = 2,978$ cases)

| Method | SC (Semantic Concordance) | CASC (Consensus-Aware SC) |
| :--- | :---: | :---: |
| **MRHex v1.0.0** | **0.90139** | **0.91674** |
| NegEx | 0.80523 | 0.81858 |
| ConText | 0.80257 | 0.81554 |
| medspaCy | 0.79490 | 0.80786 |

---

## 7. Technical Invariants & Verification Guarantees

- **Behavior-Preserving Reproduction of Frozen MRHex v1.0.0**: The reorganized distribution reproduces the frozen MRHex v1.0.0 inference behavior exactly across all 2,978 validation cases, matching predictions from git commit `e73fdb457b221db6cb9e8baf5fe7b8181907ff8a`.
- **Sealed Validation Isolation**: The validation set was strictly held out and uninspected during rule construction.
- **Fail-Closed State Coverage**: Guarantees 100% deterministic state coverage across all six states with zero unhandled cases.
- **Self-Contained & Isolated**: The package contains no absolute path dependencies and can be relocated to any machine.
