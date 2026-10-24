"""SPEC-299 etapa 7 — confronto, multa, pena, suborno, fuga e prisão."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from agents import router
from services import law, world_distance
from tests.spec299_helpers import base_state, clock_where, commit, with_clock


@pytest.fixture(autouse=True)
def _law_on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")
    monkeypatch.delenv("RPG_NPC_KNOWLEDGE", raising=False)


def _crime(cid, ctype, *, victim_faction="", severity=15, loc="nova_arcadia", status="reported"):
    return {
        "crime_id": cid,
        "crime_type": ctype,
        "jurisdiction_id": "codigo_de_ferro",
        "location_id": loc,
        "clock": 10,
        "turn": 1,
        "victim_ref": "",
        "victim_faction_id": victim_faction,
        "severity": severity,
        "witnesses": ["patrol:nova_arcadia"],
        "covert": False,
        "source": "engine",
        "status": status,
    }


def _confronted(crimes, *, loc="nova_arcadia", reason="patrol_witness", gold=500, **over):
    state = with_clock(base_state(loc), 40)
    state["player"]["gold"] = gold
    state["law_state"] = {
        "crimes": crimes,
        "wanted": {
            "codigo_de_ferro": {
                "jurisdiction_id": "codigo_de_ferro",
                "heat": 60,
                "bounty": 100,
                "capital": any(c["crime_type"] == "homicidio" for c in crimes),
                "last_crime_clock": 40,
                "known_at": {"nova_arcadia": 10},
                "signals_shown": [],
                "hunters_last_clock": -1,
            }
        },
        "confrontation": {
            "jurisdiction_id": "codigo_de_ferro",
            "location_id": loc,
            "started_turn": 5,
            "talk_turns": 0,
            "reason": reason,
        },
    }
    state.update(over)
    return state


def _route(state, text):
    state = {**state, "messages": [HumanMessage(content=text)]}
    return router.dm_router_node(state)


def _apply(state, payload):
    out = {**state, **{k: v for k, v in payload.items() if k != "messages"}}
    return out


# --------------------------------- abertura -------------------------------- #
def test_patrol_witness_opens_confrontation():
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st, _rec, _ = commit(state, "furto")
    out = law.turn_updates(st)
    conf = out["law_state"]["confrontation"]
    assert conf["reason"] == "patrol_witness" and conf["jurisdiction_id"] == "codigo_de_ferro"


def test_shadow_mode_records_but_never_confronts(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "shadow")
    state = base_state()
    state["npcs"] = {}
    state = with_clock(state, clock_where(state, "nova_arcadia", patrol=True))
    st, _rec, _ = commit(state, "furto")
    out = law.turn_updates(st)
    assert out["law_state"]["wanted"]["codigo_de_ferro"]["heat"] > 0
    assert out["law_state"]["confrontation"] is None
    assert law.scene_block(st) == ("", {}) and law.signals_for(st) == []
    assert law.resolve_choice(_confronted([_crime("a", "furto")]), "pago") == {}


def test_recognized_on_entering_opens_confrontation(monkeypatch):
    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: True)
    monkeypatch.setattr(law, "_unit", lambda *a: 0.0)
    state = _confronted([_crime("a", "agressao", severity=30)])
    state["law_state"]["confrontation"] = None
    out = law.turn_updates(state)
    assert out["law_state"]["confrontation"]["reason"] == "recognized"
    # sem repetir no mesmo local
    again = law.turn_updates(
        {**state, **out, "law_state": {**out["law_state"], "confrontation": None}}
    )
    assert "law_state" not in again or again["law_state"]["confrontation"] is None


# ----------------------------------- multa --------------------------------- #
def test_gate_pay_clears_heat_and_debits_gold():
    state = _confronted([_crime("a", "furto"), _crime("b", "agressao", severity=30)])
    payload = _route(state, "pago a multa")
    assert payload["next"] == "storyteller"
    assert payload["player"]["gold"] == 500 - (40 + 90)
    ls = payload["law_state"]
    assert ls["wanted"]["codigo_de_ferro"]["heat"] == 0 and ls["confrontation"] is None
    assert {c["status"] for c in ls["crimes"]} == {"resolved"}
    assert payload["pending_world_events"][-1]["type"] == "law_resolved"
    assert payload["pending_world_events"][-1]["payload"]["mode"] == "fine"
    assert ls["notice"]["text"]


def test_pay_insufficient_gold_keeps_confrontation():
    state = _confronted([_crime("a", "furto")], gold=10)
    payload = _route(state, "pago a multa")
    assert payload["next"] == "storyteller" and "player" not in payload
    assert payload["law_state"]["confrontation"] is not None
    assert payload["law_state"]["wanted"]["codigo_de_ferro"]["heat"] == 60
    assert "ouro" in payload["law_state"]["notice"]["text"]


def test_capital_crime_has_no_fine():
    state = _confronted([_crime("a", "homicidio", severity=70)])
    payload = _route(state, "pago a multa")
    assert payload["law_state"]["confrontation"] is not None and "player" not in payload
    assert "multa" in payload["law_state"]["notice"]["text"]
    assert law.resolve_fine(state) == ({}, False, "capital")


# ------------------------------------ pena --------------------------------- #
def test_surrender_advances_clock_and_moves_to_prison():
    state = _confronted([_crime("a", "furto")])  # 3 dias
    payload = _route(state, "me rendo")
    after = _apply(state, payload)
    assert after["world"]["current_location_id"] == "na_anel_ferro"
    before_clock = law.clock_of(state)
    travel = world_distance.travel_periods("nova_arcadia", "na_anel_ferro")
    assert law.clock_of(after) - before_clock >= 3 * 5
    assert law.clock_of(after) - before_clock <= 3 * 5 + travel + 3  # + custo de viagem/clima
    ls = payload["law_state"]
    assert ls["confrontation"] is None and ls["wanted"]["codigo_de_ferro"]["heat"] == 0
    assert ls["served"][-1]["mode"] == "sentence"
    assert payload["pending_world_events"][-1]["payload"]["mode"] == "sentence"
    assert "player" not in payload  # sem efeito em Vitalidade/inventário/ouro


def test_surrender_party_waits_at_prison():
    party = [{"name": "Lia", "id": "npc_lia", "active": True, "status": "ativo", "waiting_at": ""}]
    state = _confronted([_crime("a", "furto")], party=party)
    payload = _route(state, "me rendo")
    lia = payload["party"][0]
    assert lia["waiting_at"] == "na_anel_ferro" and lia["active"] is False


def test_long_sentence_imprisons_with_exits():
    state = _confronted([_crime("a", "homicidio", severity=70)])
    payload = _route(state, "me entrego")
    assert payload["next"] == "storyteller"
    conf = payload["law_state"]["confrontation"]
    assert conf["reason"] == "imprisoned" and conf["release_clock"] > law.clock_of(state)
    jailed = _apply(state, payload)
    assert jailed["world"]["current_location_id"] == "na_anel_ferro"
    text, _ = law.scene_block(jailed)
    assert "cela" in text
    # esperar cumpre o resto da pena e solta
    freed = _route(jailed, "aguardo a pena")
    assert freed["law_state"]["confrontation"] is None
    assert freed["law_state"]["served"][-1]["mode"] == "sentence"
    assert law.clock_of({**jailed, **freed}) >= conf["release_clock"]


def test_prison_bribe_and_refusal():
    # homicídio de civil: suborno aceito (Código de Ferro aceita) a preço 2x
    jailed = _apply(
        _confronted([_crime("a", "homicidio", severity=70)], gold=2000),
        _route(_confronted([_crime("a", "homicidio", severity=70)], gold=2000), "me entrego"),
    )
    out = _route(jailed, "tento subornar o carcereiro")
    assert out["player"]["gold"] == 2000 - 800  # 400 (capital) x 2,0
    assert out["law_state"]["confrontation"] is None
    assert out["law_state"]["wanted"]["codigo_de_ferro"]["heat"] == 30  # rastro: metade
    # vítima da própria autoridade: ninguém aceita
    legion = [_crime("a", "homicidio", severity=140, victim_faction="legiao_ferro")]
    refused = _route(
        _apply(
            _confronted(legion, gold=2000), _route(_confronted(legion, gold=2000), "me entrego")
        ),
        "tento subornar o carcereiro",
    )
    assert "player" not in refused and refused["law_state"]["confrontation"] is not None


def test_prison_escape_roll_and_rescue(monkeypatch):
    base = _confronted([_crime("a", "homicidio", severity=70)])
    jailed = _apply(base, _route(base, "me entrego"))
    # fuga falha -> pena aumenta
    monkeypatch.setattr(law, "_rng", lambda *a: __import__("random").Random(0))
    monkeypatch.setattr(
        "services.conflict_resolution.roll_kept",
        lambda adv, rng: {"rolled": [1, 1], "kept": [1, 1]},
    )
    failed = _route(jailed, "tento escapar da cela")
    assert (
        failed["law_state"]["confrontation"]["release_clock"]
        > jailed["law_state"]["confrontation"]["release_clock"]
    )
    # fuga com sucesso -> sai da jurisdição? sai da cela e ganha `evasao`
    monkeypatch.setattr(
        "services.conflict_resolution.roll_kept",
        lambda adv, rng: {"rolled": [10, 10], "kept": [10, 10]},
    )
    ok = _route(jailed, "tento escapar da cela")
    assert ok["law_state"]["confrontation"] is None
    assert ok["world"]["current_location_id"] == "na_anel_lama"  # fora da jurisdição
    assert any(c["crime_type"] == "evasao" for c in ok["law_state"]["crimes"])
    # resgate exige companheiro esperando na prisão
    nobody = _route(jailed, "espero o resgate dos companheiros")
    assert nobody["law_state"]["confrontation"]["reason"] == "imprisoned"
    waiting = {
        **jailed,
        "party": [
            {"name": "Lia", "active": False, "waiting_at": "na_anel_ferro", "status": "ativo"}
        ],
    }
    freed = _route(waiting, "espero o resgate dos companheiros")
    assert freed["law_state"]["confrontation"] is None
    assert freed["party"][0]["active"] is True


def test_bribe_during_confrontation():
    state = _confronted([_crime("a", "furto")], gold=500)
    out = _route(state, "ofereço uma propina ao guarda")
    assert out["player"]["gold"] == 500 - 80  # multa 40 x 2,0
    assert out["law_state"]["confrontation"] is None
    assert out["pending_world_events"][-1]["payload"]["mode"] == "bribe"
    poor = _route(_confronted([_crime("a", "furto")], gold=5), "ofereço uma propina ao guarda")
    assert "player" not in poor and poor["law_state"]["confrontation"] is not None


# ------------------------------- fuga e combate ---------------------------- #
def test_flee_adds_evasao_and_starts_chase():
    state = _confronted([_crime("a", "furto")])
    payload = _route(state, "fujo correndo")
    assert payload["next"] == "combat_agent"
    assert payload["combat_origin_hint"] == "law_enforcement"
    assert any(c["crime_type"] == "evasao" for c in payload["law_state"]["crimes"])
    assert payload["law_state"]["confrontation"] is None


def test_travel_intent_counts_as_fleeing():
    state = _confronted([_crime("a", "furto")])
    payload = _route(state, "vou para Brekmar")
    assert payload["next"] == "combat_agent"
    assert any(c["crime_type"] == "evasao" for c in payload["law_state"]["crimes"])


def test_attack_adds_resistencia_and_spawns_guards():
    state = _confronted([_crime("a", "furto")])
    payload = _route(state, "ataco o guarda")
    assert payload["next"] == "combat_agent"
    assert payload["combat_encounter_hint"]["enemy_id"] == "enemy_soldado_legiao_ferro"
    assert payload["combat_origin_hint"] == "law_enforcement"
    assert any(c["crime_type"] == "resistencia" for c in payload["law_state"]["crimes"])
    from services.combat_origin import from_encounter, normalize

    assert normalize("law_enforcement") == "law_enforcement"
    assert from_encounter({"reason": "law_confrontation"}, {}) == "law_enforcement"


def test_talk_routes_to_guard_then_arrest_attempt():
    state = _confronted([_crime("a", "furto")])
    first = _route(state, "explico que foi um mal-entendido")
    assert first["next"] == "npc_actor" and first["active_npc_name"] in first["npcs"]
    state = _apply(state, first)
    second = _route(state, "juro que sou inocente")
    assert second["next"] == "npc_actor"
    state = _apply(state, second)
    third = _route(state, "continuo conversando")
    assert third["next"] == "combat_agent" and third["combat_origin_hint"] == "law_enforcement"
    assert third["law_state"]["confrontation"] is None


def test_colmeia_expels_instead_of_prison():
    crime = _crime("a", "furto", loc="sx_cidades_hospedeiros")
    crime["jurisdiction_id"] = "colmeia"
    state = _confronted([crime], loc="sx_cidades_hospedeiros")
    state["law_state"]["wanted"] = {
        "colmeia": {**state["law_state"]["wanted"]["codigo_de_ferro"], "jurisdiction_id": "colmeia"}
    }
    state["law_state"]["confrontation"]["jurisdiction_id"] = "colmeia"
    payload = _route(state, "me rendo")
    after = _apply(state, payload)
    assert after["world"]["current_location_id"] == "selva_xylos"  # fora da jurisdição
    ls = payload["law_state"]
    assert ls["served"][-1]["mode"] == "expulsao"
    assert ls["wanted"]["colmeia"]["heat"] >= 65  # `cacado` lá fora
    assert "na_anel_ferro" not in str(after["world"]["current_location_id"])


def test_leaving_jurisdiction_ends_confrontation():
    state = _confronted([_crime("a", "furto")])
    moved = {**state, "world": {**state["world"], "current_location_id": "brekmar"}}
    out = law.turn_updates(moved)
    assert out["law_state"]["confrontation"] is None
    assert out["law_state"]["wanted"]["codigo_de_ferro"]["heat"] == 60  # o heat continua


def test_gate_inactive_without_confrontation(monkeypatch):
    state = with_clock(base_state(), 40)
    state["messages"] = [HumanMessage(content="pago a multa")]
    assert router._law_gate(state, state["world"], state["messages"]) is None
    confronted = _confronted([_crime("a", "furto")])
    confronted["messages"] = [HumanMessage(content="pago a multa")]
    assert router._law_gate(confronted, confronted["world"], confronted["messages"]) is not None
    monkeypatch.setenv("RPG_LAW", "off")
    assert router._law_gate(confronted, confronted["world"], confronted["messages"]) is None
    monkeypatch.setenv("RPG_LAW", "shadow")
    assert router._law_gate(confronted, confronted["world"], confronted["messages"]) is None


def test_combat_gate_has_precedence_over_law_gate():
    state = _confronted([_crime("a", "furto")])
    state["combat"] = {"active": True, "round": 1, "idle_turns": 0}
    payload = _route(state, "pago a multa")
    assert payload["next"] == "combat_agent"
