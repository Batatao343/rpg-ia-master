"""SPEC-360 R1-R6: schema, lint E1-E16 e cobertura do bloco de fauna."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from services import fauna_lint as fl

FIX = Path(__file__).parent / "fixtures" / "spec360" / "boa.yaml"


def _refs(**over) -> fl.Refs:
    base = dict(
        region="regiao_teste",
        fichas={
            "mon_alfa": {
                "id": "mon_alfa",
                "nome": "Garra Seca",
                "familia": "besta_entropia",
                "habitat": ["n1", "n2"],
                "contra_jogo": "Fogo e distância.",
            },
            "mon_beta": {
                "id": "mon_beta",
                "nome": "Olho de Vidro",
                "familia": "corpo_reescrito",
                "habitat": ["n2"],
                "contra_jogo": "Quebrar o vidro.",
            },
        },
        familias={"besta_entropia": "Besta Torta", "corpo_reescrito": "Reescrito"},
        legacy=frozenset({"enemy_gama", "enemy_boss_delta"}),
        bestiary={
            "mon_alfa": {"name": "Garra Seca", "regions": ["regiao_teste"], "boss": False},
            "mon_beta": {"name": "Olho de Vidro", "regions": ["regiao_teste"], "boss": False},
            "enemy_gama": {"name": "Cão Pardo", "regions": ["regiao_teste"], "boss": False},
            "enemy_boss_delta": {
                "name": "Rocha Andante",
                "regions": ["regiao_teste"],
                "boss": True,
            },
            "enemy_vizinho": {"name": "Vizinho", "regions": ["regiao_adj"], "boss": False},
            "enemy_longe": {"name": "Longe", "regions": ["outra"], "boss": False},
        },
        region_nodes=frozenset({"n1", "n2", "n3"}),
        periods=("Amanhecer", "Manhã", "Tarde", "Anoitecer", "Noite"),
        seasons=("primavera", "verao", "outono", "inverno"),
        weather_states=frozenset({"limpo", "nublado", "chuva"}),
        adjacency=frozenset({"regiao_adj"}),
        vagos=("presenca maligna", "algo estranho", "energia sombria"),
        leak_phrases=("lider da mao sombria",),
    )
    base.update(over)
    return fl.Refs(**base)


def _doc() -> dict:
    return yaml.safe_load(FIX.read_text(encoding="utf-8"))


def _codes(errs: list[str]) -> set[str]:
    return {e.split()[0].rstrip(":") for e in errs}


def test_fixture_boa_passa():
    assert fl.lint_region(_doc(), _refs()) == []


def _m(doc, cid, path, value):
    node = doc["criaturas"][cid]
    for k in path[:-1]:
        node = node.setdefault(k, {})
    node[path[-1]] = value


MUTATIONS = {
    "E1": lambda d: _m(d, "mon_alfa", ["ecologia", "cor"], "azul"),
    "E2": lambda d: _m(d, "mon_alfa", ["ecologia", "horario"], ["Meia-noite"]),
    "E3": lambda d: _m(d, "mon_alfa", ["ecologia", "estacoes"], {"outono": 4}),
    "E4": lambda d: _m(d, "mon_alfa", ["ecologia", "territorio"], ["n3"]),
    "E5": lambda d: _m(d, "mon_alfa", ["ecologia", "presas"], ["enemy_inexistente"]),
    "E6": lambda d: _m(d, "mon_alfa", ["ecologia", "presas"], ["enemy_boss_delta"]),
    "E7": lambda d: _m(d, "enemy_gama", ["ecologia", "presas"], ["mon_alfa"]),
    "E8": lambda d: _m(d, "mon_alfa", ["ecologia", "presas"], ["enemy_longe"]),
    "E9": lambda d: _m(d, "mon_alfa", ["sinais", "som"], None),
    "E10": lambda d: _m(d, "mon_alfa", ["sinais", "rastro"], "Uma GARRA sêca marcou o barro."),
    "E11": lambda d: _m(d, "mon_alfa", ["sinais", "som"], "Há uma presença maligna no ar."),
    "E12": lambda d: _m(
        d,
        "mon_beta",
        ["sinais", "resto"],
        "Um couro de bode virado do avesso, raspado até ficar fino.",
    ),
    "E13": lambda d: _m(d, "mon_alfa", ["contra_jogo"], "Outro contra-jogo."),
    "E14": lambda d: _m(d, "enemy_gama", ["sinais", "antecedencia"], "imediato"),
    "E15": lambda d: _m(d, "mon_alfa", ["ecologia", "presas"], []),
    "E16": lambda d: _m(
        d, "enemy_gama", ["sinais", "rumor"], "dizem que o lider da Mão Sombria passou"
    ),
}


@pytest.mark.parametrize("rule", sorted(MUTATIONS, key=lambda r: int(r[1:])))
def test_fixture_ruim_por_regra(rule):
    doc = copy.deepcopy(_doc())
    MUTATIONS[rule](doc)
    errs = fl.lint_region(doc, _refs())
    assert rule in _codes(errs), errs


def test_nome_no_sinal_reprovado():
    """E10 com acento e caixa trocados, plural e token da familia em jogo."""
    cases = (
        ("mon_alfa", "garrás SECAS no chão"),
        ("mon_alfa", "a BÉSTA passou por aqui"),
        ("mon_alfa", "pegadas de alfa"),
        ("mon_beta", "um olho de vídro na lama"),
        ("mon_beta", "rastro de reescritos"),
        ("enemy_gama", "pelo PARDO no espinho"),
    )
    for cid, text in cases:
        doc = copy.deepcopy(_doc())
        _m(doc, cid, ["sinais", "marca"], text)
        assert any(e.startswith(f"E10 {cid}") for e in fl.lint_region(doc, _refs())), text


def test_jaccard_reskin_pego():
    assert fl.jaccard("Um couro de bode virado do avesso", "Couro de bode virado ao avesso") >= 0.5
    assert fl.jaccard("Três riscos fundos na terra", "Cacos leitosos no pátio") < 0.5


def test_contra_jogo_igual_ficha():
    doc = copy.deepcopy(_doc())
    _m(doc, "mon_beta", ["contra_jogo"], "Quebrar o vidro!")
    assert any(e.startswith("E13 mon_beta") for e in fl.lint_region(doc, _refs()))


def test_cobertura_falta_e_sobra():
    doc = copy.deepcopy(_doc())
    del doc["criaturas"]["enemy_gama"]
    doc["criaturas"]["enemy_extra"] = copy.deepcopy(_doc()["criaturas"]["enemy_boss_delta"])
    errs = fl.lint_region(doc, _refs())
    assert any(e.startswith("R2") and "enemy_gama" in e and "enemy_extra" in e for e in errs)


def test_territorio_default_habitat():
    refs = _refs()
    assert fl.effective_territory("mon_beta", {}, refs) == ["n2"]
    assert fl.effective_territory("enemy_gama", {}, refs) == ["n1", "n2", "n3"]


@pytest.mark.parametrize("region", fl.covered_regions())
def test_cobertura_regiao(region):
    """R2: as chaves do arquivo real = fichas da regiao + legado `valoria` da regiao."""
    refs = fl.load_refs(region)
    doc = yaml.safe_load((fl.FAUNA_DIR / f"{region}.yaml").read_text(encoding="utf-8"))
    assert set(doc["criaturas"]) == set(refs.fichas) | set(refs.legacy)


@pytest.mark.parametrize("region", fl.covered_regions())
def test_regiao_real_sem_erro(region):
    assert fl.lint_file(region) == []


def test_validate_all_inclui_fauna():
    from services import content_validator as cv

    assert any(f.validator == "fauna" for f in cv.validate_fauna(regions=["regiao_inexistente"]))
