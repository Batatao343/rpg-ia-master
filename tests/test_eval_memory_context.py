"""Memory, retrieval and context eval contracts (SPEC-170)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.core.adapters import AdapterCase, AdapterOutput, AdapterRegistry
from evals.core.governance import load_cases
from evals.core.runner import run_eval
from services.context_builder import ContextBudget


ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/memory_context.jsonl"


def test_context_budget_preserves_legacy_positional_reserved_argument() -> None:
    reserved = {"lore": 1.0}

    budget = ContextBudget(100, reserved)

    assert budget.max_tokens == 100
    assert budget.reserved is reserved
    assert budget.max_visibility == "public"


def test_faiss_trace_preserves_distinct_chunks_with_the_same_entity_id() -> None:
    from langchain_core.documents import Document

    from rag import query_faiss_evidence

    class SameEntityIndex:
        requested_k = 0

        def similarity_search_with_score_by_vector(self, vector, *, k):
            assert vector == [1.0, 0.0]
            self.requested_k = k
            return [
                (Document(
                    page_content="Valerius governa a cidade.",
                    metadata={"id": "npc_valerius", "visibility": "public"},
                ), 0.1),
                (Document(
                    page_content="Valerius teme a Rede Carmesim.",
                    metadata={"id": "npc_valerius", "visibility": "secret"},
                ), 0.2),
            ]

    index = SameEntityIndex()
    first = query_faiss_evidence(index, [1.0, 0.0], k=2)
    second = query_faiss_evidence(index, [1.0, 0.0], k=2)

    assert index.requested_k == 2
    assert len(first) == 2
    assert [item.id for item in first] == [item.id for item in second]
    assert len({item.id for item in first}) == 2
    assert all(item.id.startswith("npc_valerius#chunk_") for item in first)
    assert all(item.metadata["entity_id"] == "npc_valerius" for item in first)


def test_memory_context_corpus_has_separate_sourced_layers() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.suite] = counts.get(case.suite, 0) + 1

    assert len(cases) == 27
    assert counts == {
        "memory_write": 11,
        "memory_retrieval": 7,
        "context_grounding": 8,
        "generation_boundary": 1,
    }
    assert all(case.description and case.created_from for case in cases)
    assert all(case.oracle in {"memory_write", "ranking", "exact"} for case in cases)
    assert all(case.oracle != "judge" for case in cases)


def test_memory_context_dataset_emits_layered_metrics_and_metadata() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="memory-context")

    assert result.passed is True
    assert len(result.results) == 27
    assert result.metric_values == pytest.approx({
        "exact_match": 1.0,
        "memory_write_precision": 1.0,
        "memory_recall_at_1": 3.5 / 6,
        "memory_recall_at_3": 1.0,
        "memory_recall_at_5": 1.0,
        "memory_mrr": 5.0 / 6,
        "context_recall_at_5": 1.0,
        "context_forbidden_leak_rate": 0.0,
        "secret_leak_count": 0.0,
        "context_token_budget_violation": 0.0,
    })
    assert result.aggregates == {
        "layer_outcomes": {
            "store": {"passed": 11, "failed": 0, "error": 0},
            "retrieve": {"passed": 7, "failed": 0, "error": 0},
            "context": {"passed": 8, "failed": 0, "error": 0},
            "generate": {"passed": 1, "failed": 0, "error": 0},
        }
    }
    ranked = [case for case in result.results if case.suite == "memory_retrieval"]
    assert all(case.actual["retrieval_metadata"]["provider"] is None for case in ranked)
    assert all(
        case.actual["retrieval_metadata"]["embedding"] == "fixture-vectors"
        and case.actual["retrieval_metadata"]["index"] == "faiss-in-memory"
        for case in ranked
    )
    assert result.metadata.provider is None
    assert result.metadata.model is None


def test_context_trace_exposes_ids_and_drop_reasons_without_story_text() -> None:
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={
            "context.budget.discards-low-score",
            "context.trace.unknown-section",
            "context.trace.visibility-reason",
            "memory.generate.boundary",
        },
        run_id="context-trace",
    )
    by_id = {case.case_id: case.actual for case in result.results}

    assert by_id["context.budget.discards-low-score"]["discarded_evidence"] == [{
        "id": "event-low",
        "section": "current_state",
        "reason": "section_or_global_budget",
    }]
    assert by_id["context.trace.unknown-section"]["discarded_evidence"] == [{
        "id": "unknown-evidence",
        "section": "unsupported",
        "reason": "unknown_section",
    }]
    assert by_id["context.trace.visibility-reason"]["discarded_evidence"] == [{
        "id": "secret-rejected",
        "section": "session_memory",
        "reason": "visibility",
    }]
    assert by_id["memory.generate.boundary"] == {
        "layer": "generate",
        "memory_context_scored": False,
        "accepted_text": "",
        "rejection_reasons": ["player_death"],
    }
    assert "story_text" not in str(by_id)


@pytest.mark.parametrize(
    ("case_id", "suite", "actual", "metric", "diagnostic"),
    [
        (
            "memory.write.canonical-event",
            "memory_write",
            {"accepted_ids": [], "rejected": []},
            "memory_write_precision",
            "memory write decisions != fixture labels",
        ),
        (
            "memory.retrieve.secret-filtered",
            "memory_retrieval",
            {"ranked_ids": ["secret-valerius"], "within_budget": True},
            "secret_leak_count",
            "secret evidence leaked: secret-valerius",
        ),
        (
            "context.visibility.secret-filtered",
            "context_grounding",
            {"ranked_ids": ["secret-truth"], "within_budget": True},
            "context_forbidden_leak_rate",
            "forbidden evidence leaked: secret-truth",
        ),
        (
            "memory.generate.boundary",
            "generation_boundary",
            {
                "layer": "generate",
                "memory_context_scored": False,
                "accepted_text": "Ari morreu.",
                "rejection_reasons": [],
            },
            "exact_match",
            "actual != fixture-authored expected",
        ),
    ],
)
def test_each_layer_fails_independently_without_oracle_access(
    case_id: str,
    suite: str,
    actual: dict,
    metric: str,
    diagnostic: str,
) -> None:
    class BrokenLayerAdapter:
        adapter_id = "broken-layer"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            assert not hasattr(case, "expected")
            assert not hasattr(case, "oracle")
            return AdapterOutput(actual=actual)

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={case_id},
        registry=AdapterRegistry({suite: BrokenLayerAdapter()}),
        run_id="known-bad-" + suite,
    )

    assert result.passed is False
    assert metric in result.metric_values
    assert diagnostic in result.results[0].diagnostics
    layer = {
        "memory_write": "store",
        "memory_retrieval": "retrieve",
        "context_grounding": "context",
        "generation_boundary": "generate",
    }[suite]
    assert result.aggregates["layer_outcomes"][layer]["failed"] == 1


def test_ranking_miss_is_measured_but_not_blocking_before_baseline() -> None:
    class MissingRelevantAdapter:
        adapter_id = "missing-relevant"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            return AdapterOutput(actual={"ranked_ids": ["fact-other"], "within_budget": True})

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"memory.retrieve.exact-top1"},
        registry=AdapterRegistry({"memory_retrieval": MissingRelevantAdapter()}),
        run_id="ranking-before-baseline",
    )

    assert result.passed is True
    assert result.metric_values["memory_recall_at_5"] == 0.0
    assert result.metric_values["memory_mrr"] == 0.0
    assert result.results[0].diagnostics == [
        "required evidence absent from top 5: fact-brother"
    ]


def test_ranking_adapter_error_stays_in_metric_denominator() -> None:
    class OneErrorAdapter:
        adapter_id = "one-error"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            if case.id.endswith("rank2"):
                raise RuntimeError("fixture failure")
            return AdapterOutput(actual={"ranked_ids": ["fact-brother"], "within_budget": True})

    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"memory.retrieve.exact-top1", "memory.retrieve.relevant-rank2"},
        registry=AdapterRegistry({"memory_retrieval": OneErrorAdapter()}),
        run_id="ranking-error-denominator",
    )

    assert result.passed is False
    assert result.error_case_ids == ["memory.retrieve.relevant-rank2"]
    assert result.metric_values["memory_recall_at_5"] == 0.5
    assert result.metric_values["memory_mrr"] == 0.5


def test_product_memory_validator_mutation_is_detected(monkeypatch) -> None:
    from services import memory_provenance

    monkeypatch.setattr(
        memory_provenance,
        "validate_memory_fact",
        lambda record, _state: (record, None),
    )
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"memory.write.secret-unrevealed"},
        run_id="mutated-memory-validator",
    )
    assert result.passed is False
    assert result.metric_values["memory_write_precision"] == 0.0


def test_product_faiss_visibility_mutation_is_detected(monkeypatch) -> None:
    import rag

    monkeypatch.setattr(
        rag,
        "query_faiss_evidence",
        lambda *_args, **_kwargs: [
            rag.RetrievedEvidence(
                id="secret-valerius",
                source="lore",
                score=1.0,
                text="segredo",
                visibility="secret",
            )
        ],
    )
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"memory.retrieve.secret-filtered"},
        run_id="mutated-retrieval-filter",
    )
    assert result.passed is False
    assert result.metric_values["secret_leak_count"] == 1.0


def test_product_context_selection_mutation_is_detected(monkeypatch) -> None:
    from services import context_builder

    monkeypatch.setattr(
        context_builder,
        "assemble_pack",
        lambda *_args, **_kwargs: context_builder.ContextPack(
            world_state_block="",
            lore_block="",
            memory_block="",
            total_tokens_est=1,
            dropped=0,
            evidence_ids=["secret-truth"],
            discarded_evidence=[],
        ),
    )
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"context.visibility.secret-filtered"},
        run_id="mutated-context-filter",
    )
    assert result.passed is False
    assert result.metric_values["context_forbidden_leak_rate"] == 1.0


def test_product_generation_guard_mutation_is_detected(monkeypatch) -> None:
    from types import SimpleNamespace
    from services import narrative_evidence

    monkeypatch.setattr(
        narrative_evidence,
        "validate_narrative",
        lambda text, *_args, **_kwargs: SimpleNamespace(text=text, rejections=[]),
    )
    result = run_eval(
        ROOT,
        datasets=[DATASET],
        case_ids={"memory.generate.boundary"},
        run_id="mutated-generation-guard",
    )
    assert result.passed is False
    assert result.metric_values["exact_match"] == 0.0
