"""SPEC-301 Etapa 4 — missões de fação: oferta, conclusão, mérito, contra-jogo (R7/R11-R13)."""

from __future__ import annotations

import world_utils as wu
from services import event_processor, quest_log
from services import faction_membership as fm
from services import faction_missions as fmi
from services import world_validators as wv
from tests.spec301_support import faction, joined, make_state, merge, mission_quest


def _member(**record):
    return joined(make_state(), "legiao_ferro", **record)


def test_offer_mission_deterministico_por_seed():
    st = _member()
    q1, quest1, _ = fmi.offer_mission(st, "legiao_ferro")
    q2, quest2, _ = fmi.offer_mission(st, "legiao_ferro")
    assert quest1 == quest2 and quest1 is not None
    assert quest1["faction_id"] == "legiao_ferro"
    assert quest1["mission_kind"] in ("apoio", "sabotagem")
    st2 = merge(st, {"game_id": "outro-jogo"})
    seen = {fmi.offer_mission(st2, "legiao_ferro")[1]["title"] for _ in range(1)}
    assert seen  # outro seed também oferece algo
    titles = set()
    st = _member(rank_index=1)
    for turn in range(1, 25):
        s = merge(st, {"world": {**st["world"], "turn_count": turn}})
        titles.add(fmi.offer_mission(s, "legiao_ferro")[1]["title"])
    assert len(titles) > 1  # o seed varia com o turno


def test_texto_vem_do_template():
    st = _member()
    _, quest, note = fmi.offer_mission(st, "legiao_ferro")
    templates = fm.load_catalog()["legiao_ferro"]["mission_templates"]
    tpl = next(t for t in templates if t["title"] == quest["title"])
    assert quest["description"] == tpl["description"]
    assert quest["title"] in note


def test_respeita_min_rank_e_uma_ativa_por_faccao():
    st = _member(rank_index=0)
    for turn in range(1, 40):
        s = merge(st, {"world": {**st["world"], "turn_count": turn}})
        quest = fmi.offer_mission(s, "legiao_ferro")[1]
        tpl = next(
            t
            for t in fm.load_catalog()["legiao_ferro"]["mission_templates"]
            if t["title"] == quest["title"]
        )
        assert tpl["min_rank"] == 0 and tpl["kind"] != "rito"
    # com uma missão ativa, não oferece outra
    quests, quest, _ = fmi.offer_mission(st, "legiao_ferro")
    st2 = merge(st, {"quests": quests})
    quests2, quest2, note = fmi.offer_mission(st2, "legiao_ferro")
    assert quest2 is None and quests2 == quests and note


def test_respeita_max_active_quests():
    st = _member()
    st["quests"] = [mission_quest("outra", qid=f"x{i}") for i in range(quest_log.MAX_ACTIVE_QUESTS)]
    quests, quest, note = fmi.offer_mission(st, "legiao_ferro")
    assert quest is None and len(quests) == quest_log.MAX_ACTIVE_QUESTS and note


def test_location_fora_do_mapa_descartado(monkeypatch):
    cat = {
        "legiao_ferro": {
            **fm.load_catalog()["legiao_ferro"],
            "mission_templates": [
                {
                    "id": "ruim",
                    "kind": "apoio",
                    "tier": 1,
                    "min_rank": 0,
                    "location_ids": ["lugar_fantasma"],
                    "title": "Ruim",
                    "description": "x",
                },
                {
                    "id": "boa",
                    "kind": "apoio",
                    "tier": 1,
                    "min_rank": 0,
                    "location_ids": ["na_anel_lama", "lugar_fantasma"],
                    "title": "Boa",
                    "description": "y",
                },
            ],
        }
    }
    monkeypatch.setattr(fm, "load_catalog", lambda: cat)
    for turn in range(1, 12):
        s = _member()
        s["world"]["turn_count"] = turn
        quest = fmi.offer_mission(s, "legiao_ferro")[1]
        assert quest["title"] == "Boa" and quest["location_id"] == "na_anel_lama"


def test_sem_template_utilizavel_nao_cria_quest(monkeypatch):
    cat = {
        "legiao_ferro": {
            **fm.load_catalog()["legiao_ferro"],
            "mission_templates": [
                {
                    "id": "ruim",
                    "kind": "apoio",
                    "tier": 1,
                    "min_rank": 0,
                    "location_ids": ["lugar_fantasma"],
                    "title": "Ruim",
                    "description": "x",
                }
            ],
        }
    }
    monkeypatch.setattr(fm, "load_catalog", lambda: cat)
    _, quest, note = fmi.offer_mission(_member(), "legiao_ferro")
    assert quest is None and note


def test_sabotagem_nao_oferecida_contra_fac_propria():
    st = joined(_member(), "filhos_chama_azul")  # membro dos Filhos: alvo da sabotagem da Legião
    for turn in range(1, 30):
        s = merge(st, {"world": {**st["world"], "turn_count": turn}})
        quest = fmi.offer_mission(s, "legiao_ferro")[1]
        assert quest["mission_kind"] != "sabotagem"


def _proposal(qid):
    return {
        "type": "quest_completed",
        "actor_id": "player",
        "target_id": qid,
        "payload": {"quest_id": qid},
        "source": "storyteller",
    }


def test_conclusao_exige_prova():
    st = _member()
    q = mission_quest("legiao_ferro", location_id="na_anel_lama", created_turn=1)
    st["quests"] = [q]
    res = wv.validate_proposal(_proposal("q1"), st)
    assert not res.ok  # sem location_reached
    q["progress_log"] += [
        {"kind": "location_reached", "turn": 3, "detail": "na_anel_lama"},
        {"kind": "investigation", "turn": 4, "detail": "x"},
    ]
    assert wv.validate_proposal(_proposal("q1"), st).ok


def _complete(st, qid="q1"):
    st = dict(st)
    st["pending_world_events"] = [
        {
            "type": "quest_completed",
            "actor_id": "player",
            "target_id": qid,
            "payload": {"quest_id": qid},
            "source": "system",
        }
    ]
    out = event_processor.process_pending_events(st)
    return merge(st, out), out


def test_conclusao_apoio_sobe_progress_satura_99():
    st = _member()
    faction(st, "legiao_ferro")["progress"] = 97
    st["quests"] = [mission_quest("legiao_ferro", kind="apoio", tier=3)]
    st2, _ = _complete(st)
    f = faction(st2, "legiao_ferro")
    assert f["progress"] == 99 and not f.get("completed")
    assert f["influence"] == fm.MISSION_INFLUENCE[3]
    st = _member()
    faction(st, "legiao_ferro")["progress"] = 10
    st["quests"] = [mission_quest("legiao_ferro", kind="apoio", tier=2)]
    st2, _ = _complete(st)
    assert faction(st2, "legiao_ferro")["progress"] == 10 + fm.MISSION_PROGRESS[2]


def test_sabotagem_desce_rival_piso_0():
    st = _member()
    faction(st, "filhos_chama_azul")["progress"] = 4
    st["quests"] = [
        mission_quest("legiao_ferro", kind="sabotagem", tier=2, target="filhos_chama_azul")
    ]
    st2, _ = _complete(st)
    f = faction(st2, "filhos_chama_azul")
    assert f["progress"] == 0  # piso 0 (4 - 5)
    assert f["influence"] == -fm.MISSION_INFLUENCE[2]
    # a própria fação não ganha progresso com sabotagem
    assert faction(st2, "legiao_ferro")["progress"] == faction(st, "legiao_ferro")["progress"]
    # mérito de sabotagem = tier + 1
    assert st2["faction_membership"]["legiao_ferro"]["merit"] == 3


def test_merito_e_promocao_uma_por_evento():
    st = _member(merit=6)  # 6 + 3 = 9: alcança o mérito do Sargento (7), mas só sobe 1
    st["player"]["level"] = 9
    st["quests"] = [mission_quest("legiao_ferro", kind="apoio", tier=3)]
    st2, out = _complete(st)
    assert st2["faction_membership"]["legiao_ferro"]["rank_index"] == 1
    promoted = [
        e
        for e in out["event_log"]
        if e["type"] == "faction_membership_changed" and e["payload"]["action"] == "promoted"
    ]
    assert len(promoted) == 1 and promoted[0]["payload"]["rank_name"] == "Legionário"
    assert any("promove" in n["text"] for n in out["reputation_notices"])


def test_min_level_segura_promocao():
    st = _member(merit=6)
    st["player"]["level"] = 1  # Legionário exige nível 2
    st["quests"] = [mission_quest("legiao_ferro", kind="apoio", tier=3)]
    st2, _ = _complete(st)
    assert st2["faction_membership"]["legiao_ferro"]["rank_index"] == 0
    assert st2["faction_membership"]["legiao_ferro"]["merit"] == 9


def test_ouro_por_tier_so_para_faction_quest():
    quests = [mission_quest("legiao_ferro", tier=3, qid="a"), {"id": "b", "status": "active"}]
    _, gold_a = quest_log.complete_quest_with_reward(quests, "a", 5)
    _, gold_b = quest_log.complete_quest_with_reward(quests, "b", 5)
    assert gold_a == quest_log.MISSION_GOLD[3] == 50
    assert gold_b == quest_log.QUEST_REWARD_GOLD == 20
    st = _member()
    st["quests"] = [mission_quest("legiao_ferro", tier=2)]
    ouro0 = st["player"]["gold"]
    st2, _ = _complete(st)
    assert st2["player"]["gold"] == ouro0 + quest_log.MISSION_GOLD[2]


def test_falha_tira_1_merito_sem_rebaixar():
    st = _member(rank_index=1, merit=4)
    q = mission_quest("legiao_ferro")
    upd = fm.on_mission_failed(st, q)
    rec = upd["faction_membership"]["legiao_ferro"]
    assert rec["merit"] == 3 and rec["rank_index"] == 1
    st0 = _member(rank_index=0, merit=0)
    assert fm.on_mission_failed(st0, q)["faction_membership"]["legiao_ferro"]["merit"] == 0
    assert fm.on_mission_failed(make_state(), q) == {}


def test_ascensao_so_no_tick():
    st = _member()
    faction(st, "legiao_ferro")["progress"] = 98
    st["quests"] = [mission_quest("legiao_ferro", kind="apoio", tier=3)]
    st2, _ = _complete(st)
    f = faction(st2, "legiao_ferro")
    assert f["progress"] == 99 and not f["completed"]
    new, events = wu.advance_factions(st2["factions"], 1)
    assert any(e["id"] == "legiao_ferro" for e in events)
    assert next(x for x in new if x["id"] == "legiao_ferro")["completed"] is True


def test_missao_so_conta_quando_ativa_e_membro():
    # membro que saiu: conclusão tardia não dá mérito nem progresso
    st = make_state()
    st["quests"] = [mission_quest("legiao_ferro", kind="apoio", tier=3)]
    st2, _ = _complete(st)
    assert "legiao_ferro" not in st2.get("faction_membership", {})
    assert faction(st2, "legiao_ferro")["progress"] == faction(st, "legiao_ferro")["progress"]


def test_regulariza_suspeito_com_apoio():
    st = _member(status="suspeito", offenses=[3])
    st["quests"] = [mission_quest("legiao_ferro", kind="apoio", tier=1)]
    st2, _ = _complete(st)
    rec = st2["faction_membership"]["legiao_ferro"]
    assert rec["status"] == "ativo" and rec["offenses"] == []
