"""Single source of truth for spec status: the spec header.

``specs/index.yaml`` is *generated* from the ``> **Status:** `x``` line of each
``specs/SPEC-NNN-<slug>.md``.  Nobody edits the index by hand any more; the
spec-landing step runs ``build``.  Provenance written by SPEC-163
(``scripts/normalize_specs.py``) is never rewritten: ``build`` only changes the
``status:`` line of an existing entry (surgical text edit, byte-stable) and
appends entries for new specs.

Commands (run from the repo root, e.g. ``uv run python scripts/spec_index.py check``)::

    build                      sync index.yaml with spec headers
    check                      exit 1 when index.yaml and headers disagree
    summary                    counts per status + in-progress list
    recent --days 7 [--write ESTADO_ATUAL.md]
                               one line per spec touched in the window; with
                               --write, replaces the block between
                               <!-- recent:start --> and <!-- recent:end -->
    next-id [--slug S --create]
                               next free SPEC number (files, index, spec-*
                               branches and rpg-spec-* worktrees); --create
                               writes specs/SPEC-NNN-S.md from TEMPLATE.md
    estado-size [--max 8192]   exit 1 when ESTADO_ATUAL.md exceeds the budget
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

STATUS_RE = re.compile(r"^\s*>\s*\*\*Status:\*\*\s*`([^`]+)`", re.IGNORECASE | re.MULTILINE)
SPEC_FILE_RE = re.compile(r"^SPEC-(\d{3,})-(.+)\.md$")
ENTRY_RE = re.compile(r"^- id: (SPEC-\d{3,})\s*$", re.MULTILINE)
RECENT_START = "<!-- recent:start -->"
RECENT_END = "<!-- recent:end -->"
INDEX = Path("specs/index.yaml")


class SpecIndexError(RuntimeError):
    pass


@dataclass(frozen=True)
class Spec:
    id: str
    number: int
    slug: str
    path: str
    status: str
    title: str


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout if result.returncode == 0 else ""


def _title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            return re.sub(r"^SPEC(-\d+)?\s*[—-]\s*", "", title)
    return ""


def scan(root: Path) -> dict[str, Spec]:
    specs: dict[str, Spec] = {}
    for path in sorted((root / "specs").glob("SPEC-*.md")):
        match = SPEC_FILE_RE.match(path.name)
        if not match:
            continue
        text = path.read_text(encoding="utf-8")
        status = STATUS_RE.search(text)
        number = int(match.group(1))
        spec_id = f"SPEC-{number:03d}"
        if spec_id in specs:
            raise SpecIndexError(f"duplicate {spec_id}: {specs[spec_id].path} and specs/{path.name}")
        specs[spec_id] = Spec(
            id=spec_id,
            number=number,
            slug=match.group(2),
            path=f"specs/{path.name}",
            status=status.group(1).strip() if status else "unknown",
            title=_title(text),
        )
    return specs


def _load_index(root: Path) -> tuple[str, dict[str, dict]]:
    raw = (root / INDEX).read_bytes().decode("utf-8")
    data = yaml.safe_load(raw) or {}
    entries = {entry["id"]: entry for entry in data.get("specs", [])}
    return raw, entries


def problems(root: Path) -> list[str]:
    specs = scan(root)
    _, entries = _load_index(root)
    found: list[str] = []
    for spec_id, spec in specs.items():
        entry = entries.get(spec_id)
        if entry is None:
            found.append(f"{spec_id}: missing from {INDEX.as_posix()}")
            continue
        if entry.get("path") != spec.path or entry.get("slug") != spec.slug:
            found.append(f"{spec_id}: identity drift ({entry.get('path')} != {spec.path})")
        if entry.get("status") != spec.status:
            found.append(f"{spec_id}: index says {entry.get('status')!r}, header says {spec.status!r}")
    for spec_id in sorted(set(entries) - set(specs)):
        found.append(f"{spec_id}: in {INDEX.as_posix()} but no spec file")
    return found


def _created(root: Path, path: str) -> tuple[str | None, str]:
    log = _git(root, "log", "--diff-filter=A", "--format=%H %cI", "--", path).strip().splitlines()
    if log:
        sha, date = log[-1].split(" ", 1)
        return sha, date
    return None, dt.date.today().isoformat()


def build(root: Path) -> list[str]:
    """Rewrite index.yaml in place; return a list of human-readable changes."""

    specs = scan(root)
    raw, entries = _load_index(root)
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    changes: list[str] = []
    orphans = sorted(set(entries) - set(specs))
    if orphans:
        raise SpecIndexError(f"{orphans[0]} is indexed but has no spec file; refusing to drop provenance")
    starts = [(m.group(1), m.start()) for m in ENTRY_RE.finditer(text)]
    bounds = {
        spec_id: (start, starts[i + 1][1] if i + 1 < len(starts) else len(text))
        for i, (spec_id, start) in enumerate(starts)
    }
    edits: list[tuple[int, int, str]] = []
    for spec_id, spec in specs.items():
        entry = entries.get(spec_id)
        if entry is None or entry.get("status") == spec.status:
            continue
        if entry.get("path") != spec.path:
            raise SpecIndexError(f"{spec_id}: identity drift ({entry.get('path')} != {spec.path})")
        start, end = bounds[spec_id]
        block = text[start:end]
        line = re.search(r"^  status: .*$", block, re.MULTILINE)
        if line is None:
            raise SpecIndexError(f"{spec_id}: entry has no status line")
        edits.append((start + line.start(), start + line.end(), f"  status: {spec.status}"))
        changes.append(f"{spec_id}: {entry.get('status')} -> {spec.status}")
    for begin, finish, replacement in sorted(edits, reverse=True):
        text = text[:begin] + replacement + text[finish:]
    new_entries = []
    for spec_id in sorted(set(specs) - set(entries), key=lambda key: specs[key].number):
        spec = specs[spec_id]
        sha, created_at = _created(root, spec.path)
        new_entries.append(
            {
                "id": spec.id,
                "slug": spec.slug,
                "status": spec.status,
                "path": spec.path,
                "created_commit": sha,
                "created_at": created_at,
                "completed_commit": None,
                "completed_at": None,
                "completed_order": None,
                "depends_on": [],
                "depends_on_raw": [],
                "depends_on_unresolved": [],
                "tie_breaker": None,
                "lineage_ambiguous": False,
                "lineage_note": "generated by scripts/spec_index.py build",
            }
        )
        changes.append(f"{spec_id}: added ({spec.status})")
    if new_entries:
        if not text.endswith("\n"):
            text += "\n"
        text += yaml.safe_dump(
            new_entries, allow_unicode=True, default_flow_style=False, sort_keys=False, width=10**9
        )
    if changes:
        (root / INDEX).write_bytes(text.replace("\n", newline).encode("utf-8"))
    return changes


def summary(root: Path) -> str:
    specs = scan(root)
    counts = Counter(spec.status for spec in specs.values())
    parts = " · ".join(f"{count} `{status}`" for status, count in counts.most_common())
    active = ", ".join(str(spec.number) for spec in specs.values() if spec.status == "in-progress")
    return f"{len(specs)} specs: {parts}" + (f" (in-progress: {active})" if active else "")


def recent(root: Path, days: int, today: dt.date | None = None) -> list[str]:
    specs = scan(root)
    by_path = {spec.path: spec for spec in specs.values()}
    since = (today or dt.date.today()) - dt.timedelta(days=days)
    log = _git(root, "log", f"--since={since.isoformat()}", "--name-only", "--format=\x1e%cs", "--", "specs/")
    touched: dict[str, str] = {}
    for record in log.split("\x1e"):
        lines = [line.strip() for line in record.strip().splitlines() if line.strip()]
        if not lines:
            continue
        date, files = lines[0], lines[1:]
        for name in files:
            if name in by_path and name not in touched:
                touched[name] = date
    for name in _git(root, "status", "--porcelain", "--", "specs/").splitlines():
        path = name[3:].strip().strip('"')
        if path in by_path:
            touched[path] = (today or dt.date.today()).isoformat()
    rows = sorted(touched.items(), key=lambda item: (item[1], by_path[item[0]].number), reverse=True)
    return [
        f"- {date} · {by_path[path].id} `{by_path[path].status}` — {by_path[path].title}"
        for path, date in rows
    ]


def write_recent(target: Path, lines: list[str]) -> None:
    raw = target.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    if RECENT_START not in text or RECENT_END not in text:
        raise SpecIndexError(f"{target} lacks {RECENT_START} / {RECENT_END} markers")
    head, rest = text.split(RECENT_START, 1)
    _, tail = rest.split(RECENT_END, 1)
    body = "\n".join(lines or ["- (nenhuma spec alterada na janela)"])
    text = f"{head}{RECENT_START}\n{body}\n{RECENT_END}{tail}"
    target.write_bytes(text.replace("\n", newline).encode("utf-8"))


def next_id(root: Path) -> int:
    numbers = {spec.number for spec in scan(root).values()}
    try:
        _, entries = _load_index(root)
        numbers |= {int(key.split("-")[1]) for key in entries}
    except (OSError, yaml.YAMLError):
        pass
    refs = _git(root, "branch", "--all", "--format=%(refname:short)") + _git(root, "worktree", "list", "--porcelain")
    numbers |= {int(m) for m in re.findall(r"(?:^|[/\s-])spec-(\d{3,})\b", refs, re.IGNORECASE | re.MULTILINE)}
    return max(numbers, default=0) + 1


def create_spec(root: Path, number: int, slug: str, today: dt.date | None = None) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", slug):
        raise SpecIndexError("slug must be lowercase kebab-case")
    path = root / "specs" / f"SPEC-{number:03d}-{slug}.md"
    if path.exists():
        raise SpecIndexError(f"{path} already exists")
    stamp = (today or dt.date.today()).isoformat()
    template = (root / "specs" / "TEMPLATE.md").read_text(encoding="utf-8")
    template = re.sub(r"^# SPEC — .*$", f"# SPEC-{number:03d} — {slug}", template, count=1, flags=re.MULTILINE)
    template = re.sub(r"^> \*\*Status:\*\*.*$", "> **Status:** `draft`", template, count=1, flags=re.MULTILINE)
    template = template.replace("YYYY-MM-DD · **Atualizada:** YYYY-MM-DD", f"{stamp} · **Atualizada:** {stamp}")
    path.write_bytes(template.replace("\r\n", "\n").encode("utf-8"))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sub.add_parser("check")
    sub.add_parser("summary")
    recent_parser = sub.add_parser("recent")
    recent_parser.add_argument("--days", type=int, default=7)
    recent_parser.add_argument("--write", type=Path)
    next_parser = sub.add_parser("next-id")
    next_parser.add_argument("--slug")
    next_parser.add_argument("--create", action="store_true")
    size_parser = sub.add_parser("estado-size")
    size_parser.add_argument("--max", type=int, default=8192)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "build":
            for change in build(root) or ["index.yaml already in sync"]:
                print(change)
        elif args.command == "check":
            found = problems(root)
            for problem in found:
                print(problem)
            if found:
                print("run: uv run python scripts/spec_index.py build")
                return 1
            print("specs/index.yaml in sync with spec headers")
        elif args.command == "summary":
            print(summary(root))
        elif args.command == "recent":
            lines = recent(root, args.days)
            if args.write:
                write_recent(root / args.write, lines)
                print(f"{len(lines)} lines -> {args.write}")
            else:
                print("\n".join(lines))
        elif args.command == "next-id":
            number = next_id(root)
            if args.create:
                if not args.slug:
                    parser.error("--create requires --slug")
                print(create_spec(root, number, args.slug).relative_to(root).as_posix())
            else:
                print(f"SPEC-{number:03d}")
        elif args.command == "estado-size":
            size = (root / "ESTADO_ATUAL.md").stat().st_size
            print(f"ESTADO_ATUAL.md = {size} bytes (max {args.max})")
            return 0 if size <= args.max else 1
    except SpecIndexError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
