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

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

import combat_mechanics as cm
import gamedata
from agents.bestiary import generate_new_enemy
from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_summary as summ
from services import death_flow
from services import discovery as disc
from services import encounter_preparation as prep
from services import graph_resolver as gr
from services.conflict_turn import _SUPPORT_EFFECTS, TurnDeclaration, TurnStep
from services.context_builder import build_context_pack
from state import GameState

_PLAYER_ID = "player"


class FleeDecision(NamedTuple):
    """Resultado único de perseguição, compatível com o unpack legado."""

    escaped: bool
    logs: list[str]
    chase: dict

    @property
    def eligible(self) -> bool:
        return self.chase.get("eligible") is True and not self.chase.get("blocked_reason")


def _downed_identity_tokens(player: dict) -> list[str]:
    """All stable identities understood by ConflictSummary for the protagonist."""
    return list(
        dict.fromkeys(
            value
            for value in (
                _PLAYER_ID,
                str(player.get("id") or ""),
                str(player.get("name") or ""),
            )
            if value
        )
    )


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

    detected_enemies: list[EnemyIdentification] = Field(max_length=_MAX_SCANNER_TYPES)
    flavor_text: str = Field(description="Descrição curta da entrada dos inimigos em combate.")


# ==========================================================================
# Eventos canônicos de morte de inimigo (mantidos do motor antigo)
# ==========================================================================
def _canonical_enemy_id(enemy: dict) -> str | None:
    raw = (enemy.get("id") or "").strip()
    if not raw:
        return None
    base = re.sub(r"_\d+$", "", raw)
    for cand in (base, raw):
        ent = gr.get_entity(cand)
        if ent and ent.get("type") == "npc":
            return cand
    return None


def _kill_events(dead: list[dict]) -> list[dict]:
    kills = []
    for e in dead:
        cid = _canonical_enemy_id(e)
        if cid:
            kills.append(
                {
                    "type": "npc_killed",
                    "actor_id": "player",
                    "target_id": cid,
                    "detail": f"{e.get('name', 'inimigo')} morto em combate",
                    "payload": {},
                    "source": "combat",
                }
            )
    return kills


def _mark_nonlethal(decl: TurnDeclaration, intent: str) -> None:
    """SPEC-325 R9: golpe do jogador declarado não-letal (texto ou chip) vira
    `params["nao_letal"]`. O orquestrador decide o efeito conforme a flag
    (`shadow` só registra, `on` incapacita). Inimigo nunca declara não-letal."""
    from services import combat_flags
    from services.combat_intents import nonlethal_declared

    step = decl.acao
    if step is None or step.kind not in ("attack", "card"):
        return
    if combat_flags.mode("nonlethal") == "off":
        return
    if step.params.get("nao_letal") or nonlethal_declared(intent):
        step.params["nao_letal"] = True


def _reveal_resistances(attacks: list[dict], enemies: list[dict], sides: dict) -> None:
    """SPEC-325 R8: imunidade/resistência/vulnerabilidade só é revelada depois de
    agir num golpe do herói/aliado contra inimigo (regra de ouro). `shadow` só
    registra. No perfil `legacy` persiste no bestiário (fail-closed como
    `_sync_enemy_knowledge`)."""
    import os

    from services import bestiary_knowledge as bk
    from services import combat_flags

    mode = combat_flags.mode("reveal_resist")
    if mode == "off":
        return
    friendly = set(sides.get("hero", [])) | set(sides.get("ally", []))
    by_id = {str(e.get("id") or e.get("name")): e for e in enemies if isinstance(e, dict)}
    shared = os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() == "legacy"
    for atk in attacks:
        hit = atk.get("resistance_hit")
        enemy = by_id.get(str(atk.get("target_id") or ""))
        if not hit or enemy is None or atk.get("actor_id") not in friendly:
            continue
        entry = f"{hit['type']}:{hit['effect']}"
        if entry in (enemy.get("revealed_resistances") or []):
            continue
        if mode == "shadow":
            _log_event("combat", "reveal_resist_shadow", effect=str(hit["effect"]))
            continue
        try:
            if shared:
                bk.reveal_resistance(enemy, entry)
            else:
                enemy.setdefault("revealed_resistances", []).append(entry)
        except Exception:  # revelação é cosmética: nunca derruba o turno
            _log_event("combat", "enemy_knowledge_failed", level="warning")
        else:
            _log_event("combat", "reveal_resist", effect=str(hit["effect"]))


def _chase_is_live(chase: object) -> bool:
    """Perseguição em andamento (não terminal, elegível) — base das escolhas da Fase B."""
    from services import chase as chase_mod

    return (
        isinstance(chase, dict)
        and chase.get("eligible") is not False
        and not chase.get("blocked_reason")
        and not chase.get("alcancado")
        and not chase.get("escapou")
        and chase.get("trilha") in chase_mod.TRACK[:-1]
    )


def _chase_attack_gate(combat_meta: dict, decl: TurnDeclaration) -> str:
    """SPEC-325 R11: ataque do jogador com perseguição ativa. À distância segue; corpo a
    corpo em `pressionado` fecha a trilha (combate normal); em `afastado`/`quase_livre` é
    RECUSADO (devolve o motivo, sem gastar a rodada). `shadow` só registra."""
    from services import cards, combat_flags
    from services import chase as chase_mod
    from services import conflict_turn as ct

    mode = combat_flags.mode("chase_attack")
    step = decl.acao
    chase = combat_meta.get("chase")
    if mode == "off" or step is None or step.kind not in ("attack", "card"):
        return ""
    if not _chase_is_live(chase):
        return ""
    card = cards.get_card(step.card_id or "") if step.card_id else None
    melee = ct._is_melee(card, step)
    verdict = chase_mod.chase_attack(dict(chase), melee=melee)
    if mode == "shadow":
        _log_event(
            "combat",
            "chase_attack_shadow",
            mode=str(verdict["mode"]),
            allowed=bool(verdict["allowed"]),
        )
        return ""
    if not verdict["allowed"]:
        _log_event("combat", "chase_attack_refused", level="info")
        return (
            "Corpo a corpo é impossível enquanto os inimigos estão a distância: "
            "reduza a distância antes ou ataque de longe."
        )
    if verdict["ends_chase"]:
        combat_meta.pop("chase", None)
        _log_event("combat", "chase_attack_reengage", level="info")
    return ""


def _soul_traits(state: dict, member: dict) -> list[str]:
    from services import companion_soul as cs_

    _key, row = cs_.npc_row(state, member)
    return [
        str(t) for t in [*(row.get("hidden_traits") or []), *(row.get("revealed_traits") or [])]
    ]


def _chase_party_choices(
    state: dict,
    combat_meta: dict,
    party: list[dict],
    allies: list[dict],
    ally_ids: list,
    actors_by_id: dict,
    sides: dict,
    player: dict,
    intent: str,
    active: list[dict],
) -> dict:
    """SPEC-325 R12/R13: "deixo <nome>" (companheiro formal que tirou Complicação na rodada
    anterior) e aceite do sacrifício oferecido. O destino é sorteado por seed e SELADO em
    `party[i]["pending_fate"]` (nada aplicado agora; `companion_soul.apply_turn` consome
    depois de >= 1 dia). O narrador só recebe "ficou para trás". `shadow` só registra."""
    from services import chase as chase_mod
    from services import combat_flags, combat_intents

    res: dict = {"flee": False, "logs": [], "events": [], "sacrificed": None, "abandoned": []}
    mode = combat_flags.mode("chase_abandon")
    prev = combat_meta.get("chase")
    if mode == "off" or not _chase_is_live(prev):
        return res
    if not _can_attempt_flee(player) or cm.has_control(player, "root"):
        return res
    formal = {
        chase_mod._ally_key(m): str(m.get("name") or "")
        for m in party
        if m.get("active") and not m.get("transient") and not m.get("pending_fate")
    }
    if mode == "shadow":
        if combat_intents.abandon_target(intent, formal):
            _log_event("combat", "chase_abandon_shadow")
        return res

    target = combat_intents.abandon_target(intent, chase_mod.abandon_candidates(prev, party))
    offer = str(prev.get("sacrifice_offer") or "")
    sacrificed = None
    if not target and offer and combat_intents.accepts_sacrifice(intent):
        entry = next((m for m in party if chase_mod._ally_key(m) == offer), None)
        if entry is not None and entry.get("active") and not entry.get("pending_fate"):
            from services import companion_soul as cs_

            probe = dict(entry)
            if "se_sacrifica_pelo_grupo" in _soul_traits(state, entry):
                probe["se_sacrifica_pelo_grupo"] = True
            soul = (state.get("companion_souls") or {}).get(cs_.comp_id(entry))
            if chase_mod.offer_sacrifice(probe, True, soul)["sacrificed"]:
                sacrificed = offer
    key = target or sacrificed
    if not key:
        return res
    entry = next(m for m in party if chase_mod._ally_key(m) == key)
    world = state.get("world") or {}
    day = int(((world.get("world_clock") or {}).get("day", 1)) or 1)
    location_id = str(world.get("current_location_id") or "")
    chase_mod.seal_fate(
        entry,
        instance_id=str(combat_meta.get("instance_id") or "game"),
        round_=int(combat_meta.get("round", 0) or 0) + 1,
        pursuers=len(active),
        day=day,
        location_id=location_id,
        outcomes=chase_mod.SACRIFICE_OUTCOMES if sacrificed else None,
    )
    # sai da cena: fora do pool de Sorte desta rodada e da própria rodada de combate
    allies[:] = [a for a in allies if chase_mod._ally_key(a) != key]
    ally_ids[:] = [i for i in ally_ids if str(i) != key]
    actors_by_id.pop(key, None)
    sides["ally"] = [i for i in sides.get("ally", []) if str(i) != key]
    player["_party_active"] = bool(allies)
    name = str(entry.get("name") or key)
    res["flee"] = True
    res["abandoned"].append(key)
    if sacrificed:
        res["sacrificed"] = sacrificed
        res["logs"].append(f"{name} fica para trás para segurar os perseguidores.")
        _log_event("combat", "chase_sacrifice", level="info")
    else:
        res["logs"].append(f"{name} ficou para trás.")
        combat_meta["chase"] = {**prev, "abandoned": [*(prev.get("abandoned") or []), key]}
        import hashlib

        res["events"].append(
            {
                # id estável por (instância, aliado, rodada), sem expor a seed do destino
                "event_id": "abandon-"
                + hashlib.sha1(entry["pending_fate"]["seed"].encode()).hexdigest()[:16],
                "turn": int(world.get("turn_count", 0) or 0),
                "type": "companion_abandoned",
                "actor_id": "player",
                "target_id": key,
                "payload": {"name": name, "location_id": location_id, "day": day},
                "source": "combat",
            }
        )
        _log_event("combat", "chase_abandon", level="info")
    return res


def _publish_sacrifice_offer(
    state: dict, party: list[dict], chase_state: dict, *, hero_fled: bool, logs: list[str]
) -> None:
    """SPEC-325 R13: com a trilha em `pressionado` e um companheiro elegível (D3), publica a
    oferta UMA vez por perseguição. Recusar/ignorar não tem penalidade (a oferta só expira)."""
    from services import chase as chase_mod
    from services import combat_flags

    mode = combat_flags.mode("chase_abandon")
    if mode == "off":
        return
    if mode == "on" and "sacrifice_offer" in chase_state:
        chase_state["sacrifice_offer"] = None  # consumida: aceita, recusada ou ignorada
    if hero_fled or chase_state.get("trilha") != "pressionado":
        return
    if mode == "on" and chase_state.get("sacrifice_offered"):
        return
    key = chase_mod.eligible_for_sacrifice(
        party,
        state.get("companion_souls") or {},
        traits_of=lambda m: _soul_traits(state, m),
    )
    if not key:
        return
    if mode == "shadow":
        _log_event("combat", "chase_sacrifice_shadow")
        return
    chase_state["sacrifice_offer"] = key
    chase_state["sacrifice_offered"] = True
    name = next((str(m.get("name") or key) for m in party if chase_mod._ally_key(m) == key), key)
    logs.append(f"{name} se oferece para ficar e segurar os perseguidores.")
    _log_event("combat", "chase_sacrifice_offered", level="info")


def _last_human_text(messages: list) -> str:
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


# ==========================================================================
# Preparação da cena (ANTES do conflito — LLM identifica; guard obrigatório)
# ==========================================================================
def _bounded_enemy_groups(scan: EncounterScanner) -> list[tuple[str, int]]:
    """Normaliza/deduplica o scanner inteiro antes de chamar qualquer factory."""
    grouped: dict[str, dict] = {}
    for ident in (scan.detected_enemies or [])[:_MAX_SCANNER_TYPES]:
        raw_name = ident.get("name") if isinstance(ident, dict) else getattr(ident, "name", "")
        name = " ".join(str(raw_name or "Inimigo").split()) or "Inimigo"
        key = name.casefold()
        raw_count = ident.get("count", 1) if isinstance(ident, dict) else getattr(ident, "count", 1)
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
    bounded: list[tuple[str, int]] = []
    for entry in grouped.values():
        if remaining <= 0:
            break
        count = min(int(entry["count"]), remaining)
        if count:
            bounded.append((str(entry["name"]), count))
            remaining -= count
    return bounded


def _grounded_template(
    name: str, context: str, encounter_level: int, state: dict | None = None
) -> dict:
    """Factory do bestiário com trava de identidade (SPEC-203 R3/H3): se o
    dedupe/gerador devolver OUTRA espécie, descarta e materializa o nome pedido."""
    from services import encounter_manifest as em

    pool_kwargs: dict = {}
    from services.shared_pool import enabled as _pool_enabled

    if _pool_enabled() and (state or {}).get("game_id"):
        # SPEC-297 R9: nome vindo da dica/scanner (texto do jogador) nunca promove (D1).
        pool_kwargs = {
            "game_id": str(state.get("game_id")),
            "location_id": str((state.get("world") or {}).get("current_location_id", "")),
            "name_origin": "player",
        }
    template = generate_new_enemy(
        name, context=context, encounter_level=encounter_level, **pool_kwargs
    )
    if em.shares_identity(name, str(template.get("name") or "")) or em.shares_identity(
        name, str(template.get("id") or "")
    ):
        return template
    _log_event("combat", "spawn_identity_mismatch", level="warning")
    from agents.bestiary import _slug, materialize_enemy_concept

    return materialize_enemy_concept(
        {
            "name": name,
            "id": f"fallback_{_slug(name)}",
            "description": "Criatura materializada pela trava de identidade.",
            "categoria": template.get("categoria") or "padrao",
            "arquetipo": template.get("arquetipo") or "bruto",
        },
        encounter_level=encounter_level,
    )


def _instances(template: dict, count: int, next_by_template: dict[str, int]) -> list[dict]:
    out = []
    base_id = str(template.get("id") or "enemy")
    for _ in range(count):
        number = next_by_template.get(base_id, 0) + 1
        next_by_template[base_id] = number
        inst = dict(template)
        inst["id"] = f"{base_id}_{number}"
        inst.setdefault("archetype_id", base_id)  # SPEC-272: chave do bestiário
        inst["name"] = f"{template['name']} {number}" if count > 1 else template["name"]
        out.append(orch.ensure_combat_sheet(inst))
    return out


def _sync_enemy_knowledge(enemies: list[dict], *, load_persisted: bool = False) -> None:
    """SPEC-272 (liga SPEC-069 R8): Carta que o inimigo já usou fica revelada no
    painel de combate; no início do encontro, o que o bestiário já sabe do arquétipo
    começa revelado. Persistir/ler o overlay compartilhado só no perfil `legacy` —
    mesmo fail-closed de `dossiers._revealed_for` (escopo não é por dono/jogo)."""
    import os

    from services import bestiary_knowledge as bk

    shared = os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() == "legacy"
    for enemy in enemies:
        if not isinstance(enemy, dict):
            continue
        try:
            # Revisão SPEC-272: reforço do orçamento (`fill_encounter`) e saves
            # antigos não passam por `_instances`; sem isso a chave do overlay
            # viraria o id da instância (`goblin_3`), poluindo o bestiário.
            if not enemy.get("archetype_id") and enemy.get("id"):
                from services.encounter_manifest import _base_id

                enemy["archetype_id"] = _base_id(enemy["id"])
            if load_persisted and shared:
                bk.apply_persisted_knowledge(enemy)
            for card_id in list(enemy.get("enemy_card_usage") or {}):
                if bk.is_card_revealed(enemy, card_id):
                    continue
                if shared:
                    bk.reveal_card(enemy, card_id)
                else:
                    enemy.setdefault("revealed_cards", []).append(card_id)
        except Exception:  # revelação é cosmética: nunca derruba o turno
            _log_event("combat", "enemy_knowledge_failed", level="warning")


def _spawn_v4_enemies(
    messages: list, target_hint: str, state: dict | None, meta: dict | None = None
) -> tuple:
    """Monta o elenco do encontro e converte CADA um em ficha v4.

    SPEC-203 R3 — ordem determinística: (a) `enemy_id` do encontro sistêmico;
    (b) NPC em cena; (c) alvo/ameaça já resolvida (nome exato do bestiário);
    (d) só então o `EncounterScanner` (LLM CLASSIFY), com saída validada contra a
    dica. `meta` (out-param) recebe source/target_ref/joined_ids/cut_ids."""
    from services import encounter_manifest as em

    meta = meta if meta is not None else {}
    _log_event("combat", "preparing_encounter", level="info")
    enemies: list[dict] = []
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
    next_instance_by_template: dict[str, int] = {}
    protected: set = set()
    canonical = em.resolve_canonical_source(
        state or {}, target_hint, (state or {}).get("combat_encounter_hint")
    )
    if canonical and canonical["kind"] == "bestiary":
        from agents.bestiary import template_by_id

        for bid, count in canonical["groups"]:
            template = template_by_id(bid, encounter_level=encounter_level)
            if template:
                enemies += _instances(template, count, next_instance_by_template)
                protected.add(bid)
        if enemies:
            meta.update(source=canonical["source"], target_ref=canonical["target_ref"])
            flavor = f"{enemies[0].get('name', 'Algo')} avança contra você."
    elif canonical and canonical["kind"] == "npc":
        npc = dict(((state or {}).get("npcs") or {}).get(canonical["npc_name"]) or {})
        sheet = prep.build_npc_combat_sheet({**npc, "name": canonical["npc_name"]})
        enemies = [orch.ensure_combat_sheet(sheet)]
        protected.add(str(sheet.get("id")))
        meta.update(source="npc_in_scene", target_ref=canonical["target_ref"])
        flavor = f"{canonical['npc_name']} se volta contra você."

    if not enemies:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
        sys_prompt = (
            f"Analise a narrativa recente. O combate começou. Identifique QUAIS "
            f"inimigos estão presentes e QUANTOS. Use a dica: '{target_hint}'. "
            f"Ex.: 'Três orcs surgem' -> [{{name:'Orc', count:3}}]."
        )
        try:
            scan = llm.with_structured_output(EncounterScanner).invoke(
                [SystemMessage(content=sys_prompt)] + messages[-2:]
            )
            if isinstance(scan, EncounterScanner):
                flavor = scan.flavor_text or flavor
                # Primeiro fecha tipos/contagens; somente depois toca bestiário/factory.
                groups = _bounded_enemy_groups(scan)
                if not em.is_generic_hint(target_hint):
                    # R3(d): saída do scanner precisa casar com a dica (fauna da
                    # prosa não entra). Nada casou → a própria dica vira o grupo.
                    grounded = [(n, c) for n, c in groups if em.shares_identity(target_hint, n)]
                    if len(grounded) != len(groups):
                        _log_event("combat", "spawn_scanner_discarded", level="warning")
                    groups = grounded or [(str(target_hint).strip(), em.hint_count(target_hint))]
                for name, count in groups:
                    template = _grounded_template(name, mechanical_context, encounter_level, state)
                    enemies += _instances(template, count, next_instance_by_template)
                if enemies:
                    meta.update(source="scanner", target_ref=str(target_hint or ""))
        except Exception as e:
            _log_event("combat", "spawn_failed", level="warning", error=type(e).__name__)

    if not enemies:
        enemies = [
            orch.ensure_combat_sheet(
                {
                    "id": "sombrio_1",
                    "name": "Inimigo Sombrio",
                    "type": "padrao",
                    "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
                }
            )
        ]
        meta.update(source="fallback", target_ref=str(target_hint or ""))
        _log_event("combat", "spawn_fallback", level="warning")

    # Orçamento determinístico do encontro (mesma lógica da Fase 4.6, escala nova).
    if state is not None:
        enemies, flavor = _apply_encounter_budget(
            enemies, state, flavor, protected=protected or None, report=meta
        )
    return enemies, flavor


def _apply_encounter_budget(
    enemies: list[dict],
    state: dict,
    flavor: str,
    *,
    protected: set | None = None,
    report: dict | None = None,
) -> tuple:
    """SPEC-203 R4: clamp/fill seguem a regra numérica, mas o alvo canônico não
    perde vaga por variedade e todo corte/reforço é reportado (ids) para virar
    evento de composição no manifesto."""
    report = report if report is not None else {}
    try:
        import encounter_budget as eb
        import party as party_mod
        from gamedata import get_location
        from services import encounter_manifest as em

        if protected is None:
            bid = em.resolve_bestiary_name(str(state.get("combat_target") or ""))
            protected = {bid} if bid else set()
        world = state.get("world") or {}
        danger = int(world.pop("encounter_eff_danger", None) or world.get("danger_level", 1) or 1)
        level = int((state.get("player") or {}).get("level", 1) or 1)
        enemy_refs = [
            str(value)
            for enemy in enemies
            for value in (enemy.get("id"), enemy.get("name"))
            if value
        ]
        n_allies = len(party_mod.active_allies(state)) + len(
            party_mod.scene_allies(state, excluded=enemy_refs)
        )
        budget = eb.encounter_budget(level, danger, n_allies)
        before_ids = [str(e.get("id")) for e in enemies]
        enemies, cut = eb.clamp_encounter(enemies, budget, player_level=level, protected=protected)
        kept_ids = {str(e.get("id")) for e in enemies}
        loc = get_location(world.get("current_location_id", "")) or {}
        enemies, fill = eb.fill_encounter(
            enemies,
            budget,
            loc,
            danger,
            turn=int(world.get("turn_count", 0) or 0),
            make_instance=lambda t, i: orch.ensure_combat_sheet(
                {**t, "id": f"{t.get('id', 'enemy')}_{i}"}
            ),
        )
        report["cut_ids"] = [i for i in before_ids if i not in kept_ids]
        report["joined_ids"] = [
            str(e.get("id")) for e in enemies if str(e.get("id")) not in kept_ids
        ]
        extra = " ".join(cut + fill)
        if extra:
            flavor = f"{flavor} {extra}".strip()
    except Exception as e:
        _log_event("combat", "budget_failed", level="warning", error=type(e).__name__)
    return enemies, flavor


def _early_game_reaction_initiator(
    state: dict, player: dict, initiator: str | None, *, combat_round: int | None = None
) -> str | None:
    """Garante uma primeira decisão a herói novo e saudável fora de apex.

    [BALANCEAR] A baseline real encontrou mortes de nível 1–2 em emboscadas antes
    de qualquer janela de fuga/cura. Não reduz dano nem budget: quando o herói
    entra com Vitalidade cheia, somente a iniciativa do primeiro round é sua.
    Depois de agir (ou em apex), a iniciativa e a letalidade normais prevalecem.
    """
    level = int(player.get("level", 1) or 1)
    vitality = int(player.get("vitalidade", player.get("hp", 0)) or 0)
    maximum = int(player.get("max_vitalidade", player.get("max_hp", 0)) or 0)
    # SPEC-232 R9: `combat_round` é a rodada CORRENTE (pós-incremento, 1 = primeira).
    # Antes lia o estado pré-incremento com `<= 1` e valia por duas rodadas.
    if combat_round is None:
        combat_round = int((state.get("combat") or {}).get("round", 0) or 0)
    world = state.get("world") or {}
    loc = gamedata.get_location(world.get("current_location_id", "")) or {}
    tags = {str(tag).casefold() for tag in (loc.get("tags") or [])}
    if (
        level <= 2
        and maximum > 0
        and vitality >= maximum
        and combat_round == 1
        and "apex" not in tags
    ):
        return "heroes"
    return initiator


_PREPARED_CATEGORIES = {"elite", "chefe", "nomeado", "boss"}


def _wants_prepared_scene(player: dict, enemies: list[dict]) -> bool:
    """D-A: Carga ≥ leve OU inimigo de categoria ≥ Elite."""
    try:
        if cm.abyss_tier(player) != "nenhum":
            return True
    except Exception:
        pass
    return any(
        str(e.get("categoria") or e.get("type") or "").strip().lower() in _PREPARED_CATEGORIES
        for e in enemies or []
    )


def _prepare_scene(state: dict, enemies: list[dict], player: dict, allies: list[dict]) -> dict:
    """Monta a cena JOGÁVEL em Python com zonas mínimas e seguras. O Nível do
    Encontro é perigo ABSOLUTO (11 R6), nunca depende da party."""
    world = state.get("world") or {}
    loc = world.get("current_location", "Campo")
    encounter_level = prep.compute_encounter_level(
        location_danger=int(world.get("danger_level", 1) or 1),
        region_danger=int(world.get("danger_level", 1) or 1),
        event_type=str(world.get("encounter_type", "comum")),
        importance="comum",
    )
    ctx = {
        "location": loc,
        "enemies": enemies,
        "npcs": [],
        "encounter_level": encounter_level,
        "narrative": "",
    }
    # SPEC-232 R10 (D-A, default do dono): a preparação por LLM (objetos, eventos
    # do Abismo, reforços, condições de fim) só roda quando importa — Carga do
    # Abismo ≥ patamar leve ou algum inimigo Elite/Chefe/Nomeado. Custo: 1 invoke
    # FAST nesses encontros; nos demais, geometria mínima em Python (sem invoke).
    if _wants_prepared_scene(player, enemies):
        try:
            # SPEC-317 R8: o contexto so serve ao prompt de preparacao (e so o estado do mundo).
            ctx["narrative"] = build_context_pack(
                state,
                query=str(loc),
                purpose="combat_narration",
                token_budget=600,
                include_lore=False,
            ).world_state_block
            llm = get_llm(temperature=0.4, tier=ModelTier.FAST)
            scene = prep.prepare_encounter(ctx, llm)  # guard + fallback internos
        except Exception as e:
            _log_event("combat", "prep_failed", level="warning", error=type(e).__name__)
            scene = prep.fallback_safe_scene(ctx)
    else:
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
def _prepared_cards_catalog(player: dict) -> str:
    from services import cards

    linhas = []
    for cid in player.get("prepared_cards") or []:
        c = cards.get_card(cid)
        if not c:
            continue
        linhas.append(
            f"- {cid}: {c.get('name', cid)} | tipo {c.get('tipo')} | "
            f"custo {c.get('custo_entropia', 0)} Entropia | {c.get('descricao', '')[:50]}"
        )
    return "\n".join(linhas) or "- (nenhuma carta preparada; use ataque básico)"


def _usable_items_catalog(player: dict) -> str:
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


def _default_card_target(card: dict, enemy_id: str | None) -> str:
    """Cartas benéficas sem alvo explícito afetam o próprio jogador. Evita que
    chips como Cura/Proteção herdem mecanicamente o primeiro inimigo."""
    kind = str((card.get("efeito") or {}).get("kind") or "")
    # SPEC-232 R9: fonte única = efeitos de suporte do motor (inclui a Purga
    # `reduzir_carga_aliado`, antes ausente e gasta num inimigo).
    return _PLAYER_ID if kind in _SUPPORT_EFFECTS else (enemy_id or _PLAYER_ID)


def _card_target_for(
    card: dict, declared: str | None, *, active_ids: list[str], friendly_ids: list[str]
) -> str:
    """SPEC-232 R5: alvo de Carta validado na borda do nó. Ofensiva só mira um
    inimigo ATIVO (nunca o jogador nem um morto); suporte só mira o próprio lado.
    Inválido → alvo default da Carta."""
    kind = str((card.get("efeito") or {}).get("kind") or "")
    allowed = friendly_ids if kind in _SUPPORT_EFFECTS else active_ids
    if declared in set(allowed):
        return str(declared)
    return _default_card_target(card, active_ids[0] if active_ids else None)


def _parse_turn_declaration(
    player: dict, enemies: list[dict], intent: str, scene: dict
) -> TurnDeclaration:
    """A IA IDENTIFICA a fala do jogador → `TurnDeclaration` estruturada (só
    identifica, não resolve). Guard de fallback: ataque básico no 1º inimigo.
    O harness passa a declaração pronta e não chega aqui."""
    from pydantic import BaseModel, Field

    alvos = ", ".join(f"{e['id']}={e.get('name', e['id'])}" for e in enemies) or "—"
    fallback = TurnDeclaration(
        actor_id=_PLAYER_ID,
        acao=TurnStep(kind="attack", target_id=(enemies[0]["id"] if enemies else None)),
    )
    if not intent:
        return fallback

    # Chips do HUD carregam nomes canônicos: resolvemos localmente, sem gastar
    # CLASSIFY e sem permitir id alucinado.
    from services import cards

    folded_intent = intent.casefold()
    target_id = enemies[0]["id"] if enemies else None
    for cid in player.get("prepared_cards") or []:
        card = cards.get_card(cid)
        if card and str(card.get("name", "")).casefold() in folded_intent:
            return TurnDeclaration(
                actor_id=_PLAYER_ID,
                acao=TurnStep(
                    kind="card", card_id=cid, target_id=_default_card_target(card, target_id)
                ),
            )
    from gamedata import ARTIFACTS_DB
    from inventory import item_display

    for entry in player.get("inventory") or []:
        if not isinstance(entry, dict):
            continue
        item = ARTIFACTS_DB.get(entry.get("id", "")) or {}
        name = item_display(entry)
        if (
            str(item.get("type", "")).lower() in ("consumable", "potion")
            and name.casefold() in folded_intent
        ):
            return TurnDeclaration(
                actor_id=_PLAYER_ID,
                acao=TurnStep(kind="item", item_id=entry.get("id"), target_id=target_id),
            )

    class PlayerMove(BaseModel):
        kind: str = Field(description="attack | card | item | maneuver | move | pass")
        card_id: str = Field(default="", description="id EXATO da Carta preparada, se kind=card.")
        item_id: str = Field(default="", description="id EXATO do consumível, se kind=item.")
        target_id: str = Field(default="", description="id do inimigo alvo (da lista).")
        maneuver: str = Field(
            default="",
            description="engajar|desengajar|guardar|esconder|procurar, se kind=maneuver.",
        )
        direction: str = Field(default="", description="aproximar|afastar, se kind=move.")

    sys = SystemMessage(
        content=f"""
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
    """
    )
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
        res = llm.with_structured_output(PlayerMove).invoke([sys, HumanMessage(content=intent)])
        if isinstance(res, PlayerMove):
            kind = (res.kind or "attack").lower()
            tid = res.target_id or (enemies[0]["id"] if enemies else None)
            if kind == "card" and res.card_id in (player.get("prepared_cards") or []):
                card = cards.get_card(res.card_id) or {}
                return TurnDeclaration(
                    actor_id=_PLAYER_ID,
                    acao=TurnStep(
                        kind="card", card_id=res.card_id, target_id=_default_card_target(card, tid)
                    ),
                )
            if kind == "item" and res.item_id:
                return TurnDeclaration(
                    actor_id=_PLAYER_ID,
                    acao=TurnStep(kind="item", item_id=res.item_id, target_id=tid),
                )
            if kind == "maneuver" and res.maneuver:
                return TurnDeclaration(
                    actor_id=_PLAYER_ID,
                    acao=TurnStep(kind="maneuver", maneuver=res.maneuver, target_id=tid),
                )
            if kind == "move" and res.direction:
                return TurnDeclaration(
                    actor_id=_PLAYER_ID, acao=TurnStep(kind="move", direction=res.direction)
                )
            if kind == "pass":
                return TurnDeclaration(actor_id=_PLAYER_ID, acao=TurnStep(kind="pass"))
            return TurnDeclaration(actor_id=_PLAYER_ID, acao=TurnStep(kind="attack", target_id=tid))
    except Exception as e:
        _log_event("combat", "parse_failed", level="warning", error=type(e).__name__)
    return fallback


# ==========================================================================
# Alias Vitalidade→hp (compatibilidade pública)
# ==========================================================================
def _mirror_vitals(actor: dict) -> None:
    """Sincroniza apenas os aliases de borda e o status textual."""
    import gamedata

    gamedata.sync_legacy_hp_aliases(actor)
    if actor.get("dead"):
        actor["status"] = "morto"
    elif actor.get("fled"):
        actor["status"] = "fugiu"
    elif actor.get("surrendered"):
        actor["status"] = "rendido"
    elif actor.get("incapacitated") and actor.get("nonlethal_by"):
        actor["status"] = "incapacitado"  # SPEC-325 R9: golpe não-letal, não é derrota
    else:
        actor.setdefault("status", "ativo")


def _canonical_player_action(
    declaration: TurnDeclaration | None,
    out: dict,
    *,
    attempted: bool = True,
    flee_requested: bool = False,
    hero_fled: bool = False,
    flee_destination_id: str | None = None,
    chase_state: dict | None = None,
) -> dict:
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
        kind = (
            raw_kind
            if raw_kind
            in {
                "attack",
                "card",
                "item",
                "maneuver",
                "move",
                "pass",
                "flee",
            }
            else "pass"
        )
        player_attack = next(
            (
                attack
                for attack in (out.get("attacks") or [])
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
        (attack for attack in (out.get("attacks") or []) if attack.get("actor_id") == _PLAYER_ID),
        {},
    )
    action = {
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
    if flee_requested and (chase_state or {}).get("approach"):
        action["chase_approach"] = chase_state["approach"]  # SPEC-325 R10 (só com a flag `on`)
    return action


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


def _is_valid_flee_destination(state: dict, destination_id: str | None) -> bool:
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
def _killer_identity(active: list) -> tuple[str, str]:
    """SPEC-288: (espécie canônica, id do bestiário) do inimigo que deu o golpe final."""
    from services import encounter_manifest as em

    enemy = next((e for e in active or [] if e), None)
    if not enemy:
        return "", ""
    base = em._base_id(enemy.get("id", ""))
    known = base in (gamedata.BESTIARY or {})
    return em.species_label_for(enemy), (base if known else str(enemy.get("bestiary_id") or ""))


def _narrate_fall(player: dict, logs: list[str], killer: str = "") -> str:
    quem = f" diante de {killer}" if killer else ""
    golpes = "\n".join(f"• {l}" for l in logs[-4:]) if logs else ""
    return (
        f"⚔️ {golpes}\n\n☠️ Você tomba{quem}. A escuridão te engole — mas a "
        f"Roda do Abismo ainda não decidiu. Voltar ao último respiro seguro, "
        f"ou aceitar o fim aqui?"
    ).strip()


def _faction_withhold_clause(manifest, factions, intel) -> str:
    """SPEC-292 (P2-3): fações dos combatentes que o jogador AINDA não conhece ficam
    sem nome na narração (descreve-se por aparência/armas). Vazio se nada a esconder."""
    from world_utils import unknown_faction_names

    ids = [p.get("faction_id") for p in (manifest or {}).get("participants") or []]
    names = unknown_faction_names(ids, factions, intel)
    if not names:
        return ""
    clause = (
        "O herói NÃO conhece as facções: "
        + "; ".join(names)
        + ". NÃO cite esses nomes nem o nome de organização dos inimigos — descreva-os "
        "por aparência, armas e comportamento."
    )
    # Revisão SPEC-292: o NOME da criatura carrega o radical da fação ("Iniciado da
    # Chama Azul"); sem esta exceção ao elenco o fallback (Groq) repetiu o nome inteiro.
    hidden = _concealed_species(manifest, factions, intel)
    if hidden:
        clause += (
            " Prevalece sobre o elenco canônico: chame "
            + "; ".join(f"'{full}' apenas de '{short}'" for full, short in hidden)
            + " — NUNCA pelo nome completo."
        )
    return clause


def _concealed_species(manifest, factions, intel) -> list[tuple[str, str]]:
    """(nome canônico, rótulo curto) das espécies cujo nome expõe fação desconhecida."""
    # SPEC-293 R7: mesmo rótulo de exibição do HUD/Bestiário (services.faction_display).
    from services.faction_display import display_label

    out: list[tuple[str, str]] = []
    for p in (manifest or {}).get("participants") or []:
        full = str(p.get("species_label") or "")
        short = display_label(full, str(p.get("faction_id") or ""), factions, intel)
        if full and short != full and full not in dict(out):
            out.append((full, short))
    return out


def _flee_alert_world(world: dict, enemies: list[dict], outcome: str) -> dict | None:
    """SPEC-296 R2: devolve o world com 1 alerta de fuga (1º inimigo `fled`), ou None.
    Fuga do herói, morte, derrota e rendição não registram (review P2-3: reforço
    não chega em cima do herói caído)."""
    if outcome in ("fled", "death", "defeat", "surrendered_enemy"):
        return None
    fugitive = next((e for e in enemies if e.get("fled") or e.get("status") == "fugiu"), None)
    if fugitive is None:
        return None
    from world_utils import register_flee_alert

    species, bestiary_id = _killer_identity([fugitive])
    hint = species or str(fugitive.get("name") or "o fugitivo")
    return register_flee_alert(
        world,
        hint,
        faction_id=(fugitive.get("faction_id") or fugitive.get("faction") or None),
        turn=int((world or {}).get("turn_count", 0) or 0),
        enemy_id=bestiary_id,
    )


def _perceived_for_combat(state: dict) -> str:
    """SPEC-309 R19: `<MUNDO_PERCEBIDO>` na narracao do combate (so ambiente; nunca quebra)."""
    from services.perceived_world import perceived_world_block

    block = perceived_world_block(state, audience="combat")
    return f"\n{block}" if block else ""


def _ambient_for_combat(world: dict, player: dict) -> str:
    """SPEC-296 R5: `<AMBIENTE>` (sem saídas) na narração do combate; nunca quebra o turno."""
    try:
        from services.ambient import ambient_block

        return ambient_block(world, player, audience="combat")
    except Exception as exc:  # noqa: BLE001 - ambientação é opcional
        from observability.telemetry import log_fallback

        log_fallback("combat_agent", "ambient_block_failed", exc)
        return ""


def _narrate(
    player: dict,
    enemies: list[dict],
    logs: list[str],
    spawned_flavor: str | None,
    intent: str,
    victory: bool,
    world_ctx: str,
    aberturas: list[str] | None = None,
    manifest: dict | None = None,
    withhold: str = "",
) -> str:
    from services import prose_guard

    canonical = sorted(
        {
            p.get("species_label", "")
            for p in (manifest or {}).get("participants") or []
            if p.get("species_label")
        }
    )
    elenco = (
        (
            "Elenco canônico (espécies EXATAS; não renomeie nem troque por fauna): "
            + ", ".join(canonical)
        )
        if canonical
        else ""
    )
    log_str = "\n".join(l for l in logs if l) or "Nada acontece."
    alive = [
        f"{e['name']} (Vit {e.get('vitalidade', 0)}/{e.get('max_vitalidade', 0)})"
        for e in enemies
        if e.get("status") == "ativo"
    ]
    varie = prose_guard.openings_clause(aberturas or [])
    fecho = (
        "O combate foi VENCIDO — encerre com o respiro da vitória."
        if victory
        else "Termine com tensão e uma deixa para a próxima ação do jogador."
    )
    sys = SystemMessage(
        content=f"""
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
    Herói: {player.get("name")} Vit {player.get("vitalidade")}/{player.get("max_vitalidade")}
    Inimigos ativos: {", ".join(alive) if alive else "nenhum"}
    {elenco}
    {withhold}
    {fecho}{varie}
    """
    )
    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.FAST)
        if getattr(llm, "is_fallback", False):
            raise RuntimeError("fallback")
        from services.narrative_sink import narrate_text

        # SPEC-319: tokens ao vivo so com sink (stream SSE); senao e o invoke de sempre.
        res = narrate_text(llm, [sys, HumanMessage(content=intent or "Continue o combate.")])
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        if text.strip():
            # SPEC-203 R9: prosa que troca a espécie do elenco é neutralizada
            # (cai no texto determinístico); o estado nunca é reescrito.
            drift = prose_guard.species_drift(text, manifest) if manifest else []
            if not drift:
                return text
            prose_guard.log_species_drift(drift, where="combate")
    except Exception as e:
        _log_event("combat", "narrate_failed", level="warning", error=type(e).__name__)
    prefix = (spawned_flavor + "\n\n") if spawned_flavor else ""
    suffix = "\n\nVitória! O campo silencia." if victory else "\n\nO que você faz?"
    return f"⚔️ {prefix}" + "\n".join(f"• {l}" for l in logs if l) + suffix


# ==========================================================================
# SPEC-203 — desfecho do encontro
# ==========================================================================
def _encounter_outcome(
    *, player: dict, enemies: list[dict], hero_fled: bool, player_dead: bool
) -> str:
    if player_dead:
        return "death"
    if hero_fled:
        return "fled"
    remaining = [
        e
        for e in enemies
        if e.get("status") == "ativo" and not e.get("dead") and not e.get("incapacitated")
    ]
    if remaining or not player.get("conscious", True):
        return "defeat"
    dead = [e for e in enemies if e.get("dead") or e.get("status") == "morto"]
    surrendered = [e for e in enemies if e.get("surrendered") or e.get("status") == "rendido"]
    if surrendered and not dead:
        return "surrendered_enemy"
    return "victory"


def _finish_encounter(combat_meta: dict, enemies: list[dict], outcome: str, *, loot: bool) -> dict:
    """Leva o encontro a `ended` e grava o snapshot do desfecho (R7)."""
    from services import encounter_manifest as em

    meta = dict(combat_meta)
    round_ = int(meta.get("round", 0) or 0)
    manifest = meta.get("encounter")
    if em.is_valid_manifest(manifest):
        manifest = em.sync_statuses(manifest, enemies, round_)
        meta["encounter"] = manifest
    meta = em.end_combat(meta, outcome)
    if em.is_valid_manifest(manifest):
        meta["result"] = em.build_result(
            manifest, outcome, round_, loot=loot and outcome == "victory"
        )
    meta["active"] = False
    return meta


# ==========================================================================
# NÓ PRINCIPAL
# ==========================================================================
def combat_node(state: GameState):
    """SPEC-251: abre o trace mecânico do turno e emite combat.mechanics/summary."""
    from services import mechanics_trace as _mt

    with _mt.scope():
        result = _combat_node(state)
        _mt.emit_turn_logs()
    return result


def _combat_node(state: GameState):
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
    # SPEC-226 R1: mortos que já constavam no estado de entrada não rendem de novo.
    dead_before = {
        str(e.get("id") or e.get("name"))
        for e in (state.get("enemies") or [])
        if e.get("dead") or e.get("status") == "morto" or e.get("xp_awarded")
    }

    if not player.get("conscious", True) and not combat_meta.get("active"):
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Você está inconsciente e não pode iniciar outro conflito. "
                        "É preciso descansar ou receber tratamento primeiro."
                    )
                )
            ],
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
    from services import encounter_manifest as em

    spawn_meta: dict = {}
    if is_start or not scene:
        import party as party_mod

        party = party_mod.backfill_party(state.get("party") or [])
        if not [e for e in enemies if e.get("status") == "ativo" and not e.get("dead")]:
            enemies, spawned_flavor = _spawn_v4_enemies(messages, combat_target, state, spawn_meta)
        enemy_refs = [
            str(value)
            for enemy in enemies
            for value in (enemy.get("id"), enemy.get("name"))
            if value
        ]
        if combat_target:
            enemy_refs.append(str(combat_target))
        allies = [
            orch.ensure_combat_sheet(dict(a), is_ally=True) for a in party if a.get("active")
        ] + [
            orch.ensure_combat_sheet(dict(a), is_ally=True)
            for a in party_mod.scene_allies(state, excluded=enemy_refs)
        ]
        scene = _prepare_scene(state, enemies, player, allies)
        _sync_enemy_knowledge(enemies, load_persisted=True)
        bestiary_knowledge = disc.record_encounter(bestiary_knowledge, enemies, turn)
        bk_changed = True
        from services.combat_origin import materialize

        continuity = state.get("continuity") or {}
        conflict_instance_id = ":".join(
            (
                str(state.get("game_id") or "game"),
                str(int(continuity.get("timeline_epoch", 0) or 0)),
                str(int(continuity.get("session_action_count", turn) or turn)),
            )
        )
        combat_meta = {
            "round": 0,
            "active": True,
            "scene": scene,
            "idle_turns": 0,
            "origin": materialize(combat_meta, state.get("combat_origin_hint")),
            "instance_id": conflict_instance_id,
            "encounter_level": scene.get("encounter_level", 1),
        }
        # SPEC-203 R1/R5: manifesto congelado no spawn → fase `entering`.
        combat_meta = em.safe_transition(combat_meta, "entering")
        combat_meta["encounter"] = em.build_manifest(
            enemies,
            source=(
                spawn_meta.get("source") or ("simulation" if is_simulation else "legacy_migrated")
            ),
            origin=combat_meta["origin"],
            encounter_id=conflict_instance_id,
            target_ref=spawn_meta.get("target_ref") or str(combat_target or ""),
            scene=scene,
            joined_ids=spawn_meta.get("joined_ids") or (),
            cut_ids=spawn_meta.get("cut_ids") or (),
        )
        _log_event("combat", "started", level="info", enemies=len(enemies))
    else:
        # R2: leitura por rodada — manifesto é a verdade; nunca reclassifica.
        if not em.is_valid_manifest(combat_meta.get("encounter")):
            combat_meta["encounter"] = em.manifest_from_legacy(
                enemies, combat_meta, game_id=str(state.get("game_id") or "game")
            )
        if combat_meta.get("phase") not in ("active",):
            combat_meta["phase"], combat_meta["outcome"] = "active", None
        combat_meta["encounter"], enemies, _violations = em.reconcile_roster(
            combat_meta["encounter"], enemies, int(combat_meta.get("round", 0) or 0)
        )

    active = [e for e in enemies if e.get("status") == "ativo" and not e.get("dead")]
    if not active:
        import party as party_mod

        party = party_mod.backfill_party(state.get("party") or [])
        enemy_refs = [
            str(value)
            for enemy in enemies
            for value in (enemy.get("id"), enemy.get("name"))
            if value
        ]
        scene_tr = combat_meta.get("scene_allies") or party_mod.scene_allies(
            state, excluded=enemy_refs
        )
        allies = [
            orch.ensure_combat_sheet(dict(a), is_ally=True) for a in party if a.get("active")
        ] + [orch.ensure_combat_sheet(dict(a), is_ally=True) for a in scene_tr]
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
        combat_meta["last_player_action"] = _canonical_player_action(None, {}, attempted=False)
        early_outcome = _encounter_outcome(
            player=player, enemies=enemies, hero_fled=False, player_dead=False
        )
        combat_meta = _finish_encounter(combat_meta, enemies, early_outcome, loot=not is_simulation)
        return {
            "messages": [AIMessage(content="O silêncio retorna ao campo. Vitória.")],
            "next": "loot",
            "combat_target": None,
            "enemies": [],
            "conflict_summary": conflict_sum,
            "combat": {
                **combat_meta,
                "active": False,
                "round": combat_meta.get("round", 0),
                "scene": None,
            },
            "archive_due": True,
        }

    # ---- Montagem dos lados + declaração do jogador ----
    import party as party_mod

    party = party_mod.backfill_party(state.get("party") or [])
    enemy_refs = [
        str(value) for enemy in enemies for value in (enemy.get("id"), enemy.get("name")) if value
    ]
    scene_tr = combat_meta.get("scene_allies") or party_mod.scene_allies(state, excluded=enemy_refs)
    allies = [orch.ensure_combat_sheet(dict(a), is_ally=True) for a in party if a.get("active")] + [
        orch.ensure_combat_sheet(dict(a), is_ally=True)
        for a in scene_tr
        if not (a.get("dead") or a.get("status") == "morto")
    ]
    player["_party_active"] = bool(allies)
    ally_ids = [a.get("id") or a.get("name") for a in allies]

    actors_by_id: dict[str, dict] = {_PLAYER_ID: player}
    for e in enemies:
        actors_by_id[e["id"]] = e
    for a in allies:
        actors_by_id[a.get("id") or a.get("name")] = a
    sides = {"hero": [_PLAYER_ID], "ally": ally_ids, "enemy": [e["id"] for e in active]}

    intent = _last_human_text(messages)
    declaration = state.get("combat_declaration")  # harness passa estruturado
    if declaration is not None and not isinstance(declaration, TurnDeclaration):
        declaration = TurnDeclaration(**declaration)

    # ---- Fuga: chase determinístico (conflito-09) ----
    flee_dest_id = None
    from services.chase import FLEE_RE

    flee_requested = bool(FLEE_RE.search(intent.lower()))
    if flee_requested:
        from services.intent_guard import log_intent_guard

        log_intent_guard("flee_regex", "FLEE_RE", intent)
    if declaration is not None and declaration.acao is not None and declaration.acao.kind == "flee":
        flee_requested = True
        flee_dest_id = declaration.acao.params.get("destination_id")
    if state.get("combat_flee_attempt"):
        flee_requested = True
        flee_dest_id = state.get("combat_flee_destination")

    # SPEC-325 R12/R13: abandono/sacrifício durante a perseguição (`off`/sem fuga = nada muda).
    choices = _chase_party_choices(
        state, combat_meta, party, allies, ally_ids, actors_by_id, sides, player, intent, active
    )
    if choices["flee"]:
        flee_requested = True
        logs_pre_flee = list(choices["logs"])
    else:
        logs_pre_flee = []

    if flee_requested:
        combat_meta["flee_attempts"] = int(combat_meta.get("flee_attempts", 0) or 0) + 1
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
    logs: list[str] = []
    world_out = None
    world = state.get("world") or {}
    from world_utils import DARK_COMBAT_PENALTY, light_level, weather_effects

    weather_fx = weather_effects(world)
    light_fx = light_level(world, player)
    weather_attack = int(weather_fx.get("combat_attack_mod", 0) or 0)
    hero_light_attack = int(light_fx.get("combat_mod", 0) or 0)
    enemy_light_attack = DARK_COMBAT_PENALTY if light_fx.get("natural_dark") else 0
    player["_env_attack_mod"] = weather_attack + hero_light_attack
    for ally in allies:
        ally["_env_attack_mod"] = weather_attack + hero_light_attack
    for enemy in active:
        enemy["_env_attack_mod"] = weather_attack + enemy_light_attack
    surprise = world.get("encounter_surprise")
    initiator = "heroes" if surprise == "player" else ("enemy" if surprise == "enemy" else None)
    initiator = _early_game_reaction_initiator(
        state, player, initiator, combat_round=int(combat_meta.get("round", 1) or 1)
    )
    if "encounter_surprise" in world:
        world_out = dict(world)
        world_out.pop("encounter_surprise", None)
    weather_logs = _apply_weather_hazard(player, world, rng=rng)
    _register_environmental_damage_terminal(player, weather_logs)
    resolved_decl: TurnDeclaration | None = declaration
    flee_allowed = _can_attempt_flee(player)
    if flee_requested and flee_allowed:
        hero_fled, flee_logs, chase_state = _attempt_flee(
            scene,
            player,
            active,
            sides,
            rng,
            existing_chase=combat_meta.get("chase"),
            intent=intent,
            force_escape=bool(choices["sacrificed"]),
        )
        if not hero_fled and _is_valid_flee_destination(state, flee_dest_id):
            hero_fled, chase_state = _enforce_flee_attempt_limit(
                chase_state,
                attempts=int(combat_meta.get("flee_attempts", 0) or 0),
            )
            if hero_fled:
                flee_logs.append("Após uma perseguição prolongada, os inimigos perdem o rastro.")
        _publish_sacrifice_offer(state, party, chase_state, hero_fled=hero_fled, logs=flee_logs)
        combat_meta["chase"] = chase_state
        logs += weather_logs + logs_pre_flee + flee_logs
    elif flee_requested:
        chase_state = {
            **dict(combat_meta.get("chase") or {}),
            "eligible": False,
            "blocked_reason": "lifecycle",
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
        _mark_nonlethal(decl, intent)
        resolved_decl = decl
        chase_refusal = _chase_attack_gate(combat_meta, decl)  # SPEC-325 R11
        # alvo inválido (inimigo já caiu / declaração pré-computada) → 1º inimigo ativo
        if (
            decl.acao
            and decl.acao.kind == "attack"
            and decl.acao.target_id not in {e["id"] for e in active}
        ):
            from services import mechanics_trace as _mt

            _mt.record_step(
                "target_redirect",
                actor=_PLAYER_ID,
                target=active[0]["id"],
                reason="target_not_active",
            )
            decl.acao.target_id = active[0]["id"]
        elif decl.acao and decl.acao.kind == "card":
            from services import cards

            declared_card = cards.get_card(decl.acao.card_id or "") or {}
            decl.acao.target_id = _card_target_for(
                declared_card,
                decl.acao.target_id,
                active_ids=[e["id"] for e in active],
                friendly_ids=[_PLAYER_ID] + [aid for aid in ally_ids if aid],
            )
        round_state = {
            "player": player,
            "_player_reaction_card_id": state.get("player_reaction_card_id"),
        }
        out = orch.run_round(
            scene,
            actors_by_id,
            sides,
            round_state,
            declarations={_PLAYER_ID: decl},
            prepared_abyss=scene.get("abyss_events"),
            initiator=initiator,
            rng=rng,
            **({"refusal": chase_refusal} if chase_refusal else {}),
        )
        if chase_refusal:
            combat_meta["round"] = max(0, int(combat_meta.get("round", 1) or 1) - 1)
        _sync_enemy_knowledge(enemies)
        _reveal_resistances(out.get("attacks") or [], enemies, sides)
        logs += weather_logs + out["logs"]
        # Gasto BRUTO da economia da Carta. O delta líquido antes/depois era
        # incorreto para classes cujo próprio uso repõe Entropia no mesmo turno.
        player_cards = [
            used for used in (out.get("cards_used") or []) if used.get("actor_id") == _PLAYER_ID
        ]
        player["_last_entropy_spent"] = sum(
            int((used.get("economy") or {}).get("cost", 0) or 0) for used in player_cards
        )
        player["_last_used_active"] = bool(player_cards)
        player["_last_ability_id"] = player_cards[-1].get("card_id") if player_cards else None
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
        attempted=(hero_fled or flee_requested or _PLAYER_ID in (out.get("resolved_turns") or [])),
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
    # SPEC-226 R1: só quem transitou para morto NESTA rodada gera XP/kill/evento.
    newly_dead = [
        e
        for e in dead
        if not e.get("xp_awarded") and str(e.get("id") or e.get("name")) not in dead_before
    ]
    # SPEC-325 R9/D2: inimigo derrubado sem matar rende o mesmo XP/loot do abate.
    downed = [e for e in enemies if e.get("incapacitated") and e.get("nonlethal_by")]
    newly_downed = [
        e
        for e in downed
        if not e.get("xp_awarded") and str(e.get("id") or e.get("name")) not in dead_before
    ]
    for e in newly_dead + newly_downed:
        e["xp_awarded"] = True
    for e in dead + downed:
        e["xp_awarded"] = True
    if newly_dead:
        bestiary_knowledge = disc.record_kills(bestiary_knowledge, newly_dead, turn)
        bk_changed = True

    player_dead = bool(out.get("player_dead")) or bool(player.get("dead"))
    combat_over = bool(out.get("ended")) or hero_fled or player_dead
    if combat_over and not player_dead:
        for participant in [player] + allies:
            if (
                not participant.get("dead")
                and not participant.get("estado_terminal")
                and not death_flow.critical_spaces_full(participant)
            ):
                death_flow.reset_terminal_episode(participant)  # SPEC-231 R6
            recovery_state = death_flow.post_combat_consciousness(participant)
            participant["post_combat_state"] = recovery_state
            if recovery_state == "inconsciente":
                participant["conscious"] = False
            elif recovery_state == "acordado":
                participant["conscious"] = True
    victory = combat_over and not player_dead and not hero_fled and bool(dead or downed)

    # ---- XP determinístico (fugitivo/queda letal não contam) ----
    level_up_events: list[dict] = []
    kill_xp = 0  # SPEC-226 R10: ganho individual p/ o guard narrativo
    if (newly_dead or newly_downed) and not player_dead and not is_simulation:
        import progression as pg

        xp = pg.xp_for_kills(newly_dead + newly_downed)
        if xp:
            player, level_up_events = pg.grant_xp(player, xp)
            kill_xp = xp
            # SPEC-199 R1: XP/nível NÃO entram em `logs` (nem na prosa/fallbacks);
            # chegam à UI por `last_turn_outcome` -> `turn_outcome`.

    # ---- Narração ----
    from services import prose_guard

    aberturas = prose_guard.ultimas_aberturas(messages)
    loc = state.get("world", {}).get("current_location", "")
    if player_dead:
        killer = _killer_identity(active)[0]
        narrative = _narrate_fall(player, logs, killer)
    elif is_simulation:
        suffix = "\n\nVitória no laboratório." if victory else "\n\nEscolha a próxima ação."
        narrative = "⚔️ " + "\n".join(f"• {line}" for line in logs if line) + suffix
    else:
        world_pack = build_context_pack(
            state,
            query=f"{loc} {intent}",
            purpose="combat_narration",
            token_budget=1200,
            include_lore=False,  # SPEC-317 R8: so world_state_block e usado
        )
        narrative = _narrate(
            player,
            enemies,
            logs,
            spawned_flavor,
            intent,
            victory,
            world_pack.world_state_block
            + "\n"
            + _ambient_for_combat(state.get("world") or {}, player)
            + _perceived_for_combat(state),
            aberturas,
            manifest=combat_meta.get("encounter"),
            withhold=_faction_withhold_clause(
                combat_meta.get("encounter"), state.get("factions"), state.get("faction_intel")
            ),
        )
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
                "downed_ids": (_downed_identity_tokens(player) if player_dead else []),
            },
        )
        narrative = summ.narrative_or_fallback(conflict_sum, narrative)
    narrative = prose_guard.sanitize_meta_preamble(narrative)
    prose_guard.log_if_repeats(narrative, aberturas[0] if aberturas else "", where="combate")

    # ---- Montagem do resultado (contrato preservado) ----
    # SPEC-231 R4: o snapshot de aliados transitórios carrega as fichas PÓS-rodada.
    if scene_tr:
        live_tr = {str(a.get("id") or a.get("name")): a for a in allies if a.get("transient")}
        scene_tr = [live_tr.get(str(a.get("id") or a.get("name")), a) for a in scene_tr]
        combat_meta["scene_allies"] = scene_tr
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
        # SPEC-203 R5/R7: resolving → ended + snapshot do desfecho.
        _outcome = _encounter_outcome(
            player=player, enemies=enemies, hero_fled=hero_fled, player_dead=player_dead
        )
        combat_meta = _finish_encounter(
            combat_meta,
            enemies,
            _outcome,
            loot=bool(victory) and not is_simulation,
        )
        # SPEC-296 R2: inimigo que fugiu pode voltar com reforços (1 alerta/encontro).
        if not is_simulation:
            _alerted = _flee_alert_world(world_out or world, enemies, _outcome)
            if _alerted is not None:
                world_out = _alerted
    else:
        # Narração de entrada enviada → encontro confirmado (entering→active).
        if combat_meta.get("phase") == "entering":
            combat_meta = em.safe_transition(combat_meta, "active")
        if em.is_valid_manifest(combat_meta.get("encounter")):
            combat_meta["encounter"] = em.sync_statuses(
                combat_meta["encounter"], enemies, int(combat_meta.get("round", 0) or 0)
            )
    result = {
        "messages": [AIMessage(content=narrative)],
        "player": player,
        "enemies": [] if combat_over else enemies,
        "combat": combat_meta,
        "combat_target": None if combat_over else combat_target,
        "next": "loot" if victory and not is_simulation else None,
        "archive_due": combat_over and not is_simulation,
        "party": _merge_formal_party(party, allies),
        "combat_declaration": None,  # consumida (não vaza para o próximo turno)
        "combat_origin_hint": None,
        "combat_encounter_hint": None,  # SPEC-203: one-shot consumido
        "combat_target_ref": None,
    }
    if conflict_sum is not None:
        result["conflict_summary"] = conflict_sum
    if choices["events"]:
        # SPEC-325 R12: `companion_abandoned` (sem o destino: ele fica selado na party).
        result["event_log"] = list(state.get("event_log") or []) + choices["events"]
    if world_out is not None:
        result["world"] = world_out
    if bk_changed:
        result["bestiary_knowledge"] = bestiary_knowledge
    if kill_xp:
        from services.turn_outcome import record_gain

        _bl = record_gain(state.get("turn_baseline"), "xp", kill_xp, "combat")
        if _bl is not state.get("turn_baseline"):
            result["turn_baseline"] = _bl

    # SPEC-305 R11: vitoria no alvo de quest de mundo (cerco/ocupacao/ascensao/objeto) = 1
    # evidencia `combat_won` por combate.
    if (
        victory
        and not is_simulation
        and any(q.get("world_kind") for q in state.get("quests") or [])
    ):
        from services import quest_log as _quest_log

        _wstate = state.get("world") or {}
        _synced = _quest_log.sync_combat_progress(
            state.get("quests") or [],
            str(_wstate.get("current_location_id") or ""),
            turn=int(_wstate.get("turn_count", 0) or 0),
        )
        if _synced != list(state.get("quests") or []):
            result["quests"] = _synced

    # SPEC-313 R20: a morte da criatura-ancora numa quest `cacar_criatura` e a unica prova da
    # caca (inimigo que fugiu e combate simulado nao contam).
    if (
        victory
        and not is_simulation
        and any(q.get("world_kind") == "cacar_criatura" for q in state.get("quests") or [])
    ):
        from services import quest_log as _quest_log
        from services import world_pressures as _wp
        from services.discovery import normalize_bestiary_id as _normalize_bestiary_id

        _w = state.get("world") or {}
        _hunted = _quest_log.sync_hunt_progress(
            result.get("quests", state.get("quests") or []),
            [_normalize_bestiary_id(e) for e in dead + downed],
            _wp.region_of(str(_w.get("current_location_id") or "")),
            turn=int(_w.get("turn_count", 0) or 0),
        )
        if _hunted != list(result.get("quests", state.get("quests") or [])):
            result["quests"] = _hunted

    # ---- Reflexo dos aliados transitórios no NPC de origem ----
    if scene_tr:
        result["npcs"] = _reflect_scene_allies(state, scene_tr, allies, combat_over)

    # ---- Eventos de mundo (kills canônicas + level up + morte do jogador) ----
    engine_events = [] if is_simulation else _kill_events(newly_dead) + level_up_events
    if out.get("recidiva_event"):
        engine_events.append(out["recidiva_event"])

    death_events = []
    if player_dead:
        stabilization = next(
            (
                entry
                for entry in reversed(out.get("stabilizations") or [])
                if entry.get("actor_id") == _PLAYER_ID
            ),
            {},
        )
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
            "killer": _killer_identity(active)[0],
        }
        result["death_pending"] = True
        result["combat"] = {**combat_meta, "active": False, "scene": None}
        result["enemies"] = []
        result["combat_target"] = None
        result["next"] = None
        result["archive_due"] = not is_simulation
        killer, killer_id = _killer_identity(active)
        death_events.append(
            {
                "type": "player_downed",
                "actor_id": "player",
                "target_id": "player",
                "detail": f"{player.get('name', 'O herói')} tombou em combate"
                + (f" diante de {killer}" if killer else ""),
                "payload": {
                    "killer": killer,
                    "killer_id": killer_id,
                    "location": loc,
                    "boss_present": any(
                        str(e.get("categoria", "")).lower() in ("chefe", "nomeado") for e in enemies
                    ),
                },
                "source": "combat",
            }
        )
    if not is_simulation:
        engine_events += death_events
    if engine_events:
        result["pending_world_events"] = (
            state.get("pending_world_events", []) or []
        ) + engine_events

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
def _can_attempt_flee(player: dict) -> bool:
    """Fuga exige protagonista em fase capaz de iniciar uma perseguição."""
    return (
        bool(player.get("conscious", True))
        and not bool(player.get("dead"))
        and not bool(player.get("estado_terminal"))
        and not bool(player.get("last_stand_pending"))
        and not bool(player.get("incapacitated"))
    )


def _attempt_flee(
    scene: dict,
    player: dict,
    active: list[dict],
    sides: dict,
    rng,
    *,
    existing_chase: dict | None = None,
    intent: str = "",
    force_escape: bool = False,
) -> FleeDecision:
    """Tenta escapar via motor de perseguição (09). Enredado (root) não foge.
    Sucesso na trilha (Escapou) encerra o combate; senão o herói segue preso.

    SPEC-325: `intent` escolhe a abordagem (R10, `RPG_CHASE_APPROACH`); `force_escape`
    é o sacrifício aceito (R13: o herói escapa nesta rodada, sem teste)."""
    import combat_mechanics as cm
    from services import chase, combat_flags, combat_intents
    from services.conflict_resolution import virtude_value

    if not _can_attempt_flee(player):
        return FleeDecision(
            False,
            [f"{player.get('name', 'O herói')} está em Estado Terminal e não pode fugir."],
            {"eligible": False, "blocked_reason": "lifecycle"},
        )
    if cm.has_control(player, "root"):
        return FleeDecision(
            False,
            [f"{player.get('name', 'O herói')} está ENREDADO — impossível fugir."],
            {
                "eligible": False,
                "blocked_reason": "rooted",
            },
        )
    chase_state = (
        dict(existing_chase)
        if chase.can_resume(existing_chase, _PLAYER_ID, active)
        else chase.start_chase(scene, _PLAYER_ID, active)
    )
    previous_track = chase_state.get("trilha")
    if force_escape:
        chase_state.update(trilha="escapou", escapou=True, alcancado=False, eligible=True)
        return FleeDecision(
            True,
            [f"{player.get('name', 'O herói')} aproveita a brecha e FOGE do combate."],
            chase_state,
        )
    difficulty = chase.chase_difficulty(active[0]) if active else 12
    virtude_key = "agilidade"
    approach_mode = combat_flags.mode("chase_approach")
    approach = combat_intents.chase_approach(intent) if approach_mode != "off" else None
    if approach_mode == "on":
        chase_state.pop("approach", None)  # a abordagem vale por rodada; sem palavra = Agilidade
    if approach:
        if approach_mode == "on":
            virtude_key = chase.approach_virtude(approach)
            chase_state["approach"] = approach
        else:
            _log_event("combat", "chase_approach_shadow", approach=approach)
    ally_rolls = [(aid, chase.luck_roll(rng)) for aid in (sides or {}).get("ally") or []]
    chase.resolve_chase_round(
        chase_state,
        condutor_virtude=virtude_value(player, virtude_key),
        difficulty=difficulty,
        companion_luck=[roll for _aid, roll in ally_rolls],
        rng=rng,
    )
    if combat_flags.mode("chase_abandon") == "on":
        # R12: Sorte por aliado da rodada, base do "deixar <nome>" da rodada seguinte.
        chase_state["last_luck"] = {str(aid): roll for aid, roll in ally_rolls}
    chase_state["eligible"] = True
    if chase_state.get("escapou"):
        return FleeDecision(
            True, [f"{player.get('name', 'O herói')} rompe o cerco e FOGE do combate."], chase_state
        )
    if chase_state.get("alcancado"):
        log = f"{player.get('name', 'O herói')} tenta fugir, mas os inimigos o alcançam."
    elif (chase_state.get("_last") or {}).get("sucesso"):
        log = (
            f"{player.get('name', 'O herói')} avança na fuga: "
            f"{previous_track} → {chase_state.get('trilha')}."
        )
    else:
        log = (
            f"{player.get('name', 'O herói')} perde terreno na fuga: "
            f"{previous_track} → {chase_state.get('trilha')}."
        )
    return FleeDecision(False, [log], chase_state)


def _apply_weather_hazard(player: dict, world: dict, *, rng=None) -> list[str]:
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
        bypass_armor=True,
        directed_region=None,
        rng=rng,
    )
    label = (
        effects.get("label")
        or world.get("weather", "")
        or world.get("weather_state", "clima hostil")
    )
    return [
        f"{player.get('name', 'O herói')} sofre {dot} pelo clima ({label}) "
        f"(Vitalidade {player['vitalidade']}).",
        *result["log"],
    ]


def _register_environmental_damage_terminal(player: dict, damage_logs: list[str]) -> None:
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


def _apply_flee_travel(
    state: dict, result: dict, flee_dest_id: str, player: dict, logs: list[str]
) -> None:
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
        "last_player_action": dict(previous_combat.get("last_player_action") or {}),
    }
    # SPEC-203: o desfecho (fase/manifesto/resultado) sobrevive à viagem de fuga.
    for key in ("phase", "outcome", "encounter", "result"):
        if key in previous_combat:
            result["combat"][key] = previous_combat[key]
    result["enemies"] = []
    result["combat_target"] = None
    result["next"] = None
    result["needs_replan"] = True
    result["combat_origin_hint"] = None


def _reflect_scene_allies(
    state: dict, scene_tr: list[dict], allies: list[dict], combat_over: bool
) -> dict:
    """Aliado TRANSITÓRIO reflete Vitalidade/morte no NPC de origem (sem 'aliado
    imortal'). Não vira party permanente."""
    npcs_out = {**(state.get("npcs") or {})}
    by_name = {(a.get("name") or a.get("id")): a for a in allies}
    for tr in scene_tr:
        name = tr.get("name") or ""
        key = next(
            (
                k
                for k in npcs_out
                if k == name or (isinstance(npcs_out[k], dict) and npcs_out[k].get("name") == name)
            ),
            None,
        )
        if key is None or not isinstance(npcs_out.get(key), dict):
            continue
        live = by_name.get(name) or tr
        npc = {**npcs_out[key]}
        npc["vitalidade"] = int(live.get("vitalidade", 0) or 0)
        npc["max_vitalidade"] = int(live.get("max_vitalidade", 1) or 1)
        import gamedata

        gamedata.sync_legacy_hp_aliases(npc)
        if live.get("dead") or live.get("status") == "morto":
            # SPEC-230 R4: mesmo formato de apply_npc_death (status/in_scene/died_turn).
            npc["status"] = "morto"
            npc["in_scene"] = False
            npc.setdefault("died_turn", int((state.get("world") or {}).get("turn_count", 0) or 0))
        npcs_out[key] = npc
    return npcs_out


def _merge_formal_party(party: list[dict], live_allies: list[dict]) -> list[dict]:
    """Persiste a ficha v4 mutada dos companheiros formais (transitórios ficam fora)."""
    live_by_id = {
        str(a.get("id") or a.get("name")): a for a in live_allies if not a.get("transient")
    }
    merged: list[dict] = []
    for companion in party:
        key = str(companion.get("id") or companion.get("name"))
        live = dict(live_by_id.get(key) or companion)
        _mirror_vitals(live)
        merged.append(live)
    return merged
