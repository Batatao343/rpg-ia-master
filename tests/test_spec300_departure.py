"""SPEC-300 Etapa 5 — aviso, partida, traição (por traço), re-recrutamento, eventos só do motor."""

from spec300_helpers import BRUNNA, BRUNNA_ID, ev, make_state, merged

import party as party_mod
from services import chronicle
from services import companion_soul as cs
from services.world_validators import validate_proposal

NEG = [ev("k", "quest_failed", "npc_x")]  # honra -1 -> negativo p/ Brunna honrada


def _honrada():
    return ["honesto_demais", "generoso_escondido"]


def _pending(
    *, traits=(), approval=10, mode_="leave", turn_set=10, gold=100, loyal=False, now=None, **kw
):
    """Alma com despedida pendente desde `turn_set` (aviso anterior)."""
    state = make_state(traits=traits, approval=approval, gold=gold, turn=now or turn_set + 1, **kw)
    soul = state["companion_souls"][BRUNNA_ID]
    soul.update(
        warned_turn=turn_set - 2,
        warned_day=2,
        departure_pending="betray" if mode_ in ("steal", "deliver") else "leave",
        betrayal_mode=mode_ if mode_ in ("steal", "deliver") else "",
        departure_turn=turn_set,
        loyal=loyal,
    )
    soul["reactions"] = [
        {"id": f"{turn_set}:despedida", "tag": "despedida", "delta": 0, "turn": turn_set}
    ]
    return state


def test_aviso_ao_cruzar_25():
    state = make_state(traits=_honrada(), approval=26, events=NEG, day=3)
    out = cs.apply_turn(state)
    soul = out["companion_souls"][BRUNNA_ID]
    assert soul["approval"] < 25 and soul["warned_turn"] == 10 and soul["warned_day"] == 3
    assert any(r["tag"] == "aviso" for r in soul["reactions"])
    assert out["companion_feedback"][-1] == "Brunna Ponte-Alta está perdendo a paciência com você."


def test_histerese_limpa_aviso_em_35():
    state = make_state(approval=30)
    state["companion_souls"][BRUNNA_ID].update(warned_turn=5, warned_day=2)
    kept = cs.apply_turn(state)["companion_souls"][BRUNNA_ID]
    assert kept["warned_turn"] == 5  # 30 < 35: histerese mantém
    state["companion_souls"][BRUNNA_ID]["approval"] = 36
    cleared = cs.apply_turn(state)["companion_souls"][BRUNNA_ID]
    assert cleared["warned_turn"] is None and cleared["departure_pending"] == ""


def test_sem_aviso_nao_parte():
    out = cs.apply_turn(make_state(approval=5))
    soul = out["companion_souls"][BRUNNA_ID]
    assert soul["warned_turn"] == 10  # avisou agora
    assert soul["departure_pending"] == "" and "party" not in out


def test_parte_apos_dia_virado_ou_nova_tag_negativa():
    # dia virou
    soul = make_state(approval=10, turn=11, day=4)["companion_souls"][BRUNNA_ID]
    soul.update(warned_turn=8, warned_day=3)
    out = cs.step_departure(soul, turn=11, day=4, negative_after_warn=False, traits=[])
    assert out["departure_pending"] == "leave"
    # mesmo dia, sem nova tag negativa: não
    same = cs.step_departure(soul, turn=11, day=3, negative_after_warn=False, traits=[])
    assert same["departure_pending"] == ""
    # mesmo dia, nova tag negativa: sim
    neg = cs.step_departure(soul, turn=11, day=3, negative_after_warn=True, traits=[])
    assert neg["departure_pending"] == "leave"


def test_partida_espera_turno_narrado_fora_de_combate():
    base = _pending()
    assert "party" not in cs.apply_turn(base)  # sem ack e sem expirar
    despedida_ack = [f"r:{BRUNNA_ID}:10:despedida"]
    em_combate = _pending(ack=despedida_ack, combat={"phase": "active"})
    assert "party" not in cs.apply_turn(em_combate)
    assert cs.apply_turn(_pending(ack=despedida_ack))["party"] == []
    expirada = _pending(turn_set=7, now=10)  # 3 turnos pendente, ninguém narrou
    assert cs.apply_turn(expirada)["party"] == []


def test_partida_remove_da_party_e_ajusta_npc():
    out = cs.apply_turn(_pending(ack=[f"r:{BRUNNA_ID}:10:despedida"]))
    assert out["party"] == []
    row = out["npcs"][BRUNNA]
    assert row["in_scene"] is False and row["relationship"] == 5 and row["left_party_day"] == 3
    soul = out["companion_souls"][BRUNNA_ID]
    assert soul["departed"] == "left" and soul["warned_turn"] is not None
    assert out["event_log"][-1]["type"] == "companion_left"
    assert out["event_log"][-1]["source"] == "engine"
    assert out["companion_feedback"] == ["Brunna Ponte-Alta deixou o grupo."]


def test_trai_so_com_traco_e_sem_blocker():
    assert cs.betrayal_mode(["ganancioso"]) == "steal"
    assert cs.betrayal_mode(["rancoroso"]) == "deliver"
    assert cs.betrayal_mode(["ganancioso", "rancoroso"]) == "deliver"
    assert cs.betrayal_mode(["ganancioso", "honesto_demais"]) == ""
    assert cs.betrayal_mode(["tagarela"]) == ""
    soul = make_state(approval=5, turn=11, day=4)["companion_souls"][BRUNNA_ID]
    soul.update(warned_turn=8, warned_day=3)
    steal = cs.step_departure(
        soul, turn=11, day=4, negative_after_warn=False, traits=["ganancioso"]
    )
    assert steal["departure_pending"] == "betray" and steal["betrayal_mode"] == "steal"
    soul["approval"] = 12  # entre 8 e 15: parte, mas não trai
    plain = cs.step_departure(
        soul, turn=11, day=4, negative_after_warn=False, traits=["ganancioso"]
    )
    assert plain["departure_pending"] == "leave"


def test_traicao_ladra_leva_ouro_limitado_e_aparece_no_recibo():
    state = _pending(
        traits=["ganancioso"],
        approval=5,
        mode_="steal",
        gold=100,
        ack=[f"r:{BRUNNA_ID}:10:despedida"],
    )
    state["last_turn_outcome"] = {"gold_delta": 0, "receipt_id": "r"}
    out = cs.apply_turn(state)
    assert out["player"]["gold"] == 75  # 25%
    assert out["last_turn_outcome"]["gold_delta"] == -25
    soul = out["companion_souls"][BRUNNA_ID]
    assert soul["departed"] == "betrayed" and soul["grudge"] and not soul["deliver_pending"]
    assert out["npcs"][BRUNNA]["relationship"] == 0
    assert out["event_log"][-1]["type"] == "companion_betrayed"
    rich = _pending(
        traits=["ganancioso"],
        approval=5,
        mode_="steal",
        gold=1000,
        ack=[f"r:{BRUNNA_ID}:10:despedida"],
    )
    assert cs.apply_turn(rich)["player"]["gold"] == 940  # teto 60


def test_traicao_rancorosa_entrega_so_interface():
    state = _pending(
        traits=["rancoroso"],
        approval=5,
        mode_="deliver",
        gold=100,
        ack=[f"r:{BRUNNA_ID}:10:despedida"],
    )
    out = cs.apply_turn(state)
    assert "player" not in out  # nada de ouro
    assert out["companion_souls"][BRUNNA_ID]["deliver_pending"] is True
    assert cs.pending_betrayal_deliveries(merged(state, out)) == [BRUNNA_ID]


def test_loyal_nunca_trai_e_so_parte_abaixo_de_5():
    soul = make_state(approval=10, turn=11, day=4)["companion_souls"][BRUNNA_ID]
    soul.update(warned_turn=8, warned_day=3, loyal=True)
    assert (
        cs.step_departure(soul, turn=11, day=4, negative_after_warn=True, traits=["ganancioso"])[
            "departure_pending"
        ]
        == ""
    )
    soul["approval"] = 3
    out = cs.step_departure(soul, turn=11, day=4, negative_after_warn=True, traits=["ganancioso"])
    assert out["departure_pending"] == "leave" and out["betrayal_mode"] == ""


def _recruit_state(souls, day):
    state = make_state(party=False, souls=souls, day=day)
    state["npcs"][BRUNNA]["relationship"] = 9
    return state


def test_recruitment_decision_estranged_e_betrayed():
    left = {BRUNNA_ID: {"departed": "left", "left_party_day": 3}}
    assert party_mod.recruitment_decision(_recruit_state(left, 4), BRUNNA)["code"] == "estranged"
    assert party_mod.recruitment_decision(_recruit_state(left, 6), BRUNNA)["code"] == "ok"
    betrayed = {BRUNNA_ID: {"departed": "betrayed", "left_party_day": 3}}
    assert (
        party_mod.recruitment_decision(_recruit_state(betrayed, 30), BRUNNA)["code"] == "betrayed"
    )


def test_volta_ao_grupo_com_ultima_aprovacao_mais_10_limitada_a_40():
    state = make_state(approval=12)
    state["companion_souls"][BRUNNA_ID].update(departed="left", left_party_day=1)
    soul = cs.apply_turn(state)["companion_souls"][BRUNNA_ID]
    assert soul["departed"] == "" and soul["approval"] == 22
    state["companion_souls"][BRUNNA_ID].update(departed="left", approval=70)
    assert cs.apply_turn(state)["companion_souls"][BRUNNA_ID]["approval"] == 40


def test_eventos_companion_so_engine():
    state = make_state()
    for etype in ("companion_left", "companion_betrayed", "companion_fate"):
        prop = {"type": etype, "target_id": BRUNNA_ID, "payload": {}, "source": "storyteller"}
        assert not validate_proposal(prop, state).ok
        assert validate_proposal({**prop, "source": "engine"}, state).ok
        assert not validate_proposal(
            {"type": etype, "target_id": BRUNNA_ID, "payload": {}}, state
        ).ok


def test_chronicle_milestone_partida():
    left = ev("x", "companion_left", BRUNNA_ID, name=BRUNNA)
    assert chronicle.render_milestone(left, {}) == "Brunna Ponte-Alta deixou o grupo."
    betrayed = ev("y", "companion_betrayed", BRUNNA_ID, name=BRUNNA)
    assert "traiu" in chronicle.render_milestone(betrayed, {})
    out = cs.apply_turn(_pending(ack=[f"r:{BRUNNA_ID}:10:despedida"]))
    assert any("deixou o grupo" in e["text"] for ch in out["chronicle"] for e in ch["entries"])
