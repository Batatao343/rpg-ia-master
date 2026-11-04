"""Compara um dump (SPEC382_DUMP) com o fixture novo e com o antigo. Uso: score.py <dump> <fixture> <old>."""

import hashlib
import json
import sys
from pathlib import Path

dump, fixture, old = (
    Path(sys.argv[1]),
    json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")),
    json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")),
)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:16]


new_fail, old_fail, parts_hit = [], [], set()
for case, parts in sorted(fixture.items()):
    diff = [
        k
        for k, h in parts.items()
        if (dump / f"{case}.{k}.txt").exists() and sha(dump / f"{case}.{k}.txt") != h
    ]
    missing = [k for k in parts if not (dump / f"{case}.{k}.txt").exists()]
    if diff or missing:
        new_fail.append(case)
        parts_hit.update(diff)
    if case in old:
        od = [k for k, h in old[case].items() if sha(dump / f"{case}.{k}.txt") != h]
        if od:
            old_fail.append(case)
print(
    json.dumps(
        {
            "new_fail": len(new_fail),
            "old_fail": len(old_fail),
            "parts": sorted(parts_hit),
            "cases": new_fail,
        },
        ensure_ascii=False,
    )
)
