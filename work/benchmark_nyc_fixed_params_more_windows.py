#!/usr/bin/env python3
"""Isolate window-count effects using longer prefixes of the full NYC stream."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64"
WINDOW = 10_000
STEP = 1_000
MINSUP = 5
WINDOW_COUNTS = (23, 50, 100, 200, 500)


def run(name: str, metadata: Path, output: Path):
    if name == "Original-Combined":
        command = [
            sys.executable, str(ROOT / "work/run_cached_fusion_ops_miner.py"),
            "--dataset", str(DATASET), "--metadata", str(metadata),
            "--window", str(WINDOW), "--step", str(STEP),
            "--minsup", str(MINSUP), "--output", str(output),
        ]
    else:
        command = [
            sys.executable, str(ROOT / "work/run_all_ops_algorithm.py"),
            "--algorithm", "OPS-NoReuse", "--dataset", str(DATASET),
            "--metadata", str(metadata), "--window", str(WINDOW),
            "--step", str(STEP), "--minsup", str(MINSUP),
            "--output", str(output),
        ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(output.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "outputs/NYC-reuse-fixed-params-more-windows.json",
    )
    args = parser.parse_args()
    records = []
    with tempfile.TemporaryDirectory() as temporary:
        temporary_dir = Path(temporary)
        for window_count in WINDOW_COUNTS:
            data_length = WINDOW + (window_count - 1) * STEP
            metadata = temporary_dir / f"metadata-{window_count}.json"
            metadata.write_text(json.dumps({
                "boundaries": [{"start": 0, "length": data_length}]
            }))
            timings = {"Original-Combined": [], "OPS-NoReuse": []}
            reference = None
            fusion_hit_rates = []
            for repetition in range(args.repetitions):
                order = list(timings)
                if repetition % 2:
                    order.reverse()
                for name in order:
                    result = run(
                        name, metadata,
                        temporary_dir / f"{window_count}-{name}-{repetition}.json",
                    )
                    timings[name].append(result["elapsed_seconds"])
                    observed = (result["windows"], result["patterns_total"])
                    if reference is None:
                        reference = observed
                    elif observed != reference:
                        raise RuntimeError(
                            f"result mismatch at {window_count}: {observed} != {reference}"
                        )
                    if name == "Original-Combined":
                        fusion_hit_rates.append(result["fusion_cache_hit_rate"])
            assert reference is not None
            reuse = statistics.median(timings["Original-Combined"])
            noreuse = statistics.median(timings["OPS-NoReuse"])
            record = {
                "data_length": data_length,
                "window": WINDOW,
                "step": STEP,
                "overlap": 0.9,
                "minsup": MINSUP,
                "windows": reference[0],
                "patterns_total": reference[1],
                "patterns_mean_per_window": reference[1] / reference[0],
                "repetitions": args.repetitions,
                "original_combined_seconds": timings["Original-Combined"],
                "noreuse_seconds": timings["OPS-NoReuse"],
                "original_combined_median_seconds": reuse,
                "noreuse_median_seconds": noreuse,
                "speedup": noreuse / reuse,
                "time_reduction_percent": (1 - reuse / noreuse) * 100,
                "fusion_cache_hit_rate_median": statistics.median(fusion_hit_rates),
            }
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
