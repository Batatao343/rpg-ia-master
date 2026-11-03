"""SPEC-371 R8-R12: saber no ator, presságio com contra-jogo e preparação da cena."""

from __future__ import annotations

import copy
import random

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.bestiary import template_by_id
from services import bestiary_knowledge as bkn
from services import conflict_orchestrator as orch
from services import encounter_preparation as prep
from services import enemy_decks as edk
from services import enemy_intent as ei
from services import fauna_saber as fs

CID = "mon_arame_vivo"
IID = f"{CID}_1"


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    monkeypatch.setenv("RPG_FAUNA_SABER", "on")
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")


def _enemy(n: int = 1) -> dict:
    t = dict(template_by_id(CID, encounter_level=2))
    t["id"] = f"{CID}_{n}"
    t["name"] = "Arame Vivo"
    return orch.ensure_combat_sheet(t)


def _sig(enemy: dict) -> str:
    return edk.assinatura_of(enemy)["carta"]


def _bk(**rec) -> dict:
    base = {"seen": 2, "fought": 2, "defeated": 1}
    base.update(rec)
    return {CID: base}


# --------------------------------------------------------------------- R8
def test_stamp_actor_campos():
    e = _enemy()
    fs.stamp_actor(
        e, _bk(assinaturas_sobrevividas=1, saber_revelado={"motivo": "sobreviveu", "turn": 3})
    )
    assert e["saber_jogador"]["contra_jogo"].startswith("Manter distância")
    assert e["saber_jogador"]["assinaturas"] == [_sig(e)]
    e2 = _enemy()
    fs.stamp_actor(e2, _bk(assinaturas_sobrevividas=1))  # sobreviveu mas sem revelacao gravada
    assert e2["saber_jogador"] == {"contra_jogo": None, "assinaturas": [_sig(e2)]}
    e3 = _enemy()
    fs.stamp_actor(e3, {})
    assert e3["saber_jogador"] == {"contra_jogo": None, "assinaturas": []}


def test_stamp_actor_off_nao_escreve(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    e = _enemy()
    fs.stamp_actor(e, _bk(assinaturas_sobrevividas=1))
    assert "saber_jogador" not in e


def test_stamp_fora_do_painel_publico():
    e = _enemy()
    fs.stamp_actor(
        e, _bk(assinaturas_sobrevividas=1, saber_revelado={"motivo": "sobreviveu", "turn": 3})
    )
    assert "saber_jogador" not in bkn._PUBLIC_FIELDS
    panel = bkn.public_panel(e)
    assert "saber_jogador" not in panel
    assert "Manter distância" not in repr(panel)


# --------------------------------------------------------------------- R9
def test_knowledge_level_assinatura_sobrevivida_estudada():
    e = _enemy()
    e.pop("revealed_cards", None)
    base = ei.knowledge_level(e, _sig(e))
    fs.stamp_actor(e, _bk(assinaturas_sobrevividas=1))
    assert ei.knowledge_level(e, _sig(e)) == "estudada"
    assert ei.knowledge_level(e, "outra_carta") != "estudada"
    assert base != "estudada"


def test_knowledge_level_contra_jogo_conhecida():
    e = _enemy()
    e.pop("revealed_cards", None)
    e["revealed_resistances"] = []
    e["known"] = False
    fs.stamp_actor(e, _bk(saber_revelado={"motivo": "estudada", "turn": 3}))
    assert ei.knowledge_level(e, "qualquer") == "conhecida"


def test_knowledge_level_off_inalterado(monkeypatch):
    e = _enemy()
    e.pop("revealed_cards", None)
    sem = ei.knowledge_level(e, _sig(e))
    fs.stamp_actor(
        e, _bk(assinaturas_sobrevividas=1, saber_revelado={"motivo": "sobreviveu", "turn": 3})
    )
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    assert ei.knowledge_level(e, _sig(e)) == sem


def test_knowledge_level_sem_campo_no_save_antigo():
    e = _enemy()
    e.pop("saber_jogador", None)
    assert ei.knowledge_level(e, _sig(e)) in {"desconhecida", "conhecida", "estudada"}


# --------------------------------------------------------------------- R10
def _frozen_with_prenuncio(enemy: dict):
    """(frozen, actors, rnd_exec) em que a assinatura cai na rodada SEGUINTE a `rnd_exec`."""
    for rnd in range(1, 10):
        if edk.prenuncio(enemy, rnd):
            actors = {IID: enemy}
            intent = {
                "actor_id": IID,
                "idx": 0,
                "tipo": "ataque",
                "alvo_id": "player",
                "carta_id": _sig(enemy),
                "declaration": {},
            }
            return {IID: [intent, dict(intent, idx=1)]}, actors, rnd
    pytest.fail("sem prenuncio")


def test_contra_jogo_so_na_linha_do_prenuncio():
    e = _enemy()
    fs.stamp_actor(e, _bk(saber_revelado={"motivo": "estudada", "turn": 3}))
    frozen, actors, rnd = _frozen_with_prenuncio(e)
    rows = ei.public_round(frozen, actors, rnd)
    assert rows[0]["prenuncio"] and rows[0]["contra_jogo"].startswith("Manter distância")
    assert "contra_jogo" not in rows[1] and "prenuncio" not in rows[1]


def test_sem_revelacao_sem_linha():
    e = _enemy()
    fs.stamp_actor(e, _bk())
    frozen, actors, rnd = _frozen_with_prenuncio(e)
    rows = ei.public_round(frozen, actors, rnd)
    assert rows[0]["prenuncio"] and all("contra_jogo" not in r for r in rows)
    # revelado, mas rodada sem prenuncio: nenhuma linha recebe
    e2 = _enemy()
    fs.stamp_actor(e2, _bk(saber_revelado={"motivo": "estudada", "turn": 3}))
    f2, a2, _ = _frozen_with_prenuncio(e2)
    rows = ei.public_round(f2, a2, 1) if not edk.prenuncio(e2, 1) else []
    assert all("contra_jogo" not in r for r in rows)


def test_public_round_off_byte_identico(monkeypatch):
    e = _enemy()
    frozen, actors, rnd = _frozen_with_prenuncio(e)
    sem_saber = ei.public_round(frozen, copy.deepcopy(actors), rnd)
    fs.stamp_actor(
        e, _bk(assinaturas_sobrevividas=1, saber_revelado={"motivo": "sobreviveu", "turn": 3})
    )
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    assert ei.public_round(frozen, actors, rnd) == sem_saber


# ------------------------------------------------------------------- R11/R12
def test_prep_line_sem_nome_e_curta():
    state = {
        "bestiary_knowledge": _bk(sinais_vistos=["rastro", "som"]),
        "combat_encounter_hint": {"aproximacao": "Algo arrasta ferro pela viela. " * 20},
    }
    line = fs.prep_line(state, [_enemy()])
    assert line.startswith("O herói leu antes: rastro, som.")
    assert len(line) <= 200
    assert "Arame" not in line and CID not in line
    assert fs.prep_line({}, [_enemy()]) == ""


def test_prep_line_off_vazia(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    assert fs.prep_line({"bestiary_knowledge": _bk(sinais_vistos=["rastro"])}, [_enemy()]) == ""


def test_prep_prompt_off_byte_identico():
    ctx = {"location": "Viela", "enemies": [_enemy()], "narrative": "noite", "allies": []}
    base = prep._prep_prompt(ctx)
    assert "Saber do herói" not in base
    com = prep._prep_prompt({**ctx, "saber_linha": "O herói leu antes: som."})
    assert "Saber do herói: O herói leu antes: som." in com
    assert com.replace("Saber do herói: O herói leu antes: som.\n", "") == base


def _drive(monkeypatch, saber: str, max_rounds: int = 6) -> dict:
    import agents.combat as combat
    import mock_llm
    from playtest.runner import _build_initial_state

    monkeypatch.setenv("RPG_FAUNA_SABER", saber)
    calls = [0]
    orig, orig_s = mock_llm.MockLLM.invoke, mock_llm._StructuredMock.invoke

    def _inv(self, messages):
        calls[0] += 1
        return orig(self, messages)

    def _inv_s(self, messages):
        calls[0] += 1
        return orig_s(self, messages)

    monkeypatch.setattr(mock_llm.MockLLM, "invoke", _inv)
    monkeypatch.setattr(mock_llm._StructuredMock, "invoke", _inv_s)
    random.seed(3)
    state = _build_initial_state("combate", 3, start_level=1)
    enemies = []
    for n in (1, 2):
        t = dict(template_by_id(CID, encounter_level=2))
        t["id"], t["name"] = f"{CID}_{n}", f"Arame Vivo {n}"
        enemies.append(orch.ensure_combat_sheet(t))
    state["enemies"] = enemies
    state["combat_target"] = "Arame Vivo"
    state["messages"] = list(state.get("messages") or []) + [
        AIMessage(content="Algo surge."),
        SystemMessage(content="SYSTEM: COMBAT START. TARGET_HINT: Arame Vivo"),
    ]
    rounds = 0
    for _ in range(max_rounds):
        out = combat.combat_node(state)
        state.update(out)
        rounds += 1
        if not (state.get("combat") or {}).get("active"):
            break
        state["messages"] = list(state["messages"]) + [HumanMessage(content="ataco o arame vivo")]
    return {"calls": calls[0], "rounds": rounds, "state": state}


def test_invoke_count_on_igual_off(monkeypatch):
    on = _drive(monkeypatch, "on")
    off = _drive(monkeypatch, "off")
    assert on["rounds"] == off["rounds"]
    assert on["calls"] == off["calls"]


def test_combate_real_grava_o_saber_e_o_fim(monkeypatch):
    seen = {"absorb": 0, "finish": 0}
    orig_a, orig_f = fs.absorb, fs.finish_combat

    def _a(*a, **k):
        seen["absorb"] += 1
        return orig_a(*a, **k)

    def _f(*a, **k):
        seen["finish"] += 1
        return orig_f(*a, **k)

    monkeypatch.setattr(fs, "absorb", _a)
    monkeypatch.setattr(fs, "finish_combat", _f)
    res = _drive(monkeypatch, "on", max_rounds=40)
    assert seen["absorb"] >= 1 and seen["finish"] == 1
    bk = res["state"]["bestiary_knowledge"][CID]
    assert bk["fought"] == 1
    assert "saber_obs" not in ((res["state"].get("combat") or {}).get("scene") or {})


def test_prep_sem_invoke_novo(monkeypatch):
    """`_prepare_scene` com saber `on` nao chama o LLM mais vezes que com `off`."""
    import agents.combat as combat
    from playtest.runner import _build_initial_state

    def _count(mode: str) -> int:
        monkeypatch.setenv("RPG_FAUNA_SABER", mode)
        n = [0]
        real = prep.prepare_encounter

        def _spy(ctx, llm):
            n[0] += 1
            return real(ctx, llm)

        monkeypatch.setattr(prep, "prepare_encounter", _spy)
        state = _build_initial_state("combate", 3, start_level=3)
        state["bestiary_knowledge"] = _bk(sinais_vistos=["rastro"])
        e = _enemy()
        e["categoria"] = "elite"  # forca a cena preparada pela LLM (R10 da 232)
        combat._prepare_scene(state, [e], state["player"], [])
        monkeypatch.setattr(prep, "prepare_encounter", real)
        return n[0]

    assert _count("on") == _count("off") == 1


def test_prompt_de_preparacao_leva_a_linha_quando_on(monkeypatch):
    import agents.combat as combat
    from playtest.runner import _build_initial_state

    prompts: list[str] = []
    real = prep._prep_prompt

    def _spy(ctx):
        out = real(ctx)
        prompts.append(out)
        return out

    monkeypatch.setattr(prep, "_prep_prompt", _spy)
    state = _build_initial_state("combate", 3, start_level=3)
    state["bestiary_knowledge"] = _bk(sinais_vistos=["rastro", "som"])
    e = _enemy()
    e["categoria"] = "elite"
    combat._prepare_scene(state, [e], state["player"], [])
    assert any("Saber do herói: O herói leu antes: rastro, som." in p for p in prompts), prompts
    assert not any(CID in p.split("Saber do herói")[-1].split("\n")[0] for p in prompts)
    prompts.clear()
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    combat._prepare_scene(state, [e], state["player"], [])
    assert not any("Saber do herói" in p for p in prompts)
