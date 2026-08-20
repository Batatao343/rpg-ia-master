"""Preview-first import/export of legacy JSON saves and portable game bundles."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from infrastructure.contracts import Conflict, Principal
from infrastructure.postgres import PostgresGameStore, PostgresPool
from services.game_serialization import (
    deserialize_game_state,
    document_sha256,
    serialize_game_state,
)


@dataclass(frozen=True)
class SavePreview:
    path: str
    game_id: str | None
    status: str
    sha256: str | None = None
    archived: bool = False
    error: str | None = None


def _preview(path: Path) -> tuple[SavePreview, dict[str, Any] | None]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        state = deserialize_game_state(raw)
        document = serialize_game_state(state)
        game_id = str(UUID(str(document["game_id"])))
        return SavePreview(
            str(path), game_id, "valid", document_sha256(document),
            bool(document.get("archived")), None,
        ), state
    except Exception as exc:
        return SavePreview(
            str(path), None, "corrupt", None, False,
            f"{type(exc).__name__}: {exc}",
        ), None


def scan_saves(source: Path) -> list[SavePreview]:
    """Scan without writes. Sources are deliberately never renamed or removed."""
    paths = [source] if source.is_file() else sorted(source.glob("*.json"))
    return [_preview(path)[0] for path in paths]


def import_saves(
    pool: PostgresPool,
    principal: Principal,
    source: Path,
    *,
    dry_run: bool = True,
    journal_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Insert-only import; identical reruns skip and divergent collisions fail."""
    store = PostgresGameStore(pool)
    completed: set[str] = set()
    if journal_path and journal_path.exists():
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") in {"imported", "already_present"}:
                completed.add(str(row.get("game_id")))

    paths = [source] if source.is_file() else sorted(source.glob("*.json"))
    report: list[dict[str, Any]] = []
    for path in paths:
        preview, state = _preview(path)
        row = asdict(preview)
        if state is None:
            report.append(row)
            continue
        game_id = UUID(str(preview.game_id))
        if dry_run:
            row["status"] = "would_import"
        else:
            existing = store.get(principal, game_id)
            if existing is None:
                store.create(principal, state)
                row["status"] = "imported"
            else:
                existing_hash = document_sha256(serialize_game_state(existing.state))
                if existing_hash != preview.sha256:
                    raise Conflict(f"colisão divergente no game_id {game_id}")
                row["status"] = (
                    "journal_skip" if str(game_id) in completed else "already_present"
                )
        report.append(row)
        if journal_path and not dry_run and row["status"] in {"imported", "already_present"}:
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            with journal_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return report


def export_game(pool: PostgresPool, principal: Principal, game_id: UUID) -> dict[str, Any]:
    """Return a provider-neutral, owner-scoped bundle with independent hashes."""
    store = PostgresGameStore(pool)
    stored = store.get(principal, game_id)
    if stored is None:
        raise KeyError("campanha não encontrada")
    state = serialize_game_state(stored.state)
    checkpoint = store.get_checkpoint(principal, game_id)
    checkpoint_doc = serialize_game_state(checkpoint) if checkpoint else None
    with pool.connection() as connection:
        events = [dict(row) for row in connection.execute(
            """select event_id,turn,event_type,payload,source,event_sha256
            from app.game_events where game_id=%s and owner_id=%s
            order by turn,event_id""",
            (game_id, principal.user_id),
        ).fetchall()]
        catalog = [dict(row) for row in connection.execute(
            """select namespace,item_key,scope,document,document_sha256,version,provenance
            from app.runtime_catalog where owner_id=%s and game_id=%s
            order by namespace,item_key""",
            (principal.user_id, game_id),
        ).fetchall()]
    return {
        "format": "valoria-game-export-v1",
        "game_id": str(game_id),
        "schema_version": stored.schema_version,
        "source_version": stored.version,
        "state": state,
        "state_sha256": document_sha256(state),
        "checkpoint": checkpoint_doc,
        "checkpoint_sha256": document_sha256(checkpoint_doc) if checkpoint_doc else None,
        "events": events,
        "catalog": catalog,
    }


def verify_export(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bundle.get("format") != "valoria-game-export-v1":
        errors.append("format")
    state = bundle.get("state")
    if not isinstance(state, dict) or document_sha256(state) != bundle.get("state_sha256"):
        errors.append("state_sha256")
    checkpoint = bundle.get("checkpoint")
    if checkpoint is not None and (
        not isinstance(checkpoint, dict)
        or document_sha256(checkpoint) != bundle.get("checkpoint_sha256")
    ):
        errors.append("checkpoint_sha256")
    if isinstance(state, dict) and str(state.get("game_id")) != str(bundle.get("game_id")):
        errors.append("game_id")
    return errors


def write_report(rows: Iterable[dict[str, Any]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = list(rows)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
