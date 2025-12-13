import random
from langchain_core.tools import tool

@tool
def roll_dice(sides: int = 20, context: str = "Teste Geral") -> str:
    """
    Rola um dado.
    Args:
        sides: Número de lados (padrão 20).
        context: O que está sendo testado? Ex: 'Ataque do Jogador', 'Defesa do Inimigo'.
    """
    result = random.randint(1, sides)
    return f"🎲 [{context}] d{sides} rolou: {result}"