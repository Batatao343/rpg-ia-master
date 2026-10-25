"""SPEC-309: o mundo COMO O HEROI O PERCEBE, em texto para os prompts.

Puro e deterministico: sem LLM, sem RAG, sem RNG. So entra o que o heroi viu ou ouviu
(presenca no local, ou evento do motor que `world_perception.event_perceived` libera). Nunca
numeros, severidade, pressao, fase do diretor nem locais/fações que o heroi nao conhece.
"""

from __future__ import annotations

from typing import Literal

Audience = Literal["story", "npc", "combat", "day"]

MAX_LINES: int = 4  # [BALANCEAR]
MAX_TOKENS: int = 120  # [BALANCEAR]
DAY_FACTS_MAX: int = 6  # [BALANCEAR]

INSTRUCTION = (
    "Fatos do mundo que o herói percebe. Pode ambientar a cena com eles; "
    "não invente causa, duração nem gravidade."
)

_ENGINE_TYPES = ("location_state_changed", "world_crisis_warning")
_CRISIS_LINES_MAX = 2


def _world(state: dict) -> dict:
    return (state or {}).get("world") or {}


def _today(state: dict) -> int:
    return int((_world(state).get("world_clock") or {}).get("day", 1) or 1)


def _loc_name(location_id: str) -> str:
    import gamedata

    return str((gamedata.get_location(location_id) or {}).get("name") or "")


def _local_state_lines(state: dict, cur: str) -> list[str]:
    from services import location_states

    row = location_states.location_state(state, cur)
    if not row:
        return []
    label = location_states.public_label(row)
    here = _loc_name(location_states._resolve_id(cur))
    if not label or not here:
        return []
    if row.get("state") == "festa" and row.get("festival_id"):
        from services import world_calendar

        fest = world_calendar._festival(str(row["festival_id"])) or {}
        if fest.get("name"):
            return [f"Hoje: {fest['name']} — {here} está {label}."]
    return [f"{here} está {label}."]


def _upcoming_festival_lines(state: dict, cur: str) -> list[str]:
    from services import location_states, world_calendar

    sim = (state or {}).get("world_sim") or {}
    herald = int(world_calendar.constants()["FESTIVAL_HERALD_DAYS"])
    today = _today(state)
    here = location_states._resolve_id(cur)
    active = (location_states.location_state(state, cur) or {}).get("festival_id")
    out: list[str] = []
    for rec in sorted(
        (r for r in sim.get("festivals") or [] if isinstance(r, dict)),
        key=lambda r: (int(r.get("start_day", 0) or 0), str(r.get("festa_id", ""))),
    ):
        if rec.get("status") != "anunciada" or rec.get("festival_id") == active:
            continue
        fest = world_calendar._festival(str(rec.get("festival_id") or "")) or {}
        if here not in (fest.get("location_ids") or []) or not fest.get("name"):
            continue
        ahead = int(rec.get("start_day", 0) or 0) - today
        if 0 <= ahead <= herald:
            out.append(f"Nos próximos dias: {fest['name']}.")
    return out[:1]


def _crisis_lines(state: dict, cur: str) -> list[str]:
    """Ultima versao PERCEBIDA de cada crise da regiao atual (nunca `world_sim.crises`)."""
    from services import world_perception
    from services import world_pressures as wp
    from services.context_builder import CRISIS_LABELS
    from services.location_states import _resolve_id, public_label

    region = wp.region_of(cur)
    if not region:
        return []
    last: dict[str, tuple[int, dict]] = {}
    for idx, ev in enumerate((state or {}).get("event_log") or []):
        if not isinstance(ev, dict) or ev.get("type") not in _ENGINE_TYPES:
            continue
        payload = ev.get("payload") or {}
        if payload.get("cause") == "calendario" or not payload.get("crisis_id"):
            continue
        ev_region = str(payload.get("region_id") or "") or wp.region_of(
            str(payload.get("location_id") or ev.get("target_id") or "")
        )
        if ev_region != region or not world_perception.event_perceived(state, ev):
            continue
        last[str(payload["crisis_id"])] = (idx, ev)
    here = _resolve_id(cur)
    lines: list[str] = []
    for _idx, ev in sorted(last.values(), key=lambda t: -t[0]):
        payload = ev.get("payload") or {}
        if ev["type"] == "world_crisis_warning":
            kind = CRISIS_LABELS.get(str(payload.get("kind") or ""))
            if kind:
                lines.append(f"Há sinais de {kind} em {wp.region_label(region) or 'a região'}.")
            continue
        new = str(payload.get("state") or "")
        loc_id = str(payload.get("location_id") or ev.get("target_id") or "")
        if not new or _resolve_id(loc_id) == here:
            continue  # fim de estado nao gera linha; o local atual ja tem a linha 1
        label = public_label({"state": new, "festival_id": payload.get("festival_id")})
        name = _loc_name(loc_id)
        if label and name:
            lines.append(f"Pelo que o herói soube, {name} está {label}.")
    return lines[:_CRISIS_LINES_MAX]


def _season_lines(state: dict, cur: str) -> list[str]:
    from services import world_calendar
    from services import world_pressures as wp

    season = world_calendar.active_season(_world(state))
    if not season:
        return []
    return [f"Estação: {world_calendar.label_for(season, wp.region_of(cur))}."]


def perceived_world_lines(state: dict, *, audience: Audience) -> list[str]:
    """Linhas percebidas por prioridade (R14), ja cortadas pelo orcamento (R16). Nunca levanta."""
    try:
        from services import world_engine
        from services.context_builder import estimate_tokens

        cur = str(_world(state).get("current_location_id") or "")
        if not cur:
            return []
        lines: list[str] = []
        if world_engine.mode() == "on":
            lines += _local_state_lines(state, cur)
            if audience != "npc":
                lines += _upcoming_festival_lines(state, cur)
                lines += _crisis_lines(state, cur)
        if audience != "story":
            lines += _season_lines(state, cur)
        lines = list(dict.fromkeys(lines))[:MAX_LINES]
        while lines and estimate_tokens(_render(lines)) > MAX_TOKENS:
            lines.pop()
        return lines
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("perceived_world", "lines_failed", exc)
        return []


def _render(lines: list[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"<MUNDO_PERCEBIDO>\n{INSTRUCTION}\n{body}\n</MUNDO_PERCEBIDO>"


def perceived_world_block(state: dict, *, audience: Audience) -> str:
    """'' ou o bloco `<MUNDO_PERCEBIDO>` (zero token quando nao ha nada a dizer)."""
    lines = perceived_world_lines(state, audience=audience)
    return _render(lines) if lines else ""


def day_memory_facts(state: dict, items: list[dict]) -> list[str]:
    """R7: textos de TEMPLATE dos itens percebidos (ordem do digest), sem vazio/duplicata."""
    try:
        from services import world_perception

        texts = [world_perception.render(state, it).strip() for it in items or []]
        return list(dict.fromkeys(t for t in texts if t))[:DAY_FACTS_MAX]
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("perceived_world", "day_facts_failed", exc)
        return []
