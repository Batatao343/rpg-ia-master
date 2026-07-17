# -*- coding: utf-8 -*-
"""Testes da spec onboarding-valoria — cobertura, limites e endpoint.

Garante que data/onboarding.json cobre TODAS as regiões/classes/raças dos
JSONs canônicos (drift ruidoso por construção) e respeita limites de campo.
"""

import json
import os

import pytest

from gamedata import CLASSES, load_json_data

ONBOARDING = load_json_data("onboarding.json")
ORIGINS = load_json_data("origins.json")


def test_onboarding_has_top_level_keys():
    assert set(ONBOARDING.keys()) >= {"world_intro", "regions", "classes", "races"}


def test_onboarding_world_intro():
    intro = ONBOARDING["world_intro"]
    assert intro["title"]
    assert len(intro["paragraphs"]) == 3
    assert all(isinstance(p, str) and p for p in intro["paragraphs"])


def test_onboarding_regions_cover_origins():
    origin_ids = {r["id"] for r in ORIGINS["regions"]}
    card_ids = set(ONBOARDING["regions"].keys())
    assert origin_ids == card_ids, (
        f"faltando card: {origin_ids - card_ids}; órfão: {card_ids - origin_ids}"
    )


def test_onboarding_classes_cover_classes_json():
    class_names = set(CLASSES.keys())
    card_names = set(ONBOARDING["classes"].keys())
    assert class_names == card_names, (
        f"faltando card: {class_names - card_names}; órfão: {card_names - class_names}"
    )


def test_onboarding_races_cover_origins():
    origin_ids = {r["id"] for r in ORIGINS["races"]}
    card_ids = set(ONBOARDING["races"].keys())
    assert origin_ids == card_ids, (
        f"faltando card: {origin_ids - card_ids}; órfão: {card_ids - origin_ids}"
    )


def test_onboarding_field_limits():
    def check_card(kind: str, key: str, card: dict, extra: dict):
        assert card.get("tagline"), f"{kind}/{key} sem tagline"
        assert len(card["tagline"]) <= 90, f"{kind}/{key} tagline > 90"
        assert card.get("description"), f"{kind}/{key} sem description"
        assert len(card["description"]) <= 400, f"{kind}/{key} description > 400"
        for field, limit in extra.items():
            assert card.get(field), f"{kind}/{key} sem {field}"
            assert len(card[field]) <= limit, f"{kind}/{key} {field} > {limit}"

    for key, card in ONBOARDING["regions"].items():
        check_card("region", key, card, {"hook": 200})
    for key, card in ONBOARDING["classes"].items():
        check_card("class", key, card, {"playstyle": 160})
    for key, card in ONBOARDING["races"].items():
        check_card("race", key, card, {})


def test_onboarding_region_name_bonus_sync():
    """name/bonus dos cards de região espelham origins.json (anti-drift)."""
    origins = {r["id"]: r for r in ORIGINS["regions"]}
    for rid, card in ONBOARDING["regions"].items():
        assert card["name"] == origins[rid]["name"], f"region/{rid} name divergente"
        assert card["bonus"] == origins[rid]["bonus"], f"region/{rid} bonus divergente"


def test_onboarding_race_name_sync():
    origins = {r["id"]: r for r in ORIGINS["races"]}
    for rid, card in ONBOARDING["races"].items():
        assert card["name"] == origins[rid]["name"], f"race/{rid} name divergente"


def test_onboarding_no_hidden_entities():
    """R9 — cards não citam entidades cujo doc do Codex é hidden/secret."""
    import glob

    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "codex")
    hidden_names: set[str] = set()
    for path in glob.glob(os.path.join(base, "**", "*.md"), recursive=True):
        with open(path, encoding="utf-8") as f:
            head = f.read(2000)
        if "visibility: hidden" in head or "visibility: secret" in head:
            for line in head.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                    if name and len(name) > 3:
                        hidden_names.add(name)
    blob = json.dumps(ONBOARDING, ensure_ascii=False)
    for name in hidden_names:
        assert name not in blob, f"onboarding.json cita entidade hidden/secret: {name}"


def test_api_onboarding_endpoint():
    from fastapi.testclient import TestClient

    from api import app

    client = TestClient(app)
    resp = client.get("/data/onboarding")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {"world_intro", "regions", "classes", "races"}
    assert len(body["regions"]) == len(ORIGINS["regions"])
    assert len(body["classes"]) == len(CLASSES)
    assert len(body["races"]) == len(ORIGINS["races"])
