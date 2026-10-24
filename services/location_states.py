"""SPEC-302 R16-R20: estados de local (leitura + escolha de alvo + recuperacao).

A FONTE DA VERDADE e `world_projection.location_states`, escrita so por
`event_processor.apply_event` (evento `location_state_changed`, source="engine").
Aqui so ha leitura (`location_state`, `location_effects`, `public_label`) e funcoes puras
que o motor usa para escolher o alvo de uma crise e decidir a recuperacao.
"""

from __future__ import annotations

from services import world_pressures as wp

STATES = ("cerco", "escassez", "praga", "ocupado", "ruina", "festa", "corrompido")
# crise -> estado de local (R16); `ascensao` nao cria estado novo.
CRISIS_STATE = {"guerra": "cerco", "fome": "escassez", "praga": "praga", "abismo": "corrompido"}
_NEUTRAL = {"price_mult": 1.0, "danger_delta": 0, "restock_mult": 1.0, "merchant_closed": False}


def _cfg() -> dict:
    return wp._load_json("location_states.json")


def _location(location_id: str) -> dict:
    return wp._map_index()[0].get(str(location_id or ""), {})


def _resolve_id(location_id: str) -> str:
    """Interior herda o estado do `parent_id` (R16)."""
    loc = _location(location_id)
    if loc.get("kind") == "interior" and loc.get("parent_id"):
        return str(loc["parent_id"])
    return str(location_id or "")


def location_state(state: dict, location_id: str) -> dict | None:
    """Linha `{state, severity, since_day, ...}` do local (ou do pai, se interior)."""
    rows = ((state or {}).get("world_projection") or {}).get("location_states") or {}
    row = rows.get(_resolve_id(location_id))
    return dict(row) if isinstance(row, dict) and row.get("state") else None


def location_effects(state: dict, location_id: str) -> dict:
    """`{price_mult, danger_delta, restock_mult, merchant_closed}`; neutro se o modo != on
    ou sem estado. Efeito por (estado, severidade) vem de `data/world/location_states.json`."""
    from services import world_engine

    if world_engine.mode() != "on":
        return dict(_NEUTRAL)
    row = location_state(state, location_id)
    spec = _cfg().get((row or {}).get("state", ""))
    if not row or not spec:
        return dict(_NEUTRAL)
    sev = max(1, min(3, int(row.get("severity", 1) or 1)))
    mults = spec.get("price_mult") or [1.0]
    danger = danger_delta(row, location_id)
    closed_at = spec.get("merchant_closed_at")
    out = {
        "price_mult": float(mults[min(sev, len(mults)) - 1]),
        "danger_delta": danger,
        "restock_mult": float(spec.get("restock_mult", 1.0)),
        "merchant_closed": bool(closed_at and sev >= int(closed_at)),
    }
    if row.get("state") == "festa" and row.get("festival_id"):
        # SPEC-303 R18: override por festival (preço/estoque/mercador); perigo nunca muda
        from services.world_calendar import festival_effects

        ov = festival_effects(str(row["festival_id"]))
        for key in ("price_mult", "restock_mult"):
            if key in ov:
                out[key] = float(ov[key])
        if "merchant_closed" in ov:
            out["merchant_closed"] = bool(ov["merchant_closed"])
    return out


def danger_delta(row: dict | None, location_id: str) -> int:
    """`danger_delta` do estado (0 em abrigo `seguro`: o early-game nao perde o descanso)."""
    spec = _cfg().get((row or {}).get("state", "")) or {}
    if "seguro" in (_location(_resolve_id(location_id)).get("tags") or []):
        return 0
    return int(spec.get("danger_delta", 0))


def public_label(row: dict | None) -> str:
    """Rotulo vago para a API (sem severidade numerica)."""
    if not row:
        return ""
    if row.get("state") == "festa" and row.get("festival_id"):
        from services.world_calendar import festival_label

        return festival_label(str(row["festival_id"])) or "em festa"
    return str((_cfg().get(row.get("state", "")) or {}).get("label", ""))


def blocks_route(state_name: str) -> bool:
    return bool((_cfg().get(state_name) or {}).get("blocks_route"))


# --- alvo da crise (R18) ----------------------------------------------------------


def _weight(kind: str, loc: dict) -> int:
    tags = set(loc.get("tags") or [])
    town = bool(tags & {"cidade", "abrigo", "comércio", "comercio", "urbano"})
    if kind == "guerra":
        return 3 if "cidade" in tags else (2 if town else 1)
    if kind == "fome":
        return 3 if loc.get("economy_tags") else 1
    if kind == "praga":
        return 3 if town else 1
    if kind == "abismo":
        return 0 if "cidade" in tags else 3
    return 1


def pick_crisis_target(region_id: str, kind: str, projection: dict, rng) -> str | None:
    """Local NAO-interior da regiao, por peso de tags; sem estado vigente. Desempate = rng."""
    rows = (projection or {}).get("location_states") or {}
    cands = sorted(
        lid
        for lid, loc in wp._map_index()[0].items()
        if loc.get("region_id") == region_id and loc.get("kind") != "interior"
    )
    roll = rng.random()  # sempre sorteia: o fluxo do rng nao depende dos candidatos
    # SPEC-303 R17: crise vence festa — um local em `festa` ainda e alvo valido da crise
    free = [lid for lid in cands if lid not in rows or (rows[lid] or {}).get("state") == "festa"]
    weights = {lid: _weight(kind, _location(lid)) for lid in free}
    pool = [lid for lid in free if weights[lid] > 0] or free
    if not pool:
        return None
    total = sum(max(1, weights[lid]) if weights[lid] <= 0 else weights[lid] for lid in pool)
    acc = 0.0
    target = roll * total
    for lid in pool:
        acc += weights[lid] if weights[lid] > 0 else 1
        if target < acc:
            return lid
    return pool[-1]
