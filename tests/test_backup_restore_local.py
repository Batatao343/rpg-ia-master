from pathlib import Path

import pytest

from services.local_backup import copy_sources, restore_files, verify_manifest, write_manifest


def test_manifest_detecta_corrupcao_e_restore_exige_destino_vazio(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "database.dump").write_bytes(b"postgres")
    (source / "objects").mkdir()
    (source / "objects" / "portrait.webp").write_bytes(b"image")
    backup = tmp_path / "backup"
    copy_sources(backup, [(source / "database.dump", "database.dump"),
                          (source / "objects", "objects")])
    write_manifest(backup)
    assert len(verify_manifest(backup)["files"]) == 2

    restored = tmp_path / "restored"
    restore_files(backup, restored, prefixes=("objects/",))
    assert (restored / "objects" / "portrait.webp").read_bytes() == b"image"
    with pytest.raises(ValueError, match="vazio"):
        restore_files(backup, restored, prefixes=("objects/",))

    (backup / "database.dump").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="inválido"):
        verify_manifest(backup)


def test_backup_interrompido_sem_manifesto_nao_e_valido(tmp_path: Path):
    backup = tmp_path / "partial"
    backup.mkdir()
    (backup / "database.dump").write_bytes(b"partial")
    with pytest.raises(FileNotFoundError):
        verify_manifest(backup)
