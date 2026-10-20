"""SPEC-294 — follow-ups da revisão da SPEC-293 (offline, zero LLM)."""

from __future__ import annotations

import copy
import json

import pytest

import api
import gamedata
import persistence
from services import combat_targeting as ct
from services import conflict_scene as cs
from services import faction_display as fd
from world_utils import apply_faction_reveal

INICIADO = "enemy_iniciado_chama_azul"
CANON = "Iniciado da Chama Azul"
FID = "filhos_chama_azul"
PROBLEM = f"e:concealed_faction_name:{FID}"


# --- R1: oráculo (e) com fronteira de palavra -------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "o Iniciado da Chama Azul ataca",
        "iniciado da chama  azul",
        "O Iniciado da\nChama-Azul avança",
        "Dois Iniciados da Chama Azul cercam",
        "INICIADO DA CHAMA AZUL 2",
        "Iniciado da Chama Azul.",
        "(Iniciado da Chama Azul)",
        "Iniciado da Chama Azules",
        "o Iniciado da Chama Azul™ ataca",
        "ⓘIniciado da Chama Azul",
    ],
)
def test_oraculo_acusa_ocorrencia_de_palavra(text):
    assert fd.concealed_name_problems({"t": text}, {}) == [PROBLEM]


@pytest.mark.parametrize(
    "text",
    [
        "Iniciado da Chama Azulado",
        "Iniciado da Chama Azul_x",
        "XIniciado da Chama Azul",
        "Iniciado da Chama Azul2",
        "Iniciado",
        "enemy_iniciado_chama_azul",
    ],
)
def test_oraculo_respeita_fronteira(text):
    assert fd.concealed_name_problems({"t": text}, {}) == []


def test_oraculo_respeita_faccao_revelada():
    intel = apply_faction_reveal({}, gamedata.seed_factions(), FID, "existencia", 1)
    assert fd.concealed_name_problems({"t": f"o {CANON}"}, {"faction_intel": intel}) == []


# --- R2: propriedade oráculo ⊇ projeção -------------------------------------------

_CORPUS = [
    f"O {CANON} avança",
    "O Iniciado da Chama  Azul avança",
    "O Iniciado da\nChama Azul avança",
    "A Cultista da Destilacao ri",
    "O Druida Renegado uiva",
    "Dois Iniciados da Chama Azul cercam",
    "Três Degoladores da Mão Sombria",
    "Os Druidas-Renegados atacam",
    "Iniciado da Chama Azulado",
    "soldado da legião de ferro 3 cai",
    "Soldados da Legiao-de-Ferro marcham",
    "nada aqui",
    "Iniciado da Chama Azul_2",
]


@pytest.mark.parametrize("text", _CORPUS)
def test_oraculo_cobre_projecao_e_projecao_e_limpa(text):
    mapping = fd.concealed_name_map({})
    out = fd.conceal_text(text, mapping)
    flagged = fd.concealed_name_problems({"t": text}, {})
    assert bool(flagged) == (out != text)
    assert fd.concealed_name_problems({"t": out}, {}) == []


# --- R4/R5/R6: id opaco para inimigo legado sem id ---------------------------------


def _legacy_raw() -> dict:
    from tests.test_fase43 import make_player

    names = [f"{CANON} 1", f"{CANON} 2"]
    enemies = []
    for name in names:
        enemy = {**gamedata.BESTIARY[INICIADO], "name": name, "status": "ativo"}
        enemy.pop("id", None)
        enemy.pop("archetype_id", None)
        enemies.append(enemy)
    scene = cs.new_scene()
    cs.place(scene, "player")
    for name in names:
        cs.place(scene, name)
    cs.engage(scene, "player", names[0], spend=False)
    scene["positions"][names[1]]["hidden_from"] = ["player"]
    state = {
        "game_id": "pytest_spec294",
        "player": make_player(hp=10, inventory=[]),
        "world": {
            "current_location": "Nova Arcadia",
            "current_location_id": "nova_arcadia",
            "turn_count": 5,
            "visited": ["nova_arcadia"],
        },
        "messages": [],
        "enemies": enemies,
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "combat": {"active": True, "round": 2, "scene": scene, "order": ["player", *names]},
        "combat_target": names[0],
        "bestiary_knowledge": {INICIADO: {"seen": 1, "fought": 1}},
        "event_log": [],
        "world_projection": {},
        "memory_facts": [],
    }
    raw = persistence._state_to_save_data(state, "pytest_spec294")
    return json.loads(json.dumps(raw, default=str))


def test_backfill_ids_opacos_deterministicos_e_puros():
    raw = _legacy_raw()
    snapshot = copy.deepcopy(raw)
    first = persistence.backfill_enemy_ids(raw)
    assert raw == snapshot
    ids = [e["id"] for e in first["enemies"]]
    assert ids == ["enemy_legacy_1", "enemy_legacy_2"]
    assert all(CANON.lower() not in i.lower() for i in ids)
    assert persistence.backfill_enemy_ids(copy.deepcopy(raw)) == first
    assert persistence.backfill_enemy_ids(first) == first
    assert [e["name"] for e in first["enemies"]] == [f"{CANON} 1", f"{CANON} 2"]
    assert {e["archetype_id"] for e in first["enemies"]} == {INICIADO}


def test_backfill_reescreve_referencias_do_combate():
    first = persistence.backfill_enemy_ids(_legacy_raw())
    combat = first["combat"]
    positions = combat["scene"]["positions"]
    assert set(positions) == {"player", "enemy_legacy_1", "enemy_legacy_2"}
    assert positions["player"]["engaged_with"] == ["enemy_legacy_1"]
    assert positions["enemy_legacy_1"]["engaged_with"] == ["player"]
    assert positions["enemy_legacy_2"]["hidden_from"] == ["player"]
    assert combat["order"] == ["player", "enemy_legacy_1", "enemy_legacy_2"]
    assert first["combat_target"] == f"{CANON} 1"  # nome resolve pelo nome; não é id


def test_save_com_id_inalterado_e_colisao():
    raw = _legacy_raw()
    raw["enemies"][0]["id"] = "enemy_legacy_2"
    out = persistence.backfill_enemy_ids(raw)
    assert out["enemies"][0]["id"] == "enemy_legacy_2"
    assert out["enemies"][1]["id"] == "enemy_legacy_3"
    with_ids = persistence.backfill_enemy_ids(out)
    assert with_ids is out


def test_save_sem_inimigos_sem_copia():
    raw = {"game_id": "g", "enemies": [], "combat": {}}
    assert persistence.backfill_enemy_ids(raw) is raw


def test_archetype_sem_casamento_cai_no_nome():
    raw = {"enemies": [{"name": "Coisa Estranha"}], "combat": {}}
    out = persistence.backfill_enemy_ids(raw)
    assert out["enemies"][0]["archetype_id"] == "Coisa Estranha"
    assert out["enemies"][0]["id"] == "enemy_legacy_1"


def test_load_legado_sem_nome_canonico_em_ids_e_alvos():
    state = persistence._raw_to_state(_legacy_raw())
    ids = [e["id"] for e in state["enemies"]]
    assert ids == ["enemy_legacy_1", "enemy_legacy_2"]
    participants = (state["combat"].get("encounter") or {}).get("participants") or []
    assert {p["participant_id"] for p in participants} == set(ids)
    payload = json.loads(api.format_response(state).model_dump_json())
    assert [e["id"] for e in payload["combat"]["enemies"]] == ids
    assert [e["name"] for e in payload["combat"]["enemies"]] == ["Iniciado 1", "Iniciado 2"]
    targets = ct.basic_action_targeting(state, "attack").valid_targets
    assert set(targets) <= set(ids) and targets
    blob = json.dumps(payload, ensure_ascii=False)
    assert CANON not in blob
    assert fd.concealed_name_problems(payload, state) == []


# --- R3: casos de eval do rótulo + mutação do oráculo ------------------------------


def _faction_label_cases() -> list[dict]:
    path = "evals/datasets/regression/player_knowledge.jsonl"
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return [c for c in rows if "faction-label" in c["tags"]]


def _oracle_outcomes() -> dict[str, bool]:
    from types import SimpleNamespace

    from evals.core.adapters import PlayerKnowledgeAdapter
    from evals.evaluators.player_knowledge import problem_class

    out = {}
    for case in _faction_label_cases():
        if case["input"]["operation"] != "oracle_mutation":
            continue
        actual = PlayerKnowledgeAdapter().execute(SimpleNamespace(input=case["input"])).actual
        got = sorted({problem_class(p) for p in actual["oracle_problems"]})
        out[case["id"]] = got == sorted(case["expected"]["oracle_problem_classes"])
    return out


def test_eval_casos_do_rotulo_passam():
    cases = _faction_label_cases()
    assert len(cases) == 5
    assert all(_oracle_outcomes().values())


def test_eval_mutacao_do_oraculo_e_detectada(monkeypatch):
    monkeypatch.setattr(fd, "concealed_name_problems", lambda payload, state: [])
    outcomes = _oracle_outcomes()
    assert outcomes["pk.oracle.concealed_faction_name"] is False
    assert outcomes["pk.oracle.concealed_faction_plural_spacing"] is False
