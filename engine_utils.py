import re
from typing import List, Annotated, Literal, Optional, Any
from pydantic import BaseModel, Field, BeforeValidator, field_validator
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from state import GameState
from gamedata import BESTIARY

# Importação preguiçosa para evitar ciclo (Bestiary Agent é importado dentro da função)

# --- VALIDATORS ---
def clean_int(v: Any) -> int:
    if isinstance(v, int): return v
    if isinstance(v, str):
        nums = re.findall(r'-?\d+', v)
        if nums: return int(nums[0])
    return 0

# --- MODELS ---
class DamageTarget(BaseModel):
    target_name: str
    damage_amount: Annotated[int, BeforeValidator(clean_int)]
    is_healing: bool = False

    @field_validator("damage_amount")
    @classmethod
    def validate_damage_amount(cls, v: int) -> int:
        """Clamp negative values to zero and guard against absurd spikes."""
        if v < 0:
            return 0
        if v > 100:
            raise ValueError("damage_amount acima do limite de sanidade (100)")
        return v

class ConditionUpdate(BaseModel):
    target_name: str
    condition: str
    operation: Literal["add", "remove"]

class EngineUpdate(BaseModel):
    reasoning_trace: str
    narrative_reason: str
    hp_updates: List[DamageTarget] = Field(default_factory=list)
    condition_updates: List[ConditionUpdate] = Field(default_factory=list)
    player_mana_change: Annotated[int, BeforeValidator(clean_int)] = Field(default=0)
    player_stamina_change: Annotated[int, BeforeValidator(clean_int)] = Field(default=0)
    gold_change: Annotated[int, BeforeValidator(clean_int)] = Field(default=0)
    items_to_add: List[str] = Field(default_factory=list)
    items_to_remove: List[str] = Field(default_factory=list)
    spawn_enemy_type: Optional[str] = None

    @field_validator("player_stamina_change")
    @classmethod
    def validate_stamina_change(cls, v: int) -> int:
        """Restringe variações de Stamina a um intervalo realista por turno."""
        if v < -20 or v > 20:
            raise ValueError("player_stamina_change fora do intervalo permitido (-20 a 20)")
        return v

# --- EXECUÇÃO GENÉRICA ---
def execute_engine(llm, prompt_sys, messages, state, context_name):
    if not messages:
        return {"messages": [AIMessage(content="Descreva sua ação inicial para começarmos a aventura.")]}

    if getattr(llm, "is_fallback", False):
        fallback_msg = llm.invoke(None)
        return {"messages": [fallback_msg]}

    # Contexto Limpo
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if last_human is None:
        return {"messages": [AIMessage(content="Envie sua próxima ação para continuar a cena.")]}

    last_tool = next((m for m in reversed(messages) if isinstance(m, ToolMessage)), None)

    last_ai_handoff = None
    if isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls:
        last_ai_handoff = messages[-1]

    input_msgs = [prompt_sys]
    if last_ai_handoff:
        input_msgs.append(last_ai_handoff)
    input_msgs.append(last_human)
    if last_tool:
        input_msgs.append(last_tool)

    # Tool Binding
    from tools import roll_dice
    if not last_tool:
        tools = llm.bind_tools([roll_dice])
        first_res = tools.invoke(input_msgs)
        if first_res.tool_calls: return {"messages": [first_res]}
    
    # Geração Estruturada
    try:
        engine = llm.with_structured_output(EngineUpdate).with_retry(stop_after_attempt=3)
        update = engine.invoke(input_msgs)
        if not update: raise ValueError("JSON Vazio")
    except Exception as e:
        print(f"[{context_name} ERROR] {e}")
        update = EngineUpdate(
            reasoning_trace=f"Erro: {e}", 
            narrative_reason="A realidade oscila. Tente uma ação mais direta."
        )

    print(f"\n[{context_name.upper()}]: {update.reasoning_trace}")
    return apply_state_update(update, state)

def apply_state_update(update: EngineUpdate, state: GameState):
    player = state['player']
    
    # SPAWN DINÂMICO
    if update.spawn_enemy_type:
        from agents.bestiary import generate_new_enemy, get_enemy_template # Import aqui pra evitar ciclo
        
        base = get_enemy_template(update.spawn_enemy_type)
        if not base:
             # Tenta no bestiário estático primeiro
            base = BESTIARY.get(update.spawn_enemy_type)
        
        if not base:
            # GERAÇÃO IA
            loc = state['world'].get('current_location', 'Desconhecido')
            base = generate_new_enemy(update.spawn_enemy_type, context=f"Local: {loc}")

        if base:
            if 'enemies' not in state: state['enemies'] = []
            new_id = f"{base['name'].lower().replace(' ', '_')}_{len(state['enemies'])}"
            new_enemy = base.copy()
            new_enemy['id'] = new_id
            new_enemy['status'] = 'ativo'
            if 'active_conditions' not in new_enemy: new_enemy['active_conditions'] = []
            state['enemies'].append(new_enemy)

    # Condições
    for cond in update.condition_updates:
        tgt = cond.target_name.lower()
        def mod_list(lst, op, val):
            if op == "add" and val not in lst: lst.append(val)
            elif op == "remove" and val in lst: lst.remove(val)

        if "valerius" in tgt or "jogador" in tgt:
            if 'active_conditions' not in player: player['active_conditions'] = []
            mod_list(player['active_conditions'], cond.operation, cond.condition)
        
        if state.get('enemies'):
            for e in state['enemies']:
                if e['status'] == 'ativo' and (e['id'] in tgt or e['name'].lower() in tgt):
                    if 'active_conditions' not in e: e['active_conditions'] = []
                    mod_list(e['active_conditions'], cond.operation, cond.condition)

    # Dano e Recursos (código padrão mantido)
    for hit in update.hp_updates:
        tgt = hit.target_name.lower()
        amt = hit.damage_amount if not hit.is_healing else -hit.damage_amount
        if "valerius" in tgt or "jogador" in tgt: player['hp'] = max(0, player['hp'] - amt)
        elif state.get('party'):
            for c in state['party']:
                if c['name'].lower() in tgt:
                    c['hp'] = max(0, c['hp'] - amt)
                    if c['hp'] == 0: c['active'] = False
        if state.get('enemies'):
            for e in state['enemies']:
                if e['status'] == 'ativo' and (e['id'] in tgt or e['name'].lower() in tgt):
                    e['hp'] = max(0, e['hp'] - amt)
                    if e['hp'] == 0: e['status'] = "morto"

    player['mana'] = max(0, min(player['mana'] + update.player_mana_change, player['max_mana']))
    player['stamina'] = max(0, min(player['stamina'] + update.player_stamina_change, player['max_stamina']))
    player['gold'] += update.gold_change
    
    if update.items_to_add:
        if 'inventory' not in player: player['inventory'] = []
        player['inventory'].extend(update.items_to_add)
    if update.items_to_remove:
        for i in update.items_to_remove:
            if i in player['inventory']: player['inventory'].remove(i)

    return {
        "messages": [AIMessage(content=update.narrative_reason)],
        "player": player,
        "enemies": state.get('enemies', []),
        "party": state.get('party', []),
        "npcs": state.get('npcs', {})
    }