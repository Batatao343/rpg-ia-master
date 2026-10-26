"""Cenários dirigidos do playtest: pré-condição + ação + oráculo fechados.

Eles não entram em ``PROFILES``/``--all``. O objetivo é provar uma vertical
específica sem esperar que a simulação sorteie NPC ou mercador adequados.
"""

from __future__ import annotations

import copy
import os
from typing import Optional

from playtest.profiles import ProfileDecision

RECRUIT_NPC_NAME = "Brunna Ponte-Alta"
RECRUIT_NPC_ID = "npc_mv_brunna_ponte_alta"
TRADE_START_GOLD = 200

_SCENARIOS = {
    "recrutamento": "recrutador",
    "comercio": "comerciante",
    "mundo": "explorador",
    "companheiro": "explorador",  # SPEC-300: Brunna já recrutada, alma derivada
    # SPEC-304: perigo off-screen forçado (minor: Skek; major: Brunna deixada esperando)
    "npc_perigo": "explorador",
    "companheiro_exposto": "explorador",
    # SPEC-313: caçador em Skallgard oferece uma tarefa ancorada na lore (caça)
    "lore_quests": "explorador",
    # SPEC-313 §6 passos 2-4: entrega (druida + 2 musgo), rumor falso percebido, escolta
    "lore_quests_entrega": "explorador",
    "lore_quests_rumor": "explorador",
    "lore_quests_escolta": "explorador",
    # SPEC-315 §6 passo 2: 1 achado de boato VERDADEIRO e 1 FALSO; viajar e buscar nas duas
    "rumor_adotado": "explorador",
}
# SPEC-325 R18/§6: um cenário por capacidade de conflito (combate pré-armado + bot roteirizado)
_COMBAT_CAP_SCENARIOS = (
    "combate_resistencia",
    "combate_nao_letal",
    "fuga_escolhas",
    "fuga_abandono",
    "combate_objeto",
    "combate_ordem",
    "combate_reforco",
)
_SCENARIOS.update(dict.fromkeys(_COMBAT_CAP_SCENARIOS, "combate"))
_COMPANION_COMBAT = ("fuga_abandono", "combate_ordem")
ADOPT_TRUE_LOC = "na_anel_ferro"
ADOPT_FALSE_LOC = "na_anel_lama"
_LORE_VARIANTS = ("lore_quests_entrega", "lore_quests_rumor", "lore_quests_escolta")
_NPC_SCENARIOS = ("npc_perigo", "companheiro_exposto")
LORE_NPC_NAME = "Rolf Caçador"
LORE_NPC_ID = "npc_mv_rolf_cacador"
LORE_DRUID_ID = "npc_mv_rolf_druida"
LORE_MERCHANT_ID = "npc_mv_rolf_mercador"
LORE_RUMOR_SEED = "rumor_a_legiao_esta_fabricando_soldados_a_partir_de_mortos"
LORE_RUMOR_LOC = "na_anel_ferro"
SKEK_ID = "npc_mv_skek_eco_curto"
WAIT_LOCATION = "ma_saidas_baixas"


def cleanup(name: str) -> None:
    """Desfaz o que `prepare` deixou fora do estado (flag do harness de `rumor_adotado`)."""
    if name == "rumor_adotado":
        os.environ.pop("RPG_PLAYTEST_FORCED_ADOPT", None)


def names() -> tuple[str, ...]:
    return tuple(_SCENARIOS)


def profile_for(name: str) -> str:
    try:
        return _SCENARIOS[str(name)]
    except KeyError as exc:
        raise KeyError(
            f"cenário desconhecido: {name!r} (conhecidos: {sorted(_SCENARIOS)})"
        ) from exc


def _move_world(world: dict, location_id: str) -> dict:
    from gamedata import get_location

    location = get_location(location_id)
    if not location:
        raise KeyError(f"local canônico ausente: {location_id}")
    moved = copy.deepcopy(world or {})
    moved["current_location_id"] = location_id
    moved["current_location"] = location["name"]
    moved["danger_level"] = int(location.get("danger", 1) or 1)
    visited = list(moved.get("visited") or [])
    if location_id not in visited:
        visited.append(location_id)
    moved["visited"] = visited
    return moved


def _prepare_mundo(prepared: dict) -> dict:
    """SPEC-302 §6: `nova_arcadia.guerra` em crise e AVISO ja emitido no dia atual; a crise
    deve abrir em ate 5 dias de jogo (MIN_WARNING_DAYS = 2) e virar `location_state`."""
    from services import world_engine as we
    from services import world_pressures as wp

    prepared["world"] = _move_world(prepared.get("world") or {}, "nova_arcadia")
    day = int(((prepared["world"].get("world_clock") or {}).get("day", 1)) or 1)
    sim = prepared.get("world_sim") or we._new_sim(str(prepared.get("game_id", "")), day, [], "on")
    sim["calm_until_day"] = 0
    sim["pressures"]["nova_arcadia"]["guerra"] = 82
    sim["bands"], _ = wp.update_bands(sim["bands"], sim["pressures"])
    if not any(
        c.get("kind") == "guerra" and c.get("region_id") == "nova_arcadia" for c in sim["crises"]
    ):
        from services import world_director as wd

        wd.announce(sim, day, "nova_arcadia", "guerra", game_id=str(prepared.get("game_id", "")))
        log = list(prepared.get("event_log") or [])
        log.append(
            {
                "event_id": wd.event_id(
                    str(prepared.get("game_id", "")), "world_crisis_warning", day, "nova_arcadia"
                ),
                "turn": 0,
                "type": "world_crisis_warning",
                "actor_id": "engine",
                "target_id": "nova_arcadia",
                "payload": {
                    "kind": "guerra",
                    "region_id": "nova_arcadia",
                    "crisis_id": "",
                    "earliest_day": day + 2,
                },
                "source": "engine",
            }
        )
        prepared["event_log"] = log
    prepared["world_sim"] = sim
    return prepared


def _prepare_npc_world(prepared: dict, name: str) -> dict:
    """SPEC-304 §6: NPC exposto num local de perigo 3 e abertura do perigo FORÇADA (o hazard
    sorteado vira acerto) — o resto do ciclo (telegrama, mensageiro, prazo, destino) é o real."""
    from services import npc_world
    from services import world_engine as we

    prepared["world"] = _move_world(prepared.get("world") or {}, "nova_arcadia")
    day = int(((prepared["world"].get("world_clock") or {}).get("day", 1)) or 1)
    sim = prepared.get("world_sim") or we._new_sim(str(prepared.get("game_id", "")), day, [], "on")
    sim["calm_until_day"] = 0  # sem a calma inicial do diretor
    prepared["world_sim"] = sim
    npc_sim = npc_world._new_sim(day)
    if name == "companheiro_exposto":
        import party

        prepared = prepare("companheiro", prepared)
        prepared["world"] = _move_world(prepared.get("world") or {}, "nova_arcadia")
        prepared["party"], _ok = party.set_waiting(prepared, RECRUIT_NPC_NAME, WAIT_LOCATION)
        npc_sim["forced"] = [RECRUIT_NPC_ID]
    else:
        npc_sim["forced"] = [SKEK_ID]
    prepared["npc_sim"] = npc_sim
    return prepared


def _prepare_lore_quests(prepared: dict) -> dict:
    """SPEC-313 §6: caçador em cena em Skallgard; o menu `<GANCHOS_POSSIVEIS>` oferece a caça."""
    prepared["world"] = _move_world(prepared.get("world") or {}, "skallgard")
    npcs = copy.deepcopy(prepared.get("npcs") or {})
    npcs[LORE_NPC_NAME] = {
        "id": LORE_NPC_ID,
        "name": LORE_NPC_NAME,
        "persona": "Caçador calado dos clãs; conhece as trilhas e as feras de Skallgard.",
        "role": "caçador",
        "relationship": 6,
        "interaction_count": 2,
        "in_scene": True,
        "known_by_player": True,
        "home_location_id": "skallgard",
        "location": "Skallgard",
        "traits": [],
        "memory": [],
    }
    prepared["npcs"] = npcs
    prepared["active_npc_name"] = LORE_NPC_NAME
    return prepared


def _lore_npc(name: str, npc_id: str, role: str, loc_id: str, loc_name: str) -> dict:
    return {
        "id": npc_id,
        "name": name,
        "persona": f"{role.capitalize()} de {loc_name}; fala pouco e conhece o ofício.",
        "role": role,
        "relationship": 6,
        "interaction_count": 2,
        "in_scene": True,
        "known_by_player": True,
        "home_location_id": loc_id,
        "location": loc_name,
        "traits": [],
        "memory": [],
    }


def _prepare_lore_variant(prepared: dict, name: str) -> dict:
    """SPEC-313 §6 passos 2-4. Pré-condições mecânicas; oferta, viagem e conclusão são do jogo."""
    from services import npc_world
    from services import rumors as _rumors
    from services import world_engine as we

    day = int(((prepared.get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)
    if name == "lore_quests_entrega":
        loc = "pantano_melancolia"
        npc = _lore_npc("Rolf Druida", LORE_DRUID_ID, "druida herbalista", loc, "Pântano")
        player = copy.deepcopy(prepared.get("player") or {})
        player["inventory"] = [
            *[i for i in (player.get("inventory") or []) if i.get("id") != "musgo_cinzento"],
            {"id": "musgo_cinzento", "qty": 2},
        ]
        prepared["player"] = player
    elif name == "lore_quests_escolta":
        loc = "nova_arcadia"
        npc = _lore_npc(
            "Rolf Mercador", LORE_MERCHANT_ID, "mercador de caravana", loc, "Nova Arcádia"
        )
    else:  # lore_quests_rumor
        loc = "nova_arcadia"
        npc = None
    prepared["world"] = _move_world(prepared.get("world") or {}, loc)
    if npc:
        npcs = copy.deepcopy(prepared.get("npcs") or {})
        npcs[npc["name"]] = npc
        prepared["npcs"] = npcs
        prepared["active_npc_name"] = npc["name"]
    sim = prepared.get("world_sim") or we._new_sim(str(prepared.get("game_id", "")), day, [], "on")
    sim["calm_until_day"] = day + 30  # sem crise nova atrapalhando o roteiro
    if name == "lore_quests_rumor":
        # boato FALSO já percebido, com gancho de quest (a verdade é só do motor)
        rid = _rumors._sha(str(prepared.get("game_id", "")), LORE_RUMOR_SEED, day)[:16]
        sim["rumors"] = [
            *[r for r in (sim.get("rumors") or []) if r.get("rumor_id") != rid],  # idempotente
            {
                "rumor_id": rid,
                "seed_id": LORE_RUMOR_SEED,
                "family": "lore",
                "region_id": "nova_arcadia",
                "location_id": LORE_RUMOR_LOC,
                "entities": [],
                "subject": "pessoa",
                "truth": False,
                "quest_eligible": True,
                "born_day": day,
                "born_turn": 0,
                "expires_day": day + 14,
                "perceived_day": max(1, day - 1),
                "resolution": "",
            },
        ]
        sim["rumor_last_perceived_day"] = day  # cooldown: nenhum outro boato percebido hoje
    prepared["world_sim"] = sim
    if name == "lore_quests_escolta":
        npc_sim = prepared.get("npc_sim") or npc_world._new_sim(day)
        npc_sim["npcs"][LORE_MERCHANT_ID] = {
            "archetype": "mercador_itinerante",
            "home": loc,
            "pos": {"location_id": loc, "since_day": day, "arrive_day": None},
            "status": "",
            "frozen": False,
        }
        npc_sim["roster"] = [
            *[r for r in npc_sim.get("roster", []) if r != LORE_MERCHANT_ID],
            LORE_MERCHANT_ID,
        ]
        prepared["npc_sim"] = npc_sim
    return prepared


def _adopted_row(game_id: str, loc: str, day: int, truth: bool, perceived: int = 1) -> dict:
    from services import rumors as _rumors

    rid = _rumors._sha(game_id, "adopt:" + loc, day)[:16]
    return {
        "rumor_id": rid,
        "seed_id": "narrador:" + rid[:12],
        "family": "narrador",
        "location_id": loc,
        "entities": ["nova_arcadia"],
        "subject": "lugar",
        "truth": truth,
        "quest_eligible": True,
        "adopted": True,
        "claim": {"kind": "esconderijo", "location_id": loc, "entity_id": ""},
        "materialized_day": 0,
        "born_day": max(0, day - 1),
        "born_turn": 0,
        "expires_day": day + 8,
        "perceived_day": perceived,
        "text": "Dizem que alguem escondeu algo por la",
        "resolution": "",
    }


def _prepare_rumor_adotado(prepared: dict) -> dict:
    """SPEC-315 §6 passo 2: duas alegacoes ADOTADAS (uma verdadeira, uma falsa) ja percebidas;
    viagem, busca e materializacao sao do jogo real."""
    from services import world_engine as we

    prepared["world"] = _move_world(prepared.get("world") or {}, "nova_arcadia")
    day = int(((prepared["world"].get("world_clock") or {}).get("day", 1)) or 1)
    gid = str(prepared.get("game_id", ""))
    sim = prepared.get("world_sim") or we._new_sim(gid, day, [], "on")
    sim["calm_until_day"] = day + 30
    sim["rumors"] = [
        _adopted_row(gid, ADOPT_TRUE_LOC, day, True),
        _adopted_row(gid, ADOPT_FALSE_LOC, day, False, perceived=2),
    ]
    sim["rumor_last_perceived_day"] = day
    sim["forced_adopt"] = [
        {"kind": "esconderijo", "location_id": ADOPT_TRUE_LOC, "truth": True},
        {"kind": "esconderijo", "location_id": ADOPT_FALSE_LOC, "truth": False},
    ]
    prepared["world_sim"] = sim
    os.environ["RPG_PLAYTEST_FORCED_ADOPT"] = "1"  # so o harness honra `forced_adopt`
    return prepared


def _adopted_decision(state: dict) -> ProfileDecision:
    cur = str((state.get("world") or {}).get("current_location_id") or "")
    rows = {
        r["claim"]["location_id"]: r
        for r in (state.get("world_sim") or {}).get("rumors") or []
        if isinstance(r, dict) and r.get("adopted")
    }
    for loc in (ADOPT_TRUE_LOC, ADOPT_FALSE_LOC):
        row = rows.get(loc) or {}
        if row.get("materialized_day"):
            continue
        if cur != loc:
            return ProfileDecision(text=_lore_hop_text(state, loc), mode="free_text")
        return ProfileDecision(
            text="Examino e procuro cada canto do local em busca de um esconderijo.",
            mode="free_text",
        )
    return ProfileDecision(text="Observo o local e descanso um instante.", mode="free_text")


def _lore_hop_text(state: dict, target: str) -> str:
    """Próximo passo (um nó do mapa) rumo a `target`, em texto de viagem."""
    import gamedata
    from services import world_distance

    cur = str((state.get("world") or {}).get("current_location_id") or "")
    best = min(  # proximo no do caminho minimo; o proprio alvo vence os empates (aneis custam 0)
        (
            (
                world_distance._edge_cost(cur, n["id"])
                + world_distance.travel_periods(n["id"], target),
                0 if n["id"] == target else 1,
                n["id"],
            )
            for n in gamedata.get_connections(cur)
            if n.get("id") and world_distance.travel_periods(n["id"], target) is not None
        ),
        default=(0, 0, target),
    )
    return f"Viajo para {gamedata.get_location(best[2])['name']}."


_LORE_ASK = {
    "lore_quests_entrega": "Converso com Rolf Druida e peço uma tarefa concreta de entrega.",
    "lore_quests_escolta": "Converso com Rolf Mercador: preciso de uma tarefa concreta, uma escolta.",
    "lore_quests_rumor": "Olho ao redor e escuto o que dizem sobre os soldados da Legião.",
}
_LORE_INVESTIGATE = (
    "Investigo as fundições e pergunto aos ferreiros sobre os soldados.",
    "Examino o local e procuro sinais do que dizem por aí.",
    "Escuto os trabalhadores e confiro a história com cuidado.",
)


def _lore_variant_decision(name: str, turn: int, state: dict) -> ProfileDecision:
    """Roteiro: pede a tarefa; com a quest ativa viaja ao alvo e cumpre o verbo do tipo."""
    from services.lore_quests import LORE_KINDS

    quest = next(
        (
            q
            for q in state.get("quests") or []
            if q.get("world_kind") in LORE_KINDS and q.get("status") == "active"
        ),
        None,
    )
    if quest is None:
        return ProfileDecision(text=_LORE_ASK[name], mode="free_text")
    cur = str((state.get("world") or {}).get("current_location_id") or "")
    target = str(quest.get("location_id") or "")
    if cur != target:
        return ProfileDecision(text=_lore_hop_text(state, target), mode="free_text")
    if quest["world_kind"] == "entregar_material":
        return ProfileDecision(text="Entrego o musgo ao boticário.", mode="free_text")
    if quest["world_kind"] == "investigar_rumor":
        text = _LORE_INVESTIGATE[int(turn) % len(_LORE_INVESTIGATE)]
        return ProfileDecision(text=text, mode="free_text")
    return ProfileDecision(text="Descanso um instante e observo o local.", mode="free_text")


def prepare(name: str, state: dict) -> dict:
    """Devolve cópia do estado com pré-condições mecânicas do cenário."""
    profile_for(name)  # valida catálogo
    prepared = copy.deepcopy(dict(state or {}))
    if name in _COMPANION_COMBAT:
        return prepare("companheiro", prepared)  # Brunna recrutada, alma derivada
    if name == "combate_reforco":  # perigo 3: o orçamento do encontro comporta um reforço
        prepared["world"] = _move_world(prepared.get("world") or {}, "montanhas_afiadas")
        return prepared
    if name in _COMBAT_CAP_SCENARIOS:
        return prepared  # o combate é armado em `decision_for` (turno 1), após o startup
    if name in _LORE_VARIANTS:
        return _prepare_lore_variant(prepared, name)
    if name == "lore_quests":
        return _prepare_lore_quests(prepared)
    if name == "rumor_adotado":
        return _prepare_rumor_adotado(prepared)
    if name == "recrutamento":
        prepared["world"] = _move_world(
            prepared.get("world") or {},
            "montanhas_afiadas",
        )
        npcs = copy.deepcopy(prepared.get("npcs") or {})
        npcs[RECRUIT_NPC_NAME] = {
            "id": RECRUIT_NPC_ID,
            "name": RECRUIT_NPC_NAME,
            "persona": (
                "Guia veterana das passagens móveis; direta, leal e avessa a promessas vazias."
            ),
            "relationship": 10,
            # SPEC-223 R4: recrutar exige >= 2 conversas registradas.
            "interaction_count": 2,
            "in_scene": True,
            "known_by_player": True,
            "home_location_id": "montanhas_afiadas",
            "location": "Montanhas Afiadas",
            "traits": [],
            "memory": [],
        }
        prepared["npcs"] = npcs
        prepared["party"] = [
            ally
            for ally in (prepared.get("party") or [])
            if str(ally.get("name") or "") != RECRUIT_NPC_NAME
        ]
        return prepared

    if name == "mundo":
        return _prepare_mundo(prepared)
    if name in _NPC_SCENARIOS:
        return _prepare_npc_world(prepared, name)
    if name == "companheiro":
        prepared = prepare("recrutamento", prepared)
        import party
        from services import companion_soul

        npc = prepared["npcs"][RECRUIT_NPC_NAME]
        comp = party.make_companion_from_npc(npc, RECRUIT_NPC_NAME)
        prepared["party"] = [comp]
        prepared["companion_souls"] = {
            companion_soul.comp_id(comp): companion_soul.ensure_soul(prepared, comp)
        }
        return prepared

    prepared["world"] = _move_world(
        prepared.get("world") or {},
        "na_anel_dourado",
    )
    player = copy.deepcopy(prepared.get("player") or {})
    player["gold"] = TRADE_START_GOLD
    player["inventory"] = [
        item
        for item in (player.get("inventory") or [])
        if str(item.get("id") or "") != "pocao_cura"
    ]
    prepared["player"] = player
    return prepared


def decision_for(name: str, turn: int, state: dict) -> ProfileDecision | None:
    """A primeira ação é inequívoca; turnos extras voltam ao perfil normal."""
    profile_for(name)
    if name in _COMBAT_CAP_SCENARIOS:
        from playtest import capability_bots

        return capability_bots.decision_for(name, int(turn), state)
    if name == "mundo" or name in _NPC_SCENARIOS:
        return ProfileDecision(text="Vou descansar e acampar aqui.", mode="free_text")
    if name in _LORE_VARIANTS:
        return _lore_variant_decision(name, turn, state)
    if name == "rumor_adotado":
        return _adopted_decision(state)
    if name == "lore_quests":
        return ProfileDecision(
            text=f"Converso com {LORE_NPC_NAME} e peço um trabalho: uma tarefa concreta.",
            mode="free_text",
        )
    if int(turn) != 1:
        return None
    if name == "recrutamento":
        return ProfileDecision(
            text=(f"Peço que {RECRUIT_NPC_NAME} se junte a mim na jornada e venha comigo."),
            mode="free_text",
        )
    if name == "companheiro":
        return ProfileDecision(
            text="Ameaço o mercador com a faca até ele baixar o preço.",
            mode="free_text",
        )
    return ProfileDecision(
        text="Compro uma Poção de Cura Menor no Empório do Anel Dourado.",
        mode="free_text",
    )


def _violation(check_id: str, message: str, turn: int) -> dict:
    return {
        "check_id": check_id,
        "severity": "error",
        "turn": int(turn),
        "message": message,
        "details": {"scenario": check_id.split(".", 1)[-1]},
    }


def _capability_violations(name: str, result, turn: int) -> list[dict]:
    """SPEC-325 §6: com a flag da capacidade `on`, ela PRECISA ter disparado ao menos 1 vez.
    Com `off`/`shadow` o cenário só roda (nada a exigir)."""
    from playtest import capability_bots
    from services import combat_flags

    cap = capability_bots.required_capabilities(name)[0]
    if combat_flags.mode(cap) != "on":
        return []
    counts = getattr(result, "capability_counts", None) or {}
    if int(counts.get(cap, 0) or 0) >= 1:
        return []
    return [
        _violation(
            f"smoke.{name}_not_observed",
            f"A capacidade `{cap}` (flag on) não disparou no cenário.",
            turn,
        )
    ]


def oracle_violations(name: str, result) -> list[dict]:
    """Pós-condição observável que transforma smoke inconclusivo em falha."""
    profile_for(name)
    state = getattr(result, "final_state", {}) or {}
    turn = int(getattr(result, "turns_completed", 0) or 0)
    if name == "recrutamento":
        import party

        if any(
            str(ally.get("name") or "") == RECRUIT_NPC_NAME for ally in party.active_allies(state)
        ):
            return []
        return [
            _violation(
                "smoke.recruitment_not_observed",
                f"{RECRUIT_NPC_NAME} não entrou na party ativa.",
                turn,
            )
        ]

    if name in _COMBAT_CAP_SCENARIOS:
        return _capability_violations(name, result, turn)

    if name in _NPC_SCENARIOS:
        target = RECRUIT_NPC_ID if name == "companheiro_exposto" else SKEK_ID
        warned = [
            e
            for e in state.get("event_log") or []
            if e.get("type") == "npc_peril_warning" and e.get("target_id") == target
        ]
        if not warned:
            return [
                _violation(
                    "smoke.npc_peril_not_observed",
                    f"npc_peril_warning de {target} não foi observado.",
                    turn,
                )
            ]
        if name == "companheiro_exposto":
            seen = set((state.get("world_sim") or {}).get("perceived_ids") or [])
            if warned[0]["payload"].get("channel") != "pedido_de_ajuda" or (
                warned[0]["event_id"] not in seen
            ):
                return [
                    _violation(
                        "smoke.npc_help_request_not_perceived",
                        "O pedido de ajuda não chegou ao jogador (mensageiro).",
                        turn,
                    )
                ]
        return []

    if name == "rumor_adotado":
        rows = [
            r
            for r in (state.get("world_sim") or {}).get("rumors") or []
            if isinstance(r, dict) and r.get("adopted")
        ]
        true_row = next((r for r in rows if r.get("truth")), {})
        false_row = next((r for r in rows if not r.get("truth")), {})
        if not true_row.get("materialized_day"):
            return [
                _violation(
                    "smoke.rumor_adopt_true_not_materialized",
                    "O achado do boato verdadeiro nao materializou.",
                    turn,
                )
            ]
        if false_row.get("materialized_day"):
            return [
                _violation(
                    "smoke.rumor_adopt_false_materialized",
                    "O boato falso materializou (proibido).",
                    turn,
                )
            ]
        return []

    if name in _LORE_VARIANTS:
        from services.lore_quests import LORE_KINDS

        want = {
            "lore_quests_entrega": "entregar_material",
            "lore_quests_rumor": "investigar_rumor",
            "lore_quests_escolta": "escoltar",
        }[name]
        if any(q.get("world_kind") == want for q in state.get("quests") or []):
            return []
        return [
            _violation(
                f"smoke.{name}_not_observed",
                f"Nenhuma quest `{want}` foi criada no cenário.",
                turn,
            )
        ]

    if name == "lore_quests":
        from services.lore_quests import LORE_KINDS

        if any(q.get("world_kind") in LORE_KINDS for q in state.get("quests") or []):
            return []
        return [
            _violation(
                "smoke.lore_quest_not_observed",
                "Nenhuma quest ancorada em lore foi oferecida pelo caçador.",
                turn,
            )
        ]

    if name == "mundo":
        sim = state.get("world_sim") or {}
        opened = any(
            c.get("region_id") == "nova_arcadia" and c.get("start_day") is not None
            for c in sim.get("crises") or []
        )
        warned = any(e.get("type") == "world_crisis_warning" for e in state.get("event_log") or [])
        if opened and warned:
            return []
        return [
            _violation(
                "smoke.world_crisis_not_observed",
                "Aviso -> crise em nova_arcadia nao foi observado em 5 dias de jogo.",
                turn,
            )
        ]

    if name == "companheiro":
        soul = (state.get("companion_souls") or {}).get(RECRUIT_NPC_ID) or {}
        if soul and isinstance(soul.get("approval"), int):
            return []
        return [
            _violation(
                "smoke.companion_soul_not_observed",
                f"{RECRUIT_NPC_NAME} não tem alma persistida após o turno dirigido.",
                turn,
            )
        ]

    player = state.get("player") or {}
    has_potion = any(
        str(item.get("id") or "") == "pocao_cura" and int(item.get("qty", 0) or 0) >= 1
        for item in (player.get("inventory") or [])
        if isinstance(item, dict)
    )
    spent_gold = int(player.get("gold", TRADE_START_GOLD) or 0) < TRADE_START_GOLD
    if has_potion and spent_gold:
        return []
    return [
        _violation(
            "smoke.trade_not_observed",
            "Compra dirigida não reduziu ouro e adicionou poção ao inventário.",
            turn,
        )
    ]
