"""
rule_engine.py — Regras sistêmicas declarativas (Fase 2.7).

Fecha a lacuna da 2.6: `npc_killed` só marcava `alive=False`. Aqui, a morte de um
líder/governante dispara a CONSEQUÊNCIA (fação desestabiliza → controle do local muda →
rival ocupa) — de forma GENÉRICA: tags + `components` + regras de `data/graph/world_rules.json`.
Zero `if npc_id == "..."`. Determinístico, sem LLM.

Segurança: sem `eval`/`exec`. Valores dinâmicos das regras vêm SÓ de `resolve_path`, um
resolvedor de paths whitelisted (literais JSON, `event.<campo>`, `target.<campo>`,
`component:<comp>.<campo>[N]`). Qualquer outra string → `RuleActionError`.

Modelo HÍBRIDO (decisão da fase): a estrutura (quem lidera/controla/é rival) é DERIVADA dos
edges do grafo (`leads`/`controls`/`enemy_of`/`operates_in`); o componente
`power_vacuum_trigger` só carrega o que edge não tem (delta de instabilidade, sucessor,
override de rival). O componente é também o DISCRIMINADOR da regra de líder.

Cascata: `run_rules` é dono da cascata — aplica os eventos derivados na projection e recursa
até profundidade 2 (anti-loop). O `event_processor` só anexa os derivados ao `event_log`
(não re-aplica). `apply_event` continua sendo o único tradutor evento→projection.

Spec: specs/fase-2.7-rules-engine.md.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from services import graph_resolver as gr

RULES_PATH = os.path.join("data", "graph", "world_rules.json")

_rules_cache: Optional[List[dict]] = None

# Sufixo de índice numérico no fim de um path: "...rival_factions[0]"
_INDEX_RE = re.compile(r"^(.*)\[(\d+)\]$")


class RuleActionError(Exception):
    """Regra malformada / op fora da whitelist / path proibido. Nunca quebra o turno:
    o `event_processor`/`run_rules` captura e descarta a regra com log."""


# --- resolvedor seguro de paths --------------------------------------------

def _walk(root: Any, dotted: str) -> Any:
    """Desce por chaves de dict separadas por ponto, com sufixo opcional [N].

    Só acesso a item de dict/lista — nunca getattr. Dunder já barrado antes.
    """
    value = root
    for raw in dotted.split("."):
        m = _INDEX_RE.match(raw)
        key, index = (m.group(1), int(m.group(2))) if m else (raw, None)
        if not isinstance(value, dict) or key not in value:
            raise RuleActionError(f"path não resolvível: chave {key!r} ausente")
        value = value[key]
        if index is not None:
            if not isinstance(value, (list, tuple)) or index >= len(value):
                raise RuleActionError(f"path não resolvível: índice [{index}] fora de {key!r}")
            value = value[index]
    return value


def resolve_path(expr: Any, ctx: dict) -> Any:
    """Resolve um valor de argumento de regra contra `ctx`.

    ctx = {"event": GameEvent, "target": entity_dict, "component": components_dict}

    Aceita SOMENTE:
      - literais JSON (não-string): bool/int/float/list/dict/None → devolve como está.
      - "event.<campo...>"        → ctx["event"][...]
      - "target.<campo...>"       → ctx["target"][...]
      - "component:<comp>.<campo...>[N]" → ctx["component"][comp][...]
    Qualquer outra string (ex.: "__import__('os')", "event.__class__") → RuleActionError.
    """
    if not isinstance(expr, str):
        return expr
    if "__" in expr:
        raise RuleActionError(f"expressão proibida (dunder): {expr!r}")

    if expr.startswith("event."):
        return _walk(ctx.get("event") or {}, expr[len("event."):])
    if expr.startswith("target."):
        return _walk(ctx.get("target") or {}, expr[len("target."):])
    if expr.startswith("component:"):
        return _walk(ctx.get("component") or {}, expr[len("component:"):])

    raise RuleActionError(f"expressão não permitida: {expr!r}")


# --- conditions -------------------------------------------------------------

def check_conditions(rule: dict, event: dict, projection: dict,
                     state: Optional[dict] = None) -> bool:
    """True se TODAS as conditions da regra passarem (AND). Regra sem conditions → True.

    Suporta: target_has_component | target_missing_component | target_has_tag |
             event_payload_equals {"key":..., "value":...} |
             target_map_tag (Fase 6.1: tag/economy_tag do NÓ do world_map) |
             new_controller_hostile (Fase 6.1: disposition da fação do payload).
    Condition de tipo desconhecido → False (regra não casa; conservador).
    """
    target = gr.get_entity(event.get("target_id")) or {}
    components = target.get("components", {}) or {}
    tags = target.get("tags", []) or []
    payload = event.get("payload", {}) or {}

    for cond in rule.get("conditions", []) or []:
        if "target_map_tag" in cond:
            from gamedata import get_location
            loc = get_location(event.get("target_id", "")) or {}
            loc_tags = set(loc.get("tags") or []) | set(loc.get("economy_tags") or [])
            if cond["target_map_tag"] not in loc_tags:
                return False
            continue
        if "new_controller_hostile" in cond:
            fid = payload.get("new_controller_id")
            disp = next((f.get("disposition") for f in (state or {}).get("factions", []) or []
                         if f.get("id") == fid), None)
            if (disp == "hostil") != bool(cond["new_controller_hostile"]):
                return False
            continue
        if "target_has_component" in cond:
            if cond["target_has_component"] not in components:
                return False
        elif "target_missing_component" in cond:
            if cond["target_missing_component"] in components:
                return False
        elif "target_has_tag" in cond:
            if cond["target_has_tag"] not in tags:
                return False
        elif "event_payload_equals" in cond:
            spec = cond["event_payload_equals"] or {}
            if payload.get(spec.get("key")) != spec.get("value"):
                return False
        else:
            return False
    return True


# --- carga de regras --------------------------------------------------------

def load_rules() -> List[dict]:
    """Lê world_rules.json (cache em módulo). Ausente/ilegível → []."""
    global _rules_cache
    if _rules_cache is None:
        if not os.path.exists(RULES_PATH):
            _rules_cache = []
        else:
            try:
                with open(RULES_PATH, "r", encoding="utf-8") as f:
                    _rules_cache = json.load(f)
            except Exception as exc:
                print(f"⚠️ [RULE] Falha ao ler {RULES_PATH}: {exc}")
                _rules_cache = []
    return _rules_cache


# --- derivações a partir dos edges (modelo híbrido) -------------------------

_PATH_PREFIXES = ("event.", "target.", "component:")


def _arg(value: Any, ctx: dict) -> Any:
    """Resolve arg de op: string path-like → resolve_path; senão literal (inclui id/campo)."""
    if isinstance(value, str) and value.startswith(_PATH_PREFIXES):
        return resolve_path(value, ctx)
    return value


def _led_faction(npc_id: str, proj: dict) -> Optional[str]:
    """Fação liderada pelo NPC (edge `leads`), ou None."""
    for e in gr.resolve_edges(proj, entity_id=npc_id, edge_type="leads", include_hidden=True):
        if e.get("source") == npc_id:
            return e.get("target")
    return None


def _controlled_locations(npc_id: str, proj: dict) -> List[str]:
    """Locais controlados pelo NPC morto E pela fação que ele lidera (edges `controls`)."""
    sources = {npc_id}
    led = _led_faction(npc_id, proj)
    if led:
        sources.add(led)
    locs: List[str] = []
    for e in gr.resolve_edges(proj, edge_type="controls", include_hidden=True):
        if e.get("source") in sources and e.get("target") not in locs:
            locs.append(e.get("target"))
    return locs


def _rival_faction(location: str, dead_faction: Optional[str], component: dict,
                   proj: dict) -> Optional[str]:
    """Quem ocupa o vácuo: override do componente → 1º enemy_of da fação → 1ª outra
    fação com operates_in no local. None se nada aplicável."""
    override = (component.get("power_vacuum_trigger") or {}).get("rival_faction_override")
    if override:
        return override
    if dead_faction:
        for e in gr.resolve_edges(proj, entity_id=dead_faction, edge_type="enemy_of",
                                  include_hidden=True):
            other = e.get("target") if e.get("source") == dead_faction else e.get("source")
            if other and gr.is_alive(other, proj):
                return other
    for e in gr.resolve_edges(proj, edge_type="operates_in", include_hidden=True):
        if e.get("target") == location and e.get("source") != dead_faction \
                and gr.is_alive(e.get("source"), proj):
            return e.get("source")
    return None


# --- execução de ações ------------------------------------------------------

def _clamp(v: int, lo: int = -100, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def _adjust_stability(proj: dict, state: dict, faction: str, delta: int) -> None:
    entities = proj.setdefault("entities", {})
    if "stability" in entities.get(faction, {}):
        cur = int(entities[faction]["stability"])
    else:  # semeia da Fase 2 (state.factions) se a projection ainda não tem
        cur = next((int(f.get("stability", 0)) for f in state.get("factions") or []
                    if f.get("id") == faction), 0)
    new = _clamp(cur + int(delta))
    entities[faction] = {**entities.get(faction, {}), "stability": new}
    # Espelha em state.factions se a fação existir lá (compat Fase 2).
    for f in state.get("factions") or []:
        if f.get("id") == faction:
            f["stability"] = new
            break


def _new_event(etype: str, target_id: str, payload: dict, actor_id: str) -> dict:
    return {
        "event_id": uuid.uuid4().hex,
        "turn": 0,
        "type": etype,
        "actor_id": actor_id,
        "target_id": target_id,
        "payload": payload,
        "source": "rule_engine",
    }


def execute_action(action: dict, event: dict, state: dict) -> List[dict]:
    """Executa UMA ação. Ops diretas mutam state['world_projection'] in place;
    `emit_event` RETORNA os GameEvents derivados (source='rule_engine'). Demais → [].

    Op fora da whitelist → RuleActionError (a regra é ignorada com log em run_rules)."""
    op = action.get("op")
    proj = state.setdefault("world_projection", {})
    target_id = event.get("target_id")
    target_ent = gr.get_entity(target_id) or {}
    component = target_ent.get("components", {}) or {}
    ctx = {"event": event, "target": target_ent, "component": component}

    if op == "set_entity_state":
        ref = action.get("entity", "target")
        eid = target_id if ref == "target" else (event.get("actor_id") if ref == "actor" else ref)
        field = action.get("field")
        value = _arg(action.get("value"), ctx)
        entities = proj.setdefault("entities", {})
        entities[eid] = {**entities.get(eid, {}), field: value}
        return []

    if op == "adjust_faction_stability":
        if "faction" in action:
            faction = _arg(action["faction"], ctx)
        else:
            faction = _led_faction(target_id, proj)
        if not faction:
            return []
        delta = _arg(action.get("delta", 0), ctx)
        _adjust_stability(proj, state, faction, delta)
        return []

    if op == "disable_controls_edges":
        sources = {target_id}
        led = _led_faction(target_id, proj)
        if led:
            sources.add(led)
        for e in gr.resolve_edges(proj, edge_type="controls", include_hidden=True):
            if e.get("source") in sources and e.get("id"):
                proj.setdefault("disabled_edges", []).append(
                    {"edge_id": e["id"], "disabled_by_event": event.get("event_id", "")})
        return []

    if op == "create_dynamic_edge":
        proj.setdefault("dynamic_edges", []).append({
            "id": f"dyn_rule_{uuid.uuid4().hex[:8]}",
            "source": _arg(action.get("source"), ctx),
            "type": _arg(action.get("type"), ctx),
            "target": _arg(action.get("target"), ctx),
            "created_by_event": event.get("event_id", ""),
        })
        return []

    if op == "emit_event":
        etype = action.get("type")
        targets_spec = action.get("targets")
        if targets_spec == "map_connections":
            # Fase 6.1: um evento por CONEXÃO do local-alvo (ex.: porto tomado
            # bloqueia todas as rotas dele). Par já bloqueado é pulado.
            from gamedata import get_location
            blocked = {frozenset((r.get("a"), r.get("b")))
                       for r in proj.get("blocked_routes", []) or []}
            derived = []
            for conn in (get_location(target_id) or {}).get("connections", []) or []:
                if frozenset((target_id, conn)) in blocked:
                    continue
                derived.append(_new_event(
                    etype, target_id, {"other_location_id": conn},
                    actor_id=event.get("actor_id", "player")))
            return derived
        if targets_spec == "controlled_locations":
            dead_faction = _led_faction(target_id, proj)
            derived = []
            for loc in _controlled_locations(target_id, proj):
                rival = _rival_faction(loc, dead_faction, component, proj)
                if not rival:
                    continue
                derived.append(_new_event(
                    etype, loc, {"new_controller_id": rival}, actor_id=target_id))
            return derived
        # targets explícito (lista ou path) — payload comum
        targets = _arg(targets_spec, ctx)
        if isinstance(targets, str):
            targets = [targets]
        payload = {k: _arg(v, ctx) for k, v in (action.get("payload") or {}).items()}
        return [_new_event(etype, t, dict(payload), actor_id=event.get("actor_id", "player"))
                for t in (targets or [])]

    raise RuleActionError(f"op desconhecida: {op!r}")


# --- orquestração da cascata ------------------------------------------------

def run_rules(event: dict, state: dict, depth: int = 0) -> List[dict]:
    """Dispara as regras casadas por `event`, aplica os derivados na projection e recursa
    até profundidade 2 (anti-loop). Devolve a lista PLANA de eventos derivados
    (source='rule_engine') para o event_processor anexar ao event_log.

    Regra com op inválida / path proibido → ignorada com log (turno não quebra)."""
    if depth >= 2:
        return []
    from services.event_processor import apply_event  # lazy: evita import circular

    state.setdefault("world_projection", {})
    derived_all: List[dict] = []

    for rule in load_rules():
        if rule.get("trigger") != event.get("type"):
            continue
        if not check_conditions(rule, event, state["world_projection"], state):
            continue
        try:
            emitted: List[dict] = []
            for action in rule.get("actions", []) or []:
                emitted += execute_action(action, event, state)
        except RuleActionError as exc:
            print(f"⚠️ [RULE] '{rule.get('id')}' ignorada: {exc}")
            continue
        for d in emitted:
            state["world_projection"] = apply_event(d, state["world_projection"])
            derived_all.append(d)
            derived_all += run_rules(d, state, depth + 1)

    return derived_all
