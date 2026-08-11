"""Regressões da execução mecânica dos arquétipos táticos fechados."""

import random

import pytest

from agents import bestiary
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
from services import encounter_preparation as prep
from services import tactical_profile as tp


def _actor(actor_id: str, archetype: str, *, category: str = "companheiro",
           agility: int = 2, body: int = 3, **over) -> dict:
    actor = prep.build_npc_combat_sheet({
        "id": actor_id,
        "name": actor_id,
        "role": "Pessoa",
        "persona": "",
        "categoria": category,
        "virtudes": {
            "forca": 2,
            "agilidade": agility,
            "corpo": body,
            "mente": 3,
            "carisma": 2,
        },
        "tactical_archetype": archetype,
    })
    actor.update(over)
    return orch.ensure_combat_sheet(actor)


def _player(**over) -> dict:
    player = _actor(
        "player", "equilibrado", category="companheiro", agility=2, body=4,
        is_player=True, class_name="Sangromante",
    )
    player.update(over)
    return orch.ensure_combat_sheet(player, is_player=True)


def _scene(*actor_ids: str) -> dict:
    scene = cs.new_scene()
    for actor_id in actor_ids:
        cs.place(scene, actor_id)
    cs.freeze(scene)
    return scene


def _pass(actor_id: str) -> ct.TurnDeclaration:
    return ct.TurnDeclaration(
        actor_id=actor_id,
        acao=ct.TurnStep(kind="pass"),
    )


def _attack(actor_id: str, target_id: str) -> ct.TurnDeclaration:
    return ct.TurnDeclaration(
        actor_id=actor_id,
        acao=ct.TurnStep(kind="attack", target_id=target_id),
    )


def _tactics(out: dict, actor_id: str, action_key: str) -> list[dict]:
    return [
        item for item in out.get("tactics", [])
        if item.get("actor_id") == actor_id and item.get("action_key") == action_key
    ]


def test_guardiao_protege_aliado_em_perigo_e_modificador_e_consumido():
    player = _player()
    guard = _actor("guard", "guardiao", agility=4)
    ward = _actor("ward", "combatente", agility=1, vitalidade=2)
    foe = _actor("foe", "combatente", category="padrao")
    scene = _scene("player", "guard", "ward", "foe")
    actors = {"player": player, "guard": guard, "ward": ward, "foe": foe}
    sides = {"hero": ["player"], "ally": ["guard", "ward"], "enemy": ["foe"]}

    out = orch.run_round(
        scene, actors, sides,
        declarations={
            "player": _pass("player"),
            "ward": _pass("ward"),
            "foe": _attack("foe", "ward"),
        },
        initiator="heroes",
        rng=random.Random(11),
    )

    assert _tactics(out, "guard", "protect")
    attack = next(a for a in out["attacks"] if a["actor_id"] == "foe")
    assert attack["target_id"] == "ward"
    assert attack["advantage"] == -1
    assert cs.has_tactical_modifier(scene, "protected", "ward") is False


def test_guardiao_nao_aceita_gatilho_externo_sem_aliado_canonico():
    player = _player()
    guard = _actor("guard", "guardiao", category="padrao")
    scene = _scene("player", "guard")
    declaration = orch.enemy_declaration(
        scene,
        "guard",
        {"player": player, "guard": guard},
        {"hero": ["player"], "enemy": ["guard"]},
        scene_state={"aliado_em_perigo": True, "_ally_danger_target": "inventado"},
        rng=random.Random(1),
    )

    assert declaration.acao.kind in ("attack", "card")
    assert declaration.acao.target_id == "player"


def test_suporte_estabiliza_aliado_terminal_com_acao_propria():
    player = _player()
    medic = _actor("medic", "suporte", agility=4, has_kit=True)
    ward = _actor(
        "ward", "combatente", agility=1,
        estado_terminal=True, vitalidade=0,
    )
    foe = _actor("foe", "combatente", category="padrao")
    scene = _scene("player", "medic", "ward", "foe")
    actors = {"player": player, "medic": medic, "ward": ward, "foe": foe}
    sides = {"hero": ["player"], "ally": ["medic", "ward"], "enemy": ["foe"]}

    out = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player"), "foe": _pass("foe")},
        initiator="heroes",
        rng=random.Random(7),
    )

    action = _tactics(out, "medic", "stabilize")
    assert action and action[0]["target_id"] == "ward"
    assert action[0]["ok"] is True
    assert ward["estado_terminal"] is False
    assert ward["vitalidade"] > 0
    assert not any(a["actor_id"] == "medic" for a in out["attacks"])


def test_batedor_flanqueia_e_so_no_turno_seguinte_ataca_com_vantagem():
    player = _player()
    scout = _actor("scout", "batedor", category="padrao", agility=4)
    scene = _scene("player", "scout")
    actors = {"player": player, "scout": scout}
    sides = {"hero": ["player"], "enemy": ["scout"]}

    first = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(3),
    )
    assert _tactics(first, "scout", "flank")
    assert not any(a["actor_id"] == "scout" for a in first["attacks"])
    assert cs.is_hidden_from(scene, "scout", "player")

    second = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(4),
    )
    attack = next(a for a in second["attacks"] if a["actor_id"] == "scout")
    assert attack["advantage"] == 1
    assert cs.is_hidden_from(scene, "scout", "player") is False


def test_mistico_controla_um_turno_e_respeita_cooldown_fechado():
    player = _player()
    mystic = _actor("mystic", "mistico", category="padrao", agility=4)
    scene = _scene("player", "mystic")
    actors = {"player": player, "mystic": mystic}
    sides = {"hero": ["player"], "enemy": ["mystic"]}

    first = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(5),
    )
    assert _tactics(first, "mystic", "control")
    assert any(c.get("control") == "stun" for c in player["active_conditions"])
    assert "player" not in first["resolved_turns"]

    second = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(6),
    )
    assert not _tactics(second, "mystic", "control")
    assert any(a["actor_id"] == "mystic" for a in second["attacks"])
    assert cs.tactical_cooldown(scene, "mystic", "control") == 1


def test_estrategista_apoia_combatente_e_vantagem_nao_empilha():
    player = _player()
    strategist = _actor("strategist", "estrategista", category="padrao", agility=4)
    fighter = _actor("fighter", "combatente", category="padrao", agility=1)
    scene = _scene("player", "strategist", "fighter")
    actors = {"player": player, "strategist": strategist, "fighter": fighter}
    sides = {"hero": ["player"], "enemy": ["strategist", "fighter"]}

    out = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(8),
    )

    action = _tactics(out, "strategist", "support")
    assert action and action[0]["target_id"] == "fighter"
    fighter_attack = next(a for a in out["attacks"] if a["actor_id"] == "fighter")
    assert fighter_attack["advantage"] == 1
    assert cs.has_tactical_modifier(scene, "attack_advantage", "fighter") is False
    assert not any(a["actor_id"] == "strategist" for a in out["attacks"])


def test_oportunista_com_vitalidade_baixa_recua_sem_atacar():
    player = _player()
    coward = _actor(
        "coward", "oportunista", category="padrao",
        vitalidade=2, max_vitalidade=12,
    )
    scene = _scene("player", "coward")
    actors = {"player": player, "coward": coward}
    sides = {"hero": ["player"], "enemy": ["coward"]}

    out = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(9),
    )

    assert _tactics(out, "coward", "flee")
    assert scene["positions"]["coward"]["distance_state"] == "distante"
    assert not any(a["actor_id"] == "coward" for a in out["attacks"])

    escaped = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(10),
    )
    assert coward["fled"] is True
    assert coward["status"] == "fugiu"
    assert escaped["ended"] is True


def test_combatente_continua_usando_ataque_mecanico():
    player = _player()
    fighter = _actor("fighter", "combatente", category="padrao")
    scene = _scene("player", "fighter")
    actors = {"player": player, "fighter": fighter}
    sides = {"hero": ["player"], "enemy": ["fighter"]}

    out = orch.run_round(
        scene, actors, sides,
        declarations={"player": _pass("player")},
        initiator="enemy",
        rng=random.Random(10),
    )

    assert any(a["actor_id"] == "fighter" for a in out["attacks"])
    assert not _tactics(out, "fighter", "support")


@pytest.mark.parametrize(
    ("archetype", "trigger", "action_key"),
    [
        ("bruto", "muito_ferido", "flee"),
        ("conjurador", "sempre", "control"),
        ("covarde_oportunista", "sozinho", "surrender"),
        ("emboscador", "descoberto", "flank"),
        ("guardiao", "sempre", "attack"),
        ("lider_matilha", "alvo_vulneravel", "support"),
        ("morto_vivo_implacavel", "sempre", "attack"),
        ("predador", "muito_ferido", "flee"),
        ("predador_apice", "plano_falhou", "flee"),
        ("tatico", "cercado", "flee"),
    ],
)
def test_perfis_curados_recebem_action_key_por_tabela_fechada(
        archetype, trigger, action_key):
    actor = orch.ensure_combat_sheet({
        "id": archetype,
        "name": archetype,
        "arquetipo": archetype,
        "tactical_profile": {"priorities": [{
            "trigger": trigger,
            # Texto contraditório não pode dirigir a mecânica.
            "action_hint": "Inventa uma ação divina sem limite.",
            "tipo": "obrigatorio",
        }]},
        "virtudes": {
            "forca": 2, "agilidade": 2, "corpo": 2, "mente": 2, "carisma": 1,
        },
    })

    assert actor["tactical_profile"]["priorities"][0]["action_key"] == action_key


def test_gatilhos_curados_sao_derivados_apenas_do_estado_canonico():
    player = _player(vitalidade=2)
    ally = _actor("hero_ally", "combatente")
    hunter = _actor(
        "hunter", "combatente", category="padrao",
        vitalidade=2, max_vitalidade=12,
    )
    dead_a = _actor("dead_a", "combatente", category="padrao", dead=True)
    dead_b = _actor("dead_b", "combatente", category="padrao", dead=True)
    scene = _scene("player", "hero_ally", "hunter", "dead_a", "dead_b")
    cs.engage(scene, "hunter", "player", spend=False)
    cs.engage(scene, "hunter", "hero_ally", spend=False)
    actors = {
        "player": player,
        "hero_ally": ally,
        "hunter": hunter,
        "dead_a": dead_a,
        "dead_b": dead_b,
    }
    sides = {
        "hero": ["player"],
        "ally": ["hero_ally"],
        "enemy": ["hunter", "dead_a", "dead_b"],
    }

    derived = orch.derive_tactical_scene_state(
        scene, "hunter", actors, sides)

    for trigger in (
        "sozinho", "muito_ferido", "alvo_vulneravel", "cercado",
        "matilha_quebrada", "descoberto", "plano_falhou",
    ):
        assert derived[trigger] is True
    assert derived["_vulnerable_enemy_target"] == "player"


def test_conjurador_curado_controla_sem_ler_action_hint():
    player = _player()
    caster = orch.ensure_combat_sheet({
        **_actor("caster", "combatente", category="padrao", agility=4),
        "arquetipo": "conjurador",
        "tactical_profile": {"priorities": [{
            "trigger": "sempre",
            "action_hint": "Texto ornamental sem verbo mecânico.",
            "tipo": "obrigatorio",
        }]},
    })
    scene = _scene("player", "caster")
    declaration = orch.enemy_declaration(
        scene,
        "caster",
        {"player": player, "caster": caster},
        {"hero": ["player"], "enemy": ["caster"]},
    )

    assert declaration.acao.kind == "tactic"
    assert declaration.acao.maneuver == "control"


def test_covarde_curado_sozinho_rende_por_trigger_canonico():
    player = _player()
    coward = orch.ensure_combat_sheet({
        **_actor("coward", "combatente", category="padrao"),
        "arquetipo": "covarde_oportunista",
        "tactical_profile": {"priorities": [{
            "trigger": "sozinho",
            "action_hint": "Texto sem semântica mecânica.",
            "tipo": "obrigatorio",
        }]},
    })
    scene = _scene("player", "coward")
    declaration = orch.enemy_declaration(
        scene,
        "coward",
        {"player": player, "coward": coward},
        {"hero": ["player"], "enemy": ["coward"]},
    )

    assert coward["surrendered"] is True
    assert declaration.acao.kind == "pass"


class _MinimumRng:
    def randint(self, lower: int, _upper: int) -> int:
        return lower


def test_estabilizacao_tatica_nao_duplica_tentativa_automatica_no_round():
    medic = _actor("medic", "suporte")
    ward = _actor(
        "ward", "combatente",
        estado_terminal=True,
        vitalidade=0,
        stabilization_attempts=0,
    )
    scene = _scene("medic", "ward")
    actors = {"medic": medic, "ward": ward}
    sides = {"ally": ["medic", "ward"], "enemy": []}
    out = {
        "logs": [],
        "deaths": [],
        "terminal": ["ward"],
        "tactics": [],
    }

    orch._resolve_tactical_action(
        scene,
        medic,
        "medic",
        actors,
        sides,
        ct.TurnStep(kind="tactic", maneuver="stabilize", target_id="ward"),
        out,
        _MinimumRng(),
    )
    assert ward["stabilization_attempts"] == 1
    assert ward["estado_terminal"] is True

    orch.resolve_terminals(
        actors,
        sides,
        out,
        scene=scene,
        rng=_MinimumRng(),
    )

    assert ward["stabilization_attempts"] == 1
    assert ward["estado_terminal"] is True
    assert ward.get("dead") is not True


def test_todo_bestiario_curado_normaliza_para_action_keys_fechadas():
    curated = bestiary._read_json(bestiary.BESTIARY_FILE)

    assert curated
    # conflito-17 é aditiva: preserva as 84 migradas e acrescenta o lote vivo.
    assert len(curated) >= 120
    assert {
        str(entry.get("arquetipo") or "")
        for entry in curated.values()
    } <= tp.ENEMY_TACTICAL_ARCHETYPES

    for enemy_id, raw in curated.items():
        actor = orch.ensure_combat_sheet(dict(raw))
        priorities = actor["tactical_profile"]["priorities"]
        assert priorities, enemy_id
        assert all(
            priority.get("action_key") in tp.TACTICAL_ACTION_KEYS
            for priority in priorities
        ), enemy_id


def test_estado_terminal_falha_uma_vez_e_tenta_de_novo_na_rodada_seguinte():
    helper = _actor("helper", "suporte")
    ward = _actor(
        "ward", "combatente", estado_terminal=True, vitalidade=0,
        stabilization_attempts=0,
    )
    actors = {"helper": helper, "ward": ward}
    sides = {"ally": ["helper", "ward"], "enemy": []}
    scene = _scene("helper", "ward")

    first = {"logs": [], "deaths": [], "terminal": ["ward"], "tactics": []}
    orch.resolve_terminals(actors, sides, first, scene=scene, rng=_MinimumRng())
    assert ward["stabilization_attempts"] == 1
    assert ward["estado_terminal"] is True

    second = {"logs": [], "deaths": [], "terminal": [], "tactics": []}
    cs.advance_tactical_state(scene)
    orch.resolve_terminals(actors, sides, second, scene=scene, rng=_MinimumRng())
    assert ward["stabilization_attempts"] == 2
    assert ward["dead"] is True
    assert second["deaths"] == ["ward"]


def test_sobrevivente_do_last_stand_so_morre_ao_receber_novo_dano():
    survivor = _player(
        last_stand_resolved=True,
        ferimentos={
            "leve": [], "grave": [],
            "critico": [{"regiao": "torso"}, {"regiao": "cabeca"}],
        },
        ferimento_espacos={"leve": 3, "grave": 3, "critico": 2},
    )
    passive = {"logs": [], "deaths": [], "terminal": []}
    orch._check_terminal(survivor, "player", passive, damage_applied=False)
    assert survivor.get("dead") is not True

    damaged = {"logs": [], "deaths": [], "terminal": []}
    orch._check_terminal(survivor, "player", damaged, damage_applied=True)
    assert survivor["dead"] is True
    assert damaged["deaths"] == ["player"]


def test_cartas_inimigas_usam_catalogo_e_economia_propria_com_reacao_uma_vez():
    player = _player(vitalidade=30, max_vitalidade=30)
    enemy = _actor(
        "predator", "predador", category="padrao",
        vitalidade=30, max_vitalidade=30,
    )
    enemy["cartas"] = ["bst_bote_certeiro", "bst_defesa_instintiva"]
    enemy["entropy"] = 4
    scene = _scene("player", "predator")
    actors = {"player": player, "predator": enemy}
    sides = {"hero": ["player"], "enemy": ["predator"]}
    player_prepared = list(player.get("prepared_cards") or [])

    first = orch.run_round(
        scene, actors, sides,
        declarations={"player": _attack("player", "predator")},
        initiator="heroes", rng=random.Random(21),
    )
    assert [item["card_id"] for item in first["reactions"]] == [
        "bst_defesa_instintiva"
    ]
    assert enemy["enemy_card_usage"]["bst_defesa_instintiva"][
        "used_this_scene"
    ] == 1
    assert player.get("prepared_cards", []) == player_prepared

    second = orch.run_round(
        scene, actors, sides,
        declarations={"player": _attack("player", "predator")},
        initiator="heroes", rng=random.Random(22),
    )
    assert second["reactions"] == []
    assert enemy["enemy_card_usage"]["bst_bote_certeiro"][
        "used_this_scene"
    ] == 1
