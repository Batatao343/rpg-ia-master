"""Normalize the historical specification filenames without changing their meaning.

The migration deliberately treats Git as the source of provenance.  It may be run
repeatedly: ``--dry-run`` only reports the plan, ``--apply`` performs the
renames/references/index/report update, and ``--check`` proves that a checkout is
already in that canonical form.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import yaml


STATUS_RE = re.compile(r"^\s*>\s*\*\*Status:\*\*\s*`([^`]+)`", re.IGNORECASE | re.MULTILINE)
SPEC_ID_RE = re.compile(r"^SPEC-(\d{3})-(.+)\.md$", re.IGNORECASE)
SPEC_REFERENCE_RE = re.compile(r"\bSPEC-(\d{3})\b")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
RECORD_SEPARATOR = "\x1e"
FIELD_SEPARATOR = "\x1f"
SKIPPED_DIRECTORIES = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "faiss_lore_index",
    "faiss_rules_index",
    "data",
    "lore_nova",
    "saves",
    "saves_playtest",
    "playtest_runs",
}
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yaml", ".yml", ".json", ".txt", ".html", ".ts", ".tsx", ".js"}
# Observed historical Markdown-link alias.  This repairs only the link target;
# it neither changes prose nor asserts an additional dependency.
REFERENCE_ALIASES = {"npcs-3-camadas.md": "npcs-3-camadas-traits"}
# One pre-existing relative link under ``specs/`` omits the parent segment.
# Keeping this contextual target repair here makes the link gate deterministic.


class MigrationError(RuntimeError):
    """The repository cannot be normalized without making up provenance."""


@dataclasses.dataclass(frozen=True)
class HistoryRecord:
    sha: str
    date: str
    path: str
    ambiguous_reason: str | None = None


@dataclasses.dataclass
class SpecRecord:
    old_path: str
    new_path: str
    slug: str
    spec_id: int
    status: str
    created_commit: str | None
    created_at: str | None
    completed_commit: str | None
    completed_at: str | None
    completed_order: int | None = None
    tie_breaker: str | None = None
    lineage_ambiguous: bool = False
    lineage_note: str | None = None
    depends_on: list[str] = dataclasses.field(default_factory=list)
    depends_on_raw: list[str] = dataclasses.field(default_factory=list)
    depends_on_unresolved: list[str] = dataclasses.field(default_factory=list)


DEPENDS_RE = re.compile(r"^\s*>\s*\*\*Depende de:\*\*\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def _run_git(repo: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and completed.returncode:
        raise MigrationError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _status(text: str) -> str:
    match = STATUS_RE.search(text)
    if not match:
        raise MigrationError("spec without a canonical Status header")
    return match.group(1).strip()


def _read_text(path: Path) -> str:
    """Decode UTF-8 without normalizing CRLF or any other bytes."""

    return path.read_bytes().decode("utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _timestamp(value: str) -> float:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _topological_order(repo: Path, revision: str = "HEAD") -> dict[str, int]:
    commits = _run_git(repo, "rev-list", "--topo-order", "--reverse", revision).splitlines()
    if not commits:
        raise MigrationError("HEAD has no reachable commits")
    return {sha: position for position, sha in enumerate(commits)}


def _history(repo: Path, current_path: str, revision: str = "HEAD") -> list[HistoryRecord]:
    """Return the tracked path at every file-changing commit, oldest first.

    ``git log --follow`` is intentionally invoked for every spec.  At a rename
    commit the blob is read from its destination, then the cursor switches to the
    source before walking to the parent.  A copy/mismatched rename is recorded as
    ambiguous instead of guessed.
    """

    output = _run_git(
        repo,
        "log",
        "--follow",
        "--find-renames=50%",
        "--name-status",
        f"--format={RECORD_SEPARATOR}%H{FIELD_SEPARATOR}%cI",
        revision,
        "--",
        current_path,
    )
    reverse_records: list[HistoryRecord] = []
    path_cursor = current_path
    for block in output.split(RECORD_SEPARATOR):
        if not block.strip():
            continue
        first_line, *status_lines = block.lstrip("\r\n").splitlines()
        try:
            sha, date = first_line.split(FIELD_SEPARATOR, 1)
        except ValueError as error:
            raise MigrationError(f"unparseable git history for {current_path!r}") from error

        ambiguous: str | None = None
        # ``path_cursor`` is the name that exists in this commit.  A rename
        # changes it only for the next (parent) commit in the backwards walk.
        reverse_records.append(HistoryRecord(sha=sha, date=date, path=path_cursor))
        for line in status_lines:
            columns = line.split("\t")
            if not columns:
                continue
            status_code = columns[0]
            if status_code.startswith("R") and len(columns) >= 3:
                old_name, new_name = columns[1], columns[2]
                if new_name == path_cursor:
                    path_cursor = old_name
                else:
                    ambiguous = "rename-path-mismatch"
            elif status_code.startswith("C"):
                ambiguous = "copy-lineage"
        if ambiguous:
            reverse_records[-1] = dataclasses.replace(reverse_records[-1], ambiguous_reason=ambiguous)

    if not reverse_records:
        raise MigrationError(f"no Git history found for {current_path}")

    return list(reversed(reverse_records))


def _blob(repo: Path, sha: str, path: str) -> str:
    return _run_git(repo, "show", f"{sha}:{path}")


def _spec_files(repo: Path, expected_count: int) -> list[tuple[Path, int | None, str, str]]:
    specs_dir = repo / "specs"
    if not specs_dir.is_dir():
        raise MigrationError("specs directory does not exist")
    candidates: list[tuple[Path, int | None, str, str]] = []
    for path in sorted(specs_dir.glob("*.md"), key=lambda value: value.name.casefold()):
        if path.name.casefold() == "template.md":
            continue
        parsed = SPEC_ID_RE.match(path.name)
        if parsed:
            current_id = int(parsed.group(1))
            if 1 <= current_id <= expected_count:
                # Renames remain unstaged during this migration.  Git evidence
                # therefore stays anchored at the historical filename.
                candidates.append((path, current_id, parsed.group(2), f"specs/{parsed.group(2)}.md"))
            continue
        candidates.append((path, None, path.stem, _as_posix(path.relative_to(repo))))
    if len(candidates) != expected_count:
        raise MigrationError(
            f"expected exactly {expected_count} historical specs, found {len(candidates)}; "
            "pass --expected-count only for a deliberately smaller fixture"
        )
    existing_ids = [item[1] for item in candidates if item[1] is not None]
    if existing_ids and len(existing_ids) != len(candidates):
        raise MigrationError("mixed numbered and legacy historical specs; refusing a partial migration")
    if len(existing_ids) != len(set(existing_ids)):
        raise MigrationError("duplicate historical SPEC id")
    return candidates


def _is_shallow(repo: Path) -> bool:
    return _run_git(repo, "rev-parse", "--is-shallow-repository").strip().lower() == "true"


def _existing_index(repo: Path) -> dict[str, object] | None:
    index_path = repo / "specs" / "index.yaml"
    if not index_path.is_file():
        return None
    try:
        loaded = yaml.safe_load(_read_text(index_path))
    except yaml.YAMLError as error:
        raise MigrationError("existing specs/index.yaml is not valid YAML") from error
    if not isinstance(loaded, dict) or loaded.get("schema_version") != 1:
        raise MigrationError("existing specs/index.yaml has an unsupported schema")
    return loaded


def _active_spec_163(repo: Path) -> SpecRecord | None:
    active = next((path for path in (repo / "specs").glob("SPEC-163-*.md")), None)
    if active is None:
        return None
    active_relative = _as_posix(active.relative_to(repo))
    parsed = SPEC_ID_RE.match(active.name)
    assert parsed is not None
    try:
        history = _history(repo, active_relative)
    except MigrationError:
        history = []
    first_done: HistoryRecord | None = None
    for historical in history:
        if _status(_blob(repo, historical.sha, historical.path)).casefold() == "done":
            first_done = historical
            break
    first = history[0] if history else None
    return SpecRecord(
        old_path=active_relative,
        new_path=active_relative,
        slug=parsed.group(2),
        spec_id=163,
        status=_status(_read_text(active)),
        created_commit=first.sha if first else None,
        created_at=first.date if first else None,
        completed_commit=first_done.sha if first_done else None,
        completed_at=first_done.date if first_done else None,
        lineage_ambiguous=not bool(first),
        lineage_note="uncommitted-current-spec" if not first else None,
    )


def _group_by_created_commit(records: Iterable[SpecRecord]) -> dict[str, list[SpecRecord]]:
    groups: dict[str, list[SpecRecord]] = {}
    for record in records:
        if record.created_commit:
            groups.setdefault(record.created_commit, []).append(record)
    return groups


def _records_from_existing_index(
    repo: Path,
    candidates: list[tuple[Path, int | None, str, str]],
    existing: dict[str, object],
    expected_count: int,
) -> tuple[list[SpecRecord], str, bool]:
    entries = existing.get("specs")
    source_sha = existing.get("source_sha")
    if not isinstance(entries, list) or not isinstance(source_sha, str):
        raise MigrationError("existing specs/index.yaml lacks immutable migration provenance")
    by_id = {
        entry.get("id"): entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    _run_git(repo, "cat-file", "-e", f"{source_sha}^{{commit}}")
    topo_order = _topological_order(repo, source_sha)
    records: list[SpecRecord] = []
    indexed: dict[int, dict[str, object]] = {}
    for path, spec_id, slug, _ in candidates:
        assert spec_id is not None
        index_entry = by_id.get(f"SPEC-{spec_id:03d}")
        expected_path = f"specs/SPEC-{spec_id:03d}-{slug}.md"
        if not isinstance(index_entry, dict) or index_entry.get("slug") != slug or index_entry.get("path") != expected_path:
            raise MigrationError(f"existing index does not match immutable identity {expected_path}")
        # Old filenames are mechanically derivable from the permanent slug.  Do
        # not retain literal legacy paths in index.yaml: the report is the sole
        # migration-evidence exception allowed to contain them.
        old_path = f"specs/{slug}.md"
        history = _history(repo, old_path, source_sha)
        first = history[0]
        first_done: HistoryRecord | None = None
        for historical in history:
            if _status(_blob(repo, historical.sha, historical.path)).casefold() == "done":
                first_done = historical
                break
        notes = sorted({record.ambiguous_reason for record in history if record.ambiguous_reason})
        note = ", ".join(notes) if notes else None
        indexed[spec_id] = index_entry
        records.append(
            SpecRecord(
                old_path=old_path,
                new_path=expected_path,
                slug=slug,
                spec_id=spec_id,
                status=_status(_read_text(path)),
                created_commit=first.sha,
                created_at=first.date,
                completed_commit=first_done.sha if first_done else None,
                completed_at=first_done.date if first_done else None,
                lineage_ambiguous=bool(note),
                lineage_note=note,
            )
        )
    if len(records) != expected_count:
        raise MigrationError("existing index has incomplete immutable historical identities")
    for group in _group_by_created_commit(records).values():
        if len(group) > 1:
            for record in group:
                record.tie_breaker = "slug_lexical"
    completed = [record for record in records if record.completed_commit]
    completed.sort(key=lambda record: (topo_order[record.completed_commit or ""], record.slug.casefold()))
    for order, record in enumerate(completed, start=1):
        record.completed_order = order
    for record in records:
        entry = indexed[record.spec_id]
        expected = {
            "created_commit": record.created_commit,
            "created_at": record.created_at,
            "completed_commit": record.completed_commit,
            "completed_at": record.completed_at,
            "completed_order": record.completed_order,
            "tie_breaker": record.tie_breaker,
            "lineage_ambiguous": record.lineage_ambiguous,
            "lineage_note": record.lineage_note,
        }
        if any(entry.get(key) != value for key, value in expected.items()):
            raise MigrationError(f"existing index provenance was altered for SPEC-{record.spec_id:03d}")
    active = _active_spec_163(repo)
    if active:
        records.append(active)
    return records, source_sha, bool(existing.get("history_shallow", False))


def build_plan(repo: Path, expected_count: int = 162) -> tuple[list[SpecRecord], str, bool]:
    """Build a deterministic migration plan from Git and current spec headers."""

    repo = repo.resolve()
    source_sha = _run_git(repo, "rev-parse", "HEAD").strip()
    history_shallow = _is_shallow(repo)
    if history_shallow:
        raise MigrationError("shallow Git history cannot prove stable creation order; fetch full history first")
    candidates = _spec_files(repo, expected_count)
    existing = _existing_index(repo)
    if existing is not None and all(spec_id is not None for _, spec_id, _, _ in candidates):
        return _records_from_existing_index(repo, candidates, existing, expected_count)
    topo_order = _topological_order(repo)
    provisional: list[tuple[SpecRecord, int | None]] = []

    for path, existing_id, slug, history_path in candidates:
        relative = _as_posix(path.relative_to(repo))
        history = _history(repo, history_path)
        first = history[0]
        if first.sha not in topo_order:
            raise MigrationError(f"creation commit for {relative} is not reachable from HEAD")
        current_text = _read_text(path)
        first_done: HistoryRecord | None = None
        for historical in history:
            try:
                historical_status = _status(_blob(repo, historical.sha, historical.path))
            except MigrationError:
                # A path Git cannot read is precisely a lineage ambiguity; do not
                # turn a missing proof into a completion date.
                continue
            if historical_status.casefold() == "done":
                first_done = historical
                break
        notes = sorted({record.ambiguous_reason for record in history if record.ambiguous_reason})
        note = ", ".join(notes) if notes else ("shallow-history" if history_shallow else None)
        provisional.append(
            (
                SpecRecord(
                    old_path=history_path,
                    new_path="",
                    slug=slug,
                    spec_id=existing_id or 0,
                    status=_status(current_text),
                    created_commit=first.sha,
                    created_at=first.date,
                    completed_commit=first_done.sha if first_done else None,
                    completed_at=first_done.date if first_done else None,
                    lineage_ambiguous=bool(note),
                    lineage_note=note,
                ),
                existing_id,
            )
        )

    all_numbered = all(existing_id is not None for _, existing_id in provisional)
    ordered = sorted(
        provisional,
        key=lambda pair: (topo_order[pair[0].created_commit or ""], pair[0].slug.casefold()),
    )
    if all_numbered:
        assigned = sorted(provisional, key=lambda pair: pair[0].spec_id)
        if [record.spec_id for record, _ in ordered] != list(range(1, expected_count + 1)):
            raise MigrationError("numbered specs no longer match their Git creation order")
        records = [record for record, _ in assigned]
    else:
        records = []
        for position, (record, _) in enumerate(ordered, start=1):
            record.spec_id = position
            records.append(record)

    created_groups: dict[str, list[SpecRecord]] = {}
    for record in records:
        created_groups.setdefault(record.created_commit, []).append(record)
        record.new_path = f"specs/SPEC-{record.spec_id:03d}-{record.slug}.md"
    for group in created_groups.values():
        if len(group) > 1:
            for record in group:
                record.tie_breaker = "slug_lexical"

    completed = [record for record in records if record.completed_commit]
    completed.sort(
        key=lambda record: (
            topo_order[record.completed_commit or ""],
            record.slug.casefold(),
        )
    )
    for order, record in enumerate(completed, start=1):
        record.completed_order = order

    # SPEC-163 is a current, uncommitted migration spec.  It is intentionally
    # indexed but cannot claim a creation/completion commit before a commit
    # exists.  Later SPECs are outside this migration's immutable 001–162 set.
    active = _active_spec_163(repo)
    if active:
        records.append(active)
    return records, source_sha, history_shallow


def _index_payload(records: Iterable[SpecRecord], source_sha: str, history_shallow: bool) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for record in sorted(records, key=lambda value: value.spec_id):
        entries.append(
            {
                "id": f"SPEC-{record.spec_id:03d}",
                "slug": record.slug,
                "status": record.status,
                "path": record.new_path,
                "created_commit": record.created_commit,
                "created_at": record.created_at,
                "completed_commit": record.completed_commit,
                "completed_at": record.completed_at,
                "completed_order": record.completed_order,
                "depends_on": record.depends_on,
                "depends_on_raw": record.depends_on_raw,
                "depends_on_unresolved": record.depends_on_unresolved,
                "tie_breaker": record.tie_breaker,
                "lineage_ambiguous": record.lineage_ambiguous,
                "lineage_note": record.lineage_note,
            }
        )
    return {
        "schema_version": 1,
        "source_sha": source_sha,
        "history_shallow": history_shallow,
        "specs": entries,
    }


def render_index(records: Iterable[SpecRecord], source_sha: str, history_shallow: bool) -> str:
    return yaml.safe_dump(
        _index_payload(records, source_sha, history_shallow),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def render_report(records: Iterable[SpecRecord], source_sha: str, history_shallow: bool) -> str:
    rows = [
        "# Relatório da migração histórica de specs",
        "",
        f"- source_sha: `{source_sha}`",
        f"- history_shallow: `{str(history_shallow).lower()}`",
        "- execution_model: `gpt-5.6-terra`",
        "- execution_effort: `high`",
        "- provenance: `git log --follow --find-renames=50%` por arquivo",
        "",
        "| ID | old_path | new_path | criação (commit/data) | primeira prova `done` | lineage |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in sorted(records, key=lambda value: value.spec_id):
        created = "—" if not record.created_commit else f"`{record.created_commit}` / {record.created_at}"
        completed = "—" if not record.completed_commit else f"`{record.completed_commit}` / {record.completed_at}"
        lineage = record.lineage_note or "complete"
        rows.append(
            f"| SPEC-{record.spec_id:03d} | `{record.old_path}` | `{record.new_path}` | "
            f"{created} | {completed} | {lineage} |"
        )
    rows.extend(
        [
            "",
            "A ausência de prova histórica mantém `completed_at: null`; nenhuma data foi inferida.",
            "Os caminhos antigos aparecem somente neste relatório como evidência de migração.",
            "",
        ]
    )
    return "\n".join(rows)


def _replace_references(text: str, records: Iterable[SpecRecord]) -> str:
    updated = text
    ordered = sorted(records, key=lambda item: len(item.old_path), reverse=True)
    for record in ordered:
        old_windows = record.old_path.replace("/", "\\")
        new_windows = record.new_path.replace("/", "\\")
        updated = updated.replace(record.old_path, record.new_path)
        updated = updated.replace(old_windows, new_windows)
    by_slug = {record.slug: record for record in ordered}
    for old_name, target_slug in REFERENCE_ALIASES.items():
        target = by_slug.get(target_slug)
        if target:
            updated = updated.replace(old_name, Path(target.new_path).name)
    for record in ordered:
        old_name = Path(record.old_path).name
        new_name = Path(record.new_path).name
        # A bare filename must not be rewritten a second time inside a qualified
        # old/new path or an already numbered filename.
        pattern = re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(old_name)}(?![A-Za-z0-9_.-])")
        updated = pattern.sub(new_name, updated)
    return updated


def _broken_markdown_links(repo: Path, paths: Iterable[Path]) -> list[str]:
    broken: list[str] = []
    for path in paths:
        if path.suffix.casefold() != ".md":
            continue
        source = _read_text(path)
        for match in MARKDOWN_LINK_RE.finditer(source):
            target = match.group(1).split("#", 1)[0].split("?", 1)[0]
            if not target or "://" in target or target.startswith(("#", "/", "mailto:")):
                continue
            destination = (path.parent / target).resolve()
            try:
                destination.relative_to(repo)
            except ValueError:
                broken.append(f"link escapes repository: {path.relative_to(repo)} -> {target}")
                continue
            if not destination.exists():
                broken.append(f"broken Markdown link: {path.relative_to(repo)} -> {target}")
    return broken


def _iter_text_files(repo: Path, excluded: set[Path]) -> Iterable[Path]:
    """Yield tracked text plus explicit, safe docs/specs work-in-progress files.

    This avoids scanning local settings, secrets, saves, lore, virtualenvs, and
    generated data.  New documentation/spec files still participate before they
    are staged, which is required for this migration.
    """

    candidates: set[Path] = set()
    for relative in _run_git(repo, "ls-files", "-z").split("\0"):
        if relative:
            candidates.add(repo / relative)
    for safe_root in (repo / "docs", repo / "specs"):
        if safe_root.is_dir():
            candidates.update(path for path in safe_root.rglob("*") if path.is_file())
    for path in sorted(candidates, key=lambda value: _as_posix(value.relative_to(repo))):
        if not path.is_file() or path.resolve() in excluded:
            continue
        relative_parts = path.relative_to(repo).parts
        if any(part in SKIPPED_DIRECTORIES or part in {".claude", ".agents", ".codex"} for part in relative_parts):
            continue
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            _read_text(path)
        except UnicodeDecodeError:
            continue
        yield path


def _update_depends_on(repo: Path, records: Iterable[SpecRecord]) -> None:
    by_slug = {record.slug: f"SPEC-{record.spec_id:03d}" for record in records}
    by_filename = {Path(record.new_path).name: f"SPEC-{record.spec_id:03d}" for record in records}
    for record in records:
        content = _read_text(repo / record.new_path)
        match = DEPENDS_RE.search(content)
        raw = match.group(1).strip() if match else ""
        record.depends_on_raw = [] if raw.casefold() in {"", "—", "nenhuma", "nada bloqueante"} else [raw]
        resolved = {f"SPEC-{value}" for value in SPEC_REFERENCE_RE.findall(raw)}
        unresolved = raw
        for filename, spec_id in by_filename.items():
            if filename in unresolved:
                resolved.add(spec_id)
                unresolved = unresolved.replace(filename, "")
        for slug, spec_id in by_slug.items():
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(slug)}(?![A-Za-z0-9_-])", unresolved):
                resolved.add(spec_id)
                unresolved = re.sub(rf"(?<![A-Za-z0-9_-]){re.escape(slug)}(?![A-Za-z0-9_-])", "", unresolved)
        resolved.discard(f"SPEC-{record.spec_id:03d}")
        record.depends_on = sorted(resolved)
        residue = re.sub(r"[\[\]`()·,;:.—–/]+", " ", unresolved).strip()
        record.depends_on_unresolved = [] if not residue else [raw]


def _apply(repo: Path, records: list[SpecRecord], source_sha: str, history_shallow: bool, report_path: Path) -> None:
    index_path = repo / "specs" / "index.yaml"
    exclusions = {report_path.resolve(), index_path.resolve()}
    exclusions.update(path.resolve() for path in (repo / "docs" / "evals-plan-v4").rglob("*") if path.is_file())
    expected_legacy_bytes: dict[Path, str] = {}
    for record in records:
        old = repo / record.old_path
        new = repo / record.new_path
        if old.exists() and old.resolve() != new.resolve():
            # This is a byte-preserving semantic guard: a historical spec may
            # differ only by the exact deterministic reference rewrites.
            expected_legacy_bytes[new] = _replace_references(_read_text(old), records)

    # Rename first; reference rewrites then see a single canonical target path.
    for record in records:
        old = repo / record.old_path
        new = repo / record.new_path
        if old.resolve() == new.resolve():
            continue
        if new.exists() and old.exists():
            raise MigrationError(f"refusing to overwrite existing path: {record.new_path}")
        if old.exists():
            old.rename(new)
        elif not new.exists():
            raise MigrationError(f"missing both legacy and canonical path: {record.old_path}")

    for path in _iter_text_files(repo, exclusions):
        original = _read_text(path)
        updated = _replace_references(original, records)
        if updated != original:
            _write_text(path, updated)

    for path, expected in expected_legacy_bytes.items():
        if _read_text(path) != expected:
            raise MigrationError(f"historical spec changed beyond mapped references: {path.relative_to(repo)}")

    _update_depends_on(repo, records)
    _write_text(index_path, render_index(records, source_sha, history_shallow))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(report_path, render_report(records, source_sha, history_shallow))


def _check(repo: Path, records: list[SpecRecord], source_sha: str, history_shallow: bool, report_path: Path) -> list[str]:
    errors: list[str] = []
    for record in records:
        if not (repo / record.new_path).is_file():
            errors.append(f"missing canonical spec: {record.new_path}")
        if record.old_path != record.new_path and (repo / record.old_path).exists():
            errors.append(f"legacy path still exists: {record.old_path}")
    _update_depends_on(repo, records)
    expected_index = render_index(records, source_sha, history_shallow)
    index_path = repo / "specs" / "index.yaml"
    if not index_path.is_file() or _read_text(index_path) != expected_index:
        errors.append("specs/index.yaml is absent or not reproducible at this SHA")
    expected_report = render_report(records, source_sha, history_shallow)
    if not report_path.is_file() or _read_text(report_path) != expected_report:
        errors.append(f"migration report is absent or not reproducible: {report_path.relative_to(repo)}")

    exclusions = {report_path.resolve(), index_path.resolve()}
    exclusions.update(path.resolve() for path in (repo / "docs" / "evals-plan-v4").rglob("*") if path.is_file())
    scanned_paths = list(_iter_text_files(repo, exclusions))
    for path in scanned_paths:
        content = _read_text(path)
        rewritten = _replace_references(content, records)
        if rewritten != content:
            errors.append(f"unrewritten spec reference in {path.relative_to(repo)}")
    errors.extend(_broken_markdown_links(repo, scanned_paths))
    return errors


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true", help="print the deterministic migration plan")
    action.add_argument("--apply", action="store_true", help="rename specs and write references/index/report")
    action.add_argument("--check", action="store_true", help="fail unless the migration is idempotently canonical")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--expected-count", type=int, default=162)
    parser.add_argument("--report", type=Path, default=Path("docs/specs-migration-report.md"))
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    repo = args.repo.resolve()
    report_path = (repo / args.report).resolve() if not args.report.is_absolute() else args.report.resolve()
    try:
        records, source_sha, history_shallow = build_plan(repo, args.expected_count)
        if args.dry_run:
            print(render_report(records, source_sha, history_shallow))
            return 0
        if args.apply:
            _apply(repo, records, source_sha, history_shallow, report_path)
            print(
                f"Applied canonical names for {args.expected_count} historical specs"
                f" and indexed {len(records) - args.expected_count} active spec(s)."
            )
            return 0
        errors = _check(repo, records, source_sha, history_shallow, report_path)
        if errors:
            print("SPEC migration check failed:", *[f"- {error}" for error in errors], sep="\n", file=sys.stderr)
            return 1
        print(
            f"SPEC migration check passed for {args.expected_count} historical specs"
            f" and {len(records) - args.expected_count} active spec(s)."
        )
        return 0
    except MigrationError as error:
        print(f"SPEC migration refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
