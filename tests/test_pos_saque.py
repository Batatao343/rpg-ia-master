"""Suíte da spec pos-saque-recuperacao — janela de recuperação após "O Saque".

Offline/determinístico. Ver specs/pos-saque-recuperacao.md.
"""
import combat_mechanics as cm
import world_utils as wu
from agents.campaign_manager import _prefix_recovery_beat, campaign_manager_node
from agents.storyteller import _recovery_clause
from playtest import invariants as inv


def _player():
    return {"name": "Kael", "class_name": "Guerreiro", "level": 2,
            "hp": 0, "max_hp": 40, "gold": 120,
            "inventory": [{"id": "espada_curta", "qty": 1}, {"id": "pao", "qty": 3}],
            "equipment": {"weapon": "espada_curta", "armor": "gibao", "accessory": None},
            "active_conditions": []}


def _world():
    return wu.ensure_world({"current_location_id": "nova_arcadia",
                            "current_location": "Nova Arcádia", "danger_level": 1})


# --- R1/R2/R4: apply_downed -------------------------------------------------

def test_apply_downed_deixa_pocao():
    player, _w, _ev, _nota = cm.apply_downed(_player(), _world())
    ids = [i.get("id") for i in player.get("inventory", [])]
    assert "pocao_cura" in ids


def test_apply_downed_seta_carencia_e_condicao():
    player, world, _ev, _nota = cm.apply_downed(_player(), _world())
    assert any(c.get("name") == "downed_recente" for c in player["active_conditions"])
    assert "downed_grace_until_day" in world
    assert wu.downed_grace_active(world) is True


def test_carencia_expira_no_dia_seguinte():
    _p, world, _e, _n = cm.apply_downed(_player(), _world())
    assert wu.downed_grace_active(world) is True
    # avança 1 dia inteiro → carência inativa
    wu.advance_clock(world, len(wu.PERIODS))
    assert wu.downed_grace_active(world) is False


def test_descanso_remove_downed_recente():
    player, world, _e, _n = cm.apply_downed(_player(), _world())
    assert any(c.get("name") == "downed_recente" for c in player["active_conditions"])
    player2, _w2 = wu.apply_rest(player, world)
    assert not any(c.get("name") == "downed_recente" for c in player2["active_conditions"])


# --- R3: beat de recuperação (campaign_manager) -----------------------------

def test_beat_de_recuperacao_prefixado():
    plan = {"beats": [{"description": "Explore a cidade", "status": "pending"}],
            "location": "Nova Arcádia"}
    out = _prefix_recovery_beat(plan, {"current_location": "Nova Arcádia"})
    assert out["beats"][0].get("recovery") is True
    assert "Recupere forças" in out["beats"][0]["description"]
    # idempotente
    out2 = _prefix_recovery_beat(out, {"current_location": "Nova Arcádia"})
    assert sum(1 for b in out2["beats"] if b.get("recovery")) == 1


def test_campaign_manager_injeta_beat_pos_downed():
    plan = {"beats": [{"description": "Siga a trilha", "status": "pending"}],
            "location": "Nova Arcádia", "current_step": 0, "last_planned_turn": 0}
    state = {
        "world": {"turn_count": 5, "current_location": "Nova Arcádia"},
        "campaign_plan": plan, "needs_replan": False,
        "player": {"active_conditions": [{"name": "downed_recente", "duration": 99}]},
    }
    out = campaign_manager_node(state)
    beats = out["campaign_plan"]["beats"]
    assert beats[0].get("recovery") is True


# --- R4: cláusula de prompt -------------------------------------------------

def test_recovery_clause_presente_com_marca():
    state = {"player": {"active_conditions": [{"name": "downed_recente"}]}}
    assert "RECUPERAÇÃO" in _recovery_clause(state)


def test_recovery_clause_ausente_sem_marca():
    assert _recovery_clause({"player": {"active_conditions": []}}) == ""


# --- R2: gate de encontro (unidade) -----------------------------------------

def test_grace_ativa_local_seguro_nao_dispara():
    world = _world()
    world["downed_grace_until_day"] = int(world["world_clock"]["day"]) + 1
    world["danger_level"] = 1
    # gate: carência ativa + seguro → sem encontro (replica a lógica do storyteller)
    assert wu.downed_grace_active(world) and int(world["danger_level"]) <= 1


def test_grace_nao_afeta_sem_campo():
    assert wu.downed_grace_active(_world()) is False


# --- R5: invariante ---------------------------------------------------------

def test_invariante_no_recovery_path_dispara():
    state = {"player": {"active_conditions": [{"name": "downed_recente"}],
                        "inventory": [{"id": "espada_curta", "qty": 1}]},
             "world": {}}
    viol = inv.check_downed_recovery(state, None, 3)
    assert viol and viol[0].check_id == "downed.no_recovery_path"
    assert viol[0].severity == "warning"


def test_invariante_no_recovery_path_ok_com_pocao():
    state = {"player": {"active_conditions": [{"name": "downed_recente"}],
                        "inventory": [{"id": "pocao_cura", "qty": 1}]},
             "world": {}}
    assert inv.check_downed_recovery(state, None, 3) == []


def test_invariante_no_recovery_path_ok_com_carencia():
    w = _world()
    w["downed_grace_until_day"] = int(w["world_clock"]["day"]) + 1
    state = {"player": {"active_conditions": [{"name": "downed_recente"}], "inventory": []},
             "world": w}
    assert inv.check_downed_recovery(state, None, 3) == []
