import uuid
from pathlib import Path

import persistence
from services import checkpoints


def _state(game_id: str, turn: int = 10) -> dict:
    return {
        "game_id": game_id,
        "player": {"name": "Valen", "gold": turn},
        "world": {"turn_count": turn},
        "messages": [],
    }


def _configure(tmp_path, monkeypatch):
    saves = tmp_path / "saves"
    memory = tmp_path / "memory"
    monkeypatch.setattr(persistence, "SAVES_DIR", str(saves))
    monkeypatch.setattr(persistence, "SESSION_MEMORY_DIR", str(memory))
    return saves, memory


def test_checkpoint_em_disco_restaura_memoria_raiz_e_npc(tmp_path, monkeypatch):
    saves, memory = _configure(tmp_path, monkeypatch)
    gid = str(uuid.uuid4())
    session = memory / gid
    (session / "npc_mara").mkdir(parents=True)
    (session / "index.faiss").write_bytes(b"antes")
    (session / "npc_mara" / "index.faiss").write_bytes(b"npc-antes")

    assert persistence.save_checkpoint(_state(gid)) is True
    (session / "index.faiss").write_bytes(b"morte")
    (session / "npc_mara" / "index.faiss").write_bytes(b"npc-morte")
    (session / "fato_futuro.txt").write_text("morreu", encoding="utf-8")

    dead = _state(gid, 18)
    dead["death_pending"] = True
    restored = checkpoints.resolve_death_choice(dead, "continue")

    assert restored["world"]["turn_count"] == 10
    assert (session / "index.faiss").read_bytes() == b"antes"
    assert (session / "npc_mara" / "index.faiss").read_bytes() == b"npc-antes"
    assert not (session / "fato_futuro.txt").exists()
    assert (saves / f"{gid}.checkpoint.memory").is_dir()


def test_checkpoint_sem_memoria_remove_fatos_criados_depois(tmp_path, monkeypatch):
    _, memory = _configure(tmp_path, monkeypatch)
    gid = str(uuid.uuid4())
    assert persistence.save_checkpoint(_state(gid)) is True
    session = memory / gid
    session.mkdir(parents=True)
    (session / "index.faiss").write_bytes(b"fato posterior")

    dead = _state(gid, 11)
    dead["death_pending"] = True
    checkpoints.resolve_death_choice(dead, "continue")
    assert not session.exists()


def test_snapshot_em_memoria_carrega_arvore_e_remove_metadado(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    gid = str(uuid.uuid4())
    session = Path(persistence.SESSION_MEMORY_DIR) / gid
    session.mkdir(parents=True)
    (session / "index.pkl").write_bytes(b"checkpoint")

    snap = checkpoints.snapshot(_state(gid))
    (session / "index.pkl").write_bytes(b"descartado")
    dead = _state(gid, 17)
    dead["death_pending"] = True
    restored = checkpoints.resolve_death_choice(dead, "continue", checkpoint=snap)

    assert (session / "index.pkl").read_bytes() == b"checkpoint"
    assert "_checkpoint_memory_snapshot" not in restored


def test_delete_save_remove_snapshot_de_memoria(tmp_path, monkeypatch):
    saves, _ = _configure(tmp_path, monkeypatch)
    gid = str(uuid.uuid4())
    assert persistence.save_checkpoint(_state(gid))
    snapshot_dir = saves / f"{gid}.checkpoint.memory"
    assert snapshot_dir.exists()
    assert persistence.delete_save(gid) is True
    assert not snapshot_dir.exists()


def test_falha_no_json_reverte_snapshot_de_memoria(tmp_path, monkeypatch):
    saves, memory = _configure(tmp_path, monkeypatch)
    gid = str(uuid.uuid4())
    session = memory / gid
    session.mkdir(parents=True)
    (session / "index.faiss").write_bytes(b"checkpoint-antigo")
    assert persistence.save_checkpoint(_state(gid, 10))
    snapshot_file = saves / f"{gid}.checkpoint.memory" / "index.faiss"
    assert snapshot_file.read_bytes() == b"checkpoint-antigo"

    (session / "index.faiss").write_bytes(b"novo-incompleto")
    monkeypatch.setattr(
        persistence, "_atomic_write_json",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disco cheio")),
    )
    assert persistence.save_checkpoint(_state(gid, 20)) is False
    assert snapshot_file.read_bytes() == b"checkpoint-antigo"


def test_checkpoint_legado_sem_snapshot_limpa_indice_posterior(tmp_path, monkeypatch):
    saves, memory = _configure(tmp_path, monkeypatch)
    gid = str(uuid.uuid4())
    assert persistence.save_checkpoint(_state(gid, 10))
    import shutil
    shutil.rmtree(saves / f"{gid}.checkpoint.memory")
    session = memory / gid
    session.mkdir(parents=True)
    (session / "index.faiss").write_bytes(b"timeline incerta")

    dead = _state(gid, 15)
    dead["death_pending"] = True
    restored = checkpoints.resolve_death_choice(dead, "continue")
    assert restored["world"]["turn_count"] == 10
    assert not session.exists()
