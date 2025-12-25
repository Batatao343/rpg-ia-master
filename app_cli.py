"""
app_cli.py
Interface de Terminal para o RPG.
"""
import sys
import game_engine as engine

def main():
    print("\n🐉 RPG Engine V8 - Terminal Edition")
    print("="*40)

    # Criação
    name = input("Nome: ") or "Batys"
    race = input("Raça: ") or "Elfo"
    cls = input("Classe: ") or "Artífice"
    concept = input("Conceito (ex: Necromante de Fungos): ") or cls

    print("\n⏳ Gerando mundo...")
    state = engine.create_new_game(name, cls, race, concept)
    
    # Loop Principal
    print("\n" + "="*40)
    print(engine.get_last_ai_message(state))
    
    while True:
        try:
            action = input("\n➤ Você: ")
        except (EOFError, KeyboardInterrupt):
            break
            
        if action.lower() in ["sair", "exit", "quit"]:
            break
            
        # Processa
        state = engine.process_turn(state, action)
        
        # Exibe
        print(f"\n🎲 DM: {engine.get_last_ai_message(state)}")

    print("\nFim da sessão.")

if __name__ == "__main__":
    main()
    