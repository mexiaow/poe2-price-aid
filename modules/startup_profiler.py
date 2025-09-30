"""
Startup profiling helpers.
"""

from time import perf_counter
from typing import Optional


class _Profiler:
    def __init__(self) -> None:
        self._start = perf_counter()
        self._last = self._start

    def mark(self, label: str) -> None:
        now = perf_counter()
        total = now - self._start
        delta = now - self._last
        print(f"[STARTUP] {label}: total={total:.3f}s delta={delta:.3f}s")
        self._last = now


_profiler: Optional[_Profiler] = None


def enable() -> None:
    """Activate profiling."""
    global _profiler
    if _profiler is None:
        _profiler = _Profiler()


def mark(label: str) -> None:
    """Record a checkpoint if profiling is active."""
    if _profiler is not None:
        _profiler.mark(label)
