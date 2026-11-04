"""SPEC-389 R11-R14: presságio frustrado no painel, Voto diz o que aconteceu, condição com nome humano,
Reação na prosa do registro (50 sementes de `random`, MockLLM)."""

from __future__ import annotations

import pytest

from tests.fixtures import spec368_seed as sd
from tests.fixtures.spec387_rounds import load, play, step_card

SEEDS = range(50)


@pytest.fixture(scope="module")
def saves(tmp_path_factory):
    return str(tmp_path_factory.mktemp("spec389_text"))


@pytest.fixture(scope="module")
def seeded(saves):
    cache: dict = {}

    def get(item: int, variant: str = ""):
        if (item, variant) not in cache:
            cache[(item, variant)] = load(item, variant, saves)
        return cache[(item, variant)]

    return get


def _all_seeds(saves, state, steps, check, **kw):
    with sd._legacy(saves):
        for seed in SEEDS:
            out, text, raw = play(state, steps, seed, **kw)
            check(out, text, raw, seed)


def test_voto_outcome_replaces_next_intent(saves, seeded):
    _, st = seeded(13, "voto")
    steps = [step_card("bas_dev_voto", st["enemies"][0]["id"])]

    def check(out, text, raw, seed):
        assert "muda de alvo" in text or "resiste" in text, (seed, text)
        assert "próxima intenção" not in text, (seed, text)

    _all_seeds(saves, st, steps, check)


def test_round_board_has_frustrado(saves, seeded):
    _, st = seeded(2, "frustrar")
    steps = [step_card("arc1_des_estouro_contido", st["enemies"][0]["id"])]

    def check(out, text, raw, seed):
        board = out["combat"]["last_round_board"]
        rows = [e for e in board if e.get("tipo") == "pressagio_frustrado"]
        assert rows and rows[0]["efeito"] == "Presságio frustrado: Goblin", (seed, board)
        assert rows[0]["carta_id"] is None and rows[0]["carta_nome"] is None, seed
        assert not [e for e in board if e.get("tipo") == "pressagio"], seed

    _all_seeds(saves, st, steps, check)


def test_reaction_named_in_log(saves, seeded):
    _, st = seeded(13, "reacao")
    guard = {"kind": "maneuver", "maneuver": "guardar", "target_id": None}

    def check(out, text, raw, seed):
        assert "reage com Encaixe do Golpe" in text, (seed, text)
        assert "com Espada Gasta" not in text, (seed, text)

    _all_seeds(saves, st, [guard], check, reaction="dev_encaixe")


def _taunt_out(**extra):
    return {
        "logs": [],
        "attacks": [],
        "condicoes_novas": [{"control": "taunt", "source_id": "player", "victim_id": "enemy_g"}],
        **extra,
    }


ACTORS = {
    "player": {"id": "player", "name": "Herói", "is_player": True},
    "enemy_g": {"id": "enemy_g", "name": "Goblin"},
}


def test_taunt_before_action_keeps_line():
    from services import round_log

    text = " ".join(round_log.round_registry(_taunt_out(), ACTORS))
    assert "Goblin está provocado: a próxima intenção dele mira você" in text
    settled = _taunt_out(pressagios_desviados=[{"actor_id": "enemy_g"}])
    assert "próxima intenção" not in " ".join(round_log.round_registry(settled, ACTORS))


def test_condition_view_name_is_label(saves, seeded):
    import api

    _, st = seeded(13, "armadura")
    step = step_card("cor_ino_fadiga", st["enemies"][0]["id"])
    step["params"]["ruptura"] = True
    with sd._legacy(saves):
        out, _text, _raw = play(st, [step], 3)
        view = api._combat_block({**st, **out})
    conds = [c for e in view["enemies"] for c in e["conditions"]]
    armor = next(c for c in conds if c["id"] == "armadura_comprometida")
    assert armor["name"] == armor["label"] == "Armadura Comprometida"
    # o estado salvo não muda (SPEC-355 R8): o nome gravado segue sendo o id
    assert any(
        c.get("name") == "armadura_comprometida"
        for e in out["enemies"]
        for c in e.get("active_conditions") or []
    )


def test_front_never_matches_condition_name_to_id():
    """R13: nenhum consumidor do front compara `name` de condição com um id."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "web" / "src"
    pat = re.compile(r"\b(?:cd|cond|condition|c)\.name\s*===?\s*['\"][a-z_]+['\"]")
    hits = [
        str(p)
        for p in list(root.rglob("*.ts")) + list(root.rglob("*.tsx"))
        if pat.search(p.read_text(encoding="utf-8"))
    ]
    assert hits == []
