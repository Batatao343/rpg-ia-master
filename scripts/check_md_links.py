"""Check relative Markdown links resolve to files inside the repo (stdlib only).

    python scripts/check_md_links.py                 # every tracked *.md
    python scripts/check_md_links.py a.md docs/b.md  # only these files
    python scripts/check_md_links.py --baseline f    # fail only on links not listed in f

The repo has historical broken links; `--baseline` lets CI and moves (e.g. relocating
docs/historico/proximas-specs/) prove "no NEW broken link" without fixing old ones first.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
ROOT = Path(__file__).resolve().parents[1]


def broken_links(root: Path, files: list[Path]) -> list[str]:
    broken: list[str] = []
    for path in files:
        if path.suffix.casefold() != ".md" or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in LINK_RE.finditer(text):
            target = unquote(match.group(1).split("#", 1)[0].split("?", 1)[0])
            if not target or "://" in target or target.startswith(("/", "mailto:", "@")):
                continue
            destination = (path.parent / target).resolve()
            rel = path.resolve().relative_to(root).as_posix()
            try:
                destination.relative_to(root)
            except ValueError:
                broken.append(f"{rel} -> {target} (escapes repo)")
                continue
            if not destination.exists():
                broken.append(f"{rel} -> {target}")
    return sorted(set(broken))


def tracked_markdown(root: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z", "*.md"], cwd=root, capture_output=True, check=True)
    return [root / name for name in out.stdout.decode("utf-8").split("\0") if name]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--baseline", type=Path, help="known broken links, one per line")
    parser.add_argument("--write-baseline", type=Path)
    args = parser.parse_args(argv)
    files = [path.resolve() for path in args.files] or tracked_markdown(ROOT)
    found = broken_links(ROOT, files)
    if args.write_baseline:
        args.write_baseline.write_text("".join(f"{line}\n" for line in found), encoding="utf-8")
    known = set()
    if args.baseline and args.baseline.exists():
        known = {line.strip() for line in args.baseline.read_text(encoding="utf-8").splitlines() if line.strip()}
    new = [line for line in found if line not in known]
    for line in new:
        print(f"broken link: {line}")
    print(f"{len(files)} files, {len(found)} broken ({len(new)} new)")
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
