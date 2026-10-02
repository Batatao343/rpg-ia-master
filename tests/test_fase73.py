"""Fase 7.3 — separação público/segredo nos NPCs do Codex.

Spec: specs/SPEC-024-fase-7.3-npc-segredos.md.
Etapas 1-3 em fixtures; testes de dado real (Valerius) rodam sobre data/codex/.
"""

from __future__ import annotations

import json
import os

import yaml

import scripts.migrate_lore_nova as migrate
from scripts.migrate_lore_nova import split_npc_secrets
from services.codex_loader import parse_codex_file
from services.content_validator import validate_visibility


# ---------------------------------------------------------------------------
# Etapa 1 — split_npc_secrets
# ---------------------------------------------------------------------------

def test_split_move_historia_real():
    body = ("Papel: taverneiro da vila.\n\n"
            "História real: fez pacto com Daruun.\n\n"
            "Aparência: gordo e simpático.")
    publico, secreto = split_npc_secrets(body)
    assert "pacto com Daruun" not in publico
    assert "pacto com Daruun" in secreto
    assert "taverneiro da vila" in publico
    assert "gordo e simpático" in publico


def test_split_preserva_paragrafo_sem_rotulo():
    body = "Uma linha de prosa livre, sem rótulo nenhum.\n\nSegredo: algo oculto."
    publico, secreto = split_npc_secrets(body)
    assert "prosa livre" in publico
    assert "algo oculto" in secreto


def test_split_rotulo_com_acento():
    body = "Motivação real: vingança contra o irmão."
    publico, secreto = split_npc_secrets(body)
    assert publico == ""
    assert "vingança" in secreto


def test_split_sem_segredo_devolve_vazio():
    body = "Papel: ferreiro.\n\nAparência: braços como troncos."
    publico, secreto = split_npc_secrets(body)
    assert secreto == ""
    assert "ferreiro" in publico


def test_split_titulo_fica_no_publico():
    body = "# GRUM — TAVERNEIRO\n\nHistória real: um segredo."
    publico, secreto = split_npc_secrets(body)
    assert publico.startswith("# GRUM")
    assert "um segredo" in secreto


def test_split_rumor_verdadeiro_e_secreto():
    body = "Rumor verdadeiro: a maldição do porto é real."
    publico, secreto = split_npc_secrets(body)
    assert publico == ""
    assert "maldição" in secreto


# ---------------------------------------------------------------------------
# Etapa 2 — migrate escreve o doc paralelo
# ---------------------------------------------------------------------------

_LORE_VAZIO = ("locations.txt", "factions.txt", "races.txt", "creatures.txt",
               "items.txt", "secrets.txt", "faction_perspectives.txt",
               "rumors.txt", "daily_life.txt")


def _run_migrate(tmp_path, monkeypatch, npcs_txt: str):
    lore = tmp_path / "lore"
    lore.mkdir()
    for fname in _LORE_VAZIO:
        (lore / fname).write_text("", encoding="utf-8")
    (lore / "npcs.txt").write_text(npcs_txt, encoding="utf-8")
    codex = tmp_path / "codex"
    graph = tmp_path / "graph"
    monkeypatch.setattr(migrate, "LORE_DIR", str(lore))
    monkeypatch.setattr(migrate, "CODEX_DIR", str(codex))
    monkeypatch.setattr(migrate, "GRAPH_DIR", str(graph))
    entities = migrate.main()
    return str(codex), str(graph), entities


_NPC_COM_SEGREDO = """[CATEGORIA: NPC]
[TAGS: Teste]
GRUM — TAVERNEIRO

Papel: taverneiro da vila.

História real: Grum vendeu a alma a Daruun.
"""

_NPC_SEM_SEGREDO = """[CATEGORIA: NPC]
[TAGS: Teste]
BORIN — FERREIRO

Papel: ferreiro honesto.
"""


def test_migrate_gera_doc_segredo_hidden(tmp_path, monkeypatch):
    codex, _graph, _entities = _run_migrate(tmp_path, monkeypatch, _NPC_COM_SEGREDO)
    pub_path = os.path.join(codex, "npcs", "npc_grum.md")
    sec_path = os.path.join(codex, "npcs", "segredos", "npc_grum_segredo.md")
    assert os.path.isfile(pub_path) and os.path.isfile(sec_path)

    fm_pub, body_pub = parse_codex_file(pub_path)
    assert "vendeu a alma" not in body_pub
    assert "taverneiro da vila" in body_pub

    fm_sec, body_sec = parse_codex_file(sec_path)
    assert fm_sec["id"] == "npc_grum_segredo"
    assert fm_sec["type"] == "npc_secret"
    assert fm_sec["visibility"] == "hidden"
    assert fm_sec["related_entities"] == ["npc_grum"]
    assert fm_sec["tags"] == fm_pub["tags"]
    assert "vendeu a alma" in body_sec


def test_npc_sem_segredo_nao_gera_arquivo(tmp_path, monkeypatch):
    codex, _graph, _entities = _run_migrate(tmp_path, monkeypatch, _NPC_SEM_SEGREDO)
    assert os.path.isfile(os.path.join(codex, "npcs", "npc_borin.md"))
    assert not os.path.exists(os.path.join(codex, "npcs", "segredos", "npc_borin_segredo.md"))


def test_segredo_nao_registra_entidade(tmp_path, monkeypatch):
    _codex, graph, entities = _run_migrate(tmp_path, monkeypatch, _NPC_COM_SEGREDO)
    assert "npc_grum" in entities
    assert "npc_grum_segredo" not in entities
    with open(os.path.join(graph, "entities.json"), encoding="utf-8") as f:
        dumped = json.load(f)
    assert "npc_grum_segredo" not in dumped


# ---------------------------------------------------------------------------
# Etapa 3 — lint anti-regressão
# ---------------------------------------------------------------------------

def _write_md(codex_dir, fname: str, front: dict, body: str) -> str:
    os.makedirs(codex_dir, exist_ok=True)
    path = os.path.join(codex_dir, fname)
    fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\n{fm}\n---\n\n{body}\n")
    return path


def _graph_vazio(tmp_path) -> str:
    graph = tmp_path / "graph"
    graph.mkdir(exist_ok=True)
    for fname in ("entities.json", "entities_extra.json", "components.json"):
        (graph / fname).write_text("{}", encoding="utf-8")
    (graph / "edges.json").write_text("[]", encoding="utf-8")
    (graph / "relation_types.json").write_text("{}", encoding="utf-8")
    return str(graph)


def _front(entity_id: str, etype: str = "npc", vis: str = "public") -> dict:
    return {"id": entity_id, "type": etype, "name": entity_id,
            "tags": [], "visibility": vis}


def test_lint_public_com_rotulo_secreto_erro(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_x.md", _front("npc_x"),
              "Papel: guarda.\n\nMotivação real: trair o rei.")
    findings = validate_visibility(codex, _graph_vazio(tmp_path))
    assert any(f.severity == "error" and "rótulo secreto" in f.message for f in findings)


def test_lint_npc_secret_public_erro(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_x_segredo.md",
              _front("npc_x_segredo", etype="npc_secret", vis="public"),
              "Verdade: tudo mentira.")
    findings = validate_visibility(codex, _graph_vazio(tmp_path))
    assert any(f.severity == "error" and "npc_secret" in f.message for f in findings)


def test_lint_npc_secret_hidden_ok(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_x_segredo.md",
              _front("npc_x_segredo", etype="npc_secret", vis="hidden"),
              "Verdade: tudo mentira.")
    findings = validate_visibility(codex, _graph_vazio(tmp_path))
    assert [f for f in findings if f.severity == "error"] == []


def test_lint_rotulo_em_doc_hidden_de_npc_nao_acusa(tmp_path):
    # o rótulo só é proibido em doc PÚBLICO de NPC
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_x.md", _front("npc_x", vis="hidden"),
              "História real: oculta de propósito.")
    findings = validate_visibility(codex, _graph_vazio(tmp_path))
    assert [f for f in findings if f.severity == "error"] == []


# ---------------------------------------------------------------------------
# Etapa 4 — dado real (roda sobre data/codex/ regenerado)
# ---------------------------------------------------------------------------

def test_valerius_publico_sem_pacto():
    path = os.path.join("data", "codex", "npcs", "npc_valerius.md")
    assert os.path.isfile(path)
    _fm, body = parse_codex_file(path)
    plain = body.lower()
    assert "história real" not in plain
    assert "motivação real" not in plain
    assert "pacto com daruun" not in plain


def test_valerius_segredo_hidden():
    path = os.path.join("data", "codex", "npcs", "segredos", "npc_valerius_segredo.md")
    assert os.path.isfile(path)
    fm, body = parse_codex_file(path)
    assert fm["type"] == "npc_secret"
    assert fm["visibility"] == "hidden"
    assert fm["related_entities"] == ["npc_valerius"]
    assert "daruun" in body.lower()


def test_codex_body_nao_vaza_segredo():
    from services.codex_loader import clear_codex_index_cache, codex_body
    clear_codex_index_cache()
    assert codex_body("npc_valerius_segredo") == ""
    publico = codex_body("npc_valerius")
    assert "pacto com Daruun" not in publico
    clear_codex_index_cache()
