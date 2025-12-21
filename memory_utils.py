from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from llm_setup import ModelTier, get_llm


def _messages_to_text(messages: List[BaseMessage]) -> str:
    parts = []
    for msg in messages:
        role = msg.__class__.__name__.replace("Message", "")
        content = getattr(msg, "content", "")
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def sanitize_history(messages: List[BaseMessage], max_messages: int = 20) -> List[BaseMessage]:
    """Compacta o histórico quando fica grande, preservando o prompt do sistema."""
    if not messages or len(messages) <= max_messages:
        return messages

    prefix: List[BaseMessage] = []
    start_idx = 0
    if isinstance(messages[0], SystemMessage):
        prefix = [messages[0]]
        start_idx = 1

    # Mantém mensagens recentes e sintetiza o excedente em um resumo
    keep_recent = max(max_messages - len(prefix) - 1, 0)
    if keep_recent == 0:
        older = messages[start_idx:]
        recent: List[BaseMessage] = []
    else:
        older = messages[start_idx:-keep_recent] if -keep_recent != 0 else messages[start_idx:]
        recent = messages[-keep_recent:]

    if not older:
        return messages

    llm = get_llm(temperature=0.2, tier=ModelTier.FAST)
    summary_prompt = SystemMessage(
        content=(
            "Summarize the following game log into 2-3 concise sentences focusing on factual events and outcomes. "
            "Do NOT add new plot points."
        )
    )
    history_text = _messages_to_text(older)
    response = llm.invoke([summary_prompt, HumanMessage(content=history_text)])
    summary_text = getattr(response, "content", str(response))

    summary_message: BaseMessage = SystemMessage(
        content=f"Summary of past events: {summary_text}"
    )

    return prefix + [summary_message] + recent
