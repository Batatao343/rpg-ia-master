"""SPEC-299 etapa 3 — classificação de crime (LLM + motor) e validador anti-alucinação."""

from __future__ import annotations

import pytest

from agents.npc import NPCResponse
from agents.storyteller import StoryUpdate
from services import law
from services.structured_outputs import CrimeClaim
from tests.spec299_helpers import base_state, commit


@pytest.fixture(autouse=True)
def _law_on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")


def _claims(state, claims, text):
    return law.apply_claims(state, claims, player_text=text)


def test_claim_without_lexical_support_rejected():
    out = _claims(
        base_state(),
        [CrimeClaim(crime_type="furto", victim="Mercador")],
        "converso com o mercador",
    )
    assert "law_state" not in out
    assert out["event_rejections"][-1]["reason"] == "crime:sem_suporte_na_acao"


def test_claim_victim_must_be_in_scene():
    out = _claims(
        base_state(),
        [{"crime_type": "agressao", "victim": "Fantasma"}],
        "esfaqueio o fantasma",
    )
    assert "law_state" not in out
    assert out["event_rejections"][-1]["reason"] == "crime:vitima_fora_de_cena"


def test_valid_claim_registers_with_scene_victim():
    out = _claims(
        base_state(),
        [{"crime_type": "agressao", "victim": "mercador"}],
        "esfaqueio o mercador",
    )
    rec = out["law_state"]["crimes"][-1]
    assert rec["crime_type"] == "agressao" and rec["victim_ref"] == "npc:npc_mercador"
    assert rec["jurisdiction_id"] == "codigo_de_ferro"


def test_quarantine_ignores_claims():
    out = law.apply_claims(
        base_state(),
        [{"crime_type": "furto", "victim": "local"}],
        player_text="roubo a bolsa",
        quarantine=True,
    )
    assert out == {}


def test_invalid_crime_type_drops_item_not_response():
    update = StoryUpdate.model_validate(
        {
            "narrative": "x",
            "crime_claims": [
                {"crime_type": "bruxaria", "victim": "x"},
                {"crime_type": "furto", "victim": "local"},
            ],
        }
    )
    assert [c.crime_type for c in update.crime_claims] == ["furto"]
    npc = NPCResponse.model_validate(
        {
            "dialogue": "d",
            "action_description": "a",
            "memory_update": "m",
            "crime_claims": [{"crime_type": "genocidio"}],
        }
    )
    assert npc.crime_claims == []


def test_fallback_aimessage_no_crime():
    from langchain_core.messages import AIMessage

    assert _claims(base_state(), AIMessage(content="erro"), "roubo a bolsa") == {}
    assert _claims(base_state(), None, "roubo a bolsa") == {}
    assert getattr(AIMessage(content="x"), "crime_claims", []) == []


def test_one_claim_per_type_per_turn():
    out = _claims(
        base_state(),
        [
            {"crime_type": "furto", "victim": "local"},
            {"crime_type": "furto", "victim": "local"},
        ],
        "roubo a bolsa",
    )
    assert len(out["law_state"]["crimes"]) == 1
    assert out["event_rejections"][-1]["reason"] == "crime:um_por_tipo"


def test_lawless_location_no_record():
    state = base_state("brekmar")
    out = _claims(state, [{"crime_type": "furto", "victim": "local"}], "roubo a bolsa")
    assert out == {}
    why = law.register_crime(
        state, {"crime_type": "furto", "victim_ref": "local", "source": "engine"}
    )[2]
    assert why == "sem_lei"


def test_llm_cannot_propose_engine_only_types():
    upd, rec, why = law.register_crime(
        base_state(),
        {
            "crime_type": "resistencia",
            "victim_ref": "local",
            "source": "llm_claim",
            "player_text": "resisto",
        },
    )
    assert rec is None and why == "tipo_so_do_motor"


def test_magia_ilegal_on_and_license_or_combat_exempt():
    state = base_state()
    ok = _claims(state, [{"crime_type": "magia_ilegal", "victim": ""}], "lanço um feitiço de éter")
    assert ok["law_state"]["crimes"][-1]["crime_type"] == "magia_ilegal"
    licensed = {**state, "law_state": {"licenses": ["codigo_de_ferro"]}}
    out = _claims(licensed, [{"crime_type": "magia_ilegal"}], "lanço um feitiço de éter")
    assert out["event_rejections"][-1]["reason"] == "crime:licenciado"
    fighting = {**state, "combat": {"active": True}}
    out = _claims(fighting, [{"crime_type": "magia_ilegal"}], "lanço um feitiço")
    assert out["event_rejections"][-1]["reason"] == "crime:em_combate"
    # Éter onde o código não habilita o crime (Skallgard) não é crime
    skall = _claims(base_state("skallgard"), [{"crime_type": "magia_ilegal"}], "lanço um feitiço")
    assert "law_state" not in skall


def test_buy_license_debits_gold_and_clears_magic_crime():
    state = base_state()
    upd, ok, why = law.buy_license(state)
    assert ok and upd["player"]["gold"] == 250
    state = {**state, **upd}
    assert law.buy_license(state)[2] == "ja_licenciado"
    why = law.register_crime(
        state, {"crime_type": "magia_ilegal", "victim_ref": "", "source": "engine"}
    )[2]
    assert why == "licenciado"
    assert law.buy_license(base_state("brekmar"))[2] == "sem_registro"
    poor = base_state(player={"gold": 3})
    assert law.buy_license(poor)[2] == "insufficient_gold"


# ---------------------------- motor (R4b) ---------------------------------- #
def _provoked(state, target="Mercador", **combat):
    return {
        **state,
        "combat": {
            "active": True,
            "origin": "player_provoked",
            "instance_id": "g:0:7",
            "encounter": {"target_ref": target},
            **combat,
        },
    }


def test_engine_player_provoked_vs_neutral_is_agressao():
    out = law.turn_updates(_provoked(base_state()))
    crimes = out["law_state"]["crimes"]
    assert [c["crime_type"] for c in crimes] == ["agressao"]
    assert crimes[0]["source"] == "engine"
    # idempotente por instância de combate (próximo turno do mesmo combate não duplica)
    again = law.turn_updates({**_provoked(base_state()), **out})
    assert "law_state" not in again or len(again["law_state"]["crimes"]) == 1


def test_engine_hostile_target_is_not_crime():
    state = base_state()
    state["npcs"]["Mercador"]["relationship"] = 0
    assert "law_state" not in law.turn_updates(_provoked(state))


def test_engine_travel_encounter_is_not_crime():
    state = _provoked(base_state())
    state["combat"]["origin"] = "travel_encounter"
    assert law.turn_updates(state) == {}
    state["combat"]["origin"] = "law_enforcement"
    assert law.turn_updates(state) == {}


def test_npc_killed_in_jurisdiction_is_homicidio():
    state = _provoked(base_state())
    state["event_log"] = [
        {"event_id": "e1", "turn": 5, "type": "npc_killed", "target_id": "npc_mercador"}
    ]
    types = [c["crime_type"] for c in law.turn_updates(state)["law_state"]["crimes"]]
    assert types == ["agressao", "homicidio"]


def test_magia_ilegal_disabled_when_code_row_disabled():
    from services import law_codes

    code = {"crimes": {"magia_ilegal": {"enabled": False}}}
    assert law_codes.crime_row(code, "magia_ilegal") is None
    st, rec, why = commit(base_state("skallgard"), "magia_ilegal")
    assert rec is None and why == "tipo_desabilitado"
