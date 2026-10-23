"""shared_pool_jobs.py — job de promoção do pool compartilhado (SPEC-297 R18/R20).

`promote_due_job` é chamado pelo cron interno (hosted) e por `scripts/pool_promote.py`
(legacy, manual). Roda fora do turno; nunca dentro de uma request de jogador.
"""

from __future__ import annotations

from datetime import datetime

from services.shared_pool import promote_due


def promote_due_job(pool_store, llm=None, now: datetime | None = None, **kwargs) -> dict[str, int]:
    """Promove/rejeita entradas vencidas. Devolve só contagens."""
    return promote_due(pool_store, now=now, llm=llm, **kwargs)
