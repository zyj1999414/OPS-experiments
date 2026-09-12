#!/usr/bin/env python3
"""Exact conditional high-order reuse for sliding OPS mining.

A child level is updated incrementally only while its parent's frequent-ID set
is unchanged.  If that set changes, the child is rebuilt in one vectorized
pass; no occurrence sets or negative-border repair walks are maintained.
"""

import argparse
import json
import resource
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Level:
    length: int
    ring_ids: np.ndarray
    pattern_to_id: dict = field(default_factory=dict)
    id_to_pattern: list = field(default_factory=lambda: [None])
    counts: np.ndarray = field(default_factory=lambda: np.zeros(1, dtype=np.int64))
    frequent_ids: set = field(default_factory=set)
    # Stable parent IDs make this transition key safe across windows.
    transition_cache: dict = field(default_factory=dict)

    def ensure_pattern(self, pattern):
        pattern_id = self.pattern_to_id.get(pattern)
        if pattern_id is None:
            pattern_id = len(self.id_to_pattern)
            self.pattern_to_id[pattern] = pattern_id
            self.id_to_pattern.append(pattern)
            self.counts = np.append(self.counts, np.int64(0))
        return pattern_id


class ConditionalHighOrderReuseMiner:
    def __init__(self, window_size, step_size, min_sup):
        self.window_size = int(window_size)
        self.step_size = int(step_size)
        self.min_sup = int(min_sup)
        self.data = None
        self.left = 0
        self.right = -1
        self.levels = []
        self.full_rebuilds = 0
        self.incremental_updates = 0
        self.parent_frequency_changes = 0
        self.fusion_hits = 0
        self.fusion_misses = 0
        self.initial_seconds = 0.0
        self.slide_seconds = 0.0

    def _new_level(self, length):
        return Level(length, np.zeros(self.window_size, dtype=np.int32))

    @staticmethod
    def _fusion(p, q, relation):
        p1, qm = p[0], q[-1]
        if p1 < qm:
            r = [p1]
            r.extend(q)
            for i in range(1, len(r)):
                if r[i] >= r[0]:
                    r[i] += 1
            return tuple(r)
        if p1 > qm:
            r = [p1 + 1]
            r.extend(q)
            for i in range(1, len(r)):
                if r[i] >= r[0]:
                    r[i] += 1
            return tuple(r)
        if relation == 0:
            return None
        middle = [value if value < p1 else value + 1 for value in p[1:]]
        if relation == 1:
            return tuple([p1] + middle + [p1 + 1])
        return tuple([p1 + 1] + middle + [p1])

    def _frequent(self, level):
        return set(np.flatnonzero(level.counts >= self.min_sup).tolist()) - {0}

    def _build_l2(self):
        level = self._new_level(2)
        rising_id = level.ensure_pattern((1, 2))
        falling_id = level.ensure_pattern((2, 1))
        endpoints = np.arange(self.left + 1, self.right + 1, dtype=np.int64)
        left_values = self.data[endpoints - 1]
        right_values = self.data[endpoints]
        ids = np.where(left_values < right_values, rising_id,
                       np.where(left_values > right_values, falling_id, 0)).astype(np.int32)
        level.ring_ids[endpoints % self.window_size] = ids
        level.counts += np.bincount(ids, minlength=level.counts.size)[:level.counts.size]
        level.frequent_ids = self._frequent(level)
        self.levels = [level]

    def _candidate_ids(self, child, parent, endpoints):
        """Return one child pattern ID per endpoint; zero means no candidate."""
        if endpoints.size == 0:
            return np.empty(0, dtype=np.int32)
        prefix_ids = parent.ring_ids[(endpoints - 1) % self.window_size]
        suffix_ids = parent.ring_ids[endpoints % self.window_size]
        valid = (prefix_ids != 0) & (suffix_ids != 0)
        valid &= ((parent.counts[prefix_ids] >= self.min_sup)
                  & (parent.counts[suffix_ids] >= self.min_sup))
        result = np.zeros(endpoints.size, dtype=np.int32)
        if not np.any(valid):
            return result

        active_endpoints = endpoints[valid]
        pids = prefix_ids[valid].astype(np.int64, copy=False)
        qids = suffix_ids[valid].astype(np.int64, copy=False)
        begin = self.data[active_endpoints - child.length + 1]
        end = self.data[active_endpoints]
        relations = np.where(begin < end, 1, np.where(begin > end, 2, 0)).astype(np.int64)
        base = len(parent.id_to_pattern)
        event_keys = (pids * base + qids) * 3 + relations
        max_event_key = int(event_keys.max())
        dense_key_limit = min(4_000_000, int(event_keys.size) * 16)
        use_bincount = max_event_key <= dense_key_limit
        if use_bincount:
            unique_keys = np.flatnonzero(np.bincount(event_keys))
            inverse = None
        else:
            unique_keys, inverse = np.unique(event_keys, return_inverse=True)
        group_ids = np.zeros(unique_keys.size, dtype=np.int32)
        for group_index, raw_key in enumerate(unique_keys.tolist()):
            relation = raw_key % 3
            pair = raw_key // 3
            prefix_id, suffix_id = pair // base, pair % base
            transition = (prefix_id, suffix_id, relation)
            missing = object()
            child_id = child.transition_cache.get(transition, missing)
            if child_id is missing:
                candidate = self._fusion(parent.id_to_pattern[prefix_id],
                                         parent.id_to_pattern[suffix_id], relation)
                child_id = 0 if candidate is None else child.ensure_pattern(candidate)
                child.transition_cache[transition] = child_id
                self.fusion_misses += 1
            else:
                self.fusion_hits += 1
            group_ids[group_index] = child_id
        if use_bincount:
            key_to_child_id = np.zeros(max_event_key + 1, dtype=np.int32)
            key_to_child_id[unique_keys] = group_ids
            result[valid] = key_to_child_id[event_keys]
        else:
            result[valid] = group_ids[inverse]
        return result

    def _rebuild_child(self, child, parent):
        child.ring_ids.fill(0)
        child.counts.fill(0)
        endpoints = np.arange(self.left + child.length - 1,
                              self.right + 1, dtype=np.int64)
        ids = self._candidate_ids(child, parent, endpoints)
        child.ring_ids[endpoints % self.window_size] = ids
        if child.counts.size:
            child.counts += np.bincount(ids, minlength=child.counts.size)[:child.counts.size]
        child.frequent_ids = self._frequent(child)
        self.full_rebuilds += 1

    def _increment_child(self, child, parent, old_left, old_right):
        leaving = np.arange(old_left + child.length - 1,
                            self.left + child.length - 1, dtype=np.int64)
        leaving_slots = leaving % self.window_size
        leaving_ids = child.ring_ids[leaving_slots]
        removed = np.bincount(leaving_ids, minlength=child.counts.size)
        removed[0] = 0
        child.counts -= removed[:child.counts.size]
        child.ring_ids[leaving_slots] = 0

        entering = np.arange(old_right + 1, self.right + 1, dtype=np.int64)
        ids = self._candidate_ids(child, parent, entering)
        child.ring_ids[entering % self.window_size] = ids
        added = np.bincount(ids, minlength=child.counts.size)
        added[0] = 0
        child.counts += added[:child.counts.size]
        child.frequent_ids = self._frequent(child)
        self.incremental_updates += 1

    def _patterns(self):
        result = []
        for level in self.levels:
            if not level.frequent_ids:
                break
            result.append({level.id_to_pattern[i]: int(level.counts[i])
                           for i in level.frequent_ids})
        return result

    def fit(self, values):
        started = time.perf_counter()
        self.data = values
        if len(values) < self.window_size:
            raise ValueError("data shorter than window")
        self.left, self.right = 0, self.window_size - 1
        self._build_l2()
        while self.levels[-1].frequent_ids:
            parent = self.levels[-1]
            child = self._new_level(parent.length + 1)
            self._rebuild_child(child, parent)
            self.levels.append(child)
            if not child.frequent_ids:
                break
        self.initial_seconds = time.perf_counter() - started
        return self._patterns()

    def _update_l2(self, old_left, old_right):
        level = self.levels[0]
        old_frequent = level.frequent_ids
        leaving = np.arange(old_left + 1, self.left + 1, dtype=np.int64)
        slots = leaving % self.window_size
        leaving_ids = level.ring_ids[slots]
        removed = np.bincount(leaving_ids, minlength=level.counts.size)
        removed[0] = 0
        level.counts -= removed[:level.counts.size]
        level.ring_ids[slots] = 0
        endpoints = np.arange(old_right + 1, self.right + 1, dtype=np.int64)
        left_values = self.data[endpoints - 1]
        right_values = self.data[endpoints]
        rising_id = level.pattern_to_id[(1, 2)]
        falling_id = level.pattern_to_id[(2, 1)]
        ids = np.where(left_values < right_values, rising_id,
                       np.where(left_values > right_values, falling_id, 0)).astype(np.int32)
        level.ring_ids[endpoints % self.window_size] = ids
        added = np.bincount(ids, minlength=level.counts.size)
        added[0] = 0
        level.counts += added[:level.counts.size]
        level.frequent_ids = self._frequent(level)
        return level.frequent_ids != old_frequent

    def slide(self):
        if self.right + self.step_size >= len(self.data):
            return None
        started = time.perf_counter()
        old_left, old_right = self.left, self.right
        self.left += self.step_size
        self.right += self.step_size
        parent_changed = self._update_l2(old_left, old_right)
        if parent_changed:
            self.parent_frequency_changes += 1

        level_index = 1
        while self.levels[level_index - 1].frequent_ids:
            parent = self.levels[level_index - 1]
            if level_index == len(self.levels):
                child = self._new_level(parent.length + 1)
                self.levels.append(child)
                rebuild = True
            else:
                child = self.levels[level_index]
                rebuild = parent_changed
            old_frequent = child.frequent_ids
            if rebuild:
                self._rebuild_child(child, parent)
            else:
                self._increment_child(child, parent, old_left, old_right)
            child_changed = child.frequent_ids != old_frequent
            if child_changed:
                self.parent_frequency_changes += 1
            parent_changed = child_changed
            level_index += 1
            if not child.frequent_ids:
                break
        if len(self.levels) > level_index:
            del self.levels[level_index:]
        self.slide_seconds += time.perf_counter() - started
        return self._patterns()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--window", type=int, required=True)
    p.add_argument("--step", type=int, required=True)
    p.add_argument("--minsup", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    values = np.memmap(a.dataset, dtype="<f8", mode="r")
    miner = ConditionalHighOrderReuseMiner(a.window, a.step, a.minsup)
    started = time.perf_counter()
    result = miner.fit(values)
    windows, patterns_total = 1, sum(map(len, result))
    while True:
        result = miner.slide()
        if result is None:
            break
        windows += 1
        patterns_total += sum(map(len, result))
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
    summary = {
        "algorithm": "OPS-ConditionalHighOrderReuse", "dataset": str(a.dataset),
        "data_length": len(values), "window": a.window, "step": a.step,
        "minsup": a.minsup, "windows": windows,
        "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows,
        "elapsed_seconds": elapsed, "peak_rss_mib": peak,
        "initial_seconds": miner.initial_seconds,
        "slide_seconds": miner.slide_seconds,
        "full_level_rebuilds": miner.full_rebuilds,
        "incremental_level_updates": miner.incremental_updates,
        "frequency_set_changes": miner.parent_frequency_changes,
        "fusion_cache_hits": miner.fusion_hits,
        "fusion_cache_misses": miner.fusion_misses,
        "levels_retained": len(miner.levels),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
