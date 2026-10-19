"""Bounded, private STT routing. Audio lives only in one temporary directory.

The service never sends an action to the game, stores a transcript or logs a
provider body. Unknown network effects are recorded and held for reconciliation.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import UUID

import httpx

from services.speech_pricing import is_definitive_no_charge, speech_event
from services.usage_metering import UsageEvent

MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_TRANSCRIPT_CHARS = 8000
SUPPORTED_MIMES = {"audio/wav", "audio/x-wav", "audio/webm", "audio/ogg", "audio/mp4"}
_URLS = {"groq": "https://api.groq.com/openai/v1/audio/transcriptions",
         "openai": "https://api.openai.com/v1/audio/transcriptions"}
_KEYS = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}


class SpeechError(ValueError):
    def __init__(self, code: str, status: int = 502):
        self.code, self.status = code, status
        super().__init__(code)


class SpeechFinance(Protocol):
    def begin(self, operation_id: UUID, request_hash: str, candidates: list["Candidate"]) -> None: ...
    def admit(self, ordinal: int, candidate: "Candidate") -> None: ...
    def finish(self, events: list[UsageEvent], success: bool) -> str: ...


@dataclass(frozen=True)
class Candidate:
    provider: str
    model: str


@dataclass(frozen=True)
class ProviderReading:
    status: int
    text: object
    usage: dict


class SpeechProvider(Protocol):
    async def transcribe(self, candidate: Candidate, audio: Path) -> ProviderReading: ...


class HttpSpeechProvider:
    """Fixed HTTPS origins; bounded response and total timeout; no SDK retries."""
    async def transcribe(self, candidate: Candidate, audio: Path) -> ProviderReading:
        data = {"model": candidate.model, "language": "pt", "temperature": "0",
                "response_format": "verbose_json" if candidate.provider == "groq" else "json"}
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
            with audio.open("rb") as stream:
                async with client.stream("POST", _URLS[candidate.provider],
                                         headers={"Authorization": "Bearer " + os.environ[_KEYS[candidate.provider]]},
                                         data=data, files={"file": ("recording.wav", stream, "audio/wav")}) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 128 * 1024:
                            raise SpeechError("provider_response_limit")
                    import json
                    try:
                        parsed = json.loads(body)
                    except (ValueError, UnicodeError):
                        parsed = {}
                    if not isinstance(parsed, dict):
                        parsed = {}
                    usage = parsed.get("usage")
                    safe = {}
                    if isinstance(usage, dict):
                        if usage.get('type') == 'duration':
                            safe['type'], safe['seconds'] = 'duration', usage.get('seconds')
                        for name in ("input_tokens", "output_tokens"):
                            safe[name] = usage.get(name)
                        details = usage.get("input_token_details")
                        if isinstance(details, dict):
                            safe["audio_tokens"] = details.get("audio_tokens")
                            safe["text_tokens"] = details.get("text_tokens")
                    return ProviderReading(response.status_code, parsed.get("text"), safe)


class SpeechCircuit:
    """Local provider circuit; spend protection remains durable in the wallet."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, tuple[int, float]] = {}

    def available(self, candidate: Candidate) -> bool:
        with self._lock:
            return self._state.get(candidate.provider + ":" + candidate.model, (0, 0))[1] <= time.monotonic()

    def record(self, candidate: Candidate, success: bool) -> None:
        key = candidate.provider + ":" + candidate.model
        with self._lock:
            count = 0 if success else self._state.get(key, (0, 0))[0] + 1
            self._state[key] = (count, time.monotonic() + 60 if count >= 3 else 0)
        if count == 3:
            from observability.telemetry import log_event
            log_event("stt", "circuit_opened", level="warning", provider=candidate.provider,
                      model=candidate.model, failures=count, open_seconds=60)


SPEECH_CIRCUIT = SpeechCircuit()


def configured_candidates() -> list[Candidate]:
    candidates = [Candidate("groq", os.getenv("RPG_SPEECH_GROQ_MODEL", "whisper-large-v3-turbo")),
                  Candidate("openai", os.getenv("RPG_SPEECH_OPENAI_MODEL", "gpt-4o-mini-transcribe"))]
    if any(not re.fullmatch(r"[A-Za-z0-9._/-]{1,150}", c.model) for c in candidates):
        raise SpeechError("speech_configuration", 503)
    from observability.telemetry import log_provider_attempt
    chosen: list[Candidate] = []
    for c in candidates:
        if not os.getenv(_KEYS[c.provider]):
            continue
        if not SPEECH_CIRCUIT.available(c):
            log_provider_attempt("stt", c.provider, c.model, "circuit_open")
        elif not _allowed_by_switches(c, primary=candidates[0]):
            log_provider_attempt("stt", c.provider, c.model, "kill_switch")
        else:
            chosen.append(c)
    return chosen


def _allowed_by_switches(candidate: Candidate, *, primary: Candidate) -> bool:
    """SPEC-196 kill switches: expensive STT fallback and per-model switches (fail-safe: allow)."""
    try:
        from services.kill_switches import STT_FALLBACK, get_switches, model_key
        switches = get_switches()
        if not switches.is_enabled(model_key(candidate.provider, candidate.model)):
            return False
        return candidate == primary or switches.is_enabled(STT_FALLBACK)
    except Exception as exc:
        from observability.telemetry import log_event
        log_event("stt", "switch_check_failed", level="warning", error_type=type(exc).__name__,
                  provider=candidate.provider, model=candidate.model)
        return True


def canonical_mime(value: str) -> str:
    mime = value.split(";", 1)[0].strip().lower()
    if mime not in SUPPORTED_MIMES:
        raise SpeechError("audio_mime", 415)
    return mime


def _wav_duration(audio: Path) -> Decimal:
    try:
        with wave.open(str(audio), "rb") as wav:
            channels, width, rate, frames = (wav.getnchannels(), wav.getsampwidth(),
                                              wav.getframerate(), wav.getnframes())
            if (wav.getcomptype() != "NONE" or channels not in (1, 2) or width not in (1, 2, 3, 4)
                    or not 8000 <= rate <= 48000 or frames <= 0):
                raise SpeechError("audio_invalid", 422)
            duration = Decimal(frames) / rate
            if duration > 60:
                raise SpeechError("audio_duration", 422)
            if len(wav.readframes(frames + 1)) != frames * width * channels:
                raise SpeechError("audio_truncated", 422)
            return duration
    except (wave.Error, EOFError, OSError) as exc:
        raise SpeechError("audio_invalid", 422) from exc


def prepare_audio(payload: bytes, mime: str, directory: Path) -> tuple[Path, Decimal]:
    """Validate magic and actual decoded PCM frames, never client duration/header metadata."""
    if not 0 < len(payload) <= MAX_AUDIO_BYTES:
        raise SpeechError("audio_bytes", 413)
    mime = canonical_mime(mime)
    magic = {"audio/webm": payload.startswith(b"\x1aE\xdf\xa3"),
             "audio/ogg": payload.startswith(b"OggS"),
             "audio/mp4": len(payload) >= 12 and payload[4:8] == b"ftyp"}
    if mime in {"audio/wav", "audio/x-wav"}:
        if payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
            raise SpeechError("audio_invalid", 422)
        original = directory / "upload.wav"
        original.write_bytes(payload)
        duration = _wav_duration(original)
        audio = directory / "recording.wav"
        # Fresh container contains exactly the PCM frames that were validated.
        # Extra RIFF chunks, metadata and alternate data chunks never reach STT.
        with wave.open(str(original), 'rb') as source, wave.open(str(audio), 'wb') as target:
            target.setparams(source.getparams())
            target.writeframes(source.readframes(source.getnframes()))
        return audio, duration
    if not magic.get(mime):
        raise SpeechError("audio_invalid", 422)
    original = directory / "upload.bin"
    original.write_bytes(payload)
    audio = directory / "recording.wav"
    decoder = os.getenv("RPG_SPEECH_FFMPEG", "ffmpeg")
    try:
        subprocess.run([decoder, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                        "-i", str(original), "-map", "0:a:0", "-vn", "-t", "61", "-ac", "1",
                        "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(audio)],
                       check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except FileNotFoundError as exc:
        raise SpeechError("audio_decoder_unavailable", 503) from exc
    except (subprocess.SubprocessError, OSError) as exc:
        raise SpeechError("audio_invalid", 422) from exc
    return audio, _wav_duration(audio)


async def transcribe_audio(payload: bytes, mime: str, operation_id: UUID,
                           finance: SpeechFinance, *, provider: SpeechProvider | None = None,
                           candidates: list[Candidate] | None = None,
                           circuit: SpeechCircuit | None = None) -> dict:
    import hashlib

    from observability.telemetry import log_provider_attempt
    circuit = circuit or SPEECH_CIRCUIT
    candidates = configured_candidates() if candidates is None else candidates
    events: list[UsageEvent] = []
    text = None
    begun = False
    with tempfile.TemporaryDirectory(prefix="rpg-speech-") as temp:
        audio, duration = prepare_audio(payload, mime, Path(temp))
        if not candidates:
            raise SpeechError("speech_unavailable", 503)
        request_hash = hashlib.sha256((canonical_mime(mime) + ":" +
                                      hashlib.sha256(payload).hexdigest()).encode()).hexdigest()
        try:
            finance.begin(operation_id, request_hash, candidates)
            begun = True
            for ordinal, candidate in enumerate(candidates):
                finance.admit(ordinal, candidate)
                # Ticket precedes dispatch. Every ticket receives a usage event,
                # including cancellation, timeout and internal transport failure.
                event = speech_event(operation_id, ordinal, candidate.provider, candidate.model,
                                     "unknown", {})
                started = time.perf_counter()
                outcome, status = "transport_error", None
                try:
                    async with asyncio.timeout(22):
                        reading = await (provider or HttpSpeechProvider()).transcribe(candidate, audio)
                    success = (200 <= reading.status < 300 and isinstance(reading.text, str)
                               and 0 < len(reading.text.strip()) <= MAX_TRANSCRIPT_CHARS)
                    if is_definitive_no_charge(reading.status):
                        # SPEC-236 R5: HTTP 4xx/429 received -> provider rejected, no charge.
                        event = speech_event(operation_id, ordinal, candidate.provider,
                                             candidate.model, "rejected", {},
                                             definitive_no_charge=True)
                    else:
                        event = speech_event(operation_id, ordinal, candidate.provider, candidate.model,
                                             "success" if success else "error", reading.usage,
                                             duration=duration if 200 <= reading.status < 300 and candidate.provider == "groq" else None)
                    status = reading.status
                    outcome = ("success" if success else "http_error"
                               if not 200 <= reading.status < 300 else "invalid_response")
                    circuit.record(candidate, success)
                    if success:
                        text = reading.text.strip()
                        break
                except (SpeechError, httpx.HTTPError, TimeoutError) as exc:
                    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                        outcome = "timeout"
                    elif isinstance(exc, SpeechError):
                        outcome = "invalid_response"
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status is not None:
                        outcome = "http_error"
                    circuit.record(candidate, False)
                finally:
                    events.append(event)
                    log_provider_attempt(
                        "stt", candidate.provider, candidate.model, outcome, http_status=status,
                        latency_ms=(time.perf_counter() - started) * 1000, attempt=ordinal + 1,
                        fell_back=ordinal > 0,
                        cost_basis="exact" if outcome == "success" else "unknown")
            if text is None:
                raise SpeechError("speech_provider_failed")
        finally:
            if begun:
                billing = finance.finish(events, text is not None)
    return {"operation_id": str(operation_id), "text": text, "billing_status": billing}
