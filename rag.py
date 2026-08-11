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
import hashlib
import logging
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional
import httpx
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

from services.memory_provenance import format_memory_fact, make_memory_fact

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


RAGOperation = Literal["add_session_memory", "add_npc_memory"]


@dataclass(frozen=True)
class RAGOperationEvent:
    """Resultado observável de uma tentativa de escrita de memória vetorial."""

    operation: RAGOperation
    success: bool
    game_id: str
    npc_id: Optional[str]
    path: str
    facts_count: int
    provider: Optional[str]
    error: Optional[str]
    provenance_counts: Dict[str, int] = field(default_factory=dict)


_RAG_OPERATION_HOOK: Optional[Callable[[RAGOperationEvent], None]] = None


def set_rag_operation_hook(
        fn: Optional[Callable[[RAGOperationEvent], None]]) -> None:
    """Registra callback para cada ``add_*``; ``None`` desliga o hook."""
    global _RAG_OPERATION_HOOK
    _RAG_OPERATION_HOOK = fn


def _emit_rag_operation(event: RAGOperationEvent) -> None:
    hook = _RAG_OPERATION_HOOK
    if hook is None:
        return
    try:
        hook(event)
    except Exception as exc:  # observabilidade nunca derruba o turno
        _LOG.warning("RAG operation hook falhou: %s", exc)


def _rag_operation_result(
        operation: RAGOperation,
        success: bool,
        *,
        game_id: str,
        npc_id: Optional[str],
        path: str,
        facts_count: int,
        provider: Optional[str],
        error: Optional[str],
        metadatas: Optional[List[Dict]] = None,
) -> bool:
    provenance_counts = dict(Counter(
        str(metadata.get("memory_provenance") or "legacy_unverified")
        for metadata in (metadatas or [])
        if isinstance(metadata, dict)
    ))
    _emit_rag_operation(RAGOperationEvent(
        operation=operation,
        success=success,
        game_id=game_id,
        npc_id=npc_id,
        path=path,
        facts_count=facts_count,
        provider=provider,
        error=error,
        provenance_counts=provenance_counts,
    ))
    return success


_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,96}$")
_WINDOWS_RESERVED_NAMES = frozenset({
    "con",
    "prn",
    "aux",
    "nul",
    "clock$",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
})


def _is_windows_reserved(value: str) -> bool:
    return value.casefold().split(".", 1)[0] in _WINDOWS_RESERVED_NAMES


def _safe_storage_component(value: object, prefix: str) -> str:
    """Mapeia um ID lógico para um único componente de path portátil.

    IDs ASCII já seguros mantêm exatamente o nome físico legado. Qualquer valor
    inseguro recebe slug ASCII legível mais hash do ID lógico, evitando colisões
    entre Unicode distintos que transliteram para o mesmo texto.
    """
    raw = str(value)
    if (
        _SAFE_COMPONENT_RE.fullmatch(raw)
        and raw not in {".", ".."}
        and not raw.endswith((".", " "))
        and not _is_windows_reserved(raw)
    ):
        return raw

    ascii_value = (
        unicodedata.normalize("NFKD", raw)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_value)
    slug = re.sub(r"_+", "_", slug).strip("._-")
    safe_prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", prefix).strip("_-") or "id"
    if not slug or _is_windows_reserved(slug):
        slug = safe_prefix
    slug = slug[:64].rstrip("._-") or safe_prefix
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{slug}--{digest}"


def _contained_storage_path(*components: str) -> str:
    """Monta path sob ``SAVES_DIR`` e verifica containment sem absolutizar o retorno.

    O retorno relativo é intencional: no Windows evita entregar ao FAISS o
    prefixo Unicode do workspace quando ``SAVES_DIR`` também é relativo.
    """
    path = os.path.join(SAVES_DIR, *components)
    root_abs = os.path.abspath(SAVES_DIR)
    path_abs = os.path.abspath(path)
    try:
        contained = os.path.normcase(os.path.commonpath([root_abs, path_abs]))
    except ValueError as exc:
        raise ValueError("path de memória fora da raiz") from exc
    if contained != os.path.normcase(root_abs):
        raise ValueError("path de memória fora da raiz")
    return path


# --- Builders por provider (cada um levanta se faltar key/dep) ---------------

_JINA_API_URL = "https://api.jina.ai/v1/embeddings"
_TRANSIENT_EMBEDDING_STATUS = {408, 429, 500, 502, 503, 504}


class _JinaEmbeddingsHTTPX(Embeddings):
    """Cliente Jina pequeno, síncrono e com limite de rede explícito.

    O adapter da comunidade usa ``requests.Session.post`` sem timeout. Em um
    playtest real isso deixou um turno pendurado por mais de 15 minutos. Aqui o
    retry permanece no MESMO provider/modelo, portanto nunca mistura espaços
    vetoriais em um índice FAISS pinado.
    """

    def __init__(self, *, api_key: str, model_name: str,
                 timeout_seconds: float = 30.0, max_attempts: int = 2,
                 client: Optional[httpx.Client] = None) -> None:
        self.model_name = model_name
        self.max_attempts = max(1, int(max_attempts))
        self._client = client or httpx.Client(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept-Encoding": "identity",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(max(0.1, float(timeout_seconds))),
        )

    def _embed(self, values: List[str]) -> List[List[float]]:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_attempts):
            try:
                response = self._client.post(
                    _JINA_API_URL,
                    json={"input": values, "model": self.model_name},
                )
                if (response.status_code in _TRANSIENT_EMBEDDING_STATUS
                        and attempt + 1 < self.max_attempts):
                    last_error = httpx.HTTPStatusError(
                        f"Jina transitório: HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    continue
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise ValueError("resposta Jina sem lista 'data'")
                ordered = sorted(rows, key=lambda row: int(row["index"]))
                vectors = [row.get("embedding") for row in ordered]
                if (len(vectors) != len(values)
                        or any(not isinstance(vector, list) for vector in vectors)):
                    raise ValueError("resposta Jina com embeddings inválidos")
                return vectors
            except httpx.TransportError as exc:
                last_error = exc
                if attempt + 1 >= self.max_attempts:
                    raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("Jina não executou nenhuma tentativa")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text])[0]


def _build_jina():
    api_key = os.getenv("JINA_API_KEY") or os.getenv("JINA_AUTH_TOKEN")
    if not api_key:
        raise ValueError("JINA_API_KEY não configurada")
    timeout_seconds = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))
    max_attempts = int(os.getenv("EMBEDDING_MAX_ATTEMPTS", "2"))
    return _JinaEmbeddingsHTTPX(
        api_key=api_key,
        model_name="jina-embeddings-v3",
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )


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


def _write_meta(dir_path: str, provider: str) -> bool:
    """Grava embeddings_meta.json ao lado do índice (pin do provider)."""
    try:
        if not provider:
            raise ValueError("provider de embeddings ausente")
        os.makedirs(dir_path, exist_ok=True)
        with open(_meta_path(dir_path), "w", encoding="utf-8") as fh:
            json.dump({"provider": provider,
                       "model": _PROVIDER_MODELS.get(provider, "?")},
                      fh, ensure_ascii=False)
        return True
    except Exception as exc:
        _LOG.warning("Embeddings: falha ao gravar meta em %s: %s", dir_path, exc)
        return False


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
    if not _write_meta(path, provider):
        raise OSError(f"falha ao gravar metadata do índice em {path}")

def get_global_db_path(index_name: str) -> str:
    """Retorna o nome da pasta do índice GLOBAL (lore ou rules)."""
    return f"faiss_{index_name}_index"

def _get_session_path(game_id: str) -> str:
    """Retorna o caminho da pasta de memória da SESSÃO específica."""
    component = _safe_storage_component(game_id, "session")
    return _contained_storage_path(component)


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


def _query_session_documents(query: str, game_id: str, *, k: int = 2) -> list:
    if not query or not game_id:
        return []
    session_path = _get_session_path(game_id)
    if not _has_faiss_index(session_path):
        return []
    embeddings = _embeddings_for_index(session_path)
    if not embeddings:
        return []
    try:
        session_db = FAISS.load_local(
            session_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        return list(session_db.similarity_search(query, k=k))
    except Exception as exc:
        _LOG.warning(
            "RAG: falha ao consultar memória da sessão '%s': %s",
            game_id,
            exc,
        )
        return []


def _format_documents(documents: list) -> str:
    seen = set()
    final_text = []
    for doc in documents:
        content = str(getattr(doc, "page_content", "") or "").strip()
        if content and content not in seen:
            seen.add(content)
            final_text.append(content)
    return "\n---\n".join(final_text)


def _format_memory_documents(documents: list) -> str:
    """Renderiza vetores de sessão com autoridade explícita.

    Documento anterior à spec não possui metadata e, por definição, é legado
    não verificado. Duplicatas com o mesmo texto preferem maior confiança.
    """
    rank = {"speculative": 0, "reported": 1, "confirmed": 2}
    by_text: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for doc in documents:
        content = str(getattr(doc, "page_content", "") or "").strip()
        if not content:
            continue
        metadata = dict(getattr(doc, "metadata", {}) or {})
        provenance = metadata.get("memory_provenance") or "legacy_unverified"
        source_turn = metadata.get("memory_source_turn")
        if source_turn in (-1, "-1", ""):
            source_turn = None
        entity_ids = str(metadata.get("memory_entity_ids") or "").split(",")
        try:
            record = make_memory_fact(
                content,
                provenance=provenance,
                confidence=metadata.get("memory_confidence") or "speculative",
                source_id=metadata.get("memory_source_id") or None,
                source_turn=source_turn,
                canonical_entity_ids=[item for item in entity_ids if item],
            )
        except Exception:
            record = make_memory_fact(
                content, provenance="legacy_unverified",
            )
        rendered = format_memory_fact(record)
        key = content.casefold()
        item_rank = rank[record["confidence"]]
        if key not in by_text:
            order.append(key)
            by_text[key] = (item_rank, rendered)
        elif item_rank > by_text[key][0]:
            by_text[key] = (item_rank, rendered)
    return "\n---\n".join(by_text[key][1] for key in order[:2])


def query_session_memory(query: str, game_id: str) -> str:
    """Busca somente fatos da sessão, sem consultar lore/regras globais."""
    return _format_memory_documents(_query_session_documents(query, game_id, k=6))


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
    global_results = []
    session_results = []
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
                global_results.extend(visiveis[:2])
            except Exception as e:
                print(f"⚠️ [RAG] Erro ao ler Global '{index_name}': {e}")

    # 2. Busca na Sessão (Se houver game_id)
    # A memória da sessão é agnóstica ao index_name (é tudo "memória do jogo")
    if game_id:
        session_results.extend(_query_session_documents(query, game_id, k=6))

    parts = [
        part for part in (
            _format_documents(global_results),
            _format_memory_documents(session_results),
        ) if part
    ]
    return "\n---\n".join(parts)

def add_memory_to_session(
    game_id: str,
    texts: List[str],
    *,
    metadatas: Optional[List[Dict]] = None,
) -> bool:
    """Adiciona fatos à sessão e informa se a gravação física terminou."""
    facts_count = len(texts) if isinstance(texts, list) else 0
    if not game_id or not texts:
        return _rag_operation_result(
            "add_session_memory",
            False,
            game_id=str(game_id or ""),
            npc_id=None,
            path="",
            facts_count=facts_count,
            provider=None,
            error="invalid_input",
            metadatas=metadatas,
        )

    session_path = ""
    provider: Optional[str] = None
    try:
        session_path = _get_session_path(game_id)
        if _has_faiss_index(session_path):
            # Índice existente: usa somente o provider pinado.
            provider = (_read_meta(session_path) or {}).get(
                "provider", _LEGACY_PROVIDER
            )
            embeddings = _embeddings_for_index(session_path)
            if not embeddings:
                return _rag_operation_result(
                    "add_session_memory",
                    False,
                    game_id=game_id,
                    npc_id=None,
                    path=session_path,
                    facts_count=facts_count,
                    provider=provider,
                    error="embeddings_unavailable",
                    metadatas=metadatas,
                )
            db = FAISS.load_local(
                session_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
            if metadatas is None:
                db.add_texts(texts)
            else:
                db.add_texts(texts, metadatas=metadatas)
        else:
            embeddings = get_embeddings()
            provider = active_provider() or _resolve_provider()
            if not embeddings or not provider:
                return _rag_operation_result(
                    "add_session_memory",
                    False,
                    game_id=game_id,
                    npc_id=None,
                    path=session_path,
                    facts_count=facts_count,
                    provider=provider,
                    error="embeddings_unavailable",
                    metadatas=metadatas,
                )
            os.makedirs(SAVES_DIR, exist_ok=True)
            if metadatas is None:
                db = FAISS.from_texts(texts, embeddings)
            else:
                db = FAISS.from_texts(texts, embeddings, metadatas=metadatas)

        _save_index(db, session_path, provider)
        print(f"💾 [RAG] Memória salva para sessão '{game_id}': +{facts_count} fatos.")
        return _rag_operation_result(
            "add_session_memory",
            True,
            game_id=game_id,
            npc_id=None,
            path=session_path,
            facts_count=facts_count,
            provider=provider,
            error=None,
            metadatas=metadatas,
        )
    except Exception as exc:
        print(f"❌ [RAG ERROR] Falha ao salvar memória: {exc}")
        return _rag_operation_result(
            "add_session_memory",
            False,
            game_id=game_id,
            npc_id=None,
            path=session_path,
            facts_count=facts_count,
            provider=provider,
            error=str(exc),
            metadatas=metadatas,
        )

# --- MEMÓRIA DE NPC VETORIZADA (namespace por game_id + npc_id) ---

def _get_npc_path(game_id: str, npc_id: str) -> str:
    """Pasta do índice FAISS de UM npc dentro da sessão."""
    session_component = _safe_storage_component(game_id, "session")
    npc_component = _safe_storage_component(npc_id, "npc")
    return _contained_storage_path(session_component, npc_component)


def add_npc_memory(
    game_id: str,
    npc_id: str,
    texts: List[str],
    *,
    metadatas: Optional[List[Dict]] = None,
) -> bool:
    """Adiciona fatos ao namespace do NPC e retorna sucesso físico."""
    facts_count = len(texts) if isinstance(texts, list) else 0
    if not game_id or not npc_id or not texts:
        return _rag_operation_result(
            "add_npc_memory",
            False,
            game_id=str(game_id or ""),
            npc_id=str(npc_id) if npc_id else None,
            path="",
            facts_count=facts_count,
            provider=None,
            error="invalid_input",
            metadatas=metadatas,
        )

    npc_path = ""
    provider: Optional[str] = None
    try:
        npc_path = _get_npc_path(game_id, npc_id)
        if _has_faiss_index(npc_path):
            provider = (_read_meta(npc_path) or {}).get(
                "provider", _LEGACY_PROVIDER
            )
            embeddings = _embeddings_for_index(npc_path)
            if not embeddings:
                return _rag_operation_result(
                    "add_npc_memory",
                    False,
                    game_id=game_id,
                    npc_id=npc_id,
                    path=npc_path,
                    facts_count=facts_count,
                    provider=provider,
                    error="embeddings_unavailable",
                    metadatas=metadatas,
                )
            db = FAISS.load_local(
                npc_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
            if metadatas is None:
                db.add_texts(texts)
            else:
                db.add_texts(texts, metadatas=metadatas)
        else:
            embeddings = get_embeddings()
            provider = active_provider() or _resolve_provider()
            if not embeddings or not provider:
                return _rag_operation_result(
                    "add_npc_memory",
                    False,
                    game_id=game_id,
                    npc_id=npc_id,
                    path=npc_path,
                    facts_count=facts_count,
                    provider=provider,
                    error="embeddings_unavailable",
                    metadatas=metadatas,
                )
            os.makedirs(os.path.dirname(npc_path), exist_ok=True)
            if metadatas is None:
                db = FAISS.from_texts(texts, embeddings)
            else:
                db = FAISS.from_texts(texts, embeddings, metadatas=metadatas)

        _save_index(db, npc_path, provider)
        print(
            f"🧠 [RAG] Memória de NPC '{npc_id}' "
            f"(sessão '{game_id}'): +{facts_count} fatos."
        )
        return _rag_operation_result(
            "add_npc_memory",
            True,
            game_id=game_id,
            npc_id=npc_id,
            path=npc_path,
            facts_count=facts_count,
            provider=provider,
            error=None,
            metadatas=metadatas,
        )
    except Exception as exc:
        print(f"❌ [RAG ERROR] Falha ao salvar memória do NPC '{npc_id}': {exc}")
        return _rag_operation_result(
            "add_npc_memory",
            False,
            game_id=game_id,
            npc_id=npc_id,
            path=npc_path,
            facts_count=facts_count,
            provider=provider,
            error=str(exc),
            metadatas=metadatas,
        )


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

    return _format_memory_documents(docs)


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
