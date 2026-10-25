"""SPEC-317 R1 - A/B do tier CLASSIFY: Groq-first vs DeepSeek-first, mesmos inputs.

Replay offline (sem staging, sem banco): cada input passa pelo ``dm_router_node`` real com
``RPG_ROUTES`` apontando a ordem do CLASSIFY; mede latencia do no e a rota escolhida.
Os inputs vem do dataset de regressao do router, lido SOMENTE LEITURA (nunca editado):
``evals/datasets/regression/routing_actions.jsonl``. So entram no calculo de latencia os
inputs que de fato chegaram ao CLASSIFY (``route_source == "classify"``); os demais sao
decididos por gates Python e nao dependem do provider.

Gates de promocao (spec 2, R1): latencia CLASSIFY p50 cai >= 40 % **e** concordancia de rota
com o DeepSeek >= 95 %. A saida traz so contagens/tempos/decisao (sem texto de input).

Uso (precisa de GROQ_API_KEY e DEEPSEEK_API_KEY no ambiente; ~US$ 0,01):
    bash scripts/dev/py.sh -m scripts.staging.classify_ab --repeat 2 [--inputs extra.txt]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals" / "datasets" / "regression" / "routing_actions.jsonl"

GROQ_FIRST = {
    "classify": [
        ["groq", "openai/gpt-oss-20b"],
        ["deepseek", "deepseek-v4-flash"],
        ["gemini", "gemini-flash-lite-latest"],
    ]
}
DEEPSEEK_FIRST = {
    "classify": [
        ["deepseek", "deepseek-v4-flash"],
        ["groq", "openai/gpt-oss-20b"],
        ["gemini", "gemini-flash-lite-latest"],
    ]
}
LATENCY_DROP_GATE = 0.40
AGREEMENT_GATE = 0.95


def load_inputs(dataset: Path = DATASET, extra: Path | None = None) -> list[str]:
    """Acoes do dataset de regressao (leitura) + linhas extras opcionais; sem duplicatas."""
    out: list[str] = []
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        action = (json.loads(line).get("input") or {}).get("action")
        if action:
            out.append(str(action))
    if extra is not None:
        out += [ln.strip() for ln in extra.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return list(dict.fromkeys(out))


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))], 1)


def summarize(groq: list[dict], deepseek: list[dict]) -> dict:
    """Cada linha: ``{"i": indice do input, "route": str, "source": str, "ms": float}``.

    Concordancia: fracao dos inputs que chegaram ao CLASSIFY nos DOIS lados e escolheram a mesma
    rota (rota do DeepSeek = referencia). Latencia: so linhas ``source == "classify"``."""
    ds_by_i = {r["i"]: r for r in deepseek if r.get("source") == "classify"}
    gq_by_i = {r["i"]: r for r in groq if r.get("source") == "classify"}
    common = sorted(set(ds_by_i) & set(gq_by_i))
    agree = sum(1 for i in common if ds_by_i[i]["route"] == gq_by_i[i]["route"])
    agreement = round(agree / len(common), 4) if common else None
    ds_ms = [r["ms"] for r in deepseek if r.get("source") == "classify"]
    gq_ms = [r["ms"] for r in groq if r.get("source") == "classify"]
    ds_p50, gq_p50 = _pct(ds_ms, 0.5), _pct(gq_ms, 0.5)
    drop = round(1 - gq_p50 / ds_p50, 4) if ds_p50 and gq_p50 is not None else None
    promote = bool(
        drop is not None
        and agreement is not None
        and drop >= LATENCY_DROP_GATE
        and agreement >= AGREEMENT_GATE
    )
    return {
        "inputs_compared": len(common),
        "agreement": agreement,
        "latency_ms": {
            "deepseek": {"p50": ds_p50, "p95": _pct(ds_ms, 0.95), "n": len(ds_ms)},
            "groq": {"p50": gq_p50, "p95": _pct(gq_ms, 0.95), "n": len(gq_ms)},
        },
        "latency_drop_p50": drop,
        "gates": {"latency_drop_min": LATENCY_DROP_GATE, "agreement_min": AGREEMENT_GATE},
        "promote_groq_first": promote,
    }


def _state(text: str) -> dict:
    from langchain_core.messages import HumanMessage

    return {
        "game_id": "classify-ab",
        "messages": [HumanMessage(content=text)],
        "world": {
            "current_location": "Brekmar",
            "current_location_id": "brekmar",
            "turn_count": 5,
        },
        "npcs": {},
        "party": [],
        "combat": None,
    }


def run_config(routes: dict, inputs: list[str], repeat: int) -> list[dict]:
    """Roda o router real com ``RPG_ROUTES`` = routes (JSON inline); Jev e atalho NPC desligados."""
    os.environ["RPG_ROUTES"] = json.dumps(routes)
    os.environ["RPG_JEV_ROUTER_MODE"] = "off"
    os.environ["RPG_ROUTER_DETERMINISTIC_NPC"] = "off"
    os.environ.pop("RPG_FORCE_MOCK", None)
    from agents.router import dm_router_node, last_decision, reset_last_decision

    rows: list[dict] = []
    for _ in range(repeat):
        for i, text in enumerate(inputs):
            reset_last_decision()
            t0 = time.perf_counter()
            out = dm_router_node(_state(text))
            ms = (time.perf_counter() - t0) * 1000
            rows.append(
                {
                    "i": i,
                    "route": str(out.get("next")),
                    "source": last_decision().get("route_source"),
                    "ms": ms,
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--repeat", type=int, default=2, help="repeticoes por input (latencia)")
    ap.add_argument("--inputs", type=Path, default=None, help="arquivo extra, 1 input por linha")
    args = ap.parse_args(argv)
    for name in ("GROQ_API_KEY", "DEEPSEEK_API_KEY"):
        if not os.getenv(name):
            print(f"{name} ausente (precisa das duas chaves)", file=sys.stderr)
            return 1
    inputs = load_inputs(extra=args.inputs)
    deepseek = run_config(DEEPSEEK_FIRST, inputs, args.repeat)
    groq = run_config(GROQ_FIRST, inputs, args.repeat)
    print(json.dumps(summarize(groq, deepseek), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
