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

from state import GameState, EnemyStats
from llm_setup import ModelTier, get_llm
from gamedata import ABILITIES
from agents.bestiary import generate_new_enemy
import combat_mechanics as cm


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


# --- SPAWN (mantém integração com bestiário/cache) ---
def _spawn_enemies_integrated(messages: List, target_hint: str):
    print(f"⚡ [COMBAT] Escaneando cena por inimigos. Dica: '{target_hint}'...")
    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)
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
                final_enemies_list.append(instance)
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


def _ability_catalog_for(player: Dict) -> str:
    """Só as habilidades RELEVANTES (conhecidas do jogador + universais) — não o dict inteiro.
    Economiza centenas de tokens por parse de combate."""
    known = [str(k).lower() for k in (player.get("known_abilities") or [])]

    def _line(aid, a):
        return f"- {aid}: {a.get('name')} | custo {a.get('cost')} {a.get('resource_type')} | {a.get('description','')[:60]}"

    linhas = []
    for aid, a in ABILITIES.items():
        name = str(a.get("name", "")).lower()
        if aid in _UNIVERSAL_ABILITIES or any(k and (k in aid.lower() or k in name or name in k) for k in known):
            linhas.append(_line(aid, a))
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
    sys = SystemMessage(content=f"""
    Você é o IDENTIFICADOR de ações de combate. NÃO resolva mecânica, só classifique.
    Traduza a fala do jogador para uma ação canônica.

    Classe: {player.get('class_name', '')}
    Habilidades conhecidas (texto livre): {player.get('known_abilities', [])}
    Atributos: {player.get('attributes', {})}

    CATÁLOGO DE HABILIDADES (use a CHAVE exata em ability_id):
    {_ability_catalog_for(player)}

    Inimigos presentes: {enemy_names}

    Regras:
    - Escolha o ability_id do catálogo que melhor casa com a intenção. Ataque comum -> 'ataque_basico'.
    - Se a ação for impossível para esta classe/ficha, is_allowed=False e explique em reason.
    - target = nome de um inimigo presente (ou vazio para o primeiro).
    """)
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.FAST)
        res = llm.with_structured_output(CombatAction).invoke([sys, HumanMessage(content=intent)])
        if isinstance(res, CombatAction):
            aid = res.ability_id if res.ability_id in ABILITIES else "ataque_basico"
            return {"ability_id": aid, "target": res.target,
                    "is_allowed": res.is_allowed, "reason": res.reason}
    except Exception as e:
        print(f"⚠️ [COMBAT PARSE] {e}")
    return fallback


# --- NARRAÇÃO (IA descreve o log mecânico) ---
def _narrate(player: Dict, enemies: List[Dict], logs: List[str],
             spawned_flavor: Optional[str], intent: str, victory: bool) -> str:
    log_str = "\n".join(logs) if logs else "Nada acontece."
    alive = [f"{e['name']} (HP {e['hp']}/{e['max_hp']})" for e in enemies if e.get("status") == "ativo"]
    sys = SystemMessage(content=f"""
    <role>Narrador de Combate — Dark Fantasy</role>
    Descreva o round de combate em 1 a 2 parágrafos, com base APENAS no log mecânico.
    Não invente dano nem resultados fora do log. Seja visceral mas conciso.

    {("ENTRADA: " + spawned_flavor) if spawned_flavor else ""}
    Ação do jogador (fala): {intent}

    <log_mecanico>
    {log_str}
    </log_mecanico>

    Herói: {player.get('name')} HP {player.get('hp')}/{player.get('max_hp')}
    Inimigos vivos: {', '.join(alive) if alive else 'nenhum'}

    {"O combate foi VENCIDO — encerre com o respiro da vitória." if victory else "Termine com tensão e uma deixa para a próxima ação do jogador."}
    """)
    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.SMART)
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
    if is_combat_start and not active:
        enemies, spawned_flavor = _spawn_enemies_integrated(messages, combat_target)
        active = [e for e in enemies if e.get("status") == "ativo"]
        print(f"⚔️ Combate: {[e['name'] for e in active]}")

    # Sem inimigos = vitória (ou nada a fazer).
    if not active:
        return {
            "messages": [AIMessage(content="O silêncio retorna ao campo de batalha. Vitória.")],
            "next": "loot", "combat_target": None, "enemies": [],
            "combat": {"active": False, "round": combat_meta.get("round", 0), "order": []},
            "archive_due": True,  # fim de combate = evento relevante
        }

    # Iniciativa: rola no 1º round; persiste depois.
    if is_combat_start or not combat_meta.get("order"):
        combat_meta = {"round": 1, "active": True, "order": cm.roll_initiative(player, active)}
    else:
        combat_meta["round"] = combat_meta.get("round", 1) + 1
        combat_meta["active"] = True

    # A IA identifica a ação do jogador.
    intent = _last_human_text(messages)
    action = _parse_combat_action(player, active, intent)

    # Resolução determinística em ordem de iniciativa.
    logs: List[str] = []
    hero_resolved = False
    for slot in combat_meta["order"]:
        if slot["side"] == "hero":
            logs += cm.tick_conditions(player)
            cm.tick_cooldowns(player)
            if int(player.get("hp", 0)) > 0:
                logs += cm.resolve_player_action(player, enemies, action, ABILITIES)
            hero_resolved = True
        else:
            e = next((x for x in enemies if x.get("id") == slot["id"]), None)
            if not e or e.get("status") != "ativo":
                continue
            logs += cm.tick_conditions(e)
            if e.get("status") == "ativo" and int(player.get("hp", 0)) > 0:
                logs += cm.resolve_enemy_turn(e, player)
    if not hero_resolved and int(player.get("hp", 0)) > 0:
        logs += cm.resolve_player_action(player, enemies, action, ABILITIES)

    active_after = [e for e in enemies if e.get("status") == "ativo"]
    victory = not active_after
    combat_meta["active"] = bool(active_after)

    narrative = _narrate(player, enemies, logs, spawned_flavor, intent, victory)

    return {
        "messages": [AIMessage(content=narrative)],
        "player": player,
        "enemies": enemies,
        "combat": combat_meta,
        "combat_target": None if victory else combat_target,
        "next": "loot" if victory else None,
        "archive_due": victory,  # fim de combate (vitória) = evento relevante
    }
