class stNode:
    __slots__ = ('start', 'depth', 'label', 'parent', 'slink', 'child',
                 'isCandidate', 'leftMax', 'visited', 'leafCount',
                 'leftDiverse', 'LCA', 'terminate_label')
    def __init__(self, start=0, depth=0, label=0, terminate_label=None):
        self.start = start
        self.depth = depth
        self.label = label
        self.parent = None
        self.slink = None
        self.child = {}
        self.isCandidate = False
        self.leftMax = True
        self.visited = False
        self.leafCount = 0
        self.leftDiverse = False
        self.LCA = None
        if terminate_label is not None:
            self.terminate_label = terminate_label
        else:
            self.terminate_label = None

    def __repr__(self):
        return (f"stNode(start={self.start}, depth={self.depth}, "
                f"label={self.label})")

    def setSLink(self, node):
        self.slink = node

    def getChild(self, label):
        return self.child.get(label, None)

    def addChild(self, node, label):
        self.child[label] = node
        node.parent = self

    def removeChild(self, node):
        label = node.label
        if label in self.child and self.child[label] == node:
            del self.child[label]

    def allChild(self):
        return list(self.child.values())

    def numChild(self):
        return len(self.child)
