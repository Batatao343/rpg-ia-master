"""SPEC-313: quests ancoradas em lore (caca, entrega, escolta, rumor, mortos).

O motor decide TUDO que e numero ou verdade: ancora (validada contra o menu oferecido ao NPC),
prazo, recompensa, conclusao e falha. A LLM do NPC so escolhe um `kind` e um `anchor_id` de
uma lista fechada (`<GANCHOS_POSSIVEIS>`) e, no maximo, redige titulo/descricao (com guarda).

Este modulo NAO monta dict de quest (SPEC-305 R7: so `services/world_quests.py` faz isso);
ele devolve `QuestSeed`. Tudo e Python puro e deterministico (sem `random`).

Modos `RPG_LORE_QUESTS=off|shadow|on` (so valem com `RPG_WORLD_QUESTS` efetivamente `on`).
"""

from __future__ import annotations

import math
import os
import re
import unicodedata
from typing import Any

from services import world_pressures as wp

MODES = ("off", "shadow", "on")
DEFAULT_MODE = "on"
LORE_KINDS = frozenset(
    {"cacar_criatura", "entregar_material", "escoltar", "investigar_rumor", "recolher_mortos"}
)
NPC_PROPOSABLE = LORE_KINDS - {"recolher_mortos"}
MECHANICAL_KINDS = frozenset({"cacar_criatura", "entregar_material", "escoltar"})
MAX_LORE_QUESTS_ACTIVE = 2
PERIODS_PER_DAY = 5
# downgrade = vira quest comum; o resto e descarte silencioso (R3 vs R9/R10/R17/R18)
DOWNGRADE_REASONS = frozenset({"not_npc", "bad_kind", "not_in_menu", "invalid_anchor", "mode_off"})

_TIME_OR_MONEY = re.compile(
    r"\d+\s*(dia|dias|noite|noites|semana|semanas|hora|horas|moeda|moedas|ouro|coroa|coroas|"
    r"pe[cç]a|pe[cç]as)\b",
    re.IGNORECASE,
)


def mode() -> str:
    """`RPG_LORE_QUESTS`; so vale `on`/`shadow` com `RPG_WORLD_QUESTS` efetivamente `on` (R32)."""
    raw = os.getenv("RPG_LORE_QUESTS", "").strip().lower()
    m = raw if raw in MODES else DEFAULT_MODE
    from services import world_quests

    return m if world_quests.mode() == "on" else "off"


def _log(action: str, **fields: Any) -> None:
    from observability.telemetry import log_event

    log_event("lore_quest", action, level="info", **fields)


def cfg() -> dict:
    return wp._load_json("lore_quests.json")


def const(name: str) -> int:
    return int(cfg()["constants"][name])


def _fold(text: object) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _day(state: dict) -> int:
    return int((((state or {}).get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)


def _cur(state: dict) -> str:
    return str((((state or {}).get("world") or {}).get("current_location_id")) or "")


def _loc_name(lid: str) -> str:
    return str((wp._map_index()[0].get(lid) or {}).get("name") or "")


def _item_name(item_id: str) -> str:
    import gamedata

    return str((gamedata.ARTIFACTS_DB.get(item_id) or {}).get("name") or item_id)


def _rumor_api() -> Any:
    from services import world_quests

    return world_quests._rumor_api()


# --- NPC de origem -----------------------------------------------------------------


def _npc(state: dict, npc_key: str) -> tuple[str, dict]:
    from services import npc_world

    return npc_world._row_for(state, npc_key)


def origin_ref(state: dict, npc_key: str) -> str:
    from services import npc_world

    key, row = _npc(state, npc_key)
    return npc_world.npc_ref(key or npc_key, row) if (key or npc_key) else ""


def _npc_here(state: dict, npc_key: str) -> bool:
    _key, row = _npc(state, npc_key)
    if not row or not row.get("in_scene"):
        return False
    from services.npc_layers import npc_alive

    return bool(npc_alive(row))


# --- bloqueios / anti-farm (R10, R16-R18) -------------------------------------------


def lore_active(quests: list[dict]) -> list[dict]:
    return [
        q for q in quests or [] if q.get("world_kind") in LORE_KINDS and q.get("status") == "active"
    ]


def on_cooldown(state: dict, kind: str, anchor: dict, origin_key: str, day: int) -> str:
    """ "" = livre; senao o motivo. Tudo em DIAS do `world_clock` (nunca turnos)."""
    c = cfg()["constants"]
    for q in (state or {}).get("quests") or []:
        if q.get("world_kind") not in LORE_KINDS:
            continue
        qa = q.get("lore_anchor") or {}
        same_anchor = (
            qa.get("type") == anchor.get("type")
            and qa.get("id") == anchor.get("id")
            and (kind != "cacar_criatura" or q.get("region_id") == anchor.get("region_id"))
        )
        if same_anchor and q.get("status") == "active":
            return "anchor_active"
        created = int(q.get("created_day", 0) or 0)
        if (
            origin_key
            and origin_key != "engine"
            and q.get("lore_origin_key") == origin_key
            and day - created < int(c["ORIGIN_COOLDOWN_DAYS"])
        ):
            return "origin_cooldown"
        resolved = int(q.get("resolved_day", 0) or 0)
        if same_anchor and resolved and day - resolved < int(c["ANCHOR_COOLDOWN_DAYS"]):
            return "anchor_cooldown"
    return ""


def cap_reached(state: dict) -> bool:
    return len(lore_active((state or {}).get("quests") or [])) >= MAX_LORE_QUESTS_ACTIVE


# --- prazo e recompensa (R14/R15) ----------------------------------------------------


def _days(periods: int | None) -> int:
    return max(1, math.ceil(int(periods or 0) / PERIODS_PER_DAY))


def deadline_for(state: dict, kind: str, anchor: dict, day: int) -> int:
    """Prazo por regra do template; nunca le o heroi (R13)."""
    c = cfg()["constants"]
    day = int(day)
    if kind == "cacar_criatura":
        return day + int(c["HUNT_DAYS"])
    if kind == "entregar_material":
        return day + _days(anchor.get("periods")) * 2 + int(c["DELIVERY_SLACK"])
    if kind == "escoltar":
        return day + _days(anchor.get("periods")) + int(c["ESCORT_SLACK"])
    if kind == "investigar_rumor":
        base = day + int(c["RUMOR_DAYS"])
        ttl = anchor.get("ttl_day")
        return min(base, int(ttl)) if ttl is not None else base
    return day + int(c["BODIES_DAYS"])  # recolher_mortos


def reward_for(kind: str, anchor: dict, origin_key: str) -> tuple[int, str]:
    """(ouro planejado INTERNO, rotulo em palavras). Banda de distancia em dias de viagem."""
    table = cfg()["rewards"]
    if kind == "cacar_criatura":
        gold = int(table[kind].get(str(anchor.get("categoria")), 0))
    elif kind in ("entregar_material", "escoltar"):
        d = _days(anchor.get("periods"))
        gold = int(table[kind][0 if d <= 1 else (1 if d <= 3 else 2)])
    elif kind == "investigar_rumor":
        gold = int(table[kind]["engine" if origin_key == "engine" else "npc"])
    else:
        gold = int(table.get(kind, 0))
    return gold, str(cfg()["reward_labels"].get(str(gold), ""))


# --- menu de ancoras (R11) ------------------------------------------------------------


def _allowed_cats() -> set[str]:
    return {str(c) for c in cfg()["allowed_hunt_categories"]}


def _hunt_ok(enemy_id: str, region: str) -> dict | None:
    import gamedata
    from encounter_budget import is_boss

    e = (gamedata.BESTIARY or {}).get(enemy_id)
    if not e or is_boss(e) or str(e.get("categoria")) not in _allowed_cats():
        return None
    return e if region in (e.get("regions") or []) else None


def _route(route_id: str) -> dict | None:
    return next((r for r in cfg()["delivery_routes"] if r.get("id") == route_id), None)


def _route_valid(r: dict) -> bool:
    import gamedata

    art = gamedata.ARTIFACTS_DB.get(str(r.get("item_id")))
    return bool(art and art.get("type") == "material" and gamedata.get_location(str(r.get("to"))))


def _patron_match(state: dict, npc_key: str, route: dict) -> bool:
    key, row = _npc(state, npc_key)
    from services import npc_world

    ref = npc_world.npc_ref(key or npc_key, row)
    hay = _fold(" ".join([str(row.get("role") or ""), ref, npc_world.npc_faction(state, ref)]))
    return any(_fold(t) in hay for t in route.get("patron_tags") or [])


def _escort_ok(state: dict, npc_key: str) -> bool:
    from services import npc_world

    if npc_world.mode() != "on" or not _npc_here(state, npc_key):
        return False
    ref = origin_ref(state, npc_key)
    entry = ((state.get("npc_sim") or {}).get("npcs") or {}).get(ref) or {}
    if not entry or entry.get("escort") or entry.get("dead") or entry.get("status") == "capturado":
        return False
    if entry.get("archetype") not in cfg()["escort_archetypes"]:
        return False
    return str((entry.get("pos") or {}).get("location_id") or "") == _cur(state)


def _hunt_anchor(enemy_id: str, region: str) -> dict:
    return {"type": "enemy", "id": enemy_id, "region_id": region}


def anchor_menu(state: dict, npc_key: str) -> tuple[str, list[dict]]:
    """`(bloco, itens)`. Bloco vazio se nada elegivel ou modo != on. Nunca inclui verdade de
    rumor, numero, perigo ou fraqueza (R11)."""
    m = mode()
    if m == "off" or not _npc_here(state, npc_key):
        return "", []
    from services import ecology

    day, cur = _day(state), _cur(state)
    region = wp.region_of(cur)
    origin = origin_ref(state, npc_key)
    maxn = const("MENU_MAX_PER_KIND")
    items: list[dict] = []

    def free(kind: str, anchor: dict) -> bool:
        return not on_cooldown(state, kind, anchor, origin, day)

    import gamedata

    hunts = []
    for e in (gamedata.BESTIARY or {}).values():
        eid = str(e.get("id") or "")
        if eid and _hunt_ok(eid, region) and free("cacar_criatura", _hunt_anchor(eid, region)):
            hunts.append(e)
    bk = state.get("bestiary_knowledge")
    turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    hunts.sort(key=lambda e: (-ecology.hunt_pressure(e["id"], bk, turn), e["id"]))
    for e in hunts[:maxn]:
        items.append(
            {
                "kind": "cacar_criatura",
                "anchor_id": e["id"],
                "label": f"{e.get('name')} anda rondando a região",
            }
        )
    for r in cfg()["delivery_routes"][:maxn]:
        if (
            r.get("origin_region") == region
            and _route_valid(r)
            and _patron_match(state, npc_key, r)
            and free("entregar_material", {"type": "route", "id": r["id"]})
        ):
            items.append(
                {
                    "kind": "entregar_material",
                    "anchor_id": r["id"],
                    "label": f"levar {r['qty']} {_item_name(r['item_id'])} a {_loc_name(r['to'])}",
                }
            )
    if _escort_ok(state, npc_key) and free("escoltar", {"type": "npc", "id": origin}):
        from services import npc_world

        for dest in npc_world.escort_destinations(state, origin)[:2]:
            items.append(
                {
                    "kind": "escoltar",
                    "anchor_id": f"{origin}|{dest}",
                    "label": f"quer ser escoltado até {_loc_name(dest)}",
                }
            )
    api = _rumor_api()
    if api is not None:
        n = 0
        for row in api.investigable(state, day):
            if n >= 2:
                break
            if wp.region_of(str(row.get("location_id") or "")) != region:
                continue
            if not free("investigar_rumor", {"type": "rumor", "id": row["rumor_id"]}):
                continue
            items.append(
                {
                    "kind": "investigar_rumor",
                    "anchor_id": str(row["rumor_id"]),
                    "label": rumor_public_text(state, str(row["rumor_id"])),
                }
            )
            n += 1
    if m == "shadow":  # R32: calcula e loga; nao emite o menu (a LLM nunca ancora)
        if items:
            _log("shadow_offer", kind="menu", channel="npc", count=len(items))
        return "", []
    items = _interleave(items)
    while items:
        block = _render_menu(items)
        if estimate_tokens(block) <= MENU_TOKEN_BUDGET:
            return block, items
        items = items[:-1]  # orcamento do prompt: descarta o fim da lista
    return "", []


MENU_TOKEN_BUDGET = 150


def _interleave(items: list[dict]) -> list[dict]:
    """Um de cada tipo por vez: o corte de orcamento nao elimina um tipo inteiro."""
    buckets: dict[str, list[dict]] = {}
    for i in items:
        buckets.setdefault(i["kind"], []).append(i)
    out: list[dict] = []
    while any(buckets.values()):
        for rows in buckets.values():
            if rows:
                out.append(rows.pop(0))
    return out


def estimate_tokens(text: str) -> int:
    from services.context_builder import estimate_tokens as _est

    return _est(text)


def _render_menu(items: list[dict]) -> str:
    lines = [
        "<GANCHOS_POSSIVEIS>",
        "Se oferecer uma dessas tarefas, use o kind e o anchor_id EXATOS. "
        "Não diga prazo nem valor: o mundo decide.",
    ]
    lines += [f"- kind={i['kind']} anchor_id={i['anchor_id']} ({i['label']})" for i in items]
    lines.append("</GANCHOS_POSSIVEIS>")
    return "\n".join(lines)


def rumor_public_text(state: dict, rumor_id: str) -> str:
    """Texto PUBLICO do rumor (nunca `truth`). Vazio se o modulo da 312 nao existe."""
    try:
        from services import rumors

        return rumors.text_for(state, rumor_id)
    except Exception as exc:  # silent-ok: rumor sem texto => descricao generica do template
        from observability.telemetry import log_fallback

        log_fallback("lore_quests", "rumor_text_failed", exc)
        return ""


# --- validacao da ancora (R3) ----------------------------------------------------------


def validate_anchor(
    state: dict,
    kind: str,
    anchor_id: str,
    npc_key: str,
    menu: list[dict],
    location_id: str = "",
) -> tuple[bool, str]:
    """A ancora so vale se estava no menu E passa nas regras do tipo. Nunca levanta."""
    if kind not in NPC_PROPOSABLE:
        return False, "bad_kind"
    if not any(i.get("kind") == kind and i.get("anchor_id") == anchor_id for i in menu or []):
        return False, "not_in_menu"
    cur = location_id or _cur(state)
    region = wp.region_of(cur)
    if kind == "cacar_criatura":
        return (True, "") if _hunt_ok(anchor_id, region) else (False, "invalid_anchor")
    if kind == "entregar_material":
        from services import world_distance

        r = _route(anchor_id)
        if not r or r.get("origin_region") != region or not _route_valid(r) or r["to"] == cur:
            return False, "invalid_anchor"
        p = world_distance.travel_periods(cur, r["to"])
        if p is None or p < const("DELIVERY_MIN_PERIODS"):
            return False, "invalid_anchor"
        return True, ""
    if kind == "escoltar":
        from services import npc_world

        ref, _sep, dest = anchor_id.partition("|")
        if ref != origin_ref(state, npc_key) or not _escort_ok(state, npc_key):
            return False, "invalid_anchor"
        return (
            (True, "")
            if dest in npc_world.escort_destinations(state, ref)
            else (False, "invalid_anchor")
        )
    api = _rumor_api()
    if api is None:
        return False, "invalid_anchor"
    ok = any(r.get("rumor_id") == anchor_id for r in api.investigable(state, _day(state)))
    return (True, "") if ok else (False, "invalid_anchor")


# --- guarda de texto (R8) ----------------------------------------------------------------


def _names_index() -> list[str]:
    import gamedata

    names = [str(e.get("name") or "") for e in (gamedata.BESTIARY or {}).values()]
    names += [str(a.get("name") or "") for a in (gamedata.ARTIFACTS_DB or {}).values()]
    names += [str(loc.get("name") or "") for loc in wp._map_index()[0].values()]
    return sorted({_fold(n) for n in names if len(n) >= 5})


def safe_llm_text(state: dict, text: str, anchor_names: set[str], max_len: int) -> str:
    """ "" = use o template. Reprova: vazio/longo, numero de tempo/dinheiro, faccao que o
    jogador nao conhece, ou nome de criatura/item/local diferente da ancora."""
    t = " ".join(str(text or "").split())
    if not t or len(t) > max_len or _TIME_OR_MONEY.search(t):
        return ""
    folded = _fold(t)
    import gamedata
    from world_utils import unknown_faction_names

    ids = {str(f.get("id")) for f in (state.get("factions") or []) if isinstance(f, dict)}
    ids |= set(gamedata.FACTIONS)
    for fname in unknown_faction_names(
        sorted(ids), state.get("factions"), state.get("faction_intel")
    ):
        if _fold(fname) in folded:
            return ""
    allowed = {_fold(n) for n in anchor_names if n}
    for name in _names_index():
        if name in folded and not any(name in a or a in name for a in allowed):
            return ""
    return t


# --- semente a partir da proposta (R5-R9, R12-R17) -------------------------------------------


def _get(p: Any, key: str, default: Any = "") -> Any:
    if isinstance(p, dict):
        return p.get(key, default)
    return getattr(p, key, default)


def seed_for_proposal(
    state: dict, proposal: Any, npc_key: str, menu: list[dict], day: int
) -> tuple[Any, str]:
    """`(QuestSeed | None, motivo)`. Motivo "" = aceita. Nunca levanta."""
    from services import world_distance
    from services.world_quests import QuestSeed

    kind = str(_get(proposal, "kind", "comum") or "comum")
    aid = str(_get(proposal, "anchor_id", ""))
    ok, why = validate_anchor(state, kind, aid, npc_key, menu)
    if not ok:
        return None, why
    origin = origin_ref(state, npc_key)
    cur = _cur(state)
    region = wp.region_of(cur)
    base: dict[str, Any] = {"origin_key": origin, "region_id": region}
    anchor: dict[str, Any]
    names: set[str] = {_loc_name(cur)}
    if kind == "cacar_criatura":
        e = _hunt_ok(aid, region) or {}
        anchor = {
            "type": "enemy",
            "id": aid,
            "region_id": region,
            "categoria": str(e.get("categoria")),
        }
        names.add(str(e.get("name") or ""))
        base.update(
            world_source_id=f"hunt:{aid}:{region}:{origin}",
            location_id=cur,
            enemy_id=aid,
            anchor_label=str(e.get("name") or "a fera"),
        )
    elif kind == "entregar_material":
        r = _route(aid) or {}
        periods = world_distance.travel_periods(cur, r["to"])
        anchor = {
            "type": "route",
            "id": aid,
            "item_id": r["item_id"],
            "qty": int(r["qty"]),
            "to": r["to"],
            "periods": periods,
        }
        names |= {_item_name(r["item_id"]), _loc_name(r["to"])}
        base.update(
            world_source_id=f"deliv:{aid}:{origin}",
            location_id=r["to"],
            other_location_id=cur,
            region_id=wp.region_of(r["to"]),
            route_id=aid,
            item_id=r["item_id"],
            qty=int(r["qty"]),
            to_location_id=r["to"],
            anchor_label=f"{r['qty']} {_item_name(r['item_id'])}",
        )
    elif kind == "escoltar":
        ref, _sep, dest = aid.partition("|")
        periods = world_distance.travel_periods(cur, dest)
        anchor = {"type": "npc", "id": ref, "to": dest, "periods": periods}
        names.add(_loc_name(dest))
        base.update(
            world_source_id=f"escort:{ref}:{dest}:{day}",
            location_id=dest,
            other_location_id=cur,
            escort_npc_key=npc_key,
            npc_id=ref,
            to_location_id=dest,
        )
    else:  # investigar_rumor (origem NPC)
        api = _rumor_api()
        row = next((r for r in api.investigable(state, day) if r.get("rumor_id") == aid), {})
        loc = str(row.get("location_id") or "")
        anchor = {"type": "rumor", "id": aid, "ttl_day": row.get("expires_day")}
        base.update(
            world_source_id=f"rumor:{aid}",
            location_id=loc,
            region_id=wp.region_of(loc),
            rumor_id=aid,
            rumor_text=rumor_public_text(state, aid),
        )
    blocked = on_cooldown(state, kind, anchor, origin, day)
    if blocked:
        return None, blocked
    if cap_reached(state):
        return None, "cap"
    gold, label = reward_for(kind, anchor, origin)
    title = safe_llm_text(state, str(_get(proposal, "title")), names, 90)
    desc = safe_llm_text(state, str(_get(proposal, "description")), names, 400)
    seed_anchor = {k: v for k, v in anchor.items() if k not in ("periods", "ttl_day", "categoria")}
    seed = QuestSeed(
        kind=kind,
        deadline_day=deadline_for(state, kind, anchor, day),
        reward_gold=gold,
        reward_label=label,
        llm_title=title,
        llm_description=desc,
        anchor=seed_anchor,
        **base,
    )
    return seed, ""


def seed_from_proposal(
    state: dict, proposal: dict, npc_key: str, menu: list[dict], day: int
) -> Any:
    seed, _why = seed_for_proposal(state, proposal, npc_key, menu, day)
    return seed


# --- ganchos de jogo ---------------------------------------------------------------------------


def active_hunt_anchor(state: dict) -> str:
    """Âncora da caça ativa na regiao do jogador ("" se nenhuma). Pura (R26)."""
    if mode() != "on":
        return ""
    region = wp.region_of(_cur(state))
    for q in (state or {}).get("quests") or []:
        if (
            q.get("world_kind") == "cacar_criatura"
            and q.get("status") == "active"
            and (q.get("lore_anchor") or {}).get("region_id") == region
        ):
            return str((q.get("lore_anchor") or {}).get("id") or "")
    return ""


def outcome_label(quest: dict) -> str:
    """Rotulo publico do desfecho do rumor; so depois de concluida (R28)."""
    if quest.get("world_kind") != "investigar_rumor" or quest.get("status") != "completed":
        return ""
    return {
        "confirmado": "confirmado",
        "desmentido": "era só boato",
        "inconclusivo": "sem conclusão",
    }.get(str(quest.get("outcome")), "")


def desfecho_block(state: dict) -> str:
    """`<DESFECHO_DE_QUEST>` para o narrador, so no turno seguinte a conclusao (R23)."""
    turn = int(((state or {}).get("world") or {}).get("turn_count", 0) or 0)
    lines = []
    for q in (state or {}).get("quests") or []:
        if (
            q.get("world_kind") == "investigar_rumor"
            and q.get("status") == "completed"
            and int(q.get("resolved_turn", 0) or 0) >= turn - 1
            and q.get("outcome") in ("confirmado", "desmentido", "inconclusivo")
        ):
            lines.append(
                {
                    "confirmado": "o que diziam se confirma",
                    "desmentido": "era só boato: ninguém viu nada disso",
                    "inconclusivo": "não se achou nada que confirme ou desminta a história",
                }[q["outcome"]]
            )
    if not lines:
        return ""
    return "<DESFECHO_DE_QUEST>\n" + "\n".join(f"- {t}" for t in lines) + "\n</DESFECHO_DE_QUEST>"


def resolve_rumor_outcome(state: dict, quest: dict, day: int) -> tuple[str, dict]:
    """Gancho unico da conclusao de `investigar_rumor` (e de qualquer quest de investigacao
    futura que reuse a interface da SPEC-312): le a verdade SO aqui e devolve
    `(outcome, world_sim novo)` com `outcome` em confirmado|desmentido|inconclusivo.
    Boato NUNCA vira fato (quem fecha o rumor e `rumors.mark_resolved`, que so grava a resolucao)."""
    sim = (state or {}).get("world_sim") or {}
    api = _rumor_api()
    rid = str((quest.get("lore_anchor") or {}).get("id") or "")
    if api is None or not rid:
        return "inconclusivo", sim
    truth = api.truth_of(state, rid)
    outcome = "inconclusivo" if truth is None else ("confirmado" if truth else "desmentido")
    return outcome, api.mark_resolved(sim, rid, outcome, int(day))
