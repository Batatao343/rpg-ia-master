"""SPEC-361 (decisão do dono, 02/11): a criatura nova é gerada FORA do turno.

No spawn, o turno usa na hora a substituta (a criatura existente mais próxima, ou a variante,
se houver) e só agenda a geração. A geração roda como job tipado da fila do projeto
(``JobQueue``), com o mesmo ciclo de lease/fence de qualquer job:

- perfil DB/hosted: ``workers/run_worker.build_handlers`` registra ``creature_gen`` e o worker
  ou o cron de drenagem (``workers/drain.py``) executa. Nada de thread solta no request
  (Vercel encerra a função depois da resposta);
- perfil legacy (fila em memória): ``drenar_local`` roda depois que a narração já foi entregue
  (SSE, ``api._execute_action``) ou por ``scripts/bestiario/gerar_pendentes.py``.

O job passa pelo gate U1–U13 (com prazo próprio, ``RPG_CREATURE_GEN_DEADLINE_S``) e grava a
criatura ``local`` (overlay do dono) ou ``pool_pendente`` (fila da revisão Opus em lote).
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from observability.telemetry import log_event

JOB_KIND = "creature_gen"
_CAMPOS = (
    "pedido",
    "regiao",
    "location_id",
    "categoria_sugerida",
    "motivo_trama",
    "encounter_level",
    "game_id",
    "turn",
)


def _uuid(valor: Any) -> UUID | None:
    try:
        return UUID(str(valor)) if valor else None
    except (TypeError, ValueError):
        return None


def payload_de(p, *, owner_id: Any = None) -> dict:
    out = {k: getattr(p, k) for k in _CAMPOS}
    out["player_inputs"] = list(p.player_inputs)
    out["owner_id"] = str(owner_id) if owner_id else None
    return out


def pedido_de(payload: dict):
    from services.creature_gen import PedidoCriatura

    return PedidoCriatura(
        pedido=str(payload.get("pedido") or "Criatura")[:160],
        regiao=str(payload.get("regiao") or ""),
        location_id=str(payload.get("location_id") or ""),
        categoria_sugerida=payload.get("categoria_sugerida"),
        motivo_trama=str(payload.get("motivo_trama") or "")[:600],
        encounter_level=int(payload.get("encounter_level") or 1),
        game_id=str(payload.get("game_id") or ""),
        turn=int(payload.get("turn") or 0),
        player_inputs=tuple(str(x) for x in (payload.get("player_inputs") or ())[:3]),
    )


def dedupe_key(p) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", p.pedido.casefold())[:60].strip("_")
    return f"creature:{p.game_id}:{p.regiao}:{slug}"


def agendar(p, *, owner_id: Any = None) -> bool:
    """Enfileira a geração (idempotente por jogo + região + pedido). Nunca levanta."""
    try:
        from infrastructure.contracts import JobRequest
        from infrastructure.runtime import get_runtime

        get_runtime().job_queue.enqueue(
            JobRequest(
                JOB_KIND,
                dedupe_key(p),
                payload_de(p, owner_id=owner_id),
                owner_id=_uuid(owner_id),
                game_id=_uuid(p.game_id),
                max_attempts=1,  # gerar de novo é decisão do próximo spawn (teto R4)
            )
        )
        log_event("bestiary", "creature_gen_scheduled")
        return True
    except Exception as exc:
        log_event(
            "bestiary", "creature_gen_schedule_failed", level="warning", error=type(exc).__name__
        )
        return False


def handler(payload: dict) -> dict:
    """Job ``creature_gen``: gera, passa no gate e persiste. Falha = fica a substituta."""
    from agents.bestiary import load_bestiary, persistir_nova
    from services import creature_gen as cg
    from services.shared_pool import enabled as pool_enabled

    p = pedido_de(payload)
    db = load_bestiary(p.game_id, p.regiao) if p.game_id and pool_enabled() else load_bestiary()
    runtime = cg.runtime_da_regiao(p.regiao, db)
    dec = cg.Decisao("nova", familia_alvo=cg.familia_alvo(f"{p.pedido} {p.motivo_trama}"))
    ficha, info = cg.gerar_nova(p, dec, bestiary=db, runtime=runtime)
    codigos = list(info.get("codigos") or [])[:12]
    if ficha is None:
        log_event("bestiary", "creature_gen_job", status="fallback", codigos=codigos)
        return {"status": "fallback", "tentativas": info.get("tentativas"), "codigos": codigos}
    template = cg.ficha_para_template(ficha, encounter_level=1)
    cg._marcar(
        template,
        caminho="nova",
        pedido=p.pedido,
        tentativas=int(info.get("tentativas") or 0),
        game_id=p.game_id,
        estado="local",
    )
    estado = persistir_nova(
        ficha,
        template,
        game_id=p.game_id,
        location_id=p.location_id,
        player_inputs=p.player_inputs,
        owner_id=_uuid(payload.get("owner_id")),
    )
    log_event("bestiary", "creature_gen_job", status="nova", estado=estado, codigos=codigos)
    return {"status": "nova", "estado": estado, "id": template["id"], "codigos": codigos}


def drenar_local(limite: int = 1, *, queue=None) -> int:
    """Perfil legacy: roda até ``limite`` jobs ``creature_gen`` da fila em memória. Só deve ser
    chamado depois de a narração ter saído (ou fora de request). Nunca levanta."""
    try:
        from infrastructure.runtime import get_runtime
        from workers.job_worker import JobWorker

        q = queue or get_runtime().job_queue
        worker = JobWorker(q, {JOB_KIND: handler}, worker_id="creature-gen-local")
        feitos = 0
        while feitos < limite and worker.run_once(limit=1):
            feitos += 1
        return feitos
    except Exception as exc:
        log_event(
            "bestiary", "creature_gen_drain_failed", level="warning", error=type(exc).__name__
        )
        return 0


__all__ = ["JOB_KIND", "agendar", "dedupe_key", "drenar_local", "handler", "pedido_de"]
