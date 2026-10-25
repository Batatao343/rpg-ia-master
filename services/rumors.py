"""SPEC-312: rumores com semente (lore -> motor sorteia -> LLM costura; boato falso nunca vira fato).

Owner do ciclo de vida do rumor dentro de `world_sim` (`rumors`, `region_presence`,
`rumor_last_perceived_day`, `rumor_seed_last_born`). Puro: sem LLM e sem RNG global
(o unico sorteio vem de `world_engine.day_rng`).

Regra de ouro: o jogador so sabe o que viu ou ouviu. `truth` e INTERNO: nunca sai em prompt,
API ou `world.news`. Nenhuma funcao daqui grava fato canonico (evento, projecao, memoria,
quest, pressao): rumor e boato, e boato falso nunca vira fato.

Interface para a SPEC-313 (`investigar_rumor`): `investigable`, `truth_of`, `mark_resolved`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

MODES = ("off", "shadow", "on")
DEFAULT_MODE = "on"  # D3: local e suite; o staging fixa `shadow` por env
RESOLUTIONS = ("confirmado", "desmentido", "inconclusivo")
NEVER_AGAIN = 1 << 30  # marcador em `rumor_seed_last_born`: semente ja percebida/resolvida
_DATA = Path(__file__).resolve().parent.parent / "data" / "world"


# --- modo e dados -------------------------------------------------------------------


def mode() -> str:
    """`RPG_RUMORS`; so vale com `RPG_WORLD_ENGINE=on` (senao se comporta como `off`)."""
    raw = os.getenv("RPG_RUMORS", "").strip().lower()
    m = raw if raw in MODES else DEFAULT_MODE
    if m == "off":
        return "off"
    from services import world_engine

    return m if world_engine.mode() == "on" else "off"


def proposed_mode() -> str:
    raw = os.getenv("RPG_RUMORS_PROPOSED", "").strip().lower()
    return raw if raw in ("off", "on") else "off"


@lru_cache(maxsize=1)
def config() -> dict:
    return json.loads((_DATA / "rumor_config.json").read_text(encoding="utf-8"))


def const(name: str) -> Any:
    return config()["constants"][name]


@lru_cache(maxsize=1)
def _all_seeds() -> dict[str, dict]:
    doc = json.loads((_DATA / "rumor_seeds.json").read_text(encoding="utf-8"))
    return dict(doc.get("seeds") or {})


def load_seeds() -> dict[str, dict]:
    """So as sementes habilitadas (`disabled` fora)."""
    return {sid: s for sid, s in _all_seeds().items() if not s.get("disabled")}


def _fold(text: str) -> str:
    import unicodedata

    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", str(text or "").lower())
        if not unicodedata.combining(ch)
    )


def _k(seed_id: str) -> str:
    """Chave curta de `rumor_seed_last_born` (S6: o save nao carrega o id inteiro da semente)."""
    return hashlib.sha256(str(seed_id).encode("utf-8")).hexdigest()[:8]


def _sha(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def is_rumor_item(item: Any) -> bool:
    """Item de digest OU entrada de `world.news` que e rumor (R11/R24: nunca vira fato)."""
    if not isinstance(item, dict):
        return False
    return item.get("kind") == "rumor" or str(item.get("template_id") or "").startswith("rumor.")


def _day_of(world: dict | None) -> int:
    return int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)


def _sim(state: dict) -> dict:
    return (state or {}).get("world_sim") or {}


def region_of_row(r: dict) -> str:
    """Regiao da instancia (compacta: derivada do local de nascimento)."""
    from services import world_pressures as wp

    return str(r.get("region_id") or wp.region_of(str(r.get("location_id") or "")))


def seed_of(r: dict) -> dict:
    return _all_seeds().get(str((r or {}).get("seed_id") or "")) or {}


def entities_of(r: dict) -> list[str]:
    return list(r.get("entities") or seed_of(r).get("entities") or [])


def subject_of(r: dict) -> str:
    return str(r.get("subject") or seed_of(r).get("subject") or "")


def is_quest_eligible(r: dict) -> bool:
    if "quest_eligible" in r:
        return bool(r["quest_eligible"])
    return bool(seed_of(r).get("quest_eligible", True))


def instance(state: dict, rumor_id: str) -> dict | None:
    for r in _sim(state).get("rumors") or []:
        if isinstance(r, dict) and r.get("rumor_id") == rumor_id:
            return r
    return None


# --- regiao frequentada (R7) ---------------------------------------------------------


def frequented_regions(sim: dict, day: int) -> list[str]:
    window = int(const("FREQUENT_WINDOW_DAYS"))
    pres = (sim or {}).get("region_presence") or {}
    return sorted(r for r, last in pres.items() if int(day) - int(last) <= window)


# --- nascimento (R8/R9) --------------------------------------------------------------


def _entity_dead(state: dict, entity_id: str) -> bool:
    proj = (state or {}).get("world_projection") or {}
    ent = (proj.get("entities") or {}).get(entity_id)
    if isinstance(ent, dict) and ent.get("alive") is False:
        return True
    from services.npc_layers import npc_alive

    for key, row in ((state or {}).get("npcs") or {}).items():
        if isinstance(row, dict) and entity_id in (key, row.get("id")) and not npc_alive(row):
            return True
    return False


def _seed_text(seed: dict) -> str:
    return " ".join(
        str(seed.get(k) or "") for k in ("title", "gist", "creature_label") if seed.get(k)
    )


def _secret(state: dict, text: str) -> bool:
    from services.memory_provenance import find_strict_unrevealed

    return bool(text) and bool(find_strict_unrevealed(text, state or {}))


def _secret_locked(state: dict, seed: dict) -> bool:
    """P2-2: semente curada com `secret_id` (a verdade dela revelaria um segredo) fica bloqueada
    enquanto esse segredo nao for revelado por evento aceito."""
    sec = str(seed.get("secret_id") or "")
    if not sec:
        return False
    from services.memory_provenance import accepted_secret_ids

    return sec.casefold() not in {i.casefold() for i in accepted_secret_ids(state or {})}


def _birth_location(seed: dict, region: str) -> str:
    from services import world_pressures as wp

    locs = wp._map_index()[0]
    loc = locs.get(str(seed.get("location_id") or "")) or {}
    if loc and loc.get("region_id") == region and not loc.get("parent_id"):
        return str(loc["id"])
    return wp.region_primary_location(region)


def candidates(state: dict, sim: dict, region_id: str, day: int) -> list[tuple[dict, float]]:
    """Sementes elegiveis para nascer em `region_id` no dia, com peso. Cada semente devolvida
    leva `_truth` (resolvido aqui, R8) e `seed_id`. Ordem estavel (por id)."""
    from services import world_pressures as wp

    cooldown = int(const("SEED_COOLDOWN_DAYS"))
    last_born = (sim or {}).get("rumor_seed_last_born") or {}
    active = {
        r.get("seed_id")
        for r in (sim or {}).get("rumors") or []
        if isinstance(r, dict) and int(r.get("expires_day", 0)) >= int(day)
    }
    adjacent = set(wp.region_adjacency().get(region_id, []))
    lore_w = float(const("LORE_WEIGHT"))
    own: list[tuple[dict, float]] = []
    adj: list[tuple[dict, float]] = []
    for sid in sorted(load_seeds()):
        seed = load_seeds()[sid]
        if sid in active or int(day) - int(last_born.get(_k(sid), -(1 << 20))) < cooldown:
            continue
        family = seed.get("family")
        regions = set(seed.get("regions") or [])
        in_region = region_id in regions
        if family == "lore" and not in_region:
            continue
        if family == "avistamento" and not in_region and not (regions & adjacent):
            continue
        if any(_entity_dead(state, e) for e in seed.get("entities") or [] if e.startswith("npc_")):
            continue
        if _secret(state, _seed_text(seed)) or _secret_locked(state, seed):
            continue
        row = {**seed, "seed_id": sid}
        if family == "lore":
            row["_truth"] = bool(seed.get("truth"))
            own.append((row, lore_w))
        elif in_region:
            row["_truth"] = True
            own.append((row, 1.0))
        else:
            row["_truth"] = False
            adj.append((row, 1.0))
    # AVISTAMENTO_FALSE_P: a massa dos avistamentos de regiao vizinha (falsos) e a fracao p
    own_avist = sum(w for s, w in own if s["family"] == "avistamento")
    if adj:
        p = float(const("AVISTAMENTO_FALSE_P"))
        target = (p / (1.0 - p)) * (own_avist if own_avist > 0 else float(len(adj)))
        scale = target / len(adj)
        adj = [(s, scale) for s, _w in adj]
    return sorted(own + adj, key=lambda sw: sw[0]["seed_id"])


def _pick(cands: list[tuple[dict, float]], u: float) -> dict:
    total = sum(w for _s, w in cands)
    acc = 0.0
    for seed, w in cands:
        acc += w
        if u * total < acc:
            return seed
    return cands[-1][0]


def _make_instance(game_id: str, seed: dict, region: str, day: int, turn: int) -> dict:
    return {
        "rumor_id": _sha(game_id, seed["seed_id"], day)[:16],
        "seed_id": seed["seed_id"],
        "family": seed["family"],
        "location_id": _birth_location(seed, region),
        "truth": bool(seed["_truth"]),
        "born_day": int(day),
        "born_turn": int(turn),
        "expires_day": int(day) + int(const("RUMOR_TTL_DAYS")),
        "perceived_day": 0,
    }  # compacto (S6): entities/subject/quest_eligible vem da semente; `resolution` so se houver


STALE_UNPERCEIVED_DAYS = 0  # nao percebida some ao expirar
STALE_PERCEIVED_DAYS = 3  # percebida sem quest possivel
# P2-3: percebida + quest_eligible + sem desfecho fica resolvivel (a 313 usa truth_of) por
# este horizonte depois de expirar
INVESTIGABLE_HORIZON_DAYS = 20


def _investigable_row(r: dict) -> bool:
    return bool(r.get("perceived_day")) and not r.get("resolution") and is_quest_eligible(r)


def _forget(last: dict, r: dict) -> None:
    """Instancia que sai do ledger: so semente da LORE percebida/resolvida nunca mais nasce
    (chave curta; `narrador:*` nao entra, o dedupe de texto cobre)."""
    key = _k(str(r.get("seed_id")))
    if r.get("family") == "lore" and (r.get("perceived_day") or r.get("resolution")):
        last[key] = NEVER_AGAIN
    else:
        last[key] = max(int(last.get(key, 0)), int(r.get("born_day", 0)))


def _cap_ledger(sim: dict, day: int) -> None:
    """Mantem o ledger pequeno: expirados velhos saem; teto `RUMOR_LEDGER_MAX` despeja primeiro
    os expirados nao percebidos, depois os percebidos; nunca um rumor ativo nem um percebido
    ainda investigavel dentro do horizonte (P2-3)."""
    day = int(day)
    last = dict(sim.get("rumor_seed_last_born") or {})
    keep: list[dict] = []
    for r in (x for x in sim.get("rumors") or [] if isinstance(x, dict)):
        age = day - int(r.get("expires_day", 0))
        if r.get("perceived_day"):
            limit = INVESTIGABLE_HORIZON_DAYS if _investigable_row(r) else STALE_PERCEIVED_DAYS
        else:
            limit = STALE_UNPERCEIVED_DAYS
        if age > limit:
            _forget(last, r)
        else:
            keep.append(r)
    cap = int(const("RUMOR_LEDGER_MAX"))
    if len(keep) > cap:
        order = sorted(
            (r for r in keep if int(r.get("expires_day", 0)) < day and not _investigable_row(r)),
            key=lambda r: (1 if r.get("perceived_day") else 0, int(r.get("born_day", 0))),
        )
        drop = order[: len(keep) - cap]
        for r in drop:
            _forget(last, r)
        ids = {r["rumor_id"] for r in drop}
        keep = [r for r in keep if r["rumor_id"] not in ids]
    cooldown = int(const("SEED_COOLDOWN_DAYS"))
    sim["rumors"] = keep
    sim["rumor_seed_last_born"] = {
        k: v for k, v in last.items() if v == NEVER_AGAIN or day - int(v) <= cooldown
    }


def day_hook(ctx: Any):
    """Hook diario `post` order 20 (R8). Muta `ctx.sim`; devolve itens `kind="rumor"` no digest."""
    from services import world_director as wd
    from services import world_engine
    from services import world_pressures as wp

    m = mode()
    result = world_engine.DayHookResult()
    if m == "off":
        return result
    sim, day = ctx.sim, int(ctx.day)
    here = wp.region_of(str(((ctx.world or {}).get("current_location_id")) or ""))
    if here:
        pres = dict(sim.get("region_presence") or {})
        pres[here] = day
        sim["region_presence"] = pres
    state = ctx.state or {}
    turn = int(((ctx.world or {}).get("turn_count")) or 0)
    p_birth = float(const("RUMOR_BIRTH_P"))
    frequented = set(frequented_regions(sim, day))
    rng = world_engine.day_rng(ctx.game_id, day, "rumors")
    from observability.telemetry import log_event

    for region in wp.region_ids():
        roll, pick = rng.random(), rng.random()  # sempre 2 sorteios: o fluxo nao depende do resto
        if region not in frequented or roll >= p_birth:
            continue
        cands = candidates(state, sim, region, day)
        if not cands:
            log_event("rumor", "exhausted", level="info", region=region)
            continue
        seed = _pick(cands, pick)
        inst = _make_instance(ctx.game_id, seed, region, day, turn)
        last = dict(sim.get("rumor_seed_last_born") or {})
        last[_k(inst["seed_id"])] = day  # shadow tambem registra o cooldown (mesma taxa do `on`)
        sim["rumor_seed_last_born"] = last
        if m == "shadow":
            log_event(
                "rumor", "shadow_born", level="info", family=inst["family"], truth=inst["truth"]
            )
            continue
        sim["rumors"] = [*(sim.get("rumors") or []), inst]
        sim["rumor_born_total"] = int(sim.get("rumor_born_total", 0)) + 1  # R31 cumulativo
        result.digest.append(
            wd.digest_item(
                ctx.game_id,
                day,
                "rumor",
                region,
                inst["location_id"],
                f"rumor.{inst['family']}",
                {
                    "seed_id": inst["seed_id"],
                    "family": inst["family"],
                    "expires_day": inst["expires_day"],
                },
                subject_id=inst["rumor_id"],
            )
        )
        log_event("rumor", "born", level="info", family=inst["family"], region=region)
    _cap_ledger(sim, day)
    return result


def trim_digest(items: list[dict], cap: int) -> list[dict]:
    """Teto do `pending_digest`: se estourar, rumores saem antes de qualquer outro item."""
    rum_idx = [i for i, it in enumerate(items) if is_rumor_item(it)]
    over = max(0, len(rum_idx) - int(const("RUMOR_DIGEST_MAX")))  # S6: poucos rumores pendentes
    if over:
        gone = set(rum_idx[:over])
        items = [it for i, it in enumerate(items) if i not in gone]
    excess = len(items) - cap
    if excess <= 0:
        return list(items)
    drop: set[int] = set()
    for i, it in enumerate(items):
        if len(drop) >= excess:
            break
        if is_rumor_item(it):
            drop.add(i)
    kept = [it for i, it in enumerate(items) if i not in drop]
    return kept[-cap:]


# --- texto (R5/R23) ------------------------------------------------------------------


def _template(rumor: dict) -> str:
    opts = config()["templates"].get(f"rumor.{rumor.get('family')}") or []
    if not opts:
        return ""
    return opts[int(_sha(rumor.get("rumor_id"))[:8], 16) % len(opts)]


def render_news(state: dict, rumor: dict) -> str:
    """Template + gist/rotulo. Nunca texto da LLM (exceto `narrador`, ja validado)."""
    from services import world_pressures as wp

    tpl = _template(rumor)
    if not tpl:
        return ""
    family = rumor.get("family")
    seed = _all_seeds().get(str(rumor.get("seed_id") or "")) or {}
    locs = wp._map_index()[0]
    local = str((locs.get(str(rumor.get("location_id") or "")) or {}).get("name") or "")
    values = {
        "text": str(rumor.get("text") or ""),
        "gist": str(seed.get("gist") or ""),
        "fonte_label": str(seed.get("fonte_label") or "alguns"),
        "criatura": str(seed.get("creature_label") or "uma criatura"),
        "local": local or wp.region_label(region_of_row(rumor)) or "a região",
    }
    if family in ("lore", "avistamento") and not (
        values["gist"] or values["criatura"] != "uma criatura"
    ):
        return ""
    text = tpl
    for k, v in values.items():
        text = text.replace("{" + k + "}", v)
    text = text.strip()
    return text[:1].upper() + text[1:] if text else ""


def text_for(state: dict, rumor_id: str) -> str:
    """Texto do rumor para o ledger da 215; vazio se a instancia sumiu ou expirou (R21)."""
    inst = instance(state, rumor_id)
    if not inst or int(inst.get("expires_day", 0)) < _day_of((state or {}).get("world")):
        return ""
    return render_news(state, inst)


def public_names(rumor: dict) -> set[str]:
    seed = _all_seeds().get(str(rumor.get("seed_id") or "")) or {}
    return {str(n) for n in seed.get("public_names") or [] if n}


# --- percepcao (R12-R16) -------------------------------------------------------------


def _settlement(loc_id: str) -> bool:
    from services import world_pressures as wp

    locs = wp._map_index()[0]
    tags = set(config().get("settlement_tags") or [])
    loc = locs.get(loc_id) or {}
    parent = locs.get(str(loc.get("parent_id") or "")) or {}
    return bool(tags & (set(loc.get("tags") or []) | set(parent.get("tags") or [])))


def channel_of(state: dict, item: dict) -> str:
    """`a` (regional habitado / origem), `b` (ouvido via `location_heard`) ou ``."""
    from services import npc_knowledge
    from services import world_perception as wperc

    cur, cur_region = wperc._cur(state)
    if not cur:
        return ""
    rid = str(item.get("subject_id") or "")
    heard = set(((state or {}).get("location_heard") or {}).get(cur, []) or [])
    if npc_knowledge.mode() == "on" and rid and rid in heard:
        return "b"
    if item.get("region_id") == cur_region and (
        _settlement(cur) or item.get("location_id") in wperc._family(cur)
    ):
        return "a"
    return ""


def perceivable(state: dict, item: dict) -> bool:
    return bool(channel_of(state, item))


def limit_perceived(state: dict, sim: dict, seen: list[dict], day: int) -> list[dict]:
    """R13: no maximo 1 rumor novo por dia e por acao; itens nao-rumor intactos."""
    rumors = [i for i in seen if is_rumor_item(i)]
    if not rumors:
        return list(seen)
    allowed = 0
    last = int((sim or {}).get("rumor_last_perceived_day", 0) or 0)
    # cooldown global (coordenador): >= RUMOR_MIN_GAP_DAYS entre rumores novos percebidos
    if int(day) - last >= int(const("RUMOR_MIN_GAP_DAYS")):
        allowed = min(int(const("RUMORS_PER_ACTION_MAX")), int(const("RUMOR_PERCEIVED_PER_DAY")))
    fresh = []
    for it in rumors:
        inst = instance({"world_sim": sim}, str(it.get("subject_id") or ""))
        if inst is None or int(inst.get("expires_day", 0)) < int(day):
            continue
        fresh.append((it, inst))
    fresh.sort(
        key=lambda p: (
            0 if channel_of(state, p[0]) == "b" else 1,
            -int(p[1].get("born_day", 0)),
            str(p[1].get("rumor_id")),
        )
    )
    keep = {id(p[0]) for p in fresh[:allowed]}
    return [i for i in seen if not is_rumor_item(i) or id(i) in keep]


def mark_perceived(sim: dict, rumor_ids: list[str], day: int) -> dict:
    ids = set(rumor_ids)
    if not ids:
        return sim
    rows = []
    last = dict(sim.get("rumor_seed_last_born") or {})
    for r in sim.get("rumors") or []:
        if isinstance(r, dict) and r.get("rumor_id") in ids and not r.get("perceived_day"):
            r = {**r, "perceived_day": int(day)}
            if r.get("family") == "lore":  # S4: rumor da lore percebido nunca se repete
                last[_k(str(r.get("seed_id")))] = NEVER_AGAIN
        rows.append(r)
    sim["rumors"] = rows
    sim["rumor_seed_last_born"] = last
    sim["rumor_last_perceived_day"] = int(day)
    return sim


def from_item(item: dict) -> dict:
    """Instancia minima para renderizar a partir do proprio item do digest (sem o `world_sim`)."""
    params = item.get("params") or {}
    return {
        "rumor_id": str(item.get("subject_id") or ""),
        "seed_id": str(params.get("seed_id") or ""),
        "family": str(params.get("family") or ""),
        "region_id": str(item.get("region_id") or ""),
        "location_id": str(item.get("location_id") or ""),
        "expires_day": int(params.get("expires_day", 0) or 0),
        "text": str(params.get("text") or ""),
    }


def news_extra(item: dict) -> dict:
    return {
        "kind": "rumor",
        "rumor_id": str(item.get("subject_id") or ""),
        "expires_day": int((item.get("params") or {}).get("expires_day", 0) or 0),
    }


def prune_news(world: dict, day: int) -> dict:
    """R15: rumor expirado sai de `world.news`; no maximo `RUMOR_NEWS_MAX` rumores; notícia
    que nao e rumor nunca e removida aqui."""
    news = [n for n in (world or {}).get("news") or [] if isinstance(n, dict)]
    live = [n for n in news if not (is_rumor_item(n) and int(n.get("expires_day", 0)) < int(day))]
    cap = int(const("RUMOR_NEWS_MAX"))
    rum_idx = [i for i, n in enumerate(live) if is_rumor_item(n)]
    drop = set(rum_idx[: max(0, len(rum_idx) - cap)])
    live = [n for i, n in enumerate(live) if i not in drop]
    out = dict(world or {})
    out["news"] = live
    return out


def public_kind(entry: dict) -> str:
    """R17: unico campo derivado de rumor que a API expoe."""
    return "boato" if is_rumor_item(entry) else "noticia"


# --- rumor proposto pelo narrador (R25-R27) -----------------------------------------


def _digits(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _reject_text(state: dict, text: str) -> str:
    if not 20 <= len(text) <= 200:
        return "length"
    if _digits(text):
        return "digits"
    name = str(((state or {}).get("player") or {}).get("name") or "").strip()
    if name and name.casefold() in text.casefold():
        return "player_name"
    if _secret(state, text):
        return "secret"
    from agents import world_simulator as wsim

    low = text.lower()
    allowed = {n.lower() for n in wsim._allowed_names(state)}
    for nm in wsim._catalog_names():
        if nm.lower() in low and nm.lower() not in allowed:
            return "name"
    return ""


def _duplicate(
    state: dict, sim: dict, text: str, entities: list[str], region: str, day: int
) -> bool:
    sim_thr = float(const("TITLE_SIMILARITY"))

    def near(other: str) -> bool:
        return bool(other) and SequenceMatcher(None, _fold(text), _fold(other)).ratio() >= sim_thr

    for r in sim.get("rumors") or []:
        if not isinstance(r, dict) or int(r.get("expires_day", 0)) < int(day):
            continue
        if near(render_news(state, r)):
            return True
        if set(entities_of(r)) == set(entities):
            return True
    for seed in load_seeds().values():
        if region in (seed.get("regions") or []) and near(str(seed.get("gist") or "")):
            return True
    return any(
        near(str(n.get("text") or ""))
        for n in ((state or {}).get("world") or {}).get("news") or []
        if isinstance(n, dict)
    )


def accept_proposed(
    state: dict, proposals: list, *, turn: int, day: int, quarantined: bool
) -> tuple[dict | None, dict | None, list[str]]:
    """R26/R27: `(world_sim novo | None, world novo | None, motivos de rejeicao)`.
    Aceito vira rumor `narrador`: falso, nao elegivel a quest, ja percebido. Nunca levanta."""
    from observability.telemetry import log_event

    reasons: list[str] = []
    if proposed_mode() != "on" or mode() != "on":
        return None, None, ["mode"]
    items = [p for p in proposals or [] if p is not None]
    if not items:
        return None, None, []
    if quarantined:
        reasons.append("quarantine")
    for p in items[: int(const("PROPOSED_PER_TURN"))]:
        why = reasons[0] if reasons else _validate_proposal(state, p, day)
        if why:
            reasons.append(why)
            log_event("rumor", "proposed_rejected", level="info", reason=why)
            continue
        world, sim = _apply_proposal(state, p, turn=turn, day=day)
        log_event("rumor", "proposed_accepted", level="info", family="narrador")
        return sim, world, reasons
    return None, None, reasons


def _get(p: Any, key: str, default: Any = "") -> Any:
    return p.get(key, default) if isinstance(p, dict) else getattr(p, key, default)


def _validate_proposal(state: dict, p: Any, day: int) -> str:
    from services import graph_resolver as gr
    from services import world_pressures as wp

    sim = _sim(state)
    text = str(_get(p, "text") or "").strip()
    ents = [str(e) for e in _get(p, "entity_ids", []) or []]
    graph = gr.load_entities()
    if not ents or any(
        e not in graph or graph[e].get("visibility", "public") != "public" for e in ents
    ):
        return "entity"
    loc = str(_get(p, "location_id") or "")
    here = str(((state or {}).get("world") or {}).get("current_location_id") or "")
    if loc and loc not in wp._map_index()[0]:
        return "location"
    bad = _reject_text(state, text)
    if bad:
        return bad
    region = wp.region_of(loc or here)
    if _duplicate(state, sim, text, ents, region, day):
        return "duplicate"
    if int(sim.get("rumor_last_perceived_day", 0) or 0) == int(day):
        return "daily_cap"
    return ""


def _subject_of(entities: list[str]) -> str:
    from services import graph_resolver as gr

    graph = gr.load_entities()
    for e in entities:
        t = (graph.get(e) or {}).get("type")
        if t == "npc":
            return "pessoa"
        if t == "faction":
            return "faccao"
    return "lugar"


def _apply_proposal(state: dict, p: Any, *, turn: int, day: int) -> tuple[dict, dict]:
    from services import world_pressures as wp
    from services.ambient import NEWS_TEXT_MAX, append_news

    sim = dict(_sim(state))
    text = str(_get(p, "text")).strip()
    ents = [str(e) for e in _get(p, "entity_ids", [])]
    world = dict((state or {}).get("world") or {})
    here = str(world.get("current_location_id") or "")
    loc = str(_get(p, "location_id") or "") or here
    game_id = str((state or {}).get("game_id") or "")
    seed_id = "narrador:" + _sha(text)[:12]
    inst = {
        "rumor_id": _sha(game_id, seed_id, day)[:16],
        "seed_id": seed_id,
        "family": "narrador",
        "location_id": loc,
        "entities": ents,
        "subject": _subject_of(ents),
        "truth": False,
        "quest_eligible": False,
        "born_day": int(day),
        "born_turn": int(turn),
        "expires_day": int(day) + int(const("RUMOR_TTL_DAYS")),
        "perceived_day": int(day),
        "text": text[:NEWS_TEXT_MAX],
        "resolution": "",
    }
    sim["rumors"] = [*(sim.get("rumors") or []), inst]
    sim["rumor_last_perceived_day"] = int(day)
    sim["rumor_born_total"] = int(sim.get("rumor_born_total", 0)) + 1
    _cap_ledger(sim, day)
    name = str((wp._map_index()[0].get(loc) or {}).get("name") or "")
    world = append_news(
        world,
        text=inst["text"],
        location_id=loc,
        location_name=name,
        turn=int(turn),
        source="narrador",
        extra={"kind": "rumor", "rumor_id": inst["rumor_id"], "expires_day": inst["expires_day"]},
    )
    return prune_news(world, day), sim


# --- interface SPEC-313 (investigar_rumor) -------------------------------------------


def investigable(state: dict, day: int) -> list[dict]:
    """Rumores PERCEBIDOS, vivos, `quest_eligible`, sem desfecho e sem segredo. Nunca devolve
    `truth` (a 313 consulta `truth_of` so na resolucao). Rumor falso tambem entra."""
    out: list[dict] = []
    for r in _sim(state).get("rumors") or []:
        if not isinstance(r, dict) or not r.get("perceived_day"):
            continue
        if int(r.get("expires_day", 0)) < int(day) or r.get("resolution"):
            continue
        if not is_quest_eligible(r):
            continue
        if _secret(state, render_news(state, r)) or _secret_locked(state, seed_of(r)):
            continue
        out.append(
            {
                k: r.get(k)
                for k in (
                    "rumor_id",
                    "family",
                    "location_id",
                    "born_day",
                    "expires_day",
                )
            }
            | {"region_id": region_of_row(r), "subject": subject_of(r), "entities": entities_of(r)}
        )
    return out


def truth_of(state: dict, rumor_id: str) -> bool | None:
    """Verdade INTERNA do rumor (None se a instancia nao existe). So a resolucao da 313 chama."""
    inst = instance(state, rumor_id)
    return None if inst is None else bool(inst.get("truth"))


def mark_resolved(sim: dict, rumor_id: str, outcome: str, day: int) -> dict:
    """Unico writer de `resolution` (a 313 chama). Devolve um `world_sim` novo; desfecho
    invalido ou rumor ja resolvido nao muda nada. Nao grava fato: so fecha o rumor."""
    if outcome not in RESOLUTIONS:
        return sim
    rows = []
    last = dict(sim.get("rumor_seed_last_born") or {})
    for r in sim.get("rumors") or []:
        if isinstance(r, dict) and r.get("rumor_id") == rumor_id and not r.get("resolution"):
            r = {**r, "resolution": outcome, "resolved_day": int(day)}
            if r.get("family") == "lore":
                last[_k(str(r.get("seed_id")))] = NEVER_AGAIN
        rows.append(r)
    return {**sim, "rumors": rows, "rumor_seed_last_born": last}
