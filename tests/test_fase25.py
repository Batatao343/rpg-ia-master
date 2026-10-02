"""
Suíte da Fase 2.5 — Codex estruturado + World State Graph.
Spec: specs/SPEC-001-fase-2.5-codex-world-state.md. 100% offline (sem embeddings/LLM real).
"""

import json
import os
import uuid

import pytest

import persistence
from persistence import load_game_state, save_game_state


# ---------------------------------------------------------------------------
# Etapa 1 — event_log / world_projection / pending_world_events no save
# ---------------------------------------------------------------------------

def _estado_minimo(game_id: str) -> dict:
    return {
        "game_id": game_id,
        "narrative_summary": "resumo",
        "player": {"name": "Testa", "hp": 10},
        "world": {"current_location": "Nova Arcádia", "turn_count": 3},
        "messages": [],
    }


def test_save_antigo_carrega_sem_event_log(tmp_path, monkeypatch):
    """Save de antes da fase (sem os campos novos) carrega com defaults vazios."""
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    save_antigo = {
        "game_id": "legacy",
        "narrative_summary": "antigo",
        "player": {"name": "Velho"},
        "world": {},
        "message_history": [],
    }
    file_path = tmp_path / "legacy.json"
    file_path.write_text(json.dumps(save_antigo), encoding="utf-8")

    state = load_game_state(str(file_path))

    assert state is not None
    assert state["event_log"] == []
    assert state["world_projection"] == {}
    assert state["pending_world_events"] == []


def test_save_roundtrip_event_log(tmp_path, monkeypatch):
    """event_log + world_projection sobrevivem a save → load intactos."""
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    game_id = f"t25-{uuid.uuid4().hex[:8]}"

    eventos = [
        {
            "event_id": uuid.uuid4().hex,
            "turn": 3,
            "type": "npc_killed",
            "actor_id": "player",
            "target_id": "npc_valerius",
            "payload": {"metodo": "duelo"},
            "source": "test",
        },
        {
            "event_id": uuid.uuid4().hex,
            "turn": 4,
            "type": "location_control_changed",
            "actor_id": "mao_sombria",
            "target_id": "brekmar",
            "payload": {},
            "source": "test",
        },
    ]
    projection = {
        "entities": {"npc_valerius": {"alive": False}},
        "dynamic_edges": [
            {
                "id": "dyn_1",
                "source": "mao_sombria",
                "type": "controls",
                "target": "brekmar",
                "created_by_event": eventos[1]["event_id"],
            }
        ],
        "disabled_edges": [],
        "revealed_facts": {},
        "location_summaries": {"brekmar": "Porto sob novo controle."},
    }

    state = _estado_minimo(game_id)
    state["event_log"] = eventos
    state["world_projection"] = projection
    state["pending_world_events"] = [{"type": "rascunho"}]

    assert save_game_state(state) is True
    loaded = load_game_state(os.path.join(str(tmp_path), f"{game_id}.json"))

    assert loaded["event_log"] == eventos
    assert loaded["world_projection"] == projection
    assert loaded["pending_world_events"] == [{"type": "rascunho"}]


# ---------------------------------------------------------------------------
# Etapa 2 — grafo estático autoral (entities/edges/relation_types)
# ---------------------------------------------------------------------------

GRAPH_DIR = os.path.join("data", "graph")
TIPOS_CONHECIDOS = {"location", "faction", "npc", "race", "monster", "artifact"}


def _load_json(*parts):
    with open(os.path.join(*parts), "r", encoding="utf-8") as f:
        return json.load(f)


def test_entities_ids_unicos_e_validos():
    entities = _load_json(GRAPH_DIR, "entities.json")
    assert len(entities) > 0
    for entity_id, ent in entities.items():
        assert ent["id"] == entity_id, f"chave != id em {entity_id}"
        for campo in ("id", "type", "name", "aliases", "tags", "visibility", "components"):
            assert campo in ent, f"{entity_id} sem campo '{campo}'"
        assert ent["type"] in TIPOS_CONHECIDOS, f"{entity_id} tipo desconhecido: {ent['type']}"
        assert ent["visibility"] in {"public", "hidden", "secret"}


def test_edges_referenciam_entidades_existentes():
    entities = _load_json(GRAPH_DIR, "entities.json")
    edges = _load_json(GRAPH_DIR, "edges.json")
    relation_types = _load_json(GRAPH_DIR, "relation_types.json")
    assert len(edges) > 0
    ids_vistos = set()
    for edge in edges:
        assert edge["id"] not in ids_vistos, f"edge id duplicado: {edge['id']}"
        ids_vistos.add(edge["id"])
        assert edge["source"] in entities, f"{edge['id']}: source '{edge['source']}' não existe"
        assert edge["target"] in entities, f"{edge['id']}: target '{edge['target']}' não existe"
        assert edge["type"] in relation_types, f"{edge['id']}: tipo '{edge['type']}' não declarado"
        assert edge.get("visibility", "public") in {"public", "hidden", "secret"}


def test_locais_overlap_tem_entidade():
    """Os 5 ids do mapa atual que sobrevivem no mundo novo têm nó no grafo.

    Cobertura total de world_map.json fica para a 2.5b (mapa realinhado a Valoria).
    """
    entities = _load_json(GRAPH_DIR, "entities.json")
    for loc_id in ("nova_arcadia", "deserto_zhur", "floresta_sussurros",
                   "montanhas_afiadas", "skallgard"):
        assert loc_id in entities, f"local '{loc_id}' sem entidade"
        assert entities[loc_id]["type"] == "location"


def test_migracao_idempotente(tmp_path, monkeypatch):
    """Rodar o script 2x produz o mesmo conjunto de entidades (sem duplicar)."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "migrate_lore_nova", os.path.join("scripts", "migrate_lore_nova.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["migrate_lore_nova"] = mod  # dataclasses resolve via sys.modules
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "CODEX_DIR", str(tmp_path / "codex"))
    monkeypatch.setattr(mod, "GRAPH_DIR", str(tmp_path / "graph"))

    primeira = mod.main()
    segunda = mod.main()

    assert set(primeira) == set(segunda)
    assert primeira == segunda


# ---------------------------------------------------------------------------
# Etapa 3 — graph_resolver (base + dinâmico, visibility)
# ---------------------------------------------------------------------------

from services import graph_resolver


def test_controller_vem_do_lore_base():
    """Projection vazia → controlador vem das edges base (poder_kahen em Brekmar)."""
    assert graph_resolver.get_current_controller("brekmar", {}) == "poder_kahen"


def test_dynamic_edge_vence_base():
    proj = {
        "disabled_edges": [{"edge_id": "e_kahen_controla_brekmar"}],
        "dynamic_edges": [
            {"id": "dyn_x", "source": "mao_sombria", "type": "controls", "target": "brekmar"}
        ],
    }
    assert graph_resolver.get_current_controller("brekmar", proj) == "mao_sombria"


def test_edge_hidden_nao_aparece_sem_flag():
    edges = graph_resolver.resolve_edges({}, entity_id="npc_velha_magda")
    tipos = {e["type"] for e in edges}
    assert "leads" not in tipos  # e_magda_lidera_mao é secret
    edges_all = graph_resolver.resolve_edges({}, entity_id="npc_velha_magda", include_hidden=True)
    assert any(e["type"] == "leads" for e in edges_all)


def test_resolve_edges_filtra_por_tipo():
    controles = graph_resolver.resolve_edges({}, edge_type="controls")
    assert all(e["type"] == "controls" for e in controles)
    assert any(e["target"] == "nova_arcadia" for e in controles)


def test_is_alive_default_true():
    assert graph_resolver.is_alive("npc_valerius", {}) is True
    proj = {"entities": {"npc_valerius": {"alive": False}}}
    assert graph_resolver.is_alive("npc_valerius", proj) is False


def test_get_entity_lookup():
    ent = graph_resolver.get_entity("legiao_ferro")
    assert ent is not None and ent["type"] == "faction"
    assert graph_resolver.get_entity("nao_existe_xyz") is None


# ---------------------------------------------------------------------------
# Etapas 4/5 — Codex (frontmatter, chunks com metadados, visibilidade)
# ---------------------------------------------------------------------------

from services import codex_loader

CODEX_DIR = os.path.join("data", "codex")


def _todos_arquivos_codex():
    for root, _dirs, files in os.walk(CODEX_DIR):
        for fname in files:
            if fname.endswith(".md"):
                yield os.path.join(root, fname)


def test_codex_frontmatter_valido():
    """Todo .md do Codex parseia, tem campos obrigatórios e id rastreável."""
    entities = _load_json(GRAPH_DIR, "entities.json")
    arquivos = list(_todos_arquivos_codex())
    assert len(arquivos) > 100  # migração completa, não amostra

    for path in arquivos:
        frontmatter, body = codex_loader.parse_codex_file(path)
        for campo in ("id", "type", "name", "tags", "visibility"):
            assert campo in frontmatter, f"{path} sem '{campo}'"
        assert frontmatter["visibility"] in {"public", "hidden", "secret"}
        assert body.strip(), f"{path} sem corpo"
        cid = frontmatter["id"]
        # story_/secret_/timeline_ são documentos de mundo, não entidades do grafo;
        # *_segredo (type npc_secret, Fase 7.3) também não registra entidade
        if not cid.startswith(("story_", "secret_", "timeline_")) \
                and frontmatter["type"] != "npc_secret":
            assert cid in entities, f"{path}: id '{cid}' não existe em entities.json"


def test_parse_codex_file_rejeita_sem_id(tmp_path):
    ruim = tmp_path / "ruim.md"
    ruim.write_text(
        "---\ntype: npc\nname: Sem Id\ntags: []\nvisibility: public\n---\ncorpo",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        codex_loader.parse_codex_file(str(ruim))


def test_load_codex_gera_chunks_com_metadata():
    docs = codex_loader.load_codex()
    assert len(docs) > 100
    for doc in docs:
        assert "id" in doc.metadata and "visibility" in doc.metadata
        assert doc.metadata["visibility"] in {"public", "hidden", "secret"}
    # segredos preservam visibility nos chunks
    assert any(d.metadata["visibility"] == "secret" for d in docs)


def test_vis_rank_ordena():
    from rag import vis_rank

    assert vis_rank("public") < vis_rank("hidden") < vis_rank("secret")
    assert vis_rank(None) == vis_rank("public")        # chunk antigo sem metadado
    assert vis_rank("desconhecida") == vis_rank("secret")  # falha fechada


# ---------------------------------------------------------------------------
# Timeline — ingestão de lore_nova/timeline_completa.txt no Codex
# (reveals que secrets.txt protege NÃO podem vazar como `public`)
# ---------------------------------------------------------------------------

TIMELINE_DIR = os.path.join(CODEX_DIR, "timeline")


def _load_migrate_module():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "migrate_lore_nova", os.path.join("scripts", "migrate_lore_nova.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["migrate_lore_nova"] = mod
    spec.loader.exec_module(mod)
    return mod


def _strip_lower(text: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    ).lower()


def test_timeline_gerada_uma_por_era():
    """data/codex/timeline/ existe e cobre as 8 eras (0–7)."""
    assert os.path.isdir(TIMELINE_DIR), "timeline não foi gerada — rodar migrate"
    eras = set()
    for path in _todos_arquivos_codex():
        if os.path.dirname(path).endswith("timeline"):
            fm, _ = codex_loader.parse_codex_file(path)
            assert fm["type"] == "timeline"
            for tag in fm["tags"]:
                if tag.startswith("era_"):
                    eras.add(int(tag.split("_")[1]))
    assert eras == set(range(8)), f"eras faltando/sobrando: {sorted(eras)}"


def test_timeline_reveals_sao_hidden():
    """Os 4 clusters de reveal caem em docs `hidden` (start-phrase → visibility)."""
    mod = _load_migrate_module()
    docs = {}
    for path in _todos_arquivos_codex():
        if os.path.dirname(path).endswith("timeline"):
            fm, body = codex_loader.parse_codex_file(path)
            docs[fm["id"]] = (fm["visibility"], _strip_lower(body))

    for start_ph, _end_ph in mod._TIMELINE_HIDDEN_CLUSTERS:
        achou = [vis for vis, body in docs.values() if start_ph in body]
        assert achou, f"cluster não encontrado na timeline: {start_ph!r}"
        assert all(v == "hidden" for v in achou), \
            f"reveal vazou como público: {start_ph!r} -> {achou}"


def test_timeline_public_nao_vaza_reveal():
    """Nenhum doc `public` da timeline contém a frase-inicial de um reveal."""
    mod = _load_migrate_module()
    for path in _todos_arquivos_codex():
        if not os.path.dirname(path).endswith("timeline"):
            continue
        fm, body = codex_loader.parse_codex_file(path)
        if fm["visibility"] != "public":
            continue
        plain = _strip_lower(body)
        for start_ph, _end in mod._TIMELINE_HIDDEN_CLUSTERS:
            assert start_ph not in plain, f"{fm['id']} (public) vaza {start_ph!r}"


def test_load_codex_inclui_timeline():
    """load_codex() traz chunks type=timeline com visibility preservada."""
    docs = codex_loader.load_codex()
    tl = [d for d in docs if d.metadata.get("type") == "timeline"]
    assert tl, "nenhum chunk de timeline em load_codex()"
    assert any(d.metadata["visibility"] == "hidden" for d in tl)
