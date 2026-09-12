#!/usr/bin/env python3
"""Run WOPP-Miner on the parameter sets selected for the reuse experiment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_wopp_miner_benchmark.py"
SDB = ROOT / "work/sdb1-8-f64"

CASES = (
    ("SDB4 Metro Traffic", SDB / "SDB4_Metro_Traffic.f64", SDB / "SDB4_Metro_Traffic.json", None, 4_422, 442, 3),
    ("CWRU轴承振动", ROOT / "OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64", ROOT / "OPS-data-main9/01_industrial_cwru/metadata.json", None, 30_000, 3_000, 60),
    ("SDB6 Jena Temperature", SDB / "SDB6_Jena_Temperature.f64", SDB / "SDB6_Jena_Temperature.json", None, 8_260, 826, 3),
    ("SDB7 Berlin Temperature", SDB / "SDB7_Berlin_Temperature.f64", SDB / "SDB7_Berlin_Temperature.json", None, 14_600, 1_460, 3),
    ("SDB8 Household Power", SDB / "SDB8_Household_Power.f64", SDB / "SDB8_Household_Power.json", None, 40_260, 4_026, 3),
    ("NYC TLC", ROOT / "OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64", None, 2_009_000, 10_000, 1_000, 3),
    ("SDB1 GOOG", SDB / "SDB1_GOOG.f64", SDB / "SDB1_GOOG.json", None, 200, 10, 1),
    ("SDB3 Beijing PM2.5", SDB / "SDB3_Beijing_PM25.f64", SDB / "SDB3_Beijing_PM25.json", None, 3_830, 383, 1),
    ("SDB5 OpenAQ PM2.5", SDB / "SDB5_OpenAQ_PM25.f64", SDB / "SDB5_OpenAQ_PM25.json", None, 400, 20, 1),
    ("NOAA USCRN", ROOT / "OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64", ROOT / "OPS-data-main9/02_weather_noaa_uscrn/metadata.json", None, 105_120, 5_256, 1),
    ("Kepler光通量", ROOT / "OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", ROOT / "OPS-data-main9/03_astronomy_kepler/metadata.json", None, 20_000, 1_000, 5),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", help="Run labels containing this text")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/reuse-hard-tuning/wopp-corresponding-params.json")
    args = parser.parse_args()
    cases = CASES
    if args.only:
        cases = tuple(c for c in cases if any(text.lower() in c[0].lower() for text in args.only))
    records = []
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        for index, (label, dataset, metadata, prefix, window, step, minsup) in enumerate(cases):
            output = temp / f"{index}.json"
            command = [sys.executable, str(RUNNER), "--dataset", str(dataset),
                       "--window", str(window), "--step", str(step),
                       "--minsup", str(minsup), "--output", str(output)]
            if metadata is not None:
                command += ["--metadata", str(metadata)]
            if prefix is not None:
                command += ["--prefix", str(prefix)]
            wall_started = time.perf_counter()
            try:
                subprocess.run(command, cwd=ROOT, check=True, capture_output=True,
                               text=True, timeout=args.timeout)
                result = json.loads(output.read_text())
                record = {"dataset": label, "status": "complete", **result}
                print(f"{label}: {result['elapsed_seconds']:.6f}s, "
                      f"{result['windows']} windows", flush=True)
            except subprocess.TimeoutExpired:
                elapsed = time.perf_counter() - wall_started
                record = {"dataset": label, "status": "timeout",
                          "timeout_seconds": args.timeout, "wall_seconds": elapsed,
                          "window": window, "step": step, "minsup": minsup}
                print(f"{label}: stopped after {elapsed:.1f}s", flush=True)
            records.append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
