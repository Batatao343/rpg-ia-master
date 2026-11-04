"""SPEC-381 R18: golden de 404 das rotas que carregam o save (antes/depois de ``_load_or_404``).

Para cada rota: ``game_id`` inexistente de formato valido e ``game_id`` omitido sem save.
Compara status e corpo (sem ``request_id``) com ``docs/spec381/not_found_golden.json``.
``RPG_GOLDEN_UPDATE=1`` regrava o arquivo (so no commit que cria o golden, antes do helper).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

GOLDEN = Path(__file__).resolve().parents[1] / "docs" / "spec381" / "not_found_golden.json"
GID = "11111111-1111-4111-8111-111111111111"
OP = "22222222-2222-4222-8222-222222222222"
ACT = "33333333-3333-4333-8333-333333333333"

# (nome, metodo, path com {gid}, corpo com {gid} ou None, params de query)
CASES = [
    ("quote", "POST", "/game/{gid}/art/quote", {"image_type": "scene"}, None),
    (
        "confirm",
        "POST",
        "/game/{gid}/art/confirm",
        {"action_id": ACT, "quote_id": OP, "confirmed": True},
        None,
    ),
    ("art_status", "GET", "/game/{gid}/art/" + OP, None, None),
    ("art_quality", "POST", "/game/{gid}/art/" + OP + "/quality", {"approved": True}, None),
    ("turn_cost", "GET", "/game/{gid}/operations/" + OP + "/cost", None, None),
    ("operation_status", "GET", "/game/{gid}/operations/" + OP, None, None),
    ("equip", "POST", "/game/equip", {"game_id": "{gid}", "item_id": "x", "action_id": ACT}, None),
    (
        "cards_prepare",
        "POST",
        "/game/cards/prepare",
        {"game_id": "{gid}", "card_ids": [], "action_id": ACT},
        None,
    ),
    (
        "levelup",
        "POST",
        "/game/levelup",
        {"game_id": "{gid}", "action_id": ACT, "choice_id": "x"},
        None,
    ),
    ("espolio", "POST", "/game/espolio", {"game_id": "{gid}", "action_id": ACT}, None),
    (
        "loja_cartas",
        "POST",
        "/game/loja-cartas",
        {"game_id": "{gid}", "action_id": ACT, "card_id": "x"},
        None,
    ),
    ("game_map", "GET", "/game/map", None, {"game_id": "{gid}"}),
    ("world_map", "GET", "/data/map", None, {"game_id": "{gid}"}),
    ("state", "GET", "/game/state", None, {"game_id": "{gid}"}),
    (
        "preview",
        "POST",
        "/game/combat/preview",
        {"game_id": "{gid}", "card_id": "x", "target_id": "y"},
        None,
    ),
    ("codex", "GET", "/game/codex", None, {"game_id": "{gid}"}),
    ("dossiers", "GET", "/game/codex/dossiers", None, {"game_id": "{gid}"}),
    ("history", "GET", "/game/history", None, {"game_id": "{gid}"}),
    (
        "chron_search",
        "POST",
        "/game/chronicle/search",
        {"game_id": "{gid}", "query": "espada longa"},
        None,
    ),
    ("chron_export", "GET", "/game/chronicle/export", None, {"game_id": "{gid}"}),
    (
        "action",
        "POST",
        "/game/action",
        {"game_id": "{gid}", "input_text": "olho", "action_id": ACT},
        None,
    ),
    ("death", "POST", "/game/death", {"game_id": "{gid}", "choice": "continue"}, None),
    (
        "stream",
        "POST",
        "/game/action/stream",
        {"game_id": "{gid}", "input_text": "olho", "action_id": ACT},
        None,
    ),
]


def _fill(obj, gid):
    if isinstance(obj, str):
        return obj.replace("{gid}", gid)
    if isinstance(obj, dict):
        return {k: _fill(v, gid) for k, v in obj.items() if not (gid == "" and v == "{gid}")}
    if isinstance(obj, list):
        return [_fill(v, gid) for v in obj]
    return obj


def _collect(client: TestClient) -> dict:
    out: dict[str, dict] = {}
    for name, method, path, body, query in CASES:
        for label, gid in (("unknown", GID), ("omitted", "")):
            if gid == "" and "{gid}" in path:
                continue
            resp = client.request(
                method, _fill(path, gid), json=_fill(body, gid), params=_fill(query, gid)
            )
            try:
                payload = resp.json()
            except ValueError:
                payload = resp.text[:200]
            if isinstance(payload, dict):
                payload.pop("request_id", None)
            out[f"{name}:{label}"] = {"status": resp.status_code, "body": payload}
    return out


def test_not_found_golden():
    import api  # noqa: PLC0415

    api._rate_hits.clear()
    got = _collect(TestClient(api.app))
    if os.environ.get("RPG_GOLDEN_UPDATE") == "1":
        GOLDEN.write_bytes(
            (json.dumps(got, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        )
        pytest.skip("golden regravado")
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert got == want
