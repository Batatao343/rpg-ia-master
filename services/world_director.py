"""SPEC-302 R11-R15: diretor de tensao (orcamento global de crises).

Fases `calmo -> tensao -> crise -> recuperacao`, aviso obrigatorio >= MIN_WARNING_DAYS
antes de toda crise, teto de crises simultaneas, cooldown por regiao, intervalo global e
ciclo da crise (abrir, escalar, encerrar). `request_crisis_slot` e a UNICA porta para
abrir uma crise (as specs filhas usam a mesma, entao o orcamento e global de verdade).

Tudo e funcao pura do `sim` + rng seeded; nada le o heroi.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from services import location_states as ls
from services import world_pressures as wp

PRESSURE_KINDS = wp.KINDS
_SIGNAL_TPL = {
    "guerra": "guerra.aviso.cerco",
    "fome": "fome.aviso.escassez",
    "praga": "praga.aviso.surto",
    "abismo": "abismo.aviso.rachadura",
    "ascensao": "ascensao.aviso",
}


def _dc(cfg: dict | None = None) -> dict:
    return wp.director_constants(cfg)


def _h(*parts: Any, n: int = 16) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:n]


def crisis_id(
    game_id: str, kind: str, region_id: str, warned_day: int, faction_id: str = ""
) -> str:
    return _h(game_id, kind, region_id, warned_day, faction_id)


def event_id(game_id: str, etype: str, day: int, target: str, extra: str = "") -> str:
    """Id DETERMINISTICO de GameEvent do motor (R2: replay produz o mesmo id)."""
    return _h(game_id, etype, day, target, extra, n=32)


def digest_item(
    game_id: str,
    day: int,
    kind: str,
    region_id: str,
    location_id: str,
    template_id: str,
    params: dict | None = None,
    subject_id: str = "",
) -> dict:
    item = {
        "item_id": _h(game_id, day, kind, region_id, location_id, template_id, n=12),
        "day": int(day),
        "kind": kind,
        "region_id": region_id,
        "location_id": location_id,
        "template_id": template_id,
        "params": dict(params or {}),
    }
    if subject_id:
        item["subject_id"] = subject_id
    return item


# --- consultas ---------------------------------------------------------------------


def active_crises(sim: dict) -> list[dict]:
    return [
        c
        for c in sim.get("crises", [])
        if c.get("start_day") is not None and c.get("end_day") is None
    ]


def announced_crises(sim: dict) -> list[dict]:
    return [
        c for c in sim.get("crises", []) if c.get("start_day") is None and c.get("end_day") is None
    ]


def _find_announced(sim: dict, region_id: str, kind: str, faction_id: str = "") -> dict | None:
    for c in announced_crises(sim):
        if c.get("region_id") == region_id and c.get("kind") == kind:
            if not faction_id or c.get("faction_id") == faction_id:
                return c
    return None


def _has_record(sim: dict, region_id: str, kind: str, faction_id: str = "") -> bool:
    for c in sim.get("crises", []):
        if c.get("end_day") is None and c.get("region_id") == region_id and c.get("kind") == kind:
            if not faction_id or c.get("faction_id") == faction_id:
                return True
    return False


def update_phase(sim: dict, day: int) -> dict:
    """R11: `crise` > `recuperacao` > `tensao` > `calmo` (mutacao in place, devolve sim)."""
    if active_crises(sim):
        phase = "crise"
    elif day < int(sim.get("recovery_until_day", 0)):
        phase = "recuperacao"
    elif announced_crises(sim):
        phase = "tensao"
    else:
        phase = "calmo"
    if sim.get("phase") != phase:
        sim["phase"] = phase
        sim["phase_since_day"] = int(day)
    return sim


# --- orcamento (R12) ---------------------------------------------------------------


def _can_open(sim: dict, day: int, region_id: str, cfg: dict | None = None) -> bool:
    c = _dc(cfg)
    act = active_crises(sim)
    if len(act) >= int(c["MAX_ACTIVE_CRISES"]):
        return False
    if any(a.get("region_id") == region_id for a in act):
        return False
    last_end = (sim.get("region_last_crisis_end") or {}).get(region_id)
    if last_end is not None and day - int(last_end) < int(c["REGION_COOLDOWN_DAYS"]):
        return False
    last_start = sim.get("last_crisis_start_day")
    if last_start is not None and day - int(last_start) < int(c["GLOBAL_GAP_DAYS"]):
        return False
    if not act and day < int(sim.get("recovery_until_day", 0)):
        return False  # fase recuperacao
    return True


def _try_open(sim: dict, rec: dict, day: int, cfg: dict | None = None) -> bool:
    c = _dc(cfg)
    if rec.get("start_day") is not None or rec.get("end_day") is not None:
        return False
    if day - int(rec.get("warned_day", day)) < int(c["MIN_WARNING_DAYS"]):
        return False  # R13: aviso previo >= MIN_WARNING_DAYS
    if not _can_open(sim, day, str(rec.get("region_id", "")), cfg):
        return False
    rec["start_day"] = int(day)
    rec["escalation_day"] = int(day) + int(c["ESCALATION_DAYS"])
    rec["severity"] = 1
    sim["last_crisis_start_day"] = int(day)
    return True


def request_crisis_slot(
    sim: dict, day: int, region_id: str, kind: str, cfg: dict | None = None
) -> bool:
    """R15: unica porta para abrir crise. Exige crise ANUNCIADA (mesma regiao e tipo) ha
    >= MIN_WARNING_DAYS e orcamento livre; ao conceder, registra a crise como ativa."""
    rec = _find_announced(sim, region_id, kind)
    return bool(rec) and _try_open(sim, rec, day, cfg)


def announce(
    sim: dict,
    day: int,
    region_id: str,
    kind: str,
    rng: Any = None,
    *,
    game_id: str = "",
    faction_id: str = "",
    cfg: dict | None = None,
) -> dict | None:
    """Registra o AVISO (R13). Nao abre. Respeita calma inicial, bloqueio pos-expiracao,
    teto de avisos+ativas e o cooldown da regiao. Devolve o registro ou None."""
    del rng
    c = _dc(cfg)
    if day < int(sim.get("calm_until_day", 0)):
        return None
    if _has_record(sim, region_id, kind, faction_id):
        return None
    block = (sim.get("announce_block") or {}).get(f"{region_id}|{kind}|{faction_id}", -1)
    if day < int(block):
        return None
    if len(active_crises(sim)) + len(announced_crises(sim)) >= int(c["MAX_ACTIVE_CRISES"]):
        return None
    last_end = (sim.get("region_last_crisis_end") or {}).get(region_id)
    if last_end is not None and day + int(c["MIN_WARNING_DAYS"]) - int(last_end) < int(
        c["REGION_COOLDOWN_DAYS"]
    ):
        return None
    rec = {
        "crisis_id": crisis_id(game_id, kind, region_id, day, faction_id),
        "kind": kind,
        "region_id": region_id,
        "location_id": "",
        "loc_state": ls.CRISIS_STATE.get(kind, ""),
        "faction_id": faction_id,
        "warned_day": int(day),
        "start_day": None,
        "escalation_day": None,
        "severity": 0,
        "end_day": None,
        "resolution": "",
    }
    sim.setdefault("crises", []).append(rec)
    return rec


# --- ciclo de vida -----------------------------------------------------------------


def end_crisis(sim: dict, rec: dict, day: int, resolution: str, cfg: dict | None = None) -> None:
    rec["end_day"] = int(day)
    rec["resolution"] = resolution
    if rec.get("start_day") is not None:
        sim.setdefault("region_last_crisis_end", {})[rec["region_id"]] = int(day)
        if not active_crises(sim):
            sim["recovery_until_day"] = int(day) + int(_dc(cfg)["RECOVERY_DAYS"])
    # poda: ativas+anunciadas + ultimas 30 encerradas
    done = [c for c in sim["crises"] if c.get("end_day") is not None]
    keep_done = done[-30:]
    sim["crises"] = [c for c in sim["crises"] if c.get("end_day") is None or c in keep_done]


def _liberation_mult() -> int:
    return int(wp._load_json("world_quests.json")["constants"]["LIBERATION_MULT"])


def relieve(sim: dict, crisis_id: str, day: int) -> dict:
    """SPEC-305 R13: contra-jogo. Marca `relieved_day` na crise vigente: ela NAO escala mais e
    encerra com `resolution="intervencao"` quando a pressao cai (writer que faltava). Aviso de
    ascensao e retirado na hora. Idempotente; mutacao in place, devolve `sim`."""
    for rec in sim.get("crises", []):
        if rec.get("crisis_id") != crisis_id or rec.get("end_day") is not None:
            continue
        if rec.get("relieved_day") is None:
            rec["relieved_day"] = int(day)
        if rec.get("kind") == "ascensao" and rec.get("start_day") is None:
            end_crisis(sim, rec, day, "intervencao")
            sim.setdefault("announce_block", {})[
                f"{rec['region_id']}|ascensao|{rec.get('faction_id', '')}"
            ] = int(day) + int(_dc()["ANNOUNCE_BLOCK_DAYS"])
    return sim


def _attacker(
    region_id: str, factions: list, rng: Any, faction_region: Callable[[dict], str | None]
) -> str:
    """Faccao atacante (R14): da regiao (hostil primeiro); senao de regiao adjacente."""
    adj = set(wp.region_adjacency().get(region_id, []))
    for scope in ({region_id}, adj):
        pool = [
            f
            for f in factions
            if isinstance(f, dict) and not f.get("defeated") and (faction_region(f) in scope)
        ]
        pool.sort(key=lambda f: (f.get("disposition") != "hostil", str(f.get("id"))))
        roll = rng.random()
        if pool:
            hostile = [f for f in pool if f.get("disposition") == "hostil"] or pool
            return str(hostile[int(roll * len(hostile)) % len(hostile)].get("id"))
    return ""


def _siege_route(target: str, attacker_region: str) -> tuple[str, str] | None:
    """Conexao do alvo rumo a regiao do atacante (senao a primeira cross-region)."""
    locs = wp._map_index()[0]
    loc = locs.get(target) or {}
    own = loc.get("region_id")
    opts = sorted(
        c
        for c in (loc.get("connections") or [])
        if locs.get(c, {}).get("region_id") not in (None, own)
    )
    if not opts:  # sem saida para outra regiao: bloqueia a ligacao com um vizinho exterior
        opts = sorted(
            c for c in (loc.get("connections") or []) if locs.get(c, {}).get("kind") != "interior"
        )
    if not opts:
        return None
    pref = [c for c in opts if locs[c].get("region_id") == attacker_region]
    return (target, (pref or opts)[0])


def controller_of(projection: dict, location_id: str) -> str:
    """Controlador vigente do local no grafo (base - disabled + dynamic), ou ''."""
    from services import graph_resolver as gr

    try:
        edges = gr.resolve_edges(projection or {}, edge_type="controls", include_hidden=True)
    except Exception:  # silent-ok: grafo ausente/saves antigos => sem controlador conhecido
        return ""
    for e in edges:
        if e.get("target") == location_id:
            return str(e.get("source") or "")
    return ""


def _ev(game_id: str, day: int, etype: str, target: str, payload: dict, extra: str = "") -> dict:
    return {
        "type": etype,
        "actor_id": "engine",
        "target_id": target,
        "detail": "",
        "payload": payload,
        "source": "engine",
        "event_id": event_id(game_id, etype, day, target, extra),
    }


def _state_event(
    game_id: str, day: int, rec: dict, new_state: str, previous: str, severity: int, tag: str
) -> dict:
    payload = {
        "state": new_state,
        "previous": previous,
        "severity": int(severity),
        "crisis_id": rec["crisis_id"],
        "cause": rec["kind"],
        "day": int(day),
    }
    if rec.get("faction_id"):
        payload["faction_id"] = rec["faction_id"]
    return _ev(game_id, day, "location_state_changed", rec["location_id"], payload, tag)


def step_crises(
    sim: dict,
    day: int,
    projection: dict,
    rng: Any,
    *,
    game_id: str = "",
    factions: list | None = None,
    faction_region: Callable[[dict], str | None] | None = None,
    enabled_emit: bool = True,
    cfg: dict | None = None,
) -> tuple[dict, list[dict], list[dict]]:
    """Um dia do diretor: encerra/escala ativas, expira avisos, anuncia e abre crises de
    PRESSAO. Devolve `(sim, eventos_do_motor, digest)`. `enabled_emit=False` (shadow)
    mantem o estado do diretor mas devolve listas vazias."""
    c = _dc(cfg)
    k = wp.constants(cfg)
    factions = factions or []
    faction_region = faction_region or (lambda f: None)
    events: list[dict] = []
    digest: list[dict] = []
    pressures = sim.get("pressures") or {}
    proj_rows = dict((projection or {}).get("location_states") or {})
    blocked = {
        frozenset((r.get("a"), r.get("b")))
        for r in (projection or {}).get("blocked_routes", []) or []
    }

    def pval(rec: dict) -> int:
        return int((pressures.get(rec["region_id"]) or {}).get(rec["kind"], 0))

    # 1. ativas: encerrar / escalar
    for rec in list(active_crises(sim)):
        kind = rec["kind"]
        age = day - int(rec["start_day"])
        if kind == "ascensao":
            if age >= int(c["ASCENSION_CRISIS_DAYS"]):
                end_crisis(sim, rec, day, "recuperou", cfg)
            continue
        if kind not in PRESSURE_KINDS:
            continue
        route = rec.get("route")
        if route and kind == "guerra" and frozenset(route) not in blocked:
            # alguem (o jogador) desbloqueou a rota do cerco: o cerco perde a razao de ser
            _close_state(
                sim, rec, day, game_id, events, digest, "intervencao", route_cleared=False, cfg=cfg
            )
            continue
        relieved = rec.get("relieved_day") is not None
        if pval(rec) < int(k["RECUPERA"]) and age >= int(c["MIN_CRISIS_DAYS"]):
            _close_state(
                sim,
                rec,
                day,
                game_id,
                events,
                digest,
                "intervencao" if relieved else "recuperou",
                route_cleared=True,
                cfg=cfg,
            )
            continue
        if day >= int(rec["escalation_day"]):
            # SPEC-305 R13: crise aliviada nao escala (o prazo da proxima janela anda).
            if pval(rec) >= int(k["CRISE"]) and not relieved:
                if kind == "guerra" and int(rec["severity"]) >= 3:
                    _occupy(sim, rec, day, game_id, events, digest, factions, projection, cfg)
                    continue
                if int(rec["severity"]) < 3:
                    rec["severity"] = int(rec["severity"]) + 1
                    if rec["loc_state"] and rec["location_id"]:
                        events.append(
                            _state_event(
                                game_id,
                                day,
                                rec,
                                rec["loc_state"],
                                rec["loc_state"],
                                rec["severity"],
                                f"esc{rec['severity']}",
                            )
                        )
                        digest.append(
                            digest_item(
                                game_id,
                                day,
                                "escala",
                                rec["region_id"],
                                rec["location_id"],
                                f"{kind}.crise.escala",
                                {"local": rec["location_id"], "faccao": rec.get("faction_id", "")},
                                subject_id=events[-1]["event_id"],
                            )
                        )
            rec["escalation_day"] = day + int(c["ESCALATION_DAYS"])

    # 2. avisos vencidos: pressao caiu ou TTL
    for rec in list(announced_crises(sim)):
        if rec["kind"] == "ascensao":
            continue  # tratada pelo motor (progresso de faccao)
        stale = day - int(rec["warned_day"]) > int(c["WARNING_TTL_DAYS"])
        fell = pval(rec) < int(k["RECUPERA"])
        if stale or fell or rec.get("relieved_day") is not None:
            end_crisis(
                sim,
                rec,
                day,
                "intervencao" if rec.get("relieved_day") is not None else "expirou_aviso",
                cfg,
            )
            sim.setdefault("announce_block", {})[
                f"{rec['region_id']}|{rec['kind']}|{rec.get('faction_id', '')}"
            ] = day + int(c["ANNOUNCE_BLOCK_DAYS"])

    # 3. anunciar: bandas em crise sem registro (ordem: pressao desc, region_id, kind)
    cands = []
    for r in sorted(pressures):
        for kind in PRESSURE_KINDS:
            if (sim.get("bands", {}).get(r) or {}).get(kind) == "crise":
                cands.append((-int(pressures[r][kind]), r, kind))
    cands.sort()
    for _, r, kind in cands:
        rec = announce(sim, day, r, kind, rng, game_id=game_id, cfg=cfg)
        if rec is None:
            continue
        rec["location_id"] = ""
        loc = wp.region_primary_location(r)
        ev = _ev(
            game_id,
            day,
            "world_crisis_warning",
            loc,
            {
                "kind": kind,
                "region_id": r,
                "crisis_id": rec["crisis_id"],
                "earliest_day": day + int(c["MIN_WARNING_DAYS"]),
            },
        )
        events.append(ev)
        digest.append(
            digest_item(
                game_id,
                day,
                "aviso",
                r,
                loc,
                _SIGNAL_TPL[kind],
                {"local": loc},
                subject_id=ev["event_id"],
            )
        )

    # 4. abrir: anunciadas maduras (pressao desc, region_id; desempate = rng)
    ready = [
        rec
        for rec in announced_crises(sim)
        if rec["kind"] in PRESSURE_KINDS
        and day - int(rec["warned_day"]) >= int(c["MIN_WARNING_DAYS"])
        and (sim.get("bands", {}).get(rec["region_id"]) or {}).get(rec["kind"]) == "crise"
    ]
    ties = {
        id(rec): rng.random() for rec in sorted(ready, key=lambda x: (x["region_id"], x["kind"]))
    }
    ready.sort(key=lambda rec: (-pval(rec), rec["region_id"], ties[id(rec)]))
    for rec in ready:
        if not _can_open(sim, day, rec["region_id"], cfg):
            continue
        target = ls.pick_crisis_target(
            rec["region_id"], rec["kind"], {"location_states": proj_rows}, rng
        )
        if target is None:
            end_crisis(sim, rec, day, "expirou_aviso", cfg)
            continue
        if not _try_open(sim, rec, day, cfg):
            continue
        rec["location_id"] = target
        proj_rows[target] = {"state": rec["loc_state"]}
        if rec["kind"] == "guerra":
            rec["faction_id"] = _attacker(rec["region_id"], factions, rng, faction_region)
            att = next((f for f in factions if f.get("id") == rec["faction_id"]), None)
            att_region = (faction_region(att) if att else "") or ""
            route = _siege_route(target, att_region)
            if route and frozenset(route) not in blocked:
                rec["route"] = list(route)
                events.append(
                    _ev(
                        game_id,
                        day,
                        "route_blocked",
                        route[0],
                        {"other_location_id": route[1], "crisis_id": rec["crisis_id"]},
                    )
                )
            else:
                rec.pop("route", None)
        sev_ev = _state_event(game_id, day, rec, rec["loc_state"], "", 1, "open")
        events.append(sev_ev)
        digest.append(
            digest_item(
                game_id,
                day,
                "crise",
                rec["region_id"],
                target,
                f"{rec['kind']}.crise.inicio",
                {"local": target, "faccao": rec.get("faction_id", "")},
                subject_id=sev_ev["event_id"],
            )
        )

    if not enabled_emit:
        return sim, [], []
    return sim, events, digest


def _close_state(
    sim: dict,
    rec: dict,
    day: int,
    game_id: str,
    events: list,
    digest: list,
    resolution: str,
    *,
    route_cleared: bool,
    cfg: dict | None = None,
) -> None:
    prev = rec.get("loc_state", "")
    if rec.get("location_id") and prev:
        ev = _state_event(game_id, day, rec, "", prev, 0, "end")
        events.append(ev)
        digest.append(
            digest_item(
                game_id,
                day,
                "fim",
                rec["region_id"],
                rec["location_id"],
                f"{rec['kind']}.crise.fim",
                {"local": rec["location_id"], "faccao": rec.get("faction_id", "")},
                subject_id=ev["event_id"],
            )
        )
    route = rec.get("route")
    if route and route_cleared:
        events.append(
            _ev(
                game_id,
                day,
                "route_cleared",
                route[0],
                {"other_location_id": route[1], "crisis_id": rec["crisis_id"]},
            )
        )
    end_crisis(sim, rec, day, resolution, cfg)


def _occupy(
    sim: dict,
    rec: dict,
    day: int,
    game_id: str,
    events: list,
    digest: list,
    factions: list,
    projection: dict,
    cfg: dict | None = None,
) -> None:
    """Cerco sev 3 escalado: `ocupado` (atacante e faccao viva) ou `ruina` (R14)."""
    fid = rec.get("faction_id") or ""
    att = next((f for f in factions if f.get("id") == fid and not f.get("defeated")), None)
    new_state = "ocupado" if att else "ruina"
    ev = _state_event(
        game_id, day, {**rec, "kind": "guerra"}, new_state, rec.get("loc_state", ""), 1, "occupy"
    )
    ev["payload"]["prev_state"] = rec.get("loc_state", "")
    ev["payload"]["prev_controller"] = controller_of(projection, rec["location_id"])
    events.append(ev)
    if att:
        events.append(
            _ev(
                game_id,
                day,
                "location_control_changed",
                rec["location_id"],
                {"new_controller_id": fid, "crisis_id": rec["crisis_id"]},
            )
        )
    route = rec.get("route")
    if route:
        events.append(
            _ev(
                game_id,
                day,
                "route_cleared",
                route[0],
                {"other_location_id": route[1], "crisis_id": rec["crisis_id"]},
            )
        )
    digest.append(
        digest_item(
            game_id,
            day,
            "escala",
            rec["region_id"],
            rec["location_id"],
            f"{new_state}.crise.escala",
            {"local": rec["location_id"], "faccao": fid if att else ""},
            subject_id=ev["event_id"],
        )
    )
    rec["loc_state"] = ""  # o estado novo ja nao pertence a crise
    end_crisis(sim, rec, day, "escalou", cfg)


def recovery_step(
    sim: dict,
    day: int,
    projection: dict,
    rng: Any,
    *,
    game_id: str = "",
    factions: list | None = None,
    cfg: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    """R20: `ruina` recupera (passando por `escassez` sev 1) e `ocupado` termina.
    Devolve `(eventos, digest)`. Atualiza `sim['war_calm_days']`."""
    c = _dc(cfg)
    k = wp.constants(cfg)
    factions = factions or []
    pressures = sim.get("pressures") or {}
    calm = sim.setdefault("war_calm_days", {})
    for r in sorted(pressures):
        calm[r] = calm.get(r, 0) + 1 if int(pressures[r]["guerra"]) < int(k["RECUPERA"]) else 0
    rows = (projection or {}).get("location_states") or {}
    events: list[dict] = []
    digest: list[dict] = []
    alive = {f.get("id") for f in factions if isinstance(f, dict) and not f.get("defeated")}
    known = {f.get("id") for f in factions if isinstance(f, dict)}

    def state_ev(loc: str, new: str, prev: str, sev: int, tag: str) -> dict:
        return _ev(
            game_id,
            day,
            "location_state_changed",
            loc,
            {
                "state": new,
                "previous": prev,
                "severity": sev,
                "crisis_id": "",
                "cause": "recuperacao",
                "day": int(day),
            },
            tag,
        )

    for loc in sorted(rows):
        row = rows[loc] or {}
        st = row.get("state")
        region = wp.region_of(loc)
        since = int(row.get("since_day", day) or day)
        roll = rng.random()  # sempre sorteia
        if st == "ruina":
            quiet = not any(a.get("region_id") == region for a in active_crises(sim)) and all(
                int((pressures.get(region) or {}).get(kk, 0)) < int(k["SINAL"])
                for kk in PRESSURE_KINDS
            )
            if day - since >= int(c["RUIN_RECOVERY_DAYS"]) and quiet:
                events.append(state_ev(loc, "escassez", "ruina", 1, "ruin_rec"))
        elif st == "escassez" and row.get("cause") == "recuperacao":
            if day - since >= int(c["RUIN_ESCASSEZ_DAYS"]):
                events.append(state_ev(loc, "", "escassez", 0, "ruin_end"))
        elif st == "ocupado":
            occupier = str(row.get("faction_id") or "")
            defeated = bool(occupier) and occupier in known and occupier not in alive
            # SPEC-305 R13/R17: libertacao (alivio) multiplica a chance de retomada; a quest
            # de libertar falhada consolida a ocupacao (so termina com a faccao derrotada).
            p_retake = float(c["REOCCUPY_P"])
            if row.get("liberation_day") is not None:
                p_retake *= float(_liberation_mult())
            consolidated = day < int(row.get("consolidated_until_day", 0) or 0)
            calmed = (
                not consolidated
                and calm.get(region, 0) >= int(c["OCCUPATION_CALM_DAYS"])
                and roll < p_retake
            )
            if defeated or calmed:
                events.append(state_ev(loc, "", "ocupado", 0, "occ_end"))
                prev = str(row.get("prev_controller") or "")
                if prev and prev in alive:
                    events.append(
                        _ev(
                            game_id,
                            day,
                            "location_control_changed",
                            loc,
                            {"new_controller_id": prev, "crisis_id": ""},
                            "reoccupy",
                        )
                    )
                digest.append(
                    digest_item(
                        game_id,
                        day,
                        "fim",
                        region,
                        loc,
                        "guerra.crise.fim",
                        {"local": loc},
                        subject_id=events[-1]["event_id"],
                    )
                )
    return events, digest
