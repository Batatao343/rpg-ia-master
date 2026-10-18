"""SPEC-217: verifier for the DEV and FROZEN Jev-router corpora. Offline, no provider call.

Run: ``uv run python evals/experiments/spec217_corpus_check.py`` (exit 0 = ok).
Checks schema, SHA-256 files, LF-only bytes, visible-target validity, canonical NPC ids,
the FROZEN counts (handoff section 4) and DEV x FROZEN non-overlap (handoff section 5).
Also probes, offline, that ``python_gate`` matches the real router (``_eligible`` method).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/experiments/data"
GRAPH = ROOT / "data/graph/entities.json"
ROUTES = {"storyteller", "combat_agent", "npc_actor", "loot"}
KINDS = {"route", "target"}
MIXES = {"npc_actor", "storyteller", "loot", "combat_agent", "ambiguous", "gate"}
FROZEN_MIX = {"npc_actor": 5, "storyteller": 4, "loot": 3, "combat_agent": 2, "ambiguous": 2}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def state_hash(case: dict[str, Any]) -> str:
    blob = json.dumps(case["input"].get("state") or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load(name: str, errors: list[str]) -> list[dict[str, Any]]:
    path = DATA / f"spec217_{name}.jsonl"
    raw = path.read_bytes()
    if b"\r" in raw:
        errors.append(f"{name}: CR byte found (LF required)")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    recorded = (DATA / f"spec217_{name}.sha256").read_text(encoding="utf-8").strip()
    if digest != recorded:
        errors.append(f"{name}: hash mismatch (file {digest} != recorded {recorded})")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def npcs(case: dict[str, Any]) -> list[dict[str, Any]]:
    return list((case["input"].get("state") or {}).get("npcs", {}).values())


def enemies(case: dict[str, Any]) -> list[dict[str, Any]]:
    return list((case["input"].get("state") or {}).get("enemies", []))


def visible_candidates(case: dict[str, Any]) -> set[str]:
    out = set()
    for n in npcs(case):
        if (n.get("id") and n.get("in_scene") and n.get("known_by_player", True)
                and n.get("visibility") not in ("hidden", "secret")):
            out.add(n["id"])
    for e in enemies(case):
        if e.get("id") and e.get("in_scene", True) and e.get("status", "ativo") == "ativo":
            out.add(e["id"])
    return out


def check_schema(cases: list[dict[str, Any]], split: str, graph_ids: set[str], errors: list[str]) -> None:
    seen: set[str] = set()
    for c in cases:
        cid = c.get("id", "?")
        if cid in seen:
            errors.append(f"{split}: duplicate id {cid}")
        seen.add(cid)
        need = {"id", "split", "kind", "input", "expected", "python_gate", "critical", "origin", "rationale"}
        if need - c.keys():
            errors.append(f"{cid}: missing fields {sorted(need - c.keys())}")
            continue
        if c["split"] != split or c["kind"] not in KINDS:
            errors.append(f"{cid}: bad split/kind")
        if c["input"].get("operation") != "route" or not c["input"].get("action"):
            errors.append(f"{cid}: bad input")
        exp = c["expected"]
        if exp.get("route") not in ROUTES:
            errors.append(f"{cid}: bad expected.route {exp.get('route')}")
        if c["kind"] == "route" and exp.get("target") is not None:
            errors.append(f"{cid}: kind=route must have target null")
        tgt = exp.get("target")
        if tgt is not None:
            if tgt not in visible_candidates(c):
                errors.append(f"{cid}: target {tgt} not among visible candidates")
            if tgt.startswith("npc_") and tgt not in graph_ids:
                errors.append(f"{cid}: target {tgt} not a public graph entity")
        for n in npcs(c):
            if (n.get("id", "").startswith("npc_") and n["id"] not in graph_ids
                    and n.get("visibility") not in ("hidden", "secret")):
                errors.append(f"{cid}: npc id {n['id']} not a public graph entity")
        if c["critical"] not in (None, "combat_escalation"):
            errors.append(f"{cid}: bad critical")
        if c["critical"] and exp["route"] == "combat_agent":
            errors.append(f"{cid}: critical=combat_escalation requires a non-combat oracle")
        if not c["rationale"].strip():
            errors.append(f"{cid}: empty rationale")
        if split == "frozen" and not (c["origin"] == "synthetic" and c.get("mix") in MIXES):
            errors.append(f"{cid}: frozen needs origin=synthetic and a valid mix")


def check_frozen(cases: list[dict[str, Any]], errors: list[str]) -> None:
    eligible = [c for c in cases if not c["python_gate"]]
    gates = [c for c in cases if c["python_gate"]]
    if len(eligible) != 16:
        errors.append(f"frozen: expected 16 eligible, got {len(eligible)}")
    if len(gates) < 4:
        errors.append(f"frozen: expected >=4 python-gate cases, got {len(gates)}")
    mix = Counter(c["mix"] for c in eligible)
    for key, n in FROZEN_MIX.items():
        if mix.get(key, 0) != n:
            errors.append(f"frozen: mix {key} expected {n}, got {mix.get(key, 0)}")
    if sorted(c.get("priority") or 0 for c in eligible) != list(range(1, 17)):
        errors.append("frozen: eligible priorities must be exactly 1..16")
    if any(c.get("priority") is not None for c in gates):
        errors.append("frozen: gate cases must have priority null")
    amb = [c for c in eligible if c["mix"] == "ambiguous"]
    if not all(c["critical"] == "combat_escalation" for c in amb):
        errors.append("frozen: ambiguous cases need critical=combat_escalation")
    with_target = [c for c in eligible if c["mix"] == "npc_actor" and c["expected"]["target"]]
    if len(with_target) < 3:
        errors.append("frozen: need >=3 npc_actor cases with target")
    if sum(1 for c in cases if len([n for n in npcs(c) if n.get("in_scene")]) > 1) < 4:
        errors.append("frozen: need >=4 cases with more than one NPC in scene")
    alias_hits = 0
    for c in cases:
        t = c["expected"]["target"]
        for n in npcs(c):
            if n.get("id") == t and any(norm(a) in norm(c["input"]["action"]) and norm(a) != norm(n["name"])
                                         for a in n.get("aliases", [])):
                alias_hits += 1
    if alias_hits < 2:
        errors.append(f"frozen: need >=2 alias-target cases, got {alias_hits}")


def template(case: dict[str, Any], extra: list[dict[str, Any]]) -> str:
    names: set[str] = set()
    for c in [case, *extra]:
        for n in npcs(c):
            for label in [n.get("name", ""), *n.get("aliases", [])]:
                names.update(t for t in norm(label).split() if len(t) >= 3)
        for e in enemies(c):
            names.update(t for t in norm(e.get("name", "")).split() if len(t) >= 3)
        w = (c["input"].get("state") or {}).get("world") or {}
        names.update(t for t in norm(w.get("current_location", "")).split() if len(t) >= 3)
    names -= {"com", "para", "uma", "dos", "das", "que", "sem", "por", "ele", "ela"}
    words = norm(case["input"]["action"]).split()
    return " ".join("X" if w in names else w for w in words)


def check_overlap(dev: list[dict[str, Any]], fro: list[dict[str, Any]], errors: list[str]) -> None:
    dev_ids = {c["id"] for c in dev}
    dev_norm = {c["id"]: norm(c["input"]["action"]) for c in dev}
    dev_fix = {(state_hash(c), c["expected"]["route"]) for c in dev}
    for f in fro:
        fid = f["id"]
        if fid in dev_ids:
            errors.append(f"overlap: id {fid}")
        fn = norm(f["input"]["action"])
        if (state_hash(f), f["expected"]["route"]) in dev_fix:
            errors.append(f"overlap: identical fixture+route {fid}")
        for d in dev:
            dn = dev_norm[d["id"]]
            if fn == dn:
                errors.append(f"overlap: same normalized action {fid} ~ {d['id']}")
            elif distance(fn, dn) <= 3:
                errors.append(f"overlap: edit distance <=3 {fid} ~ {d['id']}")
            tf, td = template(f, [d]), template(d, [f])
            if tf == td or distance(tf, td) <= 3:
                errors.append(f"overlap: same template {fid} ~ {d['id']} ({tf!r})")


class _Reached(Exception):
    pass


def probe_gate(case: dict[str, Any]) -> bool:
    """True when the real router resolves the case in Python (never reaches CLASSIFY)."""
    import copy

    import agents.router as router
    from evals.core.adapters import AdapterCase, RoutingAdapter

    original = router.get_llm

    def reached(*_a: Any, **_k: Any) -> Any:
        raise _Reached

    probe = AdapterCase(id="probe", suite="routing", description="", fixture=None,
                        input=copy.deepcopy(case["input"]), tags=(), source="", created_from=None)
    try:
        router.get_llm = reached
        try:
            RoutingAdapter().execute(probe)
        except _Reached:
            return False
        return True
    finally:
        router.get_llm = original


def main() -> int:
    errors: list[str] = []
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    ents = list(graph.values()) if isinstance(graph, dict) else graph
    graph_ids = {e["id"] for e in ents if e.get("visibility") == "public"}
    dev = load("dev", errors)
    fro = load("frozen", errors)
    check_schema(dev, "dev", graph_ids, errors)
    check_schema(fro, "frozen", graph_ids, errors)
    check_frozen(fro, errors)
    check_overlap(dev, fro, errors)
    sys.path.insert(0, str(ROOT))
    for c in [*dev, *fro]:
        if probe_gate(c) != c["python_gate"]:
            errors.append(f"{c['id']}: python_gate={c['python_gate']} but router probe says {not c['python_gate']}")
    for name, cases in (("dev", dev), ("frozen", fro)):
        routes = Counter(c["expected"]["route"] for c in cases)
        kinds = Counter(c["kind"] for c in cases)
        gates = sum(c["python_gate"] for c in cases)
        print(f"{name}: n={len(cases)} routes={dict(routes)} kinds={dict(kinds)} python_gate={gates} "
              f"critical={sum(bool(c['critical']) for c in cases)}")
    if errors:
        print(f"FAIL ({len(errors)}):")
        for e in errors:
            print(" -", e)
        return 1
    print("OK: hashes, schema, targets, frozen counts, non-overlap and gate probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
