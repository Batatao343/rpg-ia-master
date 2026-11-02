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


def _fake_350(monkeypatch, *, anchors=None, calls=None, empty=False):
    """Módulo da SPEC-350 com a MESMA forma da real: `PlotDoor`/`PlotThread` Pydantic frozen."""
    from pydantic import BaseModel

    class PlotDoor(BaseModel, frozen=True):
        id: str
        anchor_npc_id: str
        location_id: str
        link_kind: str = "vizinhanca"
        hook_public: str
        rumor_ids: tuple[str, ...] = ()
        quest_hint: object | None = None

    class PlotThread(BaseModel, frozen=True):
        id: str
        region_id: str
        title: str
        portas: tuple[PlotDoor, ...]
        postura_afinidade: tuple[str, ...] = ()

    anchor = anchors or [ot.thread_menu("nova_arcadia")["npcs"][0]["entity_id"]]
    threads = [
        PlotThread(
            id="tr_x_a",
            region_id="nova_arcadia",
            title="O pó que alivia",
            portas=(
                PlotDoor(
                    id="tr_x_a__p1",
                    anchor_npc_id=anchor[0],
                    location_id="na_anel_lama",
                    hook_public="uma lavadeira passa bilhetes",
                ),
                PlotDoor(
                    id="tr_x_a__p2",
                    anchor_npc_id=anchor[0],
                    location_id="na_anel_lama",
                    hook_public="a boticária procura entregador",
                ),
            ),
        ),
        PlotThread(
            id="tr_x_b",
            region_id="nova_arcadia",
            title="A Lista de Fornalha",
            portas=(
                PlotDoor(
                    id="tr_x_b__p1",
                    anchor_npc_id=anchor[-1],
                    location_id="na_anel_ferro",
                    hook_public="um escrivão guarda nomes",
                ),
            ),
            postura_afinidade=("Arcanista Cinzento",),
        ),
    ]
    mod = types.ModuleType("services.plot_threads")

    def plot_doors(region_id, *, state=None, postura=None):
        if calls is not None:
            calls.append((region_id, postura))
        if empty:
            return []
        ranked = sorted(
            threads, key=lambda t: 0 if postura and postura in t.postura_afinidade else 1
        )
        return [d for t in ranked for d in t.portas]

    mod.plot_doors = plot_doors
    mod.threads_for_region = lambda rid: [t for t in threads if t.region_id == rid]
    mod.catalog = lambda: types.SimpleNamespace(threads=threads)
    monkeypatch.setitem(sys.modules, "services.plot_threads", mod)
    import services

    monkeypatch.setattr(services, "plot_threads", mod, raising=False)
    return mod


def test_population_api_preferred_when_present(monkeypatch):
    calls: list = []
    _fake_350(monkeypatch, calls=calls)
    menu = ot.thread_menu("nova_arcadia", postura="Arcanista Cinzento")
    assert calls == [("nova_arcadia", "Arcanista Cinzento")] and menu["source"] == "350"
    # uma porta por trama, nome = título da trama, postura primeiro
    assert [d["name"] for d in menu["doors"]] == ["A Lista de Fornalha", "O pó que alivia"]
    assert [d["door_id"] for d in menu["doors"]] == ["tr_x_b__p1", "tr_x_a__p1"]
    assert menu["doors"][1]["hook"] == "uma lavadeira passa bilhetes"
    assert menu["npcs"]


def test_350_door_name_is_thread_title_only(monkeypatch):
    _fake_350(monkeypatch)
    assert ot._door_name("tr_x_a__p2") == "O pó que alivia"
    assert ot._door_name("tr_x_a") == "O pó que alivia"
    assert ot._door_name("inexistente") == ""


def test_350_present_but_unmappable_logs_and_falls_back(monkeypatch):
    mod = _fake_350(monkeypatch)
    mod.threads_for_region = lambda rid: []  # linhas existem, nenhuma trama dona
    logged: list = []
    monkeypatch.setattr(ot, "_log_event", lambda *a, **k: logged.append(k.get("reason")))
    assert ot.thread_menu("nova_arcadia")["source"] == "fallback"
    assert "350_unmapped" in logged


def test_fallback_when_350_absent_or_empty(monkeypatch):
    monkeypatch.setitem(sys.modules, "services.plot_threads", None)  # ImportError
    assert ot.thread_menu("nova_arcadia")["source"] == "fallback"
    monkeypatch.undo()
    _fake_350(monkeypatch, empty=True)
    assert ot.thread_menu("nova_arcadia")["source"] == "fallback"


def test_real_350_elfo_nova_arcadia_menu(monkeypatch):
    """Com o módulo real da 350 e RPG_PLOT_THREADS=on, a trama do Pó de Sonho entra no menu."""
    pt = pytest.importorskip("services.plot_threads")
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    if hasattr(pt, "clear_cache"):
        pt.clear_cache()
    if not any(t.id == "tr_na_po_de_sonho" for t in pt.threads_for_region("nova_arcadia")):
        pytest.skip("catálogo da 350 sem tr_na_po_de_sonho")
    menu = ot.thread_menu(
        "nova_arcadia",
        backstory="o pó que alivia a pele rachada da minha irmã",
        postura="Arcanista Cinzento",
    )
    assert menu["source"] == "350"
    assert any(d["door_id"].startswith("tr_na_po_de_sonho") for d in menu["doors"])
    assert any(n["entity_id"].startswith("npc_tr_") for n in menu["npcs"])
    assert ot._door_name(menu["doors"][0]["door_id"])


def test_dead_npc_is_excluded(monkeypatch):
    base = ot.thread_menu("nova_arcadia")
    dead = base["npcs"][0]["entity_id"]
    state = {"world_projection": {"entities": {dead: {"alive": False}}}}
    got = [n["entity_id"] for n in ot.thread_menu("nova_arcadia", state=state)["npcs"]]
    assert dead not in got and got


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


def test_hidden_faction_from_350_rows_never_reaches_menu_or_sheet(monkeypatch):
    """P2-5 da 350: `cast_npc_row` devolve facção oculta; a 351 não a lê nem repassa."""
    mod = _fake_350(monkeypatch)
    anchor = ot.thread_menu("nova_arcadia")["npcs"][0]["entity_id"]
    mod.cast_npc_row = lambda *a, **k: {"id": anchor, "faction_id": "encapuzados_fornalha"}
    menu = ot.thread_menu("nova_arcadia")
    assert menu["source"] == "350"
    assert "encapuzados_fornalha" not in repr(menu) + ot.menu_block(menu)
    sheet = ot.plot_npc_sheet(menu["npcs"][0], "g", "nova_arcadia", hook="gancho")
    assert "encapuzados_fornalha" not in repr(sheet) and sheet["opening_hook"] == "gancho"
