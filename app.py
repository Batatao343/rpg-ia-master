import streamlit as st
import time
from langchain_core.messages import HumanMessage, AIMessage

# Imports da Engine V8
from main import app as game_app # Importa o Grafo compilado
from state import GameState
from persistence import save_game, load_game, list_saves

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RPG Engine V8", page_icon="🐉", layout="wide")

# CSS para barras de vida e estilo
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #c9d1d9; }
    .stat-box { border: 1px solid #30363d; padding: 10px; border-radius: 5px; margin-bottom: 10px; background-color: #161b22; }
    .bar-bg { background-color: #30363d; border-radius: 5px; height: 10px; width: 100%; margin-top: 5px; overflow: hidden; }
    .hp-fill { background-color: #2ea043; height: 100%; }
    .mana-fill { background-color: #1f6feb; height: 100%; }
    .stamina-fill { background-color: #d29922; height: 100%; }
    .enemy-fill { background-color: #da3633; height: 100%; }
    .condition-tag { color: #d29922; font-size: 0.8em; font-weight: bold; margin-left: 5px; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO ---
if "game_state" not in st.session_state:
    # Estado Inicial Padrão
    st.session_state.game_state = {
        "messages": [],
        "player": {
            "name": "Valerius", "class_name": "Guerreiro",
            "hp": 30, "max_hp": 30, "mana": 10, "max_mana": 10,
            "stamina": 20, "max_stamina": 20, "gold": 0, "xp": 0, "level": 1,
            "attributes": {"strength": 16, "dexterity": 12, "constitution": 14, "intelligence": 10, "wisdom": 10, "charisma": 12},
            "inventory": ["Espada Curta", "Poção de Cura"],
            "known_abilities": ["Ataque Poderoso"],
            "defense": 15, "attack_bonus": 3, "active_conditions": [], "alignment": "Neutro"
        },
        "world": {"current_location": "Estrada Real", "time_of_day": "Dia", "turn_count": 1, "weather": "Limpo", "quest_plan": [], "quest_plan_origin": None},
        "enemies": [], "party": [], "npcs": {}, "active_npc_name": None, "next": None
    }

# Atalho
state = st.session_state.game_state

# --- SIDEBAR (HUD) ---
with st.sidebar:
    st.header(f"🛡️ {state['player']['name']}")
    st.caption(f"Nível {state['player']['level']} {state['player']['class_name']}")
    
    # Barras de Status
    p = state['player']
    
    st.markdown("**HP**")
    hp_pct = int((p['hp']/p['max_hp'])*100)
    st.markdown(f'<div class="bar-bg"><div class="hp-fill" style="width:{hp_pct}%"></div></div>', unsafe_allow_html=True)
    st.text(f"{p['hp']}/{p['max_hp']}")

    st.markdown("**Mana**")
    mana_pct = int((p['mana']/p['max_mana'])*100)
    st.markdown(f'<div class="bar-bg"><div class="mana-fill" style="width:{mana_pct}%"></div></div>', unsafe_allow_html=True)
    st.text(f"{p['mana']}/{p['max_mana']}")

    st.markdown("**Stamina**")
    stam_pct = int((p['stamina']/p['max_stamina'])*100)
    st.markdown(f'<div class="bar-bg"><div class="stamina-fill" style="width:{stam_pct}%"></div></div>', unsafe_allow_html=True)
    st.text(f"{p['stamina']}/{p['max_stamina']}")
    
    # Condições do Jogador
    if p.get('active_conditions'):
        st.warning(f"Estados: {', '.join(p['active_conditions'])}")

    st.divider()
    
    # Atributos
    with st.expander("Atributos & Inventário"):
        st.json(p['attributes'])
        st.write("**Inventário:**")
        for i in p['inventory']: st.markdown(f"- {i}")
    
    st.divider()
    
    # Persistência
    st.subheader("💾 Sistema")
    save_name = st.text_input("Nome do Save", "save1")
    if st.button("Salvar Jogo"):
        res = save_game(state, save_name)
        st.success(res)
    
    saves = list_saves()
    selected_save = st.selectbox("Carregar", saves) if saves else None
    if st.button("Carregar Jogo") and selected_save:
        try:
            st.session_state.game_state = load_game(selected_save)
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao carregar: {e}")

# --- ÁREA PRINCIPAL ---

# 1. Dashboard de Combate (Horda)
active_enemies = [e for e in state.get('enemies', []) if e['status'] == 'ativo']
if active_enemies:
    st.subheader(f"⚔️ Combate ({len(active_enemies)} Inimigos)")
    cols = st.columns(3)
    for idx, e in enumerate(active_enemies):
        col = cols[idx % 3]
        with col:
            with st.container(border=True):
                # Título com Condições
                conds = "".join([f" [{c}]" for c in e.get('active_conditions', [])])
                st.markdown(f"**{e['name']}** (AC: {e['defense']})<span class='condition-tag'>{conds}</span>", unsafe_allow_html=True)
                
                # Barra de Vida
                hp_pct = max(0, min(100, int((e['hp'] / e['max_hp']) * 100)))
                st.markdown(f'<div class="bar-bg" style="border:1px solid #550000"><div class="enemy-fill" style="width:{hp_pct}%"></div></div>', unsafe_allow_html=True)
                st.caption(f"HP: {e['hp']}/{e['max_hp']}")

# 2. Histórico de Chat
chat_container = st.container(height=500)
with chat_container:
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user", avatar="👤"):
                st.write(msg.content)
        elif isinstance(msg, AIMessage):
            # Filtra tool calls e mensagens vazias
            if msg.content:
                with st.chat_message("assistant", avatar="🎲"):
                    st.write(msg.content)

# 3. Input do Usuário
if prompt := st.chat_input("O que você faz?"):
    # Adiciona msg do usuário
    state["messages"].append(HumanMessage(content=prompt))
    
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)

    # Processamento (Spinner para feedback visual)
    with st.spinner("O Mestre está pensando..."):
        # Invoca o grafo (main.py)
        # O langgraph gerencia o estado e retorna o novo estado
        result = game_app.invoke(state)
        
        # Atualiza o session_state com o resultado
        st.session_state.game_state = result
    
    st.rerun()