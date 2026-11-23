"""SPEC-428 R12: script do pacote de pares (`scripts/dev/narration_pairs.py`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "docs" / "spec428" / "pares_casos.json"

sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import narration_pairs as np_  # noqa: E402


def test_committed_cases_match_generator():
    assert json.loads(CASES.read_text(encoding="utf-8")) == np_.build_cases()


def test_mock_run_makes_ten_pairs_with_expected_classes(tmp_path, monkeypatch):
    from services import narration_size as ns

    seen: list[str] = []
    real = ns.classify

    def spy(t):
        seen.append(real(t))
        return seen[-1]

    monkeypatch.setattr(ns, "classify", spy)
    out = tmp_path / "pares"
    rc = np_.main(["--cases", str(CASES), "--out", str(out), "--mock"])
    assert rc == 0
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert len(data["pairs"]) == 10
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    # `on` classifica 1x por caso (o `off` nao loga nem classifica)
    assert seen == [c["expected_class"] for c in cases]
    assert out.with_suffix(".md").read_text(encoding="utf-8").count("### on") == 10


def test_json_has_only_counts(tmp_path):
    out = tmp_path / "pares"
    assert np_.main(["--cases", str(CASES), "--out", str(out), "--mock"]) == 0
    raw = out.with_suffix(".json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "text" not in raw and "git_sha" in data
    for pair in data["pairs"]:
        assert set(pair["off"]["counts"]) == {"chars", "paragraphs", "option_lines"}


def test_refuses_without_key_and_without_mock(tmp_path, monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.setattr("llm_setup.get_llm", lambda *a, **k: type("M", (), {"is_mock": True})())
    with pytest.raises(SystemExit, match="sem chave"):
        np_.main(["--cases", str(CASES), "--out", str(tmp_path / "x")])
    assert not (tmp_path / "x.md").exists()


def test_refuses_with_force_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    with pytest.raises(SystemExit, match="RPG_FORCE_MOCK"):
        np_.main(["--cases", str(CASES), "--out", str(tmp_path / "x")])


def test_call_budget_aborts():
    class _L:
        def with_structured_output(self, *a, **k):
            return self

        def invoke(self, *a, **k):
            return None

    counted = np_._CountingLLM(_L(), {"calls": np_.MAX_CALLS})
    with pytest.raises(SystemExit):
        counted.with_structured_output(None).invoke([])


def _cases() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def _boom(*_a, **_k):
    raise AssertionError("chamada real de LLM no teste do pacote de pares")


def test_world_pulse_llm_is_neutralised(monkeypatch):
    """P2-1: com o LLM do mundo explodindo, o run --mock ainda gera os 10 pares (sem chamar)."""
    import llm_setup
    from agents import world_simulator

    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")  # caminho `simulate_world`, que chamaria LLM
    monkeypatch.setattr(world_simulator, "get_llm", _boom)
    monkeypatch.setattr(llm_setup, "get_llm", _boom)
    result = np_.run(_cases(), np_._FakeNarrator())
    assert len(result["pairs"]) == 10
    assert result["calls"] == 20  # 10 casos x 2 bracos, so o narrador


def test_zero_llm_calls_outside_narrator(monkeypatch):
    import llm_setup
    from agents import storyteller as st

    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")  # caminho `simulate_world`, que chamaria LLM
    monkeypatch.setattr(llm_setup, "get_llm", _boom)
    budget = {"calls": 0, "foreign": 0}
    counted = np_._CountingLLM(np_._FakeNarrator(), budget)
    with np_._llm_guard(counted, budget):
        assert st.get_llm() is counted  # o narrador recebe o proxy contado
        with pytest.raises(RuntimeError):
            llm_setup.get_llm()  # qualquer outro ponto de LLM levanta e e contado
    assert budget["foreign"] == 1
    result = np_.run(_cases(), np_._FakeNarrator())
    assert result["calls"] == 20


def test_budget_refuses_before_any_call(tmp_path):
    class _Spy(np_._FakeNarrator):
        n = 0

        def invoke(self, *a, **k):
            _Spy.n += 1
            return super().invoke(*a, **k)

    with pytest.raises(SystemExit, match="previsto 40"):
        np_.run(_cases(), _Spy(), samples=2)
    assert _Spy.n == 0
    with pytest.raises(SystemExit, match="previsto"):
        np_.main(["--cases", str(CASES), "--out", str(tmp_path / "x"), "--mock", "--samples", "2"])
    assert not (tmp_path / "x.md").exists()


def test_pairs_carry_input_hash_and_fail_on_divergence(tmp_path, monkeypatch):
    out = tmp_path / "pares"
    assert np_.main(["--cases", str(CASES), "--out", str(out), "--mock"]) == 0
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert all(len(p["input_hash"]) == 16 for p in data["pairs"])
    seq = iter(range(1000))
    monkeypatch.setattr(np_, "prompt_fingerprint", lambda _m: str(next(seq)))
    with pytest.raises(SystemExit, match="divergem"):
        np_.run(_cases(), np_._FakeNarrator())


def test_fingerprint_ignores_only_size_lines():
    a = ["x\n- Responda em 2 a 3 parágrafos.\nfim"]
    b = [
        "x\n- Responda em 2 a 3 parágrafos, salvo quando TAMANHO DA RESPOSTA, abaixo\n"
        "    - TAMANHO DA RESPOSTA: 1\nfim"
    ]
    assert np_.prompt_fingerprint(a) == np_.prompt_fingerprint(b)
    assert np_.prompt_fingerprint(a) != np_.prompt_fingerprint(["y\nfim"])


def _fake_leftovers() -> list[str]:
    return [
        name
        for name, mod in list(sys.modules.items())
        if mod is not None
        and getattr(getattr(mod, "get_llm", None), "__qualname__", "").startswith("_llm_guard")
    ]


def test_run_leaves_no_fake_get_llm_in_any_module(monkeypatch):
    """P1-1: modulo importado DURANTE o guard nao pode ficar com o `get_llm` falso."""
    monkeypatch.delitem(sys.modules, "agents.campaign_manager", raising=False)
    # `local-visitado` (viagem) e o caso que chega ao import preguicoso de campaign_manager
    case = [c for c in _cases() if c["id"] == "local-visitado"]
    assert case
    np_.run(case, np_._FakeNarrator())
    assert _fake_leftovers() == []


def test_guard_restores_imported_during_body_and_on_exception():
    import llm_setup

    original = llm_setup.get_llm
    mod = type(sys)("fake_mod_in_guard")
    budget = {"calls": 0, "foreign": 0}
    with pytest.raises(ValueError), np_._llm_guard(np_._FakeNarrator(), budget):
        mod.get_llm = llm_setup.get_llm  # `from llm_setup import get_llm` durante o guard
        sys.modules["fake_mod_in_guard"] = mod
        sys.modules["fake_none_mod"] = None
        raise ValueError("corpo falhou")
    try:
        assert llm_setup.get_llm is original
        assert mod.get_llm is original
    finally:
        sys.modules.pop("fake_mod_in_guard", None)
        sys.modules.pop("fake_none_mod", None)


def test_guard_keeps_get_llm_replaced_on_purpose():
    sentinel = lambda *a, **k: "meu"  # noqa: E731
    mod = type(sys)("fake_mod_sentinel")
    budget = {"calls": 0, "foreign": 0}
    with np_._llm_guard(np_._FakeNarrator(), budget):
        mod.get_llm = sentinel
        sys.modules["fake_mod_sentinel"] = mod
    try:
        assert mod.get_llm is sentinel
    finally:
        sys.modules.pop("fake_mod_sentinel", None)


def test_run_restores_env_and_world_pulse(monkeypatch):
    from agents import storyteller as st

    monkeypatch.setenv("RPG_NARRATION_SIZE", "orig")
    pulse, enc = st._story_world_pulse, st.check_encounter
    np_.run(_cases()[:1], np_._FakeNarrator())
    import os

    assert os.environ["RPG_NARRATION_SIZE"] == "orig"
    assert st._story_world_pulse is pulse and st.check_encounter is enc


def test_run_restores_global_random_state():
    import random

    random.seed(12345)
    control = random.Random()
    control.setstate(random.getstate())
    np_.run(_cases()[:1], np_._FakeNarrator())
    assert [random.random() for _ in range(3)] == [control.random() for _ in range(3)]


# ----------------------------------------------------------------- tentativas de LLM, teto, resumo
def _scripted(plan):
    """Narrador roteirizado: emite um `LLMAttemptEvent` por chamada pelo hook global do projeto.

    `plan(i)` -> (provider, model, fell_back[, outcome[, attempt_index]]) ou None (sem tentativa).
    Com outcome diferente de `success` devolve um `AIMessage` (como o `FallbackLLM` esgotado).
    """
    from langchain_core.messages import AIMessage

    import llm_setup
    from agents.storyteller import StoryUpdate

    class _S(np_._FakeNarrator):
        n = 0

        def invoke(self, *a, **k):
            i = _S.n
            _S.n += 1
            step = plan(i)
            if step is None:
                return StoryUpdate(narrative=self.TEXT)
            prov, model, fell, *rest = step
            outcome = rest[0] if rest else "success"
            index = rest[1] if len(rest) > 1 else (1 if fell else 0)
            llm_setup._emit_attempt_telemetry(
                llm_setup.LLMAttemptEvent(
                    provider=prov,
                    model=model,
                    tier=llm_setup.ModelTier.SMART,
                    attempt_index=index,
                    latency_ms=1,
                    fell_back=fell,
                    outcome=outcome,
                    error=None,
                    structured=True,
                )
            )
            if outcome != "success":
                return AIMessage(content="erro do provedor")
            return StoryUpdate(narrative=self.TEXT)

    return _S()


def _ok_plan(_i):
    return ("deepseek", "deepseek-chat", False)


def test_llm_attempts_recorded_per_arm():
    result = np_.run(_cases()[:2], _scripted(_ok_plan))
    for pair in result["pairs"]:
        for mode in ("off", "on"):
            rows = pair[mode]["llm_attempts"]
            assert [(r["provider"], r["model"], r["fell_back"]) for r in rows] == [
                ("deepseek", "deepseek-chat", False)
            ]
            assert set(rows[0]) >= {"outcome", "http_status", "attempt_index", "provider", "model"}
        assert pair["comparavel"] is True and pair["motivo"] == ""
    assert result["summary"]["providers"] == {
        "off": ["deepseek/deepseek-chat"],
        "on": ["deepseek/deepseek-chat"],
    }


def _trigger(kind):
    """Plano que liga SO o gatilho `kind` (a 2a chamada e o braco `on` do caso 1)."""
    base = ("deepseek", "deepseek-chat", False)
    return {
        "fell_back": lambda i: (
            ("deepseek", "deepseek-chat", True, "success", 0) if i == 1 else base
        ),
        "attempt_index": lambda i: (
            ("deepseek", "deepseek-chat", False, "success", 1) if i == 1 else base
        ),
        "provider": lambda i: ("groq", "deepseek-chat", False) if i == 1 else base,
        "model": lambda i: ("deepseek", "outro-modelo", False) if i == 1 else base,
        "invoke_error": lambda i: (*base, "invoke_error") if i == 1 else base,
        "invalid_structured": lambda i: (*base, "invalid_structured") if i == 1 else base,
        "no_attempt": lambda i: None if i == 1 else base,
    }[kind]


@pytest.mark.parametrize(
    "kind",
    [
        "fell_back",
        "attempt_index",
        "provider",
        "model",
        "invoke_error",
        "invalid_structured",
        "no_attempt",
    ],
)
def test_non_comparable_pair_marked_warned_and_rc_nonzero(tmp_path, monkeypatch, kind):
    cases = tmp_path / "c.json"
    cases.write_text(json.dumps(_cases()[:2]), encoding="utf-8")
    out = tmp_path / "pares"
    monkeypatch.setattr(np_, "_resolve_llm", lambda _m: _scripted(_trigger(kind)))
    rc = np_.main(["--cases", str(cases), "--out", str(out), "--mock"])
    assert rc != 0
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert [p["comparavel"] for p in data["pairs"]] == [False, True]
    assert data["pairs"][0]["motivo"]
    if kind in ("invoke_error", "invalid_structured"):
        assert f"braco on amostra 1: outcome {kind}" in data["pairs"][0]["motivo"]
    if kind == "no_attempt":
        assert "braco on amostra 1: nenhuma tentativa" in data["pairs"][0]["motivo"]
    md = out.with_suffix(".md").read_text(encoding="utf-8")
    assert md.index("NÃO comparável") < md.index("## cena-1")
    # o par invalido nao entra nas medianas; o valido (cena-2) sim
    summ = data["summary"]
    assert summ["excluded_pairs"] == ["cena-1"]
    assert summ["classes"]["cena"]["on"]["n"] == 1


def test_fallback_text_never_counts_in_summary(tmp_path, monkeypatch):
    """invoke_error + AIMessage: o no usa o texto deterministico; ele nao entra em mediana alguma."""
    cases = tmp_path / "c.json"
    cases.write_text(json.dumps(_cases()[:1]), encoding="utf-8")
    out = tmp_path / "pares"
    plan = lambda i: ("deepseek", "deepseek-chat", False, "invoke_error")  # noqa: E731
    monkeypatch.setattr(np_, "_resolve_llm", lambda _m: _scripted(plan))
    assert np_.main(["--cases", str(cases), "--out", str(out), "--mock"]) == 3
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["summary"]["classes"] == {} and data["summary"]["excluded_pairs"] == ["cena-1"]


def test_budget_line_printed_before_any_call(tmp_path, monkeypatch, capsys):
    def boom_if_early(*_a, **_k):
        assert "chamadas de LLM previstas: 20 (teto 30)" in capsys.readouterr().err
        return np_._FakeNarrator()

    monkeypatch.setattr(np_, "_resolve_llm", boom_if_early)
    out = tmp_path / "x"
    assert np_.main(["--cases", str(CASES), "--out", str(out), "--mock"]) == 0


def test_attempt_hook_restored_on_exit_and_on_error(monkeypatch):
    import llm_setup

    def sentinel(_e):
        return None

    llm_setup.set_llm_attempt_telemetry_hook(sentinel)
    try:
        np_.run(_cases()[:1], _scripted(_ok_plan))
        assert llm_setup._ATTEMPT_TELEMETRY_HOOK is sentinel

        seq = iter(range(1000))
        monkeypatch.setattr(np_, "prompt_fingerprint", lambda _m: str(next(seq)))
        with pytest.raises(SystemExit, match="divergem"):  # corpo do run falha no meio
            np_.run(_cases()[:1], _scripted(_ok_plan))
        assert llm_setup._ATTEMPT_TELEMETRY_HOOK is sentinel
    finally:
        llm_setup.set_llm_attempt_telemetry_hook(None)


def test_samples_three_with_max_calls_sixty_runs(tmp_path):
    scripted = _scripted(_ok_plan)
    result = np_.run(_cases(), scripted, samples=3, max_calls=60)
    assert result["calls"] == 60 and type(scripted).n == 60
    pair = result["pairs"][0]
    assert len(pair["off"]["samples"]) == 3 and len(pair["on"]["samples"]) == 3
    data = np_.counts_only(result)["pairs"][0]["on"]["samples"]
    assert [set(s) for s in data] == [{"chars", "paragraphs", "option_lines"}] * 3
    md = np_.render_md(result)
    assert md.count("### off · amostra") == 30 and md.count("### on · amostra") == 30


def test_budget_refusals_before_any_call(tmp_path):
    scripted = _scripted(_ok_plan)
    with pytest.raises(SystemExit, match="previsto 60"):
        np_.run(_cases(), scripted, samples=3)  # teto default 30
    with pytest.raises(SystemExit, match="max-calls 500"):
        np_.run(_cases(), scripted, samples=1, max_calls=500)
    base = ["--cases", str(CASES), "--out", str(tmp_path / "x"), "--mock"]
    with pytest.raises(SystemExit, match="previsto 60"):
        np_.main([*base, "--samples", "3"])
    with pytest.raises(SystemExit, match="max-calls 500"):
        np_.main([*base, "--max-calls", "500"])
    assert type(scripted).n == 0 and not (tmp_path / "x.md").exists()


def test_summary_hand_checked():
    """2 casos `cena` (faixa 750..1000): off 800/900 e 1200/1300; on 700/800 e 900/950.

    Textos de `n` caracteres: o corpo `a`*n sem linha de opcao; opcoes so no `on` do caso 1.
    """
    from services.narration_size import TARGETS

    assert (TARGETS["cena"].chars_min, TARGETS["cena"].chars_max) == (750, 1000)
    plan = {
        ("cena-1", "off"): [800, 1200],
        ("cena-1", "on"): [700, 900],
        ("cena-2", "off"): [900, 1300],
        ("cena-2", "on"): [800, 950],
    }

    def arm(cid, mode, opts=False):
        smp = []
        for n in plan[(cid, mode)]:
            text = "a" * (n - 5) + "\n— Ir" if opts else "a" * n
            smp.append({"text": text, **np_._count(text), "llm_attempts": []})
        return {"samples": smp, "llm_attempts": []}

    pairs = [
        {"id": "cena-1", "comparavel": True, "expected_class": "cena", "off": arm("cena-1", "off"),
         "on": arm("cena-1", "on", opts=True)},
        {"id": "cena-2", "comparavel": True, "expected_class": "cena", "off": arm("cena-2", "off"),
         "on": arm("cena-2", "on")},
    ]  # fmt: skip
    cls = np_.summarize(pairs)["classes"]["cena"]
    # off: 800, 1200, 900, 1300 -> mediana 1050; na faixa: 800 e 900 -> 2/4; sem opcoes
    assert cls["off"] == {
        "n": 4, "median_chars": 1050.0, "option_fraction": 0.0, "in_range_fraction": 0.5
    }  # fmt: skip
    # on: 700, 900, 800, 950 -> mediana 850; na faixa: 900, 800, 950 -> 3/4; opcoes em 2/4
    assert cls["on"] == {
        "n": 4, "median_chars": 850.0, "option_fraction": 0.5, "in_range_fraction": 0.75
    }  # fmt: skip
    assert cls["median_diff_on_minus_off"] == -200.0 and cls["control"] is False
