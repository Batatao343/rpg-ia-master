"""SPEC-300 Etapa 8 — interfaces off-screen (SPEC-302) e prisioneiro (pilar B), com dublê."""

import pytest
from spec300_helpers import BRUNNA, BRUNNA_ID, make_state, merged

import party as party_mod
from services import companion_soul as cs


def _waiting(day=5, location="skallgard", here="montanhas_afiadas"):
    state = make_state(day=day, location=here, approval=50)
    state["party"][0].update(active=False, waiting_at=location)
    state["companion_souls"][BRUNNA_ID]["last_seen_day"] = 2
    return state


def test_companions_exposed_so_em_espera():
    assert cs.companions_exposed(make_state()) == []  # ativa: não está exposta
    rows = cs.companions_exposed(_waiting())
    assert len(rows) == 1
    assert rows[0]["companion_id"] == BRUNNA_ID and rows[0]["location_id"] == "skallgard"
    assert rows[0]["days_away"] == 3 and isinstance(rows[0]["danger_level"], int)
    morta = _waiting()
    morta["party"][0].update(dead=True)
    assert cs.companions_exposed(morta) == []


def test_fate_sem_telegrama_recusa():
    with pytest.raises(cs.FateNotTelegraphed):
        cs.apply_companion_fate(_waiting(), BRUNNA_ID, "morto", 9)


def test_fate_telegrama_mesmo_dia_recusa():
    state = _waiting(day=5)
    state = merged(state, cs.telegraph_companion_danger(state, BRUNNA_ID, "rumor", 5))
    with pytest.raises(cs.FateNotTelegraphed):
        cs.apply_companion_fate(state, BRUNNA_ID, "ferido", 5)
    assert cs.apply_companion_fate(state, BRUNNA_ID, "ferido", 6)["party"]


def test_fate_cancelado_se_jogador_voltou_ou_chamou():
    state = _waiting(day=5)
    state = merged(state, cs.telegraph_companion_danger(state, BRUNNA_ID, "pedido_de_ajuda", 5))
    voltou = merged(state, {"world": {**state["world"], "current_location_id": "skallgard"}})
    with pytest.raises(cs.FateNotTelegraphed):
        cs.apply_companion_fate(voltou, BRUNNA_ID, "capturado", 8)
    novo_party, _ = party_mod.set_following(state, BRUNNA)
    chamou = merged(state, {"party": novo_party})
    with pytest.raises(cs.FateNotTelegraphed):
        cs.apply_companion_fate(chamou, BRUNNA_ID, "morto", 8)


def test_fate_morto_sincroniza_npcs_party_e_falha_missao():
    state = _waiting(day=5)
    quest = cs.build_personal_quest(state, state["party"][0], turn=4)
    state["quests"] = [quest]
    state["companion_souls"][BRUNNA_ID]["personal_quest"] = "revealed"
    state = merged(state, cs.telegraph_companion_danger(state, BRUNNA_ID, "rumor", 5))
    out = cs.apply_companion_fate(state, BRUNNA_ID, "morto", 7)
    assert out["party"] == []
    assert out["npcs"][BRUNNA]["status"] == "morto" and out["npcs"][BRUNNA]["in_scene"] is False
    assert out["companion_souls"][BRUNNA_ID]["departed"] == "dead"
    assert out["quests"][0]["status"] == "failed"
    fate = [e for e in out["event_log"] if e["type"] == "companion_fate"]
    assert fate and fate[0]["source"] == "engine" and fate[0]["payload"]["day"] == 7
    assert any(
        "morreu longe do herói" in e["text"] for ch in out["chronicle"] for e in ch["entries"]
    )


def test_motor_duble_por_dias():
    """Dublê da SPEC-302: telegrafa, deixa passar dias e só então aplica o destino."""
    state = _waiting(day=5)
    for day in range(5, 8):
        exposed = cs.companions_exposed(
            merged(
                state, {"world": {**state["world"], "world_clock": {"day": day, "period": "manha"}}}
            )
        )
        assert [e["companion_id"] for e in exposed] == [BRUNNA_ID]
        if day == 5:
            state = merged(state, cs.telegraph_companion_danger(state, BRUNNA_ID, "rumor", day))
        elif day == 6:
            state = merged(state, cs.apply_companion_fate(state, BRUNNA_ID, "capturado", day))
    assert state["party"][0]["status"] == "capturado"


def test_recruit_prisoner_ignora_relationship_respeita_max_active():
    state = make_state(party=False)
    prisoner = {
        "id": "npc_pris",
        "name": "Rendido",
        "relationship": 0,
        "faction": "legiao_ferro",
        "role": "soldado",
    }
    state["factions"] = [{"id": "legiao_ferro", "disposition": "hostil"}]
    new_party, reason = party_mod.recruit_prisoner(state, prisoner)
    assert reason == "" and new_party[0]["bound"] == "rendicao"
    state["party"] = new_party
    soul = cs.apply_turn(state)["companion_souls"]["npc_pris"]
    assert soul["origin"] == "prisoner" and soul["approval"] == 20 and soul["bound"] == "rendicao"
    cheio = make_state(party=False)
    cheio["party"] = [
        {"id": f"c{i}", "name": f"C{i}", "active": True, "status": "ativo"} for i in range(3)
    ]
    refused, why = party_mod.recruit_prisoner(cheio, prisoner)
    assert refused is None and "cheio" in why
