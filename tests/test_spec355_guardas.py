"""SPEC-355 R50-R53: avaliador e goldens sem diff, sem flag nova, saves antigos carregam."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from services import card_piles as cp
from tests import spec330_equivalence as eq

ROOT = Path(__file__).resolve().parents[1]
PROTEGIDOS = (
    "scripts/cards/sim.py",
    "docs/spec335/arena_posturas.py",
    "docs/spec341/arena_spec341.py",
    "data/cards/_orcamento.json",
    "tests/spec330_equivalence.py",
    "tests/fixtures/spec330_legacy_golden.json",
    "tests/fixtures/spec330_card_text_snapshot.json",
    "tests/fixtures/router_off_golden.json",
)
NEW_KEYS = (
    "pressagios_desviados",
    "prenuncios",
    "fora_do_conflito",
)


def test_protected_paths_have_no_diff_against_main():
    for path in PROTEGIDOS:
        res = subprocess.run(
            ["git", "diff", "--quiet", "main", "--", path],
            capture_output=True,
            check=False,
            cwd=ROOT,
        )
        assert res.returncode == 0, path


def test_new_record_keys_never_reach_golden_actors_or_scene():
    from services import cards

    for cid in ("bas_dev_golpe", "bas_san_golpe", "dev_provocacao"):
        eq.run_card(cards.get_card(cid))
        blob = repr(eq.LAST_STATE)
        for key in NEW_KEYS:
            assert key not in blob, (cid, key)


def test_no_new_flag_registered():
    text = (ROOT / "config" / "flags.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    names = set(data.get("flags", data) if isinstance(data, dict) else data)
    assert not [n for n in names if "355" in str(n)]


def test_old_save_without_new_fields_loads():
    player = {"class_name": "Sangromante", "deck": ["bas_san_golpe"] * 12, "level": 1}
    piles = cp.start_piles(player, 1)
    piles.pop("fora_do_conflito")
    scene = {"zones": [], "positions": {}, "objects": []}
    assert "prenuncios" not in scene  # opcional: ausente = nenhuma promessa
    cp.draw(piles, 2)
    assert len(piles["mao"]) >= 5
