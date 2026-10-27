"""SPEC-342 R2.1 - bloco `cena` aditivo na view de combate."""

from __future__ import annotations

import api
from services import scene_cards as sc


def _meta(rnd: int, cards: list[str]) -> dict:
    return {"scene": {"cartas_de_cena": cards, "tactical_state": {"round": rnd}}}


def _view(meta: dict) -> dict:
    return api._combat_block({"combat": meta, "enemies": [], "player": {}})


def test_cena_absent_when_off(monkeypatch):
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_SCENE_CARDS", mode)
        assert "cena" not in _view(_meta(3, ["nevoa_cinza_do_ermo"]))


def test_cena_lists_only_public_fields(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    cat = sc.catalog()
    cid = next(iter(cat))
    cena = _view(_meta(2, [cid]))["cena"]
    assert len(cena["cartas"]) == 1
    assert set(cena["cartas"][0]) == {"id", "nome", "sabor"}
    assert set(cena["relogio"]) == {"desde", "teto", "rodada", "ativo"}


def test_relogio_matches_engine_round(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    assert _view(_meta(4, []))["cena"]["relogio"] == {"desde": 5, "teto": 12, "rodada": 4, "ativo": False}
    assert _view(_meta(5, []))["cena"]["relogio"]["ativo"] is True


def test_cena_relogio_present_without_cards(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    cena = _view(_meta(1, []))["cena"]
    assert cena["cartas"] == [] and "relogio" in cena


def test_public_scene_none_without_scene(monkeypatch):
    monkeypatch.setenv("RPG_SCENE_CARDS", "on")
    assert sc.public_scene(None) is None
