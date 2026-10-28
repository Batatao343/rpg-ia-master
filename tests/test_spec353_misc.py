"""SPEC-353 etapas 6-7: nomes, Baralho x Preparacao, arestas de texto, orcamento do resumo, D6."""

from __future__ import annotations

import json
import time

import pytest

import api
from agents import combat as combat_agent
from agents import loot
from services import card_piles, cards, enemy_decks, round_log


# --- R23 nome exibivel ---
def test_participant_name_never_raw_id():
    state = {"npcs": {"npc_ketil": {"id": "npc_ketil", "name": "Ketil"}}}
    names = api._ParticipantNames(state, {}, [{"id": "enemy_1"}])
    assert names.get("npc_ketil", "npc_ketil") == "Ketil"
    assert names.get("ghost_9", "ghost_9") == "Aliado"
    assert names.get("enemy_1", "enemy_1") == "Inimigo"
    names["player"] = "Haldor"
    assert names.get("player", "x") == "Haldor"


def test_view_keeps_round_board_after_conflict_ends(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    board = [{"tipo": "jogada", "ator_nome": "Você"}]
    state = {
        "player": {"name": "Haldor"},
        "enemies": [],
        "combat": {"active": False, "last_round_board": board, "last_mech_log": ["Fuga"]},
    }
    view = api._combat_block(state)
    assert view["registro_rodada"] == board and view["mech_log"] == ["Fuga"]
    assert "pilhas" not in view


# --- R31/R32 Baralho x Preparacao ---
def _player(deck: list[str] | None) -> dict:
    return {
        "class_name": "Devoto do Abismo",
        "level": 1,
        "known_cards": ["dev_provocacao"],
        "prepared_cards": ["dev_provocacao"],
        "deck": deck or [],
    }


@pytest.mark.parametrize("mode", ["on", "off"])
def test_deck_mode_slots_invariant(monkeypatch, mode):
    monkeypatch.setenv("RPG_CARD_DECK", mode)
    deck = ["bas_dev_golpe"] * 10 + ["dev_provocacao"] * 3
    player = _player(deck)
    rows = api._cards_block(player)
    prepared = sum(1 for r in rows if r["prepared"])
    assert prepared <= api._prepared_slots(player)
    view = api._deck_view(player)
    if mode == "on":
        assert view == {"total": 13, "minimo": 12, "maximo": 24, "do_acervo": 3}
        assert api._prepared_slots(player) == cards.DECK_MAX
    else:
        assert view is None


# --- D6 revertido: utilitaria continua no baralho (arena: Medico +2,7 pp com ela fora) ---
def test_utility_cards_stay_in_the_draw_pile(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    util = next(c["id"] for c in cards.all_cards().values() if c.get("tipo") == "utilitaria")
    player = _player(["bas_dev_golpe"] * 12 + [util])
    piles = card_piles.start_piles(player, 7)
    everything = piles["compra"] + piles["mao"] + piles["descarte"] + piles["exaurida"]
    assert util in everything


# --- R34 / R36 texto ---
def test_wound_text_ptbr():
    atk = {"acerto": True, "resultado": "critico", "dano_final": 5}
    atk["ferimento"] = {"categoria": "critico", "regiao": "cabeca"}
    text = round_log._result_phrase(atk)
    assert "ferimento crítico na cabeça" in text and "região" not in text
    atk["ferimento"] = {"categoria": "grave", "regiao": "torso"}
    assert "ferimento grave no torso" in round_log._result_phrase(atk)


def test_registry_uses_voce_and_capitalized_condition():
    hero = {"name": "Haldor", "is_player": True}
    out = {"logs": ["Haldor: ganha condição desmoralizado", "Haldor: Sangramento terminou."]}
    reg = round_log.round_registry(out, {"player": hero})
    assert "Você ganha a condição Desmoralizado." in reg
    assert "Sua condição Sangramento terminou." in reg


def test_loot_rarity_text():
    assert loot._rarity_phrase("comum") == ""
    assert loot._rarity_phrase("incomum") == ", item incomum,"
    assert "(" not in f"Corda{loot._rarity_phrase('raro')} e +2 de ouro"


# --- R38 conteudo ---
def test_enemy_deck_skips_caster_cards_for_melee(monkeypatch):
    melee = {"id": "x", "arquetipo": "brutamontes", "attacks": [{"type": "melee"}]}
    caster = {"id": "y", "arquetipo": "conjurador", "attacks": [{"type": "melee"}]}
    assert enemy_decks._is_melee_only(melee) and not enemy_decks._is_melee_only(caster)
    arcane = next(
        c["id"]
        for c in cards.all_cards().values()
        if (c.get("efeito") or {}).get("dano_tipo") == "arcano"
    )
    assert not enemy_decks._fits_creature(melee, arcane)
    assert enemy_decks._fits_creature(caster, arcane)


def test_eco_da_boca_only_in_caverna():
    with open("data/combat/cartas_de_cena.json", encoding="utf-8") as f:
        data = json.load(f)
    rows = data if isinstance(data, list) else data.get("cartas") or data.get("cards") or []
    eco = next(r for r in rows if r.get("id") == "eco_da_boca")
    assert eco["tags"] == ["caverna"]


# --- R39c orcamento do resumo ---
class _SlowLLM:
    is_fallback = False

    def __init__(self, delay: float):
        self.delay = delay

    def invoke(self, *_a, **_k):
        time.sleep(self.delay)

        class _R:
            content = "O silêncio volta ao campo."

        return _R()


def _outcome(monkeypatch, delay: float, budget: float):
    events = []
    monkeypatch.setattr(combat_agent, "_OUTCOME_BUDGET_S", budget)
    monkeypatch.setattr(combat_agent, "get_llm", lambda **_k: _SlowLLM(delay))
    monkeypatch.setattr(
        combat_agent, "_log_event", lambda *a, **k: events.append((a[0], a[1]))
    )
    start = time.monotonic()
    text = combat_agent._narrate_outcome(
        "victory",
        {"mortos": ["Criatura"]},
        {"name": "Haldor", "vitalidade": 5, "max_vitalidade": 10},
        [],
        {},
        "ataco",
        "",
        manifest=None,
    )
    return text, events, time.monotonic() - start


def test_outcome_budget_exceeded_uses_fallback(monkeypatch):
    text, events, elapsed = _outcome(monkeypatch, delay=1.5, budget=0.2)
    assert ("combat", "outcome_narration_budget_exceeded") in events
    assert elapsed < 1.2 and "O silêncio volta" not in text


def test_outcome_within_budget_uses_llm(monkeypatch):
    text, events, _ = _outcome(monkeypatch, delay=0.0, budget=5.0)
    assert ("combat", "outcome_narration_budget_exceeded") not in events
    assert "O silêncio volta" in text
