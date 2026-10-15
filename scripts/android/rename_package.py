"""SPEC-198: rename the Android applicationId / namespace / Java package consistently. Dry-run by default.

  uv run python scripts/android/rename_package.py --new com.acme.valoria               # plan only
  uv run python scripts/android/rename_package.py --new com.acme.valoria --apply        # edits files + moves java dir
  uv run python scripts/android/rename_package.py --new ... --root <copy of repo> --apply   # test on a temp copy

Touches: web/capacitor.config.ts (appId), web/android/app/build.gradle (namespace+applicationId),
res/values/strings.xml (package_name/custom_url_scheme), Java sources (package decl + dir move),
scripts/android_billing_smoke.mjs. Optional --app-name rewrites app_name/title_activity_main + capacitor appName.
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
JAVA_KEYWORDS = {"abstract", "class", "default", "enum", "final", "for", "if", "int", "new", "package", "private",
                 "public", "return", "static", "switch", "this", "try", "void", "while", "import", "interface"}
OLD_RE = re.compile(r"applicationId\s+\"([^\"]+)\"")


def detect_old(root: Path) -> str:
    m = OLD_RE.search((root / "web/android/app/build.gradle").read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("cannot detect current applicationId")
    return m.group(1)


def plan(root: Path, old: str, new: str, app_name: str | None) -> tuple[list[Path], list[tuple[Path, Path]]]:
    texts = [root / p for p in ("web/capacitor.config.ts", "web/android/app/build.gradle",
                                "web/android/app/src/main/res/values/strings.xml",
                                "scripts/android_billing_smoke.mjs")]
    javas = list((root / "web/android/app/src/main").rglob("*.java"))
    moves = []
    old_dir = Path(*old.split("."))
    for j in javas:
        rel = j.relative_to(root / "web/android/app/src/main/java")
        if str(rel.parent).replace("\\", "/") == "/".join(old.split(".")):
            moves.append((j, root / "web/android/app/src/main/java" / Path(*new.split(".")) / j.name))
    return [t for t in texts if t.exists()] + javas, moves


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", required=True)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--app-name")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root)
    new = a.new
    if not ID_RE.fullmatch(new) or any(p in JAVA_KEYWORDS for p in new.split(".")):
        raise SystemExit(f"invalid applicationId: {new}")
    old = detect_old(root)
    files, moves = plan(root, old, new, a.app_name)
    print(f"{'APPLY' if a.apply else 'DRY-RUN'}: {old} -> {new}")
    changed = 0
    for f in files:
        s = f.read_text(encoding="utf-8")
        t = s.replace(old, new)
        if a.app_name and f.name in ("strings.xml", "capacitor.config.ts"):
            t = re.sub(r'(<string name="(?:app_name|title_activity_main)">)[^<]*(</string>)', rf"\g<1>{a.app_name}\g<2>", t)
            t = re.sub(r"appName: '[^']*'", f"appName: '{a.app_name}'", t)
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
    if a.apply:  # drop emptied old dirs
        base = root / "web/android/app/src/main/java"
        d = base / Path(*old.split("."))
        while d != base and d.exists() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    left = [f for f in (root / "web/android/app/src").rglob("*") if f.is_file() and f.suffix in {".java", ".xml", ".gradle"}
            and old in f.read_text(encoding="utf-8", errors="ignore")] if a.apply else []
    if left:
        print("WARNING leftover references:", [str(x.relative_to(root)) for x in left])
        return 1
    print(f"done: {changed} file(s) edited, {len(moves)} moved. Next: cd web && npx cap sync android")
    return 0


if __name__ == "__main__":
    sys.exit(main())
