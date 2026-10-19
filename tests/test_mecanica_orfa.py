"""SPEC-232 R4 — anti-órfão v2: mecânica declarada nos dados precisa de EFEITO.

O anti-órfão v1 (`combat_mechanics.HANDLED_KINDS`) só comparava NOMES: um `kind`
listado no registro passava mesmo sem consumidor no motor (foi assim que as
passivas de árvore, Cartas de Virtude, efeitos de Reação e buffs tipados ficaram
inertes após o cutover). Aqui cada chave inventariada nos dados (`data/cards/`,
`data/classes.json`, `data/artifacts.json`, `data/traits.json`) precisa de um
teste em `EFFECT_TESTS` que muda uma rolagem ou um estado com seed fixo.

`KNOWN_GAPS` só aceita chaves FORA do combate, com justificativa — qualquer
outra chave sem teste derruba a suíte.
"""

import json
import os
import random
from typing import Dict, Set
from collections.abc import Callable

import pytest

import combat_mechanics as cm
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct


# ==========================================================================
# Inventário
# ==========================================================================
def _card_effects(card: dict):
    yield card.get("efeito") or {}
    for path in ("caminho_a", "caminho_b"):
        yield (card.get("ruptura") or {}).get(path) or {}
        evo = (card.get("evolucao") or {}).get(path) or {}
        yield evo.get("efeito") or {}
        yield evo.get("ruptura") or {}


def inventory() -> dict[str, set[str]]:
    """{chave: {origens}} de tudo que os dados declaram como mecânica."""
    from gamedata import ARTIFACTS_DB, CLASSES
    from services.cards import all_cards

    found: dict[str, set[str]] = {}

    def add(key: str, origin: str) -> None:
        found.setdefault(key, set()).add(origin)

    for cid, card in all_cards().items():
        tipo = card.get("tipo")
        for eff in _card_effects(card):
            if not eff or not eff.get("kind"):
                continue
            add(f"card:{tipo}:{eff['kind']}", cid)
            if eff["kind"] == "aplicar_condicao":
                add(f"condicao:{eff.get('condicao') or card.get('name')}", cid)
        if tipo == "reacao":
            add(f"gatilho:{card.get('gatilho') or 'sempre'}", cid)

    for cname, cdata in CLASSES.items():
        for block in ("entropy_trigger", "special_rule"):
            kind = (cdata.get(block) or {}).get("kind")
            if kind:
                add(f"class.{block}:{kind}", cname)
        consequence = (cdata.get("abyss") or {}).get("consequence")
        if consequence:
            add(f"class.consequence:{consequence}", cname)
        for pe in cdata.get("passive_effects") or []:
            add(f"class.passive:{pe.get('trigger')}", cname)
        for bname, bdata in (cdata.get("branches") or {}).items():
            for block, ov in ((bdata or {}).get("overrides") or {}).items():
                if isinstance(ov, dict) and ov.get("kind"):
                    add(f"class.{block}:{ov['kind']}", f"{cname}/{bname}")

    for iid, item in ARTIFACTS_DB.items():
        mech = item.get("mechanics") or {}
        for eff in mech.get("effects") or []:
            if isinstance(eff, dict):
                sub = eff.get("stat") or eff.get("control") or ""
                add(f"item.effect:{eff.get('kind')}:{sub}", iid)
        for pe in mech.get("passive_effects") or []:
            if isinstance(pe, dict):
                add(f"item.passive:{pe.get('trigger')}", iid)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "data", "traits.json"), encoding="utf-8") as fh:
        traits = json.load(fh).get("traits") or []
    for trait in traits:
        for ctx in trait.get("dc_modifiers") or {}:
            add(f"trait.dc:{ctx}", trait.get("id", "?"))
    return found


# ==========================================================================
# Fixtures determinísticas
# ==========================================================================
_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}


def _actor(aid: str, **kw) -> dict:
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _scene(*ids) -> dict:
    scene = cs.new_scene()
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    return scene


def _card_with(tipo: str, kind: str) -> dict:
    from services.cards import all_cards

    for card in all_cards().values():
        if card.get("tipo") == tipo and (card.get("efeito") or {}).get("kind") == kind:
            return card
    raise AssertionError(f"sem Carta {tipo}/{kind}")


def _play_active(kind: str, target: str, *, prep=None):
    card = _card_with("ativa", kind)
    player = _actor(
        "player",
        class_name=card.get("classe") or "Devoto do Abismo",
        known_cards=[card["id"]],
        prepared_cards=[card["id"]],
        entropy=99,
        max_entropy=99,
        level=20,
    )
    cm.apply_condition(
        player, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
    )
    enemy = _actor("e")
    ally = _actor("ally", categoria="companheiro", transient=True)
    scene = _scene("player", "e", "ally")
    if prep:
        prep(player, enemy, ally, scene)
    actors = {"player": player, "e": enemy, "ally": ally}
    out = ct.resolve_turn(
        scene,
        actors,
        ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="card", card_id=card["id"], target_id=target)
        ),
        state={"player": player},
        sides={"hero": ["player", "ally"], "enemy": ["e"]},
        rng=random.Random(3),
    )
    return player, enemy, ally, scene, out


def _mods_delta(stat: str, mutate: Callable[[dict], None], *, is_player=True) -> int:
    actor = _actor("player" if is_player else "e")
    before = cm.combat_modifiers(actor)[stat]
    mutate(actor)
    return cm.combat_modifiers(actor)[stat] - before


def _damage_sample(attacker: dict, n: int = 40, seed: int = 9) -> int:
    target = _actor("e")
    scene = {"zones": [{"id": "z0", "name": "z", "connections": []}], "positions": {}}
    rng = random.Random(seed)
    total = 0
    for _ in range(n):
        target["vitalidade"] = target["max_vitalidade"]
        target["ferimentos"] = {"leve": [], "grave": [], "critico": []}
        out = ct.resolve_turn(
            scene,
            {"player": attacker, "e": target},
            ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="attack", target_id="e")),
            rng=rng,
        )
        total += sum(int(a.get("dano_final", 0) or 0) for a in out["attacks"])
    return total


# ==========================================================================
# Consumidores por stat (passivas estáticas)
# ==========================================================================
def _stat_consumer_changes(stat: str, add: Callable[[dict], None]) -> None:
    base = _actor("player")
    buffed = _actor("player")
    add(buffed)
    if stat == "damage":
        assert _damage_sample(buffed) > _damage_sample(base)
    elif stat == "ac":
        from services.conflict_resolution import compute_esquiva

        assert compute_esquiva(buffed) > compute_esquiva(base)
    elif stat == "initiative":
        from services.conflict_resolution import _initiative_value

        assert _initiative_value(buffed) > _initiative_value(base)
    elif stat == "dot":

        def dot_with(actor):
            card = _card_with("ativa", "dot")
            actor.update(
                known_cards=list(actor.get("known_cards") or []) + [card["id"]],
                prepared_cards=[card["id"]],
                entropy=99,
                max_entropy=99,
            )
            cm.apply_condition(
                actor, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
            )
            enemy = _actor("e")
            ct.resolve_turn(
                _scene("player", "e"),
                {"player": actor, "e": enemy},
                ct.TurnDeclaration(
                    actor_id="player",
                    acao=ct.TurnStep(kind="card", card_id=card["id"], target_id="e"),
                ),
                state={"player": actor},
                rng=random.Random(2),
            )
            return max(int(c.get("dot", 0) or 0) for c in enemy["active_conditions"])

        assert dot_with(buffed) > dot_with(base)
    elif stat == "heal":

        def healed(actor):
            card = _card_with("ativa", "cura")
            actor.update(
                known_cards=list(actor.get("known_cards") or []) + [card["id"]],
                prepared_cards=[card["id"]],
                entropy=99,
                max_entropy=99,
            )
            actor["vitalidade"] = 1
            random.seed(1)
            ct.resolve_turn(
                _scene("player"),
                {"player": actor},
                ct.TurnDeclaration(
                    actor_id="player", acao=ct.TurnStep(kind="card", card_id=card["id"])
                ),
                state={"player": actor},
                rng=random.Random(1),
            )
            return actor["vitalidade"]

        assert healed(buffed) > healed(base)
    elif stat == "vitality":
        import gamedata

        assert (
            gamedata.sync_vitality(buffed)["max_vitalidade"]
            > gamedata.sync_vitality(base)["max_vitalidade"]
        )
    elif stat == "social":
        import party

        npc_state = lambda p: {
            "player": p,
            "npcs": {"N": {"name": "N", "relationship": 0}},
            "party": [],
        }
        assert (
            party.recruitment_decision(npc_state(buffed), "N")["required_relationship"]
            < party.recruitment_decision(npc_state(base), "N")["required_relationship"]
        )
    elif stat == "perception":
        from world_utils import detection_check

        assert (
            detection_check(buffed, 2, rng=random.Random(4))["roll"]
            > detection_check(base, 2, rng=random.Random(4))["roll"]
        )
    else:
        raise AssertionError(f"stat sem consumidor no teste: {stat}")


def _passive_card_test(tipo: str, kind: str) -> Callable[[], None]:
    def run():
        card = _card_with(tipo, kind)

        def add(actor):
            if tipo == "virtude":
                actor["virtue_cards"] = [{"card_id": card["id"], "estagio": 1, "mastery": 0}]
            else:
                actor["known_cards"] = [card["id"]]

        norm = cm._normalize_card_passive(card, _actor("player"))
        stat = norm.get("stat") or ("perception" if norm.get("trigger") == "perception" else None)
        assert stat, norm
        _stat_consumer_changes(stat, add)

    return run


def _triggered_passive_test(kind: str) -> Callable[[], None]:
    def run():
        card = _card_with("passiva", kind)
        player = _actor(
            "player",
            known_cards=[card["id"]],
            entropy=99,
            max_entropy=99,
            class_name=card.get("classe"),
            level=20,
        )
        enemy = _actor("e")
        cm.apply_condition(
            player, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
        )
        scene = _scene("player", "e")
        if kind == "contra_ataque":
            cm.apply_condition(
                enemy, {"name": "Fúria", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
            )
            before = enemy["vitalidade"]
            orch.run_round(
                scene,
                {"player": player, "e": enemy},
                {"hero": ["player"], "enemy": ["e"]},
                {"player": player},
                declarations={
                    "player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass")),
                    "e": ct.TurnDeclaration(
                        actor_id="e", acao=ct.TurnStep(kind="attack", target_id="player")
                    ),
                },
                initiator="enemy",
                rng=random.Random(5),
            )
            assert enemy["vitalidade"] < before
            return
        out = ct.resolve_turn(
            scene,
            {"player": player, "e": enemy},
            ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="attack", target_id="e")),
            state={"player": player},
            rng=random.Random(5),
        )
        assert card["id"] in out.get("passives_fired", [])
        atk = out["attacks"][0]
        if kind == "vantagem":
            assert len(atk["dice_rolled"]) == 3
        elif kind == "dano":
            assert atk["dano_final"] >= int(card["efeito"]["dano_base"])
        elif kind == "aplicar_condicao":
            assert any(c.get("source") == card["id"] for c in enemy["active_conditions"])

    return run


# ==========================================================================
# Cartas ativas
# ==========================================================================
def _active_test(kind: str) -> Callable[[], None]:
    def run():
        if kind in ("dano", "contra_ataque"):
            _p, enemy, *_ = _play_active(kind, "e")
            assert enemy["vitalidade"] < enemy["max_vitalidade"]
        elif kind == "dot":
            _p, enemy, *_ = _play_active(kind, "e")
            assert any(int(c.get("dot", 0) or 0) > 0 for c in enemy["active_conditions"])
        elif kind == "aplicar_condicao":
            _p, enemy, *_ = _play_active(kind, "e")
            assert any(
                c.get("stat") or c.get("control") or c.get("dot")
                for c in enemy["active_conditions"]
            )
        elif kind in ("taunt", "marca"):
            _p, enemy, *_ = _play_active(kind, "e")
            assert cm.has_control(enemy, kind)
        elif kind == "empurrao":
            _p, _e, _a, scene, _o = _play_active(kind, "e")
            assert scene["positions"]["e"]["distance_state"] != "proximo"
        elif kind == "cura":
            player, *_ = _play_active(
                kind, "player", prep=lambda p, e, a, s: p.update(vitalidade=1)
            )
            assert player["vitalidade"] > 1
        elif kind == "estabilizar":

            def down(p, e, a, s):
                a.update(estado_terminal=True, vitalidade=0)

            _p, _e, ally, *_ = _play_active(kind, "ally", prep=down)
            assert not ally.get("estado_terminal")
        elif kind in ("protecao", "vantagem", "buff_defesa", "buff_acerto", "buff_dano"):
            stat = {
                "protecao": "protection",
                "vantagem": "advantage",
                "buff_defesa": "ac",
                "buff_acerto": "attack",
                "buff_dano": "damage",
            }[kind]
            player, *_ = _play_active(kind, "player")
            assert cm.combat_modifiers(player)[stat] > 0
        elif kind == "reposicionar":
            _p, _e, _a, scene, _o = _play_active(kind, "player")
            assert scene["positions"]["player"]["distance_state"] != "proximo"
        elif kind == "esconder":
            _p, _e, _a, scene, _o = _play_active(kind, "player")
            assert scene["positions"]["player"]["ocultacao"] == "escondido"
        elif kind == "purga_condicao":

            def poison(p, e, a, s):
                cm.apply_condition(p, {"name": "Veneno", "dot": 2, "duration": 3})

            player, *_ = _play_active(kind, "player", prep=poison)
            assert not any(c.get("name") == "Veneno" for c in player["active_conditions"])
        elif kind == "reduzir_carga_aliado":
            _p, _e, ally, *_ = _play_active(
                kind, "ally", prep=lambda p, e, a, s: a.update(abyss_charge=4)
            )
            assert ally["abyss_charge"] < 4
        else:
            raise AssertionError(kind)

    return run


# ==========================================================================
# Reações
# ==========================================================================
def _reaction_test(kind: str) -> Callable[[], None]:
    def run():
        card = _card_with("reacao", kind)
        effects = 0
        for seed in range(8):
            reactor = _actor(
                "r", virtudes={"forca": 5, "agilidade": 2, "corpo": 3, "mente": 3, "carisma": 2}
            )
            attacker = _actor(
                "player",
                virtudes={"forca": 2, "agilidade": 0, "corpo": 2, "mente": 1, "carisma": 1},
            )
            reactor["vitalidade"] = 1
            scene = _scene("player", "r")
            before = (
                attacker["vitalidade"],
                reactor["vitalidade"],
                cm.combat_modifiers(reactor),
                len(attacker["active_conditions"]),
                scene["positions"]["player"]["distance_state"],
            )
            out = {"logs": [], "deaths": [], "terminal": []}
            orch._resolve_reaction_effect(
                scene,
                reactor,
                "r",
                card,
                "player",
                {"player": attacker, "r": reactor},
                out,
                rng=random.Random(seed),
            )
            after = (
                attacker["vitalidade"],
                reactor["vitalidade"],
                cm.combat_modifiers(reactor),
                len(attacker["active_conditions"]),
                scene["positions"]["player"]["distance_state"],
            )
            effects += before != after
        assert effects >= 6, (kind, effects)

    return run


# ==========================================================================
# Condições nomeadas
# ==========================================================================
def _condition_test(name: str) -> Callable[[], None]:
    def run():
        cond = cm.parse_condition(name)
        actor = _actor("e")
        before_mods = cm.combat_modifiers(actor)
        cm.apply_condition(actor, dict(cond, duration=2))
        mods = cm.combat_modifiers(actor)
        if cond.get("dot"):
            out = {"logs": []}
            vit = actor["vitalidade"]
            orch._tick_conditions_v4(actor, out)
            assert actor["vitalidade"] < vit
        elif cond.get("control") == "silence":
            card = _card_with("ativa", "dano")
            actor.update(cartas=[card["id"]], entropy=99, max_entropy=99)
            out = ct.resolve_turn(
                _scene("e", "player"),
                {"e": actor, "player": _actor("player")},
                ct.TurnDeclaration(
                    actor_id="e",
                    acao=ct.TurnStep(kind="card", card_id=card["id"], target_id="player"),
                ),
                rng=random.Random(1),
            )
            assert not out["cards_used"]
        elif cond.get("control"):
            assert cm.has_control(actor, cond["control"])
            if cond["control"] == "fear":
                assert mods["attack"] < before_mods["attack"]
        else:
            assert mods != before_mods, (name, cond)

    return run


# ==========================================================================
# Classes / itens / traits
# ==========================================================================
def _class_player(name: str, **kw) -> dict:
    return _actor("player", **{"class_name": name, "entropy": 5, "max_entropy": 20, **kw})


def _entropy_trigger_test(kind: str) -> Callable[[], None]:
    owners = {
        "on_damage_taken": "Devoto do Abismo",
        "on_self_harm": "Sangromante",
        "on_decay_nearby": "Corruptor",
        "on_channel": "Arcanista Cinzento",
        "on_ally_suffer": "Médico de Campo",
    }

    def run():
        player = _class_player(owners[kind])
        cm.apply_entropy_trigger(player, {"kind": kind, "amount": 8, "decay_kind": "any"})
        assert player["entropy"] > 5

    return run


def _special_rule_test(kind: str) -> Callable[[], None]:
    def run():
        if kind == "taunt_scales_with_entropy":
            assert cm.taunt_aggro_multiplier(_class_player("Devoto do Abismo", entropy=10)) > 1
        elif kind == "blood_leak":
            p = _class_player("Sangromante", entropy=10, _blood_entropy=10)
            cm.apply_blood_leak(p)
            assert p["entropy"] < 10
        elif kind == "boiler":
            p = _class_player("Arcanista Cinzento")
            cm.arm_boiler(p, {})
            assert p.get("_cool_deadline")
            vit = p["vitalidade"]
            for _ in range(5):
                cm.tick_boiler(p, rng=random.Random(1))
            assert p["vitalidade"] < vit
        elif kind == "heal_abyss":
            medic = _class_player("Médico de Campo")
            ally = _actor("ally", abyss_charge=3)
            assert cm.reduce_ally_abyss(medic, ally, 2)[0] and ally["abyss_charge"] == 1
        elif kind == "domain_decay":
            from gamedata import CLASSES

            branch = next(
                b
                for b, d in CLASSES["Corruptor"]["branches"].items()
                if (d.get("overrides") or {}).get("entropy_trigger")
            )
            base = cm.entropy_config(_class_player("Corruptor"))["entropy_trigger"]
            over = cm.entropy_config(_class_player("Corruptor", subclass=branch))["entropy_trigger"]
            assert base != over
        else:
            raise AssertionError(kind)

    return run


def _consequence_test(kind: str) -> Callable[[], None]:
    def run():
        if kind == "insonia":
            from world_utils import apply_rest

            calm = _class_player("Devoto do Abismo", abyss_charge=0)
            tormented = _class_player("Devoto do Abismo", abyss_charge=9)
            for p in (calm, tormented):
                p["vitalidade"] = 1
            assert (
                apply_rest(tormented, {"world_clock": {"day": 1, "period": "manha"}})[0][
                    "vitalidade"
                ]
                < apply_rest(calm, {"world_clock": {"day": 1, "period": "manha"}})[0]["vitalidade"]
            )
        elif kind == "cicatriz":
            p = _class_player("Sangromante")
            cm.apply_scar(p, {"peak": True})
            assert p["vitalidade_max_penalty"] > 0
        elif kind == "transformacao":
            p = _class_player("Corruptor", abyss_charge=9)
            cm.apply_transformacao(p)
            assert p["active_conditions"]
        elif kind == "dependencia":
            p = _class_player("Arcanista Cinzento", abyss_charge=9)
            assert cm.dependencia_cost(p, 4) > 4
        elif kind == "recidiva":
            p = _class_player("Médico de Campo", abyss_charge=20)
            _logs, event = cm.check_recidiva(p)
            assert event and cm.combat_modifiers(p)["attack"] < 0
        else:
            raise AssertionError(kind)

    return run


def _item_by(pred) -> str:
    from gamedata import ARTIFACTS_DB

    return next(iid for iid, it in ARTIFACTS_DB.items() if pred(it.get("mechanics") or {}))


def _item_effect_test(kind: str, sub: str) -> Callable[[], None]:
    def run():
        import inventory

        iid = _item_by(
            lambda m: any(
                isinstance(e, dict)
                and e.get("kind") == kind
                and (e.get("stat") or e.get("control") or "") == sub
                for e in m.get("effects") or []
            )
        )
        hostile = kind in ("debuff", "dot", "control")
        changed = 0
        for seed in range(12):  # alvo hostil pode passar no save: mede em vários seeds
            user = _actor("player", inventory=[{"id": iid, "qty": 1}])
            target = _actor(
                "e", virtudes={"forca": 0, "agilidade": 0, "corpo": 0, "mente": 0, "carisma": 0}
            )
            before = (
                cm.combat_modifiers(target if hostile else user),
                len((target if hostile else user)["active_conditions"]),
            )
            random.seed(seed)
            updated, _logs = inventory.use_item_in_combat(
                user, iid, target=target if hostile else None
            )
            holder = target if hostile else updated
            after = (cm.combat_modifiers(holder), len(holder["active_conditions"]))
            changed += after != before
        assert changed >= 3, (iid, changed)

    return run


def _equipped(iid: str, **kw) -> dict:
    return _actor(
        "player",
        inventory=[{"id": iid, "qty": 1}],
        equipment={"weapon": None, "armor": None, "accessory": iid},
        **kw,
    )


def _item_passive_test(trigger: str) -> Callable[[], None]:
    def run():
        iid = _item_by(
            lambda m: any(
                isinstance(pe, dict) and pe.get("trigger") == trigger
                for pe in m.get("passive_effects") or []
            )
        )
        pe = next(
            p
            for p in (__import__("gamedata").ARTIFACTS_DB[iid]["mechanics"]["passive_effects"])
            if p.get("trigger") == trigger
        )
        bare = _actor("player")
        worn = _equipped(iid)
        if trigger == "always":
            assert cm.combat_modifiers(worn)[pe["stat"]] > cm.combat_modifiers(bare)[pe["stat"]]
        elif trigger == "carga_embrace":
            charged = _equipped(iid, abyss_charge=9, class_name="Devoto do Abismo")
            assert cm.combat_modifiers(charged)[pe["stat"]] > 0
        elif trigger == "damage_type":
            assert cm.damage_type_bonus(worn, pe["damage_type"]) > 0
        elif trigger == "light":
            from world_utils import light_level

            night = {"time_of_day": "Noite", "current_location_id": ""}
            assert light_level(night, worn)["lit"] and not light_level(night, bare)["lit"]
        elif trigger == "perception":
            from world_utils import detection_check

            assert (
                detection_check(worn, 2, rng=random.Random(4))["roll"]
                > detection_check(bare, 2, rng=random.Random(4))["roll"]
            )
        elif trigger == "resist":
            assert cm.is_condition_resisted(worn, pe["name"])
            assert not cm.is_condition_resisted(bare, pe["name"])
        else:
            raise AssertionError(trigger)

    return run


def _gatilho_test(gatilho: str) -> Callable[[], None]:
    from services import reactions as rx

    def run():
        card = {"tipo": "reacao", "gatilho": gatilho}
        action = {
            "kind": "attack",
            "actor": "a",
            "targets": ["r"],
            "allies_of": {"r": ["ally"]},
            "melee": True,
            "already_engaged": False,
            "supernatural": True,
            "flanked": ["r"],
            "downed": ["ally"],
            "controlled": ["ally"],
            "self_harmed": ["r"],
        }
        if gatilho in (
            "aliado_atacado",
            "ao_aliado_ser_atacado",
            "aliado_cai",
            "ao_aliado_perder_acao",
        ):
            action["targets"] = ["ally"]
        if gatilho == "ao_ser_alvo_distancia":
            action["melee"] = False
        if gatilho == "inimigo_se_move":
            action = {"kind": "move", "actor": "a", "targets": []}
            assert rx.gatilho_matches(card, action, "r")
            assert not rx.gatilho_matches(
                card, {"kind": "attack", "actor": "a", "targets": ["r"]}, "r"
            )
            return
        assert rx.gatilho_matches(card, action, "r")
        assert (
            not rx.gatilho_matches(card, {"kind": "move", "actor": "a", "targets": []}, "r")
            or gatilho == "sempre"
        )

    return run


def _trait_test(ctx: str) -> Callable[[], None]:
    def run():
        import party
        from services.npc_layers import traits_catalog

        tid = next(
            t
            for t, d in traits_catalog().items()
            if int((d.get("dc_modifiers") or {}).get(ctx, 0) or 0) > 0
        )
        state = lambda traits: {
            "player": {},
            "party": [],
            "npcs": {
                "N": {
                    "name": "N",
                    "relationship": 0,
                    "hidden_traits": traits,
                    "revealed_traits": [],
                }
            },
        }
        assert (
            party.recruitment_decision(state([tid]), "N")["required_relationship"]
            > party.recruitment_decision(state([]), "N")["required_relationship"]
        )

    return run


# ==========================================================================
# Registro chave → teste de efeito
# ==========================================================================
EFFECT_TESTS: dict[str, Callable[[], None]] = {}
for _k in (
    "dano",
    "contra_ataque",
    "dot",
    "aplicar_condicao",
    "taunt",
    "marca",
    "empurrao",
    "cura",
    "estabilizar",
    "protecao",
    "vantagem",
    "buff_defesa",
    "buff_acerto",
    "buff_dano",
    "reposicionar",
    "esconder",
    "purga_condicao",
    "reduzir_carga_aliado",
):
    EFFECT_TESTS[f"card:ativa:{_k}"] = _active_test(_k)
for _k in (
    "buff_dano",
    "buff_defesa",
    "buff_esquiva",
    "buff_iniciativa",
    "buff_dot",
    "buff_cura",
    "perception",
    "bonus_cura_por_estagio",
    "bonus_esquiva_por_estagio",
    "bonus_percepcao_por_estagio",
    "bonus_vitalidade_por_estagio",
):
    EFFECT_TESTS[f"card:passiva:{_k}"] = _passive_card_test("passiva", _k)
for _k in ("vantagem", "dano", "aplicar_condicao", "contra_ataque"):
    EFFECT_TESTS[f"card:passiva:{_k}"] = _triggered_passive_test(_k)
for _k in (
    "bonus_dano_por_estagio",
    "bonus_iniciativa_por_estagio",
    "bonus_percepcao_por_estagio",
    "bonus_social_por_estagio",
    "bonus_vitalidade_por_estagio",
):
    EFFECT_TESTS[f"card:virtude:{_k}"] = _passive_card_test("virtude", _k)
for _k in (
    "contra_ataque",
    "dano",
    "cura",
    "aplicar_condicao",
    "empurrao",
    "buff_defesa",
    "buff_esquiva",
    "protecao",
    "buff_iniciativa",
):
    EFFECT_TESTS[f"card:reacao:{_k}"] = _reaction_test(_k)


def _utility_test():
    from services.cards import all_cards
    from services.context_builder import utility_context_block

    card = next(c for c in all_cards().values() if c.get("tipo") == "utilitaria")
    assert card["name"] in utility_context_block(
        {"known_cards": [card["id"]], "class_name": card.get("classe")}
    )
    assert utility_context_block({"known_cards": []}) == ""


EFFECT_TESTS["card:utilitaria:utilitaria"] = _utility_test
EFFECT_TESTS["card:utilitaria:perception"] = _utility_test
for _name in cm.NAMED_CONDITIONS:
    EFFECT_TESTS[f"condicao:{_name}"] = _condition_test(_name)
for _name in ("atordoado", "amedrontado", "dominado", "enraizado"):
    EFFECT_TESTS[f"condicao:{_name}"] = _condition_test(_name)
for _k in ("on_damage_taken", "on_self_harm", "on_decay_nearby", "on_channel", "on_ally_suffer"):
    EFFECT_TESTS[f"class.entropy_trigger:{_k}"] = _entropy_trigger_test(_k)
for _k in ("taunt_scales_with_entropy", "blood_leak", "boiler", "heal_abyss", "domain_decay"):
    EFFECT_TESTS[f"class.special_rule:{_k}"] = _special_rule_test(_k)
for _k in ("insonia", "cicatriz", "transformacao", "dependencia", "recidiva"):
    EFFECT_TESTS[f"class.consequence:{_k}"] = _consequence_test(_k)
for _k, _sub in (
    ("buff", "ac"),
    ("buff", "attack"),
    ("debuff", "attack"),
    ("control", "fear"),
    ("control", "stun"),
    ("dot", ""),
):
    EFFECT_TESTS[f"item.effect:{_k}:{_sub}"] = _item_effect_test(_k, _sub)
for _k in ("always", "carga_embrace", "damage_type", "light", "perception", "resist"):
    EFFECT_TESTS[f"item.passive:{_k}"] = _item_passive_test(_k)
from services.reactions import GATILHOS as _GATILHOS  # noqa: E402

for _g in _GATILHOS:
    EFFECT_TESTS[f"gatilho:{_g}"] = _gatilho_test(_g)
EFFECT_TESTS["trait.dc:persuasao"] = _trait_test("persuasao")

# Lacunas FORA do combate (sem mecânica determinística consumidora ainda):
# só alimentam o prompt do NPC. Fechá-las é trabalho de spec social própria.
KNOWN_GAPS = {
    "trait.dc:comercio": "preço de mercador não lê traits de NPC (economia por mercador)",
    "trait.dc:insight": "sem teste determinístico de insight no motor",
    "trait.dc:intimidacao": "sem teste determinístico de intimidação no motor",
}


def test_todo_kind_dos_dados_tem_teste_de_efeito():
    inv = inventory()
    orphans = sorted(k for k in inv if k not in EFFECT_TESTS and k not in KNOWN_GAPS)
    assert not orphans, f"mecânica declarada sem teste de efeito: {orphans}"
    assert all(k.startswith("trait.") for k in KNOWN_GAPS), "lacuna de combate não é aceita"


def test_registro_nao_tem_teste_morto_de_chave_inexistente():
    inv = inventory()
    stale = sorted(
        k for k in EFFECT_TESTS if k not in inv and not k.startswith(("gatilho:", "condicao:"))
    )
    assert not stale, stale


@pytest.mark.parametrize("key", sorted(EFFECT_TESTS))
def test_efeito_observavel(key):
    EFFECT_TESTS[key]()
