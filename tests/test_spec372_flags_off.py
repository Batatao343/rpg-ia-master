"""SPEC-372 R12 — com `RPG_FAUNA_TRAMAS` off (ou sem requisitos) nada muda."""

from __future__ import annotations

from services import fauna
from services import plot_threads as pt


def test_registrada_off_no_registro():
    import yaml

    reg = yaml.safe_load(open("config/flags.yaml", encoding="utf-8"))
    flags = reg.get("flags", reg)
    assert flags["RPG_FAUNA_TRAMAS"]["default"] == "off"


def test_tramas_mode_exige_fauna_e_tramas(monkeypatch):
    pt.clear_cache()
    monkeypatch.setenv("RPG_FAUNA_TRAMAS", "on")
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.delenv("RPG_PLOT_THREADS", raising=False)
    assert fauna.tramas_mode() == "off"
    monkeypatch.setenv("RPG_PLOT_THREADS", "on")
    assert fauna.tramas_mode() == "on"
    monkeypatch.setenv("RPG_FAUNA", "off")
    assert fauna.tramas_mode() == "off"
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_TRAMAS", "off")
    assert fauna.tramas_mode() == "off"
