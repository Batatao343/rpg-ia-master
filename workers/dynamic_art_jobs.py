"""Worker de imagem: provider uma vez, pipeline Python e BlobStore privado."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from collections.abc import Callable, Mapping
from uuid import UUID

from PIL import Image

from infrastructure.contracts import BlobMetadata
from infrastructure.ports import ImageGenerationInput, ImageGenerator
from observability.telemetry import log_event
from services.art_brief import (
    MAX_REFERENCES,
    load_art_profile,
    quality_for,
    reference_kind,
    render_image_prompt,
)
from services.art_similarity import dhash64, dhash64_mirrored, hamming
from services.asset_pipeline import object_key, process_image
from services.usage_metering import safe_provider_usage

# Conjunto curado de referências canônicas. Fica em ``data/`` (incluído no bundle do worker);
# ``web/public/**`` é excluído do bundle da Vercel (vercel.json), então não serve de fonte.
ART_REFS_DIR = Path(__file__).resolve().parents[1] / "data" / "art_refs"
REFERENCE_MAX_SIDE = 1024


def _to_png(raw: bytes) -> bytes:
    """Reencoda (webp/png) para PNG, que é o que o ``/images/edits`` recebe; lado ≤ 1024."""
    with Image.open(BytesIO(raw)) as image:
        image.load()
        image = image.convert("RGB")
        image.thumbnail((REFERENCE_MAX_SIDE, REFERENCE_MAX_SIDE))
        out = BytesIO()
        image.save(out, "PNG")
    return out.getvalue()


def _canon_file(kind: str, name: str) -> Path | None:
    path = ART_REFS_DIR / kind / f"{name}.webp"
    return path if path.is_file() else None


def _location_candidates(location_id: str, catalog: Mapping) -> list[str]:
    from services.reputation import region_id_of

    fallback = str((catalog.get("location_fallbacks") or {}).get(location_id) or "")
    return [value for value in (location_id, fallback, region_id_of(location_id)) if value]


def _load_reference(
    asset_id: str, *, blob_store, catalog: Mapping, approved_portrait_key: Callable | None
) -> bytes | None:
    prefix, _, name = asset_id.partition(":")
    if prefix == "race":
        path = _canon_file("race", name) if name.replace("_", "").isalnum() else None
        return _to_png(path.read_bytes()) if path else None
    if prefix == "location":
        for candidate in _location_candidates(name, catalog):
            path = (
                _canon_file("location", candidate) if candidate.replace("_", "").isalnum() else None
            )
            if path:
                return _to_png(path.read_bytes())
        return None
    if prefix == "player" and name == "approved_portrait" and approved_portrait_key is not None:
        key = approved_portrait_key()
        if not key:
            return None
        with blob_store.open(key) as handle:
            return _to_png(handle.read())
    return None


def resolve_reference_payloads(
    brief: Mapping,
    *,
    blob_store,
    generation: Mapping | None = None,
    catalog: Mapping | None = None,
    approved_portrait_key: Callable[[], str | None] | None = None,
) -> tuple[tuple[str, ...], tuple[bytes, ...]]:
    """R10/R13: (ids efetivamente carregados, bytes PNG), no máximo ``MAX_REFERENCES``.

    Referência ausente/ilegível não derruba o job: segue só com texto e loga o *tipo*."""
    if catalog is None:
        from services.visual_catalog import load_visual_catalog

        catalog = load_visual_catalog()
    used: list[str] = []
    payloads: list[bytes] = []
    for asset_id in brief.get("reference_asset_ids") or []:
        if len(payloads) >= MAX_REFERENCES:
            break
        try:
            payload = _load_reference(
                str(asset_id),
                blob_store=blob_store,
                catalog=catalog,
                approved_portrait_key=approved_portrait_key,
            )
        except Exception as exc:
            log_event(
                "art",
                "reference_missing",
                level="warning",
                ref_kind=str(asset_id).partition(":")[0],
                reason=type(exc).__name__,
            )
            continue
        if payload is None:
            log_event(
                "art",
                "reference_missing",
                level="warning",
                ref_kind=str(asset_id).partition(":")[0],
                reason="not_found",
            )
            continue
        used.append(str(asset_id))
        payloads.append(payload)
    return tuple(used), tuple(payloads)


def canon_similarity(
    output: bytes, used: tuple[str, ...], payloads: tuple[bytes, ...], *, threshold: int
) -> dict:
    """R12: dHash da saída vs. cada referência canônica (o retrato do herói não entra)."""
    out_hash, out_mirror = dhash64(output), dhash64_mirrored(output)
    distances = [
        min(hamming(out_hash, ref_hash), hamming(out_mirror, ref_hash))
        for asset_id, payload in zip(used, payloads, strict=True)
        if reference_kind(asset_id) != "identity"
        for ref_hash in (dhash64(payload),)
    ]
    if not distances:
        return {"similar_to_canon": False, "canon_min_hamming": None}
    closest = min(distances)
    flagged = closest < threshold
    if flagged:
        log_event(
            "art", "canon_similarity", level="warning", min_hamming=closest, threshold=threshold
        )
    return {"similar_to_canon": flagged, "canon_min_hamming": closest}


def generate_dynamic_art_job(
    *,
    generator: ImageGenerator,
    blob_store,
    generation: dict,
    owner_id: UUID,
    game_id: UUID,
    asset_id: UUID,
    usage_sink: Callable[[str, dict], None] | None = None,
    admission: Callable[[], dict] | None = None,
    approved_portrait_key: Callable[[], str | None] | None = None,
) -> dict:
    if admission is None:
        from infrastructure.contracts import Conflict

        raise Conflict("image_quote confirmation and reservation required")
    generation = admission()
    brief = dict(generation["private_brief"])
    used, payloads = resolve_reference_payloads(
        brief,
        blob_store=blob_store,
        generation=generation,
        approved_portrait_key=approved_portrait_key,
    )
    generated = generator.generate(
        ImageGenerationInput(
            render_image_prompt(brief, used),
            generation["model"],
            brief["size"],
            payloads,
            quality_for(brief),
        )
    )
    safe_usage = safe_provider_usage(generated.usage, image_generated=True)
    if usage_sink is not None:
        usage_sink(generated.model, safe_usage)
    similarity = {"similar_to_canon": False, "canon_min_hamming": None}
    try:
        threshold = int(load_art_profile().get("canon_similarity_min_hamming", 10))
        similarity = canon_similarity(generated.payload, used, payloads, threshold=threshold)
    except Exception as exc:  # o guard só sinaliza; nunca derruba uma geração já paga (D4)
        log_event("art", "canon_similarity_failed", level="warning", error_type=type(exc).__name__)
    variants = process_image(generated.payload)
    refs = []
    for variant in variants:
        key = object_key(
            owner_id=owner_id,
            game_id=game_id,
            asset_kind="epic"
            if generation["subject_type"] == "scene"
            else generation["subject_type"],
            entity_id=generation["subject_id"],
            asset_id=asset_id,
            variant=variant.variant,
            sha256=variant.sha256,
        )
        refs.append(
            blob_store.put(
                key,
                BytesIO(variant.payload),
                BlobMetadata(
                    owner_id,
                    game_id,
                    variant.mime_type,
                    variant.sha256,
                    str(generation["trigger_kind"]),
                    len(variant.payload),
                ),
            )
        )
        refs[-1] = (refs[-1], variant)
    return {
        "status": "ready",
        "asset_id": str(asset_id),
        "variants": [
            {
                "key": ref.key,
                "sha256": ref.sha256,
                "bytes": ref.size_bytes,
                "variant": variant.variant,
                "mime_type": variant.mime_type,
                "width": variant.width,
                "height": variant.height,
            }
            for ref, variant in refs
        ],
        "provider_request_id_hash": hashlib.sha256(
            str(generated.provider_request_id or "").encode()
        ).hexdigest()[:16],
        "model": generated.model,
        "usage": safe_usage,
        **similarity,
    }
