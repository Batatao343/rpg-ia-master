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


def _cfg(monkeypatch, **over):
    base = dict(fauna._config())
    monkeypatch.setattr(fauna, "_config", lambda: {**base, **over})


def test_um_sinal_por_cena_na_ordem(on):
    st = state_at(sim=sim_with(presence()))
    seen = []
    for turn in range(200):
        st["world"]["turn_count"] = turn
        block, upd = fauna.scene_block(st)
        if not block:
            continue
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
        world,
        [],
        {},
        20 + seed,
        bestiary_knowledge={},
        projection={},
        player_level=3,
        world_sim=sim,
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


def test_presenca_nova_anuncia_so_com_a_constante(on, monkeypatch):
    """§9: presenca ainda sem sinal anuncia antes so com `ANUNCIA_PRESENCA_NOVA` (off no
    final: o P2-6 e o P1-1 ja convertem bastante)."""
    _cfg(monkeypatch, ANUNCIA_PRESENCA_NOVA=False)
    enc = _enc(sim_with(presence()))
    assert not enc.get("fauna_convert") and enc["presence_id"] == "pidarame0001"
    _cfg(monkeypatch, ANUNCIA_PRESENCA_NOVA=True)
    enc = _enc(sim_with(presence()))
    assert enc["fauna_convert"] and enc["presence_id"] == "pidarame0001"


def test_cedo_sem_anuncio_com_presenca_de_outra(on, monkeypatch):
    """P2-6 (Sol): ha presenca no local, mas o sorteio cai noutra criatura `cedo` (a da
    presenca nao cabe no porte): o encontro vira o 1o sinal da sorteada."""
    bagre = "enemy_polvo_esgoto"  # Elite: nao cabe no porte <= 2
    sim = sim_with(presence(cid=bagre, pid="pidbagre0001", shown=("resto",)))
    hits = []
    for seed in range(40):
        world_extra = {"danger_overrides": {LAMA: 4}}
        random.seed(seed)
        enc = wu.check_encounter(
            {"current_location_id": LAMA, "current_location": LAMA,
             "world_clock": {"day": 5, "period": "Noite"}, **world_extra},
            [], {}, 20 + seed, bestiary_knowledge={}, projection={}, player_level=1,
            world_sim=sim,
        )  # fmt: skip
        fe = fauna.entry(enc["enemy_id"])
        if fe and enc["enemy_id"] != bagre and fe["sinais"]["antecedencia"] == "cedo":
            hits.append(enc)
    assert hits and all(e.get("fauna_convert") and not e.get("presence_id") for e in hits)


def test_presenca_vence_a_pressao_de_caca(on):
    """R15: a criatura da presenca e a do encontro sempre que cabe no porte, mesmo cacada."""
    bk = {ARAME: {"defeated": 9, "last_update_turn": 20}}
    for seed in range(10):
        random.seed(seed)
        enc = wu.check_encounter(
            {"current_location_id": LAMA, "current_location": LAMA,
             "world_clock": {"day": 5, "period": "Noite"}, "danger_overrides": {LAMA: 4}},
            [], {}, 20 + seed, bestiary_knowledge=bk, projection={}, player_level=3,
            world_sim=sim_with(presence(shown=("rastro",))),
        )  # fmt: skip
        assert enc["enemy_id"] == ARAME


def test_shadow_so_registra(monkeypatch):
    """P2-3 (Sol): `RPG_FAUNA=shadow` + `RPG_FAUNA_SINAIS=on` nao muda o jogo nem grava."""
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    out = {}
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_FAUNA", mode)
        out[mode] = [_enc(sim_with(presence(shown=("rastro",))), seed=s) for s in range(6)]
    keys = {"presence_id", "fauna_convert", "aproximacao"}
    # o sorteio legado ponderado nao e semeado: compara-se a forma, nao a criatura
    assert [sorted(e) for e in out["off"]] == [sorted(e) for e in out["shadow"]]
    assert not any(keys & set(e) for e in out["shadow"])
    assert {e["flavor"] for e in out["shadow"]} == {e["flavor"] for e in out["off"]}
    assert fauna.sinais_mode() == "off"
    assert fauna.scene_block(state_at(sim=sim_with(presence()))) == ("", {})
    assert fauna.record_kill({}, ARAME, LAMA, 3) == {}


def test_semente_inclui_game_id(on):
    """P2-2 (Sol): mesma seed de turno/local/relogio, campanhas diferentes -> sorteios
    independentes; mesma campanha -> o mesmo."""
    loc = gamedata.get_location(FERRO)
    world = {"current_location_id": FERRO, "world_clock": {"day": 3, "period": "Tarde"}}

    def picks(gid):
        return [
            wu.pick_encounter_enemy(loc, 3, t, bestiary_knowledge={}, projection={},
                                    world=world, world_sim={}, game_id=gid)["id"]
            for t in range(30)
        ]  # fmt: skip

    assert picks("a") == picks("a")
    assert picks("a") != picks("b")


def test_densidade_segundo_sinal_em_fracao_das_cenas(on, monkeypatch):
    """P2-1 (Sol): o 1o sinal sai sempre; os seguintes so em ~`P_SINAL_CENA` das cenas."""
    _cfg(monkeypatch, P_SINAL_CENA=0.35)
    shown = 0
    for turn in range(400):
        st = state_at(sim=sim_with(presence(shown=("rastro",), pid=f"p{turn}")))
        st["world"]["turn_count"] = turn
        shown += bool(fauna.scene_block(st)[0])
    assert 0.2 < shown / 400 < 0.5
    st = state_at(sim=sim_with(presence()))
    assert all(fauna.scene_block({**st, "world": {**st["world"], "turn_count": t}})[0]
               for t in range(20))  # fmt: skip


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
