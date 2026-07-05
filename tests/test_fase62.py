"""
Fase 6.2 — Itens únicos: um por mundo, rastreados no event_log.
Spec: specs/fase-6.2-itens-unicos.md. 100% offline.
"""
import random

import pytest

import inventory as inv
from gamedata import ARTIFACTS_DB
from services import economy as eco
from services import graph_resolver as gr
from services.event_processor import apply_event, process_pending_events
from services.world_validators import validate_proposal

ADAGA = "art_adaga_vidro_dragao"
COROA = "art_coroa_pressao_rei_anao"


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


def _state(**over):
    base = {
        "world": {"turn_count": 5, "current_location_id": "skallgard",
                  "current_location": "Skallgard",
                  "world_clock": {"day": 1, "period": "Manhã"}},
        "world_projection": {}, "event_log": [], "pending_world_events": [],
        "chronicle": [], "quests": [], "factions": [],
        "player": {"name": "T", "gold": 9999, "inventory": [],
                   "hp": 30, "max_hp": 30, "class_name": ""},
    }
    base.update(over)
    return base


def _claimed(item_id, holder="player"):
    return {"unique_items": {item_id: {"holder": holder, "event_id": "e", "turn": 1}}}


# ---------------------------------------------------------------------------
# Etapa 1 — dados (autoria)
# ---------------------------------------------------------------------------

def test_20_unicos_mix_de_raridade():
    uniques = {k: v for k, v in ARTIFACTS_DB.items() if v.get("unique")}
    assert len(uniques) >= 20
    rar = [str(v["rarity"]).lower() for v in uniques.values()]
    assert rar.count("lendario") >= 3
    assert rar.count("epico") >= 7
    assert rar.count("raro") >= 10
    for k, v in uniques.items():
        assert str(v["rarity"]).lower() in ("raro", "epico", "lendario"), k
        cs = v.get("combat_stats") or {}
        # zero só-texto: todo único tem stat mecânico real
        assert cs.get("attack_bonus") or cs.get("ac_bonus") or \
            (cs.get("damage_dice") not in (None, "0")), f"{k} sem mecânica"
        assert v.get("description"), k
        assert not v.get("stackable"), k


def test_unicos_distribuidos_nas_tabelas():
    em_pool = set()
    for t in eco.LOOT_TABLES.values():
        for pool in (t.get("pools") or {}).values():
            em_pool |= {i for i in pool if inv.is_unique(i)}
    assert len(em_pool) >= 10  # boa parte encontrável no mundo


# ---------------------------------------------------------------------------
# Etapa 2 — evento + projection + gate anti-LLM
# ---------------------------------------------------------------------------

def test_llm_nao_propoe_claim():
    prop = {"type": "unique_item_claimed", "target_id": ADAGA, "payload": {}}
    res = validate_proposal(prop, _state())
    assert not res.ok and "motor" in res.reason


def test_claim_engine_valida_e_aplica():
    prop = eco.claim_event(ADAGA, "player")
    res = validate_proposal(prop, _state())
    assert res.ok, res.reason
    ev = {**prop, "event_id": "e1", "turn": 5}
    proj = apply_event(ev, {})
    assert proj["unique_items"][ADAGA]["holder"] == "player"


def test_claim_de_item_nao_unico_rejeitado():
    prop = eco.claim_event("pocao_cura", "player")
    res = validate_proposal(prop, _state())
    assert not res.ok


def test_claim_vira_milestone():
    state = _state(pending_world_events=[eco.claim_event(ADAGA, "player")])
    out = process_pending_events(state)
    texts = [e["text"] for e in out["chronicle"][-1]["entries"]]
    assert any("não há outro no mundo" in t for t in texts)


def test_lost_para_mercador_sem_milestone():
    state = _state(pending_world_events=[eco.claim_event(ADAGA, "ferreiro_skallgard")])
    out = process_pending_events(state)
    assert out["world_projection"]["unique_items"][ADAGA]["holder"] == "ferreiro_skallgard"
    texts = [e["text"] for cap in out.get("chronicle", []) for e in cap["entries"]]
    assert not any("não há outro" in t for t in texts)


# ---------------------------------------------------------------------------
# Etapa 3 — gates de entrada
# ---------------------------------------------------------------------------

def test_roll_loot_nunca_re_dropa(monkeypatch):
    proj = _claimed(ADAGA)
    rng = random.Random(1)
    for _ in range(300):
        roll = eco.roll_loot("skallgard", 4, rng, projection=proj)
        assert roll["item_id"] != ADAGA


def test_estoque_esconde_unico_reclamado():
    s = _state(world_projection=_claimed(COROA))
    _, stock = eco.merchant_stock(s, "skallgard")
    assert COROA not in stock
    # dono é o próprio mercador -> continua à venda (recompra)
    s2 = _state(world_projection=_claimed(COROA, holder="ferreiro_skallgard"))
    _, stock2 = eco.merchant_stock(s2, "skallgard")
    assert COROA in stock2


def test_craft_de_unico_existente_falha():
    eco.RECIPES["forja_da_adaga_teste"] = {
        "result_id": ADAGA, "result_qty": 1, "ingredients": {},
        "gold_cost": 0, "craft_tag": "forja", "classes": []}
    try:
        s = _state(world_projection=_claimed(ADAGA))
        out = eco.execute_craft(s, "forja_da_adaga_teste")
        assert not out["ok"] and "já existe" in out["reason"]
    finally:
        del eco.RECIPES["forja_da_adaga_teste"]


def test_items_gained_recusa_unico_reclamado(monkeypatch):
    import agents.storyteller as st

    class _FakeStoryLLM:
        def with_structured_output(self, model, *a, **k):
            self._m = model
            return self

        def invoke(self, _msgs):
            return self._m(narrative="Você encontra uma adaga negra.",
                           introduced_npcs=[], items_gained=["Adaga de Vidro-Dragão"])

    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _FakeStoryLLM())
    from langchain_core.messages import HumanMessage
    state = _state(world_projection=_claimed(ADAGA),
                   messages=[HumanMessage(content="pego a adaga")],
                   npcs={}, campaign_plan={"beats": [], "current_step": 0,
                                           "location": "x", "climax": "y",
                                           "last_planned_turn": 0})
    out = st.storyteller_node(state)
    got = (out.get("player") or {}).get("inventory") or []
    assert not any(e.get("id") == ADAGA for e in got)


def test_items_gained_unico_disponivel_gera_claim(monkeypatch):
    import agents.storyteller as st

    class _FakeStoryLLM:
        def with_structured_output(self, model, *a, **k):
            self._m = model
            return self

        def invoke(self, _msgs):
            return self._m(narrative="A lâmina é sua.", introduced_npcs=[],
                           items_gained=["Adaga de Vidro-Dragão"])

    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _FakeStoryLLM())
    from langchain_core.messages import HumanMessage
    state = _state(messages=[HumanMessage(content="pego a adaga")],
                   npcs={}, campaign_plan={"beats": [], "current_step": 0,
                                           "location": "x", "climax": "y",
                                           "last_planned_turn": 0})
    out = st.storyteller_node(state)
    assert any(e.get("id") == ADAGA for e in out["player"]["inventory"])
    claims = [e for e in out.get("pending_world_events", [])
              if e.get("type") == "unique_item_claimed"]
    assert claims and claims[0]["source"] == "engine"


# ---------------------------------------------------------------------------
# Etapa 4 — venda/recompra rastreada
# ---------------------------------------------------------------------------

def test_vender_unico_rastreia_e_permite_recompra():
    s = _state()
    s["player"]["inventory"] = inv.add_item([], COROA, 1)
    out = eco.execute_trade(s, "sell", "coroa de pressão", 1)
    assert out["ok"], out
    events = out.get("pending_events") or []
    assert events and events[0]["type"] == "unique_item_lost"
    assert events[0]["payload"]["holder"] == "ferreiro_skallgard"
    # estoque do mercador ganhou o item
    assert out["world"]["merchant_stocks"]["ferreiro_skallgard"][COROA] >= 1
    # recompra gera claim de volta
    s2 = _state(world=out["world"],
                world_projection=_claimed(COROA, holder="ferreiro_skallgard"))
    out2 = eco.execute_trade(s2, "buy", "coroa de pressão", 1)
    assert out2["ok"], out2
    ev2 = out2.get("pending_events") or []
    assert ev2 and ev2[0]["type"] == "unique_item_claimed"
