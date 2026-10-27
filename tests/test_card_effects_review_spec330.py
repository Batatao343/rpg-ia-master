"""SPEC-330 — correções da revisão Sol (handoffs/SPEC-330-sol-review.md).

P1-1 Interromper × ações extras (SPEC-295) · P1-2 `ao_derrubar` por categoria ·
P2-1 hostil sem alvo em Carta de suporte · P2-2 caminho de erro · P2-3 gatilhos de
dano no `run_round` · P2-6 dano extra respeita golpe não-letal · P2-7 catálogo de
condições em `alvo_tem`/`eu_tenho`."""

import random

import pytest

import combat_mechanics as cm
from services import card_effects as fx
from services import cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}
_MIRA = {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
_FORCA = {"name": "Fúria", "dot": 0, "duration": 9, "stat": "damage", "delta": 40}


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


def _armed(owner: str, quando: str, valor: int = 1) -> dict:
    return {
        "owner_id": owner,
        "card_id": f"t_{quando}",
        "efeito": {"kind": "vigilia", "valor": valor, "quando": quando},
    }


def _card(monkeypatch, cid: str, **fields) -> dict:
    card = {
        "id": cid,
        "name": cid,
        "tipo": "ativa",
        "classe": "Sangromante",
        "patamar": "inicial",
        "custo_entropia": 0,
        "frequencia": "livre",
        "virtude_permitida": ["forca"],
        **fields,
    }
    monkeypatch.setitem(cards._load_cards(), cid, fx.materialize(card))
    return card


def _hero(card_ids=(), **kw) -> dict:
    p = _actor(
        "player",
        class_name="Sangromante",
        known_cards=list(card_ids),
        prepared_cards=list(card_ids),
        entropy=20,
        max_entropy=99,
        level=20,
        **kw,
    )
    cm.apply_condition(p, dict(_MIRA))
    return p


def _intent(idx: int) -> dict:
    return {
        "actor_id": "e",
        "idx": idx,
        "tipo": "ataque",
        "alvo_id": "player",
        "carta_id": None,
        "declaration": {"actor_id": "e", "acao": {"kind": "attack", "target_id": "player"}},
    }


def _boss(**kw) -> dict:
    kw.setdefault("acoes_por_rodada", 2)
    e = _actor("e", categoria="chefe", **kw)
    e["vitalidade"] = e["max_vitalidade"] = 80
    return e


def _play_decl(card_id: str) -> dict:
    return {"actor_id": "player", "acao": {"kind": "card", "card_id": card_id, "target_id": "e"}}


def _no_overlap(out: dict) -> None:
    cumpridos = len(out.get("pressagios_cumpridos", []))
    frustrados = len(out.get("pressagios_frustrados", []))
    assert cumpridos + frustrados <= 2  # 2 presságios, cada um no máximo em uma lista


# ---------------------------------------------------------------- P1-1
def test_atordoar_depois_da_1a_acao_do_chefe_nao_interrompe(monkeypatch):
    """O Chefe age primeiro; o atordoamento no meio da rodada não nega a ação
    extra (SPEC-295) — então NÃO é Interromper e o 2º presságio se cumpre."""
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    _card(
        monkeypatch,
        "rv_stun",
        efeitos=[{"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1}],
        palavras_chave={"interromper": True},
    )
    player, e = _hero(["rv_stun"]), _boss()
    player["vitalidade"] = player["max_vitalidade"] = 200
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [_armed("player", "ao_pressagio_frustrado")]
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": _play_decl("rv_stun")},
        pressagios={"e": [_intent(0), _intent(1)]},
        initiator="enemy",
        rng=random.Random(4),
    )
    assert not any(k["keyword"] == "interromper" for k in out.get("keywords", []))
    assert not any(g["gatilho"] == "ao_pressagio_frustrado" for g in out.get("gatilhos", []))
    assert len(out["pressagios_cumpridos"]) == 2
    assert not out.get("pressagios_frustrados")
    _no_overlap(out)


def test_atordoar_antes_da_1a_acao_interrompe_uma_vez(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    _card(
        monkeypatch,
        "rv_stun",
        efeitos=[{"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1}],
        palavras_chave={"interromper": True},
    )
    player, e = _hero(["rv_stun"]), _boss()
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [_armed("player", "ao_pressagio_frustrado")]
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": _play_decl("rv_stun")},
        pressagios={"e": [_intent(0), _intent(1)]},
        initiator="heroes",
        rng=random.Random(4),
    )
    frus = out["pressagios_frustrados"]
    assert [f.get("via") for f in frus] == ["interromper"]
    assert not out.get("pressagios_cumpridos")
    assert [g["gatilho"] for g in out["gatilhos"]].count("ao_pressagio_frustrado") == 1
    _no_overlap(out)


def test_queda_real_depois_da_1a_acao_interrompe_a_extra(monkeypatch):
    """Queda real (Última Ação/terminal) conta sempre: o Chefe agiu uma vez, cai
    com o golpe Interromper e a ação extra vira frustrada (nunca cumprida)."""
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    _card(
        monkeypatch,
        "rv_golpe",
        efeitos=[{"kind": "dano", "dano_base": 60, "categoria_arma": "pesada"}],
        palavras_chave={"interromper": True},
    )
    player = _hero(["rv_golpe"])
    player["vitalidade"] = player["max_vitalidade"] = 200
    e = _boss(ferimento_espacos={"leve": 1, "grave": 1, "critico": 1})
    e["vitalidade"] = 0
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [_armed("player", "ao_pressagio_frustrado")]
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": _play_decl("rv_golpe")},
        pressagios={"e": [_intent(0), _intent(1)]},
        initiator="enemy",
        rng=random.Random(4),
    )
    assert fx.has_fallen(e)
    assert len(out["pressagios_cumpridos"]) == 1
    assert [f.get("via") for f in out["pressagios_frustrados"]] == ["interromper"]
    _no_overlap(out)


def test_presagio_interrompido_nunca_se_cumpre(monkeypatch):
    """Defesa extra: intent marcado `interrompido_por` que ainda seria possível
    vira frustrado e o inimigo não executa o golpe."""
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    player, e = _hero(), _boss(acoes_por_rodada=1)
    intent = dict(_intent(0), interrompido_por="player")
    vit = player["vitalidade"]
    out = orch.run_round(
        _scene("player", "e"),
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": {"actor_id": "player"}},
        pressagios={"e": [intent]},
        initiator="enemy",
        rng=random.Random(4),
    )
    assert not out.get("pressagios_cumpridos")
    assert out["pressagios_frustrados"][0]["motivo"] == "interrompido"
    assert player["vitalidade"] == vit


# ---------------------------------------------------------------- P1-2
@pytest.mark.parametrize(
    "categoria", ["lacaio", "padrao", "elite", "chefe", "nomeado", "companheiro", "jogador"]
)
def test_ao_derrubar_dispara_para_toda_categoria(categoria):
    if categoria == "jogador":
        attacker_id, target_id = "e", "player"
        target = _actor("player")
        attacker = _actor("e")
        sides = {"hero": ["player"], "enemy": ["e"]}
        initiator = "enemy"
    elif categoria == "companheiro":
        attacker_id, target_id = "e", "c"
        target = _actor("c", categoria="companheiro")
        attacker = _actor("e")
        sides = {"hero": ["player"], "ally": ["c"], "enemy": ["e"]}
        initiator = "enemy"
    else:
        attacker_id, target_id = "player", "e"
        target = _actor("e", categoria=categoria)
        attacker = _actor("player")
        sides = {"hero": ["player"], "enemy": ["e"]}
        initiator = "heroes"
    for cond in (_MIRA, _FORCA):
        cm.apply_condition(attacker, dict(cond))
    target["vitalidade"] = 0
    target["ferimento_espacos"] = {"leve": 1, "grave": 1, "critico": 1}
    actors = {attacker_id: attacker, target_id: target}
    if "player" not in actors:
        actors["player"] = _actor("player")
    scene = _scene(*actors)
    scene["gatilhos_armados"] = [_armed(attacker_id, "ao_derrubar")]
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={
            attacker_id: {
                "actor_id": attacker_id,
                "acao": {"kind": "attack", "target_id": target_id},
            },
        },
        initiator=initiator,
        rng=random.Random(2),
    )
    # (o companheiro pode ser estabilizado no fim da rodada; o gatilho já valeu)
    derr = [g for g in out.get("gatilhos", []) if g["gatilho"] == "ao_derrubar"]
    assert len(derr) == 1 and derr[0]["sujeito_id"] == attacker_id, out["logs"]


def test_atordoar_nao_e_derrubar(monkeypatch):
    _card(
        monkeypatch,
        "rv_stun2",
        efeitos=[{"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1}],
    )
    player, e = _hero(["rv_stun2"]), _actor("e")
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [_armed("player", "ao_derrubar")]
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": _play_decl("rv_stun2")},
        initiator="heroes",
        rng=random.Random(2),
    )
    assert any("atordoado" in log for log in out["logs"])
    assert not any(g["gatilho"] == "ao_derrubar" for g in out.get("gatilhos", []))


# ---------------------------------------------------------------- P2-1
def test_extra_hostil_sem_alvo_em_carta_de_suporte_vai_no_oponente(monkeypatch):
    _card(
        monkeypatch,
        "rv_sup",
        efeitos=[{"kind": "vigilia", "valor": 2}, {"kind": "torpor", "valor": 1}],
    )
    player, e = _hero(["rv_sup"]), _actor("e")
    ct.resolve_turn(
        _scene("player", "e"),
        {"player": player, "e": e},
        ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="card", card_id="rv_sup")),
        state={"player": player},
        sides={"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(1),
    )
    assert cm.combat_modifiers(player)["vigilia"] == 2
    assert not fx.has_condition(player, "torpor")
    assert fx.has_condition(e, "torpor")


# ---------------------------------------------------------------- P2-2
def test_caminho_de_erro_nao_roda_extras_mas_arma_e_registra(monkeypatch):
    _card(
        monkeypatch,
        "rv_erro",
        efeitos=[
            {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
            {"kind": "rachadura", "valor": 2},
            {"kind": "vigilia", "valor": 1, "quando": "fim_rodada"},
        ],
    )
    player = _actor(
        "player", known_cards=["rv_erro"], prepared_cards=["rv_erro"], entropy=5, max_entropy=10
    )
    e = _actor("e")
    cm.apply_condition(e, {"name": "Névoa", "dot": 0, "duration": 9, "stat": "ac", "delta": 60})
    scene = _scene("player", "e")
    out = ct.resolve_turn(
        scene,
        {"player": player, "e": e},
        ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="card", card_id="rv_erro", target_id="e")
        ),
        state={"player": player},
        sides={"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(1),
    )
    assert out["attacks"] and not out["attacks"][0]["acerto"]
    assert not fx.has_condition(e, "rachadura")
    assert scene["gatilhos_armados"][0]["card_id"] == "rv_erro"
    assert player["_cartas_rodada"][-1]["card_id"] == "rv_erro"


# ---------------------------------------------------------------- P2-3
def test_ao_receber_dano_e_ao_aliado_sofrer_no_run_round():
    player, ally, e = _actor("player"), _actor("c", categoria="companheiro"), _actor("e")
    player["vitalidade"] = player["max_vitalidade"] = 99
    for cond in (_MIRA, _FORCA):
        cm.apply_condition(e, dict(cond))
    scene = _scene("player", "c", "e")
    scene["gatilhos_armados"] = [
        _armed("player", "ao_receber_dano"),
        _armed("c", "ao_aliado_sofrer"),
    ]
    out = orch.run_round(
        scene,
        {"player": player, "c": ally, "e": e},
        {"hero": ["player"], "ally": ["c"], "enemy": ["e"]},
        {"player": player},
        declarations={
            "e": {"actor_id": "e", "acao": {"kind": "attack", "target_id": "player"}},
            "player": {"actor_id": "player"},
            "c": {"actor_id": "c"},
        },
        initiator="enemy",
        rng=random.Random(2),
    )
    got = {(g["gatilho"], g["sujeito_id"]) for g in out["gatilhos"]}
    assert ("ao_receber_dano", "player") in got and ("ao_aliado_sofrer", "c") in got


def test_dot_dispara_ao_receber_dano():
    player, e = _actor("player"), _actor("e")
    e["vitalidade"] = e["max_vitalidade"] = 40
    cm.apply_condition(e, fx.sangria_condition(2))
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [_armed("e", "ao_receber_dano")]
    out = orch.run_round(
        scene,
        {"player": player, "e": e},
        {"hero": ["player"], "enemy": ["e"]},
        {"player": player},
        declarations={"player": {"actor_id": "player"}, "e": {"actor_id": "e"}},
        rng=random.Random(2),
    )
    assert any(
        g["gatilho"] == "ao_receber_dano" and g["sujeito_id"] == "e" for g in out["gatilhos"]
    )


def test_ao_entrar_carga(monkeypatch):
    player, e = _actor("player"), _actor("e")
    actors = {"player": player, "e": e}
    scene = _scene("player", "e")
    scene["gatilhos_armados"] = [_armed("player", "ao_entrar_carga")]

    def fake_trigger(p, event, logs=None, **_):
        p["abyss_charge"] = int(p.get("abyss_charge", 0) or 0) + 1
        return logs

    monkeypatch.setattr(cm, "apply_entropy_trigger", fake_trigger)
    out: dict = {"logs": []}
    token = fx.bind(scene, actors, {"hero": ["player"], "enemy": ["e"]})
    try:
        orch._entropy_event(player, {"kind": "on_damage_taken", "amount": 3}, out)
    finally:
        fx.unbind(token)
    assert [g["gatilho"] for g in out["gatilhos"]] == ["ao_entrar_carga"]


# ---------------------------------------------------------------- P2-6
def test_dano_extra_respeita_golpe_nao_letal(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    player, e = _hero(), _actor("e", categoria="lacaio")
    e["vitalidade"] = 0
    ctx = fx.Ctx(
        scene=_scene("player", "e"),
        actors_by_id={"player": player, "e": e},
        sides={"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(1),
        nonlethal="on",
        nonlethal_actor="player",
    )
    out: dict = {"logs": []}
    fx.apply_effect(ctx, {"kind": "dano", "valor": 30}, "player", "e", out)
    assert e.get("incapacitated") and not e.get("dead")


# ---------------------------------------------------------------- P2-7
@pytest.mark.parametrize("key", ["alvo_tem", "eu_tenho"])
def test_alvo_tem_so_aceita_condicao_do_catalogo(key):
    ok = {
        "efeitos": [
            {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
            {"kind": "dano", "valor": 1, "se": {key: "rachadura"}},
        ]
    }
    bad = {
        "efeitos": [
            {"kind": "dano", "dano_base": 4, "categoria_arma": "marcial"},
            {"kind": "dano", "valor": 1, "se": {key: "lua_cheia"}},
        ]
    }
    assert fx.validate_card(ok) == []
    assert any("catálogo de condições" in m for m in fx.validate_card(bad))
    for name in ("exposto", "atordoado", "amedrontado", "sangria", "marca", "Vigília"):
        card = {"efeitos": [ok["efeitos"][0], {"kind": "dano", "valor": 1, "se": {key: name}}]}
        assert fx.validate_card(card) == [], name
