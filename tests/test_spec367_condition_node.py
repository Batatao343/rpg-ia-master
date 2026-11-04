"""SPEC-367 R14: condição de inimigo que termina, pela API de combate real (registro, mech_log, mensagem, Livro)."""

from __future__ import annotations

import re

from services import conflict_orchestrator as orch
from tests import spec364_board_helpers as hp

RAW = re.compile(r"^[^:\n|]+: \w+ terminou", re.M)


def test_enemy_condition_end_on_every_surface(monkeypatch):
    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    enemy_name = next(e["name"] for e in st["enemies"] if not e.get("dead"))
    cards = hp.hand_attack_cards(client, gid, saved)
    assert cards, "mao sem Carta de ataque jogavel"
    target = next(e["id"] for e in st["enemies"] if not e.get("dead"))
    real = orch.run_round

    def run(*a, **k):
        out = real(*a, **k)
        out["logs"] = [*(out.get("logs") or []), f"{enemy_name}: cego terminou."]
        return out

    monkeypatch.setattr(orch, "run_round", run)
    r = client.post(
        "/game/action",
        json={
            "game_id": gid,
            "input_text": "Jogo",
            "jogadas": [{"card_id": cards[0]["id"], "target_id": target}],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    hist = client.get("/game/history", params={"game_id": gid}).json()["entries"]
    combat = body["combat"]
    phrase = f"A condição Cego de {enemy_name} terminou."
    surfaces = {
        "mech_log": " | ".join(combat.get("mech_log") or []),
        "registro": " | ".join(str(x) for x in combat.get("registro_rodada") or []),
        "mensagem": body["message"],
        "livro": "\n".join(str(e.get("text") or "") for e in hist),
    }
    for name, blob in surfaces.items():
        assert ": cego terminou" not in blob, name
        assert not RAW.search(blob), name
    assert any(phrase in b for b in surfaces.values()), surfaces
    for name, blob in surfaces.items():
        assert blob.count(phrase) <= 1, (name, blob.count(phrase))
