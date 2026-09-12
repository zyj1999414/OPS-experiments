#!/usr/bin/env python3
import importlib.util
import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    "/Users/zyj/Library/Mobile Documents/com~apple~CloudDocs/Desktop/"
    "WOPP消融实验/WOPP- ablation-final/EFO-Miner.py"
)
DATASET = ROOT / "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64"
OUTPUT_DIR = ROOT / "outputs/original-efo-sdb4-first-window"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minsup", type=int, default=4)
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    window = np.asarray(np.memmap(DATASET, dtype="<f8", mode="r")[:16_000])

    spec = importlib.util.spec_from_file_location("original_efo_miner", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.read_file = lambda _path: window.tolist()

    started = time.perf_counter()
    miner = module.OPRMiner(
        file_path="MEMMAP_FIRST_WINDOW",
        output_filepath=str(OUTPUT_DIR),
        min_conf=0.4,
        min_sup=args.minsup,
    )
    miner.solve()
    elapsed = time.perf_counter() - started
    peak_rss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    record = {
        "algorithm": "EFO-Miner (original)",
        "dataset": "SDB4 Sleep-EDF EEG",
        "window_index": 1,
        "window_size": 16_000,
        "minsup": args.minsup,
        "frequent_patterns": int(miner.frequent_num),
        "candidate_patterns": int(miner.a + 2),
        "elapsed_seconds_including_initialization_and_output": elapsed,
        "peak_rss_mib": peak_rss_mib,
    }
    result_path = OUTPUT_DIR / f"result-minsup-{args.minsup}.json"
    result_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
