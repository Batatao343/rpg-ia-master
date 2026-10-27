"""SPEC-330 R5/R6/R10 — as 14 palavras-chave de Valoria: uma por teste.

Grupo A tem efeito no motor (determinístico, offline). Grupo B depende das
pilhas da SPEC-328: aqui só glossário, validador e texto; o motor registra
`pendente_pilhas` sem efeito (follow-up explícito no pouso da 328)."""

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
from services.conflict_damage import resolve_damage_and_wounds

_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}
_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "spec330_cartas_compostas.json")


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


def _player(card_ids, **kw) -> dict:
    p = _actor(
        "player",
        class_name="Sangromante",
        known_cards=list(card_ids),
        prepared_cards=list(card_ids),
        entropy=kw.pop("entropy", 20),
        max_entropy=99,
        level=1,
        **kw,
    )
    # Mira: acerto garantido, o teste mede o efeito, não o dado.
    cm.apply_condition(p, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40})
    return p


def _play(player, enemy, card_id, *, target="e", scene=None, seed=3, extra_actors=None):
    actors = {"player": player, "e": enemy, **(extra_actors or {})}
    scene = scene or _scene(*actors)
    return ct.resolve_turn(
        scene,
        actors,
        ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="card", card_id=card_id, target_id=target)
        ),
        state={"player": player},
        sides={"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(seed),
    )


def _hit(target, base, **kw) -> int:
    before = target["vitalidade"]
    resolve_damage_and_wounds(target, damage_base=base, rng=random.Random(1), **kw)
    return before - target["vitalidade"]


def _fresh_enemy(**kw):
    e = _actor("e", **kw)
    e["vitalidade"] = e["max_vitalidade"] = 60
    return e


# ---------------------------------------------------------------- Grupo A
def test_rachadura_amplia_golpe_em_25_por_cento_e_nao_o_dot():
    e = _fresh_enemy()
    assert _hit(e, 4) == 4
    cm.apply_condition(e, fx.rachadura_condition(2))
    assert _hit(e, 4) == 5  # 4 × 1,25
    assert _hit(e, 3) == 4  # 3,75 → 4 (meio para cima)
    assert _hit(e, 4, bypass_armor=True) == 4  # DoT/auto-dano não amplia


def test_exposto_segue_distinto_da_rachadura():
    """Correção do coordenador (27/10): `exposto` mantém −2 de Esquiva; Rachadura
    é condição NOVA, só de Cartas novas/compostas."""
    cond = cm.parse_condition("exposto")
    assert cond.get("stat") == "ac" and cond.get("delta") == -2
    assert cm.parse_condition("rachadura")["stat"] == "dano_recebido_pct"
    e = _fresh_enemy()
    cm.apply_condition(e, dict(cond, duration=2))
    assert fx.has_condition(e, "exposto") and not fx.has_condition(e, "rachadura")
    assert _hit(e, 4) == 4


def test_rachadura_mais_golpe_numero_do_log_bate_com_o_texto(examples):
    text = fx.render_card_text(examples["ex330_golpe_rachador"])
    assert "**Rachadura** 2" in text and "Causa 4 de dano" in text
    player = _player(["ex330_golpe_rachador", "arc_descarga"])
    e = _fresh_enemy()
    out = _play(player, e, "ex330_golpe_rachador")
    assert fx.has_condition(e, "rachadura")
    assert any(k["keyword"] == "rachadura" and k["n"] == 2 for k in out["keywords"])
    vit = e["vitalidade"]
    out2 = _play(player, e, "arc_descarga", seed=4)
    assert any("+25%" in log for log in out2["logs"])
    assert out2["attacks"][0]["dano_final"] == vit - e["vitalidade"]


def test_torpor_reduz_dano_causado_pelo_portador():
    attacker = _actor("e")
    e = _fresh_enemy()
    cm.apply_condition(attacker, fx.torpor_condition(2))
    pct = fx.damage_pct(attacker, "dealt")
    assert pct == -25
    assert _hit(e, 4, dealt_pct=pct) == 3


def test_torpor_como_carta_rola_ataque_e_aplica(examples):
    player = _player(["ex330_nevoa_pesada"])
    e = _fresh_enemy()
    out = _play(player, e, "ex330_nevoa_pesada")
    assert out["attacks"] and out["attacks"][0]["acerto"]
    assert fx.has_condition(e, "torpor")


def test_sangria_causa_n_e_decai_um_por_rodada():
    e = _fresh_enemy()
    cm.apply_condition(e, fx.sangria_condition(3))
    taken = []
    for _ in range(4):
        before = e["vitalidade"]
        orch._tick_conditions_v4(e, {"logs": []})
        taken.append(before - e["vitalidade"])
    assert taken == [3, 2, 1, 0]
    assert not fx.has_condition(e, "sangria")


def test_vigilia_persiste_no_fim_da_rodada_e_e_consumida():
    p = _actor("player")
    fx.add_vigilia(p, 3)
    fx.add_vigilia(p, 2)  # acumula
    present = list(p["active_conditions"])
    for _ in range(3):
        orch._expire_stat_conditions(p, present, {"logs": []})
    assert cm.combat_modifiers(p)["vigilia"] == 5
    p["vitalidade"] = p["max_vitalidade"] = 40
    assert _hit(p, 4) == 0
    assert cm.combat_modifiers(p)["vigilia"] == 1
    assert _hit(p, 4) == 3
    assert not fx.has_condition(p, "vigilia")


def test_vigilia_como_carta_vai_para_si(examples):
    player = _player(["ex330_muralha_vigilante"])
    out = _play(player, _fresh_enemy(), "ex330_muralha_vigilante", target=None)
    assert cm.combat_modifiers(player)["vigilia"] == 3, out["logs"]


def test_marca_do_abismo_bonus_entropia_e_consumo(examples):
    player = _player(["ex330_dedo_do_abismo", "arc_descarga"], entropy=5)
    e = _fresh_enemy()
    _play(player, e, "ex330_dedo_do_abismo")
    assert cm.has_control(e, "marca")
    entropy = player["entropy"]
    out = _play(player, e, "arc_descarga", seed=5)
    assert any("Marca do Abismo" in log and "+3" in log for log in out["logs"])
    assert player["entropy"] == entropy - 1 + 1  # paga 1, ganha 1 ao acertar
    assert not fx.has_condition(e, "marca")  # consumida


_GATILHO_FRUSTRADO = {
    "owner_id": "player",
    "card_id": "ex330_muralha_vigilante",
    "efeito": {"kind": "vigilia", "valor": 2, "quando": "ao_pressagio_frustrado"},
}


def _intent(tipo="ataque"):
    # Formato real da SPEC-329 (`enemy_intent.forecast_round`).
    return {"actor_id": "e", "idx": 0, "tipo": tipo, "alvo_id": "player", "carta_id": None}


def _interrupt_with(pressagios, cursor):
    player = _player(["ex330_golpe_interruptor"], entropy=5)
    e = _fresh_enemy()
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [dict(_GATILHO_FRUSTRADO)]
    actors = {"player": player, "e": e}
    token = fx.bind(
        scene,
        actors,
        {"hero": ["player"], "enemy": ["e"]},
        pressagios=pressagios,
        intent_cursor=cursor,
    )
    try:
        out = _play(player, e, "ex330_golpe_interruptor", scene=scene)
    finally:
        fx.unbind(token)
    return player, e, out


def test_interromper_marca_presagio_pendente_e_dispara_gatilho(examples):
    pressagios = {"e": [_intent()]}
    player, e, out = _interrupt_with(pressagios, {})
    assert cm.has_control(e, "stun")
    assert pressagios["e"][0]["interrompido_por"] == "player"
    assert {"keyword": "interromper", "actor_id": "player", "target_id": "e"} in out["keywords"]
    assert cm.combat_modifiers(player)["vigilia"] == 2  # gatilho rodou na hora


@pytest.mark.parametrize(
    "pressagios, cursor",
    [
        ({"e": [_intent()]}, {"e": 1}),  # o inimigo já agiu nesta rodada
        ({"e": [_intent("defesa")]}, {}),  # presságio não é de ataque
        ({}, {}),  # sem presságio (flag off/shadow)
    ],
)
def test_interromper_sem_presagio_de_ataque_pendente_nao_conta(examples, pressagios, cursor):
    player, _e, out = _interrupt_with(pressagios, cursor)
    assert not any(k["keyword"] == "interromper" for k in out.get("keywords", []))
    assert (
        "vigilia" not in cm.combat_modifiers(player) or not cm.combat_modifiers(player)["vigilia"]
    )


def test_interromper_no_run_round_com_presagio_real(examples, monkeypatch):
    """Ponta a ponta com RPG_ENEMY_INTENT=on: o herói age primeiro, atordoa o
    inimigo que anunciou ataque; a rodada registra o frustrado com `via`."""
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    player = _player(["ex330_golpe_interruptor"], entropy=5)
    e = _fresh_enemy()
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [dict(_GATILHO_FRUSTRADO)]
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={
            "player": {
                "actor_id": "player",
                "acao": {"kind": "card", "card_id": "ex330_golpe_interruptor", "target_id": "e"},
            }
        },
        pressagios={"e": [_intent()]},
        initiator="heroes",
        rng=random.Random(3),
    )
    # (o Atordoado de 1 rodada já expirou no turno perdido do inimigo)
    assert any("atordoado e perde o turno" in log for log in out["logs"])
    frustrated = out["pressagios_frustrados"]
    assert frustrated[0]["actor_id"] == "e"
    assert frustrated[0]["via"] == "interromper" and frustrated[0]["por"] == "player"
    assert [g["gatilho"] for g in out["gatilhos"]].count("ao_pressagio_frustrado") == 1


def test_presagio_frustrado_sem_interromper_dispara_para_a_mira(examples, monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    player = _player([])
    e = _fresh_enemy()
    cm.apply_condition(e, {"name": "Atordoado", "dot": 0, "duration": 1, "control": "stun"})
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [dict(_GATILHO_FRUSTRADO)]
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": {"actor_id": "player"}},
        pressagios={"e": [_intent()]},
        rng=random.Random(3),
    )
    assert out["pressagios_frustrados"][0].get("via") is None
    assert any(g["gatilho"] == "ao_pressagio_frustrado" for g in out["gatilhos"])


def test_sacrificio_paga_vitalidade_antes_dos_efeitos(examples):
    player = _player(["ex330_preco_de_sangue"], entropy=0)
    vit = player["vitalidade"]
    out = _play(player, _fresh_enemy(), "ex330_preco_de_sangue")
    assert player["vitalidade"] == vit - 2
    assert player.get("_self_harmed_round") is True
    i_cost = next(i for i, log in enumerate(out["logs"]) if "Sacrifício 2" in log)
    i_hit = next(i for i, log in enumerate(out["logs"]) if "player → e" in log)
    assert i_cost < i_hit  # R11: custo antes do efeito
    assert "**Sacrifício** 2" in fx.render_card_text(
        fx.materialize(_examples()["ex330_preco_de_sangue"])
    )


def test_chamado_so_vale_perto_do_abismo(examples):
    def dano(entropy):
        player = _player(["ex330_chamado_da_fenda"], entropy=entropy)
        e = _fresh_enemy()
        out = _play(player, e, "ex330_chamado_da_fenda")
        return 60 - e["vitalidade"], out

    low, out_low = dano(2)  # 2 - 1 = 1 < 4
    high, out_high = dano(9)
    assert high == low + 3
    assert any(k["keyword"] == "chamado" for k in out_high["keywords"])
    assert not any(k.get("keyword") == "chamado" for k in out_low.get("keywords", []))


# ---------------------------------------------------------------- Grupo B (SPEC-328)
@pytest.mark.parametrize("key", ["exaurir", "guardar", "eco", "ressoar", "fardo", "vazao"])
def test_grupo_b_tem_glossario_validador_e_texto(key):
    entry = fx.glossary()[key]
    assert entry["grupo"] == "B" and entry["regra"] and entry["sabor"]
    val = 2 if fx.CARD_KEYWORDS[key] == "int" else True
    card = {
        "id": "x",
        "name": "X",
        "tipo": "ativa",
        "efeitos": [{"kind": "comprar", "valor": 1}]
        + (
            [{"kind": "ganhar_folego", "valor": 1, "quando": "ao_descartar"}]
            if key == "vazao"
            else []
        ),
        "palavras_chave": {key: val},
    }
    assert fx.validate_card(card) == []
    assert f"**{entry['nome']}**" in fx.render_card_text(card)


def test_grupo_b_efeitos_de_pilha_ficam_pendentes_sem_efeito(examples):
    player = _player(["ex330_valvula_fria"])
    out = _play(player, _fresh_enemy(), "ex330_valvula_fria", target=None)
    assert out["pendente_pilhas"][0]["kind"] == "comprar"


def test_vazao_exige_efeito_ao_descartar():
    card = {"efeitos": [{"kind": "comprar", "valor": 1}], "palavras_chave": {"vazao": True}}
    assert any("Vazão" in e for e in fx.validate_card(card))


# ---------------------------------------------------------------- R10 glossário
def test_glossario_tem_as_14_palavras_chave():
    g = fx.glossary()
    assert set(g) == set(fx.KEYWORDS) and len(fx.KEYWORDS) == 14
    for key, entry in g.items():
        assert entry["nome"] and entry["regra"] and entry["sabor"], key
        assert entry["grupo"] == ("A" if key in fx.KEYWORDS_GRUPO_A else "B")


def test_glossario_para_prompt_so_as_em_jogo():
    block = fx.glossary_for_prompt(["rachadura", "sangria", "inexistente"])
    assert "Rachadura:" in block and "Sangria:" in block and "Torpor" not in block
