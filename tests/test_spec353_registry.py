"""SPEC-353 etapa 2/3: ordem unica, auto-dano, contrato do round_board, autoria do resumo."""

from __future__ import annotations

import random
import re

import pytest

from services import combat_preview as preview
from services import conflict_orchestrator as orch
from services import conflict_summary as summ
from services import conflict_turn as ct
from services import round_log
from tests.test_fix_vitalidade_terminal import _actor, _scene

SIDES = {"hero": ["player"], "ally": [], "enemy": ["boss"]}
ID_RE = re.compile(
    r"\b(cena|bas|dev|san|cor|arc|vig|bst|inf|mon|npc|enemy|fallback|sus)_[a-z0-9_]+\b"
)


def _sangromante_round(seed: int, card_id: str = "san_corte_troca", initiator="heroes"):
    hero = _actor("player", corpo=5, is_player=True)
    hero["class_name"] = "Sangromante"
    hero["prepared_cards"] = [card_id]
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["dano_base_arma"] = 3
    decl = ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="card", card_id=card_id, target_id="boss")
    )
    vit_before = hero["vitalidade"]
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={"player": decl},
        initiator=initiator,
        state={"player": hero},
        rng=random.Random(seed),
    )
    return hero, boss, out, vit_before


@pytest.mark.parametrize("card_id", ["san_corte_troca", "bas_san_corte_raso"])
@pytest.mark.parametrize("seed", range(10))
def test_self_harm_line_and_oracle(seed, card_id):
    hero, boss, out, vit_before = _sangromante_round(seed, card_id)
    harm = [m for m in out["class_mechanics"] if m["kind"] == "self_harm"]
    assert harm and harm[0]["actor_id"] == "player" and harm[0]["card_id"] == card_id
    lines = preview.mech_log(out["attacks"], [hero, boss], out["ticks"], out=out)
    assert any("· custo ·" in ln and ln.startswith("Você · ") for ln in lines)
    reg = round_log.round_registry(out, {"player": hero, "boss": boss})
    assert any(ln.startswith("Você paga ") for ln in reg)
    board = preview.round_board(out, [hero, boss], {"boss"})
    assert any(e["tipo"] == "custo" and e["dano"] == harm[0]["amount"] for e in board)
    assert not any(ID_RE.search(ln) for ln in [*lines, *reg])
    # R14: o custo nunca some da conta de Vitalidade do heroi
    paid = harm[0]["amount"]
    drop = vit_before - hero["vitalidade"]
    assert drop >= min(paid, vit_before)


def test_one_order_in_three_surfaces():
    """R12: inimigo age primeiro (emboscada) -> aparece primeiro nas 3 superficies."""
    hero = _actor("player", corpo=5, is_player=True)
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["dano_base_arma"] = 2
    decl = ct.TurnDeclaration(
        actor_id="player",
        acao=ct.TurnStep(kind="attack", target_id="boss", params={"dano_base": 3}),
    )
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={"player": decl},
        initiator="enemy",
        rng=random.Random(5),
    )
    assert out["attacks"][0]["actor_id"] == "boss"
    reg = round_log.round_registry(out, {"player": hero, "boss": boss})
    lines = preview.mech_log(out["attacks"], [hero, boss], out["ticks"], out=out)
    board = preview.round_board(out, [hero, boss], {"boss"})
    assert reg[0].startswith("Boss ataca")
    assert lines[0].startswith("Boss")
    assert board[0]["ator_id"] == "boss"


def test_round_board_tipo_and_dot_source():
    out = {
        "attacks": [],
        "ticks": [{"actor_id": "boss", "condition": "Sangramento", "dano_final": 1}],
        "turn_spans": [{"actor_id": "boss", "attacks": [0, 0], "cards": [0, 0]}],
        "deaths": ["boss"],
        "sem_vitalidade": [{"actor_id": "boss"}],
    }
    actors = [{"id": "boss", "name": "Criatura"}, {"id": "npc_ketil", "name": "Ketil"}]
    fontes = {"boss": {"Sangramento": "npc_ketil"}}
    board = preview.round_board(out, actors, {"boss"}, fontes=fontes)
    tick = board[0]
    assert tick["tipo"] == "dano_continuo" and tick["ator_id"] == "npc_ketil"
    assert tick["ator_nome"] == "Ketil" and tick["alvo_nome"] == "Criatura"
    assert {e["tipo"] for e in board} == {"dano_continuo", "queda"}
    unknown = preview.round_board(out, actors, {"boss"})[0]
    assert unknown["ator_id"] is None and unknown["lado"] == "efeito"
    assert unknown["ator_nome"] == "Sangramento"


def test_flee_roll_in_mech_log():
    out = {"fuga": {"total": 7, "dificuldade": 11, "sucesso": False}}
    assert preview.mech_log([], [], out=out) == ["Fuga · total 7 vs 11 · falhou"]


def test_zero_vitality_line_once():
    actor = {"id": "boss", "name": "Anão-Eco", "categoria": "elite", "virtudes": {"corpo": 3}}
    out = {"attacks": [], "sem_vitalidade": [{"actor_id": "boss"}]}
    reg = round_log.round_registry(out, {"boss": actor})
    assert len(reg) == 1 and reg[0].startswith("Anão-Eco está sem Vitalidade — cada golpe")


def test_final_blow_dot_recorded():
    boss = _actor("boss", corpo=0, categoria="lacaio", vitalidade=1)
    boss["active_conditions"] = [
        {"name": "Sangramento", "dot": 5, "duration": 3, "damage_type": "cortante"}
    ]
    hero = _actor("player", corpo=5, is_player=True)
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={},
        initiator="enemy",
        rng=random.Random(2),
    )
    blows = out.get("final_blows") or []
    assert blows and blows[0]["kind"] == "dano_continuo" and blows[0]["condition"] == "Sangramento"


# --- autoria do resumo (R8/R11) ---
def _auth(**kw):
    base = {"hero_cards": {}, "final_by_hero": False, "final_on_enemy": False}
    base.update(kw)
    return base


def test_attribution_rejects_smoke_texts():
    d5 = "O Sussurro Faminto, num estalo, encontra teu torso e te lança ao chão."
    assert "V1" in summ.validate_attribution(d5, _auth(hero_cards={"Sussurro Faminto": "hit"}))
    k4 = "Sua espada desce duas vezes, e a criatura desmorona na lama."
    assert "V3" in summ.validate_attribution(k4, _auth(final_on_enemy=True))
    r6 = "O Corte de Troca não encontra alvo, e o silêncio cai."
    assert "V2" in summ.validate_attribution(r6, _auth(hero_cards={"Corte de Troca": "hit"}))


def test_attribution_accepts_correct_texts():
    ok1 = "O Sussurro Faminto rasga a sombra diante de você, e o Anão-Eco cambaleia."
    assert not summ.validate_attribution(ok1, _auth(hero_cards={"Sussurro Faminto": "hit"}))
    ok2 = "Sua espada corta o ar sem achar nada; é o Sangramento que derruba a criatura."
    assert not summ.validate_attribution(ok2, _auth(final_on_enemy=True))
    ok3 = "O Corte de Troca encontra o alvo em cheio e a luta acaba."
    assert not summ.validate_attribution(ok3, _auth(hero_cards={"Corte de Troca": "hit"}))


def test_facts_have_actor_target_result_and_no_digits():
    hero = {"name": "Haldor", "vitalidade": 5, "max_vitalidade": 10}
    enemy = {"id": "c1", "name": "Criatura", "status": "ativo"}
    last_out = {
        "attacks": [{"actor_id": "player", "target_id": "c1", "acerto": False, "resultado": "erro"}],
        "ticks": [{"actor_id": "c1", "condition": "Sangramento", "dano_final": 3}],
        "final_blows": [
            {"target_id": "c1", "kind": "dano_continuo", "by_actor_id": None, "condition": "Sangramento"}
        ],
    }
    facts = round_log.outcome_facts("victory", {}, hero, [enemy], last_out)
    text = "\n".join(facts)
    assert "Você atacou em Criatura: errou." in text
    assert "Sangramento corroeu Criatura." in text
    assert "Golpe final: o Sangramento (dano contínuo) em Criatura." in text
    assert "Seu último golpe errou." in text
    assert not re.search(r"\d", text)


def test_fallback_names_final_blow():
    blow = {"target_id": "c1", "kind": "dano_continuo", "condition": "Sangramento"}
    text = round_log.deterministic_outcome_text(
        "victory",
        {"mortos": ["Criatura"]},
        {"name": "Haldor"},
        last_out={"final_blows": [blow]},
        names={"c1": "Criatura"},
    )
    assert "O Sangramento termina o serviço: Criatura tomba." in text


def test_final_blow_attack_recorded_with_card():
    hero = _actor("player", corpo=5, is_player=True)
    foe = _actor("boss", corpo=0, categoria="lacaio", vitalidade=0)
    decl = ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="attack", target_id="boss", params={"dano_base": 9})
    )
    for seed in range(40):
        foe2 = dict(foe, ferimentos={"leve": [], "grave": [], "critico": []}, dead=False)
        out = orch.run_round(
            _scene("player", "boss"),
            {"player": dict(hero), "boss": foe2},
            SIDES,
            declarations={"player": decl},
            initiator="heroes",
            rng=random.Random(seed),
        )
        blows = [b for b in out.get("final_blows") or [] if b["target_id"] == "boss"]
        if blows:
            assert blows[0]["kind"] == "ataque" and blows[0]["by_actor_id"] == "player"
            return
    raise AssertionError("nenhum golpe final registrado em 40 seeds")
