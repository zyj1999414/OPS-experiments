#!/usr/bin/env python3
"""Run SDB1--SDB7 ablations, estimating jobs projected above 180 seconds."""

import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
OUT = ROOT / "outputs/sdb1-7-high-minsup-all-ablation"
EXISTING = ROOT / "outputs/main8-high-minsup-comparison"
ALGORITHMS = [
    "OPS-SPF", "OPS-ISC", "OPS-PF", "OPS-Enum", "OPS-NoReuse",
    "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS", "OPS-Miner",
]
DATASETS = [
    ("SDB1", ROOT / "work/sdb1-8-f64/SDB1_GOOG.f64", None, 1_000, 100, 40, 45),
    ("SDB2", ROOT / "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", 48_204, 4_422, 442, 40, 100),
    ("SDB3", ROOT / "OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64", None, 15_000, 1_500, 40, 57),
    ("SDB4", ROOT / "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", 420_551, 16_000, 1_600, 80, 253),
    ("SDB5", ROOT / "OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64", None, 50_000, 5_000, 80, 95),
    ("SDB6", ROOT / "OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", "kepler", 50_000, 5_000, 80, 248),
    ("SDB7", ROOT / "OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64", 2_009_000, 60_000, 6_000, 80, 325),
    ("SDB8", ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", 4_000_000, 200_000, 20_000, 80, 191),
]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def command(algorithm, dataset, metadata, window, step, minsup, max_windows, output):
    result = [
        sys.executable, str(RUNNER), f"--algorithm={algorithm}",
        "--dataset", str(dataset), "--window", str(window), "--step", str(step),
        "--minsup", str(minsup), "--max-windows", str(max_windows), "--output", str(output),
    ]
    if metadata:
        result += ["--metadata", str(metadata)]
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for algorithm in ALGORITHMS:
        for name, dataset, boundary, window, step, minsup, windows in DATASETS:
            final_file = OUT / algorithm / f"{name}.json"
            if final_file.exists():
                record = json.loads(final_file.read_text())
                summary.append(record)
                print("SKIP", algorithm, name, record["status"], flush=True)
                continue

            if boundary == "kepler":
                metadata = ROOT / "OPS-data-main9/03_astronomy_kepler/metadata.json"
            elif isinstance(boundary, int):
                metadata = OUT / "metadata" / f"{name}.json"
                write_json(metadata, {"boundaries": [{"start": 0, "length": boundary}]})
            else:
                metadata = None

            # Reuse previously completed full measurements with identical parameters.
            prior = EXISTING / algorithm / f"{name}-timing.json"
            if algorithm in {"OPS-Miner", "OPS-NoReuse"} and prior.exists():
                measured = json.loads(prior.read_text())
                if not (
                    measured.get("window") == window and measured.get("step") == step
                    and measured.get("minsup") == minsup and measured.get("windows") == windows
                ):
                    prior = None
            if algorithm in {"OPS-Miner", "OPS-NoReuse"} and prior:
                record = {
                    "algorithm": algorithm, "dataset": name, "minsup": minsup,
                    "window": window, "step": step, "windows": windows,
                    "status": "measured", "elapsed_seconds": measured["elapsed_seconds"],
                    "peak_rss_mib": measured["peak_rss_mib"],
                    "patterns_total": measured["patterns_total"],
                    "source": str(prior),
                }
                write_json(final_file, record)
                summary.append(record)
                print("REUSE", algorithm, name, record["elapsed_seconds"], flush=True)
                continue

            first_file = OUT / algorithm / f"{name}-first-window.json"
            if not first_file.exists():
                print("FIRST", algorithm, name, flush=True)
                try:
                    subprocess.run(
                        command(algorithm, dataset, metadata, window, step, minsup, 1, first_file),
                        cwd=ROOT, check=True, capture_output=True, text=True, timeout=180,
                    )
                except subprocess.TimeoutExpired:
                    record = {
                        "algorithm": algorithm, "dataset": name, "minsup": minsup,
                        "window": window, "step": step, "windows": windows,
                        "status": "estimated_lower_bound", "first_window_seconds": ">180",
                        "estimated_seconds": f">{180 * windows}",
                    }
                    write_json(final_file, record)
                    summary.append(record)
                    print("FIRST_TIMEOUT", algorithm, name, flush=True)
                    continue
            first = json.loads(first_file.read_text())
            estimate = first["elapsed_seconds"] * windows
            if estimate > 180:
                record = {
                    "algorithm": algorithm, "dataset": name, "minsup": minsup,
                    "window": window, "step": step, "windows": windows,
                    "status": "estimated", "first_window_seconds": first["elapsed_seconds"],
                    "estimated_seconds": estimate, "first_window_peak_rss_mib": first["peak_rss_mib"],
                    "first_window_patterns": first["patterns_total"],
                }
                write_json(final_file, record)
                summary.append(record)
                print("ESTIMATE", algorithm, name, estimate, flush=True)
                continue

            pending = OUT / algorithm / f"{name}.pending.json"
            print("FULL", algorithm, name, "projected", estimate, flush=True)
            started = time.perf_counter()
            try:
                subprocess.run(
                    command(algorithm, dataset, metadata, window, step, minsup, windows, pending),
                    cwd=ROOT, check=True, capture_output=True, text=True, timeout=180,
                )
            except subprocess.TimeoutExpired:
                record = {
                    "algorithm": algorithm, "dataset": name, "minsup": minsup,
                    "window": window, "step": step, "windows": windows,
                    "status": "estimated_after_full_timeout", "first_window_seconds": first["elapsed_seconds"],
                    "estimated_seconds": estimate, "full_run_stopped_after_seconds": time.perf_counter() - started,
                }
            else:
                measured = json.loads(pending.read_text())
                record = {
                    "algorithm": algorithm, "dataset": name, "minsup": minsup,
                    "window": window, "step": step, "windows": windows,
                    "status": "measured", "elapsed_seconds": measured["elapsed_seconds"],
                    "peak_rss_mib": measured["peak_rss_mib"],
                    "patterns_total": measured["patterns_total"],
                    "first_window_seconds": first["elapsed_seconds"], "initial_estimate_seconds": estimate,
                }
            write_json(final_file, record)
            summary.append(record)
            print("DONE", algorithm, name, record["status"], record.get("elapsed_seconds", record.get("estimated_seconds")), flush=True)
    write_json(OUT / "summary.json", summary)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
