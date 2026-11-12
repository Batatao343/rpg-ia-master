"""SPEC-224 (offline): credenciais separadas, pool de request x sistema e inventario de uso do pool."""

from __future__ import annotations

import ast
import re
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

from infrastructure.runtime import RuntimeConfig
from tests.api_sources import API_FILES, api_source_text
from tests.test_hosted_supabase_contract import hosted_env

ROOT = Path(__file__).resolve().parents[1]

REQUEST = (
    "postgresql://rpg_runtime.projectref:RT_SENTINEL@aws-0-us-east-1.pooler.supabase.com:6543/"
    "postgres?sslmode=require"
)
ADMIN = (
    "postgresql://rpg_admin.projectref:AD_SENTINEL@aws-0-us-east-1.pooler.supabase.com:6543/"
    "postgres?sslmode=require"
)


def _env(**over):
    env = {**hosted_env(), "DATABASE_URL": REQUEST, "RPG_ADMIN_DATABASE_URL": ADMIN}
    env.update(over)
    return {k: v for k, v in env.items() if v is not None}


def test_hosted_accepts_distinct_runtime_and_admin_credentials():
    config = RuntimeConfig.from_env(_env())
    assert config.request_rls is True and config.admin_database_url == ADMIN
    assert "SENTINEL" not in repr(config)


@pytest.mark.parametrize(
    "over, fragment",
    [
        ({"RPG_ADMIN_DATABASE_URL": None}, "RPG_ADMIN_DATABASE_URL"),
        ({"RPG_ADMIN_DATABASE_URL": REQUEST}, "diferente"),
        ({"DATABASE_URL": REQUEST.replace("rpg_runtime", "postgres")}, "postgres"),
        (
            {"RPG_ADMIN_DATABASE_URL": ADMIN.replace("projectref", "otherref")},
            "projetos diferentes",
        ),
        # Astra: credenciais trocadas / roles de plataforma tambem falham no boot
        ({"DATABASE_URL": ADMIN, "RPG_ADMIN_DATABASE_URL": REQUEST}, "role de sistema"),
        (
            {"DATABASE_URL": REQUEST.replace("rpg_runtime", "supabase_storage_admin")},
            "role de sistema",
        ),
        ({"DATABASE_URL": REQUEST.replace("rpg_runtime", "authenticator")}, "role de sistema"),
        (
            {
                "RPG_ADMIN_DATABASE_URL": ADMIN.replace("rpg_admin", "rpg_runtime").replace(
                    "AD_", "X_"
                )
            },
            "diferente",
        ),
    ],
)
def test_runtime_requires_distinct_dsns_in_hosted(over, fragment):
    with pytest.raises(ValueError, match=fragment):
        RuntimeConfig.from_env(_env(**over))


def test_request_rls_off_is_the_documented_rollback_to_the_single_dsn():
    legacy_style = {
        **hosted_env(),
        "RPG_REQUEST_RLS": "off",
    }  # DATABASE_URL = postgres.<ref>, sem admin
    legacy_style.pop("RPG_ADMIN_DATABASE_URL")
    legacy_style["DATABASE_URL"] = REQUEST.replace("rpg_runtime", "postgres")
    config = RuntimeConfig.from_env(legacy_style)
    assert config.request_rls is False and config.admin_database_url == ""


def test_local_keeps_a_single_dsn_by_default_with_role_switch_on():
    local = RuntimeConfig.from_env(
        {"RPG_RUNTIME_PROFILE": "local", "DATABASE_URL": "postgresql://localhost/postgres"}
    )
    assert local.request_rls is True and local.admin_database_url == ""


class _FakePooled:
    def __init__(self, label, log):
        self.label, self.log = label, log

    @contextmanager
    def connection(self):
        class Conn:
            def execute(inner, sql, params=None):
                self.log.append((self.label, " ".join(str(sql).split())))
                return inner

        yield Conn()


def _pool(request_rls=True, with_admin=True, strict="off"):
    from infrastructure.postgres import PostgresPool

    log: list = []
    pool = PostgresPool.__new__(PostgresPool)
    pool._transaction_pooler = False
    pool._request_rls = request_rls
    pool._strict_principal = strict
    pool._pool = _FakePooled("user", log)
    if with_admin:
        admin = PostgresPool.__new__(PostgresPool)
        admin._transaction_pooler = False
        admin._request_rls = False
        admin._pool = _FakePooled("admin", log)
        admin.admin_pool = None
        pool.admin_pool = admin
    else:
        pool.admin_pool = None
    return pool, log


def _principal():
    from infrastructure.contracts import Principal

    owner = uuid4()
    return Principal(owner, "t", str(owner))


def test_worker_uses_admin_pool_and_never_switches_role():
    from infrastructure.request_context import principal_scope

    pool, log = _pool()
    with principal_scope(_principal()), pool.admin_connection() as c:
        c.execute("select 1")
    with pool.connection(as_admin=True) as c:
        c.execute("select 2")
    assert [label for label, _ in log] == ["admin", "admin"]
    assert not any("ROLE" in sql.upper() for _, sql in log)


def test_request_connection_sets_role_and_owner_only_with_principal():
    from infrastructure.request_context import principal_scope

    pool, log = _pool()
    with pool.connection() as c:  # SPEC-410: modo `off` (padrao) = contrato atual, sem principal
        c.execute("select 1")
    assert not any("ROLE" in sql.upper() for _, sql in log)
    assert [label for label, _ in log] == ["user"]
    log.clear()
    with principal_scope(_principal()), pool.connection() as c:
        c.execute("select 2")
    assert [label for label, _ in log] == ["user"] * 2  # role+claims num unico round trip
    assert "set_config('request.jwt.claim.sub'" in log[0][1]
    assert "set_config('role'" in log[0][1] and log[1][1] == "select 2"


def test_rls_off_never_switches_role():
    from infrastructure.request_context import principal_scope

    pool, log = _pool(request_rls=False, with_admin=False)
    with principal_scope(_principal()), pool.connection() as c:
        c.execute("select 1")
    assert [sql for _, sql in log] == ["select 1"]


def test_admin_connection_without_admin_pool_uses_same_pool():
    pool, log = _pool(with_admin=False)
    with pool.admin_connection() as c:
        c.execute("select 1")
    assert [label for label, _ in log] == ["user"]


# --- inventario de uso do pool (R5): quem e request e quem e sistema -------------------------
# Modulos cujo acesso e SEMPRE de sistema: nenhuma chamada `.connection()` direta e permitida.
SYSTEM_MODULES = [
    "infrastructure/account_lifecycle.py",
    "infrastructure/account_read_model.py",
    "infrastructure/audit_source.py",
    "infrastructure/finops_reader.py",
    "infrastructure/google_play_payments.py",
    "infrastructure/kill_switch_store.py",
    "infrastructure/reconciliation.py",
    "infrastructure/speech_finance.py",
    "infrastructure/stripe_payments.py",
    "infrastructure/supabase_blob.py",
    "infrastructure/supabase_identity.py",
    "infrastructure/usage_events.py",
    "infrastructure/wallet.py",
    "services/dynamic_art.py",
    "services/image_quotes.py",
    "services/operation_recovery.py",
    "services/retention.py",
    "services/wallet_recovery.py",
    "workers/blob_purge_jobs.py",
    "workers/embedding_jobs.py",
    "workers/projection_jobs.py",
    # SPEC-410 R3: scripts de operacao migrados de `pool.connection()` para `admin_connection`
    "scripts/admin_wallet_adjust.py",
    "scripts/admin_wallet_reconcile.py",
    "scripts/recover_account_deletions.py",
    "scripts/seed_google_play_skus.py",
]
# Modulos de request: usam `.connection()` (escopado ao owner); deve ser deliberado.
REQUEST_MODULES = [
    "infrastructure/postgres.py",
    "infrastructure/postgres_turns.py",
    "infrastructure/postgres_catalog.py",
    "infrastructure/postgres_shared_pool.py",
    "infrastructure/pgvector_memory.py",
    "infrastructure/postgres_jobs.py",
    "services/chronicle_repository.py",
    "services/game_transfer.py",
]


def _direct_connection_calls(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "connection"
            and not node.args
        ):
            out.append((node.lineno, ast.unparse(node.func)))
    return out


@pytest.mark.parametrize("relative", SYSTEM_MODULES)
def test_system_modules_never_open_a_request_scoped_connection(relative):
    assert _direct_connection_calls(ROOT / relative) == [], relative


def test_every_module_that_opens_connections_is_classified():
    classified = {*SYSTEM_MODULES, *REQUEST_MODULES, "infrastructure/db_roles.py", "api.py"}
    unclassified = []
    for folder in ("infrastructure", "services", "workers"):
        for path in (ROOT / folder).glob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if rel not in classified and _direct_connection_calls(path):
                unclassified.append(rel)
    assert unclassified == [], f"classifique como request ou sistema: {unclassified}"


def test_request_side_job_queue_only_enqueues_with_the_request_role():
    source = (ROOT / "infrastructure/postgres_jobs.py").read_text(encoding="utf-8")
    head, _, tail = source.partition("    def lease(self")
    assert len(re.findall(r"self\.pool\.connection\(\)", head)) == 1  # enqueue
    assert "self.pool.connection()" not in tail


def test_rate_limiter_is_system_only():
    source = (ROOT / "infrastructure/postgres_turns.py").read_text(encoding="utf-8")
    _, _, limiter = source.partition("class PostgresRateLimiter:")
    assert ".connection()" not in limiter


def test_api_request_queries_only_use_granted_tables():
    """api.py: as conexoes de request restantes tocam so tabelas que `rpg_api` possui."""
    source = api_source_text()
    assert source.count("admin_connection(") >= 3
    for path in API_FILES:
        for _, expr in _direct_connection_calls(path):
            assert expr.endswith("resources[0].connection")


def test_lease_heartbeat_thread_inherits_the_request_principal():
    """Astra: o renovador de lease roda em thread propria; sem copiar o contexto ele cairia no login
    de sessao (sem escopo de owner). Com o principal herdado, o UPDATE do lease fica sob `rpg_api`."""
    import threading
    from uuid import uuid4

    from infrastructure.contracts import Principal
    from infrastructure.request_context import active_principal, principal_scope
    from services.lease_heartbeat import keep_lease_alive

    seen: list = []
    in_thread = threading.Event()

    def renew():
        if threading.current_thread().name == "lease-heartbeat":
            seen.append(active_principal())
            in_thread.set()

    principal = Principal(user_id=uuid4(), issuer="test", subject="s")
    with principal_scope(principal):
        with keep_lease_alive(renew, interval_seconds=0.01):
            assert in_thread.wait(2)
    assert seen and seen[0] == principal


# --- SPEC-410: falha fechada sem principal (off | shadow | on) e marca de sistema -----------------


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, str, dict]] = []

    def record(area, event, **fields):
        seen.append((area, event, fields))

    monkeypatch.setattr("observability.telemetry.log_event", record)
    return seen


def _strict_events(events):
    return [e for e in events if e[:2] == ("pool", "checkout_without_principal")]


def test_checkout_sem_principal_modo_off_inalterado(events):
    pool, log = _pool(strict="off")
    with pool.connection() as c:
        c.execute("select 1")
    assert [label for label, _ in log] == ["user"]
    assert _strict_events(events) == []


def test_checkout_sem_principal_shadow_loga_e_nao_levanta(events):
    from observability.metrics import metrics

    key = "rpg_pool_checkout_without_principal_total{'mode': 'shadow'}"
    before = metrics.snapshot().get(key, 0)
    pool, log = _pool(strict="shadow")
    with pool.connection() as c:
        c.execute("select 1")
    assert [label for label, _ in log] == ["user"]  # abre como hoje
    (event,) = _strict_events(events)
    assert event[2]["mode"] == "shadow"
    assert event[2]["caller"].endswith("test_checkout_sem_principal_shadow_loga_e_nao_levanta")
    assert metrics.snapshot().get(key, 0) == before + 1


def test_checkout_sem_principal_on_levanta_rls_scope_error(events):
    from infrastructure.contracts import InfrastructureError, RlsScopeError, Unauthorized

    pool, log = _pool(strict="on")
    with pytest.raises(RlsScopeError):
        with pool.connection():
            pass
    assert log == []  # falha antes de tocar o pool
    assert _strict_events(events)[0][2]["mode"] == "on"
    assert issubclass(RlsScopeError, RuntimeError)
    assert not issubclass(RlsScopeError, (Unauthorized, InfrastructureError))


@pytest.mark.parametrize("strict", ["off", "shadow", "on"])
def test_marca_de_sistema_usa_pool_admin_sem_role(strict, events):
    from infrastructure.request_context import system_caller

    pool, log = _pool(strict=strict)
    with system_caller("cron:teste"), pool.connection() as c:
        c.execute("select 1")
    assert [label for label, _ in log] == ["admin"]
    assert not any("ROLE" in sql.upper() for _, sql in log)
    assert _strict_events(events) == []


def test_marca_de_sistema_sem_pool_admin_usa_o_mesmo_pool_sem_role():
    from infrastructure.request_context import system_caller

    pool, log = _pool(with_admin=False, strict="on")
    with system_caller("worker"), pool.connection() as c:
        c.execute("select 1")
    assert [label for label, _ in log] == ["user"]
    assert not any("ROLE" in sql.upper() for _, sql in log)


def test_principal_vence_marca_de_sistema():
    from infrastructure.request_context import principal_scope, system_caller

    pool, log = _pool(strict="on")
    with system_caller("cron:jobs"), principal_scope(_principal()), pool.connection() as c:
        c.execute("select 1")
    assert [label for label, _ in log] == ["user"] * 2  # role+owner e a query, pool de request
    assert "set_config('role'" in log[0][1]


def test_marca_de_sistema_restaura_ao_sair_e_exige_motivo():
    from infrastructure.request_context import active_system_caller, system_caller

    assert active_system_caller() is None
    with system_caller("a"):
        with system_caller("b"):
            assert active_system_caller() == "b"
        assert active_system_caller() == "a"
    assert active_system_caller() is None
    with pytest.raises(ValueError):
        with system_caller(" "):
            pass


def test_modo_estrito_so_vale_em_hosted_com_request_rls(monkeypatch):
    from infrastructure.pool_scope import strict_mode

    on = {"RPG_RLS_STRICT_PRINCIPAL": "on"}
    assert strict_mode("hosted-supabase", True, on) == "on"
    assert strict_mode("hosted", True, {"RPG_RLS_STRICT_PRINCIPAL": " Shadow "}) == "shadow"
    assert strict_mode("hosted-supabase", False, on) == "off"
    assert strict_mode("local", True, on) == "off"
    assert strict_mode("legacy", True, on) == "off"
    assert strict_mode("hosted-supabase", True, {}) == "off"  # padrao
    assert strict_mode("hosted-supabase", True, {"RPG_RLS_STRICT_PRINCIPAL": "talvez"}) == "off"
    monkeypatch.setenv("RPG_RLS_STRICT_PRINCIPAL", "shadow")  # sem env explicito: os.environ
    assert strict_mode("hosted-supabase", True) == "shadow"
    monkeypatch.delenv("RPG_RLS_STRICT_PRINCIPAL")
    assert strict_mode("hosted-supabase", True) == "off"


def test_request_rls_off_nunca_levanta(events):
    pool, log = _pool(request_rls=False, with_admin=False, strict="on")
    with pool.connection() as c:
        c.execute("select 1")
    assert [label for label, _ in log] == ["user"]
    assert _strict_events(events) == []


def test_rls_scope_error_vira_500_generico_sem_vazar_mensagem():
    from fastapi.testclient import TestClient

    import api
    from infrastructure.contracts import RlsScopeError

    @api.app.get("/__spec410_rls_scope_probe")
    def _probe():
        raise RlsScopeError("SEGREDO-INTERNO checkout sem principal")

    try:
        out = TestClient(api.app, raise_server_exceptions=False).get("/__spec410_rls_scope_probe")
    finally:
        api.app.router.routes[:] = [
            r
            for r in api.app.router.routes
            if getattr(r, "path", "") != "/__spec410_rls_scope_probe"
        ]
    assert out.status_code == 500
    assert "SEGREDO-INTERNO" not in out.text
    assert out.json().get("code") == "internal_error"


def test_principal_e_marca_atravessam_threads_do_hosted_em_modo_on():
    """`to_thread`/`run_in_threadpool` copiam o contexto: em `on` nao levantam.

    Cobre o caminho financeiro/STT da SPEC-412 (finance.begin/admit/finish, rate_limiter.consume)."""
    import asyncio
    import threading

    from starlette.concurrency import run_in_threadpool

    from infrastructure.contracts import RlsScopeError
    from infrastructure.request_context import principal_scope, system_caller

    pool, log = _pool(strict="on")

    def touch():
        with pool.connection() as c:
            c.execute("select 1")

    async def go():
        await asyncio.to_thread(touch)
        await run_in_threadpool(touch)

    with principal_scope(_principal()):
        asyncio.run(go())
    assert [label for label, _ in log] == ["user"] * 4  # (role+owner, query) x 2 threads
    log.clear()
    with system_caller("cron:x"):
        asyncio.run(go())
    assert [label for label, _ in log] == ["admin"] * 2
    # Thread crua (threading.Thread) NAO herda: em `on` falha alto em vez de abrir privilegiada.
    errors: list[BaseException] = []

    def raw():
        try:
            touch()
        except RlsScopeError as exc:
            errors.append(exc)

    with principal_scope(_principal()):
        t = threading.Thread(target=raw)
        t.start()
        t.join()
    assert len(errors) == 1


# --- SPEC-410 R1: inventario versionado de TODO chamador de `.connection()` (arvore de produto) --
# Classe: (a) sempre com principal (request); (c) ambiguo: roda sob request E sob worker/cron,
# coberto pela marca `system_caller` no ponto de entrada; (d) pool proprio sem `request_rls`
# (script/teste: o modo estrito nunca vale). Chamadores (b) puros usam `admin_connection` e por isso
# nao aparecem aqui. Detalhe por simbolo: `docs/spec410/inventario.md`.
CONNECTION_CALLERS: dict[str, str] = {
    "api_core.py": "a",
    "infrastructure/postgres.py": "a",
    "infrastructure/postgres_turns.py": "a",
    "routes/art.py": "a",
    "routes/billing.py": "a",
    "services/game_transfer.py": "a",
    "services/chronicle_repository.py": "a",  # enqueue_due/overlay; `complete` e sistema (admin)
    "infrastructure/pgvector_memory.py": "c",
    "infrastructure/postgres_catalog.py": "c",
    "infrastructure/postgres_jobs.py": "c",
    "infrastructure/postgres_shared_pool.py": "c",
    "scripts/chaos_test.py": "d",
    "scripts/load_test.py": "d",
    "scripts/staging/synthetic_data.py": "d",
    "scripts/verify_restore.py": "d",
}
# Unicos lugares que declaram `system_caller` (ponto de entrada, nunca metodo de store).
SYSTEM_CALLER_ENTRYPOINTS = {
    "gamedata.py",  # boot: leitura do catalogo global no import
    "scripts/pool_promote.py",
    "services/cron_internal.py",  # _run: todo /internal/cron/*
    "workers/drain.py",  # drain_jobs
    "workers/run_worker.py",  # main
}
_SKIP_DIRS = {"tests", "docs", "web", "evals", "playtest", "node_modules", "__pycache__"}


def _product_files():
    import os

    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.endswith(".py"):
                yield Path(folder) / name


def _calls(path: Path, attr: str) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == attr) or (
            isinstance(func, ast.Name) and func.id == attr
        ):
            out.append(node.lineno)
    return out


def test_todo_chamador_de_connection_esta_classificado():
    found = {
        p.relative_to(ROOT).as_posix()
        for p in _product_files()
        if p.relative_to(ROOT).as_posix() != "infrastructure/db_roles.py"
        and _calls(p, "connection")
    }
    assert found - set(CONNECTION_CALLERS) == set(), "chamador novo sem classe (a/c/d)"
    assert set(CONNECTION_CALLERS) - found == set(), "entrada obsoleta: remova da lista"
    assert set(CONNECTION_CALLERS.values()) <= {"a", "c", "d"}


def test_marca_de_sistema_so_nos_pontos_de_entrada():
    users = {
        p.relative_to(ROOT).as_posix()
        for p in _product_files()
        if _calls(p, "system_caller")
        and p.relative_to(ROOT).as_posix() != "infrastructure/request_context.py"
    }
    assert users == SYSTEM_CALLER_ENTRYPOINTS


def test_chronicle_complete_usa_conexao_de_sistema():
    tree = ast.parse((ROOT / "services/chronicle_repository.py").read_text(encoding="utf-8"))
    method = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "complete"
    )
    attrs = {
        n.func.attr
        for n in ast.walk(method)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    names = {
        n.func.id
        for n in ast.walk(method)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "connection" not in attrs and "admin_connection" in names


class _Rows:
    def __init__(self, row=None):
        self.row = row

    def fetchall(self):
        return []

    def fetchone(self):
        return self.row


@contextmanager
def _tx():
    yield


def _admin_pool(strict, log, row=None):
    pool, _ = _pool(strict=strict)

    class Conn:
        def execute(self, sql, params=None):
            log.append(("admin", " ".join(str(sql).split())))
            return _Rows(row)

        def transaction(self):
            return _tx()

    @contextmanager
    def admin_connection():
        yield Conn()

    pool.admin_connection = admin_connection
    return pool


def test_chronicle_complete_funciona_sem_principal_em_modo_estrito(events):
    """O worker nao tem principal: em `on`, `complete` abre o pool admin e nao levanta."""
    from services.chronicle import ensure_chronicle_ids
    from services.chronicle_compression import chapter_source_hash
    from services.chronicle_repository import ChronicleRepository

    game_id = str(uuid4())
    chapter = ensure_chronicle_ids([{"chapter_id": "c1"}], game_id=game_id)[0]
    log: list = []
    row = {"state": {"continuity": {"timeline_epoch": 9}}, "version": 1}
    repo = ChronicleRepository(_admin_pool("on", log, row), memory=None)
    payload = {
        "owner_id": str(uuid4()),
        "game_id": game_id,
        "timeline_epoch": 0,
        "source_hash": chapter_source_hash(chapter),
        "chapter": chapter,
    }
    with pytest.raises(ValueError, match="superseded"):  # chegou na consulta, via conexao admin
        repo.complete(payload, {"status": "ready"})
    assert log and all(label == "admin" for label, _ in log)
    assert _strict_events(events) == []


def test_claim_pending_dos_scripts_usa_pool_admin_em_modo_estrito(events):
    from scripts import recover_account_deletions

    log: list = []
    pool = _admin_pool("on", log)
    assert recover_account_deletions.claim_pending(pool, 1) == []
    assert log and all(label == "admin" for label, _ in log)
    assert _strict_events(events) == []


def test_cron_run_executa_sob_marca_de_sistema():
    from infrastructure.request_context import active_system_caller
    from services import cron_internal

    seen: list = []

    def task():
        seen.append(active_system_caller())
        return {"failed": 0}

    cron_internal._run("jobs", task)
    assert seen == ["cron:jobs"] and active_system_caller() is None


def test_drain_jobs_sob_marca_de_sistema():
    from infrastructure.request_context import active_system_caller
    from workers.drain import drain_jobs

    seen: list = []

    class Worker:
        stats: dict = {}

        def run_once(self, *, limit):
            seen.append(active_system_caller())
            return 0

    drain_jobs(100.0, 5, "t", worker=Worker())
    assert seen == ["drain"] and active_system_caller() is None


def test_run_worker_main_executa_sob_marca_de_sistema(monkeypatch):
    from infrastructure.request_context import active_system_caller
    from workers import run_worker

    seen: list = []

    class Worker:
        def __init__(self, *a, **k):
            import threading

            self.stop_event = threading.Event()

        def request_stop(self):
            self.stop_event.set()

        def run_once(self, *, limit):
            seen.append(active_system_caller())
            return 0

    class Rt:
        job_queue = object()

    monkeypatch.setattr(run_worker, "JobWorker", Worker)
    monkeypatch.setattr(run_worker, "get_runtime", lambda: Rt())
    monkeypatch.setattr(run_worker, "build_handlers", dict)
    monkeypatch.setattr("sys.argv", ["run_worker", "--once"])
    assert run_worker.main() == 0
    assert seen == ["worker"] and active_system_caller() is None


def test_marca_de_sistema_atravessa_a_thread_do_lease_heartbeat():
    import threading

    from infrastructure.request_context import active_system_caller, system_caller
    from services.lease_heartbeat import keep_lease_alive

    seen: list = []
    in_thread = threading.Event()

    def renew():
        if threading.current_thread().name == "lease-heartbeat":
            seen.append(active_system_caller())
            in_thread.set()

    with system_caller("worker"):
        with keep_lease_alive(renew, interval_seconds=0.01):
            assert in_thread.wait(2)
    assert seen and seen[0] == "worker"
