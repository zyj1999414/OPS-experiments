import time
from node import stNode
from wavelet_tree import WaveletTreeInt

NA = -1


class OPST:
    def __init__(self, w, rangeThreshold=512):
        self.w = w
        self.n = len(w)
        self.terminate_label = 2 * self.n + 1
        self.rangeThreshold = rangeThreshold
        self.waveletFlag = False
        self.wt = None
        self.waveletTime = 0.0
        self.pos2leaf = {}
        self._lc_cache = {}

        self.root = stNode(terminate_label=self.terminate_label)
        self.root.setSLink(self.root)

        u = self.root
        d = 0
        n = self.n
        last_code = self.LastCodeInt
        create_node = self.createNode
        create_leaf = self.createLeaf
        compute_slink = self.ComputeSuffixLink

        for i in range(n):
            while (i + d) < n and d == u.depth:
                child = u.getChild(last_code(i, i + d))
                if child is None:
                    break
                u = child
                d += 1
                while (i + d < n and u.start + d < n and d < u.depth and
                       last_code(u.start, u.start + d) == last_code(i, i + d)):
                    d += 1

            if d < u.depth:
                u = create_node(u, d)
            create_leaf(i, u, d)

            if u.slink is None:
                compute_slink(u)
            u = u.slink
            d = d - 1 if d > 0 else 0

    def Max(self, u, a, b):
        if self.wt.is_leaf(u):
            return b
        if self.wt.rank_bit(1, a, u) == self.wt.rank_bit(1, b, u):
            left = self.wt.expand(u)[0]
            new_a = self.wt.rank_bit(0, a, u) - 1
            new_b = self.wt.rank_bit(0, b, u) - 1
            return self.wt.select_bit(0, self.Max(left, new_a, new_b) + 1, u)
        else:
            right = self.wt.expand(u)[1]
            new_a = self.wt.rank_bit(1, a, u) - 1
            new_b = self.wt.rank_bit(1, b, u) - 1
            return self.wt.select_bit(1, self.Max(right, new_a, new_b) + 1, u)

    def predecessorWT(self, u, a, b):
        if a == b:
            return NA
        if not self.wt.is_leaf(u):
            B_u = self.wt.bit_vec(u)
            x = B_u[b + 1]
            new_a = self.wt.rank_bit(x, a, u) - 1
            new_b = self.wt.rank_bit(x, b, u) - 1
            child = self.wt.expand(u)[x]
            pos = self.predecessorWT(child, new_a, new_b)
            if pos != NA:
                return self.wt.select_bit(x, pos + 1, u)
            elif x == 0 or self.wt.rank_bit(0, a, u) == self.wt.rank_bit(0, b, u):
                return NA
            else:
                left = self.wt.expand(u)[0]
                rank0_a = self.wt.rank_bit(0, a, u) - 1
                rank0_b = self.wt.rank_bit(0, b, u) - 1
                return self.wt.select_bit(0, self.Max(left, rank0_a, rank0_b) + 1, u)
        else:
            return b

    def predecessorNV(self, a, b):
        w_local = self.w
        if not w_local or b < 0:
            return NA
        aimElement = w_local[b]
        predecessorIndex = NA
        predecessorValue = None
        start = a if a >= 0 else 0
        for j in range(start, b):
            v = w_local[j]
            if v <= aimElement and (predecessorIndex == NA or v >= predecessorValue):
                predecessorIndex = j
                predecessorValue = v
        return predecessorIndex

    def _last_code_impl(self, a, b):
        w_local = self.w
        if b - a < self.rangeThreshold:
            predecessor_local = self.predecessorNV(a, b)
        else:
            if not self.waveletFlag:
                wavelet_start = time.perf_counter()
                self.wt = WaveletTreeInt(w_local)
                wavelet_end = time.perf_counter()
                self.waveletTime = (wavelet_end - wavelet_start)
                self.waveletFlag = True
                print(f"It is necessary to construct the wavelet tree for b-a > {self.rangeThreshold}")
                print(f"sigma of input = {self.wt.sigma}")
                print(f"Runtime for wavelet tree construction  = {self.waveletTime:.6f} s.")
            predecessor_local = self.predecessorWT(self.wt.root(), a - 1, b - 1)
        if predecessor_local < 0:
            return NA * 2 + 0
        succ = 1 if w_local[predecessor_local] == w_local[b] else 0
        return (predecessor_local - a) * 2 + succ

    def LastCodeInt(self, a, b):
        if b == self.n:
            return self.terminate_label
        key = (a, b)
        try:
            return self._lc_cache[key]
        except KeyError:
            val = self._last_code_impl(a, b)
            self._lc_cache[key] = val
            return val

    def ComputeSuffixLink(self, u):
        d = u.depth
        u_copy = u
        last_code_int = self.LastCodeInt
        create_node = self.createNode
        while u_copy.parent.slink is None:
            u_copy = u_copy.parent
        v = u_copy.parent.slink
        while v.depth < d - 1:
            v = v.getChild(last_code_int(u.start + 1, u.start + v.depth + 1))
        if v.depth > d - 1:
            v = create_node(v, d - 1)
        u.setSLink(v)

    def createNode(self, u, d):
        i = u.start
        p = u.parent
        last_code_int = self.LastCodeInt
        v_label = last_code_int(i, i + p.depth)
        u_label = last_code_int(i, i + d)
        v = stNode(i, d, v_label)
        v.addChild(u, u_label)
        p.addChild(v, v_label)
        return v

    def createLeaf(self, i, u, d):
        leaf_label = self.LastCodeInt(i, i + d)
        leaf = stNode(i, self.n - i + 1, leaf_label)
        u.addChild(leaf, leaf_label)
        self.pos2leaf[i] = leaf

    def MaxTauDFS(self, tau):
        stack = [self.root]
        tauminus1 = tau - 1
        while stack:
            top = stack[-1]
            if not top.visited:
                top.visited = True
                for child in top.child.values():
                    stack.append(child)
            else:
                stack.pop()
                if not top.child:
                    top.leafCount = 1
                else:
                    if top.numChild() > 1:
                        childrenGetau = False
                        for child in top.child.values():
                            top.leafCount += child.leafCount
                            childrenGetau = childrenGetau or (child.leafCount > tauminus1)
                        if top.leafCount > tauminus1 and not childrenGetau:
                            top.isCandidate = True
                    else:
                        top.leafCount = next(iter(top.child.values())).leafCount

                    if top.isCandidate and top.slink is not None:
                        ancestor = top.slink
                        while ancestor is not None and ancestor.leftMax:
                            if ancestor.leftMax:
                                ancestor.leftMax = False
                                ancestor = ancestor.parent
                top.visited = False

    def MaxFindNodes(self):
        result = {}
        stack = [self.root]
        while stack:
            top = stack[-1]
            if not top.visited:
                top.visited = True
                for child in top.child.values():
                    stack.append(child)
            else:
                if top.isCandidate and top.leftMax:
                    result[top] = top.leafCount
                top.visited = False
                top.isCandidate = False
                top.leftMax = True
                top.leafCount = 0
                stack.pop()
        return result

    def FindLCA(self, node):
        children = node.allChild()
        u = children[0].LCA
        for it in children[1:]:
            v = it.LCA
            if u.parent is self.root and self.root.numChild() == 1:
                break
            while u is not v:
                if u.depth < v.depth:
                    v = v.parent
                else:
                    u = u.parent
        return u

    def ClosedTauDFS(self, tau):
        stack = [self.root]
        for i in range(1, self.n):
            self.pos2leaf[i].LCA = self.pos2leaf[i - 1]
        if 0 in self.pos2leaf:
            self.pos2leaf[0].LCA = self.root.allChild()[0]

        tauminus1 = tau - 1
        while stack:
            top = stack[-1]
            if not top.visited:
                top.visited = True
                for child in top.child.values():
                    stack.append(child)
            else:
                stack.pop()
                if not top.child:
                    top.leafCount = 1
                else:
                    if top.numChild() > 1:
                        for child in top.child.values():
                            top.leafCount += child.leafCount
                        if top.leafCount > tauminus1:
                            top.isCandidate = True
                        top.LCA = self.FindLCA(top)
                    else:
                        first_child = next(iter(top.child.values()))
                        top.leafCount = first_child.leafCount
                        top.LCA = first_child.LCA

                    if top.LCA is not None and top.LCA.depth < top.depth + 1:
                        top.leftDiverse = True
                top.visited = False

    def ClosedFindNodes(self):
        result = {}
        stack = [self.root]
        while stack:
            top = stack[-1]
            if not top.visited:
                top.visited = True
                for child in top.child.values():
                    stack.append(child)
            else:
                if top.isCandidate and top.leftDiverse:
                    result[top] = top.leafCount
                top.visited = False
                top.isCandidate = False
                top.leftDiverse = False
                top.leafCount = 0
                stack.pop()
        return result

    def deleteTreeIteratively(self):
        stack = [self.root]
        while stack:
            current = stack.pop()
            for child in list(current.child.values()):
                if child is not None:
                    stack.append(child)
            current.child.clear()
