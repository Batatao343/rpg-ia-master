"""SPEC-310 Etapas 1-5 — unitários de services/npc_self.py (puro, offline)."""

from __future__ import annotations

import copy
import re

import pytest

import gamedata
from services import faction_membership as fm
from services import npc_knowledge as nk
from services import npc_self as ns
from tests.spec310_helpers import (
    HERE,
    HOME,
    WAR_KEY,
    changed_today_event,
    make_state,
    sergeant,
    sim_entry,
    war_state,
)

REF = "npc_sargento_ruiva"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    monkeypatch.delenv("RPG_NPC_SELF", raising=False)


def _name(fid: str) -> str:
    return fm.faction_name(make_state(), fid)


def _text(state, row=None, key="Ruiva", **kw) -> str:
    return ns.npc_self_blocks(state, key, row or sergeant(), **kw).text()


# --- Etapa 1: fação e patente ----------------------------------------------------------
def test_faction_prefere_affiliation_da_304():
    st = make_state(world_projection={"npc_affiliations": {REF: "poder_kahen"}})
    assert ns.self_faction(st, "Ruiva", sergeant()) == "poder_kahen"


def test_faction_le_faction_id_da_semente():
    row = {"id": "npc_x", "name": "X", "faction_id": "legiao_ferro"}
    assert ns.self_faction(make_state(), "X", row) == "legiao_ferro"


def test_faction_lider_por_aresta_leads():
    row = {"id": "npc_comandante_thrace", "name": "Thrace", "role": "Comandante"}
    assert ns.self_faction(make_state(), "Thrace", row) == "legiao_ferro"


def test_faction_invalida_omitida():
    row = {"id": "npc_x", "name": "X", "faction_id": "nao_existe", "faction": "tambem_nao"}
    assert ns.self_faction(make_state(), "X", row) == ""
    assert "membro" not in ns.npc_self_blocks(make_state(), "X", row).sobre_voce


def test_rank_lider():
    row = {"id": "npc_comandante_thrace", "role": "Comandante"}
    assert ns.self_rank(make_state(), "npc_comandante_thrace", row, "legiao_ferro") == "líder"


def test_rank_por_role_sem_acento():
    row = sergeant(role="sargento da legiao")
    assert ns.self_rank(make_state(), REF, row, "legiao_ferro") == "Sargento"


def test_rank_default_membro():
    row = sergeant(role="Ferreiro")
    assert ns.self_rank(make_state(), REF, row, "legiao_ferro") == "membro"


def test_identidade_com_patente():
    assert f"Você serve em {_name('legiao_ferro')} como Sargento." in _text(make_state())


def test_faction_derrotada_vira_passado():
    st = make_state()
    for f in st["factions"]:
        if f["id"] == "legiao_ferro":
            f["defeated"] = True
    text = _text(st)
    assert "servia" in text and "caiu" in text
    assert "Sargento" not in text


def test_faccao_secreta_sem_intel_sem_nome():
    row = sergeant(faction_id="mao_sombria", role="Olheiro")
    text = _text(make_state(), row)
    assert "irmandade que não pode ser nomeada" in text
    assert _name("mao_sombria") not in text


def test_faccao_secreta_com_intel_nomeia_e_pede_sigilo():
    st = make_state(faction_intel={"mao_sombria": {"known": True}})
    text = _text(st, sergeant(faction_id="mao_sombria", role="Olheiro"))
    assert _name("mao_sombria") in text and "nunca admita isso a estranhos" in text


# --- Etapa 2: agenda e lugar -----------------------------------------------------------
def test_agenda_em_casa_com_frase_de_arquetipo():
    st = make_state(npc_sim=sim_entry(location_id=HOME, since_day=1))
    lines = ns.agenda_lines(st, "Ruiva", sergeant())
    assert lines[0] == "Você vive aqui, em Anel de Lama."
    assert len(lines) == 2 and lines[1] in ns._ARCHETYPE_PHRASES.values()


def test_agenda_de_passagem_sem_digitos():
    st = make_state(npc_sim=sim_entry(location_id=HERE, since_day=4, return_day=7))
    (line,) = ns.agenda_lines(st, "Ruiva", sergeant())
    assert "de passagem" in line and "Anel de Lama" in line
    assert "chegou ontem" in line and "em poucos dias" in line
    assert not re.search(r"\d", line)


def test_agenda_volta_amanha_e_chegou_ha_pouco():
    st = make_state(npc_sim=sim_entry(location_id=HERE, since_day=5, return_day=6))
    (line,) = ns.agenda_lines(st, "Ruiva", sergeant())
    assert "há pouco" in line and "amanhã" in line


def test_agenda_refugiado():
    st = make_state(
        npc_sim=sim_entry(location_id=HERE, since_day=4, refugee_from=HOME),
        world_projection={
            "location_states": {HOME: {"state": "cerco", "severity": 2, "since_day": 3}}
        },
    )
    (line,) = ns.agenda_lines(st, "Ruiva", sergeant())
    assert line.startswith("Você fugiu de Anel de Lama") and "por causa de" in line
    assert "severity" not in line and not re.search(r"\d", line)


def test_agenda_ferido():
    st = make_state(npc_sim=sim_entry(location_id=HOME, since_day=1))
    st["npc_sim"]["npcs"][REF]["status"] = "ferido"
    assert "Você ainda se recupera de um ferimento." in ns.agenda_lines(st, "Ruiva", sergeant())


def test_agenda_party_ativa_so_viaja():
    st = make_state(party=[{"id": REF, "name": "Ruiva", "active": True}])
    assert ns.agenda_lines(st, "Ruiva", sergeant()) == ["Você viaja com o herói."]


def test_agenda_modo_off_usa_home(monkeypatch):
    monkeypatch.setenv("RPG_NPC_WORLD", "off")
    st = make_state(npc_sim=sim_entry(location_id=HERE, since_day=4))
    lines = ns.agenda_lines(st, "Ruiva", sergeant())
    assert lines[0] == "Você vive em Anel de Lama."
    assert not any("passagem" in ln for ln in lines)


def test_lugar_rotulo_publico_e_data():
    st = make_state(
        world_projection={"location_states": {HERE: {"state": "cerco", "severity": 3}}},
    )
    st["world"]["date"] = {"day": 5, "label": "5º dia de Vorrnak"}
    lines = ns.place_lines(st)
    assert lines[0].startswith("Aqui, agora: ") and lines[1] == "Hoje é 5º dia de Vorrnak."


def test_lugar_nunca_outro_local_nem_severidade():
    st = make_state(
        world_projection={
            "location_states": {
                HERE: {"state": "cerco", "severity": 3, "crisis_id": "c1", "cause": "guerra"},
                "brekmar": {"state": "praga", "severity": 2},
            }
        }
    )
    text = "\n".join(ns.place_lines(st))
    assert "praga" not in text.lower() and "Brekmar" not in text
    assert "severity" not in text and "c1" not in text and "3" not in text


# --- Etapa 3: relações da fação --------------------------------------------------------
def test_relacao_guerra_conhecida_por_membro():
    (line,) = ns.relation_lines(war_state(), REF, "legiao_ferro")
    assert line == f"Sua fação está em guerra com {_name('filhos_chama_azul')}."


def test_relacao_mudou_hoje_membro_nao_sabe():
    st = war_state(event_log=[changed_today_event()])
    assert ns.relation_lines(st, REF, "legiao_ferro") == []


def test_relacao_mudou_hoje_lider_sabe():
    st = war_state(event_log=[changed_today_event()])
    assert len(ns.relation_lines(st, "npc_comandante_thrace", "legiao_ferro")) == 1


def test_relacao_mudou_hoje_no_ledger_sabe():
    ev = changed_today_event()
    st = war_state(
        event_log=[ev],
        knowledge_links=[
            {
                "link_id": "k1",
                "holder_id": f"npc:{REF}",
                "subject_kind": "event",
                "subject_id": ev["event_id"],
                "relation": "believed_by",
                "source": "world",
                "channel": "messenger",
                "hops": 1,
                "acquired_clock": 1,
                "acquired_turn": 1,
            }
        ],
    )
    assert len(ns.relation_lines(st, REF, "legiao_ferro")) == 1


def test_relacao_sem_numero_nem_hostil_cordial():
    st = war_state()
    st["world_sim"]["faction_relations"] = {WAR_KEY: -77, "a|b": -25, "c|d": 30}
    st["world_sim"]["relation_bands"]["legiao_ferro|poder_kahen"] = "neutra"
    text = "\n".join(ns.relation_lines(st, REF, "legiao_ferro"))
    assert "77" not in text and not re.search(r"hostil|cordial|neutra", text)


def test_relacao_max_duas_linhas_ordem():
    st = war_state()
    bands = st["world_sim"]["relation_bands"]
    bands["legiao_ferro|poder_kahen"] = "alianca"
    bands["legiao_ferro|clas_combate"] = "guerra"
    lines = ns.relation_lines(st, REF, "legiao_ferro")
    assert len(lines) == ns.MAX_RELATION_LINES
    assert all("guerra" in ln for ln in lines)  # guerra antes de aliança


def test_relacao_com_faccao_secreta_desconhecida_omitida():
    st = make_state()
    st["world_sim"] = {"relation_bands": {"legiao_ferro|mao_sombria": "guerra"}}
    assert ns.relation_lines(st, REF, "legiao_ferro") == []
    st["faction_intel"] = {"mao_sombria": {"known": True}}
    assert len(ns.relation_lines(st, REF, "legiao_ferro")) == 1


# --- Etapa 4: motivações ----------------------------------------------------------------
def _seeded_row(secret="sec_desertor") -> dict:
    return sergeant(
        seed_motives={
            "desire_id": "des_juntar_ouro",
            "fear_id": "fear_escuro",
            "secret_id": secret,
            "contradiction_id": "con_generoso_sovina",
            "mannerism_id": "man_bate_o_dedo",
        }
    )


def test_motivos_labels_da_tabela():
    text = "\n".join(ns.motive_lines(_seeded_row()))
    assert "Você deseja: juntar ouro para sair da região." in text
    assert "Você teme: o escuro total." in text
    assert "Sua contradição: generoso com estranhos, sovina com a família." in text
    assert "Seu jeito: bate o dedo na mesa ao pensar." in text


def test_segredo_vira_topico_nunca_label():
    text = "\n".join(ns.motive_lines(_seeded_row()))
    assert "Há um assunto que você evita: seu passado de armas." in text
    assert "desertou" not in text


def test_segredo_sem_topico_omitido(monkeypatch):
    monkeypatch.setattr(ns, "_secret_topics", lambda: {})
    text = "\n".join(ns.motive_lines(_seeded_row()))
    assert "assunto" not in text and "Você deseja" in text


def test_id_desconhecido_descartado():
    row = sergeant(seed_motives={"desire_id": "des_xxx", "fear_id": "fear_escuro"})
    lines = ns.motive_lines(row)
    assert lines == ["Você teme: o escuro total."]


def test_sem_semente_bloco_vazio():
    assert ns.motive_lines(sergeant()) == []
    assert ns.npc_self_blocks(make_state(), "Ruiva", sergeant()).motivacoes == ""


def test_motivacoes_rodape_fixo():
    blocks = ns.npc_self_blocks(make_state(), "Ruiva", _seeded_row())
    assert blocks.motivacoes.startswith("<MOTIVACOES_INTERNAS>")
    assert "não recite estas linhas" in blocks.motivacoes


def test_seed_motives_fora_da_allowlist_do_pool():
    from services.shared_pool_models import DOCUMENT_ALLOWLIST, PoolNamespace

    assert "seed_motives" not in DOCUMENT_ALLOWLIST[PoolNamespace.NPC]


def test_submit_grava_seed_motives(monkeypatch):
    import agents.npc as npc_mod
    from services import npc_seed

    seed = npc_seed.roll_npc_seed(game_id="g310", turn=1, location_id=HERE)
    monkeypatch.setattr(
        "services.shared_pool.submit", lambda *a, **k: type("E", (), {"entry_id": "e1"})()
    )
    data = npc_mod._submit_generated_npc(
        {"name": "Zed", "role": "Ferreiro", "persona": "x", "attributes": {}},
        seed,
        "g310",
        "",
        [],
    )
    assert data["seed_motives"] == npc_mod.seed_motives_of(seed)
    assert data["seed_motives"]["secret_id"] == seed.secret_id


def test_materialize_copia_seed_motives():
    from services import npc_seed
    from services.shared_pool import materialize_npc
    from tests.spec297_support import entry

    seed = npc_seed.roll_npc_seed(game_id="g310", turn=2, location_id=HERE)
    row = materialize_npc(entry(sd=seed), game_id="g310b")
    assert row["seed_motives"]["desire_id"] == seed.desire_id
    assert row["seed_motives"]["secret_id"] == seed.secret_id
    assert "seed_motives" not in materialize_npc(
        entry().model_copy(update={"seed": None}), game_id="g"
    )


def test_roundtrip_persistence_preserva_seed_motives(tmp_path, monkeypatch):
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    row = _seeded_row()
    st = make_state(npcs={"Ruiva": row})
    st.update(
        game_id="spec310_rt",
        narrative_summary="",
        archivist_last_run=0,
        chronicle=[],
        enemies=[],
        campaign_plan={},
    )
    assert persistence.save_game_state(st)
    loaded = persistence.load_game_state(str(tmp_path / "spec310_rt.json"))
    assert next(iter(loaded["npcs"].values()))["seed_motives"] == row["seed_motives"]
    # R24: save sem os campos novos ainda conversa
    loaded["npcs"]["Ruiva"].pop("seed_motives", None)
    loaded["npcs"]["Ruiva"].pop("faction_id", None)
    assert isinstance(ns.npc_self_blocks(loaded, "Ruiva", loaded["npcs"]["Ruiva"]).text(), str)


def test_lider_so_de_outra_faccao_nao_e_lider():
    row = {"id": "npc_comandante_thrace", "role": "Comandante"}
    assert ns.self_rank(make_state(), "npc_comandante_thrace", row, "poder_kahen") != "líder"
    st = war_state()
    st["world_sim"]["relation_bands"] = {"filhos_chama_azul|poder_kahen": "guerra"}
    st["event_log"] = [changed_today_event()]
    assert ns.relation_lines(st, "npc_comandante_thrace", "poder_kahen") != []


def test_relacao_ledger_usa_id_do_ledger():
    ev = changed_today_event()
    st = war_state(event_log=[ev])
    st["knowledge_links"] = [
        {
            "link_id": "k1",
            "holder_id": "npc:ledger_id",
            "subject_kind": "event",
            "subject_id": ev["event_id"],
            "relation": "believed_by",
            "source": "world",
            "channel": "messenger",
            "hops": 1,
            "acquired_clock": 1,
            "acquired_turn": 1,
        }
    ]
    assert ns.relation_lines(st, REF, "legiao_ferro") == []
    assert len(ns.relation_lines(st, REF, "legiao_ferro", "ledger_id")) == 1


def test_motor_off_sem_linhas_de_estado_local(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    st = make_state(world_projection={"location_states": {HERE: {"state": "cerco", "severity": 3}}})
    assert ns.place_lines(st) == []


def test_total_nunca_passa_de_1950(monkeypatch):
    monkeypatch.setattr(ns, "SELF_MAX_CHARS", 700)
    monkeypatch.setattr(ns, "_identity_lines", lambda *a: ["x" * 60] * 11)
    monkeypatch.setattr(ns, "_knows_lines", lambda *a: ["y" * 70] * 14)
    monkeypatch.setattr(ns, "motive_lines", lambda *a: ["z" * 60] * 7)
    text = ns.npc_self_blocks(make_state(), "Ruiva", sergeant()).text()
    assert 0 < len(text) <= ns.TOTAL_MAX_CHARS == 1950


# --- Etapa 5: o que ele sabe -----------------------------------------------------------
KILL = {
    "event_id": "ev_kill_1",
    "turn": 7,
    "type": "npc_killed",
    "actor_id": "player",
    "target_id": "npc_valerius",
    "payload": {},
    "source": "combat",
}
KILL2 = {**KILL, "event_id": "ev_kill_2", "target_id": "npc_rhea"}


def _link(sid: str, clock: int) -> dict:
    return {
        "link_id": sid,
        "holder_id": f"npc:{REF}",
        "subject_kind": "event",
        "subject_id": sid,
        "relation": "observed_by",
        "source": "world",
        "channel": "witness",
        "hops": 0,
        "acquired_clock": clock,
        "acquired_turn": 1,
    }


def _know_state(**over) -> dict:
    st = make_state(
        event_log=[KILL, KILL2],
        knowledge_links=[_link("ev_kill_1", 1), _link("ev_kill_2", 2)],
        npcs={"Ruiva": sergeant()},
    )
    st.update(over)
    return st


def test_sabe_vazio_com_215_off_e_shadow(monkeypatch):
    for value in ("off", "shadow"):
        monkeypatch.setenv("RPG_NPC_KNOWLEDGE", value)
        assert ns.npc_self_blocks(_know_state(), "Ruiva", sergeant()).o_que_sabe == ""


def test_sabe_traz_ledger_com_215_on():
    block = ns.npc_self_blocks(_know_state(), "Ruiva", sergeant()).o_que_sabe
    assert block.startswith("<O_QUE_VOCE_SABE>") and "[VIU]" in block


def test_sabe_exclui_ids_do_pack():
    full = ns.npc_self_blocks(_know_state(), "Ruiva", sergeant()).o_que_sabe
    part = ns.npc_self_blocks(
        _know_state(), "Ruiva", sergeant(), pack_evidence_ids=["ev_kill_2"]
    ).o_que_sabe
    assert full.count("[VIU]") == 2 and part.count("[VIU]") == 1
    assert (
        ns.npc_self_blocks(
            _know_state(), "Ruiva", sergeant(), pack_evidence_ids=["ev_kill_1", "ev_kill_2"]
        ).o_que_sabe
        == ""
    )


def test_sabe_respeita_teto_da_faixa_hostil_zero():
    row = sergeant(relationship=-80, relationship_basis={"x": 1})
    st = _know_state(npcs={"Ruiva": row})
    assert ns.npc_self_blocks(st, "Ruiva", row).o_que_sabe == ""


def test_sabe_secreto_continua_fechado(monkeypatch):
    monkeypatch.setattr(nk, "_is_secret", lambda *_a, **_k: True)
    assert ns.npc_self_blocks(_know_state(), "Ruiva", sergeant()).o_que_sabe == ""


def test_npc_knowledge_block_default_compativel():
    st = _know_state()
    old = nk.npc_knowledge_block(st, REF)
    assert old == nk.npc_knowledge_block(st, REF, limit=nk.NPC_KNOWLEDGE_CONTEXT_MAX)
    assert old.startswith("<O_QUE_VOCE_SABE>")
    assert nk.lines_cap(st, REF) == nk.NPC_KNOWLEDGE_CONTEXT_MAX


# --- puro / determinístico --------------------------------------------------------------
def test_modulo_puro_nao_muta_e_e_deterministico():
    st = war_state(npc_sim=sim_entry(location_id=HERE, since_day=4, return_day=7))
    row = _seeded_row()
    before = (copy.deepcopy(st), copy.deepcopy(row))
    a = ns.npc_self_blocks(st, "Ruiva", row).text()
    b = ns.npc_self_blocks(st, "Ruiva", row).text()
    assert a == b and a
    assert (st, row) == before


def test_exemplo_completo_tem_os_dois_blocos():
    st = war_state(npc_sim=sim_entry(location_id=HERE, since_day=4, return_day=7))
    blocks = ns.npc_self_blocks(st, "Ruiva", _seeded_row())
    assert blocks.sobre_voce.startswith("<SOBRE_VOCE>") and blocks.sobre_voce.endswith(
        "</SOBRE_VOCE>"
    )
    assert gamedata.get_location(HOME)["name"] in blocks.sobre_voce
