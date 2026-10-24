"""SPEC-299 — Códigos de lei por jurisdição (dado curado em ``data/law_codes.json``).

Loader com cache, consulta ``location_id -> código`` e lint. Local ausente do mapa
de jurisdições = SEM LEI. Arquivo ausente/inválido = lei inerte (loga uma vez).
Puro: sem LLM e sem estado de jogo.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("rpg.law")
_ROOT = Path(__file__).resolve().parent.parent
LAW_CODES_PATH = _ROOT / "data" / "law_codes.json"
BESTIARY_PATH = _ROOT / "data" / "bestiary.json"

# R5: catálogo fechado. O LLM só pode propor os cinco primeiros; o resto é do motor.
CRIME_TYPES = (
    "furto",
    "agressao",
    "homicidio",
    "dano_propriedade",
    "magia_ilegal",
    "resistencia",
    "evasao",
)
LLM_CRIME_TYPES = CRIME_TYPES[:5]

_EMPTY: dict[str, Any] = {"jurisdictions": {}, "codes": {}}


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _merge_code(code_id: str, raw: dict, defaults: dict) -> dict:
    code = deepcopy(defaults)
    for key, value in raw.items():
        if key == "crimes":
            continue
        code[key] = deepcopy(value)
    crimes: dict[str, dict] = {}
    for ctype, row in (raw.get("crimes") or {}).items():
        if isinstance(row, dict):
            crimes[ctype] = dict(row)
    code["crimes"] = crimes
    code["id"] = code_id
    return code


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    data = _read(LAW_CODES_PATH)
    if data is None or not isinstance(data.get("codes"), dict):
        _LOG.warning("law_codes.json ausente ou inválido: a lei fica inerte")
        return _EMPTY
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    codes = {
        cid: _merge_code(cid, raw, defaults)
        for cid, raw in data["codes"].items()
        if isinstance(raw, dict)
    }
    jur = {
        str(loc): str(cid) for loc, cid in (data.get("jurisdictions") or {}).items() if cid in codes
    }
    return {"jurisdictions": jur, "codes": codes}


def bestiary_name(enemy_id: str) -> str:
    data = _read(BESTIARY_PATH) or {}
    return str((data.get(enemy_id) or {}).get("name") or enemy_id)


def reload() -> None:
    """Limpa o cache (testes e troca de arquivo)."""
    _load.cache_clear()


def get_code(code_id: str) -> dict | None:
    return (_load()["codes"]).get(str(code_id or ""))


def code_for_location(location_id: str) -> dict | None:
    cid = (_load()["jurisdictions"]).get(str(location_id or ""))
    return get_code(cid) if cid else None


def jurisdiction_locations(code_id: str) -> list[str]:
    return [loc for loc, cid in _load()["jurisdictions"].items() if cid == code_id]


def crime_row(code: dict, crime_type: str) -> dict | None:
    """Linha do crime no código, ou None se ausente/desabilitada."""
    row = (code.get("crimes") or {}).get(crime_type)
    if not isinstance(row, dict) or row.get("enabled") is False:
        return None
    return row


def is_active() -> bool:
    return bool(_load()["codes"])


def lint_law_codes(data: dict | None = None) -> list[str]:
    """R1: problemas do dado curado (vazio = ok)."""
    import gamedata
    from services import graph_resolver as gr

    if data is None:
        data = _read(LAW_CODES_PATH)
    if data is None:
        return ["data/law_codes.json ausente ou inválido"]
    problems: list[str] = []
    codes = data.get("codes")
    if not isinstance(codes, dict) or not codes:
        return ["'codes' ausente ou vazio"]
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    jur = data.get("jurisdictions") or {}
    merged = {
        cid: _merge_code(cid, raw, defaults) for cid, raw in codes.items() if isinstance(raw, dict)
    }
    for loc, cid in jur.items():
        if not gamedata.get_location(loc):
            problems.append(f"jurisdição: local inexistente no mapa: {loc}")
        if cid not in merged:
            problems.append(f"jurisdição {loc}: código desconhecido {cid}")
    bestiary = _read(BESTIARY_PATH) or {}
    for cid, code in merged.items():
        fid = str(code.get("authority_faction_id") or "")
        ent = gr.get_entity(fid) if fid else None
        if not ent or ent.get("type") != "faction":
            problems.append(f"{cid}: authority_faction_id não é fação: {fid!r}")
        for pool in ("guard_pool", "hunter_pool"):
            for eid in code.get(pool) or []:
                if eid not in bestiary:
                    problems.append(f"{cid}: {pool} com id fora do bestiário: {eid}")
        prison = code.get("prison_location_id")
        if prison and jur.get(prison) != cid:
            problems.append(f"{cid}: prison_location_id {prison} fora da própria jurisdição")
        for ctype in code["crimes"]:
            if ctype not in CRIME_TYPES:
                problems.append(f"{cid}: tipo de crime fora do catálogo: {ctype}")
        for ctype in CRIME_TYPES:
            if ctype not in code["crimes"]:
                problems.append(f"{cid}: crime sem linha: {ctype}")
        for vf in code.get("victim_multiplier") or {}:
            ent = gr.get_entity(vf)
            if not ent or ent.get("type") != "faction":
                problems.append(f"{cid}: victim_multiplier com fação inexistente: {vf}")
        if code.get("punishment") not in ("prisao", "multa", "expulsao"):
            problems.append(f"{cid}: punishment inválido: {code.get('punishment')!r}")
    return problems
