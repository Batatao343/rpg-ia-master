"""Fase 7.1 — lint de conteúdo (validadores puros + CLI + gate nos dados reais).

Spec: specs/fase-7.1-validadores-conteudo.md.
Fixtures em tmp_path; o gate `test_repo_content_sem_erros` roda nos dados reais.
"""

from __future__ import annotations

import json
import os

import yaml

from services.content_validator import (
    Finding,
    validate_aliases,
    validate_all,
    validate_encoding,
    validate_frontmatter,
    validate_ids,
    validate_references,
    validate_visibility,
)


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _write_md(codex_dir, fname: str, front: dict, body: str = "Corpo do doc.") -> str:
    os.makedirs(codex_dir, exist_ok=True)
    path = os.path.join(codex_dir, fname)
    fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\n{fm}\n---\n\n{body}\n")
    return path


def _front(entity_id: str, **extra) -> dict:
    base = {"id": entity_id, "type": "npc", "name": entity_id.title(),
            "tags": ["teste"], "visibility": "public"}
    base.update(extra)
    return base


def _write_graph(graph_dir, entities=None, extra=None, components=None,
                 edges=None, relation_types=None) -> str:
    os.makedirs(graph_dir, exist_ok=True)
    dados = {
        "entities.json": entities if entities is not None else {},
        "entities_extra.json": extra if extra is not None else {},
        "components.json": components if components is not None else {},
        "edges.json": edges if edges is not None else [],
        "relation_types.json": relation_types if relation_types is not None else {},
    }
    for fname, conteudo in dados.items():
        with open(os.path.join(graph_dir, fname), "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False, indent=1)
    return str(graph_dir)


def _ent(entity_id: str, etype: str = "npc", **extra) -> dict:
    base = {"id": entity_id, "type": etype, "name": entity_id.title(),
            "aliases": [], "tags": [], "visibility": "public", "components": {}}
    base.update(extra)
    return base


def _erros(findings: list) -> list:
    return [f for f in findings if f.severity == "error"]


# ---------------------------------------------------------------------------
# Etapa 1 — frontmatter
# ---------------------------------------------------------------------------

def test_frontmatter_ok(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum"))
    assert validate_frontmatter(codex) == []


def test_frontmatter_id_diverge_do_arquivo(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_outro"))
    findings = validate_frontmatter(codex)
    assert any("diverge do nome do arquivo" in f.message for f in _erros(findings))


def test_frontmatter_type_desconhecido(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum", type="alienigena"))
    findings = validate_frontmatter(codex)
    assert any("fora do conjunto canônico" in f.message for f in _erros(findings))


def test_frontmatter_visibility_invalida(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum", visibility="privado"))
    findings = validate_frontmatter(codex)
    assert any("visibility" in f.message for f in _erros(findings))


def test_frontmatter_tags_nao_lista(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum", tags="taverneiro"))
    findings = validate_frontmatter(codex)
    assert any("lista de strings" in f.message for f in _erros(findings))


def test_frontmatter_sem_campo_obrigatorio(tmp_path):
    codex = str(tmp_path / "codex")
    front = _front("npc_grum")
    del front["visibility"]
    _write_md(codex, "npc_grum.md", front)
    findings = validate_frontmatter(codex)
    assert any("obrigatório" in f.message for f in _erros(findings))


# ---------------------------------------------------------------------------
# Etapa 2 — ids + referências
# ---------------------------------------------------------------------------

def test_id_duplicado_no_codex(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md", _front("npc_grum"))
    _write_md(codex, "npc_grum2.md", _front("npc_grum"))
    graph = _write_graph(tmp_path / "graph")
    findings = validate_ids(codex, graph)
    assert any("id duplicado no Codex" in f.message for f in _erros(findings))


def test_extra_conflita_com_canonico(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(tmp_path / "graph",
                         entities={"npc_grum": _ent("npc_grum")},
                         extra={"npc_grum": _ent("npc_grum")})
    findings = validate_ids(codex, graph)
    assert any("conflita com entities.json" in f.message for f in _erros(findings))


def test_components_id_orfao(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(tmp_path / "graph",
                         entities={"npc_grum": _ent("npc_grum")},
                         components={"_meta": {"doc": True}, "npc_fantasma": {"hp": 10}})
    findings = validate_ids(codex, graph)
    erros = _erros(findings)
    assert any(f.entity_id == "npc_fantasma" for f in erros)
    assert not any(f.entity_id == "_meta" for f in erros)


def test_edge_target_inexistente(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(
        tmp_path / "graph",
        entities={"legiao": _ent("legiao", "faction")},
        edges=[{"id": "e1", "source": "legiao", "type": "controls",
                "target": "porto_fantasma", "visibility": "public"}],
        relation_types={"controls": {"target": "location"}})
    findings = validate_references(codex, graph)
    assert any("'porto_fantasma' não existe" in f.message for f in _erros(findings))


def test_edge_type_desconhecido(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(
        tmp_path / "graph",
        entities={"a": _ent("a"), "b": _ent("b")},
        edges=[{"id": "e1", "source": "a", "type": "casado_com", "target": "b"}],
        relation_types={"controls": {"target": "location"}})
    findings = validate_references(codex, graph)
    assert any("não existe em relation_types.json" in f.message for f in _erros(findings))


def test_edge_constraint_target_location(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(
        tmp_path / "graph",
        entities={"legiao": _ent("legiao", "faction"), "grum": _ent("grum", "npc")},
        edges=[{"id": "e1", "source": "legiao", "type": "controls", "target": "grum"}],
        relation_types={"controls": {"target": "location"}})
    findings = validate_references(codex, graph)
    assert any("constraint de 'controls'" in f.message for f in _erros(findings))


def test_edge_id_duplicado(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(
        tmp_path / "graph",
        entities={"a": _ent("a"), "b": _ent("b", "location")},
        edges=[
            {"id": "e1", "source": "a", "type": "located_in", "target": "b"},
            {"id": "e1", "source": "a", "type": "located_in", "target": "b"},
        ],
        relation_types={"located_in": {"target": "location"}})
    findings = validate_references(codex, graph)
    assert any("id de edge duplicado" in f.message for f in _erros(findings))


def test_related_entities_orfao(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md",
              _front("npc_grum", related_entities=["local_inexistente"]))
    graph = _write_graph(tmp_path / "graph", entities={"npc_grum": _ent("npc_grum")})
    findings = validate_references(codex, graph)
    assert any("'local_inexistente'" in f.message for f in _erros(findings))


def test_edge_valida_passa(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(
        tmp_path / "graph",
        entities={"legiao": _ent("legiao", "faction"),
                  "arcadia": _ent("arcadia", "location")},
        edges=[{"id": "e1", "source": "legiao", "type": "controls", "target": "arcadia"}],
        relation_types={"controls": {"target": "location"}})
    assert _erros(validate_references(codex, graph)) == []


# ---------------------------------------------------------------------------
# Etapa 3 — aliases + visibilidade
# ---------------------------------------------------------------------------

def test_alias_duplicado_entre_entidades(tmp_path):
    graph = _write_graph(
        tmp_path / "graph",
        entities={
            "skallgard": _ent("skallgard", "location", aliases=["Ermo Branco"]),
            "outro_lugar": _ent("outro_lugar", "location", aliases=["ermo branco"]),
        })
    findings = validate_aliases(graph)
    assert any("duplicado" in f.message for f in _erros(findings))


def test_alias_colide_com_name_de_outra(tmp_path):
    graph = _write_graph(
        tmp_path / "graph",
        entities={
            "npc_grum": _ent("npc_grum", "npc", name="Grum"),
            "npc_falso": _ent("npc_falso", "npc", aliases=["grum"]),
        })
    findings = validate_aliases(graph)
    assert any("colide com name/id" in f.message for f in _erros(findings))


def test_alias_proprio_nao_colide(tmp_path):
    graph = _write_graph(
        tmp_path / "graph",
        entities={"npc_grum": _ent("npc_grum", "npc", name="Grum", aliases=["Grum"])})
    assert _erros(validate_aliases(graph)) == []


def test_secret_type_com_visibility_public_falha(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "secret_x.md",
              _front("secret_x", type="secret", visibility="public"))
    graph = _write_graph(tmp_path / "graph")
    findings = validate_visibility(codex, graph)
    assert any("precisa de visibility 'secret'" in f.message for f in _erros(findings))


def test_public_referencia_secret_falha(tmp_path):
    codex = str(tmp_path / "codex")
    _write_md(codex, "npc_grum.md",
              _front("npc_grum", related_entities=["segredo_mundo"]))
    graph = _write_graph(
        tmp_path / "graph",
        entities={"npc_grum": _ent("npc_grum"),
                  "segredo_mundo": _ent("segredo_mundo", "npc", visibility="secret")})
    findings = validate_visibility(codex, graph)
    assert any("vaza a existência do segredo" in f.message for f in _erros(findings))


def test_visibility_invalida_no_grafo(tmp_path):
    codex = str(tmp_path / "codex")
    graph = _write_graph(tmp_path / "graph",
                         entities={"x": _ent("x", visibility="oculto")})
    findings = validate_visibility(codex, graph)
    assert any("inválida no grafo" in f.message for f in _erros(findings))


# ---------------------------------------------------------------------------
# Etapa 4 — encoding + validate_all + CLI
# ---------------------------------------------------------------------------

def test_arquivo_cp1252_falha(tmp_path):
    path = str(tmp_path / "quebrado.md")
    with open(path, "wb") as f:
        f.write("---\nid: x\n---\ncoração de pedra\n".encode("cp1252"))
    findings = validate_encoding([path])
    assert any(f.severity == "error" and "UTF-8" in f.message for f in findings)


def test_mojibake_gera_aviso_nao_erro(tmp_path):
    path = str(tmp_path / "mojibake.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("O coraÃ§Ã£o da cidade nÃ£o dorme.\n")
    findings = validate_encoding([path])
    assert findings and all(f.severity == "warning" for f in findings)
    assert any("mojibake" in f.message for f in findings)


def test_utf8_legitimo_sem_findings(tmp_path):
    path = str(tmp_path / "ok.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("SÃO PAULO: coração, não, açúcar — prosa PT-BR legítima.\n")
    assert validate_encoding([path]) == []


def test_validate_all_agrega_e_ordena(tmp_path):
    codex = str(tmp_path / "codex")
    # erro de frontmatter (type) + erro de referência (related órfão)
    _write_md(codex, "npc_a.md", _front("npc_a", type="alienigena"))
    _write_md(codex, "npc_b.md", _front("npc_b", related_entities=["nada"]))
    graph = _write_graph(tmp_path / "graph",
                         entities={"npc_a": _ent("npc_a"), "npc_b": _ent("npc_b")})
    findings = validate_all(codex, graph)
    validadores = [f.validator for f in _erros(findings)]
    assert "frontmatter" in validadores and "references" in validadores
    # erros antes de avisos; ordenação estável por (severity, validator, path)
    severities = [f.severity for f in findings]
    assert severities == sorted(severities)


def test_cli_exit_code(tmp_path, capsys):
    import scripts.validate_content as cli

    codex_ok = str(tmp_path / "codex_ok")
    _write_md(codex_ok, "npc_a.md", _front("npc_a"))
    graph_ok = _write_graph(tmp_path / "graph_ok",
                            entities={"npc_a": _ent("npc_a")})
    assert cli.main(codex_ok, graph_ok) == 0
    assert "0 ERRO(S)" in capsys.readouterr().out

    codex_ruim = str(tmp_path / "codex_ruim")
    _write_md(codex_ruim, "npc_b.md", _front("npc_b", type="alienigena"))
    graph_ruim = _write_graph(tmp_path / "graph_ruim",
                              entities={"npc_b": _ent("npc_b")})
    assert cli.main(codex_ruim, graph_ruim) == 1
    assert "ERRO" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Etapa 5 — gate sobre os dados reais do repo
# ---------------------------------------------------------------------------

def test_repo_content_sem_erros():
    findings = validate_all()
    erros = _erros(findings)
    for f in findings:
        if f.severity == "warning":
            print(f"AVISO [{f.validator}] {f.path}: {f.message}")
    assert erros == [], "\n".join(
        f"[{f.validator}] {f.path} ({f.entity_id}): {f.message}" for f in erros)
