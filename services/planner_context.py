"""SPEC-311 R1/R6: o que o planner (campaign_manager) enxerga do mundo percebido.

Puro e determinístico: sem LLM, sem RNG, sem estado novo. Só lê `state["quests"]`, os itens
que o herói PERCEBEU no tick do dia e os eventos de quest deste turno — nunca `world_sim`
(pressões, bandas, crises não percebidas, fase do diretor).
"""

from __future__ import annotations

PLANNER_QUESTS_MAX: int = 6  # [BALANCEAR]
_FALLEN_PREFIXES = ("ocupado.", "ruina.")  # templates de "a cidade caiu" (escala do diretor)


def planner_quests_block(state: dict) -> str:
    """'' ou `<QUESTS_DO_HEROI>` (R1): quests ativas, mundo primeiro, sem id nem prova."""
    try:
        from services import quest_log

        day = int((((state or {}).get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)
        active = [
            q
            for q in (state or {}).get("quests") or []
            if isinstance(q, dict) and q.get("status") == "active" and q.get("title")
        ]
        ordered = [q for q in active if q.get("world_kind")] + [
            q for q in active if not q.get("world_kind")
        ]
        rows: list[str] = []
        for q in ordered[:PLANNER_QUESTS_MAX]:
            view = quest_log.public_quest_view(q, day)
            row = f"- {view['title']}"
            if view.get("origin_name"):
                row += f" · origem: {view['origin_name']}"
            if view.get("kind") == "mundo":
                row += " · tipo: mundo"
                if view.get("deadline_label"):
                    row += f" · prazo: {view['deadline_label']}"
            rows.append(row)
        if not rows:
            return ""
        return "<QUESTS_DO_HEROI>\n" + "\n".join(rows) + "\n</QUESTS_DO_HEROI>"
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("planner_context", "quests_block_failed", exc)
        return ""


def world_replan_cause(state: dict, perceived: list[dict], wq_events: list[dict]) -> str | None:
    """R6: 'crise_regiao' | 'queda_cidade' | 'quest_falhou' | None, nessa ordem de prioridade.

    Lê só `perceived` (itens que o herói viu/ouviu hoje) e `wq_events` (quests dele)."""
    try:
        from services import world_pressures as wp

        cur = str((((state or {}).get("world") or {}).get("current_location_id")) or "")
        region = wp.region_of(cur)
        items = [i for i in perceived or [] if isinstance(i, dict)]
        if region:
            if any(i.get("kind") == "crise" and i.get("region_id") == region for i in items):
                return "crise_regiao"
            if any(
                i.get("kind") == "escala"
                and i.get("region_id") == region
                and str(i.get("template_id") or "").startswith(_FALLEN_PREFIXES)
                for i in items
            ):
                return "queda_cidade"
        if any(isinstance(e, dict) and e.get("type") == "quest_failed" for e in wq_events or []):
            return "quest_falhou"
        return None
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("planner_context", "replan_cause_failed", exc)
        return None
