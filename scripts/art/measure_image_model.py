"""SPEC-425 R8/R9/R15: mede o modelo de imagem pelo caminho de produção, com teto de gasto.

Sem ``--confirm-spend`` só imprime o plano (nenhuma chamada, nenhuma chave lida). A chave vem da
variável ``OPENAI_API_KEY`` e nunca é impressa. Bytes de imagem vão só para ``--out-dir`` (fora do
repo); o JSON guarda ``prompt_hash``, nunca o prompt.

    uv run python -m scripts.art.measure_image_model --max-usd 2 --out-dir D:/fora --confirm-spend
    uv run python -m scripts.art.measure_image_model --canary --max-usd 0.25 --out-dir D:/fora ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from infrastructure.ports import ImageGenerationInput, ImageGenerator
from services.image_pricing import price_image_event
from services.usage_metering import normalize_attempts, safe_provider_usage

ROOT = Path(__file__).resolve().parents[2]
_PROJECT_OUT = ROOT / "docs" / "spec425" / "medicao.json"
MAX_USD_CEILING = Decimal("2.00")
PER_CALL_CEILING = Decimal("0.25")
CANARY_TOKEN_BAND = 0.30
VARIANTS = ("gpt-image-2.6-sunburst", "gpt-image-2.6-flare")
BASE_MODEL = "gpt-image-2-2026-04-21"


@dataclass(frozen=True)
class Case:
    model: str
    fmt: str
    size: str
    quality: str
    complexity: str | None
    prompt: str
    references: tuple[bytes, ...] = ()
    reference_ids: tuple[str, ...] = ()
    label: str = ""
    portrait_from: str = ""  # label of an earlier case whose output is the approved portrait


# --------------------------------------------------------------------------- #
# Plano (builders de produção)
# --------------------------------------------------------------------------- #
def _case_from_brief(
    model: str, fmt: str, brief: dict, complexity: str | None, label: str, portrait_from: str = ""
) -> Case:
    from services.art_brief import render_image_prompt
    from workers.dynamic_art_jobs import resolve_reference_payloads

    ids, payloads = resolve_reference_payloads(brief, blob_store=None, approved_portrait_key=None)
    return Case(
        model, fmt, brief["size"], brief.get("quality", "medium"), complexity,
        render_image_prompt(brief, ids), payloads, ids, label, portrait_from,
    )  # fmt: skip


def _player(race: str) -> dict:
    return {"name": race, "race": race, "class_name": "Sangromante"}


def case_plan(model: str, complexity: str | None) -> list[Case]:
    """Retrato Elfo e épico em Brekmar (o épico leva o retrato do Elfo da mesma rodada)."""
    from services.art_brief import build_epic_art_brief, build_player_art_brief

    elf = _player("Elfo")
    state = {"player": elf, "world": {"current_location_id": "brekmar"}, "enemies": []}
    return [
        _case_from_brief(model, "portrait", dict(build_player_art_brief(elf)), complexity, "elfo"),
        _case_from_brief(
            model, "epic_scene", dict(build_epic_art_brief(state, {})), complexity, "epico", "elfo"
        ),
    ]


def default_plan() -> list[Case]:
    """Matriz da §4 Etapa 1 em ordem de prioridade (o teto corta o fim)."""
    from services.art_brief import build_npc_art_brief, build_player_art_brief

    plan: list[Case] = []
    for model in VARIANTS:
        plan += case_plan(model, "high")
        for race, label in (("Vrel", "vrel"),):
            brief = dict(build_player_art_brief(_player(race)))
            plan.append(_case_from_brief(model, "portrait", brief, "high", label))
        npc = {"npcs": {"kahen": {"name": "Kahen", "role": "Mercador", "race_id": "race_cinzeus"}}}
        npc_brief = dict(build_npc_art_brief(npc, "kahen"))
        plan.append(_case_from_brief(model, "portrait", npc_brief, "high", "kahen"))
    for model in VARIANTS:
        plan += case_plan(model, "medium")
    return plan + case_plan(BASE_MODEL, None)


def canary_plan(model: str) -> list[Case]:
    """R15: 1 retrato do Elfo, ``complexity: high``."""
    return case_plan(model, "high")[:1]


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #
def _price(model: str, usage: dict) -> tuple[str, str]:
    safe = safe_provider_usage(usage, image_generated=True)
    event = normalize_attempts(
        [
            {
                "provider": "openai",
                "model": model,
                "outcome": "success",
                "network_attempted": True,
                "usage": safe,
            }
        ],
        operation_id=uuid4(),
        component="image",
        category="image",
    )[0]
    priced = price_image_event(event, safe)
    return str(priced.cost_usd), str(priced.cost_basis)


def _canon_hamming(output: bytes, case: Case) -> int | None:
    if not case.references:
        return None
    from services.art_brief import load_art_profile
    from workers.dynamic_art_jobs import canon_similarity

    threshold = int(load_art_profile().get("canon_similarity_min_hamming", 10))
    result = canon_similarity(output, case.reference_ids, case.references, threshold=threshold)
    return result["canon_min_hamming"]


def _record(case: Case, generated: Any, latency_ms: int, refs: int) -> dict:
    cost, basis = _price(case.model, generated.usage)
    return {
        "model": case.model,
        "format": case.fmt,
        "size": case.size,
        "quality": case.quality,
        "complexity": case.complexity,
        "refs": refs,
        "endpoint": "edits" if refs else "generations",
        "http_status": 200,
        "latency_ms": latency_ms,
        "usage": safe_provider_usage(generated.usage, image_generated=True),
        "cost_usd": cost,
        "cost_basis": basis,
        "canon_min_hamming": _canon_hamming(generated.payload, case),
        "prompt_hash": hashlib.sha256(case.prompt.encode()).hexdigest()[:16],
    }


def _stop_reason(record: dict) -> str | None:
    if record["cost_basis"] != "rate_card":
        return (
            f"cost_basis {record['cost_basis']!r} is not billable exactly: the switch cannot go on"
        )
    if Decimal(record["cost_usd"]) > PER_CALL_CEILING:
        return f"image cost {record['cost_usd']} above {PER_CALL_CEILING}"
    return None


def measure(
    plan: list[Case],
    generator: ImageGenerator,
    *,
    max_usd: Decimal,
    out_dir: Path,
    report: dict | None = None,
) -> list[dict]:
    """Roda o plano; para ao primeiro sinal de perigo. ``report`` recebe ``spent_usd``/``stopped``."""
    if max_usd > MAX_USD_CEILING:
        raise ValueError(f"max_usd above {MAX_USD_CEILING}")
    out_dir.mkdir(parents=True, exist_ok=True)
    calls: list[dict] = []
    outputs: dict[str, bytes] = {}
    spent, stopped = Decimal(0), None
    for index, case in enumerate(plan):
        if spent + PER_CALL_CEILING > max_usd:
            stopped = (
                f"budget: {spent} spent, next call may cost {PER_CALL_CEILING} (max {max_usd})"
            )
            break
        refs = case.references
        if case.portrait_from in outputs:
            refs = (outputs[case.portrait_from], *refs)
        started = time.perf_counter()
        try:
            generated = generator.generate(
                ImageGenerationInput(
                    case.prompt, case.model, case.size, refs, case.quality, case.complexity
                )
            )
        except Exception as exc:  # noqa: BLE001  # silent-ok: recorded as stopped (type only)
            stopped = f"provider_error: {type(exc).__name__}"
            break
        latency_ms = int((time.perf_counter() - started) * 1000)
        record = _record(case, generated, latency_ms, len(refs))
        calls.append(record)
        spent += Decimal(record["cost_usd"])
        outputs[case.label or str(index)] = generated.payload
        name = f"{index:02d}_{case.fmt}_{case.label or 'x'}_{case.model}.png"
        (out_dir / name).write_bytes(generated.payload)
        stopped = _stop_reason(record)
        if stopped:
            break
    if report is not None:
        report.update(spent_usd=str(spent), max_usd=str(max_usd), stopped=stopped)
    return calls


# --------------------------------------------------------------------------- #
# Canary check, SPEC-425 R15
# --------------------------------------------------------------------------- #
def canary_verdict(call: dict, baseline: list[dict], *, hamming_min: int) -> list[str]:
    """Divergências do canário contra a mediana de ``medicao.json``; vazio = dentro da faixa."""
    same = [
        c["usage"]["output_tokens"]
        for c in baseline
        if c["model"] == call["model"]
        and c["format"] == "portrait"
        and "output_tokens" in c["usage"]
    ]
    problems: list[str] = []
    if same:
        median = statistics.median(same)
        got = call["usage"].get("output_tokens", 0)
        if abs(got - median) > median * CANARY_TOKEN_BAND:
            problems.append(f"output_tokens {got} outside ±30% of median {median}")
    hamming = call.get("canon_min_hamming")
    if hamming is not None and hamming < hamming_min:
        problems.append(f"canon_min_hamming {hamming} below profile threshold {hamming_min}")
    return problems


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _inside_repo(path: Path) -> bool:
    return path.resolve().is_relative_to(ROOT)


def _build_generator() -> ImageGenerator:
    from infrastructure.openai_images import OpenAIImageGenerator

    return OpenAIImageGenerator(os.environ.get("OPENAI_API_KEY", ""))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-usd", type=Decimal, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--confirm-spend", action="store_true")
    parser.add_argument("--canary", action="store_true")
    parser.add_argument("--variant", choices=VARIANTS, default=VARIANTS[0])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    ceiling = PER_CALL_CEILING if args.canary else MAX_USD_CEILING
    if not Decimal(0) < args.max_usd <= ceiling:
        parser.error(f"--max-usd must be in (0, {ceiling}]")
    if _inside_repo(args.out_dir):
        parser.error("--out-dir must be outside the repository (R8: image bytes stay out)")
    plan = canary_plan(args.variant) if args.canary else default_plan()
    if not args.confirm_spend:
        print(f"plan: {len(plan)} calls, max {args.max_usd} USD (add --confirm-spend to run)")
        for case in plan:
            print(
                f"  {case.model} {case.fmt} complexity={case.complexity} refs={len(case.references)}"
            )
        return 0
    report: dict = {}
    calls = measure(
        plan, _build_generator(), max_usd=args.max_usd, out_dir=args.out_dir, report=report
    )
    target = _PROJECT_OUT.with_name("canario.json") if args.canary else _PROJECT_OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({**report, "calls": calls}, indent=2), encoding="utf-8")
    print(f"{len(calls)} calls, spent {report['spent_usd']} USD, stopped: {report['stopped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
