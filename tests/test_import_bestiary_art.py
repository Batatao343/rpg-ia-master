"""SPEC-347 R13.2: importacao da arte do bestiario contra o catalogo REAL (copia) e o validador de conteudo."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from scripts import import_bestiary_art as imp
from services import visual_catalog
from services.content_validator import validate_visual_assets

ROOT = Path(__file__).resolve().parent.parent


def _png(seed=1, size=1600) -> bytes:
    """Ruido (pior caso de compressao): obriga o display a respeitar o teto de 300 KB."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (size, size))
    row = [
        (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
        for _ in range(size * size // 16)
    ]
    img.putdata(row * 16)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


@pytest.fixture(scope="module")
def public_copy(tmp_path_factory):
    """Copia do `web/public/art/v1` real: o validador confere os derivados ja existentes."""
    root = tmp_path_factory.mktemp("public")
    shutil.copytree(ROOT / "web" / "public" / "art" / "v1", root / "art" / "v1")
    return root


@pytest.fixture
def env(tmp_path, public_copy):
    catalog = tmp_path / "visual_assets.json"
    shutil.copy(ROOT / "data" / "visual_assets.json", catalog)
    pasta = tmp_path / "in"
    (pasta / "criaturas").mkdir(parents=True)
    (pasta / "familias").mkdir()
    out_dir = public_copy / "art" / "v1" / "bestiario"
    shutil.rmtree(out_dir, ignore_errors=True)
    kw = dict(catalog_path=catalog, bestiary_path=ROOT / "data" / "bestiary.json", out_dir=out_dir)
    return pasta, kw, public_copy


def test_real_catalog_after_import_passes_the_content_validator(env):
    pasta, kw, public = env
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(_png(1))
    (pasta / "criaturas" / "bst_lobo-cinzento.png").write_bytes(_png(2, 800))
    (pasta / "familias" / "bruto.png").write_bytes(_png(3, 900))
    assert imp.import_folder(pasta, **kw) == {"added": 3, "unchanged": 0}
    assert validate_visual_assets(str(kw["catalog_path"]), str(public)) == []
    data = json.loads(kw["catalog_path"].read_text(encoding="utf-8"))
    goblin = next(a for a in data["assets"] if a["subject_id"] == "enemy_goblin")
    assert goblin["variants"]["display"]["url"].startswith("/art/v1/bestiario/")
    assert goblin["variants"]["display"]["bytes"] <= 300_000
    assert goblin["variants"]["thumbnail"]["bytes"] <= 120_000
    assert any(a["subject_id"] == "bst:lobo-cinzento" for a in data["assets"])


def test_validator_rejects_unknown_creature(env):
    pasta, kw, public = env
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(_png(1, 600))
    imp.import_folder(pasta, **kw)
    data = json.loads(kw["catalog_path"].read_text(encoding="utf-8"))
    for a in data["assets"]:
        if a["subject_id"] == "enemy_goblin":
            a["subject_id"] = "enemy_nao_existe"
    kw["catalog_path"].write_text(json.dumps(data), encoding="utf-8")
    findings = validate_visual_assets(str(kw["catalog_path"]), str(public))
    assert any("subject canônico inexistente" in f.message for f in findings)


def test_unknown_ids_and_bad_pool_id_fail_without_writing(env):
    pasta, kw, public = env
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(_png(1, 600))
    bad = pasta / "criaturas" / "bst_Má Ideia.png"
    bad.write_bytes(_png(2, 600))
    before = kw["catalog_path"].read_text(encoding="utf-8")
    with pytest.raises(imp.ImportErrorArt):
        imp.import_folder(pasta, **kw)
    assert kw["catalog_path"].read_text(encoding="utf-8") == before
    assert not kw["out_dir"].exists()  # a falha do 2o arquivo nao deixa o WebP do 1o
    bad.unlink()
    (pasta / "criaturas" / "enemy_inexistente.png").write_bytes(_png(3, 600))
    with pytest.raises(imp.ImportErrorArt):
        imp.import_folder(pasta, **kw)
    (pasta / "criaturas" / "enemy_inexistente.png").unlink()
    (pasta / "familias" / "nao_existe.png").write_bytes(_png(4, 600))
    with pytest.raises(imp.ImportErrorArt):
        imp.import_folder(pasta, **kw)


def test_idempotent_and_force_required_to_replace(env):
    pasta, kw, public = env
    payload = _png(1, 700)
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(payload)
    assert imp.import_folder(pasta, **kw)["added"] == 1
    first = kw["catalog_path"].read_text(encoding="utf-8")
    assert imp.import_folder(pasta, **kw) == {"added": 0, "unchanged": 1}
    assert kw["catalog_path"].read_text(encoding="utf-8") == first
    goblin = next(a for a in json.loads(first)["assets"] if a["subject_id"] == "enemy_goblin")
    assert goblin["source"]["sha256"] == hashlib.sha256(payload).hexdigest()
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(_png(9, 700))
    with pytest.raises(imp.ImportErrorArt, match="--force"):
        imp.import_folder(pasta, **kw)
    assert imp.import_folder(pasta, force=True, **kw)["added"] == 1
    files = list((kw["out_dir"] / "criaturas" / "enemy_goblin").glob("*.webp"))
    assert len(files) == 2  # os WebP antigos sairam junto com a troca
    assert validate_visual_assets(str(kw["catalog_path"]), str(public)) == []


def test_hand_curated_entry_is_not_overwritten_without_force(env):
    pasta, kw, public = env
    data = json.loads(kw["catalog_path"].read_text(encoding="utf-8"))
    data["assets"].append(
        {
            "asset_id": "VAL-X",
            "subject_type": "creature",
            "subject_id": "enemy_goblin",
            "visibility": "public",
            "source": {"bundle": "HANDOFF", "sha256": "0" * 64},
            "variants": {},
        }
    )
    kw["catalog_path"].write_text(json.dumps(data), encoding="utf-8")
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(_png(1, 600))
    with pytest.raises(imp.ImportErrorArt, match="CURADA"):
        imp.import_folder(pasta, **kw)


def test_catalog_reader_resolves_the_imported_creature(env, monkeypatch):
    pasta, kw, public = env
    (pasta / "criaturas" / "enemy_goblin.png").write_bytes(_png(1, 600))
    imp.import_folder(pasta, **kw)
    monkeypatch.setattr(visual_catalog, "CATALOG_PATH", kw["catalog_path"])
    visual_catalog._cached_catalog.cache_clear()
    try:
        asset = visual_catalog.visual_for("creature", "enemy_goblin")
        assert asset and asset["variants"]["thumbnail"]["url"].startswith(
            "/art/v1/bestiario/criaturas/enemy_goblin/"
        )
    finally:
        visual_catalog._cached_catalog.cache_clear()
