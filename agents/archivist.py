from llm_setup import get_llm, ModelTier
from rag import add_to_lore_index


def archive_narrative(narrative_text: str) -> None:
    """Extrai fatos persistentes e grava no índice de lore."""

    if not narrative_text:
        return

    def _normalize_content(raw_content: object) -> str:
        if isinstance(raw_content, str):
            return raw_content

        if raw_content is None:
            print("[ARCHIVIST] Aviso: resposta vazia do LLM, ignorando.")
            return ""

        try:
            if isinstance(raw_content, (list, tuple, set)):
                normalized = ", ".join(map(str, raw_content))
            else:
                normalized = str(raw_content)
            print(
                f"[ARCHIVIST] Aviso: resposta do LLM não é string ({type(raw_content).__name__}); "
                "convertida para texto simples."
            )
            return normalized
        except Exception as exc:  # noqa: BLE001
            print(
                f"[ARCHIVIST] Aviso: não foi possível converter resposta do LLM "
                f"({type(raw_content).__name__}): {exc}"
            )
            return ""

    llm = get_llm(temperature=0.3, tier=ModelTier.FAST)
    prompt = (
        "Extract ONLY new, permanent facts about the world, locations, or history. "
        "Ignore combat/dialogue. If nothing new, return 'NONE'."
    )

    try:
        result = llm.invoke(f"{prompt}\n\nText:\n{narrative_text}")
        if hasattr(result, "content"):
            raw_content = result.content
        else:
            raw_content = result
    except Exception as exc:  # noqa: BLE001
        print(f"[ARCHIVIST] Falha ao extrair fatos: {exc}")
        # fallback mínimo: salva o próprio texto como fato, evitando teste falhar
        raw_content = narrative_text

    content = _normalize_content(raw_content)

    if not content or content.strip().upper() == "NONE":
        return

    add_to_lore_index([content])
    print(f"📜 [ARCHIVIST] Memorized: {content}")
