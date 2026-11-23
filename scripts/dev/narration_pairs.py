"""SPEC-428 R12: pacote de pares de narracao (`RPG_NARRATION_SIZE` off x on) para o dono ler.

Roda `storyteller_node` com o mesmo estado e a mesma acao, uma vez com `off` e uma com `on`,
e grava `<out>.md` (texto dos dois lados + contagens) e `<out>.json` (so contagens, `git_sha` e
modelo/provedor de cada chamada; nenhum texto). Recusa rodar com `RPG_FORCE_MOCK=1` ou sem chave,
salvo `--mock` (usado so no teste). Conta TODA chamada de LLM (narrador + qualquer `get_llm`
fora dele, que e proibida) e recusa ANTES da primeira se `2 x casos x samples` passar do teto
(`--max-calls`, default 30, maximo absoluto 120). Cada tentativa de LLM (hook de telemetria do
projeto) entra em `llm_attempts` por braco; se algum texto nao veio do primeiro candidato, ou os
bracos divergem de provedor/modelo, o par fica `comparavel: false` e o rc e 3 (arquivos gravados).
O pulso do mundo e neutralizado nos dois bracos; cada par grava o hash do prompt sem as linhas de
tamanho e falha se `off` e `on` divergirem.

    bash scripts/dev/py.sh scripts/dev/narration_pairs.py \
        --cases docs/spec428/pares_casos.json --out docs/spec428/pares-2026-11-22
    bash scripts/dev/py.sh scripts/dev/narration_pairs.py --write-cases docs/spec428/pares_casos.json

O texto varia entre execucoes (temperatura 0,7, sem seed no provedor): reprodutivel = mesmos
casos, mesmo comando, mesmo sha. `--samples N` repete cada braco N vezes (contagens e textos de
todas as amostras ficam no pacote); `--samples 3 --max-calls 60` pede 60 chamadas de proposito.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import os
import random
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAX_CALLS = 30  # teto padrao; `--max-calls` o muda de proposito
ABS_MAX_CALLS = 120  # teto absoluto: nem `--max-calls` passa daqui
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


def _with_scene_people(state: dict[str, Any]) -> None:
    """P3-1: 1 NPC ja criado e presente + 1 faccao conhecida (sem ficha a gerar)."""
    state["npcs"] = {
        "Velha Magda": {
            "name": "Velha Magda",
            "role": "Vidente",
            "in_scene": True,
            "home_location_id": "nova_arcadia",
            "relationship": 6,
            "hidden_traits": ["supersticioso"],
            "revealed_traits": [],
            "memory": ["Leu as cartas para o herói."],
            "persona": "Guarda o que sabe sobre a Legião de Ferro.",
        }
    }
    state["faction_intel"] = {"legiao_ferro": {"known": True, "knows_goal": False}}


def _case(
    cid: str, cls: str, action: str, *, visited=None, mediated=False, trap=False, people=False
) -> dict:
    state = _base_state()
    if people:
        _with_scene_people(state)
    if visited:
        state["world"]["visited"] = list(visited)
    if mediated:
        state["interlocutor_reason"] = "meta_to_narrator"
        if people:
            state["mediated_subject_id"] = "npc_velha_magda"
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
        _case(
            "cena-2",
            "cena",
            "Examino a praça com calma, atento aos rostos.",
            people=True,
        ),
        _case("cena-3", "cena", "Sigo pela rua em direção ao mercado."),
        _case(
            "fala-mediada-1",
            "fala_mediada",
            "Narrador, o que a cidade sabe sobre isto?",
            mediated=True,
            people=True,
        ),
        _case(
            "fala-mediada-2",
            "fala_mediada",
            "Narrador, quem manda por aqui?",
            mediated=True,
            people=True,
        ),
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
                cap = budget.get("max", MAX_CALLS)
                if budget["calls"] + budget.get("foreign", 0) > cap:
                    raise SystemExit(f"teto de {cap} chamadas de LLM excedido")
                if a:
                    budget.setdefault("prints", []).append(prompt_fingerprint(a[0]))
                return bound.invoke(*a, **k)

        return _Bound()


def check_budget(n_cases: int, samples: int, max_calls: int = MAX_CALLS) -> int:
    """Recusa ANTES de qualquer chamada: previsto = 2 bracos x casos x samples."""
    if not 1 <= max_calls <= ABS_MAX_CALLS:
        raise SystemExit(f"--max-calls {max_calls} fora de 1..{ABS_MAX_CALLS}; nada foi chamado")
    planned = 2 * n_cases * samples
    print(f"chamadas de LLM previstas: {planned} (teto {max_calls})", file=sys.stderr)
    if planned > max_calls:
        raise SystemExit(
            f"previsto {planned} chamadas de LLM (2 x {n_cases} casos x {samples} samples) "
            f"> teto {max_calls}: reduza --samples/casos ou use --max-calls; nada foi chamado"
        )
    return planned


def _sweep_fakes(fakes: list[Any], saved: list[tuple[Any, Any]]) -> None:
    """Modulo importado DURANTE o guard prende o falso: devolve o original a todo `get_llm`
    que seja (por identidade) um dos falsos deste guard; o resto nao e tocado."""
    real = next((fn for m, fn in saved if getattr(m, "__name__", "") == "llm_setup"), None)
    if real is None:  # llm_setup so foi carregado dentro do guard: ja foi restaurado/inalterado
        import llm_setup

        real = llm_setup.get_llm
    if any(real is f for f in fakes):
        return
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        try:
            if any(getattr(mod, "get_llm", None) is f for f in fakes):
                mod.get_llm = real
        except (AttributeError, ImportError):  # modulo lazy/exotico: ignora
            continue


@contextlib.contextmanager
def _llm_guard(narrator: Any, budget: dict):
    """Ponto unico de LLM: o `get_llm` do narrador devolve o proxy; todo outro `get_llm` (em
    qualquer modulo carregado, inclusive `llm_setup`) e contado e levanta."""
    from agents import storyteller as st

    def foreign(*_a: Any, **_k: Any) -> Any:
        budget["foreign"] = budget.get("foreign", 0) + 1
        raise RuntimeError("chamada de LLM fora do narrador no pacote de pares")

    fakes: list[Any] = [foreign]
    saved: list[tuple[Any, Any]] = []
    for mod in list(sys.modules.values()):
        if mod is not None and mod is not st and callable(getattr(mod, "get_llm", None)):
            saved.append((mod, mod.get_llm))
            mod.get_llm = foreign
    saved.append((st, st.get_llm))
    st.get_llm = narrator_fn = lambda *a, **k: narrator
    fakes.append(narrator_fn)
    try:
        yield
    finally:
        for mod, fn in saved:
            mod.get_llm = fn
        _sweep_fakes(fakes, saved)


class _ProviderLog(logging.Handler):
    """Coleta provider/model das tentativas (`provider.attempt`); nunca texto."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.rows: list[dict] = []
        self.llm: list[dict] = []  # tentativas de LLM (hook do projeto); sem texto, sem chave

    def on_attempt(self, event: Any) -> None:
        """Hook `llm_setup.set_llm_attempt_telemetry_hook`: uma linha por candidato tentado."""
        self.llm.append(
            {
                "provider": event.provider,
                "model": event.model,
                "outcome": event.outcome,
                "http_status": event.http_status,
                "attempt_index": event.attempt_index,
                "fell_back": bool(event.fell_back),
            }
        )

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
) -> tuple[str, list[dict], str, list[dict]]:
    """Uma chamada do narrador com a flag `mode`; devolve (texto, tentativas, hash, llm)."""
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
    harvest.llm.clear()
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
    return text, list(harvest.rows), (prints[0] if prints else ""), list(harvest.llm)


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


def _run_arm(case: dict, mode: str, counted: _CountingLLM, handler: _ProviderLog, n: int) -> dict:
    """`n` amostras do braco `mode`; `text`/`counts` sao os da primeira (compat)."""
    samples: list[dict] = []
    arm_llm: list[dict] = []
    first: dict[str, Any] = {}
    for i in range(n):
        text, attempts, fp, llm_rows = _run_one(case, mode, counted, handler)
        samples.append({"text": text, **_count(text), "llm_attempts": llm_rows})
        arm_llm += [{**r, "sample": i} for r in llm_rows]
        if i == 0:
            first = {"text": text, "attempts": attempts, "input_hash": fp}
    return {
        **first,
        "counts": _count(first["text"]),
        "sample_chars": [x["chars"] for x in samples],
        "samples": samples,
        "llm_attempts": arm_llm,
    }


def _provider_set(arm: dict) -> set[str]:
    return {f"{r['provider']}/{r['model']}" for r in arm["llm_attempts"]}


def judge_comparable(pair: dict) -> tuple[bool, str]:
    """Par so serve se TODA narracao veio do primeiro candidato e os bracos usam o mesmo modelo."""
    why: list[str] = []
    for mode in ("off", "on"):
        rows = pair[mode]["llm_attempts"]
        if any(r["fell_back"] for r in rows):
            why.append(f"braco {mode}: narracao de candidato reserva (fell_back)")
        if any(r["attempt_index"] > 0 for r in rows):
            why.append(f"braco {mode}: tentativa com attempt_index > 0")
    off, on = _provider_set(pair["off"]), _provider_set(pair["on"])
    if off != on or len(off) > 1:
        why.append(f"provedor/modelo diferem: off={sorted(off)} on={sorted(on)}")
    return (not why), "; ".join(why)


def run(cases: list[dict], llm: Any, samples: int = 1, max_calls: int = MAX_CALLS) -> dict:
    import llm_setup

    check_budget(len(cases), samples, max_calls)
    budget: dict[str, Any] = {"calls": 0, "foreign": 0, "max": max_calls}
    counted = _CountingLLM(llm, budget)
    handler = _ProviderLog()
    plog = logging.getLogger("rpg.provider")
    plog.addHandler(handler)
    old_level = plog.level
    plog.setLevel(logging.DEBUG)
    old_hook = llm_setup._ATTEMPT_TELEMETRY_HOOK  # global: o script nao pode deixa-lo trocado
    llm_setup.set_llm_attempt_telemetry_hook(handler.on_attempt)
    pairs: list[dict] = []
    old_size = os.environ.get("RPG_NARRATION_SIZE")
    old_random = random.getstate()  # `_run_one` faz random.seed(1) no global
    try:
        for case in cases:
            row: dict[str, Any] = {"id": case["id"], "expected_class": case["expected_class"]}
            row["action"] = case["action"]
            for mode in ("off", "on"):
                row[mode] = _run_arm(case, mode, counted, handler, samples)
            if row["off"]["input_hash"] != row["on"]["input_hash"]:
                raise SystemExit(f"caso {case['id']}: entradas de off e on divergem (par invalido)")
            row["input_hash"] = row["off"]["input_hash"]
            row["comparavel"], row["motivo"] = judge_comparable(row)
            pairs.append(row)
    finally:
        llm_setup.set_llm_attempt_telemetry_hook(old_hook)
        plog.removeHandler(handler)
        plog.setLevel(old_level)
        random.setstate(old_random)
        if old_size is None:
            os.environ.pop("RPG_NARRATION_SIZE", None)
        else:
            os.environ["RPG_NARRATION_SIZE"] = old_size
    calls = budget["calls"] + budget["foreign"]
    return {
        "git_sha": _git_sha(),
        "calls": calls,
        "summary": summarize(pairs),
        "pairs": pairs,
    }


# --------------------------------------------------------------------------- saida
def _arm_stats(counts: list[dict], size_class: str) -> dict:
    from services.narration_size import TARGETS

    target = TARGETS.get(size_class)  # type: ignore[call-overload]
    n = len(counts)
    in_range = None
    if target is not None and target.chars_max:
        ok = sum(1 for c in counts if target.chars_min <= c["chars"] <= target.chars_max)
        in_range = ok / n
    return {
        "n": n,
        "median_chars": statistics.median(c["chars"] for c in counts),
        "option_fraction": sum(1 for c in counts if c["option_lines"] > 0) / n,
        "in_range_fraction": in_range,
    }


def summarize(pairs: list[dict]) -> dict:
    """Por classe e braco: mediana de caracteres, fracao com opcoes, fracao na faixa-alvo."""
    classes: dict[str, dict] = {}
    for cls in dict.fromkeys(p["expected_class"] for p in pairs):
        mine = [p for p in pairs if p["expected_class"] == cls]
        entry: dict[str, Any] = {"control": all(p["id"].startswith("controle-") for p in mine)}
        for mode in ("off", "on"):
            entry[mode] = _arm_stats([x for p in mine for x in p[mode]["samples"]], cls)
        entry["median_diff_on_minus_off"] = (
            entry["on"]["median_chars"] - entry["off"]["median_chars"]
        )
        classes[cls] = entry
    providers = {
        mode: sorted({x for p in pairs for x in _provider_set(p[mode])}) for mode in ("off", "on")
    }
    return {"classes": classes, "providers": providers}


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.0%}"


def _render_summary(result: dict) -> list[str]:
    summ = result["summary"]
    out = ["## Resumo\n"]
    for mode in ("off", "on"):
        prov = ", ".join(summ["providers"][mode]) or "(sem tentativas registradas)"
        out.append(f"- LLM do braço `{mode}`: {prov}")
    out.append("")
    out.append("| classe | braço | n | mediana de caracteres | com opções | na faixa-alvo |")
    out.append("|---|---|---|---|---|---|")
    for cls, e in summ["classes"].items():
        for mode in ("off", "on"):
            s = e[mode]
            out.append(
                f"| {cls}{' (controle)' if e['control'] else ''} | {mode} | {s['n']} | "
                f"{s['median_chars']:g} | {_pct(s['option_fraction'])} | "
                f"{_pct(s['in_range_fraction'])} |"
            )
        diff = e["median_diff_on_minus_off"]
        out.append(f"| {cls} | on − off | | {diff:+g} | | |")
    out.append("")
    return out


def render_md(result: dict) -> str:
    out = [f"# Pares de narração (SPEC-428) · sha {result['git_sha']}\n"]
    bad = [p for p in result["pairs"] if not p.get("comparavel", True)]
    if bad:
        out.append("> **AVISO: pacote NÃO comparável; não use para a leitura do dono.**\n")
        out += [f"> - `{p['id']}`: {p['motivo']}" for p in bad]
        out.append("")
    out += _render_summary(result)
    for pair in result["pairs"]:
        out.append(f"## {pair['id']} · classe `{pair['expected_class']}`\n")
        out.append(f"Ação: {pair['action']}\n")
        for mode in ("off", "on"):
            arm = pair[mode]
            prov = ", ".join(sorted(_provider_set(arm))) or "?"
            for i, smp in enumerate(arm["samples"], 1):
                tag = f" · amostra {i}" if len(arm["samples"]) > 1 else ""
                out.append(
                    f"### {mode}{tag} · {smp['chars']} caracteres · {smp['paragraphs']} parágrafos"
                    f" · {smp['option_lines']} linhas de opção · {prov}\n"
                )
                out.append(smp["text"] + "\n")
    return "\n".join(out)


def counts_only(result: dict) -> dict:
    pairs = []
    for pair in result["pairs"]:
        row = {
            "id": pair["id"],
            "expected_class": pair["expected_class"],
            "input_hash": pair["input_hash"],
            "comparavel": pair["comparavel"],
            "motivo": pair["motivo"],
        }
        for mode in ("off", "on"):
            row[mode] = {
                "counts": pair[mode]["counts"],
                "sample_chars": pair[mode]["sample_chars"],
                "samples": [
                    {k: v for k, v in smp.items() if k not in ("text", "llm_attempts")}
                    for smp in pair[mode]["samples"]
                ],
                "attempts": pair[mode]["attempts"],
                "llm_attempts": pair[mode]["llm_attempts"],
            }
        pairs.append(row)
    return {
        "git_sha": result["git_sha"],
        "calls": result["calls"],
        "summary": result["summary"],
        "pairs": pairs,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument(
        "--max-calls",
        type=int,
        default=MAX_CALLS,
        help=f"teto de chamadas de LLM (default {MAX_CALLS}, maximo {ABS_MAX_CALLS})",
    )
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
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    samples = max(1, args.samples)
    check_budget(len(cases), samples, args.max_calls)  # recusa antes de resolver o LLM
    llm = _resolve_llm(args.mock)
    result = run(cases, llm, samples, args.max_calls)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".md").write_text(render_md(result), encoding="utf-8")
    args.out.with_suffix(".json").write_text(
        json.dumps(counts_only(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    bad = [p["id"] for p in result["pairs"] if not p["comparavel"]]
    if bad:
        print(f"PACOTE NAO COMPARAVEL ({len(bad)} pares): {', '.join(bad)}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
