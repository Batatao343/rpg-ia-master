"""SPEC-296 R4/R6: bloco de ambiente único + notícias percebidas (puro, sem LLM/RNG).

`ambient_block` monta o `<AMBIENTE>` que storyteller/npc_actor/combate injetam no
prompt; `append_news` guarda o que o herói OUVIU (regra de ouro: o jogador só sabe o
que viu ou ouviu) em `world["news"]`.
"""

from __future__ import annotations

from typing import Literal

NEWS_CAP = 12
NEWS_TEXT_MAX = 280  # SPEC-296 review P2-1: rumor vem do LLM; corta antes de persistir


def danger_words(level: int) -> str:
    """Perigo em palavras: 1–2 tranquilo, 3 tenso, 4 perigoso, ≥5 mortal."""
    try:
        n = int(level)
    except (TypeError, ValueError):
        n = 1
    if n >= 5:
        return "mortal"
    if n == 4:
        return "perigoso"
    if n == 3:
        return "tenso"
    return "tranquilo"


def _ambient_block(
    world: dict,
    player: dict,
    *,
    audience: Literal["story", "npc", "combat"],
) -> str:
    """Bloco `<AMBIENTE>` determinístico. Saídas só para `audience="story"`."""
    import gamedata
    from world_utils import (
        _SHELTER_TAGS,
        clock_label,
        effective_danger,
        light_level,
        weather_effects,
    )

    world = world or {}
    player = player or {}
    loc_id = world.get("current_location_id", "")
    loc = gamedata.get_location(loc_id) or {}

    lines = [f"Momento: {clock_label(world)}"]

    # Clima local (sem o fenômeno global) + fenômeno global quando houver.
    local = weather_effects({**world, "weather_global": None})
    local_label = str(local.get("label") or "").strip()
    if local_label:
        lines.append(f"Clima local: {local_label}")
    if world.get("weather_global"):
        glabel = weather_effects(world).get("label") or "clima anômalo"
        lines.append(
            f"Fenômeno global ativo: {glabel}. Ele domina o céu e afeta toda a cena; "
            "mencione sua presença e consequências sensoriais."
        )

    ll = light_level(world, player)
    label = ll.get("label", "claro")
    lines.append(f"Luz: {label}")
    if ll.get("dark"):
        lines.append(
            "Está ESCURO e o herói NÃO tem fonte de luz: descreva a visão limitada — "
            "sombras, sons e cheiros antes de formas; o perigo pode surgir de perto."
        )
    elif label == "iluminado pela sua luz":
        lines.append(
            "A luz que o herói carrega empurra a escuridão num círculo trêmulo; "
            "além dele, o breu. Mencione a luz."
        )

    lines.append(f"Perigo: {danger_words(effective_danger(world))}")
    if _SHELTER_TAGS & set(loc.get("tags") or []):
        lines.append("Abrigo: o local oferece abrigo do clima")

    if audience == "story":
        exits = [c.get("name", "") for c in gamedata.get_connections(loc_id) if c.get("name")]
        if exits:
            lines.append("Saídas: " + ", ".join(exits))

    body = "\n    ".join(lines)
    return f"<AMBIENTE>\n    {body}\n    </AMBIENTE>"


def append_news(
    world: dict,
    *,
    text: str,
    location_id: str,
    location_name: str,
    turn: int,
    source: str = "pulse",
) -> dict:
    """Anexa uma notícia percebida a `world["news"]` (FIFO 12, sem vazio/duplicata).
    Devolve um world NOVO; não muta o original."""
    new_world = dict(world or {})
    news = [dict(n) for n in (new_world.get("news") or []) if isinstance(n, dict)]
    clean = str(text or "").strip()[:NEWS_TEXT_MAX].rstrip()
    if not clean:
        new_world["news"] = news
        return new_world
    if any(n.get("text") == clean and n.get("location_id") == location_id for n in news):
        new_world["news"] = news
        return new_world
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


def heard_block(world: dict, limit: int = 3) -> str:
    """R7: `<OUVIU_DIZER>` com as últimas notícias (vazio se não houver)."""
    news = [n for n in ((world or {}).get("news") or []) if isinstance(n, dict)]
    if not news:
        return ""
    rows = [
        f"- (Dia {n.get('day', '?')}, {n.get('location_name', '?')}) {n.get('text', '')}"
        for n in news[-limit:]
    ]
    return (
        "<OUVIU_DIZER>\n    O herói ouviu estes rumores. Pode referenciar se fizer sentido; "
        "não invente detalhes além do texto.\n    " + "\n    ".join(rows) + "\n    </OUVIU_DIZER>"
    )


def ambient_block(
    world: dict,
    player: dict,
    *,
    audience: Literal["story", "npc", "combat"],
) -> str:
    """Ambientação é opcional: erro aqui nunca derruba o turno (review P2-2)."""
    try:
        return _ambient_block(world, player, audience=audience)
    except Exception as exc:  # noqa: BLE001
        from observability.telemetry import log_fallback

        log_fallback("ambient", "ambient_block_failed", exc)
        return ""
