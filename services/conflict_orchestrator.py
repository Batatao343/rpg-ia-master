"""services/conflict_orchestrator.py — orquestrador de RODADA do conflito v2 (spec conflito-13, cutover).

A peça que sobe do TURNO (`conflict_turn.resolve_turn`, um ator) para a RODADA
inteira do combate, compondo TODOS os motores puros das specs 03-12, 100%
determinístico e ZERO LLM em resolução:

  iniciativa por lado (04) → cada ator age em ordem
    → tick de condições/DoT (motor de classes que SOBREVIVE)
    → Ataque de Oportunidade ao abandonar Engajamento (06)
    → janela de Reação sobre o ataque declarado (06)
    → resolução do turno declarado (`conflict_turn`, compõe 03/04/05/07)
    → gatilhos de Entropia/Carga da classe (SOBREVIVEM: on_damage_taken/…)
    → Estado Terminal → estabilização/morte (07)
    → evento do Abismo carregado por Cargas (10)
  fim de rodada → colheita de Entropia/Recidiva → detecção de encerramento (07)

`combat_node` (agents/combat.py) chama `run_round` a cada round; a IA de inimigo
(`enemy_declaration`) decide a `TurnDeclaration` por perfil tático (08), sem LLM.
O jogador chega com a `TurnDeclaration` já montada (parse CLASSIFY no nó).
"""
import random
from typing import Dict, List, Optional

import combat_mechanics as cm  # helpers que SOBREVIVEM (condições, Entropia/Carga)
import gamedata
from services import abyss_events
from services import conflict_scene as cs
from services import conflict_turn as ct
from services import death_flow
from services import reactions as rx
from services.conflict_resolution import (compute_esquiva, resolve_attack,
                                          roll_initiative_by_side, virtude_value)
from services.conflict_damage import resolve_damage_and_wounds
from services import tactical_profile as tp

_VIRTUDES = ("forca", "agilidade", "corpo", "mente", "carisma")

# Mapa de `type`/`categoria` legado → categoria canônica do fluxo de morte (07/15).
_CATEGORIA_ALIAS = {
    "minion": "lacaio", "lacaio": "lacaio", "trivial": "lacaio",
    "padrao": "padrao", "standard": "padrao", "normal": "padrao", "grunt": "padrao",
    "elite": "elite", "veterano": "elite",
    "boss": "chefe", "chefe": "chefe", "chefao": "chefe",
    "nomeado": "nomeado", "named": "nomeado", "unico": "nomeado",
    "companheiro": "companheiro", "aliado": "companheiro",
}
_KNOWN_CATEGORIAS = (death_flow.FULL_FLOW_CATEGORIES
                     | death_flow.NO_TERMINAL_CATEGORIES
                     | death_flow.MINION_CATEGORIES)


# ==========================================================================
# Adaptador: qualquer ator (v4 curado, legado D&D, ficha crua) → ficha v4 de combate
# ==========================================================================
def _derive_virtudes(actor: dict) -> Dict[str, int]:
    return {k: virtude_value(actor, k) for k in _VIRTUDES}


def ensure_combat_sheet(actor: dict, *, is_player: bool = False) -> dict:
    """Normaliza `actor` (mutando) para a ficha de combate v4 que o motor novo
    consome: Virtudes 0-5, Vitalidade/espaços de Ferimento por Corpo, Esquiva,
    categoria canônica (07) e um perfil tático default para inimigo. Idempotente —
    respeita campos v4 já presentes (bestiário curado da conflito-15)."""
    if not isinstance(actor.get("virtudes"), dict) or not actor["virtudes"]:
        actor["virtudes"] = _derive_virtudes(actor)
    corpo = int(actor["virtudes"].get("corpo", 0) or 0)
    legacy_hp = actor.get("hp")
    legacy_max_hp = actor.get("max_hp")
    if not actor.get("max_vitalidade"):
        actor["max_vitalidade"] = gamedata.vitalidade_para_corpo(corpo)
    if actor.get("vitalidade") is None:
        if legacy_hp is not None and legacy_max_hp:
            ratio = max(
                0.0,
                min(1.0, float(legacy_hp) / max(1, float(legacy_max_hp))),
            )
            actor["vitalidade"] = round(int(actor["max_vitalidade"]) * ratio)
        else:
            actor["vitalidade"] = int(actor["max_vitalidade"])
    if not actor.get("ferimento_espacos"):
        actor["ferimento_espacos"] = gamedata.espacos_ferimento_para_corpo(corpo)
    fer = actor.setdefault("ferimentos", {"leve": [], "grave": [], "critico": []})
    for c in ("leve", "grave", "critico"):
        fer.setdefault(c, [])
    if actor.get("esquiva") is None:
        actor["esquiva"] = compute_esquiva(actor)
    actor.setdefault("active_conditions", [])
    actor.setdefault("conscious", True)
    actor.setdefault("status", "ativo")
    if is_player or actor.get("is_player") or actor.get("player"):
        actor["is_player"] = True
        if actor.get("cartas"):
            actor["cartas"] = [
                entry for entry in actor["cartas"]
                if str(entry.get("id") if isinstance(entry, dict) else entry)
                != "bst_defesa_instintiva"
            ]
    else:
        cat = _CATEGORIA_ALIAS.get(str(actor.get("categoria") or "").strip().lower())
        if not cat:
            cat = _CATEGORIA_ALIAS.get(str(actor.get("type") or "").strip().lower(), "padrao")
        actor["categoria"] = cat if cat in _KNOWN_CATEGORIAS else "padrao"
        actor["tactical_profile"] = tp.normalize_runtime_profile(
            actor, actor.get("tactical_profile") or tp._default_profile())
        if actor["categoria"] != "companheiro":
            actor["pursuit_policy"] = actor["tactical_profile"].get(
                "pursuit_policy", "nao_persegue"
            )
            mind = int(actor["virtudes"].get("mente", 0) or 0)
            actor.setdefault("max_entropy", max(0, mind * 2))
            actor.setdefault("entropy", int(actor.get("max_entropy", 0) or 0))
            actor.setdefault("enemy_card_usage", {})
            enemy_cards = list(actor.get("cartas") or actor.get("enemy_cards") or [])
            known_ids = {
                str(entry.get("id") if isinstance(entry, dict) else entry)
                for entry in enemy_cards
            }
            if "bst_defesa_instintiva" not in known_ids:
                enemy_cards.append("bst_defesa_instintiva")
            actor["cartas"] = enemy_cards
    gamedata.sync_legacy_hp_aliases(actor)
    return actor


# ==========================================================================
# Estado do ator na cena
# ==========================================================================
def _name(actor: dict) -> str:
    return actor.get("name") or actor.get("id") or "?"


def _alive(actor: Optional[dict]) -> bool:
    """Participa do combate. A DERROTA é por FLAG (dead/status), não por Vitalidade:
    no motor novo Vitalidade 0 é só 'muito ferido' — a queda vem de Ferimentos (05/07).
    Vitalidade 0 mais status ativo segue lutando até encher os espaços de Ferimento."""
    if not actor:
        return False
    if actor.get("dead") or actor.get("fled") or actor.get("surrendered"):
        return False
    if not actor.get("conscious", True) or actor.get("incapacitated"):
        return False
    return str(actor.get("status", "ativo")) not in ("morto", "fugiu", "rendido")


def _can_act(actor: dict) -> bool:
    """Pode declarar turno: vivo e NÃO em Estado Terminal (terminal só reage/estabiliza)."""
    return (_alive(actor) and not actor.get("estado_terminal")
            and not actor.get("last_stand_pending"))


def _agility(actor: dict) -> int:
    return virtude_value(actor, "agilidade")


def _apply_dot_v4(target: dict, dot: int, dtype: str, out: dict, rng=None) -> None:
    """DoT do motor NOVO: reduz Vitalidade; excedente vira Ferimento localizado (05).
    Sangramento/veneno ignoram armadura (dano contínuo interno)."""
    known_types = set(gamedata.DANO_FISICO) | {
        "igneo", "gelido", "eletrico", "arcano", "corrosivo", "abissal",
    }
    result = resolve_damage_and_wounds(
        target,
        damage_base=max(0, int(dot)),
        damage_type=dtype if dtype in known_types else "cortante",
        ignore_resistance=True,
        defensavel=False,
        directed_region=None,
        rng=rng,
    )
    out["logs"] += result["log"]


def _tick_conditions_v4(actor: dict, out: dict, rng=None) -> bool:
    """Versão v4 de `tick_conditions`: aplica DoT em Vitalidade (não em hp), decrementa
    duração e remove condições expiradas. Substitui `cm.tick_conditions` (que ticava
    hp do motor antigo) no loop novo."""
    survivors: List[dict] = []
    damage_applied = False
    for c in actor.get("active_conditions", []) or []:
        dot = int(c.get("dot", 0) or 0)
        if dot > 0:
            damage_applied = True
            _apply_dot_v4(
                actor, dot, str(c.get("damage_type") or c.get("source") or "cortante"),
                out, rng=rng)
            out["logs"].append(
                f"{_name(actor)} sofre {dot} de {c.get('name', 'condição')} "
                f"(Vit {actor.get('vitalidade', 0)}).")
        c["duration"] = int(c.get("duration", 0)) - 1
        if c["duration"] > 0:
            survivors.append(c)
        else:
            out["logs"].append(f"{_name(actor)}: {c.get('name', 'condição')} terminou.")
    actor["active_conditions"] = survivors
    return damage_applied


# ==========================================================================
# IA de inimigo (perfil tático → TurnDeclaration), 100% sem LLM (08)
# ==========================================================================
def _opposing_ids(actor_id: str, sides: Dict[str, List[str]]) -> List[str]:
    hero = set(sides.get("hero", [])) | set(sides.get("ally", []))
    enemy = set(sides.get("enemy", []))
    return list(enemy) if actor_id in hero else list(hero)


def _nearest_target(actor_id: str, candidates: List[str], actors_by_id: Dict[str, dict]) -> Optional[str]:
    alive = [c for c in candidates if _alive(actors_by_id.get(c))]
    if not alive:
        return None
    # sem grade: "mais próximo/ameaçador" = maior Agilidade (proxy determinístico estável)
    alive.sort(key=lambda c: (-_agility(actors_by_id[c]), str(c)))
    return alive[0]


def _taunt_target(actor: dict, candidates: List[str], actors_by_id: Dict[str, dict], rng) -> Optional[str]:
    """Resolve Provocação fechada: a condição vive no provocado e aponta a fonte.

    A chance-base de 50% escala pela Entropia do Devoto e respeita teto de 90%.
    Sem fonte válida/viva, a seleção tática normal permanece intacta.
    """
    candidate_set = set(candidates)
    for condition in actor.get("active_conditions") or []:
        if condition.get("control") != "taunt":
            continue
        source_id = str(condition.get("source_actor_id") or "")
        source = actors_by_id.get(source_id)
        if source_id not in candidate_set or not _alive(source):
            continue
        chance = min(0.9, 0.5 * cm.taunt_aggro_multiplier(source))
        if rng.random() < chance:
            source.setdefault("_last_class_mechanics", []).append({
                "kind": "special:taunt", "chance": round(chance, 4),
                "target_id": source_id,
            })
            return source_id
    return None


def _same_side_ids(actor_id: str, sides: Dict[str, List[str]]) -> List[str]:
    heroes = list(sides.get("hero", [])) + list(sides.get("ally", []))
    if actor_id in heroes:
        return heroes
    enemies = list(sides.get("enemy", []))
    return enemies if actor_id in enemies else []


def _available_for_aid(actor: Optional[dict]) -> bool:
    """Pode receber ajuda mesmo inconsciente/terminal, mas não após sair da cena."""
    if not actor:
        return False
    if actor.get("dead") or actor.get("fled") or actor.get("surrendered"):
        return False
    return str(actor.get("status", "ativo")) not in ("morto", "fugiu", "rendido")


def _vitality_ratio(actor: dict) -> float:
    maximum = max(1, int(actor.get("max_vitalidade", 1) or 1))
    current = max(0, int(actor.get("vitalidade", maximum) or 0))
    return min(1.0, current / maximum)


def _has_wounds(actor: dict, *categories: str) -> bool:
    wounds = actor.get("ferimentos") or {}
    selected = categories or ("leve", "grave", "critico")
    return any(wounds.get(category) for category in selected)


def _aid_rank(actor_id: str, actors_by_id: Dict[str, dict]) -> tuple:
    actor = actors_by_id[actor_id]
    wounds = actor.get("ferimentos") or {}
    return (
        0 if actor.get("estado_terminal") else 1,
        0 if actor.get("last_stand_pending") else 1,
        -len(wounds.get("critico", []) or []),
        -len(wounds.get("grave", []) or []),
        _vitality_ratio(actor),
        str(actor_id),
    )


def _aid_target(actor_id: str, sides: Dict[str, List[str]],
                actors_by_id: Dict[str, dict], predicate) -> Optional[str]:
    candidates = [
        ally_id
        for ally_id in _same_side_ids(actor_id, sides)
        if ally_id != actor_id
        and _available_for_aid(actors_by_id.get(ally_id))
        and predicate(ally_id, actors_by_id[ally_id])
    ]
    candidates.sort(key=lambda ally_id: _aid_rank(ally_id, actors_by_id))
    return candidates[0] if candidates else None


def derive_tactical_scene_state(scene: dict, actor_id: str,
                                actors_by_id: Dict[str, dict],
                                sides: Dict[str, List[str]]) -> dict:
    """Deriva os únicos gatilhos mecânicos aceitos pelos perfis fechados.

    IDs de alvo vêm de ``sides``/``actors_by_id``; flags livres de ``scene_state``
    nunca conseguem introduzir participantes ou forçar uma ação.
    """
    actor = actors_by_id.get(actor_id) or {}
    opposing_ids = _opposing_ids(actor_id, sides)
    target_id = _nearest_target(actor_id, opposing_ids, actors_by_id)
    vulnerable_ids = [
        target
        for target in opposing_ids
        if _alive(actors_by_id.get(target))
        and (
            _vitality_ratio(actors_by_id[target]) <= 0.5
            or _has_wounds(actors_by_id[target])
            or (
                (
                    ((scene.get("positions") or {}).get(target) or {})
                    .get("postura") or {}
                ).get("state") == "exposto"
            )
        )
    ]
    vulnerable_ids.sort(
        key=lambda target: (
            _vitality_ratio(actors_by_id[target]),
            str(target),
        ))
    vulnerable_id = vulnerable_ids[0] if vulnerable_ids else None
    terminal_id = _aid_target(
        actor_id, sides, actors_by_id,
        lambda _ally_id, ally: bool(ally.get("estado_terminal")),
    )
    wounded_id = _aid_target(
        actor_id, sides, actors_by_id,
        lambda _ally_id, ally: (
            _vitality_ratio(ally) < 1.0 or _has_wounds(ally)
        ),
    )
    danger_id = _aid_target(
        actor_id, sides, actors_by_id,
        lambda _ally_id, ally: (
            bool(ally.get("estado_terminal") or ally.get("last_stand_pending"))
            or _vitality_ratio(ally) <= 0.5
            or _has_wounds(ally, "grave", "critico")
        ),
    )
    available_id = _aid_target(
        actor_id, sides, actors_by_id,
        lambda ally_id, ally: (
            _can_act(ally)
            and not cs.has_tactical_modifier(
                scene, "attack_advantage", ally_id)
        ),
    )
    has_flank = bool(
        target_id and cs.is_hidden_from(scene, actor_id, target_id))
    same_side = _same_side_ids(actor_id, sides)
    peers = [ally_id for ally_id in same_side if ally_id != actor_id]
    alive_peers = [
        ally_id for ally_id in peers if _alive(actors_by_id.get(ally_id))
    ]
    engaged = set(
        ((scene.get("positions") or {}).get(actor_id) or {}).get(
            "engaged_with", []))
    surrounded = len(engaged & set(opposing_ids)) >= 2
    alone = not alive_peers
    pack_broken = bool(peers) and len(alive_peers) * 2 <= len(peers)
    badly_wounded = (
        _vitality_ratio(actor) <= 0.35
        or _has_wounds(actor, "grave", "critico")
    )
    return {
        "aliado_terminal": terminal_id is not None,
        "aliado_ferido": wounded_id is not None,
        "aliado_em_perigo": danger_id is not None,
        "aliado_disponivel": available_id is not None,
        "vitalidade_baixa": badly_wounded,
        "sem_flanco": target_id is not None and not has_flank,
        "controle_disponivel": (
            target_id is not None
            and cs.tactical_cooldown(scene, actor_id, "control") == 0
        ),
        # Vocabulário canônico dos 84 perfis curados do bestiário.
        "sozinho": alone,
        "muito_ferido": badly_wounded,
        "alvo_vulneravel": vulnerable_id is not None,
        "cercado": surrounded,
        "matilha_quebrada": pack_broken,
        "descoberto": target_id is not None and not has_flank,
        "plano_falhou": badly_wounded and (surrounded or alone),
        "_enemy_target": target_id,
        "_vulnerable_enemy_target": vulnerable_id,
        "_ally_terminal_target": terminal_id,
        "_ally_wounded_target": wounded_id,
        "_ally_danger_target": danger_id,
        "_ally_available_target": available_id,
    }


def enemy_declaration(scene: dict, actor_id: str, actors_by_id: Dict[str, dict],
                      sides: Dict[str, List[str]], *,
                      scene_state: Optional[dict] = None, rng=None) -> "ct.TurnDeclaration":
    """R1/R2 (08): decide o turno de um inimigo pela PRECEDÊNCIA do perfil tático,
    sem LLM. A mecânica usa ``action_key`` fechado; ``action_hint`` é somente
    apresentação. Default determinístico: ataque no alvo mais ameaçador."""
    actor = actors_by_id[actor_id]
    canonical = derive_tactical_scene_state(
        scene, actor_id, actors_by_id, sides)
    decision_state = dict(scene_state or {})
    decision_state.update(canonical)
    decision = tp.pick_action(
        actor.get("tactical_profile") or tp._default_profile(),
        decision_state,
    )
    explicit_action = decision.get("action_key")
    action_key = explicit_action or tp.legacy_action_key(
        decision.get("action_hint"))
    target = (
        canonical["_vulnerable_enemy_target"]
        if decision.get("trigger") == "alvo_vulneravel"
        and canonical["_vulnerable_enemy_target"] is not None
        else canonical["_enemy_target"]
    )
    taunted_target = _taunt_target(
        actor, _opposing_ids(actor_id, sides), actors_by_id, rng or random.Random())
    if taunted_target is not None:
        target = taunted_target

    if action_key == "control" and not canonical["controle_disponivel"]:
        action_key = "attack"
    if action_key == "flank" and not canonical["sem_flanco"]:
        action_key = "attack"

    if action_key == "surrender":
        actor["surrendered"] = True
        return ct.TurnDeclaration(actor_id=actor_id, acao=ct.TurnStep(kind="pass"))
    if action_key == "flee":
        if explicit_action == "flee":
            return ct.TurnDeclaration(
                actor_id=actor_id,
                acao=ct.TurnStep(kind="tactic", maneuver="flee"),
            )
        # Compatibilidade com perfil persistido pré-action_key.
        return ct.TurnDeclaration(
            actor_id=actor_id,
            acao=ct.TurnStep(kind="move", direction="afastar"))

    if target is None:
        return ct.TurnDeclaration(actor_id=actor_id, acao=ct.TurnStep(kind="pass"))

    tactical_target = {
        "protect": canonical["_ally_danger_target"],
        "stabilize": canonical["_ally_terminal_target"],
        "flank": target,
        "control": target,
        "support": (
            canonical["_ally_wounded_target"]
            if actor.get("tactical_archetype") == "suporte"
            else canonical["_ally_available_target"]
        ),
    }.get(action_key)
    if action_key in {"protect", "stabilize", "flank", "control", "support"}:
        if tactical_target is not None:
            return ct.TurnDeclaration(
                actor_id=actor_id,
                acao=ct.TurnStep(
                    kind="tactic",
                    maneuver=action_key,
                    target_id=tactical_target,
                ),
            )
        action_key = "attack"

    # Carta de inimigo (conflito-15: `cartas`) quando houver Entropia; senão ataque básico.
    card_id = _enemy_offensive_card(actor, scene=scene, actor_id=actor_id)
    step = ct.TurnStep(kind="card" if card_id else "attack",
                       card_id=card_id, target_id=target)
    return ct.TurnDeclaration(actor_id=actor_id, acao=step)


def _enemy_offensive_card(
    actor: dict, *, scene: Optional[dict] = None, actor_id: str = "",
) -> Optional[str]:
    """Primeira Carta de inimigo ofensiva utilizável (assinatura oculta da 15) —
    só id embutido na ficha; inimigo NÃO usa o Acervo do jogador."""
    from services import cards
    for card_id in cards.enemy_card_ids(actor):
        card = cards.get_card(card_id) or {}
        effect_kind = str((card.get("efeito") or {}).get("kind") or "")
        position = ((scene or {}).get("positions") or {}).get(actor_id) or {}
        # Esconder-se de novo enquanto já oculto não cria mudança mecânica e
        # pode bloquear o conflito para sempre (Mimetismo Morto da matriz A).
        if effect_kind == "esconder" and position.get("ocultacao") == "escondido":
            continue
        if cards.can_use_enemy_card(actor, card_id, expected_type="ativa"):
            return card_id
    return None


# ==========================================================================
# Ataque de Oportunidade + janela de Reação (06)
# ==========================================================================
def _declaration_leaves_engagement(decl: "ct.TurnDeclaration") -> bool:
    for slot in (decl.pre_acao, decl.acao, decl.pos_acao):
        if slot is None:
            continue
        if slot.kind == "move" and str(slot.direction or "").lower() in ("afastar", "away", "+"):
            return True
        if slot.kind == "tactic" and str(slot.maneuver or "").lower() == "flee":
            return True
        if slot.kind == "maneuver" and str(slot.maneuver or "").lower() == "mover" \
                and str(slot.direction or "").lower() in ("afastar", "away"):
            return True
    return False


def _resolve_opportunity_attacks(scene: dict, leaving_id: str, actors_by_id: Dict[str, dict],
                                 sides: Dict[str, List[str]], out: dict, rng) -> None:
    """R5 (06): abandonar Engajamento SEM Desengajar provoca AoO de cada inimigo
    Engajado, consciente e capaz — fora do limite de reação comum."""
    allies = [a for a in sides.get("hero", []) + sides.get("ally", [])] \
        if leaving_id in set(sides.get("hero", []) + sides.get("ally", [])) \
        else list(sides.get("enemy", []))
    aoos = rx.trigger_opportunity_attack(scene, leaving_id, allies=allies, stats_by_id=actors_by_id)
    for aoo in aoos:
        atk_id, tgt_id = aoo["attacker"], aoo["target"]
        attacker, target = actors_by_id.get(atk_id), actors_by_id.get(tgt_id)
        if not _alive(attacker) or not target:
            continue
        _basic_attack(scene, attacker, atk_id, target, tgt_id, out, rng,
                      label="Ataque de Oportunidade")


def _open_reaction_window(scene: dict, attacker_id: str, target_id: str,
                          actors_by_id: Dict[str, dict], sides: Dict[str, List[str]],
                          out: dict, state: Optional[dict] = None) -> None:
    """R1/R3 (06): abre a janela sobre o ataque declarado e deixa reatores do lado
    oposto oferecerem UMA reação COMUM (Carta de reação) — reação defensiva de
    Guarda entra na cena antes de o ataque resolver. Player só reage pela UI
    (conflito-16); aqui os reatores são inimigos com Carta de reação embutida."""
    declared = {"kind": "attack", "actor": attacker_id, "targets": [target_id]}
    chain = rx.open_reaction_window(declared)
    reactors = _opposing_ids(attacker_id, sides)
    ordered = rx.reaction_order(reactors, declared, stats_by_id=actors_by_id,
                               target_allies=reactors)
    for rid in ordered:
        reactor = actors_by_id.get(rid)
        if not _alive(reactor):
            continue
        player_id = _player_id(sides)
        selected_player_card = (
            state.get("_player_reaction_card_id") if state is not None else None
        )
        from services import cards
        if rid == player_id and selected_player_card:
            card = cards.get_card(str(selected_player_card))
            if (not card or card.get("tipo") != "reacao"
                    or str(selected_player_card) not in set(
                        reactor.get("prepared_cards") or [])):
                continue
        else:
            card = _enemy_reaction_card(reactor)
        if not card:
            continue
        if not rx.gatilho_matches(card, declared, rid):
            continue
        if rid == player_id:
            spent = cards.use_card(state or {"player": reactor}, card["id"])
        else:
            spent = cards.use_enemy_card(reactor, card["id"])
        if spent.get("ok") and rx.offer_reaction(
                chain, rid, card["id"], card=card, reactor=None):
            # Proteção limitada ao próximo ataque; não deixa Guarda persistente.
            cs.grant_tactical_modifier(scene, "protected", rid, rid)
    out.setdefault("reactions", []).extend(rx.resolve_chain(chain))


def _enemy_reaction_card(actor: dict) -> Optional[dict]:
    from services import cards
    for card_id in cards.enemy_card_ids(actor):
        if cards.can_use_enemy_card(actor, card_id, expected_type="reacao"):
            return cards.get_card(card_id)
    return None


def _basic_attack(scene: dict, attacker: dict, attacker_id: str, target: dict, target_id: str,
                  out: dict, rng, *, label: str = "Ataque",
                  advantage: int = 0) -> None:
    """Ataque básico determinístico (2d10+Virtude vs Esquiva → dano→Ferimento).
    Usado por AoO/reações que não passam pela declaração de turno."""
    advantage += cs.consume_tactical_attack_modifier(
        scene, attacker_id, target_id)
    atk = resolve_attack(
        attacker, target, virtude_key="forca",
        virtude_value_override=(
            virtude_value(attacker, "forca")
            + int(attacker.get("_env_attack_mod", 0) or 0)
        ),
        advantage=advantage, rng=rng)
    atk["actor_id"] = attacker_id
    atk["target_id"] = target_id
    out.setdefault("attacks", []).append(atk)
    out["logs"].append(f"{label}: {_name(attacker)} → {_name(target)}: "
                       f"{atk['resultado']} ({atk['total']} vs {atk['esquiva_alvo']}).")
    if atk["acerto"]:
        if attacker.get("dano_base_arma") is not None:
            dmg = max(0, int(attacker.get("dano_base_arma") or 0))
        else:
            formula = str(attacker.get("attack_formula") or "1d6")
            dmg, _ = cm.roll_dice_numeric(formula)
        if attacker_id == "player" or attacker.get("is_player"):
            dmg += cm.early_game_damage_bonus(
                int(attacker.get("level", 1) or 1))
        dres = resolve_damage_and_wounds(
            target,
            damage_base=max(0, dmg),
            damage_type="cortante",
            crit_mult=atk["efeito_principal_multiplicador"],
            directed_region=None,
            rng=rng,
        )
        atk["regiao"] = dres["regiao"]
        atk["dano_final"] = int(dres.get("dano_final", 0) or 0)
        out["logs"] += dres["log"]
        _post_hit(target, target_id, out, amount=atk["dano_final"])


# ==========================================================================
# Gatilhos de classe pós-golpe + Estado Terminal
# ==========================================================================
def _record_class_event(out: dict, kind: str, **details) -> None:
    out.setdefault("class_mechanics", []).append({"kind": kind, **details})


def _entropy_event(player: dict, event: dict, out: dict) -> None:
    before = (int(player.get("entropy", 0) or 0),
              int(player.get("abyss_charge", 0) or 0))
    cm.apply_entropy_trigger(player, event, out["logs"])
    after = (int(player.get("entropy", 0) or 0),
             int(player.get("abyss_charge", 0) or 0))
    if after != before:
        _record_class_event(
            out, f"entropy:{event['kind']}",
            entropy_delta=after[0] - before[0], charge_delta=after[1] - before[1],
        )


def _post_hit(target: dict, target_id: str, out: dict, *, amount: int = 0) -> None:
    """Gatilho de Entropia da classe do alvo (on_damage_taken) + checagem de Terminal."""
    if target.get("is_player"):
        _entropy_event(target, {"kind": "on_damage_taken", "amount": amount}, out)
        before = (int(target.get("entropy", 0) or 0),
                  int(target.get("_blood_entropy", 0) or 0))
        cm.apply_blood_leak(target, out["logs"])
        after = (int(target.get("entropy", 0) or 0),
                 int(target.get("_blood_entropy", 0) or 0))
        if after != before:
            _record_class_event(out, "special:blood_leak", entropy_delta=after[0] - before[0])
    _check_terminal(target, target_id, out, damage_applied=True)


def _apply_player_card_mechanics(player: dict, used: dict, player_id: str,
                                 out: dict, rng) -> None:
    """Liga marcadores autorais fechados da Carta aos helpers sobreviventes."""
    card = used.get("card") or {}
    mechanics = card.get("mecanica_classe") or {}
    self_harm = int(mechanics.get("auto_dano", 0) or 0)
    if self_harm:
        from services.conflict_damage import sacrifice_vitality
        before = int(player.get("vitalidade", 0) or 0)
        sacrifice_vitality(player, self_harm)
        out["logs"].append(
            f"{_name(player)} sacrifica {self_harm} Vitalidade pela Carta "
            f"(Vit {player.get('vitalidade', 0)}).")
        _record_class_event(out, "self_harm", amount=self_harm,
                            vitality_delta=int(player.get("vitalidade", 0) or 0) - before)
        _entropy_event(player, {"kind": "on_self_harm", "amount": self_harm}, out)
        _check_terminal(player, player_id, out, damage_applied=True)

    decay_kind = mechanics.get("decadencia")
    if decay_kind:
        _entropy_event(
            player, {"kind": "on_decay_nearby", "decay_kind": decay_kind}, out)

    if player.get("class_name") == "Arcanista Cinzento":
        _entropy_event(player, {"kind": "on_channel"}, out)
        before_deadline = player.get("_cool_deadline")
        cm.arm_boiler(player, {"cools": bool(mechanics.get("resfria_caldeira"))})
        after_deadline = player.get("_cool_deadline")
        if before_deadline != after_deadline:
            kind = "special:boiler_cooled" if after_deadline is None else "special:boiler_armed"
            _record_class_event(out, kind, deadline=after_deadline)

    economy = used.get("economy") or {}
    if economy.get("dependencia_applied"):
        _record_class_event(
            out, "consequence:dependencia",
            cost=int(economy.get("cost", 0) or 0),
            base_cost=int(economy.get("base_cost", 0) or 0),
        )
    if str((card.get("efeito") or {}).get("kind")) == "reduzir_carga_aliado":
        _record_class_event(out, "special:purga")

    before_scar = (int(player.get("vitalidade_max_penalty", 0) or 0),
                   int(player.get("abyss_charge", 0) or 0))
    cm.apply_scar(player, {"peak": bool(mechanics.get("pico"))}, out["logs"])
    after_scar = (int(player.get("vitalidade_max_penalty", 0) or 0),
                  int(player.get("abyss_charge", 0) or 0))
    if after_scar != before_scar:
        _record_class_event(out, "consequence:cicatriz",
                            max_vitality_penalty_delta=after_scar[0] - before_scar[0],
                            charge_delta=after_scar[1] - before_scar[1])


def _has_any_wound(target: dict) -> bool:
    fer = target.get("ferimentos") or {}
    return any(fer.get(c) for c in ("leve", "grave", "critico"))


def _mark_dead(target: dict, target_id: str, out: dict) -> None:
    target["dead"] = True
    target["status"] = "morto"
    if target_id not in out["deaths"]:
        out["deaths"].append(target_id)
    out["logs"].append(f"{_name(target)} é derrotado.")


def _check_terminal(target: dict, target_id: str, out: dict, *,
                    damage_applied: bool = False) -> None:
    """Traduz o estado de Ferimentos do alvo no desfecho da categoria (07 R7):
    Lacaio cai com qualquer Ferimento; Padrão ao encher o último Crítico; full-flow
    (jogador/Elite/Chefe/Nomeado/companheiro) dispara Última Ação → Estado Terminal."""
    if target.get("dead") or target.get("estado_terminal"):
        return
    if (damage_applied and death_flow.uses_full_death_flow(target)
            and death_flow.critical_spaces_full(target)
            and target.get("last_stand_resolved")):
        # Sobreviver ao fluxo terminal não concede imortalidade. O próximo dano
        # real com todos os espaços críticos ocupados encerra a vida; mera
        # passagem de rodada, sem dano, nunca dispara esta cláusula.
        _mark_dead(target, target_id, out)
        return
    if death_flow.minion_defeated_by_wound(target) and _has_any_wound(target):
        _mark_dead(target, target_id, out)
        return
    if death_flow.should_trigger_last_stand(target):
        death_flow.trigger_last_stand(target)
        if target_id not in out["terminal"]:
            out["terminal"].append(target_id)
        out["logs"].append(f"{_name(target)} prepara sua Última Ação!")
    elif not death_flow.uses_full_death_flow(target) and death_flow.critical_spaces_full(target):
        _mark_dead(target, target_id, out)


def _record_tactic(out: dict, actor_id: str, action_key: str, *,
                   target_id: Optional[str] = None, ok: bool,
                   detail: str = "") -> None:
    out.setdefault("tactics", []).append({
        "actor_id": actor_id,
        "action_key": action_key,
        "target_id": target_id,
        "ok": bool(ok),
        "detail": str(detail or "")[:160],
    })


def _resolve_tactical_action(scene: dict, actor: dict, actor_id: str,
                             actors_by_id: Dict[str, dict],
                             sides: Dict[str, List[str]], step,
                             out: dict, rng) -> None:
    """Executa somente o catálogo mecânico fechado dos perfis determinísticos."""
    action_key = str(step.maneuver or "")
    target_id = step.target_id
    target = actors_by_id.get(target_id) if target_id else None
    same_side = set(_same_side_ids(actor_id, sides))
    opposing = set(_opposing_ids(actor_id, sides))
    ok = False
    detail = ""

    if action_key == "protect":
        if target_id in same_side and target_id != actor_id and _available_for_aid(target):
            ok = cs.grant_tactical_modifier(
                scene, "protected", target_id, actor_id)
            detail = f"{_name(actor)} protege {_name(target)} no próximo ataque."
    elif action_key == "stabilize":
        if (target_id in same_side and target_id != actor_id and target
                and target.get("estado_terminal")):
            target["_tactical_stabilization_round"] = cs.tactical_round(scene)
            has_kit = bool(actor.get("has_kit") or actor.get("_has_kit"))
            is_medic = (
                actor.get("tactical_archetype") == "suporte"
                or "medic" in str(actor.get("class_name", "")).lower()
                or "médic" in str(actor.get("class_name", "")).lower()
            )
            result = death_flow.attempt_stabilization(
                target,
                actor,
                has_kit=has_kit,
                is_medico=is_medic,
                has_potion=False,
                rng=rng,
            )
            detail = result.get("log") or result.get("cause", "")
            ok = bool(result.get("revived"))
            if result.get("dead"):
                target["status"] = "morto"
                if target_id not in out["deaths"]:
                    out["deaths"].append(target_id)
            elif result.get("revived"):
                if target_id in out.get("terminal", []):
                    out["terminal"].remove(target_id)
                out.setdefault("scars_pending", []).append(target_id)
    elif action_key == "flank":
        if target_id in opposing and _alive(target):
            result = cs.hide(
                scene,
                actor_id,
                source="flanco tático",
                observers=[target_id],
                spend=False,
            )
            ok = bool(result.get("ok"))
            detail = result.get("log") or result.get("error", "")
    elif action_key == "control":
        if (target_id in opposing and _alive(target)
                and cs.tactical_cooldown(scene, actor_id, "control") == 0):
            detail = cm.apply_condition(target, {
                "name": "Controle tático",
                "dot": 0,
                # O controle nasce durante a rodada do Místico. Mantemos um
                # tick residual para que a condição continue observável até o
                # começo do próximo turno do alvo; consumíveis aplicados antes
                # da rodada continuam usando duration=1.
                "duration": 2,
                "source": actor_id,
                "control": "stun",
            })
            ok = "resiste" not in str(detail).lower()
            cs.set_tactical_cooldown(scene, actor_id, "control", 2)
    elif action_key == "support":
        if target_id in same_side and target_id != actor_id and _available_for_aid(target):
            if actor.get("tactical_archetype") == "suporte":
                before = int(target.get("vitalidade", 0) or 0)
                maximum = int(target.get("max_vitalidade", before) or before)
                target["vitalidade"] = min(maximum, before + 2)
                gamedata.sync_legacy_hp_aliases(target)
                restored = target["vitalidade"] - before
                ok = restored > 0
                detail = f"{_name(actor)} recupera {restored} Vitalidade de {_name(target)}."
            else:
                ok = cs.grant_tactical_modifier(
                    scene, "attack_advantage", target_id, actor_id)
                detail = f"{_name(actor)} coordena o próximo ataque de {_name(target)}."
    elif action_key == "flee":
        result = cs.move_distance(scene, actor_id, "afastar")
        ok = bool(result.get("ok"))
        detail = result.get("log") or result.get("error", "")
        if ok and result.get("distance_state") == "separado":
            actor["fled"] = True
            actor["status"] = "fugiu"
            detail = f"{detail} {_name(actor)} escapa do conflito."
    else:
        detail = f"Ação tática fora do catálogo: {action_key!r}."

    out["logs"].append(detail or f"{_name(actor)} não consegue executar {action_key}.")
    _record_tactic(
        out, actor_id, action_key, target_id=target_id, ok=ok, detail=detail)


# ==========================================================================
# Resolução do turno de um ator (compõe conflict_turn + reações + AoO)
# ==========================================================================
def _resolve_actor_turn(scene: dict, actor: dict, actor_id: str, actors_by_id: Dict[str, dict],
                        sides: Dict[str, List[str]], decl, state, out: dict, rng) -> None:
    decl = decl if isinstance(decl, ct.TurnDeclaration) else ct.TurnDeclaration(**decl)
    out.setdefault("resolved_turns", []).append(actor_id)

    # AoO ao abandonar Engajamento sem Desengajar (06 R5).
    if _declaration_leaves_engagement(decl):
        _resolve_opportunity_attacks(scene, actor_id, actors_by_id, sides, out, rng)
        if not _can_act(actor):
            return

    # Janela de Reação sobre um ataque declarado (06 R1) — reator define Guarda na cena.
    acao = decl.acao
    if acao is not None and acao.kind in ("attack", "card") and acao.target_id:
        _open_reaction_window(
            scene, actor_id, acao.target_id, actors_by_id, sides, out, state)

    if acao is not None and acao.kind == "tactic":
        cs.reset_turn_budget(scene, actor_id)
        _resolve_tactical_action(
            scene, actor, actor_id, actors_by_id, sides, acao, out, rng)
        return

    sub = ct.resolve_turn(scene, actors_by_id, decl, state=state, rng=rng)
    out["logs"] += [l for l in sub.get("logs", []) if l]
    out.setdefault("attacks", []).extend(sub.get("attacks", []))
    out.setdefault("cards_used", []).extend(sub.get("cards_used", []))
    for tid in sub.get("terminal", []):
        if tid not in out["terminal"]:
            out["terminal"].append(tid)
    for did in sub.get("deaths", []):
        if did not in out["deaths"]:
            out["deaths"].append(did)

    # Gatilhos de classe do JOGADOR a partir do que o turno produziu.
    player = actors_by_id.get(_player_id(sides))
    if player is not None:
        for used in sub.get("cards_used", []):
            if used.get("actor_id") == _player_id(sides):
                _apply_player_card_mechanics(
                    player, used, _player_id(sides) or actor_id,
                    out, rng,
                )

    # on_damage_taken: quem levou dano neste turno (alvos dos ataques que acertaram).
    for tid, amount in _hit_events(sub, decl):
        tgt = actors_by_id.get(tid)
        if tgt is None:
            continue
        if tgt.get("is_player"):
            _entropy_event(tgt, {"kind": "on_damage_taken", "amount": amount}, out)
            before = (int(tgt.get("entropy", 0) or 0),
                      int(tgt.get("_blood_entropy", 0) or 0))
            cm.apply_blood_leak(tgt, out["logs"])
            after = (int(tgt.get("entropy", 0) or 0),
                     int(tgt.get("_blood_entropy", 0) or 0))
            if after != before:
                _record_class_event(
                    out, "special:blood_leak", entropy_delta=after[0] - before[0])
        elif player is not None and tid in set(sides.get("hero", []) + sides.get("ally", [])):
            _entropy_event(player, {"kind": "on_ally_suffer"}, out)
        _check_terminal(tgt, tid, out, damage_applied=True)


def _hit_events(sub: dict, decl: "ct.TurnDeclaration") -> List[tuple[str, int]]:
    """Alvos acertados e dano mecânico final; preserva alvo legado da declaração."""
    fallback = decl.acao.target_id if decl.acao else None
    events: List[tuple[str, int]] = []
    for attack in sub.get("attacks", []):
        if not attack.get("acerto"):
            continue
        target_id = attack.get("target_id") or fallback
        if target_id:
            events.append((str(target_id), int(attack.get("dano_final", 0) or 0)))
    return events


def _player_id(sides: Dict[str, List[str]]) -> Optional[str]:
    return (sides.get("hero") or [None])[0]


def _find_player(actors_by_id: Dict[str, dict], sides: Dict[str, List[str]]) -> Optional[dict]:
    pid = _player_id(sides)
    p = actors_by_id.get(pid) if pid else None
    if p is not None and p.get("is_player"):
        return p
    for a in actors_by_id.values():
        if a.get("is_player"):
            return a
    return None


# ==========================================================================
# Estabilização do Estado Terminal (07, decisão R6=A)
# ==========================================================================
def resolve_terminals(actors_by_id: Dict[str, dict], sides: Dict[str, List[str]],
                      out: dict, *, scene: Optional[dict] = None, rng=None) -> None:
    """Cada ator em Estado Terminal resolve DENTRO do combate (R6=A): auto-reanima
    com Médico+kit/poção; senão um aliado consciente tenta estabilizar; sem aliado
    capaz ou 2 falhas = morte. Sobreviver marca Cicatriz (`scar_pending`). Só a morte
    REAL do jogador vira `player_dead` (o nó de combate abre a tela de morte)."""
    pending_ids = list(out.get("terminal", []))
    pending_ids.extend(
        actor_id for actor_id, actor in actors_by_id.items()
        if actor.get("estado_terminal") and actor_id not in pending_ids
    )
    for actor_id in pending_ids:
        target = actors_by_id.get(actor_id)
        if not target or not target.get("estado_terminal"):
            continue
        try:
            tactical_stabilization_round = int(
                target.get("_tactical_stabilization_round", -1))
        except (TypeError, ValueError):
            tactical_stabilization_round = -1
        if (scene is not None
                and tactical_stabilization_round == cs.tactical_round(scene)):
            # A ação tática já consumiu a tentativa desta rodada. Não rola uma
            # segunda estabilização automática sobre a mesma queda.
            continue
        helper = _stabilizer_for(actor_id, actors_by_id, sides)
        res = death_flow.attempt_stabilization(
            target, helper,
            has_kit=bool(target.get("_has_kit") or (helper or {}).get("has_kit")),
            is_medico="médico" in str((helper or {}).get("class_name", "")).lower()
                      or "medico" in str((helper or {}).get("class_name", "")).lower(),
            has_potion=bool(target.get("_has_stabilize_potion")), rng=rng)
        out.setdefault("stabilizations", []).append({"actor_id": actor_id, **res})
        if res.get("log"):
            out["logs"].append(res["log"])
        if res.get("dead"):
            target["status"] = "morto"
            if actor_id not in out["deaths"]:
                out["deaths"].append(actor_id)
            if target.get("is_player"):
                out["player_dead"] = True
        elif res.get("revived"):
            out.setdefault("scars_pending", []).append(actor_id)


def _resolve_last_stands(scene: dict, actors_by_id: Dict[str, dict],
                         sides: Dict[str, List[str]], out: dict, rng) -> None:
    """Executa cada Última Ação pendente uma única vez, antes do terminal.

    A semântica mínima determinística usa um ataque básico com vantagem extrema
    contra o alvo vivo mais próximo. Ela deliberadamente ignora custo de Carta,
    Entropia e Ferimentos, como exige o contrato da Última Ação.
    """
    out.setdefault("last_stands", [])
    cursor = 0
    while cursor < len(out.get("terminal", [])):
        actor_id = out["terminal"][cursor]
        cursor += 1
        actor = actors_by_id.get(actor_id)
        if (actor is None or actor.get("last_stand_resolved")
                or not actor.get("last_stand_pending")):
            continue
        target_id = _nearest_target(
            actor_id,
            _opposing_ids(actor_id, sides),
            actors_by_id,
        )
        out["logs"].append(f"{_name(actor)} executa sua Última Ação.")
        if target_id is not None:
            _basic_attack(
                scene,
                actor,
                actor_id,
                actors_by_id[target_id],
                target_id,
                out,
                rng,
                label="Última Ação",
                advantage=1,
            )
        else:
            out["logs"].append(f"{_name(actor)} não encontra alvo para a Última Ação.")
        death_flow.enter_terminal_state(actor)
        out["last_stands"].append(actor_id)
        # A Última Ação pode ter preenchido o Crítico de outro ator.
        for target in actors_by_id:
            candidate = actors_by_id[target]
            if death_flow.should_trigger_last_stand(candidate):
                death_flow.trigger_last_stand(candidate)
                if target not in out["terminal"]:
                    out["terminal"].append(target)


def _stabilizer_for(down_id: str, actors_by_id: Dict[str, dict],
                    sides: Dict[str, List[str]]) -> Optional[dict]:
    same_side = None
    for side, ids in sides.items():
        if down_id in ids:
            same_side = ids
            break
    for aid in (same_side or []):
        if aid == down_id:
            continue
        a = actors_by_id.get(aid)
        if _alive(a) and not a.get("estado_terminal"):
            return a
    return None


# ==========================================================================
# Evento do Abismo carregado por Cargas (10)
# ==========================================================================
def _maybe_abyss(scene: dict, player: dict, actors_by_id: Dict[str, dict],
                 prepared_abyss: Optional[List[dict]], out: dict, *,
                 scene_state: Optional[dict] = None, rng=None) -> None:
    if not prepared_abyss or player is None:
        return
    charges = int(player.get("abyss_charge", 0) or 0)
    event = abyss_events.select_event(prepared_abyss, scene_state or {}, charges,
                                      scene_objects=scene.get("objects"),
                                      seed=rng.random() if rng else None)
    if not event:
        return
    fired = abyss_events.trigger_event(event, scene_state or {})
    if not fired.get("ok"):
        return
    player["abyss_charge"] = max(0, charges - int(fired.get("cargas_gastas", 0) or 0))
    out["logs"].append(fired["log"])
    out.setdefault("abyss", []).append(fired.get("effect"))
    apply_effect_spec(
        scene, actors_by_id, fired.get("effect") or {}, out, rng=rng)


def apply_effect_spec(scene: dict, actors_by_id: Dict[str, dict], effect: dict,
                      out: dict, *, rng=None) -> None:
    """Aplica um EffectSpec do catálogo fechado (03/10). Cobre os kinds resolvíveis
    em combate; os puramente de cena (block_route/alter_terrain…) só se registram."""
    from services import encounter_preparation as prep
    materialized = prep.materialize_effect(
        effect,
        int(scene.get("encounter_level", 1) or 1),
        valid_targets=set(actors_by_id),
    )
    if materialized is None:
        out.setdefault("logs", []).append(
            "Efeito mecânico rejeitado: potência ou alvo inválido.")
        return
    kind = str(materialized.get("kind"))
    params = materialized.get("params") or {}
    if kind == "damage":
        tid = params.get("target")
        tgt = actors_by_id.get(tid)
        if tgt is not None:
            dres = resolve_damage_and_wounds(tgt, damage_base=int(params.get("amount", 1) or 1),
                                             damage_type=str(params.get("tipo", "abissal")),
                                             directed_region=None, rng=rng)
            out["logs"] += dres["log"]
            _check_terminal(tgt, tid, out, damage_applied=True)
    elif kind == "apply_condition":
        tid = params.get("target")
        tgt = actors_by_id.get(tid)
        if tgt is not None:
            tgt.setdefault("active_conditions", []).append(
                {"name": params.get("condition", "abissal"), "duration": int(params.get("duration", 1) or 1)})


# ==========================================================================
# Rodada completa
# ==========================================================================
def run_round(scene: dict, actors_by_id: Dict[str, dict], sides: Dict[str, List[str]],
              state: Optional[dict] = None, *, declarations: Optional[dict] = None,
              prepared_abyss: Optional[List[dict]] = None, scene_state: Optional[dict] = None,
              initiator: Optional[str] = None, rng=None) -> dict:
    """Resolve uma RODADA inteira. `sides` = {"hero":[ids], "ally":[ids], "enemy":[ids]}.
    `declarations[actor_id]` = TurnDeclaration do jogador/aliado controlado; inimigos
    sem declaração recebem uma via `enemy_declaration`. Retorna
    {logs, deaths, terminal, scars_pending, player_dead, ended, reason, initiative}."""
    rng = rng or random.Random()
    declarations = dict(declarations or {})
    out = {"logs": [], "deaths": [], "terminal": [], "abyss": [],
           "attacks": [], "reactions": [], "last_stands": [],
           "stabilizations": [],
           "resolved_turns": [], "tactics": [], "cards_used": [],
           "class_mechanics": [],
           "ended": False, "reason": "", "player_dead": False}
    # Dano externo resolvido imediatamente antes da rodada (por exemplo, clima
    # durante uma tentativa de fuga) pode já ter armado a Última Ação.
    # O orquestrador precisa adotar esse estado em vez de depender apenas de
    # eventos de dano produzidos dentro de ``run_round``.
    out["terminal"].extend(
        actor_id for actor_id, actor in actors_by_id.items()
        if actor.get("last_stand_pending")
    )
    cs.advance_tactical_state(scene)
    player = _find_player(actors_by_id, sides)
    player_id = _player_id(sides)
    player_decl = declarations.get(player_id) if player_id else None
    if player_decl is not None and not isinstance(player_decl, ct.TurnDeclaration):
        player_decl = ct.TurnDeclaration(**player_decl)
    selected_reaction = (
        player_decl.reaction_card_id if player_decl is not None else None
    )
    if state is not None:
        selected_reaction = selected_reaction or state.get("_player_reaction_card_id")
        state["_player_reaction_card_id"] = selected_reaction
    from services import cards
    for enemy_id in sides.get("enemy", []):
        enemy = actors_by_id.get(enemy_id)
        if enemy is not None:
            cards.reset_enemy_card_usage(enemy, "turno")

    # Mecânica de classe do jogador no início da rodada (SOBREVIVE).
    if player is not None:
        # Lista transitória compartilhada com o resultado; o harness a lê sem
        # depender de parsing da prosa/log e o próximo round a substitui.
        player["_last_class_mechanics"] = out["class_mechanics"]
        if state is not None:
            cards.reset_card_usage(state, "turno")
        cm.reset_entropy_turn(player)
        before_boiler = (player.get("_cool_deadline"),
                         int(player.get("vitalidade", player.get("hp", 0)) or 0))
        out["logs"] += cm.tick_boiler(player, rng=rng)
        after_boiler = (player.get("_cool_deadline"),
                        int(player.get("vitalidade", player.get("hp", 0)) or 0))
        if after_boiler != before_boiler:
            _record_class_event(
                out,
                "special:boiler_overload"
                if after_boiler[1] < before_boiler[1]
                else "special:boiler_tick",
                deadline=after_boiler[0],
                vitality_delta=after_boiler[1] - before_boiler[1],
            )
        conditions_before = len(player.get("active_conditions") or [])
        out["logs"] += cm.apply_transformacao(player)
        if len(player.get("active_conditions") or []) > conditions_before:
            _record_class_event(out, "consequence:transformacao")

    side_actors = {s: [actors_by_id[a] for a in ids if a in actors_by_id]
                   for s, ids in sides.items() if s in ("hero", "ally", "enemy")}
    # hero+ally agem como um lado só na iniciativa por lado (04).
    init_sides = {"heroes": [a for s in ("hero", "ally") for a in side_actors.get(s, [])],
                  "enemy": side_actors.get("enemy", [])}
    init = roll_initiative_by_side(init_sides, initiator=initiator, rng=rng)
    out["initiative"] = init["order"]
    seq: List[str] = []
    side_ids = {"heroes": sides.get("hero", []) + sides.get("ally", []),
                "enemy": sides.get("enemy", [])}
    for side in init["order"]:
        members = [aid for aid in side_ids.get(side, []) if _can_act(actors_by_id.get(aid, {}))]
        members.sort(key=lambda aid: (-_agility(actors_by_id[aid]), str(aid)))
        seq += members

    for actor_id in seq:
        actor = actors_by_id.get(actor_id)
        if actor is None or not _can_act(actor):
            continue
        # Controle é observado ANTES do tick: duration=1 precisa negar exatamente
        # esta ação e só então expirar. O fluxo anterior removia stun/sleep antes
        # de consultá-los, tornando consumíveis de controle mecanicamente inertes.
        stunned_this_turn = cm.has_control(actor, "stun")
        dot_applied = _tick_conditions_v4(actor, out, rng=rng)
        _check_terminal(actor, actor_id, out, damage_applied=dot_applied)
        if not _can_act(actor):
            continue
        if stunned_this_turn:
            out["logs"].append(f"{_name(actor)} está atordoado e perde o turno.")
            continue
        decl = declarations.get(actor_id)
        if decl is None:
            decl = enemy_declaration(scene, actor_id, actors_by_id, sides,
                                     scene_state=scene_state, rng=rng)
        _resolve_actor_turn(scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng)

    # Última Ação acontece fora da ordem, exatamente uma vez, ANTES do terminal.
    _resolve_last_stands(scene, actors_by_id, sides, out, rng)

    # Estabilização do Estado Terminal disparado nesta rodada (07, R6=A).
    resolve_terminals(actors_by_id, sides, out, scene=scene, rng=rng)

    # Fim de rodada: colheita de Entropia por morte + Recidiva + Abismo (jogador).
    if player is not None:
        out["logs"] += cm.apply_entropy_on_kill(player, len(out["deaths"]))
        _rec_logs, rec_ev = cm.check_recidiva(player)
        out["logs"] += _rec_logs
        if rec_ev:
            out["recidiva_event"] = rec_ev
            _record_class_event(out, "consequence:recidiva")
        _maybe_abyss(scene, player, actors_by_id, prepared_abyss, out,
                     scene_state=scene_state, rng=rng)

    end = death_flow.combat_should_end({"hostiles": side_actors.get("enemy", [])})
    out["ended"] = end["ended"]
    out["reason"] = end["reason"]
    return out
