from llm_setup import get_llm, ModelTier
from rag import add_to_lore_index


def archive_narrative(narrative_text: str) -> None:
    """Extrai fatos persistentes e grava no índice de lore."""

    if not narrative_text:
        return

    llm = get_llm(temperature=0.3, tier=ModelTier.FAST)
    prompt = (
        "Extract ONLY new, permanent facts about the world, locations, or history. "
        "Ignore combat/dialogue. If nothing new, return 'NONE'."
    )

    try:
        result = llm.invoke(f"{prompt}\n\nText:\n{narrative_text}")
        if hasattr(result, "content"):
            content = result.content
        else:
            content = str(result)
    except Exception as exc:  # noqa: BLE001
        print(f"[ARCHIVIST] Falha ao extrair fatos: {exc}")
        return

    if not content or content.strip().upper() == "NONE":
        return

    add_to_lore_index([content])
    print(f"📜 [ARCHIVIST] Memorized: {content}")
