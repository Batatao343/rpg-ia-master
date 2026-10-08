"""Worker de imagem: provider uma vez, pipeline Python e BlobStore privado."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Callable
from uuid import UUID

from infrastructure.contracts import BlobMetadata
from infrastructure.ports import ImageGenerationInput, ImageGenerator
from services.art_brief import render_image_prompt
from services.asset_pipeline import object_key, process_image
from services.usage_metering import safe_provider_usage


def generate_dynamic_art_job(*, generator: ImageGenerator, blob_store, generation: dict,
                             owner_id: UUID, game_id: UUID, asset_id: UUID,
                             usage_sink: Callable[[str, dict], None] | None = None) -> dict:
    brief = dict(generation["private_brief"])
    generated = generator.generate(ImageGenerationInput(
        render_image_prompt(brief), generation["model"], brief["size"], ()))
    safe_usage = safe_provider_usage(generated.usage, image_generated=True)
    if usage_sink is not None:
        usage_sink(generated.model, safe_usage)
    variants = process_image(generated.payload)
    refs = []
    for variant in variants:
        key = object_key(
            owner_id=owner_id, game_id=game_id,
            asset_kind="epic" if generation["subject_type"] == "scene" else generation["subject_type"],
            entity_id=generation["subject_id"], asset_id=asset_id,
            variant=variant.variant, sha256=variant.sha256,
        )
        refs.append(blob_store.put(
            key, BytesIO(variant.payload), BlobMetadata(
                owner_id, game_id, variant.mime_type, variant.sha256,
                str(generation["trigger_kind"]), len(variant.payload)),
        ))
        refs[-1] = (refs[-1], variant)
    return {
        "status": "ready", "asset_id": str(asset_id),
        "variants": [{"key": ref.key, "sha256": ref.sha256,
                      "bytes": ref.size_bytes, "variant": variant.variant,
                      "mime_type": variant.mime_type, "width": variant.width,
                      "height": variant.height}
                     for ref, variant in refs],
        "provider_request_id_hash": hashlib.sha256(
            str(generated.provider_request_id or "").encode()).hexdigest()[:16],
        "model": generated.model,
        "usage": safe_usage,
    }
