"""Server-side Jev decision backend. No gameplay route imports this module.

Wire contract checked against https://docs.typesafe.ai/api on 2026-10-05.
Only the narrow DecisionState DTO may cross the provider boundary.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections.abc import Callable, Mapping
from typing import Annotated, Literal, Protocol
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_HEADER_ID = re.compile(r"[A-Za-z0-9._:-]{1,100}\Z")
_GLOBAL_INFLIGHT = threading.BoundedSemaphore(8)


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionState(_ClosedModel):
    """Small, explicit input for decision experiments; never a GameState dump."""

    action: str = Field(min_length=1, max_length=4000)
    location_id: str | None = Field(default=None, max_length=128)
    in_combat: bool = False
    active_npc: str | None = Field(default=None, max_length=128)


class ChoiceQuestion(_ClosedModel):
    type: Literal["choice"] = "choice"
    instructions: str = Field(min_length=1, max_length=1800)
    criteria: dict[str, str]

    @model_validator(mode="after")
    def valid_criteria(self) -> ChoiceQuestion:
        if not 2 <= len(self.criteria) <= 255:
            raise ValueError("choice requires 2–255 options")
        if any(not _IDENTIFIER.fullmatch(key) or not value for key, value in self.criteria.items()):
            raise ValueError("choice criteria must have identifier keys and descriptions")
        _check_criteria_size(self.criteria)
        return self


class NoulQuestion(_ClosedModel):
    type: Literal["noul"] = "noul"
    instructions: str = Field(min_length=1, max_length=1800)
    criteria: dict[str, str] | None = None

    @model_validator(mode="after")
    def valid_criteria(self) -> NoulQuestion:
        if self.criteria is not None:
            if set(self.criteria) != {"true", "false"} or not all(self.criteria.values()):
                raise ValueError("noul criteria must describe true and false")
            _check_criteria_size(self.criteria)
        return self


class ScoreQuestion(_ClosedModel):
    type: Literal["score"] = "score"
    instructions: str = Field(min_length=1, max_length=1800)
    criteria: list[str]

    @model_validator(mode="after")
    def valid_criteria(self) -> ScoreQuestion:
        if not 2 <= len(self.criteria) <= 10 or not all(self.criteria):
            raise ValueError("score requires 2–10 described levels")
        _check_criteria_size(self.criteria)
        return self


Question = Annotated[ChoiceQuestion | NoulQuestion | ScoreQuestion, Field(discriminator="type")]


def _wire_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _check_criteria_size(criteria: object) -> None:
    if len(_wire_json(criteria)) > 2000:
        raise ValueError("serialized criteria exceeds 2000 characters")


class DecisionRequest(_ClosedModel):
    state: DecisionState
    questions: dict[str, Question]
    model: str = Field(default="jev-latest", min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_request(self) -> DecisionRequest:
        if not 1 <= len(self.questions) <= 8:
            raise ValueError("request requires 1–8 questions")
        if any(not _IDENTIFIER.fullmatch(name) for name in self.questions):
            raise ValueError("question names must be identifiers of at most 64 characters")
        if len(_wire_json(self.state.model_dump(exclude_none=True))) > 8000:
            raise ValueError("serialized state exceeds 8000 characters")
        return self

    def wire_body(self) -> dict[str, object]:
        # frozen=True does not freeze nested maps/lists; validate their current
        # content and serialize a detached copy before it reaches the network.
        snapshot = DecisionRequest.model_validate(self.model_dump(mode="python"))
        return {
            "model": snapshot.model,
            "state": snapshot.state.model_dump(exclude_none=True),
            "questions": {
                name: question.model_dump(exclude_none=True)
                for name, question in snapshot.questions.items()
            },
        }


class _StrictWireModel(_ClosedModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ChoiceAnswer(_StrictWireModel):
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class NoulAnswer(_StrictWireModel):
    type: Literal["noul"]
    noul: float = Field(ge=0, le=1, allow_inf_nan=False)


class ScoreAnswer(_StrictWireModel):
    type: Literal["score"]
    score: float = Field(ge=0, allow_inf_nan=False)
    legend: dict[str, str]
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


Answer = Annotated[ChoiceAnswer | NoulAnswer | ScoreAnswer, Field(discriminator="type")]


class Usage(_StrictWireModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class _WireResponse(_StrictWireModel):
    model: str = Field(min_length=1)
    answers: dict[str, Answer]
    usage: Usage | None = None


class DecisionResult(_ClosedModel):
    model: str
    answers: dict[str, Answer]
    usage: Usage | None
    correlation_id: str
    latency_ms: int
    cost_usd: float | None = None


class DecisionTelemetry(_ClosedModel):
    correlation_id: str
    model: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    error_code: str | None


class DecisionBackend(Protocol):
    def decide(
        self,
        request: DecisionRequest,
        *,
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> DecisionResult: ...


class JevError(Exception):
    code = "jev_error"


class JevConfigurationError(JevError):
    code = "configuration"


class JevAuthenticationError(JevError):
    code = "authentication"


class JevCreditsError(JevError):
    code = "insufficient_credits"


class JevValidationError(JevError):
    code = "remote_validation"


class JevRateLimitError(JevError):
    code = "rate_limit"


class JevUpstreamError(JevError):
    code = "upstream"


class JevTimeoutError(JevError):
    code = "timeout"


class JevTransportError(JevError):
    code = "transport"


class JevResponseError(JevError):
    code = "invalid_response"


class JevHTTPError(JevError):
    code = "http_error"


_STATUS_ERRORS: Mapping[int, type[JevError]] = {
    401: JevAuthenticationError,
    402: JevCreditsError,
    422: JevValidationError,
    429: JevRateLimitError,
}


def _api_key(explicit: str | None) -> str:
    load_dotenv(override=False)
    canonical = os.getenv("TYPESAFE_API_KEY") or None
    compatibility = os.getenv("JEVMODEL_API_KEY") or None
    legacy = os.getenv("JEV_API_KEY") or None
    if canonical and compatibility and canonical != compatibility:
        raise JevConfigurationError("Conflicting TypeSafe key variables")
    if legacy:
        raise JevConfigurationError("Rename JEV_API_KEY to TYPESAFE_API_KEY")
    configured = canonical or compatibility
    if explicit and configured and explicit != configured:
        raise JevConfigurationError("Conflicting explicit Jev key")
    key = explicit or configured
    if not key:
        raise JevConfigurationError("TYPESAFE_API_KEY or JEVMODEL_API_KEY is required")
    return key


def _validate_answer(request: DecisionRequest, raw: _WireResponse) -> None:
    if set(raw.answers) != set(request.questions):
        raise JevResponseError("Jev response question set mismatch")
    for name, question in request.questions.items():
        answer = raw.answers[name]
        if question.type != answer.type:
            raise JevResponseError("Jev response answer type mismatch")
        if isinstance(question, ChoiceQuestion) and isinstance(answer, ChoiceAnswer):
            if answer.choice not in question.criteria or set(answer.probabilities) != set(
                question.criteria
            ):
                raise JevResponseError("Jev choice outside requested criteria")
            if any(not 0 <= probability <= 1 for probability in answer.probabilities.values()):
                raise JevResponseError("Jev choice probability outside [0, 1]")
            if abs(sum(answer.probabilities.values()) - 1.0) > 0.02:
                raise JevResponseError("Jev choice probabilities do not sum to one")
            if answer.probabilities[answer.choice] < max(answer.probabilities.values()):
                raise JevResponseError("Jev choice differs from highest probability")
        if isinstance(question, ScoreQuestion) and isinstance(answer, ScoreAnswer):
            levels = {str(index): description for index, description in enumerate(question.criteria)}
            if answer.score > len(question.criteria) - 1:
                raise JevResponseError("Jev score outside requested rubric")
            if answer.legend != levels or set(answer.probabilities) != set(levels):
                raise JevResponseError("Jev score levels differ from requested rubric")
            if any(not 0 <= probability <= 1 for probability in answer.probabilities.values()):
                raise JevResponseError("Jev score probability outside [0, 1]")
            if abs(sum(answer.probabilities.values()) - 1.0) > 0.02:
                raise JevResponseError("Jev score probabilities do not sum to one")
            weighted_score = sum(
                int(level) * probability for level, probability in answer.probabilities.items()
            )
            if abs(answer.score - weighted_score) > 0.05:
                raise JevResponseError("Jev score differs from weighted probabilities")


class JevDecisionBackend:
    """Bounded synchronous HTTP adapter; caller owns the logical retry key."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 8.0,
        total_timeout_seconds: float = 18.0,
        max_retries: int = 1,
        client: httpx.Client | None = None,
        telemetry_hook: Callable[[DecisionTelemetry], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._key = _api_key(api_key)
        if timeout_seconds <= 0 or total_timeout_seconds <= 0 or not 0 <= max_retries <= 2:
            raise ValueError("Invalid Jev timeout/retry settings")
        self._timeout = timeout_seconds
        self._total_timeout = total_timeout_seconds
        self._max_retries = max_retries
        self._client = client or httpx.Client()
        self._owns_client = client is None
        self._telemetry_hook = telemetry_hook
        self._sleep = sleep
        self._inflight = threading.Lock()
        self._closed = False

    def close(self) -> None:
        self._closed = True
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> JevDecisionBackend:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _emit(self, event: DecisionTelemetry) -> None:
        if self._telemetry_hook is not None:
            try:
                self._telemetry_hook(event)
            except Exception:
                pass  # Observability must not turn a typed decision into an error.

    def _call_with_deadline(
        self,
        body: dict[str, object],
        headers: dict[str, str],
        snapshot: DecisionRequest,
        remaining: float,
    ) -> tuple[int, _WireResponse | None]:
        # HTTPX's timeout is per network operation, not a whole-request deadline.
        # A daemon worker bounds transport, JSON parsing and validation. After
        # timeout its slot stays quarantined until it exits; one backend can
        # never pile up calls, and the global cap bounds abandoned peers.
        if self._closed:
            raise JevTransportError("Jev backend is closed")
        if not self._inflight.acquire(blocking=False):
            raise JevTransportError("Previous Jev request is still active")
        if not _GLOBAL_INFLIGHT.acquire(blocking=False):
            self._inflight.release()
            raise JevTransportError("Jev in-flight limit reached")
        completed = threading.Event()
        outcome: list[tuple[int, _WireResponse | None] | Exception] = []

        def send() -> None:
            try:
                response = self._client.post(
                    ENDPOINT,
                    json=body,
                    headers=headers,
                    timeout=httpx.Timeout(min(self._timeout, remaining)),
                )
                if response.status_code == 200:
                    try:
                        raw = _WireResponse.model_validate(response.json())
                        _validate_answer(snapshot, raw)
                    except JevResponseError:
                        raise
                    except (ValueError, ValidationError, TypeError):
                        raise JevResponseError("Jev response failed validation") from None
                    outcome.append((200, raw))
                else:
                    outcome.append((response.status_code, None))
            except Exception as exc:
                outcome.append(exc)
            finally:
                _GLOBAL_INFLIGHT.release()
                self._inflight.release()
                completed.set()

        try:
            threading.Thread(target=send, daemon=True, name="jev-decision-http").start()
        except RuntimeError:
            _GLOBAL_INFLIGHT.release()
            self._inflight.release()
            raise JevTransportError("Jev worker could not start") from None
        if not completed.wait(remaining):
            raise JevTimeoutError("Jev total timeout exceeded")
        result = outcome[0]
        if isinstance(result, Exception):
            raise result
        return result

    def decide(
        self,
        request: DecisionRequest,
        *,
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
    ) -> DecisionResult:
        if not isinstance(request, DecisionRequest):
            raise TypeError("request must be a DecisionRequest")
        if self._closed:
            raise JevTransportError("Jev backend is closed")
        key = idempotency_key or uuid4().hex
        correlation = correlation_id or uuid4().hex
        if not _HEADER_ID.fullmatch(key) or not _HEADER_ID.fullmatch(correlation):
            raise ValueError("Invalid Jev request identifier")
        body = request.wire_body()
        snapshot = DecisionRequest.model_validate(body)
        start = time.monotonic()
        deadline = start + self._total_timeout
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Idempotency-Key": key,
            "X-Correlation-ID": correlation,
        }
        error: JevError | None = None
        for attempt in range(self._max_retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                error = JevTimeoutError("Jev total timeout exceeded")
                break
            try:
                status, raw = self._call_with_deadline(body, headers, snapshot, remaining)
            except JevTimeoutError as exc:
                error = exc
                break
            except httpx.TimeoutException:
                error = JevTimeoutError("Jev request timed out")
                break
            except httpx.RequestError:
                error = JevTransportError("Jev transport failed")
                break
            except JevError as exc:
                error = exc
                break
            except Exception:
                error = JevTransportError("Jev transport failed")
                break
            if status == 200:
                if time.monotonic() >= deadline:
                    error = JevTimeoutError("Jev total timeout exceeded")
                    break
                assert raw is not None
                elapsed = round((time.monotonic() - start) * 1000)
                result = DecisionResult(
                    model=raw.model,
                    answers=raw.answers,
                    usage=raw.usage,
                    correlation_id=correlation,
                    latency_ms=elapsed,
                )
                self._emit(
                    DecisionTelemetry(
                        correlation_id=correlation,
                        model=raw.model,
                        latency_ms=elapsed,
                        input_tokens=raw.usage.input_tokens if raw.usage else None,
                        output_tokens=raw.usage.output_tokens if raw.usage else None,
                        cost_usd=None,
                        error_code=None,
                    )
                )
                return result
            error_type = _STATUS_ERRORS.get(status)
            if error_type is None:
                error_type = JevUpstreamError if 500 <= status <= 599 else JevHTTPError
            error = error_type(f"Jev HTTP {status}")
            if status not in (429, 529) or attempt >= self._max_retries:
                break
            pause = min(0.5 * (2**attempt), max(0, deadline - time.monotonic()))
            if pause > 0:
                self._sleep(pause)
        assert error is not None
        self._emit(
            DecisionTelemetry(
                correlation_id=correlation,
                model=None,
                latency_ms=round((time.monotonic() - start) * 1000),
                input_tokens=None,
                output_tokens=None,
                cost_usd=None,
                error_code=error.code,
            )
        )
        raise error
