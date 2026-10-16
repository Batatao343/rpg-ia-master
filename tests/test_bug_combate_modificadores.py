"""SPEC-232 — reproduções da auditoria 02-combate (BUG-02-05/06/09/10/11/13/14/15/19/20)
e do ex-R12 da SPEC-199 (carta benéfica sem alvo curava o inimigo).

Cada teste nasceu VERMELHO no HEAD 646f77e; os números vêm de rolagens com seed
fixo, nunca de narração.
"""
import random

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
import combat_mechanics as cm


def _mk(actor_id, **kw):
    base = {"id": actor_id, "name": actor_id,
            "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1}}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(actor_id == "player"))


def _scene(*ids):
    scene = cs.new_scene()
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    return scene


def _hits(attacker_conditions=(), target_conditions=(), n=200, seed=5, **akw):
    a = _mk("player", **akw)
    t = _mk("e")
    for c in attacker_conditions:
        cm.apply_condition(a, dict(c, duration=99))
    for c in target_conditions:
        cm.apply_condition(t, dict(c, duration=99))
    scene = {"zones": [{"id": "z0", "name": "z", "connections": []}], "positions": {}}
    rng = random.Random(seed)
    attacks = []
    for _ in range(n):
        t["vitalidade"] = t["max_vitalidade"]
        t["ferimentos"] = {"leve": [], "grave": [], "critico": []}
        out = ct.resolve_turn(scene, {"player": a, "e": t}, ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="attack", target_id="e")), rng=rng)
        attacks += out["attacks"]
    return attacks


# ---------------------------------------------------------------- R1 (BUG-02-05)
def test_attack_condition_changes_hit_rate():
    base = _hits()
    buffed = _hits(attacker_conditions=[{"name": "B", "dot": 0, "stat": "attack", "delta": 20}])
    evasive = _hits(target_conditions=[{"name": "D", "dot": 0, "stat": "ac", "delta": 20}])
    n_base = sum(a["acerto"] for a in base)
    assert 40 < n_base < 190
    assert sum(a["acerto"] for a in buffed) >= 190
    # Esquiva +20 só deixa passar Críticos por dupla (regra R5 da conflito-04).
    evasive_hits = [a for a in evasive if a["acerto"]]
    assert len(evasive_hits) <= 30
    assert all(a["resultado"] in ("critico", "supercritico") for a in evasive_hits)


def test_damage_and_advantage_conditions_count():
    plain = _hits(n=60)
    dmg = _hits(attacker_conditions=[{"name": "M", "dot": 0, "stat": "damage", "delta": 3}], n=60)
    for p, d in zip(plain, dmg):
        if p["acerto"]:
            assert d["dano_final"] - p["dano_final"] == 3 * p["efeito_principal_multiplicador"]
    adv = _hits(attacker_conditions=[{"name": "V", "dot": 0, "stat": "advantage", "delta": 3}], n=20)
    assert all(len(a["dice_rolled"]) == 3 and a["dice_kept"] == sorted(a["dice_rolled"])[-2:]
               for a in adv)


def test_condition_duration_counts_rounds_and_expires():
    player = _mk("player")
    enemy = _mk("e")
    scene = _scene("player", "e")
    cm.apply_condition(player, {"name": "Foco", "dot": 0, "duration": 1,
                                "stat": "attack", "delta": 20})
    actors = {"player": player, "e": enemy}
    sides = {"hero": ["player"], "enemy": ["e"]}
    decl = {"player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(
        kind="attack", target_id="e"))}
    out = orch.run_round(scene, actors, sides, {"player": player}, declarations=decl,
                         initiator="heroes", rng=random.Random(1))
    mine = [a for a in out["attacks"] if a["actor_id"] == "player"]
    assert mine and mine[0]["modificador"] == 20
    assert not player["active_conditions"], "duração 1 = uma rodada; expira ao fim dela"


# ---------------------------------------------------------------- R2 (BUG-02-06)
def test_learned_passive_buff_dano():
    without = _hits(n=80, seed=11)
    with_passive = _hits(n=80, seed=11, known_cards=["arc_des_nervo"])  # buff_dano +2
    assert any(p["acerto"] for p in without)
    for p, w in zip(without, with_passive):
        assert p["acerto"] == w["acerto"]
        if p["acerto"]:
            assert w["dano_final"] - p["dano_final"] == 2 * p["efeito_principal_multiplicador"]


def test_learned_passives_aggregates_passiva_and_virtude():
    entity = {"known_cards": ["arc_des_nervo", "arc_olho", "arc_des_nervo_exposto"],
              "virtudes": {"forca": 5, "agilidade": 1, "corpo": 1, "mente": 1, "carisma": 1},
              "virtue_cards": [{"card_id": "vc_forca_bruta", "virtude": "forca",
                                "estagio": 1, "mastery": 0}]}
    passives = cm.learned_passives(entity)
    kinds = {p["source_card"]: p for p in passives}
    assert kinds["arc_des_nervo"]["stat"] == "damage" and kinds["arc_des_nervo"]["delta"] == 2
    assert kinds["arc_olho"]["trigger"] == "perception"
    assert "arc_des_nervo_exposto" not in kinds          # ativa não é passiva
    # Virtude forca 5 = Estágio III (vale o estágio vivo, não o salvo na criação)
    assert kinds["vc_forca_bruta"]["stat"] == "damage" and kinds["vc_forca_bruta"]["delta"] == 3
    assert any(p.get("source_card") == "arc_des_nervo" for p in cm.player_passives(entity))


def test_paid_passive_vantagem_fires_once_per_scene_and_charges():
    player = _mk("player", known_cards=["dev_t7_tronco"], entropy=10, max_entropy=10,
                 class_name="Devoto do Abismo", level=15)
    enemy = _mk("e")
    scene = _scene("player", "e")
    state = {"player": player}
    attacks = []
    for _ in range(2):
        enemy["vitalidade"] = enemy["max_vitalidade"]
        out = ct.resolve_turn(scene, {"player": player, "e": enemy}, ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="attack", target_id="e")),
            state=state, rng=random.Random(3))
        attacks += out["attacks"]
    assert len(attacks[0]["dice_rolled"]) == 3          # Vantagem (3d10)
    assert len(attacks[1]["dice_rolled"]) == 2          # 1×cena
    assert player["entropy"] == 5                       # custo 5 debitado uma vez


# ---------------------------------------------------------------- R3 (BUG-02-06)
def test_reaction_contra_ataque_damages_attacker():
    dropped = 0
    for seed in range(20):
        player = _mk("player", virtudes={"forca": 2, "agilidade": 0, "corpo": 2,
                                         "mente": 1, "carisma": 1})
        enemy = _mk("e", cartas=["bst_casca_reativa"],
                    virtudes={"forca": 5, "agilidade": 2, "corpo": 3, "mente": 1, "carisma": 1})
        scene = _scene("player", "e")
        before = player["vitalidade"]
        out = {"logs": [], "deaths": [], "terminal": []}
        orch._open_reaction_window(scene, "player", "e", {"player": player, "e": enemy},
                                   {"hero": ["player"], "enemy": ["e"]}, out,
                                   rng=random.Random(seed))
        assert out["reactions"] and out["reactions"][0]["card_id"] == "bst_casca_reativa"
        dropped += player["vitalidade"] < before
    assert dropped >= 15


def test_reaction_protecao_effect_applies_to_reactor():
    player = _mk("player")
    enemy = _mk("e", cartas=["bst_defesa_instintiva"])
    scene = _scene("player", "e")
    out = {"logs": [], "deaths": [], "terminal": []}
    orch._open_reaction_window(scene, "player", "e", {"player": player, "e": enemy},
                               {"hero": ["player"], "enemy": ["e"]}, out,
                               rng=random.Random(1))
    assert cm.combat_modifiers(enemy)["protection"] == 1


# ---------------------------------------------------------------- R5 (BUG-02-09)
def _caster(**kw):
    from services import cards
    card = next(c for c in cards.all_cards().values()
                if c.get("tipo") == "ativa" and int(c.get("custo_entropia", 0) or 0) > 0
                and (c.get("efeito") or {}).get("kind") == "dano")
    player = orch.ensure_combat_sheet({
        "name": "P", "class_name": "Sangromante", "is_player": True, "level": 3,
        "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 1},
        "known_cards": [card["id"]], "prepared_cards": [card["id"]],
        "entropy": 10, "max_entropy": 10, **kw}, is_player=True)
    return player, card


def test_card_cost_not_charged_on_invalid_target():
    player, card = _caster()
    dead = _mk("dead_e", dead=True, status="morto")
    scene = {"zones": [{"id": "z0", "name": "z", "connections": []}], "positions": {}}
    for target in ("ghost", "dead_e", "player"):
        out = ct.resolve_turn(scene, {"player": player, "dead_e": dead}, ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="card", card_id=card["id"],
                                                target_id=target)),
            state={"player": player}, rng=random.Random(1))
        assert player["entropy"] == 10, (target, out["logs"])
        assert not (player.get("card_usage") or {}).get(card["id"]), target


def test_support_card_refuses_hostile_target_without_charge():
    player = _mk("player", prepared_cards=["sutura_rapida"], known_cards=["sutura_rapida"],
                 entropy=10, max_entropy=10)
    enemy = _mk("e")
    enemy["vitalidade"] = 1
    scene = _scene("player", "e")
    ct.resolve_turn(scene, {"player": player, "e": enemy}, ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="card", card_id="sutura_rapida",
                                            target_id="e")),
        state={"player": player}, sides={"hero": ["player"], "enemy": ["e"]},
        rng=random.Random(1))
    assert enemy["vitalidade"] == 1
    assert player["entropy"] == 10


# ---------------------------------------------------------------- R6 (BUG-02-10)
def test_guard_expires_next_turn():
    player = _mk("player")
    enemy = _mk("e")
    scene = _scene("player", "e")
    actors = {"player": player, "e": enemy}
    ct.resolve_turn(scene, actors, ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="maneuver", maneuver="guardar")),
        rng=random.Random(1))
    assert cs.is_guarding(scene, "player")
    out = ct.resolve_turn(scene, actors, ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="attack", target_id="e")),
        rng=random.Random(1))
    assert not cs.is_guarding(scene, "player")
    assert out["attacks"][0]["advantage"] == 0


# ---------------------------------------------------------------- R7 (BUG-02-11)
def test_dot_bypasses_armor():
    target = _mk("e")
    target["armor"] = {"protecao": 2, "integridade_atual": 5, "integridade_max": 5,
                       "reducoes_max": 0}
    before = target["vitalidade"]
    orch._apply_dot_v4(target, 1, "cortante", {"logs": []})
    assert target["vitalidade"] == before - 1
    assert target["armor"]["integridade_atual"] == 5


def test_protection_condition_absorbs_hit_but_not_dot():
    from services.conflict_damage import resolve_damage_and_wounds
    target = _mk("e")
    cm.apply_condition(target, {"name": "Muralha", "dot": 0, "duration": 2,
                                "stat": "protection", "delta": 3})
    before = target["vitalidade"]
    resolve_damage_and_wounds(target, damage_base=4, damage_type="cortante")
    assert target["vitalidade"] == before - 1
    resolve_damage_and_wounds(target, damage_base=2, damage_type="cortante",
                              bypass_armor=True)
    assert target["vitalidade"] == before - 3


# ---------------------------------------------------------------- R8 (BUG-02-14)
def test_melee_attack_engages_and_disengage_avoids_aoo():
    player = _mk("player")
    enemy = _mk("e")
    cm.apply_condition(player, {"name": "Foco", "dot": 0, "duration": 99,
                                "stat": "attack", "delta": 30})
    scene = _scene("player", "e")
    actors = {"player": player, "e": enemy}
    sides = {"hero": ["player"], "enemy": ["e"]}
    ct.resolve_turn(scene, actors, ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="attack", target_id="e")),
        rng=random.Random(2))
    assert cs.is_engaged(scene, "player", "e") and cs.is_engaged(scene, "e", "player")

    out = {"logs": [], "deaths": [], "terminal": [], "attacks": []}
    orch._resolve_actor_turn(scene, enemy, "e", actors, sides, ct.TurnDeclaration(
        actor_id="e", pos_acao=ct.TurnStep(kind="move", direction="afastar")),
        None, out, random.Random(2))
    assert any(a["actor_id"] == "player" for a in out["attacks"]), "mover sem desengajar → AoO"

    cs.engage(scene, "player", "e", spend=False)
    out = {"logs": [], "deaths": [], "terminal": [], "attacks": []}
    orch._resolve_actor_turn(scene, enemy, "e", actors, sides, ct.TurnDeclaration(
        actor_id="e", pre_acao=ct.TurnStep(kind="maneuver", maneuver="desengajar"),
        pos_acao=ct.TurnStep(kind="move", direction="afastar")),
        None, out, random.Random(2))
    assert not any(a["actor_id"] == "player" for a in out["attacks"])


# ---------------------------------------------------------------- R9
def test_early_game_initiator_only_round_1(monkeypatch):
    from agents import combat
    monkeypatch.setattr(combat.gamedata, "get_location", lambda *_: {"id": "x", "tags": []})
    state = {"world": {"current_location_id": "x"}}
    player = {"level": 1, "vitalidade": 10, "max_vitalidade": 10}
    assert combat._early_game_reaction_initiator(
        state, player, "enemy", combat_round=1) == "heroes"
    assert combat._early_game_reaction_initiator(
        state, player, "enemy", combat_round=2) == "enemy"


def test_maybe_abyss_keeps_charge_when_effect_rejected():
    player = _mk("player", abyss_charge=3)
    enemy = _mk("e")
    scene = _scene("player", "e")
    prepared = [{"id": "fissura", "gatilho": "sempre", "prioridade": 1,
                 "cargas_necessarias": 2, "usos_permitidos": 1, "base_na_cena": "altar",
                 "effect": {"kind": "apply_condition",
                            "params": {"target": "fantasma", "condition": "exposto",
                                       "duration": 1}}}]
    scene["objects"] = [{"id": "altar", "name": "Altar"}]
    out = {"logs": [], "deaths": [], "terminal": []}
    orch._maybe_abyss(scene, player, {"player": player, "e": enemy}, prepared, out,
                      rng=random.Random(1))
    assert player["abyss_charge"] == 3


def test_default_card_target_covers_purga():
    from agents import combat
    card = {"efeito": {"kind": "reduzir_carga_aliado"}}
    assert combat._default_card_target(card, "e1") == "player"


def test_api_beneficial_card_without_target_targets_player():
    import api
    state = {"combat": {"active": True},
             "enemies": [{"id": "e1", "name": "E", "status": "ativo"}]}
    req = api.ActionRequest(input_text="", card_id="sutura_rapida")
    api._apply_action_options(state, req)
    assert state["combat_declaration"]["acao"]["target_id"] == "player"
    req = api.ActionRequest(input_text="", card_id="arc_descarga")
    api._apply_action_options(state, req)
    assert state["combat_declaration"]["acao"]["target_id"] == "e1"


def test_combat_node_rejects_dead_or_self_target_for_offensive_card():
    from agents import combat
    assert combat._card_target_for(
        {"efeito": {"kind": "dano"}}, "player", active_ids=["e1"], friendly_ids=["player"]) == "e1"
    assert combat._card_target_for(
        {"efeito": {"kind": "dano"}}, "e_dead", active_ids=["e1"], friendly_ids=["player"]) == "e1"
    assert combat._card_target_for(
        {"efeito": {"kind": "cura"}}, "e1", active_ids=["e1"], friendly_ids=["player"]) == "player"


# ---------------------------------------------------------------- condições nomeadas
def test_named_condition_exposto_lowers_esquiva():
    target = _mk("e")
    base = cm.combat_modifiers(target)["ac"]
    cm.apply_condition(target, cm.parse_condition("exposto"))
    assert cm.combat_modifiers(target)["ac"] < base


# ---------------------------------------------------------------- R10 (BUG-02-13)
def test_prepare_encounter_runs_for_elite_or_abyss(monkeypatch):
    from agents import combat
    calls = []

    def fake_prepare(ctx, llm):
        calls.append(ctx)
        from services.encounter_preparation import fallback_safe_scene
        return fallback_safe_scene(ctx)

    monkeypatch.setattr(combat.prep, "prepare_encounter", fake_prepare)
    monkeypatch.setattr(combat, "build_context_pack", lambda *a, **k: type(
        "P", (), {"world_state_block": ""})())
    state = {"world": {"current_location": "Campo", "danger_level": 1}}
    combat._prepare_scene(state, [{"id": "e1", "categoria": "lacaio"}],
                          {"abyss_charge": 0, "class_name": "Devoto do Abismo"}, [])
    assert calls == []
    combat._prepare_scene(state, [{"id": "e1", "categoria": "elite"}],
                          {"abyss_charge": 0, "class_name": "Devoto do Abismo"}, [])
    assert len(calls) == 1
    combat._prepare_scene(state, [{"id": "e1", "categoria": "lacaio"}],
                          {"abyss_charge": 5, "class_name": "Devoto do Abismo"}, [])
    assert len(calls) == 2


def test_reaction_contra_ataque_not_charged_when_attacker_gone():
    """Revisão Sol: contra-ataque/dano de Reação sem atacante vivo na cena não
    cobra Entropia nem marca uso (nada a revidar)."""
    for flag in ({"dead": True}, {"fled": True}, None):
        player = _mk("player")
        if flag:
            player.update(flag)
        enemy = _mk("e", cartas=["bst_casca_reativa"], entropy=5)
        actors = {"player": player, "e": enemy} if flag else {"e": enemy}
        out = {"logs": [], "deaths": [], "terminal": []}
        orch._open_reaction_window(_scene("player", "e"), "player", "e", actors,
                                   {"hero": ["player"], "enemy": ["e"]}, out,
                                   rng=random.Random(1))
        assert not (enemy.get("enemy_card_usage") or {}).get("bst_casca_reativa")
        assert enemy["entropy"] == 5
        assert not out.get("reactions")


# ------------------------------------------- R10 (smoke real 2026-10-16)
def test_prepare_prompt_is_compact_and_lists_valid_targets():
    from services import encounter_preparation as prep
    ctx = {"location": "Forja", "encounter_level": 3, "npcs": [],
           "enemies": [{"id": "e1", "name": "Capataz", "virtudes": {"forca": 4},
                        "tactical_profile": {"x" * 50: 1}}],
           "narrative": "n" * 5000}
    prompt = prep._prep_prompt(ctx)
    assert "virtudes" not in prompt and "tactical_profile" not in prompt
    assert "player, e1" in prompt and len(prompt) < 1500


def test_prepare_encounter_deadline_falls_back(monkeypatch):
    import time as _t
    from services import encounter_preparation as prep
    monkeypatch.setenv("RPG_PREP_TIMEOUT_SECONDS", "0.2")

    class Slow:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _msgs):
            _t.sleep(1.0)
            return prep.PreparedScene(zones=[{"id": "z1", "name": "A"}])

    t0 = _t.time()
    scene = prep.prepare_encounter({"location": "X", "enemies": []}, Slow())
    assert scene["safe_fallback"] is True and _t.time() - t0 < 0.9


def test_prepared_scene_trimmed_and_gatilho_python():
    from services import encounter_preparation as prep
    eff = {"kind": "alter_terrain", "potency": "fraco"}
    proposed = prep.PreparedScene(
        zones=[{"id": f"z{i}", "name": "Z" * 500} for i in range(6)],
        objects=[{"id": f"o{i}", "base_narrativa": "pilar", "interactions": [
            {"label": "empurrar", "effect": eff}]} for i in range(5)],
        abyss_events=[{"id": f"a{i}", "base_na_cena": "o0", "effect": eff} for i in range(3)])

    class LLM:
        def with_structured_output(self, _s):
            return self

        def invoke(self, _m):
            return proposed

    scene = prep.prepare_encounter({"location": "X", "enemies": [], "encounter_level": 2}, LLM())
    assert not scene.get("safe_fallback")
    assert len(scene["zones"]) == 3 and len(scene["zones"][0]["name"]) == 120
    assert len(scene["objects"]) == 2 and len(scene["abyss_events"]) == 1
    assert scene["abyss_events"][0]["gatilho"] == "sempre"
