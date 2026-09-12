#!/usr/bin/env python3
"""Screen reuse-friendly windows for Sleep-EDF, LIGO, and BLOND-250."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("Sleep", "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", "OPS-data-main9/04_biomedical_sleep_edf/metadata.json", 600_000, 60_000, 300),
    ("Sleep", "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", "OPS-data-main9/04_biomedical_sleep_edf/metadata.json", 500_000, 50_000, 250),
    ("Sleep", "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", "OPS-data-main9/04_biomedical_sleep_edf/metadata.json", 400_000, 40_000, 200),
    ("LIGO", "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", "OPS-data-main9/05_physics_ligo/metadata.json", 3_000_000, 300_000, 1_500),
    ("LIGO", "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", "OPS-data-main9/05_physics_ligo/metadata.json", 2_000_000, 200_000, 1_000),
    ("LIGO", "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", "OPS-data-main9/05_physics_ligo/metadata.json", 1_500_000, 150_000, 750),
    ("BLOND", "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", "OPS-data-main9/06_power_blond250/metadata.json", 7_500_000, 750_000, 3_750),
    ("BLOND", "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", "OPS-data-main9/06_power_blond250/metadata.json", 5_000_000, 500_000, 2_500),
    ("BLOND", "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", "OPS-data-main9/06_power_blond250/metadata.json", 3_000_000, 300_000, 1_500),
)


def command(algorithm, dataset, metadata, window, step, minsup, output):
    if algorithm == "Original-Combined":
        runner = ROOT / "work/run_cached_fusion_ops_miner.py"
        return [sys.executable, str(runner), "--dataset", str(dataset),
                "--metadata", str(metadata), "--window", str(window),
                "--step", str(step), "--minsup", str(minsup),
                "--output", str(output)]
    runner = ROOT / "work/run_all_ops_algorithm.py"
    return [sys.executable, str(runner), "--algorithm", "OPS-NoReuse",
            "--dataset", str(dataset), "--metadata", str(metadata),
            "--window", str(window), "--step", str(step),
            "--minsup", str(minsup), "--output", str(output)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/large-reuse-parameter-sweep.json")
    args = parser.parse_args()
    summaries = []
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        for domain, dataset_rel, metadata_rel, window, step, minsup in CASES:
            results = {}
            for algorithm in ("Original-Combined", "OPS-NoReuse"):
                output = temporary / f"{domain}-{window}-{algorithm}.json"
                try:
                    subprocess.run(
                        command(algorithm, ROOT / dataset_rel, ROOT / metadata_rel,
                                window, step, minsup, output),
                        cwd=ROOT, check=True, capture_output=True, text=True,
                        timeout=args.timeout,
                    )
                    results[algorithm] = json.loads(output.read_text())
                except subprocess.TimeoutExpired:
                    results[algorithm] = {"status": "timeout", "timeout_seconds": args.timeout}
            summary = {"dataset": domain, "window": window, "step": step,
                       "minsup": minsup, "results": results}
            if all("elapsed_seconds" in results[x] for x in results):
                reuse = results["Original-Combined"]["elapsed_seconds"]
                noreuse = results["OPS-NoReuse"]["elapsed_seconds"]
                summary["speedup"] = noreuse / reuse
                summary["time_reduction_percent"] = (1 - reuse / noreuse) * 100
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
