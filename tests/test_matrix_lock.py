from __future__ import annotations

import json

import pytest

from playtest.matrix_lock import MatrixAlreadyRunningError, matrix_single_flight


def test_segunda_matriz_e_bloqueada_enquanto_dona_esta_viva(tmp_path):
    lock_path = tmp_path / ".matrix-suite.lock"

    with matrix_single_flight(lock_path):
        with pytest.raises(MatrixAlreadyRunningError):
            with matrix_single_flight(lock_path):
                pass


def test_lock_de_pid_morto_e_recuperado(tmp_path, monkeypatch):
    lock_path = tmp_path / ".matrix-suite.lock"
    lock_path.write_text(json.dumps({
        "pid": 999_999_999, "host": "local", "token": "antigo",
    }), encoding="utf-8")
    monkeypatch.setattr("playtest.matrix_lock.socket.gethostname", lambda: "local")
    monkeypatch.setattr("playtest.matrix_lock._pid_is_alive", lambda _pid: False)

    with matrix_single_flight(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_lock_invalido_e_recuperado_e_excecao_libera(tmp_path):
    lock_path = tmp_path / ".matrix-suite.lock"
    lock_path.write_text("não-json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="falha dentro da matriz"):
        with matrix_single_flight(lock_path):
            raise RuntimeError("falha dentro da matriz")

    assert not lock_path.exists()
