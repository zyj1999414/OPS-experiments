#!/usr/bin/env python3
"""Mutually exclusive phase timing for combined-reuse higher-order PIS builds."""

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

SOURCE = Path(__file__).with_name("run_cached_fusion_ops_miner.py")
spec = importlib.util.spec_from_file_location("cached_fusion_runner", SOURCE)
cached = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cached)

PHASES = ("allocate_next_pis", "extract_valid", "extract_tbegin_tend_C",
          "generate_event", "group_and_count", "fusion_lookup",
          "build_pattern_id_table", "map_and_write_next_pis")


class PhaseMiner(cached.ScanAndFusionReuseMiner):
    def __init__(self, *args):
        super().__init__(*args)
        self.phase_ns = {name: 0 for name in PHASES}

    def _mark(self, name, started):
        self.phase_ns[name] += time.perf_counter_ns() - started

    def _build_next_level(self, pattern_length, current_ids, id_to_pattern):
        t = time.perf_counter_ns()
        data_size = self.data.size
        next_ids = np.zeros(data_size, dtype=np.int32)
        self._mark("allocate_next_pis", t)

        t = time.perf_counter_ns()
        prefix_ids = current_ids[:-1]
        suffix_ids = current_ids[1:]
        valid = (prefix_ids != 0) & (suffix_ids != 0)
        aligned_indices = np.flatnonzero(valid)
        self._mark("extract_valid", t)
        if aligned_indices.size == 0:
            return {}, next_ids, [None]

        t = time.perf_counter_ns()
        endpoints = aligned_indices + 1
        starts = endpoints - pattern_length
        tbegin = self.data[starts]
        tend = self.data[endpoints]
        relations = np.where(tbegin < tend, 1, np.where(tbegin > tend, 2, 0)).astype(np.int64, copy=False)
        self._mark("extract_tbegin_tend_C", t)

        t = time.perf_counter_ns()
        active_prefix_ids = prefix_ids[aligned_indices].astype(np.int64, copy=False)
        active_suffix_ids = suffix_ids[aligned_indices].astype(np.int64, copy=False)
        id_base = len(id_to_pattern)
        event_keys = (active_prefix_ids * id_base + active_suffix_ids) * 3 + relations
        self._mark("generate_event", t)

        t = time.perf_counter_ns()
        max_event_key = int(event_keys.max())
        dense_key_limit = min(4_000_000, int(event_keys.size) * 16)
        use_bincount = max_event_key <= dense_key_limit
        if use_bincount:
            counts_by_key = np.bincount(event_keys)
            unique_keys = np.flatnonzero(counts_by_key)
            counts = counts_by_key[unique_keys]
            inverse = None
        else:
            unique_keys, inverse, counts = np.unique(event_keys, return_inverse=True, return_counts=True)
        frequent_group_indices = np.flatnonzero(counts >= self.min_sup)
        self._mark("group_and_count", t)

        t = time.perf_counter_ns()
        candidate_for_group = [None] * unique_keys.size
        frequent_patterns = {}
        for group_index in frequent_group_indices.tolist():
            event_key = int(unique_keys[group_index])
            relation = event_key % 3
            pair_key = event_key // 3
            prefix_id = pair_key // id_base
            suffix_id = pair_key % id_base
            candidate = self.frequent_pattern_fusion(id_to_pattern[prefix_id], id_to_pattern[suffix_id], relation)
            candidate_for_group[group_index] = candidate
            if candidate is not None:
                frequent_patterns[candidate] = int(counts[group_index])
        self._mark("fusion_lookup", t)

        t = time.perf_counter_ns()
        next_id_to_pattern = [None]
        pattern_to_next_id = {}
        for pattern in frequent_patterns:
            pattern_to_next_id[pattern] = len(next_id_to_pattern)
            next_id_to_pattern.append(pattern)
        group_to_next_id = np.zeros(unique_keys.size, dtype=np.int32)
        for group_index, candidate in enumerate(candidate_for_group):
            if candidate is not None:
                group_to_next_id[group_index] = pattern_to_next_id.get(candidate, 0)
        self._mark("build_pattern_id_table", t)

        t = time.perf_counter_ns()
        if use_bincount:
            key_to_next_id = np.zeros(max_event_key + 1, dtype=np.int32)
            key_to_next_id[unique_keys] = group_to_next_id
            next_ids[endpoints] = key_to_next_id[event_keys]
        else:
            next_ids[endpoints] = group_to_next_id[inverse]
        self._mark("map_and_write_next_pis", t)
        return frequent_patterns, next_ids, next_id_to_pattern


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--window", type=int, required=True)
    p.add_argument("--step", type=int, required=True)
    p.add_argument("--minsup", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    values = np.memmap(a.dataset, dtype="<f8", mode="r")
    miner = PhaseMiner(a.window, a.step, a.minsup)
    started = time.perf_counter()
    result = miner.find2(values)
    windows = 0
    patterns_total = 0
    while result is not None:
        windows += 1
        patterns_total += sum(map(len, result))
        result = miner.find2()
    elapsed = time.perf_counter() - started
    phase_ms = {k: v / 1e6 for k, v in miner.phase_ns.items()}
    build_ms = sum(phase_ms.values())
    out = {"elapsed_seconds": elapsed, "windows": windows,
           "patterns_total": patterns_total, "build_total_ms": build_ms,
           "phase_ms": phase_ms,
           "phase_percent_of_build": {k: v / build_ms * 100 for k, v in phase_ms.items()},
           "phase_percent_of_elapsed": {k: v / (elapsed * 1000) * 100 for k, v in phase_ms.items()},
           "fusion_cache_hits": miner.fusion_cache_hits,
           "fusion_cache_misses": miner.fusion_cache_misses}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
