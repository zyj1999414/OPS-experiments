#!/usr/bin/env python3
"""Profile the six required PIS2 reuse operations separately."""

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

SOURCE = Path("/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/OPS-ablation/OPS-Miner.py")
NAMES = (
    "reuse_overlap_pis2",
    "remove_leaving_counts",
    "scan_arriving_positions",
    "add_arriving_counts",
    "zero_window_first_id",
    "filter_ids_by_minsup",
)

spec = importlib.util.spec_from_file_location("ops_profile_source", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProfiledMiner(module.L2IncrementalPPCNewsup):
    def __init__(self, *args):
        super().__init__(*args)
        self.reuse_ns = {name: 0 for name in NAMES}
        self.reuse_updates = 0
        self.higher_order_ns = 0
        self.initial_pis2_ns = 0

    def _find_m(self, *args, **kwargs):
        started = time.perf_counter_ns()
        result = super()._find_m(*args, **kwargs)
        self.higher_order_ns += time.perf_counter_ns() - started
        return result

    def find2(self, values=None):
        first = not hasattr(self, "length_two_ids") or self.length_two_ids.size == 0
        if first:
            higher_before = self.higher_order_ns
            started = time.perf_counter_ns()
            result = super().find2(values)
            elapsed = time.perf_counter_ns() - started
            self.initial_pis2_ns += elapsed - (self.higher_order_ns - higher_before)
            return result
        if self.right + self.step_size >= self.data.size:
            return None

        self.reuse_updates += 1
        old_left, old_right = self.left, self.right
        new_left = old_left + self.step_size
        new_right = old_right + self.step_size

        t = time.perf_counter_ns()
        leaving_ids = self.length_two_ids[old_left + 1:new_left + 1]
        removed = np.bincount(leaving_ids, minlength=3)
        self.length_two_counts[1:3] -= removed[1:3]
        self.reuse_ns["remove_leaving_counts"] += time.perf_counter_ns() - t

        t = time.perf_counter_ns()
        start, stop = old_right + 1, new_right + 1
        left_values = self.data[start - 1:stop - 1]
        right_values = self.data[start:stop]
        ids = np.where(left_values < right_values, 1,
                       np.where(left_values > right_values, 2, 0)).astype(np.int32, copy=False)
        self.length_two_ids[start:stop] = ids
        self.reuse_ns["scan_arriving_positions"] += time.perf_counter_ns() - t

        t = time.perf_counter_ns()
        added = np.bincount(ids, minlength=3)
        self.length_two_counts[1:3] += added[1:3]
        self.reuse_ns["add_arriving_counts"] += time.perf_counter_ns() - t

        self.left, self.right = new_left, new_right
        miner_data = self.data[self.left:self.right + 1]

        t = time.perf_counter_ns()
        position_ids = self.length_two_ids[self.left:self.right + 1]
        self.reuse_ns["reuse_overlap_pis2"] += time.perf_counter_ns() - t

        t = time.perf_counter_ns()
        boundary_id = int(position_ids[0])
        position_ids[0] = 0
        self.reuse_ns["zero_window_first_id"] += time.perf_counter_ns() - t

        t = time.perf_counter_ns()
        f2 = {}
        if self.length_two_counts[1] >= self.min_sup:
            f2[(1, 2)] = int(self.length_two_counts[1])
        if self.length_two_counts[2] >= self.min_sup:
            f2[(2, 1)] = int(self.length_two_counts[2])
        if len(f2) != 2:
            active_ids = position_ids.copy()
            keep = np.zeros(3, dtype=bool)
            keep[1] = self.length_two_counts[1] >= self.min_sup
            keep[2] = self.length_two_counts[2] >= self.min_sup
            active_ids[~keep[active_ids]] = 0
        else:
            active_ids = position_ids
        self.reuse_ns["filter_ids_by_minsup"] += time.perf_counter_ns() - t

        old_data = self.data
        self.data = miner_data
        result = self._find_m(f2, active_ids, [None, (1, 2), (2, 1)])
        self.data = old_data
        position_ids[0] = boundary_id
        return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--window", type=int, required=True)
    p.add_argument("--step", type=int, required=True)
    p.add_argument("--minsup", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    values = np.memmap(a.dataset, dtype="<f8", mode="r")
    metadata = json.loads(a.metadata.read_text())
    boundaries = metadata.get("boundaries") or [{"start": 0, "length": len(values)}]
    aggregate = {name: 0 for name in NAMES}
    updates = windows = patterns_total = 0
    higher_order_ns = initial_pis2_ns = 0
    total_start = time.perf_counter()
    for boundary in boundaries:
        start, length = int(boundary["start"]), int(boundary["length"])
        if length < a.window:
            continue
        miner = ProfiledMiner(a.window, a.step, a.minsup)
        result = miner.find2(values[start:start + length])
        if result is None:
            continue
        windows += 1
        patterns_total += sum(map(len, result))
        while True:
            result = miner.find2()
            if result is None:
                break
            windows += 1
            patterns_total += sum(map(len, result))
        updates += miner.reuse_updates
        higher_order_ns += miner.higher_order_ns
        initial_pis2_ns += miner.initial_pis2_ns
        for name in NAMES:
            aggregate[name] += miner.reuse_ns[name]

    elapsed_seconds = time.perf_counter() - total_start
    total_ns = sum(aggregate.values())
    summary = {
        "dataset": str(a.dataset), "window": a.window, "step": a.step,
        "minsup": a.minsup, "windows": windows, "reuse_updates": updates,
        "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows if windows else None,
        "elapsed_seconds": elapsed_seconds,
        "component_total_ms": {k: v / 1e6 for k, v in aggregate.items()},
        "component_mean_ms_per_update": {k: v / updates / 1e6 for k, v in aggregate.items()},
        "reuse_total_ms": total_ns / 1e6,
        "reuse_mean_ms_per_update": total_ns / updates / 1e6,
        "initial_pis2_total_ms": initial_pis2_ns / 1e6,
        "higher_order_total_ms": higher_order_ns / 1e6,
        "profiled_core_total_ms": (initial_pis2_ns + total_ns + higher_order_ns) / 1e6,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
