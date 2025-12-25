"""
app_streamlit.py
Interface Web para o RPG Engine V8.
"""
import streamlit as st
import game_engine as engine # Importa nossa nova fachada

st.set_page_config(page_title="RPG Engine V8", page_icon="🐉", layout="wide")

# --- CSS Customizado para Dark Fantasy ---
st.markdown("""
<style>
    .stTextInput > div > div > input { color: #e0e0e0; background-color: #1e1e1e; }
    .stMarkdown p { font-family: 'Georgia', serif; font-size: 1.1em; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# --- Gerenciamento de Sessão ---
if "state" not in st.session_state:
    st.session_state.state = None

# --- Sidebar (Controles) ---
with st.sidebar:
    st.header("📜 Grimório")
    if st.button("Novo Jogo", use_container_width=True):
        st.session_state.state = None
        st.experimental_rerun()
    
    st.divider()
    
    # Load/Save System
    saves = engine.list_saved_games()
    selected_save = st.selectbox("Carregar Save", [""] + saves)
    if st.button("Carregar") and selected_save:
        st.session_state.state = engine.load_game_state(selected_save)
        st.toast(f"Jogo '{selected_save}' carregado!")
        st.experimental_rerun()
        
    if st.button("Salvar Jogo") and st.session_state.state:
        msg = engine.save_game_state(st.session_state.state, "quicksave")
        st.toast(msg)

# --- Tela 1: Criação de Personagem ---
if st.session_state.state is None:
    st.title("🐉 RPG Engine V8: Character Creation")
    
    with st.form("char_creator"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome", "Batys")
        race = col2.text_input("Raça", "Elfo Negro")
        c_class = col1.text_input("Classe", "Artífice")
        concept = col2.text_input("Conceito/Estilo", "Engenheiro de Autômatos Obscuros")
        
        submitted = st.form_submit_button("Iniciar Aventura")
        
    if submitted:
        with st.spinner("Conjurando o mundo..."):
            try:
                # Chama o backend
                initial_state = engine.create_new_game(name, c_class, race, concept)
                st.session_state.state = initial_state
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Erro na criação: {e}")

# --- Tela 2: O Jogo ---
else:
    state = st.session_state.state
    
    # Header com Status
    p = state['player']
    st.caption(f"👤 **{p['name']}** | {p['race']} {p['class_name']} | HP: {p['hp']}/{p['max_hp']}")
    st.divider()

    # Histórico de Mensagens (Chat Style)
    chat_container = st.container()
    with chat_container:
        for msg in state.get("messages", []):
            role = "user" if msg.type == "human" else "assistant"
            with st.chat_message(role):
                st.markdown(msg.content)

    # Input do Jogador
    if prompt := st.chat_input("O que você faz?"):
        # Adiciona mensagem do user visualmente (opcional, pois o chat history fará isso)
        with st.chat_message("user"):
            st.markdown(prompt)

        # Processa Turno
        with st.spinner("O Mestre está pensando..."):
            new_state = engine.process_turn(state, prompt)
            st.session_state.state = new_state
            
            # Mostra resposta da IA
            ai_reply = engine.get_last_ai_message(new_state)
            with st.chat_message("assistant"):
                st.markdown(ai_reply)