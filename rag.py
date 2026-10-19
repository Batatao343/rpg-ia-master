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
com aviso; re-index para trocar). Ver specs/SPEC-039-embeddings-provider.md.
"""
from observability.telemetry import log_event as _log_event
import json
import hashlib
import logging
import os
import re
import time
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional
import httpx
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

from services.memory_provenance import format_memory_fact, make_memory_fact

load_dotenv(override=True)  # .env canônico (sobrepõe env var do SO)

_LOG = logging.getLogger("rpg.rag")
_embedding_usage_hook: ContextVar[Callable[[dict], None] | None] = ContextVar(
    "embedding_usage_hook", default=None)


@contextmanager
def embedding_usage_scope(hook: Callable[[dict], None]) -> Iterator[None]:
    token = _embedding_usage_hook.set(hook)
    try:
        yield
    finally:
        _embedding_usage_hook.reset(token)


def _emit_embedding_attempt(provider: str, model: str, outcome: str,
                            usage: object = None) -> None:
    hook = _embedding_usage_hook.get()
    if hook is None:
        return
    from services.usage_metering import safe_provider_usage

    reading = safe_provider_usage(usage)
    if ("input_tokens" not in reading and isinstance(usage, dict)
            and isinstance(usage.get("total_tokens"), int)
            and not isinstance(usage["total_tokens"], bool)
            and usage["total_tokens"] >= 0):
        reading["input_tokens"] = usage["total_tokens"]
    hook({"provider": provider, "model": model, "outcome": outcome,
          "network_attempted": True, "usage": reading})

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


@dataclass(frozen=True)
class RetrievedEvidence:
    """Structured retrieval result used by diagnostics and evals.

    Production callers may keep using the text-returning query functions. This
    shape exposes stable evidence identity without making text matching an
    oracle.
    """

    id: str
    source: str
    score: float
    text: str
    visibility: str
    metadata: Dict[str, Any] = field(default_factory=dict)


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


class _ScopedMeteredEmbeddings(Embeddings):
    """Count opaque SDK calls when their vector API omits usage metadata."""

    def __init__(self, delegate: Embeddings, provider: str, model: str) -> None:
        self.delegate = delegate
        self.provider = provider
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            vectors = self.delegate.embed_documents(texts)
        except Exception:
            _emit_embedding_attempt(self.provider, self.model, "error")
            raise
        _emit_embedding_attempt(self.provider, self.model, "response")
        return vectors

    def embed_query(self, text: str) -> List[float]:
        try:
            vector = self.delegate.embed_query(text)
        except Exception:
            _emit_embedding_attempt(self.provider, self.model, "error")
            raise
        _emit_embedding_attempt(self.provider, self.model, "response")
        return vector


def _scoped_embeddings(provider: str, embeddings: Embeddings) -> Embeddings:
    if provider == "jina" or _embedding_usage_hook.get() is None:
        return embeddings
    return _ScopedMeteredEmbeddings(
        embeddings, provider, _PROVIDER_MODELS.get(provider, "unknown"))


def _has_token_usage(usage: object) -> bool:
    if not isinstance(usage, dict):
        return False
    return any(isinstance(usage.get(key), int) and not isinstance(usage.get(key), bool)
               and usage[key] >= 0 for key in ("prompt_tokens", "input_tokens", "total_tokens"))


def _estimated_embedding_usage(values: List[str]) -> dict[str, int]:
    """SPEC-237: no usage block -> conservative estimate (~2 chars/token), flagged; no text."""
    chars = sum(len(value) for value in values)
    return {"input_tokens": -(-chars // 2), "units_estimated": 1}


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

    def _log_attempt(self, outcome: str, attempt: int, started: float,
                     http_status: Optional[int]) -> None:
        # SPEC-258: so metadados (nunca o texto embeddado nem URL).
        from observability.telemetry import log_provider_attempt
        log_provider_attempt("embedding", "jina", self.model_name, outcome,
                             http_status=http_status,
                             latency_ms=(time.perf_counter() - started) * 1000,
                             attempt=attempt + 1, fell_back=False,
                             cost_basis="exact" if outcome == "success" else "unknown")

    def _embed(self, values: List[str]) -> List[List[float]]:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_attempts):
            started = time.perf_counter()
            try:
                response = self._client.post(
                    _JINA_API_URL,
                    json={"input": values, "model": self.model_name},
                )
                if (response.status_code in _TRANSIENT_EMBEDDING_STATUS
                        and attempt + 1 < self.max_attempts):
                    _emit_embedding_attempt("jina", self.model_name, "http_error")
                    self._log_attempt("http_error", attempt, started, response.status_code)
                    last_error = httpx.HTTPStatusError(
                        f"Jina transitório: HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    continue
                if response.status_code >= 400:
                    _emit_embedding_attempt("jina", self.model_name, "http_error")
                    self._log_attempt("http_error", attempt, started, response.status_code)
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError:
                    # SPEC-237: the provider answered (and may have billed) -> estimate, not US$ 1.
                    _emit_embedding_attempt("jina", self.model_name, "invalid_response",
                                            _estimated_embedding_usage(values))
                    self._log_attempt("invalid_response", attempt, started, response.status_code)
                    raise
                usage = payload.get("usage") if isinstance(payload, dict) else None
                if not _has_token_usage(usage):
                    usage = _estimated_embedding_usage(values)
                _emit_embedding_attempt("jina", self.model_name, "response", usage)
                self._log_attempt("success", attempt, started, response.status_code)
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
                _emit_embedding_attempt("jina", self.model_name, "transport_error")
                self._log_attempt("timeout" if isinstance(exc, httpx.TimeoutException)
                                  else "transport_error", attempt, started, None)
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
    api_key = _jina_key()
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
    return OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1024)


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

def _jina_key() -> str:
    """Helper unico da credencial Jina (SPEC-234 R4): API_KEY ou AUTH_TOKEN."""
    return os.getenv("JINA_API_KEY") or os.getenv("JINA_AUTH_TOKEN") or ""


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
        return bool(_jina_key()) and _dep_present("jina")
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY")) and _dep_present("openai")
    if provider == "ollama":
        # Pacote instalado não significa que o daemon local está disponível.
        # A rota automática exige host explícito; RPG_EMBEDDINGS=ollama segue
        # como opt-in e é tratado antes desta função.
        override = (os.getenv("RPG_EMBEDDINGS") or "").strip().lower()
        return (
            bool(os.getenv("OLLAMA_HOST")) or override == "ollama"
        ) and _dep_present("ollama")
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
        return _scoped_embeddings(provider, _embeddings_cache[provider])
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
    return _scoped_embeddings(provider, emb)


# SPEC-234 R9: dimensao do vetor por provider (o pgvector so aceita 1024).
_PROVIDER_DIMS: Dict[str, int] = {
    "jina": 1024, "openai": 1024, "ollama": 1024, "gemini": 3072,
}
PGVECTOR_DIMENSIONS = 1024


def embedding_profile_id(provider: Optional[str] = None) -> str:
    """ID do perfil de embedding: `{provider}-{modelo}-{dim}` (R9).

    Sem provider resolvido devolve o perfil legado `local-1024`.
    """
    provider = (provider or _resolve_provider() or "").strip().lower()
    if not provider:
        return "local-1024"
    model = _PROVIDER_MODELS.get(provider, "?").split("/")[-1]
    dims = _PROVIDER_DIMS.get(provider, PGVECTOR_DIMENSIONS)
    return re.sub(r"[^a-z0-9._-]+", "-", f"{provider}-{model}-{dims}".lower())


def validate_pgvector_provider(provider: Optional[str] = None) -> None:
    """Recusa, na inicializacao, provider cuja dimensao != 1024 (R9)."""
    provider = (provider or _resolve_provider() or "").strip().lower()
    dims = _PROVIDER_DIMS.get(provider)
    if provider and dims is not None and dims != PGVECTOR_DIMENSIONS:
        raise ValueError(
            f"provider de embeddings '{provider}' gera {dims} dimensões; "
            f"o pgvector exige {PGVECTOR_DIMENSIONS}. Use jina, openai (1024) ou ollama bge-m3."
        )


def _note_degraded(source: str) -> None:
    """Metrica `rpg_rag_degraded_total{source}` junto do WARNING (R10)."""
    try:
        from observability.metrics import metrics
        metrics.increment("rpg_rag_degraded_total", {"source": source})
    except Exception:  # pragma: no cover - telemetria nunca derruba a consulta
        pass


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
    _LOG.debug("Embeddings ativos: %s (%s).", provider, _PROVIDER_MODELS.get(provider, "?"))
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
    except FileNotFoundError:
        return None
    except Exception as exc:
        from observability.telemetry import log_event
        base = os.path.basename(os.path.normpath(dir_path))
        index = base if base in ("faiss_lore_index", "faiss_rules_index") else "session"
        log_event("rag", "meta_unreadable", level="warning", index=index,
                  error_type=type(exc).__name__, fallback_provider="gemini")
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
    override = (os.getenv("RPG_EMBEDDINGS") or "").strip().lower()
    if meta is not None and meta.get("model") not in (None, "?"):
        expected = _PROVIDER_MODELS.get(provider)
        if expected and meta.get("model") != expected:
            _LOG.warning(
                "Índice '%s' gerado com o modelo '%s' (atual '%s') — índice "
                "DESATIVADO para não misturar vetores. Re-indexe.",
                dir_path, meta.get("model"), expected,
            )
            _note_degraded("index_disabled")
            return None
    if override != provider and not _provider_available(provider):
        _LOG.warning(
            "Índice '%s' pinado no provider '%s', indisponível agora — índice "
            "DESATIVADO. Reponha a key ou re-indexe (uv run python rag.py).",
            dir_path, provider,
        )
        _note_degraded("index_disabled")
        return None
    return get_embeddings_for(provider)


def _save_index(db, path: str, provider: str) -> None:
    """save_local + grava a meta do provider (pin)."""
    # SPEC-234 R10: grava em diretorio temporario e troca arquivo a arquivo,
    # para uma falha no meio nao deixar o indice meio escrito.
    import shutil
    import tempfile
    parent = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".idx-", dir=parent)
    try:
        db.save_local(tmp)
        os.makedirs(path, exist_ok=True)
        for name in os.listdir(tmp):
            os.replace(os.path.join(tmp, name), os.path.join(path, name))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
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


def query_faiss_evidence(
    db: Any,
    vector: List[float],
    *,
    k: int = 5,
    fetch_k: Optional[int] = None,
    max_visibility: Optional[str] = None,
    source: str = "lore",
) -> List[RetrievedEvidence]:
    """Return the same FAISS ranking used by production as structured evidence.

    The text-returning production APIs format this trace after ranking. Evals can
    inspect IDs and visibility directly, using an in-memory FAISS index with
    deterministic fixture vectors and no external embedding provider.
    """

    if k < 1:
        raise ValueError("k must be positive")
    if not vector:
        raise ValueError("vector cannot be empty")
    candidate_count = k if fetch_k is None else int(fetch_k)
    if candidate_count < k:
        raise ValueError("fetch_k cannot be smaller than k")
    maximum = vis_rank(max_visibility) if max_visibility is not None else None
    candidates = db.similarity_search_with_score_by_vector(
        [float(value) for value in vector],
        k=candidate_count,
    )
    evidence: List[RetrievedEvidence] = []
    seen_ids: set[str] = set()
    for document, distance in candidates:
        metadata = dict(getattr(document, "metadata", {}) or {})
        visibility = str(metadata.get("visibility") or "public").strip().lower()
        if maximum is not None and vis_rank(visibility) > maximum:
            continue
        content = str(getattr(document, "page_content", "") or "")
        content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]
        evidence_id = str(
            metadata.get("evidence_id")
            or metadata.get("memory_id")
            or ""
        ).strip()
        if not evidence_id:
            entity_id = str(metadata.get("entity_id") or metadata.get("id") or "").strip()
            if entity_id:
                metadata.setdefault("entity_id", entity_id)
                evidence_id = f"{entity_id}#chunk_{content_digest}"
            else:
                evidence_id = f"content_{content_digest}"
        if evidence_id in seen_ids:
            chunk_id = f"{evidence_id}#chunk_{content_digest}"
            if chunk_id in seen_ids:
                continue
            evidence_id = chunk_id
        seen_ids.add(evidence_id)
        evidence.append(RetrievedEvidence(
            id=evidence_id,
            source=str(metadata.get("source") or source),
            score=-float(distance),
            text=content,
            visibility=visibility,
            metadata=metadata,
        ))
        if len(evidence) >= k:
            break
    return evidence


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
        content = str(
            getattr(doc, "page_content", None) or getattr(doc, "text", "") or ""
        ).strip()
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
        content = str(
            getattr(doc, "page_content", None) or getattr(doc, "text", "") or ""
        ).strip()
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
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.contracts import MemoryQuery
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        documents = get_runtime().memory_store.query(MemoryQuery(
            text=query, scope="session", principal=current_principal(),
            game_id=uuid.UUID(str(game_id)), k=6,
        ))
        return _format_memory_documents(documents)  # SPEC-234 R9
    return _format_memory_documents(_query_session_documents(query, game_id, k=6))


def prepare_shared_query_vector(query: str, paths: List[str]) -> tuple[Optional[List[float]], Optional[str], Optional[str]]:
    """Embed once when every existing FAISS scope uses the same pinned profile."""
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        embeddings = get_embeddings()
        provider = active_provider() or _resolve_provider()
        if not query or embeddings is None or provider is None:
            return None, provider, _PROVIDER_MODELS.get(provider or "")
        try:
            vector = list(embeddings.embed_query(query))
        except Exception:
            return None, provider, _PROVIDER_MODELS.get(provider)
        if len(vector) != 1024:
            _LOG.warning("Vetor compartilhado incompatível com PgVector: %s dimensões", len(vector))
            return None, provider, _PROVIDER_MODELS.get(provider)
        return vector, provider, _PROVIDER_MODELS.get(provider)
    indexed = [path for path in paths if _has_faiss_index(path)]
    if not query or not indexed:
        return None, None, None
    providers = set()
    metadata = []
    for path in indexed:
        meta = _read_meta(path) or {}
        metadata.append(meta)
        providers.add(meta.get("provider") or _LEGACY_PROVIDER)
    if len(providers) != 1:
        return None, None, None
    provider = providers.pop()
    model = _PROVIDER_MODELS.get(provider)
    if any(meta.get("model", model) != model for meta in metadata):
        _LOG.warning("Modelo de embedding incompatível; contexto compartilhado recusado")
        return None, provider, model
    embeddings = get_embeddings_for(provider)
    if embeddings is None:
        return None, provider, _PROVIDER_MODELS.get(provider)
    try:
        vector = list(embeddings.embed_query(query))
    except Exception:
        return None, provider, _PROVIDER_MODELS.get(provider)
    if any(
        meta.get("dimensions") is not None and meta["dimensions"] != len(vector)
        for meta in metadata
    ):
        _LOG.warning("Dimensão de embedding incompatível; contexto compartilhado recusado")
        return None, provider, model
    return vector, provider, _PROVIDER_MODELS.get(provider)


def query_global_by_vector(vector: List[float], index_name: str = "lore",
                           max_visibility: str = "public") -> str:
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.contracts import MemoryQuery
        from infrastructure.runtime import get_runtime

        documents = get_runtime().memory_store.query(MemoryQuery(
            text="", scope="rules" if index_name == "rules" else "lore",
            max_visibility=max_visibility, k=2, vector=tuple(vector),
            embedding_profile_id=embedding_profile_id(),
        ))
        return "\n---\n".join(document.text for document in documents if document.text)
    path = get_global_db_path(index_name)
    if not vector or not _has_faiss_index(path):
        return ""
    embeddings = _embeddings_for_index(path)
    if embeddings is None:
        return ""
    try:
        db = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
        evidence = query_faiss_evidence(
            db,
            vector,
            k=2,
            fetch_k=6,
            max_visibility=max_visibility,
            source=index_name,
        )
        return _format_documents(evidence)
    except Exception:
        _LOG.warning("RAG: consulta degradada (rpg.rag.degraded)", exc_info=True)
        _note_degraded("global")
        return ""


def query_session_by_vector(vector: List[float], game_id: str, *, k: int = 6) -> str:
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.contracts import MemoryQuery
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        documents = get_runtime().memory_store.query(MemoryQuery(
            text="", scope="session", principal=current_principal(),
            game_id=uuid.UUID(str(game_id)), k=k, vector=tuple(vector),
            embedding_profile_id=embedding_profile_id(),
        ))
        return _format_memory_documents(documents)  # SPEC-234 R9
    path = _get_session_path(game_id)
    if not vector or not _has_faiss_index(path):
        return ""
    embeddings = _embeddings_for_index(path)
    if embeddings is None:
        return ""
    try:
        db = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
        evidence = query_faiss_evidence(
            db, vector, k=k, source="session"
        )
        return _format_memory_documents(evidence)
    except Exception:
        _LOG.warning("RAG: consulta degradada (rpg.rag.degraded)", exc_info=True)
        _note_degraded("session")
        return ""


def query_npc_by_vector(vector: List[float], game_id: str, npc_id: str, *, k: int = 3) -> str:
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.contracts import MemoryQuery
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        documents = get_runtime().memory_store.query(MemoryQuery(
            text="", scope="npc", principal=current_principal(),
            game_id=uuid.UUID(str(game_id)), npc_id=npc_id, k=k,
            vector=tuple(vector), embedding_profile_id=embedding_profile_id(),
        ))
        return _format_memory_documents(documents)  # SPEC-234 R9
    path = _get_npc_path(game_id, npc_id)
    if not vector or not _has_faiss_index(path):
        return ""
    embeddings = _embeddings_for_index(path)
    if embeddings is None:
        return ""
    try:
        db = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
        evidence = query_faiss_evidence(
            db, vector, k=k, source="npc"
        )
        return _format_memory_documents(evidence)
    except Exception:
        _LOG.warning("RAG: consulta degradada (rpg.rag.degraded)", exc_info=True)
        _note_degraded("npc")
        return ""


def context_index_paths(*, game_id: Optional[str] = None,
                        npc_id: Optional[str] = None,
                        index_name: str = "lore") -> List[str]:
    paths = [get_global_db_path(index_name)]
    if game_id:
        paths.append(_get_session_path(game_id))
    if game_id and npc_id:
        paths.append(_get_npc_path(game_id, npc_id))
    return paths


def _query_rag_impl(query: str, index_name: str = "lore", game_id: Optional[str] = None,
                    max_visibility: str = "public") -> str:
    """
    Busca contexto de forma híbrida:
    1. Índice Global (Lore/Regras) - Imutável durante o jogo.
    2. Índice da Sessão (Memórias do Save) - Dinâmico, se game_id for fornecido.

    `max_visibility` filtra chunks do Codex pelo metadado `visibility`
    (public < hidden < secret). Default preserva o comportamento antigo:
    o jogador/narrador só vê `public`; chunks sem metadado contam como public.
    """
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.contracts import MemoryQuery
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        store = get_runtime().memory_store
        global_docs = store.query(MemoryQuery(
            text=query, scope="rules" if index_name == "rules" else "lore",
            max_visibility=max_visibility, k=2,
        ))
        session_docs = []
        if game_id:
            principal = current_principal()
            session_docs = store.query(MemoryQuery(
                text=query, scope="session", principal=principal,
                game_id=uuid.UUID(str(game_id)), max_visibility=max_visibility, k=2,
            ))
        return "\n---\n".join(
            document.text for document in [*global_docs, *session_docs]
            if document.text
        )

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
                _log_event("rag", "global_index_read_failed", level="warning", index=index_name, error=type(e).__name__)

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


def query_rag(query: str, index_name: str = "lore", game_id: Optional[str] = None,
              max_visibility: str = "public") -> str:
    """Boundary observável da busca híbrida, sem expor consulta nem IDs."""
    started = time.perf_counter()
    scope = "session" if game_id else ("rules" if index_name == "rules" else "lore")
    outcome = "ok"
    try:
        from observability.telemetry import span
        with span("rag.query", scope=scope):
            return _query_rag_impl(query, index_name, game_id, max_visibility)
    except Exception:
        outcome = "error"
        raise
    finally:
        try:
            from observability.metrics import metrics
            metrics.observe(
                "rpg_rag_duration_seconds", {"scope": scope, "outcome": outcome},
                time.perf_counter() - started,
            )
        except Exception:
            pass

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

    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        try:
            import hashlib
            from infrastructure.contracts import MemoryDocument, MemoryWriteIntent
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            principal = current_principal()
            store = get_runtime().memory_store
            for index, text in enumerate(texts):
                metadata = dict((metadatas or [{}] * len(texts))[index] or {})
                digest = hashlib.sha256(
                    f"{game_id}:{text}:{metadata}".encode("utf-8")
                ).hexdigest()
                store.stage(MemoryWriteIntent(
                    document=MemoryDocument(
                        document_id=f"session:{digest}", text=str(text),
                        scope="session", metadata=metadata,
                    ),
                    principal=principal, game_id=uuid.UUID(str(game_id)),
                    timeline_epoch=int(metadata.get("timeline_epoch", 0) or 0),
                ))
            return _rag_operation_result(
                "add_session_memory", True, game_id=game_id, npc_id=None,
                path="postgres://app.memory_documents", facts_count=facts_count,
                provider="pgvector", error=None, metadatas=metadatas,
            )
        except Exception as exc:
            return _rag_operation_result(
                "add_session_memory", False, game_id=game_id, npc_id=None,
                path="postgres://app.memory_documents", facts_count=facts_count,
                provider="pgvector", error=type(exc).__name__, metadatas=metadatas,
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
        _log_event("rag", "session_memory_saved", level="debug", facts=facts_count)
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
        _log_event("rag", "session_memory_failed", level="error", error=type(exc).__name__)
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

    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        try:
            from infrastructure.contracts import MemoryDocument, MemoryWriteIntent
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            principal = current_principal()
            store = get_runtime().memory_store
            for index, text in enumerate(texts):
                metadata = dict((metadatas or [{}] * len(texts))[index] or {})
                digest = hashlib.sha256(
                    f"{game_id}:{npc_id}:{text}:{metadata}".encode("utf-8")
                ).hexdigest()
                store.stage(MemoryWriteIntent(
                    document=MemoryDocument(
                        document_id=f"npc:{digest}", text=str(text),
                        scope="npc", metadata=metadata,
                    ),
                    principal=principal, game_id=uuid.UUID(str(game_id)),
                    npc_id=npc_id,
                    timeline_epoch=int(metadata.get("timeline_epoch", 0) or 0),
                ))
            return _rag_operation_result(
                "add_npc_memory", True, game_id=game_id, npc_id=npc_id,
                path="postgres://app.memory_documents", facts_count=facts_count,
                provider="pgvector", error=None, metadatas=metadatas,
            )
        except Exception as exc:
            return _rag_operation_result(
                "add_npc_memory", False, game_id=game_id, npc_id=npc_id,
                path="postgres://app.memory_documents", facts_count=facts_count,
                provider="pgvector", error=type(exc).__name__, metadatas=metadatas,
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
        _log_event("rag", "npc_memory_saved", level="debug", facts=facts_count)
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
        _log_event("rag", "npc_memory_failed", level="error", error=type(exc).__name__)
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

    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.contracts import MemoryQuery
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        documents = get_runtime().memory_store.query(MemoryQuery(
            text=query, scope="npc", principal=current_principal(),
            game_id=uuid.UUID(str(game_id)), npc_id=npc_id, k=k,
        ))
        return _format_memory_documents(documents)  # SPEC-234 R9

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
        _LOG.warning("RAG: consulta degradada (rpg.rag.degraded)", exc_info=True)
        _note_degraded("query_npc_memory")
        return ""

    return _format_memory_documents(docs)


# --- FUNÇÕES DE UTILIDADE (Setup Inicial) ---

def ingest_file(file_path: str, index_name: str):
    """
    Ingere um arquivo de texto para criar os índices GLOBAIS (lore/rules).
    Use isso no setup ou quando alterar o data/rules.txt.
    """
    if not os.path.exists(file_path):
        _log_event("rag", "ingest_file_missing", level="error")
        return

    embeddings = get_embeddings()
    if embeddings is None: return
    provider = _resolve_provider()

    _log_event("rag", "ingest_started", level="info", index=index_name, provider=provider)

    loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    # Salva no caminho global + meta (pin do provider).
    path = get_global_db_path(index_name)
    db = FAISS.from_documents(chunks, embeddings)
    _save_index(db, path, provider)
    _log_event("rag", "ingest_done", level="info", index=index_name)

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
            _log_event("rag", "lint_error", level="error", validator=f.validator, path=f.path, message=f.message)
        _log_event("rag", "reindex_aborted", level="error", lint_errors=len(errors))
        sys.exit(1)

    # Fase 2.5: lore vem do Codex (data/codex/); world_lore.txt foi removido na 2.5b (R5).
    _log_event("rag", "reindex_started", level="info")
    from services.codex_loader import ingest_codex
    ingest_codex()
    rules_path = os.path.join("data", "rules.txt")
    if os.path.exists(rules_path):
        ingest_file(rules_path, "rules")
    else:
        _log_event("rag", "rules_missing", level="error")


if __name__ == "__main__":
    # Console Windows é cp1252; força UTF-8 p/ os emojis dos prints não quebrarem
    # (main.py já faz isso no fluxo do jogo; aqui rodamos standalone).
    import sys
    # SPEC-222: o CLI de reindexação mostra os eventos rpg.rag/rpg.codex no terminal.
    from observability.logging_setup import configure_logging
    configure_logging()
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    reindex_global()
