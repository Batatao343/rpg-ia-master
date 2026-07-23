"""
agents/combat.py
Agente de Combate.

Arquitetura: a IA só IDENTIFICA (linguagem natural -> CombatAction) e NARRA.
Toda a mecânica é resolvida em Python (combat_mechanics.py), de forma
determinística e testável offline.

Fluxo de 1 chamada = 1 round completo:
  spawn (1º round) -> iniciativa -> parse da ação -> resolução em ordem de
  iniciativa (tick condições/cooldowns, ação do herói, turnos dos inimigos)
  -> narração do log mecânico.
"""
from typing import List, Dict, Optional
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

import re

from state import GameState, EnemyStats
from llm_setup import ModelTier, get_llm
from gamedata import ABILITIES
from agents.bestiary import generate_new_enemy
from services import discovery as disc
from services import graph_resolver as gr
from services.context_builder import build_context_pack
import combat_mechanics as cm


def _canonical_enemy_id(enemy: Dict) -> Optional[str]:
    """Id canônico (entities.json, type npc) de um inimigo morto, ou None se genérico.

    O spawn dá ids do tipo `{template_id}_{i}` — remove o sufixo de instância e casa
    contra o grafo. Inimigo de bestiário sem entrada canônica → None (não gera evento).
    """
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
    """Propostas npc_killed para os mortos CANÔNICos deste round (genéricos são ignorados)."""
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


# --- MODELOS DE IDENTIFICAÇÃO (IA) ---
class EnemyIdentification(BaseModel):
    name: str = Field(description="Nome singular do inimigo. Ex: 'Goblin', 'Rato da Peste'")
    count: int = Field(description="Quantidade destes inimigos na cena.")


class EncounterScanner(BaseModel):
    detected_enemies: List[EnemyIdentification]
    flavor_text: str = Field(description="Descrição curta da entrada dos inimigos em combate.")


class CombatAction(BaseModel):
    """A IA traduz a fala livre do jogador para uma ação mecânica canônica."""
    ability_id: str = Field(description="Chave EXATA do catálogo de habilidades, 'ataque_basico' ou 'improvisado'.")
    target: str = Field(default="", description="Nome ou id do inimigo alvo. Vazio = primeiro inimigo.")
    is_allowed: bool = Field(default=True, description="False se a ação não faz sentido para a classe/ficha.")
    reason: str = Field(default="", description="Curta justificativa do gating (por que falha, se for o caso).")
    # Fase 4.3: "bebo a poção" -> uso de item (id da lista de USÁVEIS do prompt).
    item_id: str = Field(default="", description="Se o jogador USA UM ITEM (poção etc.): id exato do item. Vazio caso contrário.")


def _instance_from_template(template: Dict, i: int) -> Dict:
    """Entrada de bestiário -> instância de combate (mesmos defaults do spawn)."""
    inst = dict(template)
    inst["id"] = f"{template.get('id', 'enemy')}_{i}"
    inst.setdefault("stamina", 10)
    inst.setdefault("mana", 0)
    inst["defense"] = inst.get("defense", inst.get("ac", 10))
    inst.setdefault("attack_mod", 0)
    inst["active_conditions"] = []
    inst.setdefault("status", "ativo")
    inst.setdefault("behavior", {"profile": "feroz"})
    inst["hp"] = inst.get("max_hp", inst.get("hp", 10))
    return inst


# --- SPAWN (mantém integração com bestiário/cache) ---
def _spawn_enemies_integrated(messages: List, target_hint: str, state: Optional[Dict] = None):
    print(f"⚡ [COMBAT] Escaneando cena por inimigos. Dica: '{target_hint}'...")
    llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
    sys_prompt = f"""
    Analise a narrativa recente. O combate começou.
    Identifique QUAIS inimigos estão presentes e QUANTOS.
    Use a dica do alvo se ajudar: "{target_hint}".
    Exemplo: "Três orcs surgem" -> [{{name: "Orc", count: 3}}].
    """
    try:
        scanner = llm.with_structured_output(EncounterScanner)
        scan_result = scanner.invoke([SystemMessage(content=sys_prompt)] + messages[-2:])
        if not isinstance(scan_result, EncounterScanner):
            raise ValueError("scanner fallback")

        final_enemies_list = []
        for identified in scan_result.detected_enemies:
            template = generate_new_enemy(identified.name, context=target_hint)
            for i in range(identified.count):
                instance = template.copy()
                instance["id"] = f"{template['id']}_{i+1}"
                instance["name"] = f"{template['name']} {i+1}" if identified.count > 1 else template["name"]
                instance.setdefault("stamina", 10)
                instance.setdefault("mana", 0)
                instance.setdefault("defense", instance.get("ac", 10))
                instance.setdefault("attack_mod", 0)
                instance.setdefault("active_conditions", [])
                instance.setdefault("status", "ativo")
                # Fase 2.5b: perfil de comportamento (bestiário curado traz; LLM pode
                # omitir -> default feroz = comportamento clássico "luta até morrer")
                instance.setdefault("behavior", {"profile": "feroz"})
                final_enemies_list.append(instance)
        # Fase 4.6 (R1/R2): CLAMP + PISO determinísticos — o LLM narra a horda,
        # o motor decide quantos entram de fato (orçamento por tier/nível/party).
        if state is not None:
            import encounter_budget as eb
            import party as party_mod
            from gamedata import get_location
            world = state.get("world") or {}
            # R5 (fix-playtest-achados): encontro FORÇADO carimba `encounter_eff_danger`
            # (perigo escalado pelo nível; apex = cheio). Combate DELIBERADO não carimba
            # → usa danger_level cheio (o jogador escolheu a briga). One-shot: consome.
            danger = int(world.pop("encounter_eff_danger", None) or world.get("danger_level", 1) or 1)
            level = int((state.get("player") or {}).get("level", 1) or 1)
            # spec aliados-em-combate (R6): aliados transitórios (amigos em cena)
            # também contam p/ o orçamento — mais aliados, inimigos escalam junto.
            n_allies = len(party_mod.active_allies(state)) + len(party_mod.scene_allies(state))
            budget = eb.encounter_budget(level, danger, n_allies)
            final_enemies_list, cut_logs = eb.clamp_encounter(final_enemies_list, budget,
                                                              player_level=level)
            loc = get_location(world.get("current_location_id", "")) or {}
            final_enemies_list, fill_logs = eb.fill_encounter(
                final_enemies_list, budget, loc, danger,
                turn=int(world.get("turn_count", 0) or 0),
                make_instance=_instance_from_template)
            extra = " ".join(cut_logs + fill_logs)
            if extra:
                return final_enemies_list, f"{scan_result.flavor_text} {extra}".strip()
        return final_enemies_list, scan_result.flavor_text

    except Exception as e:
        print(f"⚠️ Erro no Spawn Integrado: {e}")
        return [{
            "id": "fallback_enemy_1", "name": "Inimigo Sombrio", "hp": 15, "max_hp": 15,
            "defense": 12, "status": "ativo", "active_conditions": [], "attributes": {"dex": 10},
            "abilities": [], "attacks": [{"name": "Golpe", "bonus": 3, "damage": "1d6"}],
            "stamina": 0, "mana": 0, "attack_mod": 3,
        }], "Algo hostil emerge das sombras!"


# --- PARSER (IA identifica a ação) ---
def _last_human_text(messages: List) -> str:
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


_UNIVERSAL_ABILITIES = ("ataque_basico", "improvisado")


def _allowed_ability_ids(player: Dict) -> set:
    """Ids que ESTA ficha pode usar EM COMBATE: conhecidas ATIVAS + universais.
    Passiva/utilitária (spec arvores-habilidade-classes) não é ação de combate."""
    known = {str(k) for k in (player.get("known_abilities") or [])}
    return {aid for aid in known
            if aid in ABILITIES
            and ABILITIES[aid].get("ability_kind", "active") == "active"} \
        | set(_UNIVERSAL_ABILITIES)


def _ability_catalog_for(player: Dict) -> str:
    """Só as habilidades RELEVANTES (conhecidas + universais) — match por id EXATO
    (Fase 4.1: known_abilities guarda ids canônicos). Economiza tokens no parse."""
    def _line(aid, a):
        return f"- {aid}: {a.get('name')} | custo {a.get('cost')} {a.get('resource_type')} | {a.get('description','')[:60]}"

    linhas = [_line(aid, ABILITIES[aid])
              for aid in sorted(_allowed_ability_ids(player)) if aid in ABILITIES]
    if not linhas:  # fallback mínimo: as universais
        for aid in _UNIVERSAL_ABILITIES:
            a = ABILITIES.get(aid, {})
            linhas.append(_line(aid, a) if a else f"- {aid}: {aid}")
    return "\n".join(linhas)


def _parse_combat_action(player: Dict, enemies: List[Dict], intent: str) -> Dict:
    """IA mapeia a fala livre -> CombatAction. Guard de fallback resiliente."""
    fallback = {"ability_id": "ataque_basico",
                "target": enemies[0]["name"] if enemies else "",
                "is_allowed": True, "reason": ""}
    if not intent:
        return fallback

    enemy_names = ", ".join(e.get("name", "?") for e in enemies) or "—"
    # Fase 4.3: itens consumíveis presentes no inventário (id: nome xqty)
    import inventory as inv_mod
    usables = []
    for e in (player.get("inventory") or []):
        if isinstance(e, dict):
            item = inv_mod.ARTIFACTS_DB.get(e.get("id", "")) or {}
            if str(item.get("type", "")).lower() in ("consumable", "potion"):
                usables.append(f"- {e['id']}: {item.get('name', e['id'])} x{e.get('qty', 1)}")
    usables_block = "\n".join(usables) or "- (nenhum)"
    sys = SystemMessage(content=f"""
    Você é o IDENTIFICADOR de ações de combate. NÃO resolva mecânica, só classifique.
    Traduza a fala do jogador para uma ação canônica.

    Classe: {player.get('class_name', '')}
    Virtudes: {player.get('virtudes', {})}

    CATÁLOGO DE HABILIDADES (use a CHAVE exata em ability_id):
    {_ability_catalog_for(player)}

    ITENS USÁVEIS no inventário (se o jogador USAR um item, preencha item_id com a chave exata):
    {usables_block}

    Inimigos presentes: {enemy_names}

    Regras:
    - Escolha o ability_id do catálogo que melhor casa com a intenção. Ataque comum -> 'ataque_basico'.
    - Se o jogador usa um ITEM ("bebo a poção"), preencha item_id e deixe ability_id='ataque_basico'.
    - Se a ação for impossível para esta classe/ficha, is_allowed=False e explique em reason.
    - target = nome de um inimigo presente (ou vazio para o primeiro).
    """)
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
        res = llm.with_structured_output(CombatAction).invoke([sys, HumanMessage(content=intent)])
        if isinstance(res, CombatAction):
            # Fase 4.3: uso de item tem prioridade (gate real fica no use_item_in_combat)
            if getattr(res, "item_id", ""):
                return {"ability_id": "ataque_basico", "target": res.target,
                        "is_allowed": True, "reason": "", "item_id": res.item_id}
            aid = res.ability_id if res.ability_id in ABILITIES else "ataque_basico"
            # Fase 4.1 (R7): gate DETERMINÍSTICO — habilidade fora da ficha não
            # passa nem se o LLM disser que pode (id alucinado/de outra classe).
            if aid not in _allowed_ability_ids(player):
                nome = ABILITIES.get(aid, {}).get("name", aid)
                return {"ability_id": aid, "target": res.target, "is_allowed": False,
                        "reason": f"{player.get('name', 'O herói')} não conhece {nome}."}
            return {"ability_id": aid, "target": res.target,
                    "is_allowed": res.is_allowed, "reason": res.reason}
    except Exception as e:
        print(f"⚠️ [COMBAT PARSE] {e}")
    return fallback


# --- NARRAÇÃO (IA descreve o log mecânico) ---
# (spec checkpoints-morte: _death_template/_narrate_downed do "O Saque" REMOVIDOS —
# a queda letal usa _narrate_fall + a tela de morte decide o desfecho.)


def _narrate_fall(player: Dict, logs: List[str], killer: str = "") -> str:
    """spec checkpoints-morte: narração DETERMINÍSTICA da queda letal (2ª pessoa,
    sem finalidade). A escolha (restaurar/aceitar) é da TELA DE MORTE — aqui só a
    tomba. Sem LLM (a tela precisa aparecer rápido e o desfecho ainda é aberto)."""
    quem = f" diante de {killer}" if killer else ""
    golpes = "\n".join(f"• {l}" for l in logs[-4:]) if logs else ""
    return (f"⚔️ {golpes}\n\n☠️ Você tomba{quem}. A escuridão te engole — mas a "
            f"Roda do Abismo ainda não decidiu. Voltar ao último respiro seguro, "
            f"ou aceitar o fim aqui?").strip()


def _narrate(player: Dict, enemies: List[Dict], logs: List[str],
             spawned_flavor: Optional[str], intent: str, victory: bool,
             world_ctx: str = "", player_dead: bool = False,
             aberturas: Optional[List[str]] = None) -> str:
    from services import prose_guard
    log_str = "\n".join(logs) if logs else "Nada acontece."
    alive = [f"{e['name']} (HP {e['hp']}/{e['max_hp']})" for e in enemies if e.get("status") == "ativo"]
    # spec polish-prosa: R1 (varie a abertura) + R2 (morte em 2ª pessoa).
    varie = prose_guard.openings_clause(aberturas or [])
    if player_dead:
        fecho = ("O HERÓI MORREU NESTE ROUND — narre a queda como o FECHO de uma saga: "
                 "solene, definitivo, digno da crônica (3 a 4 frases). Sem deixa para "
                 "próxima ação. SEMPRE em 2ª pessoa ('você'), NUNCA em 3ª ('o herói', "
                 "'o viajante', 'o aventureiro').")
    elif victory:
        fecho = "O combate foi VENCIDO — encerre com o respiro da vitória."
    else:
        fecho = "Termine com tensão e uma deixa para a próxima ação do jogador."
    sys = SystemMessage(content=f"""
    <role>Narrador de Combate — Dark Fantasy</role>
    Descreva o round de combate em 1 a 2 parágrafos, com base APENAS no log mecânico.
    Não invente dano nem resultados fora do log. Seja visceral mas conciso.
    Use o CONTEXTO DO MUNDO só para AMBIENTAR (local, quem manda) — números vêm só do log.

    {("ENTRADA: " + spawned_flavor) if spawned_flavor else ""}
    Ação do jogador (fala): {intent}

    {world_ctx}

    <log_mecanico>
    {log_str}
    </log_mecanico>

    Herói: {player.get('name')} HP {player.get('hp')}/{player.get('max_hp')}
    Inimigos vivos: {', '.join(alive) if alive else 'nenhum'}

    {fecho}{varie}
    """)
    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.FAST)
        if getattr(llm, "is_fallback", False):
            raise RuntimeError("fallback")
        res = llm.invoke([sys] + [HumanMessage(content=intent or "Continue o combate.")])
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in text
            )
        if text.strip():
            return text
    except Exception as e:
        print(f"⚠️ [COMBAT NARRATE] {e}")
    # Fallback determinístico: devolve o próprio log legível.
    prefix = (spawned_flavor + "\n\n") if spawned_flavor else ""
    suffix = "\n\nVitória! O campo silencia." if victory else "\n\nO que você faz?"
    return f"⚔️ {prefix}" + "\n".join(f"• {l}" for l in logs) + suffix


# --- NÓ PRINCIPAL ---
def combat_node(state: GameState):
    messages = state.get("messages", [])
    if not messages:
        return {"next": "dm_router"}

    player = dict(state["player"])
    player.setdefault("ability_cooldowns", {})
    player.setdefault("active_conditions", [])
    enemies = [dict(e) for e in (state.get("enemies") or [])]
    combat_meta = dict(state.get("combat") or {})

    last_msg = messages[-1]
    is_combat_start = isinstance(last_msg, SystemMessage) and "COMBAT START" in str(last_msg.content)
    combat_target = state.get("combat_target", "Inimigos")

    active = [e for e in enemies if e.get("status") == "ativo"]
    spawned_flavor = None
    bestiary_knowledge = dict(state.get("bestiary_knowledge") or {})
    bk_changed = False
    turn = int(state.get("world", {}).get("turn_count", 0) or 0)
    if is_combat_start and not active:
        enemies, spawned_flavor = _spawn_enemies_integrated(messages, combat_target, state)
        active = [e for e in enemies if e.get("status") == "ativo"]
        print(f"⚔️ Combate: {[e['name'] for e in active]}")
        # Fase 3.2 (R2): 1ª vez que estas criaturas entram em cena neste combate.
        bestiary_knowledge = disc.record_encounter(bestiary_knowledge, active, turn)
        bk_changed = True

    # Sem inimigos = vitória (ou nada a fazer).
    if not active:
        return {
            "messages": [AIMessage(content="O silêncio retorna ao campo de batalha. Vitória.")],
            "next": "loot", "combat_target": None, "enemies": [],
            "combat": {"active": False, "round": combat_meta.get("round", 0), "order": []},
            "archive_due": True,  # fim de combate = evento relevante
        }

    # Fase 6.5: clima em campo aberto — modificador de acerto SIMÉTRICO (leitura
    # pontual via flags _env; nunca condição gravada) + dot de miasma outdoor.
    import world_utils as wu_mod
    wfx = wu_mod.weather_effects(state.get("world") or {})
    env_atk = int(wfx.get("combat_attack_mod", 0) or 0)
    env_dot = int(wfx.get("dot_outdoor", 0) or 0)
    # spec itens-vivos-e-luz (R4): lutar no escuro sem luz penaliza o acerto de
    # todos (simétrico); uma fonte de luz do herói ilumina a cena e zera isso.
    light = wu_mod.light_level(state.get("world") or {}, player)
    env_atk += int(light.get("combat_mod", 0) or 0)
    if env_atk:
        player["_env_attack_mod"] = env_atk
        for e in enemies:
            e["_env_attack_mod"] = env_atk

    # Fase 4.5: aliados ativos entram no combate (mesmo motor, lado 'ally').
    import party as party_mod
    party = party_mod.backfill_party(state.get("party") or [])
    # spec aliados-em-combate (R2/R4): amigos EM CENA viram aliados TRANSITÓRIOS.
    # Nascem no início do combate e persistem em combat_meta p/ acumular dano
    # entre rounds; nunca entram na party permanente (R3). combat_party = os dois
    # lados do herói só p/ ESTE combate (iniciativa/resolução/alvo de inimigo).
    if is_combat_start or not combat_meta.get("order"):
        scene_tr = party_mod.scene_allies(state)
    else:
        scene_tr = combat_meta.get("scene_allies") or []
    combat_party = party + scene_tr
    allies_active = [a for a in combat_party if a.get("active")
                     and a.get("status", "ativo") == "ativo" and int(a.get("hp", 0)) > 0]
    # passiva do Cavaleiro (Muralha Humana) agora é condicional a party ativa
    player["_party_active"] = bool(allies_active)

    # Iniciativa: rola no 1º round; persiste depois.
    surprise_world_update = None
    if is_combat_start or not combat_meta.get("order"):
        order = cm.roll_initiative(player, active, allies_active)
        # Fase 6.4 (R6): surpresa da detecção — quem foi pego de surpresa cede
        # a iniciativa (±5 no lado); flag transitória consumida AQUI.
        wstate = dict(state.get("world") or {})
        surprise = wstate.pop("encounter_surprise", None)
        if surprise in ("player", "enemy"):
            for slot in order:
                hero_side_slot = slot["side"] in ("hero", "ally")
                if surprise == "player" and hero_side_slot:
                    slot["init"] += 5
                elif surprise == "enemy" and not hero_side_slot:
                    slot["init"] += 5
            order.sort(key=lambda x: x["init"], reverse=True)
            surprise_world_update = wstate
        combat_meta = {"round": 1, "active": True, "order": order,
                       "scene_allies": scene_tr}
    else:
        combat_meta["round"] = combat_meta.get("round", 1) + 1
        combat_meta["active"] = True
        combat_meta["scene_allies"] = scene_tr
    # combate-lifecycle (R3): combat_node RECEBEU rota de combate → zera o
    # contador de ociosidade (só cresce quando o combate fica órfão do router).
    combat_meta["idle_turns"] = 0

    # A IA identifica a ação do jogador.
    intent = _last_human_text(messages)
    action = _parse_combat_action(player, active, intent)

    # FUGA do jogador — determinística, ANTES de resolver. Não-enredado escapa
    # (rompe o cerco e sai do combate); enredado NÃO foge (gate 4.2).
    #  - fix-playtest-achados (R5): fuga por TEXTO ("fujo", "corro").
    #  - combate-lifecycle (R1): VIAGEM durante combate — o router marca
    #    `combat_flee_attempt` + `combat_flee_destination`; a fuga bem-sucedida
    #    aplica a viagem no mesmo turno (não teleporta sem passar pela fuga).
    flee_dest_id = None
    flee_requested = bool(re.search(r"\bfuj|fugir|escap|retir|recu|corr[oe]\b", intent.lower()))
    if state.get("combat_flee_attempt"):
        flee_requested = True
        flee_dest_id = state.get("combat_flee_destination")
    if flee_requested:
        if cm.has_control(player, "root"):
            action = {"ability_id": "ataque_basico", "target": "", "is_allowed": False,
                      "reason": f"{player.get('name','O herói')} está ENREDADO — impossível fugir."}
            flee_dest_id = None  # fuga falhou → sem viagem; inimigos agem
        else:
            action = {"flee": True, "ability_id": "ataque_basico", "target": "",
                      "is_allowed": True, "reason": ""}

    # Resolução determinística em ordem de iniciativa.
    logs: List[str] = []
    hero_resolved = False
    hero_fled = False  # R5: jogador fugiu → encerra o combate após esta rodada
    rnd = int(combat_meta.get("round", 1))

    # spec refatoracao-sistema-classes (etapa 3): zera o contador de ativações do
    # gatilho de Entropia no início do round (per_turn_cap conta por round).
    cm.reset_entropy_turn(player)
    # Arcanista — a caldeira conta o tempo: sem vazão no prazo, estoura (auto-dano).
    logs += cm.tick_boiler(player)
    # Corruptor — Transformação: Carga ≥ leve mantém o debuff do domínio enquanto
    # o combate durar (spec fiacao-regras-orfas-classes R2; renova sem stack).
    logs += cm.apply_transformacao(player)

    # Fase 6.5: miasma/tempestade mordem TODOS em campo aberto (1x por round)
    if env_dot:
        for ent in [player] + [e for e in enemies if e.get("status") == "ativo"]:
            ent["hp"] = max(0, int(ent.get("hp", 0)) - env_dot)
            if ent is not player and ent["hp"] <= 0:
                ent["status"] = "morto"
        logs.append(f"O clima ({wfx.get('label', 'miasma')}) morde a todos: -{env_dot} HP.")
    for slot in combat_meta["order"]:
        if slot["side"] == "hero":
            # Fase 4.2: atordoado perde o turno (tick roda; ação não).
            stunned = cm.has_control(player, "stun")
            logs += cm.tick_conditions(player)
            cm.tick_cooldowns(player)
            if stunned:
                logs.append(f"{player.get('name','Herói')} está ATORDOADO e perde o turno.")
            elif action.get("flee") and int(player.get("hp", 0)) > 0:
                # R5: fuga bem-sucedida — o herói rompe o cerco e sai do combate.
                logs.append(f"{player.get('name','O herói')} rompe o cerco e FOGE do combate.")
                hero_fled = True
            elif int(player.get("hp", 0)) > 0:
                if action.get("item_id"):
                    # Fase 4.3: usar item consome o turno; resolução 100% Python.
                    # spec itens-vivos-e-luz (R5): item ofensivo mira o alvo atual
                    # (efeito hostil vai no inimigo; buff/cura seguem no herói).
                    import inventory as inv_mod
                    tgt = (cm._find_target(enemies, action.get("target", ""))
                           or next((e for e in enemies if e.get("status") == "ativo"), None))
                    player_new, item_logs = inv_mod.use_item_in_combat(
                        player, action["item_id"], target=tgt)
                    player.clear()
                    player.update(player_new)
                    logs += item_logs
                else:
                    logs += cm.resolve_player_action(player, enemies, action, ABILITIES,
                                                     allies=combat_party)
            hero_resolved = True
        elif slot["side"] == "ally":
            a = next((x for x in combat_party if x.get("id") == slot["id"]), None)
            if not a or a.get("status", "ativo") != "ativo" or not a.get("active"):
                continue
            logs += cm.tick_conditions(a)
            logs += cm.resolve_ally_turn(a, enemies, rnd=rnd)
        else:
            e = next((x for x in enemies if x.get("id") == slot["id"]), None)
            if not e or e.get("status") != "ativo":
                continue
            logs += cm.tick_conditions(e)
            if e.get("status") == "ativo" and int(player.get("hp", 0)) > 0:
                hero_side = [player] + [a for a in combat_party if a.get("active")
                                        and a.get("status", "ativo") == "ativo"
                                        and int(a.get("hp", 0)) > 0]
                logs += cm.resolve_enemy_turn(e, player, allies=enemies, rnd=rnd,
                                              hero_side=hero_side)
    if not hero_resolved and int(player.get("hp", 0)) > 0:
        logs += cm.resolve_player_action(player, enemies, action, ABILITIES,
                                         allies=combat_party)

    # Fase 2.5b: fugido sai do combate — não conta como ativo, não vira loot.
    active_after = [e for e in enemies if e.get("status") == "ativo"]
    fled = [e for e in enemies if e.get("status") == "fugiu"]
    dead = [e for e in enemies if e.get("status") == "morto"]
    # spec refatoracao-sistema-classes (etapa 3): Corruptor — cada inimigo que se
    # desfaz (morte) é decadência ao redor que o alimenta de Entropia.
    for _d in dead:
        cm.apply_entropy_trigger(player, {"kind": "on_decay_nearby", "decay_kind": "any"}, logs)
    # spec arvores-habilidade-classes: passiva entropy_on_kill (colheita da morte).
    cm.apply_entropy_on_kill(player, len(dead), logs)
    # Médico — Recidiva: Carga oculta que cruza 'severo' estoura num colapso (1x).
    _recidiva_logs, recidiva_event = cm.check_recidiva(player)
    logs += _recidiva_logs
    # R5: herói que fugiu ENCERRA o combate (mesmo com inimigos vivos) — sem vitória,
    # sem espólio, sem XP dos que ficaram para trás.
    combat_over = (not active_after) or hero_fled
    victory = combat_over and bool(dead) and not hero_fled  # espólio só se alguém caiu

    # Fase 3.2 (R2): morte de instância vira `defeated` no bestiário do jogador.
    if dead:
        bestiary_knowledge = disc.record_kills(bestiary_knowledge, dead, turn)
        bk_changed = True

    # spec checkpoints-morte (D4): a queda letal NÃO é mais "O Saque" (2ª chance
    # com poção) nem memorial imposto — abre a tela de morte (death_pending), e o
    # jogador escolhe restaurar do checkpoint ou aceitar o fim. Decisão 100% Python.
    player_dead = int(player.get("hp", 0)) <= 0

    # Fase 4.1: XP determinístico por kill (tier do bestiário; fugitivo não conta).
    # grant_xp devolve cópia — reatribui ANTES de montar o result.
    # Queda letal encerra SEM espólio/XP (o progresso do turno se perde no restore).
    level_up_events: List[Dict] = []
    if dead and not player_dead:
        import progression as pg
        xp = pg.xp_for_kills(dead)
        if xp:
            player, level_up_events = pg.grant_xp(player, xp)
            logs.append(f"+{xp} XP" + (f" — NÍVEL {player['level']}!" if level_up_events else ""))

    # spec checkpoints-morte (D4): sem apply_downed/Saque. A queda letal narra a
    # tomba (2ª pessoa) e a TELA DE MORTE (death_pending) decide o destino —
    # restaurar do checkpoint ou aceitar o fim.
    from services import prose_guard
    aberturas = prose_guard.ultimas_aberturas(messages)
    loc = state.get("world", {}).get("current_location", "")
    if player_dead:
        killer = next((e.get("name") for e in enemies if e.get("status") == "ativo"), "")
        narrative = _narrate_fall(player, logs, killer)
    else:
        world_pack = build_context_pack(state, query=f"{loc} {intent}",
                                        purpose="combat_narration", token_budget=1200)
        narrative = _narrate(player, enemies, logs, spawned_flavor, intent, combat_over,
                             world_pack.world_state_block, player_dead=False,
                             aberturas=aberturas)
    # R4: telemetria de repetição (não re-tenta) — compara com a abertura anterior.
    prose_guard.log_if_repeats(narrative, aberturas[0] if aberturas else "", where="combate")

    result = {
        "messages": [AIMessage(content=narrative)],
        "player": player,
        "enemies": [] if combat_over else enemies,
        "combat": combat_meta,
        "combat_target": None if combat_over else combat_target,
        # todos fugiram e ninguém morreu -> sem loot; volta ao fluxo normal
        "next": "loot" if victory else None,
        "archive_due": combat_over,  # fim de combate = evento relevante
    }
    if bk_changed:
        result["bestiary_knowledge"] = bestiary_knowledge
    # combate-lifecycle (R5): fim de combate (vitória/fuga/expiração) SEMPRE zera
    # o `active`. Antes, herói que fugia com inimigos vivos deixava active=True
    # (combat_over mas bool(active_after) verdadeiro) — flag zumbi.
    combat_meta["active"] = not combat_over

    # Fase 4.5: party atualizada volta ao estado; aliado canônico morto vira
    # npc_killed (actor=enemy) — crônica/quests órfãs/cascata 2.7 reagem de graça.
    result["party"] = party
    fallen_events = []
    for a in party:
        if a.get("status") == "morto" and not a.get("_death_logged"):
            a["_death_logged"] = True
            origin = a.get("origin_npc") or ""
            ent = gr.get_entity(origin) if origin else None
            if ent and ent.get("type") == "npc":
                fallen_events.append({
                    "type": "npc_killed", "actor_id": "enemy", "target_id": origin,
                    "detail": f"{a.get('name','aliado')} caiu lutando ao lado do herói",
                    "payload": {}, "source": "combat",
                })

    # spec aliados-em-combate (R3/R4): aliados TRANSITÓRIOS NÃO viram party
    # permanente; seu dano/morte reflete no NPC de origem (sem 'aliado imortal'
    # que morre no combate e volta são na conversa seguinte). Combate acabou →
    # a cena transitória se encerra.
    if scene_tr:
        npcs_out = {**(state.get("npcs") or {})}
        for a in scene_tr:
            name = a.get("name") or ""
            key = next((k for k in npcs_out if k == name
                        or (isinstance(npcs_out[k], dict)
                            and npcs_out[k].get("name") == name)), None)
            if key is None or not isinstance(npcs_out.get(key), dict):
                continue
            npc = {**npcs_out[key]}
            npc["hp"] = int(a.get("hp", 0) or 0)
            if a.get("status") == "morto":
                npc["status"] = "morto"
                npc["in_scene"] = False
            npcs_out[key] = npc
        result["npcs"] = npcs_out
        if combat_over:
            combat_meta.pop("scene_allies", None)

    # spec checkpoints-morte (R2/R4): a queda letal abre a TELA DE MORTE
    # (death_pending) — NÃO seta game_over (memorial só pela via voluntária
    # "Aceitar"). Combate encerrado, sem espólio/XP; a resolução (API/CLI/harness)
    # decide restaurar do checkpoint ou aceitar o fim.
    death_events = []
    if player_dead:
        result["death_pending"] = True
        result["combat"] = {**combat_meta, "active": False}
        result["enemies"] = []
        result["combat_target"] = None
        result["next"] = None
        result["archive_due"] = True
        killer = next((e.get("name") for e in enemies if e.get("status") == "ativo"), "")
        death_events.append({
            "type": "player_downed", "actor_id": "player", "target_id": "player",
            "detail": f"{player.get('name','O herói')} tombou em combate"
                      + (f" diante de {killer}" if killer else ""),
            "payload": {"killer": killer, "location": loc,
                        "boss_present": any(str(e.get("type", "")).strip().lower() == "boss"
                                            for e in enemies)},
            "source": "combat",
        })

    # Fase 2.6 (R5): morte de inimigo CANÔNICO vira npc_killed determinístico (sem LLM).
    # O motor já sabe quem caiu; ids genéricos de bestiário não geram evento.
    # Fase 4.1: level_up (source=progression) entra na mesma fila.
    engine_events = _kill_events(dead) + level_up_events + fallen_events + death_events
    if recidiva_event:
        engine_events.append(recidiva_event)
    if engine_events:
        result["pending_world_events"] = (state.get("pending_world_events", []) or []) + engine_events

    # Fase 2.5b (R10): fuga vira alerta de mundo — o fugitivo pode voltar com amigos.
    if fled:
        import world_utils as wu
        world = wu.ensure_world(dict(state.get("world") or {}))
        faction_id = next((e.get("faction") for e in fled if e.get("faction")), None)
        world = wu.register_flee_alert(
            world,
            fled_hint=fled[0].get("name", "o fugitivo"),
            faction_id=faction_id,
            turn=int(world.get("turn_count", 0) or 0),
            enemy_id=disc.normalize_bestiary_id(fled[0]),
        )
        result["world"] = world

    # Fase 6.4: flag de surpresa é one-shot — garante que não persiste.
    if surprise_world_update is not None:
        if "world" in result:
            result["world"].pop("encounter_surprise", None)
        else:
            result["world"] = surprise_world_update

    # combate-lifecycle (R1): fuga bem-sucedida com destino → aplica a viagem no
    # MESMO turno (o herói rompe o cerco E se move). Sem destino (fuga por texto),
    # só sai do combate. Limpa a flag de tentativa (one-shot).
    if hero_fled and flee_dest_id:
        import world_utils as wu
        from gamedata import get_location
        dest = get_location(flee_dest_id)
        if dest:
            base_world = result.get("world") or wu.ensure_world(dict(state.get("world") or {}))
            result["world"] = wu.apply_travel(base_world, dest)
            # spec npc-in-scene-viagem (R1): fugir muda de local → zera a cena
            # (ninguém teleporta junto). Sem isto, um NPC gerado ficava
            # in_scene=True no destino e disparava narrative.recycled_npc a cada
            # turno seguinte (43 warnings no playtest longo). Party vive em lista
            # própria — não é afetada.
            from services import npc_layers
            base_npcs = result.get("npcs")
            if base_npcs is None:
                base_npcs = state.get("npcs", {})
            result["npcs"] = npc_layers.reset_scene(base_npcs)
            logs.append(f"{player.get('name','O herói')} escapa rumo a {dest['name']}.")
    if state.get("combat_flee_attempt"):
        result["combat_flee_attempt"] = False
        result["combat_flee_destination"] = None

    return result
