"""SPEC-370 R12: com `RPG_FAUNA=on` o migrante pesa MIGRANT_WEIGHT x o fator neutro."""

from __future__ import annotations

import gamedata
import world_utils as wu

LOC = "nova_arcadia"  # no raiz com conexao para outra regiao


def _hunted_bk() -> dict:
    """Toda criatura de Nova Arcadia quase extinta: a fauna local rareia e abre vaga ao migrante."""
    return {
        cid: {"defeated": 8, "last_update_turn": 100}
        for cid, e in gamedata.BESTIARY.items()
        if "nova_arcadia" in (e.get("regions") or [])
    }


def _rows(period: str):
    return wu.encounter_distribution(
        gamedata.get_location(LOC),
        3,
        100,
        bestiary_knowledge=_hunted_bk(),
        projection={},
        world={"current_location_id": LOC, "world_clock": {"day": 5, "period": period}},
        world_sim={},
    )


def _migrant_share(rows) -> float | None:
    total = sum(w for _e, w in rows)
    mig = [w for e, w in rows if "nova_arcadia" not in (e.get("regions") or [])]
    return (sum(mig) / total) if mig and total else None


def test_migrante_fatia_nao_explode_com_fauna_on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "off")
    off = _migrant_share(_rows("Noite"))
    assert off is not None, "o cenario precisa disparar o migrante"
    monkeypatch.setenv("RPG_FAUNA", "on")
    on = _migrant_share(_rows("Manhã"))  # fora do horario de boa parte da fauna
    assert on is not None
    assert on <= 1.5 * off, (on, off)


def test_migrante_peso_vira_neutro_no_on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "off")
    off = {e["id"]: w for e, w in _rows("Manhã") if "nova_arcadia" not in (e.get("regions") or [])}
    monkeypatch.setenv("RPG_FAUNA", "on")
    on = {e["id"]: w for e, w in _rows("Manhã") if "nova_arcadia" not in (e.get("regions") or [])}
    assert off and on
    assert max(on.values()) <= max(off.values()) + 1e-9  # neutro <= 1 aqui; nunca acima do fixo
