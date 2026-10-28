"""SPEC-355 R2: Provocacao aplicada nesta rodada desvia a intencao de ataque congelada."""

from __future__ import annotations

import copy

import pytest

from services import conflict_orchestrator as orch
from services import conflict_turn as ct
from services import enemy_intent as ei
from tests.test_spec339_duracao_condicoes import ORDENS, _cena_devoto, _Rng0, _voto


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    monkeypatch.setattr(ei, "_fork_rng", lambda rng: _Rng0(0))


def _round(actors, scene, sides, decl, frozen=None, rng=None, initiator="heroes"):
    return orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": decl},
        initiator=initiator,
        rng=rng or _Rng0(1),
        pressagios=frozen,
    )


def _frozen(actors, scene, sides):
    return ei.forecast_round(scene, actors, sides, _Rng0(1))


def _hit_on(out, who):
    return next((x for x in out["logs"] if x.startswith(f"e → {who}")), None)


def test_taunt_same_round_redirects_frozen_attack():
    actors, scene, sides = _cena_devoto()
    frozen = _frozen(actors, scene, sides)
    assert frozen["e"][0]["alvo_id"] == "ally"
    out = _round(actors, scene, sides, _voto(), frozen)
    assert _hit_on(out, "player") and not _hit_on(out, "ally")
    assert out["pressagios_desviados"] == [
        {"actor_id": "e", "alvo_original": "ally", "alvo_novo": "player", "por": "player"}
    ]
    assert any("provocado por" in ln and "muda de alvo" in ln for ln in out["logs"])


def test_taunt_same_round_spends_one_declaration():
    actors, scene, sides = _cena_devoto()
    frozen = _frozen(actors, scene, sides)
    alvos = []
    for rnd in range(1, 4):
        decl = _voto() if rnd == 1 else ct.TurnDeclaration(actor_id="player")
        out = _round(actors, scene, sides, decl, frozen, rng=_Rng0(rnd))
        alvos.append(
            "player" if _hit_on(out, "player") else "ally" if _hit_on(out, "ally") else None
        )
        frozen = ei.forecast_round(scene, actors, sides, _Rng0(rnd))
    assert alvos[0] == "player"
    assert "player" not in alvos[1:], alvos  # o congelamento seguinte nao le a Provocacao


def test_taunt_no_roll_when_already_target():
    actors, scene, sides = _cena_devoto()
    frozen = copy.deepcopy(_frozen(actors, scene, sides))
    intent = frozen["e"][0]
    intent["alvo_id"] = "player"
    intent["declaration"]["acao"]["target_id"] = "player"
    out = _round(actors, scene, sides, _voto(), frozen)
    assert _hit_on(out, "player") and "pressagios_desviados" not in out
    # nada foi gasto: a Provocacao segue no inimigo para o proximo congelamento
    assert any(c.get("control") == "taunt" for c in actors["e"]["active_conditions"])


def test_taunt_resisted_same_round_line():
    class _RngHigh(_Rng0):
        def random(self):
            return 0.99

    actors, scene, sides = _cena_devoto()
    frozen = _frozen(actors, scene, sides)
    out = _round(actors, scene, sides, _voto(), frozen, rng=_RngHigh(1))
    assert _hit_on(out, "ally") and "pressagios_desviados" not in out
    assert any(m.get("kind") == "special:taunt_resisted" for m in out["class_mechanics"])


def test_non_attack_intent_not_redirected():
    actors, scene, sides = _cena_devoto()
    frozen = copy.deepcopy(_frozen(actors, scene, sides))
    frozen["e"][0]["tipo"] = "defesa"
    out = _round(actors, scene, sides, _voto(), frozen)
    assert "pressagios_desviados" not in out


def test_intent_off_unchanged(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "off")
    actors, scene, sides = _cena_devoto()
    out = _round(actors, scene, sides, _voto())
    assert "pressagios_desviados" not in out


def test_modulo_ordens_cobertas():
    assert set(ORDENS) == {"hero_first", "enemy_first"}
