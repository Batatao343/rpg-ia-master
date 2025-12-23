import os
import sys
from typing import Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from character_creator import create_player_character
from memory_utils import sanitize_history
from persistence import load_game, save_game, list_saves
from prologue_manager import generate_prologue
from main import app as dm_graph
from test_runner import create_base_state


def _init_game_state(player_data: dict, prologue: dict) -> dict:
    state = create_base_state()
    state["player"] = player_data
    state["world"].update(
        {
            "current_location": prologue.get("current_location", state["world"].get("current_location", "")),
            "quest_plan": prologue.get("quest_plan", []),
            "quest_plan_origin": prologue.get("quest_plan_origin"),
        }
    )
    intro_text = prologue.get("intro_narrative", "A jornada começa...")
    state["messages"] = [AIMessage(content=intro_text)]
    return state


# ----------------- STREAMLIT UI -----------------
def run_streamlit():
    import streamlit as st

    st.set_page_config(page_title="RPG Engine V8", page_icon="🐉", layout="wide")
    st.title("🐉 RPG Engine V8")

    if "player_data" not in st.session_state:
        st.session_state.player_data = None
    if "prologue" not in st.session_state:
        st.session_state.prologue = None
    if "state" not in st.session_state:
        st.session_state.state = None

    st.markdown("### 1) Crie seu herói")
    with st.form("create_char"):
        name = st.text_input("Nome", value="Herói Sem Nome")
        class_name = st.text_input("Classe", value="Aventureiro")
        race = st.text_input("Raça", value="Humano")
        submit_char = st.form_submit_button("Gerar ficha e prólogo")
    if submit_char:
        player_data = create_player_character({"name": name, "class_name": class_name, "race": race})
        prologue = generate_prologue(player_data)
        st.session_state.player_data = player_data
        st.session_state.prologue = prologue
        st.session_state.state = None
        st.success("Prólogo gerado! Revise e inicie a aventura.")

    if st.session_state.prologue:
        st.markdown("### 2) Prólogo")
        p = st.session_state.prologue
        st.info(p.get("intro_narrative", "A jornada começa..."))
        st.write(f"Local inicial: **{p.get('current_location', 'Desconhecido')}**")
        st.write("Plano de missão inicial:")
        for idx, step in enumerate(p.get("quest_plan", []), start=1):
            st.write(f"{idx}. {step}")
        if st.button("Iniciar aventura", type="primary"):
            st.session_state.state = _init_game_state(st.session_state.player_data, p)
            st.success("Aventura iniciada! Digite sua primeira ação.")

    if st.session_state.state:
        st.markdown("### 3) Aventura")
        state = st.session_state.state

        # Histórico
        with st.expander("Histórico", expanded=True):
            for msg in state.get("messages", []):
                role = msg.__class__.__name__.replace("Message", "")
                st.markdown(f"**{role}:** {getattr(msg, 'content', '')}")

        action = st.text_input("Sua ação", key="action_input")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button("Enviar", use_container_width=True):
                if action.strip():
                    state["messages"].append(HumanMessage(content=action.strip()))
                    result = dm_graph.invoke(state)
                    result["messages"] = sanitize_history(result.get("messages", []))
                    st.session_state.state = result
                    st.experimental_rerun()
        with col2:
            if st.button("Salvar", use_container_width=True):
                msg = save_game(st.session_state.state, filename="quicksave")
                st.toast(msg)
        with col3:
            available = list_saves()
            chosen = st.selectbox("Carregar", options=[""] + available, index=0)
            if st.button("Restaurar", use_container_width=True):
                if chosen:
                    st.session_state.state = load_game(chosen)
                    st.toast(f"Carregado {chosen}")


# ----------------- CLI LEGACY -----------------
def run_cli() -> None:
    print("\n🐉 RPG Engine V8 - CLI Edition")

    player_data = create_player_character()
    print("\n⏳ Gerando Prólogo...")
    prologue_data = generate_prologue(player_data)

    state = _init_game_state(player_data, prologue_data)
    print(f"\n{state['messages'][0].content}\n")

    while True:
        try:
            user_input = input("➤ Sua ação (ou 'sair'): ")
        except EOFError:
            print("Saindo...")
            break

        if user_input.strip().lower() in {"sair", "exit", "quit"}:
            print("Até a próxima aventura!")
            break

        state["messages"].append(HumanMessage(content=user_input))

        result = dm_graph.invoke(state)
        result["messages"] = sanitize_history(result.get("messages", []))
        state = result

        if state.get("messages"):
            last_ai: Optional[BaseMessage] = next(
                (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None
            )
            if last_ai:
                print(f"\n{last_ai.content}\n")


if __name__ == "__main__":
    try:
        if os.getenv("STREAMLIT_SERVER_PORT"):
            run_streamlit()
        else:
            # Executa CLI por padrão, ou defina STREAMLIT_SERVER_PORT para UI
            run_cli()
    except KeyboardInterrupt:
        sys.exit("\nA aventura foi interrompida.")
