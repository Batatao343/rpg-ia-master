"""SPEC-262 R4: gera ``observability/events.py`` e ``docs/operacao/EVENTOS_DE_LOG.md``.

Varre o codigo (AST) atras de chamadas de log com area/evento literais — diretas
(``log_event("area", "evento", ...)``), por wrappers conhecidos (ver ``WRAPPERS``) e a lista
``MANUAL`` para eventos cujo nome e montado em tempo de execucao. Uso::

    uv run python scripts/gen_event_catalog.py          # reescreve os dois arquivos
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "node_modules", "tests", "evals", "project_index", "web", "dist", "docs",
             "saves", "saves_playtest", "playtest_runs", "__pycache__", ".git"}

# chamada -> ("fixed", area, indice_do_evento) | ("both", indice_area, indice_evento) | ("event", "area.evento")
WRAPPERS: dict[str, tuple] = {
    "log_event": ("both", 0, 1), "_log_event": ("both", 0, 1),
    "_sse_log": ("fixed", "sse", 0), "_db_conflict": ("fixed", "db", 0), "db_log.conflict": ("fixed", "db", 0),
    "reject": ("fixed", "auth", 0), "_announce_once": ("fixed", "llm", 0),
    "wallet_event": ("fixed", "wallet", 0), "log_fallback": ("fallback", 0),
    "_op_rejected": ("event", "operation.rejected"), "_op_replayed": ("event", "operation.replayed"),
    "_release_failed": ("event", "operation.release_failed"), "_log_attempt": ("event", "llm.attempt"),
    "_log_exhausted": ("event", "llm.exhausted"),
    "stripe_webhook": ("event", "payments.stripe_webhook"), "_wh": ("event", "payments.stripe_webhook"),
    "google_verify": ("event", "payments.google_verify"), "checkout_failed": ("event", "payments.checkout_failed"),
}
# nome montado em runtime (nao aparece como literal): registrado a mao.
MANUAL: dict[str, str] = {
    "jev.shadow": "Observacao do Jev no router (modo shadow).",
    "jev.primary": "Decisao do Jev no router (modo primary).",
    "db.statement_timeout": "Query cancelada pelo statement_timeout.",
    "db.lock_timeout": "Query cancelada pelo lock_timeout.",
}
_SKIP_KW = {"level"}
# eventos emitidos por um wrapper: os kwargs do ponto de chamada nao sao os campos logados.
OVERRIDES: dict[str, tuple[str, ...]] = {
    "db.lease_conflict": ("game_ref", "op_kind", "op_ref", "reason"),
    "db.stale_version": ("game_ref", "op_kind", "op_ref", "reason"),
    "db.idempotency_conflict": ("game_ref", "op_kind", "op_ref", "reason"),
    "db.statement_timeout": ("error_type", "query_name"),
    "db.lock_timeout": ("error_type", "query_name"),
    "llm.attempt": ("attempt_index", "cost_basis", "error_type", "fell_back", "http_status", "latency_ms",
                    "model", "node", "outcome", "provider", "structured_failure_code", "tier"),
    "llm.mock_selected": ("profile", "reason"), "llm.fallback_llm_selected": ("profile", "reason"),
    "operation.rejected": ("op_kind", "op_ref", "reason"), "operation.replayed": ("op_kind", "op_ref"),
    "operation.release_failed": ("cause_type", "error_type", "op_ref"),
    "payments.stripe_webhook": ("apply_result", "duration_ms", "error_code", "event_ref", "event_type", "outcome"),
    "payments.google_verify": ("duration_ms", "order_ref", "outcome", "product_id", "upstream_status"),
    "payments.checkout_failed": ("error_code", "error_type", "stage"),
    "wallet.settle_failed": ("error_type", "op_ref", "stage"),
    "wallet.recovery_item_failed": ("error_type", "op_ref", "stage"),
    "wallet.reservation_uncertain": ("error_type", "op_ref", "stage"),
    # SPEC-261/259: campos de build/app vem de _client_build_fields (**kwargs).
    "http.request": ("app_version", "build_skew", "client", "client_build", "duration_ms", "error_code", "method",
                     "owner_ref", "request_id", "route", "status"),
    # SPEC-244: campos validados pelo modelo ClientErrorReport (**kwargs).
    "client.error": ("beacon_request_id", "build", "client", "code", "error_name", "kind", "request_id", "route",
                     "stack", "ts"),
}


def _const(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _name(call: ast.Call) -> str:
    func, parts = call.func, []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return ".".join(reversed(parts))


def scan() -> dict[str, set[str]]:
    """``{"area.evento": {campos...}}`` achados no codigo de producao."""
    found: dict[str, set[str]] = {}
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if set(rel.parts[:-1]) & SKIP_DIRS or rel.parts[0] in SKIP_DIRS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # So dicts passados a safe_json(...) sao linhas de log; dicts de eventos de jogo
        # (ex.: ``events.append({"event": ...})``) nao entram no catalogo (revisao Sol).
        log_dicts = {id(arg) for call in ast.walk(tree) if isinstance(call, ast.Call)
                     and _name(call).split(".")[-1] == "safe_json"
                     for arg in call.args if isinstance(arg, ast.Dict)}
        log_dicts |= {id(kw.value) for call in ast.walk(tree) if isinstance(call, ast.Call)
                      for kw in call.keywords if kw.arg == "extra" and isinstance(kw.value, ast.Dict)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict) and id(node) not in log_dicts:
                continue
            if isinstance(node, ast.Dict):        # linhas legadas: safe_json({"event": "turn", ...})
                keys = [_const(k) for k in node.keys]
                if "event" in keys and _const(node.values[keys.index("event")])                         and ("evt" in keys or "outcome" in keys or "task" in keys or "stage" in keys
                             or "flow" in keys or "owner_ref" in keys or "attempted_gold" in keys
                             or "action_ref" in keys):
                    legacy = _const(node.values[keys.index("event")])
                    found.setdefault(legacy, set()).update(
                        k for k in keys if k and k not in {"event", "evt"})
                continue
            if not isinstance(node, ast.Call):
                continue
            name = _name(node)
            spec = WRAPPERS.get(name) or WRAPPERS.get(name.split(".")[-1])
            if spec is None or (name.endswith("conflict") and name not in {"_db_conflict", "db_log.conflict"}):
                continue
            key = None
            if spec[0] == "both" and len(node.args) > max(spec[1], spec[2]):
                area, evt = _const(node.args[spec[1]]), _const(node.args[spec[2]])
                key = f"{area}.{evt}" if area and evt else None
            elif spec[0] == "fixed" and len(node.args) > spec[2]:
                evt = _const(node.args[spec[2]])
                key = f"{spec[1]}.{evt}" if evt else None
            elif spec[0] == "fallback" and node.args:
                area = _const(node.args[0])
                key = f"{area}.fallback" if area else None
            elif spec[0] == "event":
                key = spec[1]
            if key:
                found.setdefault(key, set()).update(
                    kw.arg for kw in node.keywords if kw.arg and kw.arg not in _SKIP_KW)
    return found


def build() -> dict[str, tuple[str, ...]]:
    events = {key: tuple(sorted(fields)) for key, fields in scan().items()}
    for key in MANUAL:
        events.setdefault(key, ())
    for key, fields in OVERRIDES.items():
        events[key] = fields
    for key in list(events):
        if key.startswith("auth.") and key != "auth.rate_limited" and "reason" not in events[key]:
            events[key] = tuple(sorted({*events[key], "reason"}))
    return dict(sorted(events.items()))


def render_module(events: dict[str, tuple[str, ...]]) -> str:
    lines = ['"""Catalogo de eventos de log (SPEC-262 R4). GERADO por scripts/gen_event_catalog.py — nao edite.',
             '', 'Chave ``area.evento`` -> campos conhecidos (alem dos de correlacao). Um evento novo no codigo',
             'sem entrada aqui faz ``tests/test_log_event_registry.py`` falhar.', '"""', '',
             'EVENTS: dict[str, tuple[str, ...]] = {']
    for key, fields in events.items():
        lines.append(f"    {key!r}: {fields!r},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_doc(events: dict[str, tuple[str, ...]]) -> str:
    out = ["# Eventos de log", "",
           "> Gerado por `scripts/gen_event_catalog.py` a partir do codigo. Nao edite: rode "
           "`uv run python scripts/gen_event_catalog.py`.", "",
           "Toda linha e JSON em stdout com `event` (`area.evento`), `level`, `logger`, `ts`, "
           "`instance_ref` e, quando houver, `request_id`/`game_ref`/`action_ref`/`owner_ref`. "
           "Campos abaixo sao os conhecidos por evento (podem variar por chamada).", "",
           "| evento | campos |", "|---|---|"]
    for key, fields in events.items():
        extra = MANUAL.get(key)
        cell = ", ".join(f"`{f}`" for f in fields) or (extra or "—")
        out.append(f"| `{key}` | {cell} |")
    return "\n".join(out) + "\n"


def main() -> None:
    events = build()
    (ROOT / "observability" / "events.py").write_text(render_module(events), encoding="utf-8", newline="\n")
    (ROOT / "docs" / "operacao" / "EVENTOS_DE_LOG.md").write_text(render_doc(events), encoding="utf-8", newline="\n")
    print(f"{len(events)} eventos")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
