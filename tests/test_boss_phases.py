"""SPEC-332 R5: fases de chefe (baralho extra + padrão novo + troca narrada + presságio novo)."""

from __future__ import annotations

import random

import pytest

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
from services import enemy_decks as edk


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    edk.reload()


def _boss():
    return orch.ensure_combat_sheet(
        {
            "id": "chefe_1",
            "name": "Valerius",
            "categoria": "chefe",
            "arquetipo": "guardiao",
            "max_vitalidade": 40,
            "vitalidade": 40,
            "entropy": 10,
            "max_entropy": 10,
            "cartas": ["bst_postura_muralha"],
            "tactical_profile": {
                "priorities": [{"trigger": "sempre", "action_key": "attack"}],
                "padrao": ["ataque"],
                "fases": [
                    {
                        "ate_vitalidade_pct": 70,
                        "baralho_extra": ["bst_furia_final"],
                        "padrao": ["reforco_proprio", "ataque"],
                        "narracao": "{nome} cospe sangue e rasga o manto.",
                    },
                    {
                        "ate_vitalidade_pct": 30,
                        "baralho_extra": ["bst_golpe_mestre", "carta_que_nao_existe"],
                        "padrao": ["ataque"],
                    },
                ],
            },
        }
    )


def _world(boss):
    scene = cs.new_scene()
    player = orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Herói",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        },
        is_player=True,
    )
    for i in ("player", "chefe_1"):
        cs.place(scene, i)
    cs.freeze(scene)
    return (
        scene,
        {"player": player, "chefe_1": boss},
        {"hero": ["player"], "ally": [], "enemy": ["chefe_1"]},
    )


def test_phase_changes_once_with_narration_extra_deck_and_pattern():
    boss = _boss()
    _, actors, sides = _world(boss)
    out: dict = {"logs": []}
    assert edk.apply_phases(actors, sides, out) is False  # vida cheia: fase 0
    assert edk.pattern_of(boss) == ["ataque"]
    boss["vitalidade"] = 25  # 62 %
    assert edk.apply_phases(actors, sides, out) is True
    assert boss["fase_idx"] == 1
    assert "bst_furia_final" in boss["cartas"]
    assert edk.pattern_of(boss) == ["reforco_proprio", "ataque"]
    assert out["logs"] == ["Valerius cospe sangue e rasga o manto."]
    assert out["fases"] == [{"actor_id": "chefe_1", "fase": 1}]
    assert edk.apply_phases(actors, sides, out) is False  # não repete a mesma fase


def test_phase_skips_forward_and_never_regresses_or_loads_unknown_cards():
    boss = _boss()
    _, actors, sides = _world(boss)
    boss["vitalidade"] = 8  # 20 %: cruza as duas de uma vez
    out: dict = {}
    assert edk.apply_phases(actors, sides, out) is True
    assert boss["fase_idx"] == 2
    assert "bst_furia_final" in boss["cartas"] and "bst_golpe_mestre" in boss["cartas"]
    assert "carta_que_nao_existe" not in boss["cartas"]
    boss["vitalidade"] = 40  # curou: a fase não volta
    assert edk.apply_phases(actors, sides, out) is False
    assert boss["fase_idx"] == 2


def test_phases_inert_when_flag_off(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "off")
    boss = _boss()
    _, actors, sides = _world(boss)
    boss["vitalidade"] = 5
    assert edk.apply_phases(actors, sides, {"logs": []}) is False
    assert "fase_idx" not in boss


def test_run_round_narrates_phase_and_recomputes_the_presságio(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    boss = _boss()
    scene, actors, sides = _world(boss)
    stale = {
        "chefe_1": [
            {
                "actor_id": "chefe_1",
                "idx": 0,
                "tipo": "ataque",
                "alvo_id": "player",
                "carta_id": None,
                "declaration": ct.TurnDeclaration(
                    actor_id="chefe_1", acao=ct.TurnStep(kind="pass")
                ).model_dump(),
            }
        ]
    }
    boss["vitalidade"] = 20
    decl = {"player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))}
    out = orch.run_round(
        scene, actors, sides, {}, declarations=decl, rng=random.Random(3), pressagios=stale
    )
    assert any("cospe sangue" in line for line in out["logs"])
    assert out["fases"] == [{"actor_id": "chefe_1", "fase": 1}]
    # o presságio congelado antigo (passar a vez) foi descartado e recalculado na nova fase
    assert not any("cumpre o que o presságio anunciava" in line for line in out["logs"][:1])
    assert boss["fase_idx"] == 1


def test_phase_applied_at_end_of_round_before_next_forecast(monkeypatch):
    boss = _boss()
    scene, actors, sides = _world(boss)
    calls = []
    real = edk.apply_phases

    def spy(a, s, out, rnd=0):
        calls.append(rnd)
        if len(calls) == 2:  # 2a chamada = fim da rodada (depois do dano)
            boss["vitalidade"] = 16
        return real(a, s, out, rnd)

    monkeypatch.setattr(edk, "apply_phases", spy)
    decl = {"player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))}
    out = orch.run_round(scene, actors, sides, {}, declarations=decl, rng=random.Random(3))
    assert len(calls) == 2 and boss["fase_idx"] >= 1
    assert any("cospe sangue" in line for line in out["logs"])
    assert boss["fase_rnd"] == calls[1] + 1


def test_phase_signature_waits_one_telegraphed_round():
    boss = _boss()
    boss["tactical_profile"]["fases"][0]["assinatura"] = {
        "carta": "bst_furia_final",
        "a_cada_n": 2,
        "desvio": 0,
        "telegrafo": "{nome} sangra e sorri.",
    }
    _, actors, sides = _world(boss)
    boss["vitalidade"] = 20
    edk.apply_phases(actors, sides, {"logs": []}, rnd=3)  # fase 1 vale a partir da rodada 4
    assert boss["fase_rnd"] == 4
    sig = edk.assinatura_of(boss)
    assert sig["_fase"] is True
    assert edk._sig_falls_on(boss, sig, 4) is False  # cairia (par), mas sem telégrafo prévio
    assert edk.prenuncio(boss, 3) is None
    assert edk._sig_falls_on(boss, sig, 6) is True
    assert edk.prenuncio(boss, 5) == "Valerius sangra e sorri."


def test_signature_warning_goes_to_log_when_intent_is_off():
    boss = _boss()
    boss["tactical_profile"]["assinatura"] = {
        "carta": "bst_golpe_mestre",
        "a_cada_n": 3,
        "desvio": 0,
        "telegrafo": "{nome} range os dentes.",
    }
    boss["cartas"].append("bst_golpe_mestre")
    scene, actors, sides = _world(boss)
    decl = {"player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))}
    texts = []
    for _ in range(2):
        texts += orch.run_round(scene, actors, sides, {}, declarations=decl, rng=random.Random(3))[
            "logs"
        ]
    assert texts.count("Valerius range os dentes.") == 1  # fim da rodada 2 avisa a 3


# --- Lote 2: fases autoradas dos 12 chefes (`_decks.json`) --------------------------------
def test_all_twelve_bosses_have_two_authored_phases_with_valid_cards():
    from agents.bestiary import load_bestiary
    from services import cards
    from services import enemy_decks as edk

    bosses = [b for b, e in load_bestiary().items() if e.get("categoria") == "chefe"]
    assert len(bosses) == 12
    fases = edk._meta()["fases"]
    for bid in bosses:
        fs = fases[bid]
        assert [f["ate_vitalidade_pct"] for f in fs] == [60, 40]
        for f in fs:
            assert f["padrao"] and "{nome}" in f["narracao"]
            for c in f["baralho_extra"]:
                assert cards.get_card(c), (bid, c)
        sig = fs[1]["assinatura"]
        assert sig["carta"] in fs[1]["baralho_extra"] and sig["a_cada_n"] >= 2
        assert "{nome}" in sig["telegrafo"]


def test_authored_boss_phase_applies_from_decks_json_only_when_on(monkeypatch):
    from services import enemy_decks as edk

    boss = {
        "id": "enemy_boss_valerius_1",
        "archetype_id": "enemy_boss_valerius",
        "name": "Lorde",
        "cartas": ["bst_golpe_mestre"],
        "max_vitalidade": 20,
        "vitalidade": 10,
    }
    for flag in ("off", "shadow"):
        monkeypatch.setenv("RPG_ENEMY_DECKS", flag)
        edk.reload()
        b = dict(boss)
        out: dict = {}
        assert not edk.apply_phases({b["id"]: b}, {"enemy": [b["id"]]}, out)
        assert "fase_idx" not in b
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    edk.reload()
    b = dict(boss)
    out = {}
    assert edk.apply_phases({b["id"]: b}, {"enemy": [b["id"]]}, out, rnd=2)
    assert b["fase_idx"] == 1 and "inf_predador_apice_pele_de_veterano" in b["cartas"]
    assert any("Lorde" in line for line in out["logs"])
    assert out["fases"] == [{"actor_id": b["id"], "fase": 1}]


def test_authored_phase_narrations_are_distinct_per_boss():
    fases = edk._meta()["fases"]
    for idx in (0, 1):
        textos = [fs[idx]["narracao"] for fs in fases.values()]
        assert len(set(textos)) == len(textos)


def test_phase_jump_narrates_every_phase_crossed():
    boss = _boss()
    _, actors, sides = _world(boss)
    boss["vitalidade"] = 8  # 20 %: cruza as fases de 70 % e 30 % de uma vez
    out: dict = {"logs": []}
    assert edk.apply_phases(actors, sides, out, rnd=1)
    assert out["fases"] == [
        {"actor_id": "chefe_1", "fase": 1},
        {"actor_id": "chefe_1", "fase": 2},
    ]
    assert len(out["logs"]) == 2 and "cospe sangue" in out["logs"][0]


def _valerius():
    from agents.bestiary import load_bestiary

    entry = load_bestiary()["enemy_boss_valerius"]
    boss = orch.ensure_combat_sheet({**entry, "id": "enemy_boss_valerius_1"})
    boss["archetype_id"] = "enemy_boss_valerius"
    return boss


def test_prenuncio_does_not_promise_when_the_boss_would_flee():
    boss = _valerius()
    boss["vitalidade"] = int(boss["max_vitalidade"] * 0.39)
    edk.apply_phases({boss["id"]: boss}, {"enemy": [boss["id"]]}, {"logs": []}, rnd=1)
    assert boss["fase_idx"] == 2 and "inf_chefe_decreto_de_ferro" in boss["cartas"]
    sig = edk.assinatura_of(boss)
    ex = next(r for r in range(3, 14) if edk._sig_falls_on(boss, sig, r + 1))
    assert edk.prenuncio(boss, ex)  # a ~39 % o `sempre` decide: promete
    boss["vitalidade"] = int(boss["max_vitalidade"] * 0.30)  # <= 35 %: o perfil foge, nao promete
    assert edk.prenuncio(boss, ex) is None


def test_phase_two_boss_uses_signature_before_fleeing():
    """Fase 2 a ~39 % (acima de `muito_ferido` 35 %): o chefe solo ainda joga a assinatura."""
    boss = _valerius()
    boss["vitalidade"] = int(boss["max_vitalidade"] * 0.39)
    scene = cs.new_scene()
    player = orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Heroi",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        },
        is_player=True,
    )
    for i in ("player", boss["id"]):
        cs.place(scene, i)
    cs.freeze(scene)
    actors = {"player": player, boss["id"]: boss}
    sides = {"hero": ["player"], "ally": [], "enemy": [boss["id"]]}
    edk.apply_phases(actors, sides, {"logs": []}, rnd=1)
    assert boss["fase_idx"] == 2
    sig = edk.assinatura_of(boss)
    rnd = next(r for r in range(3, 14) if edk._sig_falls_on(boss, sig, r))
    decl = orch.enemy_declaration(
        scene, boss["id"], actors, sides, scene_state={"_rodada_decisao": rnd}
    )
    assert decl.acao.card_id == sig["carta"]
