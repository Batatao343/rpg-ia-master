"""SPEC-416 Bloco D: evidência de staging não cai em `docs/` por padrão.

O teste por AST percorre `scripts/staging/*.py` (caso "proibição de chamada" de
`docs/guias/TESTES.md`): é a única forma de pegar um default novo em caminho versionado.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from scripts.staging import common, incident_drill, s192

STAGING = Path(common.__file__).resolve().parent


def test_write_evidence_default_fora_de_docs(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    path = common.write_evidence("x", {"ok": True})
    assert path == tmp_path / ".tmp" / "evidence" / "x.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
    assert not (tmp_path / "docs").exists()


def test_write_evidence_out_explicito_respeitado(tmp_path):
    out = tmp_path / "docs" / "x.json"
    assert common.write_evidence("x", {"ok": 1}, out) == out
    assert out.exists()


def _is_docs(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (node.value == "docs" or node.value.startswith("docs/"))
    )


def _offenders(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _is_docs(node.left) or _is_docs(node.right):
                lines.append(node.lineno)
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument":
            lines += [
                node.lineno
                for kw in node.keywords
                if kw.arg == "default" and any(_is_docs(n) for n in ast.walk(kw.value))
            ]
    return lines


def test_nenhum_default_em_docs_nos_scripts_de_staging():
    bad = {}
    for path in sorted(STAGING.glob("*.py")):
        found = _offenders(ast.parse(path.read_text(encoding="utf-8")))
        if found:
            bad[path.name] = found
    assert not bad, f"default de saída em docs/ (use .tmp/evidence/): {bad}"


def test_incident_drill_acumula_no_caminho_efetivo(monkeypatch, tmp_path):
    out = tmp_path / "drill.json"
    monkeypatch.setattr(s192, "load_env", dict)
    monkeypatch.setattr(incident_drill, "kill_switch", lambda base, env: {"ok": True})
    monkeypatch.setattr(incident_drill, "rollback", lambda base, env, *rest: {"ok": True, "t": 1})
    assert incident_drill.main(["kill-switch", "--out", str(out)]) == 0
    assert incident_drill.main(["rollback", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert {"kill_switch", "vercel_rollback"} <= set(data)
