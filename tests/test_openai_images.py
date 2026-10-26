"""Adapter HTTP do GPT Image 2 (SPEC-326 R15/R16); httpx mockado, zero rede."""

import base64

import pytest

import infrastructure.openai_images as images
from infrastructure.ports import ImageGenerationInput


class _Response:
    status_code = 200
    text = ""
    headers = {"x-request-id": "r1"}

    def json(self):
        return {"data": [{"b64_json": base64.b64encode(b"png").decode()}], "usage": {}}


@pytest.fixture
def posts(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _Response()

    monkeypatch.setattr(images.httpx, "post", fake_post)
    return calls


def _generator():
    return images.OpenAIImageGenerator("sk-test")


def test_quality_enviada_generations_e_edits(posts):
    request = ImageGenerationInput("p", "gpt-image-2", "1024x1536", (), "medium")
    _generator().generate(request)
    url, kwargs = posts[0]
    assert url.endswith("/images/generations") and kwargs["json"]["quality"] == "medium"

    with_refs = ImageGenerationInput("p", "gpt-image-2", "1024x1536", (b"a", b"b"), "medium")
    _generator().generate(with_refs)
    url, kwargs = posts[1]
    assert url.endswith("/images/edits") and kwargs["data"]["quality"] == "medium"
    assert [name for name, _ in kwargs["files"]] == ["image[]", "image[]"]


def test_sem_quality_nao_envia_campo(posts):
    _generator().generate(ImageGenerationInput("p", "gpt-image-2", "1024x1536", ()))
    assert "quality" not in posts[0][1]["json"]


def test_idempotency_key_muda_com_quality_e_referencias(posts):
    base = ImageGenerationInput("p", "m", "1x1", (b"a",), "low")
    for variant in (
        base,
        ImageGenerationInput("p", "m", "1x1", (b"b",), "low"),
        ImageGenerationInput("p", "m", "1x1", (b"a",), "medium"),
    ):
        _generator().generate(variant)
    keys = {call[1]["headers"]["Idempotency-Key"] for call in posts}
    assert len(keys) == 3


def test_timeout_worker_300():
    assert images.IMAGE_PROVIDER_TIMEOUT_S >= 300.0
    assert _generator().timeout >= 300.0
    # O worker passa a constante (verificado com o handler real em
    # tests/test_art_worker_reconciliation.py, que captura o kwarg ``timeout``).
    import workers.run_worker as run_worker

    assert run_worker.IMAGE_PROVIDER_TIMEOUT_S == images.IMAGE_PROVIDER_TIMEOUT_S
