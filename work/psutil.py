"""Minimal local compatibility shim for legacy OPS baselines."""
import resource
class _Info:
    @property
    def rss(self):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
class Process:
    def __init__(self, _pid=None): pass
    def memory_info(self): return _Info()
