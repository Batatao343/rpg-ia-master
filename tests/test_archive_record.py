"""SPEC-422: registro deterministico do arquivista (descanso sem gancho e resposta descartada).

Etapa 1 (R11): oraculos de equivalencia das duas extracoes (linhas de rejeicao do resumo e
marca `archive_low` da viagem). O golden do arquivista foi gravado no HEAD ANTES da extracao.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents import archivist
from agents.archivist import MemoryUpdate
from tests.fakes.scripted_llm import ScriptedLLM

_GOLDEN = Path(__file__).parent / "fixtures" / "spec422_rejection_rows_golden.json"

_LOC = "O Anel Dourado é um bairro alto de Brekmar."
_INV = "O viajante carrega o Diário da Casa Vesper."
_NPC = "Skriit Mil-olhos é um homem alto de cabelo grisalho."
_BAD = f"{_LOC} {_INV} {_NPC} Ceslo segue viagem."


def _grounded_state(summary: str) -> dict:
    return {
        "game_id": "g422-golden",
        "player": {"name": "Ceslo", "inventory": [{"id": "pocao_cura", "qty": 1}]},
        "world": {
            "turn_count": 49,
            "current_location_id": "na_anel_dourado",
            "current_location": "Anel Dourado",
        },
        "npcs": {
            "Skriit Mil-olhos": {
                "id": "npc_skriit_mil-olhos",
                "name": "Skriit Mil-olhos",
                "appearance": "Goblin pequeno e encolhido, de pele verde-acinzentada.",
                "in_scene": True,
            }
        },
        "rejected_item_claims": ["Diário da Casa Vesper"],
        "archive_due": True,
        "messages": [HumanMessage(content="oi"), AIMessage(content="Olá.")],
        "narrative_summary": summary,
        "memory_facts": [],
        "chronicle": [],
    }


def _run_golden(scenario: str, monkeypatch) -> dict:
    monkeypatch.setattr(archivist, "add_memory_to_session", lambda *_a, **_k: True)
    monkeypatch.setenv("RPG_ARCHIVE_POLICY", "legacy")
    if scenario == "initial":
        state = _grounded_state(_BAD)
        llm = ScriptedLLM(
            {MemoryUpdate: MemoryUpdate(new_summary="Ceslo descansa.", important_facts=[])}
        )
    elif scenario == "success":
        state = _grounded_state("Ceslo investiga.")
        llm = ScriptedLLM({MemoryUpdate: MemoryUpdate(new_summary=_BAD, important_facts=[])})
    else:  # plain
        state = _grounded_state("Ceslo investiga.")
        llm = ScriptedLLM({MemoryUpdate: AIMessage(content="erro")}, text=_BAD)
    monkeypatch.setattr(archivist, "get_llm", lambda **_kw: llm)
    out = archivist.archive_node(state)
    keep = ("narrative_summary", "memory_rejections", "memory_facts", "archivist_last_run")
    return json.loads(json.dumps({k: out.get(k) for k in keep}, sort_keys=True, default=str))


@pytest.mark.parametrize("scenario", ["initial", "success", "plain"])
def test_archivist_rejeicoes_iguais_ao_golden_do_head(scenario, monkeypatch):
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    got = _run_golden(scenario, monkeypatch)
    assert got["memory_rejections"], "o cenario precisa exercitar as linhas de rejeicao"
    assert got == golden[scenario]


def test_summary_rejection_rows_igual_ao_bloco_antigo():
    from services.archive_record import summary_rejection_rows

    loc = [{"location_id": "x", "claimed_region": "Y"}]
    inv = [{"item_name": "Diario", "claim_kind": "rejected_item"}]
    npc = [{"npc_name": "Skriit", "field": "species"}]

    def _old(turn, a, b, c):  # copia literal do bloco antigo de archivist.py
        return [
            *[
                {
                    "turn": int(turn),
                    "provenance": "narrative_summary",
                    "reason": "location_region_contradiction",
                    **row,
                }
                for row in a
            ],
            *[
                {
                    "turn": int(turn),
                    "provenance": "narrative_summary",
                    "reason": "inventory_possession_contradiction",
                    **row,
                }
                for row in b
            ],
            *[
                {
                    "turn": int(turn),
                    "provenance": "narrative_summary",
                    "reason": "npc_identity_contradiction",
                    **row,
                }
                for row in c
            ],
        ]

    for args in ((loc, [], []), ([], inv, []), ([], [], npc), (loc, inv, npc), ([], [], [])):
        assert summary_rejection_rows(7, *args) == _old(7, *args)
    assert summary_rejection_rows("7", loc, inv, npc)[0]["turn"] == 7


def _story_turn(**kw):
    base = dict(  # noqa: C408
        dest="x",
        rested_player=None,
        beat_done=False,
        updates={},
        turn=5,
        state={},
        world={},
        update=SimpleNamespace(introduced_npcs=[]),
        quarantine_llm_payload=False,
        pending_llm_events=[],
        enc=None,
        _fauna_sign_shown=False,
        rest_note="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _old_archive_low(t, same_region, wanted):  # copia literal da condicao antiga do storyteller
    if (
        wanted
        and t.dest
        and t.rested_player is None
        and not t.beat_done
        and not t.updates.get("pending_world_events")
        and "quests" not in t.updates
        and "memory_canonical_facts" not in t.updates
        and same_region()
    ):
        return {"archive_low": t.turn}
    return {}


@pytest.mark.parametrize("policy", ["legacy", "lean"])
@pytest.mark.parametrize(
    "kw",
    [
        {},
        {"dest": None},
        {"rested_player": {"hp": 1}},
        {"beat_done": True},
        {"updates": {"pending_world_events": [{"a": 1}]}},
        {"updates": {"quests": []}},
        {"updates": {"memory_canonical_facts": ["x"]}},
    ],
)
@pytest.mark.parametrize("same_region", [True, False])
def test_story_marks_archive_low_igual(policy, kw, same_region, monkeypatch):
    from services import archive_record, latency_flags

    monkeypatch.setenv("RPG_ARCHIVE_POLICY", policy)
    monkeypatch.delenv("RPG_ARCHIVE_POLICY_SHADOW", raising=False)
    monkeypatch.delenv("RPG_ARCHIVE_RECORD", raising=False)
    t = _story_turn(**kw)
    got = archive_record.story_marks(t, same_region=lambda: same_region)
    assert got == _old_archive_low(t, lambda: same_region, latency_flags.archive_low_wanted())
