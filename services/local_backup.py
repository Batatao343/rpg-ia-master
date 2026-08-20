"""Manifesto/hashes para backup local completo, independente do subprocesso."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


MANIFEST_VERSION = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> dict:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "manifest.json":
            continue
        files.append({
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return {
        "version": MANIFEST_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "files": files,
    }


def write_manifest(root: Path) -> dict:
    manifest = build_manifest(root)
    fd, temporary = tempfile.mkstemp(prefix=".manifest.", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, root / "manifest.json")
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return manifest


def verify_manifest(root: Path) -> dict:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError("versão de manifesto incompatível")
    expected = {row["path"]: row for row in manifest.get("files") or []}
    actual = {row["path"]: row for row in build_manifest(root)["files"]}
    if set(expected) != set(actual):
        raise ValueError("conjunto de arquivos do backup divergiu")
    for path, row in expected.items():
        if row["sha256"] != actual[path]["sha256"] or row["size"] != actual[path]["size"]:
            raise ValueError(f"hash/tamanho inválido: {path}")
    return manifest


def copy_sources(destination: Path, sources: Iterable[tuple[Path, str]]) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("destino de backup precisa estar vazio")
    destination.mkdir(parents=True, exist_ok=True)
    for source, relative in sources:
        target = destination / relative
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def restore_files(backup: Path, destination: Path, *, prefixes: tuple[str, ...]) -> None:
    verify_manifest(backup)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("destino de restore precisa estar vazio")
    destination.mkdir(parents=True, exist_ok=True)
    for row in json.loads((backup / "manifest.json").read_text(encoding="utf-8"))["files"]:
        relative = str(row["path"])
        if not relative.startswith(prefixes):
            continue
        source = backup / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
