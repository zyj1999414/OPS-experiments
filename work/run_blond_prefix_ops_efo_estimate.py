#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
EFO_RUNNER = ROOT / "work/run_original_efo_sopp_first_window.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/blond-prefix-ops-efo-estimate"
CONFIGS = [
    ("SDB61_1", 65_536, 4), ("SDB62_2", 131_072, 17),
    ("SDB63_3", 196_608, 30), ("SDB64_4", 262_144, 43),
    ("SDB65_5", 327_680, 56), ("SDB66_6", 393_216, 69),
    ("SDB67_7", 458_752, 82), ("SDB68_8", 524_288, 95),
]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, length, windows in CONFIGS:
        result = OUT / "OPS-Miner" / f"{name}.json"
        if result.exists():
            print("SKIP OPS", name, flush=True)
            continue
        metadata = OUT / "metadata" / f"{name}.json"
        save(metadata, {"boundaries": [{"start": 0, "length": length}]})
        pending = result.with_suffix(".pending.json")
        pending.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, str(RUNNER), "--algorithm", "OPS-Miner",
            "--dataset", str(DATA), "--metadata", str(metadata),
            "--window", "50000", "--step", "5000", "--minsup", "80",
            "--max-windows", str(windows), "--output", str(pending),
        ]
        print("START OPS", name, flush=True)
        done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        result.parent.mkdir(parents=True, exist_ok=True)
        result.with_suffix(".log").write_text(done.stdout + "\n" + done.stderr)
        if done.returncode:
            print("FAILED OPS", name, done.returncode, flush=True)
            continue
        pending.replace(result)
        r = json.loads(result.read_text())
        print("DONE OPS", name, r["elapsed_seconds"], r["peak_rss_mib"], r["patterns_total"], flush=True)

    efo_json = ROOT / "outputs/original-efo-sopp-first-windows/EFO-Miner/SDB8/result-w50000-minsup80.json"
    if not efo_json.exists():
        print("START EFO FIRST", flush=True)
        done = subprocess.run([
            sys.executable, str(EFO_RUNNER), "--algorithm", "EFO-Miner",
            "--dataset", "SDB8", "--window-size", "50000", "--minsup", "80",
        ], cwd=ROOT, capture_output=True, text=True)
        (OUT / "efo-first-window.log").write_text(done.stdout + "\n" + done.stderr)
        if done.returncode:
            raise SystemExit(done.returncode)
    efo = json.loads(efo_json.read_text())
    estimates = []
    for name, length, windows in CONFIGS:
        estimates.append({
            "dataset": name, "data_length": length, "windows": windows,
            "first_window_seconds": efo["elapsed_seconds"],
            "estimated_seconds": efo["elapsed_seconds"] * windows,
            "first_window_peak_rss_mib": efo["peak_rss_mib"],
            "first_window_frequent_patterns": efo["frequent_patterns"],
            "first_window_candidate_patterns": efo["candidate_patterns"],
        })
    save(OUT / "EFO-Miner-estimates.json", estimates)
    print("EFO FIRST", efo["elapsed_seconds"], efo["peak_rss_mib"], flush=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
