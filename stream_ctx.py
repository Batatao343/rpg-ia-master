"""Stream context — ContextVar para fila SSE de tokens (TOP 1 streaming).

Permite que agentes injetem tokens em tempo real sem passar fila como argumento.
Usar: push_token(token_str) dentro de qualquer nó do grafo.
"""

import queue
from contextvars import ContextVar
from typing import Optional

_sse_queue_var: ContextVar[Optional[queue.Queue]] = ContextVar(
    '_sse_queue', default=None
)


def push_token(token: str) -> None:
    """Enfileira um token para transmissão SSE ao cliente."""
    q = _sse_queue_var.get()
    if q and token:
        q.put(token)


def set_queue(q: queue.Queue):
    """Define a fila para o contexto atual (use em try/finally com reset_queue)."""
    return _sse_queue_var.set(q)


def reset_queue(tok) -> None:
    """Reseta a fila ao valor anterior (context-safe)."""
    _sse_queue_var.reset(tok)
