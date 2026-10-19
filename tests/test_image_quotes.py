"""SPEC-188 strict API/automatic-offer and mandatory dispatch admission gates."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from infrastructure.contracts import Conflict
from services.art_triggers import ArtGenerationRequest
from tests.fakes.fake_image_generator import FakeImageGenerator
from workers.dynamic_art_jobs import generate_dynamic_art_job


def test_unconfirmed_worker_input_never_calls_even_fake_provider():
    generator = FakeImageGenerator()
    with pytest.raises(Conflict, match="confirmation"):
        generate_dynamic_art_job(
            generator=generator,
            blob_store=None,
            generation={},
            owner_id=uuid4(),
            game_id=uuid4(),
            asset_id=uuid4(),
        )
    assert generator.calls == 0


@pytest.mark.parametrize(
    "kind,subject", [("npc_first_appearance", "npc"), ("arc_epic_moment", "scene")]
)
def test_automatic_triggers_only_offer_without_any_runtime_wallet_or_job(
    monkeypatch, kind, subject
):
    import api
    import infrastructure.runtime

    monkeypatch.setattr(
        infrastructure.runtime,
        "get_runtime",
        lambda: pytest.fail("automatic offer touched infrastructure"),
    )
    state = {"game_id": str(uuid4()), "art_arc_budgets": {}, "art_generation_ledger": []}
    trigger = ArtGenerationRequest(kind, "subject", subject, "subject", "arc", "action")
    first = api._enqueue_art_generation(state, trigger, {"subject": "private"})
    assert api._enqueue_art_generation(state, trigger, {})["offer_id"] == first["offer_id"]
    assert first["status"] == "offered" and len(state["art_offers"]) == 1
    assert state["art_arc_budgets"] == {} and state["art_generation_ledger"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {"action_id": "legacy"},
        {"action_id": str(uuid4()), "quote_id": str(uuid4()), "confirmed": False},
        {"action_id": str(uuid4()), "quote_id": str(uuid4()), "confirmed": 1},
        {
            "action_id": str(uuid4()),
            "quote_id": str(uuid4()),
            "confirmed": True,
            "credits_milli": 1,
        },
        {
            "action_id": str(uuid4()),
            "quote_id": str(uuid4()),
            "confirmed": True,
            "model": "cheaper",
        },
        {
            "action_id": str(uuid4()),
            "quote_id": str(uuid4()),
            "confirmed": True,
            "reformulation": True,
        },
    ],
)
def test_confirm_requires_quote_and_explicit_confirmation_and_forbids_client_prices(payload):
    import api

    with TestClient(api.app) as client:
        assert client.post(f"/game/{uuid4()}/art/confirm", json=payload).status_code == 422


def test_legacy_enabled_images_fail_closed_without_wallet(monkeypatch):
    import api

    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    with TestClient(api.app) as client:
        result = client.post(f"/game/{uuid4()}/art/quote", json={})
    assert result.status_code == 503 and result.json()["detail"] == "image_quotes_unavailable"


@pytest.mark.parametrize(
    "field", ["credits_milli", "pricing_version", "model", "owner_id", "private_brief"]
)
def test_quote_input_rejects_financial_and_private_client_fields(field):
    import api

    with TestClient(api.app) as client:
        assert client.post(f"/game/{uuid4()}/art/quote", json={field: "forged"}).status_code == 422


def test_public_refs_support_all_image_types_without_private_quote_or_brief():
    import api

    ids = [str(uuid4()) for _ in range(3)]
    state = {
        "art_generation_ledger": [
            {
                "generation_id": generation_id,
                "subject_type": kind,
                "subject_id": kind,
                "image_quote_id": "private quote",
                "private_brief": "secret prompt",
            }
            for generation_id, kind in zip(ids, ["player", "npc", "scene"])
        ],
        "art_offers": [{"offer_id": "offer", "type": "npc", "brief": "private"}],
    }
    public = api._public_art_refs(state)
    assert [row["type"] for row in public["art_generations"]] == ["player", "npc", "scene"]
    assert "private" not in str(public) and "secret" not in str(public)
    assert public["art_offers"] == [{"offer_id": "offer", "type": "npc"}]
