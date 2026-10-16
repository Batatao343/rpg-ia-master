"""SPEC-213 — canônico síncrono × projeções derivadas (unidade, offline)."""
from __future__ import annotations

import copy
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from services import projections


@pytest.fixture
def base_state():
    return {
        "game_id": "proj-test",
        "player": {"name": "Ari", "inventory": [], "gold": 10},
        "world": {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia",
                  "turn_count": 4},
        "continuity": {"session_action_count": 4, "timeline_epoch": 0},
        "event_log": [], "npcs": {}, "chronicle": [],
        "archive_due": True,
        "messages": [HumanMessage("Olho a praça."), AIMessage("A chuva cai na praça.")],
    }


class _Model:
    """LLM fake do arquivista: resumo/crônica configuráveis, conta chamadas."""

    def __init__(self, summary="A chuva segue na praça.", chronicle="O bardo canta a chuva."):
        self.summary, self.chronicle, self.calls = summary, chronicle, 0

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        import agents.archivist as archive
        self.calls += 1
        return archive.MemoryUpdate(new_summary=self.summary, important_facts=[],
                                    chronicle_entry=self.chronicle)


@pytest.fixture
def model(monkeypatch):
    import agents.archivist as archive
    fake = _Model()
    monkeypatch.setattr(archive, "get_llm", lambda **kwargs: fake)
    monkeypatch.setattr(archive, "add_memory_to_session", lambda *a, **k: True)
    return fake


def _defer(monkeypatch):
    monkeypatch.setenv(projections.MODE_ENV, "post_response")


def _stamped(state, action_id="a1"):
    return projections.stamp_commit(copy.deepcopy(state), action_id)


# --- Etapa 1: partição e paridade ---------------------------------------------

def test_split_classifies_fields(monkeypatch, base_state, model):
    """R2/R3: com a janela aberta, o arquivista não chama o LLM e só devolve o
    canônico + a linha de base do plano; derivados ficam para a projeção."""
    import agents.archivist as archive
    _defer(monkeypatch)
    base_state["pending_world_events"] = []
    with projections.deferral_scope():
        out = archive.archive_node(base_state)
    assert model.calls == 0
    assert out["pending_derived"]["canonical_version"] is None
    for derived in ("narrative_summary", "memory_facts", "chronicle", "archivist_last_run"):
        assert derived not in out


def test_inline_mode_byte_identical(monkeypatch, base_state, model):
    """R11: sem a janela (CLI, perfis DB) o modo é inline mesmo com a env ligada."""
    import agents.archivist as archive
    reference = archive.archive_node(copy.deepcopy(base_state))
    _defer(monkeypatch)
    outside = archive.archive_node(copy.deepcopy(base_state))
    assert json.dumps(outside, default=str, sort_keys=True) == json.dumps(
        reference, default=str, sort_keys=True)
    assert "pending_derived" not in outside
    with projections.deferral_scope(enabled=False):
        disabled = archive.archive_node(copy.deepcopy(base_state))
    assert "pending_derived" not in disabled


def test_drained_projection_matches_inline(monkeypatch, base_state, model):
    """Paridade: inline × (adiado + drenado) produzem os mesmos derivados."""
    import agents.archivist as archive
    inline = {**base_state, **archive.archive_node(copy.deepcopy(base_state))}
    _defer(monkeypatch)
    with projections.deferral_scope():
        partial = archive.archive_node(copy.deepcopy(base_state))
    deferred = _stamped({**base_state, **partial})
    drained = projections.run_pending(deferred)
    for key in ("narrative_summary", "chronicle", "memory_facts", "archivist_last_run"):
        assert drained[key] == inline[key], key
    assert drained["projection_state"]["summary"]["status"] == "completed"
    assert drained["pending_derived"] is None


def test_canonical_persisted_when_derived_fails(monkeypatch, base_state, model, tmp_path):
    """R1/R12: derivado que falha não apaga o canônico nem derruba o turno."""
    import agents.archivist as archive
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    _defer(monkeypatch)
    base_state["event_log"] = [{"event_id": "ev-dead", "turn": 4, "type": "npc_died",
                                "target_id": "npc_x"}]
    with projections.deferral_scope():
        partial = archive.archive_node(copy.deepcopy(base_state))
    state = _stamped({**base_state, **partial})

    def boom(state, plan):
        raise RuntimeError("provider down")

    out = projections.run_pending(state, executor=boom)
    assert out["event_log"] == base_state["event_log"]
    assert out["projection_state"]["summary"]["status"] == "failed"
    assert out["projection_state"]["summary"]["last_error_code"] == "exception"
    assert out["pending_derived"] is not None          # retentado no próximo turno
    assert persistence.save_game_state(out)
    loaded = persistence.load_game_state(str(tmp_path / "proj-test.json"))
    assert loaded["event_log"][0]["event_id"] == "ev-dead"
    assert loaded["pending_derived"]["action_id"] == "a1"


def test_failed_projection_gives_up_after_max_attempts(base_state):
    state = _stamped({**base_state, "pending_derived": projections.make_plan(
        new_event_ids=[], new_rejections=False, turn=4, epoch=0)})

    def boom(state, plan):
        raise RuntimeError("x")

    for _ in range(projections.MAX_ATTEMPTS):
        state = projections.run_pending(state, executor=boom)
    assert state["pending_derived"] is None
    assert state["projection_state"]["memory"]["attempts"] == projections.MAX_ATTEMPTS


# --- Etapa 2: versão, estados, migração ---------------------------------------

def _plan_state(base_state, version=None, epoch=0, action="a1"):
    state = copy.deepcopy(base_state)
    state["pending_derived"] = projections.make_plan(
        new_event_ids=[], new_rejections=False, turn=4, epoch=epoch)
    return projections.stamp_commit(state, action) if version is None else state


def test_apply_rejects_older_version(base_state):
    """R5: derivado de versão mais velha que a aplicada é descartado."""
    state = _plan_state(base_state)
    plan = state["pending_derived"]
    for name in projections.PROJECTIONS:
        state["projection_state"][name].update(status="completed",
                                               projected_version=plan["canonical_version"] + 1)
    state["projection_state"]["canonical_version"] = plan["canonical_version"] + 1
    calls = []
    out = projections.run_pending(state, executor=lambda s, p: calls.append(p) or {})
    assert calls == []
    assert out["pending_derived"] is None


def test_never_ahead_of_canonical(base_state):
    """R6: normalização clampa projected_version <= canonical_version."""
    raw = {"canonical_version": 3, "summary": {"status": "completed", "projected_version": 9}}
    state = {**base_state, "continuity": {"session_action_count": 2, "timeline_epoch": 0}}
    ps = projections.normalize_projection_state(raw, state)
    assert ps["summary"]["projected_version"] == 3
    from playtest.invariants import check_projection_ahead
    bad = {"projection_state": {"canonical_version": 2,
                                "summary": {"projected_version": 5}}}
    assert [v.check_id for v in check_projection_ahead(bad, None, 1)] == [
        "projection.ahead_of_canonical"]
    assert check_projection_ahead({"projection_state": ps}, None, 1) == []


def test_stale_reschedules(base_state):
    """R5: aplicado quando já há versão canônica mais nova → `stale` + reagenda."""
    state = _plan_state(base_state)
    state["projection_state"]["canonical_version"] += 1
    out = projections.run_pending(state, executor=lambda s, p: {"narrative_summary": "novo"})
    assert out["projection_state"]["summary"]["status"] == "stale"
    assert out["narrative_summary"] == "novo"
    assert out["archive_due"] is True


def test_idempotent_by_action_id(monkeypatch, base_state, model):
    """R8: reexecutar a mesma ação não duplica crônica nem chama o LLM de novo."""
    import agents.archivist as archive
    _defer(monkeypatch)
    with projections.deferral_scope():
        partial = archive.archive_node(copy.deepcopy(base_state))
    state = _stamped({**base_state, **partial})
    plan = copy.deepcopy(state["pending_derived"])
    once = projections.run_pending(state)
    again = projections.run_pending({**once, "pending_derived": plan})
    prose = [e for ch in again["chronicle"] for e in ch.get("entries", [])
             if e.get("kind") == "prose"]
    assert len(prose) == 1
    assert model.calls == 1


def test_wait_timeout_marks_failed(base_state):
    """R10: derivado que estoura RPG_PROJECTION_WAIT_SECONDS é descartado (`failed`)."""
    state = _plan_state(base_state)
    ticks = iter([0.0, 999.0])
    out = projections.run_pending(state, executor=lambda s, p: {"narrative_summary": "tarde"},
                                  clock=lambda: next(ticks), timeout=20)
    assert out["projection_state"]["summary"]["status"] == "failed"
    assert out["projection_state"]["summary"]["last_error_code"] == "timeout"
    assert out.get("narrative_summary") != "tarde"


def test_wait_seconds_env(monkeypatch):
    monkeypatch.setenv(projections.WAIT_ENV, "5")
    assert projections.wait_seconds() == 5.0
    monkeypatch.setenv(projections.WAIT_ENV, "lixo")
    assert projections.wait_seconds() == projections.DEFAULT_WAIT_SECONDS
    monkeypatch.setenv(projections.MODE_ENV, "job")
    assert projections.projection_mode() == "inline"


def test_restore_cancels_pending_projection_of_old_epoch(base_state):
    """R7b: restore (época nova) cancela projeção pendente da época anterior."""
    state = _plan_state(base_state)
    state["continuity"]["timeline_epoch"] = 1          # resolve_death_choice → epoch+1
    calls = []
    out = projections.run_pending(state, executor=lambda s, p: calls.append(1) or {})
    assert calls == []
    assert out["pending_derived"] is None
    assert out["projection_state"]["summary"]["last_error_code"] == "epoch_mismatch"


def test_canonical_version_monotonic_across_restore(base_state):
    """R4: o checkpoint antigo não faz canonical_version voltar."""
    from services.continuity import after_restore
    live = _stamped(_stamped(base_state, "a1"), "a2")
    checkpoint = copy.deepcopy(base_state)
    checkpoint["projection_state"] = projections.normalize_projection_state(None, checkpoint)
    restored = copy.deepcopy(checkpoint)
    live["continuity"]["session_action_count"] = 6
    restored["continuity"] = after_restore(live, restored)
    ps = projections.normalize_projection_state(restored["projection_state"], restored)
    assert ps["canonical_version"] >= live["projection_state"]["canonical_version"]
    assert ps["timeline_epoch"] == restored["continuity"]["timeline_epoch"]


def test_v8_save_loads_with_completed_projection(tmp_path, monkeypatch, base_state):
    """R16: save v8 sem projection_state nasce `completed` em session_action_count;
    round-trip preserva o estado (sem bump de SCHEMA_VERSION)."""
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    assert persistence.SCHEMA_VERSION == 8
    state = copy.deepcopy(base_state)
    state["continuity"] = {"session_action_count": 7, "timeline_epoch": 2}
    assert persistence.save_game_state(state)
    path = tmp_path / "proj-test.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("projection_state")
    raw.pop("pending_derived")
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded = persistence.load_game_state(str(path))
    ps = loaded["projection_state"]
    assert ps["canonical_version"] == 7 and ps["timeline_epoch"] == 2
    assert all(ps[n]["status"] == "completed" and ps[n]["projected_version"] == 7
               for n in projections.PROJECTIONS)
    assert loaded["pending_derived"] is None
    # round-trip com plano pendente
    stamped = _plan_state({**loaded, "game_id": "proj-test"})
    assert persistence.save_game_state(stamped)
    again = persistence.load_game_state(str(path))
    assert again["projection_state"] == stamped["projection_state"]
    assert again["pending_derived"] == stamped["pending_derived"]
    assert persistence.load_game_state(str(path))["projection_state"] == again["projection_state"]


# --- Etapa 3: guard de reintrodução -------------------------------------------

def test_dead_npc_not_reintroduced_by_stale_summary(monkeypatch, base_state, model):
    """R7: NPC morto no canônico atual não volta a falar pelo resumo/crônica."""
    import agents.archivist as archive
    model.summary = "Brunna conversa com você na praça. A chuva segue."
    model.chronicle = "Brunna sorri ao herói. O vento canta."
    _defer(monkeypatch)
    with projections.deferral_scope():
        partial = archive.archive_node(copy.deepcopy(base_state))
    state = _stamped({**base_state, **partial})
    # O canônico mudou (NPC morto) antes de o derivado ser aplicado.
    state["npcs"] = {"brunna": {"id": "brunna", "name": "Brunna", "status": "morto"}}
    out = projections.run_pending(state)
    assert "Brunna" not in out["narrative_summary"]
    assert "A chuva segue." in out["narrative_summary"]
    assert "Brunna" not in json.dumps(out["chronicle"], ensure_ascii=False)
    reasons = {r["reason"] for r in out["evidence_rejections"]}
    assert "dead_npc_presence" in reasons
    # Memória de morte é preservada (fala DA morte não é reintrodução).
    text, rejected = projections.strip_dead_npc_presence(
        "Todos lembram que Brunna morreu.", state)
    assert text == "Todos lembram que Brunna morreu." and rejected == []


def test_unrevealed_secret_stripped_at_apply(monkeypatch, base_state, model):
    """R7: segredo não revelado no canônico atual é removido do derivado."""
    import agents.archivist as archive
    model.summary = "Valerius fez um pacto com Valerius em troca de imortalidade. A praça dorme."
    _defer(monkeypatch)
    with projections.deferral_scope():
        partial = archive.archive_node(copy.deepcopy(base_state))
    out = projections.run_pending(_stamped({**base_state, **partial}))
    assert "imortalidade" not in out["narrative_summary"]
    assert "unrevealed_secret" in {r["reason"] for r in out["evidence_rejections"]}


def test_projection_status_view_has_no_content(base_state):
    view = projections.projection_status_view(_plan_state(base_state))
    assert set(view) == {"canonical_version", "summary", "memory", "chronicle"}
    assert view["summary"] == {"status": "pending", "projected_version": 3}
    assert view["canonical_version"] == 4


# --- Revisão Astra (2026-10-16) -----------------------------------------------

def test_failed_plan_baseline_survives_next_deferred_archive(monkeypatch, base_state, model):
    """Projeção que falhou (aguarda retry) não perde os eventos do seu turno quando
    o turno seguinte também adia derivados: as linhas de base se unem."""
    import agents.archivist as archive
    _defer(monkeypatch)
    state = copy.deepcopy(base_state)
    state["pending_derived"] = projections.make_plan(
        new_event_ids=["ev-old"], new_rejections=True, turn=4, epoch=0)
    state = projections.stamp_commit(state, "a1")
    state["event_log"] = [{"event_id": "ev-new", "turn": 5, "type": "x"}]
    with projections.deferral_scope():
        out = archive.archive_node(state)
    plan = out["pending_derived"]
    assert plan["new_event_ids"][0] == "ev-old"
    assert plan["new_rejections"] is True


def test_timeout_does_not_retry_side_effects(base_state):
    """R8/R10: no timeout o executor já rodou (memória FAISS pode estar gravada);
    a projeção não é reexecutada — evita duplicar fatos."""
    state = _plan_state(base_state)
    ticks = iter([0.0, 999.0])
    out = projections.run_pending(state, executor=lambda s, p: {"narrative_summary": "x"},
                                  clock=lambda: next(ticks), timeout=20)
    assert out["projection_state"]["summary"]["last_error_code"] == "timeout"
    assert out["pending_derived"] is None


def test_restore_carries_live_canonical_version(base_state):
    """R4: mesmo com versão canônica à frente de session_action_count, o restore
    não volta a versão; a projeção da época antiga é cancelada (R7b)."""
    from services.continuity import after_restore
    live = _plan_state(base_state)
    live["projection_state"]["canonical_version"] = 40      # > session_action_count
    checkpoint = copy.deepcopy(base_state)
    checkpoint["pending_derived"] = live["pending_derived"]
    checkpoint["projection_state"] = projections.normalize_projection_state(None, checkpoint)
    checkpoint["continuity"] = after_restore(live, checkpoint)
    restored = projections.carry_over_restore(live, checkpoint)
    assert restored["projection_state"]["canonical_version"] == 40
    assert restored["pending_derived"] is None
