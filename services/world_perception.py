"""SPEC-302 R22-R25: digest do dia -> o que o JOGADOR percebe (regra de ouro).

O jogador so sabe o que viu ou ouviu: (a) testemunho local, (b) testemunho regional
(templates `regional`), (c) rumor via `location_heard` (SPEC-215 `on`). Nomes de faccao
so aparecem se `faction_intel[id].known` (R24). O texto que persiste em `world.news` e SEMPRE
o render do template, nunca texto da LLM (R25). Puro: sem LLM, sem RNG.
"""

from __future__ import annotations

from functools import lru_cache

from services import world_pressures as wp

NEWS_CAP = 12
SOURCE = "world_engine"


@lru_cache(maxsize=1)
def _merged_templates() -> dict:
    """signals.json + templates dos itens `npc_*` da SPEC-304 (R20)."""
    base = dict(wp._load_json("signals.json"))
    base["templates"] = {
        **base["templates"],
        **wp._load_json("npc_templates.json")["templates"],
    }
    return base


def _templates() -> dict:
    return _merged_templates()


def _cur(state: dict) -> tuple[str, str]:
    loc = str(((state or {}).get("world") or {}).get("current_location_id") or "")
    return loc, wp.region_of(loc)


def _family(location_id: str) -> set[str]:
    """Local + pai + filhos interiores (interior e parte do mesmo lugar)."""
    locs = wp._map_index()[0]
    fam = {location_id}
    loc = locs.get(location_id) or {}
    if loc.get("parent_id"):
        fam.add(str(loc["parent_id"]))
    fam |= {lid for lid, other in locs.items() if other.get("parent_id") == location_id}
    return fam


def _rumor_enabled() -> bool:
    from services import npc_knowledge

    return npc_knowledge.mode() == "on"


def perceivable(state: dict, items: list[dict]) -> list[dict]:
    """Filtra o digest pela posicao de referencia (destino = local atual do `world`)."""
    cur, cur_region = _cur(state)
    if not cur:
        return []
    fam = _family(cur)
    heard = set(((state or {}).get("location_heard") or {}).get(cur, []) or [])
    rumor_on = _rumor_enabled()
    tpls = _templates()["templates"]
    today = int((((state or {}).get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)
    out: list[dict] = []
    from services import rumors as _rumors

    for it in items or []:
        if _rumors.is_rumor_item(it):  # SPEC-312 R12: canais proprios do rumor
            if _rumors.perceivable(state, it):
                out.append(it)
            continue
        tpl = tpls.get(it.get("template_id", ""))
        if not tpl:
            continue
        local = it.get("location_id") in fam
        regional = (
            tpl.get("visibility") == "regional"
            and bool(cur_region)
            and it.get("region_id") == cur_region
        )
        # SPEC-303 R20: a estacao e visivel de qualquer lugar (ceu e frio) — unico tipo `global`
        seen_everywhere = tpl.get("visibility") == "global" and it.get("kind") == "estacao"
        rumor = rumor_on and bool(it.get("subject_id")) and it["subject_id"] in heard
        # SPEC-304 R21 (d): o mensageiro dirigido acha o jogador ONDE ELE ESTIVER, no dia de
        # entrega (testemunho: alguem veio contar). Antes disso o item espera no digest.
        messenger = tpl.get("visibility") == "dirigido" and today >= int(
            (it.get("params") or {}).get("delivery_day", 1 << 30)
        )
        if local or regional or rumor or seen_everywhere or messenger:
            out.append(it)
    return out


def _faction_label(state: dict, fid: str) -> str:
    cfg = _templates()
    if not fid:
        return cfg["unknown_faction_label"]
    intel = (state or {}).get("faction_intel") or {}
    if not (intel.get(fid) or {}).get("known"):
        return cfg["unknown_faction_label"]
    fac = next((f for f in (state or {}).get("factions") or [] if f.get("id") == fid), None)
    if fac is None:
        import gamedata

        fac = gamedata.FACTIONS.get(fid) or {}
    return str(fac.get("name") or cfg["unknown_faction_label"])


def render(state: dict, item: dict) -> str:
    """Template pt-BR do item, sem numeros e sem nomes nao conhecidos (R24)."""
    cfg = _templates()
    tid = item.get("template_id", "")
    params = item.get("params") or {}
    if str(tid).startswith("rumor."):  # SPEC-312: texto do rumor = template + gist da semente
        from services import rumors

        return rumors.render_news(state, rumors.from_item(item))
    if tid == "ascensao.crise.inicio":
        fid = str(params.get("faccao") or "")
        intel = (state or {}).get("faction_intel") or {}
        if not (intel.get(fid) or {}).get("known"):
            tid = "ascensao.crise.desconhecida"
    if tid.startswith("estacao.inicio."):
        # SPEC-303 R6: no norte o rotulo regional vira Noite Longa / Dia Longo
        cur_region = wp.region_of(
            str(((state or {}).get("world") or {}).get("current_location_id") or "")
        )
        from services.world_calendar import label_for

        regional_label = label_for(tid.rsplit(".", 1)[-1], cur_region)
        tid = {
            "Noite Longa": "estacao.inicio.noite_longa",
            "Dia Longo": "estacao.inicio.dia_longo",
        }.get(regional_label, tid)
    tpl = cfg["templates"].get(tid)
    if not tpl:
        return ""
    locs = wp._map_index()[0]
    loc_id = str(params.get("local") or item.get("location_id") or "")
    region = str(item.get("region_id") or "")
    text = tpl["text"]
    values = {
        "local": str((locs.get(loc_id) or {}).get("name") or wp.region_label(region) or "a região"),
        "regiao": wp.region_label(region) or "a região",
        "faccao": _faction_label(state, str(params.get("faccao") or "")),
        "percebido": _ascension_text(state, str(params.get("faccao") or "")),
        "festa": str(params.get("festa") or ""),
        "rotulo": str(params.get("rotulo") or ""),
    }
    if tid.startswith("npc_"):  # SPEC-304 R20: nome so se conhecido; senao um rotulo
        from services import npc_world

        values["npc"] = npc_world.npc_label(state, str(params.get("npc_id") or ""))
        values["destino"] = str(
            (locs.get(str(params.get("destino") or "")) or {}).get("name") or "outro lugar"
        )
    for key, val in values.items():
        text = text.replace("{" + key + "}", val)
    mes = str(params.get("mes") or "")
    if mes and tid.startswith("estacao.inicio."):
        text = f"Começa o mês de {mes}. {text}"  # SPEC-307: rótulo do calendário, não a estação
    return text


def _ascension_text(state: dict, fid: str) -> str:
    import gamedata

    fac = next((f for f in (state or {}).get("factions") or [] if f.get("id") == fid), None)
    fac = fac or gamedata.FACTIONS.get(fid) or {}
    return str((fac.get("ascension") or {}).get("perceived") or "")


def _append(world: dict, **kw) -> dict:
    try:
        from services.ambient import append_news  # SPEC-296 (contrato compartilhado)
    except ImportError:
        append_news = _append_news_fallback
    return append_news(world, **kw)


def _append_news_fallback(
    world, *, text, location_id, location_name, turn, source="world_engine", extra=None
):
    """Mesmo contrato de `services.ambient.append_news` (SPEC-296) enquanto ela nao pousa."""
    new_world = dict(world or {})
    news = [dict(n) for n in (new_world.get("news") or []) if isinstance(n, dict)]
    clean = str(text or "").strip()[:400].rstrip()
    if clean and not any(
        n.get("text") == clean and n.get("location_id") == location_id for n in news
    ):
        clock = new_world.get("world_clock") or {}
        news.append(
            {
                "day": int(clock.get("day", 1) or 1),
                "period": str(clock.get("period", "") or ""),
                "location_id": location_id,
                "location_name": location_name,
                "text": clean,
                "source": source,
                "turn": int(turn),
                **(extra or {}),
            }
        )
    new_world["news"] = news[-NEWS_CAP:]
    return new_world


def record_news(world: dict, state: dict, items: list[dict]) -> dict:
    """R25: grava o TEXTO DO TEMPLATE dos itens percebidos em `world.news` (anel de 12)."""
    out = dict(world or {})
    turn = int(out.get("turn_count", 0) or 0)
    for it in items:
        text = render(state, it)
        if not text:
            continue
        loc_id = str(it.get("location_id") or "")
        name = str((wp._map_index()[0].get(loc_id) or {}).get("name") or "")
        extra = None
        if str(it.get("template_id", "")).startswith("rumor."):
            from services import rumors

            extra = rumors.news_extra(it)
        out = _append(
            out,
            text=text,
            location_id=loc_id,
            location_name=name,
            turn=turn,
            source=SOURCE,
            **({"extra": extra} if extra else {}),
        )
    return out


# --- SPEC-308: regra de ouro para os EVENTOS do motor ---------------------------------


# Tipos do MOTOR DE MUNDO (SPEC-302) que o heroi so conhece se viu/ouviu. Os demais eventos
# `source="engine"` (quest, companheiro, membership, item unico, destino de NPC) sao feitos do
# proprio heroi ou ja tem filtro proprio (SPEC-304).
WORLD_EVENT_TYPES = frozenset(
    {
        "location_state_changed",
        "world_crisis_warning",
        "route_blocked",
        "route_cleared",
        "faction_relation_changed",
        "location_control_changed",
        "companion_fate",  # destino fora de cena: so por crenca (SPEC-304)
    }
)


def _is_engine_derived(ev: dict) -> bool:
    payload = ev.get("payload") or {}
    src = str(ev.get("source") or "")
    if payload.get("offscreen"):
        return False  # SPEC-304 (R23) ja cobre
    if ev.get("actor_id") == "player":
        return False  # feito do proprio heroi (ex.: rota liberada por quest de mundo): testemunho
    if src == "engine":
        return ev.get("type") in WORLD_EVENT_TYPES
    return src == "rule_engine" and bool(payload.get("cause_event_id"))


def event_perceived(state: dict, ev: dict) -> bool:
    """SPEC-308 R3: o heroi pode saber deste evento? Pura, sem I/O.

    Evento que nao e do motor (turno do jogador/narrativa) segue como hoje. Evento do motor
    (ou derivado dele, via `cause_event_id`) so vale se: esta no livro-razao
    `world_sim.perceived_ids`, e crenca conhecida (SPEC-304) ou e testemunho direto (mesmo
    local/familia, no mesmo dia)."""
    if not isinstance(ev, dict) or not _is_engine_derived(ev):
        return True
    payload = ev.get("payload") or {}
    key = str(payload.get("cause_event_id") or ev.get("event_id") or "")
    ledger = set(((state or {}).get("world_sim") or {}).get("perceived_ids") or [])
    if key and key in ledger:
        return True
    from services import npc_world

    if key and key in npc_world._known_sources(state or {}):
        return True
    cur, _region = _cur(state)
    if not cur:
        return False
    world = (state or {}).get("world") or {}
    today = int((world.get("world_clock") or {}).get("day", 1) or 1)
    day = payload.get("day")
    if day is None:  # sem dia no payload: so conta se foi emitido neste turno
        same_day = int(ev.get("turn", -1) or 0) == int(world.get("turn_count", -2) or 0)
    else:
        same_day = int(day) == today
    if not same_day:
        return False
    places = {
        str(x)
        for x in (ev.get("target_id"), payload.get("location_id"), payload.get("other_location_id"))
        if x
    }
    return any(cur in _family(p) for p in places)


def perceived_events(state: dict, events: list | None) -> list[dict]:
    """SPEC-308 R7: so os eventos que o heroi pode saber (para mapa/dossie/API)."""
    return [e for e in events or [] if isinstance(e, dict) and event_perceived(state, e)]


def perceived_projection(state: dict, projection: dict | None = None) -> dict:
    """SPEC-308 R7/P0-1: a projection COMO O HEROI A CONHECE. Remove o que um evento do motor
    nao percebido escreveu: arestas dinamicas (`controls`, `enemy_of`...), desativacoes de aresta
    base (o controlador antigo volta) e rotas bloqueadas. Evento fora do `event_log` (log
    truncado) nao filtra. Copia rasa; nao muta a original."""
    proj = projection if projection is not None else (state or {}).get("world_projection") or {}
    index = {
        str(e.get("event_id")): e
        for e in (state or {}).get("event_log") or []
        if isinstance(e, dict) and e.get("event_id")
    }

    def ok(event_id) -> bool:
        ev = index.get(str(event_id or ""))
        return ev is None or event_perceived(state, ev)

    out = dict(proj)
    for key, field in (
        ("dynamic_edges", "created_by_event"),
        ("disabled_edges", "disabled_by_event"),
        ("blocked_routes", "blocked_by_event"),
    ):
        if proj.get(key):
            out[key] = [r for r in proj[key] if not isinstance(r, dict) or ok(r.get(field))]
    return out


def hidden_blocked_route_events(state: dict, a: str, b: str) -> list[str]:
    """SPEC-309 F2 (SPEC-308 review): ids dos eventos do motor que bloqueiam a rota a<->b e que o
    heroi ainda NAO percebeu. Ao tentar viajar por ela, ele descobre o bloqueio."""
    pair = frozenset((a, b))
    index = {
        str(e.get("event_id")): e
        for e in (state or {}).get("event_log") or []
        if isinstance(e, dict) and e.get("event_id")
    }
    out: list[str] = []
    for r in ((state or {}).get("world_projection") or {}).get("blocked_routes") or []:
        if not isinstance(r, dict) or frozenset((r.get("a"), r.get("b"))) != pair:
            continue
        ev = index.get(str(r.get("blocked_by_event") or ""))
        if ev is not None and not event_perceived(state, ev):
            out.append(str(ev["event_id"]))
    return out
