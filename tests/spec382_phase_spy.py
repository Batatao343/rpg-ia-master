"""SPEC-382 (Sol P2-1): espiao de FASES do `_run_round` para o golden ficar sensivel a ordem.

Envolve, sem mudar comportamento, os colaboradores de nivel de modulo que `_run_round` chama
(nomes globais de `services.conflict_orchestrator` e funcoes dos modulos que ele usa). Cada
chamada vira `[nome, args leves...]`, na ordem em que aconteceu; dict de rodada (`out`) entra
como `out#<n logs>` e ator como `@<id>`. Uma refatoracao pura chama os mesmos globais na mesma
ordem; trocar duas fases, pular um passo ou ligar um passo cedo muda a lista.
"""

from __future__ import annotations

import functools
import importlib
from typing import Any

# (modulo, atributo). Os do orquestrador sao globais consultados na hora da chamada, entao o
# patch vale tambem dentro de helpers extraidos na Etapa 3.
TARGETS: tuple[tuple[str, str], ...] = (
    *(
        ("services.conflict_orchestrator", name)
        for name in (
            "_refused_player_item",
            "_stalemate_guard",
            "_mark_fresh_conditions",
            "_fire_omen_frustrated",
            "_taunt_target",
            "enemy_declaration",
            "_resolve_actor_turn",
            "_extra_mark",
            "_close_extra_action",
            "_note_turn_records",
            "_note_denied_span",
            "_tick_conditions_v4",
            "_check_terminal",
            "_expire_stat_conditions",
            "_resolve_last_stands",
            "resolve_terminals",
            "_maybe_abyss",
            "_record_class_event",
            "roll_initiative_by_side",
            "extra_actions",
        )
    ),
    ("services.conflict_scene", "advance_tactical_state"),
    ("services.scene_cards", "tick"),
    ("services.scene_cards", "abyss_clock"),
    ("services.scene_cards", "clock_hard_stop"),
    ("services.scene_cards", "check_objective"),
    ("services.enemy_decks", "apply_phases"),
    ("services.enemy_decks", "check_promises"),
    ("services.enemy_decks", "close_promises"),
    ("services.enemy_decks", "note_declaration"),
    ("services.enemy_decks", "declare_extra"),
    ("services.enemy_decks", "prenuncio"),
    ("services.enemy_decks", "record_promise"),
    ("services.enemy_decks", "shadow_summary"),
    ("services.enemy_intent", "forecast_round"),
    ("services.enemy_intent", "still_possible"),
    ("services.enemy_intent", "frustrated_line"),
    ("services.card_effects", "fire"),
    ("services.card_effects", "reset_round"),
    ("combat_mechanics", "tick_boiler"),
    ("combat_mechanics", "apply_transformacao"),
    ("combat_mechanics", "apply_entropy_on_kill"),
    ("combat_mechanics", "check_recidiva"),
    ("combat_mechanics", "reset_entropy_turn"),
    ("combat_mechanics", "has_control"),
    ("services.cards", "reset_enemy_card_usage"),
    ("services.cards", "reset_card_usage"),
    ("services.card_deck_round", "refusal"),
    ("services.card_deck_round", "shadow"),
    ("services.card_deck_round", "resolve_player_plays"),
    ("services.card_deck_round", "end_round"),
    ("services.death_flow", "combat_should_end"),
)


def _light(v: Any) -> Any:
    """Resumo estavel de um argumento: escalares crus, `out` pelo tamanho do log, ator pelo id."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, dict):
        if isinstance(v.get("logs"), list) and "ended" in v:
            return f"out#{len(v['logs'])}"
        if "id" in v and isinstance(v.get("id"), str):
            return f"@{v['id']}"
        return "{}"
    if isinstance(v, (list, tuple)):
        return f"[{len(v)}]"
    return type(v).__name__


def install(monkeypatch, calls: list) -> None:
    """Liga o espiao (desfeito pelo `monkeypatch` no fim do caso)."""
    for mod_name, attr in TARGETS:
        mod = importlib.import_module(mod_name)
        orig = getattr(mod, attr)
        label = f"{mod_name.rsplit('.', 1)[-1]}.{attr}"

        def wrapper(*a, __orig=orig, __label=label, **kw):
            row = [__label, *(_light(v) for v in a)]
            row += [f"{k}={_light(kw[k])}" for k in sorted(kw)]
            calls.append(row)
            return __orig(*a, **kw)

        functools.update_wrapper(wrapper, orig)
        monkeypatch.setattr(mod, attr, wrapper)
