# MRHex Validation Dataset

This directory contains the frozen internal validation dataset for **MRHex v1.0.0** clinical report assertion evaluation.

---

## 1. Overview

The validation dataset consists of two aligned CSV files:

| File | Description | Records |
| :--- | :--- | :---: |
| `validation_input.csv` | Input report text and target pathologies for model evaluation | 2,978 |
| `reference_outputs.csv` | Frozen assertion decisions from four independent reference models | 2,978 |

---

## 2. Validation Input (`validation_input.csv`)

`validation_input.csv` represents the held-out internal validation input containing:
- **N = 2,978** clinical report–pathology pairs
- **32** official active MR-RATE target pathologies

### Schema:
- `case_id`: Unique identifier for each clinical report case.
- `report_label_pair_id`: Unique composite identifier for alignment and provenance tracking.
- `target_pathology`: Canonical name of the target MR-RATE pathology evaluated for this case.
- `report`: Full unedited clinical radiology report text (findings and/or impression).

### Inference Protocol:
During inference, MRHex consumes **only**:
1. `report` (the clinical report text)
2. `target_pathology` (the target pathology name)

The `case_id` and `report_label_pair_id` fields are strictly auxiliary identifiers used solely for alignment and reproducibility verification. Reference-model decisions are never accessed or visible during MRHex inference.

---

## 3. Reference Outputs (`reference_outputs.csv`)

`reference_outputs.csv` contains frozen reference outputs from four independent reference language models:
1. **DeepSeek-V4.1-Flash** (`deepseek_v4_1_flash`)
2. **Agnes-AI/Agnes-3.0-Flash** (`agnes_3_0_flash`)
3. **Mercury 2.5** (`mercury_2_5`)
4. **internlm/Atria-Dawn-Preview** (`atria_dawn_preview`)

### Schema:
- `case_id`: Aligned case identifier matching `validation_input.csv`.
- `target_pathology`: Evaluated target pathology.
- `deepseek_v4_1_flash`: Output assertion state from DeepSeek-V4.1-Flash.
- `agnes_3_0_flash`: Output assertion state from Agnes-AI/Agnes-3.0-Flash.
- `mercury_2_5`: Output assertion state from Mercury 2.5.
- `atria_dawn_preview`: Output assertion state from internlm/Atria-Dawn-Preview.

### Output States:
All reference-model decisions use the canonical six-state MR-RATE assertion taxonomy:
- `S`: Supported (definite affirmative current finding)
- `U`: Unsupported (absent / unmentioned finding)
- `C`: Contradicted (explicitly negated / absent finding)
- `UC`: Uncertain (hedged, equivocal, or differential diagnosis)
- `H`: Historical (prior history or resolved condition)
- `NEI`: Not Enough Information (conflicting or ambiguous evidence)

### Reference-Model Agreement Cohorts:
Across the 2,978 validation cases, reference-model agreement is distributed as:
- **Four-model unanimous reference cohort** (4/4 agreement): **2,647 cases** (88.89%)
- **Exact three-of-four reference cohort** (3/4 agreement): **234 cases** (7.86%)
- **Two-two split** (2–2): **43 cases** (1.44%)
- **Two-one-one split** (2–1–1): **50 cases** (1.68%)
- **Four-way disagreement** (1–1–1–1): **4 cases** (0.13%)
- **Total**: **2,978 cases** (100.00%)
