"""SPEC-310 R15 — lint dos tópicos vagos de segredo (data/npc_secret_topics.json)."""

from __future__ import annotations

import json
from pathlib import Path

from services import content_validator as cv
from services import npc_seed

TOPICS = json.loads(
    (Path(npc_seed.SEED_TABLES_PATH).parent / "npc_secret_topics.json").read_text(encoding="utf-8")
)
SECRETS = npc_seed.load_seed_tables()["secrets"]


def test_todo_segredo_tem_topico():
    assert cv.lint_secret_topics(TOPICS, SECRETS) == []
    assert len(SECRETS) == 44 and {r["id"] for r in SECRETS} <= set(TOPICS)


def test_topico_nao_repete_palavra_do_label():
    bad = {**TOPICS, "sec_desertor": "um grupo armado desconhecido"}
    problems = cv.lint_secret_topics(bad, SECRETS)
    assert any("sec_desertor" in p and "palavra" in p for p in problems)


def test_lint_pega_ausente_longo_e_id_orfao():
    broken = {k: v for k, v in TOPICS.items() if k != "sec_amante"}
    broken["sec_poupanca"] = "x" * 61
    broken["sec_fantasma"] = "qualquer coisa"
    problems = cv.lint_secret_topics(broken, SECRETS)
    assert any("sec_amante: sem tópico" in p for p in problems)
    assert any("sec_poupanca" in p and "60" in p for p in problems)
    assert any("sec_fantasma" in p for p in problems)


def test_validate_all_inclui_o_lint():
    assert cv.validate_npc_secret_topics() == []
