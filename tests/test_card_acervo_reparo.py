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


# ----------------------------------------------------------------- Lote 2 (Sangromante)
def _lote2() -> list[dict]:
    return [
        c for c in card_lint.load_pool() if c.get("onda") == 1 and c.get("classe") == "Sangromante"
    ]


def test_lote2_sangromante_36_cartas_12_por_subclasse_e_raridade_compensada():
    cs = _lote2()
    assert len(cs) == 36
    assert Counter(c["subclasse"] for c in cs) == {"exposto": 12, "avaro": 12, "silencioso": 12}
    assert len({c["id"] for c in cs}) == 36
    # P2-7: mais comuns e menos incomuns que o Lote 1 (16/13/5/2); alvo da R3 = 50/30/15/5.
    assert Counter(c["raridade"] for c in cs) == {
        "comum": 20,
        "incomum": 10,
        "rara": 4,
        "abissal": 2,
    }


def test_lote2_passa_no_lint_e_no_orcamento_e_legado_tem_momento_proprio():
    pool = card_lint.load_pool()
    for c in _lote2():
        others = [o for o in pool if o["id"] != c["id"]]
        assert not card_lint.errors(card_lint.lint_card(c, others)), c["id"]
        assert fx.budget_error(c) is None, c["id"]
    legado = [c for c in pool if c.get("classe") == "Sangromante" and c.get("onda") is None]
    assert len(legado) >= 53
    assert not [c["id"] for c in legado if c.get("momento_placeholder")]


# ----------------------------------------------------------------- Lote 3 (Devoto)
def _lote3() -> list[dict]:
    return [
        c
        for c in card_lint.load_pool()
        if c.get("onda") == 1 and c.get("classe") == "Devoto do Abismo"
    ]


def test_lote3_devoto_36_cartas_12_por_subclasse_e_raridade_20_10_4_2():
    cs = _lote3()
    assert len(cs) == 36
    assert Counter(c["subclasse"] for c in cs) == {"consagrado": 12, "zeloso": 12, "enlutado": 12}
    assert len({c["id"] for c in cs}) == 36
    assert all(c["id"].startswith("dev1_") for c in cs)
    assert Counter(c["raridade"] for c in cs) == {
        "comum": 20,
        "incomum": 10,
        "rara": 4,
        "abissal": 2,
    }


def test_lote3_passa_no_lint_e_no_orcamento_e_legado_tem_momento_proprio():
    pool = card_lint.load_pool()
    for c in _lote3():
        others = [o for o in pool if o["id"] != c["id"]]
        assert not card_lint.errors(card_lint.lint_card(c, others)), c["id"]
        assert fx.budget_error(c) is None, c["id"]
    legado = [c for c in pool if c.get("classe") == "Devoto do Abismo" and c.get("onda") is None]
    assert len(legado) >= 55
    assert not [c["id"] for c in legado if c.get("momento_placeholder")]


def test_lote3_licoes_da_revisao_do_lote2():
    """Reação com gatilho; sem `ativa`+buff_esquiva; Provocar nunca é o único ganho em solo;
    `escala` fora do principal de dano; Eco/condição não engolidos pela mesma da Carta."""
    for c in _lote3():
        effs = fx.normalize(c)
        if c["tipo"] == "reacao":
            assert c.get("gatilho"), c["id"]
        if c["tipo"] == "ativa":
            assert all(e["kind"] != "buff_esquiva" for e in effs), c["id"]
        solo = [e for e in effs if e["kind"] != "taunt"]
        assert solo, c["id"]  # taunt sozinho não vale em luta solo
        assert not card_lint.check_escala_principal(c), c["id"]
        assert not fx.keywords(c).get("eco"), c["id"]  # o Lote 3 não usa Eco


# ----------------------------------------------------------------- Lote 4 (Corruptor)
def _lote4() -> list[dict]:
    return [
        c for c in card_lint.load_pool() if c.get("onda") == 1 and c.get("classe") == "Corruptor"
    ]


def test_lote4_corruptor_36_cartas_12_por_subclasse_e_raridade_20_10_4_2():
    cs = _lote4()
    assert len(cs) == 36
    assert Counter(c["subclasse"] for c in cs) == {"biologia": 12, "alma": 12, "inorganica": 12}
    assert len({c["id"] for c in cs}) == 36
    assert all(c["id"].startswith("cor1_") for c in cs)
    assert Counter(c["raridade"] for c in cs) == {
        "comum": 20,
        "incomum": 10,
        "rara": 4,
        "abissal": 2,
    }


def test_lote4_passa_no_lint_e_no_orcamento_e_legado_tem_momento_proprio():
    pool = card_lint.load_pool()
    for c in _lote4():
        others = [o for o in pool if o["id"] != c["id"]]
        issues = card_lint.lint_card(c, others)
        assert not card_lint.errors(issues), c["id"]
        assert not [i for i in issues if i.level == "warn"], (c["id"], issues)
        assert fx.budget_error(c) is None, c["id"]
    legado = [c for c in pool if c.get("classe") == "Corruptor" and c.get("onda") is None]
    assert len(legado) >= 53
    assert not [c["id"] for c in legado if c.get("momento_placeholder")]


def test_lote4_licoes_da_revisao_dos_lotes_anteriores():
    """Reação com gatilho; sem `ativa`+buff_esquiva; sem Provocar/Eco; `escala` só em efeito
    extra; cor da roda (sem cura, sem Proteção/Vigília em aliado); a Marca do Abismo não é
    consumida pelo dano da própria Carta (o dano extra vem antes ou não existe)."""
    for c in _lote4():
        effs = fx.normalize(c)
        kinds = [e["kind"] for e in effs]
        if c["tipo"] == "reacao":
            assert c.get("gatilho"), c["id"]
            assert len(effs) == 1, c["id"]
        if c["tipo"] == "ativa":
            assert "buff_esquiva" not in kinds, c["id"]
        assert "taunt" not in kinds, c["id"]
        assert not fx.keywords(c).get("eco"), c["id"]
        assert not card_lint.check_escala_principal(c), c["id"]
        assert not {"cura", "estabilizar"} & set(kinds), c["id"]
        assert all(e.get("alvo") not in ("aliados",) for e in effs), c["id"]
        assert not card_lint.check_marca_dano(c), c["id"]  # Marca consumida pelo próprio dano
        assert not card_lint.check_revelar_publico(c), c["id"]
        assert not card_lint.check_reacao_folego(c), c["id"]


# ----------------------------------------------------------------- Lote 5 (Médico de Campo)
def _lote5() -> list[dict]:
    return [
        c
        for c in card_lint.load_pool()
        if c.get("onda") == 1 and c.get("classe") == "Médico de Campo"
    ]


def test_lote5_medico_36_cartas_12_por_subclasse_e_raridade_20_10_4_2():
    cs = _lote5()
    assert len(cs) == 36
    assert Counter(c["subclasse"] for c in cs) == {
        "cirurgiao_trincheira": 12,
        "boticario": 12,
        "cirurgiao_ferro": 12,
    }
    assert len({c["id"] for c in cs}) == 36
    assert all(c["id"].startswith("med1_") for c in cs)
    assert Counter(c["raridade"] for c in cs) == {
        "comum": 20,
        "incomum": 10,
        "rara": 4,
        "abissal": 2,
    }


def test_lote5_passa_no_lint_e_no_orcamento_e_legado_tem_momento_proprio():
    pool = card_lint.load_pool()
    for c in _lote5():
        others = [o for o in pool if o["id"] != c["id"]]
        issues = card_lint.lint_card(c, others)
        assert not card_lint.errors(issues), c["id"]
        assert not [i for i in issues if i.level == "warn"], (c["id"], issues)
        assert fx.budget_error(c) is None, c["id"]
    legado = [c for c in pool if c.get("classe") == "Médico de Campo" and c.get("onda") is None]
    assert len(legado) >= 52
    assert not [c["id"] for c in legado if c.get("momento_placeholder")]


def test_lote5_licoes_da_revisao_dos_lotes_anteriores():
    """Reação com gatilho e um só efeito; sem `ativa`+buff_esquiva; sem Provocar/Eco/Rachadura;
    `escala` só em efeito extra; dano ate o teto da roda; cada Carta vale em luta solo (algum
    efeito que não depende de aliado); nenhuma condição de estatística repetida na mesma Carta
    (a 2ª seria engolida pela 1ª, que leva o nome da Carta)."""
    # kinds cuja condição leva o NOME da Carta: dois deles na mesma Carta, o 2º é engolido.
    nomeadas = {"protecao", "buff_defesa", "buff_acerto", "buff_dano", "vantagem", "dot", "marca"}
    for c in _lote5():
        effs = fx.normalize(c)
        kinds = [e["kind"] for e in effs]
        if c["tipo"] == "reacao":
            assert c.get("gatilho"), c["id"]
            assert len(effs) == 1, c["id"]
            assert fx.custo_folego(c) >= 1, c["id"]
        if c["tipo"] == "ativa":
            assert "buff_esquiva" not in kinds, c["id"]
        assert not {"taunt", "rachadura"} & set(kinds), c["id"]
        assert not fx.keywords(c).get("eco"), c["id"]
        assert not card_lint.check_escala_principal(c), c["id"]
        assert not card_lint.check_marca_dano(c), c["id"]
        assert not card_lint.check_revelar_publico(c), c["id"]
        assert not card_lint.check_reacao_folego(c), c["id"]
        assert all(e.get("kind") != "mover_alvo_zona" for e in effs), c["id"]
        assert not card_lint.check_controle_duracao(c), c["id"]
        if fx.custo_folego(c) == 0:  # Fôlego 0 só com `cena` (efeito grátis a cada turno é demais)
            assert c["frequencia"] == "cena", c["id"]
        if c["raridade"] == "incomum" and "dano" in kinds:  # híbrido de golpe: `cena`, não `turno`
            assert c["frequencia"] == "cena", c["id"]
        assert sum(1 for k in kinds if k in nomeadas) <= 1, c["id"]
        # luta solo: estabilizar sozinho só vale com aliado caído (sem aliado, é Carta morta).
        assert set(kinds) != {"estabilizar"}, c["id"]
        # primário legado ignora `alvo`: área só em efeito extra.
        prim = fx.primary_effect(c)
        assert prim is None or prim.get("alvo") not in ("aliados", "inimigos"), c["id"]


# R4: `momento` distinto por Postura. As Posturas abaixo ainda têm `momento` de MODELO
# (`momento_placeholder: true`), reescrito no lote de cada uma. A lista só pode ENCOLHER:
# ao entregar o lote de uma Postura, tire-a daqui (o teste passa a exigir 0 duplicata).
POSTURAS_COM_MOMENTO_PLACEHOLDER = {
    "Inimigo",
    "",  # Cartas de Virtude
}
MAX_PLACEHOLDERS = 45  # só pode diminuir (== no teste: baixe aqui ao reescrever)


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
