"""SPEC-224 (offline): credenciais separadas, pool de request x sistema e inventario de uso do pool."""

from __future__ import annotations

import ast
import re
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

from infrastructure.runtime import RuntimeConfig
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


def _pool(request_rls=True, with_admin=True):
    from infrastructure.postgres import PostgresPool

    log: list = []
    pool = PostgresPool.__new__(PostgresPool)
    pool._transaction_pooler = False
    pool._request_rls = request_rls
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
    with pool.connection() as c:  # sem principal: nada escopado (health/boot)
        c.execute("select 1")
    assert not any("ROLE" in sql.upper() for _, sql in log)
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
]
# Modulos de request: usam `.connection()` (escopado ao owner); deve ser deliberado.
REQUEST_MODULES = [
    "infrastructure/postgres.py",
    "infrastructure/postgres_turns.py",
    "infrastructure/postgres_catalog.py",
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
    source = (ROOT / "api.py").read_text(encoding="utf-8")
    assert source.count("admin_connection(") >= 3
    for _, expr in _direct_connection_calls(ROOT / "api.py"):
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
