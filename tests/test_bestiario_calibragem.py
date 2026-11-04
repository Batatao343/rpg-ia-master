"""SPEC-394: recalibragem das criaturas que derivaram depois da SPEC-387.

Le so os artefatos gravados em ``docs/spec394/``: o ``ok`` que o ``arena.py`` (congelado)
gravou e os hashes de ``snapshot.py``. Nao roda a arena. Faltou artefato -> falha, nao pula.
Exceções nominais (D2/D3) constam em ``docs/spec394/RELATORIO.md`` como linha ``EXCECAO <id>``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "spec394"
SETE = {
    "mon_anzolado_da_casa",
    "mon_lacrador_de_saidas",
    "mon_bracos_de_tenaz",
    "mon_armador_de_fosso",
    "mon_portao_que_morde",
    "mon_carregador_de_ganchos",
    "mon_escuta_do_sinal",
}
FAIXA = (0.45, 0.85)


def _json(nome: str) -> dict:
    p = D / nome
    assert p.exists(), f"artefato ausente: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _f_ids() -> set[str]:
    """F = ids sem ok na medicao da Etapa 0 (R2)."""
    cri = _json("base.json")["criaturas"]
    return {i for i, c in cri.items() if not c["ok"]}


def _excecoes() -> set[str]:
    p = D / "RELATORIO.md"
    assert p.exists(), f"artefato ausente: {p}"
    return set(re.findall(r"^EXCECAO (mon_\w+)", p.read_text(encoding="utf-8"), re.M))


def test_base_394_tinha_derivadas_fora():
    cri = _json("base.json")["criaturas"]
    assert set(cri) == SETE
    assert _f_ids(), "a base ja estava toda na faixa: o portao nao discrimina"
    assert _f_ids() <= SETE


def test_derivadas_387_com_ok_na_arena():
    final = _json("arena-final.json")["criaturas"]
    exc = _excecoes()
    assert exc <= _f_ids()
    for bid in _f_ids() - exc:
        assert bid in final, f"{bid} sem medicao final"
        cells = final[bid]["cells"]
        assert final[bid]["ok"], f"{bid} fora da faixa: {cells}"
        assert all(FAIXA[0] <= w <= FAIXA[1] for w in cells.values()), cells


def test_snapshot_fora_de_F_identico():
    antes = _json("base-snapshot.json")
    depois = _json("final-snapshot.json")
    assert set(depois) == set(antes) - _f_ids(), "final-snapshot deve excluir exatamente F"
    mudados = sorted(i for i in depois if antes[i] != depois[i])
    assert not mudados, mudados


def test_ajustes_registrados():
    aj = yaml.safe_load(
        (ROOT / "data/bestiario/mecanica/_ajustes.yaml").read_text(encoding="utf-8")
    )
    aj = aj.get("ajustes", aj)
    for bid in _f_ids() - _excecoes():
        e = aj.get(bid) or {}
        assert e.get("arena"), f"{bid} sem leitura da arena em _ajustes.yaml"
        for dial in ("corpo", "dano", "forca", "sig"):
            assert -7 <= int(e.get(dial, 0)) <= 7, (bid, dial)
