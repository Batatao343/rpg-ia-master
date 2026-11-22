"""SPEC-421: texto ao vivo na narracao mediada (frase a frase) com o filtro de segredo.

O narrador mediado (`interlocutor_reason` em `MEDIATION_REASONS`) nao streamava porque o guard
de segredo da SPEC-202 R11 so rodava no texto final. Agora o MESMO filtro (`find_unrevealed`,
no MESMO `scene_state`) vira o risco `mediation_secret` do `StreamGuard`: o stream so mostra
frases fechadas e para ANTES da primeira que o filtro final reprovaria. O filtro final nao muda.

Flag `RPG_MEDIATED_STREAM=off|shadow|on` (default `off`). `shadow` streama para um coletor
local (a API nao recebe nada) e mede; `on` entrega ao vivo.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal

MediatedStreamMode = Literal["off", "shadow", "on"]

_clock: Callable[[], float] = time.monotonic  # injetavel nos testes


def mediated_stream_mode() -> MediatedStreamMode:
    """`RPG_MEDIATED_STREAM` (default `off`; valor invalido = `off`)."""
    raw = os.getenv("RPG_MEDIATED_STREAM", "off").strip().lower()
    if raw in ("shadow", "on"):
        return raw  # type: ignore[return-value]
    return "off"


@dataclass(frozen=True)
class StreamPlan:
    stream: bool  # chama stream_structured?
    extra_risk: Callable[[str], str] | None  # gate de segredo (so mediacao)
    shadow: bool  # deltas vao ao coletor local


_NO_STREAM = StreamPlan(False, None, False)


def secret_gate(scene_state: Mapping) -> Callable[[str], str]:
    """frase -> 'mediation_secret' | ''; excecao -> 'check_error' (fail-closed)."""

    def gate(sentence: str) -> str:
        try:
            from services.secret_signatures import find_unrevealed

            return "mediation_secret" if find_unrevealed(sentence, scene_state) else ""  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 - log_fallback abaixo
            from observability.telemetry import log_fallback

            log_fallback("sse", "mediated_gate_failed", exc)
            return "check_error"

    return gate


def stream_plan(state: Mapping, scene_state: Mapping | None, *, rumor_nothing: bool) -> StreamPlan:
    """Nao mediado: `StreamPlan(not rumor_nothing, None, False)` (como antes). Mediado: `off`, sem
    `scene_state` ou boato sem achado -> sem stream; ambos so com sink ativo."""
    from services import interlocutor, narrative_sink

    if rumor_nothing:
        return _NO_STREAM
    if state.get("interlocutor_reason") not in interlocutor.MEDIATION_REASONS:
        return StreamPlan(True, None, False)
    mode = mediated_stream_mode()
    if mode == "off" or not scene_state or not narrative_sink.active():
        return _NO_STREAM  # sem sink (POST/CLI/playtest) o sink aninhado ligaria o stream sozinho
    return StreamPlan(True, secret_gate(scene_state), mode == "shadow")


class _Run:
    """O que o narrador mediado emitiu neste turno (nunca vai a state/save)."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.shown = ""
        self.held_rule = ""
        self.first_delta_ms: int | None = None
        self.t0 = _clock()

    def observe(self, kind: str, text: str) -> None:
        if kind == "delta":
            if self.first_delta_ms is None:
                self.first_delta_ms = int((_clock() - self.t0) * 1000)
            self.shown += text
        elif kind == "reset":
            self.shown = ""
        elif kind == "hold" and not self.held_rule:
            self.held_rule = text


_RUN: ContextVar[_Run | None] = ContextVar("rpg_mediated_run", default=None)


def narrate(plan: StreamPlan, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Chama `fn` (o `narrate_structured`) com `stream`/`extra_risk` do plano. Em mediacao, sob um
    sink aninhado que registra o mostrado (em `shadow` ele isola a API; em `on` repassa)."""
    from services import narrative_sink

    if plan.extra_risk is None:
        _RUN.set(None)  # um turno anterior que falhou nao contamina o `after_final` deste
        return fn(*args, stream=plan.stream, **kwargs)
    run = _Run("shadow" if plan.shadow else "on")
    run_token = _RUN.set(run)
    tap = narrative_sink.bind_tap(run.observe, forward=not plan.shadow)
    try:
        return fn(*args, stream=plan.stream, extra_risk=plan.extra_risk, **kwargs)
    except BaseException:
        _RUN.reset(run_token)
        raise
    finally:
        narrative_sink.unbind(tap)


def after_final(final_text: str, scene_state: Mapping, state: Mapping) -> None:
    """Se houve stream mediado neste turno, loga `sse.mediated_stream` (so tamanhos e regra)."""
    run = _RUN.get()
    if run is None:
        return
    _RUN.set(None)
    try:
        from observability.telemetry import log_event
        from services import narrative_sink
        from services.faction_display import conceal_text
        from services.secret_signatures import find_unrevealed

        final_vis = conceal_text(str(final_text), narrative_sink._conceal_map(state))
        shown = run.shown
        log_event(
            "sse",
            "mediated_stream",
            mode=run.mode,
            reason=str(state.get("interlocutor_reason") or ""),
            shown_len=len(shown),
            final_len=len(final_vis),
            would_replace=not final_vis.startswith(shown),
            replace_reason=narrative_sink.replace_reason(shown, final_vis),
            held_rule=run.held_rule,
            first_delta_ms=run.first_delta_ms,
            leak=find_unrevealed(shown, scene_state) is not None,  # type: ignore[arg-type]
        )
    except Exception as exc:  # noqa: BLE001 - log_fallback abaixo
        from observability.telemetry import log_fallback

        log_fallback("sse", "mediated_stream_log_failed", exc)
