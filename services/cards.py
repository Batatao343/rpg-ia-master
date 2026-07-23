"""services/cards.py — motor DETERMINÍSTICO de Cartas (spec conflito-02).

Gestão de Acervo/Preparação/Frequência/Ruptura/Evolução. NÃO resolve ataque em
combate (isso é conflito-04) — aqui só o schema, a economia de uso e as regras de
preparo. Convive com o motor antigo (known_abilities/ability_cooldowns) até o
cutover (conflito-13).

Convenções: funções que consomem recurso MUTAM `state`/`player` e retornam um
Result dict {"ok": bool, "error": Optional[str], "log": str}.
"""
import glob
import json
import os
from typing import Dict, List, Optional

import gamedata

# --------------------------------------------------------------------------
# Catálogo FECHADO de efeitos de Carta (conflito-14 R3).
# --------------------------------------------------------------------------
# A conflito-03 R6 fecha os efeitos de CENA (objetos/ambiente). Cartas de
# classe têm um vocabulário próprio de efeito, resolvido em combate pela
# conflito-04/05 — mas também precisa ser FECHADO: nenhuma Carta autora um
# `efeito.kind` sem correspondência mecânica (mesmo princípio do catálogo de
# cena). Este é o catálogo canônico consumido pela autoria (conflito-14) e pelo
# lint de conteúdo (`scripts/validate_content.py`).
CARD_EFFECT_KINDS = frozenset({
    # ataque / dano ao longo do tempo / cura
    "dano", "dot", "cura", "estabilizar",
    # defesa / posição / controle
    "protecao", "taunt", "empurrao", "reposicionar", "esconder", "marca",
    "aplicar_condicao", "purga_condicao", "contra_ataque", "vantagem",
    # buffs (passivas e ativas de suporte)
    "buff_defesa", "buff_acerto", "buff_dano", "buff_cura", "buff_dot",
    "buff_iniciativa", "buff_esquiva", "perception",
    # utilitária fora de combate
    "utilitaria",
    # exclusivo do Médico (purga a Carga do Abismo de aliado)
    "reduzir_carga_aliado",
    # Cartas de Virtude: bônus que escala com o Estágio da Virtude
    "bonus_dano_por_estagio", "bonus_percepcao_por_estagio",
    "bonus_vitalidade_por_estagio", "bonus_iniciativa_por_estagio",
    "bonus_social_por_estagio", "bonus_esquiva_por_estagio",
    "bonus_cura_por_estagio",
})

# Dano-base por categoria de arma (doc 01 §19; conflito-05 R1). Escala NOVA —
# valores FLAT, não dados. A autoria (conflito-14 R2) ancora todo `dano` aqui.
DANO_BASE_ARMA = {"leve": 3, "marcial": 4, "versatil": 6, "pesada": 8}


def valid_effect_kind(effect: dict) -> bool:
    """True se `efeito.kind` está no catálogo fechado de Cartas (R3)."""
    return bool(effect) and str(effect.get("kind")) in CARD_EFFECT_KINDS


# Escopo de reset por frequência -> contador em card_usage.
FREQ_COUNTER = {
    "turno": "used_this_turn",
    "cena": "used_this_scene",
    "descanso_curto": "used_since_short_rest",
    "descanso_longo": "used_since_long_rest",
}
# Reset em cascata: um escopo mais largo zera os mais estreitos aninhados.
_RESET_CASCADE = {
    "turno": ("used_this_turn",),
    "cena": ("used_this_turn", "used_this_scene"),
    "descanso_curto": ("used_this_turn", "used_this_scene", "used_since_short_rest"),
    "descanso_longo": ("used_this_turn", "used_this_scene",
                       "used_since_short_rest", "used_since_long_rest"),
}
_ALL_COUNTERS = ("used_this_turn", "used_this_scene",
                 "used_since_short_rest", "used_since_long_rest")

_CARDS: Optional[Dict[str, dict]] = None


def _load_cards() -> Dict[str, dict]:
    global _CARDS
    if _CARDS is not None:
        return _CARDS
    out: Dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(gamedata.DATA_DIR, "cards", "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for c in (data.get("cards") or []):
            if isinstance(c, dict) and c.get("id"):
                out[c["id"]] = c
    _CARDS = out
    return out


def reload_cards() -> None:
    """Descarta o cache (usado por testes que injetam data/cards temporário)."""
    global _CARDS, _VIRTUE_SUGGESTIONS
    _CARDS = None
    _VIRTUE_SUGGESTIONS = None


def all_cards() -> Dict[str, dict]:
    return _load_cards()


def get_card(card_id: str) -> Optional[dict]:
    return _load_cards().get(card_id)


def cards_for_class(class_name: str, subclass: str = "") -> List[dict]:
    """Cartas de classe/subclasse (exclui Cartas de Virtude, tipo 'virtude')."""
    out = []
    for c in _load_cards().values():
        if c.get("tipo") == "virtude":
            continue
        if c.get("classe") in (class_name, "") or class_name == "":
            if not subclass or c.get("subclasse") in (subclass, ""):
                out.append(c)
    return out


def virtue_cards_pool() -> List[dict]:
    return [c for c in _load_cards().values() if c.get("tipo") == "virtude"]


def cards_at_patamar(class_name: str, subclass: str, patamar: str) -> List[dict]:
    """Cartas de uma classe (tronco + subclasse) de um patamar específico."""
    out = []
    for c in cards_for_class(class_name, subclass):
        if c.get("patamar") == patamar:
            out.append(c)
    return out


_VIRTUE_SUGGESTIONS: Optional[Dict[str, List[str]]] = None


def _load_virtue_suggestions() -> Dict[str, List[str]]:
    global _VIRTUE_SUGGESTIONS
    if _VIRTUE_SUGGESTIONS is not None:
        return _VIRTUE_SUGGESTIONS
    path = os.path.join(gamedata.DATA_DIR, "cards", "virtude_sugeridas.json")
    data: Dict[str, List[str]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = (json.load(f) or {}).get("sugestoes", {})
    except Exception:
        data = {}
    _VIRTUE_SUGGESTIONS = data
    return data


def suggested_virtue_cards(class_name: str, subclass: str = "") -> List[str]:
    """R6: 2 Cartas de Virtude sugeridas por combinação classe/subclasse (só
    recomendação — o jogador escolhe livremente na criação, conflito-02)."""
    key = f"{class_name}/{subclass}" if subclass else class_name
    sug = _load_virtue_suggestions()
    return list(sug.get(key) or sug.get(class_name) or [])


# --------------------------------------------------------------------------
# Preparação
# --------------------------------------------------------------------------
def prepare_slots_for_level(level) -> int:
    """Cartas preparadas por nível (R2). Delegado à tabela de gamedata."""
    return gamedata.prepared_slots_for_level(level)


_APEX_TAG = "apex"
_SAFE_DANGER = 3


def can_reorganize(state: dict) -> bool:
    """R5: reorganizar preparação é livre FORA de combate, em zona segura sem
    ameaça imediata. Reaproveita a noção de 'seguro' (perigo <= 3, não-apex)."""
    combat = state.get("combat") or {}
    if combat.get("active"):
        return False
    world = state.get("world") or {}
    danger = int(world.get("danger_level", 1) or 1)
    loc = state.get("_location") or {}
    tags = (loc.get("tags") or []) if isinstance(loc, dict) else []
    if _APEX_TAG in tags:
        return False
    return danger <= _SAFE_DANGER


def set_prepared(state: dict, prepared: List[str]) -> dict:
    """Aplica uma nova lista de preparadas. Valida: reorganização permitida,
    subconjunto do Acervo, dentro do limite do nível. Mantém card_usage."""
    if not can_reorganize(state):
        return {"ok": False, "error": "Não é seguro reorganizar as Cartas agora.", "log": ""}
    player = state.get("player") or {}
    known = set(player.get("known_cards") or [])
    limite = prepare_slots_for_level(player.get("level", 1))
    prepared = list(dict.fromkeys(prepared))  # dedup preservando ordem
    fora = [c for c in prepared if c not in known]
    if fora:
        return {"ok": False, "error": f"Cartas fora do Acervo: {fora}.", "log": ""}
    if len(prepared) > limite:
        return {"ok": False, "error": f"Máximo {limite} Cartas preparadas neste nível.", "log": ""}
    player["prepared_cards"] = prepared
    return {"ok": True, "error": None, "log": f"Preparação atualizada ({len(prepared)}/{limite})."}


# --------------------------------------------------------------------------
# Uso / frequência
# --------------------------------------------------------------------------
def _usage_entry(player: dict, card_id: str) -> dict:
    usage = player.setdefault("card_usage", {})
    return usage.setdefault(card_id, {k: 0 for k in _ALL_COUNTERS})


def use_card(state: dict, card_id: str) -> dict:
    """Gasta uma Carta preparada/de Virtude: checa frequência + custo de Entropia,
    debita Entropia e incrementa os contadores de uso (R6). NÃO resolve efeito."""
    player = state.get("player") or {}
    card = get_card(card_id)
    if not card:
        return {"ok": False, "error": f"Carta '{card_id}' desconhecida.", "log": ""}
    prepared = set(player.get("prepared_cards") or [])
    virtude_ids = {vc.get("card_id") for vc in (player.get("virtue_cards") or [])}
    if card_id not in prepared and card_id not in virtude_ids:
        return {"ok": False, "error": f"Carta '{card_id}' não está preparada.", "log": ""}

    freq = str(card.get("frequencia", "livre"))
    entry = _usage_entry(player, card_id)
    counter = FREQ_COUNTER.get(freq)
    if counter and int(entry.get(counter, 0)) >= 1:
        return {"ok": False, "error": f"'{card.get('name', card_id)}' já foi usada (1×{freq}).", "log": ""}

    custo = int(card.get("custo_entropia", 0) or 0)
    if custo > int(player.get("entropy", 0) or 0):
        return {"ok": False,
                "error": f"Entropia insuficiente ({player.get('entropy', 0)}/{custo}).", "log": ""}

    if custo:
        player["entropy"] = int(player.get("entropy", 0)) - custo
    for k in _ALL_COUNTERS:
        entry[k] = int(entry.get(k, 0)) + 1
    return {"ok": True, "error": None,
            "log": f"Usa {card.get('name', card_id)}" + (f" (-{custo} Entropia)" if custo else "")}


def reset_card_usage(state: dict, scope: str) -> None:
    """Reseta contadores no gatilho certo (R6). scope: turno/cena/descanso_curto/
    descanso_longo — cascata: escopo largo zera os aninhados."""
    player = state.get("player") or {}
    zerar = _RESET_CASCADE.get(scope, ())
    for entry in (player.get("card_usage") or {}).values():
        for k in zerar:
            entry[k] = 0


# --------------------------------------------------------------------------
# Evolução (Caminho A/B, permanente e única a partir do nível 4)
# --------------------------------------------------------------------------
def evolve_card(state: dict, card_id: str, caminho: str) -> dict:
    """R4: evolui uma Carta conhecida por um Caminho (A|B), permanente e ÚNICO a
    partir do nível 4. Segunda evolução da mesma Carta é rejeitada."""
    player = state.get("player") or {}
    if int(player.get("level", 1) or 1) < 4:
        return {"ok": False, "error": "Evolução de Carta só a partir do nível 4.", "log": ""}
    if card_id not in set(player.get("known_cards") or []):
        return {"ok": False, "error": f"Carta '{card_id}' não está no Acervo.", "log": ""}
    caminho = str(caminho or "").strip().upper()
    if caminho not in ("A", "B"):
        return {"ok": False, "error": "Caminho de evolução inválido (use A ou B).", "log": ""}
    evolved = player.setdefault("evolved_cards", {})
    if card_id in evolved:
        return {"ok": False,
                "error": f"'{card_id}' já evoluiu pelo Caminho {evolved[card_id]} (único).", "log": ""}
    evolved[card_id] = caminho
    return {"ok": True, "error": None, "log": f"'{card_id}' evoluiu pelo Caminho {caminho}."}


# --------------------------------------------------------------------------
# Ruptura (declarada antes da rolagem; gera Carga mesmo em falha)
# --------------------------------------------------------------------------
def use_ruptura(state: dict, card_id: str) -> dict:
    """R8: Ruptura paga o custo NORMAL da Carta e gera 1 Carga do Abismo mesmo em
    falha. A Carga gerada NÃO alimenta a própria Ruptura (cobrança acontece antes).
    A resolução do efeito extremo é conflito-04 — aqui só a economia."""
    player = state.get("player") or {}
    card = get_card(card_id)
    if not card:
        return {"ok": False, "error": f"Carta '{card_id}' desconhecida.", "log": ""}
    if not card.get("ruptura"):
        return {"ok": False, "error": f"'{card.get('name', card_id)}' não tem Ruptura.", "log": ""}

    # paga o custo/frequência como uso normal (cobra a Entropia ANTES da Carga nova)
    res = use_card(state, card_id)
    if not res["ok"]:
        return res
    # Carga do Abismo +1 (mesmo em falha na rolagem — a rolagem é conflito-04)
    player["abyss_charge"] = int(player.get("abyss_charge", 0) or 0) + 1
    res["log"] += " — RUPTURA (+1 Carga do Abismo)"
    return res
