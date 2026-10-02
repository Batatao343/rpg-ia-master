"""Run the short real-provider contract gate with hard request and cost caps."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterator, Sequence

import pytest

import llm_setup
from evals.core.schemas import EVALUATOR_VERSION
from playtest.pricing import PRICE_PER_MTOK, estimate_cost


class ContractBudgetExceeded(RuntimeError):
    """Raised before a provider request that would exceed the approved budget."""


@dataclass
class ContractBudget:
    max_requests: int
    max_cost_usd: float
    requests_started: int = 0
    conservative_cost_reserved_usd: float = 0.0

    @property
    def worst_case_request_cost(self) -> float:
        models = list(PRICE_PER_MTOK) or [""]
        return max(estimate_cost(model) for model in models)

    def reserve(self, provider: str) -> None:
        next_requests = self.requests_started + 1
        next_cost = self.conservative_cost_reserved_usd + self.worst_case_request_cost
        if next_requests > self.max_requests:
            raise ContractBudgetExceeded(
                f"request cap exceeded before {provider} call "
                f"({next_requests}/{self.max_requests})"
            )
        if next_cost > self.max_cost_usd:
            raise ContractBudgetExceeded(
                f"cost cap exceeded before {provider} call "
                f"(${next_cost:.6f}/${self.max_cost_usd:.6f}, conservative estimate)"
            )
        self.requests_started = next_requests
        self.conservative_cost_reserved_usd = next_cost


def _product_sha(root: Path) -> str:
    configured = os.getenv("GITHUB_SHA", "").strip()
    if configured:
        return configured
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() or "unknown"


def run_gate(
    *,
    root: Path,
    output: Path,
    junit_xml: Path,
    max_requests: int,
    max_cost_usd: float,
    pytest_runner: Callable[[Sequence[str]], int | pytest.ExitCode] = pytest.main,
) -> int:
    if max_requests <= 0 or max_cost_usd <= 0:
        raise ValueError("max_requests and max_cost_usd must be positive")
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY is required; unavailable provider is not a pass")

    output.parent.mkdir(parents=True, exist_ok=True)
    junit_xml.parent.mkdir(parents=True, exist_ok=True)
    budget = ContractBudget(max_requests=max_requests, max_cost_usd=max_cost_usd)
    attempts: list[dict[str, object]] = []
    original_slot = llm_setup._provider_slot

    @contextmanager
    def guarded_slot(provider: str) -> Iterator[None]:
        budget.reserve(provider)
        with original_slot(provider):
            yield

    def capture(event: llm_setup.LLMAttemptEvent) -> None:
        row = asdict(event)
        row["tier"] = event.tier.value
        row["estimated_cost_usd"] = estimate_cost(event.model)
        row.pop("error", None)
        attempts.append(row)

    llm_setup._provider_slot = guarded_slot
    llm_setup.set_llm_attempt_telemetry_hook(capture)
    started_at = datetime.now(UTC)
    try:
        pytest_code = int(pytest_runner([
            "-m", "llm_contract", "-v", "-s", f"--junitxml={junit_xml}"
        ]))
    finally:
        llm_setup.set_llm_attempt_telemetry_hook(None)
        llm_setup._provider_slot = original_slot

    estimated_cost = sum(float(row["estimated_cost_usd"]) for row in attempts)
    successful = sum(row["outcome"] == "success" for row in attempts)
    payload = {
        "schema_version": 1,
        "gate": "real-provider-short",
        "product_sha": _product_sha(root),
        "evaluator_version": EVALUATOR_VERSION,
        "platform": f"{platform.system().lower()}-py{platform.python_version()}",
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "limits": {
            "max_requests": max_requests,
            "max_cost_usd": max_cost_usd,
            "cost_method": "conservative pre-request reservation",
        },
        "usage": {
            "requests_started": budget.requests_started,
            "successful_attempts": successful,
            "estimated_cost_usd": round(estimated_cost, 8),
            "conservative_cost_reserved_usd": round(
                budget.conservative_cost_reserved_usd, 8
            ),
        },
        "attempts": attempts,
        "pytest_exit_code": pytest_code,
        "passed": pytest_code == 0 and successful > 0,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if payload["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--junitxml", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run_gate(
            root=Path.cwd(),
            output=args.output,
            junit_xml=args.junitxml,
            max_requests=args.max_requests,
            max_cost_usd=args.max_cost_usd,
        )
    except (ValueError, RuntimeError) as error:
        print(f"real-provider contract gate failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
