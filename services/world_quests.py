"""SPEC-305: quests de mundo com prazo (nascem do estado do motor, falham com consequencia).

OWNER CANONICO da CRIACAO e do PRAZO de quests com `world_kind` (nenhum outro modulo monta
esses dicts). Tudo e Python puro e deterministico: titulo, descricao e texto de falha vem de
templates (`data/world/world_quests.json`); a LLM so narra a cena em que o gancho aparece.

Principios (R4/R5/R18):
- fontes (crise anunciada/aberta, local ocupado, rota fechada, objeto unico em maos de faccao,
  NPC em perigo) e prazos NUNCA leem o heroi (nivel, ficha, ouro, party); a posicao do
  jogador so decide PERCEPCAO e VIABILIDADE;
- so nasce quest do que o jogador VIU ou OUVIU (testemunho, cartaz, NPC, rumor, mensageiro),
  com a prova gravada em `heard_via`;
- o motor segue o que ja tinha decidido (escalada, ocupacao, destino do NPC): a falha so
  muda o status da quest e usa texto neutro, sem revelar o desfecho.

Modos `RPG_WORLD_QUESTS=off|shadow|on` (so `on` com `RPG_WORLD_ENGINE=on`).
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass, field
from typing import Any

from services import world_director as wd
from services import world_pressures as wp

MODES = ("off", "shadow", "on")
DEFAULT_MODE = "on"
MAX_WORLD_QUESTS_ACTIVE = 3
PERIODS_PER_DAY = 5  # len(world_utils.PERIODS)

_CRISIS_KIND = {
    "guerra": "romper_cerco",
    "fome": "socorrer_escassez",
    "praga": "conter_praga",
    "abismo": "selar_corrupcao",
    "ascensao": "frear_ascensao",
}
CRISIS_QUEST_KINDS = frozenset(_CRISIS_KIND.values())
_BAD_CRISIS_RESOLUTIONS = frozenset({"escalou"})
_MORTOS_TEMPLATES = frozenset({"ruina.crise.escala", "praga.crise.escala"})


# --- catalogo ----------------------------------------------------------------------


def _cfg() -> dict:
    return wp._load_json("world_quests.json")


def _const(name: str) -> int:
    return int(_cfg()["constants"][name])


def kind_cfg(kind: str) -> dict:
    return dict((_cfg().get("kinds") or {}).get(str(kind), {}))


def action_vocab(kind: str) -> list[str]:
    return [str(s) for s in kind_cfg(kind).get("action_vocab", [])]


def combat_counts(kind: str) -> bool:
    return bool(kind_cfg(kind).get("combat_counts"))


def mode() -> str:
    """`RPG_WORLD_QUESTS`; so vale `on`/`shadow` com o motor de mundo em `on` (R26)."""
    raw = os.getenv("RPG_WORLD_QUESTS", "").strip().lower()
    m = raw if raw in MODES else DEFAULT_MODE
    from services import world_engine

    return m if world_engine.mode() == "on" else "off"


def _log(action: str, **fields: Any) -> None:
    from observability.telemetry import log_event

    log_event("world_quest", action, level="info", **fields)


# --- primitivos --------------------------------------------------------------------


@dataclass(frozen=True)
class QuestSeed:
    kind: str
    world_source_id: str
    region_id: str
    location_id: str
    deadline_day: int
    source_event_id: str = ""
    faction_id: str = ""
    npc_id: str = ""
    other_location_id: str = ""
    crisis_kind: str = ""
    item_id: str = ""
    provisional: bool = False
    origin_faction_id: str = ""
    # --- SPEC-313: quests ancoradas em lore (INTERNO; vazio nas 9 quests de crise)
    enemy_id: str = ""
    route_id: str = ""
    rumor_id: str = ""
    escort_npc_key: str = ""
    qty: int = 0
    reward_gold: int = 0
    reward_label: str = ""
    llm_title: str = ""
    llm_description: str = ""
    origin_key: str = ""
    to_location_id: str = ""
    anchor_label: str = ""
    rumor_text: str = ""
    anchor: dict = field(default_factory=dict)


def quest_id(game_id: str, kind: str, world_source_id: str) -> str:
    """R3: id deterministico (replay gera o mesmo id)."""
    raw = f"{game_id}|{kind}|{world_source_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _day(state: dict) -> int:
    return int((((state or {}).get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)


def _turn(state: dict) -> int:
    return int((((state or {}).get("world") or {}).get("turn_count", 0)) or 0)


def _cur(state: dict) -> str:
    return str((((state or {}).get("world") or {}).get("current_location_id")) or "")


def _loc_name(lid: str) -> str:
    locs = wp._map_index()[0]
    return str((locs.get(lid) or {}).get("name") or wp.region_label(wp.region_of(lid)) or "")


def _faction_dict(state: dict, fid: str) -> dict:
    for f in (state or {}).get("factions") or []:
        if isinstance(f, dict) and f.get("id") == fid:
            return f
    import gamedata

    return dict(gamedata.FACTIONS.get(fid) or {})


def _faction_ids(state: dict) -> set[str]:
    import gamedata

    ids = {str(f.get("id")) for f in (state or {}).get("factions") or [] if isinstance(f, dict)}
    return {i for i in ids | set(gamedata.FACTIONS) if i}


def _item_name(item_id: str) -> str:
    import gamedata

    return str((gamedata.ARTIFACTS_DB.get(item_id) or {}).get("name") or "o objeto")


def projection_after(state: dict, events: list[dict], day: int) -> dict:
    """Projection com os eventos do motor deste tick JA aplicados (o archivist so os aplica
    no fim do turno; a oferta do mesmo tick precisa enxerga-los). Puro."""
    from services.event_processor import apply_event

    proj = dict((state or {}).get("world_projection") or {})
    for ev in events or []:
        proj.update(apply_event({**ev, "turn": day}, proj))
    return proj


# --- candidatas (R1) ---------------------------------------------------------------


def _crisis_seeds(sim: dict, day: int) -> list[QuestSeed]:
    dc = wp.director_constants()
    out: list[QuestSeed] = []
    for rec in sim.get("crises") or []:
        if rec.get("end_day") is not None or rec.get("relieved_day") is not None:
            continue
        kind = _CRISIS_KIND.get(str(rec.get("kind")))
        if not kind:
            continue
        opened = rec.get("start_day") is not None
        warned = int(rec.get("warned_day", day))
        provisional = False
        if rec["kind"] == "ascensao":
            if opened:
                continue  # ja aconteceu: nao ha mais o que frear
            deadline = warned + _const("ASCENSION_WINDOW")
        elif opened:
            deadline = int(rec.get("escalation_day") or warned)
        else:
            deadline = warned + int(dc["MIN_WARNING_DAYS"]) + int(dc["ESCALATION_DAYS"])
            provisional = True
        loc = str(rec.get("location_id") or "") or wp.region_primary_location(rec["region_id"])
        if not loc:
            continue
        out.append(
            QuestSeed(
                kind=kind,
                world_source_id=str(rec["crisis_id"]),
                region_id=str(rec["region_id"]),
                location_id=loc,
                deadline_day=deadline,
                faction_id=str(rec.get("faction_id") or ""),
                crisis_kind=str(rec["kind"]),
                provisional=provisional,
            )
        )
    return out


def _occupation_seeds(proj: dict) -> list[QuestSeed]:
    out: list[QuestSeed] = []
    for lid, row in sorted((proj.get("location_states") or {}).items()):
        if (row or {}).get("state") != "ocupado":
            continue
        since = int(row.get("since_day", 0) or 0)
        out.append(
            QuestSeed(
                kind="libertar_ocupado",
                world_source_id=f"occ:{lid}:{since}",
                region_id=wp.region_of(lid),
                location_id=str(lid),
                deadline_day=since + _const("OCCUPATION_WINDOW"),
                faction_id=str(row.get("faction_id") or ""),
                origin_faction_id=str(row.get("prev_controller") or ""),
            )
        )
    return out


def _route_seeds(sim: dict, proj: dict, day: int) -> list[QuestSeed]:
    siege = {
        frozenset(rec["route"])
        for rec in sim.get("crises") or []
        if rec.get("route") and rec.get("end_day") is None
    }
    out: list[QuestSeed] = []
    for r in proj.get("blocked_routes") or []:
        a, b = str(r.get("a") or ""), str(r.get("b") or "")
        if not a or not b or frozenset((a, b)) in siege:
            continue
        ev = str(r.get("blocked_by_event") or "")
        out.append(
            QuestSeed(
                kind="reabrir_rota",
                world_source_id=f"route:{a}|{b}:{ev[:8]}",
                region_id=wp.region_of(a),
                location_id=a,
                other_location_id=b,
                deadline_day=day + _const("ROUTE_WINDOW"),
                source_event_id=ev,
            )
        )
    return out


def _object_seeds(state: dict, proj: dict, day: int) -> list[QuestSeed]:
    from services import world_engine

    held_by = _faction_ids(state)
    out: list[QuestSeed] = []
    for item_id, entry in sorted((proj.get("unique_items") or {}).items()):
        holder = str((entry or {}).get("holder") or "")
        if holder not in held_by:
            continue
        region = world_engine.faction_region_id(_faction_dict(state, holder)) or ""
        loc = wp.region_primary_location(region) if region else ""
        if not loc:
            continue
        ev = str(entry.get("event_id") or "")
        out.append(
            QuestSeed(
                kind="recuperar_objeto",
                world_source_id=f"obj:{item_id}:{ev[:8]}",
                region_id=region,
                location_id=loc,
                deadline_day=day + _const("OBJECT_WINDOW"),
                source_event_id=ev,
                faction_id=holder,
                item_id=str(item_id),
            )
        )
    return out


def _peril_api() -> Any:
    """SPEC-304 (`services.npc_world`) ainda pode nao existir: `resgate` fica desligado."""
    try:
        from services import npc_world
    except ImportError:
        return None
    return npc_world if hasattr(npc_world, "active_perils") else None


def _perils(state: dict) -> list[dict]:
    api = _peril_api()
    if api is None:
        return []
    try:
        return [p for p in api.active_perils(state) if isinstance(p, dict)]
    except Exception as exc:  # silent-ok: SPEC-304 indisponivel => resgate desligado
        from observability.telemetry import log_fallback

        log_fallback("world_quests", "peril_api_failed", exc)
        return []


def _peril_seeds(state: dict) -> list[QuestSeed]:
    out: list[QuestSeed] = []
    for p in _perils(state):
        if p.get("resolution"):
            continue
        loc = str(p.get("held_at_location_id") or p.get("location_id") or "")
        pid = str(p.get("peril_id") or "")
        if not loc or not pid or p.get("deadline_day") is None:
            continue
        out.append(
            QuestSeed(
                kind="resgate",
                world_source_id=pid,
                region_id=str(p.get("region_id") or wp.region_of(loc)),
                location_id=loc,
                deadline_day=int(p["deadline_day"]),
                source_event_id=str(p.get("event_id") or pid),
                npc_id=str(p.get("npc_id") or ""),
            )
        )
    return out


def _rumor_api() -> Any:
    """SPEC-312 (`services.rumors`): sem `investigable/truth_of/mark_resolved` o tipo
    `investigar_rumor` fica desligado (fora do menu e de `candidates`)."""
    try:
        from services import rumors
    except ImportError:
        return None
    ok = all(hasattr(rumors, n) for n in ("investigable", "truth_of", "mark_resolved"))
    return rumors if ok else None


def _rumor_seeds(state: dict, day: int) -> list[QuestSeed]:
    """SPEC-313 R23 (origem motor): rumor PERCEBIDO e `quest_eligible` vira candidata; falso
    e verdadeiro sao indistinguiveis aqui (a verdade so existe na conclusao)."""
    api = _rumor_api()
    if api is None:
        return []
    from services import lore_quests as lq

    out: list[QuestSeed] = []
    for row in api.investigable(state, day):
        loc = str(row.get("location_id") or "")
        rid = str(row.get("rumor_id") or "")
        if not loc or not rid or not wp._map_index()[0].get(loc):
            continue
        anchor = {"type": "rumor", "id": rid, "ttl_day": row.get("expires_day")}
        gold, label = lq.reward_for("investigar_rumor", anchor, "engine")
        out.append(
            QuestSeed(
                kind="investigar_rumor",
                world_source_id=f"rumor:{rid}",
                region_id=wp.region_of(loc),
                location_id=loc,
                deadline_day=lq.deadline_for(state, "investigar_rumor", anchor, day),
                rumor_id=rid,
                rumor_text=lq.rumor_public_text(state, rid),
                origin_key="engine",
                reward_gold=gold,
                reward_label=label,
                anchor={"type": "rumor", "id": rid},
            )
        )
    return out


def _dead_seeds(sim: dict, day: int) -> list[QuestSeed]:
    """SPEC-313 R24: guerra/praga que escalou deixa corpos (uma quest por crise)."""
    from services import lore_quests as lq

    out: list[QuestSeed] = []
    for rec in sim.get("crises") or []:
        if rec.get("kind") not in ("guerra", "praga"):
            continue
        if not (rec.get("resolution") == "escalou" or int(rec.get("severity", 0) or 0) >= 2):
            continue
        loc = str(rec.get("location_id") or "") or wp.region_primary_location(rec["region_id"])
        if not loc:
            continue
        gold, label = lq.reward_for("recolher_mortos", {}, "engine")
        cid = str(rec["crisis_id"])
        out.append(
            QuestSeed(
                kind="recolher_mortos",
                world_source_id=f"mortos:{cid}",
                region_id=str(rec["region_id"]),
                location_id=loc,
                deadline_day=lq.deadline_for({}, "recolher_mortos", {}, day),
                crisis_kind=str(rec["kind"]),
                origin_key="engine",
                reward_gold=gold,
                reward_label=label,
                anchor={"type": "crisis", "id": cid},
            )
        )
    return out


def candidates(state: dict, day: int) -> list[QuestSeed]:
    """R1: fontes ativas no estado do motor, SEM percepcao (R4: nada do heroi)."""
    sim = (state or {}).get("world_sim") or {}
    proj = (state or {}).get("world_projection") or {}
    seeds = [
        *_crisis_seeds(sim, day),
        *_occupation_seeds(proj),
        *_route_seeds(sim, proj, day),
        *_object_seeds(state, proj, day),
        *_peril_seeds(state),
    ]
    from services import lore_quests as lq

    if lq.mode() != "off":  # SPEC-313: fontes do motor (rumor percebido, corpos)
        seeds += [*_rumor_seeds(state, day), *_dead_seeds(sim, day)]
    return sorted(seeds, key=lambda s: (s.deadline_day, s.world_source_id))


# --- viabilidade (R8) --------------------------------------------------------------


def _distance(state: dict, target: str) -> int | None:
    from services import world_distance

    return world_distance.travel_periods(_cur(state), target)


def is_feasible(state: dict, target_location_id: str, deadline_day: int, day: int) -> bool:
    """R8 (D2): so oferece o que da tempo de alcançar antes do prazo."""
    periods = _distance(state, target_location_id)
    if periods is None:
        return False
    return int(day) + math.ceil(periods / PERIODS_PER_DAY) < int(deadline_day)


# --- texto (templates; R18) --------------------------------------------------------


def _npc_label(state: dict, npc_id: str, fallback: str = "alguém") -> str:
    for key, npc in ((state or {}).get("npcs") or {}).items():
        if isinstance(npc, dict) and npc_id and npc.get("id") == npc_id:
            if npc.get("known_by_player", True):
                return str(npc.get("name") or key)
    return fallback


def render_quest_text(
    state: dict, seed: QuestSeed, channel: str, origin: str = ""
) -> dict[str, str]:
    """Titulo, descricao e texto de falha por template; faccao so se conhecida (R24 da 302)."""
    from services import world_perception as wperc

    cfg = kind_cfg(seed.kind)
    tpls = cfg.get("description") or {}
    tpl = tpls.get(channel) or tpls.get("npc") or tpls.get("testemunho") or ""
    npc_name = origin or (_npc_label(state, seed.npc_id) if seed.npc_id else "alguém")
    rumor = seed.rumor_text or "Dizem que algo anda acontecendo por lá."
    values = {
        "criatura": seed.anchor_label or "a fera",
        "material": seed.anchor_label or "a encomenda",
        "rumor": rumor,
        "rumor_curto": rumor.rstrip(".!? ")[:70],
        "local": _loc_name(seed.location_id) or "o lugar",
        "local_b": _loc_name(seed.other_location_id) or "o outro lado",
        "faccao": wperc._faction_label(state, seed.faction_id),
        "regiao": wp.region_label(seed.region_id) or "a região",
        "origem": npc_name or "alguém",
        "objeto": _item_name(seed.item_id) if seed.item_id else "o objeto",
    }

    def fill(text: str) -> str:
        for key, val in values.items():
            text = text.replace("{" + key + "}", val)
        return text

    return {
        "title": fill(str(cfg.get("title", ""))),
        "description": fill(str(tpl)),
        "fail_text": fill(str(cfg.get("fail_text", ""))),
        "reward_hint": "",
    }


# --- percepcao (R5/R6) -------------------------------------------------------------


def _heard(state: dict, loc: str) -> set[str]:
    return set(((state or {}).get("location_heard") or {}).get(loc, []) or [])


def _rumor_enabled() -> bool:
    from services import npc_knowledge

    return npc_knowledge.mode() == "on"


def _active_npc_name(state: dict) -> str:
    name = str((state or {}).get("active_npc_name") or "")
    npc = ((state or {}).get("npcs") or {}).get(name)
    return name if name and isinstance(npc, dict) and npc.get("in_scene") else ""


def _item_matches(seed: QuestSeed, item: dict) -> bool:
    from services import rumors

    if rumors.is_rumor_item(item):  # SPEC-312 R11: boato nunca e causa de quest de mundo
        return False
    tid = str(item.get("template_id") or "")
    prefix = tid.split(".")[0]
    kind = str(item.get("kind") or "")
    if seed.kind == "resgate":  # SPEC-304: o telegrama do perigo (rumor ou mensageiro)
        return (
            kind == "npc_perigo"
            and bool(seed.npc_id)
            and str((item.get("params") or {}).get("npc_id") or "") == seed.npc_id
        )
    if seed.kind == "recolher_mortos":  # SPEC-313 R24: so o que o heroi percebeu da escalada
        return tid in _MORTOS_TEMPLATES and item.get("region_id") == seed.region_id
    if seed.kind == "libertar_ocupado":
        return tid == "ocupado.crise.escala" and item.get("location_id") == seed.location_id
    if seed.kind == "frear_ascensao":
        return (
            prefix == "ascensao"
            and kind == "aviso"
            and str((item.get("params") or {}).get("faccao") or "") == seed.faction_id
        )
    if seed.crisis_kind and seed.kind in CRISIS_QUEST_KINDS:
        return (
            item.get("region_id") == seed.region_id
            and prefix == seed.crisis_kind
            and kind in ("aviso", "crise", "escala")
        )
    return False


def _seed_event_ids(state: dict, seed: QuestSeed) -> list[str]:
    """Ids de evento que provam a fonte (para o canal de rumor/NPC via `location_heard`)."""
    ids: list[str] = []
    if seed.source_event_id:
        ids.append(seed.source_event_id)
    for ev in (state or {}).get("event_log") or []:
        if not isinstance(ev, dict):
            continue
        payload = ev.get("payload") or {}
        if seed.kind == "recolher_mortos" and payload.get("crisis_id") == seed.anchor.get("id"):
            ids.append(str(ev.get("event_id") or ""))
        elif seed.kind in CRISIS_QUEST_KINDS and payload.get("crisis_id") == seed.world_source_id:
            ids.append(str(ev.get("event_id") or ""))
        elif (
            seed.kind == "libertar_ocupado"
            and ev.get("type") == "location_state_changed"
            and ev.get("target_id") == seed.location_id
            and payload.get("state") == "ocupado"
        ):
            ids.append(str(ev.get("event_id") or ""))
    for it in ((state or {}).get("world_sim") or {}).get("pending_digest") or []:
        if it.get("subject_id") and _item_matches(seed, it):
            ids.append(str(it["subject_id"]))
    return [i for i in dict.fromkeys(ids) if i]


def _is_town(loc: str) -> bool:
    tags = set((wp._map_index()[0].get(loc) or {}).get("tags") or [])
    return bool(tags & {"cidade", "vila"})


def _witness_direct(state: dict, seed: QuestSeed) -> tuple[str, str] | None:
    """Testemunho sem digest: o jogador esta na estrada fechada ou viu o objeto ser levado."""
    from services import world_perception as wperc

    cur = _cur(state)
    if not cur:
        return None
    fam = wperc._family(cur)
    if seed.kind == "reabrir_rota" and (seed.location_id in fam or seed.other_location_id in fam):
        return "testemunho", seed.source_event_id or seed.world_source_id
    if seed.kind == "recuperar_objeto" and seed.source_event_id:
        for ev in reversed((state or {}).get("event_log") or []):
            if isinstance(ev, dict) and ev.get("event_id") == seed.source_event_id:
                if int(ev.get("turn", -1) or -1) == _turn(state):
                    return "testemunho", seed.source_event_id
                break
    return None


def _resolve_channel(
    state: dict, seed: QuestSeed, perceived: list[dict] | None
) -> tuple[str, str, str] | None:
    """(canal, event_id, origem) ou None. Sem percepcao registrada nao nasce quest."""
    from services import world_perception as wperc

    if seed.kind == "investigar_rumor":  # SPEC-313: `investigable` so devolve rumor PERCEBIDO
        return ("rumor", seed.rumor_id, "") if seed.rumor_id else None
    cur = _cur(state)
    if not cur:
        return None
    fam = wperc._family(cur)
    cur_region = wp.region_of(cur)
    tpls = wperc._templates()["templates"]
    for it in perceived or []:
        if not _item_matches(seed, it):
            continue
        ref = str(it.get("subject_id") or it.get("item_id") or "")
        if it.get("location_id") in fam:
            return "testemunho", ref, ""
        regional = (tpls.get(it.get("template_id", "")) or {}).get("visibility") == "regional"
        if regional and it.get("region_id") == cur_region and _is_town(cur):
            return "cartaz", ref, ""
    direct = _witness_direct(state, seed)
    if direct:
        return direct[0], direct[1], ""
    if _rumor_enabled():
        heard = _heard(state, cur)
        for ev_id in _seed_event_ids(state, seed):
            if ev_id in heard:
                npc = _active_npc_name(state)
                return ("npc", ev_id, npc) if npc else ("rumor", ev_id, "")
    return None


# --- oferta (R7/R9) ----------------------------------------------------------------


def _active_world(quests: list[dict]) -> int:
    from services.lore_quests import LORE_KINDS

    return sum(
        1
        for q in quests
        if q.get("world_kind") and q["world_kind"] not in LORE_KINDS and q.get("status") == "active"
    )


def _bucket(left: int) -> str:
    return "urgente" if left <= 2 else ("poucos_dias" if left <= 5 else "folgado")


def _origin_faction(state: dict, seed: QuestSeed, proj: dict) -> str:
    from services import graph_resolver as gr

    if seed.origin_faction_id:
        cand = seed.origin_faction_id
    elif seed.kind in ("frear_ascensao", "recuperar_objeto", "resgate"):
        return ""
    else:
        try:
            cand = str(gr.get_current_controller(seed.location_id, proj) or "")
        except Exception:  # silent-ok: sem grafo/projection => sem fação de origem
            cand = ""
    ent = gr.get_entity(cand) if cand else None
    return cand if ent and ent.get("type") == "faction" else ""


def _build_quest(
    state: dict, seed: QuestSeed, channel: str, event_id: str, origin: str, day: int
) -> dict:
    labels = _cfg().get("origin_labels") or {}
    texts = render_quest_text(state, seed, channel, origin=origin)
    turn = _turn(state)
    quest = {
        "id": quest_id(str(state.get("game_id", "")), seed.kind, seed.world_source_id),
        "title": texts["title"],
        "description": texts["description"],
        "status": "active",
        "origin_name": origin or str(labels.get(channel, "")),
        "origin_entity_id": "",
        "location_id": seed.location_id,
        "created_turn": turn,
        "resolved_turn": 0,
        "reward_hint": texts["reward_hint"],
        "progress_log": [{"kind": "created", "turn": turn, "detail": ""}],
        "reward_gold": 0,
        "reward_delivered": False,
        "world_kind": seed.kind,
        "world_source_id": seed.world_source_id,
        "region_id": seed.region_id,
        "created_day": int(day),
        "deadline_day": int(seed.deadline_day),
        "heard_via": {"channel": channel, "event_id": event_id, "day": int(day)},
        "origin_faction_id": _origin_faction(state, seed, state.get("world_projection") or {}),
        "resolved_day": 0,
        "fail_reason": "",
        "fail_text": texts["fail_text"],
    }
    if seed.other_location_id:
        quest["other_location_id"] = seed.other_location_id
    if seed.provisional:
        quest["deadline_provisional"] = True
    if seed.kind in _lore_kinds():
        quest.update(_lore_fields(seed))
    return quest


def _lore_kinds() -> frozenset:
    from services.lore_quests import LORE_KINDS

    return LORE_KINDS


def _lore_fields(seed: QuestSeed) -> dict:
    """SPEC-313 R15/R28: campos INTERNOS da quest ancorada + texto da LLM (ja guardado).
    O `reward_hint` da LLM e descartado; vale o rotulo do motor."""
    refs = kind_cfg(seed.kind).get("lore_refs") or [""]
    out = {
        "lore_anchor": dict(seed.anchor),
        "lore_origin_key": seed.origin_key or "engine",
        "lore_ref": str(refs[0]),
        "reward_gold_planned": int(seed.reward_gold),
        "reward_hint": seed.reward_label,
    }
    if seed.llm_title:
        out["title"] = seed.llm_title
    if seed.llm_description:
        out["description"] = seed.llm_description
    return out


def _offer(state: dict, day: int, perceived: list[dict] | None) -> tuple[list[dict], list[dict]]:
    quests = [dict(q) for q in (state.get("quests") or [])]
    m = mode()
    if m == "off":
        return quests, []
    existing = {q.get("world_source_id") for q in quests if q.get("world_kind")}
    ids = {q.get("id") for q in quests}
    gid = str(state.get("game_id", ""))
    ready: list[tuple[tuple, QuestSeed, tuple[str, str, str]]] = []
    for seed in candidates(state, day):
        if seed.world_source_id in existing:  # R3: uma por fonte, qualquer status (D8)
            continue
        if quest_id(gid, seed.kind, seed.world_source_id) in ids:
            continue
        if not is_feasible(state, seed.location_id, seed.deadline_day, day):
            continue
        res = _resolve_channel(state, seed, perceived)
        if not res:
            continue
        dist = _distance(state, seed.location_id) or 0
        ready.append(((seed.deadline_day, dist, seed.world_source_id), seed, res))
    ready.sort(key=lambda row: row[0])
    created: list[dict] = []
    active_world = _active_world(quests)
    active_all = sum(1 for q in quests if q.get("status") == "active")
    from services import lore_quests as lq
    from services.quest_log import MAX_ACTIVE_QUESTS

    for _key, seed, (channel, event_id, origin) in ready:
        if seed.kind in lq.LORE_KINDS:
            # SPEC-313: teto proprio (R18) e anti-farm (R17); sem vaga => nenhuma quest.
            lore_mode = lq.mode()
            if lore_mode == "off":
                continue
            if lq.cap_reached({"quests": quests}) or active_all >= MAX_ACTIVE_QUESTS:
                lq._log("cap_reached", kind=seed.kind)
                continue
            if lq.on_cooldown(
                {"quests": quests}, seed.kind, seed.anchor, seed.origin_key or "engine", day
            ):
                continue
            if lore_mode == "shadow":
                lq._log("shadow_offer", kind=seed.kind, channel=channel)
                continue
        elif active_world >= MAX_WORLD_QUESTS_ACTIVE or active_all >= MAX_ACTIVE_QUESTS:
            _log("cap_reached", kind=seed.kind)
            continue
        quest = _build_quest(state, seed, channel, event_id, origin, day)
        left = int(seed.deadline_day) - int(day)
        if m == "shadow":
            _log("shadow_offer", kind=seed.kind, channel=channel, days_left_bucket=_bucket(left))
            continue
        quests.append(quest)
        created.append(quest)
        if seed.kind not in lq.LORE_KINDS:
            active_world += 1
        active_all += 1
        _log("offered", kind=seed.kind, channel=channel, days_left_bucket=_bucket(left))
    return quests, created


def offer_from_perceived(
    state: dict, perceived: list[dict], day: int
) -> tuple[list[dict], list[dict]]:
    """R7 (ponto 1, tick do storyteller): `(quests, criadas)` a partir do digest percebido."""
    return _offer(state, day, perceived)


def offer_from_heard(state: dict, day: int) -> tuple[list[dict], list[dict]]:
    """R7 (ponto 2, `turn_finalizer`): canais `npc`/`rumor` e testemunho direto."""
    return _offer(state, day, None)


def offer_from_proposal(
    state: dict,
    proposal: Any,
    npc_key: str,
    menu: list[dict],
    day: int,
    *,
    origin_entity_id: str = "",
) -> tuple[list[dict], dict | None, str]:
    """SPEC-313 R7: proposta ANCORADA do `npc_actor` -> quest montada pelo motor.

    `(quests, criada | None, motivo)`. Motivo "" = criada; motivo em
    `lore_quests.DOWNGRADE_REASONS` = o chamador a trata como quest COMUM (R3); qualquer outro
    motivo = descartada (cooldown, teto, duplicata, inviavel, fonte ja usada). Nunca levanta."""
    from difflib import SequenceMatcher

    from services import lore_quests as lq
    from services.quest_log import MAX_ACTIVE_QUESTS

    quests = [dict(q) for q in (state.get("quests") or [])]
    kind = str(getattr(proposal, "kind", None) or (proposal or {}).get("kind", "comum") or "comum")
    m = lq.mode()
    reason = ""
    if m == "off":
        reason = "mode_off"
    elif kind not in lq.NPC_PROPOSABLE:
        reason = "bad_kind"
    seed = None
    if not reason:
        seed, reason = lq.seed_for_proposal(state, proposal, npc_key, menu, day)
    if seed is not None:
        existing = {q.get("world_source_id") for q in quests if q.get("world_kind")}
        active = [q for q in quests if q.get("status") == "active"]
        if seed.world_source_id in existing:
            reason = "source_used"
        elif len(active) >= MAX_ACTIVE_QUESTS:
            reason = "cap"
        elif not is_feasible(state, seed.location_id, seed.deadline_day, day):
            reason = "infeasible"
    if seed is None or reason:
        key = "downgraded" if reason in lq.DOWNGRADE_REASONS else "ignored"
        lq._log(key, kind=kind, reason=reason, menu_size=len(menu or []))
        if reason == "cap":
            lq._log("cap_reached", kind=kind)
        return quests, None, reason
    _k, row = lq._npc(state, npc_key)
    origin_name = str(row.get("name") or npc_key)
    turn = _turn(state)
    quest = _build_quest(state, seed, "npc", f"npc:{seed.origin_key}:{turn}", origin_name, day)
    if any(
        SequenceMatcher(None, quest["title"].lower(), str(q.get("title", "")).lower()).ratio()
        >= 0.75
        for q in active
    ):
        lq._log("ignored", kind=kind, reason="title_duplicate")
        return quests, None, "title_duplicate"
    quest["origin_entity_id"] = origin_entity_id
    if m == "shadow":
        lq._log("shadow_offer", kind=kind, channel="npc")
        return quests, None, "shadow"
    quests.append(quest)
    lq._log("offered", kind=kind, channel="npc")
    return quests, quest, ""


# --- prazo, falha e conclusao do motor (R12/R16/R19) -------------------------------


def _find_crisis(sim: dict, crisis_id: str) -> dict | None:
    return next((c for c in sim.get("crises") or [] if c.get("crisis_id") == crisis_id), None)


def _source_state(state: dict, q: dict) -> str:
    """`active` | `bad_end` (o desfecho ruim ja aconteceu) | `ok_end` (acabou sozinha)."""
    kind = str(q.get("world_kind"))
    sim = state.get("world_sim") or {}
    proj = state.get("world_projection") or {}
    sid = str(q.get("world_source_id") or "")
    if kind in CRISIS_QUEST_KINDS:
        rec = _find_crisis(sim, sid)
        if rec is None:
            return "ok_end"
        if kind == "frear_ascensao":
            if rec.get("end_day") is None:
                return "bad_end" if rec.get("start_day") is not None else "active"
            return "ok_end" if rec.get("resolution") == "intervencao" else "bad_end"
        if rec.get("end_day") is None:
            return "active"
        return "bad_end" if rec.get("resolution") in _BAD_CRISIS_RESOLUTIONS else "ok_end"
    if kind == "libertar_ocupado":
        row = (proj.get("location_states") or {}).get(q.get("location_id")) or {}
        since = int(row.get("since_day", -1) or -1)
        ok = row.get("state") == "ocupado" and f"occ:{q.get('location_id')}:{since}" == sid
        return "active" if ok else "ok_end"
    if kind == "reabrir_rota":
        a, b = str(q.get("location_id") or ""), str(q.get("other_location_id") or "")
        for r in proj.get("blocked_routes") or []:
            if frozenset((r.get("a"), r.get("b"))) == frozenset((a, b)):
                return "active"
        return "ok_end"
    if kind == "recuperar_objeto":
        item = sid.split(":")[1] if sid.count(":") >= 2 else ""
        holder = str(((proj.get("unique_items") or {}).get(item) or {}).get("holder") or "")
        return "active" if holder in _faction_ids(state) else "ok_end"
    if kind == "resgate":
        peril = next((p for p in _perils(state) if str(p.get("peril_id")) == sid), None)
        if peril is None:
            return "ok_end"
        res = str(peril.get("resolution") or "")
        if not res:
            return "active"
        return "ok_end" if res == "intervencao" else "bad_end"
    if kind == "escoltar":  # SPEC-313: o escoltado morreu por outra via => sem falha (R25)
        from services import npc_world

        ref = str((q.get("lore_anchor") or {}).get("id") or "")
        key, row = npc_world._row_for(state, ref)
        sim_row = ((state.get("npc_sim") or {}).get("npcs") or {}).get(ref) or {}
        dead = bool(sim_row.get("dead")) or (bool(row) and npc_world._is_dead(state, ref, row, {}))
        return "ok_end" if dead else "active"
    if kind == "investigar_rumor":  # SPEC-313: o rumor sumiu ou ja foi resolvido
        api = _rumor_api()
        inst = (
            api.instance(state, str((q.get("lore_anchor") or {}).get("id") or "")) if api else None
        )
        return "ok_end" if (inst is None or inst.get("resolution")) else "active"
    if kind in ("cacar_criatura", "entregar_material", "recolher_mortos"):
        return "active"
    return "ok_end"


def _retarget(q: dict, location_id: str) -> dict:
    """A crise anunciada abriu em outro local: o alvo muda e as evidencias do local velho
    deixam de valer."""
    drop = (
        "location_reached",
        "investigation",
        "combat_won",
        "completion_ready",
        "npc_interaction",
    )
    q = dict(q)
    q["location_id"] = location_id
    q["progress_log"] = [r for r in q.get("progress_log") or [] if r.get("kind") not in drop]
    q.pop("completion_ready", None)
    return q


def _quest_event(state: dict, etype: str, q: dict, day: int, reason: str = "") -> dict:
    payload = {
        "quest_id": q["id"],
        "quest_title": _event_title(q),
        "world_kind": q.get("world_kind", ""),
        "location_id": q.get("location_id", ""),
        "region_id": q.get("region_id", ""),
        "day": int(day),
    }
    if q.get("other_location_id"):
        payload["other_location_id"] = q["other_location_id"]
    if etype == "quest_failed":
        payload["reason"] = reason
    return {
        "type": etype,
        "actor_id": "player" if etype == "quest_completed" else "engine",
        "target_id": q["id"],
        "detail": "",
        "payload": payload,
        "source": "engine",
        "event_id": wd.event_id(str(state.get("game_id", "")), etype, day, q["id"]),
    }


def _already_queued(state: dict, etype: str, qid: str) -> bool:
    for ev in (state.get("pending_world_events") or []) + (state.get("event_log") or []):
        if isinstance(ev, dict) and ev.get("type") == etype and ev.get("target_id") == qid:
            return True
    return False


def _perceived_end(q: dict, perceived: list[dict] | None) -> bool:
    """R19: o jogador percebeu o fim da fonte (item `fim` da 302)."""
    for it in perceived or []:
        if it.get("kind") != "fim":
            continue
        prefix = str(it.get("template_id") or "").split(".")[0]
        if q.get("world_kind") in CRISIS_QUEST_KINDS:
            crisis = {v: k for k, v in _CRISIS_KIND.items()}.get(str(q.get("world_kind")))
            if prefix == crisis and it.get("region_id") == q.get("region_id"):
                return True
        elif q.get("world_kind") == "libertar_ocupado" and it.get("location_id") == q.get(
            "location_id"
        ):
            return True
    return False


def sync_deadlines(
    state: dict, tick_day: int, perceived: list[dict] | None = None
) -> tuple[list[dict], list[dict]]:
    """R16/R19. `(quests, propostas engine)`: `quest_failed` no prazo (fonte ainda ativa) ou
    `expired` (fonte acabou sozinha). Chamada so quando o dia vira, depois de `advance_days`."""
    quests = [dict(q) for q in (state.get("quests") or [])]
    m = mode()
    if m == "off":
        return quests, []
    out: list[dict] = []
    events: list[dict] = []
    turn = _turn(state)
    from services import quest_log

    for q in quests:
        if not (q.get("world_kind") and q.get("status") == "active"):
            out.append(q)
            continue
        src = _source_state(state, q)
        deadline = int(q.get("deadline_day", 0) or 0)
        if q.get("deadline_provisional"):
            rec = _find_crisis(state.get("world_sim") or {}, str(q.get("world_source_id")))
            if rec is not None and rec.get("start_day") is not None:
                deadline = max(deadline, int(rec.get("escalation_day") or deadline))  # R2
                q["deadline_day"] = deadline
                q.pop("deadline_provisional", None)
                new_loc = str(rec.get("location_id") or "")
                if new_loc and new_loc != q.get("location_id"):
                    q = _retarget(q, new_loc)
            elif src == "active":
                out.append(q)  # ainda so anunciada: o prazo real vem quando abrir
                continue
        if q["world_kind"] == "escoltar" and src == "ok_end" and m != "shadow":
            out.append(_expire(q, turn, tick_day, quest_log))  # escoltado morreu: sem espera
            continue
        if m == "shadow":
            if src == "ok_end" and _perceived_end(q, perceived):
                _log("shadow_fail", kind=q["world_kind"], reason="superada")
            elif tick_day >= deadline and src != "ok_end":
                _log("shadow_fail", kind=q["world_kind"], reason="prazo")
            out.append(q)
            continue
        if src == "ok_end" and _perceived_end(q, perceived):
            out.append(_expire(q, turn, tick_day, quest_log))
            continue
        if q["world_kind"] == "resgate" and src == "bad_end":
            deadline = tick_day  # o destino do NPC ja foi decidido pela 304
        if tick_day >= deadline:
            if src == "ok_end":
                out.append(_expire(q, turn, tick_day, quest_log))
                continue
            if not _already_queued(state, "quest_failed", q["id"]):
                events.append(_quest_event(state, "quest_failed", q, tick_day, "prazo"))
                _log("failed", kind=q["world_kind"], days_left_bucket="urgente")
        out.append(q)
    return out, events


def _expire(q: dict, turn: int, day: int, quest_log: Any) -> dict:
    _log("expired", kind=q.get("world_kind"), days_left_bucket="urgente")
    return quest_log.expire_quest([q], q["id"], turn, day)[0]


def engine_completions(state: dict) -> list[dict]:
    """R12: conclusoes que o proprio motor prova (`resgate` por intervencao; objeto de volta
    as maos do jogador). `quest_completed` com `source="engine"` (pula a prova de investigacao)."""
    if mode() != "on":
        return []
    day = _day(state)
    proj = state.get("world_projection") or {}
    events: list[dict] = []
    for q in state.get("quests") or []:
        if not (q.get("world_kind") and q.get("status") == "active"):
            continue
        done = False
        sid = str(q.get("world_source_id") or "")
        if q["world_kind"] == "resgate":
            peril = next((p for p in _perils(state) if str(p.get("peril_id")) == sid), None)
            done = bool(peril and peril.get("resolution") == "intervencao")
        elif q["world_kind"] == "recuperar_objeto" and sid.count(":") >= 2:
            holder = str(
                ((proj.get("unique_items") or {}).get(sid.split(":")[1]) or {}).get("holder")
            )
            done = holder == "player"
        elif q["world_kind"] == "cacar_criatura":  # SPEC-313 R19/R20: so por morte da ancora
            done = any(r.get("kind") == "hunt_kill" for r in q.get("progress_log") or [])
        elif q["world_kind"] == "entregar_material":  # R21
            done = _delivery_ready(state, q)
        elif q["world_kind"] == "escoltar":  # R22
            from services import npc_world

            done = npc_world.escort_arrived(state, q)
        if done and not _already_queued(state, "quest_completed", q["id"]):
            events.append(_quest_event(state, "quest_completed", q, day))
    return events


def _last_player_text(state: dict) -> str:
    for msg in reversed(state.get("messages") or []):
        if getattr(msg, "type", "") == "human":
            return str(getattr(msg, "content", "") or "")
    return ""


def _delivery_ready(state: dict, q: dict) -> bool:
    """SPEC-313 R21: no destino, com `qty` do item no inventario e verbo de entrega na acao do
    turno. A remocao do item acontece no `event_processor` (mesmo apply do ouro)."""
    import inventory
    from services import quest_log

    anchor = q.get("lore_anchor") or {}
    if _cur(state) != str(anchor.get("to") or "") or _turn(state) <= int(q.get("created_turn", 0)):
        return False
    inv = (state.get("player") or {}).get("inventory") or []
    if inventory.get_qty(inv, str(anchor.get("item_id") or "")) < int(anchor.get("qty") or 1):
        return False
    return quest_log._vocab_match("entregar_material", _last_player_text(state))


def _event_title(q: dict) -> str:
    """Titulo que entra no event_log/cronica. `investigar_rumor` leva texto de rumor no titulo:
    nunca vai para o log canonico (SPEC-312 R24 `rumor.became_fact`)."""
    if q.get("world_kind") == "investigar_rumor":
        return "Conferir um rumor"
    return str(q.get("title", ""))
