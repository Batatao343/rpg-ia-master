"""SPEC-330 R1–R4, R7–R9, R11 — gramática de efeitos (formato, equivalência,
gatilhos + fila anti-loop, condições, texto gerado, orçamento, validador)."""

import copy
import json
import os
import random

import pytest

import combat_mechanics as cm
from services import card_effects as fx
from services import cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
from services.content_validator import validate_cards
from tests import spec330_equivalence as eq

_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}
_HERE = os.path.dirname(__file__)
_FIXTURE = os.path.join(_HERE, "fixtures", "spec330_cartas_compostas.json")
_SNAPSHOT = os.path.join(_HERE, "fixtures", "spec330_card_text_snapshot.json")


def _examples() -> dict[str, dict]:
    with open(_FIXTURE, encoding="utf-8") as f:
        return {c["id"]: c for c in json.load(f)["cards"]}


@pytest.fixture
def examples(monkeypatch):
    catalog = cards._load_cards()
    ex = _examples()
    for cid, card in ex.items():
        monkeypatch.setitem(catalog, cid, fx.materialize(card))
    return ex


def _actor(aid: str, **kw) -> dict:
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _scene(*ids) -> dict:
    scene = cs.new_scene()
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    return scene


def _ctx(actors, scene=None, sides=None):
    return fx.Ctx(
        scene=scene if scene is not None else _scene(*actors),
        actors_by_id=actors,
        sides=sides or {"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(1),
    )


# ---------------------------------------------------------------- R1 formato
def test_normalize_legado_vira_lista_e_efeitos_tem_precedencia():
    legacy = {"efeito": {"kind": "dano", "dano_base": 4}}
    assert fx.normalize(legacy) == [{"kind": "dano", "dano_base": 4}]
    novo = {"efeitos": [{"kind": "rachadura", "valor": 1}, {"kind": "dano", "dano_base": 3}]}
    assert [e["kind"] for e in fx.normalize(novo)] == ["rachadura", "dano"]
    # principal = primeiro incondicional ao_jogar de kind LEGADO
    assert fx.primary_effect(novo) == {"kind": "dano", "dano_base": 3}
    assert [e["kind"] for e in fx.extra_effects(novo)] == ["rachadura"]
    assert fx.normalize({}) == [] and fx.primary_effect(None) is None


def test_materialize_deriva_efeito_sem_mutar_e_respeita_legado():
    novo = {"id": "x", "efeitos": [{"kind": "dano", "dano_base": 3, "categoria_arma": "leve"}]}
    out = fx.materialize(novo)
    assert out["efeito"]["kind"] == "dano" and "efeito" not in novo
    legacy = {"id": "y", "efeito": {"kind": "cura", "valor": 2}}
    assert fx.materialize(legacy) is legacy


def _list_form(card: dict) -> dict:
    out = copy.deepcopy(card)
    out["efeitos"] = [out.pop("efeito")]
    return fx.materialize(out)


def test_equivalencia_das_308_cartas_legadas_contra_o_motor_anterior():
    """D-3: golden gerado com o código da `main` PRÉ-330 (tests/spec330_equivalence.py)."""
    with open(eq.GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    legacy = eq.legacy_cards()
    assert len(legacy) == len(golden) == 308
    diffs = [cid for cid, c in sorted(legacy.items()) if eq.run_card_full(c) != golden[cid]]
    assert diffs == []


def test_equivalencia_forma_lista_igual_a_forma_legada(monkeypatch):
    catalog = cards._load_cards()
    with open(eq.GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    diffs = []
    for cid, card in sorted(eq.legacy_cards().items()):
        monkeypatch.setitem(catalog, cid, _list_form(card))
        if eq.run_card_full(catalog[cid]) != golden[cid]:
            diffs.append(cid)
        monkeypatch.setitem(catalog, cid, card)
    assert diffs == []


# ---------------------------------------------------------------- R4 condições
def test_condicoes_fechadas():
    player = _actor("player", entropy=5, max_entropy=10)
    player["vitalidade"], player["max_vitalidade"] = 10, 40
    e = _actor("e", arquetipo="predador")
    scene = _scene("player", "e")
    scene["objects"] = [{"id": "barril", "tags": ["inflamavel"], "zone_id": "z0"}]
    ctx = _ctx({"player": player, "e": e}, scene)
    cm.apply_condition(e, fx.rachadura_condition(2))
    cm.apply_condition(player, fx.torpor_condition(1))
    fx.record_play(player, {"id": "a", "tipo": "ativa", "classe": "Corruptor"}, "e")
    ok = {
        "alvo_tem": "rachadura",
        "eu_tenho": "torpor",
        "entropia_min": 5,
        "vitalidade_max_pct": 25,
        "cartas_jogadas_na_rodada_min": 1,
        "ultima_carta_tipo": "ativa",
        "ultima_carta_postura": "Corruptor",
        "engajado": False,
        "zona_tem_objeto": "inflamavel",
        "alvo_familia": "predador",
    }
    assert set(ok) == set(fx.CONDICOES)
    for key, arg in ok.items():
        assert fx.check({key: arg}, ctx, "player", "e"), key
    bad = {
        "alvo_tem": "torpor",
        "eu_tenho": "rachadura",
        "entropia_min": 6,
        "vitalidade_max_pct": 20,
        "cartas_jogadas_na_rodada_min": 2,
        "ultima_carta_tipo": "reacao",
        "ultima_carta_postura": "Sangromante",
        "engajado": True,
        "zona_tem_objeto": "altar",
        "alvo_familia": "bruto",
    }
    for key, arg in bad.items():
        assert not fx.check({key: arg}, ctx, "player", "e"), key
    assert fx.check(ok, ctx, "player", "e")  # todas juntas (E lógico)


def test_condicao_se_no_efeito_extra(examples):
    player = _actor(
        "player",
        class_name="Corruptor",
        known_cards=["ex330_lamina_da_ruina"],
        prepared_cards=["ex330_lamina_da_ruina"],
        entropy=9,
        max_entropy=99,
        level=20,
    )
    cm.apply_condition(
        player, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
    )

    def dano(rachado: bool) -> int:
        e = _actor("e")
        e["vitalidade"] = e["max_vitalidade"] = 60
        if rachado:
            e["active_conditions"] = [fx.rachadura_condition(3)]
        player["card_usage"] = {}
        ct.resolve_turn(
            _scene("player", "e"),
            {"player": player, "e": e},
            ct.TurnDeclaration(
                actor_id="player",
                acao=ct.TurnStep(kind="card", card_id="ex330_lamina_da_ruina", target_id="e"),
            ),
            state={"player": player},
            rng=random.Random(2),
        )
        return 60 - e["vitalidade"]

    # sem Rachadura: 3; com: 3×1,25→4 no golpe + 2×1,25→3 no extra condicional
    assert dano(False) == 3
    assert dano(True) == 7


# ---------------------------------------------------------------- R3/R11 gatilhos e fila
def test_passiva_com_gatilho_inicio_rodada_dispara_no_run_round(examples):
    player = _actor(
        "player",
        class_name="Médico de Campo",
        known_cards=["ex330_vigia_paciente"],
        prepared_cards=[],
    )
    e = _actor("e")
    out = orch.run_round(
        _scene("player", "e"),
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": {"actor_id": "player"}},
        rng=random.Random(1),
    )
    assert [g["gatilho"] for g in out["gatilhos"]] == ["inicio_rodada"]
    assert out["logs"][0] == "player: ganha Vigília 1."  # antes de qualquer golpe


def test_fire_sem_contexto_e_no_op():
    out: dict = {}
    fx.fire("inicio_rodada", sujeito_id="player", out=out)
    assert out == {}


def test_gatilho_desconhecido_nao_enfileira():
    actors = {"player": _actor("player"), "e": _actor("e")}
    ctx = _ctx(actors)
    out: dict = {}
    fx.fire("ao_espirrar", sujeito_id="player", out=out, ctx=ctx)
    assert not ctx.queue and out == {}


def test_fila_fifo_com_profundidade_maxima_3():
    """Gatilho que se re-dispara (laço) para na profundidade 3."""
    player, e = _actor("player"), _actor("e")
    e["vitalidade"] = e["max_vitalidade"] = 99
    actors = {"player": player, "e": e}
    ctx = _ctx(actors)
    # e: ao receber dano, revida 1 no player; player: ao receber dano, bate 1 em e.
    ctx.scene["gatilhos_armados"] = [
        {
            "owner_id": "e",
            "card_id": "loop_e",
            "efeito": {"kind": "dano", "valor": 1, "quando": "ao_receber_dano"},
        },
        {
            "owner_id": "player",
            "card_id": "loop_p",
            "efeito": {"kind": "dano", "valor": 1, "quando": "ao_receber_dano"},
        },
    ]

    player["vitalidade"] = player["max_vitalidade"] = 99
    out: dict = {"logs": []}
    # Sem patch: o dano vindo de gatilho dispara `ao_receber_dano` de verdade (P2-3).
    fx.fire("ao_receber_dano", sujeito_id="e", alvo_id="player", out=out, ctx=ctx)
    depths = [g["profundidade"] for g in out["gatilhos"]]
    assert depths == [1, 2, 3]  # FIFO, e→player→e, e o 4º é descartado
    assert [g["sujeito_id"] for g in out["gatilhos"]] == ["e", "player", "e"]
    assert out["gatilhos_descartados"][0]["profundidade"] == 4
    assert ctx.depth == 0 and not ctx.draining


def test_ordem_r11_custos_se_efeitos_gatilhos(examples):
    """Sacrifício paga antes; o `se` lê o estado DEPOIS do custo; efeitos na
    ordem da lista; o gatilho armado só roda quando disparado."""
    player = _actor("player", entropy=3, max_entropy=10)
    player["vitalidade"] = player["max_vitalidade"] = 20
    e = _actor("e")
    e["vitalidade"] = e["max_vitalidade"] = 60
    actors = {"player": player, "e": e}
    ctx = _ctx(actors)
    card = {
        "id": "ordem",
        "name": "Ordem",
        "palavras_chave": {"sacrificio": 15},
        "efeitos": [
            {"kind": "rachadura", "valor": 1},
            {"kind": "dano", "valor": 4, "se": {"vitalidade_max_pct": 25}},
            {"kind": "torpor", "valor": 1},
            {"kind": "vigilia", "valor": 2, "quando": "fim_rodada"},
        ],
    }
    out: dict = {"logs": []}
    events = fx.resolve_card(ctx, card, "player", "e", out)
    assert [ev["keyword"] for ev in events] == ["sacrificio", "rachadura", "torpor"]
    assert 60 - e["vitalidade"] == 5  # 4 × Rachadura (o `se` viu Vit 5/20)
    assert not fx.has_condition(player, "vigilia")
    fx.fire("fim_rodada", sujeito_id="player", out=out, ctx=ctx)
    assert cm.combat_modifiers(player)["vigilia"] == 2


# ---------------------------------------------------------------- R7 efeitos novos
def test_copiar_ultima_repete_a_carta_anterior(examples):
    player, e = _actor("player"), _actor("e")
    e["vitalidade"] = e["max_vitalidade"] = 60
    ctx = _ctx({"player": player, "e": e})
    fx.record_play(player, cards.get_card("ex330_golpe_rachador"), "e")
    out: dict = {"logs": []}
    fx.apply_effect(ctx, {"kind": "copiar_ultima"}, "player", "e", out)
    assert 60 - e["vitalidade"] == 4 and fx.has_condition(e, "rachadura")


def test_mover_alvo_zona_e_revelar():
    player, e = _actor("player"), _actor("e")
    ctx = _ctx({"player": player, "e": e})
    out: dict = {"logs": []}
    fx.apply_effect(ctx, {"kind": "mover_alvo_zona", "direcao": "afastar"}, "player", "e", out)
    assert ctx.scene["positions"]["e"]["distance_state"] != "proximo"
    fx.apply_effect(ctx, {"kind": "revelar", "campo": "resistencias"}, "player", "e", out)
    assert out["revelacoes"] == [{"target_id": "e", "campo": "resistencias"}]
    assert e["_revelado"] == ["resistencias"]


def test_alvo_inimigos_e_escala():
    player = _actor("player", entropy=7, max_entropy=10)
    e1, e2 = _actor("e"), _actor("e2")
    actors = {"player": player, "e": e1, "e2": e2}
    ctx = _ctx(actors, sides={"hero": ["player"], "enemy": ["e", "e2"]})
    eff = {
        "kind": "sangria",
        "valor": 1,
        "alvo": "inimigos",
        "escala": {"por": "entropia", "fator": 0.5, "max": 2},
    }
    fx.apply_effect(ctx, eff, "player", None, {"logs": []})
    for enemy in (e1, e2):
        sang = next(c for c in enemy["active_conditions"] if c["keyword"] == "sangria")
        assert sang["dot"] == 3  # 1 + min(2, floor(0,5×7))


# ---------------------------------------------------------------- R8 texto gerado
def test_texto_gerado_snapshot_das_308_cartas():
    texts = {cid: fx.render_card_text(c) for cid, c in sorted(eq.legacy_cards().items())}
    assert len(texts) == 308 and all(texts.values())
    basicas = [c for c in cards.all_cards().values() if c.get("origem") == "cartas-328"]
    assert len(basicas) == 15 and all(fx.render_card_text(c) for c in basicas)
    if os.environ.get("RPG_UPDATE_SNAPSHOT") == "1":
        with open(_SNAPSHOT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(texts, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    with open(_SNAPSHOT, encoding="utf-8") as f:
        assert texts == json.load(f)


def test_texto_nunca_mente_sobre_o_numero():
    for card in cards.all_cards().values():
        eff = card["efeito"]
        text = fx.render_card_text(card)
        if eff.get("kind") == "dano" and eff.get("dano_base") is not None:
            assert f"Causa {eff['dano_base']} de dano" in text, card["id"]
        if eff.get("condicao") == "exposto":
            assert "Exposto" in text and "Rachadura" not in text, card["id"]


def test_texto_das_cartas_compostas():
    ex = {cid: fx.materialize(c) for cid, c in _examples().items()}
    assert len(ex) >= 10
    expect = {
        "ex330_golpe_rachador": "Causa 4 de dano. Aplica **Rachadura** 2.",
        "ex330_nevoa_pesada": "Aplica **Torpor** 2.",
        "ex330_corte_sangria": "Causa 3 de dano. Aplica **Sangria** 3.",
        "ex330_muralha_vigilante": "Aplica **Vigília** 3.",
        "ex330_dedo_do_abismo": "Aplica **Marca do Abismo** 3.",
        "ex330_golpe_interruptor": "**Interromper**. Aplica Atordoado.",
        "ex330_preco_de_sangue": "**Sacrifício** 2. Causa 8 de dano.",
        "ex330_chamado_da_fenda": "Causa 4 de dano. **Chamado** 4 — Causa 3 de dano.",
        "ex330_lamina_da_ruina": "Causa 3 de dano. Se o alvo tem **Rachadura**: causa 2 de dano.",
        "ex330_eco_da_postura": (
            "**Eco**. Causa 3 de dano. Se a última Carta foi de Arcanista Cinzento: "
            "causa 2 de dano."
        ),
        "ex330_vigia_paciente": "No início da rodada: aplica **Vigília** 1.",
        "ex330_valvula_fria": (
            "**Exaurir**. **Vazão**. Compra 1 Carta. Ao ser descartada: ganha 1 de Fôlego."
        ),
    }
    for cid, text in expect.items():
        assert fx.render_card_text(ex[cid]) == text, cid


# ---------------------------------------------------------------- R9 orçamento
def test_orcamento_as_308_cartas_cabem_na_faixa():
    out = [(cid, fx.budget_error(c)) for cid, c in cards.all_cards().items() if fx.budget_error(c)]
    assert out == []


def test_orcamento_cartas_compostas_cabem():
    for cid, card in _examples().items():
        assert fx.budget_error(fx.materialize(card)) is None, cid


def test_power_score_e_deterministico_e_monotono():
    base = {
        "tipo": "ativa",
        "patamar": "inicial",
        "frequencia": "turno",
        "efeitos": [{"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"}],
    }
    mais = copy.deepcopy(base)
    mais["efeitos"].append({"kind": "rachadura", "valor": 2})
    caro = dict(base, custo_entropia=3)
    assert fx.power_score(base) == fx.power_score(copy.deepcopy(base))
    assert fx.power_score(mais) > fx.power_score(base) > fx.power_score(caro)
    assert fx.custo_folego(base) == 1 and fx.custo_folego(dict(base, custo_folego=3)) == 3


# ---------------------------------------------------------------- R2 validador
def _write_cards(tmp_path, card_list):
    d = tmp_path / "cards"
    d.mkdir()
    (d / "x.json").write_text(json.dumps({"cards": card_list}), encoding="utf-8")
    return str(d)


def _good(**over):
    card = copy.deepcopy(_examples()["ex330_golpe_rachador"])
    card["origem"] = "conflito-14"
    card.update(over)
    return card


def test_validador_aceita_carta_composta_valida(tmp_path):
    assert validate_cards(_write_cards(tmp_path, [_good()])) == []


@pytest.mark.parametrize(
    "efeitos, needle",
    [
        ([{"kind": "explodir"}], "fora do catálogo fechado"),
        (
            [
                {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
                {"kind": "rachadura", "valor": 1, "quando": "ao_espirrar"},
            ],
            "gatilho",
        ),
        (
            [
                {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
                {"kind": "dano", "valor": 1, "se": {"lua_cheia": True}},
            ],
            "condição",
        ),
        (
            [
                {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
                {"kind": "dano", "valor": 1, "alvo": "todos"},
            ],
            "alvo",
        ),
        (
            [
                {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
                {"kind": "dano", "valor": 1, "escala": {"por": "sorte"}},
            ],
            "escala",
        ),
        (
            [
                {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
                {"kind": "dano", "valor": 1, "chamado": 0},
            ],
            "Chamado",
        ),
        ([{"kind": "rachadura", "valor": 1, "se": {"entropia_min": 2}}], "principal"),
    ],
)
def test_validador_rejeita_vocabulario_fora_do_catalogo(tmp_path, efeitos, needle):
    findings = validate_cards(_write_cards(tmp_path, [_good(efeitos=efeitos)]))
    assert any(needle in f.message for f in findings), [f.message for f in findings]


def test_validador_rejeita_palavra_chave_desconhecida(tmp_path):
    findings = validate_cards(_write_cards(tmp_path, [_good(palavras_chave={"furia": True})]))
    assert any("fora do glossário" in f.message for f in findings)


def test_validador_rejeita_carta_fora_do_orcamento(tmp_path):
    forte = _good(
        efeitos=[
            {"kind": "dano", "dano_base": 40, "categoria_arma": "marcial"},
            {"kind": "rachadura", "valor": 9, "alvo": "inimigos"},
        ]
    )
    findings = validate_cards(_write_cards(tmp_path, [forte]))
    assert any("fora do orçamento" in f.message for f in findings)


def test_validador_acervo_real_continua_limpo():
    assert validate_cards() == []
