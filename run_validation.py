"""End-to-End Held-Out Validation and Baseline Comparison Pipeline.

Executes:
1. MRHex v1.0.0 (production release)
2. NegEx baseline
3. ConText / pyConTextNLP baseline
4. medspaCy baseline

Strict protocol:
- Predictions are generated using ONLY validation_input.csv.
- Reference outputs are NEVER accessed during prediction.
- Loads reference_outputs.csv only AFTER all predictions are serialized.
- Constructs validation cohorts, computes all locked metrics,
  and generates authoritative supervisor comparison tables.
"""
from collections import Counter
import csv
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Tuple

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

# MRHex imports
from mrhex import classify, load_config
from mrhex.classifier import SYSTEM_ID, VALID_STATES, VERSION

STATES = ["S", "U", "C", "UC", "H", "NEI"]
STATE_TO_IDX = {s: i for i, s in enumerate(STATES)}
REFERENCE_MODELS = [
    "deepseek_v4_1_flash",
    "agnes_3_0_flash",
    "mercury_2_5",
    "atria_dawn_preview",
]


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate exact two-sided Wilson score binomial confidence interval."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963984540054  # 95% confidence normal quantile
    p = k / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2.0 * n)) / denom
    margin = (z * math.sqrt((p * (1.0 - p)) / n + (z**2) / (4.0 * (n**2)))) / denom
    ci_low = max(0.0, center - margin)
    ci_high = min(1.0, center + margin)
    return round(ci_low, 5), round(ci_high, 5)


def compute_conventional_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
    """Compute 11 locked conventional metrics on hard-labeled reference subset."""
    n = len(y_true)
    assert n == len(y_pred), "y_true and y_pred length mismatch"
    if n == 0:
        return {}

    cm = np.zeros((6, 6), dtype=np.int64)
    for yt, yp in zip(y_true, y_pred):
        cm[STATE_TO_IDX[yt], STATE_TO_IDX[yp]] += 1

    exact_matches = int(np.trace(cm))
    exact_agreement = exact_matches / n
    ci_low, ci_high = wilson_score_interval(exact_matches, n, 0.95)

    per_state = {}
    f1_list = []
    recall_list = []
    support_list = []

    for idx, s in enumerate(STATES):
        tp = int(cm[idx, idx])
        fp = int(cm[:, idx].sum() - tp)
        fn = int(cm[idx, :].sum() - tp)
        support = int(cm[idx, :].sum())

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_state[s] = {
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(prec, 5),
            "recall": round(rec, 5),
            "f1": round(f1, 5),
        }
        f1_list.append(f1)
        recall_list.append(rec)
        support_list.append(support)

    macro_f1 = float(np.mean(f1_list))
    weighted_f1 = (
        sum(f1 * sup for f1, sup in zip(f1_list, support_list)) / n if n > 0 else 0.0
    )
    six_state_macro_recall = float(np.mean(recall_list))

    po = exact_matches / n
    row_sums = cm.sum(axis=1)
    col_sums = cm.sum(axis=0)
    pe = float(np.sum(row_sums * col_sums)) / (n * n)
    kappa = (po - pe) / (1.0 - pe) if (1.0 - pe) != 0 else 0.0

    c = exact_matches
    s = n
    p = col_sums
    t = row_sums
    num = c * s - float(np.dot(p, t))
    denom = math.sqrt(max(0.0, s * s - float(np.dot(p, p)))) * math.sqrt(
        max(0.0, s * s - float(np.dot(t, t)))
    )
    mcc = num / denom if denom > 0 else 0.0

    return {
        "n": n,
        "exact_matches": exact_matches,
        "exact_agreement": round(exact_agreement, 5),
        "exact_agreement_ci_low": ci_low,
        "exact_agreement_ci_high": ci_high,
        "macro_f1": round(macro_f1, 5),
        "weighted_f1": round(weighted_f1, 5),
        "six_state_macro_recall": round(six_state_macro_recall, 5),
        "balanced_accuracy": round(six_state_macro_recall, 5),  # Deprecated compatibility alias
        "kappa": round(kappa, 5),
        "mcc": round(mcc, 5),
        "per_state": per_state,
        "confusion_matrix_counts": cm.tolist(),
        "confusion_matrix_normalized": [
            [
                round(float(cm[r, c]) / row_sums[r], 5) if row_sums[r] > 0 else 0.0
                for c in range(6)
            ]
            for r in range(6)
        ],
    }


def compute_sc_casc(
    cases_data: List[Dict[str, Any]],
    predictions: List[str],
    affinity_matrix: Dict[str, Dict[str, float]],
) -> Tuple[float, float, List[Dict[str, Any]]]:
    """Calculate case-level g_i, overall SC, and CASC."""
    n = len(cases_data)
    assert n == len(predictions)

    sum_qi_gi = 0.0
    sum_qi = 0.0
    sum_gi = 0.0
    case_scores = []

    for c_data, pred in zip(cases_data, predictions):
        p_dist = c_data["p_dist"]
        qi = c_data["q_consensus_concentration"]

        gi = sum(p_dist[st] * affinity_matrix[pred][st] for st in STATES)

        sum_gi += gi
        sum_qi_gi += qi * gi
        sum_qi += qi

        rec = {
            "case_id": c_data["case_id"],
            "target_pathology": c_data["target_pathology"],
            "method_prediction": pred,
            "vote_S": c_data["reference_counts"]["S"],
            "vote_U": c_data["reference_counts"]["U"],
            "vote_C": c_data["reference_counts"]["C"],
            "vote_UC": c_data["reference_counts"]["UC"],
            "vote_H": c_data["reference_counts"]["H"],
            "vote_NEI": c_data["reference_counts"]["NEI"],
            "p_S": round(p_dist["S"], 4),
            "p_U": round(p_dist["U"], 4),
            "p_C": round(p_dist["C"], 4),
            "p_UC": round(p_dist["UC"], 4),
            "p_H": round(p_dist["H"], 4),
            "p_NEI": round(p_dist["NEI"], 4),
            "vote_pattern": c_data["agreement_pattern"],
            "q_consensus_concentration": round(qi, 4),
            "g_semantic_concordance": round(gi, 5),
            "weighted_contribution": round(qi * gi, 5),
        }
        case_scores.append(rec)

    sc = sum_gi / n if n > 0 else 0.0
    casc = sum_qi_gi / sum_qi if sum_qi > 0 else 0.0

    return round(sc, 5), round(casc, 5), case_scores


def load_affinity_matrix(csv_path: Path) -> Dict[str, Dict[str, float]]:
    matrix: Dict[str, Dict[str, float]] = {s: {} for s in STATES}
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_from = row["state"]
            for s_to in STATES:
                matrix[s_from][s_to] = float(row[s_to])
    return matrix


def run_validation():
    print("=================================================================", flush=True)
    print("   MRHex v1.0.0 & Baselines Validation Pipeline                  ", flush=True)
    print("=================================================================", flush=True)
    t_start = time.time()

    # Paths
    validation_input_path = PACKAGE_ROOT / "data" / "validation_data" / "validation_input.csv"
    ref_outputs_path = PACKAGE_ROOT / "data" / "validation_data" / "reference_outputs.csv"
    codebook_path = PACKAGE_ROOT / "configs" / "final_pathology_codebook.yaml"
    base_rules_path = PACKAGE_ROOT / "configs" / "final_deterministic_rules_v2.yaml"
    label_cfg_path = PACKAGE_ROOT / "configs" / "mrhex_label_configuration.yaml"
    affinity_path = PACKAGE_ROOT / "evaluation" / "semantic_affinity_matrix.csv"
    if not affinity_path.exists():
        raise FileNotFoundError(f"Missing semantic affinity matrix: {affinity_path}")
    outputs_dir = PACKAGE_ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    aff_matrix = load_affinity_matrix(affinity_path)

    # -------------------------------------------------------------
    # STEP 1: Load validation corpus ONLY (blind to reference outputs)
    # -------------------------------------------------------------
    print(f"\n[Step 1/10] Loading validation corpus (blind to reference outputs)...", flush=True)
    with validation_input_path.open("r", encoding="utf-8") as f:
        corpus = list(csv.DictReader(f))
    total_cases = len(corpus)
    print(f"            Loaded {total_cases} report-pathology cases.", flush=True)

    # -------------------------------------------------------------
    # STEP 2: Execute MRHex v1.0.0
    # -------------------------------------------------------------
    print(f"\n[Step 2/10] Running MRHex v1.0.0 on {total_cases} cases...", flush=True)
    lookup, _ = load_config(codebook_path, base_rules_path, label_cfg_path)
    t0 = time.time()
    mrhex_preds = []
    mrhex_details = []
    for c in corpus:
        st_out = classify(
            c["report"],
            lookup[c["target_pathology"]],
            case_id=c.get("case_id", ""),
            source_mode="full_report",
        )
        st_state = st_out["state"]
        assert st_state in VALID_STATES
        mrhex_preds.append(st_state)
        mrhex_details.append(st_out)
    print(f"            MRHex completed in {time.time() - t0:.2f}s.", flush=True)

    # -------------------------------------------------------------
    # STEP 3: Execute NegEx baseline (live execution mandatory)
    # -------------------------------------------------------------
    print(f"\n[Step 3/10] Running NegEx on {total_cases} cases...", flush=True)
    try:
        from baselines.negex.negex_baseline import NegExBaseline
    except ImportError as e:
        print(
            f"\nERROR: NegEx dependencies missing ({e}).\n"
            "Install dependencies using:\n\n"
            "pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)

    negex_model = NegExBaseline()
    t0 = time.time()
    negex_preds = []
    negex_details = []
    for c in corpus:
        res = negex_model.process_report(
            c["report"], c["target_pathology"], c.get("case_id", "")
        )
        negex_preds.append(res["decision"])
        negex_details.append(res)
    print(f"            NegEx completed in {time.time() - t0:.2f}s.", flush=True)

    # -------------------------------------------------------------
    # STEP 4: Execute ConText / pyConTextNLP baseline (live execution mandatory)
    # -------------------------------------------------------------
    print(f"\n[Step 4/10] Running ConText / pyConTextNLP on {total_cases} cases...", flush=True)
    try:
        from baselines.pycontext.pycontext_baseline import PyConTextBaseline
    except ImportError as e:
        print(
            f"\nERROR: pyConTextNLP is not installed ({e}).\n"
            "Install dependencies using:\n\n"
            "pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)

    pycontext_model = PyConTextBaseline()
    t0 = time.time()
    context_preds = []
    context_details = []
    for c in corpus:
        res = pycontext_model.process_report(
            c["report"], c["target_pathology"], c.get("case_id", "")
        )
        context_preds.append(res["decision"])
        context_details.append(res)
    print(f"            ConText completed in {time.time() - t0:.2f}s.", flush=True)

    # -------------------------------------------------------------
    # STEP 5: Execute medspaCy baseline (live execution mandatory)
    # -------------------------------------------------------------
    print(f"\n[Step 5/10] Running medspaCy on {total_cases} cases...", flush=True)
    try:
        from baselines.medspacy.medspacy_baseline import MedspaCyBaseline
    except ImportError as e:
        print(
            f"\nERROR: medspaCy is not installed ({e}).\n"
            "Install dependencies using:\n\n"
            "pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)

    medspacy_model = MedspaCyBaseline()
    t0 = time.time()
    medspacy_preds = []
    medspacy_details = []
    for idx, c in enumerate(corpus):
        if (idx + 1) % 500 == 0 or idx == total_cases - 1:
            print(f"            medspaCy progress: {idx + 1}/{total_cases} cases ({time.time() - t0:.1f}s)...", flush=True)
        res = medspacy_model.process_report(
            c["report"], c["target_pathology"], c.get("case_id", "")
        )
        medspacy_preds.append(res["decision"])
        medspacy_details.append(res)
    print(f"            medspaCy completed in {time.time() - t0:.2f}s.", flush=True)

    # -------------------------------------------------------------
    # STEP 6: Save all predictions files
    # -------------------------------------------------------------
    print(f"\n[Step 6/10] Saving prediction files for all four systems...", flush=True)
    all_methods = [
        ("mrhex", "MRHex v1.0.0", mrhex_preds, mrhex_details),
        ("negex", "NegEx", negex_preds, negex_details),
        ("context", "ConText / pyConTextNLP", context_preds, context_details),
        ("medspacy", "medspaCy", medspacy_preds, medspacy_details),
    ]

    for method_key, method_name, preds, details in all_methods:
        method_dir = outputs_dir / method_key
        method_dir.mkdir(parents=True, exist_ok=True)
        pred_csv = method_dir / "predictions.csv"
        with pred_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "case_id",
                "target_pathology",
                "report_label_pair_id",
                "method",
                "method_prediction",
                "raw_reason",
            ])
            for c, pred, det in zip(corpus, preds, details):
                reason = det.get("reason_code") or det.get("reason") or det.get("fallback_rule_id") or ""
                if isinstance(reason, list):
                    reason = ";".join(str(x) for x in reason)
                writer.writerow([
                    c.get("case_id", ""),
                    c["target_pathology"],
                    c.get("report_label_pair_id", ""),
                    method_key,
                    pred,
                    reason,
                ])
    print("            Predictions saved for all methods.", flush=True)

    # -------------------------------------------------------------
    # STEP 7: Only AFTER predictions are complete: load reference_outputs.csv
    # -------------------------------------------------------------
    print(f"\n[Step 7/10] Loading reference outputs from {ref_outputs_path}...", flush=True)
    with ref_outputs_path.open("r", encoding="utf-8") as f:
        ref_rows = list(csv.DictReader(f))
    assert len(ref_rows) == total_cases, "Reference rows count does not match corpus cases count"

    # Map (case_id, target_pathology) -> reference outputs
    ref_lookup = {}
    for r in ref_rows:
        ref_lookup[(r["case_id"], r["target_pathology"])] = [
            r[model_name] for model_name in REFERENCE_MODELS
        ]

    # -------------------------------------------------------------
    # STEP 8: Construct validation cohorts
    # -------------------------------------------------------------
    print(f"\n[Step 8/10] Constructing validation cohorts...", flush=True)
    cases_metadata = []
    cohort_a_indices = []
    cohort_b_indices = []
    pattern_counts = Counter()

    for idx, c in enumerate(corpus):
        cid = c.get("case_id", "")
        tgt = c["target_pathology"]
        ref_decisions = ref_lookup[(cid, tgt)]

        r_counts = Counter(ref_decisions)
        p_dist = {s: r_counts.get(s, 0) / 4.0 for s in STATES}
        qi = sum(p**2 for p in p_dist.values())

        top_ref_count = max(r_counts.values())
        if top_ref_count == 4:
            pattern = "4-0"
            cohort_a_indices.append(idx)
            hard_ref = ref_decisions[0]
        elif top_ref_count == 3:
            pattern = "3-1"
            cohort_b_indices.append(idx)
            hard_ref = r_counts.most_common(1)[0][0]
        elif top_ref_count == 2:
            if len(r_counts) == 2:
                pattern = "2-2"
            else:
                pattern = "2-1-1"
            hard_ref = None
        else:
            pattern = "1-1-1-1"
            hard_ref = None

        pattern_counts[pattern] += 1
        cases_metadata.append({
            "case_id": cid,
            "target_pathology": tgt,
            "report_label_pair_id": c.get("report_label_pair_id", ""),
            "reference_decisions": ref_decisions,
            "reference_counts": {s: r_counts.get(s, 0) for s in STATES},
            "p_dist": p_dist,
            "q_consensus_concentration": qi,
            "agreement_pattern": pattern,
            "hard_ref": hard_ref,
        })

    print(f"            Cohort A (4/4 Unanimous): {len(cohort_a_indices)} cases ({len(cohort_a_indices)/total_cases*100:.2f}%)", flush=True)
    print(f"            Cohort B (Exact 3/4):      {len(cohort_b_indices)} cases ({len(cohort_b_indices)/total_cases*100:.2f}%)", flush=True)
    print(f"            Tied / Non-Majority:     {total_cases - len(cohort_a_indices) - len(cohort_b_indices)} cases", flush=True)
    print(f"              - 2-2: {pattern_counts['2-2']}", flush=True)
    print(f"              - 2-1-1: {pattern_counts['2-1-1']}", flush=True)
    print(f"              - 1-1-1-1: {pattern_counts['1-1-1-1']}", flush=True)
    print(f"            Cohort C (All cases):     {total_cases} cases (100.0%)", flush=True)

    # -------------------------------------------------------------
    # STEP 9: Compute metrics and save method artifacts
    # -------------------------------------------------------------
    print(f"\n[Step 9/10] Calculating metrics and serializing method results...", flush=True)
    method_comparison_rows = []
    supervisor_comparison_rows = []
    sc_casc_comparison_rows = []

    for method_key, method_name, preds, details in all_methods:
        method_dir = outputs_dir / method_key

        # Cohort A (4/4)
        y_true_a = [cases_metadata[i]["hard_ref"] for i in cohort_a_indices]
        y_pred_a = [preds[i] for i in cohort_a_indices]
        metrics_a = compute_conventional_metrics(y_true_a, y_pred_a)

        with (method_dir / "metrics_4of4.json").open("w", encoding="utf-8") as f:
            json.dump(metrics_a, f, indent=2)

        with (method_dir / "per_state_metrics_4of4.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["State", "Support", "Precision", "Recall", "F1", "TP", "FP", "FN"])
            for s in STATES:
                row_m = metrics_a["per_state"][s]
                writer.writerow([
                    s,
                    row_m["support"],
                    f"{row_m['precision']:.4f}",
                    f"{row_m['recall']:.4f}",
                    f"{row_m['f1']:.4f}",
                    row_m["tp"],
                    row_m["fp"],
                    row_m["fn"],
                ])

        with (method_dir / "confusion_matrix_4of4_counts.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["reference_state"] + STATES)
            for s_ref, row_vals in zip(STATES, metrics_a["confusion_matrix_counts"]):
                writer.writerow([s_ref] + row_vals)

        with (method_dir / "confusion_matrix_4of4_normalized.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["reference_state"] + STATES)
            for s_ref, row_vals in zip(STATES, metrics_a["confusion_matrix_normalized"]):
                writer.writerow([s_ref] + [f"{v:.4f}" for v in row_vals])

        # Cohort B (exact 3/4)
        y_true_b = [cases_metadata[i]["hard_ref"] for i in cohort_b_indices]
        y_pred_b = [preds[i] for i in cohort_b_indices]
        metrics_b = compute_conventional_metrics(y_true_b, y_pred_b)

        with (method_dir / "metrics_exact3of4.json").open("w", encoding="utf-8") as f:
            json.dump(metrics_b, f, indent=2)

        with (method_dir / "per_state_metrics_exact3of4.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["State", "Support", "Precision", "Recall", "F1", "TP", "FP", "FN"])
            for s in STATES:
                row_m = metrics_b["per_state"][s]
                writer.writerow([
                    s,
                    row_m["support"],
                    f"{row_m['precision']:.4f}",
                    f"{row_m['recall']:.4f}",
                    f"{row_m['f1']:.4f}",
                    row_m["tp"],
                    row_m["fp"],
                    row_m["fn"],
                ])

        with (method_dir / "confusion_matrix_exact3of4_counts.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["reference_state"] + STATES)
            for s_ref, row_vals in zip(STATES, metrics_b["confusion_matrix_counts"]):
                writer.writerow([s_ref] + row_vals)

        with (method_dir / "confusion_matrix_exact3of4_normalized.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["reference_state"] + STATES)
            for s_ref, row_vals in zip(STATES, metrics_b["confusion_matrix_normalized"]):
                writer.writerow([s_ref] + [f"{v:.4f}" for v in row_vals])

        # Cohort C (SC and CASC)
        sc_val, casc_val, case_scores = compute_sc_casc(cases_metadata, preds, aff_matrix)

        with (method_dir / "sc_casc_all_cases.json").open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "method": method_key,
                    "all_cases_n": total_cases,
                    "semantic_concordance_SC": sc_val,
                    "CASC": casc_val,
                    "q_consensus_sum": sum(
                        c["q_consensus_concentration"] for c in cases_metadata
                    ),
                },
                f,
                indent=2,
            )

        with (method_dir / "sc_casc_case_scores.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "case_id",
                    "target_pathology",
                    "method_prediction",
                    "vote_S",
                    "vote_U",
                    "vote_C",
                    "vote_UC",
                    "vote_H",
                    "vote_NEI",
                    "p_S",
                    "p_U",
                    "p_C",
                    "p_UC",
                    "p_H",
                    "p_NEI",
                    "vote_pattern",
                    "q_consensus_concentration",
                    "g_semantic_concordance",
                    "weighted_contribution",
                ],
            )
            writer.writeheader()
            writer.writerows(case_scores)

        # Record for comparison tables
        method_comparison_rows.append({
            "method": method_name,
            "4of4_n": metrics_a["n"],
            "4of4_exact_agreement": f"{metrics_a['exact_agreement']:.5f}",
            "4of4_exact_agreement_ci_low": f"{metrics_a['exact_agreement_ci_low']:.5f}",
            "4of4_exact_agreement_ci_high": f"{metrics_a['exact_agreement_ci_high']:.5f}",
            "4of4_macro_f1": f"{metrics_a['macro_f1']:.5f}",
            "4of4_weighted_f1": f"{metrics_a['weighted_f1']:.5f}",
            "4of4_six_state_macro_recall": f"{metrics_a['six_state_macro_recall']:.5f}",
            "4of4_kappa": f"{metrics_a['kappa']:.5f}",
            "4of4_mcc": f"{metrics_a['mcc']:.5f}",
            "exact3of4_n": metrics_b["n"],
            "exact3of4_exact_agreement": f"{metrics_b['exact_agreement']:.5f}",
            "exact3of4_exact_agreement_ci_low": f"{metrics_b['exact_agreement_ci_low']:.5f}",
            "exact3of4_exact_agreement_ci_high": f"{metrics_b['exact_agreement_ci_high']:.5f}",
            "exact3of4_macro_f1": f"{metrics_b['macro_f1']:.5f}",
            "exact3of4_weighted_f1": f"{metrics_b['weighted_f1']:.5f}",
            "exact3of4_six_state_macro_recall": f"{metrics_b['six_state_macro_recall']:.5f}",
            "exact3of4_kappa": f"{metrics_b['kappa']:.5f}",
            "exact3of4_mcc": f"{metrics_b['mcc']:.5f}",
            "all_cases_n": total_cases,
            "semantic_concordance_SC": f"{sc_val:.5f}",
            "CASC": f"{casc_val:.5f}",
        })

        supervisor_comparison_rows.append({
            "Method": method_name,
            "4/4 Exact Agreement": f"{metrics_a['exact_agreement']:.5f}",
            "4/4 Macro F1": f"{metrics_a['macro_f1']:.5f}",
            "4/4 Weighted F1": f"{metrics_a['weighted_f1']:.5f}",
            "4/4 Six-State Macro Recall": f"{metrics_a['six_state_macro_recall']:.5f}",
            "4/4 Cohen's Kappa": f"{metrics_a['kappa']:.5f}",
            "4/4 MCC": f"{metrics_a['mcc']:.5f}",
            "3/4 Exact Agreement": f"{metrics_b['exact_agreement']:.5f}",
            "3/4 Macro F1": f"{metrics_b['macro_f1']:.5f}",
            "3/4 Weighted F1": f"{metrics_b['weighted_f1']:.5f}",
            "3/4 Six-State Macro Recall": f"{metrics_b['six_state_macro_recall']:.5f}",
            "3/4 Cohen's Kappa": f"{metrics_b['kappa']:.5f}",
            "3/4 MCC": f"{metrics_b['mcc']:.5f}",
            "SC": f"{sc_val:.5f}",
            "CASC": f"{casc_val:.5f}",
        })

        sc_casc_comparison_rows.append({
            "Method": method_name,
            "Cohort C Cases N": total_cases,
            "SC (Semantic Concordance)": f"{sc_val:.5f}",
            "CASC (Consensus-Aware)": f"{casc_val:.5f}",
        })

    # -------------------------------------------------------------
    # STEP 10: Comparison Tables & Sensitivity Analysis
    # -------------------------------------------------------------
    print(f"\n[Step 10/10] Writing comparison summaries and sensitivity analysis...", flush=True)

    # 10a: METHOD_COMPARISON.csv
    with (outputs_dir / "METHOD_COMPARISON.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(method_comparison_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(method_comparison_rows)

    # 10b: SUPERVISOR_COMPARISON.csv
    with (outputs_dir / "SUPERVISOR_COMPARISON.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(supervisor_comparison_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(supervisor_comparison_rows)

    # 10c: SC_CASC_COMPARISON.csv
    with (outputs_dir / "SC_CASC_COMPARISON.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(sc_casc_comparison_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sc_casc_comparison_rows)

    # 10d: SC_CASC_SENSITIVITY.csv
    identity_matrix = {
        s1: {s2: 1.0 if s1 == s2 else 0.0 for s2 in STATES} for s1 in STATES
    }
    matrix_plus = {
        s1: {
            s2: 1.0 if s1 == s2 else min(1.0, round(aff_matrix[s1][s2] + 0.10, 2))
            for s2 in STATES
        }
        for s1 in STATES
    }
    matrix_minus = {
        s1: {
            s2: 1.0 if s1 == s2 else max(0.0, round(aff_matrix[s1][s2] - 0.10, 2))
            for s2 in STATES
        }
        for s1 in STATES
    }

    sensitivity_rows = []
    for method_key, method_name, preds, _ in all_methods:
        sc_a, casc_a, _ = compute_sc_casc(cases_metadata, preds, aff_matrix)
        sc_b, casc_b, _ = compute_sc_casc(cases_metadata, preds, identity_matrix)
        sc_cp, casc_cp, _ = compute_sc_casc(cases_metadata, preds, matrix_plus)
        sc_cm, casc_cm, _ = compute_sc_casc(cases_metadata, preds, matrix_minus)

        sensitivity_rows.append({
            "method": method_name,
            "MatrixA_SC": f"{sc_a:.5f}",
            "MatrixA_CASC": f"{casc_a:.5f}",
            "MatrixB_Identity_SC": f"{sc_b:.5f}",
            "MatrixB_Identity_CASC": f"{casc_b:.5f}",
            "Perturb_Plus0.10_SC": f"{sc_cp:.5f}",
            "Perturb_Plus0.10_CASC": f"{casc_cp:.5f}",
            "Perturb_Minus0.10_SC": f"{sc_cm:.5f}",
            "Perturb_Minus0.10_CASC": f"{casc_cm:.5f}",
        })

    with (outputs_dir / "SC_CASC_SENSITIVITY.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(sensitivity_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sensitivity_rows)

    total_pipeline_time = time.time() - t_start
    print(f"\n=================================================================", flush=True)
    print(f"Validation completed successfully in {total_pipeline_time:.2f}s.", flush=True)
    print(f"All outputs generated in:\n  {outputs_dir}", flush=True)
    print(f"=================================================================\n", flush=True)


if __name__ == "__main__":
    run_validation()
