"""Lock local atômico para impedir duas matrizes de longrun simultâneas."""
from __future__ import annotations

import json
import os
import socket
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4


class MatrixAlreadyRunningError(RuntimeError):
    pass


def default_matrix_lock_path() -> Path:
    return Path(os.getenv("RPG_PLAYTEST_RUNS_DIR", "playtest_runs")) / ".matrix-suite.lock"


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            process_query_limited_information, False, pid,
        )
        if not handle:
            # Acesso negado prova que o PID existe, ainda que não seja consultável.
            return int(kernel32.GetLastError()) == 5
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_owner(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _owner_is_active(owner: dict) -> bool:
    host = str(owner.get("host") or "")
    try:
        pid = int(owner.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    if not host or host != socket.gethostname():
        # Em diretório compartilhado, não é seguro declarar morto um PID remoto.
        return bool(host and pid > 0)
    return _pid_is_alive(pid)


@contextmanager
def matrix_single_flight(path: Path | None = None) -> Iterator[dict]:
    lock_path = Path(path) if path is not None else default_matrix_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    owner = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "token": token,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    while True:
        try:
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            current = _read_owner(lock_path)
            if _owner_is_active(current):
                raise MatrixAlreadyRunningError(
                    f"matrix-suite já está ativa (pid={current.get('pid')}, "
                    f"host={current.get('host')})"
                )
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            continue
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(owner, stream, ensure_ascii=False)
        except Exception:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            raise
        break

    try:
        yield dict(owner)
    finally:
        current = _read_owner(lock_path)
        if current.get("token") == token:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
