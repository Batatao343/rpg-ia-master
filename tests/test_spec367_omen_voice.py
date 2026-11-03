"""SPEC-367 R7-R9: presságio na voz do jogador ("você"), catálogo legível com nome e com "você"."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import api
from services import enemy_intent as ei

CATALOG = Path(__file__).resolve().parents[1] / "data" / "combat" / "pressagio_sinais.json"
HERO = "Smoke5A"


def _actors():
    return {
        "g1": {"id": "g1", "name": "Goblin", "family": "fera"},
        "h": {"id": "h", "name": HERO, "is_player": True},
        "a": {"id": "a", "name": "Bram"},
    }


def _intent(alvo):
    return {"actor_id": "g1", "tipo": "ataque", "alvo_id": alvo, "carta_id": None}


def test_hero_target_is_voce():
    row = ei.public_intent(_intent("h"), "desconhecida", actors_by_id=_actors())
    assert HERO not in row["sinal"]
    assert "você" in row["sinal"]


def test_ally_and_enemy_keep_name():
    row = ei.public_intent(_intent("a"), "desconhecida", actors_by_id=_actors())
    assert "Bram" in row["sinal"] and "você" not in row["sinal"]


def _phrases():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for tipo, fams in data.items():
        if tipo.startswith("_"):
            continue
        for fam, frases in fams.items():
            for f in frases:
                yield tipo, fam, f


def test_catalog_lint_no_de_alvo():
    bad = re.compile(
        r"\b(?:de|do|da) \{alvo\}|\{alvo\}-(?:lo|la|los|las)\b|\{alvo\}[^.;:,]*?\w+-(?:lo|la|los|las)\b"
    )
    for tipo, fam, f in _phrases():
        assert not bad.search(f), (tipo, fam, f)
        assert not f.lstrip().startswith("{alvo}"), (tipo, fam, f)
        assert not re.search(r"\{alvo\}[^.]*-(?:lo|la|los|las)\b", f), (tipo, fam, f)


@pytest.mark.parametrize("alvo", ["Mirela5", "você"])
def test_every_phrase_formats_with_name_and_voce(alvo):
    n = 0
    for _tipo, _fam, f in _phrases():
        out = f.format(nome="Goblin", alvo=alvo)
        assert "{" not in out and alvo in out if "{alvo}" in f else "{" not in out
        n += 1
    assert n > 20


def _rounds_with(monkeypatch, enemy_id, hint, hero, n=2, danger=3):
    """Combate real pelo nó, com herói nomeado e o encontro da família pedida."""
    import json
    import random

    import agents.combat as combat
    from tests.test_encounter_identity_repro import _install_llm, _start_state
    from tests.test_encounter_lifecycle_reload import _decl, _merge, _reload

    random.seed(9)
    _install_llm(monkeypatch)
    state0 = _start_state(hint=hint)
    state0["player"]["name"] = hero
    state = _decl(
        _start_state(
            hint=hint,
            player=state0["player"],
            combat_encounter_hint={"enemy_id": enemy_id, "reason": "random", "hint": hint},
            world={**state0["world"], "danger_level": danger},
            continuity={"session_action_count": 4, "timeline_epoch": 0},
        )
    )
    metas = []
    for _ in range(n):
        out = combat.combat_node(state)
        state = _reload(_merge(state, out))
        metas.append(json.loads(json.dumps(state["combat"], default=str)))
        if not state["combat"].get("active"):
            break
        _decl(state)
    return state, metas


@pytest.mark.parametrize(
    ("fam", "enemy_id", "hint", "hero"),
    [
        ("fera", "enemy_lobo_sombrio", "Lobo Sombrio", "Smoke5A"),
        ("morto_inquieto", "enemy_esqueleto", "Esqueleto", "Mirela5"),
    ],
)
def test_state_view_omens_without_hero_name(monkeypatch, fam, enemy_id, hint, hero):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    state, metas = _rounds_with(monkeypatch, enemy_id, hint, hero)
    assert state["player"]["name"] == hero
    rows = []
    for meta in metas:
        view = api._combat_block({"combat": meta, "enemies": [], "player": {}})
        rows += view.get("pressagios_publicos", [])
    assert rows, "nenhum presságio chegou à view"
    actors = {r["actor_id"] for r in rows}
    assert len(actors) >= 2, f"esperava 2 inimigos presságiando, veio {actors}"
    assert any(ei.family_of({"id": a}) == fam for a in actors), (fam, actors)
    for row in rows:
        assert hero not in row["sinal"], row
        assert hero not in str(row.get("prenuncio") or "")
    assert any("você" in r["sinal"] for r in rows)
