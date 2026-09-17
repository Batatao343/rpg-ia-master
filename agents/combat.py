"""
agents/combat.py — Agente de Combate (conflito v2, pós-cutover conflito-13).

Arquitetura NOVA: a IA só PREPARA a cena (uma vez, antes) e NARRA (depois). A
resolução do conflito é 100% Python/determinística no motor novo
(`services/conflict_orchestrator.run_round`, que compõe as specs 03-12). ZERO LLM
durante a resolução — só a identificação da fala do jogador → `TurnDeclaration`
(tier CLASSIFY) e a narração final (tier FAST).

Fluxo de 1 chamada = 1 RODADA:
  (1º turno) preparar cena jogável → congelar → posicionar
  → identificar a ação do jogador (fala livre → TurnDeclaration)
  → run_round (iniciativa/ataques/dano→Ferimento/Reações/Terminal/Abismo)
  → espelhar Vitalidade→hp (HUD/checkpoints) → narrar → summary→loot na vitória.
"""
import random
import re
from typing import Dict, List, NamedTuple, Optional

import gamedata
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from state import GameState
from llm_setup import ModelTier, get_llm
from services import discovery as disc
from services import graph_resolver as gr
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_summary as summ
from services import death_flow
from services import encounter_preparation as prep
from services.conflict_turn import TurnDeclaration, TurnStep
from services.context_builder import build_context_pack
from agents.bestiary import generate_new_enemy
from pydantic import BaseModel, ConfigDict, Field

_PLAYER_ID = "player"


class FleeDecision(NamedTuple):
    """Resultado único de perseguição, compatível com o unpack legado."""

    escaped: bool
    logs: List[str]
    chase: dict

    @property
    def eligible(self) -> bool:
        return self.chase.get("eligible") is True and not self.chase.get("blocked_reason")


def _downed_identity_tokens(player: dict) -> list[str]:
    """All stable identities understood by ConflictSummary for the protagonist."""
    return list(dict.fromkeys(
        value for value in (
            _PLAYER_ID,
            str(player.get("id") or ""),
            str(player.get("name") or ""),
        ) if value
    ))
_MAX_SCANNER_TYPES = 8
_MAX_SCANNER_PER_TYPE = 12
_MAX_SCANNER_TOTAL = 24


# --- Schema de identificação de inimigos na cena (IA só identifica) ---
class EnemyIdentification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Nome singular do inimigo. Ex: 'Goblin'.")
    count: int = Field(
        ge=1,
        le=_MAX_SCANNER_PER_TYPE,
        description="Quantidade destes inimigos na cena.",
    )


class EncounterScanner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_enemies: List[EnemyIdentification] = Field(
        max_length=_MAX_SCANNER_TYPES)
    flavor_text: str = Field(description="Descrição curta da entrada dos inimigos em combate.")


# ==========================================================================
# Eventos canônicos de morte de inimigo (mantidos do motor antigo)
# ==========================================================================
def _canonical_enemy_id(enemy: Dict) -> Optional[str]:
    raw = (enemy.get("id") or "").strip()
    if not raw:
        return None
    base = re.sub(r"_\d+$", "", raw)
    for cand in (base, raw):
        ent = gr.get_entity(cand)
        if ent and ent.get("type") == "npc":
            return cand
    return None


def _kill_events(dead: List[Dict]) -> List[Dict]:
    kills = []
    for e in dead:
        cid = _canonical_enemy_id(e)
        if cid:
            kills.append({
                "type": "npc_killed", "actor_id": "player", "target_id": cid,
                "detail": f"{e.get('name', 'inimigo')} morto em combate",
                "payload": {}, "source": "combat",
            })
    return kills


def _last_human_text(messages: List) -> str:
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


# ==========================================================================
# Preparação da cena (ANTES do conflito — LLM identifica; guard obrigatório)
# ==========================================================================
def _bounded_enemy_groups(scan: EncounterScanner) -> List[tuple[str, int]]:
    """Normaliza/deduplica o scanner inteiro antes de chamar qualquer factory."""
    grouped: Dict[str, dict] = {}
    for ident in (scan.detected_enemies or [])[:_MAX_SCANNER_TYPES]:
        raw_name = (
            ident.get("name")
            if isinstance(ident, dict)
            else getattr(ident, "name", "")
        )
        name = " ".join(str(raw_name or "Inimigo").split()) or "Inimigo"
        key = name.casefold()
        raw_count = (
            ident.get("count", 1)
            if isinstance(ident, dict)
            else getattr(ident, "count", 1)
        )
        try:
            count = max(1, int(raw_count or 1))
        except (TypeError, ValueError):
            count = 1
        entry = grouped.setdefault(key, {"name": name, "count": 0})
        entry["count"] = min(
            _MAX_SCANNER_PER_TYPE,
            int(entry["count"]) + min(count, _MAX_SCANNER_PER_TYPE),
        )

    remaining = _MAX_SCANNER_TOTAL
    bounded: List[tuple[str, int]] = []
    for entry in grouped.values():
        if remaining <= 0:
            break
        count = min(int(entry["count"]), remaining)
        if count:
            bounded.append((str(entry["name"]), count))
            remaining -= count
    return bounded


def _spawn_v4_enemies(messages: List, target_hint: str, state: Optional[Dict]) -> tuple:
    """Identifica os inimigos da cena (LLM CLASSIFY) + bestiário + orçamento de
    encontro, e converte CADA um em ficha de combate v4 (`ensure_combat_sheet`).
    O bestiário curado (conflito-15) já traz v4; o gerador legado é adaptado."""
    print(f"⚡ [COMBAT] Preparando encontro. Dica: '{target_hint}'...")
    llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
    sys_prompt = (f"Analise a narrativa recente. O combate começou. Identifique QUAIS "
                  f"inimigos estão presentes e QUANTOS. Use a dica: '{target_hint}'. "
                  f"Ex.: 'Três orcs surgem' -> [{{name:'Orc', count:3}}].")
    enemies: List[Dict] = []
    flavor = "Algo hostil emerge."
    world = (state or {}).get("world") or {}
    encounter_level = prep.compute_encounter_level(
        location_danger=int(world.get("danger_level", 1) or 1),
        region_danger=int(world.get("danger_level", 1) or 1),
        event_type=str(world.get("encounter_type", "comum")),
        importance="comum",
    )
    mechanical_context = (
        f"{target_hint}; local={world.get('current_location', 'desconhecido')}; "
        f"nível_do_encontro={encounter_level}"
    )
    try:
        scan = llm.with_structured_output(EncounterScanner).invoke(
            [SystemMessage(content=sys_prompt)] + messages[-2:])
        if isinstance(scan, EncounterScanner):
            flavor = scan.flavor_text or flavor
            # Primeiro fecha tipos/contagens; somente depois toca bestiário/factory.
            groups = _bounded_enemy_groups(scan)
            next_instance_by_template: Dict[str, int] = {}
            for name, count in groups:
                template = generate_new_enemy(
                    name,
                    context=mechanical_context,
                    encounter_level=encounter_level,
                )
                base_id = str(template.get("id") or "enemy")
                for _ in range(count):
                    instance_number = next_instance_by_template.get(base_id, 0) + 1
                    next_instance_by_template[base_id] = instance_number
                    inst = dict(template)
                    inst["id"] = f"{base_id}_{instance_number}"
                    inst["name"] = (f"{template['name']} {instance_number}"
                                    if count > 1 else template["name"])
                    enemies.append(orch.ensure_combat_sheet(inst))
    except Exception as e:
        print(f"⚠️ [COMBAT SPAWN] {e}")

    if not enemies:
        enemies = [orch.ensure_combat_sheet(
            {"id": "sombrio_1", "name": "Inimigo Sombrio", "type": "padrao",
             "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1}})]

    # Orçamento determinístico do encontro (mesma lógica da Fase 4.6, escala nova).
    if state is not None:
        enemies, flavor = _apply_encounter_budget(enemies, state, flavor)
    return enemies, flavor


def _apply_encounter_budget(enemies: List[Dict], state: Dict, flavor: str) -> tuple:
    try:
        import encounter_budget as eb
        import party as party_mod
        from gamedata import get_location
        world = state.get("world") or {}
        danger = int(world.pop("encounter_eff_danger", None) or world.get("danger_level", 1) or 1)
        level = int((state.get("player") or {}).get("level", 1) or 1)
        enemy_refs = [str(value) for enemy in enemies
                      for value in (enemy.get("id"), enemy.get("name")) if value]
        n_allies = (len(party_mod.active_allies(state))
                    + len(party_mod.scene_allies(state, excluded=enemy_refs)))
        budget = eb.encounter_budget(level, danger, n_allies)
        enemies, cut = eb.clamp_encounter(enemies, budget, player_level=level)
        loc = get_location(world.get("current_location_id", "")) or {}
        enemies, fill = eb.fill_encounter(
            enemies, budget, loc, danger, turn=int(world.get("turn_count", 0) or 0),
            make_instance=lambda t, i: orch.ensure_combat_sheet(
                {**t, "id": f"{t.get('id', 'enemy')}_{i}"}))
        extra = " ".join(cut + fill)
        if extra:
            flavor = f"{flavor} {extra}".strip()
    except Exception as e:
        print(f"⚠️ [COMBAT BUDGET] {e}")
    return enemies, flavor


def _early_game_reaction_initiator(state: Dict, player: Dict,
                                   initiator: Optional[str]) -> Optional[str]:
    """Garante uma primeira decisão a herói novo e saudável fora de apex.

    [BALANCEAR] A baseline real encontrou mortes de nível 1–2 em emboscadas antes
    de qualquer janela de fuga/cura. Não reduz dano nem budget: quando o herói
    entra com Vitalidade cheia, somente a iniciativa do primeiro round é sua.
    Depois de agir (ou em apex), a iniciativa e a letalidade normais prevalecem.
    """
    level = int(player.get("level", 1) or 1)
    vitality = int(player.get("vitalidade", player.get("hp", 0)) or 0)
    maximum = int(player.get("max_vitalidade", player.get("max_hp", 0)) or 0)
    combat_round = int((state.get("combat") or {}).get("round", 0) or 0)
    world = state.get("world") or {}
    loc = gamedata.get_location(world.get("current_location_id", "")) or {}
    tags = {str(tag).casefold() for tag in (loc.get("tags") or [])}
    if (level <= 2 and maximum > 0 and vitality >= maximum
            and combat_round <= 1 and "apex" not in tags):
        return "heroes"
    return initiator


def _prepare_scene(state: Dict, enemies: List[Dict], player: Dict, allies: List[Dict]) -> dict:
    """Monta a cena JOGÁVEL em Python com zonas mínimas e seguras. O Nível do
    Encontro é perigo ABSOLUTO (11 R6), nunca depende da party."""
    world = state.get("world") or {}
    loc = world.get("current_location", "Campo")
    encounter_level = prep.compute_encounter_level(
        location_danger=int(world.get("danger_level", 1) or 1),
        region_danger=int(world.get("danger_level", 1) or 1),
        event_type=str(world.get("encounter_type", "comum")),
        importance="comum")
    ctx = {"location": loc, "enemies": enemies, "npcs": [],
           "encounter_level": encounter_level,
           "narrative": build_context_pack(state, query=str(loc),
                                           purpose="combat_narration", token_budget=600).world_state_block}
    # Mecânica é Python: geometria mínima e válida não precisa de um segundo
    # invoke FAST no primeiro turno. A LLM continua identificando e narrando.
    scene = prep.fallback_safe_scene(ctx)
    if not scene.get("zones"):
        scene["zones"] = [{"id": "z0", "name": loc, "connections": []}]
    scene["positions"] = {}
    zone_id = scene["zones"][0]["id"]
    cs.place(scene, _PLAYER_ID, zone_id=zone_id, distance_state="proximo")
    for a in allies:
        cs.place(scene, a.get("id") or a.get("name"), zone_id=zone_id, distance_state="proximo")
    for e in enemies:
        cs.place(scene, e["id"], zone_id=zone_id, distance_state="proximo")
    cs.freeze(scene)
    scene["encounter_level"] = encounter_level
    return scene


# ==========================================================================
# Identificação da ação do jogador (fala livre → TurnDeclaration, CLASSIFY)
# ==========================================================================
def _prepared_cards_catalog(player: Dict) -> str:
    from services import cards
    linhas = []
    for cid in (player.get("prepared_cards") or []):
        c = cards.get_card(cid)
        if not c:
            continue
        linhas.append(f"- {cid}: {c.get('name', cid)} | tipo {c.get('tipo')} | "
                      f"custo {c.get('custo_entropia', 0)} Entropia | {c.get('descricao', '')[:50]}")
    return "\n".join(linhas) or "- (nenhuma carta preparada; use ataque básico)"


def _usable_items_catalog(player: Dict) -> str:
    from gamedata import ARTIFACTS_DB
    from inventory import item_display
    lines = []
    for entry in player.get("inventory") or []:
        if not isinstance(entry, dict):
            continue
        item = ARTIFACTS_DB.get(entry.get("id", "")) or {}
        if str(item.get("type", "")).lower() not in ("consumable", "potion"):
            continue
        lines.append(f"- {entry.get('id')}: {item_display(entry)} (x{entry.get('qty', 1)})")
    return "\n".join(lines) or "- (nenhum consumível)"


def _default_card_target(card: Dict, enemy_id: Optional[str]) -> str:
    """Cartas benéficas sem alvo explícito afetam o próprio jogador. Evita que
    chips como Cura/Proteção herdem mecanicamente o primeiro inimigo."""
    friendly = {
        "cura", "estabilizar", "protecao", "reposicionar", "esconder",
        "purga_condicao", "vantagem", "buff_defesa", "buff_acerto", "buff_dano",
    }
    kind = str((card.get("efeito") or {}).get("kind") or "")
    return _PLAYER_ID if kind in friendly else (enemy_id or _PLAYER_ID)


def _parse_turn_declaration(player: Dict, enemies: List[Dict], intent: str,
                            scene: dict) -> TurnDeclaration:
    """A IA IDENTIFICA a fala do jogador → `TurnDeclaration` estruturada (só
    identifica, não resolve). Guard de fallback: ataque básico no 1º inimigo.
    O harness passa a declaração pronta e não chega aqui."""
    from pydantic import BaseModel, Field

    alvos = ", ".join(f"{e['id']}={e.get('name', e['id'])}" for e in enemies) or "—"
    fallback = TurnDeclaration(
        actor_id=_PLAYER_ID,
        acao=TurnStep(kind="attack", target_id=(enemies[0]["id"] if enemies else None)))
    if not intent:
        return fallback

    # Chips do HUD carregam nomes canônicos: resolvemos localmente, sem gastar
    # CLASSIFY e sem permitir id alucinado.
    from services import cards
    folded_intent = intent.casefold()
    target_id = enemies[0]["id"] if enemies else None
    for cid in (player.get("prepared_cards") or []):
        card = cards.get_card(cid)
        if card and str(card.get("name", "")).casefold() in folded_intent:
            return TurnDeclaration(
                actor_id=_PLAYER_ID,
                acao=TurnStep(kind="card", card_id=cid,
                              target_id=_default_card_target(card, target_id)))
    from gamedata import ARTIFACTS_DB
    from inventory import item_display
    for entry in (player.get("inventory") or []):
        if not isinstance(entry, dict):
            continue
        item = ARTIFACTS_DB.get(entry.get("id", "")) or {}
        name = item_display(entry)
        if str(item.get("type", "")).lower() in ("consumable", "potion") \
                and name.casefold() in folded_intent:
            return TurnDeclaration(
                actor_id=_PLAYER_ID,
                acao=TurnStep(kind="item", item_id=entry.get("id"), target_id=target_id))

    class PlayerMove(BaseModel):
        kind: str = Field(description="attack | card | item | maneuver | move | pass")
        card_id: str = Field(default="", description="id EXATO da Carta preparada, se kind=card.")
        item_id: str = Field(default="", description="id EXATO do consumível, se kind=item.")
        target_id: str = Field(default="", description="id do inimigo alvo (da lista).")
        maneuver: str = Field(default="", description="engajar|desengajar|guardar|esconder|procurar, se kind=maneuver.")
        direction: str = Field(default="", description="aproximar|afastar, se kind=move.")

    sys = SystemMessage(content=f"""
    Você IDENTIFICA a ação de combate do jogador (não resolva mecânica).
    Traduza a fala numa ação estruturada do conflito de Valoria.

    Cartas preparadas (use o id EXATO em card_id):
    {_prepared_cards_catalog(player)}

    Consumíveis presentes (use o id EXATO em item_id):
    {_usable_items_catalog(player)}

    Inimigos presentes (use o id em target_id): {alvos}

    Regras:
    - Ataque com arma comum -> kind=attack, target_id do alvo.
    - Usar uma Carta -> kind=card, card_id da Carta, target_id se ofensiva.
    - Beber/usar consumível -> kind=item, item_id do inventário, target_id se hostil.
    - Manobra tática (guardar/esconder/engajar/desengajar/procurar) -> kind=maneuver.
    - Mover (aproximar/afastar) -> kind=move + direction.
    - Sem alvo claro -> kind=attack no primeiro inimigo.
    """)
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
        res = llm.with_structured_output(PlayerMove).invoke([sys, HumanMessage(content=intent)])
        if isinstance(res, PlayerMove):
            kind = (res.kind or "attack").lower()
            tid = res.target_id or (enemies[0]["id"] if enemies else None)
            if kind == "card" and res.card_id in (player.get("prepared_cards") or []):
                card = cards.get_card(res.card_id) or {}
                return TurnDeclaration(actor_id=_PLAYER_ID,
                                       acao=TurnStep(
                                           kind="card", card_id=res.card_id,
                                           target_id=_default_card_target(card, tid)))
            if kind == "item" and res.item_id:
                return TurnDeclaration(actor_id=_PLAYER_ID,
                                       acao=TurnStep(kind="item", item_id=res.item_id,
                                                     target_id=tid))
            if kind == "maneuver" and res.maneuver:
                return TurnDeclaration(actor_id=_PLAYER_ID,
                                       acao=TurnStep(kind="maneuver", maneuver=res.maneuver, target_id=tid))
            if kind == "move" and res.direction:
                return TurnDeclaration(actor_id=_PLAYER_ID,
                                       acao=TurnStep(kind="move", direction=res.direction))
            if kind == "pass":
                return TurnDeclaration(actor_id=_PLAYER_ID, acao=TurnStep(kind="pass"))
            return TurnDeclaration(actor_id=_PLAYER_ID,
                                   acao=TurnStep(kind="attack", target_id=tid))
    except Exception as e:
        print(f"⚠️ [COMBAT PARSE] {e}")
    return fallback


# ==========================================================================
# Alias Vitalidade→hp (compatibilidade pública)
# ==========================================================================
def _mirror_vitals(actor: Dict) -> None:
    """Sincroniza apenas os aliases de borda e o status textual."""
    import gamedata
    gamedata.sync_legacy_hp_aliases(actor)
    if actor.get("dead"):
        actor["status"] = "morto"
    elif actor.get("fled"):
        actor["status"] = "fugiu"
    elif actor.get("surrendered"):
        actor["status"] = "rendido"
    else:
        actor.setdefault("status", "ativo")


def _canonical_player_action(declaration: Optional[TurnDeclaration], out: dict, *,
                             attempted: bool = True,
                             flee_requested: bool = False,
                             hero_fled: bool = False,
                             flee_destination_id: Optional[str] = None,
                             chase_state: Optional[dict] = None) -> dict:
    """Contrato mecânico consumido pelo harness; não depende da prosa do LLM."""
    step = declaration.acao if declaration is not None else None
    if flee_requested:
        kind = "flee"
        if hero_fled:
            result = "fled"
        elif (chase_state or {}).get("eligible") is False:
            result = "flee_blocked"
        elif chase_state and not chase_state.get("alcancado"):
            result = "flee_progress"
        else:
            result = "flee_failed"
    else:
        raw_kind = str((step.kind if step else "pass") or "pass").lower()
        kind = raw_kind if raw_kind in {
            "attack", "card", "item", "maneuver", "move", "pass", "flee",
        } else "pass"
        player_attack = next(
            (
                attack for attack in (out.get("attacks") or [])
                if attack.get("actor_id") == _PLAYER_ID
            ),
            None,
        )
        if kind in ("attack", "card") and player_attack is not None:
            result = "hit" if player_attack.get("acerto") else "miss"
        elif kind == "pass":
            result = "pass"
        elif not attempted:
            result = "interrupted"
        else:
            result = "ok"
    params = (step.params if step is not None else {}) or {}
    player_attack = next(
        (
            attack for attack in (out.get("attacks") or [])
            if attack.get("actor_id") == _PLAYER_ID
        ),
        {},
    )
    return {
        "kind": kind,
        "card_id": step.card_id if step is not None else None,
        "item_id": step.item_id if step is not None else None,
        "target_id": step.target_id if step is not None else None,
        "maneuver": step.maneuver if step is not None else None,
        "direction": step.direction if step is not None else None,
        "region": player_attack.get("regiao") or params.get("regiao"),
        "result": result,
        "attempted": bool(attempted),
        "flee_destination_id": flee_destination_id,
        "chase_track": (chase_state or {}).get("trilha") if flee_requested else None,
    }


MAX_CONSECUTIVE_FLEE_ATTEMPTS = 6


def _enforce_flee_attempt_limit(chase_state: dict, *, attempts: int) -> tuple[bool, dict]:
    """Fecha perseguições que oscilaram demais sem retirar letalidade do combate.

    O limite é local à instância e só é aplicado pelo chamador quando existe
    um destino de fuga válido. Até lá, cada rodada continua usando os testes
    normais da trilha.
    """
    chase = dict(chase_state or {})
    if chase.get("eligible") is False or chase.get("blocked_reason"):
        return False, chase
    if int(attempts or 0) < MAX_CONSECUTIVE_FLEE_ATTEMPTS:
        return bool(chase.get("escapou")), chase
    chase.update({"trilha": "escapou", "escapou": True, "alcancado": False})
    return True, chase


def _is_valid_flee_destination(state: Dict, destination_id: Optional[str]) -> bool:
    if not destination_id:
        return False
    current_id = str((state.get("world") or {}).get("current_location_id") or "")
    try:
        return any(
            str(location.get("id") or "") == str(destination_id)
            for location in gamedata.get_connections(current_id)
            if isinstance(location, dict)
        )
    except Exception:
        return False


# ==========================================================================
# Narração (depois da resolução — LLM FAST, guard)
# ==========================================================================
def _narrate_fall(player: Dict, logs: List[str], killer: str = "") -> str:
    quem = f" diante de {killer}" if killer else ""
    golpes = "\n".join(f"• {l}" for l in logs[-4:]) if logs else ""
    return (f"⚔️ {golpes}\n\n☠️ Você tomba{quem}. A escuridão te engole — mas a "
            f"Roda do Abismo ainda não decidiu. Voltar ao último respiro seguro, "
            f"ou aceitar o fim aqui?").strip()


def _narrate(player: Dict, enemies: List[Dict], logs: List[str],
             spawned_flavor: Optional[str], intent: str, victory: bool,
             world_ctx: str, aberturas: Optional[List[str]] = None) -> str:
    from services import prose_guard
    log_str = "\n".join(l for l in logs if l) or "Nada acontece."
    alive = [f"{e['name']} (Vit {e.get('vitalidade', 0)}/{e.get('max_vitalidade', 0)})"
             for e in enemies if e.get("status") == "ativo"]
    varie = prose_guard.openings_clause(aberturas or [])
    fecho = ("O combate foi VENCIDO — encerre com o respiro da vitória." if victory
             else "Termine com tensão e uma deixa para a próxima ação do jogador.")
    sys = SystemMessage(content=f"""
    <role>Narrador de Combate — Dark Fantasy</role>
    Descreva o round em 1-2 parágrafos, com base APENAS no log mecânico. Não invente
    dano nem resultado fora do log. Visceral, conciso. Ferimentos são localizados e
    permanentes; Vitalidade é fôlego/vigor. Use o CONTEXTO só para ambientar.

    {("ENTRADA: " + spawned_flavor) if spawned_flavor else ""}
    Ação do jogador: {intent}
    {world_ctx}
    <log_mecanico>
    {log_str}
    </log_mecanico>
    Herói: {player.get('name')} Vit {player.get('vitalidade')}/{player.get('max_vitalidade')}
    Inimigos ativos: {', '.join(alive) if alive else 'nenhum'}
    {fecho}{varie}
    """)
    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.FAST)
        if getattr(llm, "is_fallback", False):
            raise RuntimeError("fallback")
        res = llm.invoke([sys, HumanMessage(content=intent or "Continue o combate.")])
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        if text.strip():
            return text
    except Exception as e:
        print(f"⚠️ [COMBAT NARRATE] {e}")
    prefix = (spawned_flavor + "\n\n") if spawned_flavor else ""
    suffix = "\n\nVitória! O campo silencia." if victory else "\n\nO que você faz?"
    return f"⚔️ {prefix}" + "\n".join(f"• {l}" for l in logs if l) + suffix


# ==========================================================================
# NÓ PRINCIPAL
# ==========================================================================
def combat_node(state: GameState):
    messages = state.get("messages", [])
    if not messages:
        return {"next": "dm_router"}

    player = dict(state["player"])
    orch.ensure_combat_sheet(player, is_player=True)
    enemies = [orch.ensure_combat_sheet(dict(e)) for e in (state.get("enemies") or [])]
    combat_meta = dict(state.get("combat") or {})
    combat_target = state.get("combat_target", "Inimigos")
    turn = int(state.get("world", {}).get("turn_count", 0) or 0)
    bestiary_knowledge = dict(state.get("bestiary_knowledge") or {})
    bk_changed = False
    is_simulation = bool((state.get("combat_simulation") or {}).get("enabled"))

    if (not player.get("conscious", True)
            and not combat_meta.get("active")):
        return {
            "messages": [AIMessage(content=(
                "Você está inconsciente e não pode iniciar outro conflito. "
                "É preciso descansar ou receber tratamento primeiro."
            ))],
            "player": player,
            "enemies": [],
            "combat": {**combat_meta, "active": False, "scene": None},
            "combat_target": None,
            "next": None,
            "archive_due": False,
            "combat_declaration": None,
        }

    last_msg = messages[-1]
    is_start = isinstance(last_msg, SystemMessage) and "COMBAT START" in str(last_msg.content)
    scene = combat_meta.get("scene")
    spawned_flavor = None

    # ---- Preparação (1x): identifica inimigos + monta cena jogável + congela ----
    # Um encontro pode chegar aqui já com `enemies` preenchido (router, save v4,
    # testes/e2e). Nesse caso preservamos os combatentes e apenas construímos a
    # cena ausente; só pedimos spawn quando não há inimigo ativo.
    if is_start or not scene:
        import party as party_mod
        party = party_mod.backfill_party(state.get("party") or [])
        if not [e for e in enemies if e.get("status") == "ativo" and not e.get("dead")]:
            enemies, spawned_flavor = _spawn_v4_enemies(messages, combat_target, state)
        enemy_refs = [str(value) for enemy in enemies
                      for value in (enemy.get("id"), enemy.get("name")) if value]
        if combat_target:
            enemy_refs.append(str(combat_target))
        allies = [orch.ensure_combat_sheet(dict(a)) for a in party if a.get("active")] \
            + [orch.ensure_combat_sheet(dict(a)) for a in
               party_mod.scene_allies(state, excluded=enemy_refs)]
        scene = _prepare_scene(state, enemies, player, allies)
        bestiary_knowledge = disc.record_encounter(bestiary_knowledge, enemies, turn)
        bk_changed = True
        from services.combat_origin import materialize
        continuity = state.get("continuity") or {}
        conflict_instance_id = ":".join((
            str(state.get("game_id") or "game"),
            str(int(continuity.get("timeline_epoch", 0) or 0)),
            str(int(continuity.get("session_action_count", turn) or turn)),
        ))
        combat_meta = {"round": 0, "active": True, "scene": scene, "idle_turns": 0,
                       "origin": materialize(combat_meta, state.get("combat_origin_hint")),
                       "instance_id": conflict_instance_id,
                       "encounter_level": scene.get("encounter_level", 1)}
        print(f"⚔️ Combate: {[e['name'] for e in enemies]}")

    active = [e for e in enemies if e.get("status") == "ativo" and not e.get("dead")]
    if not active:
        import party as party_mod
        party = party_mod.backfill_party(state.get("party") or [])
        enemy_refs = [str(value) for enemy in enemies
                      for value in (enemy.get("id"), enemy.get("name")) if value]
        scene_tr = (combat_meta.get("scene_allies")
                    or party_mod.scene_allies(state, excluded=enemy_refs))
        allies = [orch.ensure_combat_sheet(dict(a)) for a in party if a.get("active")] \
            + [orch.ensure_combat_sheet(dict(a)) for a in scene_tr]
        # Saves legados podem ter somente o status textual. O summary precisa das
        # flags canônicas usadas por build_summary.
        for participant in enemies + allies:
            status = str(participant.get("status") or "").lower()
            if status == "morto":
                participant["dead"] = True
                participant["conscious"] = False
            elif status == "fugiu":
                participant["fled"] = True
            elif status == "rendido":
                participant["surrendered"] = True
        conflict_sum = summ.build_summary(
            [player] + enemies + allies,
            scene=scene,
            extras={"turn": turn, "conflict_id": combat_meta.get("instance_id")},
        )
        combat_meta["last_player_action"] = _canonical_player_action(
            None, {}, attempted=False)
        return {"messages": [AIMessage(content="O silêncio retorna ao campo. Vitória.")],
                "next": "loot", "combat_target": None, "enemies": [],
                "conflict_summary": conflict_sum,
                "combat": {
                    **combat_meta,
                    "active": False,
                    "round": combat_meta.get("round", 0),
                    "scene": None,
                },
                "archive_due": True}

    # ---- Montagem dos lados + declaração do jogador ----
    import party as party_mod
    party = party_mod.backfill_party(state.get("party") or [])
    enemy_refs = [str(value) for enemy in enemies
                  for value in (enemy.get("id"), enemy.get("name")) if value]
    scene_tr = (combat_meta.get("scene_allies")
                or party_mod.scene_allies(state, excluded=enemy_refs))
    allies = [orch.ensure_combat_sheet(dict(a)) for a in party if a.get("active")] \
        + [orch.ensure_combat_sheet(dict(a)) for a in scene_tr]
    player["_party_active"] = bool(allies)
    ally_ids = [a.get("id") or a.get("name") for a in allies]

    actors_by_id: Dict[str, dict] = {_PLAYER_ID: player}
    for e in enemies:
        actors_by_id[e["id"]] = e
    for a in allies:
        actors_by_id[a.get("id") or a.get("name")] = a
    sides = {"hero": [_PLAYER_ID], "ally": ally_ids,
             "enemy": [e["id"] for e in active]}

    intent = _last_human_text(messages)
    declaration = state.get("combat_declaration")   # harness passa estruturado
    if declaration is not None and not isinstance(declaration, TurnDeclaration):
        declaration = TurnDeclaration(**declaration)

    # ---- Fuga: chase determinístico (conflito-09) ----
    flee_dest_id = None
    flee_requested = bool(re.search(r"\bfuj|fugir|escap|retir|recu|corr[oe]\b", intent.lower()))
    if (declaration is not None and declaration.acao is not None
            and declaration.acao.kind == "flee"):
        flee_requested = True
        flee_dest_id = declaration.acao.params.get("destination_id")
    if state.get("combat_flee_attempt"):
        flee_requested = True
        flee_dest_id = state.get("combat_flee_destination")

    if flee_requested:
        combat_meta["flee_attempts"] = int(
            combat_meta.get("flee_attempts", 0) or 0
        ) + 1
    else:
        # O teto mede tentativas consecutivas dentro deste conflito.
        combat_meta.pop("flee_attempts", None)

    combat_meta["round"] = int(combat_meta.get("round", 0)) + 1
    combat_meta["active"] = True
    combat_meta["idle_turns"] = 0
    combat_meta["scene_allies"] = scene_tr
    # RNG = módulo global (semeado pelo harness/persistência) → reprodutível por seed.
    rng = random

    hero_fled = False
    logs: List[str] = []
    world_out = None
    world = state.get("world") or {}
    from world_utils import (DARK_COMBAT_PENALTY, light_level,
                             weather_effects)
    weather_fx = weather_effects(world)
    light_fx = light_level(world, player)
    weather_attack = int(weather_fx.get("combat_attack_mod", 0) or 0)
    hero_light_attack = int(light_fx.get("combat_mod", 0) or 0)
    enemy_light_attack = (
        DARK_COMBAT_PENALTY if light_fx.get("natural_dark") else 0
    )
    player["_env_attack_mod"] = weather_attack + hero_light_attack
    for ally in allies:
        ally["_env_attack_mod"] = weather_attack + hero_light_attack
    for enemy in active:
        enemy["_env_attack_mod"] = weather_attack + enemy_light_attack
    surprise = world.get("encounter_surprise")
    initiator = "heroes" if surprise == "player" else ("enemy" if surprise == "enemy" else None)
    initiator = _early_game_reaction_initiator(state, player, initiator)
    if "encounter_surprise" in world:
        world_out = dict(world)
        world_out.pop("encounter_surprise", None)
    weather_logs = _apply_weather_hazard(player, world, rng=rng)
    _register_environmental_damage_terminal(player, weather_logs)
    resolved_decl: Optional[TurnDeclaration] = declaration
    flee_allowed = _can_attempt_flee(player)
    if flee_requested and flee_allowed:
        hero_fled, flee_logs, chase_state = _attempt_flee(
            scene, player, active, sides, rng,
            existing_chase=combat_meta.get("chase"))
        if (not hero_fled
                and _is_valid_flee_destination(state, flee_dest_id)):
            hero_fled, chase_state = _enforce_flee_attempt_limit(
                chase_state,
                attempts=int(combat_meta.get("flee_attempts", 0) or 0),
            )
            if hero_fled:
                flee_logs.append(
                    "Após uma perseguição prolongada, os inimigos perdem o rastro."
                )
        combat_meta["chase"] = chase_state
        logs += weather_logs + flee_logs
    elif flee_requested:
        chase_state = {
            **dict(combat_meta.get("chase") or {}),
            "eligible": False, "blocked_reason": "lifecycle",
        }
        combat_meta["chase"] = chase_state
        logs += weather_logs + [
            "Sua condição atual impede iniciar a fuga; a rodada resolve sua recuperação."
        ]
    if not hero_fled:
        if flee_requested:
            # A tentativa falhou, mas consumiu a Ação do protagonista. Inimigos
            # ainda resolvem a rodada; não há parse secundário nem ataque oculto.
            decl = TurnDeclaration(
                actor_id=_PLAYER_ID,
                acao=TurnStep(kind="pass"),
            )
        else:
            decl = (
                declaration
                if declaration is not None and declaration.acao is not None
                else _parse_turn_declaration(player, active, intent, scene)
            )
        resolved_decl = decl
        # alvo inválido (inimigo já caiu / declaração pré-computada) → 1º inimigo ativo
        if decl.acao and decl.acao.kind == "attack" and \
                decl.acao.target_id not in {e["id"] for e in active}:
            decl.acao.target_id = active[0]["id"]
        elif decl.acao and decl.acao.kind == "card":
            from services import cards
            declared_card = cards.get_card(decl.acao.card_id or "") or {}
            expected = _default_card_target(declared_card, active[0]["id"])
            valid_ids = set(actors_by_id)
            if decl.acao.target_id not in valid_ids:
                decl.acao.target_id = expected
        round_state = {
            "player": player,
            "_player_reaction_card_id": state.get("player_reaction_card_id"),
        }
        out = orch.run_round(scene, actors_by_id, sides, round_state,
                             declarations={_PLAYER_ID: decl},
                             prepared_abyss=scene.get("abyss_events"),
                             initiator=initiator, rng=rng)
        logs += weather_logs + out["logs"]
        # Gasto BRUTO da economia da Carta. O delta líquido antes/depois era
        # incorreto para classes cujo próprio uso repõe Entropia no mesmo turno.
        player_cards = [
            used for used in (out.get("cards_used") or [])
            if used.get("actor_id") == _PLAYER_ID
        ]
        player["_last_entropy_spent"] = sum(
            int((used.get("economy") or {}).get("cost", 0) or 0)
            for used in player_cards
        )
        player["_last_used_active"] = bool(player_cards)
        player["_last_ability_id"] = (
            player_cards[-1].get("card_id") if player_cards else None
        )
    else:
        out = {
            "deaths": [],
            "ended": True,
            "player_dead": False,
            "scars_pending": [],
            "reason": "fuga",
            "recidiva_event": None,
            "attacks": [],
            "reactions": [],
            "resolved_turns": [_PLAYER_ID],
        }

    last_player_action = _canonical_player_action(
        resolved_decl,
        out,
        attempted=(
            hero_fled
            or flee_requested
            or _PLAYER_ID in (out.get("resolved_turns") or [])
        ),
        flee_requested=flee_requested,
        hero_fled=hero_fled,
        flee_destination_id=flee_dest_id,
        chase_state=chase_state if flee_requested else None,
    )

    # ---- Espelho de vitais + Cicatrizes obrigatórias ----
    _mirror_vitals(player)
    for e in enemies:
        _mirror_vitals(e)
    for ally in allies:
        _mirror_vitals(ally)
    for sid in out.get("scars_pending", []):
        if sid == _PLAYER_ID and death_flow.check_scar_required(player):
            llm = get_llm(temperature=0.6, tier=ModelTier.SMART)
            death_flow.generate_scar(player, llm)

    dead = [e for e in enemies if e.get("dead") or e.get("status") == "morto"]
    if dead:
        bestiary_knowledge = disc.record_kills(bestiary_knowledge, dead, turn)
        bk_changed = True

    player_dead = bool(out.get("player_dead")) or bool(player.get("dead"))
    combat_over = bool(out.get("ended")) or hero_fled or player_dead
    if combat_over and not player_dead:
        for participant in [player] + allies:
            recovery_state = death_flow.post_combat_consciousness(participant)
            participant["post_combat_state"] = recovery_state
            if recovery_state == "inconsciente":
                participant["conscious"] = False
            elif recovery_state == "acordado":
                participant["conscious"] = True
    victory = combat_over and not player_dead and not hero_fled and bool(dead)

    # ---- XP determinístico (fugitivo/queda letal não contam) ----
    level_up_events: List[Dict] = []
    if dead and not player_dead and not is_simulation:
        import progression as pg
        xp = pg.xp_for_kills(dead)
        if xp:
            player, level_up_events = pg.grant_xp(player, xp)
            logs.append(f"+{xp} XP" + (f" — NÍVEL {player['level']}!" if level_up_events else ""))

    # ---- Narração ----
    from services import prose_guard
    aberturas = prose_guard.ultimas_aberturas(messages)
    loc = state.get("world", {}).get("current_location", "")
    if player_dead:
        killer = next((e.get("name") for e in active), "")
        narrative = _narrate_fall(player, logs, killer)
    elif is_simulation:
        suffix = "\n\nVitória no laboratório." if victory else "\n\nEscolha a próxima ação."
        narrative = "⚔️ " + "\n".join(f"• {line}" for line in logs if line) + suffix
    else:
        world_pack = build_context_pack(state, query=f"{loc} {intent}",
                                        purpose="combat_narration", token_budget=1200)
        narrative = _narrate(player, enemies, logs, spawned_flavor, intent, victory,
                             world_pack.world_state_block, aberturas)
    # ---- Resumo canônico do conflito (conflito-12) na saída ----
    conflict_sum = None
    if combat_over:
        participants = [player] + enemies + allies
        conflict_sum = summ.build_summary(
            participants,
            scene=scene,
            extras={
                "turn": turn,
                "conflict_id": combat_meta.get("instance_id"),
                # Player saves historically do not persist ``id``. Carry both
                # the canonical role and the runtime display identity so the
                # summary cannot downgrade a recoverable fall into death.
                "downed_ids": (
                    _downed_identity_tokens(player)
                    if player_dead else []
                ),
            },
        )
        narrative = summ.narrative_or_fallback(conflict_sum, narrative)
    narrative = prose_guard.sanitize_meta_preamble(narrative)
    prose_guard.log_if_repeats(
        narrative, aberturas[0] if aberturas else "", where="combate")

    # ---- Montagem do resultado (contrato preservado) ----
    combat_meta["active"] = not combat_over
    combat_meta["initiative"] = list(out.get("initiative") or [])
    combat_meta["last_player_action"] = last_player_action
    combat_meta["last_reactions"] = list(out.get("reactions") or [])
    combat_meta["last_tactics"] = list(out.get("tactics") or [])
    if combat_over:
        from services import cards
        cards.reset_card_usage({"player": player}, "cena")
        combat_meta["scene"] = None
        combat_meta.pop("scene_allies", None)
    result = {
        "messages": [AIMessage(content=narrative)],
        "player": player,
        "enemies": [] if combat_over else enemies,
        "combat": combat_meta,
        "combat_target": None if combat_over else combat_target,
        "next": "loot" if victory and not is_simulation else None,
        "archive_due": combat_over and not is_simulation,
        "party": _merge_formal_party(party, allies),
        "combat_declaration": None,   # consumida (não vaza para o próximo turno)
        "combat_origin_hint": None,
    }
    if conflict_sum is not None:
        result["conflict_summary"] = conflict_sum
    if world_out is not None:
        result["world"] = world_out
    if bk_changed:
        result["bestiary_knowledge"] = bestiary_knowledge

    # ---- Reflexo dos aliados transitórios no NPC de origem ----
    if scene_tr:
        result["npcs"] = _reflect_scene_allies(state, scene_tr, allies, combat_over)

    # ---- Eventos de mundo (kills canônicas + level up + morte do jogador) ----
    engine_events = [] if is_simulation else _kill_events(dead) + level_up_events
    if out.get("recidiva_event"):
        engine_events.append(out["recidiva_event"])

    death_events = []
    if player_dead:
        stabilization = next((entry for entry in reversed(out.get("stabilizations") or [])
                              if entry.get("actor_id") == _PLAYER_ID), {})
        combat_meta["death_context"] = {
            "last_action": last_player_action,
            "entered_terminal": bool(
                _PLAYER_ID in (out.get("terminal") or [])
                or _PLAYER_ID in (out.get("last_stands") or [])
            ),
            "stabilization": stabilization.get("cause") or stabilization.get("log", ""),
            "stabilization_attempts": int(
                stabilization.get("attempts", player.get("stabilization_attempts", 0)) or 0
            ),
            "killer": next((e.get("name") for e in active), ""),
        }
        result["death_pending"] = True
        result["combat"] = {**combat_meta, "active": False, "scene": None}
        result["enemies"] = []
        result["combat_target"] = None
        result["next"] = None
        result["archive_due"] = not is_simulation
        killer = next((e.get("name") for e in active), "")
        death_events.append({
            "type": "player_downed", "actor_id": "player", "target_id": "player",
            "detail": f"{player.get('name', 'O herói')} tombou em combate"
                      + (f" diante de {killer}" if killer else ""),
            "payload": {"killer": killer, "location": loc,
                        "boss_present": any(str(e.get("categoria", "")).lower() in ("chefe", "nomeado")
                                            for e in enemies)},
            "source": "combat"})
    if not is_simulation:
        engine_events += death_events
    if engine_events:
        result["pending_world_events"] = (state.get("pending_world_events", []) or []) + engine_events

    # ---- Fuga bem-sucedida → viagem no mesmo turno + reset de cena ----
    if hero_fled and flee_dest_id:
        _apply_flee_travel(state, result, flee_dest_id, player, logs)
    if state.get("combat_flee_attempt"):
        result["combat_flee_attempt"] = False
        result["combat_flee_destination"] = None
    result["player_reaction_card_id"] = None

    return result


# ===========================================================================
# Fuga (chase, conflito-09) + reflexos auxiliares
# ===========================================================================
def _can_attempt_flee(player: Dict) -> bool:
    """Fuga exige protagonista em fase capaz de iniciar uma perseguição."""
    return bool(player.get("conscious", True)) \
        and not bool(player.get("dead")) \
        and not bool(player.get("estado_terminal")) \
        and not bool(player.get("last_stand_pending")) \
        and not bool(player.get("incapacitated"))


def _attempt_flee(scene: dict, player: Dict, active: List[Dict], sides: dict, rng,
                  *, existing_chase: Optional[dict] = None) -> FleeDecision:
    """Tenta escapar via motor de perseguição (09). Enredado (root) não foge.
    Sucesso na trilha (Escapou) encerra o combate; senão o herói segue preso."""
    import combat_mechanics as cm
    from services import chase
    from services.conflict_resolution import virtude_value
    if not _can_attempt_flee(player):
        return FleeDecision(False, [
            f"{player.get('name', 'O herói')} está em Estado Terminal e não pode fugir."
        ], {"eligible": False, "blocked_reason": "lifecycle"})
    if cm.has_control(player, "root"):
        return FleeDecision(False, [f"{player.get('name', 'O herói')} está ENREDADO — impossível fugir."], {
            "eligible": False,
            "blocked_reason": "rooted",
        })
    chase_state = (
        dict(existing_chase)
        if chase.can_resume(existing_chase, _PLAYER_ID, active)
        else chase.start_chase(scene, _PLAYER_ID, active)
    )
    previous_track = chase_state.get("trilha")
    difficulty = chase.chase_difficulty(active[0]) if active else 12
    chase.resolve_chase_round(chase_state, condutor_virtude=virtude_value(player, "agilidade"),
                              difficulty=difficulty, rng=rng)
    chase_state["eligible"] = True
    if chase_state.get("escapou"):
        return FleeDecision(True, [f"{player.get('name', 'O herói')} rompe o cerco e FOGE do combate."], chase_state)
    if chase_state.get("alcancado"):
        log = f"{player.get('name', 'O herói')} tenta fugir, mas os inimigos o alcançam."
    elif (chase_state.get("_last") or {}).get("sucesso"):
        log = (f"{player.get('name', 'O herói')} avança na fuga: "
               f"{previous_track} → {chase_state.get('trilha')}.")
    else:
        log = (f"{player.get('name', 'O herói')} perde terreno na fuga: "
               f"{previous_track} → {chase_state.get('trilha')}.")
    return FleeDecision(False, [log], chase_state)


def _apply_weather_hazard(player: Dict, world: Dict, *, rng=None) -> List[str]:
    """Clima continua mecânico no conflito v2. Dano ambiental exterior reduz
    Vitalidade (não HP d20); o espelho para HP é feito no fim da rodada."""
    from world_utils import weather_effects
    effects = weather_effects(world)
    dot = int(effects.get("dot_outdoor", 0) or 0)
    if dot <= 0:
        return []
    from services.conflict_damage import resolve_damage_and_wounds
    result = resolve_damage_and_wounds(
        player,
        damage_base=dot,
        damage_type="arcano",
        ignore_resistance=True,
        defensavel=False,
        directed_region=None,
        rng=rng,
    )
    label = effects.get("label") or world.get("weather", "") \
        or world.get("weather_state", "clima hostil")
    return [
        f"{player.get('name', 'O herói')} sofre {dot} pelo clima ({label}) "
        f"(Vitalidade {player['vitalidade']}).",
        *result["log"],
    ]


def _register_environmental_damage_terminal(player: Dict, damage_logs: List[str]) -> None:
    """Fia dano pré-rodada ao mesmo fluxo terminal usado pelos ataques.

    O clima é resolvido antes da perseguição. Sem este gate, um herói podia
    preencher o último Crítico e ainda concluir a fuga, deixando um estado vivo
    impossível fora do combate.
    """
    if not damage_logs or not death_flow.critical_spaces_full(player):
        return
    if player.get("last_stand_resolved"):
        player["dead"] = True
        player["status"] = "morto"
        player["vitalidade"] = 0
        gamedata.sync_legacy_hp_aliases(player)
        return
    if death_flow.should_trigger_last_stand(player):
        death_flow.trigger_last_stand(player)


def _apply_flee_travel(state: Dict, result: Dict, flee_dest_id: str, player: Dict,
                       logs: List[str]) -> None:
    import world_utils as wu
    from gamedata import get_location
    from services import npc_layers
    dest = get_location(flee_dest_id)
    if not dest:
        return
    base_world = result.get("world") or wu.ensure_world(dict(state.get("world") or {}))
    result["world"] = wu.apply_travel(base_world, dest)
    base_npcs = result.get("npcs")
    if base_npcs is None:
        base_npcs = state.get("npcs", {})
    result["npcs"] = npc_layers.reset_scene(base_npcs)
    previous_combat = result.get("combat") or {}
    result["combat"] = {
        "active": False,
        "round": int(previous_combat.get("round", 0) or 0),
        "idle_turns": 0,
        "scene": None,
        "origin": "unknown",
        # Recibo do turno atual: o harness o consome uma vez a partir do update
        # do nó. Não é estado de perseguição e preserva a auditabilidade.
        "last_player_action": dict(
            previous_combat.get("last_player_action") or {}
        ),
    }
    result["enemies"] = []
    result["combat_target"] = None
    result["next"] = None
    result["needs_replan"] = True
    result["combat_origin_hint"] = None


def _reflect_scene_allies(state: Dict, scene_tr: List[Dict], allies: List[Dict],
                          combat_over: bool) -> Dict:
    """Aliado TRANSITÓRIO reflete Vitalidade/morte no NPC de origem (sem 'aliado
    imortal'). Não vira party permanente."""
    npcs_out = {**(state.get("npcs") or {})}
    by_name = {(a.get("name") or a.get("id")): a for a in allies}
    for tr in scene_tr:
        name = tr.get("name") or ""
        key = next((k for k in npcs_out if k == name
                    or (isinstance(npcs_out[k], dict) and npcs_out[k].get("name") == name)), None)
        if key is None or not isinstance(npcs_out.get(key), dict):
            continue
        live = by_name.get(name) or tr
        npc = {**npcs_out[key]}
        npc["vitalidade"] = int(live.get("vitalidade", 0) or 0)
        npc["max_vitalidade"] = int(live.get("max_vitalidade", 1) or 1)
        import gamedata
        gamedata.sync_legacy_hp_aliases(npc)
        if live.get("dead") or live.get("status") == "morto":
            npc["status"] = "morto"
            npc["in_scene"] = False
        npcs_out[key] = npc
    return npcs_out


def _merge_formal_party(party: List[Dict], live_allies: List[Dict]) -> List[Dict]:
    """Persiste a ficha v4 mutada dos companheiros formais (transitórios ficam fora)."""
    live_by_id = {
        str(a.get("id") or a.get("name")): a
        for a in live_allies
        if not a.get("transient")
    }
    merged: List[Dict] = []
    for companion in party:
        key = str(companion.get("id") or companion.get("name"))
        live = dict(live_by_id.get(key) or companion)
        _mirror_vitals(live)
        merged.append(live)
    return merged
