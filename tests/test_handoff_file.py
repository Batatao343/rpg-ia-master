"""SPEC-415 R21: `scripts/dev/handoff.py` (handoff de sessao em formato fixo)."""

from __future__ import annotations

import datetime
from pathlib import Path

from scripts.dev import handoff as ho

NOW = datetime.datetime(2026, 11, 12, 9, 30)
FACTS = {"main": "abc123 assunto\n\n3 commit(s) à frente.", "worktrees": "/x [spec-415]"}


def test_render_has_fixed_sections_in_order() -> None:
    text = ho.render(FACTS, NOW)
    assert text.startswith("# Handoff do coordenador — 2026-11-12 09:30")
    pos = [text.index(f"## {s}\n") for s in ho.SECTIONS]
    assert pos == sorted(pos) and len(pos) == 7
    assert "abc123 assunto" in text and "Ver ESTADO_ATUAL.md § Bloqueios" in text


def test_check_flags_placeholders_and_missing_sections() -> None:
    text = ho.render(FACTS, NOW)
    assert any("PREENCHER" in p for p in ho.check(text))
    filled = text.replace("<PREENCHER: comando → resultado>", "x").replace("<PREENCHER>", "x")
    filled = filled.replace("<PREENCHER: 1 a 3 itens>", "x").replace(
        "<PREENCHER: lições/armadilhas desta sessão>", "x"
    )
    assert ho.check(filled) == []
    assert ho.check(filled.replace("## Não refazer\n", "")) != []


def test_existing_file_rotates_to_prev(tmp_path: Path) -> None:
    out = tmp_path / "handoff-2026-11-12.md"
    prev = tmp_path / "handoff-2026-11-12.prev.md"
    prev.write_text("antigo", encoding="utf-8")
    out.write_text("v1", encoding="utf-8")
    ho.write(out, "v2")
    assert out.read_text(encoding="utf-8") == "v2"
    assert prev.read_text(encoding="utf-8") == "v1"
