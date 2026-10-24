"""SPEC-301 Etapa 6 — sair, trair, rivais odeiam ao saber, dissolução (R16-R19)."""

from __future__ import annotations

import pytest

import world_utils as wu
from services import faction_membership as fm
from tests.spec301_support import (
    add_npc,
    at,
    faction,
    joined,
    make_state,
    merge,
    mission_quest,
    set_day,
    set_rep,
)


def _rep(state, fid):
    return faction(state, fid)["reputation"]


@pytest.mark.parametrize(
    "fid,policy,steps",
    [("druidas_ciclo_cinzento", "livre", 1), ("legiao_ferro", "desonra", 2)],
)
def test_leave_livre_desonra(fid, policy, steps):
    assert fm.load_catalog()[fid]["exit_policy"] == policy
    st = set_rep(joined(make_state(), fid, merit=5, rank_index=1), fid, 20)
    upd, events, note = fm.leave(st, fid)
    rec = upd["faction_membership"][fid]
    assert rec["status"] == "ex_membro" and rec["merit"] == 0 and rec["rank_index"] == 1
    assert rec["left_day"] == 3
    assert _rep(merge(st, upd), fid) == 20 - steps * fm.REP_STEP
    assert [
        e["payload"]["action"] for e in events if e["type"] == "faction_membership_changed"
    ] == ["left"]
    if policy == "desonra":
        assert rec["cooldown_until_day"] == 3 + fm.COOLDOWN_HONOR_DAYS
    else:
        assert rec["cooldown_until_day"] == 0
    assert note


def test_leave_traicao_vale_como_traicao():
    st = joined(make_state(), "mao_sombria", merit=4)
    upd, events, _ = fm.leave(st, "mao_sombria")
    rec = upd["faction_membership"]["mao_sombria"]
    assert rec["status"] == "traidor" and rec["cooldown_until_day"] == 3 + 30
    assert [
        e["payload"]["action"] for e in events if e["type"] == "faction_membership_changed"
    ] == ["betrayed"]
    assert _rep(merge(st, upd), "mao_sombria") <= fm.HOSTILE_AT


def test_leave_sem_ser_membro():
    upd, events, note = fm.leave(make_state(), "legiao_ferro")
    assert upd == {} and events == [] and note


def test_limiar_hostil_coincide_com_world_utils():
    assert fm.HOSTILE_AT == wu._HOSTIL_AT


def test_primeira_ofensa_vira_suspeito_com_aviso():
    st = joined(make_state(), "legiao_ferro")
    upd, events, note = fm.register_offense(st, "legiao_ferro", "prejudicou")
    rec = upd["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "suspeito" and rec["offenses"] == [3]
    assert "calados" in note and events == []


def test_segunda_ofensa_na_janela_trai():
    st = joined(make_state(), "legiao_ferro", status="suspeito", offenses=[2])
    upd, events, _ = fm.register_offense(st, "legiao_ferro", "prejudicou")
    rec = upd["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "traidor"
    st2 = merge(st, upd)
    assert _rep(st2, "legiao_ferro") <= fm.HOSTILE_AT
    assert any(e["payload"].get("action") == "betrayed" for e in events)


def test_ofensa_fora_da_janela_so_suspeita():
    st = joined(make_state(), "legiao_ferro", status="suspeito", offenses=[1])
    st = set_day(st, 1 + fm.SUSPICION_WINDOW_DAYS + 1)
    upd, _, _ = fm.register_offense(st, "legiao_ferro", "prejudicou")
    rec = upd["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "suspeito" and rec["offenses"] == [1 + fm.SUSPICION_WINDOW_DAYS + 1]


def test_sabotar_a_propria_faccao_conta_como_ofensa():
    st = joined(joined(make_state(), "legiao_ferro"), "filhos_chama_azul")
    st["quests"] = [
        mission_quest("legiao_ferro", kind="sabotagem", tier=1, target="filhos_chama_azul")
    ]
    upd, _, _ = fm.on_mission_completed(st, st["quests"][0])
    assert upd["faction_membership"]["filhos_chama_azul"]["status"] == "suspeito"
    assert upd["faction_membership"]["legiao_ferro"]["merit"] == 2


def test_entrar_em_exclusiva_confirma_traicao():
    # conversão (Ciclo -> Renegados) é o caminho autorado de "entrar traindo"
    st = at(joined(make_state(), "druidas_ciclo_cinzento"), "pm_profundezas")
    st = add_npc(st, "npc_saelwen_a_que_afundou", "Saelwen")
    st["npcs"]["Saelwen"]["interaction_count"] = 4
    upd, events, _ = fm.join(st, "druidas_renegados")
    assert upd["faction_membership"]["druidas_ciclo_cinzento"]["status"] == "traidor"
    assert _rep(merge(st, upd), "druidas_ciclo_cinzento") <= fm.HOSTILE_AT


def test_traidor_cooldown_30_dias():
    st = joined(make_state(), "legiao_ferro", status="suspeito", offenses=[3])
    upd, _, _ = fm.register_offense(st, "legiao_ferro")
    st2 = merge(st, upd)
    assert fm.can_join(st2, "legiao_ferro") == (False, "traidor_recente")
    assert fm.can_join(set_day(st2, 3 + 29), "legiao_ferro")[1] == "traidor_recente"
    # passados 30 dias o cooldown cai (a reputação hostil ainda barra: outro motivo)
    assert fm.can_join(set_day(st2, 3 + 30), "legiao_ferro")[1] != "traidor_recente"


def test_rival_awareness_publica_aplica_ao_chegar_na_regiao():
    st = make_state()
    upd, _, _ = fm.join(st, "legiao_ferro")
    st = merge(st, upd)
    assert st["faction_membership"]["legiao_ferro"]["rival_awareness"]
    # Filhos/Mão têm base em Nova Arcádia; chegar a Skallgard não ensina ninguém
    _, events, note = fm.apply_rival_awareness(st, "skallgard", arrived=True)
    assert events == []
    before = _rep(st, "filhos_chama_azul")
    upd2, events2, note2 = fm.apply_rival_awareness(st, "na_anel_lama", arrived=True)
    st2 = merge(st, upd2)
    assert _rep(st2, "filhos_chama_azul") == before - fm.REP_STEP
    assert _rep(st2, "mao_sombria") == before - fm.REP_STEP
    assert all(e["type"] == "reputation_changed" for e in events2)
    # idempotente: consumida
    assert st2["faction_membership"]["legiao_ferro"]["rival_awareness"] == {}
    upd3, events3, _ = fm.apply_rival_awareness(st2, "na_anel_lama", arrived=True)
    assert upd3 == {} and events3 == []


def test_rival_awareness_nao_nomeia_faccao_desconhecida():
    st = make_state()
    upd, _, _ = fm.join(st, "legiao_ferro")
    st = merge(st, upd)
    _, _, note = fm.apply_rival_awareness(st, "na_anel_lama", arrived=True)
    assert "Filhos" not in note and "Mão" not in note  # rivais não conhecidos pelo jogador


def test_rival_awareness_secreta_so_apos_exposicao():
    st = at(make_state(), "na_anel_lama")
    st["faction_intel"]["mao_sombria"] = {"known": True}
    st = set_rep(st, "mao_sombria", 20)
    st = add_npc(st, "npc_pardal", "Pardal")
    upd, _, _ = fm.join(st, "mao_sombria")
    st = merge(st, upd)
    assert st["faction_membership"]["mao_sombria"]["rival_awareness"] == {}
    assert fm.apply_rival_awareness(st, "na_anel_ferro", arrived=True)[0] == {}
    # traição expõe e gera pendência POSITIVA para os rivais da fação traída
    upd2, _, _ = fm.leave(st, "mao_sombria")
    rec = upd2["faction_membership"]["mao_sombria"]
    assert rec["status"] == "traidor" and rec["exposed"] is True
    assert rec["rival_awareness"] == {"legiao_ferro": 1}
    st2 = merge(st, upd2)
    before = _rep(st2, "legiao_ferro")
    upd3, _, _ = fm.apply_rival_awareness(st2, "na_anel_ferro", arrived=True)
    assert _rep(merge(st2, upd3), "legiao_ferro") == before + fm.REP_STEP


def test_rival_awareness_via_npc_knowledge_quando_on(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    st = make_state()
    upd, events, _ = fm.join(st, "legiao_ferro")
    st = merge(st, upd)
    ev = {**events[0], "event_id": "ev-join-1", "turn": 5}
    st["event_log"] = [ev]
    st["npcs"]["Capanga"] = {
        "id": "npc_x",
        "name": "Capanga",
        "faction_id": "filhos_chama_azul",
        "in_scene": False,
        "relationship": 5,
    }
    st["knowledge_links"] = [
        {
            "link_id": "l1",
            "holder_id": "npc:Capanga",
            "subject_kind": "event",
            "subject_id": "ev-join-1",
            "relation": "told_to",
            "source": "player",
            "channel": "messenger",
            "hops": 1,
            "clock": 1,
            "turn": 5,
        }
    ]
    # sem chegar à região do rival (arrived=False): só a notícia conta
    called = {}

    def fake_known(state, npc_id):
        called["id"] = npc_id
        return {"heard": {"ev-join-1"}, "observed": set(), "believed": set()}

    from services import npc_knowledge

    monkeypatch.setattr(npc_knowledge, "known_subject_ids", fake_known)
    before = _rep(st, "filhos_chama_azul")
    upd2, _, _ = fm.apply_rival_awareness(st, "skallgard", arrived=False)
    st2 = merge(st, upd2)
    assert _rep(st2, "filhos_chama_azul") == before - fm.REP_STEP
    # a Mão Sombria não ouviu nada (nenhum NPC dela): segue pendente
    assert "mao_sombria" in st2["faction_membership"]["legiao_ferro"]["rival_awareness"]


def test_membership_event_so_propaga_se_publico():
    from services import npc_knowledge

    pub = {
        "type": "faction_membership_changed",
        "target_id": "legiao_ferro",
        "payload": {"action": "joined"},
    }
    sec = {
        "type": "faction_membership_changed",
        "target_id": "mao_sombria",
        "payload": {"action": "joined"},
    }
    exp = {
        "type": "faction_membership_changed",
        "target_id": "mao_sombria",
        "payload": {"action": "betrayed", "exposed": True},
    }
    assert npc_knowledge._witnessable(pub) is True
    assert npc_knowledge._witnessable(sec) is False
    assert npc_knowledge._witnessable(exp) is True


def test_faccao_defeated_dissolve_vinculo():
    st = joined(make_state(), "druidas_ciclo_cinzento", merit=3)
    st["quests"] = [mission_quest("druidas_ciclo_cinzento")]
    for f in st["factions"]:
        if f["id"] == "druidas_ciclo_cinzento":
            f["defeated"] = True
    upd, events, note = fm.on_faction_defeated(st, "druidas_ciclo_cinzento")
    assert upd["faction_membership"]["druidas_ciclo_cinzento"]["status"] == "dissolvida"
    assert [e["payload"]["action"] for e in events] == ["dissolved"]
    assert upd["quests"][0]["status"] == "failed" and note
    # idempotente
    assert fm.on_faction_defeated(merge(st, upd), "druidas_ciclo_cinzento") == ({}, [], "")
    assert fm.can_join(merge(st, upd), "druidas_ciclo_cinzento") == (False, "fechada")


def test_ascensao_da_propria_faccao_nomeia_no_bloco():
    st = joined(make_state(), "legiao_ferro")
    events = [{"id": "legiao_ferro", "name": "A Legião de Ferro"}]
    line = fm.ascension_member_note(st, events)
    assert line.startswith("[FAÇÃO]") and "Legião" in line
    assert fm.ascension_member_note(make_state(), events) == ""
    # fim a fim: a ascensão resolve o objetivo e a nota do membro entra no turno
    new, ev = wu.advance_factions(
        [dict(f, progress=99) if f["id"] == "legiao_ferro" else f for f in st["factions"]], 1
    )
    assert any(e["id"] == "legiao_ferro" for e in ev)
    assert fm.ascension_member_note(st, ev)


def test_expulsao_quando_reputacao_despenca():
    st = joined(make_state(), "legiao_ferro", rank_index=2)
    st = set_rep(st, "legiao_ferro", -45)
    upd, events, note = fm.check_expulsion(st)
    rec = upd["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "expulso" and rec["rank_index"] == 2  # patente fica só no histórico
    assert [e["payload"]["action"] for e in events] == ["expelled"] and note
    assert fm.check_expulsion(make_state()) == ({}, [], "")
