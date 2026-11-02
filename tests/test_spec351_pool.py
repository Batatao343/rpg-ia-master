"""SPEC-351 Etapa 5 — NPC pessoal, token e pool compartilhado (R14–R18)."""

from __future__ import annotations

import pytest

from playtest import opening_checks as oc
from services import prologue
from services import shared_pool as sp
from services.shared_pool_models import PoolNamespace, PoolStatus
from tests.spec297_support import NOW, FakeJudge, make_store

SECRET = "t" * 40
CHAR = {
    "name": "Aranel",
    "race": "Elfo",
    "class_name": "Arcanista Cinzento",
    "region": "Nova Arcádia",
    "level": 1,
    "backstory": "saí do Anel Dourado depois que minha irmã parou de me reconhecer",
}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("RPG_SESSION_SECRET", SECRET)
    monkeypatch.setenv("RPG_SHARED_POOL", "shadow")
    monkeypatch.setenv("RPG_POOL_HOLD_HOURS", "0")
    monkeypatch.setenv("RPG_POOL_ALLOW_MOCK_EVAL", "1")
    st = make_store(tmp_path)
    monkeypatch.setattr(sp, "get_store", lambda: st)
    return st


def _built():
    scenario, _m, ctx = prologue.build_start_scenario_ctx(CHAR)
    return scenario, ctx


def test_seed_rolled_before_llm_and_in_prompt(monkeypatch):
    seen = {}

    class _LLM:
        is_mock = False

        def with_structured_output(self, _s):
            class _B:
                def invoke(_self, messages):
                    seen["system"] = messages[0].content
                    return None

            return _B()

    monkeypatch.setattr(prologue, "get_llm", lambda *a, **k: _LLM())
    _scenario, _m, ctx = prologue.build_start_scenario_ctx(CHAR)
    assert "<SEMENTE_NPC_PESSOAL>" in seen["system"]
    assert "profissao:" in seen["system"] and "desejo:" in seen["system"]
    assert ctx["nonce"] and ctx["slot"] >= 0
    # o template (sem NPC pessoal) descarta a semente e não entra no token
    assert ctx["seed"] is None
    assert prologue.sign_for_client(_scenario, ctx, "legacy") == ""


def test_token_roundtrip_and_tamper_goes_local_only(monkeypatch):
    monkeypatch.setenv("RPG_SESSION_SECRET", SECRET)
    scenario, ctx = _built()
    token = prologue.sign_for_client(scenario, ctx, "dono-1")
    assert token
    start = "nova_arcadia"
    assert prologue.verified_seed(scenario, token, "dono-1", start) == ctx["seed"]
    # persona alterada no cliente
    tampered = scenario.model_copy(
        update={
            "personal_npc": scenario.personal_npc.model_copy(update={"persona_public": "outra"})
        }
    )
    assert prologue.verified_seed(tampered, token, "dono-1", start) is None
    # outro dono, sem token, token de lixo
    assert prologue.verified_seed(scenario, token, "dono-2", start) is None
    assert prologue.verified_seed(scenario, None, "dono-1", start) is None
    assert prologue.verified_seed(scenario, "lixo", "dono-1", start) is None
    # vencido
    from services import prologue_token as pt

    nonce, slot, sig = token.split(".", 2)
    issued = int(sig.split(".")[1])
    monkeypatch.setattr(pt.time, "time", lambda: issued + pt.TOKEN_MAX_AGE + 5)
    assert prologue.verified_seed(scenario, token, "dono-1", start) is None
    # sem segredo (D8)
    monkeypatch.delenv("RPG_SESSION_SECRET")
    assert prologue.sign_for_client(scenario, ctx, "dono-1") == ""
    assert prologue.verified_seed(scenario, token, "dono-1", start) is None


def test_pool_document_only_public_layer():
    scenario, ctx = _built()
    doc = prologue.personal_pool_document(scenario.personal_npc, ctx["seed"])
    assert set(doc) <= oc._allowed_keys()
    blob = " ".join(oc._doc_strings(doc)).lower()
    for forbidden in (
        scenario.personal_npc.bond,
        CHAR["name"],
        CHAR["backstory"],
        scenario.seeking,
        scenario.plot_npc_id,
        *scenario.thread_refs,
    ):
        assert forbidden.lower() not in blob
    assert "attitude" not in doc and "bond" not in doc
    assert oc.check_personal_npc_private(
        doc, character_name=CHAR["name"], backstory=CHAR["backstory"], seeking=scenario.seeking
    ).ok


def test_player_typed_name_never_promotes(store):
    scenario, ctx = _built()
    typed = scenario.model_copy(
        update={"personal_npc": scenario.personal_npc.model_copy(update={"name": "Toren"})}
    )
    char = {**CHAR, "backstory": "procuro meu pai, Toren"}
    entry_id = prologue.submit_personal_npc(
        typed, ctx["seed"], game_id="g1", region_id="nova_arcadia", char_input=char
    )
    entry = store.get(entry_id)
    assert entry.name_origin == "player" and entry.status == PoolStatus.LOCAL_ONLY


def test_backstory_shingle_rejected_by_validators(store):
    scenario, ctx = _built()
    leaky = scenario.personal_npc.model_copy(
        update={
            "persona_public": "saí do Anel Dourado depois que minha irmã parou de me reconhecer"
        }
    )
    leaky_sc = scenario.model_copy(update={"personal_npc": leaky})
    entry_id = prologue.submit_personal_npc(
        leaky_sc, ctx["seed"], game_id="g1", region_id="nova_arcadia", char_input=CHAR
    )
    from services.shared_pool_validators import run_validators

    codes = {f.code for f in run_validators(store.get(entry_id), owner_values=[CHAR["name"]])}
    assert "literal_player_text" in codes


def test_pool_off_means_no_submit(store, monkeypatch):
    monkeypatch.setenv("RPG_SHARED_POOL", "off")
    scenario, ctx = _built()
    assert (
        prologue.submit_personal_npc(
            scenario, ctx["seed"], game_id="g1", region_id="nova_arcadia", char_input=CHAR
        )
        is None
    )
    assert store.select(namespace=PoolNamespace.NPC, statuses=list(PoolStatus)) == []


def test_submit_failure_does_not_raise(store, monkeypatch):
    scenario, ctx = _built()

    def boom(*a, **k):
        raise RuntimeError("store caiu")

    monkeypatch.setattr(sp, "submit", boom)
    assert (
        prologue.submit_personal_npc(
            scenario, ctx["seed"], game_id="g1", region_id="nova_arcadia", char_input=CHAR
        )
        is None
    )


def test_promote_due_with_fake_judge_promotes_clean_personal_npc(store):
    scenario, ctx = _built()
    entry_id = prologue.submit_personal_npc(
        scenario, ctx["seed"], game_id="g1", region_id="nova_arcadia", char_input=CHAR
    )
    assert store.get(entry_id).status == PoolStatus.HELD
    out = sp.promote_due(
        store,
        now=NOW.replace(year=2030),
        llm=FakeJudge(),
        embedder=None,
        embedding_profile="x",
        owner_values=lambda e: [CHAR["name"]],
    )
    assert out["promoted"] == 1, out
    promoted = store.get(entry_id)
    assert promoted.status == PoolStatus.PROMOTED
    assert CHAR["name"].lower() not in " ".join(oc._doc_strings(promoted.document)).lower()


def test_promoted_personal_npc_castable_in_other_game(store, monkeypatch):
    scenario, ctx = _built()
    entry_id = prologue.submit_personal_npc(
        scenario, ctx["seed"], game_id="g1", region_id="nova_arcadia", char_input=CHAR
    )
    sp.promote_due(
        store, now=NOW.replace(year=2030), llm=FakeJudge(), embedder=None, embedding_profile="x"
    )
    monkeypatch.setenv("RPG_SHARED_POOL", "on")
    monkeypatch.setenv("RPG_POOL_REUSE_RATE", "1")
    state = {
        "game_id": "game-outro",
        "world": {"turn_count": 3, "current_location_id": "na_anel_lama"},
        "npcs": {},
        "pool_used": [],
    }
    cast = sp.cast_entries(state, store=store)
    assert [e.entry_id for e in cast] == [entry_id]
    assert "bond" not in cast[0].document


def test_hostile_backstory_never_promotes(store):
    import json
    from pathlib import Path

    corpus = json.loads(Path("tests/fixtures/prompt_injection/corpus.json").read_text("utf-8"))
    hostile = next(c["player_input"] for c in corpus["cases"] if c.get("player_input"))
    scenario, ctx = _built()
    entry_id = prologue.submit_personal_npc(
        scenario,
        ctx["seed"],
        game_id="g8",
        region_id="nova_arcadia",
        char_input={**CHAR, "backstory": hostile},
    )
    entry = store.get(entry_id)
    assert entry.status == PoolStatus.LOCAL_ONLY and entry.name_origin == "player"
    assert not prologue.looks_hostile(CHAR["backstory"], "procuro meu pai, Toren")


def test_reused_seed_goes_local_only(store):
    scenario, ctx = _built()
    first = prologue.submit_personal_npc(
        scenario, ctx["seed"], game_id="g1", region_id="nova_arcadia", char_input=CHAR
    )
    second = prologue.submit_personal_npc(
        scenario, ctx["seed"], game_id="g2", region_id="nova_arcadia", char_input=CHAR
    )
    assert store.get(first).status == PoolStatus.HELD
    assert store.get(second).status == PoolStatus.LOCAL_ONLY
