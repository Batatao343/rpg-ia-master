"""Gera as copias mutadas (nunca toca o worktree). Uso: make.py <worktree> <outdir>."""

import sys
from pathlib import Path

wt, out = Path(sys.argv[1]), Path(sys.argv[2])
ORCH = (wt / "services/conflict_orchestrator.py").read_text(encoding="utf-8")
COMBAT = (wt / "agents/combat.py").read_text(encoding="utf-8")


def rep(src, a, b):
    assert src.count(a) == 1, a[:70]
    return src.replace(a, b)


def move(src, block, anchor, *, after=False):
    """Tira `block` e o recoloca antes (ou depois) de `anchor`."""
    src = rep(src, block, "")
    return rep(src, anchor, anchor + block if after else block + anchor)


M = {}
# M1: inicio da cena - impasse antes de avancar o estado tatico
M["M1_stalemate_before_tactical"] = (
    "orch",
    rep(
        ORCH,
        "    cs.advance_tactical_state(scene)\n    stalemate_events = _stalemate_guard(scene, actors_by_id, sides)\n",
        "    stalemate_events = _stalemate_guard(scene, actors_by_id, sides)\n    cs.advance_tactical_state(scene)\n",
    ),
)
# M2: fase de chefe depois do Presságio (troca de duas fases do scene_start)
_phase = "    phase_changed = _edk_mod.apply_phases(actors_by_id, sides, out, cs.tactical_round(scene))\n"
_m2 = move(ORCH, _phase, "    def _next_intent(actor_id: str) -> dict | None:\n")
_m2 = rep(_m2, "pressagios is not None and not phase_changed)", "pressagios is not None)")
M["M2_boss_phase_after_forecast"] = ("orch", _m2)
# M3: `inicio_rodada` dos atores depois da mecanica de classe do jogador
_fire = (
    "    for aid in sorted(actors_by_id):\n        if _alive(actors_by_id[aid]):\n"
    '            fx.fire("inicio_rodada", sujeito_id=aid, out=out)\n'
)
M["M3_inicio_rodada_after_class"] = (
    "orch",
    move(ORCH, _fire, "    side_actors = {\n        s: [actors_by_id[a]"),
)
# M4: esquecer de ligar `acted` (helper extraido sem o add)
M["M4_skip_acted_add"] = ("orch", rep(ORCH, "        acted.add(actor_id)\n", ""))
# M5: `_tf_acted` ligado a um set novo (closure capturou outro `acted`)
M["M5_tf_acted_fresh_set"] = (
    "orch",
    rep(
        ORCH,
        '        return acted if (intent_mode == "on" and frozen is not None) else None\n',
        '        return set() if (intent_mode == "on" and frozen is not None) else None\n',
    ),
)
# M6: declaracao do inimigo ligada cedo (antes do tick/atordoamento)
_decl = (
    "        decl = declarations.get(actor_id)\n        if decl is None:\n"
    "            decl = _enemy_decl(actor_id, actor)\n"
)
M["M6_enemy_decl_early"] = (
    "orch",
    move(ORCH, _decl, '        stunned_this_turn = cm.has_control(actor, "stun")\n'),
)
# M7: gastar Provocacao depois do registro do turno (1a acao)
M["M7_spend_taunt_after_records"] = (
    "orch",
    rep(
        ORCH,
        "        _spend_taunt(actor_id, actor)\n        _note_turn_records(_cond_before, actors_by_id, actor_id, out, scene)\n        _mark_fresh_conditions(\n            _cond_before, actors_by_id, actor_id, sides, taunt_frozen_acted=_tf_acted()\n        )\n        _expire_stat_conditions",
        "        _note_turn_records(_cond_before, actors_by_id, actor_id, out, scene)\n        _spend_taunt(actor_id, actor)\n        _mark_fresh_conditions(\n            _cond_before, actors_by_id, actor_id, sides, taunt_frozen_acted=_tf_acted()\n        )\n        _expire_stat_conditions",
    ),
)
# M8: fim de rodada - terminais antes da Ultima Acao
_ls = (
    "    _resolve_last_stands(scene, actors_by_id, sides, out, rng, preferred_targets=_declared)\n"
)
_rt = "    resolve_terminals(actors_by_id, sides, out, scene=scene, rng=rng)\n"
M["M8_terminals_before_last_stand"] = ("orch", move(ORCH, _rt, _ls))
# M9: fim de rodada - `fim_rodada` das Cartas antes da colheita de Entropia/Abismo
_fim = (
    "    for aid in sorted(actors_by_id):\n        if _alive(actors_by_id[aid]):\n"
    '            fx.fire("fim_rodada", sujeito_id=aid, out=out)\n'
)
M["M9_fim_rodada_before_entropy"] = (
    "orch",
    move(
        ORCH,
        _fim,
        "    # Fim de rodada: colheita de Entropia por morte + Recidiva + Abismo (jogador).\n",
    ),
)
# M10: fim de rodada - fase de chefe antes de fechar promessas
_cp = "    _edk_mod.close_promises(scene, actors_by_id, cs.tactical_round(scene), out)  # SPEC-355 R3\n"
M["M10_phases_before_close_promises"] = (
    "orch",
    move(ORCH, _cp, '    if _edk_mod.active() and ei.mode() != "on":\n'),
)
# M11: Cartas de Cena de fim de rodada depois dos terminais
_sc_end = (
    "    if _scene_ctx is not None:  # SPEC-331: fim de rodada da cena, antes do terminal\n"
    '        _scene_mark = len(out["logs"])\n        _sc.tick(_scene_ctx, _scene_rnd, "fim_rodada", out)\n'
    "        _sc.clock_hard_stop(_scene_ctx, _scene_rnd, out)\n"
    '        out.setdefault("scene_logs", []).extend(out["logs"][_scene_mark:])  # SPEC-346 R4\n'
)
M["M11_scene_end_after_terminals"] = ("orch", move(ORCH, _sc_end, _rt, after=True))
# M12: acao extra do chefe declarada sem `declare_extra` (perde o filtro R12 da 373)
M["M12_extra_without_declare_extra"] = (
    "orch",
    rep(
        ORCH,
        "            decl = _edk_mod.declare_extra(actor, _enemy_decl, actor_id)  # SPEC-373 R12\n",
        "            decl = _enemy_decl(actor_id, actor)\n",
    ),
)
# M13: shadow do Baralho antes da recusa do Baralho
M["M13_deck_shadow_before_refusal"] = (
    "orch",
    move(
        ORCH,
        "    _deck.shadow(state, actors_by_id, _player_id(sides), declarations, out)\n",
        "    deck_refusal = (\n",
    ),
)
# C1 (controle Sol P2-1): no de combate, close_round_log antes de close_round_meta
M["C1_combat_log_before_meta"] = (
    "combat",
    rep(
        COMBAT,
        "    _combat_close_round_meta(t)\n    _combat_close_round_log(t)\n",
        "    _combat_close_round_log(t)\n    _combat_close_round_meta(t)\n",
    ),
)

out.mkdir(parents=True, exist_ok=True)
for name, (kind, src) in M.items():
    assert src != (ORCH if kind == "orch" else COMBAT), name
    compile(src, name, "exec")
    (out / f"{kind}__{name}.py").write_text(src, encoding="utf-8")
    print(name, kind)
