"""services/conflict_orchestrator.py — orquestrador de RODADA do conflito v2 (spec conflito-13, cutover).

A peça que sobe do TURNO (`conflict_turn.resolve_turn`, um ator) para a RODADA
inteira do combate, compondo TODOS os motores puros das specs 03-12, 100%
determinístico e ZERO LLM em resolução:

  iniciativa por lado (04) → cada ator age em ordem
    → tick de condições/DoT (motor de classes que SOBREVIVE)
    → Ataque de Oportunidade ao abandonar Engajamento (06)
    → janela de Reação sobre o ataque declarado (06)
    → resolução do turno declarado (`conflict_turn`, compõe 03/04/05/07)
    → gatilhos de Entropia/Carga da classe (SOBREVIVEM: on_damage_taken/…)
    → Estado Terminal → estabilização/morte (07)
    → evento do Abismo carregado por Cargas (10)
  fim de rodada → colheita de Entropia/Recidiva → detecção de encerramento (07)

`combat_node` (agents/combat.py) chama `run_round` a cada round; a IA de inimigo
(`enemy_declaration`) decide a `TurnDeclaration` por perfil tático (08), sem LLM.
O jogador chega com a `TurnDeclaration` já montada (parse CLASSIFY no nó).
"""

import contextvars
import copy
import json
import logging
import random
import re
from typing import Dict, List, Optional

import combat_mechanics as cm  # helpers que SOBREVIVEM (condições, Entropia/Carga)
import gamedata
from observability.telemetry import log_event as _log_event
from services import abyss_events, combat_flags, death_flow
from services import card_effects as fx
from services import conflict_scene as cs
from services import conflict_turn as ct
from services import enemy_decks as _edk_mod
from services import reactions as rx
from services import tactical_profile as tp
from services.conflict_damage import resolve_damage_and_wounds
from services.conflict_resolution import (
    compute_esquiva,
    resolve_attack,
    roll_initiative_by_side,
    virtude_value,
)

_VIRTUDES = ("forca", "agilidade", "corpo", "mente", "carisma")

# Mapa de `type`/`categoria` legado → categoria canônica do fluxo de morte (07/15).
_CATEGORIA_ALIAS = {
    "minion": "lacaio",
    "lacaio": "lacaio",
    "trivial": "lacaio",
    "padrao": "padrao",
    "standard": "padrao",
    "normal": "padrao",
    "grunt": "padrao",
    "elite": "elite",
    "veterano": "elite",
    "boss": "chefe",
    "chefe": "chefe",
    "chefao": "chefe",
    "nomeado": "nomeado",
    "named": "nomeado",
    "unico": "nomeado",
    "companheiro": "companheiro",
    "aliado": "companheiro",
}
_KNOWN_CATEGORIAS = (
    death_flow.FULL_FLOW_CATEGORIES
    | death_flow.NO_TERMINAL_CATEGORIES
    | death_flow.MINION_CATEGORIES
)


# ==========================================================================
# Adaptador: qualquer ator (v4 curado, legado D&D, ficha crua) → ficha v4 de combate
# ==========================================================================
def _derive_virtudes(actor: dict) -> dict[str, int]:
    return {k: virtude_value(actor, k) for k in _VIRTUDES}


def ensure_combat_sheet(actor: dict, *, is_player: bool = False, is_ally: bool = False) -> dict:
    """Normaliza `actor` (mutando) para a ficha de combate v4 que o motor novo
    consome: Virtudes 0-5, Vitalidade/espaços de Ferimento por Corpo, Esquiva,
    categoria canônica (07) e um perfil tático default para inimigo. Idempotente —
    respeita campos v4 já presentes (bestiário curado da conflito-15)."""
    if not isinstance(actor.get("virtudes"), dict) or not actor["virtudes"]:
        actor["virtudes"] = _derive_virtudes(actor)
    corpo = int(actor["virtudes"].get("corpo", 0) or 0)
    legacy_hp = actor.get("hp")
    legacy_max_hp = actor.get("max_hp")
    if not actor.get("max_vitalidade"):
        actor["max_vitalidade"] = gamedata.vitalidade_para_corpo(corpo)
    if actor.get("vitalidade") is None:
        if legacy_hp is not None and legacy_max_hp:
            ratio = max(
                0.0,
                min(1.0, float(legacy_hp) / max(1, float(legacy_max_hp))),
            )
            actor["vitalidade"] = round(int(actor["max_vitalidade"]) * ratio)
        else:
            actor["vitalidade"] = int(actor["max_vitalidade"])
    if not actor.get("ferimento_espacos"):
        actor["ferimento_espacos"] = gamedata.espacos_ferimento_para_corpo(corpo)
    fer = actor.setdefault("ferimentos", {"leve": [], "grave": [], "critico": []})
    for c in ("leve", "grave", "critico"):
        fer.setdefault(c, [])
    if actor.get("esquiva") is None:
        actor["esquiva"] = compute_esquiva(actor, include_modifiers=False)
    actor.setdefault("active_conditions", [])
    actor.setdefault("conscious", True)
    actor.setdefault("status", "ativo")
    if is_player or actor.get("is_player") or actor.get("player"):
        actor["is_player"] = True
        if actor.get("cartas"):
            actor["cartas"] = [
                entry
                for entry in actor["cartas"]
                if str(entry.get("id") if isinstance(entry, dict) else entry)
                != "bst_defesa_instintiva"
            ]
    else:
        cat = _CATEGORIA_ALIAS.get(str(actor.get("categoria") or "").strip().lower())
        if is_ally or actor.get("transient") or actor.get("origin_npc") is not None:
            cat = (
                "companheiro"  # SPEC-231 R3: aliado nunca é "padrao" nem tem política de bestiário
            )
        if not cat:
            cat = _CATEGORIA_ALIAS.get(str(actor.get("type") or "").strip().lower(), "padrao")
        actor["categoria"] = cat if cat in _KNOWN_CATEGORIAS else "padrao"
        actor["tactical_profile"] = tp.normalize_runtime_profile(
            actor, actor.get("tactical_profile") or tp._default_profile()
        )
        if actor["categoria"] != "companheiro":
            actor["pursuit_policy"] = actor["tactical_profile"].get(
                "pursuit_policy", "nao_persegue"
            )
            mind = int(actor["virtudes"].get("mente", 0) or 0)
            actor.setdefault("max_entropy", max(0, mind * 2))
            actor.setdefault("entropy", int(actor.get("max_entropy", 0) or 0))
            actor.setdefault("enemy_card_usage", {})
            enemy_cards = list(actor.get("cartas") or actor.get("enemy_cards") or [])
            known_ids = {
                str(entry.get("id") if isinstance(entry, dict) else entry) for entry in enemy_cards
            }
            if "bst_defesa_instintiva" not in known_ids:
                enemy_cards.append("bst_defesa_instintiva")
            actor["cartas"] = enemy_cards
            from services import enemy_decks as _edk  # SPEC-332 (atras de RPG_ENEMY_DECKS)

            _edk.apply_deck(actor)
    gamedata.sync_legacy_hp_aliases(actor)
    return actor


# ==========================================================================
# Estado do ator na cena
# ==========================================================================
def _name(actor: dict) -> str:
    return actor.get("name") or actor.get("id") or "?"


def _alive(actor: dict | None) -> bool:
    """Participa do combate. A DERROTA é por FLAG (dead/status), não por Vitalidade:
    no motor novo Vitalidade 0 é só 'muito ferido' — a queda vem de Ferimentos (05/07).
    Vitalidade 0 mais status ativo segue lutando até encher os espaços de Ferimento."""
    if not actor:
        return False
    if actor.get("dead") or actor.get("fled") or actor.get("surrendered"):
        return False
    if not actor.get("conscious", True) or actor.get("incapacitated"):
        return False
    return str(actor.get("status", "ativo")) not in ("morto", "fugiu", "rendido")


def _can_act(actor: dict) -> bool:
    """Pode declarar turno: vivo e NÃO em Estado Terminal (terminal só reage/estabiliza)."""
    return (
        _alive(actor) and not actor.get("estado_terminal") and not actor.get("last_stand_pending")
    )


def _agility(actor: dict) -> int:
    return virtude_value(actor, "agilidade")


def _apply_dot_v4(target: dict, dot: int, dtype: str, out: dict, rng=None) -> None:
    """DoT do motor NOVO: reduz Vitalidade; excedente vira Ferimento localizado (05).
    Sangramento/veneno ignoram armadura (dano contínuo interno)."""
    known_types = set(gamedata.DANO_FISICO) | {
        "igneo",
        "gelido",
        "eletrico",
        "arcano",
        "corrosivo",
        "abissal",
    }
    result = resolve_damage_and_wounds(
        target,
        damage_base=max(0, int(dot)),
        damage_type=dtype if dtype in known_types else "cortante",
        ignore_resistance=True,
        defensavel=False,
        bypass_armor=True,
        directed_region=None,
        rng=rng,
    )
    out["logs"] += result["log"]
    return int(result.get("dano_final", 0) or 0)


# SPEC-339: controles lidos DEPOIS do tick do portador (stun é lido antes: não entra).
_LATE_READ_CONTROLS: frozenset[str] = frozenset({"taunt", "marca", "fear", "root", "silence"})
_SKIP_KEY = "_pula_tick"


def _is_defensive_debuff(c: dict) -> bool:
    """Stat de leitura defensiva que PIORA o portador (exposto, Rachadura, armadura comprometida)."""
    stat, delta = c.get("stat"), int(c.get("delta", 0) or 0)
    return (stat in ("ac", "protection") and delta < 0) or (
        stat == "dano_recebido_pct" and delta > 0
    )


def _snapshot_conditions(actors_by_id: dict[str, dict]) -> dict[str, list[dict]]:
    return {aid: list(a.get("active_conditions") or []) for aid, a in actors_by_id.items()}


def _note_turn_records(
    before: dict[str, list[dict]], actors_by_id: dict[str, dict], actor_id: str, out: dict
) -> None:
    """SPEC-353 R51/R27: registro de view. Quem pôs cada condição nova (``condicoes_novas``) e
    quem chegou a 0 de Vitalidade ainda de pé (``sem_vitalidade``). Nunca muda mecânica."""
    seen = len(out.get("reactions") or [])
    reacted = seen > int(out.get("_reactions_noted", 0) or 0)
    out["_reactions_noted"] = seen
    for aid, actor in actors_by_id.items():
        prev = before.get(aid, [])
        for c in actor.get("active_conditions") or []:
            if c.get("persistente") or c.get("name") is None:
                continue
            if bool(c.get("_renovada")) or not any(c is p for p in prev):
                source = c.get("source_actor_id") or actor_id
                if reacted and aid == actor_id and not c.get("source_actor_id"):
                    source = None  # pode ter vindo de uma Reação: fonte DESCONHECIDA, nunca errada
                out.setdefault("condicoes_novas", []).append(
                    {
                        "victim_id": aid,
                        "condition": str(c["name"]),
                        "source_id": source,
                        "control": c.get("control"),
                    }
                )
        if aid == actor_id and _actor_key(actor) in _taunt_resisted_ids():
            _taunt_resisted_ids().remove(_actor_key(actor))
            _record_class_event(out, "special:taunt_resisted", actor_id=aid)
        if (
            not actor.get("is_player")
            and int(actor.get("vitalidade", actor.get("hp", 1)) or 0) <= 0
            and not actor.get("dead")
            and not actor.get("incapacitated")
            and actor.get("status", "ativo") == "ativo"
            and not any(x["actor_id"] == aid for x in out.get("sem_vitalidade") or [])
        ):  # o agente filtra os já avisados (combat_meta), sem marca no ator
            out.setdefault("sem_vitalidade", []).append({"actor_id": aid})


def _mark_fresh_conditions(
    before: dict[str, list[dict]],
    actors_by_id: dict[str, dict],
    current_actor_id: str | None,
    sides: dict[str, list[str]] | None = None,
    *,
    taunt_frozen_acted: set[str] | None = None,
) -> int:
    """SPEC-339: depois de um passo da rodada, marca (`_pula_tick`) a condição NOVA (ou
    renovada) que outro ator pôs em Y, para o 1º tick/expiração de Y não a consumir antes de
    valer. Controle de leitura tardia: Y != ator do turno, ou Y é o ator do turno e a fonte é
    outra (reação). Stat defensivo (R8b): só dentro do turno de outro ator e só se for
    debuff (ou buff dado por aliado do mesmo lado). `stun` e DoT nunca recebem marcador.
    `taunt_frozen_acted` (presságio `on`): o `taunt` é lido no congelamento, ANTES do tick; quem já
    agiu nesta rodada será lido no congelamento do fim dela, então não precisa pular o tick."""
    marked = 0
    team = set((sides or {}).get("hero", [])) | set((sides or {}).get("ally", []))
    for aid, actor in actors_by_id.items():
        prev = before.get(aid, [])
        for c in actor.get("active_conditions") or []:
            renewed = bool(c.pop("_renovada", False))
            if not (renewed or not any(c is p for p in prev)):
                continue
            if c.get("persistente"):
                continue
            ctl = c.get("control")
            if ctl:
                if ctl not in _LATE_READ_CONTROLS or int(c.get("dot", 0) or 0) > 0:
                    continue
                if aid == current_actor_id and str(c.get("source_actor_id") or "") == aid:
                    continue
                if ctl == "taunt" and taunt_frozen_acted is not None and aid in taunt_frozen_acted:
                    continue
            elif _is_stat_only(c):
                if current_actor_id is None or aid == current_actor_id:
                    continue
                if not _is_defensive_debuff(c):
                    same_side = aid in team and current_actor_id in team
                    if not (
                        same_side
                        and c.get("stat") in ("ac", "protection")
                        and int(c.get("delta", 0) or 0) > 0
                    ):
                        continue
            else:
                continue
            if not c.get(_SKIP_KEY):
                c[_SKIP_KEY] = True
                marked += 1
    return marked


def _is_stat_only(condition: dict) -> bool:
    """Buff/debuff puro ({stat, delta} sem DoT nem controle)."""
    return (
        bool(condition.get("stat"))
        and not int(condition.get("dot", 0) or 0)
        and not condition.get("control")
    )


def _expire_stat_conditions(actor: dict, present_at_start: list, out: dict) -> None:
    """SPEC-232 R1: buff/debuff tipado decresce ao FIM do turno do portador, e só
    se já estava ativo quando o turno começou. Assim `duracao: 1` aplicada no
    próprio turno vale para o próximo ataque/defesa, e aplicada antes do turno
    vale exatamente para este turno."""
    survivors: list[dict] = []
    for c in actor.get("active_conditions", []) or []:
        if c.get("persistente"):  # SPEC-330 Vigília: só some quando consumida
            survivors.append(c)
            continue
        if _is_stat_only(c) and any(c is p for p in present_at_start):
            if c.pop(_SKIP_KEY, False):  # SPEC-339 R8b: aplicada por outro ator, vale mais 1 turno
                survivors.append(c)
                continue
            c["duration"] = int(c.get("duration", 0) or 0) - 1
            if c["duration"] <= 0:
                out["logs"].append(f"{_name(actor)}: {c.get('name', 'condição')} terminou.")
                continue
        survivors.append(c)
    actor["active_conditions"] = survivors


def _tick_conditions_v4(actor: dict, out: dict, rng=None) -> bool:
    """Versão v4 de `tick_conditions`: aplica DoT em Vitalidade (não em hp), decrementa
    duração e remove condições expiradas. Substitui `cm.tick_conditions` (que ticava
    hp do motor antigo) no loop novo. Buff/debuff puro expira no fim do turno
    (`_expire_stat_conditions`), não aqui."""
    survivors: list[dict] = []
    damage_applied = False
    for c in actor.get("active_conditions", []) or []:
        if _is_stat_only(c):
            survivors.append(c)
            continue
        dot = int(c.get("dot", 0) or 0)
        if c.pop(_SKIP_KEY, False) and dot <= 0:
            # SPEC-339 R1: controle aplicado por outro ator pula o 1º tick do portador.
            survivors.append(c)
            continue
        if dot > 0:
            damage_applied = True
            dealt = _apply_dot_v4(
                actor, dot, str(c.get("damage_type") or c.get("source") or "cortante"), out, rng=rng
            )
            _fx_damage(actor, dealt, out)  # SPEC-330 R3: DoT também é dano recebido
            out.setdefault("ticks", []).append(  # SPEC-346 R7: o tick tem registro próprio
                {
                    "actor_id": str(
                        actor.get("id") or ("player" if actor.get("is_player") else _name(actor))
                    ),
                    "condition": str(c.get("name") or "condição"),
                    "damage_type": str(c.get("damage_type") or c.get("source") or "cortante"),
                    "dano_final": int(dealt or 0),
                    "vitalidade_depois": int(actor.get("vitalidade", 0) or 0),
                }
            )
            out["logs"].append(
                f"{_name(actor)} sofre {dot} de {c.get('name', 'condição')} "
                f"(Vit {actor.get('vitalidade', 0)})."
            )
            if c.get("decai"):  # SPEC-330 Sangria: decai 1 por rodada
                c["dot"] = max(0, dot - int(c.get("decai") or 0))
        c["duration"] = int(c.get("duration", 0)) - 1
        if c["duration"] > 0:
            survivors.append(c)
        else:
            out["logs"].append(f"{_name(actor)}: {c.get('name', 'condição')} terminou.")
    actor["active_conditions"] = survivors
    return damage_applied


# ==========================================================================
# IA de inimigo (perfil tático → TurnDeclaration), 100% sem LLM (08)
# ==========================================================================
def _opposing_ids(actor_id: str, sides: dict[str, list[str]]) -> list[str]:
    hero = set(sides.get("hero", [])) | set(sides.get("ally", []))
    enemy = set(sides.get("enemy", []))
    return list(enemy) if actor_id in hero else list(hero)


def _nearest_target(
    actor_id: str, candidates: list[str], actors_by_id: dict[str, dict]
) -> str | None:
    alive = [c for c in candidates if _alive(actors_by_id.get(c))]
    if not alive:
        return None
    # sem grade: "mais próximo/ameaçador" = maior Agilidade (proxy determinístico estável)
    alive.sort(key=lambda c: (-_agility(actors_by_id[c]), str(c)))
    return alive[0]


_TAUNT_RESISTED: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "taunt_resisted", default=None
)


def _taunt_resisted_ids() -> list:
    """Lista efêmera (por contexto) de quem resistiu à Provocação; nunca vai para ator/save."""
    lst = _TAUNT_RESISTED.get()
    if lst is None:
        lst = []
        _TAUNT_RESISTED.set(lst)
    del lst[:-32]
    return lst


def _actor_key(actor: dict) -> str:
    return str(actor.get("id") or ("player" if actor.get("is_player") else actor.get("name")))


def _taunt_target(
    actor: dict, candidates: list[str], actors_by_id: dict[str, dict], rng
) -> str | None:
    """Resolve Provocação fechada: a condição vive no provocado e aponta a fonte.

    A chance-base de 50% escala pela Entropia do Devoto e respeita teto de 90%.
    Sem fonte válida/viva, a seleção tática normal permanece intacta.
    """
    candidate_set = set(candidates)
    for condition in actor.get("active_conditions") or []:
        if condition.get("control") != "taunt":
            continue
        source_id = str(condition.get("source_actor_id") or "")
        source = actors_by_id.get(source_id)
        if source_id not in candidate_set or not _alive(source):
            continue
        chance = min(0.9, 0.5 * cm.taunt_aggro_multiplier(source))
        if rng.random() < chance:
            source.setdefault("_last_class_mechanics", []).append(
                {
                    "kind": "special:taunt",
                    "chance": round(chance, 4),
                    "target_id": source_id,
                }
            )
            return source_id
        _taunt_resisted_ids().append(_actor_key(actor))  # SPEC-353 R39a: efêmero, fora do save
    return None


def _same_side_ids(actor_id: str, sides: dict[str, list[str]]) -> list[str]:
    heroes = list(sides.get("hero", [])) + list(sides.get("ally", []))
    if actor_id in heroes:
        return heroes
    enemies = list(sides.get("enemy", []))
    return enemies if actor_id in enemies else []


def _available_for_aid(actor: dict | None) -> bool:
    """Pode receber ajuda mesmo inconsciente/terminal, mas não após sair da cena."""
    if not actor:
        return False
    if actor.get("dead") or actor.get("fled") or actor.get("surrendered"):
        return False
    return str(actor.get("status", "ativo")) not in ("morto", "fugiu", "rendido")


def _vitality_ratio(actor: dict) -> float:
    maximum = max(1, int(actor.get("max_vitalidade", 1) or 1))
    current = max(0, int(actor.get("vitalidade", maximum) or 0))
    return min(1.0, current / maximum)


def _has_wounds(actor: dict, *categories: str) -> bool:
    wounds = actor.get("ferimentos") or {}
    selected = categories or ("leve", "grave", "critico")
    return any(wounds.get(category) for category in selected)


def _aid_rank(actor_id: str, actors_by_id: dict[str, dict]) -> tuple:
    actor = actors_by_id[actor_id]
    wounds = actor.get("ferimentos") or {}
    return (
        0 if actor.get("estado_terminal") else 1,
        0 if actor.get("last_stand_pending") else 1,
        -len(wounds.get("critico", []) or []),
        -len(wounds.get("grave", []) or []),
        _vitality_ratio(actor),
        str(actor_id),
    )


def _aid_target(
    actor_id: str, sides: dict[str, list[str]], actors_by_id: dict[str, dict], predicate
) -> str | None:
    candidates = [
        ally_id
        for ally_id in _same_side_ids(actor_id, sides)
        if ally_id != actor_id
        and _available_for_aid(actors_by_id.get(ally_id))
        and predicate(ally_id, actors_by_id[ally_id])
    ]
    candidates.sort(key=lambda ally_id: _aid_rank(ally_id, actors_by_id))
    return candidates[0] if candidates else None


def derive_tactical_scene_state(
    scene: dict, actor_id: str, actors_by_id: dict[str, dict], sides: dict[str, list[str]]
) -> dict:
    """Deriva os únicos gatilhos mecânicos aceitos pelos perfis fechados.

    IDs de alvo vêm de ``sides``/``actors_by_id``; flags livres de ``scene_state``
    nunca conseguem introduzir participantes ou forçar uma ação.
    """
    actor = actors_by_id.get(actor_id) or {}
    opposing_ids = _opposing_ids(actor_id, sides)
    target_id = _nearest_target(actor_id, opposing_ids, actors_by_id)
    vulnerable_ids = [
        target
        for target in opposing_ids
        if _alive(actors_by_id.get(target))
        and (
            _vitality_ratio(actors_by_id[target]) <= 0.5
            or _has_wounds(actors_by_id[target])
            or (
                (((scene.get("positions") or {}).get(target) or {}).get("postura") or {}).get(
                    "state"
                )
                == "exposto"
            )
        )
    ]
    vulnerable_ids.sort(
        key=lambda target: (
            _vitality_ratio(actors_by_id[target]),
            str(target),
        )
    )
    vulnerable_id = vulnerable_ids[0] if vulnerable_ids else None
    terminal_id = _aid_target(
        actor_id,
        sides,
        actors_by_id,
        lambda _ally_id, ally: bool(ally.get("estado_terminal")),
    )
    wounded_id = _aid_target(
        actor_id,
        sides,
        actors_by_id,
        lambda _ally_id, ally: _vitality_ratio(ally) < 1.0 or _has_wounds(ally),
    )
    danger_id = _aid_target(
        actor_id,
        sides,
        actors_by_id,
        lambda _ally_id, ally: (
            bool(ally.get("estado_terminal") or ally.get("last_stand_pending"))
            or _vitality_ratio(ally) <= 0.5
            or _has_wounds(ally, "grave", "critico")
        ),
    )
    available_id = _aid_target(
        actor_id,
        sides,
        actors_by_id,
        lambda ally_id, ally: (
            _can_act(ally) and not cs.has_tactical_modifier(scene, "attack_advantage", ally_id)
        ),
    )
    has_flank = bool(target_id and cs.is_hidden_from(scene, actor_id, target_id))
    same_side = _same_side_ids(actor_id, sides)
    peers = [ally_id for ally_id in same_side if ally_id != actor_id]
    alive_peers = [ally_id for ally_id in peers if _alive(actors_by_id.get(ally_id))]
    engaged = set(((scene.get("positions") or {}).get(actor_id) or {}).get("engaged_with", []))
    surrounded = len(engaged & set(opposing_ids)) >= 2
    alone = not alive_peers
    pack_broken = bool(peers) and len(alive_peers) * 2 <= len(peers)
    badly_wounded = _vitality_ratio(actor) <= 0.35 or _has_wounds(actor, "grave", "critico")
    return {
        "aliado_terminal": terminal_id is not None,
        "aliado_ferido": wounded_id is not None,
        "aliado_em_perigo": danger_id is not None,
        "aliado_disponivel": available_id is not None,
        "vitalidade_baixa": badly_wounded,
        "sem_flanco": target_id is not None and not has_flank,
        "controle_disponivel": (
            target_id is not None and cs.tactical_cooldown(scene, actor_id, "control") == 0
        ),
        # Vocabulário canônico dos 84 perfis curados do bestiário.
        "sozinho": alone,
        "muito_ferido": badly_wounded,
        "alvo_vulneravel": vulnerable_id is not None,
        "cercado": surrounded,
        "matilha_quebrada": pack_broken,
        "descoberto": target_id is not None and not has_flank,
        "plano_falhou": badly_wounded and (surrounded or alone),
        "_enemy_target": target_id,
        "_vulnerable_enemy_target": vulnerable_id,
        "_ally_terminal_target": terminal_id,
        "_ally_wounded_target": wounded_id,
        "_ally_danger_target": danger_id,
        "_ally_available_target": available_id,
    }


def enemy_declaration(
    scene: dict,
    actor_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    *,
    scene_state: dict | None = None,
    rng=None,
) -> "ct.TurnDeclaration":
    """R1/R2 (08): decide o turno de um inimigo pela PRECEDÊNCIA do perfil tático,
    sem LLM. A mecânica usa ``action_key`` fechado; ``action_hint`` é somente
    apresentação. Default determinístico: ataque no alvo mais ameaçador."""
    actor = actors_by_id[actor_id]
    canonical = derive_tactical_scene_state(scene, actor_id, actors_by_id, sides)
    decision_state = dict(scene_state or {})
    decision_state.update(canonical)
    decision = tp.pick_action(
        actor.get("tactical_profile") or tp._default_profile(),
        decision_state,
    )
    explicit_action = decision.get("action_key")
    action_key = explicit_action or tp.legacy_action_key(decision.get("action_hint"))
    target = (
        canonical["_vulnerable_enemy_target"]
        if decision.get("trigger") == "alvo_vulneravel"
        and canonical["_vulnerable_enemy_target"] is not None
        else canonical["_enemy_target"]
    )
    taunted_target = _taunt_target(
        actor, _opposing_ids(actor_id, sides), actors_by_id, rng or random.Random()
    )
    if taunted_target is not None:
        target = taunted_target

    forced_attack = bool(actor.pop("_forced_attack", None))
    if forced_attack and action_key not in {"flee", "surrender"}:
        action_key = "attack"  # SPEC-275 R5: quebra de impasse — ataca.
    # SPEC-332: padrao de intencao/assinatura. Gatilho especifico do perfil (vida baixa,
    # alvo vulneravel...) tem precedencia: o plano so vale quando decide o `sempre`.
    deck_plan = None
    if (
        _edk_mod.active()
        and not forced_attack
        and action_key not in {"flee", "surrender"}
        and decision.get("trigger") in (None, "sempre")
    ):
        deck_plan = _edk_mod.plan(
            actor, int(decision_state.get("_rodada_decisao") or cs.tactical_round(scene))
        )
        if deck_plan is not None and action_key in {
            "support",
            "flank",
            "protect",
            "stabilize",
            "control",
        }:
            # Perfil de apoio/flanco (lider de matilha, covarde): o padrao nao troca o carater
            # dele por ataque; so a assinatura (a jogada memoravel) pode sobrepor.
            deck_plan["slot"] = "mover"
    if action_key == "control" and not canonical["controle_disponivel"]:
        action_key = "attack"
    if action_key == "flank" and not canonical["sem_flanco"]:
        action_key = "attack"

    if action_key == "surrender":
        actor["surrendered"] = True
        return ct.TurnDeclaration(actor_id=actor_id, acao=ct.TurnStep(kind="pass"))
    if action_key == "flee":
        if explicit_action == "flee":
            return ct.TurnDeclaration(
                actor_id=actor_id,
                acao=ct.TurnStep(kind="tactic", maneuver="flee"),
            )
        # Compatibilidade com perfil persistido pré-action_key.
        return ct.TurnDeclaration(
            actor_id=actor_id, acao=ct.TurnStep(kind="move", direction="afastar")
        )

    if target is None:
        return ct.TurnDeclaration(actor_id=actor_id, acao=ct.TurnStep(kind="pass"))

    if (
        deck_plan is not None
        and taunted_target is None
        and not cm.has_control(actor, "silence")
        and actor_id in set(sides.get("enemy", []))
    ):
        planned = _enemy_deck_declaration(
            scene, actor, actor_id, actors_by_id, sides, canonical, deck_plan, target
        )
        if planned is not None:
            return planned

    tactical_target = {
        "protect": canonical["_ally_danger_target"],
        "stabilize": canonical["_ally_terminal_target"],
        "flank": target,
        "control": target,
        "support": (
            canonical["_ally_wounded_target"]
            if actor.get("tactical_archetype") == "suporte"
            else canonical["_ally_available_target"]
        ),
    }.get(action_key)
    tactical_keys = {"protect", "stabilize", "flank", "control", "support"}
    # Manobra tática sem alvo válido degrada para ataque (mesma regra abaixo).
    effective_action = (
        "attack" if action_key in tactical_keys and tactical_target is None else action_key
    )
    if (
        not forced_attack
        and effective_action != "stabilize"
        # Revisão SPEC-283: silenciado não usa Carta (cairia num "ataque" a si
        # mesmo); provocado ataca a fonte da Provocação; só o lado inimigo.
        and not cm.has_control(actor, "silence")
        and taunted_target is None
        and actor_id in set(sides.get("enemy", []))
    ):
        # SPEC-283: Carta de suporte do bestiário no próprio lado, quando a cena
        # justifica. Quebra de impasse (SPEC-275 R5) e estabilização vêm antes.
        choice = _enemy_support_card(
            scene, actor, actor_id, actors_by_id, sides, canonical, effective_action
        )
        if choice is not None:
            support_card, support_target, direction = choice
            return ct.TurnDeclaration(
                actor_id=actor_id,
                acao=ct.TurnStep(
                    kind="card",
                    card_id=support_card,
                    target_id=support_target,
                    direction=direction,
                ),
            )
    if action_key in tactical_keys:
        if tactical_target is not None:
            return ct.TurnDeclaration(
                actor_id=actor_id,
                acao=ct.TurnStep(
                    kind="tactic",
                    maneuver=action_key,
                    target_id=tactical_target,
                ),
            )
        action_key = "attack"

    # Carta de inimigo (conflito-15: `cartas`) quando houver Entropia; senão ataque básico.
    card_id = _enemy_offensive_card(
        actor, scene=scene, actor_id=actor_id, allow_hide=not forced_attack
    )
    if card_id:
        # SPEC-275 R2: Carta de suporte mira o próprio lado, nunca o jogador.
        kind = str(((_get_card(card_id) or {}).get("efeito") or {}).get("kind") or "")
        if kind in ct._SUPPORT_EFFECTS:
            target = actor_id
    step = ct.TurnStep(kind="card" if card_id else "attack", card_id=card_id, target_id=target)
    return ct.TurnDeclaration(actor_id=actor_id, acao=step)


# SPEC-283: famílias de Carta de suporte que a IA inimiga sabe usar no próprio lado.
_ENEMY_DEFENSIVE_SUPPORT = frozenset({"protecao", "buff_defesa"})
_ENEMY_OFFENSIVE_SUPPORT = frozenset({"buff_dano", "buff_acerto", "vantagem"})
_ENEMY_MOVE_SUPPORT = frozenset({"reposicionar"})
_ENEMY_HEAL_SUPPORT = frozenset({"cura"})  # SPEC-332: ferido (si ou aliado) -> cura


def _has_condition_from(actor: dict | None, card_id: str) -> bool:
    return any(
        str(c.get("source") or "") == card_id for c in (actor or {}).get("active_conditions") or []
    )


def _enemy_support_card(
    scene: dict,
    actor: dict,
    actor_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    canonical: dict,
    action_key: str,
) -> tuple[str, str, str | None] | None:
    """SPEC-283 R1/R2/R4/R5: escolhe, sem RNG, uma Carta de suporte do bestiário
    para o PRÓPRIO lado. Devolve ``(card_id, target_id, direction)`` ou ``None``.

    Ordem: defensiva (aliado em perigo → si mesmo ferido) → ofensiva (aliado na
    ação ``support`` → si mesmo antes de ``attack``) → movimento (fechar distância
    antes de ``attack``). O alvo é sempre o ator ou um aliado do mesmo lado — nunca
    o jogador nem um aliado dele. Custo/frequência/Entropia via
    ``cards.can_use_enemy_card``; Carta cuja condição ainda está ativa no alvo não
    é repetida."""
    from services import cards

    own_side = set(_same_side_ids(actor_id, sides)) | {actor_id}
    hostile = set(_opposing_ids(actor_id, sides))
    usable: list[tuple[str, str]] = []
    for card_id in cards.enemy_card_ids(actor):
        kind = str(((cards.get_card(card_id) or {}).get("efeito") or {}).get("kind") or "")
        if (
            kind
            not in _ENEMY_DEFENSIVE_SUPPORT
            | _ENEMY_OFFENSIVE_SUPPORT
            | _ENEMY_MOVE_SUPPORT
            | _ENEMY_HEAL_SUPPORT
        ):
            continue
        if cards.can_use_enemy_card(actor, card_id, expected_type="ativa"):
            usable.append((card_id, kind))
    if not usable:
        return None

    def valid(target_id: str | None, card_id: str) -> bool:
        return bool(
            target_id
            and target_id in own_side
            and target_id not in hostile
            and _available_for_aid(actors_by_id.get(target_id))
            and not _has_condition_from(actors_by_id.get(target_id), card_id)
        )

    self_hurt = bool(canonical.get("vitalidade_baixa")) or _vitality_ratio(actor) <= 0.5
    for card_id, kind in usable:
        if kind not in _ENEMY_DEFENSIVE_SUPPORT:
            continue
        danger = canonical.get("_ally_danger_target")
        if valid(danger, card_id):
            return card_id, danger, None
        if self_hurt and valid(actor_id, card_id):
            return card_id, actor_id, None
    for card_id, kind in usable:
        if kind not in _ENEMY_HEAL_SUPPORT:
            continue
        wounded = canonical.get("_ally_wounded_target")
        if valid(wounded, card_id):
            return card_id, wounded, None
        if _vitality_ratio(actor) <= 0.7 and valid(actor_id, card_id):
            return card_id, actor_id, None
    for card_id, kind in usable:
        if kind not in _ENEMY_OFFENSIVE_SUPPORT:
            continue
        ally = canonical.get("_ally_available_target")
        if action_key == "support" and valid(ally, card_id):
            return card_id, ally, None
        if action_key == "attack" and canonical.get("_enemy_target") and valid(actor_id, card_id):
            return card_id, actor_id, None
    position = ((scene.get("positions") or {}).get(actor_id)) or {}
    far = position and position.get("distance_state", "proximo") != "proximo"
    for card_id, kind in usable:
        if kind in _ENEMY_MOVE_SUPPORT and action_key == "attack" and far:
            if valid(actor_id, card_id):
                return card_id, actor_id, "aproximar"
    return None


def _get_card(card_id: str) -> dict | None:
    from services import cards

    return cards.get_card(card_id)


def _enemy_deck_declaration(
    scene: dict,
    actor: dict,
    actor_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    canonical: dict,
    plan: dict,
    target: str,
) -> "ct.TurnDeclaration | None":
    """SPEC-332 R3/R4: escolhe a Carta DENTRO do baralho montado conforme o padrao da
    rodada. Assinatura primeiro (telegrafada pelo Pressagio na rodada anterior); depois o
    tipo do padrao. ``None`` = nao ha o que fazer pelo padrao: segue o fluxo do perfil."""
    from services import cards

    rnd = int(plan.get("rnd") or 1)
    sig = plan.get("assinatura")
    if sig and cards.can_use_enemy_card(actor, sig, expected_type="ativa"):
        kind = str(((_get_card(sig) or {}).get("efeito") or {}).get("kind") or "")
        who = actor_id if kind in ct._SUPPORT_EFFECTS else target
        return ct.TurnDeclaration(
            actor_id=actor_id, acao=ct.TurnStep(kind="card", card_id=sig, target_id=who)
        )
    slot = str(plan.get("slot") or "ataque")
    if slot in ("reforco_proprio", "defesa"):
        choice = _enemy_support_card(
            scene, actor, actor_id, actors_by_id, sides, canonical, "attack"
        )
        if choice is None:
            return None
        card_id, who, direction = choice
        return ct.TurnDeclaration(
            actor_id=actor_id,
            acao=ct.TurnStep(kind="card", card_id=card_id, target_id=who, direction=direction),
        )
    if slot == "mover":
        return None
    from services import enemy_decks as edk

    skip = {str(a["carta"]) for a in [edk.assinatura_of(actor)] if a}
    kinds = edk.card_pool_kinds(slot)
    card_id = _enemy_offensive_card(
        actor, scene=scene, actor_id=actor_id, kinds=kinds, rotate=rnd, skip=skip
    )
    if card_id is None and slot == "enfraquecer":
        return None  # sem controle no baralho: o perfil decide
    step = ct.TurnStep(kind="card" if card_id else "attack", card_id=card_id, target_id=target)
    return ct.TurnDeclaration(actor_id=actor_id, acao=step)


def _enemy_offensive_card(
    actor: dict,
    *,
    scene: dict | None = None,
    actor_id: str = "",
    allow_hide: bool = True,
    kinds: "frozenset[str] | None" = None,
    rotate: int = 0,
    skip: "set[str] | None" = None,
) -> str | None:
    """Primeira Carta de inimigo ofensiva utilizável (assinatura oculta da 15) —
    só id embutido na ficha; inimigo NÃO usa o Acervo do jogador.
    SPEC-332: ``kinds`` restringe aos efeitos do padrao, ``rotate`` alterna entre os
    candidatos por rodada e ``skip`` reserva a assinatura. Sem eles, comportamento antigo."""
    from services import cards

    found: list[str] = []
    for card_id in cards.enemy_card_ids(actor):
        if skip and card_id in skip:
            continue
        card = cards.get_card(card_id) or {}
        effect_kind = str((card.get("efeito") or {}).get("kind") or "")
        position = ((scene or {}).get("positions") or {}).get(actor_id) or {}
        # Esconder-se de novo enquanto já oculto não cria mudança mecânica e
        # pode bloquear o conflito para sempre (Mimetismo Morto da matriz A).
        if effect_kind == "esconder" and (
            not allow_hide or position.get("ocultacao") == "escondido"
        ):
            # SPEC-275 R5 (revisão Astra): na quebra de impasse o inimigo ATACA —
            # esconder-se de novo anularia a quebra.
            continue
        # SPEC-275 R1: "ofensiva" de verdade — Carta de suporte recusada contra
        # o jogador deixava o inimigo inerte para sempre.
        # `esconder` segue elegível (Mimetismo Morto) — mira o próprio ator (R2).
        if effect_kind not in ct._ATTACK_EFFECTS and effect_kind != "esconder":
            continue
        if kinds is not None and effect_kind not in kinds:
            continue
        if cards.can_use_enemy_card(actor, card_id, expected_type="ativa"):
            if not rotate:
                return card_id
            found.append(card_id)
    if found:
        from services import enemy_decks as _edk

        return found[_edk.rotate_index(actor, rotate, len(found))]
    return None


# ==========================================================================
# Ataque de Oportunidade + janela de Reação (06)
# ==========================================================================
def _declaration_leaves_engagement(decl: "ct.TurnDeclaration") -> bool:
    for slot in (decl.pre_acao, decl.acao, decl.pos_acao):
        if slot is None:
            continue
        if slot.kind == "maneuver" and str(slot.maneuver or "").lower() == "desengajar":
            # SPEC-232 R8: Desengajar ANTES de afastar encerra o Engajamento com
            # segurança (conflito-06 R7) — não há AoO no resto da declaração.
            return False
        if slot.kind == "move" and str(slot.direction or "").lower() in ("afastar", "away", "+"):
            return True
        if slot.kind == "tactic" and str(slot.maneuver or "").lower() == "flee":
            return True
        if (
            slot.kind == "maneuver"
            and str(slot.maneuver or "").lower() == "mover"
            and str(slot.direction or "").lower() in ("afastar", "away")
        ):
            return True
    return False


def _resolve_opportunity_attacks(
    scene: dict,
    leaving_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    out: dict,
    rng,
) -> None:
    """R5 (06): abandonar Engajamento SEM Desengajar provoca AoO de cada inimigo
    Engajado, consciente e capaz — fora do limite de reação comum."""
    allies = (
        [a for a in sides.get("hero", []) + sides.get("ally", [])]
        if leaving_id in set(sides.get("hero", []) + sides.get("ally", []))
        else list(sides.get("enemy", []))
    )
    aoos = rx.trigger_opportunity_attack(scene, leaving_id, allies=allies, stats_by_id=actors_by_id)
    for aoo in aoos:
        atk_id, tgt_id = aoo["attacker"], aoo["target"]
        attacker, target = actors_by_id.get(atk_id), actors_by_id.get(tgt_id)
        if not _alive(attacker) or not target:
            continue
        _basic_attack(
            scene, attacker, atk_id, target, tgt_id, out, rng, label="Ataque de Oportunidade"
        )


def _open_reaction_window(
    scene: dict,
    attacker_id: str,
    target_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    out: dict,
    state: dict | None = None,
    *,
    rng=None,
    step=None,
) -> None:
    """R1/R3 (06): abre a janela sobre o ataque declarado e deixa reatores do lado
    oposto oferecerem UMA reação COMUM (Carta de reação) — reação defensiva de
    Guarda entra na cena antes de o ataque resolver. Player só reage pela UI
    (conflito-16); aqui os reatores são inimigos com Carta de reação embutida."""
    declared = _declared_attack(scene, attacker_id, target_id, actors_by_id, sides, step)
    chain = rx.open_reaction_window(declared)
    reactors = _opposing_ids(attacker_id, sides)
    ordered = rx.reaction_order(
        reactors, declared, stats_by_id=actors_by_id, target_allies=reactors
    )
    for rid in ordered:
        reactor = actors_by_id.get(rid)
        if not _alive(reactor):
            continue
        player_id = _player_id(sides)
        selected_player_card = state.get("_player_reaction_card_id") if state is not None else None
        from services import cards

        if rid == player_id and selected_player_card:
            card = cards.get_card(str(selected_player_card))
            if (
                not card
                or card.get("tipo") != "reacao"
                or str(selected_player_card) not in set(reactor.get("prepared_cards") or [])
            ):
                continue
            from services import card_deck_round as _deck

            if _deck.reaction_gate(state, reactor, card) is False:
                continue  # SPEC-328 R12: fora da mao ou sem Folego sobrando
        else:
            card = _enemy_reaction_card(reactor)
        if not card:
            continue
        if not rx.gatilho_matches(card, declared, rid):
            continue
        if str((card.get("efeito") or {}).get("kind") or "") in (
            "contra_ataque",
            "dano",
        ) and not _alive(actors_by_id.get(attacker_id)):
            # Revisão Sol (SPEC-232 R3): revide sem atacante vivo na cena não
            # cobra Entropia nem uso — não há o que resolver.
            continue
        snapshot = (
            reactor.get("entropy"),
            copy.deepcopy(reactor.get("card_usage")),
            copy.deepcopy(reactor.get("enemy_card_usage")),
        )
        if rid == player_id:
            spent = cards.use_card(state or {"player": reactor}, card["id"])
        else:
            spent = cards.use_enemy_card(reactor, card["id"])
        if not spent.get("ok"):
            continue
        if not rx.offer_reaction(chain, rid, card["id"], card=card, reactor=None):
            # SPEC-232 R3: reação não ofertada → reembolsa Entropia e uso.
            reactor["entropy"] = snapshot[0]
            for key, value in (("card_usage", snapshot[1]), ("enemy_card_usage", snapshot[2])):
                if value is None:
                    reactor.pop(key, None)
                else:
                    reactor[key] = value
            continue
        if rid == player_id:
            from services import card_deck_round as _deck

            _deck.reaction_commit(state, reactor, card)  # SPEC-328 R12 (no-op sem baralho)
        # Proteção limitada ao próximo ataque; não deixa Guarda persistente.
        cs.grant_tactical_modifier(scene, "protected", rid, rid)
        _resolve_reaction_effect(scene, reactor, rid, card, attacker_id, actors_by_id, out, rng=rng)
    out.setdefault("reactions", []).extend(rx.resolve_chain(chain))


def _resolve_reaction_effect(
    scene: dict,
    reactor: dict,
    reactor_id: str,
    card: dict,
    attacker_id: str,
    actors_by_id: dict[str, dict],
    out: dict,
    *,
    rng=None,
) -> None:
    """SPEC-232 R3: o `efeito` da Carta de Reação roda pelo mesmo pipeline das
    ações — contra-ataque/dano rolam ataque do reagente contra o atacante; cura,
    buff e Proteção valem para o reagente; condição/empurrão miram o atacante."""
    effect = card.get("efeito") or {}
    kind = str(effect.get("kind") or "")
    name = card.get("name", card.get("id", "Reação"))
    attacker = actors_by_id.get(attacker_id)
    amount = ct._effect_amount(effect)
    duration = max(1, int(effect.get("duracao", effect.get("duration", 1)) or 1))
    if kind in ("contra_ataque", "dano"):
        if _alive(attacker):
            _basic_attack(
                scene,
                reactor,
                reactor_id,
                attacker,
                attacker_id,
                out,
                rng,
                label=name,
                damage_override=amount,
                damage_type=str(effect.get("dano_tipo") or "cortante"),
            )
    elif kind == "cura":
        before = int(reactor.get("vitalidade", 0) or 0)
        heal = max(0, amount + int(cm.combat_modifiers(reactor).get("heal", 0) or 0))
        reactor["vitalidade"] = min(
            int(reactor.get("max_vitalidade", before) or before), before + heal
        )
        gamedata.sync_legacy_hp_aliases(reactor)
        out.setdefault("heals", []).append(  # SPEC-346 R10
            {"actor_id": reactor_id, "card": name, "amount": reactor["vitalidade"] - before}
        )
        out["logs"].append(
            f"{name}: {_name(reactor)} recupera {reactor['vitalidade'] - before} Vitalidade."
        )
    elif kind == "aplicar_condicao":
        if attacker is not None:
            cond = cm.parse_condition(
                str(effect.get("condicao") or name), source=card.get("id", name)
            )
            cond["duration"] = duration
            out["logs"].append(cm.apply_condition(attacker, cond))
    elif kind == "empurrao":
        result = cs.move_distance(scene, attacker_id, "afastar")
        cs.disengage(scene, reactor_id, attacker_id, spend=False)
        out["logs"].append(result.get("log") or result.get("error", ""))
    elif kind in ("buff_defesa", "buff_esquiva", "protecao", "buff_iniciativa"):
        stat = {
            "buff_defesa": "ac",
            "buff_esquiva": "ac",
            "protecao": "protection",
            "buff_iniciativa": "initiative",
        }[kind]
        out["logs"].append(
            cm.apply_condition(
                reactor,
                {
                    "name": name,
                    "dot": 0,
                    "duration": duration,
                    "source": card.get("id", name),
                    "stat": stat,
                    "delta": amount,
                },
            )
        )
    else:
        out["logs"].append(f"{name}: reação sem efeito resolvível ({kind!r}).")


def _declared_attack(
    scene: dict,
    attacker_id: str,
    target_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    step=None,
) -> dict:
    """Ação declarada para a janela de Reação, com os campos determinísticos que
    os gatilhos lêem (SPEC-232 R4): lados, corpo a corpo/distância, tipo de
    dano, flanqueio, aliados caídos/controlados e auto-dano recente."""
    card = None
    if step is not None and getattr(step, "card_id", None):
        from services import cards

        card = cards.get_card(step.card_id)
    effect = (card or {}).get("efeito") or {}
    melee = ct._is_melee(card, step) if step is not None else True
    dtype = str(
        effect.get("damage_type")
        or effect.get("tipo_dano")
        or effect.get("dano_tipo")
        or "cortante"
    ).lower()
    hero = set(sides.get("hero", [])) | set(sides.get("ally", []))
    enemy = set(sides.get("enemy", []))
    allies_of = {aid: sorted((hero if aid in hero else enemy) - {aid}) for aid in hero | enemy}
    positions = scene.get("positions") or {}
    flanked = [
        aid
        for aid, pos in positions.items()
        if len([o for o in pos.get("engaged_with", []) if (o in hero) != (aid in hero)]) >= 2
    ]
    return {
        "kind": "attack",
        "actor": attacker_id,
        "targets": [target_id],
        "allies_of": allies_of,
        "melee": bool(melee),
        "already_engaged": cs.is_engaged(scene, attacker_id, target_id),
        "damage_type": dtype,
        "supernatural": dtype not in set(gamedata.DANO_FISICO),
        "flanked": flanked,
        "downed": [
            aid
            for aid, a in actors_by_id.items()
            if a.get("estado_terminal") or int(a.get("vitalidade", 1) or 0) <= 0
        ],
        "controlled": [aid for aid, a in actors_by_id.items() if cm.has_control(a, "stun")],
        "self_harmed": [aid for aid, a in actors_by_id.items() if a.get("_self_harmed_round")],
    }


def _enemy_reaction_card(actor: dict) -> dict | None:
    from services import cards

    for card_id in cards.enemy_card_ids(actor):
        if cards.can_use_enemy_card(actor, card_id, expected_type="reacao"):
            return cards.get_card(card_id)
    return None


def _basic_attack(
    scene: dict,
    attacker: dict,
    attacker_id: str,
    target: dict,
    target_id: str,
    out: dict,
    rng,
    *,
    label: str = "Ataque",
    advantage: int = 0,
    damage_override: int | None = None,
    damage_type: str = "cortante",
) -> None:
    """Ataque básico determinístico (2d10+Virtude vs Esquiva → dano→Ferimento).
    Usado por AoO/reações que não passam pela declaração de turno."""
    advantage += cs.consume_tactical_attack_modifier(scene, attacker_id, target_id)
    atk = resolve_attack(
        attacker,
        target,
        virtude_key="forca",
        virtude_value_override=(
            virtude_value(attacker, "forca") + int(attacker.get("_env_attack_mod", 0) or 0)
        ),
        advantage=advantage,
        rng=rng,
    )
    atk["actor_id"] = attacker_id
    atk["target_id"] = target_id
    if (
        "resolved_turns" in out
    ):  # SPEC-347 R5.2: só dentro de uma rodada real (golden da 330 fica intacto)
        atk["fora_de_turno"] = label  # anotação de view (rótulo no log mecânico)
    out.setdefault("attacks", []).append(atk)
    out["logs"].append(
        f"{label}: {_name(attacker)} → {_name(target)}: "
        f"{atk['resultado']} ({atk['total']} vs {atk['esquiva_alvo']})."
    )
    if atk["acerto"]:
        if damage_override is not None:
            dmg = max(0, int(damage_override))
        elif attacker.get("dano_base_arma") is not None:
            dmg = max(0, int(attacker.get("dano_base_arma") or 0))
        else:
            formula = str(attacker.get("attack_formula") or "1d6")
            dmg, _ = cm.roll_dice_numeric(formula)
        if attacker_id == "player" or attacker.get("is_player"):
            dmg += cm.early_game_damage_bonus(int(attacker.get("level", 1) or 1))
        # SPEC-232 R1/R2: `damage` de condições/passivas estáticas do atacante.
        dmg += int(cm.combat_modifiers(attacker).get("damage", 0) or 0)
        dmg += fx.consume_marca_abismo(attacker, target, out)  # SPEC-330
        dres = resolve_damage_and_wounds(
            target,
            damage_base=max(0, dmg),
            damage_type=damage_type,
            crit_mult=atk["efeito_principal_multiplicador"],
            directed_region=None,
            dealt_pct=fx.damage_pct(attacker, "dealt"),
            rng=rng,
        )
        atk["regiao"] = dres["regiao"]
        atk["dano_final"] = int(dres.get("dano_final", 0) or 0)
        if (dres.get("wound") or {}).get("categoria"):  # SPEC-346 R4
            atk["ferimento"] = {
                "categoria": dres["wound"]["categoria"],
                "regiao": dres["wound"].get("regiao") or dres.get("regiao"),
            }
        if dres.get("resistance_hit") and combat_flags.mode("reveal_resist") != "off":
            atk["resistance_hit"] = dres["resistance_hit"]  # SPEC-325 R8
        out["logs"] += dres["log"]
        _post_hit(target, target_id, out, amount=atk["dano_final"])


# ==========================================================================
# Gatilhos de classe pós-golpe + Estado Terminal
# ==========================================================================
def _record_class_event(out: dict, kind: str, **details) -> None:
    out.setdefault("class_mechanics", []).append({"kind": kind, **details})


def _entropy_event(player: dict, event: dict, out: dict) -> None:
    before = (int(player.get("entropy", 0) or 0), int(player.get("abyss_charge", 0) or 0))
    cm.apply_entropy_trigger(player, event, out["logs"])
    after = (int(player.get("entropy", 0) or 0), int(player.get("abyss_charge", 0) or 0))
    if after != before:
        _record_class_event(
            out,
            f"entropy:{event['kind']}",
            entropy_delta=after[0] - before[0],
            charge_delta=after[1] - before[1],
        )
    if after[1] > before[1]:
        _fire_for(player, "ao_entrar_carga", out)


def _fx_damage(actor: dict, amount: int, out: dict) -> None:
    """SPEC-330: dano fora de golpe (DoT) → `ao_receber_dano`/`ao_aliado_sofrer`."""
    ctx = fx.current()
    if ctx is None:
        return
    actor_id = next((aid for aid, a in ctx.actors_by_id.items() if a is actor), None)
    if actor_id is not None:
        fx.on_damage(ctx, actor_id, None, amount, out)


def _fire_for(actor: dict, gatilho: str, out: dict, *, alvo_id: str | None = None) -> None:
    """SPEC-330: dispara `gatilho` para o ator (id achado no contexto da rodada)."""
    ctx = fx.current()
    if ctx is None:
        return
    actor_id = next((aid for aid, a in ctx.actors_by_id.items() if a is actor), None)
    if actor_id is not None:
        fx.fire(gatilho, sujeito_id=actor_id, alvo_id=alvo_id, out=out)


def _post_hit(target: dict, target_id: str, out: dict, *, amount: int = 0) -> None:
    """Gatilho de Entropia da classe do alvo (on_damage_taken) + checagem de Terminal."""
    if target.get("is_player"):
        _entropy_event(target, {"kind": "on_damage_taken", "amount": amount}, out)
        before = (int(target.get("entropy", 0) or 0), int(target.get("_blood_entropy", 0) or 0))
        cm.apply_blood_leak(target, out["logs"])
        after = (int(target.get("entropy", 0) or 0), int(target.get("_blood_entropy", 0) or 0))
        if after != before:
            _record_class_event(out, "special:blood_leak", entropy_delta=after[0] - before[0])
    _check_terminal(target, target_id, out, damage_applied=True)


def _wound_snapshot(actor: dict) -> list[tuple[str, str]]:
    fer = actor.get("ferimentos") or {}
    return [
        (cat, str(w.get("regiao")))
        for cat in ("leve", "grave", "critico")
        for w in (fer.get(cat) or [])
        if isinstance(w, dict)
    ]


def _new_wound_note(actor: dict, before: list[tuple[str, str]]) -> dict | None:
    """Ferimento que apareceu desde ``before`` (a pior categoria); ``None`` se nenhum."""
    now = _wound_snapshot(actor)
    fresh = [w for w in now if w not in before] or (
        [w for w in now if now.count(w) > before.count(w)]
    )
    if not fresh:
        return None
    cat, regiao = max(fresh, key=lambda w: ("leve", "grave", "critico").index(w[0]))
    return {"categoria": cat, "regiao": regiao}


def _apply_player_card_mechanics(player: dict, used: dict, player_id: str, out: dict, rng) -> None:
    """Liga marcadores autorais fechados da Carta aos helpers sobreviventes."""
    card = used.get("card") or {}
    mechanics = card.get("mecanica_classe") or {}
    self_harm = int(mechanics.get("auto_dano", 0) or 0)
    if self_harm:
        from services.conflict_damage import sacrifice_vitality

        before = int(player.get("vitalidade", 0) or 0)
        wounds_before = _wound_snapshot(player)
        sacrifice_vitality(player, self_harm)
        player["_self_harmed_round"] = True  # gatilho `apos_auto_dano` (SPEC-232)
        out["logs"].append(
            f"{_name(player)} sacrifica {self_harm} Vitalidade pela Carta "
            f"(Vit {player.get('vitalidade', 0)})."
        )
        _record_class_event(
            out,
            "self_harm",
            amount=self_harm,
            vitality_delta=int(player.get("vitalidade", 0) or 0) - before,
            actor_id=player_id,  # SPEC-353 R13: o custo tem dono e Carta no registro
            card_id=used.get("card_id") or card.get("id"),
            ferimento=_new_wound_note(player, wounds_before),
        )
        _entropy_event(player, {"kind": "on_self_harm", "amount": self_harm}, out)
        _check_terminal(
            player, player_id, out, damage_applied=True, cause="auto_dano", record=True
        )

    decay_kind = mechanics.get("decadencia")
    if decay_kind:
        _entropy_event(player, {"kind": "on_decay_nearby", "decay_kind": decay_kind}, out)

    if player.get("class_name") == "Arcanista Cinzento":
        _entropy_event(player, {"kind": "on_channel"}, out)
        before_deadline = player.get("_cool_deadline")
        cm.arm_boiler(player, {"cools": bool(mechanics.get("resfria_caldeira"))})
        after_deadline = player.get("_cool_deadline")
        if before_deadline != after_deadline:
            kind = "special:boiler_cooled" if after_deadline is None else "special:boiler_armed"
            _record_class_event(out, kind, deadline=after_deadline)

    economy = used.get("economy") or {}
    if economy.get("dependencia_applied"):
        _record_class_event(
            out,
            "consequence:dependencia",
            cost=int(economy.get("cost", 0) or 0),
            base_cost=int(economy.get("base_cost", 0) or 0),
        )
    if str((card.get("efeito") or {}).get("kind")) == "reduzir_carga_aliado":
        _record_class_event(out, "special:purga")

    before_scar = (
        int(player.get("vitalidade_max_penalty", 0) or 0),
        int(player.get("abyss_charge", 0) or 0),
    )
    cm.apply_scar(player, {"peak": bool(mechanics.get("pico"))}, out["logs"])
    after_scar = (
        int(player.get("vitalidade_max_penalty", 0) or 0),
        int(player.get("abyss_charge", 0) or 0),
    )
    if after_scar != before_scar:
        _record_class_event(
            out,
            "consequence:cicatriz",
            max_vitality_penalty_delta=after_scar[0] - before_scar[0],
            charge_delta=after_scar[1] - before_scar[1],
        )


def _has_any_wound(target: dict) -> bool:
    fer = target.get("ferimentos") or {}
    return any(fer.get(c) for c in ("leve", "grave", "critico"))


def _mark_dead(target: dict, target_id: str, out: dict) -> None:
    target["dead"] = True
    target["status"] = "morto"
    if target_id not in out["deaths"]:
        out["deaths"].append(target_id)
    out["logs"].append(f"{_name(target)} é derrotado.")


def _mark_down(target: dict, target_id: str, out: dict, nonlethal: str, by: str) -> None:
    """Desfecho de queda do alvo. `nonlethal` = "" (letal), "shadow" (só registra o que
    aconteceria e mata como hoje) ou "on" (SPEC-325 R9: incapacitado, não morto)."""
    if nonlethal == "on":
        death_flow.apply_nonlethal_finish(target)
        target["status"] = "incapacitado"
        target["nonlethal_by"] = by
        if target_id not in out.setdefault("incapacitated", []):
            out["incapacitated"].append(target_id)
        out["logs"].append(f"{_name(target)} cai desacordado.")
        _log_event("combat", "nonlethal", target=target_id)
        return
    if nonlethal == "shadow":
        _log_event("combat", "nonlethal_shadow", target=target_id)
    _mark_dead(target, target_id, out)


def _check_terminal(
    target: dict,
    target_id: str,
    out: dict,
    *,
    damage_applied: bool = False,
    nonlethal: str = "",
    by: str = "",
    cause: str = "",
    record: bool = False,
) -> None:
    """Wrapper (SPEC-353 R7): com ``record=True`` grava em ``out["final_blows"]`` quem causou a
    queda. Só os chamadores do nível do orquestrador pedem; Reação/efeitos de Carta não (R40)."""
    before = (
        target_id in out.get("deaths", []),
        target_id in out.get("terminal", []),
        bool(target.get("incapacitated")),
    )
    _check_terminal_inner(
        target, target_id, out, damage_applied=damage_applied, nonlethal=nonlethal, by=by
    )
    after = (
        target_id in out.get("deaths", []),
        target_id in out.get("terminal", []),
        bool(target.get("incapacitated")),
    )
    if record and after != before:
        _record_final_blow(out, target_id, by=by, cause=cause)


def _record_final_blow(out: dict, target_id: str, *, by: str = "", cause: str = "") -> None:
    """Registro de autoria da queda (só para o resumo/registro; nunca afeta o motor)."""
    blow: dict = {
        "target_id": target_id,
        "kind": cause or ("ataque" if by else "dano_continuo"),
        "by_actor_id": by or None,
        "card_id": None,
        "condition": None,
    }
    if blow["kind"] == "ataque":
        for atk in reversed(out.get("attacks") or []):
            if (
                str(atk.get("actor_id")) == str(by)
                and str(atk.get("target_id")) == str(target_id)
                and atk.get("acerto")
            ):
                blow["card_id"] = atk.get("card_id")
                if atk.get("label") == "Última Ação":
                    blow["kind"] = "ultima_acao"
                break
    elif blow["kind"] == "dano_continuo":
        for tick in reversed(out.get("ticks") or []):
            if str(tick.get("actor_id")) == str(target_id):
                blow["condition"] = tick.get("condition")
                break
    out.setdefault("final_blows", []).append(blow)


def _check_terminal_inner(
    target: dict,
    target_id: str,
    out: dict,
    *,
    damage_applied: bool = False,
    nonlethal: str = "",
    by: str = "",
) -> None:
    """Traduz o estado de Ferimentos do alvo no desfecho da categoria (07 R7):
    Lacaio cai com qualquer Ferimento; Padrão ao encher o último Crítico; full-flow
    (jogador/Elite/Chefe/Nomeado/companheiro) dispara Última Ação → Estado Terminal.
    `nonlethal` (SPEC-325): a queda vira incapacitação quando o golpe foi declarado
    não-letal e a forma do ataque permite."""
    if target.get("dead") or target.get("estado_terminal") or target.get("incapacitated"):
        return
    if (
        damage_applied
        and death_flow.uses_full_death_flow(target)
        and death_flow.critical_spaces_full(target)
        and target.get("last_stand_resolved")
    ):
        # Sobreviver ao fluxo terminal não concede imortalidade. O próximo dano
        # real com todos os espaços críticos ocupados encerra a vida; mera
        # passagem de rodada, sem dano, nunca dispara esta cláusula.
        _mark_down(target, target_id, out, nonlethal, by)
        return
    if death_flow.minion_defeated_by_wound(target) and _has_any_wound(target):
        _mark_down(target, target_id, out, nonlethal, by)
        return
    if death_flow.should_trigger_last_stand(target):
        death_flow.trigger_last_stand(target)
        if target_id not in out["terminal"]:
            out["terminal"].append(target_id)
        out["logs"].append(f"{_name(target)} prepara sua Última Ação!")
    elif not death_flow.uses_full_death_flow(target) and death_flow.critical_spaces_full(target):
        _mark_down(target, target_id, out, nonlethal, by)


def _record_tactic(
    out: dict,
    actor_id: str,
    action_key: str,
    *,
    target_id: str | None = None,
    ok: bool,
    detail: str = "",
) -> None:
    out.setdefault("tactics", []).append(
        {
            "actor_id": actor_id,
            "action_key": action_key,
            "target_id": target_id,
            "ok": bool(ok),
            "detail": str(detail or "")[:160],
        }
    )


def _resolve_tactical_action(
    scene: dict,
    actor: dict,
    actor_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    step,
    out: dict,
    rng,
) -> None:
    """Executa somente o catálogo mecânico fechado dos perfis determinísticos."""
    action_key = str(step.maneuver or "")
    target_id = step.target_id
    target = actors_by_id.get(target_id) if target_id else None
    same_side = set(_same_side_ids(actor_id, sides))
    opposing = set(_opposing_ids(actor_id, sides))
    ok = False
    detail = ""

    if action_key == "protect":
        if target_id in same_side and target_id != actor_id and _available_for_aid(target):
            ok = cs.grant_tactical_modifier(scene, "protected", target_id, actor_id)
            detail = f"{_name(actor)} protege {_name(target)} no próximo ataque."
    elif action_key == "stabilize":
        if (
            target_id in same_side
            and target_id != actor_id
            and target
            and target.get("estado_terminal")
        ):
            target["_tactical_stabilization_round"] = cs.tactical_round(scene)
            has_kit = bool(actor.get("has_kit") or actor.get("_has_kit"))
            is_medic = (
                actor.get("tactical_archetype") == "suporte"
                or "medic" in str(actor.get("class_name", "")).lower()
                or "médic" in str(actor.get("class_name", "")).lower()
            )
            result = death_flow.attempt_stabilization(
                target,
                actor,
                has_kit=has_kit,
                is_medico=is_medic,
                has_potion=False,
                rng=rng,
            )
            detail = result.get("log") or result.get("cause", "")
            ok = bool(result.get("revived"))
            if result.get("dead"):
                target["status"] = "morto"
                if target_id not in out["deaths"]:
                    out["deaths"].append(target_id)
            elif result.get("revived"):
                if target_id in out.get("terminal", []):
                    out["terminal"].remove(target_id)
                out.setdefault("scars_pending", []).append(target_id)
    elif action_key == "flank":
        if target_id in opposing and _alive(target):
            result = cs.hide(
                scene,
                actor_id,
                source="flanco tático",
                observers=[target_id],
                spend=False,
            )
            ok = bool(result.get("ok"))
            detail = result.get("log") or result.get("error", "")
    elif action_key == "control":
        if (
            target_id in opposing
            and _alive(target)
            and cs.tactical_cooldown(scene, actor_id, "control") == 0
        ):
            detail = cm.apply_condition(
                target,
                {
                    "name": "Controle tático",
                    "dot": 0,
                    # SPEC-285 R4: nega exatamente UM turno do alvo. O controle é
                    # observado no início do turno do portador e só então o tick
                    # decrementa — duration=1 já sobrevive até o próximo turno do
                    # alvo, nasça antes ou depois dele na rodada. O antigo
                    # duration=2 negava DOIS turnos por controle e, com o cooldown
                    # de 2 rodadas, um Místico sozinho prendia o alvo em
                    # atordoamento contínuo.
                    "duration": 1,
                    "source": actor_id,
                    "control": "stun",
                },
            )
            ok = "resiste" not in str(detail).lower()
            cs.set_tactical_cooldown(scene, actor_id, "control", 2)
    elif action_key == "support":
        if target_id in same_side and target_id != actor_id and _available_for_aid(target):
            if actor.get("tactical_archetype") == "suporte":
                before = int(target.get("vitalidade", 0) or 0)
                maximum = int(target.get("max_vitalidade", before) or before)
                target["vitalidade"] = min(maximum, before + 2)
                gamedata.sync_legacy_hp_aliases(target)
                restored = target["vitalidade"] - before
                ok = restored > 0
                out.setdefault("heals", []).append(  # SPEC-346 R10: a cura de apoio fecha a conta
                    {"actor_id": target_id, "card": "Apoio", "amount": restored}
                )
                detail = f"{_name(actor)} recupera {restored} Vitalidade de {_name(target)}."
            else:
                ok = cs.grant_tactical_modifier(scene, "attack_advantage", target_id, actor_id)
                detail = f"{_name(actor)} coordena o próximo ataque de {_name(target)}."
    elif action_key == "flee":
        result = cs.move_distance(scene, actor_id, "afastar")
        ok = bool(result.get("ok"))
        detail = result.get("log") or result.get("error", "")
        if ok and result.get("distance_state") == "separado":
            actor["fled"] = True
            actor["status"] = "fugiu"
            detail = f"{detail} {_name(actor)} escapa do conflito."
    else:
        detail = f"Ação tática fora do catálogo: {action_key!r}."

    out["logs"].append(detail or f"{_name(actor)} não consegue executar {action_key}.")
    _record_tactic(out, actor_id, action_key, target_id=target_id, ok=ok, detail=detail)


# ==========================================================================
# Resolução do turno de um ator (compõe conflict_turn + reações + AoO)
# ==========================================================================
def _extend_ally_defense(ev: dict, actors_by_id: dict[str, dict], out: dict) -> None:
    """SPEC-283 R2 / SPEC-285 R3 (os dois lados): buff/debuff tipado expira no fim do turno do PORTADOR
    (SPEC-232 R1). Proteção posta num aliado que ainda vai agir nesta rodada
    expiraria antes de qualquer ataque do lado oposto — então ganha +1 turno e
    passa a cobrir os ataques da próxima rodada, como a defesa posta em si mesmo."""
    target_id = ev.get("target_id")
    if ev.get("kind") not in _ENEMY_DEFENSIVE_SUPPORT or target_id == ev.get("actor_id"):
        return
    if target_id in (out.get("resolved_turns") or []):
        return
    for condition in (actors_by_id.get(target_id) or {}).get("active_conditions") or []:
        if str(condition.get("source") or "") == str(ev.get("card_id")):
            condition["duration"] = int(condition.get("duration", 1) or 1) + 1


def _own_side_support(step, actor_id: str, sides: dict[str, list[str]]) -> bool:
    """SPEC-283 R6: Carta de suporte no próprio ator/lado não é ataque declarado —
    não abre a janela de Reação do lado oposto."""
    if step.kind != "card" or not step.card_id:
        return False
    kind = str(((_get_card(step.card_id) or {}).get("efeito") or {}).get("kind") or "")
    if kind not in ct._SUPPORT_EFFECTS:
        return False
    return step.target_id == actor_id or step.target_id in set(_same_side_ids(actor_id, sides))


def _note_denied_span(out: dict, actor_id: str) -> None:
    """SPEC-347 R14.1: turno negado (atordoado/incapaz) — registro vazio, só para a view."""
    out.setdefault("turn_spans", []).append(
        {
            "actor_id": actor_id,
            "attacks": [len(out.get("attacks") or [])] * 2,
            "cards": [len(out.get("cards_used") or [])] * 2,
            "negado": True,
        }
    )


def _resolve_actor_turn(
    scene: dict,
    actor: dict,
    actor_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    decl,
    state,
    out: dict,
    rng,
) -> None:
    """SPEC-347 R14.1: anota em `out["turn_spans"]` os índices de `attacks`/`cards_used` do turno
    (só view; nenhum número muda). A resolução em si está em `_resolve_actor_turn_inner`."""
    a0, c0 = len(out.get("attacks") or []), len(out.get("cards_used") or [])
    try:
        _resolve_actor_turn_inner(
            scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng
        )
    finally:
        out.setdefault("turn_spans", []).append(
            {
                "actor_id": actor_id,
                "attacks": [a0, len(out.get("attacks") or [])],
                "cards": [c0, len(out.get("cards_used") or [])],
            }
        )


_ABSORB_RE = re.compile(r"(?:Proteção(?: \(efeito\))?|Vigília) -(\d+)")


def _annotate_absorbed(sub: dict) -> None:
    """SPEC-353 R20: quanto a Proteção do alvo tirou de cada golpe que acertou, lido do registro
    do próprio pipeline de dano (uma linha com "(excedente" por golpe com dano, na mesma ordem)."""
    dmg_logs = [l for l in sub.get("logs", []) if l and "(excedente" in str(l)]
    hits = [
        a for a in sub.get("attacks", []) if a.get("acerto") and a.get("dano_final") is not None
    ]
    if len(dmg_logs) != len(hits):
        return
    for atk, line in zip(hits, dmg_logs, strict=True):
        total = sum(int(n) for n in _ABSORB_RE.findall(str(line)))
        if total > 0:
            atk["absorvido"] = total


def _resolve_actor_turn_inner(
    scene: dict,
    actor: dict,
    actor_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    decl,
    state,
    out: dict,
    rng,
) -> None:
    decl = decl if isinstance(decl, ct.TurnDeclaration) else ct.TurnDeclaration(**decl)
    out.setdefault("resolved_turns", []).append(actor_id)

    # AoO ao abandonar Engajamento sem Desengajar (06 R5).
    if _declaration_leaves_engagement(decl):
        _resolve_opportunity_attacks(scene, actor_id, actors_by_id, sides, out, rng)
        if not _can_act(actor):
            return

    # Janela de Reação sobre um ataque declarado (06 R1) — reator define Guarda na cena.
    acao = decl.acao
    if (
        acao is not None
        and acao.kind in ("attack", "card")
        and acao.target_id
        and not _own_side_support(acao, actor_id, sides)
    ):
        _open_reaction_window(
            scene, actor_id, acao.target_id, actors_by_id, sides, out, state, rng=rng, step=acao
        )

    if acao is not None and acao.kind == "tactic":
        cs.reset_turn_budget(scene, actor_id)
        _resolve_tactical_action(scene, actor, actor_id, actors_by_id, sides, acao, out, rng)
        return

    # SPEC-330: queda medida ANTES do turno (P1-2) e modo não-letal do golpe
    # declarado visível ao dano extra das Cartas (P2-6).
    fallen_before = {aid for aid, a in actors_by_id.items() if fx.has_fallen(a)}
    fx_ctx = fx.current()
    if fx_ctx is not None:
        fx_ctx.nonlethal_actor = actor_id
        fx_ctx.nonlethal = (
            _nonlethal_mode(decl, acao, actor_id, acao.target_id, sides)
            if acao is not None and acao.target_id
            else ""
        )
    try:
        sub = ct.resolve_turn(scene, actors_by_id, decl, state=state, rng=rng, sides=sides)
    finally:
        if fx_ctx is not None:
            fx_ctx.nonlethal, fx_ctx.nonlethal_actor = "", None
    _annotate_absorbed(sub)  # SPEC-353 R20 (registro; fora de ct.resolve_turn)
    out["logs"] += [l for l in sub.get("logs", []) if l]
    out.setdefault("attacks", []).extend(sub.get("attacks", []))
    out.setdefault("cards_used", []).extend(sub.get("cards_used", []))
    if sub.get("heals"):  # SPEC-346 R10
        out.setdefault("heals", []).extend(sub["heals"])
    if sub.get("enemy_fallbacks"):
        out.setdefault("enemy_fallbacks", []).extend(sub["enemy_fallbacks"])
    # SPEC-330: eventos estruturados do intérprete de efeitos produzidos no turno.
    for key in fx.TURN_EVENT_KEYS:
        if sub.get(key):
            out.setdefault(key, []).extend(sub[key])
    if sub.get("enemy_support_cards"):
        out.setdefault("enemy_support_cards", []).extend(sub["enemy_support_cards"])
        for ev in sub["enemy_support_cards"]:
            _extend_ally_defense(ev, actors_by_id, out)
        logger.info(
            "enemy_support_card actor=%s cards=%s",
            actor_id,
            [ev.get("card_id") for ev in sub["enemy_support_cards"]],
        )
    if actor_id not in set(sides.get("enemy", [])) and acao is not None and acao.kind == "card":
        # SPEC-285 R3: simetria da SPEC-283 R2 — proteção que o lado do JOGADOR
        # põe num aliado que ainda vai agir também ganha +1 turno. Companheiro
        # (não-player) com Carta de bestiário já sai em `enemy_support_cards` e
        # foi estendido acima — não estende de novo (sem dupla contagem).
        already = {
            (ev.get("actor_id"), ev.get("card_id")) for ev in sub.get("enemy_support_cards") or []
        }
        for used in sub.get("cards_used", []):
            if used.get("actor_id") != actor_id or acao.target_id not in _same_side_ids(
                actor_id, sides
            ):
                continue
            if (used.get("actor_id"), used.get("card_id")) in already:
                continue
            _extend_ally_defense(
                {
                    "kind": str(((used.get("card") or {}).get("efeito") or {}).get("kind") or ""),
                    "actor_id": actor_id,
                    "target_id": acao.target_id,
                    "card_id": used.get("card_id"),
                },
                actors_by_id,
                out,
            )
    for tid in sub.get("terminal", []):
        if tid not in out["terminal"]:
            out["terminal"].append(tid)
    for did in sub.get("deaths", []):
        if did not in out["deaths"]:
            out["deaths"].append(did)
    for sid in sub.get("scars_pending", []):  # SPEC-231 R8: carta estabilizar
        scars = out.setdefault("scars_pending", [])
        if sid not in scars:
            scars.append(sid)

    # Gatilhos de classe do JOGADOR a partir do que o turno produziu.
    player = actors_by_id.get(_player_id(sides))
    if player is not None:
        for used in sub.get("cards_used", []):
            if used.get("actor_id") == _player_id(sides):
                _apply_player_card_mechanics(
                    player,
                    used,
                    _player_id(sides) or actor_id,
                    out,
                    rng,
                )

    # on_damage_taken: quem levou dano neste turno (alvos dos ataques que acertaram).
    for tid, amount in _hit_events(sub, decl):
        tgt = actors_by_id.get(tid)
        if tgt is None:
            continue
        if tgt.get("is_player"):
            _entropy_event(tgt, {"kind": "on_damage_taken", "amount": amount}, out)
            before = (int(tgt.get("entropy", 0) or 0), int(tgt.get("_blood_entropy", 0) or 0))
            cm.apply_blood_leak(tgt, out["logs"])
            after = (int(tgt.get("entropy", 0) or 0), int(tgt.get("_blood_entropy", 0) or 0))
            if after != before:
                _record_class_event(out, "special:blood_leak", entropy_delta=after[0] - before[0])
        elif player is not None and tid in set(sides.get("hero", []) + sides.get("ally", [])):
            _entropy_event(player, {"kind": "on_ally_suffer"}, out)
        nl_mode = _nonlethal_mode(decl, acao, actor_id, tid, sides)
        _check_terminal(
            tgt, tid, out, damage_applied=True, nonlethal=nl_mode, by=actor_id, record=True
        )
        if fx_ctx is not None:  # SPEC-330 R3 (no-op sem ouvintes armados)
            fx.on_damage(fx_ctx, tid, actor_id, amount, out)
        if (
            nl_mode
            and not tgt.get("dead")
            and not tgt.get("incapacitated")
            and not tgt.get("is_player")
            and (tgt.get("last_stand_pending") or tgt.get("estado_terminal"))
            and not tgt.get("last_stand_resolved")
        ):
            # SPEC-325 R9/D2: o golpe não-letal que enche o último Crítico de um
            # Elite/Chefe/Nomeado ainda dispara a Última Ação, mas o desfecho
            # terminal vira incapacitação (nunca morte) — ver _resolve_terminal_states.
            if nl_mode == "on":
                tgt["nonlethal_pending_by"] = actor_id
            else:
                _log_event("combat", "nonlethal_shadow", target=tid)
        if tgt.get("is_player") and _can_act(tgt) and _alive(actor):
            # SPEC-232 R2: passiva `contra_ataque` (tier 8) — revida 1×frequência.
            for pe in cm.triggered_passives(tgt, "on_hit_taken"):
                from services import cards

                paid = cards.use_passive(tgt, pe["source_card"])
                if paid.get("ok"):
                    out["logs"].append(paid["log"])
                    _basic_attack(
                        scene,
                        tgt,
                        tid,
                        actor,
                        actor_id,
                        out,
                        rng,
                        label="Contra-ataque",
                        damage_override=pe.get("value"),
                    )

    # SPEC-330 R3 `ao_derrubar`: quem caiu NESTE turno (golpe, efeito extra ou
    # gatilho), comparado com o estado anterior ao turno. Atordoar não conta.
    if fx_ctx is not None:
        for aid in sorted(actors_by_id):
            if aid != actor_id and aid not in fallen_before and fx.has_fallen(actors_by_id[aid]):
                fx.fire("ao_derrubar", sujeito_id=actor_id, alvo_id=aid, out=out)


def _nonlethal_mode(decl, acao, actor_id: str, target_id: str, sides: dict) -> str:
    """SPEC-325 R9: "" / "shadow" / "on" para o golpe do JOGADOR declarado não-letal.
    Só ataque/Carta do herói contra o lado inimigo; forma letal da Carta recusa."""
    if (
        acao is None
        or acao.kind not in ("attack", "card")
        or not (acao.params or {}).get("nao_letal")
        or actor_id != _player_id(sides)
        or target_id not in set(sides.get("enemy", []))
    ):
        return ""
    mode = combat_flags.mode("nonlethal")
    if mode == "off":
        return ""
    form: dict = {}
    if acao.kind == "card":
        from services import cards

        card = cards.get_card(acao.card_id or "") or {}
        form = {
            "tipo": str((card.get("efeito") or {}).get("kind") or ""),
            "letal_forcado": bool(card.get("letal")),
        }
    return mode if death_flow.can_be_nonlethal(form) else ""


def _hit_events(sub: dict, decl: "ct.TurnDeclaration") -> list[tuple[str, int]]:
    """Alvos acertados e dano mecânico final; preserva alvo legado da declaração."""
    fallback = decl.acao.target_id if decl.acao else None
    events: list[tuple[str, int]] = []
    for attack in sub.get("attacks", []):
        if not attack.get("acerto"):
            continue
        target_id = attack.get("target_id") or fallback
        if target_id:
            events.append((str(target_id), int(attack.get("dano_final", 0) or 0)))
    return events


def _player_id(sides: dict[str, list[str]]) -> str | None:
    return (sides.get("hero") or [None])[0]


def _find_player(actors_by_id: dict[str, dict], sides: dict[str, list[str]]) -> dict | None:
    pid = _player_id(sides)
    p = actors_by_id.get(pid) if pid else None
    if p is not None and p.get("is_player"):
        return p
    for a in actors_by_id.values():
        if a.get("is_player"):
            return a
    return None


# ==========================================================================
# Estabilização do Estado Terminal (07, decisão R6=A)
# ==========================================================================
def resolve_terminals(
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    out: dict,
    *,
    scene: dict | None = None,
    rng=None,
) -> None:
    """Cada ator em Estado Terminal resolve DENTRO do combate (R6=A): auto-reanima
    com Médico+kit/poção; senão um aliado consciente tenta estabilizar; sem aliado
    capaz ou 2 falhas = morte. Sobreviver marca Cicatriz (`scar_pending`). Só a morte
    REAL do jogador vira `player_dead` (o nó de combate abre a tela de morte)."""
    pending_ids = list(out.get("terminal", []))
    pending_ids.extend(
        actor_id
        for actor_id, actor in actors_by_id.items()
        if actor.get("estado_terminal") and actor_id not in pending_ids
    )
    for actor_id in pending_ids:
        target = actors_by_id.get(actor_id)
        if not target or not target.get("estado_terminal"):
            continue
        if target.get("nonlethal_pending_by") and not target.get("is_player"):
            by = str(target.pop("nonlethal_pending_by"))
            death_flow.apply_nonlethal_finish(target)
            target["status"] = "incapacitado"
            target["nonlethal_by"] = by
            if actor_id not in out.setdefault("incapacitated", []):
                out["incapacitated"].append(actor_id)
            out["logs"].append(f"{_name(target)} cai desacordado.")
            continue
        try:
            tactical_stabilization_round = int(target.get("_tactical_stabilization_round", -1))
        except (TypeError, ValueError):
            tactical_stabilization_round = -1
        if scene is not None and tactical_stabilization_round == cs.tactical_round(scene):
            # A ação tática já consumiu a tentativa desta rodada. Não rola uma
            # segunda estabilização automática sobre a mesma queda.
            continue
        helper = _stabilizer_for(actor_id, actors_by_id, sides)
        res = death_flow.attempt_stabilization(
            target,
            helper,
            has_kit=bool(target.get("_has_kit") or (helper or {}).get("has_kit")),
            is_medico="médico" in str((helper or {}).get("class_name", "")).lower()
            or "medico" in str((helper or {}).get("class_name", "")).lower(),
            has_potion=bool(target.get("_has_stabilize_potion")),
            rng=rng,
        )
        out.setdefault("stabilizations", []).append({"actor_id": actor_id, **res})
        if res.get("log"):
            out["logs"].append(res["log"])
        if res.get("dead"):
            target["status"] = "morto"
            if actor_id not in out["deaths"]:
                out["deaths"].append(actor_id)
            if target.get("is_player"):
                out["player_dead"] = True
        elif res.get("revived"):
            out.setdefault("scars_pending", []).append(actor_id)


def _declared_target(actor_id: str, actor: dict, out: dict, opposing: list[str]) -> str | None:
    """SPEC-346 R9: alvo hostil declarado na rodada. Inimigo: alvo do presságio cumprido; senão
    (e para o herói) o `target_id` do ultimo ataque do ator contra o lado oposto."""
    if not actor.get("is_player"):
        for p in reversed(out.get("pressagios_cumpridos") or []):
            if p.get("actor_id") == actor_id and p.get("alvo_id") in opposing:
                return p["alvo_id"]
    for atk in reversed(out.get("attacks") or []):
        if atk.get("actor_id") == actor_id and atk.get("target_id") in opposing:
            return atk["target_id"]
    return None


def _resolve_last_stands(
    scene: dict,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    out: dict,
    rng,
    preferred_targets: dict[str, str] | None = None,
) -> None:
    """Executa cada Última Ação pendente uma única vez, antes do terminal.

    A semântica mínima determinística usa um ataque básico com vantagem extrema
    contra o alvo vivo mais próximo. Ela deliberadamente ignora custo de Carta,
    Entropia e Ferimentos, como exige o contrato da Última Ação.
    """
    out.setdefault("last_stands", [])
    cursor = 0
    while cursor < len(out.get("terminal", [])):
        actor_id = out["terminal"][cursor]
        cursor += 1
        actor = actors_by_id.get(actor_id)
        if actor is None or actor.get("last_stand_resolved") or not actor.get("last_stand_pending"):
            continue
        opposing = _opposing_ids(actor_id, sides)
        target_id = None
        # SPEC-346 R9: a Última Ação mira o alvo declarado (ultimo ataque / presságio), se vivo.
        preferred = (preferred_targets or {}).get(actor_id) or _declared_target(
            actor_id, actor, out, opposing
        )
        if preferred in opposing and _alive(actors_by_id.get(preferred)):
            target_id = preferred
        if target_id is None:
            target_id = _nearest_target(actor_id, opposing, actors_by_id)
        out["logs"].append(f"{_name(actor)} executa sua Última Ação.")
        if target_id is not None:
            _n_attacks = len(out.get("attacks") or [])
            _basic_attack(
                scene,
                actor,
                actor_id,
                actors_by_id[target_id],
                target_id,
                out,
                rng,
                label="Última Ação",
                advantage=1,
            )
            if (
                len(out.get("attacks") or []) > _n_attacks
            ):  # SPEC-346 R9: o mech_log rotula e diz se o alvo foi o declarado
                out["attacks"][-1]["label"] = "Última Ação"
                out["attacks"][-1]["alvo_declarado"] = target_id == preferred
        else:
            out["logs"].append(f"{_name(actor)} não encontra alvo para a Última Ação.")
        death_flow.enter_terminal_state(actor)
        out["last_stands"].append(actor_id)
        # A Última Ação pode ter preenchido o Crítico de outro ator.
        for target in actors_by_id:
            candidate = actors_by_id[target]
            if death_flow.should_trigger_last_stand(candidate):
                death_flow.trigger_last_stand(candidate)
                if target not in out["terminal"]:
                    out["terminal"].append(target)


def _stabilizer_for(
    down_id: str,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    *,
    scene: dict | None = None,
) -> dict | None:
    """SPEC-231 R1/R2: hero+ally são UM lado. Ordem: party ativa, aliado
    transitório, depois maior Agilidade (D-B: sem exigir adjacência)."""
    candidates = []
    for aid in _same_side_ids(down_id, sides):
        if aid == down_id:
            continue
        a = actors_by_id.get(aid)
        if _alive(a) and not a.get("estado_terminal"):
            candidates.append(a)
    if not candidates:
        return None

    def rank(a: dict):
        tier = 0 if a.get("is_player") else (2 if a.get("transient") else 1)
        agi = int((a.get("virtudes") or {}).get("agilidade", 0) or 0)
        return (tier, -agi)

    return sorted(candidates, key=rank)[0]


# ==========================================================================
# Evento do Abismo carregado por Cargas (10)
# ==========================================================================
def _maybe_abyss(
    scene: dict,
    player: dict,
    actors_by_id: dict[str, dict],
    prepared_abyss: list[dict] | None,
    out: dict,
    *,
    scene_state: dict | None = None,
    rng=None,
) -> None:
    if not prepared_abyss or player is None:
        return
    charges = int(player.get("abyss_charge", 0) or 0)
    event = abyss_events.select_event(
        prepared_abyss,
        scene_state or {},
        charges,
        scene_objects=scene.get("objects"),
        seed=rng.random() if rng else None,
    )
    if not event:
        return
    from services import encounter_preparation as prep

    # SPEC-232 R9: só gasta Cargas/usos se o EffectSpec materializa (alvo e
    # potência válidos); rejeitado = nada debitado.
    if (
        prep.materialize_effect(
            event.get("effect") or {},
            int(scene.get("encounter_level", 1) or 1),
            valid_targets=set(actors_by_id),
        )
        is None
    ):
        out["logs"].append("Evento do Abismo sem alvo válido — nenhuma Carga gasta.")
        return
    fired = abyss_events.trigger_event(event, scene_state or {})
    if not fired.get("ok"):
        return
    player["abyss_charge"] = max(0, charges - int(fired.get("cargas_gastas", 0) or 0))
    out["logs"].append(fired["log"])
    out.setdefault("abyss", []).append(fired.get("effect"))
    apply_effect_spec(scene, actors_by_id, fired.get("effect") or {}, out, rng=rng)


def apply_effect_spec(
    scene: dict, actors_by_id: dict[str, dict], effect: dict, out: dict, *, rng=None
) -> None:
    """Aplica um EffectSpec do catálogo fechado (03/10). Cobre os kinds resolvíveis
    em combate; os puramente de cena (block_route/alter_terrain…) só se registram."""
    from services import encounter_preparation as prep

    materialized = prep.materialize_effect(
        effect,
        int(scene.get("encounter_level", 1) or 1),
        valid_targets=set(actors_by_id),
    )
    if materialized is None:
        out.setdefault("logs", []).append("Efeito mecânico rejeitado: potência ou alvo inválido.")
        return
    kind = str(materialized.get("kind"))
    params = materialized.get("params") or {}
    if kind == "damage":
        tid = params.get("target")
        tgt = actors_by_id.get(tid)
        if tgt is not None:
            dres = resolve_damage_and_wounds(
                tgt,
                damage_base=int(params.get("amount", 1) or 1),
                damage_type=str(params.get("tipo", "abissal")),
                directed_region=None,
                rng=rng,
            )
            out["logs"] += dres["log"]
            _check_terminal(tgt, tid, out, damage_applied=True)
    elif kind == "apply_condition":
        tid = params.get("target")
        tgt = actors_by_id.get(tid)
        if tgt is not None:
            # SPEC-232: condição nomeada passa pelo catálogo fechado (efeito real).
            cond = cm.parse_condition(str(params.get("condition", "abissal")), source="abismo")
            cond["duration"] = int(params.get("duration", 1) or 1)
            out.setdefault("logs", []).append(cm.apply_condition(tgt, cond))


# ==========================================================================
# Rodada completa
# ==========================================================================
def _refused_player_item(actors_by_id, sides, declarations) -> str:
    """Motivo da recusa se o protagonista declarou um item que `try_use_item`
    recusaria (sem mutar nada); '' caso contrário."""
    import inventory

    pid = _player_id(sides)
    decl = (declarations or {}).get(pid) if pid else None
    player = actors_by_id.get(pid) if pid else None
    if decl is None or player is None:
        return ""
    if not isinstance(decl, ct.TurnDeclaration):
        decl = ct.TurnDeclaration(**decl)
    for step in (decl.pre_acao, decl.acao, decl.pos_acao):
        if step is None or str(step.kind or "").lower() != "item":
            continue
        target = actors_by_id.get(step.target_id) if step.target_id else None
        res = inventory.try_use_item(player, step.item_id or step.object_id or "", target=target)
        if not res["ok"]:
            return res["reason"]
    return ""


logger = logging.getLogger("rpg.conflict")
STALEMATE_ROUNDS = 6


def _damage_fingerprint(actors_by_id: dict[str, dict]) -> str:
    """Só dano/estado vital — posição e ocultação ficam de fora de propósito
    (esconder/revelar em ciclo é exatamente o impasse)."""
    bits = []
    for aid in sorted(actors_by_id):
        a = actors_by_id[aid]
        bits.append(
            (
                aid,
                int(a.get("vitalidade", a.get("hp", 0)) or 0),
                str(a.get("status") or ""),
                bool(a.get("dead")),
                bool(a.get("fled")),
                bool(a.get("surrendered")),
                json.dumps(a.get("ferimentos") or {}, sort_keys=True, default=str),
            )
        )
    return json.dumps(bits, default=str)


def _is_cowardly(actor: dict) -> bool:
    profile = actor.get("tactical_profile") or {}
    names = (
        actor.get("tactical_archetype"),
        actor.get("arquetipo"),
        actor.get("profile"),
        profile.get("archetype") if isinstance(profile, dict) else None,
    )
    return any(str(n or "").startswith("covarde") for n in names)


def _stalemate_guard(
    scene: dict, actors_by_id: dict[str, dict], sides: dict[str, list[str]]
) -> list[dict]:
    """SPEC-275 R5 (decisão do dono 2026-10-18): após ``STALEMATE_ROUNDS``
    rodadas seguidas SEM dano, o motor quebra o impasse, 100% determinístico:
    inimigos ``covarde*`` fogem (``fled``); os demais perdem a ocultação e
    atacam na rodada seguinte. Contador em ``scene["stalemate"]`` (persistido
    junto da cena; ausente em saves antigos = 0). Devolve eventos estruturados
    ``{event, actor_id, outcome, log}`` — só ``log`` (pt-BR) vai à narração."""
    fp = _damage_fingerprint(actors_by_id)
    st = scene.setdefault("stalemate", {"rounds": 0, "fp": fp})
    if st.get("fp") != fp:
        st["rounds"], st["fp"] = 0, fp
        return []
    st["rounds"] = int(st.get("rounds", 0) or 0) + 1
    if st["rounds"] <= STALEMATE_ROUNDS:
        return []
    st["rounds"] = 0
    events = []
    for eid in sides.get("enemy", []):
        enemy = actors_by_id.get(eid)
        if enemy is None or not _can_act(enemy):
            continue
        if _is_cowardly(enemy):
            enemy["fled"] = True
            enemy["status"] = "fugiu"
            events.append(
                {
                    "event": "conflict_stalemate_broken",
                    "actor_id": eid,
                    "outcome": "fled",
                    "log": f"{_name(enemy)} desiste do impasse e foge do conflito.",
                }
            )
        else:
            pos = (scene.get("positions") or {}).get(eid)
            if pos is not None:
                cs._reveal(pos)
            enemy["_forced_attack"] = True
            events.append(
                {
                    "event": "conflict_stalemate_broken",
                    "actor_id": eid,
                    "outcome": "reveal_attack",
                    "log": f"{_name(enemy)} perde a paciência e sai da ocultação para atacar.",
                }
            )
    if events:
        logger.info("conflict_stalemate_broken events=%s", len(events))
    return events


def extra_actions(actor: dict) -> int:
    """SPEC-295 (K2): ações além da primeira na rodada (`acoes_por_rodada` − 1).

    Só ficha de inimigo traz o campo; ausente (saves antigos) = 1 ação.
    As ações da rodada dividem o mesmo limite por turno das Cartas de inimigo
    (`reset_enemy_card_usage` roda uma vez por rodada; revisão P3-2)."""
    try:
        return max(0, int(actor.get("acoes_por_rodada") or 1) - 1)
    except (TypeError, ValueError):
        return 0


def run_round(
    scene: dict,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    state: dict | None = None,
    **kwargs,
) -> dict:
    """Resolve uma RODADA inteira (ver `_run_round`). SPEC-330: liga o contexto
    do intérprete de efeitos (gatilhos, fila anti-loop) durante a rodada."""
    token = fx.bind(scene, actors_by_id, sides, rng=kwargs.get("rng"))
    try:
        return _run_round(scene, actors_by_id, sides, state, **kwargs)
    finally:
        fx.unbind(token)


def _run_round(
    scene: dict,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    state: dict | None = None,
    *,
    declarations: dict | None = None,
    prepared_abyss: list[dict] | None = None,
    scene_state: dict | None = None,
    initiator: str | None = None,
    rng=None,
    refusal: str = "",
    pressagios: dict | None = None,
) -> dict:
    """Resolve uma RODADA inteira. `sides` = {"hero":[ids], "ally":[ids], "enemy":[ids]}.
    `pressagios` (SPEC-329, flag `RPG_ENEMY_INTENT=on`): intenções congeladas no fim da rodada
    anterior; ausente (save antigo/1ª rodada) = calcula no início desta rodada.
    `declarations[actor_id]` = TurnDeclaration do jogador/aliado controlado; inimigos
    sem declaração recebem uma via `enemy_declaration`. Retorna
    {logs, deaths, terminal, scars_pending, player_dead, ended, reason, initiative}."""
    rng = rng or random.Random()
    declarations = dict(declarations or {})
    out = {
        "logs": [],
        "deaths": [],
        "terminal": [],
        "abyss": [],
        "attacks": [],
        "ticks": [],
        "reactions": [],
        "last_stands": [],
        "stabilizations": [],
        "resolved_turns": [],
        "tactics": [],
        "cards_used": [],
        "class_mechanics": [],
        "ended": False,
        "reason": "",
        "player_dead": False,
    }
    # Dano externo resolvido imediatamente antes da rodada (por exemplo, clima
    # durante uma tentativa de fuga) pode já ter armado a Última Ação.
    # O orquestrador precisa adotar esse estado em vez de depender apenas de
    # eventos de dano produzidos dentro de ``run_round``.
    out["terminal"].extend(
        actor_id for actor_id, actor in actors_by_id.items() if actor.get("last_stand_pending")
    )
    # SPEC-325 R11: `refusal` vem do nó (ataque corpo a corpo durante a fuga) e segue o
    # mesmo caminho do item recusado: nada na cena é tocado, os inimigos não agem.
    refusal = refusal or _refused_player_item(actors_by_id, sides, declarations)
    from services import card_deck_round as _deck  # SPEC-328 (atras de RPG_CARD_DECK)

    deck_refusal = (
        "" if refusal else _deck.refusal(state, actors_by_id, _player_id(sides), declarations)
    )
    refusal = refusal or deck_refusal
    _deck.shadow(state, actors_by_id, _player_id(sides), declarations, out)
    if refusal:
        if deck_refusal:
            out["deck_refused"] = True
        # SPEC-227 R8: item recusado (ex.: Vitalidade cheia) NÃO gasta a Ação nem
        # dá turno aos inimigos — nada na cena é tocado, o jogador redeclara.
        out["logs"].append(refusal)
        out["action_refused"] = True
        return out
    for _a in actors_by_id.values():  # SPEC-339: sobra de refresh fora de combate não vale marcador
        for _c in _a.get("active_conditions") or []:
            _c.pop("_renovada", None)
    cs.advance_tactical_state(scene)
    stalemate_events = _stalemate_guard(scene, actors_by_id, sides)
    if stalemate_events:
        out["stalemate_events"] = stalemate_events
        out["logs"].extend(ev["log"] for ev in stalemate_events)
    # SPEC-331: Cartas de Cena (início de rodada) + Relógio do Abismo. `off` = nada.
    from services import scene_cards as _sc

    _scene_rnd = cs.tactical_round(scene)
    _scene_ctx = fx.current() if _sc.enabled() else None
    if _scene_ctx is not None:
        _cond_before = _snapshot_conditions(actors_by_id)  # SPEC-339
        _scene_mark = len(out["logs"])
        _sc.tick(_scene_ctx, _scene_rnd, "inicio_rodada", out)
        _sc.abyss_clock(_scene_ctx, _scene_rnd, out)
        out.setdefault("scene_logs", []).extend(out["logs"][_scene_mark:])  # SPEC-346 R4
        _mark_fresh_conditions(_cond_before, actors_by_id, None, sides)
    # SPEC-332: fase de chefe (so `on`) ANTES do presságio; troca de fase invalida o congelado.
    phase_changed = _edk_mod.apply_phases(actors_by_id, sides, out, cs.tactical_round(scene))
    if _edk_mod.mode() == "shadow":
        out["decks_shadow"] = _edk_mod.shadow_summary(actors_by_id, sides)
    # SPEC-329: Presságio. `off` = byte a byte como antes; `shadow` calcula e compara com a
    # decisão tardia sem mudar nada; `on` executa o presságio congelado (R4).
    from services import enemy_intent as ei

    intent_mode = ei.mode()
    frozen: dict | None = None
    intent_cursor: dict[str, int] = {}
    if intent_mode != "off":
        frozen = (
            pressagios
            if (intent_mode == "on" and pressagios is not None and not phase_changed)
            else ei.forecast_round(scene, actors_by_id, sides, rng, scene_state=scene_state)
        )

    def _next_intent(actor_id: str) -> dict | None:
        i = intent_cursor.get(actor_id, 0)
        intent_cursor[actor_id] = i + 1
        lst = (frozen or {}).get(actor_id) or []
        return lst[i] if i < len(lst) else None

    def _frustrate(actor_id: str, intent: dict, motivo: str) -> None:
        # R4/R5: presságio que ficou impossível (gancho da keyword "Interromper", SPEC-330).
        a = actors_by_id.get(actor_id) or {}
        entry = {"actor_id": actor_id, "tipo": intent["tipo"], "motivo": motivo}
        if intent.get("interrompido_por"):
            # SPEC-330 Interromper: o gatilho já rodou na hora da Carta.
            entry["por"] = intent["interrompido_por"]
            entry["via"] = "interromper"
        out.setdefault("pressagios_frustrados", []).append(entry)
        if not intent.get("interrompido_por") and intent.get("alvo_id") in actors_by_id:
            # SPEC-330 R3: quem era a mira do presságio frustrado reage.
            fx.fire(
                "ao_pressagio_frustrado", sujeito_id=intent["alvo_id"], alvo_id=actor_id, out=out
            )
        out["logs"].append(ei.frustrated_line(intent, actors_by_id))
        from services import mechanics_trace as _mt

        _mt.record_step("pressagio_frustrado", actor=actor_id, reason=motivo, card_id=None)
        logger.info("pressagio_frustrado actor=%s motivo=%s name=%s", actor_id, motivo, _name(a))

    def _enemy_decl(actor_id: str, actor: dict):
        def late():
            return enemy_declaration(
                scene, actor_id, actors_by_id, sides, scene_state=scene_state, rng=rng
            )

        if frozen is None:
            return late()
        intent = _next_intent(actor_id)
        if intent_mode == "shadow":
            decl_late = late()
            if intent is not None:
                sh = out.setdefault("intent_shadow", {"total": 0, "changed": 0})
                sh["total"] += 1
                sh["changed"] += int(intent["declaration"] != decl_late.model_dump())
            return decl_late
        if intent is None or actor.get("_forced_attack"):
            return late()
        if intent.get("interrompido_por"):
            # SPEC-330 Interromper: presságio frustrado não se cumpre (nunca nos dois).
            _frustrate(actor_id, intent, "interrompido")
            return ct.TurnDeclaration(actor_id=actor_id)
        if ei.still_possible(intent, actors_by_id, scene):
            if intent["tipo"] == "render-se":
                actor["surrendered"] = True
            out.setdefault("pressagios_cumpridos", []).append(
                {"actor_id": actor_id, "tipo": intent["tipo"], "alvo_id": intent.get("alvo_id")}
            )
            out["logs"].append(f"{_name(actor)} cumpre o que o presságio anunciava.")  # R8
            return ct.TurnDeclaration(**intent["declaration"])
        _frustrate(actor_id, intent, "impossivel")
        return late()

    player = _find_player(actors_by_id, sides)
    player_id = _player_id(sides)
    player_decl = declarations.get(player_id) if player_id else None
    if player_decl is not None and not isinstance(player_decl, ct.TurnDeclaration):
        player_decl = ct.TurnDeclaration(**player_decl)
    selected_reaction = player_decl.reaction_card_id if player_decl is not None else None
    if state is not None:
        selected_reaction = selected_reaction or state.get("_player_reaction_card_id")
        state["_player_reaction_card_id"] = selected_reaction
    from services import cards

    for enemy_id in sides.get("enemy", []):
        enemy = actors_by_id.get(enemy_id)
        if enemy is not None:
            cards.reset_enemy_card_usage(enemy, "turno")
    ctx = fx.current()
    if ctx is not None:
        ctx.rng = rng
        if _deck.deck_mode(state) == "on":
            # SPEC-330 R6/R7: efeitos de pilha agem nas pilhas do jogador (so `on`).
            ctx.piles = state["_piles"]
            ctx.piles_actor = _player_id(sides)
        if intent_mode == "on" and frozen is not None:
            # SPEC-330 Interromper lê o presságio pendente (não em `shadow`).
            ctx.pressagios = frozen
            ctx.intent_cursor = intent_cursor
    for a in actors_by_id.values():
        if a.get("_cartas_rodada"):
            fx.reset_round(a)
    for aid in sorted(actors_by_id):
        if _alive(actors_by_id[aid]):
            fx.fire("inicio_rodada", sujeito_id=aid, out=out)

    # Mecânica de classe do jogador no início da rodada (SOBREVIVE).
    if player is not None:
        # Lista transitória compartilhada com o resultado; o harness a lê sem
        # depender de parsing da prosa/log e o próximo round a substitui.
        player["_last_class_mechanics"] = out["class_mechanics"]
        if state is not None:
            cards.reset_card_usage(state, "turno")
        cm.reset_entropy_turn(player)
        player.pop("_self_harmed_round", None)
        before_boiler = (
            player.get("_cool_deadline"),
            int(player.get("vitalidade", player.get("hp", 0)) or 0),
        )
        out["logs"] += cm.tick_boiler(player, rng=rng)
        after_boiler = (
            player.get("_cool_deadline"),
            int(player.get("vitalidade", player.get("hp", 0)) or 0),
        )
        if after_boiler != before_boiler:
            _record_class_event(
                out,
                "special:boiler_overload"
                if after_boiler[1] < before_boiler[1]
                else "special:boiler_tick",
                deadline=after_boiler[0],
                vitality_delta=after_boiler[1] - before_boiler[1],
            )
        conditions_before = len(player.get("active_conditions") or [])
        out["logs"] += cm.apply_transformacao(player)
        if len(player.get("active_conditions") or []) > conditions_before:
            _record_class_event(out, "consequence:transformacao")

    side_actors = {
        s: [actors_by_id[a] for a in ids if a in actors_by_id]
        for s, ids in sides.items()
        if s in ("hero", "ally", "enemy")
    }
    # hero+ally agem como um lado só na iniciativa por lado (04).
    init_sides = {
        "heroes": [a for s in ("hero", "ally") for a in side_actors.get(s, [])],
        "enemy": side_actors.get("enemy", []),
    }
    init = roll_initiative_by_side(init_sides, initiator=initiator, rng=rng)
    out["initiative"] = init["order"]
    seq: list[str] = []
    side_ids = {
        "heroes": sides.get("hero", []) + sides.get("ally", []),
        "enemy": sides.get("enemy", []),
    }
    for side in init["order"]:
        members = [aid for aid in side_ids.get(side, []) if _can_act(actors_by_id.get(aid, {}))]
        members.sort(key=lambda aid: (-_agility(actors_by_id[aid]), str(aid)))
        seq += members
    # SPEC-295 (K2): ações extras do Chefe entram no FIM da rodada, depois de todos.
    # Tick de condição, stun e expiração de buffs acontecem só na 1ª ação.
    first_turn = set(seq)
    extra = [
        aid
        for aid in sides.get("enemy", [])
        if aid in first_turn
        for _ in range(extra_actions(actors_by_id.get(aid) or {}))
    ]
    seq += extra
    denied: set[str] = set()
    acted: set[str] = set()

    def _tf_acted() -> set[str] | None:
        return acted if (intent_mode == "on" and frozen is not None) else None

    for actor_id in seq:
        actor = actors_by_id.get(actor_id)
        _cond_before = _snapshot_conditions(actors_by_id)  # SPEC-339
        if actor_id in acted:
            # Ação extra: só se a 1ª não foi negada e o ator segue de pé. Stun
            # aplicado no meio da rodada vale para a próxima, como para todos.
            if actor is None or not _can_act(actor) or actor_id in denied:
                if intent_mode == "on" and frozen is not None and actor_id not in denied:
                    _it = _next_intent(actor_id)
                    if _it is not None and _it.get("interrompido_por"):
                        _frustrate(actor_id, _it, "incapaz")  # SPEC-330 Interromper
                continue
            out["logs"].append(f"{_name(actor)} age de novo.")
            decl = _enemy_decl(actor_id, actor)
            _resolve_actor_turn(scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng)
            _note_turn_records(_cond_before, actors_by_id, actor_id, out)
            _mark_fresh_conditions(
                _cond_before, actors_by_id, actor_id, sides, taunt_frozen_acted=_tf_acted()
            )
            continue
        acted.add(actor_id)
        if actor is None or not _can_act(actor):
            denied.add(actor_id)
            _note_denied_span(out, actor_id)
            if intent_mode == "on" and frozen is not None:
                _it = _next_intent(actor_id)
                if _it is not None:
                    _frustrate(actor_id, _it, "incapaz")
            continue
        # Controle é observado ANTES do tick: duration=1 precisa negar exatamente
        # esta ação e só então expirar. O fluxo anterior removia stun/sleep antes
        # de consultá-los, tornando consumíveis de controle mecanicamente inertes.
        stunned_this_turn = cm.has_control(actor, "stun")
        # Lista de refs (não set de id()): mantém os dicts vivos — o id() de uma
        # condição removida no tick podia ser reusado por buff novo deste turno.
        present_at_start = list(actor.get("active_conditions") or [])
        dot_applied = _tick_conditions_v4(actor, out, rng=rng)
        _check_terminal(actor, actor_id, out, damage_applied=dot_applied, record=True)
        if not _can_act(actor):
            if intent_mode == "on" and frozen is not None:
                _it = _next_intent(actor_id)
                if _it is not None:
                    _frustrate(actor_id, _it, "incapaz")
            continue
        if stunned_this_turn:
            denied.add(actor_id)
            _note_denied_span(out, actor_id)
            out["logs"].append(f"{_name(actor)} está atordoado e perde o turno.")
            if intent_mode == "on" and frozen is not None:
                _it = _next_intent(actor_id)
                if _it is not None:
                    _frustrate(actor_id, _it, "atordoado")
            _expire_stat_conditions(actor, present_at_start, out)
            continue
        decl = declarations.get(actor_id)
        if decl is None:
            decl = _enemy_decl(actor_id, actor)
        if actor_id == player_id and _deck.deck_mode(state) == "on":
            _deck.resolve_player_plays(
                scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng
            )
        else:
            _resolve_actor_turn(scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng)
        _note_turn_records(_cond_before, actors_by_id, actor_id, out)
        _mark_fresh_conditions(
            _cond_before, actors_by_id, actor_id, sides, taunt_frozen_acted=_tf_acted()
        )
        _expire_stat_conditions(actor, present_at_start, out)

    _cond_before = _snapshot_conditions(actors_by_id)  # SPEC-339
    if _scene_ctx is not None:  # SPEC-331: fim de rodada da cena, antes do terminal
        _scene_mark = len(out["logs"])
        _sc.tick(_scene_ctx, _scene_rnd, "fim_rodada", out)
        _sc.clock_hard_stop(_scene_ctx, _scene_rnd, out)
        out.setdefault("scene_logs", []).extend(out["logs"][_scene_mark:])  # SPEC-346 R4

    # Última Ação acontece fora da ordem, exatamente uma vez, ANTES do terminal.
    _declared = {}
    if player_id and player_decl is not None:  # SPEC-346 R9: alvo DECLARADO, mesmo se caiu antes
        for _step in reversed(player_decl.plays()):
            if _step.target_id in sides.get("enemy", []):
                _declared[player_id] = _step.target_id
                break
    _resolve_last_stands(scene, actors_by_id, sides, out, rng, preferred_targets=_declared)
    _mark_fresh_conditions(_cond_before, actors_by_id, None, sides, taunt_frozen_acted=_tf_acted())

    # Estabilização do Estado Terminal disparado nesta rodada (07, R6=A).
    resolve_terminals(actors_by_id, sides, out, scene=scene, rng=rng)

    # Fim de rodada: colheita de Entropia por morte + Recidiva + Abismo (jogador).
    if player is not None:
        out["logs"] += cm.apply_entropy_on_kill(player, len(out["deaths"]))
        _rec_logs, rec_ev = cm.check_recidiva(player)
        out["logs"] += _rec_logs
        if rec_ev:
            out["recidiva_event"] = rec_ev
            _record_class_event(out, "consequence:recidiva")
        _maybe_abyss(
            scene, player, actors_by_id, prepared_abyss, out, scene_state=scene_state, rng=rng
        )

    for aid in sorted(actors_by_id):
        if _alive(actors_by_id[aid]):
            fx.fire("fim_rodada", sujeito_id=aid, out=out)
    if player is not None and _alive(player):
        _deck.end_round(fx.current(), state, player_id, out)  # SPEC-330: Guardar/Vazao

    # SPEC-332 P2-1/P2-2: fase de chefe no FIM da rodada (depois do dano), para o presságio da
    # rodada seguinte já nascer na fase nova; sem Presságio `on` o aviso da assinatura vai ao log.
    _edk_mod.apply_phases(actors_by_id, sides, out, cs.tactical_round(scene))
    if _edk_mod.active() and ei.mode() != "on":
        for _eid in sides.get("enemy", []):
            _en = actors_by_id.get(_eid)
            _warn = _edk_mod.prenuncio(_en, cs.tactical_round(scene)) if _alive(_en) else None
            if _warn:
                out["logs"].append(_warn)
    end = death_flow.combat_should_end({"hostiles": side_actors.get("enemy", [])})
    out["ended"] = end["ended"]
    out["reason"] = end["reason"]
    if _scene_ctx is not None and not out["player_dead"]:  # SPEC-331 R5: desfecho do Objetivo
        _why = _sc.check_objective(_scene_ctx, _scene_rnd)
        if _why:
            out["ended"], out["reason"] = True, _why
            out["objetivo"] = {
                "tipo": (scene.get("objetivo") or {}).get("tipo"),
                "resultado": scene.get("objetivo_resultado"),
            }
            out["logs"].append(_why)
    return out
