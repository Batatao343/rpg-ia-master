"""SPEC-342 R1.3 - 'Sem matar' vale para toda jogada attack/card da rodada."""

from __future__ import annotations

from agents import combat as cbt
from services.conflict_turn import TurnDeclaration, TurnStep


def _decl() -> TurnDeclaration:
    defesa = TurnStep(kind="maneuver", maneuver="guardar")
    golpe = TurnStep(kind="card", card_id="c2", target_id="e1")
    # `acao` e `jogadas[0]` sao o mesmo objeto (como o parser faz)
    return TurnDeclaration(actor_id="player", acao=defesa, jogadas=[defesa, golpe])


def test_spare_marks_every_attack_play(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    decl = _decl()
    cbt._mark_nonlethal(decl, "Encerro a rodada: Guardar, Golpe. Sem matar.")
    assert not decl.jogadas[0].params.get("nao_letal")  # manobra nao e golpe
    assert decl.jogadas[1].params["nao_letal"] is True


def test_spare_marks_all_strikes(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    a = TurnStep(kind="attack", target_id="e1")
    b = TurnStep(kind="card", card_id="c2", target_id="e1")
    decl = TurnDeclaration(actor_id="player", acao=a, jogadas=[a, b])
    cbt._mark_nonlethal(decl, "Encerro a rodada: A, B. Sem matar.")
    assert a.params["nao_letal"] and b.params["nao_letal"]


def test_spare_off_flag_untouched(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "off")
    decl = _decl()
    cbt._mark_nonlethal(decl, "Encerro a rodada: A. Sem matar.")
    assert all("nao_letal" not in s.params for s in decl.jogadas)


def test_no_declaration_no_mark(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    decl = _decl()
    cbt._mark_nonlethal(decl, "Encerro a rodada: Guardar, Golpe.")
    assert all("nao_letal" not in s.params for s in decl.jogadas)


def test_wrapped_player_input_still_marks_nonlethal(monkeypatch):
    """SPEC-344: a entrada embrulhada em <entrada_do_jogador> nao quebra o 'Sem matar.'."""
    from services.death_flow import nonlethal_declared
    from services.prompt_guard import wrap_player_input

    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    text = "Encerro a rodada: Guardar, Golpe. Sem matar."
    assert nonlethal_declared(wrap_player_input(text))
    assert not nonlethal_declared(wrap_player_input("Encerrar turno: Guardar, Golpe."))
    decl = _decl()
    cbt._mark_nonlethal(decl, wrap_player_input(text))
    assert decl.jogadas[1].params["nao_letal"] is True
    # o texto legado continua valendo
    old = _decl()
    cbt._mark_nonlethal(old, "Encerrar turno: Guardar, Golpe. Sem matar.")
    assert old.jogadas[1].params["nao_letal"] is True


# --- P2-5: integracao com o no real (Baralho + 2 jogadas) -------------------------------
def _deck_state(monkeypatch, plays, intent):
    import random

    from langchain_core.messages import HumanMessage

    import api
    from services import card_piles as cp
    from tests.test_api_jogadas import GUARDA, _req, _state

    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    monkeypatch.setattr(cp, "FOLEGO_BASE", 3)
    state = _state(monkeypatch)
    state["messages"] = [HumanMessage(content=intent)]
    for e in state["enemies"]:
        e["vitalidade"] = e["hp"] = 1
        e["max_vitalidade"] = e["max_hp"] = 1
        e["esquiva"] = 0
        e["categoria"] = "lacaio"
        e["defense"] = 0
    eid = state["enemies"][0]["id"]
    steps = [
        api.PlayStepRequest(card_id=c, target_id="player" if c == GUARDA else eid) for c in plays
    ]
    api._apply_action_options(state, _req(jogadas=steps))
    random.seed(3)
    return state, eid


def test_second_card_kill_becomes_down(monkeypatch):
    from tests.test_api_jogadas import GOLPE, GUARDA

    seen = {}
    real = cbt._finish_encounter

    def spy(meta, enemies, outcome, *, loot):
        seen["enemies"] = enemies
        return real(meta, enemies, outcome, loot=loot)

    monkeypatch.setattr(cbt, "_finish_encounter", spy)
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")
    state, eid = _deck_state(
        monkeypatch, [GUARDA, GOLPE], "Encerro a rodada: Guarda, Golpe. Sem matar."
    )
    cbt._combat_node(state)
    e = next(x for x in seen["enemies"] if x["id"] == eid)
    assert e.get("incapacitated") and not e.get("dead"), e.get("status")


def test_second_card_kill_without_declaration_kills(monkeypatch):
    from tests.test_api_jogadas import GOLPE, GUARDA

    seen = {}
    real = cbt._finish_encounter

    def spy(meta, enemies, outcome, *, loot):
        seen["enemies"] = enemies
        return real(meta, enemies, outcome, loot=loot)

    monkeypatch.setattr(cbt, "_finish_encounter", spy)
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")
    state, eid = _deck_state(monkeypatch, [GUARDA, GOLPE], "Encerro a rodada: Guarda, Golpe.")
    cbt._combat_node(state)
    e = next(x for x in seen["enemies"] if x["id"] == eid)
    assert e.get("dead") and not e.get("incapacitated")
