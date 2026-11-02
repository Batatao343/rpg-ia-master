"""SPEC-360 R3: compilacao deterministica do `fauna.json` e bestiario intocado."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.fauna import build

ROOT = Path(__file__).resolve().parents[1]


def test_build_deterministico():
    assert build.render(build.build_doc()) == build.render(build.build_doc())


def test_fauna_json_fresco():
    assert build.OUT.exists(), "rode scripts/fauna/build.py"
    assert build.is_fresh(), "fauna.json desatualizado: rode scripts/fauna/build.py"


def test_fauna_json_lf_e_ordenado():
    raw = build.OUT.read_bytes()
    assert b"\r\n" not in raw
    doc = json.loads(raw.decode("utf-8"))
    assert doc["version"] == 1
    assert list(doc["criaturas"]) == sorted(doc["criaturas"])


def test_predadores_derivados():
    doc = build.build_doc()
    for cid, e in doc["criaturas"].items():
        for prey in e["ecologia"]["presas"]:
            if prey in doc["criaturas"]:
                assert cid in doc["criaturas"][prey]["predadores"]


def test_contra_jogo_igual_ficha():
    """E13 no compilado: toda ficha leva o mesmo `contra_jogo` da ficha."""
    import yaml

    doc = build.build_doc()
    for path in sorted((ROOT / "data" / "bestiario" / "fichas").glob("*.yaml")):
        fichas = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for c in fichas.get("criaturas") or []:
            if c["id"] in doc["criaturas"] and c.get("status") in (
                "nova",
                "reinventada",
                "adotada",
            ):
                assert doc["criaturas"][c["id"]]["contra_jogo"] == str(c["contra_jogo"]).strip()


def test_bestiary_json_intocado():
    """`data/bestiary.json` nao muda (as linhas alimentam o `source` das sementes): o build
    nao o escreve e a arvore de trabalho bate com o HEAD (no pouso, o diff da branch)."""
    before = (ROOT / "data" / "bestiary.json").read_bytes()
    build.render(build.build_doc())
    assert (ROOT / "data" / "bestiary.json").read_bytes() == before
    try:
        diff = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", "data/bestiary.json"], cwd=ROOT, check=False
        )
    except OSError:
        return
    assert diff.returncode in (0, 128)  # 128 = sem git (pacote); 1 = alterado
