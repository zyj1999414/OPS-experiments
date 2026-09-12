"""Exact sliding Newsup prototype with a dynamic negative border."""

from dataclasses import dataclass, field
from collections import deque
import time

import numpy as np

from newsup import NewsupMiner


@dataclass
class BorderLevel:
    length: int
    ring_ids: np.ndarray
    pattern_to_id: dict = field(default_factory=dict)
    id_to_pattern: list = field(default_factory=lambda: [None])
    occurrences: list = field(default_factory=lambda: [set()])
    counts: np.ndarray = field(
        default_factory=lambda: np.zeros(1, dtype=np.int64)
    )
    transition_cache: dict = field(default_factory=dict)

    def ensure_pattern(self, pattern):
        pattern_id = self.pattern_to_id.get(pattern)
        if pattern_id is None:
            pattern_id = len(self.id_to_pattern)
            self.pattern_to_id[pattern] = pattern_id
            self.id_to_pattern.append(pattern)
            self.occurrences.append(set())
            self.counts = np.append(self.counts, np.int64(0))
        return pattern_id

    def frequent_ids(self, minsup):
        return {
            pattern_id
            for pattern_id in range(1, len(self.id_to_pattern))
            if self.counts[pattern_id] >= minsup
        }


class NegativeBorderSlidingNewsup:
    """Maintain frequent patterns and their exact dynamic negative border."""

    def __init__(self, window_size, step_size, min_sup,
                 repair_mode="neighbors", activation_sup=None,
                 update_mode="batch_halo", expire_mode="bincount_lazy"):
        self.window_size = int(window_size)
        self.step_size = int(step_size)
        self.min_sup = int(min_sup)
        self.activation_sup = (
            self.min_sup if activation_sup is None else int(activation_sup)
        )
        if self.activation_sup <= 0 or self.activation_sup > self.min_sup:
            raise ValueError("activation_sup must be in [1, min_sup]")
        if repair_mode not in {"neighbors", "intersections"}:
            raise ValueError("unknown repair_mode")
        if update_mode not in {"scalar", "batch_halo"}:
            raise ValueError("unknown update_mode")
        if expire_mode not in {"scalar", "bincount_lazy"}:
            raise ValueError("unknown expire_mode")
        self.repair_mode = repair_mode
        self.update_mode = update_mode
        self.expire_mode = expire_mode
        self.data = np.empty(0, dtype=np.float64)
        self.left = 0
        self.right = -1
        self.levels = []
        self.initial_runtime = 0.0
        self.update_runtimes = []
        self.repair_pair_checks = 0
        self.repair_endpoint_checks = 0
        self.normal_new_endpoint_checks = 0
        self.normal_unique_event_checks = 0
        self.slide_count = 0

    def _new_level(self, length):
        return BorderLevel(
            length=length,
            ring_ids=np.zeros(self.window_size, dtype=np.int32),
        )

    @staticmethod
    def _candidate(p, q, relation):
        candidates = NewsupMiner.fuse_patterns(p, q)
        return NewsupMiner._select_fused_candidate(candidates, relation)

    def _relation(self, endpoint, child_length):
        begin = self.data[endpoint - child_length + 1]
        end = self.data[endpoint]
        if begin < end:
            return 1
        if begin > end:
            return 2
        return 0

    def _record(self, level, endpoint, pattern):
        pattern_id = level.ensure_pattern(pattern)
        slot = endpoint % self.window_size
        previous_id = int(level.ring_ids[slot])
        if previous_id == pattern_id:
            return pattern_id
        if previous_id:
            if self.expire_mode == "scalar":
                level.occurrences[previous_id].discard(endpoint)
            level.counts[previous_id] -= 1
        level.ring_ids[slot] = pattern_id
        level.occurrences[pattern_id].add(int(endpoint))
        level.counts[pattern_id] += 1
        return pattern_id

    def _build_length_two(self):
        level = self._new_level(2)
        rising_id = level.ensure_pattern((1, 2))
        falling_id = level.ensure_pattern((2, 1))
        endpoints = np.arange(
            self.left + 1, self.right + 1, dtype=np.int64
        )
        left_values = self.data[endpoints - 1]
        right_values = self.data[endpoints]
        rising = left_values < right_values
        falling = left_values > right_values
        ids = np.where(rising, rising_id, np.where(falling, falling_id, 0))
        level.ring_ids[endpoints % self.window_size] = ids
        level.occurrences[rising_id] = set(endpoints[rising].tolist())
        level.occurrences[falling_id] = set(endpoints[falling].tolist())
        level.counts[rising_id] = int(np.count_nonzero(rising))
        level.counts[falling_id] = int(np.count_nonzero(falling))
        self.levels = [level]

    def _build_border_level(self, previous, frequent_previous):
        child = self._new_level(previous.length + 1)
        endpoints = np.arange(
            self.left + child.length - 1,
            self.right + 1,
            dtype=np.int64,
        )
        prefix_ids = previous.ring_ids[
            (endpoints - 1) % self.window_size
        ]
        suffix_ids = previous.ring_ids[endpoints % self.window_size]
        frequent_lookup = np.zeros(len(previous.id_to_pattern), dtype=bool)
        frequent_lookup[list(frequent_previous)] = True
        valid = (
            (prefix_ids != 0)
            & (suffix_ids != 0)
            & frequent_lookup[prefix_ids]
            & frequent_lookup[suffix_ids]
        )
        endpoints = endpoints[valid]
        if endpoints.size:
            prefix_ids = prefix_ids[valid].astype(np.int64, copy=False)
            suffix_ids = suffix_ids[valid].astype(np.int64, copy=False)
            begin = self.data[endpoints - child.length + 1]
            end = self.data[endpoints]
            relations = np.where(
                begin < end, 1, np.where(begin > end, 2, 0)
            ).astype(np.int64, copy=False)
            base = len(previous.id_to_pattern)
            keys = (prefix_ids * base + suffix_ids) * 3 + relations
            unique_keys, inverse = np.unique(keys, return_inverse=True)
            group_ids = np.zeros(unique_keys.size, dtype=np.int32)
            for group_index, key_value in enumerate(unique_keys.tolist()):
                relation = key_value % 3
                pair = key_value // 3
                prefix_id = pair // base
                suffix_id = pair % base
                candidate = self._candidate(
                    previous.id_to_pattern[prefix_id],
                    previous.id_to_pattern[suffix_id],
                    relation,
                )
                if candidate is not None:
                    group_ids[group_index] = child.ensure_pattern(candidate)
            ids = group_ids[inverse]
            child.ring_ids[endpoints % self.window_size] = ids
            for pattern_id in range(1, len(child.id_to_pattern)):
                child.occurrences[pattern_id] = set(
                    endpoints[ids == pattern_id].tolist()
                )
                child.counts[pattern_id] = int(
                    np.count_nonzero(ids == pattern_id)
                )
        self.levels.append(child)
        return child

    def fit(self, values):
        start = time.perf_counter()
        self.data = np.ascontiguousarray(values, dtype=np.float64)
        if self.data.size < self.window_size:
            raise ValueError("data shorter than window")
        self.left = 0
        self.right = self.window_size - 1
        self.repair_pair_checks = 0
        self.repair_endpoint_checks = 0
        self.normal_new_endpoint_checks = 0
        self.normal_unique_event_checks = 0
        self.slide_count = 0
        self._build_length_two()
        while True:
            frequent = self.levels[-1].frequent_ids(self.activation_sup)
            if not frequent:
                break
            self._build_border_level(self.levels[-1], frequent)
        self.initial_runtime = time.perf_counter() - start
        return self.patterns()

    def _expire_level(self, level, old_left, new_left):
        start = old_left + level.length - 1
        stop = new_left + level.length - 1
        for endpoint in range(start, stop):
            slot = endpoint % self.window_size
            pattern_id = int(level.ring_ids[slot])
            if pattern_id:
                level.occurrences[pattern_id].discard(endpoint)
                level.counts[pattern_id] -= 1
            level.ring_ids[slot] = 0

    def _expire_level_batch_lazy(self, level, old_left, new_left):
        start = old_left + level.length - 1
        stop = new_left + level.length - 1
        endpoints = np.arange(start, stop, dtype=np.int64)
        if endpoints.size == 0:
            return
        slots = endpoints % self.window_size
        leaving_ids = level.ring_ids[slots]
        removed = np.bincount(
            leaving_ids, minlength=level.counts.size
        )
        removed[0] = 0
        level.counts -= removed[:level.counts.size]
        level.ring_ids[slots] = 0

    def _compact_lazy_occurrences(self):
        """Periodically bound stale occurrence memory without per-slide deletes."""
        for level in self.levels:
            valid_left = self.left + level.length - 1
            for pattern_id in range(1, len(level.id_to_pattern)):
                occurrence = level.occurrences[pattern_id]
                active_count = int(level.counts[pattern_id])
                if len(occurrence) <= active_count * 2 + 64:
                    continue
                level.occurrences[pattern_id] = {
                    endpoint
                    for endpoint in occurrence
                    if valid_left <= endpoint <= self.right
                    and int(
                        level.ring_ids[endpoint % self.window_size]
                    ) == pattern_id
                }

    def _add_new_length_two(self, level, endpoints):
        for endpoint in endpoints:
            left_value = self.data[endpoint - 1]
            right_value = self.data[endpoint]
            if left_value < right_value:
                pattern_id = level.pattern_to_id[(1, 2)]
            elif left_value > right_value:
                pattern_id = level.pattern_to_id[(2, 1)]
            else:
                pattern_id = 0
            level.ring_ids[endpoint % self.window_size] = pattern_id
            if pattern_id:
                level.occurrences[pattern_id].add(int(endpoint))
                level.counts[pattern_id] += 1

    def _add_new_length_two_batch(self, level, old_right, endpoints):
        """Build new length-2 IDs from one old value plus the new batch."""
        if endpoints.size == 0:
            return
        scan_values = self.data[old_right:self.right + 1]
        left_values = scan_values[:-1]
        right_values = scan_values[1:]
        rising_id = level.pattern_to_id[(1, 2)]
        falling_id = level.pattern_to_id[(2, 1)]
        ids = np.where(
            left_values < right_values,
            rising_id,
            np.where(left_values > right_values, falling_id, 0),
        ).astype(np.int32, copy=False)
        level.ring_ids[endpoints % self.window_size] = ids
        rising_endpoints = endpoints[ids == rising_id]
        falling_endpoints = endpoints[ids == falling_id]
        level.occurrences[rising_id].update(rising_endpoints.tolist())
        level.occurrences[falling_id].update(falling_endpoints.tolist())
        added = np.bincount(ids, minlength=level.counts.size)
        added[0] = 0
        level.counts += added[:level.counts.size]

    def _add_new_to_level(self, level_index, endpoints, frequent_previous):
        previous = self.levels[level_index - 1]
        level = self.levels[level_index]
        for endpoint in endpoints:
            self.normal_new_endpoint_checks += 1
            prefix_id = int(
                previous.ring_ids[(endpoint - 1) % self.window_size]
            )
            suffix_id = int(previous.ring_ids[endpoint % self.window_size])
            slot = endpoint % self.window_size
            level.ring_ids[slot] = 0
            if not prefix_id or not suffix_id:
                continue
            relation = self._relation(endpoint, level.length)
            candidate = self._candidate(
                previous.id_to_pattern[prefix_id],
                previous.id_to_pattern[suffix_id],
                relation,
            )
            if candidate is None:
                continue
            candidate_id = level.pattern_to_id.get(candidate)
            if candidate_id is None:
                if (
                    prefix_id not in frequent_previous
                    or suffix_id not in frequent_previous
                ):
                    continue
                candidate_id = level.ensure_pattern(candidate)
            level.ring_ids[slot] = candidate_id
            level.occurrences[candidate_id].add(int(endpoint))
            level.counts[candidate_id] += 1

    def _add_new_to_level_batch(
        self, level_index, endpoints, old_last_id, frequent_previous
    ):
        """Use a one-ID halo and fuse once per distinct NumPy event key."""
        previous = self.levels[level_index - 1]
        level = self.levels[level_index]
        if endpoints.size == 0:
            return

        # The first pair is (old last ID, first new ID); all remaining pairs
        # are adjacent IDs inside the new batch.
        new_previous_ids = previous.ring_ids[
            endpoints % self.window_size
        ]
        scan_ids = np.empty(endpoints.size + 1, dtype=np.int32)
        scan_ids[0] = old_last_id
        scan_ids[1:] = new_previous_ids
        prefix_ids = scan_ids[:-1]
        suffix_ids = scan_ids[1:]

        slots = endpoints % self.window_size
        level.ring_ids[slots] = 0
        valid = (prefix_ids != 0) & (suffix_ids != 0)
        if not np.any(valid):
            return

        active_endpoints = endpoints[valid]
        active_prefix_ids = prefix_ids[valid].astype(np.int64, copy=False)
        active_suffix_ids = suffix_ids[valid].astype(np.int64, copy=False)
        begin = self.data[active_endpoints - level.length + 1]
        end = self.data[active_endpoints]
        relations = np.where(
            begin < end, 1, np.where(begin > end, 2, 0)
        ).astype(np.int64, copy=False)

        base = len(previous.id_to_pattern)
        event_keys = (
            (active_prefix_ids * base + active_suffix_ids) * 3 + relations
        )
        unique_keys, inverse = np.unique(event_keys, return_inverse=True)
        self.normal_new_endpoint_checks += int(endpoints.size)
        self.normal_unique_event_checks += int(unique_keys.size)

        frequent_lookup = np.zeros(base, dtype=bool)
        if frequent_previous:
            frequent_lookup[list(frequent_previous)] = True
        event_pattern_ids = np.zeros(unique_keys.size, dtype=np.int32)

        for event_index, key_value in enumerate(unique_keys.tolist()):
            relation = key_value % 3
            pair = key_value // 3
            prefix_id = pair // base
            suffix_id = pair % base
            transition = (prefix_id, suffix_id, relation)
            missing = object()
            candidate = level.transition_cache.get(transition, missing)
            if candidate is missing:
                candidate = self._candidate(
                    previous.id_to_pattern[prefix_id],
                    previous.id_to_pattern[suffix_id],
                    relation,
                )
                level.transition_cache[transition] = candidate
            if candidate is None:
                continue
            candidate_id = level.pattern_to_id.get(candidate)
            if candidate_id is None:
                if not (
                    frequent_lookup[prefix_id]
                    and frequent_lookup[suffix_id]
                ):
                    continue
                candidate_id = level.ensure_pattern(candidate)
            event_pattern_ids[event_index] = candidate_id

        ids = event_pattern_ids[inverse]
        level.ring_ids[active_endpoints % self.window_size] = ids
        for pattern_id in np.unique(ids):
            if pattern_id:
                level.occurrences[int(pattern_id)].update(
                    active_endpoints[ids == pattern_id].tolist()
                )
        added = np.bincount(ids, minlength=level.counts.size)
        added[0] = 0
        level.counts += added[:level.counts.size]

    def _adjacent_endpoints(self, prefix_occ, suffix_occ):
        if len(prefix_occ) <= len(suffix_occ):
            return [
                endpoint + 1
                for endpoint in prefix_occ
                if endpoint + 1 in suffix_occ
            ]
        return [
            endpoint
            for endpoint in suffix_occ
            if endpoint - 1 in prefix_occ
        ]

    def _active_occurrences(self, level, pattern_id):
        occurrence = level.occurrences[pattern_id]
        if self.expire_mode == "scalar":
            return occurrence
        valid_left = self.left + level.length - 1
        return {
            endpoint
            for endpoint in occurrence
            if valid_left <= endpoint <= self.right
            and int(level.ring_ids[endpoint % self.window_size]) == pattern_id
        }

    def _repair_pair(self, level_index, prefix_id, suffix_id):
        parent = self.levels[level_index]
        child_index = level_index + 1
        if child_index == len(self.levels):
            self.levels.append(self._new_level(parent.length + 1))
        child = self.levels[child_index]
        self.repair_pair_checks += 1
        endpoints = self._adjacent_endpoints(
            self._active_occurrences(parent, prefix_id),
            self._active_occurrences(parent, suffix_id),
        )
        valid_left = self.left + child.length - 1
        endpoints = [
            endpoint for endpoint in endpoints
            if valid_left <= endpoint <= self.right
        ]
        self.repair_endpoint_checks += len(endpoints)
        for endpoint in endpoints:
            relation = self._relation(endpoint, child.length)
            candidate = self._candidate(
                parent.id_to_pattern[prefix_id],
                parent.id_to_pattern[suffix_id],
                relation,
            )
            if candidate is not None:
                self._record(child, endpoint, candidate)

    def _repair_neighbors(self, level_index, promoted_id, frequent):
        """Repair both fusion directions by reading one neighboring ID."""
        parent = self.levels[level_index]
        child_index = level_index + 1
        if child_index == len(self.levels):
            self.levels.append(self._new_level(parent.length + 1))
        child = self.levels[child_index]
        promoted_pattern = parent.id_to_pattern[promoted_id]
        promoted_occurrences = self._active_occurrences(
            parent, promoted_id
        )

        for prefix_endpoint in promoted_occurrences:
            child_endpoint = prefix_endpoint + 1
            if child_endpoint > self.right:
                continue
            self.repair_endpoint_checks += 1
            suffix_id = int(
                parent.ring_ids[child_endpoint % self.window_size]
            )
            if suffix_id not in frequent:
                continue
            self.repair_pair_checks += 1
            candidate = self._candidate(
                promoted_pattern,
                parent.id_to_pattern[suffix_id],
                self._relation(child_endpoint, child.length),
            )
            if candidate is not None:
                self._record(child, child_endpoint, candidate)

        for child_endpoint in promoted_occurrences:
            prefix_endpoint = child_endpoint - 1
            if prefix_endpoint < self.left + parent.length - 1:
                continue
            self.repair_endpoint_checks += 1
            prefix_id = int(
                parent.ring_ids[prefix_endpoint % self.window_size]
            )
            if prefix_id not in frequent:
                continue
            self.repair_pair_checks += 1
            candidate = self._candidate(
                parent.id_to_pattern[prefix_id],
                promoted_pattern,
                self._relation(child_endpoint, child.length),
            )
            if candidate is not None:
                self._record(child, child_endpoint, candidate)

    def _repair_promotions(self, before_frequent):
        queue = deque()
        for level_index, level in enumerate(self.levels):
            current = level.frequent_ids(self.activation_sup)
            old = before_frequent[level_index] if level_index < len(before_frequent) else set()
            for pattern_id in current - old:
                queue.append((level_index, pattern_id))

        processed = set()
        while queue:
            level_index, promoted_id = queue.popleft()
            marker = (level_index, promoted_id)
            if marker in processed:
                continue
            processed.add(marker)
            parent = self.levels[level_index]
            frequent = parent.frequent_ids(self.activation_sup)
            child_before = (
                self.levels[level_index + 1].frequent_ids(self.activation_sup)
                if level_index + 1 < len(self.levels)
                else set()
            )
            if self.repair_mode == "neighbors":
                self._repair_neighbors(level_index, promoted_id, frequent)
            else:
                for other_id in frequent:
                    self._repair_pair(level_index, promoted_id, other_id)
                    if other_id != promoted_id:
                        self._repair_pair(level_index, other_id, promoted_id)
            child = self.levels[level_index + 1]
            child_after = child.frequent_ids(self.activation_sup)
            for child_id in child_after - child_before:
                queue.append((level_index + 1, child_id))

    def slide(self, emit=True):
        if self.right + self.step_size >= self.data.size:
            return None
        start = time.perf_counter()
        before_frequent = [
            level.frequent_ids(self.activation_sup) for level in self.levels
        ]
        old_left = self.left
        old_right = self.right
        old_last_ids = [
            int(level.ring_ids[old_right % self.window_size])
            for level in self.levels
        ]
        self.left += self.step_size
        self.right += self.step_size
        endpoints_array = np.arange(
            old_right + 1, self.right + 1, dtype=np.int64
        )
        endpoints_range = range(old_right + 1, self.right + 1)

        for level in self.levels:
            if self.expire_mode == "bincount_lazy":
                self._expire_level_batch_lazy(level, old_left, self.left)
            else:
                self._expire_level(level, old_left, self.left)
        if self.update_mode == "batch_halo":
            self._add_new_length_two_batch(
                self.levels[0], old_right, endpoints_array
            )
        else:
            self._add_new_length_two(
                self.levels[0], endpoints_range
            )

        for level_index in range(1, len(self.levels)):
            frequent_previous = self.levels[level_index - 1].frequent_ids(
                self.activation_sup
            )
            if self.update_mode == "batch_halo":
                self._add_new_to_level_batch(
                    level_index,
                    endpoints_array,
                    old_last_ids[level_index - 1],
                    frequent_previous,
                )
            else:
                self._add_new_to_level(
                    level_index,
                    endpoints_range,
                    frequent_previous,
                )

        self._repair_promotions(before_frequent)
        self.slide_count += 1
        if (
            self.expire_mode == "bincount_lazy"
            and self.slide_count % 128 == 0
        ):
            self._compact_lazy_occurrences()
        runtime = time.perf_counter() - start
        self.update_runtimes.append(runtime)
        return self.patterns() if emit else None

    def patterns(self):
        result = []
        for level in self.levels:
            frequent = {
                level.id_to_pattern[pattern_id]: int(level.counts[pattern_id])
                for pattern_id in level.frequent_ids(self.min_sup)
            }
            if not frequent:
                break
            result.append(frequent)
        return result
