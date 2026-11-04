"""SPEC-369 R10 - testes da regua (Fase A): a ferramenta reproduz a 368 e o bot leitor de
Pressagio segue a regra pre-registrada do R7, com caso bom e caso ruim conhecidos."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name: str, rel: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def M():
    return _load("metricas_369", "docs/spec369/metricas_369.py")


@pytest.fixture(scope="module")
def BP(M):
    return M.BP


@pytest.fixture(autouse=True)
def _deck_on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")  # como o `sim.deck_env` da arena


# So golpe e guarda basicos: o teste nao depende do custo da assinatura (`bas_dev_voto`, taunt, que o
# R7 conta como ataque de dano 0 e cujo Folego a Fase B pode mudar). Os custos reais de golpe/guarda
# sao lidos do catalogo em `_esperado_cego`.
HAND_DEV = ["bas_dev_golpe", "bas_dev_golpe", "bas_dev_guarda", "bas_dev_golpe", "bas_dev_golpe"]


def _esperado_cego(BP, piles) -> list[str]:
    """Golpes que o bot cego declara: tantos quanto o Folego paga (custo real do catalogo)."""
    custo = BP.fx.custo_folego(BP.cards.get_card("bas_dev_golpe"))
    golpes = HAND_DEV.count("bas_dev_golpe")
    n = golpes if custo == 0 else min(golpes, int(piles["folego"]) // custo)
    return ["bas_dev_golpe"] * n


def _cena(BP, *, hand, vit_inimigos=(16, 16), dano_arma=None, known=False):
    """Devoto L1 com a mao dada e dois inimigos reais do bestiario (padrao)."""
    A = BP.A
    player = A.hero("Devoto do Abismo", 1)
    player["deck"] = sorted(BP.sim.full_deck("Devoto do Abismo", 1))
    piles = BP.card_piles.start_piles(player, 0)
    piles["mao"] = list(hand)
    bid = A.creatures_by_category()["padrao"][0]
    enemies = A._instances(A.template_by_id(bid, encounter_level=2), len(vit_inimigos))
    for e, vit in zip(enemies, vit_inimigos, strict=True):
        e["vitalidade"] = vit
        if dano_arma is not None:
            e["dano_base_arma"] = dano_arma
            e["attack_formula"] = None
        if known:
            e["known"] = True
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    return player, piles, actors, sides, [e["id"] for e in enemies]


def _ataque(eid: str, alvo: str = "player", tipo: str = "ataque") -> dict:
    return {"actor_id": eid, "idx": 0, "tipo": tipo, "alvo_id": alvo, "carta_id": None}


def _cards(decl) -> list[str]:
    return [s.card_id for s in decl.jogadas if s.kind == "card"]


def test_base_reproduz_368(M):
    kw = {"classes": ["Sangromante"], "levels": [1], "categories": ["padrao"], "per_cat": 1}
    mine, log, seen = M.run_base([0, 1], **kw)
    ref = M.ME.run([0, 1], [1], ["padrao"], 1, r10=True, classes=["Sangromante"])
    assert mine == ref  # observar a luta nao muda nenhum numero
    assert set(mine) == {"r9", "r10"}
    assert mine["r9"]["total"]["conflitos"] == 2
    assert [f["omen"] for f in log] == [False, False, True, True]
    assert set(seen) == {"Sangromante"} and seen["Sangromante"]
    # o laco proprio do pressagio reproduz a luta da 368 nos bracos off e on-368
    enc = M.sim.encounters([1], ["padrao"], 1)[0]
    deck = M.sim.full_deck("Sangromante", 1)
    for braco, intent, omen in (("off", "off", False), ("on-368", "on", True)):
        with M.sim.deck_env(), M.ME._env(RPG_ENEMY_DECKS="off", RPG_ENEMY_INTENT=intent):
            for seed in (0, 1):
                a = M.fight_braco(*enc[:2], "Sangromante", 1, seed, deck, braco, known=False)
                b = M.ME.fight(*enc[:2], "Sangromante", 1, seed, deck, "m368", omen=omen, seen={})
                assert (a["outcome"], a["rounds"], a["damage"]) == (
                    b["outcome"],
                    b["rounds"],
                    b["damage"],
                )


def test_bot_faixa_troca_ataque_por_defesa(BP):
    player, piles, actors, sides, ids = _cena(BP, hand=HAND_DEV, dano_arma=6, known=True)
    forecast = {ids[0]: [_ataque(ids[0])]}
    assert BP.ameaca_prevista(forecast, actors) == 9.0  # faixa [6, 12] -> meio 9
    assert BP.ameaca_seria(9.0, player)
    golpe, guarda = (BP.cards.get_card(c) for c in ("bas_dev_golpe", "bas_dev_guarda"))
    # a situacao provada: a troca cabe no Folego (guarda nao custa mais que o golpe que sai)
    assert BP.fx.custo_folego(guarda) <= BP.fx.custo_folego(golpe)
    esperado = _esperado_cego(BP, piles)
    assert len(esperado) >= 1
    cego = BP.cego_decl(player, copy.deepcopy(piles), ids[0], None)
    assert _cards(cego) == esperado
    decl = BP.leitor_faixa_decl(player, piles, actors, sides, None, forecast, None)
    assert sorted(_cards(decl)) == sorted([*esperado[:-1], "bas_dev_guarda"])
    assert decl.jogadas[len(esperado) - 1].target_id == "player"  # o ultimo golpe saiu


def test_bot_faixa_mantem_sem_ameaca(BP):
    player, piles, actors, sides, ids = _cena(BP, hand=HAND_DEV, dano_arma=6, known=True)
    forecast = {ids[0]: [_ataque(ids[0], alvo=ids[1])], ids[1]: [_ataque(ids[1], tipo="defesa")]}
    assert BP.ameaca_prevista(forecast, actors) == 0.0
    decl = BP.leitor_faixa_decl(player, piles, actors, sides, None, forecast, None)
    cego = BP.cego_decl(player, copy.deepcopy(piles), ids[0], None)
    assert decl.model_dump() == cego.model_dump()


def test_bot_faixa_desconhecida_usa_dano_padrao(BP):
    player, piles, actors, sides, ids = _cena(BP, hand=HAND_DEV, dano_arma=6, known=False)
    um = {ids[0]: [_ataque(ids[0])]}
    dois = {ids[0]: [_ataque(ids[0])], ids[1]: [_ataque(ids[1], tipo="ataque_multiplo")]}
    padrao = BP.ct._DANO_BASICO_DEFAULT
    assert padrao == 3  # Etapa 0: conflict_turn.py:233
    assert BP.ameaca_prevista(um, actors) == padrao  # sem faixa: nao le o dano real (6)
    assert BP.ameaca_prevista(dois, actors) == 2 * padrao
    assert not BP.ameaca_seria(padrao, player)  # 3 < 25 % de 18 e 15 >= 9
    player["vitalidade"] = 10
    assert BP.ameaca_seria(2 * padrao, player)  # 6 >= 2,5 (e 4 < 9)


def test_bot_faixa_mira_quem_ameaca_e_morre(BP):
    player, piles, actors, sides, ids = _cena(BP, hand=HAND_DEV, vit_inimigos=(16, 2))
    forecast = {ids[1]: [_ataque(ids[1])]}  # so o segundo ataca; 3 de ameaca nao e seria
    decl = BP.leitor_faixa_decl(player, piles, actors, sides, None, forecast, None)
    alvos = {s.target_id for s in decl.jogadas if s.kind == "card"}
    assert alvos == {ids[1]}
    actors[ids[1]]["vitalidade"] = 50  # nao morre com 6 de dano -> segue alive[0]
    decl = BP.leitor_faixa_decl(player, piles, actors, sides, None, forecast, None)
    assert {s.target_id for s in decl.jogadas if s.kind == "card"} == {ids[0]}


def test_braco_cego_nao_le_pressagio(M, BP):
    player, piles, actors, sides, ids = _cena(BP, hand=HAND_DEV, dano_arma=6, known=True)
    cego = M.decisor("on-cego")
    ameaca = {i: [_ataque(i)] for i in ids}
    a = cego(player, copy.deepcopy(piles), actors, sides, None, ameaca, {}, ids[0])
    b = cego(player, copy.deepcopy(piles), actors, sides, None, {}, {}, ids[0])
    ref = BP.sim.full_deck_decl(player, copy.deepcopy(piles), ids[0], {})
    assert a.model_dump() == b.model_dump() == ref.model_dump()
    faixa = M.decisor("on-faixa")(
        player, copy.deepcopy(piles), actors, sides, None, ameaca, {}, ids[0]
    )
    assert faixa.model_dump() != a.model_dump()  # o leitor reage ao mesmo pressagio


def test_emboscada_credita_passiva_preparada(M):
    # dev_zel_vigilia: passiva, zeloso, level_req 1. A 355 so credita o full_deck (sem passiva).
    assert not M.E.has_initiative_card("Devoto do Abismo", 1, "zeloso")
    assert M.tem_iniciativa("Devoto do Abismo", 1, "zeloso")
    assert not M.tem_iniciativa("Devoto do Abismo", 1, "consagrado")
    # san_conta_memorizada: passiva level_req 4 -> so do nivel 4 em diante
    assert not M.tem_iniciativa("Sangromante", 3, "")
    assert M.tem_iniciativa("Sangromante", 5, "")
    # Corruptor: robusto ao catalogo com ou sem a Carta do R17 (B2, `cor1_tro_faro_do_abismo`).
    ini = tuple(
        c["id"]
        for c in M.cards._load_cards().values()
        if c.get("classe") == "Corruptor"
        and any(e.get("kind") == "buff_iniciativa" for e in M.fx.normalize(c))
    )
    with M.sem_cartas(ini):  # estado da base (meta 6): sem Carta -> sem credito
        assert not any(M.tem_iniciativa("Corruptor", lv, "") for lv in (1, 3, 5))
    for cid in ini:  # cada Carta do Corruptor: passiva fora do full_deck, creditada so pelo D-369-6
        card = M.cards.get_card(cid)
        assert card["tipo"] == "passiva", cid
        lv = max(int(card.get("level_req", 1) or 1), 1)
        assert not M.E.has_initiative_card("Corruptor", lv, "")
        assert M.tem_iniciativa("Corruptor", lv, "")
    assert M.E.has_initiative_card is M._orig_has_initiative  # nada ficou trocado


def test_categoria_de_carta(M):
    assert M.categoria("bas_dev_golpe") == "basica"
    assert M.categoria("bas_med_golpe") == "basica"
    assert M.categoria("bas_san_corte_raso") == "sangromante"  # trava do dono vence
    assert M.categoria("san1_exp_selo_de_dor") == "sangromante"
    assert M.categoria("san_sil_exato") == "sangromante"
    assert M.categoria("arc_descarga") == "legada"
    assert M.categoria("cor_bio_gangrena") == "legada"
    assert M.categoria("med1_fer_lente_de_protese") == "onda"
    assert M.categoria("arc1_imp_bomba_estopim") == "onda"


def test_familia_classificacao_d369_7(M):
    def row(off: float, on: float) -> dict:
        return {"off": {"win": off}, "on": {"win": on}, "delta_pp": round((on - off) * 100, 1)}

    assert M.classifica_familia(row(0.455, 0.405)) == "alvo"  # conjurador L5 do lote 2
    assert M.classifica_familia(row(0.88, 0.755)) == "fora_de_escopo"  # covarde L5
    assert M.classifica_familia(row(0.62, 0.50)) == "alvo"  # |Delta| 12 > 10
    assert M.classifica_familia(row(0.62, 0.655)) == "ok"


def test_write_section_mescla(M, tmp_path):
    p = str(tmp_path / "x.json")
    M.write_section(p, "base", {"a": 1})
    M.write_section(p, "uso", {"b": 2})
    with open(p, encoding="utf-8") as fh:
        assert json.load(fh) == {"base": {"a": 1}, "uso": {"b": 2}}


def test_base_commitada_reproduz_368_e_tem_as_secoes():
    """R9(a)/(b): o artefato da base tem as 7 secoes e reproduz a 368 byte a byte."""
    with open(os.path.join(ROOT, "docs", "spec369", "base-0-19.json"), encoding="utf-8") as fh:
        base = json.load(fh)
    secoes = {"base", "duracao", "uso", "posturas", "emboscada", "pressagio", "familias"}
    assert secoes <= set(base)
    # catalogo mudou depois da 368 (SPEC-371): sem as Cartas posteriores, byte a byte igual
    assert base["base"]["equivalencia_368_sem_cartas_pos_368"] == {"r9": True, "r10": True}
    assert set(base["base"]["equivalencia_368"]) == {"r9", "r10"}
    assert base["base"]["meta"]["seeds"] == [0, 19]
    assert base["familias"]["meta"]["seeds"] == [0, 7]
    for k in ("desconhecida", "conhecida"):
        for d in ("decks_off", "decks_on"):
            assert set(base["pressagio"][k][d]) >= {"off", "on-cego", "on-368", "on-faixa"}
    # o laco proprio do pressagio reproduz o R10 da 368 (desconhecida, decks off)
    r10, p = base["base"]["r10"]["total"], base["pressagio"]["desconhecida"]["decks_off"]
    for braco, arm in (("off", "off"), ("on-368", "on")):
        assert p[braco]["dano_medio"] == r10[arm]["dano_medio"], braco
        assert p[braco]["vitoria_pct"] == r10[arm]["vitoria_pct"], braco


def test_sem_cartas_tira_e_devolve_catalogo_e_herois(M):
    """P3-4 (Astra): a prova do R9a tira as Cartas pos-368 e devolve catalogo e cache de herois."""
    cat = M.cards._load_cards()
    antes = {i: cat[i] for i in M.CARTAS_POS_368}
    M.A.hero("Devoto do Abismo", 1)  # garante cache nao vazio
    herois = dict(M.A._HEROES)
    with M.sem_cartas(M.CARTAS_POS_368):
        assert not any(i in cat for i in M.CARTAS_POS_368)
        assert M.A._HEROES == {}
    assert {i: cat[i] for i in M.CARTAS_POS_368} == antes
    assert herois == M.A._HEROES


def test_r14a_conta_assinatura_basica_fora_do_sangromante():
    """P1-1 (Astra): R14(d) poe a assinatura basica na meta (a); golpe/guarda e Sangromante, nao."""
    T = _load("test_spec369_metas_regua", "tests/test_spec369_metas.py")
    assert T.na_meta_r14a("bas_cor_mofo", "basica")
    assert T.na_meta_r14a("med1_fer_lente_de_protese", "onda")
    assert not T.na_meta_r14a("bas_cor_golpe", "basica")
    assert not T.na_meta_r14a("bas_dev_guarda", "basica")
    with open(os.path.join(ROOT, "docs", "spec369", "base-0-19.json"), encoding="utf-8") as fh:
        base = json.load(fh)
    falhas = T.r14(base)
    assert "(a) med1_fer_lente_de_protese uso 1.0" in falhas  # onda sem limite registrado reprova
    assert not any("bas_cor_golpe" in f or "san" in f for f in falhas)
    # D-369-10: bas_cor_mofo tem teto registrado 0,714 (Fase B), que nao pode subir
    usos = base["uso"]["cartas"]["bas_cor_mofo"]
    for uso, reprova in ((0.714, False), (0.72, True)):
        usos["uso"] = uso
        assert any(f.startswith("(a) bas_cor_mofo") for f in T.r14(base)) is reprova, uso
    usos["uso"] = 0.76
    assert not any("bas_cor_mofo" in f for f in T.r14(base, "confirmacao"))  # 0,714 + 0,05


def test_d369_10_assinatura_gratis_le_o_catalogo():
    """D-369-10 item 1: a isencao vem do `custo_folego` 0 do catalogo, nao de lista de ids."""
    T = _load("test_spec369_metas_regua", "tests/test_spec369_metas.py")
    from services import card_effects as fx
    from services import cards

    for cid in ("bas_dev_voto", "bas_arc_vazao", "bas_cor_mofo", "bas_dev_golpe", "arc_descarga"):
        card = cards.get_card(cid)
        esperado = bool(card.get("basica")) and fx.custo_folego(card) == 0
        assert T.assinatura_gratis(cid) is esperado, cid
    assert not T.assinatura_gratis("arc_descarga")  # nao basica nunca isenta


def test_d369_10_limites_registrados_nao_podem_piorar():
    """D-369-10: p95 do Medico 16, razao do Pressagio 1,0257 e as 2 celulas do R20 sao tetos."""
    T = _load("test_spec369_metas_regua", "tests/test_spec369_metas.py")
    with open(os.path.join(ROOT, "docs", "spec369", "final-0-19.json"), encoding="utf-8") as fh:
        final = json.load(fh)
    assert T.r15(final) == [] and T.r16(final) == []
    final["base"]["r9"]["por_postura"]["Médico de Campo"]["p95_rodadas_conflito"] = 17.0
    assert T.r15(final) == ["Médico de Campo p95 17.0"]
    assert T.r15(final, "confirmacao") == []  # 16 + 1 rodada de tolerancia
    final["pressagio"]["conhecida"]["decks_on"]["razao_faixa_cego"] = 1.03
    assert T.r16(final) == ["on-faixa/on-cego 1.03"]
    cell = final["familias"]["cells"]["predador_apice|L3"]
    cell["delta_pp"] = -14.0
    assert any(f.startswith("predador_apice|L3") for f in T.r20(final, ["predador_apice|L3"]))
    cell["delta_pp"] = -13.5
    assert T.r20(final, ["predador_apice|L3"]) == []
    # as outras 3 celulas seguem com a meta cheia
    assert T._faixa_celula("abissal|L3", "final") == (45.0, 85.0, 10.0)


def test_posturas_deterministico_e_igual_a_base_do_emboscada(M):
    """Revisao Sol P3-5 (Fase B): o `posturas` isolado, repetido, e a base medida DENTRO do
    `emboscada` dao o mesmo numero; o braco de emboscada e outro protocolo e nao vaza estado."""
    sel = ["Médico de Campo"]
    orig = M.orch.run_round
    a = M.cmd_posturas([0], sel)["posturas"]
    emb = M.cmd_emboscada([0], None, sel)["posturas"]["Médico de Campo"]["todas"]
    b = M.cmd_posturas([0], sel)["posturas"]
    assert a == b  # mesmo comando 2x, com o patch de emboscada no meio
    assert emb["base_total"] == a["Médico de Campo"]["todas"]["total"]
    assert M.orch.run_round is orig  # monkeypatch devolvido
    assert M.E.has_initiative_card is M._orig_has_initiative


def test_limiares_do_gate_r9c_contra_a_base():
    """Gate R9c (04/11): Sangromante fora do piso do R13 (total segue), 3 reacoes legadas fora do
    R14(b), guarda basica fora do R14(a)."""
    T = _load("test_spec369_metas_regua", "tests/test_spec369_metas.py")
    with open(os.path.join(ROOT, "docs", "spec369", "base-0-19.json"), encoding="utf-8") as fh:
        base = json.load(fh)
    r13 = T.r13(base)
    assert "total 1.915" in r13 and not any(f.startswith("Sangromante") for f in r13)
    r14 = T.r14(base)
    assert not any(f.startswith("(b)") for f in r14)  # so as 3 legadas travadas eram (b)
    assert not T.na_meta_r14a("bas_med_guarda", "basica")


def test_r20_exige_200_lutas_e_sementes_da_fase():
    """Astra rodada 4 (P2-3): a base passa o controle de amostra (apex com 0-19); com 80 lutas, reprova."""
    import copy as _copy

    T = _load("test_spec369_metas_regua", "tests/test_spec369_metas.py")
    with open(os.path.join(ROOT, "docs", "spec369", "base-0-19.json"), encoding="utf-8") as fh:
        base = json.load(fh)
    alvo = base["familias"]["celulas_alvo"]
    falhas = T.r20(base, alvo)
    assert not any("lutas" in f or "sementes" in f for f in falhas)
    pequeno = _copy.deepcopy(base)
    k = "predador_apice|L3"
    pequeno["familias"]["cells"][k] = pequeno["familias"]["cells"][k]["amostra_original_0_7"]
    falhas = T.r20(pequeno, alvo)
    assert f"{k} off so 80 lutas" in falhas and any("sementes None" in f for f in falhas)
    # faixas de familia nao colidem: ajuste ate 19, confirmacao a partir de 260
    fin = [T.SEMENTES_FAMILIA["final"], T.SEMENTES_FAMILIA_CELULA[k]["final"]]
    conf = [T.SEMENTES_FAMILIA["confirmacao"], T.SEMENTES_FAMILIA_CELULA[k]["confirmacao"]]
    assert max(b for _, b in fin) < min(a for a, _ in conf)
    assert all(260 <= a <= b <= 339 for a, b in conf)


def test_d369_11_tolerancia_so_na_dimensao_fora_da_meta():
    """Astra P2-5: na confirmacao, o Delta do conjurador L5 (-8,0, dentro da meta) segue com |Delta|
    <= 10; so a vitoria `on` (38,5 %, fora) ganha limite registrado + 5 pp. No apex e o contrario."""
    T = _load("test_spec369_metas_regua", "tests/test_spec369_metas.py")
    assert T._faixa_celula("conjurador|L5", "final") == (38.5, 85.0, 10.0)
    assert T._faixa_celula("conjurador|L5", "confirmacao") == (33.5, 85.0, 10.0)
    assert T._faixa_celula("predador_apice|L3", "final") == (45.0, 85.0, 13.5)
    assert T._faixa_celula("predador_apice|L3", "confirmacao") == (45.0, 85.0, 18.5)


def test_p3_8_isencao_le_snapshot_do_artefato():
    """Astra P3-8: com `custo_folego` gravado na linha do `uso`, a isencao segue o snapshot, nao o
    catalogo atual; sem o campo (artefato antigo), cai no catalogo."""
    T = _load("test_spec369_metas_regua", "tests/test_spec369_metas.py")
    assert T.assinatura_gratis("bas_cor_mofo", {"categoria": "basica", "custo_folego": 0})
    assert not T.assinatura_gratis("bas_dev_voto", {"categoria": "basica", "custo_folego": 1})
    assert not T.assinatura_gratis("arc1_x", {"categoria": "onda", "custo_folego": 0})
    sem = {"categoria": "basica"}
    assert T.assinatura_gratis("bas_dev_voto", sem) is T.assinatura_gratis("bas_dev_voto")
