"""SPEC-360 R21: o rumor de avistamento conta o sinal, nao o nome; boost com presenca."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services import fauna, rumors
from services.fauna_lint import forbidden_for, leaked_tokens, load_refs

ROOT = Path(__file__).resolve().parents[1]
ARAME = "mon_arame_vivo"
SEED = "rumor_avist_" + ARAME


def _seeds() -> dict:
    return json.loads((ROOT / "data" / "world" / "rumor_seeds.json").read_text(encoding="utf-8"))[
        "seeds"
    ]


def test_semente_tem_sinal_rumor():
    seeds = _seeds()
    assert seeds[SEED]["sinal_rumor"] == fauna.entry(ARAME)["sinais"]["rumor"]
    for _sid, s in seeds.items():
        if s.get("family") == "avistamento" and s.get("sinal_rumor"):
            assert fauna.entry(s["entities"][0])


def test_rumor_seeds_fresco():
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, "scripts/build_rumor_seeds.py", "--check"], cwd=ROOT, capture_output=True
    )
    assert res.returncode == 0, res.stdout


def _row() -> dict:
    return {
        "rumor_id": "r1",
        "seed_id": SEED,
        "family": "avistamento",
        "location_id": "na_anel_lama",
    }


def test_render_usa_sinal_sem_nome(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    text = rumors.render_news({}, _row())
    assert fauna.entry(ARAME)["sinais"]["rumor"] in text
    assert not leaked_tokens(text, forbidden_for(ARAME, load_refs("nova_arcadia")))


def test_sem_fauna_texto_antigo(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "off")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "off")
    text = rumors.render_news({}, _row())
    assert "arame vivo" in text.lower()  # flags off: o template de antes (byte a byte)
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    other = {**_row(), "seed_id": "rumor_avist_enemy_bandido"}
    seeds = _seeds()
    if "rumor_avist_enemy_bandido" in seeds:
        assert "sinal_rumor" not in seeds["rumor_avist_enemy_bandido"]
        assert rumors.render_news({}, other)


@pytest.mark.parametrize("mode", ["on", "off"])
def test_boost_com_presenca(monkeypatch, mode):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", mode)
    sim = {
        "fauna": {
            "v": 1,
            "presencas": [
                {
                    "pid": "p1",
                    "creature_id": ARAME,
                    "region_id": "nova_arcadia",
                    "locais": ["na_anel_lama"],
                    "born_day": 5,
                    "expires_day": 9,
                    "sinais_mostrados": [],
                    "origem": "dia",
                    "status": "ativa",
                }
            ],
            "carcacas": [],
        }
    }
    w1 = next(w for s, w in rumors.candidates({}, sim, "nova_arcadia", 6) if s["seed_id"] == SEED)
    w0 = next(w for s, w in rumors.candidates({}, {}, "nova_arcadia", 6) if s["seed_id"] == SEED)
    if mode == "on":
        assert w1 == pytest.approx(w0 * fauna.const("RUMOR_BOOST"))
    else:
        assert w1 == pytest.approx(w0)
