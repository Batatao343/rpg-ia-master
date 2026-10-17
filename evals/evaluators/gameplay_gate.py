"""Deterministic oracles and evaluator for the desktop gameplay gate (SPEC-212).

The vertical journey J-V1 (``web/e2e/vertical-journey.spec.ts``) records a trace
of everything it observed (console events, per-turn ledger, surfaces, latency,
speakers, combat frames, gestures, axe results). The functions here turn such a
trace into a list of *problem classes* (``<oracle>:<kind>``); ``[]`` means the
oracle found nothing. They are owned by the ruler (not by the product) so a
product change can never move the goalposts.

* ``trace_problems(operation, data)`` - one oracle over one fixture/trace section.
* ``scan_trace(trace)`` - every oracle over a full J-V1 trace (the journey calls it
  through ``python -m evals.gameplay_scan`` with the trace on stdin).
* ``GameplayGateEvaluator`` - scores fixture-authored cases: the oracle must report
  exactly the labelled problem classes (known-good -> ``[]``, known-bad -> labelled),
  so a blind oracle is caught by the dataset, not by luck.

Secret scanning reuses the product signature list (``services.secret_signatures`` via
``services.memory_provenance.find_strict_unrevealed``) and the SPEC-206 leak oracle (``services.player_knowledge.assert_no_player_leak``),
imported lazily so the module stays importable without the product graph.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Iterable, Mapping

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult

OPERATIONS = (
    "console", "turns", "secrets", "xp", "latency", "speaker", "roster", "gesture", "a11y",
)
_XP_IN_PROSE = re.compile(r"\d+\s*xp\b|\[\s*resultado\s*\]", re.IGNORECASE)
_PERF_ORDER = ("ack_ms", "ttfmc_ms", "ttlt_ms", "state_ms")
_CLIENT_REQUIRED = ("ack_ms", "ttfmc_ms", "ttlt_ms", "state_ms")
_PHASES = ("router", "context", "narrator", "archivist", "persistence")
_FORBIDDEN_LATENCY_KEYS = ("ttft", "ttft_ms", "ttft_server_ms")
_BLOCKING_IMPACTS = frozenset({"serious", "critical"})
MAX_CLICKS_PER_ACTION = 2


def _num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --- console / request guard (R10) -------------------------------------------------------


def console_problems(data: Mapping[str, Any]) -> list[str]:
    """pageerror / console.error / failed request / HTTP>=500 / request outside the allowlist.

    ``allowlist`` is the explicit, versioned list of regexes the journey tolerates
    (empty by default). ``expected_origins`` lists the only origins a request may hit."""

    allow = [re.compile(item) for item in data.get("allowlist") or []]
    origins = tuple(data.get("expected_origins") or ())
    problems: list[str] = []
    for event in data.get("events") or []:
        kind = str(event.get("kind"))
        subject = " ".join(str(event[key]) for key in ("url", "text") if event.get(key))
        if any(rx.search(subject) for rx in allow):
            continue
        if kind == "pageerror":
            problems.append("console:pageerror")
        elif kind == "console_error":
            problems.append("console:console_error")
        elif kind == "request_failed":
            problems.append("console:request_failed")
        elif kind == "http_5xx":
            problems.append("console:http_5xx")
        elif kind == "request" and origins and not str(event.get("url", "")).startswith(origins):
            problems.append("console:unexpected_request")
    return sorted(set(problems))


# --- turn duplication / idempotent replay (R11) -----------------------------------------


def turn_problems(data: Mapping[str, Any]) -> list[str]:
    """Each distinct accepted ``action_id`` yields exactly one turn everywhere.

    ``turns`` is the submission ledger (replays and retries included);
    ``world_turn_delta`` / ``history_player_delta`` are measured over the whole journey;
    ``export_action_refs`` are the pseudonymised refs of the exported sessions."""

    problems: list[str] = []
    turns = list(data.get("turns") or [])
    accepted: dict[str, Mapping[str, Any]] = {}
    for turn in turns:
        aid = str(turn.get("action_id"))
        if not turn.get("accepted", True):
            continue
        first = accepted.get(aid)
        if first is None:
            accepted[aid] = turn
            continue
        # A replay of an accepted action must answer with the same receipt and
        # must not advance the turn counter or double the XP.
        if turn.get("receipt_id") != first.get("receipt_id"):
            problems.append("duplicate:replay_receipt_changed")
        if turn.get("world_turn_after") != first.get("world_turn_after"):
            problems.append("duplicate:replay_new_turn")
        if turn.get("xp_after") != first.get("xp_after"):
            problems.append("duplicate:replay_xp_doubled")
    distinct = len(accepted)
    if data.get("world_turn_delta") is not None and data["world_turn_delta"] != distinct:
        problems.append("duplicate:turn_count_mismatch")
    if data.get("history_player_delta") is not None and data["history_player_delta"] != distinct:
        problems.append("duplicate:history_mismatch")
    refs = data.get("export_action_refs")
    if refs is not None:
        if len(refs) != len(set(refs)):
            problems.append("duplicate:export_duplicate")
        if len(set(refs)) != distinct:
            problems.append("duplicate:export_count_mismatch")
    return sorted(set(problems))


# --- secret leak (R12) -------------------------------------------------------------------


def secret_problems(data: Mapping[str, Any]) -> list[str]:
    """Scan prose, tab panels, public API payloads and export text for unrevealed secrets.

    ``surfaces`` maps a surface name (``prose.t3``, ``tab.codex``, ``api.state``,
    ``export.sessions``...) to its text. ``revealed_secret_ids`` come from the export
    (``player_revealed_secret_ids``) and desarm only their own signature."""

    from services.memory_provenance import find_strict_unrevealed
    from services.player_knowledge import assert_no_player_leak

    revealed = [str(item) for item in data.get("revealed_secret_ids") or []]
    state: dict[str, Any] = dict(data.get("state") or {})
    # Only an accepted ``secret_revealed`` event desarms a signature (SPEC-206/234 strict rule);
    # prose and summaries never do.
    state.setdefault(
        "event_log", [{"type": "secret_revealed", "target_id": item} for item in revealed]
    )
    surfaces = data.get("surfaces") or {}
    problems: list[str] = []
    for text in surfaces.values():
        hit = find_strict_unrevealed(str(text), state)
        if hit:
            problems.append(f"secret:signature:{hit}")
    view = {
        "surfaces": dict(surfaces),
        "meta": {"counts": {k: 0 for k in ("locations", "factions", "characters", "creatures", "secrets")}},
        "locations": [], "factions": [], "characters": [], "creatures": [], "secrets": [],
    }
    if any(item.startswith("a:") for item in assert_no_player_leak(view, state)):
        problems.append("secret:hidden_entity")
    return sorted(set(problems))


# --- XP only in structured UI (R6) -----------------------------------------------------


def xp_problems(data: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for turn in data.get("turns") or []:
        if _XP_IN_PROSE.search(str(turn.get("prose") or "")):
            problems.append("xp:prose_number")
        outcome = turn.get("turn_outcome")
        if not isinstance(outcome, Mapping):
            if turn.get("ui_xp") not in (None, 0):
                problems.append("xp:ui_without_outcome")
            continue
        delta = outcome.get("xp_delta")
        if turn.get("ui_xp") is not None and turn["ui_xp"] != delta:
            problems.append("xp:ui_mismatch")
        if turn.get("ui_checked") and _num(delta) and delta > 0 and turn.get("ui_xp") is None:
            problems.append("xp:ui_missing")
        before, after = turn.get("xp_before"), turn.get("xp_after")
        if _num(before) and _num(after) and not outcome.get("level_delta"):
            if after - before != delta:
                problems.append("xp:state_delta_mismatch")
        if not outcome.get("receipt_id"):
            problems.append("xp:receipt_missing")
    return sorted(set(problems))


# --- latency presence with the SPEC-200 names (R13) -----------------------------------


def _client_problems(transport: str, client: Any) -> list[str]:
    if not isinstance(client, Mapping):
        return ["latency:client_missing"]
    problems: list[str] = []
    if any(key in client for key in _FORBIDDEN_LATENCY_KEYS):
        problems.append("latency:wrong_name")
    required = list(_CLIENT_REQUIRED) + (["first_phase_ms"] if transport == "stream" else [])
    if any(not _num(client.get(key)) for key in required):
        return problems + ["latency:client_mark_missing"]
    if any(client[key] < 0 for key in required):
        problems.append("latency:corrupt")
    sequence = [client[key] for key in _PERF_ORDER]
    if any(b < a for a, b in zip(sequence, sequence[1:])):
        problems.append("latency:corrupt")
    if transport == "stream" and not client["first_phase_ms"] <= client["ttfmc_ms"]:
        problems.append("latency:corrupt")
    return problems


def _server_problems(transport: str, server: Any) -> list[str]:
    if not isinstance(server, Mapping):
        return ["latency:server_missing"]
    problems: list[str] = []
    if any(key in server for key in _FORBIDDEN_LATENCY_KEYS):
        problems.append("latency:wrong_name")
    phases = server.get("phase_ms")
    if (
        server.get("transport") not in ("stream", "post")
        or "pseudo_streaming" not in server
        or not isinstance(phases, Mapping)
        or any(name not in phases for name in _PHASES)
    ):
        return problems + ["latency:server_field_missing"]
    if transport == "stream":
        # Stream turns must carry a closed first/last-content pair.
        if not (_num(server.get("ack_server_ms")) and _num(server.get("ttfmc_server_ms"))
                and _num(server.get("ttlt_server_ms"))):
            return problems + ["latency:null_server_stream"]
        if server["ttfmc_server_ms"] < 0 or server["ttlt_server_ms"] < server["ttfmc_server_ms"]:
            problems.append("latency:corrupt")
    # transport=post: ttfmc/ttlt server marks are null by contract.
    return problems


def latency_problems(data: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for turn in data.get("turns") or []:
        transport = turn.get("transport")
        if transport not in ("stream", "post"):
            problems.append("latency:transport_unknown")
            continue
        problems += _client_problems(transport, turn.get("client"))
        problems += _server_problems(transport, turn.get("server"))
    return sorted(set(problems))


def _nearest_rank(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def latency_baseline(turns: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """p50/p95 (nearest-rank) of client TTFMC/TTLT; ``indicative`` below 20 turns. No target."""

    rows = [t.get("client") for t in turns if isinstance(t.get("client"), Mapping)]
    out: dict[str, Any] = {"turns": len(rows), "indicative": len(rows) < 20, "baseline_only": True}
    for key in ("ttfmc_ms", "ttlt_ms"):
        values = [r[key] for r in rows if _num(r.get(key))]
        out[key] = {"p50": _nearest_rank(values, 0.5), "p95": _nearest_rank(values, 0.95)}
    return out


# --- interlocutor (R2) --------------------------------------------------------------


def speaker_problems(data: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for step in data.get("steps") or []:
        expected, actual = step.get("expected") or {}, step.get("actual") or {}
        if expected.get("kind") == "narrator" and actual.get("kind") == "npc":
            problems.append("speaker:npc_on_narrator_question")
        elif (expected.get("kind"), expected.get("id")) != (actual.get("kind"), actual.get("id")):
            problems.append("speaker:mismatch")
        if step.get("ui_label") is not None and step.get("ui_label") != step.get("expected_label"):
            problems.append("speaker:label_mismatch")
        if step.get("selector_in_dom"):
            problems.append("speaker:selector_present")
    return sorted(set(problems))


# --- encounter roster (R3) ----------------------------------------------------------


def roster_problems(data: Mapping[str, Any]) -> list[str]:
    """Participant ids shown in every frame stay equal to the frozen manifest until the outcome.

    A participant may leave the *active* set only by dying/fleeing (``final_status``), never by
    identity swap; ``frames`` are the id lists observed in the UI, in order, while combat was active."""

    manifest = set(data.get("manifest_ids") or [])
    problems: list[str] = []
    if not manifest:
        problems.append("roster:manifest_missing")
    for frame in data.get("frames") or []:
        shown = set(frame.get("ids") or [])
        gone = set(frame.get("resolved_ids") or [])
        if shown - manifest:
            problems.append("roster:identity_changed")
        if manifest - shown - gone:
            problems.append("roster:participant_vanished")
    outcome_ids = data.get("outcome_ids")
    if outcome_ids is not None and set(outcome_ids) != manifest:
        problems.append("roster:outcome_differs_from_manifest")
    return sorted(set(problems))


# --- gesture economy (R4) --------------------------------------------------------------


def gesture_problems(data: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for action in data.get("actions") or []:
        if action.get("confirm_dialogs", 0) > 0:
            problems.append("gesture:confirmation_dialog")
        limit = 1 if action.get("kind") in ("card_self", "basic_single") else MAX_CLICKS_PER_ACTION
        if action.get("clicks", 0) > limit:
            problems.append("gesture:too_many_clicks")
        if not action.get("shows_result"):
            problems.append("gesture:no_visible_result")
    return sorted(set(problems))


# --- a11y per tab (R15) --------------------------------------------------------------------


def a11y_problems(data: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for row in data.get("tabs") or []:
        impacts = {v.get("impact") for v in row.get("violations") or []}
        if impacts & _BLOCKING_IMPACTS:
            problems.append("a11y:serious_critical")
    return sorted(set(problems))


_ORACLES = {
    "console": console_problems,
    "turns": turn_problems,
    "secrets": secret_problems,
    "xp": xp_problems,
    "latency": latency_problems,
    "speaker": speaker_problems,
    "roster": roster_problems,
    "gesture": gesture_problems,
    "a11y": a11y_problems,
}


def trace_problems(operation: str, data: Mapping[str, Any]) -> list[str]:
    try:
        oracle = _ORACLES[operation]
    except KeyError:
        raise ValueError(f"unsupported gameplay_gate operation: {operation!r}") from None
    return oracle(data)


def scan_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Run every oracle that has a section in a full J-V1 trace."""

    problems: dict[str, list[str]] = {}
    for operation in OPERATIONS:
        section = trace.get(operation)
        if section is not None:
            found = trace_problems(operation, section)
            if found:
                problems[operation] = found
    latency = trace.get("latency") or {}
    return {
        "ok": not problems,
        "problems": problems,
        "baseline": latency_baseline(latency.get("turns") or []),
    }


class GameplayGateEvaluator:
    """Score the oracles against fixture-labelled traces."""

    evaluator_id = "gameplay_gate_contract"
    evaluator_version = EVALUATOR_VERSION

    def evaluate(
        self,
        case: EvalCase,
        actual: Any,
        *,
        product_sha: str,
        dataset_hash: str,
        seed: int,
    ) -> EvalCaseResult:
        if case.oracle != "gameplay_gate":
            raise ValueError(f"gameplay gate evaluator cannot evaluate {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        if not isinstance(case.input, dict) or not isinstance(case.expected, dict):
            raise ValueError("gameplay gate case requires object input and expected")
        if set(case.expected) != {"problem_classes"}:
            raise ValueError("gameplay gate expected must be exactly {problem_classes}")
        wanted = case.expected["problem_classes"]
        if not isinstance(wanted, list) or any(
            not isinstance(item, str) or ":" not in item for item in wanted
        ):
            raise ValueError("problem_classes must be <oracle>:<kind> strings")
        if not isinstance(actual, dict) or actual.get("operation") != case.input.get("operation"):
            raise ValueError("gameplay gate actual operation differs from the case")
        got = actual.get("problems")
        if not isinstance(got, list):
            raise ValueError("gameplay gate actual requires a problems list")
        got_sorted, want_sorted = sorted(set(map(str, got))), sorted(set(wanted))
        passed = got_sorted == want_sorted
        missed = float(bool(want_sorted) and not (set(want_sorted) & set(got_sorted)))
        false_alarm = float(not want_sorted and bool(got_sorted))
        diagnostics = (
            [] if passed else [f"oracle classes {got_sorted} differ from labelled {want_sorted}"]
        )
        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=passed,
            actual=actual,
            expected=case.expected,
            metric_values={
                "gameplay_oracle_accuracy": 1.0 if passed else 0.0,
                "gameplay_oracle_missed_defects": missed,
                "gameplay_oracle_false_alarms": false_alarm,
            },
            diagnostics=diagnostics,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            product_sha=product_sha,
            dataset_hash=dataset_hash,
            seed=seed,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )
