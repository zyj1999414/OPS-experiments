class WTNode:
    __slots__ = ('offset', 'size', 'bits', 'rank1_prefix', 'lo', 'hi', 'left', 'right')

    def __init__(self):
        self.offset = 0
        self.size = 0
        self.bits = []
        self.rank1_prefix = []
        self.lo = 0
        self.hi = 0
        self.left = None
        self.right = None


class WaveletTreeInt:
    def __init__(self, arr):
        self.arr = arr
        self.n = len(arr)
        if self.n == 0:
            self.sigma = 0
            self._root = None
            return
        self.min_val = min(arr)
        self.max_val = max(arr)
        self.sigma = self.max_val - self.min_val + 1
        self.maxbits = max(self.max_val.bit_length(), 1)
        self._root = WTNode()
        self._build(self._root, arr, 0, self.n, self.min_val,
                     self.min_val + (1 << self.maxbits) - 1, self.maxbits - 1)

    def _build(self, node, arr, offset, size, lo, hi, bit_pos):
        node.offset = offset
        node.size = size
        node.lo = lo
        node.hi = hi
        if bit_pos < 0 or size == 0:
            return
        bits = [0] * size
        rank1 = [0] * size
        left_arr = []
        right_arr = []
        cnt1 = 0
        for i, v in enumerate(arr):
            b = (v >> bit_pos) & 1
            bits[i] = b
            if b == 0:
                left_arr.append(v)
            else:
                right_arr.append(v)
                cnt1 += 1
            rank1[i] = cnt1
        node.bits = bits
        node.rank1_prefix = rank1
        mid = (lo + hi) // 2
        node.left = WTNode()
        self._build(node.left, left_arr, offset, len(left_arr), lo, mid, bit_pos - 1)
        node.right = WTNode()
        self._build(node.right, right_arr, offset + len(left_arr),
                     len(right_arr), mid + 1, hi, bit_pos - 1)

    def root(self):
        return self._root

    def is_leaf(self, node):
        return node.lo == node.hi

    def expand(self, node):
        return node.left, node.right

    def bit_vec(self, node):
        return node.bits

    def rank_bit(self, c, i, node):
        if i < 0 or node.size == 0:
            return 0
        i = min(i, node.size - 1)
        if c == 1:
            return node.rank1_prefix[i]
        else:
            return (i + 1) - node.rank1_prefix[i]

    def select_bit(self, c, i, node):
        if c == 1:
            pref = node.rank1_prefix
        else:
            pref = [j + 1 - v for j, v in enumerate(node.rank1_prefix)]
        lo, hi = 0, len(pref) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if pref[mid] >= i:
                hi = mid
            else:
                lo = mid + 1
        return lo
