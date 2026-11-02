"""SPEC-351 Etapa 2 — menu de portas/NPCs da trama e contexto (R1–R4)."""

from __future__ import annotations

import sys
import types

import pytest

from services import npc_world, rumors
from services import opening_threads as ot

BACKSTORY = "saí do Anel Dourado depois que minha irmã parou de me reconhecer"


def test_menu_deterministic_and_ranked_by_backstory():
    a = ot.thread_menu("nova_arcadia", backstory=BACKSTORY)
    b = ot.thread_menu("nova_arcadia", backstory=BACKSTORY)
    assert a == b
    ranked = ot.thread_menu("nova_arcadia", backstory="o pó de sonho mostra o futuro")
    assert ranked["doors"][0]["door_id"] == "rumor_o_po_de_sonho_mostra_o_futuro"
    assert len(a["doors"]) <= ot.MENU_MAX_DOORS and len(a["npcs"]) <= ot.MENU_MAX_NPCS


def test_nova_arcadia_menu_has_po_de_sonho_door():
    menu = ot.thread_menu("nova_arcadia", backstory="quero saber do pó de sonho")
    ids = [d["door_id"] for d in menu["doors"]]
    assert "rumor_o_po_de_sonho_mostra_o_futuro" in ids
    assert menu["source"] == "fallback" and menu["npcs"]


def test_menu_excludes_leaders_secrets_hidden_dead(monkeypatch):
    base = ot.thread_menu("nova_arcadia")
    victim = base["npcs"][0]["entity_id"]
    monkeypatch.setattr(npc_world, "leaders", lambda: {victim: "alguma_faccao"})
    assert victim not in [n["entity_id"] for n in ot.thread_menu("nova_arcadia")["npcs"]]
    monkeypatch.undo()

    ot._secret_entity_ids.cache_clear()
    from services import secret_signatures

    other = base["npcs"][1]["entity_id"]
    monkeypatch.setattr(secret_signatures, "SECRET_ENTITY_IDS", {"x": frozenset({other})})
    try:
        assert other not in [n["entity_id"] for n in ot.thread_menu("nova_arcadia")["npcs"]]
    finally:
        ot._secret_entity_ids.cache_clear()

    # rumor com secret_id ainda não revelado fica fora (R2)
    seeds = {k: dict(v) for k, v in rumors.load_seeds().items()}
    po = "rumor_o_po_de_sonho_mostra_o_futuro"
    seeds[po]["secret_id"] = "pacto_valerius"
    monkeypatch.setattr(rumors, "load_seeds", lambda: seeds)
    ids = [d["door_id"] for d in ot.thread_menu("nova_arcadia", backstory="pó de sonho")["doors"]]
    assert po not in ids


def test_menu_never_has_rumor_truth_or_fonte(monkeypatch):
    seeds = {k: dict(v) for k, v in rumors.load_seeds().items()}
    po = "rumor_o_po_de_sonho_mostra_o_futuro"
    texts = []
    for truth in (True, False):
        seeds[po].update(truth=truth, fonte="SEGREDO-FONTE-XYZ", confiabilidade="SEGREDO-CONF")
        monkeypatch.setattr(rumors, "load_seeds", lambda s=seeds: s)
        menu = ot.thread_menu("nova_arcadia", backstory="pó de sonho")
        texts.append(ot.menu_block(menu))
    assert texts[0] == texts[1]
    assert "SEGREDO" not in texts[0] and "truth" not in texts[0].lower()


def test_menu_and_lore_token_budget(monkeypatch):
    menu = ot.thread_menu("nova_arcadia")
    for d in menu["doors"]:
        d["hook"] = "palavra " * 200
    assert ot._estimate(ot.menu_block(menu)) <= ot.MENU_TOKENS_MAX
    import rag

    monkeypatch.setattr(rag, "query_rag", lambda *a, **k: "lore " * 20000)
    assert ot._estimate(ot.lore_block(menu, BACKSTORY)) <= ot.LORE_TOKENS_MAX


def test_single_public_rag_query(monkeypatch):
    import rag
    from services import prologue

    calls: list[dict] = []

    def fake(query, **kw):
        calls.append({"query": query, **kw})
        return "Nova Arcádia é uma cidade murada. [chunk público]"

    monkeypatch.setattr(rag, "query_rag", fake)
    prologue.build_start_scenario_ctx(
        {
            "name": "A",
            "race": "Elfo",
            "class_name": "Arcanista Cinzento",
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": BACKSTORY,
        }
    )
    assert len(calls) == 1
    assert calls[0]["max_visibility"] == "public"
    assert calls[0]["prefer_region"] == "nova_arcadia"
    assert calls[0]["index_name"] == "lore"


def test_hidden_chunk_never_reaches_prompt(monkeypatch):
    """R4: o prólogo só pede `public`; um índice que respeita a visibilidade não devolve hidden."""
    import rag

    def fake(query, *, max_visibility="public", **kw):
        chunks = {"public": "pública", "hidden": "SEGREDO-OCULTO"}
        return chunks["public"] if max_visibility == "public" else chunks["hidden"]

    monkeypatch.setattr(rag, "query_rag", fake)
    menu = ot.thread_menu("nova_arcadia")
    assert "SEGREDO-OCULTO" not in ot.lore_block(menu, "")


def _fake_350(monkeypatch, doors, calls=None):
    mod = types.ModuleType("services.plot_threads")

    def plot_doors(region_id, state=None, postura=None):
        if calls is not None:
            calls.append(region_id)
        return doors

    mod.plot_doors = plot_doors
    monkeypatch.setitem(sys.modules, "services.plot_threads", mod)
    import services

    monkeypatch.setattr(services, "plot_threads", mod, raising=False)


def test_population_api_preferred_when_present(monkeypatch):
    base = ot.thread_menu("nova_arcadia")
    anchor = base["npcs"][0]["entity_id"]
    calls: list[str] = []
    _fake_350(
        monkeypatch,
        [
            {
                "door_id": "door_tr_na_po_de_sonho",
                "thread_id": "tr_na_po_de_sonho",
                "name": "O Pó de Sonho",
                "hook": "algo corre nas vielas",
                "entity_ids": [],
                "location_id": "na_anel_lama",
                "anchor_npc_ids": [anchor],
                "visibility": "public",
            },
            {"door_id": "oculta", "name": "Oculta", "visibility": "hidden"},
        ],
        calls,
    )
    menu = ot.thread_menu("nova_arcadia")
    assert calls == ["nova_arcadia"] and menu["source"] == "350"
    assert [d["door_id"] for d in menu["doors"]] == ["door_tr_na_po_de_sonho"]
    assert [n["entity_id"] for n in menu["npcs"]] == [anchor]


def test_fallback_when_350_absent_or_empty(monkeypatch):
    monkeypatch.setitem(sys.modules, "services.plot_threads", None)  # ImportError
    assert ot.thread_menu("nova_arcadia")["source"] == "fallback"
    monkeypatch.undo()
    _fake_350(monkeypatch, [])
    assert ot.thread_menu("nova_arcadia")["source"] == "fallback"


@pytest.mark.parametrize(
    "region",
    [
        "aethelgard",
        "brekmar",
        "costa_negra",
        "deserto_zhur",
        "floresta_sussurros",
        "montanhas_afiadas",
        "nova_arcadia",
        "ophidia",
        "pantano_melancolia",
        "pradaria_ruinas",
        "selva_xylos",
        "skallgard",
    ],
)
def test_every_start_region_has_plot_npc(region):
    assert ot.thread_menu(region)["npcs"], region
