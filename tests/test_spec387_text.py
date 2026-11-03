"""SPEC-387 R28-R31, R33-R35: textos e rótulos do registro, do Acervo, do modo `off` e da loja."""

from __future__ import annotations

import re

import pytest

import agents.combat as combat
from services import card_piles as cp
from services import card_text, cards, prose_guard, round_log
from tests.fixtures import spec368_seed as sd
from tests.fixtures import spec387_smoke as fixt
from tests.fixtures.spec387_rounds import load, play, step_card
from tests.test_card_piles import _player, _Step

ID_RE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


@pytest.fixture(scope="module")
def saves(tmp_path_factory):
    return str(tmp_path_factory.mktemp("spec387_text"))


def _rachadura(saves, seed=0):
    _, st = load(3, "rachadura", saves)
    steps = [
        step_card("cor1_ino_junta_emperrada", st["enemies"][0]["id"]),
        step_card("bas_cor_golpe"),
    ]
    steps[1]["target_id"] = st["enemies"][0]["id"]
    with sd._legacy(saves):
        return play(st, steps, seed)


def test_mech_log_rachadura_pct(saves):
    for seed in range(5):
        out, _text, _raw = _rachadura(saves, seed)
        assert any("Rachadura +25 %" in ln for ln in out["combat"]["last_mech_log"]), seed


def test_condition_line_order(saves):
    for seed in range(5):
        _out, text, _raw = _rachadura(saves, seed)
        lines = text.splitlines()
        cond = next(i for i, ln in enumerate(lines) if "ganha a condição Rachadura" in ln)
        enemy_attack = next(i for i, ln in enumerate(lines) if ln.startswith("Goblin ataca"))
        play_line = next(i for i, ln in enumerate(lines) if "Junta Emperrada" in ln)
        assert play_line < cond < enemy_attack, (seed, lines)


def _boss(saves, seed=0):
    _, st = load(5, "chefe_fase", saves)
    with sd._legacy(saves):
        return play(st, [step_card("bas_dev_golpe", st["enemies"][0]["id"])], seed)


def test_phase_line_once_all_surfaces(saves):
    for seed in range(5):
        _out, text, raw = _boss(saves, seed)
        assert raw["fases"], seed
        for fase in raw["fases"]:
            assert text.count(fase["texto"]) == 1, (seed, fase)


def test_extra_action_without_target_silent(saves):
    for seed in range(20):
        _out, text, _raw = _boss(saves, seed)
        assert "Ataque sem alvo válido" not in text, seed
        if "age de novo" in text:
            assert text.count(" ataca ") >= 2, (seed, text)


def test_pressagio_cumprido_names_card(saves):
    _out, text, _raw = _boss(saves)
    assert "cumpre o presságio" not in text
    out, _t, _r = _boss(saves)
    entries = [e for e in out["combat"]["last_round_board"] if e.get("tipo") == "pressagio"]
    assert entries
    for e in entries:
        assert " — " in e["efeito"] or e["efeito"].endswith("age como anunciou"), e
        assert "cumpre o presságio" not in e["efeito"]


def test_subclass_label_human():
    mao = next(c for cid, c in cards.all_cards().items() if cid.startswith("inf_fac_mao_sombria_"))
    assert card_text.subclass_label(mao) == "Mão Sombria"
    assert (
        card_text.subclass_label({"classe": "Devoto do Abismo", "subclasse": "zeloso"})
        == "O Zeloso"
    )
    assert card_text.subclass_label({"subclasse": "inexistente_x"}) == ""
    assert card_text.subclass_label({}) == ""
    for c in cards.all_cards().values():
        label = card_text.subclass_label(c)
        assert "_" not in label and not re.fullmatch(r"[a-z0-9_]+", label or "x "), (c["id"], label)


LOGS = [
    "enemy_goblin_1 não está na cena.",
    "Goblin: Defesa Instintiva terminou.",
    "Smoke: ganha condição Rachadura",
    "dano 6×1=6; Vitalidade 18 -> 12 (excedente 0)",
]


def test_off_fallback_no_ids_no_bullets():
    text = round_log.off_fallback_text(LOGS, "Smoke", "Algo hostil emerge.", False)
    assert "⚔️" not in text and "•" not in text
    assert not ID_RE.search(text) and "não está na cena" not in text
    assert "A condição Defesa Instintiva de Goblin terminou." in text
    assert "Você ganha a condição Rachadura." in text
    assert text.endswith("O que você faz?")
    assert round_log.off_fallback_text([], "Smoke", "", True).endswith("Vitória! O campo silencia.")


def test_off_prose_with_hero_name_falls_back(monkeypatch):
    class _Llm:
        is_fallback = False

    monkeypatch.setattr(combat, "get_llm", lambda **_k: _Llm())
    from services import narrative_sink

    monkeypatch.setattr(
        narrative_sink,
        "narrate_text",
        lambda *_a, **_k: type("R", (), {"content": "Smoke avança e Goblin recua."})(),
    )
    player = {"name": "Smoke", "vitalidade": 5, "max_vitalidade": 9}
    out = combat._narrate(player, [], ["Smoke: ganha condição Rachadura"], None, "ataco", False, "")
    assert "Smoke avança" not in out and "⚔️" not in out and "•" not in out
    assert "Você ganha a condição Rachadura." in out


def test_pact_refusal_cites_batch():
    p = _player()
    piles = cp.start_piles(p, 1)
    piles["folego"] = 2
    golpe = next(c for c in piles["mao"] + piles["compra"] if c.startswith("bas_"))
    piles["mao"] = [golpe] * 5
    plan = cp.plan_plays(piles, p, [_Step("card", golpe)] * 5)
    assert not plan["ok"]
    assert plan["motivo"] == (
        "Fôlego insuficiente: estas jogadas custam 5, você tem 2 e o Pacto do Abismo empresta "
        f"no máximo {cp.PACTO_MAX_FOLEGO} por rodada."
    )
    assert "(0/1)" not in plan["motivo"]


def test_place_as_actor_rejects_smoke_text():
    assert prose_guard.place_as_actor(fixt.SMOKE_REJECTED, fixt.PLACE)
    assert not prose_guard.place_as_actor(fixt.SMOKE_REJECTED, "")


def test_place_as_actor_benign_corpus():
    for text in fixt.ACCEPTED:
        assert not prose_guard.place_as_actor(text, fixt.PLACE), text


def test_merchant_context_says_the_place_does_not_act():
    from agents import loot

    ctx = loot._merchant_context("Forja dos Clãs", "Skallgard")
    assert "Mercador: Forja dos Clãs. Lugar: Skallgard (o lugar não age;" in ctx


def test_narrate_rejects_place_as_actor(monkeypatch):
    from agents import loot
    from services import narrative_sink

    class _Llm:
        is_fallback = False

    monkeypatch.setattr(loot, "get_llm", lambda **_k: _Llm())
    monkeypatch.setattr(
        narrative_sink,
        "narrate_text",
        lambda *_a, **_k: type("R", (), {"content": fixt.SMOKE_REJECTED})(),
    )
    events: list = []
    monkeypatch.setattr(loot, "_log_event", lambda *a, **k: events.append(k.get("reason")))
    out = loot._narrate(
        "BUY",
        "Forja dos Clãs fecha o negócio sem cerimônia.",
        gold_check=({50, 30}, 30, "Skallgard"),
    )
    assert out == "Forja dos Clãs fecha o negócio sem cerimônia." and "place_as_actor" in events


def test_frustrated_omen_line_in_registry(saves):
    """SPEC-387 (pendência 6a): o presságio frustrado aparece no registro, sem id nem Carta oculta."""
    _, st = load(2, "frustrar", saves)
    foe = st["enemies"][0]["id"]
    with sd._legacy(saves):
        for seed in range(10):
            _out, text, raw = play(st, [step_card("arc1_des_estouro_contido", foe)], seed)
            assert raw.get("pressagios_frustrados"), seed
            assert text.count("Presságio frustrado: Goblin") == 1, (seed, text)
            assert (
                not ID_RE.search(text)
                and "Investida" not in text.split("Presságio frustrado")[1].splitlines()[0]
            )
