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
GOOD_LLM = "Você tomba diante do Goblin. O chão frio recebe o seu corpo."
BAD_LLM = (
    "Smoke4A cai. Ficas de pé, com teu cajado firme, e Você respira fundo."  # V5: tratamento misto
)


def _die(monkeypatch, llm_text: str):
    """Herói em Estado Terminal; o seam é a estabilização (morte). Round-trip pela API."""
    from services import death_flow

    client, saved, gid = hp.api_client(monkeypatch, hero=HERO)
    st = hp.open_combat(client, saved, gid)
    st["player"]["vitalidade"] = 0
    st["player"]["estado_terminal"] = True
    saved[gid] = deepcopy(st)
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


def test_forced_fallback_source(monkeypatch):
    resp, saved, _hist = _die(monkeypatch, BAD_LLM)
    assert saved["combat"]["last_outcome_source"] == "fallback_attribution"
    assert "Você tomba." in resp["message"] and "Smoke4A cai" not in resp["message"]


def test_accepted_llm_source(monkeypatch):
    _resp, saved, _hist = _die(monkeypatch, GOOD_LLM)
    assert saved["combat"]["last_outcome_source"] == "llm"
