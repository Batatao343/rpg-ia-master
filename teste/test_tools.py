# test_tools.py
from tools import roll_dice

print("--- INICIANDO TESTE DE TOOLS ---")

# TESTE 1: Invocação Padrão (d20)
# O LangChain exige que passemos os argumentos como um dicionário, 
# pois é assim que a LLM envia os dados (em formato JSON).
print("\n1. Testando d20 (padrão):")
try:
    # O método .invoke() simula exatamente o que o Agente fará
    resultado = roll_dice.invoke({}) 
    print(f"Resultado: {resultado}")
except Exception as e:
    print(f"ERRO: {e}")

# TESTE 2: Invocação com Argumentos (d6)
print("\n2. Testando d6 (personalizado):")
try:
    resultado = roll_dice.invoke({"sides": 6})
    print(f"Resultado: {resultado}")
except Exception as e:
    print(f"ERRO: {e}")

# TESTE 3: Verificando a Assinatura (Schema)
# Isso é crucial! É assim que a LLM "lê" como usar sua ferramenta.
print("\n3. Verificando o Schema JSON (O que a LLM vê):")
print(roll_dice.args)