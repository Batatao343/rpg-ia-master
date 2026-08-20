"""Fakes e auditoria de writes para testes de infraestrutura."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from infrastructure.local_adapters import *  # noqa: F403 - módulo público de fakes


@dataclass
class WriteRecorder:
    allowed_roots: tuple[Path, ...]
    writes: list[Path] = field(default_factory=list)

    def record(self, path: str | Path) -> None:
        resolved = Path(path).resolve()
        self.writes.append(resolved)
        if not any(root.resolve() == resolved or root.resolve() in resolved.parents for root in self.allowed_roots):
            raise AssertionError(f"write persistente fora do sandbox: {resolved}")

    @contextmanager
    def capture(self) -> Iterator["WriteRecorder"]:
        self.writes.clear()
        yield self
