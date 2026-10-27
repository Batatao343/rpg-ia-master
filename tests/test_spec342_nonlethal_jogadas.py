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
