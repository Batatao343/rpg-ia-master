from uuid import uuid4
import pytest

from infrastructure.file_blob import FileBlobStore
from tests.fakes.fake_image_generator import FakeImageGenerator
from workers.dynamic_art_jobs import generate_dynamic_art_job
import workers.dynamic_art_jobs as art_jobs


def test_worker_fake_gera_duas_variantes_privadas_sem_provider_real(tmp_path):
    generator = FakeImageGenerator()
    owner, game, asset = uuid4(), uuid4(), uuid4()
    generation = {
        "private_brief": {
            "subject": "Iria", "canon": ["Valoria"], "player_description": "adulta",
            "composition": ["natural spine"], "exclusions": ["no text"],
            "reference_asset_ids": [], "profile_version": "v1", "size": "1024x1536",
        },
        "model": "gpt-image-2-2026-04-21", "subject_type": "player",
        "subject_id": "player", "trigger_kind": "player_portrait",
    }
    result = generate_dynamic_art_job(
        generator=generator, blob_store=FileBlobStore(tmp_path), generation=generation,
        owner_id=owner, game_id=game, asset_id=asset,
    )
    assert generator.calls == 1 and result["status"] == "ready"
    assert len(result["variants"]) == 2
    assert all((tmp_path / row["key"]).exists() for row in result["variants"])


def test_usage_is_published_before_image_processing_can_fail(tmp_path, monkeypatch):
    published = []

    def fail_processing(_payload):
        raise RuntimeError("failed after provider response")

    monkeypatch.setattr(art_jobs, "process_image", fail_processing)
    generation = {
        "private_brief": {
            "subject": "Iria", "canon": ["Valoria"], "player_description": "adulta",
            "composition": ["natural spine"], "exclusions": ["no text"],
            "reference_asset_ids": [], "profile_version": "v1", "size": "1024x1536",
        },
        "model": "gpt-image-2-2026-04-21", "subject_type": "player",
        "subject_id": "player", "trigger_kind": "player_portrait",
    }
    with pytest.raises(RuntimeError, match="failed after provider"):
        generate_dynamic_art_job(
            generator=FakeImageGenerator(), blob_store=FileBlobStore(tmp_path),
            generation=generation, owner_id=uuid4(), game_id=uuid4(), asset_id=uuid4(),
            usage_sink=lambda model, usage: published.append((model, usage)),
        )
    assert published == [("gpt-image-2-2026-04-21", {
        "image_units": 1, "provider_cost_usd": "0",
    })]
