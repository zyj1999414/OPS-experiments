#!/usr/bin/env python3
"""Run all 11 OPS ablation algorithms on the final eight-dataset design."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS = [
    "OPS-Miner", "-1OPS-Miner", "OPS-NoReuse", "OPS-NoNumpy", "OPS-PF", "OPS-Enum",
    "OPS-ISC", "OPS-SPF", "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS",
]
DATASETS = [
    ("00_transport_nyc", "OPS-data-main9/00_transport_nyc/00_transport_nyc_256KiB.f64", "OPS-data-main9/00_transport_nyc/metadata.json", 20_000, 2_000, 10),
    ("01_industrial_cwru", "OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64", "OPS-data-main9/01_industrial_cwru/metadata.json", 50_000, 5_000, 25),
    ("02_weather_noaa_uscrn", "OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64", "OPS-data-main9/02_weather_noaa_uscrn/metadata.json", 105_120, 10_512, 53),
    ("03_astronomy_kepler", "OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", "OPS-data-main9/03_astronomy_kepler/metadata.json", 100_000, 10_000, 50),
    ("04_biomedical_sleep_edf", "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", "OPS-data-main9/04_biomedical_sleep_edf/metadata.json", 600_000, 60_000, 300),
    ("05_physics_ligo", "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", "OPS-data-main9/05_physics_ligo/metadata.json", 4_096_000, 409_600, 2_048),
    ("06_power_blond250", "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", "OPS-data-main9/06_power_blond250/metadata.json", 15_000_000, 1_500_000, 7_500),
    ("07_finance_binance", "OPS-data-main9/07_finance_binance/07_finance_binance_512MiB.f64", "OPS-data-main9/07_finance_binance/metadata.json", 1_000_000, 100_000, 500),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=[x[0][:2] for x in DATASETS], required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    item = next(x for x in DATASETS if x[0].startswith(args.dataset))
    key, dataset, metadata, window, step, minsup = item
    out_dir = ROOT / "outputs/OPS-ablation-main8-minsup0005" / key
    out_dir.mkdir(parents=True, exist_ok=True)
    for algorithm in ALGORITHMS:
        output = out_dir / f"{algorithm}.json"
        if output.exists():
            try:
                json.loads(output.read_text())
                print("SKIP", key, algorithm, flush=True)
                continue
            except Exception:
                pass
        command = [
            sys.executable, str(ROOT / "work/run_all_ops_algorithm.py"),
            f"--algorithm={algorithm}", "--dataset", str(ROOT / dataset),
            "--metadata", str(ROOT / metadata), "--window", str(window),
            "--step", str(step), "--minsup", str(minsup), "--output", str(output),
        ]
        print("START", key, algorithm, flush=True)
        wall_start = time.time()
        try:
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                    timeout=args.timeout)
        except subprocess.TimeoutExpired as exc:
            record = {"algorithm": algorithm, "dataset": dataset, "status": "timeout",
                      "timeout_seconds": args.timeout}
            output.with_suffix(".timeout.json").write_text(json.dumps(record, indent=2) + "\n")
            print("TIMEOUT", key, algorithm, args.timeout, flush=True)
            continue
        if result.returncode:
            output.with_suffix(".error.txt").write_text(result.stdout + "\n" + result.stderr)
            print("ERROR", key, algorithm, result.returncode, flush=True)
            continue
        summary = json.loads(output.read_text())
        print("DONE", key, algorithm, f"wall={time.time()-wall_start:.2f}",
              f"windows={summary['windows']}",
              f"mean={summary['patterns_mean_per_window']:.3f}",
              f"rss={summary['peak_rss_mib']:.2f}", flush=True)


if __name__ == "__main__":
    main()
