"""SPEC-312 Etapa 1: gerador, dados e curadoria das sementes de rumor."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from scripts import build_rumor_seeds as gen
from services import rumors
from services import world_pressures as wp

ROOT = Path(__file__).resolve().parent.parent


def _seeds() -> dict:
    return json.loads((ROOT / "data/world/rumor_seeds.json").read_text(encoding="utf-8"))["seeds"]


def _lore() -> dict:
    return {k: v for k, v in _seeds().items() if v["family"] == "lore"}


def test_forty_lore_seeds_with_source_line():
    lore = _lore()
    assert len(lore) == 40
    lines = (ROOT / "lore_nova/rumors.txt").read_text(encoding="utf-8").split("\n")
    for seed in lore.values():
        path, _, n = seed["source"].rpartition(":")
        assert path == "lore_nova/rumors.txt"
        assert lines[int(n) - 1].startswith("[CATEGORIA: RUMOR]")


def test_confiabilidade_distribution_13_15_12():
    counts = Counter(s["confiabilidade"] for s in _lore().values())
    assert (counts["alta"], counts["media"], counts["baixa"]) == (13, 15, 12)


def test_regions_locations_entities_exist():
    from services import graph_resolver as gr

    ents = gr.load_entities()
    locs = wp._map_index()[0]
    for sid, s in _lore().items():
        assert s["regions"], sid
        assert set(s["regions"]) <= set(wp.region_ids()), sid
        assert s["location_id"] in locs, sid
        assert all(e in ents for e in s["entities"]), sid


def test_default_truth_by_confiabilidade_and_false_ratio():
    lore = _lore()
    ov = gen.load_overrides()
    for sid, s in lore.items():
        if "truth" not in ov.get(sid, {}):
            assert s["truth"] is (s["confiabilidade"] != "baixa"), sid
    ratio = sum(1 for s in lore.values() if not s["truth"]) / len(lore)
    assert 0.20 <= ratio <= 0.35


def test_avistamento_excludes_boss_and_points_to_bestiary_line():
    bestiary = json.loads((ROOT / "data/bestiary.json").read_text(encoding="utf-8"))
    lines = (ROOT / "data/bestiary.json").read_text(encoding="utf-8").split("\n")
    avist = {k: v for k, v in _seeds().items() if v["family"] == "avistamento"}
    assert avist
    for s in avist.values():
        eid = s["entities"][0]
        assert bestiary[eid]["type"] in ("Minion", "Standard", "Elite")
        assert bestiary[eid]["regions"]
        n = int(s["source"].rpartition(":")[2])
        assert f'"{eid}"' in lines[n - 1]
        assert s["truth_mode"] == "regional"
        assert not re.search(r"\d", s["creature_label"])
    assert not any(b["type"] == "BOSS" and f"rumor_avist_{k}" in avist for k, b in bestiary.items())


def test_gist_short_no_digits_no_unlisted_names():
    from agents.world_simulator import _catalog_names

    catalog = _catalog_names()
    for sid, s in rumors.load_seeds().items():
        if s["family"] != "lore":
            continue
        gist = s["gist"]
        assert len(gist) <= 200 and not re.search(r"\d", gist), sid
        for name in catalog:
            if name.lower() in gist.lower():
                assert name in s.get("public_names", []), (sid, name)


def test_overrides_survive_regeneration(monkeypatch, tmp_path):
    ov = tmp_path / "ov.json"
    ov.write_text(
        json.dumps({"overrides": {"rumor_valerius_nao_come_nem_dorme": {"truth": False}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(gen, "OVERRIDES", ov)
    doc, _ = gen.build()
    assert doc["seeds"]["rumor_valerius_nao_come_nem_dorme"]["truth"] is False
    # gerado sem override: padrao da confiabilidade (media -> verdadeiro)
    monkeypatch.setattr(gen, "OVERRIDES", tmp_path / "none.json")
    doc2, _ = gen.build()
    assert doc2["seeds"]["rumor_valerius_nao_come_nem_dorme"]["truth"] is True


def test_generator_is_byte_stable_lf():
    raw = (ROOT / "data/world/rumor_seeds.json").read_bytes()
    assert b"\r" not in raw
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_rumor_seeds.py"), "--check"],
        capture_output=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout


def test_disabled_seed_is_not_loaded():
    assert "rumor_valerius_nao_come_nem_dorme" in rumors.load_seeds()
    assert all(not s.get("disabled") for s in rumors.load_seeds().values())


@pytest.mark.parametrize("family", ["lore", "avistamento"])
def test_every_family_has_templates(family):
    assert rumors.config()["templates"][f"rumor.{family}"]
