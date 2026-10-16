"""SPEC-203 — regressões da revisão independente Astra (2026-10-16)."""
from __future__ import annotations

from langchain_core.messages import HumanMessage

import agents.combat as combat
from agents.router import RouterDecision, RouteType, dm_router_node
from services import encounter_manifest as em
from services import prose_guard
from tests.test_encounter_identity_repro import _BANDIT
from tests.test_encounter_lifecycle_reload import _decl, _merge, _start


def _ended_state(route: RouteType, monkeypatch, msg: str):
    manifest = em.build_manifest([{"id": f"{_BANDIT}_1", "name": "Bandido", "status": "rendido"}],
                                 source="systemic", origin="unknown", encounter_id="g:0:1")
    combat_state = em.end_combat({"active": False, "phase": "active", "encounter": manifest},
                                 "surrendered_enemy")
    combat_state["result"] = em.build_result(manifest, "surrendered_enemy", 2)

    class _LLM:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _msgs):
            return RouterDecision(route=route, target="Bandido", reasoning="x",
                                  confidence=0.9, loot_context=None)

    import agents.router as router
    monkeypatch.setattr(router, "get_llm", lambda **_k: _LLM())
    return {"combat": combat_state, "world": {"current_location_id": "x"}, "npcs": {},
            "messages": [HumanMessage(content=msg)]}


def test_r6_pos_desfecho_respeita_intencao_npc(monkeypatch):
    """R6 bloqueia só a reabertura de combate; NPC/LOOT não são sequestrados."""
    out = dm_router_node(_ended_state(RouteType.NPC, monkeypatch,
                                      "Pergunto ao bandido rendido quem o mandou."))
    assert out["next"] == RouteType.NPC.value
    assert out["combat"]["explore_resumed"] is True


def test_r6_pos_desfecho_hostilidade_explicita_reabre(monkeypatch):
    out = dm_router_node(_ended_state(RouteType.COMBAT, monkeypatch, "Ataco o bandido de novo."))
    assert out["next"] == RouteType.COMBAT.value


def test_combat_node_sem_normalizacao_de_load_reconstroi_legacy(monkeypatch):
    """Perfil que não passa por `_raw_to_state`: combate ativo sem manifesto/fase
    vira `legacy_migrated` no combat_node, sem trocar espécie nem elenco."""
    state = _start(monkeypatch, ["hit", "hit", "hit"])
    out = combat.combat_node(state)
    state = _merge(state, out)
    species = {e["id"]: em.species_label_for(e) for e in state["enemies"]}
    stripped = {k: v for k, v in state["combat"].items()
                if k not in ("encounter", "phase", "outcome", "result")}
    state["combat"] = stripped
    out2 = combat.combat_node(_decl(state))
    manifest = out2["combat"]["encounter"]
    assert manifest["source"] == "legacy_migrated"
    assert out2["combat"]["phase"] in ("active", "ended")
    assert {p["participant_id"]: p["species_label"] for p in manifest["participants"]} == species
    assert {e["id"] for e in out2["enemies"]} <= set(species)
    assert not [ev for ev in manifest["events"] if ev["cause"] == "roster_violation"]


def test_species_drift_nao_apaga_prosa_legitima():
    manifest = em.build_manifest([{"id": f"{_BANDIT}_1", "name": "Bandido", "status": "ativo"}],
                                 source="systemic", origin="unknown", encounter_id="e")
    legit = ("Uma faísca salta quando sua lâmina raspa a cota do salteador; ele vinha "
             "pela esquerda, envolto em fumaça e horror.")
    assert prose_guard.species_drift(legit, manifest) == []
    # A troca real de espécie continua marcada.
    assert prose_guard.species_drift("O lobo rosna e salta sobre você.", manifest)
