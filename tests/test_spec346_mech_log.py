"""SPEC-346 R7-R10: o mech_log fecha a conta (DoT, critico por dupla, Ultima Acao)."""

from __future__ import annotations

import random

import pytest

from services import combat_preview as preview
from services import conflict_damage as cd
from services import conflict_orchestrator as orch
from services import conflict_turn as ct
from tests.test_fix_vitalidade_terminal import _actor, _HighRng, _scene

SIDES = {"hero": ["player"], "ally": [], "enemy": ["boss"]}


class _OnesRng:
    """Dados sempre 1 -> dupla de 1 (critico por regra) com total baixo."""

    def randint(self, _a, _b):
        return 1

    def random(self):
        return 0.99


def _names(*actors):
    return list(actors)


def test_dot_tick_has_line_and_structured_record():
    hero = _actor("player", corpo=3, is_player=True)
    hero["active_conditions"] = [
        {"name": "Toque Gélido da Morte", "dot": 3, "duration": 3, "damage_type": "gelido"}
    ]
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["dano_base_arma"] = 1
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={},
        initiator="heroes",
        rng=random.Random(3),
    )
    assert out["ticks"], "o tick de DoT precisa de registro estruturado"
    tick = out["ticks"][0]
    assert tick["condition"] == "Toque Gélido da Morte" and tick["actor_id"] == "player"
    assert set(tick) >= {"actor_id", "condition", "damage_type", "dano_final", "vitalidade_depois"}
    lines = preview.mech_log(out["attacks"], _names(hero, boss), out["ticks"])
    assert any(
        ln.startswith("Toque Gélido da Morte → Você · dano contínuo · ") and ln.endswith(" dano")
        for ln in lines
    )


def test_dot_with_zero_damage_still_has_line():
    lines = preview.mech_log(
        [],
        [],
        [{"actor_id": "player", "condition": "Veneno", "dano_final": 0, "damage_type": "x"}],
    )
    assert lines == ["Veneno → Você · dano contínuo · 0 dano"]


def test_crit_by_doubles_below_esquiva_is_labeled():
    hero = _actor("player", corpo=3, is_player=True)
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["esquiva"] = 30
    decl = ct.TurnDeclaration(
        actor_id="player",
        acao=ct.TurnStep(kind="attack", target_id="boss", params={"dano_base": 5}),
    )
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={"player": decl},
        initiator="heroes",
        rng=_OnesRng(),
    )
    atk = next(a for a in out["attacks"] if a["actor_id"] == "player")
    assert atk["resultado"] == "critico" and atk["total"] < atk["esquiva_alvo"]
    line = preview.mech_log([atk], [hero, boss])[0]
    assert "crítico (dupla de 1)" in line


def test_crit_label_when_total_beats_esquiva():
    atk = {
        "actor_id": "player",
        "target_id": "boss",
        "dice_kept": [4, 4],
        "dice_rolled": [4, 4],
        "virtude": 3,
        "modificador": 0,
        "total": 11,
        "esquiva_alvo": 8,
        "resultado": "critico",
        "acerto": True,
        "dano_final": 9,
    }
    assert "crítico (dupla de 4) · 9 dano" in preview.mech_log([atk], [])[0]


def _last_stand_setup(extra_target_dead=False):
    hero = _actor("player", corpo=3, is_player=True)
    a = _actor("a", corpo=3, categoria="padrao")
    b = _actor("b", corpo=3, categoria="padrao")
    a["virtudes"]["agilidade"] = 9  # "mais proximo" = maior Agilidade -> A
    b["virtudes"]["agilidade"] = 1
    if extra_target_dead:
        b["dead"] = True
    hero["last_stand_pending"] = True
    sides = {"hero": ["player"], "ally": [], "enemy": ["a", "b"]}
    return hero, a, b, sides


def test_last_stand_uses_declared_target():
    hero, a, b, sides = _last_stand_setup()
    out = {
        "logs": [],
        "attacks": [{"actor_id": "player", "target_id": "b"}],
        "terminal": ["player"],
        "deaths": [],
    }
    orch._resolve_last_stands(
        _scene("player", "a", "b"), {"player": hero, "a": a, "b": b}, sides, out, _HighRng()
    )
    last = out["attacks"][-1]
    assert last["target_id"] == "b" and last["label"] == "Última Ação"
    assert last["alvo_declarado"] is True
    line = preview.mech_log([last], [hero, a, b])[0]
    assert line.startswith("Última Ação: Você → B (alvo declarado) ·")


def test_last_stand_falls_back_to_nearest_when_declared_is_dead():
    hero, a, b, sides = _last_stand_setup(extra_target_dead=True)
    out = {
        "logs": [],
        "attacks": [{"actor_id": "player", "target_id": "b"}],
        "terminal": ["player"],
        "deaths": [],
    }
    orch._resolve_last_stands(
        _scene("player", "a", "b"), {"player": hero, "a": a, "b": b}, sides, out, _HighRng()
    )
    assert out["attacks"][-1]["target_id"] == "a"
    assert out["attacks"][-1]["alvo_declarado"] is False


def test_enemy_last_stand_uses_pressagio_target():
    boss = _actor("boss", corpo=3, categoria="chefe")
    boss["last_stand_pending"] = True
    hero = _actor("player", corpo=3, is_player=True)
    hero["virtudes"]["agilidade"] = 9
    ally = _actor("ally1", corpo=3, categoria="padrao")
    ally["virtudes"]["agilidade"] = 1
    sides = {"hero": ["player"], "ally": ["ally1"], "enemy": ["boss"]}
    out = {
        "logs": [],
        "attacks": [],
        "terminal": ["boss"],
        "deaths": [],
        "pressagios_cumpridos": [{"actor_id": "boss", "tipo": "atacar", "alvo_id": "ally1"}],
    }
    orch._resolve_last_stands(
        _scene("player", "ally1", "boss"),
        {"player": hero, "ally1": ally, "boss": boss},
        sides,
        out,
        _HighRng(),
    )
    assert out["attacks"][-1]["target_id"] == "ally1"


@pytest.mark.parametrize("seed", range(20))
def test_mech_log_accounts_for_hero_vitality(seed, monkeypatch):
    """R10: soma de dano das linhas contra o heroi = queda de Vitalidade + excedente (Ferimento)."""
    hero = _actor("player", corpo=5, is_player=True)
    hero["active_conditions"] = [
        {"name": "Sangria", "dot": 2, "duration": 3, "damage_type": "cortante"}
    ]
    boss = _actor("boss", corpo=3, categoria="padrao")
    boss["dano_base_arma"] = 4
    results = []
    real = cd.resolve_damage_and_wounds

    def spy(target, **kw):
        res = real(target, **kw)
        if target is hero:
            results.append(res)
        return res

    monkeypatch.setattr(orch, "resolve_damage_and_wounds", spy)
    vit_before = hero["vitalidade"]
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        SIDES,
        declarations={},
        initiator="enemy",
        rng=random.Random(seed),
    )
    import re

    # R10 sobre as LINHAS do mech_log (o que o jogador lê), não sobre out["attacks"]
    lines = preview.mech_log(out["attacks"], [hero, boss], out["ticks"])
    lines_total = sum(
        int(m.group(1)) for ln in lines if "→ Você" in ln and (m := re.search(r"(\d+) dano$", ln))
    )
    drop = vit_before - hero["vitalidade"]
    excess = sum(int(r.get("excedente", 0) or 0) for r in results)
    assert lines_total == drop + excess, (seed, lines_total, drop, excess)


def test_last_stand_uses_declared_target_even_if_hero_fell_before_acting():
    """P2-1: emboscada derruba o herói antes de agir; a Última Ação mira o alvo DECLARADO."""
    hero, a, b, sides = _last_stand_setup()
    out = {"logs": [], "attacks": [], "terminal": ["player"], "deaths": []}
    orch._resolve_last_stands(
        _scene("player", "a", "b"),
        {"player": hero, "a": a, "b": b},
        sides,
        out,
        _HighRng(),
        preferred_targets={"player": "b"},
    )
    assert out["attacks"][-1]["target_id"] == "b"


def test_last_stand_label_only_when_attack_was_added(monkeypatch):
    hero, a, b, sides = _last_stand_setup()
    prior = {"actor_id": "a", "target_id": "player", "label": None}
    out = {"logs": [], "attacks": [prior], "terminal": ["player"], "deaths": []}
    monkeypatch.setattr(orch, "_basic_attack", lambda *args, **k: None)  # nada acrescentado
    orch._resolve_last_stands(
        _scene("player", "a", "b"), {"player": hero, "a": a, "b": b}, sides, out, _HighRng()
    )
    assert "label" in prior and prior["label"] is None and "alvo_declarado" not in prior


@pytest.mark.parametrize(
    "enemy_id", ["enemy_bandido", "mon_corvo_gelo", "enemy_soldado_legiao_ferro"]
)
@pytest.mark.parametrize("seed", range(10))
def test_mech_log_accounts_with_enemy_cards_in_play(seed, enemy_id, monkeypatch):
    """R10 com inimigo do bestiário (Cartas inimigas, efeitos e DoT): linhas do mech_log
    contra o herói = queda real da Vitalidade + excedente que virou Ferimento."""
    import re

    from agents.bestiary import template_by_id

    template = template_by_id(enemy_id, encounter_level=4)
    assert template, f"{enemy_id} precisa existir no bestiário"
    foe = orch.ensure_combat_sheet(dict(template) | {"id": "boss"})
    hero = _actor("player", corpo=5, is_player=True)
    hero["esquiva"] = 4
    results = []
    real = cd.resolve_damage_and_wounds

    def spy(target, **kw):
        res = real(target, **kw)
        if target is hero:
            results.append(res)
        return res

    monkeypatch.setattr(orch, "resolve_damage_and_wounds", spy)
    monkeypatch.setattr(cd, "resolve_damage_and_wounds", spy)
    vit_before = hero["vitalidade"]
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": foe},
        SIDES,
        declarations={},
        initiator="enemy",
        rng=random.Random(seed),
    )
    lines = preview.mech_log(out["attacks"], [hero, foe], out["ticks"])
    lines_total = sum(
        int(m.group(1)) for ln in lines if "→ Você" in ln and (m := re.search(r"(\d+) dano$", ln))
    )
    drop = vit_before - hero["vitalidade"]
    excess = sum(int(r.get("excedente", 0) or 0) for r in results)
    assert lines_total == drop + excess, (enemy_id, seed, lines, drop, excess)


def _hero_lines_total(out, actors):
    import re

    lines = preview.mech_log(out["attacks"], actors, out.get("ticks") or [], out.get("heals") or [])
    dmg = sum(
        int(m.group(1)) for ln in lines if "→ Você" in ln and (m := re.search(r"(\d+) dano$", ln))
    )
    heal = sum(
        int(m.group(1))
        for ln in lines
        if "→ Você" in ln and (m := re.search(r"cura · (\d+) Vitalidade$", ln))
    )
    return dmg, heal


@pytest.mark.parametrize("reaction", ["san_esquiva", "san_troco_carmesim"])
@pytest.mark.parametrize("seed", range(12))
def test_mech_log_accounts_when_hero_plays_cards_heal_and_reaction(seed, reaction, monkeypatch):
    """P3-8: o herói joga Cartas (dano + cura) e uma Reação (reflexo / contra-ataque) com o
    goblin atacando forte. Linhas do mech_log contra o herói = queda real + excedente - cura."""
    from tests.test_round_multi_play import _card, _plays, _run, _setup

    results = []
    real = cd.resolve_damage_and_wounds

    def spy(target, **kw):
        res = real(target, **kw)
        if target.get("is_player"):
            results.append(res)
        return res

    monkeypatch.setattr(orch, "resolve_damage_and_wounds", spy)
    monkeypatch.setattr(cd, "resolve_damage_and_wounds", spy)
    hand = ["bas_san_golpe", "bas_med_pressao", "bas_san_guarda", reaction, "san_finta"]
    scene, actors, sides, state = _setup(mode="on", hand=hand)
    actors["gob_1"]["dano_base_arma"] = 6
    actors["gob_1"]["attack_formula"] = "1d6+4"
    hero = actors["player"]
    hero["prepared_cards"] = list(
        dict.fromkeys([*hero["prepared_cards"], reaction, "bas_med_pressao"])
    )
    hero["esquiva"] = 2  # o goblin acerta: a conta de dano precisa ter o que fechar
    hero["vitalidade"] = max(1, hero["max_vitalidade"] - 6)
    state["_player_reaction_card_id"] = reaction
    decl = _plays(_card("bas_san_golpe"), _card("bas_med_pressao", "player"))
    decl.reaction_card_id = reaction
    before = hero["vitalidade"]
    out = _run(scene, actors, sides, state, decl, seed=seed)
    dmg, heal = _hero_lines_total(out, list(actors.values()))
    gained = hero["vitalidade"] - before
    excess = sum(int(r.get("excedente", 0) or 0) for r in results)
    # vitalidade final = antes - dano_total + excedente(o que ficou como Ferimento) + cura
    assert gained == heal - dmg + excess, (seed, reaction, out["logs"], dmg, heal, gained, excess)
    assert heal > 0, "a Carta de cura precisa ter sido jogada"
    assert out["cards_used"], "o herói precisa ter jogado Carta"


def test_mech_log_accounts_for_ally_support_heal():
    """R10: a cura por ação de apoio de aliado também tem linha e fecha com a Vitalidade real."""
    hero = _actor("player", corpo=3, is_player=True)
    hero["vitalidade"] = hero["max_vitalidade"] - 5
    ally = _actor("medico", corpo=3, categoria="padrao")
    ally["tactical_archetype"] = "suporte"
    foe = _actor("boss", corpo=3, categoria="padrao")
    sides = {"hero": ["player"], "ally": ["medico"], "enemy": ["boss"]}
    out = {"logs": [], "attacks": []}
    before = hero["vitalidade"]
    orch._resolve_tactical_action(
        _scene("player", "medico", "boss"),
        ally,
        "medico",
        {"player": hero, "medico": ally, "boss": foe},
        sides,
        ct.TurnStep(kind="maneuver", maneuver="support", target_id="player"),
        out,
        random.Random(1),
    )
    gained = hero["vitalidade"] - before
    assert gained == 2
    lines = preview.mech_log([], [hero, ally, foe], [], out["heals"])
    assert lines == [f"Apoio → Você · cura · {gained} Vitalidade"]
