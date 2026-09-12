"""Position-driven order-preserving pattern miner.

This module keeps WOPPclean's complete-series, absolute-minsup semantics, but
transposes its support representation:

    WOPPclean: pattern -> occurrence bitarray
    Newsup:    ending position -> pattern ID

At each pattern length, Newsup aligns the pattern-ID array with a one-position
shift, groups all observed (prefix ID, suffix ID, endpoint relation) keys in
one NumPy pass, and obtains candidate supports from the group counts.  The
original WOPPclean.py is not modified.
"""

import argparse
import time
from collections import defaultdict

import numpy as np


class NewsupMiner:
    """Mine frequent OPPs with one position-grouping pass per pattern length."""

    def __init__(self, min_sup=5):
        self.min_sup = min_sup
        self.data = np.empty(0, dtype=np.float64)
        self.level_counts = []
        self.patterns_by_level = []

        # The current level's horizontal representation.  A zero means that
        # no frequent pattern of the current length ends at that position.
        self.position_pattern_ids = np.empty(0, dtype=np.int32)
        self.id_to_pattern = [None]

        self.candidate_generated_count = 0
        self.candidate_checked_count = 2
        self.fusion_count = 0
        self.support_calc_count = 0
        self.position_check_count = 0
        self.bincount_level_count = 0
        self.unique_level_count = 0
        self.operation = 0
        self.runtime = 0.0

    def reset_stats(self):
        self.candidate_generated_count = 0
        self.candidate_checked_count = 2
        self.fusion_count = 0
        self.support_calc_count = 0
        self.position_check_count = 0
        self.bincount_level_count = 0
        self.unique_level_count = 0
        self.operation = 0
        self.runtime = 0.0

    @staticmethod
    def fuse_patterns(p, q):
        """Copy WOPPclean's complete order-preserving fusion rule."""
        p1 = p[0]
        qm = q[-1]
        candidates = []

        if p1 != qm:
            r = [p[0] if p[0] < qm else p[0] + 1]
            r.extend(q)
            for i in range(1, len(r)):
                if r[i] >= r[0]:
                    r[i] += 1
            candidates.append(tuple(r))
        else:
            r = list(p) + [qm]
            h = list(p) + [qm]
            for i in range(1, len(r)):
                if r[i] > r[0]:
                    r[i] += 1
                if h[i] > h[0]:
                    h[i] += 1
            r[-1] += 1
            h[0] += 1
            candidates.extend((tuple(r), tuple(h)))

        return candidates

    def find_2(self):
        """Create the length-2 support table and position-to-pattern IDs."""
        data_size = self.data.size
        position_ids = np.zeros(data_size, dtype=np.int32)
        if data_size < 2:
            return {}, position_ids, [None]

        rising = self.data[:-1] < self.data[1:]
        falling = self.data[:-1] > self.data[1:]
        rising_support = int(np.count_nonzero(rising))
        falling_support = int(np.count_nonzero(falling))
        self.position_check_count += data_size - 1
        self.operation += data_size - 1

        patterns = {}
        id_to_pattern = [None]

        if rising_support >= self.min_sup:
            pattern = (1, 2)
            pattern_id = len(id_to_pattern)
            patterns[pattern] = rising_support
            id_to_pattern.append(pattern)
            position_ids[np.flatnonzero(rising) + 1] = pattern_id

        if falling_support >= self.min_sup:
            pattern = (2, 1)
            pattern_id = len(id_to_pattern)
            patterns[pattern] = falling_support
            id_to_pattern.append(pattern)
            position_ids[np.flatnonzero(falling) + 1] = pattern_id

        return patterns, position_ids, id_to_pattern

    @staticmethod
    def _select_fused_candidate(candidates, relation):
        """Select the unique candidate represented by an observed endpoint relation.

        relation is 1 when the first value is smaller than the last value, 2
        when it is greater, and 0 for a tie.  A tie invalidates the ambiguous
        two-candidate fusion, exactly as in WOPPclean.cal_occ_2().
        """
        if len(candidates) == 1:
            return candidates[0]
        if relation == 0:
            return None
        if relation == 1:
            return next(candidate for candidate in candidates if candidate[0] < candidate[-1])
        return next(candidate for candidate in candidates if candidate[0] > candidate[-1])

    def _build_next_level(self, pattern_length, current_ids, id_to_pattern):
        """Group all observed length-(k+1) candidates in one aligned pass."""
        data_size = self.data.size
        next_ids = np.zeros(data_size, dtype=np.int32)
        if data_size <= pattern_length:
            return {}, next_ids, [None]

        # current_ids[:-1] identifies the k-pattern ending one position before
        # current_ids[1:].  Their overlap describes one (k+1)-window.
        prefix_ids = current_ids[:-1]
        suffix_ids = current_ids[1:]
        valid = (prefix_ids != 0) & (suffix_ids != 0)
        aligned_indices = np.flatnonzero(valid)
        if aligned_indices.size == 0:
            return {}, next_ids, [None]

        endpoints = aligned_indices + 1
        starts = endpoints - pattern_length
        begin_values = self.data[starts]
        end_values = self.data[endpoints]
        relations = np.where(
            begin_values < end_values,
            1,
            np.where(begin_values > end_values, 2, 0),
        ).astype(np.int64, copy=False)

        active_prefix_ids = prefix_ids[aligned_indices].astype(np.int64, copy=False)
        active_suffix_ids = suffix_ids[aligned_indices].astype(np.int64, copy=False)
        id_base = len(id_to_pattern)

        # An event key uniquely describes the two subpatterns and, only for
        # ambiguous r/h fusion, which endpoint-order branch was observed.
        event_keys = (
            (active_prefix_ids * id_base + active_suffix_ids) * 3 + relations
        )
        # np.unique sorts all keys.  When IDs form a compact key space,
        # bincount is a faster linear counting pass and also lets us map keys
        # to next-level IDs without constructing an inverse array.  For a
        # sparse/large key space, unique avoids a potentially huge dense table.
        max_event_key = int(event_keys.max())
        dense_key_limit = min(4_000_000, int(event_keys.size) * 16)
        use_bincount = max_event_key <= dense_key_limit
        if use_bincount:
            counts_by_key = np.bincount(event_keys)
            unique_keys = np.flatnonzero(counts_by_key)
            counts = counts_by_key[unique_keys]
            inverse = None
            self.bincount_level_count += 1
        else:
            unique_keys, inverse, counts = np.unique(
                event_keys, return_inverse=True, return_counts=True
            )
            self.unique_level_count += 1

        self.support_calc_count += 1
        self.position_check_count += int(aligned_indices.size)
        self.operation += int(aligned_indices.size)

        candidate_for_group = []
        candidate_supports = defaultdict(int)
        fusion_cache = {}

        for group_index, event_key in enumerate(unique_keys.tolist()):
            relation = event_key % 3
            pair_key = event_key // 3
            prefix_id = pair_key // id_base
            suffix_id = pair_key % id_base
            pair = (prefix_id, suffix_id)

            if pair not in fusion_cache:
                p = id_to_pattern[prefix_id]
                q = id_to_pattern[suffix_id]
                candidates = self.fuse_patterns(p, q)
                fusion_cache[pair] = candidates
                self.fusion_count += len(candidates)
                self.candidate_checked_count += len(candidates)

            candidate = self._select_fused_candidate(
                fusion_cache[pair], relation
            )
            candidate_for_group.append(candidate)
            if candidate is not None:
                candidate_supports[candidate] += int(counts[group_index])

        self.candidate_generated_count += len(candidate_supports)

        frequent_patterns = {
            pattern: support
            for pattern, support in candidate_supports.items()
            if support >= self.min_sup
        }
        if not frequent_patterns:
            return {}, next_ids, [None]

        next_id_to_pattern = [None]
        pattern_to_next_id = {}
        for pattern in frequent_patterns:
            pattern_to_next_id[pattern] = len(next_id_to_pattern)
            next_id_to_pattern.append(pattern)

        group_to_next_id = np.zeros(unique_keys.size, dtype=np.int32)
        for group_index, candidate in enumerate(candidate_for_group):
            if candidate is not None:
                group_to_next_id[group_index] = pattern_to_next_id.get(candidate, 0)

        if use_bincount:
            key_to_next_id = np.zeros(max_event_key + 1, dtype=np.int32)
            key_to_next_id[unique_keys] = group_to_next_id
            next_ids[endpoints] = key_to_next_id[event_keys]
        else:
            next_ids[endpoints] = group_to_next_id[inverse]
        return frequent_patterns, next_ids, next_id_to_pattern

    def find_m(self, f2, position_ids, id_to_pattern):
        """Grow patterns while retaining only one horizontal ID array."""
        current_patterns = f2
        current_ids = position_ids
        current_id_to_pattern = id_to_pattern
        self.level_counts = []
        self.patterns_by_level = []

        while current_patterns:
            self.level_counts.append(len(current_patterns))
            self.patterns_by_level.append(dict(current_patterns))

            pattern_length = len(next(iter(current_patterns)))
            next_patterns, next_ids, next_id_to_pattern = self._build_next_level(
                pattern_length, current_ids, current_id_to_pattern
            )
            if not next_patterns:
                break

            current_patterns = next_patterns
            current_ids = next_ids
            current_id_to_pattern = next_id_to_pattern

        self.position_pattern_ids = current_ids
        self.id_to_pattern = current_id_to_pattern
        return self.patterns_by_level

    def mine(self, values):
        """Mine one complete sequence using one absolute minsup threshold."""
        T1=time.time()
        self.reset_stats()
        self.level_counts = []
        self.patterns_by_level = []

        start = time.perf_counter()
        self.data = np.asarray(values, dtype=np.float64)
        f2, position_ids, id_to_pattern = self.find_2()
        patterns = self.find_m(f2, position_ids, id_to_pattern)
        self.runtime = time.perf_counter() - start
        T2=time.time()
        print("Execution runtime:",T2-T1)
        return patterns

    def stats(self):
        return {
            "level_counts": self.level_counts.copy(),
            "total_frequent_patterns": sum(self.level_counts),
            "candidate_generated_count": self.candidate_generated_count,
            "candidate_checked_count": self.candidate_checked_count,
            "fusion_count": self.fusion_count,
            "support_calc_count": self.support_calc_count,
            "position_check_count": self.position_check_count,
            "bincount_level_count": self.bincount_level_count,
            "unique_level_count": self.unique_level_count,
            "new_sup_runtime": self.runtime,
            "operation": self.operation,
        }


# A compatibility alias for scripts that import a miner named WOPPMiner.
WOPPMiner = NewsupMiner


def read_numeric_series(file_name):
    data = []
    with open(file_name, "r", encoding="utf-8") as stream:
        for line in stream:
            for token in line.replace(",", " ").split():
                try:
                    data.append(float(token))
                except ValueError:
                    continue
    return data


def _support_map(patterns_by_level):
    return {
        pattern: int(support)
        for level in patterns_by_level
        for pattern, support in level.items()
    }


def main():
    parser = argparse.ArgumentParser(
        description="Position-driven WOPP support miner"
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        default="/Users/zyj/Downloads/AAPL.txt",
        help="Path to a numeric time series",
    )
    parser.add_argument("--min-sup", "--minsup", type=int, default=5)
    parser.add_argument(
        "--compare-wopp",
        action="store_true",
        help="compare patterns, supports, and runtime with WOPPclean",
    )
    args = parser.parse_args()

    data = read_numeric_series(args.dataset)
    if not data:
        raise ValueError(f"No numeric values read from {args.dataset}")

    miner = NewsupMiner(min_sup=args.min_sup)
    patterns = miner.mine(data)
    print(f"Data count: {len(data)}")
    print(f"Level counts: {miner.level_counts}")
    print(f"Total frequent patterns: {sum(miner.level_counts)}")
    print(f"Stats: {miner.stats()}")

    # if args.compare_wopp:
    #     from WOPPclean import WOPPMiner as BaselineWOPPMiner

    #     baseline = BaselineWOPPMiner(min_sup=args.min_sup)
    #     baseline_patterns = baseline.mine(data)
    #     baseline_supports = {
    #         pattern: occurrences.count(1)
    #         for level in baseline_patterns
    #         for pattern, occurrences in level.items()
    #     }
    #     newsup_supports = _support_map(patterns)

    #     missing = sorted(baseline_supports.keys() - newsup_supports.keys())
    #     extra = sorted(newsup_supports.keys() - baseline_supports.keys())
    #     support_mismatches = sorted(
    #         (
    #             pattern,
    #             baseline_supports[pattern],
    #             newsup_supports[pattern],
    #         )
    #         for pattern in baseline_supports.keys() & newsup_supports.keys()
    #         if baseline_supports[pattern] != newsup_supports[pattern]
    #     )

        # print("Comparison with WOPPclean:")
        # print(f"  WOPPclean patterns: {len(baseline_supports)}")
        # print(f"  Newsup patterns: {len(newsup_supports)}")
        # print(f"  Missing patterns: {len(missing)}")
        # print(f"  Extra patterns: {len(extra)}")
        # print(f"  Support mismatches: {len(support_mismatches)}")
        # print(f"  WOPPclean runtime: {baseline.runtime:.9f}s")
        # print(f"  Newsup runtime: {miner.runtime:.9f}s")
        # if miner.runtime:
        #     print(f"  Speedup (WOPPclean/Newsup): {baseline.runtime / miner.runtime:.6f}x")
        # if missing:
        #     print(f"  First missing patterns: {missing[:5]}")
        # if extra:
        #     print(f"  First extra patterns: {extra[:5]}")
        # if support_mismatches:
        #     print(f"  First support mismatches: {support_mismatches[:5]}")


if __name__ == "__main__":
    main()


