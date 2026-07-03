"""
graph_resolver.py — Consultas ao grafo de mundo (Fase 2.5).

Combina o grafo ESTÁTICO autoral (data/graph/) com o estado DINÂMICO da sessão
(`world_projection` do GameState): base_edges − disabled_edges + dynamic_edges.

Sem estado global mutável além dos caches de leitura; a projection sempre chega
por parâmetro (vem do GameState). Spec: specs/fase-2.5-codex-world-state.md §3.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

GRAPH_DIR = os.path.join("data", "graph")

_entities_cache: Optional[Dict[str, dict]] = None
_edges_cache: Optional[List[dict]] = None
_relation_types_cache: Optional[Dict[str, dict]] = None


def _read_json(filename: str, default):
    path = os.path.join(GRAPH_DIR, filename)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"⚠️ [GRAPH] Falha ao ler {path}: {exc}")
        return default


def load_entities() -> Dict[str, dict]:
    """Lookup canônico de entidades (cache em módulo).

    União de `entities.json` (gerado por migrate_lore_nova.py) com
    `entities_extra.json` (curadoria manual — sublocais do mapa, combatentes
    de fação; o script de migração NÃO toca nele). Em conflito de id, o
    canônico vence e o extra é ignorado.
    """
    global _entities_cache
    if _entities_cache is None:
        base = _read_json("entities.json", {})
        extra = _read_json("entities_extra.json", {})
        merged = dict(base)
        for eid, ent in extra.items():
            if eid in merged:
                print(f"⚠️ [GRAPH] entities_extra ignorado: id '{eid}' já existe no canônico.")
                continue
            merged[eid] = ent
        # Fase 2.7: overlay de componentes (migration-safe — migrate_lore_nova.py não toca).
        # Sobrepõe `components` na entidade sem apagar os demais campos. Chaves `_meta`/`_*`
        # são documentação, não entidades.
        components = _read_json("components.json", {})
        for eid, comps in components.items():
            if eid.startswith("_"):
                continue
            if eid not in merged:
                print(f"⚠️ [GRAPH] components.json ignorado: id '{eid}' não existe.")
                continue
            ent = dict(merged[eid])
            ent["components"] = {**(ent.get("components") or {}), **comps}
            merged[eid] = ent
        _entities_cache = merged
    return _entities_cache


def load_base_edges() -> List[dict]:
    global _edges_cache
    if _edges_cache is None:
        _edges_cache = _read_json("edges.json", [])
    return _edges_cache


def load_relation_types() -> Dict[str, dict]:
    global _relation_types_cache
    if _relation_types_cache is None:
        _relation_types_cache = _read_json("relation_types.json", {})
    return _relation_types_cache


def clear_cache() -> None:
    """Invalida os caches de leitura (testes / reload de dados)."""
    global _entities_cache, _edges_cache, _relation_types_cache
    _entities_cache = None
    _edges_cache = None
    _relation_types_cache = None


def get_entity(entity_id: str) -> Optional[dict]:
    return load_entities().get(entity_id)


def resolve_edges(projection: Optional[dict], *,
                  entity_id: Optional[str] = None,
                  edge_type: Optional[str] = None,
                  include_hidden: bool = False) -> List[dict]:
    """Edges efetivas AGORA: base − disabled + dynamic, com filtro de visibilidade.

    - `entity_id`: só edges onde a entidade é source ou target.
    - `edge_type`: só edges deste tipo de relação.
    - `include_hidden=False` omite edges `hidden`/`secret` (visão do jogador).
    """
    projection = projection or {}
    disabled_ids = {d.get("edge_id") for d in projection.get("disabled_edges", [])}

    effective: List[dict] = [
        e for e in load_base_edges() if e.get("id") not in disabled_ids
    ]
    effective.extend(projection.get("dynamic_edges", []))

    result: List[dict] = []
    for edge in effective:
        if not include_hidden and edge.get("visibility", "public") != "public":
            continue
        if edge_type and edge.get("type") != edge_type:
            continue
        if entity_id and entity_id not in (edge.get("source"), edge.get("target")):
            continue
        result.append(edge)
    return result


def get_current_controller(location_id: str, projection: Optional[dict],
                           include_hidden: bool = True) -> Optional[str]:
    """Quem controla o local AGORA. Dynamic edge vence base (é mais recente).

    Default (`include_hidden=True`) é a verdade do mundo, considera edges hidden/
    secret. Fase 3.4: `include_hidden=False` dá a visão do JOGADOR (HUD/mapa).
    """
    controls = resolve_edges(projection, edge_type="controls", include_hidden=include_hidden)
    controller = None
    for edge in controls:  # dynamic vem depois da base → última vence
        if edge.get("target") == location_id:
            controller = edge.get("source")
    return controller


def is_alive(entity_id: str, projection: Optional[dict]) -> bool:
    """Default True: entidade sem EntityState na projection está viva."""
    projection = projection or {}
    ent_state = projection.get("entities", {}).get(entity_id, {})
    return bool(ent_state.get("alive", True))
