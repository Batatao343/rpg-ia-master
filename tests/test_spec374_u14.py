"""SPEC-374 U14 — coerência eixo × corpo (rejeição do curador a "Ouvido de Sal")."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from services import axis_text, card_lint
from services import creature_gen as cg
from tests.test_spec374_eixos import REGIAO, _gen, _livres, _p, _Script, _usar

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def ouvido() -> dict:
    doc = yaml.safe_load((ROOT / "docs/spec374/pool-export-pendente.yaml").read_text("utf-8"))
    return doc["entradas"][0]["ficha"]


def test_ouvido_de_sal_reprova(ouvido):
    achados = axis_text.incoerencias(ouvido)
    assert ("material", "carne_exposta", "domina:sal_mineral") in achados
    assert ("locomocao", "nada", "ausente") in achados
    issues = cg.lint_runtime(ouvido, "deserto_zhur", runtime=[])
    u14 = [i for i in issues if i.code == "U14"]
    assert u14 and "sal_mineral" in u14[0].message and "linha_eixos" in u14[0].message


def test_corpo_coerente_passa(ouvido):
    certa = {**ouvido, "anatomia": {**ouvido["anatomia"], "material": "sal_mineral"}}
    assert [m for m in axis_text.incoerencias(certa) if m[0] == "material"] == []


def test_taxa_de_falso_positivo_nas_aprovadas():
    """Conservadora: <= 4 % das fichas aprovadas (curadoria 349 + pool) reprovam em U14."""
    fichas = list(cg.fichas_aprovadas().values())
    assert len(fichas) >= 250
    ruins = [f["id"] for f in fichas if axis_text.incoerencias(f)]
    assert len(ruins) / len(fichas) <= 0.04, (len(ruins), ruins)


def test_percepcao_e_plano_nao_entram():
    f = {
        "anatomia": {"percepcao": "visao", "plano_corporal": "radial", "escala": "enorme"},
        "anatomia_texto": "x",
        "silhueta": "Um vulto sem olho nenhum.",
    }
    assert axis_text.incoerencias(f) == []


def test_reparar_eixos_troca_linha_em_u14(ouvido):
    livres = [
        {**_livres()[0], "material": "carne_exposta"},
        {**_livres()[1], "material": "sal_mineral", "locomocao": "ancorada"},
    ]
    ficha = {**ouvido, "id": "mon_x_rt_abcdef"}
    ficha["anatomia"] = {
        **ouvido["anatomia"],
        **{e: livres[0][e] for e in livres[0] if e != "papel_tatico"},
    }
    ficha["papel_tatico"] = livres[0]["papel_tatico"]
    antes = [i for i in cg.checar_coerencia_eixos(ficha)]
    assert antes and all(i.code == "U14" for i in antes)
    nova = cg.reparar_eixos(ficha, antes, livres, lambda f: cg.checar_coerencia_eixos(f))
    assert nova is not None and nova["anatomia"]["material"] == "sal_mineral"
    assert nova["anatomia"]["texto"] == ouvido["anatomia"]["texto"]  # a prosa fica


def test_u14_conta_no_lint_primeira_e_reparo_nao(monkeypatch):
    corpo = (
        "Caroço de sal branco grudado no fundo da cisterna, crosta de sal que estala. "
        "Seis hastes de sal com salmoura na ponta. Raízes de sal prendem o corpo na pedra."
    )
    base = _livres()
    livres = [{**base[0], "material": "carne_exposta"}, {**base[1], "material": "sal_mineral"}]
    monkeypatch.setattr(cg, "eixos_livres", lambda *a, **k: livres)
    llm = _Script([cg.FichaCriaturaGerada(**_gen(linha_eixos=1, anatomia_texto=corpo))])
    _usar(monkeypatch, llm)
    ficha, info = cg.gerar_nova(_p(), cg.Decisao("nova"), bestiary={}, runtime=[], lore="")
    assert info["lint_primeira"] is False  # U14 conta no lint_primeira (é a 1ª leitura)
    if ficha is not None:
        assert ficha["anatomia"]["material"] == "sal_mineral"
        assert "U2U3-eixos-reparados" in info["codigos"]
    assert any(m.startswith("U14:") for m in info["lint_primeira_msgs"])


def test_correcao_explica_u14():
    msgs = cg.montar_prompt_correcao(
        _p(),
        _gen(),
        cg.checar_coerencia_eixos(
            {
                "id": "x",
                "anatomia": {"material": "carne_exposta"},
                "anatomia_texto": "sal sal salgado salmoura",
                "silhueta": "sal",
            }
        )
        or [card_lint.Issue("error", "U14", "x")],
        ocupados="",
        eixos=_livres(),
    )
    assert "U2/U3/U14" in str(msgs[0].content)


def test_composicao_usa_o_lugar_do_texto(ouvido):
    spec = importlib.util.spec_from_file_location(
        "pool_revisao_374", ROOT / "scripts/bestiario/pool_revisao.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    comp = mod._composicao(ouvido, REGIAO)
    assert comp.startswith("Cisterna de pedra (Deserto de Zhur)")
    assert "Mar de Vidro" not in comp
    sem_lugar = {**ouvido, "arte": {}, "silhueta": "Vulto.", "description": "Vulto."}
    assert "Mar de Vidro" in mod._composicao(sem_lugar, REGIAO)  # sem lugar no texto: habitat
