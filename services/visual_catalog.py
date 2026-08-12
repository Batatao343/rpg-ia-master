"""Catálogo público e gatilhos determinísticos da Fase 8A."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

import gamedata
from services.entity_identity import normalize_entity_label, resolve_npc_entity_id
from services.npc_layers import is_in_scene


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "visual_assets.json"
WEB_PUBLIC = ROOT / "web" / "public"
LEDGER_LIMIT = 64


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _cached_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def load_visual_catalog(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        return deepcopy(_cached_catalog())
    return json.loads(path.read_text(encoding="utf-8"))


def _asset_index() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (asset["subject_type"], asset["subject_id"]): asset
        for asset in _cached_catalog()["assets"]
    }


def _public_asset(asset: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not asset or asset.get("visibility") != "public":
        return None
    return {
        key: deepcopy(asset[key])
        for key in ("asset_id", "subject_type", "subject_id", "title", "alt",
                    "placeholder_color", "variants")
    }


def visual_for(subject_type: str, subject_id: str) -> Optional[dict[str, Any]]:
    return _public_asset(_asset_index().get((subject_type, subject_id)))


def creation_visuals() -> dict[str, dict[str, dict[str, Any]]]:
    catalog = _cached_catalog()
    return {
        "races": {
            subject_id: visual_for("race", subject_id)
            for subject_id in catalog["creation"]["races"]
        },
        "classes": {
            subject_id: visual_for("class", subject_id)
            for subject_id in catalog["creation"]["classes"]
        },
    }


def scene_visual(world: Mapping[str, Any]) -> dict[str, Any]:
    location_id = str(world.get("current_location_id") or "")
    location = gamedata.get_location(location_id) or {}
    name = str(location.get("name") or world.get("current_location") or location_id)
    asset = visual_for("location", location_id)
    scope = "exact"
    if asset is None:
        fallback_id = str(_cached_catalog().get("location_fallbacks", {}).get(location_id) or "")
        if fallback_id:
            asset = visual_for("location", fallback_id)
            scope = "regional"
        else:
            scope = "placeholder"
    return {"location_id": location_id, "location_name": name, "scope": scope,
            "asset": asset}


def _runtime_token(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", normalize_entity_label(name)).strip("_")
    return f"runtime_npc:{slug or 'desconhecido'}"


def _eligible_npcs(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, npc in (state.get("npcs") or {}).items():
        if not isinstance(npc, dict) or not npc.get("known_by_player", True) or not is_in_scene(npc):
            continue
        name = str(npc.get("name") or key)
        entity_id = resolve_npc_entity_id(npc, name)
        out.append({"key": str(key), "name": name, "npc": npc, "entity_id": entity_id,
                    "token": f"npc:{entity_id}" if entity_id else _runtime_token(name)})
    return out


def _cue_for(candidate: dict[str, Any]) -> dict[str, Any]:
    entity_id = candidate["entity_id"]
    asset = visual_for("npc", entity_id) if entity_id else None
    role = str(candidate["npc"].get("role") or "Personagem")
    return {
        "kind": "npc_first_appearance",
        "subject_id": entity_id or candidate["token"],
        "subject_name": candidate["name"],
        "caption": role,
        "asset_id": asset["asset_id"] if asset else None,
        "fallback": asset is None,
    }


def resolve_turn_visual_state(previous: Mapping[str, Any], current: Mapping[str, Any], *,
                              action_key: str) -> dict[str, Any]:
    seen = list(dict.fromkeys(str(v) for v in (current.get("visual_seen_entity_ids") or []) if v))
    seen_set = set(seen)
    previous_tokens = {row["token"] for row in _eligible_npcs(previous)}
    eligible = [row for row in _eligible_npcs(current) if row["token"] not in seen_set]
    active = normalize_entity_label(str(current.get("active_npc_name") or ""))

    chosen = next((row for row in eligible if active and normalize_entity_label(row["name"]) == active), None)
    if chosen is None:
        newly_present = [row for row in eligible if row["token"] not in previous_tokens]
        chosen = sorted(newly_present, key=lambda row: (row["entity_id"] or row["token"]))[0] \
            if newly_present else None
    cue = _cue_for(chosen) if chosen else None
    if chosen:
        seen.append(chosen["token"])
    ledger = [row for row in (current.get("visual_cue_ledger") or [])
              if isinstance(row, dict) and row.get("action_key") != action_key]
    ledger.append({"action_key": action_key, "cue": cue})
    return {"visual_seen_entity_ids": seen[-LEDGER_LIMIT:],
            "visual_cue_ledger": ledger[-LEDGER_LIMIT:]}


def visual_response(state: Mapping[str, Any], *, cue_action_key: str | None) -> dict[str, Any]:
    cue = None
    if cue_action_key:
        record = next((row for row in reversed(state.get("visual_cue_ledger") or [])
                       if isinstance(row, dict) and row.get("action_key") == cue_action_key), None)
        stored = deepcopy(record.get("cue")) if record else None
        if stored:
            stored["asset"] = visual_for("npc", stored.get("subject_id", ""))
            stored.pop("asset_id", None)
            cue = stored
    return {"scene": scene_visual(state.get("world") or {}), "cue": cue}
