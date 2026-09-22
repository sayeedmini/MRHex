# MRHex v1.0.0 Internal Validation Protocol

Model: MRHex v1.0.0  
Validation Dataset: Internal validation dataset  
N = 2,978 report–pathology pairs  
Target Pathologies: 32  
Evaluation Scope: Frozen, reproducible internal validation  

---

## 1. Validation Cohorts

The internal validation dataset comprises $N = 2,978$ clinical report–pathology pairs evaluated against four frozen reference language models:
- **DeepSeek-V4.1-Flash**
- **internlm/Atria-Dawn-Preview**
- **Agnes-AI/Agnes-3.0-Flash**
- **Mercury 2.5**

Validation cohorts are partitioned by reference-model agreement level:

1. **Cohort A — Four-Model Unanimous Reference Cohort ($N = 2,647$)**:
   - All 4 reference models agree unanimously on the exact same discrete state.
   - Represents the highest-agreement reference subset.
   - Evaluated using conventional classification metrics.

2. **Cohort B — Exact Three-of-Four Reference Cohort ($N = 234$)**:
   - Exactly 3 of 4 reference models agree on the majority state.
   - The three-model majority state serves as the reference state.
   - Evaluated separately from Cohort A to avoid diluting high-agreement findings.

3. **Cohort C — Full Validation Dataset ($N = 2,978$)**:
   - All cases evaluated regardless of reference agreement level:
     - 4–0: 2,647 cases (88.89%)
     - 3–1: 234 cases (7.86%)
     - 2–2: 43 cases (1.44%)
     - 2–1–1: 50 cases (1.68%)
     - 1–1–1–1: 4 cases (0.13%)
   - Evaluated using distribution-aware continuous metrics: **Semantic Concordance (SC)** and **Consensus-Aware Semantic Concordance (CASC)**.
   - Zero cases are excluded or discarded.

---

## 2. Six Output States

All evaluated models emit exactly one of the six frozen MR-RATE assertion states:
- **S** (Supported): Affirmative current finding present.
- **U** (Unsupported): Target pathology absent / not mentioned.
- **C** (Contradicted): Target pathology explicitly negated or ruled out.
- **UC** (Uncertain): Hedged, differential, or equivocal mention.
- **H** (Historical): Past medical history or prior resolved finding.
- **NEI** (Not Enough Information): Conflicting or unresolvable evidence.

---

## 3. Conventional Classification Metrics

Computed separately for Cohort A and Cohort B:
1. **Exact Six-State Agreement**: $\text{Agreement} = \frac{\sum_i \mathbf{1}(\hat{y}_i = y_i)}{N}$
2. **95% Wilson Score Binomial Confidence Interval** for exact agreement.
3. **Macro F1**: Unweighted arithmetic mean of F1 scores across all six states.
4. **Weighted F1**: Support-weighted mean of F1 scores across all six states.
5. **Per-State Precision, Recall, F1, Support**: For each of the six states.
6. **6×6 Confusion Matrix**: Raw counts and row-normalized proportions.
7. **Unweighted Cohen's $\kappa$**: Standard nominal inter-annotator agreement.
8. **Multiclass MCC**: Gorodkin formulation for multiclass Matthews Correlation Coefficient.
9. **Six-State Macro Recall**: The arithmetic mean of per-state recall across the fixed MR-RATE state ontology S/U/C/UC/H/NEI. States with zero reference support in a cohort contribute recall = 0. This metric is intentionally distinct from standard library implementations of multiclass balanced accuracy that average only over classes represented in the reference labels. (In serialized per-method JSON metrics artifacts, the key `"balanced_accuracy"` is retained strictly as an explicitly documented deprecated compatibility key for `"six_state_macro_recall"`.)

---

## 4. Semantic Concordance (SC) and CASC

Evaluated over all $N = 2,978$ cases of the validation dataset:

### Semantic Concordance (SC)
For each case $i$, reference-state distribution $p_{ic} = \frac{1}{4}\sum_{m=1}^4 \mathbf{1}(y_{im} = c)$.  
Case semantic concordance score:
$$g_i = \sum_{c \in \mathcal{S}} p_{ic} A(\hat{y}_i, c)$$
where $A$ is the frozen $6 \times 6$ semantic affinity matrix (`evaluation/semantic_affinity_matrix.csv`).  
Overall dataset SC:
$$\text{SC} = \frac{1}{N} \sum_{i=1}^N g_i$$

### Consensus-Aware Semantic Concordance (CASC)
Consensus concentration weight for case $i$:
$$q_i = \sum_{c \in \mathcal{S}} p_{ic}^2$$
Values of $q_i$:
- 4–0: $1.000$
- 3–1: $0.625$
- 2–2: $0.500$
- 2–1–1: $0.375$
- 1–1–1–1: $0.250$

Overall dataset CASC:
$$\text{CASC} = \frac{\sum_{i=1}^N q_i g_i}{\sum_{i=1}^N q_i}$$

---

## 5. Sensitivity Analysis

Evaluates SC and CASC robustness across semantic affinity matrix variations:
1. **Primary Matrix**: Primary frozen semantic affinity matrix.
2. **Identity Matrix**: $A(a,b) = \mathbf{1}(a = b)$ (exact agreement-share).
3. **Perturbation (+0.10)**: Off-diagonal values increased by $0.10$ (clamped at $1.0$).
4. **Perturbation (-0.10)**: Off-diagonal values decreased by $0.10$ (clamped at $0.0$).
