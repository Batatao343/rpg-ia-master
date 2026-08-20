"""Registra evidências G0–G7 e produz relatório único JSON + Markdown."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observability.telemetry import redact


GATES = {
    "G0": "suíte offline",
    "G1": "integração local",
    "G2": "segurança local",
    "G3": "caos local",
    "G4": "carga multiworker",
    "G5": "soak de 1.000 turnos",
    "G6": "backup/restore",
    "G7": "browser/build/lint/audits",
}


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], text=True, capture_output=True, check=False,
    )
    return result.stdout.strip()[:200]


def record_gate(root: Path, gate: str, *, status: str, command: str,
                evidence: str, metrics: dict[str, Any] | None = None) -> Path:
    gate = gate.upper()
    if gate not in GATES:
        raise ValueError(f"gate inválido: {gate}")
    if status not in {"passed", "failed", "skipped"}:
        raise ValueError("status deve ser passed, failed ou skipped")
    payload = redact({
        "gate": gate,
        "name": GATES[gate],
        "status": status,
        "command": command,
        "evidence": evidence,
        "metrics": metrics or {},
        "recorded_at": datetime.now(UTC).isoformat(),
    })
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{gate.lower()}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_report(root: Path, output_dir: Path) -> dict[str, Any]:
    gates: dict[str, dict[str, Any]] = {}
    for gate, name in GATES.items():
        source = root / f"{gate.lower()}.json"
        if source.exists():
            row = json.loads(source.read_text(encoding="utf-8"))
        else:
            row = {"gate": gate, "name": name, "status": "missing", "evidence": ""}
        gates[gate] = row
    ready = all(row.get("status") == "passed" for row in gates.values())
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ready_local": ready,
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "dirty": bool(_git("status", "--porcelain")),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "gates": gates,
        "pending": [gate for gate, row in gates.items() if row.get("status") != "passed"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "readiness-local.json"
    md_path = output_dir / "readiness-local.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Valoria — prontidão local", "",
        f"- Resultado: **{'READY' if ready else 'NOT READY'}**",
        f"- Commit: `{payload['git']['commit']}`",
        f"- Gerado: {payload['generated_at']}", "",
        "| Gate | Escopo | Estado | Evidência |", "|---|---|---|---|",
    ]
    for gate, row in gates.items():
        evidence = str(row.get("evidence") or "—").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {gate} | {GATES[gate]} | {row.get('status')} | {evidence} |")
    if payload["pending"]:
        lines.extend(["", "## Pendências", "", ", ".join(payload["pending"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("readiness_artifacts/gates"))
    sub = parser.add_subparsers(dest="action", required=True)
    record = sub.add_parser("record")
    record.add_argument("gate", choices=sorted(GATES))
    record.add_argument("--status", choices=("passed", "failed", "skipped"), required=True)
    record.add_argument("--command", required=True)
    record.add_argument("--evidence", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output-dir", type=Path, default=Path("docs/readiness"))
    args = parser.parse_args()
    if args.action == "record":
        print(record_gate(
            args.root, args.gate, status=args.status,
            command=args.command, evidence=args.evidence,
        ))
        return 0
    report = build_report(args.root, args.output_dir)
    print(json.dumps({"ready_local": report["ready_local"], "pending": report["pending"]}))
    return 0 if report["ready_local"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
