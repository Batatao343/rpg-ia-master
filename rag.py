"""
rag.py
Sistema Híbrido: Global Lore (Google Gemini) + Session Memory.
Mantém compatibilidade com indexação de arquivos de texto e busca contextual.
"""
import os
from typing import List, Optional
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv(override=True)  # .env canônico (sobrepõe env var do SO)

# Configurações de Caminho
SAVES_DIR = "data/saves_memory" # Pasta onde ficam os vetores dos saves individuais

_embeddings: Optional[GoogleGenerativeAIEmbeddings] = None

def get_embeddings() -> Optional[GoogleGenerativeAIEmbeddings]:
    """Inicializa embeddings do Google sob demanda."""
    global _embeddings
    if _embeddings:
        return _embeddings

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[RAG] GOOGLE_API_KEY não configurada. Embeddings desativados.")
        return None

    try:
        # text-embedding-004 foi removido do v1beta (404). gemini-embedding-001 é o
        # estável atual. Troca de modelo muda a dimensão → reindexar lore/rules
        # (`uv run python rag.py`); índices de sessão são regerados em runtime.
        _embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    except Exception as exc:
        print(f"[RAG] Falha ao inicializar embeddings: {exc}")
        _embeddings = None

    return _embeddings

def get_global_db_path(index_name: str) -> str:
    """Retorna o nome da pasta do índice GLOBAL (lore ou rules)."""
    return f"faiss_{index_name}_index"

def _get_session_path(game_id: str) -> str:
    """Retorna o caminho da pasta de memória da SESSÃO específica."""
    return os.path.join(SAVES_DIR, game_id)

def query_rag(query: str, index_name: str = "lore", game_id: Optional[str] = None) -> str:
    """
    Busca contexto de forma híbrida:
    1. Índice Global (Lore/Regras) - Imutável durante o jogo.
    2. Índice da Sessão (Memórias do Save) - Dinâmico, se game_id for fornecido.
    """
    embeddings = get_embeddings()
    if not embeddings: return ""

    results = []

    # 1. Busca Global (Baseado no index_name: 'lore' ou 'rules')
    global_path = get_global_db_path(index_name)
    if os.path.exists(global_path):
        try:
            global_db = FAISS.load_local(global_path, embeddings, allow_dangerous_deserialization=True)
            # Busca 2 chunks globais
            results.extend(global_db.similarity_search(query, k=2))
        except Exception as e:
            print(f"⚠️ [RAG] Erro ao ler Global '{index_name}': {e}")

    # 2. Busca na Sessão (Se houver game_id)
    # A memória da sessão é agnóstica ao index_name (é tudo "memória do jogo")
    if game_id:
        session_path = _get_session_path(game_id)
        if os.path.exists(session_path):
            try:
                session_db = FAISS.load_local(session_path, embeddings, allow_dangerous_deserialization=True)
                # Busca +2 chunks pessoais
                results.extend(session_db.similarity_search(query, k=2))
            except Exception:
                pass 
    
    if not results: return ""
    
    # Formata e desduplica
    seen = set()
    final_text = []
    for doc in results:
        content = doc.page_content.strip()
        if content not in seen:
            seen.add(content)
            # Adiciona prefixo para ajudar a IA a saber a fonte
            # (Opcional, mas ajuda a distinguir Regra de Memória)
            final_text.append(content)
            
    return "\n---\n".join(final_text)

def add_memory_to_session(game_id: str, texts: List[str]):
    """
    Adiciona novas memórias ao índice específico deste save (game_id).
    """
    if not game_id or not texts: return

    embeddings = get_embeddings()
    if not embeddings: return

    session_path = _get_session_path(game_id)
    
    try:
        if os.path.exists(session_path):
            # Carrega existente
            db = FAISS.load_local(session_path, embeddings, allow_dangerous_deserialization=True)
            db.add_texts(texts)
        else:
            # Cria novo
            if not os.path.exists(SAVES_DIR): os.makedirs(SAVES_DIR)
            db = FAISS.from_texts(texts, embeddings)

        # Salva
        db.save_local(session_path)
        print(f"💾 [RAG] Memória salva para sessão '{game_id}': +{len(texts)} fatos.")
        
    except Exception as e:
        print(f"❌ [RAG ERROR] Falha ao salvar memória: {e}")

# --- MEMÓRIA DE NPC VETORIZADA (namespace por game_id + npc_id) ---

def _get_npc_path(game_id: str, npc_id: str) -> str:
    """Pasta do índice FAISS de UM npc dentro da sessão."""
    return os.path.join(SAVES_DIR, game_id, npc_id)


def add_npc_memory(game_id: str, npc_id: str, texts: List[str]):
    """
    Adiciona fatos ao índice do NPC (isolado por game_id+npc_id).
    No-op se faltar game_id/npc_id/texts ou se não houver embeddings (sem chave).
    """
    if not game_id or not npc_id or not texts:
        return

    embeddings = get_embeddings()
    if not embeddings:
        return

    npc_path = _get_npc_path(game_id, npc_id)
    try:
        if os.path.exists(npc_path):
            db = FAISS.load_local(npc_path, embeddings, allow_dangerous_deserialization=True)
            db.add_texts(texts)
        else:
            os.makedirs(os.path.dirname(npc_path), exist_ok=True)
            db = FAISS.from_texts(texts, embeddings)
        db.save_local(npc_path)
        print(f"🧠 [RAG] Memória de NPC '{npc_id}' (sessão '{game_id}'): +{len(texts)} fatos.")
    except Exception as e:
        print(f"❌ [RAG ERROR] Falha ao salvar memória do NPC '{npc_id}': {e}")


def query_npc_memory(game_id: str, npc_id: str, query: str, k: int = 3) -> str:
    """
    Recupera por relevância o que ESTE npc viveu com o jogador. "" se sem índice/sem chave.
    """
    if not game_id or not npc_id or not query:
        return ""

    embeddings = get_embeddings()
    if not embeddings:
        return ""

    npc_path = _get_npc_path(game_id, npc_id)
    if not os.path.exists(npc_path):
        return ""

    try:
        db = FAISS.load_local(npc_path, embeddings, allow_dangerous_deserialization=True)
        docs = db.similarity_search(query, k=k)
    except Exception:
        return ""

    seen, out = set(), []
    for doc in docs:
        content = doc.page_content.strip()
        if content and content not in seen:
            seen.add(content)
            out.append(content)
    return "\n---\n".join(out)


# --- FUNÇÕES DE UTILIDADE (Setup Inicial) ---

def ingest_file(file_path: str, index_name: str):
    """
    Ingere um arquivo de texto para criar os índices GLOBAIS (lore/rules).
    Use isso no setup ou quando alterar o world_lore.txt.
    """
    if not os.path.exists(file_path):
        print(f"[ERRO] Arquivo não encontrado: {file_path}")
        return

    embeddings = get_embeddings()
    if embeddings is None: return

    print(f"--- INGESTÃO: {file_path} -> ÍNDICE: {index_name} ---")
    
    loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    
    # Salva no caminho global
    path = get_global_db_path(index_name)
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(path)
    print(f"✅ Indexado com sucesso em '{path}'!")

if __name__ == "__main__":
    # Console Windows é cp1252; força UTF-8 p/ os emojis dos prints não quebrarem
    # (main.py já faz isso no fluxo do jogo; aqui rodamos standalone).
    import sys
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # Script rápido para re-gerar a Lore Global se rodar este arquivo direto
    print("Recriando índices globais...")
    lore_path = os.path.join("data", "world_lore.txt")
    rules_path = os.path.join("data", "rules.txt")
    if os.path.exists(lore_path):
        ingest_file(lore_path, "lore")
    else:
        print(f"[ERRO] Lore não encontrada em {lore_path}")
    if os.path.exists(rules_path):
        ingest_file(rules_path, "rules")
    else:
        print(f"[ERRO] Regras não encontradas em {rules_path}")