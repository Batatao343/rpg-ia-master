"""SPEC-198: rename the Android applicationId / namespace / Java package consistently. Dry-run by default.

  uv run python scripts/android/rename_package.py --new com.acme.valoria               # plan only
  uv run python scripts/android/rename_package.py --new com.acme.valoria --apply        # edits files + moves java dir
  uv run python scripts/android/rename_package.py --new ... --root <copy of repo> --apply   # test on a temp copy

Touches: web/capacitor.config.ts (appId), web/android/app/build.gradle (namespace+applicationId),
res/values/strings.xml (package_name/custom_url_scheme), Java sources (package decl + dir move),
scripts/android_billing_smoke.mjs, scripts/android/* (incl. store_screenshots.mjs). Optional --app-name rewrites app_name/title_activity_main + capacitor appName.
Afterwards run `npx cap sync android` (regenerates capacitor.config.json). Idempotent; refuses invalid ids.
The package id is IMMUTABLE once the first AAB is uploaded to Play: choose it deliberately.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ID_RE = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
JAVA_KEYWORDS = {
    "abstract",
    "class",
    "default",
    "enum",
    "final",
    "for",
    "if",
    "int",
    "new",
    "package",
    "private",
    "public",
    "return",
    "static",
    "switch",
    "this",
    "try",
    "void",
    "while",
    "import",
    "interface",
}
OLD_RE = re.compile(r"applicationId\s+\"([^\"]+)\"")


def detect_old(root: Path) -> str:
    m = OLD_RE.search((root / "web/android/app/build.gradle").read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("cannot detect current applicationId")
    return m.group(1)


APP_NAME_RE = re.compile(r"[A-Za-z0-9 ._()\-]{1,30}")
JAVA_ROOT = "web/android/app/src/main/java"
TEXT_EXT = {
    ".java",
    ".xml",
    ".gradle",
    ".ts",
    ".js",
    ".mjs",
    ".json",
    ".kt",
    ".ps1",
    ".py",
    ".properties",
}


def text_files(root: Path) -> list[Path]:
    """Files that may carry the id: web/android sources (no build output), capacitor config, scripts/android/*."""
    out = [root / "web/capacitor.config.ts", root / "scripts/android_billing_smoke.mjs"]
    out += [
        p
        for p in (root / "scripts/android").glob("*")
        if p.is_file() and p.name != Path(__file__).name
    ]
    skip = {"build", ".gradle", "node_modules", ".idea"}
    for p in (root / "web/android").rglob("*"):
        if (
            p.is_file()
            and p.suffix in TEXT_EXT
            and not (skip & set(p.relative_to(root / "web/android").parts))
        ):
            out.append(p)
    return [p for p in dict.fromkeys(out) if p.exists()]


def plan(root: Path, old: str, new: str) -> tuple[list[Path], list[tuple[Path, Path]]]:
    base = root / JAVA_ROOT
    old_dir, new_dir = base / Path(*old.split(".")), base / Path(*new.split("."))
    moves = (
        [(j, new_dir / j.relative_to(old_dir)) for j in old_dir.rglob("*.java")]
        if old_dir.is_dir()
        else []
    )
    return text_files(root), moves


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--new", required=True)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--app-name")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root)
    new = a.new
    if not ID_RE.fullmatch(new) or any(p in JAVA_KEYWORDS for p in new.split(".")):
        raise SystemExit(f"invalid applicationId: {new}")
    if a.app_name is not None and not APP_NAME_RE.fullmatch(a.app_name):
        raise SystemExit(
            "invalid --app-name: use 1-30 of letters, digits, space . _ ( ) - (no quotes, backslashes, &, <, > or control chars)"
        )
    old = detect_old(root)
    files, moves = plan(root, old, new)
    print(f"{'APPLY' if a.apply else 'DRY-RUN'}: {old} -> {new}")
    changed = 0
    for f in files:
        s = f.read_text(encoding="utf-8")
        t = s.replace(old, new)
        if a.app_name and f.name in ("strings.xml", "capacitor.config.ts"):
            t = re.sub(
                r'(<string name="(?:app_name|title_activity_main)">)[^<]*(</string>)',
                lambda m: m.group(1) + a.app_name + m.group(2),
                t,
            )
            t = re.sub(r"appName: '[^']*'", lambda m: f"appName: '{a.app_name}'", t)
        if t != s:
            changed += 1
            print(f"  edit {f.relative_to(root)} ({s.count(old)} occurrence(s))")
            if a.apply:
                f.write_text(t, encoding="utf-8", newline="")
    for src, dst in moves:
        print(f"  move {src.relative_to(root)} -> {dst.relative_to(root)}")
        if a.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    if a.apply:  # drop emptied old dirs (including nested sub-packages)
        base = root / JAVA_ROOT
        for d in sorted(
            (p for p in (base / Path(*old.split("."))).rglob("*") if p.is_dir()), reverse=True
        ):
            if not any(d.iterdir()):
                d.rmdir()
        d = base / Path(*old.split("."))
        while d != base and d.exists() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
        left = [
            f for f in text_files(root) if old in f.read_text(encoding="utf-8", errors="ignore")
        ]
        if left:
            print("WARNING leftover references:", [str(x.relative_to(root)) for x in left])
            return 1
    print(
        f"done: {changed} file(s) edited, {len(moves)} moved. Next: cd web && npx cap sync android"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
