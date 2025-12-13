# rag.py (VERSÃO MULTI-INDEX)
import os
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

def get_db_path(index_name: str) -> str:
    """Retorna o nome da pasta baseado no tipo (lore ou rules)."""
    return f"faiss_{index_name}_index"

def get_vector_store(index_name: str):
    """Carrega o banco específico (lore ou rules)."""
    path = get_db_path(index_name)
    if os.path.exists(path):
        return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    return None

def ingest_file(file_path: str, index_name: str):
    """
    Ingere um arquivo e salva em um índice específico.
    Ex: ingest_file("world_lore.txt", "lore")
    Ex: ingest_file("rules.txt", "rules")
    """
    if not os.path.exists(file_path):
        print(f"[ERRO] Arquivo não encontrado: {file_path}")
        return

    print(f"--- INGESTÃO: {file_path} -> ÍNDICE: {index_name} ---")
    
    loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    
    # Cria/Sobrescreve o índice específico
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(get_db_path(index_name))
    print(f"Indexado com sucesso em '{get_db_path(index_name)}'!")

def query_rag(query: str, index_name: str, k: int = 2) -> str:
    """Consulta o banco especificado."""
    db = get_vector_store(index_name)
    if not db:
        return ""
    
    results = db.similarity_search(query, k=k)
    return "\n".join([f"[{index_name.upper()}]: {res.page_content}" for res in results])

# SCRIPT DE CONFIGURAÇÃO INICIAL
if __name__ == "__main__":
    # 1. Atualizar Lore
    ingest_file("world_lore.txt", "lore")
    
    # 2. Criar Regras
    ingest_file("rules.txt", "rules")
    
    # Teste rápido
    print("\nTeste de Regra: ", query_rag("Como funciona magia?", "rules"))