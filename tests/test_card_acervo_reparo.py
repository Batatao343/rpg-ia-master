"""SPEC-335 R5 (Lote 0) e Lote 1: reparo do acervo e Arcanista Cinzento da onda 1."""

from collections import Counter

from services import card_effects as fx
from services import card_lint
from tests import spec330_equivalence as eq

RARIDADES = {"comum", "incomum", "rara", "abissal"}


def _legacy() -> list[dict]:
    return list(eq.legacy_cards().values())


def test_308_legadas_com_descricao_raridade_e_momento():
    legacy = _legacy()
    assert len(legacy) == 308
    for c in legacy:
        assert str(c.get("descricao") or "").strip(), c["id"]
        assert c.get("raridade") in RARIDADES, c["id"]
        assert str(c.get("momento") or "").strip(), c["id"]
        assert not any(ch.isdigit() for ch in c["momento"]), c["id"]


def test_raridade_acompanha_o_patamar():
    esperado = {
        "inicial": "comum",
        "avancado": "incomum",
        "superior": "incomum",
        "epico_i": "rara",
        "epico_ii": "rara",
        "lendario": "abissal",
        "mitico": "abissal",
        "apice": "abissal",
    }
    for c in _legacy():
        if c.get("classe") != "Inimigo":
            assert c["raridade"] == esperado[c["patamar"]], c["id"]


def test_80_cartas_de_tiers_5_plus_sem_texto_generico():
    t5 = [c for c in _legacy() if c.get("origem") == "tiers-5-plus"]
    assert len(t5) == 80
    for c in t5:
        assert not card_lint.errors(card_lint.check_voice(c)), c["id"]
        assert len(c["descricao"]) <= card_lint.MAX_CHARS_DESCRICAO, c["id"]
        assert "Consome Entropia e respeita a frequência" not in c["contrapartida"], c["id"]
    assert len({c["descricao"] for c in t5}) == 80
    assert len({c["contrapartida"] for c in t5}) == 80


def test_lint_recusa_frase_modelo_do_gerador_antigo():
    c = {
        "name": "Selo Frio",
        "descricao": "Selo Frio converte risco acumulado em uma decisão mecânica de fim de campanha.",
    }
    assert any("genérica" in i.message for i in card_lint.check_voice(c))


# ----------------------------------------------------------------- Lote 1 (Arcanista)
def _onda1() -> list[dict]:
    return [
        c
        for c in card_lint.load_pool()
        if c.get("onda") == 1 and c.get("classe") == "Arcanista Cinzento"
    ]


def test_lote1_arcanista_36_cartas_12_por_subclasse():
    cs = _onda1()
    assert len(cs) == 36
    assert Counter(c["subclasse"] for c in cs) == {
        "calibrado": 12,
        "descoberto": 12,
        "improvisador": 12,
    }
    assert len({c["id"] for c in cs}) == 36
    assert Counter(c["raridade"] for c in cs) == {
        "comum": 16,
        "incomum": 13,
        "rara": 5,
        "abissal": 2,
    }


def test_lote1_passa_no_lint_contra_o_acervo():
    pool = card_lint.load_pool()
    for c in _onda1():
        others = [o for o in pool if o["id"] != c["id"]]
        assert not card_lint.errors(card_lint.lint_card(c, others)), c["id"]
        assert fx.budget_error(c) is None, c["id"]


# R4: `momento` distinto por Postura. As Posturas abaixo ainda têm `momento` de MODELO
# (`momento_placeholder: true`), reescrito no lote de cada uma. A lista só pode ENCOLHER:
# ao entregar o lote de uma Postura, tire-a daqui (o teste passa a exigir 0 duplicata).
POSTURAS_COM_MOMENTO_PLACEHOLDER = {
    "Devoto do Abismo",
    "Sangromante",
    "Corruptor",
    "Médico de Campo",
    "Inimigo",
    "",  # Cartas de Virtude
}
MAX_PLACEHOLDERS = 255  # só pode diminuir (== no teste: baixe aqui ao reescrever)


def test_momento_distinto_por_postura_com_excecoes_que_so_encolhem():
    pool = [c for c in card_lint.load_pool() if c.get("momento")]
    placeholders = [c for c in pool if c.get("momento_placeholder")]
    assert len(placeholders) == MAX_PLACEHOLDERS
    assert not [c["id"] for c in placeholders if c.get("onda") is not None]
    assert {c.get("classe") for c in placeholders} <= POSTURAS_COM_MOMENTO_PLACEHOLDER
    por_postura: dict = {}
    for c in pool:
        if c.get("momento_placeholder") or str(c["id"]).startswith(("inf_", "bas_")):
            continue
        por_postura.setdefault(c.get("classe"), []).append(c)
    for postura, cs in por_postura.items():
        if postura in POSTURAS_COM_MOMENTO_PLACEHOLDER:
            continue
        momentos = [c["momento"] for c in cs]
        assert len(momentos) == len(set(momentos)), postura
        for i, a in enumerate(momentos):
            for b in momentos[i + 1 :]:
                assert card_lint.similarity(a, b) < card_lint.LIMIAR_MOMENTO, (postura, a, b)
