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
GOOD_LLM = "Você tomba diante do Goblin. O Corvo Rubro, que já tinha tombado, jaz ao seu lado."
BAD_LLM = (
    "Smoke4A cai. O Corvo Rubro também tomba sem vida ao seu lado."  # V6: queda antiga no presente
)


def _die(monkeypatch, llm_text: str):
    """Corvo Rubro já caído numa rodada anterior (semeado no estado e no manifesto, sem busca de semente);
    o herói morre agora (seam = estabilização)."""
    from services import death_flow, round_log

    client, saved, gid = hp.api_client(monkeypatch, hero=HERO)
    st = hp.open_combat(client, saved, gid)
    other = hp.add_second_enemy(st)
    for e in st["enemies"]:
        if e["id"] == other:
            e.update(dead=True, status="morto", vitalidade=0, hp=0)
    for part in st["combat"]["encounter"]["participants"]:
        if part["participant_id"] == other:
            part["status"] = "morto"
    st["player"]["vitalidade"] = 0
    st["player"]["estado_terminal"] = True
    saved[gid] = deepcopy(st)
    monkeypatch.setattr(
        death_flow,
        "attempt_stabilization",
        lambda *a, **k: {"dead": True, "log": "Você não resiste.", "revived": False},
    )
    monkeypatch.setattr(combat, "_fast_text", lambda *a, **k: llm_text)
    seen: list[list[str]] = []
    real = round_log.authorship

    def spy(*a, **k):
        out = real(*a, **k)
        seen.append(list(out.get("earlier_fallen") or []))
        return out

    monkeypatch.setattr(round_log, "authorship", spy)
    random.seed(1)
    r = client.post(
        "/game/action", json={"game_id": gid, "input_text": "Passo", "action_kind": "pass"}
    )
    assert r.status_code == 200, r.text
    assert any("Corvo Rubro" in fallen for fallen in seen), seen  # a queda antiga chegou ao resumo
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
    assert "Corvo Rubro" in resp["message"] and "já tinha tombado" in resp["message"]
    assert "Smoke4A cai" not in resp["message"] and "também tomba" not in resp["message"]


def test_accepted_llm_source(monkeypatch):
    _resp, saved, _hist = _die(monkeypatch, GOOD_LLM)
    assert saved["combat"]["last_outcome_source"] == "llm"
