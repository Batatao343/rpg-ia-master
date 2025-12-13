import os
from dotenv import load_dotenv

# Tenta carregar o arquivo .env
load_dotenv()

chave = os.getenv("GOOGLE_API_KEY")

if chave:
    # Mostra só os 4 primeiros caracteres por segurança
    print(f"✅ Sucesso! Chave encontrada: {chave[:4]}...")
else:
    print("❌ Erro: Não encontrei a chave. Verifique o nome do arquivo .env")