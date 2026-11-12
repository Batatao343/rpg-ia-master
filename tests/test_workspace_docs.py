"""SPEC-415: documentos de processo (template, guia de casos, agentes, ruff, gitattributes).

Teste de documento, nao de codigo-fonte (docs/guias/TESTES.md, "Onde mora um teste novo").
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ["concorrência", "sql-rls", "api", "persistência", "llm-structured"]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ruff_format_excludes_specs_and_handoffs() -> None:
    cfg = tomllib.loads(_read("pyproject.toml"))
    exclude = cfg["tool"]["ruff"]["format"]["exclude"]
    assert "specs/**" in exclude and "handoffs/**" in exclude


def test_template_has_new_sections() -> None:
    text = _read("specs/TEMPLATE.md")
    for needle in ("## Invariantes", "## Concorrência", "## Não rodou e por quê"):
        assert needle in text
    assert "**Requer:**" in text and "**Domínios de revisão:**" in text
    old = [
        "## 1. Contexto",
        "## 2. Requisitos",
        "## 3. Design",
        "## 4. Plano",
        "## 5. Crit",
        "## 6. Smoke",
        "## 7. Riscos",
    ]
    pos = [text.index(h) for h in old]
    assert pos == sorted(pos)
    assert "<MEDIR:" not in text


def test_reviewer_cases_guide_shape() -> None:
    text = _read("docs/guias/CASOS_QUE_O_REVISOR_PEDE.md")
    heads = re.findall(r"^## (.+)$", text, re.M)
    assert heads == DOMAINS
    for block in re.split(r"^## .+$", text, flags=re.M)[1:]:
        items = [ln for ln in block.splitlines() if ln.startswith("- ")]
        assert 1 <= len(items) <= 12
        assert all(ln.rstrip().endswith(")") for ln in items)


def test_cases_guide_is_union_merge() -> None:
    attrs = _read(".gitattributes")
    assert "docs/guias/CASOS_QUE_O_REVISOR_PEDE.md merge=union" in attrs


def test_agent_docs_mention_new_rules() -> None:
    reviewer = _read(".claude/agents/spec-reviewer.md")
    for word in ("sol", "terra", "red_green.sh", "CASOS_QUE_O_REVISOR_PEDE"):
        assert word in reviewer
    author = _read(".claude/agents/spec-author.md")
    tools = re.search(r"^tools:(.*)$", author, re.M).group(1)
    assert "Bash" in tools and "<MEDIR:" in author
    executor = _read(".claude/agents/spec-executor.md")
    for word in ("size_budget", "F401", "Requer: web"):
        assert word in executor


def test_review_handoff_template_has_evidence_section() -> None:
    assert "## Evidência verificada" in _read("docs/templates/handoff-review.md")
