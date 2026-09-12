#!/usr/bin/env python3
import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "EFO-Miner": ROOT / "algorithms/EFO-Miner.py",
    "SOPP-Miner": ROOT / "algorithms/SOPP-Miner.py",
}
DATASETS = {
    "SDB1": (ROOT.parent / "data/SDB1/SDB1_GOOG.f64", 1_000),
    "SDB2": (ROOT.parent / "data/SDB2/05_physics_ligo_128MiB.f64", 4_422),
    "SDB3": (ROOT.parent / "data/SDB3/01_industrial_cwru_800KB.f64", 15_000),
    "SDB4": (ROOT.parent / "data/SDB4/04_biomedical_sleep_edf_approx64MiB.f64", 16_000),
    "SDB5": (ROOT.parent / "data/SDB5/02_weather_noaa_uscrn_4MiB.f64", 50_000),
    "SDB6": (ROOT.parent / "data/SDB6/03_astronomy_kepler_approx16MiB.f64", 20_000),
    "SDB7": (ROOT.parent / "data/SDB7/05_transport_nyc_tlc_640MiB.f64", 60_000),
    "SDB8": (ROOT.parent / "data/SDB8/06_power_blond250_256MiB.f64", 40_000),
}


def load_module(algorithm):
    spec = importlib.util.spec_from_file_location("original_" + algorithm.lower().replace("-", "_"), SOURCES[algorithm])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--algorithm", choices=SOURCES, required=True)
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--window-size", type=int)
    parser.add_argument("--minsup", type=int, default=8)
    args = parser.parse_args()

    path, window_size = DATASETS[args.dataset]
    if args.window_size is not None:
        window_size = args.window_size
    window = np.asarray(np.memmap(path, dtype="<f8", mode="r")[:window_size]).tolist()
    out_dir = ROOT / "outputs/original-efo-sopp-first-windows" / args.algorithm / args.dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    module = load_module(args.algorithm)

    if args.algorithm == "EFO-Miner":
        module.read_file = lambda _path: window
        miner = module.OPRMiner("MEMMAP_FIRST_WINDOW", str(out_dir), min_conf=0.4, min_sup=args.minsup)
        started = time.perf_counter()
        miner.solve()
        frequent = int(miner.frequent_num)
        candidates = int(miner.a + 2)
    else:
        module.T = [0, *window]
        module.T_size = window_size
        module.output_filename = "SOPP-Miner-Output.txt"
        miner = module.NEFOMiner("MEMMAP_FIRST_WINDOW", str(out_dir), args.minsup)
        started = time.perf_counter()
        miner.FOP_miner()
        frequent = int(sum(len(level) for level in miner.Flist))
        candidates = int(module.cand_cnt)

    elapsed = time.perf_counter() - started
    peak_rss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    record = {
        "algorithm": args.algorithm,
        "dataset": args.dataset,
        "window_index": 1,
        "window_size": window_size,
        "minsup": args.minsup,
        "elapsed_seconds": elapsed,
        "peak_rss_mib": peak_rss_mib,
        "frequent_patterns": frequent,
        "candidate_patterns": candidates,
    }
    result = out_dir / f"result-w{window_size}-minsup{args.minsup}.json"
    result.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
