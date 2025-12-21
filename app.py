import sys
from langchain_core.messages import HumanMessage, AIMessage

from character_creator import create_player_character
from prologue_manager import generate_prologue
from main import app as dm_graph
from test_runner import create_base_state


WELCOME_BANNER = """
=============================
🐉 RPG Engine V8 - CLI Edition
=============================
"""


def main() -> None:
    print(WELCOME_BANNER)

    player_data = create_player_character()
    print("\n⏳ Generating Prologue...")
    prologue_data = generate_prologue(player_data)

    state = create_base_state()
    state["player"] = player_data
    state["world"].update(
        {
            "current_location": prologue_data.get("current_location", state["world"].get("current_location", "")),
            "quest_plan": prologue_data.get("quest_plan", []),
            "quest_plan_origin": prologue_data.get("quest_plan_origin"),
        }
    )
    intro_text = prologue_data.get("intro_narrative", "A jornada começa...")
    state["messages"] = [AIMessage(content=intro_text)]

    print(f"\n{intro_text}\n")

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
        state = result

        if state.get("messages"):
            last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None)
            if last_ai:
                print(f"\n{last_ai.content}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nA aventura foi interrompida.")
