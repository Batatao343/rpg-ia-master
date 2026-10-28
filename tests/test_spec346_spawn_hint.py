"""SPEC-346 R23-R25: nucleo da dica, nome de inimigo nunca e frase do jogador."""

import pytest

from services import encounter_manifest as em

GALERIA = "primeira criatura hostil que surgir na galeria"


@pytest.mark.parametrize(
    ("hint", "core", "generic"),
    [
        (GALERIA, "criatura hostil", True),
        ("o bandido mais próximo", "bandido", False),
        ("o saqueador ferido à minha esquerda", "saqueador", False),
        ("a criatura que mora lá embaixo", "criatura", True),
        ("Goblin", "goblin", False),
        ("o Trasgo", "trasgo", False),
    ],
)
def test_hint_core_examples(hint, core, generic):
    assert em.hint_core(hint) == core
    assert em.is_generic_hint(hint) is generic


# --- spawn (R24, R25) --------------------------------------------------------
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

import agents.combat as combat  # noqa: E402
from llm_setup import FallbackLLM  # noqa: E402
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state  # noqa: E402

YSOLDE_HINT = "primeira criatura hostil que surgir na galeria"


def _wrong_species_factory(name, **_kw):
    return {
        "id": "enemy_cultista_encapuzado",
        "name": "Cultista Encapuzado",
        "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
    }


def _names_ok(enemies, hint):
    for e in enemies:
        name = e["name"]
        assert " que " not in name.lower()
        assert len(name.split()) <= 4
        assert name.casefold() != hint.casefold()


def test_generic_hint_accepts_scanner(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    events = []
    monkeypatch.setattr(combat, "_log_event", lambda *a, **k: events.append(a[:2]))
    state = _start_state(hint=YSOLDE_HINT)
    enemies, _ = combat._spawn_v4_enemies(state["messages"], YSOLDE_HINT, state, {})
    assert enemies[0]["name"] == "Goblin"
    assert ("combat", "spawn_scanner_discarded") not in events
    _names_ok(enemies, YSOLDE_HINT)


def test_identity_lock_never_uses_raw_phrase(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Saqueador", 1)))
    monkeypatch.setattr(combat, "generate_new_enemy", _wrong_species_factory)
    hint = "o saqueador ferido à minha esquerda"
    state = _start_state(hint=hint)
    enemies, _ = combat._spawn_v4_enemies(state["messages"], hint, state, {})
    assert enemies[0]["name"] == "Saqueador"
    assert enemies[0]["id"].startswith("fallback_saqueador")
    _names_ok(enemies, hint)


def test_identity_lock_with_hint_phrase_scanner_empty(monkeypatch):
    _install_llm(monkeypatch, scan=_scan(("Cultista", 1)))
    monkeypatch.setattr(combat, "generate_new_enemy", _wrong_species_factory)
    hint = "o lutador mascarado que mora lá embaixo"
    state = _start_state(hint=hint)
    enemies, _ = combat._spawn_v4_enemies(state["messages"], hint, state, {})
    assert enemies[0]["name"] == "Lutador mascarado"
    _names_ok(enemies, hint)


def test_scanner_down_uses_bestiary_from_narration(monkeypatch):
    monkeypatch.setattr(combat, "get_llm", lambda **k: FallbackLLM("sem chave"))
    msgs = [
        AIMessage(content="Na galeria escura, um goblin rosna e ergue a adaga."),
        HumanMessage(content="ataco a primeira criatura hostil que surgir"),
    ]
    meta = {}
    enemies, _ = combat._spawn_v4_enemies(msgs, YSOLDE_HINT, None, meta)
    assert enemies[0]["name"] == "Goblin"
    assert meta["source"] == "narration_bestiary"
    _names_ok(enemies, YSOLDE_HINT)
