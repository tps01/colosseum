"""Record in-process soak metrics each suite repeat (R-SOAK-02 fixture)."""

from __future__ import annotations


def _rss_mb() -> float:
    import sys
    from pathlib import Path

    if sys.platform == "win32":
        import ctypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        )
        return counters.WorkingSetSize / (1024 * 1024)

    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return float(line.split()[1]) / 1024.0

    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = usage.ru_maxrss
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024.0


def main() -> None:
    import gc

    from colosseum.context import get_context

    ctx = get_context()
    out = ctx.suite_output_dir
    if out is None:
        raise RuntimeError("soak_probe requires an allocated suite container")

    cache_len = len(ctx.resource_cache)
    if cache_len > 0:
        raise RuntimeError(f"resource_cache must stay empty during soak, got {cache_len}")

    col_count = sum(
        1
        for obj in gc.get_objects()
        if isinstance(getattr(type(obj), "__module__", None), str)
        and type(obj).__module__.startswith("colosseum")
    )
    gc_count = len(gc.get_objects())
    repeat = ctx.slot_repeat_index if ctx.slot_repeat_index is not None else -1

    path = out / "soak_metrics.tsv"
    write_header = not path.exists()
    with path.open("a", encoding="utf-8") as handle:
        if write_header:
            handle.write(
                "repeat_index\trss_mb\tgc_objects\tcolosseum_objects\tresource_cache_len\n",
            )
        handle.write(
            f"{repeat}\t{_rss_mb():.3f}\t{gc_count}\t{col_count}\t{cache_len}\n",
        )
