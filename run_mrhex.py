"""MRHex v1.0.0 Prediction Runner.

Executes deterministic report assertion classification on an input CSV
containing clinical radiology reports and target pathologies.

Usage:
    python run_mrhex.py [--input INPUT_CSV] [--output OUTPUT_CSV]

Defaults:
    --input:  data/validation_data/validation_input.csv
    --output: outputs/mrhex_predictions.csv
"""
import argparse
import csv
from pathlib import Path
import sys
import time

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from mrhex import classify
from mrhex.config import load_config


def run_mrhex(input_path: Path, output_path: Path) -> None:
    print("=================================================================")
    print("           MRHex v1.0.0 Standalone Prediction Runner             ")
    print("=================================================================")
    print(f"Input file:  {input_path}")
    print(f"Output file: {output_path}")

    # Preload configuration
    print("Loading MRHex configuration...")
    lookup, active_labels = load_config()
    print("Loaded MRHex configuration for 32 official target pathologies.")

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        assert "report" in fieldnames, "Input CSV must contain 'report' column"
        assert "target_pathology" in fieldnames, "Input CSV must contain 'target_pathology' column"
        rows = list(reader)

    total_cases = len(rows)
    print(f"Processing {total_cases} cases...")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    out_records = []
    for idx, row in enumerate(rows):
        cid = row.get("case_id", f"case_{idx+1}")
        target = row["target_pathology"]
        report_text = row["report"]

        res = classify(report_text, target, case_id=cid, lookup=lookup)

        state = res["state"]
        raw_reason = res.get("reason", "")
        if isinstance(raw_reason, list):
            reason_str = ";".join(str(r) for r in raw_reason)
        else:
            reason_str = str(raw_reason)

        out_records.append({
            "case_id": cid,
            "target_pathology": target,
            "prediction": state,
            "resolution_source": res.get("resolution_source", ""),
            "fallback_rule_id": res.get("fallback_rule_id", ""),
            "reason": reason_str,
        })

    elapsed = time.time() - t0
    print(f"Inference completed in {elapsed:.2f}s ({total_cases/elapsed:.1f} cases/sec).")

    fieldnames = [
        "case_id",
        "target_pathology",
        "prediction",
        "resolution_source",
        "fallback_rule_id",
        "reason",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_records)

    print(f"Predictions written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Execute MRHex v1.0.0 prediction pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=PACKAGE_ROOT / "data" / "validation_data" / "validation_input.csv",
        help="Path to input CSV containing report and target_pathology columns.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PACKAGE_ROOT / "outputs" / "mrhex_predictions.csv",
        help="Path to output CSV destination for predictions.",
    )
    args = parser.parse_args()
    run_mrhex(args.input, args.output)


if __name__ == "__main__":
    main()
