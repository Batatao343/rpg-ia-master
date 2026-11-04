"""SPEC-393 R1: texto de encerramento quando o jogador aceita o fim (tela de morte)."""

from __future__ import annotations

import copy

from langchain_core.messages import AIMessage

from services.round_log import WHEEL_TEXT

ACCEPT_TEXT = (
    "Você aceita o fim. A Roda do Abismo se cala, e a sua história descansa aqui, "
    "guardada na crônica como memorial."
)


def _swap(text: str) -> str:
    return text.replace(WHEEL_TEXT, ACCEPT_TEXT)


def apply_accept_text(state: dict) -> dict:
    """Troca a pergunta da Roda pelo encerramento, em mensagens e no histórico de apresentação."""
    messages = list(state.get("messages") or [])
    swapped = False
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if getattr(msg, "type", "") == "ai" and WHEEL_TEXT in str(msg.content):
            messages[idx] = AIMessage(content=_swap(str(msg.content)))
            swapped = True
            break
    if not swapped:
        messages.append(AIMessage(content=ACCEPT_TEXT))
    state["messages"] = messages
    history = copy.deepcopy(state.get("presentation_history") or [])
    for row in reversed(history):  # só a última pergunta, como nas mensagens
        if isinstance(row, dict) and WHEEL_TEXT in str(row.get("text", "")):
            row["text"] = _swap(str(row["text"]))
            break
    if history:
        state["presentation_history"] = history
    return state
