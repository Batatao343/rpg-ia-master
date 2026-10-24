"""SPEC-301 R1/R9 — lint do catálogo ``data/faction_membership.json`` (puro, sem I/O).

Devolve uma lista de problemas em texto PT-BR; ``services.content_validator`` embrulha cada
um em ``Finding("faction_membership", "error", ...)``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

PERK_TYPES = ("desconto", "intendente", "abrigo", "informacao", "passagem", "intercessao")
MISSION_KINDS = ("apoio", "sabotagem", "rito")
EXIT_POLICIES = ("livre", "desonra", "traicao")
ACCEPTS = ("sim", "condicional", "nao")
PATH_KINDS = ("traidor_de", "ex_membro_desonra", "reputation_at_least", "npc_met")


def lint_faction_membership(
    catalog: Any,
    *,
    faction_ids: Iterable[str],
    location_ids: Iterable[str],
    npc_ids: Iterable[str],
    item_ids: Iterable[str],
    merchant_location_ids: Iterable[str] = (),
) -> list[str]:
    problems: list[str] = []
    if not isinstance(catalog, Mapping):
        return ["catálogo não é um objeto JSON"]
    factions = set(faction_ids)
    locations = set(location_ids)
    npcs = set(npc_ids)
    items = set(item_ids)
    merchant_locs = set(merchant_location_ids)

    missing = sorted(factions - set(catalog))
    extra = sorted(set(catalog) - factions)
    if missing:
        problems.append(f"fações sem entrada no catálogo: {', '.join(missing)}")
    if extra:
        problems.append(f"entradas que não são fação de factions.json: {', '.join(extra)}")

    for fid, row in catalog.items():
        if fid not in factions:
            continue
        if not isinstance(row, Mapping):
            problems.append(f"{fid}: entrada não é objeto")
            continue
        accepts = row.get("accepts")
        if accepts not in ACCEPTS:
            problems.append(f"{fid}: accepts inválido ({accepts!r})")
            continue
        if accepts == "nao":
            if set(row) - {"accepts"}:
                problems.append(f"{fid}: fação 'nao' não pode ter ranks/requisitos/missões")
            continue
        problems.extend(_lint_accepting(fid, row, factions, locations, npcs, items, merchant_locs))
    return problems


def _lint_accepting(
    fid: str,
    row: Mapping,
    factions: set[str],
    locations: set[str],
    npcs: set[str],
    items: set[str],
    merchant_locs: set[str],
) -> list[str]:
    out: list[str] = []
    ranks = row.get("ranks")
    if not isinstance(ranks, list) or not 3 <= len(ranks) <= 5:
        out.append(f"{fid}: ranks deve ter de 3 a 5 patentes")
        ranks = ranks if isinstance(ranks, list) else []
    prev_merit = -1
    seen_ids: set[str] = set()
    for i, rank in enumerate(ranks):
        if not isinstance(rank, Mapping) or not rank.get("id") or not rank.get("name"):
            out.append(f"{fid}: patente {i} sem id/name")
            continue
        if rank["id"] in seen_ids:
            out.append(f"{fid}: id de patente repetido ({rank['id']})")
        seen_ids.add(rank["id"])
        merit = rank.get("merit")
        if not isinstance(merit, int) or merit < prev_merit or (i == 0 and merit != 0):
            out.append(f"{fid}: mérito da patente {i} inválido (crescente, a 1ª em 0)")
        else:
            prev_merit = merit
        if not isinstance(rank.get("min_level"), int) or rank["min_level"] < 1:
            out.append(f"{fid}: min_level da patente {i} inválido")
    if row.get("exit_policy") not in EXIT_POLICIES:
        out.append(f"{fid}: exit_policy inválido ({row.get('exit_policy')!r})")
    if not isinstance(row.get("secret"), bool):
        out.append(f"{fid}: secret deve ser booleano")
    hq = row.get("hq_location_ids") or []
    if not hq:
        out.append(f"{fid}: sem hq_location_ids")
    for loc in hq:
        if loc not in locations:
            out.append(f"{fid}: hq fora do mapa ({loc})")
    for npc in row.get("recruiter_npc_ids") or []:
        if npc not in npcs:
            out.append(f"{fid}: recrutador fora do grafo ({npc})")
    for key in ("rivals", "exclusive_with"):
        for other in row.get(key) or []:
            if other not in factions:
                out.append(f"{fid}: {key} contém id que não é fação ({other})")
    req = row.get("requirements") or {}
    for cond in req.get("requires_any") or []:
        if not isinstance(cond, Mapping) or cond.get("kind") not in PATH_KINDS:
            out.append(f"{fid}: requires_any com tipo inválido")
            continue
        if cond.get("faction") and cond["faction"] not in factions:
            out.append(f"{fid}: requires_any aponta fação inexistente ({cond['faction']})")
        if cond.get("npc_id") and cond["npc_id"] not in npcs:
            out.append(f"{fid}: requires_any aponta NPC inexistente ({cond['npc_id']})")
    for key in ("never_member_of", "converts_from"):
        for other in req.get(key) or []:
            if other not in factions:
                out.append(f"{fid}: {key} contém id que não é fação ({other})")
    out.extend(_lint_perks(fid, row, len(ranks), items, hq, merchant_locs))
    out.extend(_lint_missions(fid, row, len(ranks), factions, locations))
    return out


def _lint_perks(
    fid: str, row: Mapping, n_ranks: int, items: set[str], hq: list, merchant_locs: set[str]
) -> list[str]:
    out: list[str] = []
    has_qm = False
    for key, perks in (row.get("perks_by_rank") or {}).items():
        if not str(key).isdigit() or int(key) >= n_ranks:
            out.append(f"{fid}: perks_by_rank com patente inexistente ({key})")
        for perk in perks or []:
            ptype = perk.get("type") if isinstance(perk, Mapping) else None
            if ptype not in PERK_TYPES:
                out.append(f"{fid}: perk de tipo desconhecido ({ptype!r})")
            if ptype == "intendente":
                has_qm = True
            if ptype == "desconto":
                mult = perk.get("mult")
                if not isinstance(mult, (int, float)) or not 0 < mult <= 1.0:
                    out.append(f"{fid}: desconto com mult fora de (0, 1]")
    qm = row.get("quartermaster") or {}
    for iid, min_rank in qm.items():
        if iid not in items:
            out.append(f"{fid}: item do intendente fora de artifacts.json ({iid})")
        if not isinstance(min_rank, int) or not 0 <= min_rank < max(1, n_ranks):
            out.append(f"{fid}: min_rank do intendente inválido ({iid})")
    if qm and not has_qm:
        out.append(f"{fid}: quartermaster sem perk 'intendente'")
    if has_qm and not any(loc in merchant_locs for loc in hq):
        out.append(f"{fid}: perk 'intendente' sem mercador no QG")
    return out


def _lint_missions(
    fid: str, row: Mapping, n_ranks: int, factions: set[str], locations: set[str]
) -> list[str]:
    out: list[str] = []
    templates = [t for t in (row.get("mission_templates") or []) if isinstance(t, Mapping)]
    if len(templates) < 3:
        out.append(f"{fid}: precisa de ao menos 3 mission_templates")
    kinds = [t.get("kind") for t in templates]
    if kinds.count("apoio") < 2:
        out.append(f"{fid}: precisa de ao menos 2 missões de apoio")
    if kinds.count("sabotagem") < 1:
        out.append(f"{fid}: precisa de ao menos 1 missão de sabotagem")
    seen: set[str] = set()
    for t in templates:
        tid = str(t.get("id") or "")
        if not tid or tid in seen:
            out.append(f"{fid}: template sem id ou com id repetido ({tid!r})")
        seen.add(tid)
        if t.get("kind") not in MISSION_KINDS:
            out.append(f"{fid}/{tid}: kind inválido ({t.get('kind')!r})")
        if t.get("tier") not in (1, 2, 3):
            out.append(f"{fid}/{tid}: tier deve ser 1, 2 ou 3")
        if not isinstance(t.get("min_rank"), int) or not 0 <= t["min_rank"] < max(1, n_ranks):
            out.append(f"{fid}/{tid}: min_rank inválido")
        if not t.get("title") or not t.get("description"):
            out.append(f"{fid}/{tid}: título/descrição vazios")
        for loc in t.get("location_ids") or []:
            if loc not in locations:
                out.append(f"{fid}/{tid}: local fora do mapa ({loc})")
        if t.get("kind") == "sabotagem":
            target = t.get("target_faction_id")
            if target not in factions or target == fid:
                out.append(f"{fid}/{tid}: sabotagem com target_faction_id inválido")
    rite = (row.get("requirements") or {}).get("entry_rite")
    if rite and "rito" not in kinds:
        out.append(f"{fid}: entry_rite sem template de missão kind='rito'")
    return out
