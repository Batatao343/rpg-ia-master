"""
agents/archivist.py
O Escriba do Mundo. Lê a narrativa, extrai fatos novos e os grava
Tanto no Banco Vetorial (FAISS) quanto no Arquivo de Texto (world_lore.txt).
"""
import os
from llm_setup import get_llm, ModelTier
from rag import add_to_lore_index

# Caminho do arquivo de Lore (na raiz do projeto)
LORE_FILE_PATH = "world_lore.txt"

def _append_to_file(content: str) -> None:
    """Escreve o novo conhecimento no final do arquivo .txt."""
    try:
        # Garante que começa com uma nova linha se o arquivo não estiver vazio
        prefix = "\n"
        if not os.path.exists(LORE_FILE_PATH):
            prefix = ""
            
        with open(LORE_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"{prefix}{content}")
        print(f"📜 [ARCHIVIST] Gravado em '{LORE_FILE_PATH}' com sucesso.")
    except Exception as e:
        print(f"❌ [ARCHIVIST] Erro ao gravar em arquivo: {e}")

def archive_narrative(narrative_text: str) -> None:
    """
    Analisa a narrativa recente. Se houver fatos novos (NPCs mortos, locais descobertos),
    formata-os no padrão 'Markdown Rico' e salva permanentemente.
    """
    if not narrative_text or len(narrative_text) < 50:
        return

    llm = get_llm(temperature=0.2, tier=ModelTier.FAST)
    
    # Prompt forçando o formato de Tags que criamos
    system_prompt = """
    You are the Royal Archivist of a Dark Fantasy world.
    Analyze the NARRATIVE below. Did the players discover a NEW location, kill a named NPC, or change the world state?
    
    If YES, extract this fact and format it EXACTLY like this (Markdown):
    
    ---
    [CATEGORIA: <TYPE>] [TAGS: <KEYWORD1>, <KEYWORD2>]
    ## <TITLE OF THE FACT>
    <Detailed description of what happened or what was learned.>
    
    Examples of Categories: HISTÓRIA, NPC, LOCALIZAÇÃO, ITEM, FACÇÃO.
    
    If NO new permanent info is found (just combat or dialogue), return exactly: NONE
    """

    try:
        # Invoca a IA
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"NARRATIVE:\n{narrative_text}"}
        ])
        
        content = response.content.strip()

        # Se a IA não achou nada, aborta
        if content == "NONE" or "NONE" in content[:10]:
            return

        # 1. Grava no FAISS (Memória Vetorial para RAG)
        add_to_lore_index([content])
        
        # 2. Grava no TXT (Para leitura humana e persistência física)
        _append_to_file(content)
        
        print(f"🧠 [ARCHIVIST] Novo conhecimento preservado: {content.splitlines()[2]}")

    except Exception as exc:
        print(f"⚠️ [ARCHIVIST] Falha ao arquivar: {exc}")