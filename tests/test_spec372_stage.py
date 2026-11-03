"""SPEC-372 Etapa 2 — plot_stage/plot_stages puros (R1-R3)."""

from __future__ import annotations

import copy
import json
import time

from services import plot_threads as pt

CORPOS = "tr_na_corpos_marcados"
SEED = "rumor_a_praga_de_ferro_nao_veio_das_minas"
NPC = "npc_tr_pio_ferrugem"


def _rumor(rid: str, perceived: int = 2, resolution: str = "") -> dict:
    row = {"rumor_id": rid, "seed_id": SEED, "perceived_day": perceived}
    if resolution:
        row["resolution"] = resolution
    return row


def _quest(rid: str, status: str = "active") -> dict:
    return {
        "id": "q1",
        "world_kind": "investigar_rumor",
        "status": status,
        "lore_anchor": {"type": "rumor", "id": rid},
    }


def _st(**kw) -> dict:
    base = {"world_sim": {"rumors": []}, "npcs": {}, "quests": [], "event_log": []}
    base.update(kw)
    return base


def test_dormente_sem_sinal():
    assert pt.plot_stage(_st(), CORPOS) == "dormente"


def test_tocada_por_npc_conhecido():
    npcs = {NPC: {"id": NPC, "known_by_player": True, "knowledge_source": "met"}}
    assert pt.plot_stage(_st(npcs=npcs), CORPOS) == "tocada"
    mention = {NPC: {"id": NPC, "known_by_player": False, "knowledge_source": "mentioned"}}
    assert pt.plot_stage(_st(npcs=mention), CORPOS) == "dormente"


def test_tocada_por_rumor_percebido():
    st = _st(world_sim={"rumors": [_rumor("r1")]})
    assert pt.plot_stage(st, CORPOS) == "tocada"
    st = _st(world_sim={"rumors": [_rumor("r1", perceived=0)]})
    assert pt.plot_stage(st, CORPOS) == "dormente"


def test_tocada_por_fio_de_abertura():
    for ref in (f"{CORPOS}__p1", CORPOS):
        st = _st(campaign_plan={"opening_thread": {"thread_refs": [ref]}})
        assert pt.plot_stage(st, CORPOS) == "tocada"


def test_investigada_por_quest():
    st = _st(world_sim={"rumors": [_rumor("r1")]}, quests=[_quest("r1")])
    assert pt.plot_stage(st, CORPOS) == "investigada"


def test_investigada_por_rumor_confirmado():
    st = _st(world_sim={"rumors": [_rumor("r1", resolution="confirmado")]})
    assert pt.plot_stage(st, CORPOS) == "investigada"


def test_revelada_por_segredo_aceito():
    st = _st(event_log=[{"type": "secret_revealed", "target_id": "corpos"}])
    assert pt.plot_stage(st, CORPOS) == "revelada"
    st = _st(event_log=[{"type": "secret_hinted", "target_id": "corpos"}])
    assert pt.plot_stage(st, CORPOS) == "dormente"


def test_maior_estagio_vence():
    st = _st(
        world_sim={"rumors": [_rumor("r1")]},
        quests=[_quest("r1")],
        event_log=[{"type": "secret_revealed", "target_id": "corpos"}],
    )
    assert pt.plot_stage(st, CORPOS) == "revelada"


def test_quest_abandonada_volta_a_tocada():
    st = _st(world_sim={"rumors": [_rumor("r1")]}, quests=[_quest("r1", "failed")])
    assert pt.plot_stage(st, CORPOS) == "tocada"


def test_trama_inexistente_dormente():
    assert pt.plot_stage(_st(), "tr_nao_existe") == "dormente"
    assert pt.plot_stages(_st(), "regiao_inexistente") == {}


def test_plot_stages_uma_passada(monkeypatch):
    calls = []
    real = pt._stage_signals
    monkeypatch.setattr(pt, "_stage_signals", lambda s: calls.append(1) or real(s))
    out = pt.plot_stages(_st(), "nova_arcadia")
    assert len(calls) == 1
    assert CORPOS in out and set(out.values()) == {"dormente"}
    assert len(out) == len(pt.threads_for_region("nova_arcadia"))


def test_plot_stage_nao_muta_estado():
    st = _st(world_sim={"rumors": [_rumor("r1")]}, quests=[_quest("r1")])
    before = json.dumps(copy.deepcopy(st), sort_keys=True)
    pt.plot_stage(st, CORPOS)
    pt.plot_stages(st, "nova_arcadia")
    assert json.dumps(st, sort_keys=True) == before


def test_plot_stages_latencia():
    rumors = [_rumor(f"r{i}") for i in range(100)]
    quests = [_quest(f"r{i}") for i in range(50)]
    events = [{"type": "x", "target_id": str(i)} for i in range(200)]
    st = _st(world_sim={"rumors": rumors}, quests=quests, event_log=events)
    pt.plot_stages(st, "nova_arcadia")
    t0 = time.perf_counter()
    for _ in range(10):
        pt.plot_stages(st, "nova_arcadia")
    assert (time.perf_counter() - t0) / 10 < 0.020
