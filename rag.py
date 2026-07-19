"""
rag.py
Sistema Híbrido: Global Lore + Session Memory, com embeddings multi-provider.

Embeddings resolvem por uma CADEIA ordenada de candidatos (`EMBEDDING_ROUTES`):
o primeiro com key/dep disponível vira o provider ativo. Gemini é o ÚLTIMO
fallback (caro/sem créditos) — só assume sem nenhum outro configurado.

Diferença crítica vs o `RoutedLLM`: embeddings NÃO têm fallback por request —
vetores de providers diferentes no mesmo índice FAISS são incompatíveis
(dimensão/espaço). O fallback é só na RESOLUÇÃO (qual provider está disponível
ao construir). Cada índice grava `embeddings_meta.json` e fica PINADO ao
provider que o gerou; abrir com outro provider é proibido (índice desativado
com aviso; re-index para trocar). Ver specs/embeddings-provider.md.
"""
import json
import logging
import os
from typing import Callable, Dict, List, Optional
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv(override=True)  # .env canônico (sobrepõe env var do SO)

_LOG = logging.getLogger("rpg.rag")

# Configurações de Caminho
SAVES_DIR = "data/saves_memory" # Pasta onde ficam os vetores dos saves individuais
_META_FILE = "embeddings_meta.json"

# Cadeia ordenada: primário → ... → último fallback. Gemini SEMPRE por último
# (decisão do usuário 2026-07-16: caro/sem créditos; só assume sem outro).
EMBEDDING_ROUTES: List[str] = ["jina", "openai", "ollama", "gemini"]

_PROVIDER_MODELS: Dict[str, str] = {
    "jina": "jina-embeddings-v3",
    "openai": "text-embedding-3-small",
    "ollama": "bge-m3",
    "gemini": "models/gemini-embedding-001",
}

# Provider assumido por índice LEGADO (gerado antes da meta) — histórico Google.
_LEGACY_PROVIDER = "gemini"

_embeddings_cache: Dict[str, object] = {}   # provider -> objeto de embeddings
_active_provider_name: Optional[str] = None  # provider resolvido para ESCRITA


# --- Builders por provider (cada um levanta se faltar key/dep) ---------------

def _build_jina():
    from langchain_community.embeddings import JinaEmbeddings
    return JinaEmbeddings(model_name="jina-embeddings-v3")


def _build_openai():
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(model="text-embedding-3-small")


def _build_ollama():
    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(model="bge-m3")


def _build_gemini():
    # gemini-embedding-001 é o estável atual (text-embedding-004 saiu do v1beta).
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")


def _default_builders() -> Dict[str, Callable[[], object]]:
    return {
        "jina": _build_jina,
        "openai": _build_openai,
        "ollama": _build_ollama,
        "gemini": _build_gemini,
    }


_EMBEDDING_BUILDERS: Dict[str, Callable[[], object]] = _default_builders()


# --- Disponibilidade + resolução da cadeia ----------------------------------

def _dep_present(provider: str) -> bool:
    """True se a dependência Python do provider está instalada."""
    import importlib.util as _u
    mod = {
        "jina": "langchain_community.embeddings",
        "openai": "langchain_openai",
        "ollama": "langchain_ollama",
        "gemini": "langchain_google_genai",
    }.get(provider)
    return bool(mod and _u.find_spec(mod) is not None)


def _provider_available(provider: str) -> bool:
    """Candidato disponível na RESOLUÇÃO: key presente (quando aplicável) + dep.
    Ollama não usa key (roda local); gate é só a dep instalada."""
    if provider == "jina":
        return bool(os.getenv("JINA_API_KEY")) and _dep_present("jina")
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY")) and _dep_present("openai")
    if provider == "ollama":
        return _dep_present("ollama")
    if provider == "gemini":
        return bool(os.getenv("GOOGLE_API_KEY")) and _dep_present("gemini")
    return False


def _resolve_provider() -> Optional[str]:
    """Provider ativo para ESCRITA. `RPG_EMBEDDINGS=<p>` força um candidato
    (pula a cadeia; análogo ao LLM_PROVIDER). Senão, primeiro da cadeia
    disponível. None = nenhum candidato → embeddings desativados."""
    override = os.getenv("RPG_EMBEDDINGS")
    if override:
        return override.strip().lower()
    for provider in EMBEDDING_ROUTES:
        if _provider_available(provider):
            return provider
    return None


def get_embeddings_for(provider: str) -> Optional[object]:
    """Constrói (com cache) o objeto de embeddings de UM provider específico.
    Usado para abrir índice pinado. None se o builder falhar (key/dep faltando)."""
    if provider in _embeddings_cache:
        return _embeddings_cache[provider]
    builder = _EMBEDDING_BUILDERS.get(provider)
    if builder is None:
        _LOG.warning("Embeddings: provider desconhecido '%s'.", provider)
        return None
    try:
        emb = builder()
    except Exception as exc:  # sem key/dep, erro de init → indisponível
        _LOG.warning("Embeddings: falha ao inicializar '%s': %s", provider, exc)
        return None
    _embeddings_cache[provider] = emb
    return emb


def active_provider() -> Optional[str]:
    """Provider resolvido na última chamada a get_embeddings() (para meta)."""
    return _active_provider_name


def get_embeddings() -> Optional[object]:
    """Embeddings do provider ATIVO (cabeça da cadeia disponível). Mantém a
    assinatura/singleton histórica. None → embeddings desativados (sem provider
    ou builder falhou); o jogo segue sem RAG."""
    global _active_provider_name
    provider = _resolve_provider()
    if provider is None:
        _LOG.warning("Embeddings desativados: nenhum provider configurado "
                     "(defina JINA_API_KEY/OPENAI_API_KEY/GOOGLE_API_KEY ou Ollama).")
        _active_provider_name = None
        return None
    emb = get_embeddings_for(provider)
    if emb is None:
        _active_provider_name = None
        return None
    _active_provider_name = provider
    _LOG.info("Embeddings ativos: %s (%s).", provider, _PROVIDER_MODELS.get(provider, "?"))
    return emb


# --- Meta por índice (pin) --------------------------------------------------

def _meta_path(dir_path: str) -> str:
    return os.path.join(dir_path, _META_FILE)


def _write_meta(dir_path: str, provider: str) -> None:
    """Grava embeddings_meta.json ao lado do índice (pin do provider)."""
    try:
        os.makedirs(dir_path, exist_ok=True)
        with open(_meta_path(dir_path), "w", encoding="utf-8") as fh:
            json.dump({"provider": provider,
                       "model": _PROVIDER_MODELS.get(provider, "?")},
                      fh, ensure_ascii=False)
    except Exception as exc:
        _LOG.warning("Embeddings: falha ao gravar meta em %s: %s", dir_path, exc)


def _read_meta(dir_path: str) -> Optional[dict]:
    try:
        with open(_meta_path(dir_path), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _embeddings_for_index(dir_path: str) -> Optional[object]:
    """Embeddings PINADOS a um índice existente: usa o provider da meta.
    Índice legado SEM meta → assume gemini (comportamento histórico, R2).
    Meta presente mas sem provider nomeado → reabre com o provider ATIVO
    (`get_embeddings()`): só acontece quando `get_embeddings` foi sobreposto
    — em produção o provider é sempre nomeado. Provider nomeado indisponível
    → None + warning (índice desativado; nunca consultado com vetor alheio)."""
    meta = _read_meta(dir_path)
    if meta is None:
        provider = _LEGACY_PROVIDER
    else:
        provider = meta.get("provider")
        if not provider:
            return get_embeddings()
    if not _provider_available(provider):
        _LOG.warning(
            "Índice '%s' pinado no provider '%s', indisponível agora — índice "
            "DESATIVADO. Reponha a key ou re-indexe (uv run python rag.py).",
            dir_path, provider,
        )
        return None
    return get_embeddings_for(provider)


def _save_index(db, path: str, provider: str) -> None:
    """save_local + grava a meta do provider (pin)."""
    db.save_local(path)
    _write_meta(path, provider)

def get_global_db_path(index_name: str) -> str:
    """Retorna o nome da pasta do índice GLOBAL (lore ou rules)."""
    return f"faiss_{index_name}_index"

def _get_session_path(game_id: str) -> str:
    """Retorna o caminho da pasta de memória da SESSÃO específica."""
    return os.path.join(SAVES_DIR, game_id)


def _has_faiss_index(path: str) -> bool:
    """True só se há um índice FAISS gravado em `path` (arquivo index.faiss).

    O diretório existir NÃO basta: `saves_memory/{game_id}/` é criado como pai
    das subpastas de memória de NPC (`.../{npc_id}/`) mesmo sem índice de sessão.
    Checar o dir levaria `add_memory_to_session` ao ramo de load e a um
    FileIOReader ('could not open .../index.faiss for reading')."""
    return os.path.isfile(os.path.join(path, "index.faiss"))

# --- Visibilidade do Codex (Fase 2.5): public < hidden < secret ---
_VIS_ORDER = {"public": 0, "hidden": 1, "secret": 2}


def vis_rank(visibility: Optional[str]) -> int:
    """Rank de visibilidade. Sem metadado = public; valor desconhecido = secret
    (falha fechada: nunca vazar por typo)."""
    if visibility is None:
        return _VIS_ORDER["public"]
    return _VIS_ORDER.get(visibility, _VIS_ORDER["secret"])


def query_rag(query: str, index_name: str = "lore", game_id: Optional[str] = None,
              max_visibility: str = "public") -> str:
    """
    Busca contexto de forma híbrida:
    1. Índice Global (Lore/Regras) - Imutável durante o jogo.
    2. Índice da Sessão (Memórias do Save) - Dinâmico, se game_id for fornecido.

    `max_visibility` filtra chunks do Codex pelo metadado `visibility`
    (public < hidden < secret). Default preserva o comportamento antigo:
    o jogador/narrador só vê `public`; chunks sem metadado contam como public.
    """
    results = []
    max_rank = vis_rank(max_visibility)

    # 1. Busca Global (Baseado no index_name: 'lore' ou 'rules')
    # Busca k maior e corta após o filtro de visibilidade (spec 2.5 §3).
    # Cada índice usa o provider PINADO na sua meta (nunca mistura vetores).
    global_path = get_global_db_path(index_name)
    if os.path.exists(global_path):
        embeddings = _embeddings_for_index(global_path)
        if embeddings:
            try:
                global_db = FAISS.load_local(global_path, embeddings, allow_dangerous_deserialization=True)
                candidatos = global_db.similarity_search(query, k=6)
                visiveis = [
                    d for d in candidatos
                    if vis_rank(d.metadata.get("visibility")) <= max_rank
                ]
                results.extend(visiveis[:2])
            except Exception as e:
                print(f"⚠️ [RAG] Erro ao ler Global '{index_name}': {e}")

    # 2. Busca na Sessão (Se houver game_id)
    # A memória da sessão é agnóstica ao index_name (é tudo "memória do jogo")
    if game_id:
        session_path = _get_session_path(game_id)
        if _has_faiss_index(session_path):
            embeddings = _embeddings_for_index(session_path)
            if embeddings:
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

    session_path = _get_session_path(game_id)

    try:
        if _has_faiss_index(session_path):
            # Índice existente: precisa do provider PINADO (não pode misturar).
            embeddings = _embeddings_for_index(session_path)
            if not embeddings: return
            provider = (_read_meta(session_path) or {}).get("provider", _LEGACY_PROVIDER)
            db = FAISS.load_local(session_path, embeddings, allow_dangerous_deserialization=True)
            db.add_texts(texts)
        else:
            # Índice novo: provider ATIVO da cadeia + grava meta (pin).
            embeddings = get_embeddings()
            if not embeddings: return
            provider = _resolve_provider()  # puro (lê env); casa com get_embeddings
            if not os.path.exists(SAVES_DIR): os.makedirs(SAVES_DIR)
            db = FAISS.from_texts(texts, embeddings)

        _save_index(db, session_path, provider)
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

    npc_path = _get_npc_path(game_id, npc_id)
    try:
        if _has_faiss_index(npc_path):
            embeddings = _embeddings_for_index(npc_path)
            if not embeddings:
                return
            provider = (_read_meta(npc_path) or {}).get("provider", _LEGACY_PROVIDER)
            db = FAISS.load_local(npc_path, embeddings, allow_dangerous_deserialization=True)
            db.add_texts(texts)
        else:
            embeddings = get_embeddings()
            if not embeddings:
                return
            provider = _resolve_provider()  # puro (lê env); casa com get_embeddings
            os.makedirs(os.path.dirname(npc_path), exist_ok=True)
            db = FAISS.from_texts(texts, embeddings)
        _save_index(db, npc_path, provider)
        print(f"🧠 [RAG] Memória de NPC '{npc_id}' (sessão '{game_id}'): +{len(texts)} fatos.")
    except Exception as e:
        print(f"❌ [RAG ERROR] Falha ao salvar memória do NPC '{npc_id}': {e}")


def query_npc_memory(game_id: str, npc_id: str, query: str, k: int = 3) -> str:
    """
    Recupera por relevância o que ESTE npc viveu com o jogador. "" se sem índice/sem chave.
    """
    if not game_id or not npc_id or not query:
        return ""

    npc_path = _get_npc_path(game_id, npc_id)
    if not _has_faiss_index(npc_path):
        return ""

    embeddings = _embeddings_for_index(npc_path)
    if not embeddings:
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
    Use isso no setup ou quando alterar o data/rules.txt.
    """
    if not os.path.exists(file_path):
        print(f"[ERRO] Arquivo não encontrado: {file_path}")
        return

    embeddings = get_embeddings()
    if embeddings is None: return
    provider = _resolve_provider()

    print(f"--- INGESTÃO: {file_path} -> ÍNDICE: {index_name} (provider: {provider}) ---")

    loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    # Salva no caminho global + meta (pin do provider).
    path = get_global_db_path(index_name)
    db = FAISS.from_documents(chunks, embeddings)
    _save_index(db, path, provider)
    print(f"✅ Indexado com sucesso em '{path}'!")

def reindex_global() -> None:
    """Re-gera os índices globais (lore do Codex + regras).

    Fase 7.2: roda o lint de conteúdo ANTES de ingerir — qualquer ERRO aborta
    com exit 1 sem tocar nos índices FAISS. Só este caminho valida; `query_rag`
    em runtime não (custo por turno desnecessário; índice já nasceu válido).
    """
    import sys

    from services import content_validator

    findings = content_validator.validate_all()
    errors = [f for f in findings if f.severity == "error"]
    if errors:
        for f in errors:
            print(f"❌ [{f.validator}] {f.path}: {f.message}")
        print(f"Lint de conteúdo falhou ({len(errors)} erro(s)) — reindexação abortada.")
        sys.exit(1)

    # Fase 2.5: lore vem do Codex (data/codex/); world_lore.txt foi removido na 2.5b (R5).
    print("Recriando índices globais...")
    from services.codex_loader import ingest_codex
    ingest_codex()
    rules_path = os.path.join("data", "rules.txt")
    if os.path.exists(rules_path):
        ingest_file(rules_path, "rules")
    else:
        print(f"[ERRO] Regras não encontradas em {rules_path}")


if __name__ == "__main__":
    # Console Windows é cp1252; força UTF-8 p/ os emojis dos prints não quebrarem
    # (main.py já faz isso no fluxo do jogo; aqui rodamos standalone).
    import sys
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    reindex_global()