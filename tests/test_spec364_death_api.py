"""SPEC-364 R21 / P2-4: morte do heroi "Smoke4A" (nome com digito) PONTA A PONTA pela API.

Estado semeado (heroi em Estado Terminal, um inimigo caido numa rodada anterior); o unico seam e a
estabilizacao (`death_flow.attempt_stabilization` -> morte), porque o teste de sobrevivencia e sorteio."""

from __future__ import annotations

import random
from copy import deepcopy

import pytest

import agents.combat as combat
from tests import spec364_board_helpers as hp

HERO = "Smoke4A"
GOOD_LLM = "Você tomba diante do Goblin. O Goblin B, que já tinha tombado, jaz ao seu lado."
BAD_LLM = (
    "Smoke4A cai. O Goblin B também tomba sem vida ao seu lado."  # V6: queda antiga no presente
)


def _die(monkeypatch, llm_text: str):
    """Rodada 1: o herói derruba o Goblin B (semente buscada); rodada 2: o herói morre (seam de estabilização)."""
    from services import death_flow

    client, saved, gid = hp.api_client(monkeypatch, hero=HERO)
    st = hp.open_combat(client, saved, gid)
    other = hp.add_second_enemy(st)
    for e in st["enemies"]:
        if e["id"] == other:
            e.update(vitalidade=1, hp=1)
    st["player"]["vitalidade"] = max(int(st["player"].get("vitalidade", 18) or 18), 12)
    saved[gid] = deepcopy(st)
    fell = False
    for seed in range(60):
        snapshot = deepcopy(saved[gid])
        random.seed(seed)
        r = client.post(
            "/game/action",
            json={
                "game_id": gid,
                "input_text": "Ataco",
                "action_kind": "attack",
                "target_id": other,
            },
        )
        assert r.status_code == 200, r.text
        now = saved[gid]
        goblin_b = next((e for e in now["enemies"] if e["id"] == other), None)
        if (
            (goblin_b is None or goblin_b.get("dead"))
            and (now.get("combat") or {}).get("active")
            and not now.get("death_pending")
        ):
            fell = True
            break
        saved[gid] = snapshot
    assert fell, "nenhuma semente derrubou o Goblin B na rodada 1"
    st2 = deepcopy(saved[gid])
    st2["player"]["vitalidade"] = 0
    st2["player"]["estado_terminal"] = True
    saved[gid] = st2
    monkeypatch.setattr(
        death_flow,
        "attempt_stabilization",
        lambda *a, **k: {"dead": True, "log": "Você não resiste.", "revived": False},
    )
    monkeypatch.setattr(combat, "_fast_text", lambda *a, **k: llm_text)
    random.seed(1)
    r = client.post(
        "/game/action", json={"game_id": gid, "input_text": "Passo", "action_kind": "pass"}
    )
    assert r.status_code == 200, r.text
    hist = client.get("/game/history", params={"game_id": gid}).json()["entries"]
    return r.json(), saved[gid], hist


@pytest.mark.parametrize("llm_text", [GOOD_LLM, BAD_LLM], ids=["llm_aceito", "fallback_forcado"])
def test_death_end_to_end(monkeypatch, llm_text):
    resp, saved, hist = _die(monkeypatch, llm_text)
    assert saved["death_pending"] is True and resp["death_pending"] is True
    player_surfaces = "\n".join([resp["message"], *(str(e.get("text") or "") for e in hist)])
    assert "SmokeA" not in player_surfaces  # nome mutilado nunca
    assert "Você" in resp["message"]
    assert not any(
        str(e.get("text") or "").lstrip().startswith(HERO) for e in hist
    )  # voz do jogador
    ctx = saved["combat"]["death_context"]
    assert ctx["killer"] == "Goblin"
    chronicle = "\n".join(
        str(item.get("text") or "")
        for chapter in saved["chronicle"]
        for item in chapter.get("entries") or []
    )
    assert (
        "SmokeA" not in chronicle and f"{HERO} tombou em combate" in chronicle
    )  # só a crônica leva o nome
    mech = " ".join(saved["combat"].get("last_mech_log") or [])
    assert "SmokeA" not in mech and not mech.lstrip().startswith(HERO)


def test_forced_fallback_source_and_past_tense(monkeypatch):
    resp, saved, _hist = _die(monkeypatch, BAD_LLM)
    assert saved["combat"]["last_outcome_source"] == "fallback_attribution"
    assert "Goblin B" in resp["message"] and "já tinha tombado" in resp["message"]
    assert "Smoke4A cai" not in resp["message"] and "também tomba" not in resp["message"]


def test_accepted_llm_source(monkeypatch):
    _resp, saved, _hist = _die(monkeypatch, GOOD_LLM)
    assert saved["combat"]["last_outcome_source"] == "llm"
