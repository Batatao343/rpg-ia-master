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
