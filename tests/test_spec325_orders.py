"""SPEC-325 Fase C / R15 - ordem a companheiro (via `combat_node` real, MockLLM, tabela D9)."""

from __future__ import annotations

import json

import pytest

from services import companion_orders as co
from services.prompt_guard import unwrap_player_input
from tests.spec325_chase_helpers import BRUNNA, BRUNNA_ID, chaser, first_state, step
from tests.spec325_helpers import run_node


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_COMPANION_ORDERS", "on")


def _surrendered():
    return chaser(id="e2", name="Rendido", status="rendido", surrendered=True)


def _fallen():
    return chaser(
        id="e3", name="Caido", status="incapacitado", incapacitated=True, nonlethal_by="player"
    )


def _state(*, values=None, approval=None, enemies=None, party_over=None):
    state = first_state(party=True, approval=approval, enemies=enemies or [chaser()])
    soul = state["companion_souls"].get(BRUNNA_ID)
    if soul is not None and values:
        soul["values"] = {**soul["values"], **values}
    if party_over:
        state["party"][0].update(party_over)
    return state


def _order(monkeypatch, intent, **kw):
    """Rodada 1 (cria a cena) + rodada 2 com a ordem. Devolve (logs da narração, saída)."""
    state = _state(**kw)
    out = run_node(state, monkeypatch)
    captured: list[list[str]] = []

    def narrate(player, enemies, logs, *a, **k):
        captured.append(list(logs))
        return "Fim."

    _m, out2 = step(state, out, monkeypatch, intent, narrate=narrate)
    return captured[-1], out2


def _joined(logs):
    return " | ".join(logs)


def test_order_becomes_ally_declaration(monkeypatch):
    logs, out = _order(monkeypatch, "Brunna, proteger.")
    assert any("protege" in line for line in logs)
    assert not any("recusa" in line for line in logs)


def test_order_attack_resolves_attack_by_ally(monkeypatch):
    orc = chaser(id="e4", name="Orc")
    logs, _out = _order(monkeypatch, "Brunna, ataque o Orc.", enemies=[chaser(), orc])
    hers = [line for line in logs if line.startswith(BRUNNA[:12])]
    assert any("→ Orc" in line for line in hers), logs
    monkeypatch.setenv("RPG_COMPANION_ORDERS", "off")  # sem ordem, o perfil escolhe outro alvo
    logs_off, _ = _order(monkeypatch, "Brunna, ataque o Orc.", enemies=[chaser(), orc])
    assert not any("→ Orc" in line for line in logs_off if line.startswith(BRUNNA[:12])), logs_off


def test_order_ignored_when_flag_off(monkeypatch):
    monkeypatch.setenv("RPG_COMPANION_ORDERS", "off")
    logs, _out = _order(monkeypatch, "Brunna, proteger.")
    assert not any("protege" in line for line in logs)


def test_absolute_restriction_refuses_and_ally_uses_profile(monkeypatch):
    """Honra >= 2 bloqueia `atacar_rendido` como absoluta, mesmo com lealdade."""
    logs, out = _order(
        monkeypatch,
        "Brunna, ataque o Rendido.",
        values={"honra": 2},
        approval=95,
        enemies=[chaser(), _surrendered()],
    )
    assert any("recusa a ordem" in line for line in logs)
    rendido = next(e for e in out["enemies"] if e["id"] == "e2")
    assert rendido["vitalidade"] == rendido["max_vitalidade"]  # ninguém atacou o rendido


def test_resistant_yields_with_loyalty(monkeypatch):
    kw = {"values": {"compaixao": 2}, "enemies": [chaser(), _fallen()]}
    logs, _ = _order(monkeypatch, "Brunna, ataque o Caido.", approval=40, **kw)
    assert any("recusa a ordem" in line for line in logs)
    logs, _ = _order(monkeypatch, "Brunna, ataque o Caido.", approval=80, **kw)
    assert not any("recusa a ordem" in line for line in logs)


def test_lost_command_ignores_order(monkeypatch):
    logs, _out = _order(
        monkeypatch,
        "Brunna, proteger.",
        party_over={"active_conditions": [{"name": "Medo", "duration": 3}]},
    )
    assert any("ignora a ordem" in line for line in logs)
    assert not any("protege" in line for line in logs)


def test_player_action_unchanged_on_refusal(monkeypatch):
    kw = {"values": {"honra": 2}, "enemies": [chaser(), _surrendered()]}
    _logs, with_order = _order(monkeypatch, "Brunna, ataque o Rendido.", **kw)
    monkeypatch.setenv("RPG_COMPANION_ORDERS", "off")
    _logs, without = _order(monkeypatch, "Brunna, ataque o Rendido.", **kw)
    assert with_order["combat"]["last_player_action"] == without["combat"]["last_player_action"]


def test_restrictions_table_from_soul():
    assert co.restrictions_from_soul(None) == []
    assert co.restrictions_from_soul({"values": {"honra": 1, "compaixao": 1}}) == []
    got = {
        r["blocks"][0]: r["resistance"]
        for r in co.restrictions_from_soul({"values": {"honra": 2, "compaixao": 2, "coragem": 2}})
    }
    assert got == {
        "atacar_rendido": "absoluta",
        "atacar_incapacitado": "resistente",
        "abandonar_posto": "resistente",
    }


def test_validate_order_leverage_from_approval():
    soul = {"values": {"compaixao": 2}, "approval": 50}
    order = {"tags": ["atacar_incapacitado"]}
    assert co.validate_order({}, soul, order)["accepted"] is False
    assert co.validate_order({}, {**soul, "approval": 70}, order)["accepted"] is True
    absolute = {"values": {"honra": 2}, "approval": 100}
    assert co.validate_order({}, absolute, {"tags": ["atacar_rendido"]})["accepted"] is False


def test_scene_ally_without_soul_has_no_restriction(monkeypatch):
    state = _state(enemies=[chaser(), _surrendered()])
    state["companion_souls"] = {}
    out = run_node(state, monkeypatch)
    captured: list[list[str]] = []

    def narrate(p, e, logs, *a, **k):
        captured.append(list(logs))
        return "Fim."

    step(state, out, monkeypatch, "Brunna, ataque o Rendido.", narrate=narrate)
    assert not any("recusa" in line for line in captured[-1])


def _norm(out):
    res = {k: v for k, v in out.items() if k != "messages"}
    res["narr"] = [m.content for m in out.get("messages", [])]
    return json.dumps(res, default=str, sort_keys=True)


def test_shadow_no_state_change(monkeypatch):
    results = {}
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_COMPANION_ORDERS", mode)
        state = _state(values={"honra": 2}, enemies=[chaser(), _surrendered()])
        out = run_node(state, monkeypatch)
        _m, out2 = step(state, out, monkeypatch, "Brunna, ataque o Rendido.")
        results[mode] = _norm(out2)
    assert results["off"] == results["shadow"]


def test_api_order_chips_only_with_flag_on(monkeypatch):
    import api

    state = _state()
    out = run_node(state, monkeypatch)
    merged = {**state, **{k: v for k, v in out.items() if k != "next"}}
    assert api._combat_block(merged)["companion_orders"] == [{"id": BRUNNA_ID, "name": BRUNNA}]
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_COMPANION_ORDERS", mode)
        assert "companion_orders" not in api._combat_block(merged)


class _SpyLLM:
    def __init__(self, seen):
        self.seen = seen

    def with_structured_output(self, model):
        seen = self.seen

        class _Bound:
            def invoke(self, msgs):
                seen.append(unwrap_player_input(str(msgs[-1].content)))
                return model(kind="attack")

        return _Bound()


def test_order_clause_not_sent_to_player_classify(monkeypatch):
    """C-P2-1: "Brunna, recuar." não pode virar `move` do herói no CLASSIFY real."""
    from agents import combat as cbt

    seen: list[str] = []
    state = _state()
    out = run_node(state, monkeypatch)
    monkeypatch.setattr(cbt, "get_llm", lambda *a, **k: _SpyLLM(seen))
    _m, out2 = step(state, out, monkeypatch, "Brunna, recuar. Ataco o Goblin.")
    assert seen == ["Ataco o Goblin."]
    assert out2["combat"]["last_player_action"]["kind"] == "attack"


def test_order_only_skips_classify(monkeypatch):
    from agents import combat as cbt

    seen: list[str] = []
    state = _state()
    out = run_node(state, monkeypatch)
    monkeypatch.setattr(cbt, "get_llm", lambda *a, **k: _SpyLLM(seen))
    _m, out2 = step(state, out, monkeypatch, "Brunna, recuar.")
    assert seen == []
    assert out2["combat"]["last_player_action"]["kind"] == "attack"


def test_order_text_still_classified_when_flag_off(monkeypatch):
    from agents import combat as cbt

    monkeypatch.setenv("RPG_COMPANION_ORDERS", "off")
    seen: list[str] = []
    state = _state()
    out = run_node(state, monkeypatch)
    monkeypatch.setattr(cbt, "get_llm", lambda *a, **k: _SpyLLM(seen))
    step(state, out, monkeypatch, "Brunna, proteger.")
    assert seen == ["Brunna, proteger."]
