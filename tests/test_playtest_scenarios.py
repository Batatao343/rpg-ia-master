"""Smokes dirigidos de recrutamento e comércio."""
from __future__ import annotations

from types import SimpleNamespace

import party
import pytest
from playtest import scenarios
from playtest.runner import run_campaign
from services import economy


def _base_state():
    return {
        "game_id": "00000000-0000-0000-0000-000000000042",
        "player": {"gold": 50, "inventory": [{"id": "pocao_cura", "qty": 2}]},
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "visited": ["nova_arcadia"],
            "world_clock": {"day": 1, "period": "manhã"},
            "turn_count": 1,
        },
        "npcs": {},
        "party": [],
        "factions": [],
    }


def test_cenario_recrutamento_prepara_gate_e_acao_inequivoca():
    state = scenarios.prepare("recrutamento", _base_state())

    ok, reason = party.can_recruit(state, scenarios.RECRUIT_NPC_NAME)
    decision = scenarios.decision_for("recrutamento", 1, state)

    assert ok, reason
    assert party.detect_party_command(decision.text) == "recruit"
    assert scenarios.RECRUIT_NPC_NAME in decision.text
    assert scenarios.profile_for("recrutamento") == "recrutador"


def test_oraculo_recrutamento_passa_e_falha():
    recruited = scenarios.prepare("recrutamento", _base_state())
    recruited["party"] = [
        party.make_companion_from_npc(
            recruited["npcs"][scenarios.RECRUIT_NPC_NAME],
            scenarios.RECRUIT_NPC_NAME,
        )
    ]

    assert scenarios.oracle_violations(
        "recrutamento", SimpleNamespace(final_state=recruited, turns_completed=1)
    ) == []
    failure = scenarios.oracle_violations(
        "recrutamento", SimpleNamespace(final_state=_base_state(), turns_completed=1)
    )
    assert failure[0]["check_id"] == "smoke.recruitment_not_observed"
    assert failure[0]["severity"] == "error"


def test_cenario_comercio_prepara_mercador_estoque_e_baseline():
    state = scenarios.prepare("comercio", _base_state())
    merchant_id, stock = economy.merchant_stock(
        state, state["world"]["current_location_id"],
    )
    decision = scenarios.decision_for("comercio", 1, state)

    assert state["world"]["current_location_id"] == "na_anel_dourado"
    assert merchant_id == "mercado_anel_dourado"
    assert stock["pocao_cura"] >= 1
    assert state["player"]["gold"] == scenarios.TRADE_START_GOLD
    assert not any(i.get("id") == "pocao_cura" for i in state["player"]["inventory"])
    assert "poção de cura" in decision.text.lower()
    assert scenarios.profile_for("comercio") == "comerciante"


def test_oraculo_comercio_exige_ouro_e_item():
    state = scenarios.prepare("comercio", _base_state())
    outcome = economy.execute_trade(state, "buy", "poção de cura", 1)
    assert outcome["ok"] is True
    bought = {**state, "player": outcome["player"], "world": outcome["world"]}

    assert scenarios.oracle_violations(
        "comercio", SimpleNamespace(final_state=bought, turns_completed=1)
    ) == []
    failure = scenarios.oracle_violations(
        "comercio", SimpleNamespace(final_state=state, turns_completed=1)
    )
    assert failure[0]["check_id"] == "smoke.trade_not_observed"
    assert failure[0]["severity"] == "error"


def test_catalogo_rejeita_cenario_desconhecido():
    try:
        scenarios.profile_for("inexistente")
    except KeyError as exc:
        assert "inexistente" in str(exc)
    else:
        raise AssertionError("cenário desconhecido deveria falhar")


@pytest.mark.parametrize(
    ("scenario", "profile"),
    [("recrutamento", "recrutador"), ("comercio", "comerciante")],
)
def test_cenario_dirigido_percorre_grafo_offline_com_oraculo_verde(
    scenario, profile,
):
    result = run_campaign(
        profile,
        turns=1,
        seed=1703,
        invariants=True,
        scenario=scenario,
    )

    assert result.errors == []
    assert result.aborted_reason is None
    assert result.scenario == scenario
    assert not [v for v in result.violations if v.get("severity") == "error"]


def test_runner_rejeita_perfil_incompativel_com_cenario():
    with pytest.raises(ValueError, match="exige perfil"):
        run_campaign("explorador", turns=1, scenario="recrutamento")
