"""SPEC-414 R1: planejamento da suíte completa local (`scripts/dev/full.sh`).

Sem dependência nova. CLI:
    full_plan.py workers              imprime n; rc 3 se RAM livre abaixo do piso
    full_plan.py crashed <log>        um nodeid por linha dos workers que morreram
    full_plan.py failed <log>         nodeids FAILED/ERROR do log
    full_plan.py verdict <log> <rerun_rc|none>   rc final (0/1)
"""

from __future__ import annotations

import os
import re
import sys

PISO_GB = 3.0
RESERVA_GB = 2.0
MAX_WORKERS = 6
POR_WORKER_GB = 1.0  # provisório; o coordenador mede no pouso (SPEC-414 Etapa 0.2)
MAX_RERUN = 20

_CRASH_RE = re.compile(r"worker '(gw\d+)' crashed while running '([^']+)'")
_FAIL_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)


def free_ram_gb() -> float | None:
    """RAM física disponível em GB; `FULL_PLAN_FREE_GB` é seam de teste."""
    seam = os.environ.get("FULL_PLAN_FREE_GB")
    if seam:
        try:
            return float(seam)
        except ValueError:
            return None
    try:
        if sys.platform == "win32":
            return _free_windows()
        if sys.platform.startswith("linux"):
            return _free_linux()
    except (OSError, ValueError, AttributeError):
        return None
    return None


def _free_windows() -> float:
    import ctypes

    class MemStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    st = MemStatus()
    st.dwLength = ctypes.sizeof(MemStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        raise OSError("GlobalMemoryStatusEx")
    return st.ullAvailPhys / 1024**3


def _free_linux() -> float:
    with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024**2
    raise ValueError("MemAvailable ausente")


def pick_workers(free_gb: float | None, cpus: int, env_n: str | None) -> int | None:
    """`-n` pela RAM; None = abaixo do piso (não roda). `env_n` inteiro >= 1 vence tudo."""
    if env_n and env_n.strip().isdigit() and int(env_n) >= 1:
        return int(env_n)
    if free_gb is None:
        return 2
    if free_gb < PISO_GB:
        return None
    teto = max(2, min(cpus, MAX_WORKERS))
    n = int((free_gb - RESERVA_GB) // POR_WORKER_GB)
    return max(2, min(n, teto))


def crashed_ids(log: str) -> list[str]:
    """Nodeids em que um worker xdist morreu (sem repetição, ordem do log)."""
    seen: list[str] = []
    for _gw, nodeid in _CRASH_RE.findall(log):
        if nodeid not in seen:
            seen.append(nodeid)
    return seen


def failed_ids(log: str) -> list[str]:
    seen: list[str] = []
    for nodeid in _FAIL_RE.findall(log):
        if nodeid not in seen:
            seen.append(nodeid)
    return seen


def verdict(failed: list[str], crashed: list[str], rerun_rc: int | None) -> int:
    """rc final: 0 só se tudo que falhou era crash de worker e o rerun passou."""
    if not failed and not crashed:
        return 0
    if len(crashed) > MAX_RERUN:
        return 1
    if any(f not in crashed for f in failed):
        return 1
    return 0 if rerun_rc == 0 else 1


def _cmd_workers() -> int:
    free = free_ram_gb()
    n = pick_workers(free, os.cpu_count() or 2, os.environ.get("FULL_N"))
    if n is None:
        print(
            f"full: RAM livre {free:.1f} GB < {PISO_GB:.1f} GB; feche processos ou use FULL_N=<n>",
            file=sys.stderr,
        )
        return 3
    if os.environ.get("FULL_N"):
        print(f"full: FULL_N={n} (RAM não consultada)", file=sys.stderr)
    else:
        shown = "?" if free is None else f"{free:.1f}"
        print(f"full: RAM livre {shown} GB -> n={n} (FULL_N para forçar)", file=sys.stderr)
    print(n)
    return 0


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "workers":
        return _cmd_workers()
    if cmd in {"crashed", "failed"} and len(argv) == 2:
        fn = crashed_ids if cmd == "crashed" else failed_ids
        print("\n".join(fn(_read(argv[1]))))
        return 0
    if cmd == "verdict" and len(argv) == 3:
        log = _read(argv[1])
        rerun = int(argv[2]) if argv[2].lstrip("-").isdigit() else None
        return verdict(failed_ids(log), crashed_ids(log), rerun)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
