"""SPEC-301 Etapa 2 — entrar, requisitos, limite, exclusividade, rito (R2-R6, R8)."""

from __future__ import annotations

import copy

import pytest

from services import event_processor
from services import faction_membership as fm
from services import world_validators as wv
from tests.spec301_support import (
    add_npc,
    at,
    faction,
    joined,
    make_state,
    merge,
    set_day,
    set_rep,
)

CLOSED = [
    "bandos_orc_saidas_baixas",
    "goblins_mineiros",
    "colmeia_hospedeiros",
    "mercadores_escravos_pradaria",
]


@pytest.mark.parametrize("fid", CLOSED)
def test_faccao_fechada_recusa_sempre(fid):
    st = set_rep(make_state(), fid, 100)
    assert fm.can_join(st, fid) == (False, "fechada")
    upd, events, note = fm.join(st, fid)
    assert upd == {} and events == [] and note


def test_ordem_dos_motivos():
    # Estado que falha em vários pontos: devolve o primeiro da ordem de R3.
    st = joined(make_state(), "legiao_ferro")
    assert fm.can_join(st, "legiao_ferro") == (False, "ja_membro")
    st = make_state()
    st["faction_membership"]["legiao_ferro"] = {
        "faction_id": "legiao_ferro",
        "status": "traidor",
        "cooldown_until_day": 99,
    }
    st["player"]["class_name"] = "X"
    assert fm.can_join(st, "legiao_ferro") == (False, "traidor_recente")
    # sem cooldown: cai no motivo seguinte (limite)
    st = joined(joined(make_state(), "druidas_ciclo_cinzento"), "poder_kahen")
    assert fm.can_join(st, "legiao_ferro") == (False, "limite_membros")
    # fora do QG e sem recrutador: 'local' vem depois de raça/classe/reputação
    st = at(make_state(), "skallgard")
    assert fm.can_join(st, "legiao_ferro") == (False, "local")
    st = set_rep(at(make_state(), "skallgard"), "legiao_ferro", -50)
    assert fm.can_join(st, "legiao_ferro") == (False, "reputacao")


def test_osshari_so_raca_osshari():
    st = at(make_state(), "bk_docas_velhas")
    assert fm.can_join(st, "osshari_brekmar") == (False, "raca")
    st["player"]["race_id"] = "race_osshari"
    st["player"]["race"] = "Osshari"
    assert fm.can_join(st, "osshari_brekmar") == (True, "")


def test_cultistas_so_classe_arcana():
    st = at(make_state(), "ae_ruinas_submersas")
    assert fm.can_join(st, "cultistas_destilacao") == (False, "classe")
    st["player"]["class_name"] = "Arcanista Cinzento"
    assert fm.can_join(st, "cultistas_destilacao") == (True, "")


def test_devoradores_so_origem_zhur():
    st = at(make_state(), "deserto_zhur")
    assert fm.can_join(st, "tribos_devoradores_sol") == (False, "origem")
    st["player"]["origin_region_id"] = "deserto_zhur"
    assert fm.can_join(st, "tribos_devoradores_sol") == (True, "")


def test_kahen_rank_cap_nao_sangromante():
    st = at(set_rep(make_state(), "poder_kahen", 20), "brekmar")
    assert fm.rank_cap_index(st, "poder_kahen") == 1
    st["player"]["class_name"] = "Sangromante"
    assert fm.rank_cap_index(st, "poder_kahen") == 2
    # mérito acima do teto é ignorado e não promove
    st = joined(at(make_state(), "brekmar"), "poder_kahen", rank_index=1, merit=5)
    st["player"]["level"] = 9
    q = {
        "id": "q",
        "faction_id": "poder_kahen",
        "mission_kind": "apoio",
        "mission_tier": 3,
        "status": "active",
    }
    upd, events, _ = fm.on_mission_completed(st, q)
    rec = upd.get("faction_membership", st["faction_membership"])["poder_kahen"]
    assert rec["rank_index"] == 1 and rec["merit"] == 5
    assert not [e for e in events if e["payload"]["action"] == "promoted"]


def test_limite_dois_vinculos():
    st = joined(joined(make_state(), "druidas_ciclo_cinzento"), "poder_kahen")
    assert fm.can_join(st, "legiao_ferro") == (False, "limite_membros")
    assert fm.MAX_MEMBERSHIPS == 2


def test_exclusiva_bloqueia():
    st = joined(make_state(), "legiao_ferro")
    st = at(st, "na_anel_lama")
    ok, reason = fm.can_join(set_rep(st, "filhos_chama_azul", 0), "filhos_chama_azul")
    assert (ok, reason) == (False, "exclusiva:legiao_ferro")


def test_secreta_conta_limite_nao_exclusividade():
    # Mão Sombria (secreta) + Legião: sem conflito de exclusividade; mas conta no limite.
    st = joined(make_state(), "mao_sombria")
    st["faction_intel"]["mao_sombria"] = {"known": True}
    st = set_rep(st, "legiao_ferro", 0)
    # secreta não pesa na exclusividade: Filhos (exclusive_with legiao) segue possível via legião ausente
    ok, _ = fm.can_join(at(st, "na_anel_ferro"), "legiao_ferro")
    assert ok
    # conta para o limite: secreta + outra = 2
    st2 = joined(joined(make_state(), "mao_sombria"), "druidas_ciclo_cinzento")
    assert fm.can_join(st2, "legiao_ferro") == (False, "limite_membros")
    # espião duplo: membro secreto de Filhos (exclusiva com Legião) pode entrar na Legião
    st3 = joined(make_state(), "filhos_chama_azul")
    assert fm.can_join(st3, "legiao_ferro") == (True, "")
    # mas se a secreta foi exposta, a exclusividade vale
    st4 = joined(make_state(), "filhos_chama_azul", exposed=True)
    assert fm.can_join(st4, "legiao_ferro") == (False, "exclusiva:filhos_chama_azul")


def test_local_exige_qg_ou_recrutador_presente():
    st = at(make_state(), "skallgard")
    assert fm.can_join(st, "legiao_ferro") == (False, "local")
    st = add_npc(st, "npc_comandante_thrace", "Comandante Thrace")
    assert fm.can_join(st, "legiao_ferro") == (True, "")
    st = add_npc(at(make_state(), "skallgard"), "npc_comandante_thrace", "Thrace", in_scene=False)
    assert fm.can_join(st, "legiao_ferro") == (False, "local")


def test_join_emite_um_evento_engine_e_marca_intel():
    st = make_state()
    upd, events, note = fm.join(st, "legiao_ferro")
    assert len(events) == 1
    ev = events[0]
    assert ev["type"] == "faction_membership_changed" and ev["source"] == "engine"
    assert ev["payload"]["action"] == "joined" and ev["payload"]["rank_id"] == "recruta"
    rec = upd["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "ativo" and rec["rank_index"] == 0 and rec["merit"] == 0
    assert upd["faction_intel"]["legiao_ferro"] == {"known": True, "knows_goal": True}
    assert "Recruta" in note
    # R16: fação pública gera pendência de rivais (-1 passo), ainda NÃO aplicada
    assert rec["rival_awareness"] == {"filhos_chama_azul": -1, "mao_sombria": -1}
    assert faction(merge(st, upd), "filhos_chama_azul")["reputation"] == 0


def test_rito_cria_quest_e_nao_registra_membro():
    st = make_state()
    st["player"]["class_name"] = "Sangromante"  # classe arcana paga o registro
    upd, events, note = fm.join(st, "legiao_ferro")
    assert events == []
    rec = upd["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "rito_pendente" and rec["rite_quest_id"]
    quest = next(q for q in upd["quests"] if q["id"] == rec["rite_quest_id"])
    assert quest["mission_kind"] == "rito" and quest["faction_id"] == "legiao_ferro"
    assert fm.active_memberships(merge(st, upd)) == {}
    # rito_pendente é o motivo de recusa de um segundo pedido
    assert fm.can_join(at(merge(st, upd), "na_anel_ferro"), "legiao_ferro") == (
        False,
        "rito_pendente",
    )


def test_rito_exigido_so_para_classes_do_rito():
    st = make_state()  # Médico de Campo: sem rito na Legião
    assert fm.entry_rite_for(st, "legiao_ferro") is None
    st["player"]["class_name"] = "Corruptor"
    assert fm.entry_rite_for(st, "legiao_ferro")["kind"] == "registro_arcano"
    # Clãs: origem Skallgard dispensa o rito
    st = at(make_state(), "skallgard")
    assert fm.entry_rite_for(st, "clas_combate")["kind"] == "rito_passagem"
    st["player"]["origin_region_id"] = "skallgard"
    assert fm.entry_rite_for(st, "clas_combate") is None


def _complete_rite(st, fid, upd):
    st = merge(st, upd)
    rec = st["faction_membership"][fid]
    quest = next(q for q in st["quests"] if q["id"] == rec["rite_quest_id"])
    return st, quest


def test_rito_concluido_efetiva_e_aplica_custo_batismo():
    st = at(make_state(), "na_anel_lama")
    upd, _, _ = fm.join(st, "filhos_chama_azul")
    assert upd["faction_membership"]["filhos_chama_azul"]["status"] == "rito_pendente"
    st, quest = _complete_rite(st, "filhos_chama_azul", upd)
    upd2, events, _ = fm.on_mission_completed(st, quest)
    rec = upd2["faction_membership"]["filhos_chama_azul"]
    assert rec["status"] == "ativo" and rec["marks"] == ["cicatriz_labios"]
    wounds = upd2["player"]["ferimentos"]["leve"]
    assert any(w["regiao"] == "labios" for w in wounds)
    assert [e["payload"]["action"] for e in events] == ["joined"]


def test_rito_registro_arcano_cobra_ouro():
    st = make_state()
    st["player"]["class_name"] = "Sangromante"
    upd, _, _ = fm.join(st, "legiao_ferro")
    st, quest = _complete_rite(st, "legiao_ferro", upd)
    upd2, _, _ = fm.on_mission_completed(st, quest)
    assert upd2["player"]["gold"] == 150
    assert upd2["faction_membership"]["legiao_ferro"]["status"] == "ativo"


def test_procurado_noop_sem_spec299(monkeypatch):
    # sem a SPEC-299 o requisito 'procurado' nunca recusa
    assert fm._is_wanted(make_state(), "Nova Arcádia") is False
    assert fm.can_join(make_state(), "legiao_ferro") == (True, "")
    monkeypatch.setattr(fm, "_is_wanted", lambda *_a, **_k: True)
    assert fm.can_join(make_state(), "legiao_ferro") == (False, "procurado")


def test_renegados_exigem_caminho_e_converte_traindo():
    st = at(make_state(), "skallgard")
    st = add_npc(st, "npc_korrin_sem_cla", "Korrin")
    assert fm.can_join(st, "renegados_ermo") == (False, "caminho")
    # ex-membro dos Clãs com desonra abre o caminho
    st["faction_membership"]["clas_combate"] = {
        "faction_id": "clas_combate",
        "status": "ex_membro",
        "left_day": 2,
        "cooldown_until_day": 0,
    }
    assert fm.can_join(st, "renegados_ermo") == (True, "")


def test_druidas_renegados_conversao_trai_o_ciclo():
    st = at(joined(make_state(), "druidas_ciclo_cinzento"), "pm_profundezas")
    st = add_npc(st, "npc_saelwen_a_que_afundou", "Saelwen")
    st["npcs"]["Saelwen"]["interaction_count"] = 3
    assert fm.can_join(st, "druidas_renegados") == (True, "")
    upd, events, _ = fm.join(st, "druidas_renegados")
    actions = sorted(
        e["payload"]["action"] for e in events if e["type"] == "faction_membership_changed"
    )
    assert actions == ["betrayed", "joined"]
    assert upd["faction_membership"]["druidas_ciclo_cinzento"]["status"] == "traidor"
    assert upd["faction_membership"]["druidas_renegados"]["status"] == "ativo"


def test_validator_aceita_evento_engine_e_rejeita_llm():
    st = make_state()
    base = {
        "type": "faction_membership_changed",
        "actor_id": "player",
        "target_id": "legiao_ferro",
        "payload": {"action": "joined"},
    }
    assert wv.validate_proposal({**base, "source": "engine"}, st).ok
    assert not wv.validate_proposal({**base, "source": "storyteller"}, st).ok
    assert not wv.validate_proposal(base, st).ok
    assert not wv.validate_proposal(
        {**base, "source": "engine", "payload": {"action": "voar"}}, st
    ).ok
    assert not wv.validate_proposal(
        {**base, "source": "engine", "target_id": "npc_comandante_thrace"}, st
    ).ok


def test_evento_passa_pelo_event_processor_e_vira_milestone():
    st = make_state()
    upd, events, _ = fm.join(st, "legiao_ferro")
    st = merge(st, upd)
    st["pending_world_events"] = events
    out = event_processor.process_pending_events(st)
    log = out["event_log"]
    assert any(e["type"] == "faction_membership_changed" for e in log)
    texts = [e["text"] for ch in out["chronicle"] for e in ch["entries"]]
    assert any("Recruta" in t for t in texts)


def test_nao_muta_estado_de_entrada():
    st = make_state()
    snap = copy.deepcopy(st)
    fm.join(st, "legiao_ferro")
    fm.leave(joined(st), "legiao_ferro")
    assert st == snap
    st2 = set_day(st, 7)
    assert fm.can_join(st2, "legiao_ferro")[0]
