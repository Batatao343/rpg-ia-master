"""SPEC-363 R37/R38: cenários que o smoke real não sorteia, provados por seed/fixture (MockLLM, offline)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

import agents.combat as combat
from llm_setup import FallbackLLM
from services import card_effects as fx
from services import cards, round_log
from services import enemy_decks as edk
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state
from tests.test_spec346_board_no_llm import _after_open, _attack_decl, _no_llm, _open
from tests.test_spec362_run_round import _round

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _board_on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(21)


# --- R37: nenhuma chamada de LLM nas rodadas de meio de luta --------------------------------------
def test_mid_fight_rounds_make_zero_llm_calls(monkeypatch):
    state, res = _open(monkeypatch)
    cur = _after_open(state, res)
    calls: list[int] = []

    def counting(*a, **k):
        calls.append(1)
        raise RuntimeError("sem LLM no meio da luta")

    _no_llm(monkeypatch)
    monkeypatch.setattr(combat, "get_llm", counting)
    mid_rounds = 0
    for step in range(5):
        before = len(calls)
        cur["messages"] = [*cur["messages"], HumanMessage(content="Jogo")]
        cur["combat_declaration"] = (
            {"actor_id": "player", "acao": {"kind": "flee"}} if step == 3 else _attack_decl(cur)
        )
        out = combat._combat_node(cur)
        still_active = bool(out["combat"].get("active"))
        if still_active:
            mid_rounds += 1
            assert len(calls) == before, f"rodada {step} chamou LLM"
        cur = {**cur, **{k: v for k, v in out.items() if k != "messages"}}
        cur["messages"] = [*cur["messages"], *out["messages"]]
        if not still_active:
            break
    assert mid_rounds >= 1


# --- (b) iniciativa contra emboscada ---------------------------------------------------------------
def test_b_initiative_card_negates_ambush_in_opening(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    state["world"]["encounter_surprise"] = "enemy"
    ambush = combat._combat_node(state)
    assert ambush["combat"]["initiator"] == "enemy"
    state2 = _start_state(hint="Goblin")
    state2["world"]["encounter_surprise"] = "enemy"
    prepared = list(state2["player"].get("prepared_cards") or [])
    state2["player"]["prepared_cards"] = [*prepared, "dev_zel_vigilia"]
    calmer = combat._combat_node(state2)
    assert calmer["combat"]["initiator"] != "enemy"


# --- (c) fuga concluída ---------------------------------------------------------------------------
def test_c_flee_completed_ends_with_fled_and_keeps_last_round(monkeypatch):
    for seed in range(40):
        state, res = _open(monkeypatch)
        cur = _after_open(state, res)
        random.seed(seed)
        for _press in range(6):
            cur["messages"] = [*cur["messages"], HumanMessage(content="Fugir")]
            cur["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "flee"}}
            out = combat._combat_node(cur)
            if not out["combat"]["active"]:
                break
            cur = {**cur, **{k: v for k, v in out.items() if k != "messages"}}
        if out["combat"].get("outcome") == "fled":
            meta = out["combat"]
            assert any("escapou" in line for line in meta.get("last_mech_log") or []), meta.get("last_mech_log")
            assert meta.get("last_round_board") is not None  # registro da rodada final preservado
            assert out["messages"][0].content.strip()
            return
    pytest.fail("nenhuma semente concluiu a fuga")


# --- (d)(e)(g) cartas alteradas / Leitura de Pressão / Armadura Comprometida -----------------------
@pytest.mark.parametrize(("cid", "numero"), [("arc1_imp_truque", "3"), ("arc1_cal_pulso_medido", "4")])
def test_d_altered_arcanist_text_has_new_numbers(cid, numero):
    assert numero in fx.render_card_text(cards.get_card(cid))


def test_e_leitura_de_pressao_reveals_intent_in_registry():
    out, _piles = _round("arc1_cal_leitura", 3, "enemy")
    assert any("intencao à mostra" in str(line) or "intenção à mostra" in str(line) for line in out["logs"]), out["logs"]
    assert out.get("revelacoes")


def test_g_armadura_comprometida_is_readable():
    label = fx.condition_label("armadura_comprometida")
    assert label and "_" not in label and label[0].isupper()


# --- (h) Renegado de corpo a corpo -----------------------------------------------------------------
def test_h_renegado_never_gets_descarga_arcana():
    bestiary = json.loads((ROOT / "data" / "bestiary.json").read_text(encoding="utf-8"))
    renegado = bestiary["enemy_renegado_ermo"]
    assert edk.family_key(renegado) != "conjurador"
    for seed in range(20):
        assert "bst_descarga_arcana" not in edk.build_enemy_deck(renegado, seed)


# --- (i) vitória com Reação ------------------------------------------------------------------------
def test_i_victory_by_reaction_facts():
    last = {"final_blows": [{"target_id": "e1", "kind": "reacao", "by_actor_id": "player"}]}
    names = {"player": "Você", "e1": "Goblin"}
    assert round_log.final_blow_sentence(last, names) == "Sua reação termina o serviço: Goblin tomba."
    facts = round_log.outcome_facts(
        "victory", {"mortos": ["Goblin"]}, {"name": "H", "vitalidade": 5, "max_vitalidade": 5},
        [{"id": "e1", "name": "Goblin"}], last, names={"e1": "Goblin"},
    )
    assert any("Sua reação termina o serviço" in f for f in facts) or any("reação" in f for f in facts)


# --- (k) modo off ------------------------------------------------------------------------------------
def test_k_deck_off_keeps_the_legacy_flow(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    state, res = _open(monkeypatch)
    assert not (res["combat"] or {}).get("pilhas")
    assert not any("?" in str(line) for line in (res["combat"] or {}).get("last_mech_log") or [])


# --- (l) router esgotado -----------------------------------------------------------------------------
def test_l_exhausted_llm_still_opens_the_board(monkeypatch):
    state = _start_state(hint="Goblin")
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: FallbackLLM("todos os candidatos falharam"))
    res = combat._combat_node(state)
    assert res["messages"][0].content.strip()
    assert (res["combat"] or {}).get("active")
    assert isinstance((res["combat"] or {}).get("pilhas"), dict)


# --- (m) quest de lore `justa` --------------------------------------------------------------------
def test_m_lore_quest_grants_the_promised_card_once(monkeypatch):
    from services.event_processor import process_pending_events
    from tests.test_card_quest_rewards import _quest, _state

    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    q = _quest("qjusta", label="justa")
    out = process_pending_events(_state(q))
    got = [c for c in out["player"]["known_cards"] if c.startswith("neu1_")]
    assert len(got) == 1
    again = process_pending_events(_state(_quest("qjusta", label="justa")))
    assert again["player"]["known_cards"] == out["player"]["known_cards"]


# --- (j) "Vasculho o corpo" depois da vitória: uma vez só, sem id no texto ------------------------
def test_j_corpse_search_once_and_without_ids(monkeypatch):
    from agents import loot
    from services.economy import ARTIFACTS_DB
    from tests.test_spec346_loot_once import CLAIMED, _state

    out = loot.loot_node(_state("Vasculho o corpo da criatura", combat=CLAIMED))
    text = out["messages"][0].content
    assert text == loot.CORPSE_ALREADY_LOOTED and "player" not in out
    assert not any(item_id in text for item_id in ARTIFACTS_DB)


# --- (a) objeto de cena: a Carta do objeto vai à mão, é jogada e resolve ----------------------------
def test_a_scene_object_card_is_played_and_resolves(monkeypatch):
    from services import conflict_scene as cs
    from services import scene_cards as sc

    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    state, res = _open(monkeypatch)
    cur = _after_open(state, res)
    scene = cur["combat"]["scene"]
    cs.add_object(
        scene,
        {
            "id": "barril",
            "name": "Barril",
            "zone_id": "z0",
            "uses_remaining": 1,
            "interactions": [
                {"label": "derrubar", "effect": {"kind": "damage", "params": {"amount": 3, "target": "e"}}}
            ],
        },
        from_trigger=True,
    )
    ids = sc.sync_hand(scene, cur["combat"]["pilhas"], "player")
    assert ids and ids[0] in cur["combat"]["pilhas"]["mao"]
    card_id = ids[0]
    eid = next(e["id"] for e in cur["enemies"] if not e.get("dead"))
    cur["messages"] = [*cur["messages"], HumanMessage(content="Derrubo o barril")]
    cur["combat_declaration"] = {
        "actor_id": "player",
        "acao": {"kind": "card", "card_id": card_id, "target_id": eid},
    }
    out = combat._combat_node(cur)
    text = out["messages"][0].content
    assert "não pôde ser jogada" not in text and "nao pode ser jogada" not in text.lower()
    assert card_id not in out["combat"]["pilhas"]["mao"] or not out["combat"].get("active")


# --- (f) Voto Sussurrado com presságio congelado mirando o aliado -------------------------------
@pytest.mark.parametrize("ordem", ["hero_first", "enemy_first"])
def test_f_voto_sussurrado_on_ally_targeted_omen(ordem, monkeypatch):
    from services import conflict_orchestrator as orch
    from services import enemy_intent as ei
    from tests import test_spec339_duracao_condicoes as t339

    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    monkeypatch.setattr(ei, "_fork_rng", lambda rng: t339._Rng0(0))
    actors, scene, sides = t339._cena_devoto()
    frozen = ei.forecast_round(scene, actors, sides, t339._Rng0(1))
    assert frozen["e"][0]["alvo_id"] == "ally"  # o presságio congelado mira o aliado
    logs: list[str] = []
    for rnd in (1, 2):
        decl = t339._voto() if rnd == 1 else t339.ct.TurnDeclaration(actor_id="player")
        out = orch.run_round(
            scene, actors, sides, {"player": actors["player"]},
            declarations={"player": decl}, initiator=t339.ORDENS[ordem],
            rng=t339._Rng0(rnd), pressagios=frozen,
        )
        logs += out["logs"]
        frozen = ei.forecast_round(scene, actors, sides, t339._Rng0(rnd))  # presságio da rodada seguinte
    text = "\n".join(logs)
    # 355 §6.1: a Provocação diz o que fez — muda de alvo ou é resistida; nunca silêncio
    if ordem == "hero_first":  # o Voto cai antes do ataque congelado: a linha diz que ele muda de alvo
        assert "provocado por" in text and "muda de alvo" in text, text
    else:  # o inimigo já agiu; na rodada seguinte o presságio recalculado mira o herói
        assert "e → player" in text, text
