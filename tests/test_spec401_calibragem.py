"""SPEC-401: recalibragem de odre, armador e escuta.

Le so os artefatos gravados em ``docs/spec401/`` (o ``ok`` que o ``arena.py`` congelado gravou e
os hashes de ``docs/spec394/snapshot.py``). Nao roda a arena. Faltou artefato -> falha.
Excecoes nominais (D1) constam em ``docs/spec401/RELATORIO.md`` como linha ``EXCECAO <id>``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "spec401"
TRES = {"mon_odre_de_oleo", "mon_armador_de_fosso", "mon_escuta_do_sinal"}
FAIXA = (0.45, 0.85)
sys.path.insert(0, str(ROOT / "tests"))


def _json(nome: str) -> dict:
    p = D / nome
    assert p.exists(), f"artefato ausente: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _excecoes() -> set[str]:
    p = D / "RELATORIO.md"
    assert p.exists(), f"artefato ausente: {p}"
    return set(re.findall(r"^EXCECAO (mon_\w+)", p.read_text(encoding="utf-8"), re.M))


def _ajustes(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc.get("ajustes", doc)


def test_base_tinha_fora_e_so_os_tres():
    cri = _json("base.json")["criaturas"]
    assert set(cri) == TRES
    assert any(not c["ok"] for c in cri.values()), "a base ja estava na faixa"


def test_fechados_com_ok_na_arena_e_na_confirmacao():
    exc = _excecoes()
    assert exc <= TRES
    for nome in ("arena-final.json", "confirmacao-40-119.json"):
        cri = _json(nome)["criaturas"]
        assert set(cri) == TRES
        for bid in TRES - exc:
            cells = cri[bid]["cells"]
            assert cri[bid]["ok"], f"{nome}: {bid} fora da faixa: {cells}"
            assert all(FAIXA[0] <= w <= FAIXA[1] for w in cells.values()), cells


def test_so_os_tres_mudaram_de_dial():
    from test_spec373_artefatos import ids_com_dial_mudado

    base = _ajustes(D / "ajustes-base.yaml")
    pos = _ajustes(ROOT / "data/bestiario/mecanica/_ajustes.yaml")
    mudados = ids_com_dial_mudado(base, pos)
    assert mudados <= TRES, sorted(mudados - TRES)
    assert mudados, "nenhum dial dos tres mudou"


def test_snapshot_das_demais_identico():
    antes = _json("base-snapshot.json")
    depois = _json("final-snapshot.json")
    assert set(depois) == set(antes) - TRES, "final-snapshot deve excluir exatamente os tres"
    mudados = sorted(i for i in depois if antes[i] != depois[i])
    assert not mudados, mudados


def test_ajustes_registrados():
    aj = _ajustes(ROOT / "data/bestiario/mecanica/_ajustes.yaml")
    for bid in TRES:
        e = aj.get(bid) or {}
        assert e.get("arena"), f"{bid} sem leitura da arena em _ajustes.yaml"
        for dial in ("corpo", "dano", "forca", "sig"):
            assert -7 <= int(e.get(dial, 0)) <= 7, (bid, dial)
