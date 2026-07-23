"""services/bestiary_knowledge.py — informação revelada do inimigo (spec conflito-08).

Painel inicial só com campos PÚBLICOS (R7) e revelação progressiva de Cartas (R8)
e Resistências/Vulnerabilidades/Imunidades (R9) — que persistem no bestiário
(overlay `data/runtime/`, mesmo padrão de `isolar-cache-runtime`, NUNCA nos dados
curados) e começam reveladas em encontros futuros com o mesmo arquétipo. Variantes
podem ter Cartas exclusivas ainda ocultas.
"""
import json
import os
from typing import Dict, List, Optional

import gamedata

_KNOWLEDGE_FILE = "bestiary_knowledge.json"

# Campos PÚBLICOS do painel inicial (R7). Tudo o mais fica oculto até descoberto.
_PUBLIC_FIELDS = (
    "vitalidade", "max_vitalidade", "esquiva", "protecao",
    "integridade_atual", "integridade_max", "recursos_visiveis",
    "active_conditions", "posicao", "engajamentos",
)


# ==========================================================================
# Painel público (R7)
# ==========================================================================
def public_panel(enemy: dict) -> dict:
    """R7: só os campos SEMPRE visíveis. Cartas não usadas, Virtudes, perfil
    tático, prioridades, espaços de Ferimento e resistências não ativadas ficam
    FORA — expostos só via revelação (R8/R9)."""
    panel: Dict[str, object] = {}
    for f in _PUBLIC_FIELDS:
        if f in enemy:
            panel[f] = enemy[f]
    # armadura expõe só Proteção/Integridade, nunca resist_tipos ocultos
    armor = enemy.get("armor") or {}
    if armor:
        panel.setdefault("protecao", armor.get("protecao"))
        panel.setdefault("integridade_atual", armor.get("integridade_atual"))
        panel.setdefault("integridade_max", armor.get("integridade_max"))
    return panel


# ==========================================================================
# Persistência no overlay runtime (R8/R9)
# ==========================================================================
def _load_all() -> dict:
    path = gamedata.runtime_cache_path(_KNOWLEDGE_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        return json.loads(content) if content else {}
    except Exception:
        return {}


def _save_all(data: dict) -> None:
    path = gamedata.runtime_cache_path(_KNOWLEDGE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _archetype_id(entry: dict) -> str:
    return str(entry.get("archetype_id") or entry.get("archetype")
               or entry.get("id") or entry.get("name") or "desconhecido")


def _persist(archetype: str, *, card: Optional[str] = None,
             resistance: Optional[str] = None) -> None:
    data = _load_all()
    rec = data.setdefault(archetype, {"revealed_cards": [], "revealed_resistances": []})
    if card and card not in rec["revealed_cards"]:
        rec["revealed_cards"].append(card)
    if resistance and resistance not in rec["revealed_resistances"]:
        rec["revealed_resistances"].append(resistance)
    _save_all(data)


# ==========================================================================
# Revelação (R8/R9)
# ==========================================================================
def reveal_card(entry: dict, card_id: str) -> dict:
    """R8: a Carta usada pelo inimigo fica revelada pelo resto do combate E entra
    no bestiário — reaparece revelada em encontros futuros do mesmo arquétipo.
    Cartas marcadas `variant_exclusive` NÃO propagam pro arquétipo (variante)."""
    revealed = entry.setdefault("revealed_cards", [])
    if card_id not in revealed:
        revealed.append(card_id)
    if card_id not in _variant_exclusive(entry):
        _persist(_archetype_id(entry), card=card_id)
    return {"revealed": True, "card_id": card_id}


def reveal_resistance(entry: dict, resistance_type: str) -> dict:
    """R9: Resistência/Vulnerabilidade/Imunidade revelada quando afeta uma
    resolução — permanece visível e entra no bestiário."""
    revealed = entry.setdefault("revealed_resistances", [])
    if resistance_type not in revealed:
        revealed.append(resistance_type)
    _persist(_archetype_id(entry), resistance=resistance_type)
    return {"revealed": True, "resistance_type": resistance_type}


def _variant_exclusive(entry: dict) -> set:
    return set(entry.get("variant_exclusive_cards") or [])


def is_card_revealed(entry: dict, card_id: str) -> bool:
    return card_id in (entry.get("revealed_cards") or [])


def is_resistance_revealed(entry: dict, resistance_type: str) -> bool:
    return resistance_type in (entry.get("revealed_resistances") or [])


def apply_persisted_knowledge(entry: dict) -> dict:
    """R8/R9: no início de um encontro, carrega o que o bestiário já sabe do
    arquétipo — as Cartas/Resistências reveladas antes começam reveladas. Cartas
    exclusivas de variante desta ficha permanecem ocultas."""
    data = _load_all().get(_archetype_id(entry), {})
    variant = _variant_exclusive(entry)
    cards = entry.setdefault("revealed_cards", [])
    for c in data.get("revealed_cards", []):
        if c not in cards and c not in variant:
            cards.append(c)
    res = entry.setdefault("revealed_resistances", [])
    for r in data.get("revealed_resistances", []):
        if r not in res:
            res.append(r)
    return entry
