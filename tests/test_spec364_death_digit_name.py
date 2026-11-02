"""SPEC-364 R21: morte com nome de heroi contendo digito ("Smoke4A") nao mutila o nome nem fala o nome ao jogador.

Cobertura: o desfecho (`_narrate_outcome`) nos dois caminhos (resumo do LLM aceito e fallback forcado por
V4/V6), o registro e os fatos. A queda do heroi em si e aleatoria no motor real; o oraculo e o texto."""

from __future__ import annotations

import pytest

import agents.combat as combat
from services import round_log

HERO = "Smoke4A"
PLAYER = {
    "name": HERO,
    "vitalidade": 0,
    "max_vitalidade": 18,
    "ferimentos": {"critico": [{"regiao": "perna"}]},
}
ENEMIES = [
    {"id": "enemy_mino", "name": "Minotauro Esqueleto"},
    {"id": "enemy_goblin", "name": "Goblin"},
]
NAMES = {"enemy_mino": "Minotauro Esqueleto", "enemy_goblin": "Goblin"}
SUMMARY = {
    "participantes": [HERO, "Goblin", "Minotauro Esqueleto"],
    "mortos": ["Goblin"],  # caiu numa rodada anterior
    "caidos": [HERO],
    "inconscientes": [],
}
LAST_OUT = {
    "final_blows": [{"target_id": "player", "kind": "ataque", "by_actor_id": "enemy_mino"}],
    "terminal": ["player"],
}
GOOD_LLM = (
    "Você tomba diante de Minotauro Esqueleto. O Goblin, que já tinha tombado, jaz ao seu lado. "
    "Você carrega ferimento crítico na perna."
)
BAD_LLM = "Você tomba. O Goblin também tomba sem vida ao seu lado. Smoke4A cai."


def _outcome(monkeypatch, text, sink):
    monkeypatch.setattr(combat, "_fast_text", lambda *a, **k: text)
    return combat._narrate_outcome(
        "death",
        SUMMARY,
        PLAYER,
        ENEMIES,
        LAST_OUT,
        "ataco",
        "",
        manifest=None,
        names=NAMES,
        source_sink=sink,
    )


def _assert_clean(text: str):
    assert "SmokeA" not in text
    assert "Você" in text


def test_llm_summary_accepted_keeps_voice(monkeypatch):
    sink: dict = {}
    text = _outcome(monkeypatch, GOOD_LLM, sink)
    assert sink["last_outcome_source"] == "llm"
    _assert_clean(text)


def test_forced_fallback_keeps_voice_and_past_tense(monkeypatch):
    sink: dict = {}
    text = _outcome(monkeypatch, BAD_LLM, sink)
    assert sink["last_outcome_source"] == "fallback_attribution"
    _assert_clean(text)
    assert "Smoke4A" not in text  # o heroi e "Você"; o nome so aparece na cronica
    assert "Goblin tomba" not in text and "já tinha tombado" in text
    assert text.startswith("Você tomba diante de Minotauro Esqueleto.")


def test_registry_and_facts_never_mutilate_the_name():
    actors = {
        "player": {"is_player": True, "name": HERO},
        "enemy_mino": {"name": "Minotauro Esqueleto"},
    }
    out = {
        "scene_logs": [f"{HERO} sente o Abismo mais perto (+1 Carga)."],
        "logs": [f"{HERO}: ganha condição cego"],
        "attacks": [
            {
                "actor_id": "enemy_mino",
                "target_id": "player",
                "acerto": True,
                "resultado": "acerto",
                "dano_final": 5,
            }
        ],
        **LAST_OUT,
    }
    lines = "\n".join(round_log.round_registry(out, actors))
    assert "SmokeA" not in lines
    assert not any(ln.startswith(HERO) for ln in lines.splitlines())
    facts = "\n".join(
        round_log.outcome_facts("death", SUMMARY, PLAYER, ENEMIES, LAST_OUT, names=NAMES)
    )
    assert "SmokeA" not in facts
    assert "Antes do fim, Goblin já tinha morrido." in facts


def test_killer_is_author_of_final_blow():
    active = [dict(e) for e in ENEMIES]
    assert combat._killer_identity(active, LAST_OUT, ENEMIES)[0] != ""
    only_goblin = [ENEMIES[1]]
    # sem final_blows o primeiro ativo responde; com final_blows vale o autor do golpe
    first = combat._killer_identity(only_goblin, None, ENEMIES)[0]
    blow = combat._killer_identity(active, LAST_OUT, ENEMIES)[0]
    assert first != blow  # o autor do golpe final (Minotauro), não o 1º ativo (Goblin)
    from services import encounter_manifest as em

    assert blow == em.species_label_for(ENEMIES[0])


@pytest.mark.parametrize("name", ["Smoke4A", "Bandido 2", "Mirela4"])
def test_no_digits_keeps_protected_names(name):
    assert name in round_log._no_digits(f"{name} cai com 3 de dano.", [name])
