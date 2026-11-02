"""SPEC-361 Etapa 2 — catálogo de modificadores e variante sem LLM (R5-R8)."""

import re
import time

import pytest

from agents.bestiary import template_by_id
from services import creature_variants as cv
from services.discovery import normalize_bestiary_id


def test_catalogo_lint():
    mods = cv.catalogo()
    assert 12 <= len(mods) <= 16
    assert cv.lint_catalogo() == []


def test_catalogo_lint_pega_erros():
    ruim = dict(cv.modificador_por_id("mente_unica"))
    ruim = {
        **ruim,
        "id": "ruim",
        "texto": {
            "epiteto": "Alfa",
            "frase": "sem base 3",
            "telegrafo": "sem nome",
            "aparencia": "um troll",
        },
        "efeitos": {"categoria_delta": 2, "papel_tatico": "xx", "padrao": ["voar", "ataque"]},
    }
    codigos = {i.code for i in cv.lint_catalogo([*cv.catalogo()[:12], ruim])}
    assert {"U5", "R20", "U8", "CAT", "ENUM"} <= codigos


@pytest.mark.parametrize(
    "texto", ["lacaio mente-colmeia", "uma colmeia de bichos", "pensam como um só"]
)
def test_detecta_mente_unica(texto):
    assert cv.detectar_modificador(texto)["id"] == "mente_unica"


def test_detecta_nada_em_texto_neutro():
    assert cv.detectar_modificador("um bandido na estrada") is None
    assert cv.detectar_modificador("") is None


def test_base_zhur_saltador():
    mod = cv.modificador_por_id("mente_unica")
    assert (
        cv.escolher_base(mod, "deserto_zhur", nucleo="lacaio", categoria="lacaio")
        == "mon_saltador_de_palafita"
    )


def _variante(mod_id="mente_unica", base="mon_saltador_de_palafita"):
    return cv.aplicar_variante(template_by_id(base), cv.modificador_por_id(mod_id))


def test_variante_sem_llm(monkeypatch):
    import llm_setup

    def boom(*a, **k):
        raise AssertionError("variante não chama LLM")

    monkeypatch.setattr(llm_setup, "get_llm", boom)
    t = _variante()
    assert t["id"] == "mon_saltador_de_palafita__v_mente_unica"
    assert t["name"] == "Saltador de Palafita da Mente Única"
    assert t["tactical_profile"]["padrao"] == ["reforco_proprio", "ataque_multiplo"]
    assert "{nome}" in t["tactical_profile"]["assinatura"]["telegrafo"]
    assert cv.contagem_min(t) == 3


def test_variante_latencia():
    base = template_by_id("mon_saltador_de_palafita")
    mod = cv.modificador_por_id("mente_unica")
    tempos = []
    for _ in range(40):
        t0 = time.perf_counter()
        cv.aplicar_variante(base, mod)
        tempos.append(time.perf_counter() - t0)
    assert sorted(tempos)[int(len(tempos) * 0.95) - 1] < 0.05


def test_variante_nao_passa_de_elite():
    assert cv._sobe("lacaio", 1) == "padrao"
    assert cv._sobe("elite", 1) == "elite"
    assert cv._sobe("chefe", 1) == "chefe"
    # praga_terminal sobe a categoria e recalcula os números pelo Python
    base = template_by_id("mon_saltador_de_palafita")
    t = cv.aplicar_variante(base, cv.modificador_por_id("praga_terminal"))
    assert t["categoria"] == "padrao" and t["type"] == "Standard"
    assert t["max_vitalidade"] >= 1 and isinstance(t["virtudes"], dict)


def test_variante_archetype_id_base():
    from agents.combat import _instances

    t = _variante()
    inst = _instances(t, 2, {}, None)
    assert all(normalize_bestiary_id(i) == "mon_saltador_de_palafita" for i in inst)
    assert t["variant_of"] == "mon_saltador_de_palafita"


def test_variante_texto_sem_digito_e_sem_u5():
    for mod in cv.catalogo():
        t = cv.aplicar_variante(template_by_id("mon_saltador_de_palafita"), mod)
        assert cv.lint_variante(t, mod) == [], mod["id"]
        for campo in ("name", "description", "appearance"):
            assert not re.search(r"\d", t[campo]), (mod["id"], campo)


def test_variante_deterministica():
    a, b, c = _variante(), _variante(), _variante()
    assert a == b == c
