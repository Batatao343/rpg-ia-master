"""Regressões do smoke real: Vitalidade canônica, regiões e Última Ação."""

from __future__ import annotations

import random

from langchain_core.messages import AIMessage

import api
import combat_mechanics as cm
import gamedata
import party
import persistence
import progression
import world_utils
from services import conflict_damage as cd
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct


def _actor(actor_id: str, *, corpo: int = 3, vitalidade: int | None = None,
           is_player: bool = False, categoria: str = "chefe") -> dict:
    max_vitalidade = gamedata.vitalidade_para_corpo(corpo)
    return {
        "id": actor_id,
        "name": actor_id.title(),
        "is_player": is_player,
        "categoria": categoria,
        "virtudes": {
            "forca": 5,
            "agilidade": 3,
            "corpo": corpo,
            "mente": 2,
            "carisma": 1,
        },
        "vitalidade": max_vitalidade if vitalidade is None else vitalidade,
        "max_vitalidade": max_vitalidade,
        "hp": 999,
        "max_hp": 999,
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "ferimento_espacos": gamedata.espacos_ferimento_para_corpo(corpo),
        "active_conditions": [],
        "conscious": True,
        "status": "ativo",
        "dano_base_arma": 20,
        "esquiva": 8,
    }


def _scene(*actor_ids: str) -> dict:
    scene = {
        "zones": [{"id": "z0", "name": "Arena", "connections": []}],
        "positions": {},
        "objects": [],
    }
    for actor_id in actor_ids:
        cs.place(scene, actor_id, zone_id="z0", distance_state="proximo")
    cs.freeze(scene)
    return scene


class _HighRng:
    def randint(self, _a: int, b: int) -> int:
        return b

    def random(self) -> float:
        return 0.99


def test_sync_vitality_aplica_penalidade_permanente_e_aliases() -> None:
    actor = _actor("heroi", corpo=3, vitalidade=11, is_player=True)
    actor["vitalidade_max_penalty"] = 2

    gamedata.sync_vitality(actor)

    assert actor["max_vitalidade"] == 10
    assert actor["vitalidade"] == 10
    assert actor["hp"] == actor["vitalidade"]
    assert actor["max_hp"] == actor["max_vitalidade"]


def test_cicatriz_sobrevive_recalculo_por_corpo_e_level_up() -> None:
    actor = _actor("heroi", corpo=3, is_player=True)
    actor.update({
        "class_name": "Sangromante",
        "level": 1,
        "xp": 0,
        "entropy": 5,
        "max_entropy": 5,
        "abyss_charge": 0,
        "pending_choices": [],
    })
    classes = {
        "Sangromante": {
            "abyss": {
                "consequence": "cicatriz",
                "params": {"scar_hp_loss": 2},
            },
            "level_gains": {"hp": 99, "entropy": 0},
        },
    }

    cm.apply_scar(actor, {"peak": True}, classes_db=classes)
    actor, _events = progression.grant_xp(
        actor, progression.XP_TABLE[2], classes_db=classes)
    gamedata.sync_vitality(actor)

    assert actor["vitalidade_max_penalty"] == 2
    assert actor["max_vitalidade"] == 16  # Corpo 3 (12) + Postura 6 - cicatriz 2
    assert actor["max_hp"] == 16


def test_migracao_v4_para_v5_escolhe_vitalidade_e_normaliza_party() -> None:
    raw = {
        "schema_version": 4,
        "player": {
            "virtudes": {"corpo": 2},
            "vitalidade": 4,
            "max_vitalidade": 10,
            "hp": 30,
            "max_hp": 40,
        },
        "party": [{
            "name": "Iria",
            "virtudes": {"corpo": 1},
            "vitalidade": 3,
            "max_vitalidade": 8,
            "hp": 0,
            "max_hp": 20,
        }],
    }

    migrated = persistence.migrate_state(raw)

    assert migrated["schema_version"] == persistence.SCHEMA_VERSION
    assert migrated["player"]["hp"] == 4
    assert migrated["player"]["max_hp"] == 10
    assert migrated["party"][0]["hp"] == 3
    assert migrated["party"][0]["max_hp"] == 8


def test_save_pre_v4_permanece_arquivado_no_schema_atual() -> None:
    migrated = persistence.migrate_state({
        "schema_version": 3,
        "player": {"hp": 20, "max_hp": 20},
    })

    assert migrated["schema_version"] == persistence.SCHEMA_VERSION
    assert migrated["archived"] is True
    assert "virtudes" not in migrated["player"]


def test_critico_repetido_na_mesma_regiao_ocupa_proximo_espaco_sem_overflow() -> None:
    target = _actor("alvo", corpo=3)
    original = {"categoria": "critico", "regiao": "torso", "suprimida": False}
    target["ferimentos"]["critico"].append(original)

    segundo = cd.apply_wound(target, "critico", "torso")
    terceiro = cd.apply_wound(target, "critico", "torso")

    assert target["ferimentos"]["critico"][0] is original
    assert segundo["aplicado"] is True
    assert terceiro["aplicado"] is False
    assert len(target["ferimentos"]["critico"]) == 2


def test_regiao_nao_direcionada_e_reprodutivel_por_rng() -> None:
    a = _actor("a", corpo=0, vitalidade=1)
    b = _actor("b", corpo=0, vitalidade=1)

    ra = cd.resolve_damage_and_wounds(
        a, damage_base=4, directed_region=None, rng=random.Random(123))
    rb = cd.resolve_damage_and_wounds(
        b, damage_base=4, directed_region=None, rng=random.Random(123))

    assert ra["regiao"] == rb["regiao"]
    assert cd.is_valid_hit_region(a, ra["regiao"])
    assert ra["wound"]["regiao"] == ra["regiao"]


def test_ataque_direcionado_valida_regiao_e_aplica_penalidade(monkeypatch) -> None:
    attacker = _actor("a")
    target = _actor("b")
    captured: dict = {}

    def fake_attack(_actor, _target, **kwargs):
        captured["advantage"] = kwargs["advantage"]
        return {
            "resultado": "falha",
            "total": 1,
            "esquiva_alvo": 99,
            "acerto": False,
            "efeito_principal_multiplicador": 1,
        }

    monkeypatch.setattr(ct, "resolve_attack", fake_attack)
    out = ct.resolve_turn(
        _scene("a", "b"),
        {"a": attacker, "b": target},
        {
            "actor_id": "a",
            "acao": {
                "kind": "attack",
                "target_id": "b",
                "params": {"regiao": "cabeca"},
            },
        },
        rng=_HighRng(),
    )

    assert out["attacks"]
    assert captured["advantage"] == -1


def test_ultima_acao_resolve_exatamente_uma_vez_antes_do_terminal() -> None:
    hero = _actor("player", corpo=3, is_player=True)
    boss = _actor("boss", corpo=1, vitalidade=0, categoria="chefe")
    boss["ferimentos"]["critico"] = []
    boss["dano_base_arma"] = 3
    scene = _scene("player", "boss")
    declaration = ct.TurnDeclaration(
        actor_id="player",
        acao=ct.TurnStep(
            kind="attack",
            target_id="boss",
            params={"dano_base": 20},
        ),
    )
    hero_before = hero["vitalidade"]

    out = orch.run_round(
        scene,
        {"player": hero, "boss": boss},
        {"hero": ["player"], "ally": [], "enemy": ["boss"]},
        declarations={"player": declaration},
        initiator="heroes",
        rng=_HighRng(),
    )

    assert boss["_last_stand_count"] == 1
    assert boss["last_stand_resolved"] is True
    # Sem aliado, a estabilização já conclui o Estado Terminal em morte.
    assert boss["estado_terminal"] is False
    assert boss["dead"] is True
    assert hero["vitalidade"] < hero_before
    assert out["last_stands"] == ["boss"]

    orch.run_round(
        scene,
        {"player": hero, "boss": boss},
        {"hero": ["player"], "ally": [], "enemy": ["boss"]},
        declarations={"player": declaration},
        initiator="heroes",
        rng=_HighRng(),
    )
    assert boss["_last_stand_count"] == 1


def test_descanso_e_party_usam_vitalidade_nao_hp() -> None:
    player = _actor("player", corpo=2, vitalidade=0, is_player=True)
    rested, _world = world_utils.apply_rest(
        player,
        {
            "current_location_id": "x",
            "world_clock": {"day": 1, "period": "Manhã"},
        },
    )
    ally = _actor("ally", corpo=1, vitalidade=2)
    ally.update({"active": True, "status": "ativo", "hp": 0})

    assert rested["vitalidade"] > 0
    assert rested["hp"] == rested["vitalidade"]
    assert party.active_allies({"party": [ally]}) == [ally]


def test_descanso_longo_acorda_mas_preserva_critico_sem_medico_e_kit() -> None:
    player = _actor("player", corpo=2, vitalidade=0, is_player=True)
    player["conscious"] = False
    player["post_combat_state"] = "inconsciente"
    player["ferimentos"]["critico"] = [
        {"categoria": "critico", "regiao": "torso", "aplicado": True}
    ]

    rested, _world = world_utils.apply_rest(
        player,
        {"current_location_id": "x", "world_clock": {"day": 1, "period": "Manhã"}},
    )

    assert len(rested["ferimentos"]["critico"]) == 1
    assert rested["post_combat_state"] == "tratavel"
    assert rested["conscious"] is True


def test_api_expoe_alias_hp_derivado_e_game_over_canonico() -> None:
    player = _actor("player", corpo=2, vitalidade=4, is_player=True)
    state = {
        "game_id": "g",
        "messages": [AIMessage(content="Tudo quieto.")],
        "player": player,
        "world": {"current_location": "Arena"},
        "game_over": True,
        "death_pending": False,
    }

    response = api.format_response(state)

    assert response.player_stats["vitalidade"] == 4
    assert response.player_stats["hp"] == 4
    assert response.game_over is True
