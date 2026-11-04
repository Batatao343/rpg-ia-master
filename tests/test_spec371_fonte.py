"""SPEC-371 R5-R7: fonte do contra-jogo em runtime (`bestiario_saber.json`)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from services import fauna_saber

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "world" / "bestiario_saber.json"


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_saber_371", ROOT / "scripts" / "fauna" / "build_saber.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def built():
    return _builder().build_doc()


def test_build_deterministico(built):
    b = _builder()
    assert b.render(built) == b.render(b.build_doc())
    assert list(built["criaturas"]) == sorted(built["criaturas"])


def test_bestiario_saber_fresco(built):
    b = _builder()
    assert JSON_PATH.read_text(encoding="utf-8") == b.render(built)


def test_cobre_todas_as_fichas(built):
    assert len(built["criaturas"]) == 281
    assert all(e["contra_jogo"].strip() and e["regiao"] for e in built["criaturas"].values())


def test_legado_fora(built):
    legado = yaml.safe_load(
        (ROOT / "data" / "bestiario" / "curadoria_legado.yaml").read_text(encoding="utf-8")
    )
    ids_legado = {cid for cid, e in legado.items() if e.get("classe") == "valoria"}
    assert ids_legado, "fixture do legado vazia"
    com_ficha_nova = set(built["criaturas"])
    # legado sem ficha nova nao revela (R7); legado reinventado/adotado ja tem ficha propria
    from services import bestiary_lint as bl

    retro = {i for i, f in bl.load_fichas().items() if f.get("status") == "retro"}
    assert not (retro & com_ficha_nova)
    for cid in ids_legado & retro:
        assert fauna_saber.contra_jogo_of(cid) == ""


def test_contra_jogo_of_ordem(monkeypatch):
    fauna_saber._compiled.cache_clear()
    assert fauna_saber.contra_jogo_of("mon_arame_vivo").startswith("Manter distância")
    assert fauna_saber.contra_jogo_of("") == ""
    assert fauna_saber.contra_jogo_of("nao_existe_xyz") == ""
    # 2) template gerado em jogo (overlay) com ficha
    from services import discovery

    fake = {"gerada_x": {"ficha": {"contra_jogo": "Fuja da luz."}}, "gerada_y": {}}
    monkeypatch.setattr(discovery, "_bestiary_db", lambda: fake)
    assert fauna_saber.contra_jogo_of("gerada_x") == "Fuja da luz."
    assert fauna_saber.contra_jogo_of("gerada_y") == ""
    # 1) o JSON compilado vence o overlay
    fake["mon_arame_vivo"] = {"ficha": {"contra_jogo": "outro"}}
    assert fauna_saber.contra_jogo_of("mon_arame_vivo").startswith("Manter distância")


def test_bestiary_e_fauna_json_intocados():
    # SHA da main em 86cb7bb8 (nenhum byte muda nesta spec). Guarda de branch: depois do pouso specs
    # seguintes podem mudar esses arquivos, e o clone raso do CI nem tem o commit.
    import subprocess

    def _git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)

    if _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "spec-371":
        pytest.skip("guarda só vale na branch spec-371")
    if _git("cat-file", "-e", "86cb7bb8^{commit}").returncode != 0:
        pytest.skip("commit base ausente (clone raso)")
    for rel in ("data/bestiary.json", "data/world/fauna.json"):
        head = subprocess.run(
            ["git", "show", f"86cb7bb8:{rel}"], cwd=ROOT, capture_output=True, check=True
        ).stdout
        assert (
            hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            == hashlib.sha256(head.replace(b"\r\n", b"\n")).hexdigest()
            or (ROOT / rel).read_bytes() == head
        )
    assert json.loads(JSON_PATH.read_text(encoding="utf-8"))["version"] == 1
