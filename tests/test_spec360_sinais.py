"""SPEC-360 R5, R14-R18, R22: sinais em cena, encontro com presenca, conversao e aproximacao."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import HumanMessage

import gamedata
import world_utils as wu
from services import fauna
from services.fauna_lint import forbidden_for, leaked_tokens, load_refs

LAMA, FERRO = "na_anel_lama", "na_anel_ferro"
ARAME = "mon_arame_vivo"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")


def presence(cid=ARAME, locais=(LAMA,), shown=(), day=5, pid="pidarame0001") -> dict:
    return {
        "pid": pid,
        "creature_id": cid,
        "region_id": "nova_arcadia",
        "locais": list(locais),
        "born_day": day,
        "expires_day": day + 4,
        "sinais_mostrados": list(shown),
        "origem": "dia",
        "status": "ativa",
    }


def sim_with(*pres) -> dict:
    return {"fauna": {"v": 1, "presencas": list(pres), "carcacas": []}}


def state_at(loc=LAMA, sim=None, day=5, period="Noite", text="olho a viela", **extra) -> dict:
    st = {
        "game_id": "spec360-game",
        "world": {
            "turn_count": 20,
            "current_location": (gamedata.get_location(loc) or {}).get("name", loc),
            "current_location_id": loc,
            "visited": [loc],
            "world_clock": {"day": day, "period": period},
            "last_encounter_turn": -99,
        },
        "world_sim": sim or {},
        "player": {"name": "Heroi", "level": 3, "gold": 10, "virtudes": {"mente": 2}},
        "npcs": {},
        "party": [],
        "event_log": [],
        "pending_world_events": [],
        "bestiary_knowledge": {},
        "messages": [HumanMessage(content=text)],
    }
    st.update(extra)
    return st


def test_um_sinal_por_cena_na_ordem(on):
    st = state_at(sim=sim_with(presence()))
    seen = []
    for _ in range(6):
        block, upd = fauna.scene_block(st)
        if not block:
            break
        st["world_sim"] = upd["world_sim"]
        seen = st["world_sim"]["fauna"]["presencas"][0]["sinais_mostrados"]
        assert block.count("\n- ") == 1  # 1 sinal por cena
    kinds = {k for k, v in fauna.entry(ARAME)["sinais"].items() if v} & set(fauna.SIGN_TYPES)
    assert set(seen) == kinds
    assert seen[0] in fauna.FIRST_SIGNS  # vestigio antes de som/cheiro


def test_tipo_nunca_repete(on):
    st = state_at(sim=sim_with(presence()))
    for _ in range(10):
        _b, upd = fauna.scene_block(st)
        if upd:
            st["world_sim"] = upd["world_sim"]
    shown = st["world_sim"]["fauna"]["presencas"][0]["sinais_mostrados"]
    assert len(shown) == len(set(shown))


def test_bloco_vazio_zero_token(on, monkeypatch):
    assert fauna.scene_block(state_at(sim={})) == ("", {})
    assert fauna.scene_block(state_at(loc=FERRO, sim=sim_with(presence()))) == ("", {})
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "off")
    assert fauna.scene_block(state_at(sim=sim_with(presence()))) == ("", {})


def test_bloco_sem_nome(on):
    """R5/M6 no bloco: nenhum sinal de nenhuma criatura leva token do proprio nome."""
    refs = load_refs("nova_arcadia")
    for cid, e in fauna.load().items():
        for kind in fauna.SIGN_TYPES:
            text = (e["sinais"] or {}).get(kind)
            if text:
                block = fauna.render_block(text)
                assert not leaked_tokens(block, forbidden_for(cid, refs)), (cid, kind)
                assert "<SINAIS_NA_CENA>" in block and fauna.SCENE_RULE in block


def _enc(sim, loc=LAMA, period="Noite", seed=1, world_extra=None):
    world = {
        "current_location_id": loc,
        "current_location": loc,
        "world_clock": {"day": 5, "period": period},
        "danger_overrides": {loc: 4},
        **(world_extra or {}),
    }
    random.seed(seed)
    return wu.check_encounter(
        world, [], {}, 20 + seed, bestiary_knowledge={}, projection={}, player_level=3, world_sim=sim
    )


def test_encontro_prefere_presenca(on):
    for seed in range(8):
        enc = _enc(sim_with(presence(shown=("rastro",))), seed=seed)
        assert enc["enemy_id"] == ARAME and enc["presence_id"] == "pidarame0001"
        assert not enc.get("fauna_convert")


def test_conversao_em_sinal_sem_combate(on):
    convs = [_enc({}, seed=s) for s in range(30)]
    cedo = [
        e
        for e in convs
        if (fauna.entry(e["enemy_id"]) or {}).get("sinais", {}).get("antecedencia") == "cedo"
    ]
    assert cedo and all(e.get("fauna_convert") for e in cedo)
    e = cedo[0]
    note, upd = fauna.convert_to_signal(state_at(sim={}), fauna.entry(e["enemy_id"]), LAMA, 5)
    pres = upd["world_sim"]["fauna"]["presencas"][0]
    assert pres["origem"] == "conversao" and len(pres["sinais_mostrados"]) == 1
    assert note == fauna.entry(e["enemy_id"])["sinais"][pres["sinais_mostrados"][0]]
    # presenca ainda sem sinal: o primeiro encontro tambem anuncia antes (§9)
    enc = _enc(sim_with(presence()))
    assert enc["fauna_convert"] and enc["presence_id"] == "pidarame0001"


def test_imediato_combate_com_aproximacao(on):
    bagre = "enemy_polvo_esgoto"
    assert fauna.entry(bagre)["sinais"]["antecedencia"] == "imediato"
    enc = _enc(sim_with(presence(cid=bagre, pid="pidbagre0001")))
    assert enc["enemy_id"] == bagre and not enc.get("fauna_convert")
    assert enc["flavor"] == fauna.approach_line(bagre)
    hits = [e for e in (_enc({}, seed=s) for s in range(80)) if e["enemy_id"] == bagre]
    assert hits and all(not e.get("fauna_convert") and e["aproximacao"] for e in hits)


def test_aproximacao_no_combat_start_e_handoff(on, monkeypatch):
    from agents import storyteller

    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")  # o sim do teste nao e um sim do motor
    st = state_at(sim=sim_with(presence(shown=("rastro", "som"))), text="descanso aqui")
    st["world"]["danger_overrides"] = {LAMA: 4}
    monkeypatch.setattr(wu, "roll_encounter_type", lambda *a, **k: "combat")
    import world_utils

    monkeypatch.setattr(world_utils, "recovery_rest_safe", lambda *a, **k: False)
    out = storyteller.storyteller_node(st)
    assert out["next"] == "combat_agent"
    line = fauna.approach_line(ARAME)
    assert line in out["messages"][0].content
    assert out["combat_encounter_hint"]["aproximacao"] == line
    assert out["combat_encounter_hint"]["enemy_id"] == ARAME
    # R23: os sinais vistos ganham dono
    assert out["bestiary_knowledge"][ARAME]["sinais_vistos"] == ["rastro", "som"]
    pres = out["world_sim"]["fauna"]["presencas"][0]
    assert pres["status"] == "encontrada"


def test_bonus_deteccao_com_2_sinais():
    one = sim_with(presence(shown=("rastro",)))
    two = sim_with(presence(shown=("rastro", "som")))
    assert fauna.detection_bonus(one, "pidarame0001") == 0
    assert fauna.detection_bonus(two, "pidarame0001") == fauna.const("PRESENCA_BONUS_DETECCAO")
    assert fauna.detection_bonus(two, "") == 0


def test_rastro_sorteado_vira_sinal(on):
    e = fauna.entry(ARAME)
    note, upd = fauna.track_signal(state_at(sim={}), e, LAMA, 5)
    assert note == e["sinais"]["rastro"]
    pres = upd["world_sim"]["fauna"]["presencas"][0]
    assert pres["origem"] == "rastro" and pres["sinais_mostrados"] == ["rastro"]
    # reforca a presenca que ja existe (sem duplicar)
    st = state_at(sim=sim_with(presence(locais=(FERRO,))))
    note, upd = fauna.track_signal(st, e, LAMA, 5)
    rows = upd["world_sim"]["fauna"]["presencas"]
    assert len(rows) == 1 and LAMA in rows[0]["locais"] and "rastro" in rows[0]["sinais_mostrados"]
    # resolve_track: a frase nao nomeia; o registro de rumor continua
    bk, text, _t = wu.resolve_track(
        {}, gamedata.get_location(LAMA), 3, 7, rng=random.Random(1),
        describe=lambda ent: "VESTIGIO",
    )  # fmt: skip
    assert "VESTIGIO" in text and "Rastros frescos de" not in text and bk


def test_bloco_ate_60_tokens(on):
    for cid, e in fauna.load().items():
        for kind in fauna.SIGN_TYPES:
            text = (e["sinais"] or {}).get(kind)
            if text:
                assert len(fauna.render_block(text)) / 4 <= 60, (cid, kind)


def test_storyteller_prompt_tem_bloco_e_off_nao(on, monkeypatch):
    from agents import storyteller

    captured: list = []

    class _Runner:
        def invoke(self, msgs):
            captured.extend(msgs)
            return storyteller.StoryUpdate(narrative="A viela está quieta.")

    class _LLM:
        def with_structured_output(self, model):
            return _Runner()

        def invoke(self, msgs):
            captured.extend(msgs)
            from langchain_core.messages import AIMessage

            return AIMessage(content="A viela está quieta.")

    monkeypatch.setattr(storyteller, "get_llm", lambda *a, **k: _LLM())
    out = storyteller.storyteller_node(state_at(sim=sim_with(presence())))
    prompt = "\n".join(str(m.content) for m in captured)
    assert "<SINAIS_NA_CENA>" in prompt
    assert out["world_sim"]["fauna"]["presencas"][0]["sinais_mostrados"]
    captured.clear()
    monkeypatch.setenv("RPG_FAUNA", "off")
    storyteller.storyteller_node(state_at(sim=sim_with(presence())))
    assert "<SINAIS_NA_CENA>" not in "\n".join(str(m.content) for m in captured)
