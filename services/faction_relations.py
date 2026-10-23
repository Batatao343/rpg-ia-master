"""SPEC-302 R21: relacoes continuas entre as fac coes de `data/factions.json`.

`world_sim.faction_relations["a|b"]` (ids ordenados) fica em [-100, 100]. Semente: arestas
`enemy_of` do grafo (-60) e disposicao (hostil x hostil -20). Deriva diaria por causas
(inimigo comum +, regiao disputada -, controle de local -15, deriva lenta a semente).
Cruzar -WAR / +ALLIANCE muda a banda e o motor emite `faction_relation_changed`.
Puro: sem estado global, sem LLM; aleatoriedade so via `rng` recebido.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

WAR_THRESHOLD = 70
ALLIANCE_THRESHOLD = 60
WAR_EXIT = 50  # histerese: sai da guerra acima de -50
ALLIANCE_EXIT = 40
SEED_ENEMY = -60
SEED_HOSTILE = -20
INCIDENT_P = 0.01  # [BALANCEAR] incidente seeded entre vizinhos hostis
INCIDENT_DELTA = -20
CONTROL_DELTA = -15
WAR_BOOST = 30  # empurrao de `guerra` na regiao ao romper (a crise passa pelo diretor)


def pair_key(a: str, b: str) -> str:
    x, y = sorted((str(a), str(b)))
    return f"{x}|{y}"


def split_key(key: str) -> tuple[str, str]:
    a, _, b = key.partition("|")
    return a, b


def _enemy_pairs() -> set[str]:
    from services import graph_resolver as gr

    pairs = set()
    for e in gr.resolve_edges({}, edge_type="enemy_of", include_hidden=True):
        pairs.add(pair_key(e.get("source", ""), e.get("target", "")))
    return pairs


def seed_relations(factions: list) -> dict[str, int]:
    """Matriz semente para as faccoes vivas da partida (so ids de `factions`)."""
    facs = [f for f in factions if isinstance(f, dict) and f.get("id")]
    enemies = _enemy_pairs()
    out: dict[str, int] = {}
    for i, fa in enumerate(facs):
        for fb in facs[i + 1 :]:
            key = pair_key(fa["id"], fb["id"])
            if key in enemies:
                out[key] = SEED_ENEMY
            elif fa.get("disposition") == "hostil" and fb.get("disposition") == "hostil":
                out[key] = SEED_HOSTILE
            else:
                out[key] = 0
    return out


def faction_relation(state: dict, a: str, b: str) -> int:
    sim = (state or {}).get("world_sim") or {}
    return int((sim.get("faction_relations") or {}).get(pair_key(a, b), 0))


def relation_label(value: int) -> str:
    if value <= -WAR_THRESHOLD:
        return "guerra"
    if value <= -20:
        return "hostil"
    if value >= ALLIANCE_THRESHOLD:
        return "alianca"
    if value >= 20:
        return "cordial"
    return "neutra"


def next_relation_band(old: str, value: int) -> str:
    """Bandas `guerra | neutra | alianca` com histerese."""
    if old == "guerra":
        return "guerra" if value <= -WAR_EXIT else "neutra"
    if old == "alianca":
        return "alianca" if value >= ALLIANCE_EXIT else "neutra"
    if value <= -WAR_THRESHOLD:
        return "guerra"
    if value >= ALLIANCE_THRESHOLD:
        return "alianca"
    return "neutra"


def step_relations(
    relations: dict[str, int],
    seed: dict[str, int],
    *,
    factions: list,
    rng: Any,
    faction_region: Callable[[dict], str | None],
    control_events: list[dict] | None = None,
    region_of: Callable[[str], str] | None = None,
) -> dict[str, int]:
    """Um dia de deriva. Devolve nova matriz (clamp [-100, 100])."""
    by_id = {f["id"]: f for f in factions if isinstance(f, dict) and f.get("id")}
    out = {k: int(v) for k, v in relations.items() if all(x in by_id for x in split_key(k))}
    for key, seed_v in seed.items():
        out.setdefault(key, int(seed_v))
    region = {fid: (faction_region(f) or "") for fid, f in by_id.items()}
    keys = sorted(out)
    snapshot = dict(out)
    for key in keys:
        a, b = split_key(key)
        fa, fb = by_id.get(a), by_id.get(b)
        if not fa or not fb or fa.get("defeated") or fb.get("defeated"):
            continue
        v = snapshot[key]
        # deriva lenta rumo a semente
        s = int(seed.get(key, 0))
        v += (s > v) - (s < v)
        # inimigo comum (+1): ambos hostis a um terceiro
        for c in sorted(by_id):
            if c in (a, b):
                continue
            if snapshot.get(pair_key(a, c), 0) <= -40 and snapshot.get(pair_key(b, c), 0) <= -40:
                v += 1
                break
        # regiao disputada (-1)
        same_region = bool(region[a]) and region[a] == region[b]
        if same_region:
            v -= 1
        # incidente seeded (sempre sorteia)
        roll = rng.random()
        if same_region and snapshot[key] < 0 and roll < INCIDENT_P:
            v += INCIDENT_DELTA
        out[key] = max(-100, min(100, v))
    # controle de local (-15 entre o novo controlador e as demais faccoes da regiao)
    for ev in control_events or []:
        new = str((ev.get("payload") or {}).get("new_controller_id") or "")
        reg = region_of(str(ev.get("target_id") or "")) if region_of else ""
        if new not in by_id or not reg:
            continue
        for fid in sorted(by_id):
            if fid != new and region.get(fid) == reg:
                k = pair_key(new, fid)
                if k in out:
                    out[k] = max(-100, out[k] + CONTROL_DELTA)
    return out


def crossings(
    relations: dict[str, int], bands: dict[str, str]
) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    """Novas bandas (esparsas: `neutra` nao e guardada) + mudancas `(chave, antiga, nova)`."""
    new: dict[str, str] = {}
    changes: list[tuple[str, str, str]] = []
    for key in sorted(relations):
        old = bands.get(key, "neutra")
        nb = next_relation_band(old, relations[key])
        if nb != "neutra":
            new[key] = nb
        if nb != old:
            changes.append((key, old, nb))
    return new, changes
