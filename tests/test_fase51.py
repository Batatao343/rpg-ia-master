"""Suíte da Fase 5.1 — harness de playtest + 10 perfis (offline, MockLLM)."""
import os

import pytest

from playtest.profiles import PROFILES
from playtest.runner import run_campaign, PLAYTEST_SAVES_DIR


# --- Etapa 1 — runner + explorador -----------------------------------------

def test_campanha_10_turnos_sem_erros():
    """R6 — smoke automatizado permanente: 10 turnos sem exceção não-capturada."""
    res = run_campaign("explorador", turns=10, seed=42)
    assert res.turns_completed == 10
    assert res.errors == [], res.errors


def test_determinismo_mesma_seed():
    """R3 — mesmo (profile, seed, turns) → mesma sequência de ações."""
    a = run_campaign("explorador", turns=8, seed=7)
    b = run_campaign("explorador", turns=8, seed=7)
    assert [r.action for r in a.history] == [r.action for r in b.history]


def test_erro_de_turno_nao_derruba_campanha(monkeypatch):
    """R4 — exceção de um turno vira registro em errors; campanha completa."""
    import main

    class _Flaky:
        def __init__(self, real):
            self.real, self.n = real, 0

        def invoke(self, state, *a, **k):
            self.n += 1
            if self.n == 4:  # call 1 = cena de abertura; turno 3 = 4ª chamada
                raise RuntimeError("boom no turno 3")
            return self.real.invoke(state, *a, **k)

    monkeypatch.setattr(main, "app", _Flaky(main.app))
    res = run_campaign("explorador", turns=5, seed=1)
    assert res.turns_completed == 5
    assert len(res.errors) == 1
    assert res.errors[0]["turn"] == 3


def test_saves_em_diretorio_isolado():
    """R7 — save da campanha vai p/ saves_playtest/, não polui saves/."""
    import persistence
    antes = persistence.SAVES_DIR
    res = run_campaign("explorador", turns=3, seed=3)
    assert PLAYTEST_SAVES_DIR in res.save_path
    assert os.path.exists(res.save_path)
    # SAVES_DIR restaurado ao fim (context manager).
    assert persistence.SAVES_DIR == antes


# --- Etapa 2 — os outros 9 perfis ------------------------------------------

@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_todos_perfis_rodam_5_turnos(profile):
    """Todos os 10 perfis rodam 5 turnos sem exceção não-capturada."""
    res = run_campaign(profile, turns=5, seed=11)
    assert res.turns_completed == 5
    assert res.errors == [], (profile, res.errors)


def test_troll_nao_quebra_router():
    """Inputs absurdos/injeção não derrubam o turno."""
    res = run_campaign("troll", turns=6, seed=99)
    assert res.errors == [], res.errors


def test_mapa_breaker_nao_teleporta():
    """Local final sempre existe no grafo (nunca teleporta p/ fora do mapa)."""
    from gamedata import get_location
    res = run_campaign("mapa_breaker", turns=8, seed=5)
    loc_id = res.final_state.get("world", {}).get("current_location_id", "")
    assert get_location(loc_id), f"local final {loc_id!r} não existe no grafo"


def test_quester_fecha_quest_no_harness():
    """Fase 5: o perfil quester + o MockLLM propondo quest_completed fazem o
    harness FECHAR quest offline (antes, o mock só criava, nunca completava)."""
    res = run_campaign("quester", turns=25, seed=1)
    assert res.errors == [], res.errors
    completadas = [q for q in res.final_state.get("quests", [])
                   if isinstance(q, dict) and q.get("status") == "completed"]
    assert completadas, "nenhuma quest foi concluída na campanha do quester"
    assert any(e.get("type") == "quest_completed"
               for e in res.final_state.get("event_log", []))


# --- Etapa 3 — CLI ----------------------------------------------------------

def test_cli_run_devolve_exit_0(monkeypatch, tmp_path):
    """CLI `run` roda uma campanha curta, grava telemetria e sai 0."""
    from playtest import telemetry
    from playtest.__main__ import main
    monkeypatch.setattr(telemetry, "PLAYTEST_RUNS_DIR", str(tmp_path / "runs"))
    rc = main(["run", "--profile", "explorador", "--turns", "3", "--seed", "0"])
    assert rc == 0
