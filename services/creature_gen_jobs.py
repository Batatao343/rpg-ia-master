"""SPEC-361 (decisão do dono, 02/11): a criatura nova é gerada FORA do turno.

No spawn, o turno usa na hora a substituta (a criatura existente mais próxima, ou a variante,
se houver) e só agenda a geração. A geração roda como job tipado da fila do projeto
(``JobQueue``), com o mesmo ciclo de lease/fence de qualquer job:

- perfil DB/hosted: ``workers/run_worker.build_handlers`` registra ``creature_gen`` e o worker
  ou o cron de drenagem (``workers/drain.py``) executa. Nada de thread solta no request
  (Vercel encerra a função depois da resposta);
- perfil legacy (processo local, fila em memória): ``drenar_em_segundo_plano`` roda UM job por
  vez numa thread daemon, fora do lock do jogo, depois que a narração já saiu (R2-P1-2).

O job passa pelo gate U1–U13 (com prazo próprio, ``RPG_CREATURE_GEN_DEADLINE_S``) e grava a
criatura ``local`` (overlay do dono) ou ``pool_pendente`` (fila da revisão Opus em lote), com a
chave opaca ``chave_geracao`` (hash de pedido + região) para o próximo encontro achá-la.

**Dedupe permanente (R2-P2-2, decisão registrada na §9).** A chave ``creature:<jogo>:<região>:
<pedido>`` é única para sempre (no Postgres, ``unique (kind, dedupe_key)``): cada pedido gera no
máximo UMA vez por jogo. Se a geração cair em fallback, aquele pedido segue com a substituta
pelo resto do jogo; não há nova tentativa (o teto R4 já contou a tentativa).

**Retenção (R2-P2-4).** O payload não guarda as falas do jogador: só hashes de tokens (para o
``name_origin``) e os shingles em hash que o validador de texto literal já usa.
"""

from __future__ import annotations

import hashlib
import re
import threading
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
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _uuid(valor: Any) -> UUID | None:
    try:
        return UUID(str(valor)) if valor else None
    except (TypeError, ValueError):
        return None


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def hashes_de_tokens(textos) -> list[str]:
    """Tokens dobrados com ≥ 4 letras, em hash (o mesmo corte de ``name_typed_by_player``)."""
    from services.shared_pool_models import fold_name

    vistos = {
        _hash(tok) for texto in textos for tok in _TOKEN.findall(fold_name(texto)) if len(tok) >= 4
    }
    return sorted(vistos)


def nome_digitado(nome: str, token_hashes) -> bool:
    """``name_typed_by_player`` sobre os hashes guardados: algum token do nome foi digitado."""
    alvo = set(token_hashes or ())
    return any(h in alvo for h in hashes_de_tokens([nome]))


def payload_de(p, *, owner_id: Any = None) -> dict:
    from services.shared_pool_validators import input_shingles

    out = {k: getattr(p, k) for k in _CAMPOS}
    out["player_token_hashes"] = hashes_de_tokens(p.player_inputs)
    out["player_shingles"] = input_shingles(p.player_inputs)
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
    )


def dedupe_key(p) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", p.pedido.casefold())[:60].strip("_")
    return f"creature:{p.game_id}:{p.regiao}:{slug}"


def agendar(p, *, owner_id: Any = None) -> bool:
    """Enfileira a geração (uma por jogo + região + pedido, para sempre). Nunca levanta."""
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
                # R2-P2-1: um job interrompido pela plataforma (lease expirada) roda de novo
                # uma vez; fallback do gate termina o job normalmente (não é falha).
                max_attempts=2,
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
    if cg.ja_gerada(p, db):  # retry depois de interrupção: já persistida, nada a fazer
        return {"status": "ja_gerada"}
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
        chave=cg.chave_geracao(p.pedido, p.regiao),
        tentativas=int(info.get("tentativas") or 0),
        game_id=p.game_id,
        estado="local",
    )
    estado = persistir_nova(
        ficha,
        template,
        game_id=p.game_id,
        location_id=p.location_id,
        player_inputs=(),
        owner_id=_uuid(payload.get("owner_id")),
        nome_digitado=nome_digitado(
            str(ficha.get("nome") or ""), payload.get("player_token_hashes")
        ),
        shingles=list(payload.get("player_shingles") or ()),
    )
    log_event("bestiary", "creature_gen_job", status="nova", estado=estado, codigos=codigos)
    return {"status": "nova", "estado": estado, "id": template["id"], "codigos": codigos}


def drenar_local(limite: int = 1, *, queue=None) -> int:
    """Roda até ``limite`` jobs ``creature_gen`` da fila (perfil legacy). Nunca levanta."""
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


_EM_VOO = threading.Lock()
_ULTIMA_THREAD: threading.Thread | None = None


def drenar_em_segundo_plano() -> bool:
    """Perfil legacy (processo local): UM job por vez numa thread daemon, fora do lock do jogo
    (R2-P1-2). O job não toca no estado do jogo; a próxima ação nunca espera por ele.
    Devolve False se já há um job em voo (o próximo turno tenta de novo)."""
    global _ULTIMA_THREAD
    if not _EM_VOO.acquire(blocking=False):
        return False

    def rodar() -> None:
        try:
            drenar_local(1)
        finally:
            _EM_VOO.release()

    _ULTIMA_THREAD = threading.Thread(target=rodar, name="creature-gen-drain", daemon=True)
    _ULTIMA_THREAD.start()
    return True


def aguardar_drenagem(timeout: float = 30.0) -> None:
    """Para testes e encerramento: espera a thread em voo terminar."""
    if _ULTIMA_THREAD is not None:
        _ULTIMA_THREAD.join(timeout)


__all__ = [
    "JOB_KIND",
    "agendar",
    "dedupe_key",
    "drenar_em_segundo_plano",
    "drenar_local",
    "handler",
    "nome_digitado",
    "pedido_de",
]
