"""SPEC-414 R3: basetemp com PID e limpeza por idade."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from tests.basetemp_support import basetemp_name, choose_basetemp, prune_old_basetemps


def test_basetemp_name_has_pid() -> None:
    a = basetemp_name(Path("C:/x"), 4242)
    assert re.match(r"^pt-[0-9a-f]{8}-4242$", a)
    b = basetemp_name(Path("C:/x"), 4243)
    assert a != b and a.rsplit("-", 1)[0] == b.rsplit("-", 1)[0]


def test_prune_removes_only_old_pt_dirs(tmp_path: Path) -> None:
    now = 1_000_000.0
    old, new = now - 7 * 3600, now - 60
    names = {
        "pt-0123abcd": old,
        "pt-0123abcd-77": old,
        "pt-0123abcd-88": new,
        "pt-zz": old,
        "outro": old,
    }
    for name, mtime in names.items():
        d = tmp_path / name
        d.mkdir()
        os.utime(d, (mtime, mtime))
    removed = prune_old_basetemps(tmp_path, now, 6 * 3600)
    assert sorted(p.name for p in removed) == ["pt-0123abcd", "pt-0123abcd-77"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["outro", "pt-0123abcd-88", "pt-zz"]


def test_prune_survives_locked_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "pt-0123abcd-1"
    d.mkdir()
    os.utime(d, (1.0, 1.0))

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("locked")

    monkeypatch.setattr(shutil, "rmtree", boom)
    assert prune_old_basetemps(tmp_path, 10**9, 3600) == []


def test_choose_basetemp_rules(tmp_path: Path) -> None:
    def pick(**kw: object) -> str | None:
        args: dict = {
            "platform": "win32",
            "is_worker": False,
            "has_basetemp": False,
            "numprocesses": 2,
            "checkout": Path("C:/x"),
            "tmpdir": tmp_path,
            "pid": 5,
        }
        args.update(kw)
        return choose_basetemp(**args)

    chosen = pick()
    assert chosen == str(tmp_path / basetemp_name(Path("C:/x"), 5))
    assert pick(is_worker=True) is None
    assert pick(has_basetemp=True) is None
    assert pick(numprocesses=None) is None
    assert pick(platform="linux") is None
