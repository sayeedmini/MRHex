# MR-RATE Baseline State Mapping Policy — Held-Out Validation

## 1. Governance & Immutability Guarantee

This document defines the deterministic mapping adapters for all baseline clinical NLP systems evaluated on the held-out validation corpus:
1. **NegEx** (Chapman et al., 2001)
2. **ConText / pyConTextNLP** (Harkema et al., 2009; Chapman et al., 2011)
3. **medspaCy** (Eyre et al., 2021)

### Non-Negotiable Protocol Rules
- **Pre-Execution Freeze**: This mapping was defined, documented, and frozen **prior to** inspecting baseline predictions or performance metrics on the held-out validation set.
- **Fairness & Uniformity**: The mapping is identical across all validation cases and cohorts.
- **Zero Tuning**: No mapping rules are adjusted or tuned based on validation outcomes.
- **No Retrofitting**: The baselines are evaluated as standard clinical NLP systems with their genuine architectural capabilities and limitations; they are not artificially retrofitted with MRHex-specific overrides or clinical rescues.

---

## 2. MR-RATE Six-State Universe

The target classification space $\mathcal{C}$ for MR-RATE consists of six discrete states:
- `S`: **Supported** — Definite current presence of the target pathology or accepted lexical variant in the target anatomical compartment.
- `U`: **Unsupported** — Target pathology is not mentioned anywhere in the report, or the relevant anatomy is described as completely normal.
- `C`: **Contradicted** — Target pathology is explicitly negated or ruled out.
- `UC`: **Uncertain** — Target pathology is described with equivocal hedging, differential suspicion, or indeterminacy (e.g., "cannot rule out", "possible", "favored", "suggestive of").
- `H`: **Historical** — Target pathology is noted exclusively as past medical history, resolved, or status-post resection without active acute presence.
- `NEI`: **Not Enough Information** — Irreconcilable contradictory statements or unparseable text preventing a deterministic conclusion.

---

## 3. Baseline Native Cues and MR-RATE Mappings

### 3.1 NegEx Baseline Adapter
NegEx is an algorithmic sentence-level negation detector. By design, classic NegEx evaluates concept mentions for pre- and post-negation triggers within a directional token window (up to 6 tokens within sentence boundaries), suppressing pseudo-negations and terminating at conjunctions. It natively distinguishes between affirmed concepts, negated concepts, and absent concepts, but lacks uncertainty and temporality components.

| NegEx Native Cue / Document Aggregation | MR-RATE State | Precedence | Clinical Rationale & Documented Limitations |
| :--- | :---: | :---: | :--- |
| `affirmed_mention_found` | `S` | 1 | Any sentence contains an affirmed mention of the target pathology concept. |
| `all_mentions_negated` | `C` | 2 | All detected mentions of the target pathology concept fall within a negation trigger window. |
| `target_not_found` / `empty_report` | `U` | 3 | No mention of the target pathology is identified in the report text. |

*Documented Architectural Limitations*:
- NegEx cannot natively emit `UC` (uncertainty), `H` (historical), or `NEI` (conflicting/unresolvable).
- If an uncertain phrase (e.g. "possible glioma") appears, NegEx will treat the concept mention as affirmed (`S`) unless explicitly negated.

---

### 3.2 pyConTextNLP Baseline Adapter
pyConTextNLP constructs a modifier-concept markup dependency graph (`pyConTextNLP==0.7.0.1`), applying linguistic modifier rules for negation (`definite_negated_existence`), uncertainty (`probable_possible`), and temporality (`historical`).

| pyConTextNLP Assertion | MR-RATE State | Precedence Rank | Codebook Policy Reference |
| :--- | :---: | :---: | :--- |
| `AFFIRMED_CURRENT` | `S` | 1 (Highest) | Definite current target pathology or variant present in report text. |
| `UNCERTAIN` | `UC` | 2 | Target mentioned with uncertainty, hedging, or differential suspicion. |
| `HISTORICAL` | `H` | 3 | Target mentioned as past medical history or resolved without current active presence. |
| `NEGATED` | `C` | 4 | Target explicitly negated / ruled out across all mentions. |
| `TARGET_NOT_FOUND` | `U` | 5 | Target concept not found anywhere in report text. |
| `UNRESOLVABLE` | `NEI` | 6 (Lowest) | Irreconcilably conflicting assertions. |

*Document-Level Precedence Hierarchy*:
1. If $\ge 1$ mention is `AFFIRMED_CURRENT` $\rightarrow$ **`S`**
2. Else if $\ge 1$ mention is `UNCERTAIN` $\rightarrow$ **`UC`**
3. Else if $\ge 1$ mention is `HISTORICAL` $\rightarrow$ **`H`**
4. Else if all mentions are `NEGATED` $\rightarrow$ **`C`**
5. Else (target not found) $\rightarrow$ **`U`**

*Documented Architectural Limitations*:
- pyConTextNLP emits `NEI` only if contradictory assertions cannot be prioritized. Under deterministic precedence, almost all multi-mention cases resolve to `S > UC > H > C > U`.

---

### 3.3 medspaCy Baseline Adapter
medspaCy (`medspacy==1.3.1`, `spacy==3.7.5`) utilizes a clinical NLP pipeline incorporating `TargetMatcher` rules for canonical concepts and variants, coupled with `ConText` rules for contextual modifier detection (`is_negated`, `is_uncertain`, `is_historical`).

| medspaCy Mention Modifier Profile | Baseline Assertion | MR-RATE State | Precedence Rank |
| :--- | :--- | :---: | :---: |
| Not negated, Not uncertain, Not historical | `AFFIRMED_CURRENT` | `S` | 1 |
| Not negated, Uncertain (`is_uncertain=True`) | `UNCERTAIN` | `UC` | 2 |
| Not negated, Historical (`is_historical=True`) | `HISTORICAL` | `H` | 3 |
| Negated (`is_negated=True`) | `NEGATED` | `C` | 4 |
| Target not matched in document | `TARGET_NOT_FOUND` | `U` | 5 |
| Unresolved conflicting evidence | `UNRESOLVABLE` | `NEI` | 6 |

*Document-Level Precedence Hierarchy*:
Follows the identical hierarchy as pyConTextNLP (`S > UC > H > C > U > NEI`).

---

## 4. Method-Agnostic Output Invariant

For every evaluable report-pathology pair $(i)$ in the validation cohort, each baseline emits exactly **one** discrete prediction $\hat{y}_i \in \{S, U, C, UC, H, NEI\}$.
Neither confidence scores nor internal probabilities from baselines are utilized for scoring, ensuring complete parity with MRHex v1.0.0.
