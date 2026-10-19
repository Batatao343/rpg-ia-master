"""SPEC-262 R4: todo evento de log literal esta no catalogo e o doc gerado esta fresco."""

import importlib.util
from pathlib import Path

from observability.events import EVENTS

ROOT = Path(__file__).resolve().parents[1]


def _generator():
    spec = importlib.util.spec_from_file_location(
        "gen_event_catalog", ROOT / "scripts" / "gen_event_catalog.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_logged_event_is_registered():
    found = set(_generator().scan())
    missing = sorted(found - set(EVENTS))
    assert not missing, (
        "evento de log novo sem registro; rode "
        f"`uv run python scripts/gen_event_catalog.py`: {missing}"
    )


def test_registry_has_no_stale_events():
    gen = _generator()
    stale = sorted(set(EVENTS) - set(gen.scan()) - set(gen.MANUAL) - set(gen.OVERRIDES))
    assert not stale, f"eventos registrados que nao existem mais no codigo: {stale}"


def test_registry_and_doc_are_fresh():
    gen = _generator()
    events = gen.build()
    assert EVENTS == events, (
        "observability/events.py desatualizado: rode scripts/gen_event_catalog.py"
    )
    doc = (ROOT / "docs" / "operacao" / "EVENTOS_DE_LOG.md").read_text(encoding="utf-8")
    assert doc.replace("\r\n", "\n") == gen.render_doc(events)


LEGACY_NAMES = {
    "turn",
    "turn_delivery",
    "client_latency",
    "rpg.cron",
}  # linhas JSON diretas (anteriores)


def test_event_names_are_area_dot_event():
    for key in EVENTS:
        if key in LEGACY_NAMES:
            continue
        area, _, event = key.partition(".")
        assert area and event and key == key.lower() and " " not in key, key
