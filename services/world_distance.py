"""SPEC-215 — distância em períodos entre dois locais do mapa (Dijkstra).

Reaproveita a regra de custo de `world_utils.travel_cost` (travel_times do nó
atual, fallback simétrico, interior = 0, sem entrada = 1). Puro e cacheado: o
mapa é imutável durante o jogo.
"""
from __future__ import annotations

import heapq
from functools import lru_cache
from typing import Dict, Optional

import gamedata


def _edge_cost(from_id: str, to_id: str) -> int:
    import world_utils
    return world_utils.travel_cost({"current_location_id": from_id},
                                   gamedata.get_location(to_id) or {"id": to_id})


@lru_cache(maxsize=64)
def _distances_from(from_id: str) -> dict[str, int]:
    dist: dict[str, int] = {from_id: 0}
    heap = [(0, from_id)]
    while heap:
        d, node = heapq.heappop(heap)
        if d > dist.get(node, d):
            continue
        for nxt in gamedata.get_connections(node):
            nid = nxt.get("id")
            if not nid:
                continue
            nd = d + _edge_cost(node, nid)
            if nd < dist.get(nid, 1 << 30):
                dist[nid] = nd
                heapq.heappush(heap, (nd, nid))
    return dist


def travel_periods(from_id: str, to_id: str) -> int | None:
    """Menor custo em períodos de `from_id` até `to_id`; None se inalcançável
    ou se algum dos ids não existe no mapa."""
    if not from_id or not to_id:
        return None
    if not gamedata.get_location(from_id) or not gamedata.get_location(to_id):
        return None
    return _distances_from(str(from_id)).get(str(to_id))


def reachable_within(from_id: str, radius: int) -> dict[str, int]:
    """Locais alcançáveis com custo ≤ radius (inclui o próprio)."""
    if not gamedata.get_location(from_id):
        return {}
    return {k: v for k, v in _distances_from(str(from_id)).items() if v <= radius}
