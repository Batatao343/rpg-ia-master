"""SPEC-302 R22-R25: digest do dia -> o que o JOGADOR percebe (regra de ouro).

O jogador so sabe o que viu ou ouviu: (a) testemunho local, (b) testemunho regional
(templates `regional`), (c) rumor via `location_heard` (SPEC-215 `on`). Nomes de faccao
so aparecem se `faction_intel[id].known` (R24). O texto que persiste em `world.news` e SEMPRE
o render do template, nunca texto da LLM (R25). Puro: sem LLM, sem RNG.
"""

from __future__ import annotations

from services import world_pressures as wp

NEWS_CAP = 12
SOURCE = "world_engine"


def _templates() -> dict:
    return wp._load_json("signals.json")


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
    out: list[dict] = []
    for it in items or []:
        tpl = tpls.get(it.get("template_id", ""))
        if not tpl:
            continue
        local = it.get("location_id") in fam
        regional = (
            tpl.get("visibility") == "regional"
            and bool(cur_region)
            and it.get("region_id") == cur_region
        )
        rumor = rumor_on and bool(it.get("subject_id")) and it["subject_id"] in heard
        if local or regional or rumor:
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
    if tid == "ascensao.crise.inicio":
        fid = str(params.get("faccao") or "")
        intel = (state or {}).get("faction_intel") or {}
        if not (intel.get(fid) or {}).get("known"):
            tid = "ascensao.crise.desconhecida"
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
    }
    for key, val in values.items():
        text = text.replace("{" + key + "}", val)
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


def _append_news_fallback(world, *, text, location_id, location_name, turn, source="world_engine"):
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
        out = _append(
            out, text=text, location_id=loc_id, location_name=name, turn=turn, source=SOURCE
        )
    return out
