"""Explicit product adapters for deterministic eval suites.

Adapters compute only the candidate's actual output. Expected values always
come from immutable dataset fixtures and are never derived here.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
import copy
from io import StringIO
import json
import os
import tempfile
from typing import Any, Protocol

from evals.core.schemas import EvalCase


class AdapterError(RuntimeError):
    """A case cannot be executed by its registered product adapter."""


@dataclass(frozen=True)
class AdapterOutput:
    actual: Any
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdapterCase:
    """Candidate-facing case view that deliberately excludes expected/oracle."""

    id: str
    suite: str
    description: str
    fixture: str | None
    input: Any
    tags: tuple[str, ...]
    source: str
    created_from: str | None

    @classmethod
    def from_eval_case(cls, case: EvalCase) -> "AdapterCase":
        return cls(
            id=case.id,
            suite=case.suite,
            description=case.description,
            fixture=case.fixture,
            input=case.input,
            tags=tuple(case.tags),
            source=case.source,
            created_from=case.created_from,
        )


class EvalAdapter(Protocol):
    adapter_id: str

    def execute(self, case: AdapterCase) -> AdapterOutput: ...


class FixtureActualAdapter:
    """Calibration adapter whose candidate value is explicitly fixture-authored."""

    adapter_id = "fixture_actual"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict) or "actual" not in case.input:
            raise AdapterError("fixture_actual requires input.actual")
        return AdapterOutput(actual=case.input["actual"])


class PlaytestInvariantsAdapter:
    """Reuse the systemic invariant catalogue instead of cloning its rules."""

    adapter_id = "playtest_invariants"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict) or not isinstance(case.input.get("state"), dict):
            raise AdapterError("playtest_invariants requires input.state object")
        previous = case.input.get("prev_state")
        if previous is not None and not isinstance(previous, dict):
            raise AdapterError("input.prev_state must be an object or null")
        context = case.input.get("context")
        if context is not None and not isinstance(context, dict):
            raise AdapterError("input.context must be an object or null")

        from playtest.invariants import check_all

        violations = check_all(
            case.input["state"],
            previous,
            int(case.input.get("turn", 0)),
            context,
        )
        errors = sorted(
            violation.check_id for violation in violations if violation.severity == "error"
        )
        diagnostics = tuple(
            f"[{violation.severity}] {violation.check_id}: {violation.message}"
            for violation in violations
        )
        return AdapterOutput(actual=errors, diagnostics=diagnostics)


def _read_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return copy.deepcopy(current)


def _project(value: Any, paths: list[str]) -> dict[str, Any]:
    if not paths or any(not isinstance(path, str) or not path for path in paths):
        raise AdapterError("state_rules requires non-empty input.projection_paths")
    return {path: _read_path(value, path) for path in paths}


class StateRulesAdapter:
    """Execute deterministic product transitions and return declared projections."""

    adapter_id = "state_rules"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("state_rules requires object input")
        operation = case.input.get("operation")
        paths = case.input.get("projection_paths") or []

        if operation in {"apply_event", "replay_event"}:
            from services.event_processor import apply_event

            projection = copy.deepcopy(case.input.get("projection") or {})
            original = copy.deepcopy(projection)
            event = copy.deepcopy(case.input.get("event") or {})
            first = apply_event(event, projection)
            second = apply_event(event, first) if operation == "replay_event" else first
            return AdapterOutput(
                actual={
                    "projection": _project(second, paths),
                    "input_unchanged": projection == original,
                    "idempotent": first == second if operation == "replay_event" else None,
                }
            )

        if operation == "rule_action":
            from services.rule_engine import execute_action

            state = copy.deepcopy(case.input.get("state") or {})
            emitted = execute_action(
                copy.deepcopy(case.input.get("action") or {}),
                copy.deepcopy(case.input.get("event") or {}),
                state,
            )
            return AdapterOutput(
                actual={
                    "projection": _project(state, paths),
                    "emitted": [
                        {
                            key: row.get(key)
                            for key in ("type", "actor_id", "target_id", "payload", "source")
                        }
                        for row in emitted
                    ],
                }
            )

        if operation == "quest_reward":
            from services.quest_log import complete_quest_with_reward

            quest_id = str(case.input.get("quest_id") or "")
            turn = int(case.input.get("turn", 0))
            first, first_reward = complete_quest_with_reward(
                copy.deepcopy(case.input.get("quests") or []), quest_id, turn
            )
            second, second_reward = complete_quest_with_reward(first, quest_id, turn)
            return AdapterOutput(
                actual={
                    "quests": _project({"quests": second}, paths),
                    "first_reward": first_reward,
                    "second_reward": second_reward,
                    "idempotent": first == second,
                }
            )

        if operation == "death_choice":
            from services.checkpoints import resolve_death_choice

            result = resolve_death_choice(
                copy.deepcopy(case.input.get("state") or {}),
                str(case.input.get("choice") or ""),
                checkpoint=copy.deepcopy(case.input.get("checkpoint")),
                initial_state=copy.deepcopy(case.input.get("initial_state")),
            )
            return AdapterOutput(
                actual={
                    "state": _project(result, paths),
                    "event_types": [
                        row.get("type")
                        for row in result.get("event_log", [])
                        if isinstance(row, dict)
                    ],
                }
            )

        if operation == "transition_readiness":
            from services.actor_lifecycle import transition_readiness

            return AdapterOutput(
                actual=transition_readiness(copy.deepcopy(case.input.get("state") or {}))
            )

        if operation == "migrate_state":
            from persistence import migrate_state

            original = copy.deepcopy(case.input.get("state") or {})
            first = migrate_state(original)
            second = migrate_state(copy.deepcopy(first))
            return AdapterOutput(
                actual={
                    "state": _project(second, paths),
                    "input_unchanged": original == case.input.get("state"),
                    "idempotent": first == second,
                }
            )

        if operation == "persistence_roundtrip":
            import persistence

            state = copy.deepcopy(case.input.get("state") or {})
            old_saves_dir = persistence.SAVES_DIR
            old_profile = os.environ.get("RPG_RUNTIME_PROFILE")
            try:
                with tempfile.TemporaryDirectory(prefix="valoria-eval-save-") as directory:
                    persistence.SAVES_DIR = directory
                    os.environ["RPG_RUNTIME_PROFILE"] = "legacy"
                    saved = persistence.save_game_state(state)
                    loaded = persistence.load_game_state(
                        persistence.save_path(str(state.get("game_id") or ""))
                    )
            finally:
                persistence.SAVES_DIR = old_saves_dir
                if old_profile is None:
                    os.environ.pop("RPG_RUNTIME_PROFILE", None)
                else:
                    os.environ["RPG_RUNTIME_PROFILE"] = old_profile
            if not saved or not isinstance(loaded, dict):
                raise AdapterError("persistence roundtrip failed")
            return AdapterOutput(actual={"saved": saved, "state": _project(loaded, paths)})

        raise AdapterError(f"unknown state_rules operation: {operation!r}")


class RoutingAdapter:
    """Capture router/action structured output before any narrative generation."""

    adapter_id = "routing"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("routing requires object input")
        operation = case.input.get("operation", "route")

        if operation == "optional_entity_ref":
            from services.input_normalization import optional_entity_ref

            return AdapterOutput(actual={"normalized": optional_entity_ref(case.input.get("value"))})

        if operation == "decision_parse":
            from pydantic import ValidationError
            from agents.router import RouterDecision

            try:
                decision = RouterDecision.model_validate(case.input.get("decision"))
            except ValidationError as error:
                return AdapterOutput(
                    actual={
                        "valid": False,
                        "error_types": sorted({str(item["type"]) for item in error.errors()}),
                    },
                    diagnostics=("structured RouterDecision validation failed as expected",),
                )
            return AdapterOutput(
                actual={
                    "valid": True,
                    "route": decision.route.value,
                    "target": decision.target,
                    "loot_context": decision.loot_context,
                }
            )

        if operation != "route":
            raise AdapterError(f"unknown routing operation: {operation!r}")

        from langchain_core.messages import HumanMessage
        from agents.router import dm_router_node

        state = copy.deepcopy(case.input.get("state") or {})
        state["messages"] = [HumanMessage(content=str(case.input.get("action") or ""))]
        state.setdefault("world", {"current_location": "Aethelgard"})
        state.setdefault("npcs", {})
        state.setdefault("combat", None)
        # Product nodes emit decorative terminal output. It is outside the
        # scored contract and may contain glyphs unsupported by Windows CP1252.
        with redirect_stdout(StringIO()):
            decision = dm_router_node(state)
        route = decision.get("next")
        target = (
            decision.get("combat_target")
            if route == "combat_agent"
            else decision.get("active_npc_name")
            if route == "npc_actor"
            else None
        )
        return AdapterOutput(
            actual={
                "route": route,
                "target": target,
                "loot_context": decision.get("loot_source"),
                "combat_origin_hint": decision.get("combat_origin_hint"),
                "flee_attempt": bool(decision.get("combat_flee_attempt")),
                "flee_destination": decision.get("combat_flee_destination"),
            }
        )


class MemoryWriteAdapter:
    """Validate labelled memory facts without persisting or generating prose."""

    adapter_id = "memory_write"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("memory_write requires object input")
        operation = case.input.get("operation", "validate")
        if operation == "commit":
            from services.memory_provenance import commit_memory_facts

            ledger, promotions = commit_memory_facts(
                copy.deepcopy(case.input.get("existing") or []),
                copy.deepcopy(case.input.get("new") or []),
            )
            return AdapterOutput(actual={
                "texts": [str(row.get("text") or "") for row in ledger],
                "confidences": [str(row.get("confidence") or "") for row in ledger],
                "promotions": promotions,
            })
        if operation != "validate":
            raise AdapterError(f"unknown memory_write operation: {operation!r}")

        facts = case.input.get("facts")
        state = copy.deepcopy(case.input.get("state") or {})
        if not isinstance(facts, list):
            raise AdapterError("memory_write requires input.facts list")

        from services.memory_provenance import validate_memory_fact

        accepted_ids: list[str] = []
        rejected: list[dict[str, str]] = []
        for row in facts:
            if not isinstance(row, dict) or not str(row.get("id") or "").strip():
                raise AdapterError("each memory fact requires a stable id")
            fact_id = str(row["id"])
            record = copy.deepcopy(row.get("record") or {})
            accepted, reason = validate_memory_fact(record, state)
            if accepted is not None:
                accepted_ids.append(fact_id)
            else:
                rejected.append({"id": fact_id, "reason": str(reason or "unknown")})
        return AdapterOutput(actual={"accepted_ids": accepted_ids, "rejected": rejected})


class RetrievalAdapter:
    """Run the production FAISS ranking path with deterministic fixture vectors."""

    adapter_id = "memory_retrieval"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("memory_retrieval requires object input")
        candidates = case.input.get("candidates")
        query_vector = case.input.get("query_vector")
        if not isinstance(candidates, list) or not isinstance(query_vector, list):
            raise AdapterError("memory_retrieval requires candidates and query_vector lists")

        from langchain_community.vectorstores import FAISS
        from langchain_core.embeddings import Embeddings
        from rag import query_faiss_evidence

        class _FixtureEmbeddings(Embeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                raise RuntimeError("fixture vectors must be supplied explicitly")

            def embed_query(self, text: str) -> list[float]:
                return [float(value) for value in query_vector]

        k = int(case.input.get("k", 5))
        max_visibility = str(case.input.get("max_visibility") or "public")
        text_vectors: list[tuple[str, list[float]]] = []
        metadatas: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for row in candidates:
            if not isinstance(row, dict):
                raise AdapterError("each retrieval candidate must be an object")
            evidence_id = str(row.get("id") or "").strip()
            vector = row.get("vector")
            if not evidence_id or evidence_id in seen_ids:
                raise AdapterError("retrieval candidate IDs must be non-empty and unique")
            if not isinstance(vector, list) or len(vector) != len(query_vector):
                raise AdapterError(f"retrieval vector dimension mismatch: {evidence_id}")
            seen_ids.add(evidence_id)
            text_vectors.append((str(row.get("text") or ""), [float(value) for value in vector]))
            metadatas.append({
                "evidence_id": evidence_id,
                "source": str(row.get("source") or "fixture"),
                "visibility": str(row.get("visibility") or "public"),
                **dict(row.get("metadata") or {}),
            })
        db = FAISS.from_embeddings(
            text_vectors,
            _FixtureEmbeddings(),
            metadatas=metadatas,
        )
        evidence = query_faiss_evidence(
            db,
            [float(value) for value in query_vector],
            k=k,
            fetch_k=max(k, len(candidates)),
            max_visibility=max_visibility,
            source="fixture",
        )
        return AdapterOutput(actual={
            "ranked_ids": [item.id for item in evidence],
            "trace": [asdict(item) for item in evidence],
            "within_budget": True,
            "retrieval_metadata": {
                "provider": None,
                "embedding": "fixture-vectors",
                "index": "faiss-in-memory",
                "k": k,
                "max_visibility": max_visibility,
            },
        })


class ContextGroundingAdapter:
    """Assemble a bounded context and expose included/discarded evidence IDs."""

    adapter_id = "context_grounding"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("context_grounding requires object input")
        operation = case.input.get("operation", "assemble")
        rows = case.input.get("facts")
        if not isinstance(rows, list):
            raise AdapterError("context_grounding requires input.facts list")

        from services.context_builder import (
            ContextBudget,
            ScoredFact,
            active_memory_facts,
            assemble_pack,
        )

        if operation == "active_memory":
            labelled = [row for row in rows if isinstance(row, dict)]
            active = active_memory_facts(
                [copy.deepcopy(row.get("record") or {}) for row in labelled],
                current_turn=int(case.input.get("current_turn", 0)),
                state=copy.deepcopy(case.input.get("state") or {}),
            )
            active_texts = {str(row.get("text") or "") for row in active}
            rows = [
                {
                    "id": row.get("id"),
                    "text": (row.get("record") or {}).get("text"),
                    "score": row.get("score", 1.0),
                    "section": "session_memory",
                    "visibility": "public",
                }
                for row in labelled
                if str((row.get("record") or {}).get("text") or "") in active_texts
            ]
        elif operation != "assemble":
            raise AdapterError(f"unknown context_grounding operation: {operation!r}")

        facts = [
            ScoredFact(
                text=str(row.get("text") or ""),
                score=float(row.get("score", 0.0)),
                section=str(row.get("section") or ""),
                source_id=str(row.get("id") or ""),
                visibility=str(row.get("visibility") or "public"),
            )
            for row in rows
            if isinstance(row, dict)
        ]
        if len(facts) != len(rows) or any(not fact.source_id for fact in facts):
            raise AdapterError("every context fact requires a stable id")
        if len({fact.source_id for fact in facts}) != len(facts):
            raise AdapterError("context evidence IDs must be unique")
        token_budget = int(case.input.get("token_budget", 3500))
        pack = assemble_pack(
            facts,
            ContextBudget(
                max_tokens=token_budget,
                max_visibility=str(case.input.get("max_visibility") or "public"),
            ),
        )
        hard_cap = int(token_budget * 1.05)
        return AdapterOutput(actual={
            "ranked_ids": pack.evidence_ids,
            "discarded_evidence": pack.discarded_evidence,
            "total_tokens_est": pack.total_tokens_est,
            "hard_cap": hard_cap,
            "within_budget": pack.total_tokens_est <= hard_cap,
            "retrieval_metadata": {
                "provider": None,
                "embedding": None,
                "index": "context-budget-v1",
            },
        })


class GenerationBoundaryAdapter:
    """Observe the deterministic post-generation evidence guard.

    This does not score LLM generation quality; SPEC-171 owns that layer. It
    keeps the generation boundary visible without feeding prose into memory or
    retrieval metrics.
    """

    adapter_id = "generation_boundary"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("generation_boundary requires object input")
        from services.narrative_evidence import build_evidence, validate_narrative

        state = copy.deepcopy(case.input.get("state") or {})
        story_text = str(case.input.get("story_text") or "")
        result = validate_narrative(story_text, build_evidence(state), channel="message")
        return AdapterOutput(actual={
            "layer": "generate",
            "memory_context_scored": False,
            "accepted_text": result.text,
            "rejection_reasons": [str(row.get("reason")) for row in result.rejections],
        })


class NarrativeClaimAdapter:
    """Observe deterministic product contracts for fixture-labelled hard claims."""

    adapter_id = "narrative_claims"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("narrative_claims requires object input")
        operation = str(case.input.get("operation") or "narrative_guard")
        state = copy.deepcopy(case.input.get("state") or {})
        if not isinstance(state, dict):
            raise AdapterError("narrative claim state must be an object")

        accepted = True
        reasons: list[str] = []
        trace: dict[str, Any]
        if operation == "narrative_guard":
            from services.narrative_evidence import build_evidence, validate_narrative

            evidence = build_evidence(state)
            checked = validate_narrative(
                str(case.input.get("text") or ""), evidence, channel="eval"
            )
            reasons = sorted({str(row.get("reason")) for row in checked.rejections})
            accepted = not reasons
            trace = {
                "operation": operation,
                "turn": evidence.turn,
                "location_id": evidence.location_id,
                "accepted_event_ids": evidence.accepted_event_ids,
            }
            sanitized_text = checked.text
        elif operation == "scene_presence":
            from services.npc_layers import npcs_in_scene

            entity = str(case.input.get("entity") or "").strip()
            if not entity:
                raise AdapterError("scene_presence requires input.entity")
            present = entity in npcs_in_scene(state)
            asserted_present = bool(case.input.get("asserted_present", True))
            if asserted_present != present:
                accepted = False
                reasons = ["entity_out_of_scene" if asserted_present else "entity_in_scene"]
            trace = {"operation": operation, "entity": entity, "present": present}
        elif operation == "action_eligibility":
            from services.actor_lifecycle import evaluate_action

            decision = evaluate_action(state, str(case.input.get("action") or ""))
            asserted_success = bool(case.input.get("asserted_success", True))
            if asserted_success and not decision["allowed"]:
                accepted = False
                reasons = ["action_incompatible"]
            trace = {
                "operation": operation,
                "phase": decision["phase"],
                "code": decision["code"],
                "allowed": decision["allowed"],
            }
        elif operation == "conflict_lifecycle":
            from services.conflict_summary import validate_narrative_text

            summary = copy.deepcopy(case.input.get("summary") or {})
            if not isinstance(summary, dict):
                raise AdapterError("conflict_lifecycle requires input.summary object")
            checked = validate_narrative_text(summary, str(case.input.get("text") or ""))
            accepted = bool(checked["ok"])
            if not accepted:
                reasons = ["lifecycle_contradiction"]
            trace = {
                "operation": operation,
                "violation_count": len(checked["violations"]),
            }
        else:
            raise AdapterError(f"unsupported narrative claim operation: {operation}")

        actual = {
            "accepted": accepted,
            "rejection_reasons": reasons,
            "trace": trace,
        }
        if operation == "narrative_guard":
            actual["sanitized_text"] = sanitized_text
        return AdapterOutput(actual=actual)


_PLAYER_KNOWLEDGE_KEYS = {
    "locations": "id",
    "factions": "id",
    "characters": "name",
    "creatures": "id",
    "secrets": "entity_id",
}


def _apply_codex_mutation(codex: dict[str, Any], mutation: Any) -> None:
    """Apply one fixture-authored mutation to a projected Codex (oracle probes)."""

    if not isinstance(mutation, dict) or not isinstance(mutation.get("path"), str):
        raise AdapterError("player_knowledge mutation requires op and path")
    operation = mutation.get("op")
    parts = mutation["path"].split(".")
    parent: Any = codex
    for part in parts[:-1]:
        if isinstance(parent, list) and part.isdigit() and int(part) < len(parent):
            parent = parent[int(part)]
        elif isinstance(parent, dict) and part in parent:
            parent = parent[part]
        else:
            raise AdapterError(f"mutation path not found: {mutation['path']}")
    last = parts[-1]
    if isinstance(parent, list):
        if not last.isdigit() or int(last) >= len(parent):
            raise AdapterError(f"mutation path not found: {mutation['path']}")
        key: Any = int(last)
    elif isinstance(parent, dict):
        key = last
    else:
        raise AdapterError(f"mutation path not found: {mutation['path']}")
    value = copy.deepcopy(mutation.get("value"))
    if operation == "set":
        parent[key] = value
    elif operation == "append":
        target = parent[key] if isinstance(parent, list) or key in parent else None
        if not isinstance(target, list):
            raise AdapterError("append mutation requires a list target")
        target.append(value)
    elif operation == "delete":
        if isinstance(parent, dict) and key not in parent:
            raise AdapterError(f"mutation path not found: {mutation['path']}")
        del parent[key]
    else:
        raise AdapterError(f"unsupported player_knowledge mutation: {operation!r}")


class PlayerKnowledgeAdapter:
    """Observe the player-facing Codex projection and its leak oracle (SPEC-206)."""

    adapter_id = "player_knowledge"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("player_knowledge requires object input")
        operation = str(case.input.get("operation") or "project")
        state = copy.deepcopy(case.input.get("state"))
        if not isinstance(state, dict):
            raise AdapterError("player_knowledge requires input.state object")

        from services.discovery import player_codex
        from services.player_knowledge import CATEGORIES, assert_no_player_leak

        codex = player_codex(copy.deepcopy(state))
        if operation == "project":
            entries: dict[str, dict[str, Any]] = {}
            notes: dict[str, list[dict[str, Any]]] = {}
            for category in CATEGORIES:
                key_field = _PLAYER_KNOWLEDGE_KEYS[category]
                rows: dict[str, Any] = {}
                for entry in codex.get(category) or []:
                    if not isinstance(entry, dict):
                        raise AdapterError(f"non-object entry in {category}")
                    key = str(entry.get(key_field) or "")
                    if not key or key in rows:
                        raise AdapterError(f"missing or duplicate {category} key: {key!r}")
                    rows[key] = copy.deepcopy(entry.get("knowledge"))
                    entry_notes = [
                        {
                            "text": note.get("text"),
                            "knowledge_kind": note.get("knowledge_kind"),
                            "certainty": note.get("certainty"),
                            "source_kind": note.get("source_kind"),
                            "label": note.get("label"),
                        }
                        for note in entry.get("notes") or []
                        if isinstance(note, dict)
                    ]
                    if entry_notes:
                        notes[f"{category}/{key}"] = entry_notes
                entries[category] = rows
            meta = codex.get("meta") if isinstance(codex.get("meta"), dict) else {}
            actual = {
                "operation": operation,
                "entries": entries,
                "notes": notes,
                "counts": copy.deepcopy(meta.get("counts")),
                "list_lengths": {
                    category: len(codex.get(category) or []) for category in CATEGORIES
                },
                "redactions": meta.get("redactions"),
                "oracle_problems": sorted(assert_no_player_leak(codex, state)),
                "codex_json": json.dumps(codex, ensure_ascii=False, sort_keys=True),
            }
            return AdapterOutput(actual=actual)
        if operation == "oracle_mutation":
            mutations = case.input.get("mutations")
            if not isinstance(mutations, list):
                raise AdapterError("oracle_mutation requires input.mutations list")
            for mutation in mutations:
                _apply_codex_mutation(codex, mutation)
            return AdapterOutput(actual={
                "operation": operation,
                "oracle_problems": sorted(assert_no_player_leak(codex, state)),
            })
        raise AdapterError(f"unsupported player_knowledge operation: {operation}")


class AdapterRegistry:
    """Small explicit suite registry; unknown suites fail closed."""

    def __init__(self, adapters: dict[str, EvalAdapter] | None = None) -> None:
        self._adapters = dict(adapters or {})

    def register(self, suite: str, adapter: EvalAdapter) -> None:
        if not suite or suite in self._adapters:
            raise AdapterError(f"suite adapter already registered or invalid: {suite!r}")
        self._adapters[suite] = adapter

    def resolve(self, suite: str) -> EvalAdapter:
        try:
            return self._adapters[suite]
        except KeyError as error:
            raise AdapterError(f"no product adapter registered for suite {suite!r}") from error


def default_registry() -> AdapterRegistry:
    return AdapterRegistry(
        {
            "governance": FixtureActualAdapter(),
            "playtest_invariants": PlaytestInvariantsAdapter(),
            "state_rules": StateRulesAdapter(),
            "routing": RoutingAdapter(),
            "action_contracts": RoutingAdapter(),
            "memory_write": MemoryWriteAdapter(),
            "memory_retrieval": RetrievalAdapter(),
            "context_grounding": ContextGroundingAdapter(),
            "generation_boundary": GenerationBoundaryAdapter(),
            "narrative_claims": NarrativeClaimAdapter(),
            "player_knowledge": PlayerKnowledgeAdapter(),
        }
    )


__all__ = [
    "AdapterError",
    "AdapterCase",
    "AdapterOutput",
    "AdapterRegistry",
    "EvalAdapter",
    "FixtureActualAdapter",
    "PlaytestInvariantsAdapter",
    "NarrativeClaimAdapter",
    "PlayerKnowledgeAdapter",
    "StateRulesAdapter",
    "RoutingAdapter",
    "MemoryWriteAdapter",
    "RetrievalAdapter",
    "ContextGroundingAdapter",
    "GenerationBoundaryAdapter",
    "default_registry",
]
