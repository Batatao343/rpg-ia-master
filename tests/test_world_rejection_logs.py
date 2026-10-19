"""SPEC-252: rejeicoes do mundo, guarda narrativa, economia e replanejamento com motivo em log."""
import json

import pytest

from observability import logging_setup

SENT = "SENTINELA-252-xk"


@pytest.fixture(autouse=True)
def _log(monkeypatch):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})


def _events(capsys, name):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get("event") == name:
            out.append(d)
    return out


def _state():
    return {"world": {"turn_count": 3, "current_location_id": "nova_arcadia"},
            "event_log": [], "world_projection": {}, "quests": [], "pending_world_events": []}


def test_rejection_has_reason_code(capsys):
    from services.event_processor import process_pending_events
    st = _state()
    st["pending_world_events"] = [
        {"type": "npc_killed", "target_id": f"{SENT} nome livre", "actor_id": "player",
         "detail": SENT, "payload": {}},
        {"type": "quest_completed", "target_id": "q1", "actor_id": "player", "payload": {}},
    ]
    capsys.readouterr()
    process_pending_events(st)
    lines = _events(capsys, "event.proposal_rejected")
    assert len(lines) == 2
    from services.world_validators import REASON_CODES
    for l in lines:
        assert l["reason_code"] in REASON_CODES and l["source"] in ("llm", "rule", "prevalidation")
        assert "target_ref" not in l  # nome livre / id de quest nao e id de catalogo
        assert SENT not in json.dumps(l)
    assert {l["reason_code"] for l in lines} == {"unknown_target", "invalid_payload"}


def test_reason_code_mapping_and_unknown_is_other():
    from services import world_validators as wv
    assert wv.reason_code(f"{wv.UNPROVEN_PREFIX}: x") == "unproven"
    assert wv.reason_code(f"{wv.LIMIT_PREFIX}: cooldown de 3 turnos") == "cooldown"
    assert wv.reason_code("duplicata: a/b") == "duplicate"
    assert wv.reason_code("qualquer coisa nova") == "other"
    assert wv.catalog_ref("texto livre do llm") is None


def test_trade_refused_logged(capsys):
    from services import economy
    capsys.readouterr()
    economy.log_trade("buy", {"ok": False, "reason": f"Ouro insuficiente (1/50). {SENT}"})
    economy.log_trade("buy", {"ok": True, "item_id": "inexistente-no-catalogo", "gold_delta": -5})
    lines = _events(capsys, "economy.trade")
    assert lines[0]["outcome"] == "refused" and lines[0]["reason_code"] == "insufficient_gold"
    assert lines[1]["outcome"] == "ok" and lines[1]["gold_delta"] == -5
    assert "item_id" not in lines[1]
    assert SENT not in json.dumps(lines)


def test_unique_conflict_logged(capsys):
    from services import economy
    capsys.readouterr()
    economy.log_trade("craft", {"ok": False,
                                "reason": "Esse artefato já existe no mundo — não há como forjar outro."})
    assert _events(capsys, "economy.trade")[0]["reason_code"] == "unique_conflict"


def test_unique_conflict_event_level(capsys):
    from services import economy
    capsys.readouterr()
    economy.log_trade("craft", {"ok": False, "reason": "Esse artefato já existe no mundo"})
    out = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    c = [d for d in out if d.get("event") == "economy.unique_claim_conflict"]
    assert c and c[0]["level"].lower() == "warning"


def test_replan_reason_logged(capsys):
    from agents import campaign_manager as cm
    assert cm._replan_reason({"needs_replan": True}) == "needs_replan"
    assert cm._replan_reason({"world": {}}) == "first_plan"
    assert cm._replan_reason({"world": {"current_location": "a"},
                              "campaign_plan": {"location": "a", "beats": []}}) == "periodic"
    assert cm._replan_reason({"world": {"current_location": "a", "turn_count": 3},
                              "campaign_plan": {"location": "a", "beats": [], "current_step": 0,
                                                "last_planned_turn": 2}}) == "arc_finished"


def test_replan_event_emitted(capsys, monkeypatch):
    from agents import campaign_manager as cm
    plan = {"location": "Nova Arcádia", "beats": [{"description": "x", "status": "pending"}],
            "climax": "c", "current_step": 0, "last_planned_turn": 1, "arc_title": "Arco"}

    def fake(state, info=None):
        if info is not None:
            info["outcome"] = "template"
        return plan
    monkeypatch.setattr(cm, "_build_plan", fake)
    capsys.readouterr()
    cm.campaign_manager_node({"world": {"turn_count": 0, "current_location": "Nova Arcádia"},
                              "messages": []})
    line = _events(capsys, "campaign.replan")[0]
    assert line["reason"] == "first_plan" and line["outcome"] == "template"


def test_narrative_rejected_counts(capsys):
    from agents.storyteller import _log_narrative_rejected
    from observability.telemetry import begin_fallbacks, end_fallbacks
    tok, bucket = begin_fallbacks()
    try:
        capsys.readouterr()
        _log_narrative_rejected("item", ["unknown_item", "unknown_item", "unique_claimed"])
        lines = _events(capsys, "narrative.rejected")
        assert {(l["kind"], l["reason_code"], l["count"]) for l in lines} == {
            ("item", "unknown_item", 2), ("item", "unique_claimed", 1)}
        assert bucket.counters == {"item": 3}
    finally:
        end_fallbacks(tok)


def test_no_free_text(capsys):
    from agents.storyteller import _log_narrative_rejected
    capsys.readouterr()
    _log_narrative_rejected("event", ["unproven"])
    assert SENT not in capsys.readouterr().out


def _literal_text(node):
    import ast
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        from services import world_validators as wv
        consts = {"UNPROVEN_PREFIX": wv.UNPROVEN_PREFIX, "LIMIT_PREFIX": wv.LIMIT_PREFIX}
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(v.value)
            else:
                name = getattr(getattr(v, "value", None), "id", None)
                parts.append(consts.get(name, "X"))
        return "".join(parts)
    return None


def _rejection_messages(path, kind):
    """Mensagens reais de recusa no codigo (AST): ``ValidationResult(False, msg)`` ou
    ``{"ok": False, "reason": msg}``."""
    import ast
    from pathlib import Path
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if kind == "validator" and isinstance(node, ast.Call) and getattr(node.func, "id", "") == "ValidationResult" \
                and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) and node.args[0].value is False:
            out.append(_literal_text(node.args[1]))
        if kind == "trade" and isinstance(node, ast.Dict):
            keys = [k.value if isinstance(k, ast.Constant) else None for k in node.keys]
            if "ok" in keys and "reason" in keys:
                ok = node.values[keys.index("ok")]
                if isinstance(ok, ast.Constant) and ok.value is False:
                    out.append(_literal_text(node.values[keys.index("reason")]))
    return [m for m in out if m]


def test_every_real_validator_message_has_a_code():
    """Revisao P2/P3: mensagem de recusa reescrita nao pode cair em ``other`` em silencio."""
    from services.world_validators import reason_code
    msgs = (_rejection_messages("services/world_validators.py", "validator")
            + _rejection_messages("services/event_processor.py", "validator"))
    assert len(msgs) >= 10
    assert [m for m in msgs if reason_code(m) == "other"] == []


def test_every_real_trade_refusal_has_a_code():
    from services.economy import trade_reason_code
    msgs = _rejection_messages("services/economy.py", "trade")
    assert len(msgs) >= 10
    assert [m for m in msgs if trade_reason_code(m) == "other"] == []
