"""Suíte da Fase 5.3 — telemetria + relatório agregado (offline, MockLLM)."""
import glob
import json
import os

from playtest import pricing, report, telemetry
from playtest.runner import run_campaign


# --- Etapa 1 — telemetria por turno + summary ------------------------------

def test_jsonl_uma_linha_por_turno(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    res = run_campaign("explorador", turns=5, seed=1)
    telemetry.persist_campaign("run1", res)
    jsonl = os.path.join(str(tmp_path), "run1", f"{res.profile}_{res.seed}.jsonl")
    with open(jsonl, encoding="utf-8") as f:
        linhas = [json.loads(l) for l in f if l.strip()]
    assert len(linhas) == 5
    assert all("turn" in r and "route" in r and "cost_usd" in r for r in linhas)


def test_summary_campos_obrigatorios(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))
    res = run_campaign("explorador", turns=5, seed=1)
    summ = telemetry.persist_campaign("run1", res)
    for campo in ("profile", "seed", "turns_completed", "errors", "violations",
                  "routes", "latency_ms", "deaths", "final_level", "final_gold",
                  "locations_visited", "quests", "llm_requests_by_provider",
                  "cost_usd_total", "cost_usd_by_tier", "fell_back_turns", "mock"):
        assert campo in summ, campo


def test_violacao_aparece_no_turno_e_no_summary(tmp_path, monkeypatch):
    import main
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path))

    class _Corrupt:
        def __init__(self, real):
            self.real, self.n = real, 0

        def invoke(self, state, *a, **k):
            self.n += 1
            out = self.real.invoke(state, *a, **k)
            if self.n == 3:
                out["player"]["gold"] = -100
            return out

    monkeypatch.setattr(main, "app", _Corrupt(main.app))
    res = run_campaign("explorador", turns=4, seed=1, invariants=True)
    summ = telemetry.persist_campaign("run1", res)
    assert summ["violations"].get("economy.gold_negative", 0) >= 1
    jsonl = os.path.join(str(tmp_path), "run1", f"{res.profile}_{res.seed}.jsonl")
    with open(jsonl, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f if l.strip()]
    assert any("economy.gold_negative" in r["violations"] for r in recs)


# --- Etapa 2 — agregação + relatório ---------------------------------------

def _synthetic_run(dirpath, profile, seed, errors=0, violations=None):
    os.makedirs(dirpath, exist_ok=True)
    summ = {
        "profile": profile, "seed": seed, "turns_completed": 10, "errors": errors,
        "violations": violations or {}, "routes": {"storyteller": 8, "combat_agent": 2},
        "latency_ms": {"p50": 30, "p95": 90}, "deaths": 0, "final_level": 2,
        "final_gold": 40, "locations_visited": 5, "quests": {"created": 1, "completed": 0},
        "llm_requests_by_provider": {"groq": 10}, "cost_usd_total": 0.05,
        "cost_usd_by_tier": {"fast": 0.03, "smart": 0.02}, "fell_back_turns": 1, "mock": False,
    }
    with open(os.path.join(dirpath, f"{profile}_{seed}.summary.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f)
    with open(os.path.join(dirpath, f"{profile}_{seed}.jsonl"), "w", encoding="utf-8") as f:
        for t in range(1, 11):
            err = "boom" if (errors and t == 2) else None
            f.write(json.dumps({"turn": t, "route": "storyteller", "error": err,
                                "violations": []}) + "\n")


def test_aggregate_cruza_campanhas(tmp_path):
    run_dir = os.path.join(str(tmp_path), "runX")
    _synthetic_run(run_dir, "explorador", 1, errors=1, violations={"economy.gold_negative": 2})
    _synthetic_run(run_dir, "combate", 2, errors=0, violations={"economy.gold_negative": 1})
    rep = report.aggregate(run_dir)
    assert len(rep.campaigns) == 2
    assert dict(rep.top_violations).get("economy.gold_negative") == 3
    assert dict(rep.top_errors).get("storyteller") == 1


def test_render_markdown_secoes_canonicas(tmp_path):
    run_dir = os.path.join(str(tmp_path), "runX")
    _synthetic_run(run_dir, "explorador", 1, violations={"vitals.hp_bounds": 1})
    md = report.render_markdown(report.aggregate(run_dir))
    assert "## Por perfil" in md
    assert "## Violações" in md
    assert "## Erros" in md


def test_baseline_gera_deltas(tmp_path):
    cur = os.path.join(str(tmp_path), "cur")
    base = os.path.join(str(tmp_path), "base")
    _synthetic_run(cur, "explorador", 1, errors=3)
    _synthetic_run(base, "explorador", 1, errors=1)
    rep = report.aggregate(cur, base)
    assert rep.deltas is not None
    assert rep.deltas["errors"] == 2  # 3 - 1
    assert "## Deltas" in report.render_markdown(rep)


# --- Etapa 3 — teto de orçamento + custo -----------------------------------

def test_custo_por_modelo_da_tabela():
    # 1M tokens de entrada, 0 de saída → exatamente o preço_in do modelo.
    assert pricing.estimate_cost("gemini-pro-latest", 1_000_000, 0) == 1.25
    assert pricing.estimate_cost("openai/gpt-oss-20b", 0, 1_000_000) == 0.30
    # modelo desconhecido cai no default.
    assert pricing.estimate_cost("modelo-fantasma", 1_000_000, 0) == 1.00


def _emit_wrapper(main_mod, monkeypatch):
    """Faz o grafo emitir 1 evento de telemetria por invoke (simula LLM real)."""
    import llm_setup
    from llm_setup import ModelTier

    class _Emit:
        def __init__(self, real):
            self.real = real

        def invoke(self, state, *a, **k):
            out = self.real.invoke(state, *a, **k)
            llm_setup._emit_telemetry("groq", "openai/gpt-oss-20b", ModelTier.FAST, 10, False)
            return out

    monkeypatch.setattr(main_mod, "app", _Emit(main_mod.app))


def test_max_requests_aborta_educadamente(monkeypatch):
    import main
    _emit_wrapper(main, monkeypatch)
    res = run_campaign("explorador", turns=10, seed=1, max_requests=3)
    assert res.aborted_reason is not None
    assert "max_requests" in res.aborted_reason
    assert res.turns_completed < 10


def test_max_cost_aborta_educadamente(monkeypatch):
    import main
    _emit_wrapper(main, monkeypatch)
    # cada invoke ~0.00024 USD; teto baixo aborta em poucos turnos.
    res = run_campaign("explorador", turns=20, seed=1, max_cost=0.0005)
    assert res.aborted_reason is not None
    assert "max_cost" in res.aborted_reason
    assert res.turns_completed < 20
