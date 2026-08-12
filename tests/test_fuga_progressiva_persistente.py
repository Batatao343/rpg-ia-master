from agents.combat import _attempt_flee, _canonical_player_action
from services import chase
from services.conflict_turn import TurnDeclaration


class _HighRng:
    def randint(self, a, b):
        return b


def _scene():
    return {"positions": {"player": {"distance_state": "proximo"}}}


def _player():
    return {
        "name": "Valen",
        "conscious": True,
        "virtudes": {"agilidade": 5},
    }


def _enemy(enemy_id="lobo"):
    return {
        "id": enemy_id,
        "name": "Lobo",
        "pursuit_policy": "persegue",
        "virtudes": {"agilidade": 0},
    }


def test_perseguicao_compativel_pode_ser_retomada():
    existing = {
        "trilha": "afastado",
        "perseguidores": ["lobo"],
        "fugitive_id": "player",
        "alcancado": False,
        "escapou": False,
    }
    assert chase.can_resume(existing, "player", [_enemy()]) is True


def test_perseguicao_terminal_ou_com_outros_atores_nao_e_retomada():
    reached = {
        "trilha": "alcancado", "perseguidores": ["lobo"],
        "fugitive_id": "player", "alcancado": True, "escapou": False,
    }
    assert chase.can_resume(reached, "player", [_enemy()]) is False
    assert chase.can_resume({**reached, "trilha": "afastado", "alcancado": False},
                            "outro", [_enemy()]) is False
    assert chase.can_resume({**reached, "trilha": "afastado", "alcancado": False},
                            "player", [_enemy("urso")]) is False


def test_duas_tentativas_retomam_afastado_e_terminam_em_escape():
    first = {
        "trilha": "afastado",
        "perseguidores": ["lobo"],
        "fugitive_id": "player",
        "alcancado": False,
        "escapou": False,
    }
    fled, logs, progressed = _attempt_flee(
        _scene(), _player(), [_enemy()], {}, _HighRng(), existing_chase=first,
    )
    assert fled is False
    assert progressed["trilha"] == "quase_livre"
    assert "avança" in " ".join(logs).lower()

    fled, _, escaped = _attempt_flee(
        _scene(), _player(), [_enemy()], {}, _HighRng(), existing_chase=progressed,
    )
    assert fled is True
    assert escaped["trilha"] == "escapou"


def test_resultado_canonico_distingue_progresso_falha_e_escape():
    decl = TurnDeclaration(actor_id="player")
    base = dict(declaration=decl, out={}, flee_requested=True,
                flee_destination_id="costa_negra")
    progress = _canonical_player_action(
        **base, hero_fled=False,
        chase_state={"trilha": "afastado", "alcancado": False},
    )
    failed = _canonical_player_action(
        **base, hero_fled=False,
        chase_state={"trilha": "alcancado", "alcancado": True},
    )
    escaped = _canonical_player_action(
        **base, hero_fled=True,
        chase_state={"trilha": "escapou", "escapou": True},
    )
    assert progress["result"] == "flee_progress"
    assert failed["result"] == "flee_failed"
    assert escaped["result"] == "fled"
    assert progress["chase_track"] == "afastado"
