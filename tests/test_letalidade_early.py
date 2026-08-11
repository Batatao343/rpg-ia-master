"""Contratos da spec letalidade-early-game-v2 após o cutover v4."""
import random

import combat_mechanics as cm
import agents.combat as combat
from gamedata import CLASSES
from playtest.profiles import PROFILES
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
import world_utils as wu


def test_descanso_early_game_seguro_e_apex_preservado():
    assert wu.recovery_rest_safe(3, 3, {"tags": ["cidade"]})
    assert not wu.recovery_rest_safe(3, 3, {"tags": ["apex"]})
    assert not wu.recovery_rest_safe(3, 4, {"tags": []})
    assert not wu.recovery_rest_safe(4, 2, {"tags": []})


def test_cooldown_encontro_maior_no_early_game(monkeypatch):
    monkeypatch.setattr(wu, "_effective_danger", lambda *_: 4)
    monkeypatch.setattr(wu.gamedata, "get_location", lambda *_: {
        "id": "ermo", "name": "Ermo", "region": "Ermo", "tags": []})
    world = {"current_location_id": "ermo", "current_location": "Ermo",
             "danger_level": 4, "last_encounter_turn": 7}
    assert wu.check_encounter(dict(world), [], {}, turn=10, player_level=2) is None
    assert wu.check_encounter(dict(world), [], {}, turn=10, player_level=4) is not None


def test_early_damage_bonus_faixas():
    assert [cm.early_game_damage_bonus(level) for level in range(1, 6)] == [2, 2, 1, 0, 0]


def _actor(actor_id: str, *, player=False, level=1):
    return orch.ensure_combat_sheet({
        "id": actor_id, "name": actor_id, "is_player": player, "level": level,
        "vitalidade": 30, "max_vitalidade": 30,
        "virtudes": {"forca": 5, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        "dano_base_arma": 3, "active_conditions": [],
    }, is_player=player)


def test_bonus_entra_no_dano_v4_so_para_jogador(monkeypatch):
    monkeypatch.setattr(ct, "resolve_attack", lambda *a, **k: {
        "acerto": True, "resultado": "acerto", "total": 20,
        "esquiva_alvo": 10, "efeito_principal_multiplicador": 1})
    scene = cs.new_scene()
    cs.place(scene, "player")
    cs.place(scene, "enemy")
    player, enemy = _actor("player", player=True), _actor("enemy")
    player_out = ct.resolve_turn(
        scene, {"player": player, "enemy": enemy},
        ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(
            kind="attack", target_id="enemy")), rng=random.Random(1))
    assert player_out["attacks"][0]["dano_final"] == 5

    player2, enemy2 = _actor("player", player=True), _actor("enemy")
    enemy_out = ct.resolve_turn(
        scene, {"player": player2, "enemy": enemy2},
        ct.TurnDeclaration(actor_id="enemy", acao=ct.TurnStep(
            kind="attack", target_id="player")), rng=random.Random(1))
    assert enemy_out["attacks"][0]["dano_final"] == 3


def test_pisos_de_hp_e_pocoes_iniciais():
    expected = {"Devoto do Abismo": (18, 2), "Sangromante": (18, 2),
                "Corruptor": (18, 2), "Arcanista Cinzento": (14, 2),
                "Médico de Campo": (16, 3)}
    for name, (vitality, potions) in expected.items():
        data = CLASSES[name]
        assert data["base_stats"]["vitalidade_bonus"] == 6
        assert data["starting_equipment"].count("pocao_cura") >= potions
        actor = {"class_name": name, "virtudes": data["base_stats"]["virtudes"]}
        wu.gamedata.sync_vitality(actor, heal_to_full=True)
        assert actor["max_vitalidade"] == vitality


def test_perfil_razoavel_descansa_abaixo_de_metade():
    state = {"player": {"vitalidade": 10, "max_vitalidade": 30,
                        "conscious": True}, "combat": None, "enemies": []}
    decision = PROFILES["combate"].decide(state, random.Random(1))
    assert "descanso" in decision.text.casefold()


def test_perfil_razoavel_sai_do_perigo_para_descansar(monkeypatch):
    monkeypatch.setattr("playtest.profiles._connections", lambda _loc: [
        {"id": "seguro", "name": "Refúgio", "danger": 2},
        {"id": "pior", "name": "Abismo", "danger": 5},
    ])
    state = {"player": {"vitalidade": 4, "max_vitalidade": 16,
                        "conscious": True}, "combat": None, "enemies": [],
             "world": {"current_location_id": "perigo", "danger_level": 4}}
    decision = PROFILES["combate"].decide(state, random.Random(1))
    assert "Viajo para Refúgio" in decision.text


def test_perfil_razoavel_evacuacao_aceita_primeiro_passo_de_mesmo_perigo(monkeypatch):
    monkeypatch.setattr("playtest.profiles._connections", lambda _loc: [
        {"id": "saida", "name": "Galeria de Saída", "danger": 4},
    ])
    state = {"player": {"vitalidade": 3, "max_vitalidade": 18,
                        "conscious": True}, "combat": None, "enemies": [],
             "world": {"current_location_id": "cripta", "danger_level": 4}}
    decision = PROFILES["combate"].decide(state, random.Random(1))
    assert "Viajo para Galeria de Saída" in decision.text


def test_perfil_razoavel_cura_em_combate_abaixo_de_metade():
    state = {
        "player": {
            "name": "Sangromante", "vitalidade": 8, "max_vitalidade": 18,
            "conscious": True,
            "inventory": [{"id": "pocao_cura", "qty": 1}],
            "prepared_cards": [],
        },
        "combat": {"active": True},
        "enemies": [{"id": "inimigo", "name": "Inimigo", "status": "ativo"}],
    }
    decision = PROFILES["combate"].decide(state, random.Random(1))
    assert decision.mode == "declaration"
    assert decision.declaration["acao"]["kind"] == "item"
    assert decision.declaration["acao"]["item_id"] == "pocao_cura"


def test_save_v5_recebe_bonus_sem_apagar_dano():
    from persistence import _normalize_vitality_actor
    old = {"class_name": "Devoto do Abismo", "virtudes": {"corpo": 3},
           "vitalidade": 6, "max_vitalidade": 12}
    migrated = _normalize_vitality_actor(old)
    assert migrated["max_vitalidade"] == 18
    assert migrated["vitalidade"] == 12
    assert migrated["hp"] == 12 and migrated["max_hp"] == 18


def test_heroi_cheio_early_game_reage_antes_da_emboscada(monkeypatch):
    monkeypatch.setattr(combat.gamedata, "get_location", lambda *_: {
        "id": "ermo", "tags": ["ermo"]})
    state = {"combat": {"round": 1}, "world": {"current_location_id": "ermo"}}
    player = {"level": 2, "vitalidade": 14, "max_vitalidade": 14}
    assert combat._early_game_reaction_initiator(state, player, "enemy") == "heroes"


def test_protecao_de_reacao_nao_altera_apex_ferido_ou_nivel_alto(monkeypatch):
    state = {"combat": {"round": 1}, "world": {"current_location_id": "zona"}}
    monkeypatch.setattr(combat.gamedata, "get_location", lambda *_: {
        "id": "zona", "tags": ["apex"]})
    full = {"level": 2, "vitalidade": 14, "max_vitalidade": 14}
    assert combat._early_game_reaction_initiator(state, full, "enemy") == "enemy"

    monkeypatch.setattr(combat.gamedata, "get_location", lambda *_: {
        "id": "zona", "tags": []})
    assert combat._early_game_reaction_initiator(
        state, {**full, "vitalidade": 13}, "enemy") == "enemy"
    assert combat._early_game_reaction_initiator(
        state, {**full, "level": 3}, "enemy") == "enemy"


def test_queda_deliberada_ainda_pode_virar_memorial():
    from services import checkpoints
    dead = {"death_pending": True, "game_over": False, "player": {
        "vitalidade": 0, "max_vitalidade": 18}}
    memorial = checkpoints.resolve_death_choice(dead, "accept")
    assert memorial["game_over"] is True
    assert memorial["death_pending"] is False
