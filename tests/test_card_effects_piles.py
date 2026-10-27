"""SPEC-330 R6/R7 (Grupo B) sobre as pilhas da SPEC-328: Exaurir, Guardar, Eco, Ressoar,
Fardo, Vazão e os efeitos `comprar`/`descartar`/`ganhar_folego`/`gerar_carta`/
`purgar_fardo`. Só com `RPG_CARD_DECK=on`; em `off`/`shadow` seguem inertes."""

import copy
import random

import pytest

import combat_mechanics as cm
from services import card_effects as fx
from services import card_piles as cp
from services import cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

_BASE = {
    "tipo": "ativa",
    "classe": "Sangromante",
    "frequencia": "livre",
    "custo_entropia": 0,
    "custo_folego": 1,
    "tier": 1,
    "level_req": 1,
    "descricao": "x",
}
DANO = {"kind": "dano", "categoria_arma": "leve", "dano_base": 4}

SYN = {
    "t_comprar": {"name": "Respiro", "efeito": {"kind": "comprar", "valor": 2}},
    "t_descartar": {"name": "Purga", "efeito": {"kind": "descartar", "valor": 1, "escolha": True}},
    "t_folego": {"name": "Folga", "efeito": {"kind": "ganhar_folego", "valor": 2}},
    "t_gerar": {
        "name": "Cria",
        "efeito": {"kind": "gerar_carta", "id": "bas_san_guarda", "pilha": "mao"},
    },
    "t_gerar_fardo": {
        "name": "Praga",
        "efeito": {"kind": "gerar_carta", "id": cp.FARDO_ID, "pilha": "mao"},
    },
    "t_purgar": {"name": "Limpa", "efeito": {"kind": "purgar_fardo", "valor": 1}},
    "t_exaurir": {"name": "Brasa", "efeito": dict(DANO), "palavras_chave": {"exaurir": True}},
    "t_guardar": {"name": "Reserva", "efeito": dict(DANO), "palavras_chave": {"guardar": True}},
    "t_vazao": {
        "name": "Escoa",
        "efeitos": [dict(DANO), {"kind": "sangria", "valor": 2, "quando": "ao_descartar"}],
        "palavras_chave": {"vazao": True},
    },
    "t_vazao_folego": {
        "name": "Escoa Fôlego",
        "efeitos": [dict(DANO), {"kind": "ganhar_folego", "valor": 1, "quando": "ao_descartar"}],
        "palavras_chave": {"vazao": True},
    },
    "t_eco": {"name": "Reverbera", "efeito": dict(DANO), "palavras_chave": {"eco": True}},
    "t_ressoar": {
        "name": "Cresce",
        "efeito": {"kind": "dano", "categoria_arma": "leve", "dano_base": 2},
        "palavras_chave": {"ressoar": 2},
    },
}


@pytest.fixture(autouse=True)
def _synthetic(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    catalog = cards._load_cards()
    for cid, extra in SYN.items():
        monkeypatch.setitem(catalog, cid, fx.materialize({"id": cid, **_BASE, **extra}))


def _player():
    p = {
        "id": "player",
        "name": "Herói",
        "is_player": True,
        "class_name": "Sangromante",
        "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        "known_cards": list(SYN),
        "prepared_cards": [],
        "entropy": 6,
        "max_entropy": 10,
        "abyss_charge": 0,
    }
    p = orch.ensure_combat_sheet(p, is_player=True)
    cp.migrate_deck(p)
    p["prepared_cards"] = list(dict.fromkeys(p["prepared_cards"] + list(SYN)))
    cm.apply_condition(p, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40})
    return p


def _enemy():
    e = orch.ensure_combat_sheet(
        {
            "id": "gob_1",
            "name": "Goblin",
            "type": "Minion",
            "hp": 60,
            "max_hp": 60,
            "ac": 11,
            "attributes": {"str": 10, "dex": 12, "con": 10, "int": 8, "wis": 8, "cha": 6},
        }
    )
    e["vitalidade"] = e["max_vitalidade"] = 60
    return e


def _setup(hand, mode="on", compra=None):
    player, enemy = _player(), _enemy()
    piles = cp.start_piles(player, 11)
    piles["mao"] = list(hand)
    if compra is not None:
        piles["compra"] = list(compra)
    scene = cs.new_scene()
    for aid in ("player", "gob_1"):
        cs.place(scene, aid)
    cs.freeze(scene)
    state = {"player": player, "_piles": piles, "_deck_mode": mode}
    return (
        scene,
        {"player": player, "gob_1": enemy},
        {"hero": ["player"], "enemy": ["gob_1"]},
        state,
    )


def _step(cid, target="gob_1"):
    return ct.TurnStep(kind="card", card_id=cid, target_id=target)


def _run(setup, *steps, seed=5):
    scene, actors, sides, state = setup
    decl = ct.TurnDeclaration(actor_id="player", jogadas=list(steps))
    return orch.run_round(
        scene, actors, sides, state, declarations={"player": decl}, rng=random.Random(seed)
    )


# ------------------------------------------------------------------ comprar / descartar / folego
def test_comprar_traz_cartas_do_monte_para_a_mao():
    s = _setup(["t_comprar"], compra=["bas_san_golpe", "bas_san_guarda", "san_esquiva"])
    out = _run(s, _step("t_comprar", "player"))
    piles = s[3]["_piles"]
    assert piles["mao"] == ["bas_san_golpe", "bas_san_guarda"]
    assert piles["compra"] == ["san_esquiva"] and piles["descarte"] == ["t_comprar"]
    assert out["pilhas_eventos"][0] == {
        "kind": "comprar",
        "cartas": ["bas_san_golpe", "bas_san_guarda"],
        "card_id": "t_comprar",
    }
    assert not out.get("pendente_pilhas")


def test_comprar_com_monte_vazio_reembaralha_e_gera_fardo():
    s = _setup(["t_comprar"], compra=[])
    s[3]["_piles"]["descarte"] = ["bas_san_golpe", "bas_san_guarda"]
    _run(s, _step("t_comprar", "player"))
    piles = s[3]["_piles"]
    assert piles["fardos"] == 1
    assert len(piles["mao"]) == 2 and set(piles["mao"]) <= {
        "bas_san_golpe",
        "bas_san_guarda",
        cp.FARDO_ID,
    }


def test_descartar_com_escolha_leva_o_fardo_primeiro_e_poupa_a_carta_em_jogo():
    s = _setup(["t_descartar", "bas_san_golpe", cp.FARDO_ID])
    _run(s, _step("t_descartar", "player"))
    piles = s[3]["_piles"]
    assert piles["mao"] == ["bas_san_golpe"]
    assert sorted(piles["descarte"]) == sorted([cp.FARDO_ID, "t_descartar"])


def test_descartar_ao_acaso_e_deterministico_pela_semente(monkeypatch):
    results = []
    for _ in range(2):
        s = _setup(["t_descartar", "bas_san_golpe", "bas_san_guarda", "san_esquiva"])
        s[3]["_piles"]["seed"] = 77
        # sem `escolha`: ao acaso
        card = copy.deepcopy(cards.get_card("t_descartar"))
        card["efeito"]["escolha"] = False
        monkeypatch.setitem(cards._load_cards(), "t_descartar", fx.materialize(card))
        _run(s, _step("t_descartar", "player"))
        results.append(list(s[3]["_piles"]["descarte"]))
    assert results[0] == results[1] and len(results[0]) == 2


def test_ganhar_folego_soma_e_respeita_o_teto():
    s = _setup(["t_folego", "t_folego"])
    _run(s, _step("t_folego", "player"), _step("t_folego", "player"))
    # 3 base - 1 - 1 + 2 + 2, teto FOLEGO_MAX
    assert s[3]["_piles"]["folego"] == min(cp.FOLEGO_MAX, 3 - 1 + 2 - 1 + 2)
    assert cp.gain_folego({"folego": cp.FOLEGO_MAX}, 5) == 0


def test_gerar_carta_poe_copia_na_pilha():
    s = _setup(["t_gerar"])
    _run(s, _step("t_gerar", "player"))
    assert s[3]["_piles"]["mao"] == ["bas_san_guarda"]


def test_gerar_carta_desconhecida_nao_quebra():
    assert cp.add_card({"mao": [], "compra": [], "descarte": []}, "nao_existe", "mao") is False
    assert cp.add_card({"mao": [], "compra": [], "descarte": []}, "bas_san_golpe", "lixo") is False


# ------------------------------------------------------------------ Fardo
def test_fardo_gerado_e_injogavel_e_purgar_remove():
    s = _setup(["t_gerar_fardo", "t_purgar"])
    out = _run(s, _step("t_gerar_fardo", "player"))
    piles = s[3]["_piles"]
    assert piles["mao"] == ["t_purgar", cp.FARDO_ID]
    assert piles["fardos"] == 1
    # o Fardo na mao e injogavel: a rodada e recusada, sem gastar nada
    before = copy.deepcopy(piles)
    ref = _run(s, _step(cp.FARDO_ID, "player"))
    assert ref["action_refused"] and "Fardo" in ref["logs"][-1]
    assert s[3]["_piles"] == before
    out2 = _run(s, _step("t_purgar", "player"))
    assert cp.FARDO_ID not in s[3]["_piles"]["mao"]
    assert any(e["kind"] == "purgar_fardo" and e["valor"] == 1 for e in out2["pilhas_eventos"])
    assert out["pilhas_eventos"][0]["kind"] == "gerar_carta"


def test_fardo_vem_do_glossario_como_palavra_chave():
    assert cp.FARDO_CARD["palavras_chave"] == {"fardo": True}
    assert cp.is_fardo(cp.FARDO_CARD) and cp.is_fardo({"palavras_chave": {"fardo": True}})
    assert not cp.is_fardo({"id": "x"})
    from services.card_effects import glossary

    assert "fardo" in glossary()


def test_inimigo_pode_plantar_fardo_na_mao_do_jogador_mas_nao_comprar():
    s = _setup(["bas_san_golpe"])
    scene, actors, sides, state = s
    token = fx.bind(scene, actors, sides, rng=random.Random(1))
    try:
        ctx = fx.current()
        ctx.piles, ctx.piles_actor = state["_piles"], "player"
        out: dict = {"logs": []}
        fx.apply_effect(
            ctx, {"kind": "gerar_carta", "id": cp.FARDO_ID}, "gob_1", "player", out, card={}
        )
        assert state["_piles"]["mao"] == ["bas_san_golpe", cp.FARDO_ID]
        fx.apply_effect(ctx, {"kind": "comprar", "valor": 2}, "gob_1", "player", out, card={})
        assert state["_piles"]["mao"] == ["bas_san_golpe", cp.FARDO_ID]
        assert out["pendente_pilhas"][0]["kind"] == "comprar"
    finally:
        fx.unbind(token)


# ------------------------------------------------------------------ Exaurir / Guardar
def test_exaurir_sai_ate_o_fim_do_conflito():
    s = _setup(["t_exaurir"])
    _run(s, _step("t_exaurir"))
    piles = s[3]["_piles"]
    assert piles["exaurida"].count("t_exaurir") == 1 and "t_exaurir" not in piles["descarte"]
    assert piles["mao"] == []
    cp.begin_round(piles)  # a proxima rodada nao a traz de volta
    assert "t_exaurir" not in piles["mao"] + piles["compra"] + piles["descarte"]


def test_guardar_sobrevive_ao_fim_da_rodada():
    s = _setup(["t_guardar", "bas_san_golpe"])
    out = _run(s, _step("bas_san_golpe"))
    piles = s[3]["_piles"]
    assert piles["guardadas"] == ["t_guardar"]
    assert {"kind": "guardar", "cartas": ["t_guardar"]} in out["pilhas_eventos"]
    cp.begin_round(piles)
    assert "t_guardar" in piles["mao"] and "t_guardar" not in piles["descarte"]
    assert len(piles["mao"]) == cp.MAO_BASE


def test_sem_guardar_a_mao_inteira_vai_ao_descarte():
    s = _setup(["bas_san_golpe", "bas_san_guarda"])
    _run(s, _step("bas_san_golpe"))
    piles = s[3]["_piles"]
    cp.begin_round(piles)
    assert "bas_san_guarda" in piles["descarte"] or "bas_san_guarda" in piles["mao"]
    assert piles["guardadas"] == []


# ------------------------------------------------------------------ Vazão
def test_vazao_dispara_ao_descartar_sem_jogar_no_fim_da_rodada():
    s = _setup(["t_vazao", "bas_san_golpe"])
    out = _run(s, _step("bas_san_golpe"))
    enemy = s[1]["gob_1"]
    assert fx.has_condition(enemy, "sangria")
    assert any(
        g["gatilho"] == "ao_descartar" and g["card_id"] == "t_vazao" for g in out["gatilhos"]
    )
    assert {"kind": "vazao", "carta": "t_vazao"} in out["pilhas_eventos"]


def test_vazao_nao_dispara_se_a_carta_foi_jogada():
    s = _setup(["t_vazao"])
    _run(s, _step("t_vazao"))
    assert not fx.has_condition(s[1]["gob_1"], "sangria")


def test_vazao_nao_dispara_se_guardada(monkeypatch):
    cat = cards._load_cards()
    card = copy.deepcopy(cat["t_vazao"])
    card["palavras_chave"]["guardar"] = True
    monkeypatch.setitem(cat, "t_vazao", card)
    s = _setup(["t_vazao", "bas_san_golpe"])
    _run(s, _step("bas_san_golpe"))
    assert not fx.has_condition(s[1]["gob_1"], "sangria")


def test_vazao_via_descartar_do_jogador():
    s = _setup(["t_descartar", "t_vazao"])
    _run(s, _step("t_descartar", "player"))
    assert fx.has_condition(s[1]["gob_1"], "sangria")
    assert "t_vazao" in s[3]["_piles"]["descarte"]


# ------------------------------------------------------------------ Eco / Ressoar
def _hp_loss(setup):
    e = setup[1]["gob_1"]
    return e["max_vitalidade"] - e["vitalidade"]


def test_eco_repete_pela_metade_depois_de_carta_da_mesma_postura():
    solo = _setup(["t_eco"])
    out_solo = _run(solo, _step("t_eco"))
    assert not any(k["keyword"] == "eco" for k in out_solo.get("keywords", []))
    combo = _setup(["bas_san_golpe", "t_eco"])
    out = _run(combo, _step("bas_san_golpe"), _step("t_eco"))
    assert any(k["keyword"] == "eco" for k in out["keywords"])
    assert any("Eco:" in log for log in out["logs"])
    extra = [h for h in out.get("extra_hits", []) if h["actor_id"] == "player"]
    assert len(extra) == 1  # o eco: dano_base 4 -> 2


def test_eco_outra_postura_nao_conta():
    s = _setup(["bas_dev_golpe", "t_eco"]) if "bas_dev_golpe" in cards.all_cards() else None
    if s is None:
        pytest.skip("sem basica de outra Postura no acervo")
    out = _run(s, _step("bas_dev_golpe"), _step("t_eco"))
    assert not any(k["keyword"] == "eco" for k in out.get("keywords", []))


def test_ressoar_soma_n_a_cada_jogada_anterior_na_cena():
    s = _setup(["t_ressoar", "t_ressoar", "t_ressoar"])
    out = _run(s, _step("t_ressoar"), _step("t_ressoar"), _step("t_ressoar"))
    finals = [a["dano_final"] for a in out["attacks"] if a["actor_id"] == "player"]
    assert len(finals) == 3
    assert finals[1] - finals[0] == 2 and finals[2] - finals[1] == 2
    assert cards.get_card("t_ressoar")["efeito"]["dano_base"] == 2  # catalogo intacto
    assert s[0]["ressoar"] == {"player:t_ressoar": 3}


def test_prepare_play_sem_ressoar_devolve_a_mesma_carta():
    card = cards.get_card("t_eco")
    assert fx.prepare_play({"ressoar": {}}, card, {"id": "player"}, "player") is card


# ------------------------------------------------------------------ inércia fora do `on`
@pytest.mark.parametrize("mode", ["shadow", "off"])
def test_fora_do_on_efeitos_de_pilha_ficam_inertes(mode, monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", mode)
    s = _setup(["t_comprar"], mode=mode, compra=["bas_san_golpe"])
    scene, actors, sides, state = s
    if mode == "off":
        state.pop("_piles")
    piles_before = copy.deepcopy(state.get("_piles"))
    decl = ct.TurnDeclaration(actor_id="player", acao=_step("t_comprar", "player"))
    out = orch.run_round(
        scene, actors, sides, state, declarations={"player": decl}, rng=random.Random(5)
    )
    assert out.get("pendente_pilhas") and out["pendente_pilhas"][0]["kind"] == "comprar"
    assert "pilhas_eventos" not in out
    if piles_before is not None:
        assert state["_piles"] == piles_before


def test_exaurir_e_guardar_sem_baralho_nao_mudam_nada(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    s = _setup(["t_exaurir"], mode="off")
    scene, actors, sides, state = s
    state.pop("_piles")
    decl = ct.TurnDeclaration(actor_id="player", acao=_step("t_exaurir"))
    out = orch.run_round(
        scene, actors, sides, state, declarations={"player": decl}, rng=random.Random(5)
    )
    assert out["attacks"] and "pilhas_eventos" not in out


# ------------------------------------------------------------------ ao_exaurir / ao_comprar
def test_ao_exaurir_dispara_o_efeito_da_propria_carta(monkeypatch):
    cat = cards._load_cards()
    monkeypatch.setitem(
        cat,
        "t_exaurir",
        fx.materialize(
            {
                "id": "t_exaurir",
                **_BASE,
                "name": "Brasa",
                "efeitos": [dict(DANO), {"kind": "sangria", "valor": 1, "quando": "ao_exaurir"}],
                "palavras_chave": {"exaurir": True},
            }
        ),
    )
    s = _setup(["t_exaurir"])
    out = _run(s, _step("t_exaurir"))
    # a Sangria (1 rodada) ja expirou no tick do inimigo: o gatilho e o log provam
    assert any(g["gatilho"] == "ao_exaurir" and g["kind"] == "sangria" for g in out["gatilhos"])
    assert any("Sangria" in log for log in out["logs"])


def test_ao_comprar_profundidade_limitada(monkeypatch):
    """Carta cujo `ao_comprar` compra outra com `ao_comprar`: para na profundidade 3."""
    cat = cards._load_cards()
    loop = {
        "id": "t_loop",
        **_BASE,
        "name": "Laço",
        "efeitos": [dict(DANO), {"kind": "comprar", "valor": 1, "quando": "ao_comprar"}],
    }
    monkeypatch.setitem(cat, "t_loop", fx.materialize(loop))
    s = _setup(["t_comprar"], compra=["t_loop"] * 10)
    _run(s, _step("t_comprar", "player"))
    piles = s[3]["_piles"]
    # comprar 2 (valor da carta) + no maximo 3 niveis de laco por carta comprada
    assert len(piles["mao"]) <= 2 + 2 * 3
    assert len(piles["mao"]) >= 2


# ------------------------------------------------------------------ revelar -> bestiary_knowledge (P2-5)
def _reveal(target, campo, monkeypatch, profile="legacy"):
    from services import bestiary_knowledge as bk

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", profile)
    calls = []
    monkeypatch.setattr(bk, "reveal_resistance", lambda e, r, **k: calls.append(("res", r)))
    monkeypatch.setattr(bk, "reveal_card", lambda e, c, **k: calls.append(("card", c)))
    scene, actors, sides, _ = _setup(["bas_san_golpe"])
    actors["gob_1"].update(target)
    token = fx.bind(scene, actors, sides, rng=random.Random(1))
    try:
        out: dict = {"logs": []}
        fx.apply_effect(
            fx.current(), {"kind": "revelar", "campo": campo}, "player", "gob_1", out, card={}
        )
    finally:
        fx.unbind(token)
    return calls, actors["gob_1"], out


def test_revelar_resistencias_persiste_no_bestiario(monkeypatch):
    calls, enemy, out = _reveal(
        {
            "immunities": ["veneno"],
            "resistances": {"igneo": ["resistencia"], "gelido": ["vulnerabilidade"]},
        },
        "resistencias",
        monkeypatch,
    )
    assert ("res", "veneno:imune") in calls
    assert ("res", "igneo:resiste") in calls and ("res", "gelido:vulneravel") in calls
    assert out["revelacoes"] == [{"target_id": "gob_1", "campo": "resistencias"}]
    assert enemy["_revelado"] == ["resistencias"]


def test_revelar_cartas_persiste_cada_carta_do_inimigo(monkeypatch):
    calls, _, _ = _reveal({"cartas": [{"id": "gob_facada"}, "gob_grito"]}, "cartas", monkeypatch)
    assert calls == [("card", "gob_facada"), ("card", "gob_grito")]


def test_revelar_fora_do_perfil_legacy_nao_toca_o_bestiario(monkeypatch):
    calls, enemy, _ = _reveal({"immunities": ["veneno"]}, "resistencias", monkeypatch, "hosted")
    assert calls == [] and enemy["revealed_resistances"] == ["veneno:imune"]


def test_revelar_no_jogador_ou_campo_cosmetico_nao_persiste(monkeypatch):
    calls, _, _ = _reveal({"immunities": ["veneno"]}, "vitalidade", monkeypatch)
    assert calls == []
