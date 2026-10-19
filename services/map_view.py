"""SPEC-210 - view de mapa com fog SERVER-SIDE (funcoes puras, sem FastAPI).

O cliente so recebe o que o jogador descobriu: locais visitados (completos) e
adjacentes ao local atual (id/coords/nome - a "placa da estrada"). Nada de
nome/perigo/lore/arte de local nao alcancado. Estado derivado do servidor.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

import gamedata
import world_utils
from services import state_views as sv
from services.visual_catalog import location_visual

NO_DIRECT_ROUTE = "Sem rota direta daqui."
BLOCKED_REASON = "Rota bloqueada."


def interiors_block(loc_id: str) -> dict[str, Any]:
    """Interiores do local atual ("Locais daqui") + caminho de volta ao pai."""
    loc = gamedata.get_location(loc_id) or {}
    here = [
        {"id": i["id"], "name": i["name"], "danger": i.get("danger", 0),
         "tags": i.get("tags", [])}
        for i in gamedata.interiors_of(loc_id)
    ]
    exit_to = None
    if loc.get("kind") == "interior":
        parent = gamedata.get_location(loc.get("parent_id", "")) or {}
        if parent:
            exit_to = {"id": parent["id"], "name": parent["name"]}
    return {"here": here, "exit_to": exit_to}


def _blocked_pairs(projection: dict | None) -> set:
    return {frozenset((r.get("a", ""), r.get("b", "")))
            for r in (projection or {}).get("blocked_routes", []) or []}


def travel_gate(state: dict) -> dict[str, Any]:
    """R7: motivo (pt-BR) pelo qual 'Viajar' fica desabilitado; o backend segue
    sendo a autoridade (_combat_gate converte viagem em fuga)."""
    if state.get("archived"):
        return {"blocked": True, "reason": "Esta saga foi arquivada."}
    if state.get("game_over"):
        return {"blocked": True, "reason": "A saga terminou."}
    if state.get("death_pending"):
        return {"blocked": True, "reason": "Queda pendente: resolva a morte antes de viajar."}
    if (state.get("combat") or {}).get("active") or (state.get("combat_simulation") or {}).get("enabled"):
        return {"blocked": True, "reason": "Em combate: fuga é uma ação do encontro."}
    return {"blocked": False, "reason": ""}


def _anchor_id(world: dict) -> str:
    cur = world.get("current_location_id", "") or ""
    loc = gamedata.get_location(cur) or {}
    if loc.get("kind") == "interior" and loc.get("parent_id"):
        return loc["parent_id"]
    return cur


def _travel_options(world: dict, blocked: set) -> list[dict[str, Any]]:
    cur = world.get("current_location_id", "") or ""
    dests = list(gamedata.get_connections(cur))
    loc = gamedata.get_location(cur) or {}
    parent = gamedata.get_location(loc.get("parent_id", "")) if loc.get("kind") == "interior" else None
    if parent and all(d["id"] != parent["id"] for d in dests):
        dests.append(parent)
    out = []
    for d in dests:
        is_blocked = frozenset((cur, d["id"])) in blocked
        out.append({"location_id": d["id"], "name": d["name"],
                    "periods": world_utils.travel_cost(world, d),
                    "reachable": not is_blocked, "blocked": is_blocked,
                    "reason": BLOCKED_REASON if is_blocked else ""})
    return out


def build_map_view(state: dict) -> dict[str, Any]:
    world = dict(state.get("world") or {})
    projection = state.get("world_projection") or {}
    blocked = _blocked_pairs(projection)
    cur = world.get("current_location_id", "") or ""
    anchor = _anchor_id(world)
    visited = [v for v in (world.get("visited") or []) if v]
    turn = int(world.get("turn_count", 0) or 0)

    options = _travel_options(world, blocked)
    opt_by_id = {o["location_id"]: o for o in options}

    controllers = sv.visible_controllers(world, projection)
    threats = {t["region_id"]: t["hint"] for t in sv.active_threats(world, turn)}
    contested = {c["location_id"] for c in sv.recent_control_changes(
        state.get("event_log") or [], visited, turn)}
    quest_targets = {q.get("location_id") for q in (state.get("quests") or [])
                     if isinstance(q, dict) and q.get("status") == "active" and q.get("location_id")}

    # Conjunto enviado: visitados (nao-interior) + adjacentes (connections da ancora).
    sent: dict[str, str] = {}
    for vid in visited:
        loc = gamedata.get_location(vid) or {}
        if loc and loc.get("kind") != "interior":
            sent[vid] = "visited"
    if anchor:
        sent[anchor] = "visited"
        for c in gamedata.get_connections(anchor):
            if c.get("kind") != "interior":
                sent.setdefault(c["id"], "adjacent")

    nodes: list[dict[str, Any]] = []
    for lid, kind in sent.items():
        loc = gamedata.get_location(lid) or {}
        if not loc:
            continue
        is_cur = lid == anchor
        is_blocked = (not is_cur) and frozenset((cur, lid)) in blocked
        if is_cur:
            st = "atual"
        elif is_blocked:
            st = "bloqueado"
        elif kind == "visited":
            st = "visitado"
        else:
            st = "adjacente"
        node: dict[str, Any] = {"id": lid, "state": st, "name": loc.get("name", lid),
                                "coords": dict(loc.get("coords") or {"x": 50, "y": 50})}
        if not is_cur:
            opt = opt_by_id.get(lid)
            node["reachable"] = bool(opt and opt["reachable"])
            if not node["reachable"]:
                node["reason"] = (opt or {}).get("reason") or NO_DIRECT_ROUTE
        if kind == "visited":
            node["region_id"] = loc.get("region_id", "")
            node["danger"] = world_utils._effective_danger(world, lid)
            node["lore_seed"] = loc.get("lore_seed", "")
            node["art"] = location_visual(lid)
            if lid in controllers:
                node["ruler"] = controllers[lid]
            if lid in quest_targets:
                node["quest_target"] = True
            hint = threats.get(loc.get("region_id", ""))
            if hint:
                node["threatened"] = True
                node["threat_hint"] = hint
            if lid in contested:
                node["contested"] = True
        nodes.append(node)

    ids = {n["id"] for n in nodes}
    edges = []
    for lid in ids:
        for c in (gamedata.get_location(lid) or {}).get("connections", []):
            if c in ids and lid < c:
                edges.append({"a": lid, "b": c, "blocked": frozenset((lid, c)) in blocked})
    edges.sort(key=lambda e: (e["a"], e["b"]))
    nodes.sort(key=lambda n: n["id"])

    view: dict[str, Any] = {
        "game_id": state.get("game_id", ""),
        "turn_count": turn,
        "current_id": cur,
        "anchor_id": anchor,
        "nodes": nodes,
        "edges": edges,
        "interiors": interiors_block(cur),
        "travel_options": options,
        "travel_gate": travel_gate(state),
        "looming_threat": world.get("looming_threat", "") or "",
    }
    # map_version: hash estavel do conteudo visivel (sem o turno, que muda sozinho).
    stable = {k: v for k, v in view.items() if k != "turn_count"}
    view["map_version"] = hashlib.sha256(json.dumps(
        stable, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]
    return view


def legacy_filtered_map(state: dict) -> dict[str, Any]:
    """`GET /data/map?game_id=`: mesmo formato legado, so com os nos da view
    (adjacentes sem lore/perigo/conexoes). Sem game_id o endpoint global segue
    igual (CLI/smoke)."""
    view = build_map_view(state)
    sent = {n["id"]: n for n in view["nodes"]}
    locations = []
    for lid, n in sent.items():
        if "lore_seed" not in n:
            locations.append({"id": lid, "name": n["name"], "region": "", "region_id": "",
                              "coords": n["coords"], "danger": 0, "tags": [],
                              "connections": [], "lore_seed": ""})
        else:
            # Whitelist (revisao Sol): o JSON cru tem `treasure` (bau curado) e
            # `travel_times` citando IDs de locais nao alcancados - nunca saem.
            raw = gamedata.get_location(lid) or {}
            locations.append({
                "id": lid, "name": n["name"], "region": raw.get("region", ""),
                "region_id": n.get("region_id", ""), "coords": n["coords"],
                "danger": n.get("danger", 0), "tags": list(raw.get("tags") or []),
                "connections": [c for c in raw.get("connections", []) if c in sent],
                "lore_seed": n.get("lore_seed", ""),
            })
    return {"start_location": view["anchor_id"], "locations": locations}
