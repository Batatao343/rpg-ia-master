"""SPEC-239: configuração central de logging."""
import json
import logging

import pytest

from observability import logging_setup
from observability.telemetry import log_event


@pytest.fixture(autouse=True)
def _clean_logger():
    logger = logging.getLogger("rpg")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    logger.handlers = []
    yield logger
    logger.handlers, logger.level, logger.propagate = saved[0], saved[1], saved[2]


def _lines(capsys):
    return [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.strip()]


def test_info_event_reaches_stdout(capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "info"})
    log_event("jev", "shadow", level="info", n=1)
    (line,) = _lines(capsys)
    assert line["event"] == "jev.shadow" and line["level"] == "info"
    assert line["logger"] == "rpg.jev" and line["ts"].endswith("Z")


def test_warning_level_hides_info(capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "warning"})
    log_event("jev", "shadow", level="info")
    log_event("jev", "bad", level="warning")
    assert [x["event"] for x in _lines(capsys)] == ["jev.bad"]


def test_idempotent_no_duplicate_lines(capsys):
    for _ in range(3):
        logging_setup.configure_logging({})
    log_event("x", "once")
    assert len(_lines(capsys)) == 1


def test_invalid_level_falls_back_info(capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "loud"})
    log_event("x", "ok")
    events = [x["event"] for x in _lines(capsys)]
    assert "logging.config_invalid_level" in events and "x.ok" in events


def test_area_override(capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "info", "RPG_LOG_LEVEL_NOISY": "error"})
    log_event("noisy", "a", level="warning")
    log_event("quiet", "b", level="warning")
    assert [x["event"] for x in _lines(capsys)] == ["quiet.b"]
    logging.getLogger("rpg.noisy").setLevel(logging.NOTSET)


def test_legacy_string_wrapped_and_redacted(capsys):
    logging_setup.configure_logging({})
    logging.getLogger("rpg.old").warning("blocked user=joao@example.com\nsecond")
    (line,) = _lines(capsys)
    assert line["event"] == "rpg.old.legacy"
    assert "joao@example.com" not in line["message"] and "[EMAIL]" in line["message"]


def test_exception_logs_type_not_message(capsys):
    logging_setup.configure_logging({})
    try:
        raise RuntimeError("segredo-XYZ")
    except RuntimeError:
        logging.getLogger("rpg.old").exception("boom")
    out = capsys.readouterr().out
    assert "segredo-XYZ" not in out and json.loads(out)["error_type"] == "RuntimeError"


def test_turn_line_has_event_key(capsys):
    import api

    logging_setup.configure_logging({})
    api._log_turn({"game_id": "g", "world": {"turn_count": 1}, "next": "STORY"}, 0.0, 0, None)
    lines = [x for x in _lines(capsys) if x.get("evt") == "turn"]
    assert len(lines) == 1 and lines[0]["event"] == "turn"
