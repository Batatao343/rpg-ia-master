"""Adapter HTTP do GPT Image 2 pinado; sem fallback para outro modelo."""

from __future__ import annotations

import base64
import hashlib
import time

import httpx

from infrastructure.contracts import InfrastructureError
from infrastructure.ports import GeneratedImage, ImageGenerationInput
from observability.telemetry import log_provider_attempt


class ImageProviderError(InfrastructureError):
    """Falha do provider de imagem; ``http_status``/``outcome`` estruturados (SPEC-258 R4)."""

    def __init__(
        self, message: str, *, http_status: int | None = None, outcome: str = "http_error"
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.outcome = outcome


class ImageGenerationRefused(ImageProviderError):
    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message, http_status=http_status, outcome="refused")


#: SPEC-326 R16: /images/edits com referências passou de 300 s numa chamada real.
IMAGE_PROVIDER_TIMEOUT_S = 300.0


class OpenAIImageGenerator:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = IMAGE_PROVIDER_TIMEOUT_S,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY ausente")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, request: ImageGenerationInput) -> GeneratedImage:
        started = time.perf_counter()
        status: int | None = None
        outcome = "success"
        try:
            image, status = self._generate(request)
            return image
        except ImageProviderError as exc:
            status, outcome = exc.http_status, exc.outcome
            raise
        except httpx.TimeoutException:
            outcome = "timeout"
            raise
        except httpx.HTTPError:
            outcome = "transport_error"
            raise
        except Exception:
            outcome = "invalid_response"
            raise
        finally:
            log_provider_attempt(
                "image",
                "openai",
                request.model,
                outcome,
                http_status=status,
                latency_ms=(time.perf_counter() - started) * 1000,
                cost_basis="exact" if outcome == "success" else "unknown",
            )

    def _generate(self, request: ImageGenerationInput) -> tuple[GeneratedImage, int]:
        key_material = f"{request.model}\n{request.size}\n{request.quality or ''}\n{request.prompt}"
        digest = hashlib.sha256(key_material.encode())
        for payload in request.reference_payloads:
            digest.update(hashlib.sha256(payload).digest())
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": digest.hexdigest(),
        }
        fields = {"model": request.model, "prompt": request.prompt, "size": request.size}
        if request.quality:  # SPEC-326 R15: fixa o detalhe/custo nas duas rotas
            fields["quality"] = request.quality
        if request.reference_payloads:
            files = [
                ("image[]", (f"reference-{index}.png", payload, "image/png"))
                for index, payload in enumerate(request.reference_payloads)
            ]
            response = httpx.post(
                f"{self.base_url}/images/edits",
                headers=headers,
                data=fields,
                files=files,
                timeout=self.timeout,
            )
        else:
            response = httpx.post(
                f"{self.base_url}/images/generations",
                headers={**headers, "Content-Type": "application/json"},
                json=fields,
                timeout=self.timeout,
            )
        if response.status_code in (400, 403) and "safety" in response.text.lower():
            raise ImageGenerationRefused(
                "imagem recusada pela política do provider", http_status=response.status_code
            )
        if response.status_code != 200:
            raise ImageProviderError(
                f"provider de imagem indisponível ({response.status_code})",
                http_status=response.status_code,
            )
        payload = response.json()
        encoded = (payload.get("data") or [{}])[0].get("b64_json")
        if not encoded:
            raise ImageProviderError(
                "provider não retornou bytes de imagem", http_status=200, outcome="invalid_response"
            )
        return GeneratedImage(
            base64.b64decode(encoded, validate=True),
            "image/png",
            response.headers.get("x-request-id"),
            request.model,
            dict(payload.get("usage") or {}),
        ), response.status_code
