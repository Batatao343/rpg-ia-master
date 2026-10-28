"""SPEC-347 R13.2: importacao idempotente da arte do bestiario para o catalogo curado."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO

import pytest
from PIL import Image

from scripts import import_bestiary_art as imp
from services import visual_catalog


def _png(color=(120, 40, 40)) -> bytes:
    out = BytesIO()
    Image.new("RGB", (64, 64), color).save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def env(tmp_path):
    catalog = tmp_path / "visual_assets.json"
    catalog.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "asset_id": "A",
                        "subject_type": "class",
                        "subject_id": "X",
                        "visibility": "public",
                        "variants": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    best = tmp_path / "bestiary.json"
    best.write_text(json.dumps({"enemy_goblin": {"name": "Goblin"}}), encoding="utf-8")
    pasta = tmp_path / "in"
    (pasta / "criaturas").mkdir(parents=True)
    (pasta / "familias").mkdir()
    return pasta, dict(catalog_path=catalog, bestiary_path=best, out_dir=tmp_path / "out")


def test_unknown_creature_id_fails(env):
    pasta, kw = env
    (pasta / "criaturas" / "enemy_inexistente.png").write_bytes(_png())
    with pytest.raises(imp.ImportErrorArt):
        imp.import_folder(pasta, **kw)


def test_unknown_family_fails(env):
    pasta, kw = env
    (pasta / "familias" / "nao_existe.png").write_bytes(_png())
    with pytest.raises(imp.ImportErrorArt):
        imp.import_folder(pasta, **kw)


def test_import_is_idempotent_and_sha_matches(env):
    pasta, kw = env
    payload = _png()
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(payload)
    (pasta / "familias" / "bruto.png").write_bytes(_png((10, 90, 10)))
    assert imp.import_folder(pasta, **kw) == {"added": 2, "unchanged": 0}
    first = kw["catalog_path"].read_text(encoding="utf-8")
    assert imp.import_folder(pasta, **kw) == {"added": 0, "unchanged": 2}
    assert kw["catalog_path"].read_text(encoding="utf-8") == first
    data = json.loads(first)
    goblin = next(a for a in data["assets"] if a["subject_id"] == "enemy_goblin")
    assert goblin["subject_type"] == "creature" and goblin["visibility"] == "public"
    assert goblin["source"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert goblin["alt"] == "Retrato de Goblin"
    assert data["assets"][0]["subject_id"] == "X"  # entradas antigas mantêm a ordem
    thumb = goblin["variants"]["thumbnail"]
    written = next((kw["out_dir"] / "criaturas" / "enemy_goblin").glob("*.thumb.webp"))
    assert hashlib.sha256(written.read_bytes()).hexdigest() == thumb["sha256"]


def test_catalog_reader_resolves_the_imported_creature(env, monkeypatch):
    pasta, kw = env
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(_png())
    imp.import_folder(pasta, **kw)
    monkeypatch.setattr(visual_catalog, "CATALOG_PATH", kw["catalog_path"])
    visual_catalog._cached_catalog.cache_clear()
    try:
        asset = visual_catalog.visual_for("creature", "enemy_goblin")
        assert asset and asset["variants"]["thumbnail"]["url"].startswith(
            "/art/bestiario/criaturas/enemy_goblin/"
        )
    finally:
        visual_catalog._cached_catalog.cache_clear()
