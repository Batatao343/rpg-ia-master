"""services/secret_signatures.py — assinaturas de segredo + sanitização de beat.

spec beats-visibilidade-ptbr. Módulo compartilhado (R1): as frases-assinatura da
VERDADE oculta de cada segredo canônico vivem AQUI, consumidas tanto pelo
invariante `knowledge.secret_leak` (playtest) quanto pelo `campaign_manager`
(sanitização determinística do texto do beat, R2). Também expõe uma heurística
barata de idioma (R4). Zero LLM — tudo determinístico.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# Frases-assinatura da VERDADE oculta (não do rumor público — 7.3 separou os dois).
# Curadas dos docs `visibility: hidden`. Movidas de playtest/invariants.py (R1).
SECRET_SIGNATURES: Dict[str, List[str]] = {
    "pacto_valerius": [
        "pacto com valerius", "pacto com daruun", "consumiu a família",
        "cedeu a família", "em troca de imortalidade",
    ],
    "rede_carmesim": [
        "rede carmesim pode despertar", "despertar dentro de uma geração",
    ],
    "arauto_identidade": [
        "aprendiz élfico que destruiu aethelgard", "fundido com a energia liberada",
        "almas das vítimas das câmaras",
    ],
    "rei_subterraneo": [
        "verme-primordial das raízes do mundo", "medo do verme",
        "rei se aquietou por medo",
    ],
}

# Rumor PÚBLICO neutro que substitui o beat vazado (R2) — nada revela a verdade.
PUBLIC_RUMOR: Dict[str, str] = {
    "pacto_valerius": "os boatos em torno da ascensão de Valerius",
    "rede_carmesim": "os rumores sobre a Rede Carmesim",
    "arauto_identidade": "as lendas sobre o Arauto e a queda de Aethelgard",
    "rei_subterraneo": "os rumores sobre o Rei Subterrâneo",
}


def revealed_corpus(state: dict) -> str:
    """Texto do que JÁ foi revelado (event_log secret_revealed + facts da
    projection) — desarma a assinatura correspondente."""
    parts: List[str] = []
    for ev in state.get("event_log", []) or []:
        if isinstance(ev, dict) and ev.get("type") == "secret_revealed":
            parts.append(str(ev.get("payload", {})))
            parts.append(str(ev.get("target_id", "")))
    facts = (state.get("world_projection", {}) or {}).get("facts", {}) or {}
    for f in facts.values():
        parts.append(str(f))
    return " ".join(parts).lower()


def find_unrevealed(text: str, state: dict) -> Optional[Tuple[str, str]]:
    """Se `text` contém a assinatura de um segredo AINDA NÃO revelado, devolve
    (secret_id, phrase). None caso contrário."""
    low = (text or "").lower()
    if not low:
        return None
    revealed = revealed_corpus(state)
    for secret_id, phrases in SECRET_SIGNATURES.items():
        for ph in phrases:
            if ph in low and ph not in revealed:
                return secret_id, ph
    return None


def sanitize_beat(text: str, state: dict) -> str:
    """R2: se o beat contém a verdade oculta de um segredo não revelado, troca o
    texto INTEIRO por uma versão neutra (rumor público). Determinístico."""
    hit = find_unrevealed(text, state)
    if not hit:
        return text
    secret_id, _ph = hit
    rumor = PUBLIC_RUMOR.get(secret_id, "os rumores locais")
    return f"Investigue {rumor}."


# --- R4: heurística de idioma (barata, determinística) ----------------------

_EN_STOPWORDS = re.compile(
    r"\b(the|of|and|to|with|from|explore|mysteries|secret|ancient|reveal|"
    r"uncover|beneath|shadow|forest|castle|king|dark)\b")
_PT_STOPWORDS = re.compile(
    r"\b(de|da|do|das|dos|que|com|para|uma|um|os|as|você|voce|é|ao|na|no|"
    r"pelo|pela|sua|seu|ele|ela|revele|descubra|investigue)\b")
_ACCENTS = re.compile(r"[áàâãéêíóôõúüç]", re.IGNORECASE)


def looks_english(text: str) -> bool:
    """True se o beat parece inglês: >=2 stopwords EN e NENHUM sinal de PT
    (stopword pt-BR ou acento). Conservador — não pune nomes próprios."""
    low = (text or "").lower()
    if not low:
        return False
    en = len(_EN_STOPWORDS.findall(low))
    pt = len(_PT_STOPWORDS.findall(low))
    has_accent = bool(_ACCENTS.search(low))
    return en >= 2 and pt == 0 and not has_accent
