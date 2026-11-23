"""SPEC-428 R12: pacote de pares de narracao (`RPG_NARRATION_SIZE` off x on) para o dono ler.

Roda `storyteller_node` com o mesmo estado e a mesma acao, uma vez com `off` e uma com `on`,
e grava `<out>.md` (texto dos dois lados + contagens) e `<out>.json` (so contagens, `git_sha` e
modelo/provedor de cada chamada; nenhum texto). Recusa rodar com `RPG_FORCE_MOCK=1` ou sem chave,
salvo `--mock` (usado so no teste). Conta TODA chamada de LLM (narrador + qualquer `get_llm`
fora dele, que e proibida) e recusa ANTES da primeira se `2 x casos x samples` passar do teto (30).
O pulso do mundo e neutralizado nos dois bracos; cada par grava o hash do prompt sem as linhas de
tamanho e falha se `off` e `on` divergirem.

    bash scripts/dev/py.sh scripts/dev/narration_pairs.py \
        --cases docs/spec428/pares_casos.json --out docs/spec428/pares-2026-11-22
    bash scripts/dev/py.sh scripts/dev/narration_pairs.py --write-cases docs/spec428/pares_casos.json

O texto varia entre execucoes (temperatura 0,7, sem seed no provedor): reprodutivel = mesmos
casos, mesmo comando, mesmo sha. `--samples N` repete so para contagem de tamanho.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAX_CALLS = 30
OUTRA_ACAO = "— Ou outra ação."


# --------------------------------------------------------------------------- casos
def _base_state() -> dict[str, Any]:
    """Estado fixo sem mensagens (a acao entra em `action`); um jogador simples em Nova Arcadia."""
    return {
        "game_id": "pares428",
        "player": {
            "name": "Ari",
            "class_name": "Guerreiro",
            "level": 1,
            "xp": 0,
            "gold": 10,
            "inventory": [],
            "vitalidade": 5,
            "max_vitalidade": 8,
        },
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "turn_count": 4,
            "danger_level": 1,
            "world_clock": {"day": 1, "period": "Manhã"},
            "visited": ["nova_arcadia"],
        },
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "quests": [],
        "campaign_plan": {},
        "event_log": [],
        "world_projection": {},
        "narrative_summary": "",
        "archivist_last_run": 0,
    }


def _case(cid: str, cls: str, action: str, *, visited=None, mediated=False, trap=False) -> dict:
    state = _base_state()
    if visited:
        state["world"]["visited"] = list(visited)
    if mediated:
        state["interlocutor_reason"] = "meta_to_narrator"
    return {
        "id": cid,
        "expected_class": cls,
        "action": action,
        "encounter": "trap" if trap else "none",
        "state": state,
    }


def build_cases() -> list[dict]:
    both = ["nova_arcadia", "brekmar"]
    return [
        _case("cena-1", "cena", "Observo a rua."),
        _case("cena-2", "cena", "Examino a praça com calma, atento aos rostos."),
        _case("cena-3", "cena", "Sigo pela rua em direção ao mercado."),
        _case(
            "fala-mediada-1",
            "fala_mediada",
            "Narrador, o que a cidade sabe sobre isto?",
            mediated=True,
        ),
        _case("fala-mediada-2", "fala_mediada", "Narrador, quem manda por aqui?", mediated=True),
        _case("descanso-1", "descanso", "Descanso até o amanhecer."),
        _case("descanso-2", "descanso", "Descanso um pouco antes de seguir."),
        _case("local-visitado", "cena", "Viajo para Brekmar.", visited=both),
        _case("controle-local-novo", "local_novo", "Viajo para Brekmar."),
        _case("controle-revelacao", "revelacao", "Viajo para Brekmar.", visited=both, trap=True),
    ]


# --------------------------------------------------------------------------- execucao
SIZE_LINE_MARKS = ("TAMANHO DA RESPOSTA", "- Responda em 2 a 3 parágrafos")


def prompt_fingerprint(messages: Any) -> str:
    """Hash do prompt sem as linhas de tamanho (as unicas que `on` pode mudar); nunca o texto."""
    items = messages if isinstance(messages, list | tuple) else [messages]
    joined = "\n".join(str(getattr(m, "content", m)) for m in items)
    kept = [ln for ln in joined.split("\n") if not any(mark in ln for mark in SIZE_LINE_MARKS)]
    return hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()[:16]


class _CountingLLM:
    """Proxy do narrador: conta as chamadas, guarda o hash do prompt e aborta ao passar do teto."""

    def __init__(self, inner: Any, budget: dict) -> None:
        self._inner, self._budget = inner, budget

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def with_structured_output(self, *args: Any, **kwargs: Any) -> Any:
        bound = self._inner.with_structured_output(*args, **kwargs)
        budget = self._budget

        class _Bound:
            def __getattr__(self, attr: str) -> Any:
                return getattr(bound, attr)

            def invoke(self, *a: Any, **k: Any) -> Any:
                budget["calls"] += 1
                if budget["calls"] + budget.get("foreign", 0) > MAX_CALLS:
                    raise SystemExit(f"teto de {MAX_CALLS} chamadas de LLM excedido")
                if a:
                    budget.setdefault("prints", []).append(prompt_fingerprint(a[0]))
                return bound.invoke(*a, **k)

        return _Bound()


def check_budget(n_cases: int, samples: int) -> int:
    """Recusa ANTES de qualquer chamada: previsto = 2 bracos x casos x samples."""
    planned = 2 * n_cases * samples
    if planned > MAX_CALLS:
        raise SystemExit(
            f"previsto {planned} chamadas de LLM (2 x {n_cases} casos x {samples} samples) "
            f"> teto {MAX_CALLS}: reduza --samples/casos; nada foi chamado"
        )
    return planned


@contextlib.contextmanager
def _llm_guard(narrator: Any, budget: dict):
    """Ponto unico de LLM: o `get_llm` do narrador devolve o proxy; todo outro `get_llm` (em
    qualquer modulo carregado, inclusive `llm_setup`) e contado e levanta."""
    from agents import storyteller as st

    def foreign(*_a: Any, **_k: Any) -> Any:
        budget["foreign"] = budget.get("foreign", 0) + 1
        raise RuntimeError("chamada de LLM fora do narrador no pacote de pares")

    saved: list[tuple[Any, Any]] = []
    for mod in list(sys.modules.values()):
        if mod is not None and mod is not st and callable(getattr(mod, "get_llm", None)):
            saved.append((mod, mod.get_llm))
            mod.get_llm = foreign
    saved.append((st, st.get_llm))
    st.get_llm = lambda *a, **k: narrator
    try:
        yield
    finally:
        for mod, fn in saved:
            mod.get_llm = fn


class _ProviderLog(logging.Handler):
    """Coleta provider/model das tentativas (`provider.attempt`); nunca texto."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.rows: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            data = json.loads(record.getMessage())
        except ValueError:
            return
        if data.get("event") == "provider.attempt":
            self.rows.append({k: data.get(k) for k in ("provider", "model", "outcome")})


def _count(text: str) -> dict:
    lines = text.split("\n")
    options = [ln for ln in lines if ln.startswith("— ") and ln.strip() != OUTRA_ACAO]
    body = "\n".join(ln for ln in lines if not ln.startswith("— "))
    paragraphs = [p for p in body.split("\n\n") if p.strip()]
    return {"chars": len(text), "paragraphs": len(paragraphs), "option_lines": len(options)}


def _run_one(
    case: dict, mode: str, llm: _CountingLLM, harvest: _ProviderLog
) -> tuple[str, list[dict], str]:
    """Uma chamada do narrador no caso com a flag `mode`; devolve (texto, tentativas, hash)."""
    from langchain_core.messages import HumanMessage

    import world_utils
    from agents import storyteller as st

    os.environ["RPG_NARRATION_SIZE"] = mode
    state = json.loads(json.dumps(case["state"]))
    state["messages"] = [HumanMessage(content=case["action"])]
    budget = llm._budget
    n_prints, n_foreign = len(budget.get("prints", [])), budget.get("foreign", 0)
    saved = (st.check_encounter, world_utils.roll_encounter_type, st._story_world_pulse)
    trap = case.get("encounter") == "trap"
    st.check_encounter = (
        (lambda *a, **k: {"reason": "x", "flavor": "Uma armadilha na estrada.", "hint": "x"})
        if trap
        else (lambda *a, **k: None)
    )
    world_utils.roll_encounter_type = lambda danger: "trap"
    st._story_world_pulse = lambda t: None  # P2-1: sem LLM do mundo, igual nos dois bracos
    harvest.rows.clear()
    random.seed(1)
    try:
        with _llm_guard(llm, budget):
            out = st.storyteller_node(state)
    finally:
        st.check_encounter, world_utils.roll_encounter_type, st._story_world_pulse = saved
    if budget.get("foreign", 0) > n_foreign:
        raise SystemExit(f"caso {case['id']}: chamada de LLM fora do narrador (par invalido)")
    prints = budget.get("prints", [])[n_prints:]
    msgs = out.get("messages") or []
    text = str(getattr(msgs[-1], "content", "")) if msgs else ""
    return text, list(harvest.rows), (prints[0] if prints else "")


def _git_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


class _FakeNarrator:
    """LLM fixo para `--mock` (teste): uma `StoryUpdate` valida, sem rede."""

    def with_structured_output(self, *_a: Any, **_k: Any) -> _FakeNarrator:
        return self

    def invoke(self, *_a: Any, **_k: Any) -> Any:
        from agents.storyteller import StoryUpdate

        text = "A cena segue.\n\n— Ir adiante\n— Esperar\n— Ou outra ação."
        return StoryUpdate(narrative=text)


def _resolve_llm(use_mock: bool) -> Any:
    if use_mock:
        return _FakeNarrator()
    if os.environ.get("RPG_FORCE_MOCK") == "1":
        raise SystemExit(
            "RPG_FORCE_MOCK=1: o pacote de pares exige LLM real (use --mock so em teste)"
        )
    from llm_setup import get_llm

    llm = get_llm(temperature=0.7)
    if getattr(llm, "is_mock", False):
        raise SystemExit(
            "sem chave de LLM: o pacote de pares exige LLM real (use --mock so em teste)"
        )
    return llm


def run(cases: list[dict], llm: Any, samples: int = 1) -> dict:
    check_budget(len(cases), samples)
    budget: dict[str, Any] = {"calls": 0, "foreign": 0}
    counted = _CountingLLM(llm, budget)
    handler = _ProviderLog()
    plog = logging.getLogger("rpg.provider")
    plog.addHandler(handler)
    old_level = plog.level
    plog.setLevel(logging.DEBUG)
    pairs: list[dict] = []
    try:
        for case in cases:
            row: dict[str, Any] = {"id": case["id"], "expected_class": case["expected_class"]}
            row["action"] = case["action"]
            for mode in ("off", "on"):
                text, attempts, fp = _run_one(case, mode, counted, handler)
                extra = [_run_one(case, mode, counted, handler)[0] for _ in range(samples - 1)]
                row[mode] = {"text": text, "counts": _count(text), "attempts": attempts}
                row[mode]["sample_chars"] = [len(text)] + [len(x) for x in extra]
                row[mode]["input_hash"] = fp
            if row["off"]["input_hash"] != row["on"]["input_hash"]:
                raise SystemExit(f"caso {case['id']}: entradas de off e on divergem (par invalido)")
            row["input_hash"] = row["off"]["input_hash"]
            pairs.append(row)
    finally:
        plog.removeHandler(handler)
        plog.setLevel(old_level)
        os.environ.pop("RPG_NARRATION_SIZE", None)
    calls = budget["calls"] + budget["foreign"]
    return {"git_sha": _git_sha(), "calls": calls, "pairs": pairs}


# --------------------------------------------------------------------------- saida
def render_md(result: dict) -> str:
    out = [f"# Pares de narração (SPEC-428) · sha {result['git_sha']}\n"]
    for pair in result["pairs"]:
        off, on = pair["off"]["counts"], pair["on"]["counts"]
        out.append(f"## {pair['id']} · classe `{pair['expected_class']}`\n")
        out.append(f"Ação: {pair['action']}\n")
        for label, key, counts in (("off", "off", off), ("on", "on", on)):
            out.append(
                f"### {label} · {counts['chars']} caracteres · {counts['paragraphs']} parágrafos"
                f" · {counts['option_lines']} linhas de opção\n"
            )
            out.append(pair[key]["text"] + "\n")
    return "\n".join(out)


def counts_only(result: dict) -> dict:
    pairs = []
    for pair in result["pairs"]:
        row = {
            "id": pair["id"],
            "expected_class": pair["expected_class"],
            "input_hash": pair["input_hash"],
        }
        for mode in ("off", "on"):
            row[mode] = {
                "counts": pair[mode]["counts"],
                "sample_chars": pair[mode]["sample_chars"],
                "attempts": pair[mode]["attempts"],
            }
        pairs.append(row)
    return {"git_sha": result["git_sha"], "calls": result["calls"], "pairs": pairs}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--mock", action="store_true", help="LLM roteirizado (so em teste)")
    ap.add_argument("--write-cases", type=Path, help="grava os 10 casos fixos e sai")
    args = ap.parse_args(argv)
    if args.write_cases:
        args.write_cases.parent.mkdir(parents=True, exist_ok=True)
        args.write_cases.write_text(
            json.dumps(build_cases(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return 0
    if not args.cases or not args.out:
        ap.error("--cases e --out são obrigatórios")
    llm = _resolve_llm(args.mock)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    result = run(cases, llm, max(1, args.samples))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".md").write_text(render_md(result), encoding="utf-8")
    args.out.with_suffix(".json").write_text(
        json.dumps(counts_only(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
