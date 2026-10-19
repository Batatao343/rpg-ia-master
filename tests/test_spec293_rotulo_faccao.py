"""SPEC-293 — rótulo de exibição de combatente de fação oculta (offline, zero LLM)."""

from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

import api
import gamedata
from services import encounter_manifest as em
from services import faction_display as fd
from world_utils import apply_faction_reveal

INICIADO = "enemy_iniciado_chama_azul"
SOLDADO = "enemy_soldado_legiao_ferro"
CANON = "Iniciado da Chama Azul"
FID = "filhos_chama_azul"


def _intel_known(fid=FID):
    return apply_faction_reveal({}, gamedata.seed_factions(), fid, "existencia", 1)


# --- R1: regra pura -----------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "fid", "label"),
    [
        ("Iniciado da Chama Azul", "filhos_chama_azul", "Iniciado"),
        ("Soldado da Legião de Ferro", "legiao_ferro", "Soldado"),
        ("Degolador da Mão Sombria", "mao_sombria", "Degolador"),
        ("Cultista da Destilação", "cultistas_destilacao", "Cultista"),
        ("Devorador de Sol (Zhur)", "tribos_devoradores_sol", "Devorador"),
        ("Iniciado da Chama Azul 2", "filhos_chama_azul", "Iniciado 2"),
        ("Druida-Renegado", "druidas_renegados", fd.GENERIC_LABEL),
        ("Nômade Canibal", "bandos_nomades", "Nômade Canibal"),
        ("Guerreiro Bjorn", "clas_combate", "Guerreiro Bjorn"),
        ("Lobo Sombrio", "", "Lobo Sombrio"),
    ],
)
def test_display_label_regra(name, fid, label):
    assert fd.display_label(name, fid, [], {}) == label


def test_display_label_faccao_conhecida_mostra_canonico():
    assert fd.display_label(CANON, FID, [], _intel_known()) == CANON


# --- R2/R3: mapa + projeção ------------------------------------------------------


def test_mapa_por_observador_sai_apos_revelacao():
    assert fd.concealed_name_map({})[CANON] == "Iniciado"
    after = fd.concealed_name_map({"faction_intel": _intel_known()})
    assert CANON not in after and "Soldado da Legião de Ferro" in after


def test_conceal_payload_caixa_ids_e_sem_mutacao():
    mapping = fd.concealed_name_map({})
    obj = {
        "id": "Iniciado da Chama Azul",
        "enemy_id": CANON,
        "entity_ids": [CANON],
        "name": "Iniciado da Chama Azul 2",
        "log": ["O iniciado da chama azul cai.", "Iniciado da Chama Azulado"],
        CANON: "chave intacta",
    }
    original = copy.deepcopy(obj)
    out = fd.conceal_payload(obj, mapping)
    assert obj == original
    assert out["id"] == out["enemy_id"] == CANON and out["entity_ids"] == [CANON]
    assert out["name"] == "Iniciado 2"
    assert out["log"][0] == "O iniciado cai."
    assert out["log"][1] == "Iniciado da Chama Azulado"  # fronteira de palavra
    assert CANON in out


# --- estado de combate real -----------------------------------------------------


def _enemy(bid, n=1, **extra):
    base = gamedata.BESTIARY[bid]
    return {**base, "id": f"{bid}_{n}", "name": base["name"], "status": "ativo", **extra}


def _combat_state(intel=None):
    from tests.test_fase43 import make_player

    enemies = [_enemy(INICIADO, 1, name=f"{CANON} 1"), _enemy(INICIADO, 2, name=f"{CANON} 2")]
    manifest = em.build_manifest(
        list(enemies),
        source="systemic",
        origin="travel_encounter",
        encounter_id="g:0:1",
        target_ref=INICIADO,
    )
    log = f"⚔️ Você acerta {CANON} 1 (−4). {CANON} 2 avança."
    return {
        "game_id": "pytest_spec293",
        "player": make_player(hp=10, inventory=[]),
        "world": {
            "current_location": "Nova Arcadia",
            "current_location_id": "nova_arcadia",
            "turn_count": 5,
            "visited": ["nova_arcadia"],
        },
        "messages": [HumanMessage(content=f"ataco o {CANON}"), AIMessage(content=log)],
        "enemies": enemies,
        "npcs": {},
        "factions": [],
        "faction_intel": intel or {},
        "combat": {
            "active": True,
            "phase": "active",
            "outcome": None,
            "encounter": manifest,
            "round": 1,
        },
        "combat_target": CANON,
        "bestiary_knowledge": {INICIADO: {"rumor": 1, "seen": 1, "fought": 1}},
        "narrative_summary": f"Um {CANON} emboscou o herói.",
        "chronicle": [
            {
                "chapter_id": "c1",
                "title": "Emboscada",
                "started_turn": 1,
                "location": "Nova Arcadia",
                "entries": [{"text": f"Derrotou {CANON}.", "turn": 4, "kind": "milestone"}],
            }
        ],
        "presentation_history": [
            {"id": "h1", "epoch": 0, "turn": 5, "role": "narrator", "text": log, "type": "COMBAT"}
        ],
        "event_log": [],
        "world_projection": {},
        "memory_facts": [],
        "continuity": {"timeline_epoch": 0},
    }


def _resp(state) -> dict:
    return json.loads(api.format_response(state).model_dump_json())


def test_format_response_sem_nome_canonico_e_com_rotulo():
    state = _combat_state()
    snapshot = copy.deepcopy(state)
    payload = _resp(state)
    assert fd.concealed_name_problems(payload, state) == []
    names = [e["name"] for e in payload["combat"]["enemies"]]
    assert names == ["Iniciado 1", "Iniciado 2"]
    species = {p["species_label"] for p in payload["combat"]["encounter_view"]["participants"]}
    assert species == {"Iniciado"}
    assert "Você acerta Iniciado 1" in payload["message"]
    assert [e["id"] for e in payload["combat"]["enemies"]] == [f"{INICIADO}_1", f"{INICIADO}_2"]
    # R4: estado/save intactos
    assert state["enemies"] == snapshot["enemies"] and state["combat"] == snapshot["combat"]
    assert state["combat_target"] == CANON


def test_oraculo_pega_superficie_sem_projecao():
    state = _combat_state()
    problems = fd.concealed_name_problems({"x": [{"y": f"o {CANON}"}]}, state)
    assert problems == [f"e:concealed_faction_name:{FID}"]


def test_codex_e_dossies_sem_nome_canonico_e_oraculo_e():
    from services.discovery import player_codex
    from services.dossiers import build_dossiers
    from services.player_knowledge import assert_no_player_leak

    state = _combat_state()
    codex = player_codex(state)
    titles = [c["name"] for c in codex["creatures"]]
    assert titles == ["Iniciado"]
    assert not [p for p in assert_no_player_leak(codex, state) if p.startswith("e:")]
    dossiers = build_dossiers(state)
    assert fd.concealed_name_problems(dossiers, state) == []
    assert dossiers["bestiary"][0]["title"] == "Iniciado"
    # oráculo (e) dentro de assert_no_player_leak
    leaky = copy.deepcopy(codex)
    leaky["creatures"][0]["name"] = CANON
    assert f"e:concealed_faction_name:{FID}" in assert_no_player_leak(leaky, state)


def test_retroativo_apos_revelacao():
    from services.discovery import player_codex
    from services.dossiers import build_dossiers

    state = _combat_state(intel=_intel_known())
    payload = _resp(state)
    assert [e["name"] for e in payload["combat"]["enemies"]] == [f"{CANON} 1", f"{CANON} 2"]
    assert CANON in payload["message"]
    assert player_codex(state)["creatures"][0]["name"] == CANON
    assert build_dossiers(state)["bestiary"][0]["title"] == CANON


# --- endpoints (state/history/codex/crônica/SSE) ----------------------------------


@pytest.fixture()
def client(monkeypatch):
    state = _combat_state()
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    monkeypatch.setattr(api, "_resolve_save_file", lambda *_a, **_k: "x")
    monkeypatch.setattr(api, "load_game_state", lambda *_a, **_k: copy.deepcopy(state))
    monkeypatch.setattr(api, "_load_unlocked_or_locked", lambda *_a, **_k: copy.deepcopy(state))
    return TestClient(api.app), state


def test_endpoints_sem_nome_canonico(client):
    c, state = client
    gid = state["game_id"]
    bodies = {
        "state": c.get(f"/game/state?game_id={gid}").json(),
        "history": c.get(f"/game/history?game_id={gid}").json(),
        "codex": c.get(f"/game/codex?game_id={gid}").json(),
        "dossiers": c.get(f"/game/codex/dossiers?game_id={gid}").json(),
        "search": c.post(
            "/game/chronicle/search", json={"game_id": gid, "query": "Derrotou"}
        ).json(),
        "export": c.get(f"/game/chronicle/export?game_id={gid}").text,
    }
    for name, body in bodies.items():
        assert fd.concealed_name_problems(body, state) == [], name
    assert "Iniciado" in bodies["history"]["entries"][0]["text"]
    assert "Derrotou Iniciado." in bodies["export"]


def test_sse_sem_nome_canonico(client, monkeypatch):
    c, state = client

    def fake_execute(req, progress=None, timeline=None, on_response=None):
        return api.format_response(copy.deepcopy(state))

    monkeypatch.setattr(api, "_execute_action", fake_execute)
    with c.stream(
        "POST",
        "/game/action/stream",
        json={"input_text": "ataco", "game_id": state["game_id"]},
    ) as r:
        raw = "".join(chunk for chunk in r.iter_text())
    assert "Iniciado 1" in raw
    assert CANON.lower() not in raw.lower()


# --- R7: narrador ----------------------------------------------------------------


def test_clausula_narrador_usa_rotulo():
    from agents.combat import _concealed_species

    state = _combat_state()
    manifest = state["combat"]["encounter"]
    assert _concealed_species(manifest, [], {}) == [(CANON, "Iniciado")]
    druida = em.build_manifest(
        [_enemy("enemy_druida_renegado")],
        source="systemic",
        origin="travel_encounter",
        encounter_id="g:0:2",
        target_ref="enemy_druida_renegado",
    )
    assert _concealed_species(druida, [], {}) == [("Druida-Renegado", fd.GENERIC_LABEL)]
    assert _concealed_species(manifest, [], _intel_known()) == []


# --- revisão: variações de prosa do LLM -------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("O Iniciado da Chama  Azul avança", "O Iniciado avança"),
        ("O Iniciado da\nChama Azul avança", "O Iniciado avança"),
        ("A Cultista da Destilacao ri", "A Cultista ri"),
        ("O Druida Renegado uiva", f"O {fd.GENERIC_LABEL} uiva"),
        ("Dois Iniciados da Chama Azul cercam", "Dois Iniciados cercam"),
        ("Três Degoladores da Mão Sombria", "Três Degoladores"),
        ("Os Druidas-Renegados atacam", "Os Combatentes desconhecidos atacam"),
        ("Iniciado da Chama Azulado", "Iniciado da Chama Azulado"),
    ],
)
def test_conceal_tolera_espaco_acento_e_plural(text, expected):
    mapping = fd.concealed_name_map({})
    out = fd.conceal_text(text, mapping)
    assert out == expected
    assert fd.concealed_name_problems({"t": out}, {}) == []  # SPEC-294: oráculo com fronteira
