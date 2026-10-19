"""SPEC-258: provider.attempt para STT, imagem e embeddings (offline, sem conteudo em log)."""
import asyncio
import io
import json
import wave
from uuid import uuid4

import httpx
import pytest

from observability import logging_setup
from observability.metrics import metrics
from services.speech_to_text import (Candidate, ProviderReading, SpeechCircuit, transcribe_audio)

GROQ = Candidate("groq", "whisper-large-v3-turbo")
OPENAI = Candidate("openai", "gpt-4o-mini-transcribe")
SENTINEL = "SENTINELA-SECRETA-XYZ"


@pytest.fixture(autouse=True)
def _logs():
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def _events(capsys, name):
    return [ln for ln in _lines(capsys) if ln.get("event") == name]


def _wav():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000)
    return buf.getvalue()


class _Finance:
    def begin(self, *a): pass
    def admit(self, *a): pass
    def finish(self, events, ok): return "settled"


class _Provider:
    def __init__(self, *results):
        self.results = list(results)

    async def transcribe(self, candidate, audio):
        r = self.results.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


def _run(provider, circuit=None):
    return asyncio.run(transcribe_audio(_wav(), "audio/wav", uuid4(), _Finance(), provider=provider,
                                        candidates=[GROQ, OPENAI], circuit=circuit or SpeechCircuit()))


def test_stt_fallback_logged(capsys):
    capsys.readouterr()
    _run(_Provider(ProviderReading(429, None, {}), ProviderReading(200, f"{SENTINEL} fala", {})))
    attempts = _events(capsys, "provider.attempt")
    assert [(a["provider"], a["outcome"], a["fell_back"], a["attempt"]) for a in attempts] == [
        ("groq", "http_error", False, 1), ("openai", "success", True, 2)]
    assert attempts[0]["http_status"] == 429 and attempts[0]["capability"] == "stt"
    assert SENTINEL not in json.dumps(attempts)


def test_stt_timeout_logged(capsys):
    capsys.readouterr()
    _run(_Provider(httpx.ReadTimeout("t"), ProviderReading(200, "ok", {})))
    attempts = _events(capsys, "provider.attempt")
    assert attempts[0]["outcome"] == "timeout" and attempts[0]["http_status"] is None
    assert attempts[1]["outcome"] == "success"


def test_stt_circuit_opened_logged(capsys):
    capsys.readouterr()
    circuit = SpeechCircuit()
    for _ in range(3):
        circuit.record(GROQ, False)
    ev = _events(capsys, "stt.circuit_opened")
    assert len(ev) == 1 and ev[0]["provider"] == "groq"


def test_stt_switch_check_failed_logged(capsys, monkeypatch):
    import services.kill_switches as ks
    from services.speech_to_text import _allowed_by_switches
    monkeypatch.setattr(ks, "get_switches", lambda: (_ for _ in ()).throw(RuntimeError(SENTINEL)))
    capsys.readouterr()
    assert _allowed_by_switches(GROQ, primary=GROQ) is True
    ev = _events(capsys, "stt.switch_check_failed")
    assert ev and ev[0]["error_type"] == "RuntimeError" and SENTINEL not in json.dumps(ev)


def test_image_http_status_logged(capsys, monkeypatch):
    from infrastructure.openai_images import OpenAIImageGenerator, ImageProviderError
    from infrastructure.ports import ImageGenerationInput
    transport = httpx.MockTransport(lambda r: httpx.Response(503, text=SENTINEL))
    monkeypatch.setattr(httpx, "post", lambda url, **kw: httpx.Client(transport=transport).post(
        url, json=kw.get("json"), headers=kw.get("headers")))
    capsys.readouterr()
    with pytest.raises(ImageProviderError) as info:
        OpenAIImageGenerator("k").generate(ImageGenerationInput(f"prompt {SENTINEL}", "gpt-image-2", "1024x1024", ()))
    assert info.value.http_status == 503
    attempts = _events(capsys, "provider.attempt")
    assert attempts[0]["capability"] == "image" and attempts[0]["http_status"] == 503
    assert attempts[0]["outcome"] == "http_error" and SENTINEL not in json.dumps(attempts)


def test_image_refusal_outcome(capsys, monkeypatch):
    from infrastructure.openai_images import OpenAIImageGenerator, ImageGenerationRefused
    from infrastructure.ports import ImageGenerationInput
    transport = httpx.MockTransport(lambda r: httpx.Response(400, text="safety violation"))
    monkeypatch.setattr(httpx, "post", lambda url, **kw: httpx.Client(transport=transport).post(
        url, json=kw.get("json"), headers=kw.get("headers")))
    capsys.readouterr()
    with pytest.raises(ImageGenerationRefused):
        OpenAIImageGenerator("k").generate(ImageGenerationInput("p", "gpt-image-2", "1024x1024", ()))
    assert _events(capsys, "provider.attempt")[0]["outcome"] == "refused"


def test_jina_retry_logged(capsys):
    from rag import _JinaEmbeddingsHTTPX
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(503, text=SENTINEL)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1]}],
                                          "usage": {"total_tokens": 3}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    emb = _JinaEmbeddingsHTTPX(api_key="k", model_name="jina-embeddings-v3", client=client)
    capsys.readouterr()
    assert emb.embed_query(f"texto {SENTINEL}") == [0.1]
    attempts = _events(capsys, "provider.attempt")
    assert [(a["outcome"], a["http_status"], a["attempt"]) for a in attempts] == [
        ("http_error", 503, 1), ("success", 200, 2)]
    assert all(a["capability"] == "embedding" for a in attempts)
    assert SENTINEL not in json.dumps(attempts)
    assert any("rpg_provider_attempts_total" in k for k in metrics.snapshot())


def test_no_audio_or_prompt_in_logs(capsys):
    capsys.readouterr()
    _run(_Provider(ProviderReading(200, f"{SENTINEL}", {})))
    raw = capsys.readouterr().out
    assert SENTINEL not in raw and "RIFF" not in raw
