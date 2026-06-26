"""
agents/class_themes.py
Limites temáticos por classe (o que faz ou não sentido um personagem tentar).
Fonte da verdade: data/class_themes.json (determinístico, sem LLM, funciona offline).
Usado pelo Ruler para o gating de habilidades abertas (Fase 0).
"""
from typing import Dict, List

from gamedata import CLASS_THEMES

_DEFAULT = {
    "allowed": ["ações comuns de aventura", "combate básico", "diálogo"],
    "forbidden": ["façanhas absurdas fora do personagem"],
    "style": "Aventureiro versátil.",
}


def get_class_theme(class_name: str) -> Dict[str, object]:
    """Retorna {allowed, forbidden, style} para a classe (ou um padrão genérico)."""
    if not class_name:
        return dict(_DEFAULT)
    theme = CLASS_THEMES.get(class_name)
    if theme:
        return theme
    # casa ignorando caixa
    low = class_name.strip().lower()
    for name, data in CLASS_THEMES.items():
        if name.lower() == low:
            return data
    return dict(_DEFAULT)


def get_power_guideline(level: int) -> str:
    if level <= 4:
        return "TIER 1 (Iniciante): Dano baixo, local, sem voo."
    if level <= 10:
        return "TIER 2 (Heroico): Dano médio, área pequena, voo curto."
    if level <= 16:
        return "TIER 3 (Mestre): Dano alto, exércitos, ressurreição."
    return "TIER 4 (Lenda): Alteração da realidade."
