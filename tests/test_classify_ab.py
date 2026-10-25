"""SPEC-317 R1 - harness do A/B de CLASSIFY (offline: so a parte pura)."""

from __future__ import annotations

import json

from scripts.staging import classify_ab as ab
from scripts.staging import vercel_env as ve


def _rows(routes, ms, source="classify"):
    return [
        {"i": i, "route": r, "source": source, "ms": m} for i, (r, m) in enumerate(zip(routes, ms))
    ]


def test_promote_when_faster_and_agreeing():
    ds = _rows(["npc_actor"] * 19 + ["loot"], [1500] * 20)
    gq = _rows(["npc_actor"] * 19 + ["loot"], [600] * 20)
    out = ab.summarize(gq, ds)
    assert out["agreement"] == 1.0 and out["latency_drop_p50"] == 0.6
    assert out["promote_groq_first"] is True


def test_no_promotion_when_agreement_low_or_not_faster():
    ds = _rows(["npc_actor"] * 10, [1500] * 10)
    low_agree = _rows(["storyteller"] * 3 + ["npc_actor"] * 7, [600] * 10)
    assert ab.summarize(low_agree, ds)["promote_groq_first"] is False
    slow = _rows(["npc_actor"] * 10, [1400] * 10)
    assert ab.summarize(slow, ds)["promote_groq_first"] is False


def test_gate_decided_inputs_do_not_count():
    ds = _rows(["storyteller"] * 5, [3] * 5, source="story_regex")
    gq = _rows(["storyteller"] * 5, [3] * 5, source="story_regex")
    out = ab.summarize(gq, ds)
    assert out["inputs_compared"] == 0 and out["promote_groq_first"] is False


def test_dataset_is_loadable_read_only():
    inputs = ab.load_inputs()
    assert inputs and all(isinstance(t, str) for t in inputs)


def test_inline_routes_json_is_accepted_by_llm_setup(monkeypatch):
    import llm_setup

    monkeypatch.setenv("RPG_ROUTES", json.dumps(ab.GROQ_FIRST))
    routes = llm_setup._load_routes()
    assert routes[llm_setup.ModelTier.CLASSIFY][0] == ("groq", "openai/gpt-oss-20b")
    assert routes[llm_setup.ModelTier.FAST] == llm_setup.ROUTES[llm_setup.ModelTier.FAST]


def test_vercel_env_classify_routes_flag():
    files = {k: f"v-{k}" for k in ve.SECRET_FROM_FILE}
    prod, _ = ve.build_env(files, classify_routes="groq_first")
    assert json.loads(prod["RPG_ROUTES"]) == ab.GROQ_FIRST
    prod_default, _ = ve.build_env(files)
    # sem --classify-routes o script nao gerencia (nem apaga) um RPG_ROUTES posto a mao
    assert "RPG_ROUTES" not in prod_default and "RPG_ROUTES" not in ve.stale_names(prod_default)
    prod_flags, _ = ve.build_env(
        files, world_flags={"RPG_ROUTER_DETERMINISTIC_NPC": "on", "RPG_PROMPT_STATIC_FIRST": "on"}
    )
    assert prod_flags["RPG_ROUTER_DETERMINISTIC_NPC"] == "on"
