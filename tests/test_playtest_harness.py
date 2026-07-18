"""Suíte da spec playtest-stop-gameover — runner para na morte + rota fiel.

Offline/determinístico. `_run_turn` é testado direto com um grafo fake (evita
depender de combate real acontecer num turno específico); a rota nunca-vazia é
verificada também numa campanha mock real. Ver specs/playtest-stop-gameover.md.
"""
from playtest import runner
from playtest.runner import CampaignResult, TurnRecord, _run_turn, run_campaign


class _FakeGraph:
    """Grafo fake: `.invoke` devolve o estado; `.stream` emite o update do
    dm_router (rota) + o estado final via `values`. `die_at` liga game_over no
    N-ésimo turno de streaming (para exercitar o stop do runner)."""

    def __init__(self, router_next="storyteller", die_at=None):
        self.router_next = router_next
        self.die_at = die_at
        self.turn = 0

    def invoke(self, state):
        return state

    def stream(self, state, stream_mode=None):
        self.turn += 1
        yield ("updates", {"campaign_manager": {}})
        yield ("updates", {"dm_router": {"next": self.router_next}})
        out = dict(state)
        if self.die_at is not None and self.turn >= self.die_at:
            out["game_over"] = True
        yield ("values", out)


# --- Etapa 1: stop no game_over ---------------------------------------------

def test_runner_para_no_game_over(monkeypatch):
    import main
    monkeypatch.setattr(main, "app", _FakeGraph(die_at=3))
    res = run_campaign("explorador", turns=10, seed=0, invariants=False)
    assert res.turns_completed == 3
    assert len(res.history) == 3
    assert res.aborted_reason and "player_death" in res.aborted_reason
    assert "turno 3" in res.aborted_reason


def test_runner_sem_morte_completa_os_turnos(monkeypatch):
    import main
    monkeypatch.setattr(main, "app", _FakeGraph(die_at=None))
    res = run_campaign("explorador", turns=5, seed=0, invariants=False)
    assert res.turns_completed == 5
    assert res.aborted_reason is None


# --- Etapa 2: rota fiel ------------------------------------------------------

def test_run_turn_usa_decisao_do_router():
    fake = _FakeGraph(router_next="npc_actor")
    state = {"combat": {"active": False}}
    _final, route = _run_turn(fake, state)
    assert route == "npc_actor"


def test_run_turn_combate_ativo_registra_combat_agent():
    # Lock de combate: entrada com combat.active → rota combat_agent, ainda que
    # o router diga outra coisa (spec R3).
    fake = _FakeGraph(router_next="storyteller")
    state = {"combat": {"active": True}}
    _final, route = _run_turn(fake, state)
    assert route == "combat_agent"


def test_run_turn_rota_nunca_vazia_em_turno_vivo():
    fake = _FakeGraph(router_next="loot")
    _final, route = _run_turn(fake, {"combat": None})
    assert route == "loot"


def test_rota_nunca_vazia_campanha_mock_real():
    # Campanha mock no grafo REAL: todo turno vivo (sem erro) tem rota não-vazia.
    res = run_campaign("explorador", turns=5, seed=1, invariants=False)
    vivos = [r for r in res.history if not r.error]
    assert vivos, "esperava ao menos um turno vivo"
    assert all(r.route for r in vivos), \
        f"turno vivo com rota vazia: {[r.turn for r in vivos if not r.route]}"
    assert all(r.route in runner._ROUTER_ROUTES for r in vivos)


# --- Etapa: telemetria/report da morte (R4) ---------------------------------

def _rec(turn, route="combat_agent"):
    return TurnRecord(turn=turn, action="ataco", route=route, latency_ms=1,
                      player_hp=0 if turn == 3 else 10, player_max_hp=10)


def test_summary_tem_death_location_e_cause():
    from playtest.telemetry import build_summary
    final = {
        "game_over": True,
        "player": {"level": 2, "gold": 0},
        "world": {"visited": []},
        "event_log": [{"type": "player_died", "payload":
                       {"killer": "Zumbi Blindado", "location": "Caverna de Morrakh"}}],
    }
    res = CampaignResult(profile="combate", seed=0, turns_completed=3, errors=[],
                         history=[_rec(1), _rec(2), _rec(3)], final_state=final,
                         save_path="x", aborted_reason="player_death (turno 3)")
    recs = [{"turn": r.turn, "route": r.route, "latency_ms": 1,
             "player_hp": r.player_hp, "player_max_hp": r.player_max_hp,
             "violations": [], "cost_usd": 0.0} for r in res.history]
    summary = build_summary(res, recs)
    assert summary["deaths"] == 1
    assert summary["death_location"] == "Caverna de Morrakh"
    assert summary["death_cause"] == "Zumbi Blindado"


def test_report_renderiza_secao_de_mortes():
    from playtest.report import RunReport, render_markdown
    rep = RunReport(
        run_id="r1",
        campaigns=[{"profile": "combate", "seed": 0, "deaths": 1,
                    "first_death_turn": 13, "death_location": "Skallgard",
                    "death_cause": "Afogado", "latency_ms": {}}],
        top_violations=[], top_errors=[], deltas=None, mock_any=True)
    md = render_markdown(rep)
    assert "## Mortes" in md
    assert "Skallgard" in md and "Afogado" in md
