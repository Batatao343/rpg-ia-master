"""SPEC-372: criaturas de trama. Portao, puxao, nascimento nos locais e rumor da trama.

Tudo puro e deterministico; o estagio vem de `plot_threads.plot_stages` (derivado, sem estado
novo). Com `RPG_FAUNA_TRAMAS=off` (ou sem `RPG_FAUNA=on` / `RPG_PLOT_THREADS=on`) nada daqui
muda o jogo. `services.fauna` e importado dentro das funcoes (evita ciclo).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from services.fauna_lint_tramas import normalize_tramas
from services.plot_threads import STAGES

MODES = ("off", "on")
_warned = False


def mode() -> str:
    """`RPG_FAUNA_TRAMAS`; exige `RPG_FAUNA=on` e `RPG_PLOT_THREADS=on` (R12), senao `off`."""
    global _warned
    from services import fauna, plot_threads

    raw = os.getenv("RPG_FAUNA_TRAMAS", "").strip().lower()
    val = raw if raw in MODES else "off"
    if val == "on" and (fauna.mode() != "on" or plot_threads.mode() != "on"):
        if not _warned:
            _warned = True
            fauna._log("tramas_sem_motor")
        return "off"
    return val


def _rank(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else 0


def reached(entry: dict | None, stages: Mapping[str, str] | None) -> list[str]:
    """Ids das tramas ligadas cujo estagio ja atingiu o `desde` (ordem do autor)."""
    out = []
    for link in normalize_tramas((entry or {}).get("tramas")):
        if _rank((stages or {}).get(link["id"], "dormente")) >= _rank(link["desde"]):
            out.append(link["id"])
    return out


def gate_closed(entry: dict | None, stages: Mapping[str, str] | None) -> bool:
    """R7: criatura ligada sem nenhuma trama atingida. Sem flag, sem estagios ou sem ligacao: nao."""
    if not stages or not (entry or {}).get("tramas") or mode() != "on":
        return False
    return not reached(entry, stages)


def _locations(thread_ids: list[str]) -> set[str]:
    from services import plot_threads

    out: set[str] = set()
    for tid in thread_ids:
        thr = plot_threads.thread(tid)
        if thr is not None:
            out.update(thr.locations)
    return out


def factor(
    entry: dict | None, location_id: str, stages: Mapping[str, str] | None
) -> tuple[float, str | None]:
    """R7/R9 (`trama_factor`): `(fator, razao)`; `(1.0, None)` sem efeito."""
    from services import fauna

    if not stages or not (entry or {}).get("tramas") or mode() != "on":
        return 1.0, None
    hit = reached(entry, stages)
    if not hit:
        return 0.0, "trama_dormente"
    if location_id and location_id in _locations(hit):
        return float(fauna.const("TRAMA_MULT")), f"trama:{hit[0]}"
    return 1.0, f"trama:{hit[0]}"


def apply_gate(pool: list[dict], weights: list[float], stages: Mapping[str, str] | None) -> list:
    """R8: zera o peso de quem esta atras do portao, inclusive no fallback legado e nos migrantes."""
    if not stages or mode() != "on":
        return weights
    from services import fauna

    return [
        0.0 if gate_closed(fauna.entry(str(e.get("id") or "")), stages) else w
        for e, w in zip(pool, weights)
    ]


def open_pool(pool: list[dict], stages: Mapping[str, str] | None) -> list[dict]:
    """Pool sem as criaturas atras do portao (ramo legado por turno, sem pesos)."""
    if not stages or mode() != "on":
        return pool
    from services import fauna

    return [e for e in pool if not gate_closed(fauna.entry(str(e.get("id") or "")), stages)]


def stages_for(state: dict, world: dict | None) -> dict[str, str] | None:
    """Estagios das tramas da regiao atual; `None` com a flag `off` (R3/R12)."""
    if mode() != "on":
        return None
    from services import plot_threads
    from services import world_pressures as wp

    region = wp.region_of(str((world or {}).get("current_location_id") or ""))
    return dict(plot_threads.plot_stages(state, region)) if region else None


def region_stages(state: dict, region: str) -> dict[str, str]:
    """Estagios das tramas de uma regiao (day_hook); `{}` com a flag `off`."""
    if mode() != "on":
        return {}
    from services import plot_threads

    return dict(plot_threads.plot_stages(state, region))


def birth(
    entry: dict, stages: Mapping[str, str], locais: list[str]
) -> tuple[list[str], str] | None:
    """R10: `(locais ∩ locais das tramas atingidas, trama_id)`; `None` = sem efeito (nao ligada
    ou flag off); `([], "")` = nao cabe (o chamador pula o dia)."""
    if not stages or not entry.get("tramas") or mode() != "on":
        return None
    hit = reached(entry, stages)
    allowed = _locations(hit)
    out = [n for n in locais if n in allowed]
    tid = next((t for t in hit if set(out) & _locations([t])), "")
    return (out, tid) if out else ([], "")


def presence_error(p: dict, e: dict) -> str | None:
    """R16: motivo de invalidade de uma presenca com `trama_id`, ou `None`."""
    tid = p.get("trama_id")
    if not tid:
        return None
    from services import plot_threads

    thr = plot_threads.thread(str(tid))
    if thr is None or tid not in {t["id"] for t in normalize_tramas((e or {}).get("tramas"))}:
        return "trama_id sem ligacao"
    if not set(p.get("locais") or []) <= set(thr.locations):
        return "local fora da trama"
    return None


def disperse_closed(fauna: dict, state: dict, day: int) -> None:
    """P2-10: presenca ativa de criatura cuja trama regrediu (portao fechado) e dispersa; assim
    nao ocupa o teto da regiao nem mostra sinal. Muta `fauna`; sem efeito com a flag `off`."""
    if mode() != "on":
        return
    from services import fauna as fa

    cache: dict[str, dict[str, str]] = {}
    for p in fauna.get("presencas") or []:
        if not p.get("trama_id") or not fa._active(p, day):
            continue
        region = str(p.get("region_id") or "")
        stages = cache.setdefault(region, region_stages(state, region))
        if gate_closed(fa.entry(p["creature_id"]), stages):
            p["status"] = "dispersa"
            fa._log(
                "trama_portao", creature=p["creature_id"], thread=p["trama_id"], stage="regrediu"
            )


def log_pull(picked: dict | None, stages: Mapping[str, str] | None, location_id: str) -> None:
    """R14: `trama_puxao` quando a criatura sorteada pesou `TRAMA_MULT` neste local."""
    if not picked or not stages or mode() != "on":
        return
    from services import fauna

    e = fauna.entry(str(picked.get("id") or ""))
    f, why = factor(e, location_id, stages)
    if f > 1.0 and why:
        fauna._log("trama_puxao", creature=picked.get("id"), thread=why.split(":", 1)[1])


def log_gates(cands: list[dict], stages: Mapping[str, str] | None) -> None:
    from services import fauna

    for e in cands:
        if gate_closed(e, stages):
            for link in normalize_tramas(e.get("tramas")):
                fauna._log(
                    "trama_portao",
                    creature=e.get("id"),
                    thread=link["id"],
                    stage=(stages or {}).get(link["id"], "dormente"),
                )


def rumor_adjust(
    state: dict, sim: dict, region_id: str, day: int, own: list[tuple[dict, float]]
) -> list[tuple[dict, float]]:
    """R11: boost das sementes da trama com presenca ligada ativa; `avistamento` da criatura
    atras do portao pesa 0 (D7). O portao de segredo ja filtrou `own` antes."""
    from services import fauna, plot_threads

    if fauna.sinais_mode() != "on" or mode() != "on":
        return own
    stages = region_stages(state, region_id)
    live = {
        str(p.get("trama_id"))
        for p in ((sim or {}).get("fauna") or {}).get("presencas") or []
        if isinstance(p, dict)
        and p.get("trama_id")
        and p.get("region_id") == region_id
        and p.get("status") == "ativa"
        and int(p.get("expires_day", 0)) >= int(day)
    }
    seeds: set[str] = set()
    for tid in live:
        thr = plot_threads.thread(tid)
        if thr is not None:
            seeds.update(thr.rumor_ids)
            for door in thr.portas:
                seeds.update(door.rumor_ids)
    boost = float(fauna.const("RUMOR_BOOST"))
    out = []
    for s, w in own:
        ents: Any = s.get("entities") or []
        if s.get("family") == "avistamento" and any(
            gate_closed(fauna.entry(str(c)), stages) for c in ents
        ):
            w = 0.0
        elif s.get("seed_id") in seeds:
            w *= boost
        out.append((s, w))
    return out
