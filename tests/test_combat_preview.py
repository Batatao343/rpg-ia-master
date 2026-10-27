"""SPEC-334 R4 - preview determinístico: exato (vs simulação), puro e sem vazar defesa."""

from __future__ import annotations

import copy
import random

import pytest
from fastapi.testclient import TestClient

import api
from services import combat_preview as cpv
from services.conflict_resolution import resolve_attack
from tests.test_combat_simulator import _request

GOLPE = "bas_san_golpe"


def _state(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    return api._build_combat_simulator_state(_request(quantity=1))


@pytest.mark.parametrize("advantage", [0, 1, -1])
def test_chance_bate_com_dez_mil_rolagens(monkeypatch, advantage):
    state = _state(monkeypatch)
    player, enemy = state["player"], state["enemies"][0]
    dist = cpv.exact_attack_distribution(player, enemy, virtude_key="forca", advantage=advantage)
    exact = 1 - dist["erro"]
    rng = random.Random(334)
    n = 10_000
    hits = sum(
        resolve_attack(player, enemy, virtude_key="forca", advantage=advantage, rng=rng)["acerto"]
        for _ in range(n)
    )
    assert abs(hits / n - exact) < 0.01
    assert abs(sum(dist.values()) - 1) < 1e-9


def test_preview_nao_altera_estado_e_nao_vaza_defesa(monkeypatch):
    state = _state(monkeypatch)
    enemy = state["enemies"][0]
    enemy["immunities"] = ["cortante"]
    enemy["armor"] = {"protecao": 9, "integridade_atual": 5}
    before = copy.deepcopy(state)
    out = cpv.preview(state, GOLPE, str(enemy["id"]))
    assert state == before
    assert 0 < out["chance_acerto_pct"] <= 100
    assert out["dano_min"] > 0 and out["dano_max"] == 2 * out["dano_min"]  # bruto, sem defesa
    assert set(out) == {
        "chance_acerto_pct",
        "chance_critico_pct",
        "dano_min",
        "dano_max",
        "ferimento_provavel",
        "efeitos_extra",
        "pressagio_frustrado",
    }


@pytest.mark.parametrize(
    ("card", "target", "reason"),
    [
        ("nao_existe", "e", "card_unknown"),
        (GOLPE, "ninguem", "target_unknown"),
        ("bas_san_guarda", "e", "not_offensive"),
    ],
)
def test_preview_recusa_entradas_invalidas(monkeypatch, card, target, reason):
    state = _state(monkeypatch)
    target = str(state["enemies"][0]["id"]) if target == "e" else target
    with pytest.raises(ValueError, match=reason):
        cpv.preview(state, card, target)


def test_endpoint_puro_e_codigos(monkeypatch):
    state = _state(monkeypatch)
    eid = str(state["enemies"][0]["id"])
    monkeypatch.setattr(api, "_resolve_save_file", lambda gid: "x")
    monkeypatch.setattr(api, "load_game_state", lambda f: state)
    saved = []
    monkeypatch.setattr(api, "save_game_state", lambda *a, **k: saved.append(1), raising=False)
    client = TestClient(api.app, raise_server_exceptions=False)
    ok = client.post("/game/combat/preview", json={"card_id": GOLPE, "target_id": eid})
    assert ok.status_code == 200 and ok.json()["chance_acerto_pct"] > 0
    assert ok.headers["cache-control"] == "private, no-store"
    bad = client.post("/game/combat/preview", json={"card_id": GOLPE, "target_id": "nope"})
    assert bad.status_code == 409 and bad.json()["code"] == "preview_invalid"
    state["combat"]["active"] = False
    off = client.post("/game/combat/preview", json={"target_id": eid})
    assert off.json()["code"] == "preview_no_combat"
    assert not saved
    g = client.get("/data/cards/glossario")
    assert "palavras_chave" in g.json()


def test_mech_log_uma_linha_com_numeros_do_motor():
    atk = {
        "actor_id": "player",
        "target_id": "lobo",
        "card_id": GOLPE,
        "dice_rolled": [6, 7],
        "dice_kept": [6, 7],
        "virtude": 2,
        "modificador": 0,
        "total": 15,
        "esquiva_alvo": 12,
        "resultado": "acerto",
        "acerto": True,
        "dano_final": 5,
    }
    [line] = cpv.mech_log([atk], [{"id": "lobo", "name": "Lobo"}])
    assert line.startswith("Você · ") and "→ Lobo" in line
    assert "2d10 6 + 7 +2 = 15 vs 12" in line and line.endswith("acerto · 5 dano")


def test_pilhas_publicas_trazem_texto_e_listas_ordenadas_por_nome(monkeypatch):
    from services import card_piles as cp

    state = _state(monkeypatch)
    piles = cp.start_piles(state["player"], 1)
    view = cp.public_view(piles)
    assert all("texto" in c and "palavras_chave" in c for c in view["mao"])
    for rows in view["listas"].values():
        names = [r["name"].lower() for r in rows]
        assert names == sorted(names)
    assert len(view["listas"]["compra"]) == view["compra"]
