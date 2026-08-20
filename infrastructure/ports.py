"""Portas de provider que não pertencem ao núcleo LLM textual."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ImageGenerationInput:
    prompt: str
    model: str
    size: str
    reference_payloads: tuple[bytes, ...] = ()


@dataclass(frozen=True)
class GeneratedImage:
    payload: bytes
    mime_type: str
    provider_request_id: str | None
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class ImageGenerator(Protocol):
    def generate(self, request: ImageGenerationInput) -> GeneratedImage: ...
