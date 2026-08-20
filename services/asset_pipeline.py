"""Validação e normalização Python de imagens dinâmicas."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

from PIL import Image, UnidentifiedImageError


MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 24_000_000
VARIANTS = {"full": (1536, 1536), "thumb": (384, 384)}


@dataclass(frozen=True)
class ProcessedAsset:
    variant: str
    payload: bytes
    sha256: str
    width: int
    height: int
    mime_type: str = "image/webp"


def safe_entity_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    if not normalized or len(normalized) > 80:
        raise ValueError("entity_id inválido")
    return normalized


def object_key(*, owner_id: UUID, game_id: UUID, asset_kind: str, entity_id: str,
               asset_id: UUID, variant: str, sha256: str) -> str:
    if variant not in VARIANTS or asset_kind not in {"player","npc","location","item","monster","epic"}:
        raise ValueError("tipo/variante inválido")
    entity = safe_entity_id(entity_id)
    return (f"users/{owner_id}/games/{game_id}/{asset_kind}/{entity}/"
            f"{asset_id}.{variant}.{sha256[:12]}.webp")


def process_image(payload: bytes) -> list[ProcessedAsset]:
    if not payload or len(payload) > MAX_SOURCE_BYTES:
        raise ValueError("imagem vazia ou grande demais")
    try:
        with Image.open(BytesIO(payload)) as source:
            source.load()
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("imagem excede limite de pixels")
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("formato de imagem não permitido")
            clean = source.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("conteúdo não é uma imagem válida") from exc
    result: list[ProcessedAsset] = []
    for variant, bounds in VARIANTS.items():
        image = clean.copy()
        image.thumbnail(bounds, Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="WEBP", quality=88, method=6, exif=b"")
        data = output.getvalue()
        result.append(ProcessedAsset(
            variant, data, hashlib.sha256(data).hexdigest(), image.width, image.height,
        ))
    return result


def can_serve(*, visibility: str, revealed: bool) -> bool:
    if visibility not in {"public", "hidden", "secret"}:
        raise ValueError("visibility inválida")
    return visibility == "public" or revealed
