"""SPEC-335 R5 (Lote 0), Lotes 1-6 (Posturas e neutras) e tronco do nível 1: acervo da onda 1."""

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


def test_pool_inteiro_sem_descricao_vazia_ou_generica():
    """Critério da SPEC-335: 0 descrições vazias/genéricas em todo o pool."""
    pool = card_lint.load_pool()
    assert len(pool) > 500
    for c in pool:
        ruins = [
            i.message
            for i in card_lint.check_voice(c)
            if "vazia" in i.message or "genérica" in i.message
        ]
        assert not ruins, (c["id"], ruins)


def test_lint_recusa_descricao_vazia():
    for desc in ("", "   ", None):
        c = {"name": "Selo Frio", "descricao": desc}
        assert any("vazia" in i.message for i in card_lint.check_voice(c))


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
        if c.get("onda") == 1 and c.get("classe") == "Arcanista Cinzento" and c.get("subclasse")
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
        c
        for c in card_lint.load_pool()
        if c.get("onda") == 1 and c.get("classe") == "Sangromante" and c.get("subclasse")
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
        if c.get("onda") == 1 and c.get("classe") == "Devoto do Abismo" and c.get("subclasse")
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
        c
        for c in card_lint.load_pool()
        if c.get("onda") == 1 and c.get("classe") == "Corruptor" and c.get("subclasse")
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
        if c.get("onda") == 1 and c.get("classe") == "Médico de Campo" and c.get("subclasse")
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


# R4: `momento` distinto por classe. Não há mais `momento_placeholder` no pool (Lote 0 fechado).


def test_momento_distinto_por_classe_sem_placeholder():
    pool = [c for c in card_lint.load_pool() if c.get("momento")]
    assert not [c["id"] for c in card_lint.load_pool() if c.get("momento_placeholder")]
    por_postura: dict = {}
    for c in pool:
        if str(c["id"]).startswith(("inf_", "bas_")):
            continue
        por_postura.setdefault(c.get("classe"), []).append(c)
    for postura, cs in por_postura.items():
        momentos = [c["momento"] for c in cs]
        assert len(momentos) == len(set(momentos)), postura
        for i, a in enumerate(momentos):
            for b in momentos[i + 1 :]:
                assert card_lint.similarity(a, b) < card_lint.LIMIAR_MOMENTO, (postura, a, b)


# ----------------------------------------------------------------- Lote 6 (40 neutras de Valoria, R2)
POSTURAS = (
    "Devoto do Abismo",
    "Sangromante",
    "Corruptor",
    "Arcanista Cinzento",
    "Médico de Campo",
)
# region_id do mapa (data/world_map.json) onde as neutras regionais podem sair no espólio.
REGIOES_NEUTRAS = {"nova_arcadia", "skallgard", "brekmar", "montanhas_afiadas"}


def _neutras() -> list[dict]:
    return [c for c in card_lint.load_pool() if c.get("classe") == "Neutra"]


def test_lote6_40_neutras_raridade_20_12_6_2_e_regioes():
    cs = _neutras()
    assert len(cs) == 40
    assert len({c["id"] for c in cs}) == 40
    assert all(c["id"].startswith("neu1_") and c.get("neutra") is True for c in cs)
    assert all(not c.get("subclasse") and c.get("onda") == 1 for c in cs)
    assert Counter(c["raridade"] for c in cs) == {
        "comum": 20,
        "incomum": 12,
        "rara": 6,
        "abissal": 2,
    }
    regioes = Counter(c.get("regiao") for c in cs)
    assert set(regioes) - {None} == REGIOES_NEUTRAS  # as regiões do R2 estão representadas
    assert regioes[None] >= 6  # itens gerais (lore_nova/items.txt): saem em qualquer lugar


def test_lote6_origem_lore_e_um_id_real_do_codex():
    from services import content_validator as cv

    ids = {str(fm.get("id")) for _p, fm, _b in cv._parse_codex(cv.CODEX_DIR) if fm.get("id")}
    assert ids
    for c in _neutras():
        assert c.get("origem_lore") in ids, (c["id"], c.get("origem_lore"))
    lore = {c["origem_lore"] for c in _neutras()}
    # Kahen, Saídas Baixas e Ermo têm âncora própria no codex
    assert {"poder_kahen", "bandos_orc_saidas_baixas", "renegados_ermo"} <= lore


def test_validador_recusa_origem_lore_invalida_e_neutra_sem_lore(tmp_path):
    import json

    from services import content_validator as cv

    cards_dir = tmp_path / "cards"
    codex_dir = tmp_path / "codex"
    cards_dir.mkdir()
    codex_dir.mkdir()
    (codex_dir / "a.md").write_text(
        "---\nid: lugar_real\ntype: location\nname: A\naliases: []\ntags: []\nvisibility: public\n"
        "---\n\nx\n",
        encoding="utf-8",
    )
    base = next(c for c in _neutras() if c["id"] == "neu1_na_espada_da_legiao")
    ruim = dict(base, id="neu1_zz_ruim", name="Ruim Zero", origem_lore="id_que_nao_existe")
    sem = {k: v for k, v in base.items() if k != "origem_lore"}
    sem.update(id="neu1_zz_sem", name="Sem Lore Zero")
    ok = dict(base, id="neu1_zz_ok", name="Bom Zero", origem_lore="lugar_real")
    (cards_dir / "n.json").write_text(json.dumps({"cards": [ruim, sem, ok]}), encoding="utf-8")
    msgs: dict[str, str] = {}
    for f in cv.validate_cards(str(cards_dir)):
        if f.severity == "error":
            msgs[f.entity_id] = msgs.get(f.entity_id, "") + " | " + f.message
    assert "origem_lore" in msgs.get("neu1_zz_ruim", "")
    assert "origem_lore" in msgs.get("neu1_zz_sem", "")
    assert "origem_lore" not in msgs.get("neu1_zz_ok", "")


def test_lote6_passa_no_lint_e_no_orcamento_sem_avisos():
    pool = card_lint.load_pool()
    for c in _neutras():
        others = [o for o in pool if o["id"] != c["id"]]
        issues = card_lint.lint_card(c, others)
        assert not card_lint.errors(issues), (c["id"], issues)
        assert not [i for i in issues if i.level == "warn"], (c["id"], issues)
        assert fx.budget_error(c) is None, c["id"]


def test_lote6_licoes_da_revisao_dos_lotes_anteriores():
    """Mesmas regras dos Lotes 2-5, aplicadas às neutras (que não têm roda de Postura)."""
    nomeadas = {"protecao", "buff_defesa", "buff_acerto", "buff_dano", "vantagem", "dot", "marca"}
    for c in _neutras():
        effs = fx.normalize(c)
        kinds = [e["kind"] for e in effs]
        if c["tipo"] == "reacao":
            assert c.get("gatilho"), c["id"]
            assert len(effs) == 1 and fx.custo_folego(c) >= 1, c["id"]
        if c["tipo"] == "ativa":
            assert "buff_esquiva" not in kinds, c["id"]
        assert "taunt" not in kinds, c["id"]  # Provocar só vale com aliados
        assert not card_lint.check_escala_principal(c), c["id"]
        assert not card_lint.check_marca_dano(c), c["id"]
        assert not card_lint.check_revelar_publico(c), c["id"]
        assert not card_lint.check_reacao_folego(c), c["id"]
        assert not card_lint.check_controle_duracao(c), c["id"]
        if fx.custo_folego(c) == 0:
            assert c["frequencia"] == "cena", c["id"]
        assert sum(1 for k in kinds if k in nomeadas) <= 1, c["id"]
        prim = fx.primary_effect(c)
        assert prim is None or prim.get("alvo") not in ("aliados", "inimigos"), c["id"]
        if c["raridade"] == "abissal":  # só chefe; Exaurir e custo explícito
            assert fx.keywords(c).get("exaurir") and c["custo_entropia"] > 0, c["id"]
        assert len(c["descricao"]) <= 140, c["id"]


def test_lote6_neutras_nao_vazam_para_nenhuma_postura_nem_para_o_baralho_inicial():
    import character_creator as cc
    import progression
    from services import cards

    ids = {c["id"] for c in _neutras()}
    for postura in POSTURAS:
        assert not ids & {c["id"] for c in cards.cards_for_class(postura)}, postura
        player = {"class_name": postura, "level": 20, "known_cards": [], "subclass": ""}
        assert not ids & set(progression.eligible_cards(player)), postura
        inicial = cc._resolve_starting_cards({}, postura, {})
        assert not ids & set(inicial["known_cards"] + inicial["prepared_cards"]), postura


def test_lote6_neutras_entram_pelo_espolio_e_respeitam_a_regiao():
    from services import card_rewards as cr

    def estado(local: str, level: int = 20) -> dict:
        player = {"class_name": "Corruptor", "level": level, "known_cards": [], "subclass": ""}
        return {"player": player, "world": {"current_location_id": local}}

    ids = {c["id"]: c for c in _neutras()}
    # local = nó dentro da região (na_anel_ferro -> nova_arcadia): o region_id entra no sorteio
    vistas: set[str] = set()
    for seed in range(400):
        vistas.update(cr.roll_rewards(estado("na_anel_ferro"), None, seed))
    neutras_vistas = vistas & set(ids)
    assert any(i.startswith("neu1_na_") for i in neutras_vistas)
    assert not any(i.startswith("neu1_er_") for i in neutras_vistas)  # Ermo só em skallgard
    assert not any(i.startswith("neu1_sb_") for i in neutras_vistas)
    assert any(i.startswith("neu1_ge_") for i in neutras_vistas)  # itens gerais: qualquer lugar
    assert not [i for i in neutras_vistas if ids[i]["raridade"] == "abissal"]  # abissal: só chefe
    boss = [{"id": "x", "categoria": "chefe"}]
    chefe: set[str] = set()
    for seed in range(600):
        chefe.update(cr.roll_rewards(estado("brekmar"), None, seed, defeated=boss))
    assert any(ids[i]["raridade"] == "abissal" for i in chefe & set(ids))
    baixo: set[str] = set()
    for seed in range(300):  # nível 1 respeita level_req: só as comuns
        baixo.update(cr.roll_rewards(estado("skallgard", level=1), None, seed))
    assert all(ids[i]["raridade"] == "comum" for i in baixo & set(ids))
    assert any(i.startswith("neu1_er_") for i in baixo & set(ids))


# ----------------------------------------------------------------- R6: tronco do nível 1
def test_tronco_cartas_por_postura_sem_subclasse_nivel_1():
    pool = card_lint.load_pool()
    cs = [c for c in pool if "_tro_" in str(c["id"])]
    assert Counter(c["classe"] for c in cs) == {
        "Devoto do Abismo": 3,
        "Sangromante": 3,
        "Corruptor": 3,
        "Arcanista Cinzento": 4,
        "Médico de Campo": 3,
    }
    for c in cs:
        assert not c.get("subclasse")
        if (
            c["id"] == "arc1_tro_lance_calculado"
        ):  # pilha pura não vale no baralho off: incomum, nível 4
            assert c["raridade"] == "incomum" and c["level_req"] == 4
            assert fx.primary_effect(c)["kind"] == "protecao"
        else:
            assert c["level_req"] == 1 and c["raridade"] == "comum"
        assert c.get("onda") == 1 and c["tipo"] == "ativa"
        others = [o for o in pool if o["id"] != c["id"]]
        issues = card_lint.lint_card(c, others)
        assert not issues, (c["id"], issues)
        assert fx.budget_error(c) is None, c["id"]
        if fx.custo_folego(c) == 0:
            assert c["frequencia"] == "cena", c["id"]
