"""Adapter HTTP do GPT Image 2 pinado; sem fallback para outro modelo."""

from __future__ import annotations

import base64
import hashlib

import httpx

from infrastructure.contracts import InfrastructureError
from infrastructure.ports import GeneratedImage, ImageGenerationInput


class ImageGenerationRefused(InfrastructureError):
    pass


class OpenAIImageGenerator:
    def __init__(self, api_key: str, *, base_url: str = "https://api.openai.com/v1",
                 timeout: float = 120.0) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY ausente")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, request: ImageGenerationInput) -> GeneratedImage:
        request_key = hashlib.sha256(
            f"{request.model}\n{request.size}\n{request.prompt}".encode()
        ).hexdigest()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": request_key,
        }
        if request.reference_payloads:
            files = [("image[]", (f"reference-{index}.png", payload, "image/png"))
                     for index, payload in enumerate(request.reference_payloads)]
            response = httpx.post(
                f"{self.base_url}/images/edits", headers=headers,
                data={"model": request.model, "prompt": request.prompt,
                      "size": request.size, "response_format": "b64_json"},
                files=files, timeout=self.timeout,
            )
        else:
            response = httpx.post(
                f"{self.base_url}/images/generations",
                headers={**headers, "Content-Type": "application/json"},
                json={"model": request.model, "prompt": request.prompt,
                      "size": request.size, "response_format": "b64_json"},
                timeout=self.timeout,
            )
        if response.status_code in (400, 403) and "safety" in response.text.lower():
            raise ImageGenerationRefused("imagem recusada pela política do provider")
        if response.status_code != 200:
            raise InfrastructureError(f"provider de imagem indisponível ({response.status_code})")
        payload = response.json()
        encoded = (payload.get("data") or [{}])[0].get("b64_json")
        if not encoded:
            raise InfrastructureError("provider não retornou bytes de imagem")
        return GeneratedImage(
            base64.b64decode(encoded, validate=True), "image/png",
            response.headers.get("x-request-id"), request.model,
            dict(payload.get("usage") or {}),
        )
