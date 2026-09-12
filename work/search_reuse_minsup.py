#!/usr/bin/env python3
"""Screen minsup values for Original-Combined versus OPS-NoReuse."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("NYC", "OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64", None, 10_000, 1_000, 5, 509_000),
    ("CWRU", "OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64", "OPS-data-main9/01_industrial_cwru/metadata.json", 30_000, 3_000, 15, None),
    ("NOAA", "OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64", "OPS-data-main9/02_weather_noaa_uscrn/metadata.json", 105_120, 10_512, 53, None),
    ("Kepler", "OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", "OPS-data-main9/03_astronomy_kepler/metadata.json", 100_000, 10_000, 50, None),
    ("Sleep", "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", "OPS-data-main9/04_biomedical_sleep_edf/metadata.json", 500_000, 50_000, 250, None),
    ("LIGO", "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", "OPS-data-main9/05_physics_ligo/metadata.json", 2_000_000, 200_000, 1_000, None),
    ("BLOND", "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", "OPS-data-main9/06_power_blond250/metadata.json", 5_000_000, 500_000, 2_500, None),
)
MULTIPLIERS = (1, 2, 4, 10, 20)


def command(name, dataset, metadata, window, step, minsup, output):
    common = ["--dataset", str(dataset), "--metadata", str(metadata),
              "--window", str(window), "--step", str(step),
              "--minsup", str(minsup), "--output", str(output)]
    if name == "Original-Combined":
        return [sys.executable, str(ROOT / "work/run_cached_fusion_ops_miner.py"), *common]
    return [sys.executable, str(ROOT / "work/run_all_ops_algorithm.py"),
            "--algorithm", "OPS-NoReuse", *common]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=[x[0] for x in CASES])
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/reuse-minsup-search.json")
    args = parser.parse_args()
    cases = [x for x in CASES if args.dataset in (None, x[0])]
    records = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for label, dataset_rel, metadata_rel, window, step, base, prefix in cases:
            dataset = ROOT / dataset_rel
            if prefix is not None:
                metadata = tmp / f"{label}-metadata.json"
                metadata.write_text(json.dumps({"boundaries": [{"start": 0, "length": prefix}]}))
            else:
                metadata = ROOT / metadata_rel
            for multiplier in MULTIPLIERS:
                minsup = base * multiplier
                results = {}
                for name in ("Original-Combined", "OPS-NoReuse"):
                    output = tmp / f"{label}-{minsup}-{name}.json"
                    try:
                        subprocess.run(
                            command(name, dataset, metadata, window, step, minsup, output),
                            cwd=ROOT, check=True, capture_output=True, text=True,
                            timeout=args.timeout,
                        )
                        results[name] = json.loads(output.read_text())
                    except subprocess.TimeoutExpired:
                        results[name] = {"status": "timeout"}
                record = {"dataset": label, "window": window, "step": step,
                          "minsup": minsup, "minsup_multiplier": multiplier,
                          "results": results}
                if all("elapsed_seconds" in x for x in results.values()):
                    reuse = results["Original-Combined"]["elapsed_seconds"]
                    noreuse = results["OPS-NoReuse"]["elapsed_seconds"]
                    record.update({
                        "windows": results["Original-Combined"]["windows"],
                        "patterns_mean": results["Original-Combined"]["patterns_mean_per_window"],
                        "reuse_seconds": reuse, "noreuse_seconds": noreuse,
                        "speedup": noreuse / reuse,
                    })
                records.append(record)
                print(json.dumps(record, ensure_ascii=False), flush=True)
    existing = []
    if args.output.exists():
        try:
            existing = json.loads(args.output.read_text())
        except Exception:
            pass
    labels = {x[0] for x in cases}
    existing = [x for x in existing if x.get("dataset") not in labels]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(existing + records, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
