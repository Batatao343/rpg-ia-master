from __future__ import annotations

import os
import threading
import time
import uuid
from copy import deepcopy

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pydantic import ValidationError

import api
import persistence
from llm_setup import LLMAttemptEvent, ModelTier


def _state(game_id: str, *, gold: int = 10) -> dict:
    req = api.CombatSimulatorRequest(
        class_name=next(iter(api.gamedata.CLASSES)),
        level=1,
        enemy_id=next(iter(api.gamedata.BESTIARY)),
        quantity=1,
    )
    state = api._build_combat_simulator_state(req)
    state["game_id"] = game_id
    state["player"]["gold"] = gold
    state["combat_simulation"] = {"enabled": False}
    return state


def _checkpoint_state(game_id: str, *, gold: int = 10) -> dict:
    state = _state(game_id, gold=gold)
    state["combat"] = {"active": False, "round": 0, "scene": None}
    state["enemies"] = []
    state["combat_target"] = None
    return state


def test_checkpoint_nao_entra_em_latest_nem_listagem(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid, gold=11))
    assert persistence.save_checkpoint(_checkpoint_state(gid, gold=99))
    checkpoint = tmp_path / f"{gid}.checkpoint.json"
    os.utime(checkpoint, (checkpoint.stat().st_atime, checkpoint.stat().st_mtime + 10))

    assert persistence.get_latest_save_file() == str(tmp_path / f"{gid}.json")
    listed = persistence.list_saves()
    assert len(listed) == 1
    assert listed[0]["game_id"] == gid


def test_delete_remove_save_checkpoint_e_memoria_inclusive_orfao(tmp_path, monkeypatch):
    saves = tmp_path / "saves"
    memory = tmp_path / "memory"
    monkeypatch.setattr(persistence, "SAVES_DIR", str(saves))
    monkeypatch.setattr(persistence, "SESSION_MEMORY_DIR", str(memory))
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid))
    assert persistence.save_checkpoint(_checkpoint_state(gid))
    session_dir = memory / gid
    session_dir.mkdir(parents=True)
    (session_dir / "index.bin").write_bytes(b"x")

    assert persistence.delete_save(gid) is True
    assert not (saves / f"{gid}.json").exists()
    assert not (saves / f"{gid}.checkpoint.json").exists()
    assert not session_dir.exists()

    # Um checkpoint órfão ainda deve ser limpável pelo endpoint normal.
    assert persistence.save_checkpoint(_checkpoint_state(gid))
    assert persistence.delete_save(gid) is True
    assert not (saves / f"{gid}.checkpoint.json").exists()


def test_escrita_atomica_preserva_save_anterior_quando_replace_falha(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid, gold=10))
    original = (tmp_path / f"{gid}.json").read_text(encoding="utf-8")

    monkeypatch.setattr(persistence.os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))
    assert persistence.save_game_state(_state(gid, gold=999)) is False
    assert (tmp_path / f"{gid}.json").read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.tmp"))


def test_action_id_repetido_nao_executa_segundo_turno(monkeypatch):
    gid = str(uuid.uuid4())
    state = _state(gid)
    assert persistence.save_game_state(state)
    calls = []

    class Graph:
        def invoke(self, current):
            calls.append(1)
            out = deepcopy(current)
            out["world"]["turn_count"] = int(out["world"].get("turn_count", 0)) + 1
            out["messages"] = list(out.get("messages") or []) + [AIMessage(content="feito")]
            return out

    monkeypatch.setattr(api, "game_graph", Graph())
    client = TestClient(api.app)
    action_id = str(uuid.uuid4())
    body = {"game_id": gid, "input_text": "avanço", "action_id": action_id}
    first = client.post("/game/action", json=body)
    second = client.post("/game/action", json=body)

    assert first.status_code == second.status_code == 200
    assert len(calls) == 1
    assert second.json()["world"]["turn_count"] == 1
    loaded = persistence.load_game_state(persistence.save_path(gid))
    assert loaded["processed_action_ids"] == [action_id]


def test_mutacoes_do_mesmo_jogo_sao_serializadas(monkeypatch):
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid))
    guard = threading.Lock()
    active = 0
    max_active = 0

    class Graph:
        def invoke(self, current):
            nonlocal active, max_active
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            out = deepcopy(current)
            out["world"]["turn_count"] = int(out["world"].get("turn_count", 0)) + 1
            out["messages"] = list(out.get("messages") or []) + [AIMessage(content="feito")]
            with guard:
                active -= 1
            return out

    monkeypatch.setattr(api, "game_graph", Graph())
    responses = []

    def send():
        responses.append(TestClient(api.app).post(
            "/game/action",
            json={"game_id": gid, "input_text": "avanço",
                  "action_id": str(uuid.uuid4())},
        ))

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert [response.status_code for response in responses] == [200, 200]
    assert max_active == 1
    loaded = persistence.load_game_state(persistence.save_path(gid))
    assert loaded["world"]["turn_count"] == 2


def test_worker_sse_persiste_mesmo_se_consumidor_fecha(monkeypatch):
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid))
    finished = threading.Event()
    action_id = str(uuid.uuid4())

    class Graph:
        def stream(self, current, **_kwargs):
            yield "updates", {"campaign_manager": {}}
            out = deepcopy(current)
            out["world"]["turn_count"] = int(out["world"].get("turn_count", 0)) + 1
            out["messages"] = list(out.get("messages") or []) + [AIMessage(content="feito")]
            yield "values", out
            finished.set()

    monkeypatch.setattr(api, "game_graph", Graph())
    req = api.ActionRequest(game_id=gid, input_text="avanço", action_id=action_id)
    stream = api._stream_turn(req, gid)
    assert "accepted" in next(stream)
    assert "phase" in next(stream)
    stream.close()

    assert finished.wait(timeout=2)
    deadline = time.monotonic() + 2
    loaded = None
    while time.monotonic() < deadline:
        loaded = persistence.load_game_state(persistence.save_path(gid))
        if action_id in (loaded.get("processed_action_ids") or []):
            break
        time.sleep(0.01)
    assert loaded["world"]["turn_count"] == 1
    assert action_id in loaded["processed_action_ids"]


def test_falha_de_persistencia_no_turno_retorna_500(monkeypatch):
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid))

    class Graph:
        def invoke(self, current):
            out = deepcopy(current)
            out["messages"] = list(out.get("messages") or []) + [AIMessage(content="feito")]
            return out

    monkeypatch.setattr(api, "game_graph", Graph())
    monkeypatch.setattr(api, "save_game_state", lambda _state: False)
    response = TestClient(api.app).post(
        "/game/action",
        json={"game_id": gid, "input_text": "avanço", "action_id": str(uuid.uuid4())},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Erro interno ao processar o turno."


def test_circuit_open_nao_conta_rede_falha_ou_custo():
    event = LLMAttemptEvent(
        provider="deepseek", model="deepseek-v4-flash", tier=ModelTier.FAST,
        attempt_index=0, latency_ms=0, fell_back=False,
        outcome="circuit_open", error="quota", structured=False,
    )
    token = api._llm_attempt_events.set([])
    try:
        api._attempt_telemetry_hook(event)
        fields = api._llm_log_fields([], api._llm_attempt_events.get())
    finally:
        api._llm_attempt_events.reset(token)
    assert fields["llm_requests"] == 0
    assert fields["llm_failures"] == 0
    assert fields["cost_usd_est"] == 0
    assert fields["llm_skipped"] == 1


def test_criacao_rejeita_opcoes_fora_dos_catalogos():
    base = {
        "name": "Teste", "race": "Humano",
        "class_name": next(iter(api.gamedata.CLASSES)),
        "region": (api.load_json_data("origins.json")["regions"])[0]["name"],
        "level": 1,
    }
    for field, value in (("class_name", "Batedor das Fronteiras"),
                         ("race", "Marciano"), ("region", "Lua")):
        payload = {**base, field: value}
        try:
            api.CreateCharacterRequest(**payload)
        except ValidationError:
            continue
        raise AssertionError(f"{field} desconhecido foi aceito")


def test_fixture_global_isola_diretorios_de_runtime(tmp_path):
    assert os.path.abspath(persistence.SAVES_DIR).startswith(os.path.abspath(str(tmp_path)))
    import rag
    assert os.path.abspath(rag.SAVES_DIR).startswith(os.path.abspath(str(tmp_path)))
