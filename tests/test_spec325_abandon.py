"""SPEC-325 Fase B / R12-R13 - abandono e sacrificio na fuga (via `combat_node` + SPEC-304)."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

import api
from agents import combat as cbt
from services import chase as chase_mod
from services import companion_soul as cs
from services import companion_tags
from tests.spec300_helpers import BRUNNA, BRUNNA_ID
from tests.spec325_chase_helpers import first_state, narration_spy, step
from tests.spec325_helpers import run_node

LOC = "montanhas_afiadas"
PRESSIONADO = {
    "trilha": "pressionado",
    "perseguidores": ["e1"],
    "fugitive_id": "player",
    "alcancado": False,
    "escapou": False,
    "eligible": True,
}


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_CHASE_ABANDON", "on")


def _round1(monkeypatch, *, chase=None, **kw):
    """Rodada 1 (cria a cena) com a Brunna recrutada; depois injeta a trilha."""
    state = first_state(party=True, **kw)
    out = run_node(state, monkeypatch)
    out["combat"] = {**out["combat"], "chase": {**(chase or PRESSIONADO)}}
    return state, out


def _abandon(monkeypatch, luck=-1, intent="Fujo e deixo a Brunna para trás.", **kw):
    state, out = _round1(monkeypatch, **kw)
    out["combat"]["chase"]["last_luck"] = {BRUNNA_ID: luck}
    narrate, seen = narration_spy()
    merged, out2 = step(state, out, monkeypatch, intent, narrate=narrate)
    return merged, out2, seen


def _brunna(out):
    return next(c for c in out["party"] if c.get("origin_npc") == BRUNNA_ID)


def test_last_luck_recorded_only_with_flag_on(monkeypatch):
    state = first_state(party=True)
    on = run_node(state, monkeypatch)
    assert set(on["combat"]["chase"]["last_luck"]) == {BRUNNA_ID}
    monkeypatch.setenv("RPG_CHASE_ABANDON", "off")
    off = run_node(first_state(party=True), monkeypatch)
    assert "last_luck" not in off["combat"]["chase"]


def test_only_complicacao_ally_can_be_abandoned(monkeypatch):
    _m, out, _ = _abandon(monkeypatch, luck=0)
    assert _brunna(out)["active"] is True and "pending_fate" not in _brunna(out)
    _m, out, _ = _abandon(monkeypatch, luck=1)
    assert "pending_fate" not in _brunna(out)
    _m, out, _ = _abandon(monkeypatch, luck=-1)
    assert _brunna(out)["active"] is False and "pending_fate" in _brunna(out)


def test_scene_ally_cannot_be_abandoned(monkeypatch):
    state, out = _round1(monkeypatch)
    out["combat"]["chase"]["last_luck"] = {"npc_estranho": -1}
    _m, out2 = step(state, out, monkeypatch, "Fujo e deixo o Estranho para trás.")
    assert "pending_fate" not in _brunna(out2)
    assert not any(c.get("pending_fate") for c in out2["party"])
    # unitario: transitorio (aliado de cena) nunca e candidato
    party = [{"id": "t", "name": "Estranho", "active": True, "transient": True}]
    assert chase_mod.abandon_candidates({"last_luck": {"t": -1}}, party) == {}


def test_abandon_removes_luck_this_round(monkeypatch):
    _m, out, _ = _abandon(monkeypatch)
    assert BRUNNA_ID not in out["combat"]["chase"]["last_luck"]
    assert out["combat"]["chase"]["abandoned"] == [BRUNNA_ID]
    pf = _brunna(out)["pending_fate"]
    assert _brunna(out)["waiting_at"] == LOC and pf["location_id"] == LOC
    assert pf["resultado"] in chase_mod.ABANDON_OUTCOMES
    assert out["combat"]["last_player_action"]["kind"] == "flee"


def test_abandon_event_without_fate(monkeypatch):
    merged, out, _ = _abandon(monkeypatch)
    events = [e for e in out["event_log"] if e["type"] == "companion_abandoned"]
    assert len(events) == 1 and events[0]["target_id"] == BRUNNA_ID
    pf = _brunna(out)["pending_fate"]
    blob = json.dumps(events[0])
    assert pf["resultado"] not in blob and pf["seed"] not in blob and "fate" not in blob


def test_fate_sealed_not_in_narration_or_api(monkeypatch):
    """Oraculo do R5: nem o narrador nem /game/state veem o `pending_fate`."""
    merged, out, seen = _abandon(monkeypatch)
    pf = _brunna(out)["pending_fate"]
    narration = seen[-1]
    assert "ficou para trás" in narration
    assert "pending_fate" not in narration and pf["seed"] not in narration
    for word in ("capturado", "morto", "fate"):
        assert word not in narration
    payload = _api_payload(merged, out)
    dumped = json.dumps(payload, default=str)
    assert "pending_fate" not in dumped and pf["seed"] not in dumped
    assert pf["resultado"] not in json.dumps(payload["party"], default=str)
    party = [c for c in payload["party"] if c["name"] == BRUNNA]
    assert party and party[0]["status"] == "ativo"  # nada de destino na ficha publica


def _api_payload(merged, out):
    state = {**merged, **{k: v for k, v in out.items() if k != "next"}}
    state["world"] = {**state["world"], "current_location": "Montanhas Afiadas"}
    state["messages"] = [*state["messages"], AIMessage(content="Fim.")]
    return api.format_response(state).model_dump()


def test_api_chips_only_with_flag_on(monkeypatch):
    state, out = _round1(monkeypatch)
    out["combat"]["chase"]["last_luck"] = {BRUNNA_ID: -1}
    out["combat"]["chase"]["sacrifice_offer"] = BRUNNA_ID
    chase = _api_payload(state, out)["combat"]["chase"]
    assert chase["abandon_candidates"] == [{"id": BRUNNA_ID, "name": BRUNNA}]
    assert chase["sacrifice_offer"] == {"id": BRUNNA_ID, "name": BRUNNA}
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_CHASE_ABANDON", mode)
        chase = _api_payload(state, out)["combat"]["chase"]
        assert "abandon_candidates" not in chase and "sacrifice_offer" not in chase


def test_same_seed_same_fate(monkeypatch):
    _m, a, _ = _abandon(monkeypatch)
    _m, b, _ = _abandon(monkeypatch)
    assert _brunna(a)["pending_fate"] == _brunna(b)["pending_fate"]
    assert _brunna(a)["pending_fate"]["seed"].endswith(f":{BRUNNA_ID}:2")


def test_other_companions_get_abandon_tag(monkeypatch):
    merged, out, _ = _abandon(monkeypatch)
    state = {**merged, **{k: v for k, v in out.items() if k != "next"}}
    state["turn_baseline"] = {"event_ids": [], "turn": 10}
    tags = [t["id"] for t in companion_tags.detect_choice_tags(state)]
    assert "abandonou_companheiro" in tags
    tag = companion_tags.catalog()["abandonou_companheiro"]
    assert tag["axes"] == {"compaixao": -2, "honra": -1} and tag["magnitude"] == 3


# ------------------------------------------------------- consumo (SPEC-304)
def _after(monkeypatch, *, day, location, fate="morto"):
    merged, out, _ = _abandon(monkeypatch)
    state = {**merged, **{k: v for k, v in out.items() if k != "next"}}
    state["party"] = [
        {**c, "pending_fate": {**c["pending_fate"], "fate": fate}} if c.get("pending_fate") else c
        for c in state["party"]
    ]
    state["combat"] = {"phase": "ended"}
    state["world"] = {
        **state["world"],
        "current_location_id": location,
        "world_clock": {"day": day, "period": "manha"},
        "turn_count": 12,
    }
    return state


def test_fate_not_applied_same_day_but_telegraphed(monkeypatch):
    state = _after(monkeypatch, day=3, location="nova_arcadia")
    up = cs.apply_turn(state)
    assert not [e for e in up.get("event_log", []) if e["type"] == "companion_fate"]
    soul = up["companion_souls"][BRUNNA_ID]
    assert [t for t in soul["telegraphs"] if t["source"] == "abandono"]  # o aviso e o telegrama
    # nada aplicado: o destino segue selado na party (o apply_turn nem reescreve a party)
    assert "party" not in up
    assert state["party"][0]["pending_fate"]["fate"] == "morto"


def test_fate_applied_after_one_day_via_304(monkeypatch):
    state = _after(monkeypatch, day=3, location="nova_arcadia")
    state = {**state, **cs.apply_turn(state)}  # dia 3: so o telegrama
    state["world"] = {**state["world"], "world_clock": {"day": 4, "period": "manha"}}
    up = cs.apply_turn(state)
    events = [e for e in up["event_log"] if e["type"] == "companion_fate"]
    assert len(events) == 1 and events[0]["payload"]["fate"] == "morto"
    assert events[0]["payload"]["day"] == 4
    assert not [c for c in up["party"] if cs.comp_id(c) == BRUNNA_ID]  # morreu (apply_npc_death)
    assert up["companion_souls"][BRUNNA_ID]["departed"] == "dead"
    assert any("não sobreviveu" in f for f in up["companion_feedback"])


@pytest.mark.parametrize(("fate", "status"), [("capturado", "capturado"), ("ferido", "ativo")])
def test_other_fates_use_304_pipeline(monkeypatch, fate, status):
    state = _after(monkeypatch, day=3, location="nova_arcadia", fate=fate)
    state = {**state, **cs.apply_turn(state)}
    state["world"] = {**state["world"], "world_clock": {"day": 5, "period": "manha"}}
    up = cs.apply_turn(state)
    brunna = next(c for c in up["party"] if cs.comp_id(c) == BRUNNA_ID)
    assert brunna["status"] == status and "pending_fate" not in brunna
    assert brunna["active"] is False


def test_no_damage_fates_return_to_waiting(monkeypatch):
    state = _after(monkeypatch, day=3, location="nova_arcadia", fate="")
    state = {**state, **cs.apply_turn(state)}
    state["world"] = {**state["world"], "world_clock": {"day": 5, "period": "manha"}}
    up = cs.apply_turn(state)
    brunna = next(c for c in up["party"] if cs.comp_id(c) == BRUNNA_ID)
    assert "pending_fate" not in brunna and brunna["waiting_at"] == LOC
    assert not [e for e in up.get("event_log", []) if e["type"] == "companion_fate"]


def test_return_before_day_rescues(monkeypatch):
    state = _after(monkeypatch, day=3, location="nova_arcadia")
    state = {**state, **cs.apply_turn(state)}
    state["world"] = {**state["world"], "current_location_id": LOC}  # voltou ao local
    up = cs.apply_turn(state)
    brunna = next(c for c in up["party"] if cs.comp_id(c) == BRUNNA_ID)
    assert "pending_fate" not in brunna and brunna["status"] == "ativo"
    assert not [e for e in up.get("event_log", []) if e["type"] == "companion_fate"]
    # nem depois de varios dias: o destino foi cancelado
    later = {**state, **up}
    later["world"] = {
        **later["world"],
        "current_location_id": "nova_arcadia",
        "world_clock": {"day": 9, "period": "manha"},
    }
    assert not [
        e for e in cs.apply_turn(later).get("event_log", []) if e["type"] == "companion_fate"
    ]


def test_recalled_companion_cancels_fate(monkeypatch):
    state = _after(monkeypatch, day=3, location="nova_arcadia")
    state = {**state, **cs.apply_turn(state)}
    state["party"] = [{**c, "active": True, "waiting_at": ""} for c in state["party"]]
    up = cs.apply_turn(state)
    assert "pending_fate" not in next(c for c in up["party"] if cs.comp_id(c) == BRUNNA_ID)


def test_peril_pipeline_skips_sealed_companion(monkeypatch):
    state = _after(monkeypatch, day=3, location="nova_arcadia")
    assert BRUNNA_ID not in [c["companion_id"] for c in cs.companions_exposed(state)]


# ------------------------------------------------------------- sacrificio
def _stalled(monkeypatch):
    """A rodada de fuga nao avanca a trilha (isola a oferta do acaso dos dados)."""

    def stub(chase, **kw):
        chase["_last"] = {"total": 0, "difficulty": 10, "sucesso": False, "advantage": 0}
        return chase

    monkeypatch.setattr(chase_mod, "resolve_chase_round", stub)


def _offer_state(monkeypatch, coragem=None, **kw):
    state = first_state(party=True, **kw)
    if coragem is not None:  # a alma derivada ja traz coragem; o teste fixa o valor
        state["companion_souls"][BRUNNA_ID]["values"]["coragem"] = coragem
    _stalled(monkeypatch)
    out = run_node(state, monkeypatch)  # rodada 1: pressionado + elegivel -> oferta
    return state, out


def test_sacrifice_offer_once_for_loyal_brave(monkeypatch):
    state, out = _offer_state(monkeypatch, approval=80, coragem=1)
    chase = out["combat"]["chase"]
    assert chase["sacrifice_offer"] == BRUNNA_ID and chase["sacrifice_offered"] is True
    # rodada seguinte: a oferta expira e nao volta (1x por perseguicao)
    _m, out2 = step(state, out, monkeypatch, "continuo fugindo")
    assert out2["combat"]["chase"]["sacrifice_offer"] is None
    assert out2["combat"]["chase"]["sacrifice_offered"] is True
    assert "pending_fate" not in _brunna(out2)


@pytest.mark.parametrize(
    ("approval", "coragem"),
    [(50, 2), (80, 0), (60, 0), (69, 2)],
    ids=["sem_lealdade", "sem_coragem", "nenhum", "quase_leal"],
)
def test_no_offer_without_trait_or_soul(monkeypatch, approval, coragem):
    _state, out = _offer_state(monkeypatch, approval=approval, coragem=coragem)
    assert not out["combat"]["chase"].get("sacrifice_offer")
    assert not out["combat"]["chase"].get("sacrifice_offered")


def test_explicit_trait_offers_sacrifice(monkeypatch):
    _state, out = _offer_state(
        monkeypatch, approval=30, coragem=0, traits=("se_sacrifica_pelo_grupo",)
    )
    assert out["combat"]["chase"]["sacrifice_offer"] == BRUNNA_ID


def test_accept_sacrifice_escapes_and_seals_fate(monkeypatch):
    state, out = _offer_state(monkeypatch, approval=80, coragem=1)
    narrate, seen = narration_spy()
    merged, out2 = step(state, out, monkeypatch, "Aceito o sacrifício.", narrate=narrate)
    assert out2["combat"]["outcome"] == "fled" and out2["combat"]["active"] is False
    brunna = _brunna(out2)
    assert brunna["active"] is False and brunna["waiting_at"] == LOC
    pf = brunna["pending_fate"]
    assert pf["resultado"] in chase_mod.SACRIFICE_OUTCOMES
    assert pf["fate"] in ("ferido", "capturado", "morto")
    assert "fica para trás" in seen[-1] and "pending_fate" not in seen[-1]
    # sacrificio nao e abandono: sem evento nem tag
    assert not [e for e in out2.get("event_log", []) if e["type"] == "companion_abandoned"]


def test_refuse_no_penalty(monkeypatch):
    state, out = _offer_state(monkeypatch, approval=80, coragem=1)
    soul_before = json.dumps(state["companion_souls"], sort_keys=True)
    merged, out2 = step(state, out, monkeypatch, "Não aceito. Continuo fugindo.")
    assert "pending_fate" not in _brunna(out2) and _brunna(out2)["active"] is True
    assert out2["combat"]["chase"]["sacrifice_offer"] is None
    assert not [e for e in out2.get("event_log", []) if e["type"] == "companion_abandoned"]
    assert "companion_souls" not in out2  # o combate nunca escreve na alma
    assert json.dumps(state["companion_souls"], sort_keys=True) == soul_before


# ------------------------------------------------------------ off / shadow
def _snapshot(out):
    return {k: out.get(k) for k in ("combat", "party", "player", "enemies", "event_log")}


def test_abandon_off_ignores_declaration(monkeypatch):
    monkeypatch.setenv("RPG_CHASE_ABANDON", "off")
    state, out = _round1(monkeypatch)
    out["combat"]["chase"]["last_luck"] = {BRUNNA_ID: -1}
    _m, out2 = step(state, out, monkeypatch, "Fujo e deixo a Brunna para trás.")
    assert "pending_fate" not in _brunna(out2) and _brunna(out2)["active"] is True
    assert "abandoned" not in out2["combat"]["chase"]


def test_abandon_shadow_logs_without_state_change(monkeypatch):
    logs: list[tuple] = []
    monkeypatch.setattr(cbt, "_log_event", lambda *a, **k: logs.append((a, k)))
    runs = {}
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_CHASE_ABANDON", mode)
        state, out = _round1(monkeypatch)
        _m, runs[mode] = step(state, out, monkeypatch, "Fujo e deixo a Brunna para trás.")
    assert [e for e in logs if e[0][1] == "chase_abandon_shadow"]
    assert _snapshot(runs["off"]) == _snapshot(runs["shadow"])


def test_sacrifice_shadow_logs_without_offer(monkeypatch):
    logs: list[tuple] = []
    monkeypatch.setattr(cbt, "_log_event", lambda *a, **k: logs.append((a, k)))
    monkeypatch.setenv("RPG_CHASE_ABANDON", "shadow")
    _stalled(monkeypatch)
    state = first_state(party=True, approval=80)
    state["companion_souls"][BRUNNA_ID]["values"]["coragem"] = 1
    out = run_node(state, monkeypatch)
    assert [e for e in logs if e[0][1] == "chase_sacrifice_shadow"]
    assert "sacrifice_offer" not in out["combat"]["chase"]
    assert "last_luck" not in out["combat"]["chase"]
