"""Installation and environment verification script for MRHex v1.0.0.

Verifies:
1. MRHex runtime imports and initializes cleanly from the package.
2. Baseline runtime implementations (NegEx, pyConTextNLP, medspaCy) import and initialize.
3. All 4 required configuration files load and validate with 32 official labels.
4. Validation input exists, has N = 2,978 cases, 0 missing values across all required fields.
5. Reference model outputs exist, N = 2,978, exact alignment, valid six states, and exact agreement counts:
   - 4/4 = 2,647
   - 3/4 = 234
   - 2-2 = 43
   - 2-1-1 = 50
   - 1-1-1-1 = 4
6. Semantic affinity matrix and baseline state mapping exist and load.
7. Executes a local MRHex smoke test.
"""
from collections import Counter
import csv
from pathlib import Path
import sys
import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from mrhex import classify, load_config
from mrhex.classifier import SYSTEM_ID, VALID_STANDALONE_STATES, VERSION

VALID_STATES = frozenset({"S", "U", "C", "UC", "H", "NEI"})


def fail(msg: str):
    print(f"\nERROR: {msg}", file=sys.stderr)
    print("\n============================================", file=sys.stderr)
    print("INSTALLATION VERIFICATION FAILED", file=sys.stderr)
    print("============================================\n", file=sys.stderr)
    sys.exit(1)


def verify_all():
    print("=================================================================")
    print("      MRHex v1.0.0 Package & Runtime Environment Verification    ")
    print("=================================================================")

    # 1. MRHex Module
    print("\n[1/7] Verifying MRHex module imports...")
    try:
        assert callable(classify)
        assert callable(load_config)
        print(f"      MRHex runtime (version {VERSION}) imported successfully.")
    except Exception as exc:
        fail(f"Failed to import MRHex runtime: {exc}")

    # 2. Baseline Runtime Execution Verification
    print("\n[2/7] Verifying baseline runtime implementations...")
    print("Baseline runtime verification:\n")

    # 2a: NegEx
    try:
        from baselines.negex.negex_baseline import NegExBaseline
        negex_instance = NegExBaseline()
        assert negex_instance is not None
        print("NegEx:\nPASS\n")
    except Exception as exc:
        print("NegEx:\nFAIL\n", file=sys.stderr)
        print(f"Missing or broken NegEx dependency: {exc}\nInstall dependencies using:\n\npip install -r requirements.txt\n", file=sys.stderr)
        fail("NegEx runtime verification failed.")

    # 2b: pyConTextNLP / ConText
    try:
        from baselines.pycontext.pycontext_baseline import PyConTextBaseline
        pycontext_instance = PyConTextBaseline()
        assert pycontext_instance is not None
        print("pyConTextNLP / ConText:\nPASS\n")
    except Exception as exc:
        print("pyConTextNLP / ConText:\nFAIL\n", file=sys.stderr)
        print(f"Missing or broken pyConTextNLP dependency: {exc}\nInstall dependencies using:\n\npip install -r requirements.txt\n", file=sys.stderr)
        fail("pyConTextNLP runtime verification failed.")

    # 2c: medspaCy
    try:
        from baselines.medspacy.medspacy_baseline import MedspaCyBaseline
        medspacy_instance = MedspaCyBaseline()
        assert medspacy_instance is not None
        print("medspaCy:\nPASS\n")
    except Exception as exc:
        print("medspaCy:\nFAIL\n", file=sys.stderr)
        print(f"Missing or broken medspaCy dependency: {exc}\nInstall dependencies using:\n\npip install -r requirements.txt\n", file=sys.stderr)
        fail("medspaCy runtime verification failed.")

    # 3. Configurations and Official 32 Pathologies
    print("[3/7] Verifying configuration files and 32 official labels...")
    codebook_path = PACKAGE_ROOT / "configs" / "final_pathology_codebook.yaml"
    base_rules_path = PACKAGE_ROOT / "configs" / "final_deterministic_rules_v2.yaml"
    label_cfg_path = PACKAGE_ROOT / "configs" / "mrhex_label_configuration.yaml"
    official32_path = PACKAGE_ROOT / "configs" / "official_mrrate_32_labels.yaml"

    for p in [codebook_path, base_rules_path, label_cfg_path, official32_path]:
        if not p.exists():
            fail(f"Missing config file: {p}")
        try:
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                assert isinstance(data, (dict, list))
        except Exception as exc:
            fail(f"YAML parsing error in {p}: {exc}")

    with official32_path.open("r", encoding="utf-8") as f:
        off32_data = yaml.safe_load(f)
    labels = off32_data.get("active_labels", off32_data.get("pathologies", off32_data.get("labels", [])))
    if len(labels) != 32:
        fail(f"Expected 32 official labels in {official32_path}, found {len(labels)}")

    lookup, active_labels = load_config(codebook_path, base_rules_path, label_cfg_path)
    for lbl in labels:
        if lbl not in lookup:
            fail(f"Label '{lbl}' missing from MRHex lookup dictionary")
    print(f"      All {len(labels)} official pathologies validated in configuration lookup (4/4 YAML PASS).")

    # 4. Validation Input Integrity
    print("\n[4/7] Verifying validation input corpus integrity...")
    validation_input = PACKAGE_ROOT / "data" / "validation_data" / "validation_input.csv"
    if not validation_input.exists():
        fail(f"Missing validation input: {validation_input}")
    with validation_input.open("r", encoding="utf-8") as f:
        corpus = list(csv.DictReader(f))

    if len(corpus) != 2978:
        fail(f"Expected 2,978 validation rows, found {len(corpus)}")

    unique_case_ids = set()
    unique_pair_ids = set()
    missing_case_id = 0
    missing_pair_id = 0
    missing_target = 0
    missing_report = 0
    pathologies_found = set()

    for r in corpus:
        cid = r.get("case_id", "").strip()
        pid = r.get("report_label_pair_id", "").strip()
        tgt = r.get("target_pathology", "").strip()
        rep = r.get("report", "").strip()

        if not cid:
            missing_case_id += 1
        else:
            unique_case_ids.add(cid)

        if not pid:
            missing_pair_id += 1
        else:
            unique_pair_ids.add(pid)

        if not tgt:
            missing_target += 1
        else:
            pathologies_found.add(tgt)

        if not rep:
            missing_report += 1

    if len(unique_case_ids) != 2978:
        fail(f"Expected 2,978 unique case_id values, found {len(unique_case_ids)}")
    if len(unique_pair_ids) != 2978:
        fail(f"Expected 2,978 unique report_label_pair_id values, found {len(unique_pair_ids)}")
    if len(pathologies_found) != 32:
        fail(f"Expected 32 target pathologies, found {len(pathologies_found)}")
    if missing_case_id > 0:
        fail(f"Found {missing_case_id} missing case_id values")
    if missing_pair_id > 0:
        fail(f"Found {missing_pair_id} missing report_label_pair_id values")
    if missing_target > 0:
        fail(f"Found {missing_target} missing target_pathology values")
    if missing_report > 0:
        fail(f"Found {missing_report} missing report values")

    print(f"      Validation input verified:")
    print(f"      - 2,978 rows")
    print(f"      - 2,978 unique case_id")
    print(f"      - 2,978 unique report_label_pair_id")
    print(f"      - 32 target pathologies")
    print(f"      - 0 missing required fields")

    # 5. Reference Model Outputs & Agreement Counts
    print("\n[5/7] Verifying reference model outputs and agreement distribution...")
    ref_outputs_path = PACKAGE_ROOT / "data" / "validation_data" / "reference_outputs.csv"
    if not ref_outputs_path.exists():
        fail(f"Missing reference outputs: {ref_outputs_path}")
    with ref_outputs_path.open("r", encoding="utf-8") as f:
        ref_rows = list(csv.DictReader(f))

    if len(ref_rows) != 2978:
        fail(f"Expected 2,978 reference output rows, found {len(ref_rows)}")

    ref_case_ids = set()
    required_models = [
        "deepseek_v4_1_flash",
        "agnes_3_0_flash",
        "mercury_2_5",
        "atria_dawn_preview",
    ]

    for m in required_models:
        if m not in ref_rows[0]:
            fail(f"Missing reference model column: {m}")

    patterns = Counter()
    for i, r in enumerate(ref_rows):
        cid = r.get("case_id", "").strip()
        tgt = r.get("target_pathology", "").strip()

        if not cid:
            fail(f"Empty case_id in reference outputs row {i}")
        if cid in ref_case_ids:
            fail(f"Duplicate case_id '{cid}' in reference outputs row {i}")
        ref_case_ids.add(cid)

        # Verify exact alignment with validation_input.csv
        inp_row = corpus[i]
        if cid != inp_row["case_id"]:
            fail(f"Case ID alignment mismatch at index {i}: ref='{cid}' vs input='{inp_row['case_id']}'")
        if tgt != inp_row["target_pathology"]:
            fail(f"Target pathology alignment mismatch at index {i}: ref='{tgt}' vs input='{inp_row['target_pathology']}'")

        outputs = []
        for m in required_models:
            val = r[m].strip()
            if val not in VALID_STATES:
                fail(f"Invalid model output state '{val}' for model '{m}' in case {cid}")
            outputs.append(val)

        rc = Counter(outputs)
        top_c = rc.most_common(1)[0][1]
        if top_c == 4:
            patterns["4/4"] += 1
        elif top_c == 3:
            patterns["3/4"] += 1
        elif top_c == 2:
            if len(rc) == 2:
                patterns["2-2"] += 1
            else:
                patterns["2-1-1"] += 1
        else:
            patterns["1-1-1-1"] += 1

    expected_patterns = {
        "4/4": 2647,
        "3/4": 234,
        "2-2": 43,
        "2-1-1": 50,
        "1-1-1-1": 4,
    }
    for k, exp_val in expected_patterns.items():
        actual_val = patterns[k]
        if actual_val != exp_val:
            fail(f"Pattern count mismatch for {k}: expected {exp_val}, got {actual_val}")

    print(f"      Reference outputs verified:")
    print(f"      - 2,978 rows aligned with validation input")
    print(f"      - 2,978 unique case_id, 0 duplicate case_id")
    print(f"      - All model outputs belong to {sorted(list(VALID_STATES))}")
    print(f"      - Agreement counts: 4/4={patterns['4/4']}, 3/4={patterns['3/4']}, 2-2={patterns['2-2']}, 2-1-1={patterns['2-1-1']}, 1-1-1-1={patterns['1-1-1-1']}")

    # 6. Evaluation Resources
    print("\n[6/7] Verifying evaluation resources...")
    affinity_path = PACKAGE_ROOT / "evaluation" / "semantic_affinity_matrix.csv"
    mapping_path = PACKAGE_ROOT / "evaluation" / "baseline_state_mapping.md"
    if not affinity_path.exists():
        fail(f"Missing affinity matrix: {affinity_path}")
    if not mapping_path.exists():
        fail(f"Missing baseline mapping: {mapping_path}")

    with affinity_path.open("r", encoding="utf-8") as f:
        aff_rows = list(csv.DictReader(f))
    if len(aff_rows) != 6:
        fail(f"Expected 6 states in affinity matrix, found {len(aff_rows)}")
    print("      Evaluation resources (matrix, state mappings) verified.")

    # 7. Local MRHex Smoke Test
    print("\n[7/7] Running local MRHex smoke test...")
    sample_text = "No acute intracranial hemorrhage or mass effect."
    smoke_res = classify(
        sample_text,
        lookup["Subdural intracranial hemorrhage"],
        case_id="SMOKE_001",
        source_mode="full_report",
    )
    smoke_state = smoke_res["state"]
    if smoke_state not in VALID_STANDALONE_STATES:
        fail(f"Invalid smoke test output state: {smoke_state}")
    print(f"      Smoke test passed: predicted state = '{smoke_state}'.")

    print("\n============================================")
    print("MRHex v1.0.0 Production Package")
    print("INSTALLATION VERIFICATION PASSED")
    print("============================================\n")


if __name__ == "__main__":
    verify_all()
