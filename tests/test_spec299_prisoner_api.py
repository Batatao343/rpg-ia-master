"""SPEC-299 etapa 9 — interface de prisioneiros (sem chamador no grafo)."""

from __future__ import annotations

import pathlib
import re

import pytest

from services import law
from tests.spec299_helpers import base_state


@pytest.fixture(autouse=True)
def _law_on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")


def _prisoner(pid="p1", enemy="enemy_bandido_capitao", alive=True):
    return {
        "prisoner_id": pid,
        "name": "Capitão",
        "enemy_id": enemy,
        "faction_id": "",
        "alive": alive,
    }


def test_prisoner_bounty_zero_lawless():
    assert law.prisoner_bounty(base_state("brekmar"), _prisoner(), "brekmar") == 0
    assert (
        law.prisoner_bounty(base_state(), _prisoner(enemy="enemy_desconhecido"), "nova_arcadia")
        == 0
    )
    assert law.prisoner_bounty(base_state(), _prisoner(), "nova_arcadia") == 60


def test_deliver_pays_bounty_by_enemy():
    state = base_state()
    upd, receipt = law.deliver_prisoner(state, _prisoner(), "nova_arcadia")
    assert receipt == {"ok": True, "reason": "ok", "gold": 60, "jurisdiction_id": "codigo_de_ferro"}
    assert upd["player"]["gold"] == 560
    assert "p1" in upd["law_state"]["delivered"]
    # entregar no local da jurisdição não gera crime
    assert not upd["law_state"]["crimes"]


def test_deliver_in_lawless_location_refused():
    upd, receipt = law.deliver_prisoner(base_state("brekmar"), _prisoner(), "brekmar")
    assert upd == {} and receipt["reason"] == "sem_lei" and not receipt["ok"]


def test_deliver_dead_prisoner_rejected():
    upd, receipt = law.deliver_prisoner(base_state(), _prisoner(alive=False), "nova_arcadia")
    assert upd == {} and receipt["reason"] == "prisioneiro_morto"


def test_deliver_is_idempotent_by_prisoner_id():
    state = base_state()
    upd, _ = law.deliver_prisoner(state, _prisoner(), "nova_arcadia")
    state = {**state, **upd}
    again, receipt = law.deliver_prisoner(state, _prisoner(), "nova_arcadia")
    assert again == {} and receipt["reason"] == "ja_entregue"
    assert state["player"]["gold"] == 560


def test_no_graph_caller():
    """R23: nenhum nó/serviço do grafo chama a interface de prisioneiros."""
    root = pathlib.Path(__file__).resolve().parent.parent
    pattern = re.compile(r"\b(?:deliver_prisoner|prisoner_bounty)\b")
    offenders = []
    for folder in ("agents", "services", "api.py", "main.py", "world_utils.py", "playtest"):
        target = root / folder
        files = [target] if target.is_file() else list(target.rglob("*.py"))
        for path in files:
            if path.name == "law.py":
                continue
            if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(str(path.relative_to(root)))
    assert offenders == []
