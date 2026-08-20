"""Bootstrap seguro da stack Supabase exclusivamente local.

Uso: ``uv run python scripts/dev_stack.py doctor|start|status|stop`` e
``uv run python scripts/dev_stack.py reset --confirm-local``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
SUPABASE_DIR = ROOT / "supabase"
SUPABASE_CLI_VERSION = "2.115.0"
LOCAL_PORTS = (55321, 55322, 55323, 55324)
MIN_DOCKER_MEMORY_BYTES = 7 * 1024**3
MIN_FREE_DISK_BYTES = 8 * 1024**3


class StackError(RuntimeError):
    pass


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), cwd=ROOT, capture_output=True, text=True, check=False, timeout=1800
    )


def cli_command() -> list[str]:
    configured = os.getenv("SUPABASE_CLI_COMMAND", "").strip()
    if configured:
        return configured.split()
    global_cli = shutil.which("supabase")
    if global_cli:
        return [global_cli]
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if npx:
        return [npx, "--yes", f"supabase@{SUPABASE_CLI_VERSION}"]
    raise StackError(
        "Supabase CLI indisponível: instale via Scoop ou disponibilize npm/npx; "
        "nenhum download foi iniciado."
    )


def _checked(command: Sequence[str], runner: Runner) -> subprocess.CompletedProcess[str]:
    result = runner(command)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise StackError(detail or f"comando falhou: {' '.join(command)}")
    return result


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _assert_unlinked() -> None:
    project_ref = SUPABASE_DIR / ".temp" / "project-ref"
    if project_ref.exists() and project_ref.read_text(encoding="utf-8").strip():
        raise StackError(
            "stack parece vinculada a projeto remoto; remova o link manualmente após revisar o alvo"
        )


@dataclass(frozen=True)
class DoctorReport:
    cli_version: str
    docker_version: str
    docker_memory_bytes: int
    free_disk_bytes: int
    ports_available: dict[int, bool]
    config_present: bool


def doctor(*, runner: Runner = _run, require_free_ports: bool = False) -> DoctorReport:
    command = cli_command()
    cli = _checked([*command, "--version"], runner)
    _checked([*command, "start", "--help"], runner)
    docker = _checked(["docker", "version", "--format", "{{.Server.Version}}"], runner)
    memory = _checked(["docker", "info", "--format", "{{.MemTotal}}"], runner)
    try:
        docker_memory = int(memory.stdout.strip())
    except ValueError as exc:
        raise StackError("Docker não informou memória utilizável") from exc
    if docker_memory < MIN_DOCKER_MEMORY_BYTES:
        raise StackError(
            f"Docker possui {docker_memory / 1024**3:.1f} GiB; Supabase Local exige ao menos 7 GiB"
        )
    free_disk = shutil.disk_usage(ROOT).free
    if free_disk < MIN_FREE_DISK_BYTES:
        raise StackError("menos de 8 GiB livres para imagens/volumes locais")
    ports = {port: _port_available(port) for port in LOCAL_PORTS}
    if require_free_ports and not all(ports.values()):
        occupied = ", ".join(str(port) for port, available in ports.items() if not available)
        raise StackError(f"portas locais ocupadas: {occupied}")
    if not (SUPABASE_DIR / "config.toml").exists():
        raise StackError("supabase/config.toml ausente")
    _assert_unlinked()
    return DoctorReport(
        cli_version=cli.stdout.strip(),
        docker_version=docker.stdout.strip(),
        docker_memory_bytes=docker_memory,
        free_disk_bytes=free_disk,
        ports_available=ports,
        config_present=True,
    )


def start(*, runner: Runner = _run) -> None:
    doctor(runner=runner, require_free_ports=True)
    command = cli_command()
    _checked([*command, "start", "--help"], runner)
    _checked([*command, "start"], runner)


def _redact_status(raw: str) -> str:
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return "status disponível; saída não estruturada omitida por segurança"
    public: dict[str, object] = {}
    for key, value in values.items():
        upper = key.upper()
        if any(marker in upper for marker in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            continue
        if upper == "DB_URL" and isinstance(value, str):
            parsed = urlsplit(value)
            host = parsed.hostname or "127.0.0.1"
            netloc = f"{host}:{parsed.port}" if parsed.port else host
            value = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
        public[key] = value
    return json.dumps(public, ensure_ascii=False, sort_keys=True)


def status(*, runner: Runner = _run) -> str:
    command = cli_command()
    _checked([*command, "status", "--help"], runner)
    result = _checked([*command, "status", "-o", "json"], runner)
    return _redact_status(result.stdout)


def stop(*, runner: Runner = _run) -> None:
    command = cli_command()
    _checked([*command, "stop", "--help"], runner)
    _checked([*command, "stop"], runner)


def reset(*, confirm_local: bool, runner: Runner = _run) -> None:
    if not confirm_local:
        raise StackError("reset recusado: informe --confirm-local")
    _assert_unlinked()
    command = cli_command()
    help_result = _checked([*command, "db", "reset", "--help"], runner)
    if "--local" not in help_result.stdout:
        raise StackError("CLI não oferece db reset --local; atualização/revisão necessária")
    _checked([*command, "db", "reset", "--local"], runner)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "start", "status", "stop"):
        sub.add_parser(name)
    reset_parser = sub.add_parser("reset")
    reset_parser.add_argument("--confirm-local", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            print(json.dumps(asdict(doctor()), indent=2, ensure_ascii=False))
        elif args.command == "start":
            start()
        elif args.command == "status":
            print(status())
        elif args.command == "stop":
            stop()
        elif args.command == "reset":
            reset(confirm_local=args.confirm_local)
    except StackError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
