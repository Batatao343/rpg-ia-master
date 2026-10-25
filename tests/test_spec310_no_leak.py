"""SPEC-310 Etapa 7 — não-vazamento (R19-R23): o motor não fala pelo NPC."""

from __future__ import annotations

import json
import re

import pytest

import api
from services import dossiers as dz
from services import npc_seed
from services import npc_self as ns
from tests.spec310_helpers import HERE, sergeant, sim_entry, war_state
from tests.test_spec310_npc_prompt import SEEDED, _prompt, _state

SENTINEL_NEWS = "BOATOSENTINELA-do-jogador"
SENTINEL_BLOCK = "ROTABLOQUEADASENTINELA"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    monkeypatch.delenv("RPG_NPC_SELF", raising=False)


def _poisoned_state() -> dict:
    st = war_state()
    st["world"]["date"] = {"day": 5, "label": "5º dia de Vorrnak"}
    st["world"]["news"] = [{"text": SENTINEL_NEWS, "turn": 7}]
    st["world_sim"].update(
        pressures={"nova_arcadia": {"guerra": 987}},
        bands={"nova_arcadia": {"guerra": "alta"}},
        faction_relations={"filhos_chama_azul|legiao_ferro": -7711},
        director={"phase": "FASEDIRETOR"},
        crises=[{"kind": "guerra", "severity": 4242, "region_id": "nova_arcadia"}],
        perceived_ids=["e-x"],
    )
    st["world_projection"] = {
        "location_states": {HERE: {"state": "cerco", "severity": 4242, "crisis_id": "c-1"}}
    }
    other = {"home": "brekmar", "pos": {"location_id": "brekmar", "since_day": 1}, "status": ""}
    st["npc_sim"] = {
        "version": 1,
        "npcs": {
            **sim_entry(location_id=HERE, since_day=4, return_day=7)["npcs"],
            "npc_outro_secreto": other,
        },
    }
    st["npcs"] = {
        "Ruiva": sergeant(),
        "Outro": {"id": "npc_outro_secreto", "name": "Zefirino Outro", "role": "Ladrão"},
    }
    st["event_log"] = [
        {
            "event_id": "ev-blocked",
            "type": "route_blocked",
            "turn": 6,
            "target_id": "ophidia",
            "payload": {"note": SENTINEL_BLOCK},
            "source": "engine",
        }
    ]
    return st


def test_motor_nao_fala_pelo_npc():
    st = _poisoned_state()
    text = ns.npc_self_blocks(st, "Ruiva", sergeant(seed_motives=SEEDED)).text()
    assert text
    for needle in (SENTINEL_NEWS, SENTINEL_BLOCK, "Zefirino", "Brekmar", "FASEDIRETOR"):
        assert needle not in text
    for number in ("987", "7711", "4242"):
        assert number not in text
    assert not re.search(r"severidade|tensão|pressão|crise|fase", text, re.I)


def test_world_news_do_jogador_ausente():
    st = _poisoned_state()
    st["messages"] = []
    assert SENTINEL_NEWS not in ns.npc_self_blocks(st, "Ruiva", sergeant()).text()


def test_sem_digitos_fora_da_data():
    st = _poisoned_state()
    blocks = ns.npc_self_blocks(st, "Ruiva", sergeant(seed_motives=SEEDED))
    scan = "\n".join(
        ln
        for ln in (blocks.sobre_voce + "\n" + blocks.motivacoes).splitlines()
        if "Hoje é" not in ln
    )
    assert "Hoje é 5º dia de Vorrnak." in blocks.sobre_voce
    assert not re.search(r"\d", scan)


def _secret_ids() -> list[str]:
    return [r["id"] for r in npc_seed.load_seed_tables()["secrets"]]


@pytest.mark.parametrize("secret_id", _secret_ids())
def test_44_segredos_nunca_literais(monkeypatch, secret_id):
    label = next(r["label"] for r in npc_seed.load_seed_tables()["secrets"] if r["id"] == secret_id)
    row = sergeant(seed_motives={**SEEDED, "secret_id": secret_id})
    prompt = _prompt(monkeypatch, _state(row))
    assert label not in prompt
    assert "Há um assunto que você evita:" in prompt


def test_seed_motives_fora_da_api_e_dossie():
    st = {
        "game_id": "g310api",
        "narrative_summary": "",
        "messages": [],
        "player": {"name": "T", "class_name": "Devoto do Abismo", "race": "Humano", "gold": 5},
        "world": {
            "current_location": "Anel de Ferro",
            "current_location_id": HERE,
            "turn_count": 3,
            "visited": [HERE],
        },
        "npcs": {
            "Ruiva": sergeant(
                seed_motives=SEEDED, known_by_player=True, knowledge_source="met", last_seen_turn=2
            )
        },
        "factions": [],
        "faction_intel": {},
        "event_log": [],
        "world_projection": {},
        "memory_facts": [],
        "chronicle": [],
    }
    payload = api.format_response(st)
    dump = payload.model_dump() if hasattr(payload, "model_dump") else payload
    blob = json.dumps(dump, default=str) + json.dumps(dz.build_dossiers(st), default=str)
    assert (
        "seed_motives" not in blob and "sec_desertor" not in blob and "des_juntar_ouro" not in blob
    )
