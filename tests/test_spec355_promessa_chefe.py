"""SPEC-355 R3: toda promessa publica (`prenuncio`) e cumprida ou frustrada com motivo e linha."""

from __future__ import annotations

import pytest

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
from services import enemy_decks as edk
from tests.test_enemy_decks import _custom

SIG = {
    "carta": "bst_golpe_mestre",
    "a_cada_n": 3,
    "desvio": 0,
    "telegrafo": "{nome} range os dentes.",
}
FASES = [
    {"ate_vitalidade_pct": 60, "narracao": "{nome} muda de postura."},
    {"ate_vitalidade_pct": 35, "narracao": "{nome} entra em fúria."},
]


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)
    monkeypatch.delenv("RPG_ENEMY_DECKS", raising=False)
    edk.reload()
    yield
    edk.reload()


def _boss(monkeypatch, *, fases=None):
    e, scene, actors, sides = _custom(monkeypatch, ["ataque"], dict(SIG))
    e["cartas"].append("bst_golpe_mestre")
    if fases:
        e["tactical_profile"]["fases"] = fases
    return e, scene, actors, sides


def _round(scene, actors, sides, rnd_before):
    cs._tactical_state(scene)["round"] = rnd_before
    return orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": ct.TurnDeclaration(actor_id="player")},
        initiator="heroes",
        rng=__import__("random").Random(1),
    )


def test_prenuncio_broken_by_low_vitality_is_logged(monkeypatch):
    e, scene, actors, sides = _boss(monkeypatch, fases=FASES)
    assert edk.record_promise(scene, e, 2)  # anuncio no fim de N; assinatura em N+1 = 3
    e["vitalidade"] = 9  # 30 %: cruza as duas fases
    out = _round(scene, actors, sides, 2)
    frustrados = [f for f in out["pressagios_frustrados"] if f["tipo"] == "assinatura"]
    assert frustrados == [{"actor_id": "lobo_1", "tipo": "assinatura", "motivo": "troca_de_fase"}]
    logs = out["logs"]
    i_fase = next(i for i, ln in enumerate(logs) if "entra em fúria" in ln)
    i_abandona = next(i for i, ln in enumerate(logs) if "abandona o golpe" in ln)
    assert i_fase < i_abandona
    assert "a nova fase o muda" in logs[i_abandona]
    assert "prenuncios" not in scene or "lobo_1" not in scene["prenuncios"]


def test_prenuncio_broken_without_phase_change_is_muito_ferido(monkeypatch):
    e, scene, actors, sides = _boss(monkeypatch)
    edk.record_promise(scene, e, 2)
    e["vitalidade"] = 9
    out = _round(scene, actors, sides, 2)
    motivos = [f["motivo"] for f in out["pressagios_frustrados"] if f["tipo"] == "assinatura"]
    assert motivos == ["muito_ferido"]
    assert any("ferido demais" in ln for ln in out["logs"])


def test_prenuncio_kept_is_not_frustrated(monkeypatch):
    e, scene, actors, sides = _boss(monkeypatch)
    edk.record_promise(scene, e, 2)
    out = _round(scene, actors, sides, 2)
    assert not [f for f in out.get("pressagios_frustrados", []) if f["tipo"] == "assinatura"]
    assert "lobo_1" not in scene.get("prenuncios", {})  # cumprida: sai da cena


def test_prenuncio_intent_off_path(monkeypatch):
    e, scene, actors, sides = _boss(monkeypatch)
    out = _round(scene, actors, sides, 1)  # rodada 2: a assinatura cai na 3
    assert any("range os dentes" in ln for ln in out["logs"])
    assert scene["prenuncios"]["lobo_1"] == {"carta": "bst_golpe_mestre", "rnd": 3, "fase_idx": 0}


def test_prenuncios_live_in_scene_not_actor(monkeypatch):
    e, scene, actors, sides = _boss(monkeypatch)
    edk.record_promise(scene, e, 2)
    assert "prenuncios" in scene
    assert "prenuncios" not in e and not any("prenuncio" in k for k in e)
