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
    if not actor.get("max_vitalidade"):
        actor["max_vitalidade"] = gamedata.vitalidade_para_corpo(corpo)
    if actor.get("vitalidade") is None:
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
    if is_player:
        actor["is_player"] = True
    else:
        cat = _CATEGORIA_ALIAS.get(str(actor.get("categoria") or "").strip().lower())
        if not cat:
            cat = _CATEGORIA_ALIAS.get(str(actor.get("type") or "").strip().lower(), "padrao")
        actor["categoria"] = cat if cat in _KNOWN_CATEGORIAS else "padrao"
        actor.setdefault("tactical_profile", tp._default_profile())
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
    return _alive(actor) and not actor.get("estado_terminal")


def _agility(actor: dict) -> int:
    return virtude_value(actor, "agilidade")


def _apply_dot_v4(target: dict, dot: int, dtype: str, out: dict) -> None:
    """DoT do motor NOVO: reduz Vitalidade; excedente vira Ferimento localizado (05).
    Sangramento/veneno ignoram armadura (dano contínuo interno)."""
    from services.conflict_damage import apply_wound
    vit = int(target.get("vitalidade", 0) or 0)
    exc = max(0, int(dot) - vit)
    target["vitalidade"] = max(0, vit - int(dot))
    if exc > 0:
        corpo = int((target.get("virtudes") or {}).get("corpo", 0) or 0)
        cat = gamedata.categoria_ferimento(corpo, exc)
        if cat:
            apply_wound(target, cat, "torso")


def _tick_conditions_v4(actor: dict, out: dict) -> None:
    """Versão v4 de `tick_conditions`: aplica DoT em Vitalidade (não em hp), decrementa
    duração e remove condições expiradas. Substitui `cm.tick_conditions` (que ticava
    hp do motor antigo) no loop novo."""
    survivors: List[dict] = []
    for c in actor.get("active_conditions", []) or []:
        dot = int(c.get("dot", 0) or 0)
        if dot > 0:
            _apply_dot_v4(actor, dot, str(c.get("source") or "cortante"), out)
            out["logs"].append(
                f"{_name(actor)} sofre {dot} de {c.get('name', 'condição')} "
                f"(Vit {actor.get('vitalidade', 0)}).")
        c["duration"] = int(c.get("duration", 0)) - 1
        if c["duration"] > 0:
            survivors.append(c)
        else:
            out["logs"].append(f"{_name(actor)}: {c.get('name', 'condição')} terminou.")
    actor["active_conditions"] = survivors


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


def enemy_declaration(scene: dict, actor_id: str, actors_by_id: Dict[str, dict],
                      sides: Dict[str, List[str]], *,
                      scene_state: Optional[dict] = None, rng=None) -> "ct.TurnDeclaration":
    """R1/R2 (08): decide o turno de um inimigo pela PRECEDÊNCIA do perfil tático,
    sem LLM. Traduz o `action_hint` em uma `TurnDeclaration` estruturada. Default
    determinístico: ataque básico no alvo mais ameaçador do lado oposto."""
    actor = actors_by_id[actor_id]
    decision = tp.pick_action(actor.get("tactical_profile") or tp._default_profile(),
                              scene_state or {})
    hint = str(decision.get("action_hint") or "").lower()
    target = _nearest_target(actor_id, _opposing_ids(actor_id, sides), actors_by_id)

    # rendição/fuga determinística tem precedência (o perfil já decidiu)
    if any(w in hint for w in ("rende", "implora", "rendi")):
        actor["surrendered"] = True
        return ct.TurnDeclaration(actor_id=actor_id, acao=ct.TurnStep(kind="pass"))
    if any(w in hint for w in ("foge", "fugir", "recua", "escapa")):
        return ct.TurnDeclaration(
            actor_id=actor_id,
            acao=ct.TurnStep(kind="move", direction="afastar"))

    if target is None:
        return ct.TurnDeclaration(actor_id=actor_id, acao=ct.TurnStep(kind="pass"))

    # Carta de inimigo (conflito-15: `cartas`) quando houver Entropia; senão ataque básico.
    card_id = _enemy_offensive_card(actor)
    step = ct.TurnStep(kind="card" if card_id else "attack",
                       card_id=card_id, target_id=target)
    return ct.TurnDeclaration(actor_id=actor_id, acao=step)


def _enemy_offensive_card(actor: dict) -> Optional[str]:
    """Primeira Carta de inimigo ofensiva utilizável (assinatura oculta da 15) —
    só id embutido na ficha; inimigo NÃO usa o Acervo do jogador."""
    for c in (actor.get("cartas") or actor.get("enemy_cards") or []):
        if isinstance(c, dict) and c.get("tipo") not in ("reacao", "passiva"):
            cid = c.get("id")
            custo = int(c.get("custo_entropia", 0) or 0)
            if cid and custo <= int(actor.get("entropy", 0) or 0):
                return cid
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
                          actors_by_id: Dict[str, dict], sides: Dict[str, List[str]]) -> None:
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
        card = _enemy_reaction_card(reactor)
        if not card:
            continue
        if rx.offer_reaction(chain, rid, card["id"], card=card, reactor=reactor):
            # Reação de Guarda: entra na cena (Desvantagem no atacante) antes de resolver.
            if scene.get("positions", {}).get(rid):
                cs.guard(scene, rid, spend=False)
    rx.resolve_chain(chain)


def _enemy_reaction_card(actor: dict) -> Optional[dict]:
    for c in (actor.get("cartas") or actor.get("enemy_cards") or []):
        if isinstance(c, dict) and c.get("tipo") == "reacao":
            if int(c.get("custo_entropia", 0) or 0) <= int(actor.get("entropy", 0) or 0):
                return c
    return None


def _basic_attack(scene: dict, attacker: dict, attacker_id: str, target: dict, target_id: str,
                  out: dict, rng, *, label: str = "Ataque") -> None:
    """Ataque básico determinístico (2d10+Virtude vs Esquiva → dano→Ferimento).
    Usado por AoO/reações que não passam pela declaração de turno."""
    atk = resolve_attack(attacker, target, virtude_key="forca", rng=rng)
    out["logs"].append(f"{label}: {_name(attacker)} → {_name(target)}: "
                       f"{atk['resultado']} ({atk['total']} vs {atk['esquiva_alvo']}).")
    if atk["acerto"]:
        formula = str(attacker.get("attack_formula") or "1d6")
        dmg, _ = cm.roll_dice_numeric(formula)
        dres = resolve_damage_and_wounds(target, damage_base=max(0, dmg), damage_type="cortante",
                                         crit_mult=atk["efeito_principal_multiplicador"])
        out["logs"] += dres["log"]
        _post_hit(target, target_id, out)


# ==========================================================================
# Gatilhos de classe pós-golpe + Estado Terminal
# ==========================================================================
def _post_hit(target: dict, target_id: str, out: dict) -> None:
    """Gatilho de Entropia da classe do alvo (on_damage_taken) + checagem de Terminal."""
    if target.get("is_player"):
        cm.apply_entropy_trigger(target, {"kind": "on_damage_taken"}, out["logs"])
    _check_terminal(target, target_id, out)


def _has_any_wound(target: dict) -> bool:
    fer = target.get("ferimentos") or {}
    return any(fer.get(c) for c in ("leve", "grave", "critico"))


def _mark_dead(target: dict, target_id: str, out: dict) -> None:
    target["dead"] = True
    target["status"] = "morto"
    if target_id not in out["deaths"]:
        out["deaths"].append(target_id)
    out["logs"].append(f"{_name(target)} é derrotado.")


def _check_terminal(target: dict, target_id: str, out: dict) -> None:
    """Traduz o estado de Ferimentos do alvo no desfecho da categoria (07 R7):
    Lacaio cai com qualquer Ferimento; Padrão ao encher o último Crítico; full-flow
    (jogador/Elite/Chefe/Nomeado/companheiro) dispara Última Ação → Estado Terminal."""
    if target.get("dead") or target.get("estado_terminal"):
        return
    if death_flow.minion_defeated_by_wound(target) and _has_any_wound(target):
        _mark_dead(target, target_id, out)
        return
    if death_flow.should_trigger_last_stand(target):
        death_flow.trigger_last_stand(target)
        death_flow.enter_terminal_state(target)
        if target_id not in out["terminal"]:
            out["terminal"].append(target_id)
        out["logs"].append(f"{_name(target)} entra em Estado Terminal!")
    elif not death_flow.uses_full_death_flow(target) and death_flow.critical_spaces_full(target):
        _mark_dead(target, target_id, out)


# ==========================================================================
# Resolução do turno de um ator (compõe conflict_turn + reações + AoO)
# ==========================================================================
def _resolve_actor_turn(scene: dict, actor: dict, actor_id: str, actors_by_id: Dict[str, dict],
                        sides: Dict[str, List[str]], decl, state, out: dict, rng) -> None:
    decl = decl if isinstance(decl, ct.TurnDeclaration) else ct.TurnDeclaration(**decl)

    # AoO ao abandonar Engajamento sem Desengajar (06 R5).
    if _declaration_leaves_engagement(decl):
        _resolve_opportunity_attacks(scene, actor_id, actors_by_id, sides, out, rng)

    # Janela de Reação sobre um ataque declarado (06 R1) — reator define Guarda na cena.
    acao = decl.acao
    if acao is not None and acao.kind in ("attack", "card") and acao.target_id:
        _open_reaction_window(scene, actor_id, acao.target_id, actors_by_id, sides)

    sub = ct.resolve_turn(scene, actors_by_id, decl, state=state, rng=rng)
    out["logs"] += [l for l in sub.get("logs", []) if l]
    for tid in sub.get("terminal", []):
        if tid not in out["terminal"]:
            out["terminal"].append(tid)
    for did in sub.get("deaths", []):
        if did not in out["deaths"]:
            out["deaths"].append(did)

    # Gatilhos de classe do JOGADOR a partir do que o turno produziu.
    player = actors_by_id.get(_player_id(sides))
    # on_damage_taken: quem levou dano neste turno (alvos dos ataques que acertaram).
    for tid in _hit_targets(sub, decl):
        tgt = actors_by_id.get(tid)
        if tgt is None:
            continue
        if tgt.get("is_player"):
            cm.apply_entropy_trigger(tgt, {"kind": "on_damage_taken"}, out["logs"])
        elif player is not None and tid in set(sides.get("hero", []) + sides.get("ally", [])):
            cm.apply_entropy_trigger(player, {"kind": "on_ally_suffer"}, out["logs"])
        _check_terminal(tgt, tid, out)


def _hit_targets(sub: dict, decl: "ct.TurnDeclaration") -> List[str]:
    tid = decl.acao.target_id if decl.acao else None
    hits = [a for a in sub.get("attacks", []) if a.get("acerto")]
    return [tid] if (tid and hits) else []


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
                      out: dict, *, rng=None) -> None:
    """Cada ator em Estado Terminal resolve DENTRO do combate (R6=A): auto-reanima
    com Médico+kit/poção; senão um aliado consciente tenta estabilizar; sem aliado
    capaz ou 2 falhas = morte. Sobreviver marca Cicatriz (`scar_pending`). Só a morte
    REAL do jogador vira `player_dead` (o nó de combate abre a tela de morte)."""
    for actor_id in list(out.get("terminal", [])):
        target = actors_by_id.get(actor_id)
        if not target or not target.get("estado_terminal"):
            continue
        helper = _stabilizer_for(actor_id, actors_by_id, sides)
        res = death_flow.attempt_stabilization(
            target, helper,
            has_kit=bool(target.get("_has_kit") or (helper or {}).get("has_kit")),
            is_medico="médico" in str((helper or {}).get("class_name", "")).lower()
                      or "medico" in str((helper or {}).get("class_name", "")).lower(),
            has_potion=bool(target.get("_has_stabilize_potion")), rng=rng)
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
    apply_effect_spec(scene, actors_by_id, fired.get("effect") or {}, out)


def apply_effect_spec(scene: dict, actors_by_id: Dict[str, dict], effect: dict, out: dict) -> None:
    """Aplica um EffectSpec do catálogo fechado (03/10). Cobre os kinds resolvíveis
    em combate; os puramente de cena (block_route/alter_terrain…) só se registram."""
    if not cs.validate_effect_kind(effect):
        return
    kind = str(effect.get("kind"))
    params = effect.get("params") or {}
    if kind == "damage":
        tid = params.get("target")
        tgt = actors_by_id.get(tid)
        if tgt is not None:
            dres = resolve_damage_and_wounds(tgt, damage_base=int(params.get("amount", 1) or 1),
                                             damage_type=str(params.get("tipo", "abissal")))
            out["logs"] += dres["log"]
            _check_terminal(tgt, tid, out)
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
           "ended": False, "reason": "", "player_dead": False}
    player = _find_player(actors_by_id, sides)

    # Mecânica de classe do jogador no início da rodada (SOBREVIVE).
    if player is not None:
        cm.reset_entropy_turn(player)
        out["logs"] += cm.tick_boiler(player)
        out["logs"] += cm.apply_transformacao(player)

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
        _tick_conditions_v4(actor, out)
        _check_terminal(actor, actor_id, out)   # DoT pode ter derrubado/aberto Terminal
        if not _can_act(actor):
            continue
        if cm.has_control(actor, "stun"):
            out["logs"].append(f"{_name(actor)} está atordoado e perde o turno.")
            continue
        decl = declarations.get(actor_id)
        if decl is None:
            decl = enemy_declaration(scene, actor_id, actors_by_id, sides,
                                     scene_state=scene_state, rng=rng)
        _resolve_actor_turn(scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng)

    # Estabilização do Estado Terminal disparado nesta rodada (07, R6=A).
    resolve_terminals(actors_by_id, sides, out, rng=rng)

    # Fim de rodada: colheita de Entropia por morte + Recidiva + Abismo (jogador).
    if player is not None:
        out["logs"] += cm.apply_entropy_on_kill(player, len(out["deaths"]))
        _rec_logs, rec_ev = cm.check_recidiva(player)
        out["logs"] += _rec_logs
        if rec_ev:
            out["recidiva_event"] = rec_ev
        _maybe_abyss(scene, player, actors_by_id, prepared_abyss, out,
                     scene_state=scene_state, rng=rng)

    end = death_flow.combat_should_end({"hostiles": side_actors.get("enemy", [])})
    out["ended"] = end["ended"]
    out["reason"] = end["reason"]
    return out
