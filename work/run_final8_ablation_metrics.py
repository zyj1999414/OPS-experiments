#!/usr/bin/env python3
"""Run the selected algorithms and datasets sequentially, collecting three metrics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
ALGORITHMS = [
    "OPS-SPF", "OPS-ISC", "OPS-PF", "OPS-Enum", "OPS-NoReuse",
    "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS", "OPS-Miner",
]
DATASETS = [
    ("SDB1", "work/sdb1-8-f64/SDB1_GOOG.f64", None, None, 1_000, 100, 4),
    ("SDB2", "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", None, 48_204, 4_422, 442, 4),
    ("SDB3", "OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64", None, None, 15_000, 1_500, 4),
    ("SDB4", "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", None, 420_551, 16_000, 1_600, 4),
    ("SDB5", "OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64", None, None, 50_000, 5_000, 8),
    ("SDB6", "OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", "OPS-data-main9/03_astronomy_kepler/metadata.json", None, 20_000, 2_000, 8),
    ("SDB7", "OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64", None, 2_009_000, 60_000, 6_000, 8),
    ("SDB8", "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", None, 4_000_000, 40_000, 4_000, 8),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output_root = ROOT / "outputs/final8-ablation-metrics"
    output_root.mkdir(parents=True, exist_ok=True)
    for algorithm in ALGORITHMS:
        for name, dataset, metadata, prefix, window, step, minsup in DATASETS:
            out_dir = output_root / algorithm
            out_dir.mkdir(parents=True, exist_ok=True)
            timing_output = out_dir / f"{name}-timing.json"
            candidate_output = out_dir / f"{name}-candidates.json"
            if prefix is not None:
                local_metadata = output_root / f"{name}-metadata.json"
                local_metadata.write_text(json.dumps({"boundaries": [{"start": 0, "length": prefix}]}) + "\n")
                metadata_path = local_metadata
            elif metadata:
                metadata_path = ROOT / metadata
            else:
                metadata_path = None

            base = [
                sys.executable, str(RUNNER), f"--algorithm={algorithm}",
                "--dataset", str(ROOT / dataset), "--window", str(window),
                "--step", str(step), "--minsup", str(minsup),
            ]
            if metadata_path:
                base += ["--metadata", str(metadata_path)]

            runs = [("timing", timing_output, False)]
            if algorithm in {"OPS-PF", "OPS-Enum", "OPS-NoReuse", "OPS-Miner"}:
                runs.append(("candidates", candidate_output, True))
            for label, output, count_candidates in runs:
                timeout_file = output.with_suffix(".timeout.json")
                prior_timeout_is_terminal = args.timeout is not None and timeout_file.exists()
                if not args.force and (output.exists() or prior_timeout_is_terminal):
                    print("SKIP", algorithm, name, label, flush=True)
                    continue
                command = [*base]
                if count_candidates:
                    command.append("--count-candidates")
                command += ["--output", str(output)]
                print("START", algorithm, name, label, flush=True)
                started = time.perf_counter()
                try:
                    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    elapsed = time.perf_counter() - started
                    timeout_file.write_text(json.dumps({
                        "algorithm": algorithm, "dataset": name, "metric_run": label,
                        "status": "timeout", "timeout_seconds": args.timeout,
                        "elapsed_wall_seconds": elapsed,
                    }, indent=2) + "\n")
                    print("TIMEOUT", algorithm, name, label, f"{elapsed:.2f}s", flush=True)
                    break
                if completed.returncode != 0:
                    output.with_suffix(".error.txt").write_text(completed.stdout + "\n" + completed.stderr)
                    print("ERROR", algorithm, name, label, completed.returncode, flush=True)
                    break
                record = json.loads(output.read_text())
                print("DONE", algorithm, name, label,
                      f"time={record['elapsed_seconds']:.6f}",
                      f"rss={record['peak_rss_mib']:.2f}",
                      f"candidates={record.get('candidates_total')}", flush=True)


if __name__ == "__main__":
    main()
