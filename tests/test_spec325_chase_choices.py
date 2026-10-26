"""SPEC-325 Fase B / R10-R11 - abordagem da fuga e ataque durante a fuga (via `combat_node`)."""

from __future__ import annotations

import pytest

from agents import combat as cbt
from services import chase as chase_mod
from tests.spec325_chase_helpers import first_state, narration_spy, step
from tests.spec325_helpers import run_node

CHASE = {
    "trilha": "afastado",
    "perseguidores": ["e1"],
    "fugitive_id": "player",
    "alcancado": False,
    "escapou": False,
    "eligible": True,
}


@pytest.fixture
def conductor(monkeypatch):
    """Captura a Virtude (`condutor_virtude`) que entrou no teste da trilha."""
    seen: list[int] = []
    real = chase_mod.resolve_chase_round

    def wrapped(state, **kw):
        seen.append(kw.get("condutor_virtude"))
        return real(state, **kw)

    monkeypatch.setattr(chase_mod, "resolve_chase_round", wrapped)
    return seen


def _flee(monkeypatch, intent, mode=None):
    if mode:
        monkeypatch.setenv("RPG_CHASE_APPROACH", mode)
    state = first_state()
    state["messages"][0].content = intent
    return state, run_node(state, monkeypatch)


# --------------------------------------------------------------------- R10
def test_approach_keyword_picks_virtude(monkeypatch, conductor):
    _state, out = _flee(monkeypatch, "fujo pelos atalhos", "on")
    assert conductor == [1]  # atalhos -> Mente (herói de teste: mente 1)
    action = out["combat"]["last_player_action"]
    assert out["combat"]["chase"]["approach"] == "atalhos"
    assert action["kind"] == "flee" and action["chase_approach"] == "atalhos"


def test_force_keyword_picks_forca(monkeypatch, conductor):
    _flee(monkeypatch, "rompo o cerco e fujo", "on")
    assert conductor == [5]  # romper -> Força 5


def test_default_agilidade(monkeypatch, conductor):
    _state, out = _flee(monkeypatch, "fujo", "on")
    assert conductor == [5]  # Agilidade 5
    assert "approach" not in out["combat"]["chase"]
    assert "chase_approach" not in out["combat"]["last_player_action"]


def test_approach_off_and_shadow_keep_agilidade(monkeypatch, conductor):
    _flee(monkeypatch, "fujo pelos atalhos", "off")
    _flee(monkeypatch, "fujo pelos atalhos")  # default = shadow
    assert conductor == [5, 5]


def test_approach_shadow_state_identical_to_off(monkeypatch):
    logs: list[tuple] = []
    monkeypatch.setattr(cbt, "_log_event", lambda *a, **k: logs.append((a, k)))
    _s, off = _flee(monkeypatch, "fujo pelos atalhos", "off")
    off_events = [e for e in logs if e[0][1].endswith("_shadow")]
    _s, shadow = _flee(monkeypatch, "fujo pelos atalhos", "shadow")
    assert not off_events
    assert [e for e in logs if e[0][1] == "chase_approach_shadow"]
    for key in ("combat", "player", "enemies", "party"):
        assert shadow.get(key) == off.get(key), key
    assert shadow["messages"][0].content == off["messages"][0].content


def test_approach_not_sticky_between_rounds(monkeypatch, conductor):
    monkeypatch.setenv("RPG_CHASE_APPROACH", "on")
    state, out = _flee(monkeypatch, "fujo pelos atalhos", "on")
    out["combat"] = {**out["combat"], "chase": {**CHASE, "approach": "atalhos"}}
    _m, out2 = step(state, out, monkeypatch, "continuo fugindo")
    assert conductor[-1] == 5
    assert "approach" not in out2["combat"]["chase"]


# --------------------------------------------------------------------- R11
def _in_chase(monkeypatch, trilha, mode, ranged=False):
    """Rodada 1 cria a cena (fuga); depois injeta a trilha e ataca na rodada 2."""
    if mode:
        monkeypatch.setenv("RPG_CHASE_ATTACK", mode)
    state = first_state()
    out = run_node(state, monkeypatch)
    out["combat"] = {**out["combat"], "chase": {**CHASE, "trilha": trilha}}
    decl = {
        "actor_id": "player",
        "acao": {
            "kind": "attack",
            "target_id": "e1",
            "params": {"ranged": True} if ranged else {},
        },
    }
    narrate, seen = narration_spy()
    merged, out2 = step(
        state, out, monkeypatch, "ataco o inimigo", declaration=decl, narrate=narrate
    )
    return merged, out2, seen


def test_ranged_attack_keeps_chase(monkeypatch):
    merged, out, _ = _in_chase(monkeypatch, "afastado", "on", ranged=True)
    assert out["combat"]["chase"]["trilha"] == "afastado"
    assert out["combat"]["last_player_action"]["attempted"] is True
    assert out["combat"]["round"] == merged["combat"]["round"] + 1


def test_melee_pressionado_ends_chase(monkeypatch):
    _m, out, _ = _in_chase(monkeypatch, "pressionado", "on")
    assert "chase" not in out["combat"]
    assert out["combat"]["last_player_action"]["attempted"] is True


def test_melee_afastado_refused_without_spending_round(monkeypatch):
    merged, out, seen = _in_chase(monkeypatch, "afastado", "on")
    assert out["combat"]["round"] == merged["combat"]["round"]  # rodada nao gasta
    assert out["combat"]["last_player_action"]["attempted"] is False
    assert out["combat"]["chase"]["trilha"] == "afastado"
    assert "reduza a distância" in seen[-1]  # o motivo vai ao log/narracao
    hurt = [e for e in out["enemies"] if e["vitalidade"] != 30]
    assert not hurt  # nenhum golpe foi resolvido
    assert out["player"]["vitalidade"] == merged["player"]["vitalidade"]  # inimigos nao agiram


def test_melee_quase_livre_also_refused(monkeypatch):
    _m, out, _ = _in_chase(monkeypatch, "quase_livre", "on")
    assert out["combat"]["last_player_action"]["attempted"] is False


def test_attack_off_unchanged_chase_stale(monkeypatch):
    merged, out, _ = _in_chase(monkeypatch, "afastado", "off")
    assert out["combat"]["last_player_action"]["attempted"] is True
    assert out["combat"]["chase"]["trilha"] == "afastado"  # comportamento atual: nada fecha
    assert out["combat"]["round"] == merged["combat"]["round"] + 1


def test_attack_shadow_equals_off(monkeypatch):
    logs: list[tuple] = []
    monkeypatch.setattr(cbt, "_log_event", lambda *a, **k: logs.append((a, k)))
    _m, off, _ = _in_chase(monkeypatch, "afastado", "off")
    _m, shadow, _ = _in_chase(monkeypatch, "afastado", "shadow")
    assert [e for e in logs if e[0][1] == "chase_attack_shadow"]
    for key in ("combat", "player", "enemies", "party"):
        assert shadow.get(key) == off.get(key), key


def test_resume_old_chase_snapshot(monkeypatch):
    """Save gravado no meio de uma fuga antiga (sem approach/last_luck): retoma sem erro."""
    monkeypatch.setenv("RPG_CHASE_APPROACH", "on")
    monkeypatch.setenv("RPG_CHASE_ABANDON", "on")
    monkeypatch.setenv("RPG_CHASE_ATTACK", "on")
    state = first_state()
    out = run_node(state, monkeypatch)
    old = {k: v for k, v in CHASE.items() if k != "eligible"}
    out["combat"] = {**out["combat"], "chase": old}
    _m, out2 = step(state, out, monkeypatch, "fujo")
    chase = out2["combat"].get("chase") or {}
    assert chase.get("trilha") in ("quase_livre", "pressionado", "alcancado", "escapou")
    assert out2["combat"]["last_player_action"]["kind"] == "flee"
