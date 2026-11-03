"""SPEC-370 R11: `ecologia.suprime` (F-16) e as regras E17/E18 do lint."""

from __future__ import annotations

import pytest

from scripts.fauna import build
from services import fauna
from services import fauna_lint as fl


def _ctx() -> fauna.EcoCtx:
    return fauna.EcoCtx(
        location_id="", region_id="nova_arcadia", period=None, season=None, turn=100
    )


@pytest.fixture
def _sup(monkeypatch):
    monkeypatch.setattr(fauna, "_in_region", lambda *_a: True)
    monkeypatch.setattr(fauna, "_suppressed", lambda cid, _ctx: cid == "A")


def test_suprime_libera_sem_fome(_sup):
    # A (supressor) foi cacado: B, que A suprime, ganha PRESA_LIBERADA
    b = {"ecologia": {"horario": []}, "suprimidos_por": ["A"], "predadores": []}
    f, why = fauna.eco_multiplier(b, _ctx())
    assert "presa_liberada" in why and f == pytest.approx(fauna.const("PRESA_LIBERADA"))
    # o inverso: o supressor A nao fica faminto por causa de B
    a = {"ecologia": {"horario": [], "suprime": ["A"]}, "predadores": []}
    f, why = fauna.eco_multiplier(a, _ctx())
    assert "predador_faminto" not in why and f == 1.0


def test_presas_continua_dando_fome(_sup):
    a = {"ecologia": {"horario": [], "presas": ["A"]}, "predadores": []}
    assert "predador_faminto" in fauna.eco_multiplier(a, _ctx())[1]


def test_f16_migrado_no_json():
    sold = fauna.entry("enemy_soldado_legiao_ferro")
    assert sold["ecologia"]["suprime"] == ["enemy_degolador_mao_sombria"]
    assert sold["ecologia"]["presas"] == []
    deg = fauna.entry("enemy_degolador_mao_sombria")
    assert "enemy_soldado_legiao_ferro" in deg["suprimidos_por"]
    assert "enemy_soldado_legiao_ferro" not in deg["predadores"]
    assert "suprime" not in fauna.entry("mon_porca_da_queda")["ecologia"]  # so quando existe


def test_build_json_fresco_com_suprime():
    assert build.is_fresh()


# ----------------------------------------------------------------------------- lint


def _refs(hub: str = "hub") -> fl.Refs:
    ids = ("A", "B", "C", "D")
    return fl.Refs(
        region="r",
        fichas={},
        legacy=frozenset(ids),
        bestiary={c: {"name": c, "regions": ["r"], "boss": False} for c in ids},
        region_nodes=frozenset({"hub", "n2"}),
        periods=("Noite",),
        seasons=("verao",),
        hub=hub,
    )


def _entry(ante: str = "cedo", **eco) -> dict:
    return {
        "fonte": "legado",
        "ecologia": {"horario": ["Noite"], **eco},
        "sinais": {"antecedencia": ante},
        "contra_jogo": "x",
        "autor": "t",
        "revisao": "pendente",
    }


def _errs(crit: dict, refs: fl.Refs, prefix: str) -> list[str]:
    out = fl.lint_region({"regiao": "r", "criaturas": crit}, refs)
    return [e for e in out if e.startswith(prefix)]


def test_suprime_no_e15():
    sem = {c: _entry() for c in "ABCD"}
    assert _errs(sem, _refs(), "E15")
    com = {"A": _entry(suprime=["B"]), "B": _entry(), "C": _entry(suprime=["D"]), "D": _entry()}
    assert not _errs(com, _refs(), "E15")


def test_e17_ciclo():
    crit = {"A": _entry(suprime=["B"]), "B": _entry(suprime=["A"]), "C": _entry(), "D": _entry()}
    assert any("ciclo de suprime" in e for e in _errs(crit, _refs(), "E17"))


def test_e17_presa_e_suprime_juntos():
    crit = {"A": _entry(presas=["B"], suprime=["B"]), "B": _entry(), "C": _entry(), "D": _entry()}
    assert any("presas e suprime" in e for e in _errs(crit, _refs(), "E17"))


def test_e17_alvo_inexistente_ou_si_mesmo():
    crit = {"A": _entry(suprime=["A", "ZZZ"]), "B": _entry(), "C": _entry(), "D": _entry()}
    errs = _errs(crit, _refs(), "E5")
    assert any("propria criatura" in e for e in errs) and any("ZZZ" in e for e in errs)


def test_e18_imediato_no_hub():
    ruim = {c: _entry("imediato", territorio=["hub"]) for c in "ABC"}
    ruim["D"] = _entry()
    assert _errs(ruim, _refs(), "E18")
    boa = {c: _entry("imediato", territorio=["hub"]) for c in "AB"}
    boa["C"] = _entry("imediato", territorio=["n2"])
    boa["D"] = _entry()
    assert not _errs(boa, _refs(), "E18")
    assert not _errs(ruim, _refs(hub=""), "E18")  # sem no raiz com o id da regiao: nao se aplica
