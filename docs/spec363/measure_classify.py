"""SPEC-363 R34: p50/p95/p99 das chamadas CLASSIFY bem-sucedidas do DeepSeek nos logs dos smokes (leitura)."""

import json
import sys

import statistics


def main(paths: list[str]) -> None:
    lat: list[int] = []
    fails = 0
    for path in paths:
        for line in open(path, encoding="utf-8", errors="replace"):
            if '"llm.attempt"' not in line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("provider") != "deepseek" or ev.get("tier") != "classify":
                continue
            if ev.get("outcome") == "success":
                lat.append(int(ev.get("latency_ms") or 0))
            else:
                fails += 1
    lat.sort()
    q = lambda p: lat[min(len(lat) - 1, int(p * len(lat)))] if lat else None  # noqa: E731
    print(json.dumps({"n_ok": len(lat), "n_fail": fails, "p50": q(.5), "p90": q(.9), "p95": q(.95), "p99": q(.99),
                      "max": lat[-1] if lat else None, "mean": round(statistics.mean(lat)) if lat else None}))


main(sys.argv[1:])
