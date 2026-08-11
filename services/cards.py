"""services/cards.py — motor DETERMINÍSTICO de Cartas (specs conflito-02/13).

Gestão de Acervo/Preparação/Frequência/Ruptura/Evolução. A resolução de ataque
vive em conflito-04/`conflict_turn`; o catálogo d20 antigo foi removido no cutover.

Convenções: funções que consomem recurso MUTAM `state`/`player` e retornam um
Result dict {"ok": bool, "error": Optional[str], "log": str}.
"""
import glob
import json
import os
import copy
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

# Marcadores determinísticos que conectam uma Carta ao motor das 5 Posturas.
# O campo é autoral (nunca vem do LLM) e fechado para evitar regra livre em JSON.
CLASS_MECHANIC_FIELDS = frozenset({
    "auto_dano", "pico", "decadencia", "resfria_caldeira",
})
_DECAY_KINDS = frozenset({"any", "flesh", "morale", "gear"})


def valid_effect_kind(effect: dict) -> bool:
    """True se `efeito.kind` está no catálogo fechado de Cartas (R3)."""
    return bool(effect) and str(effect.get("kind")) in CARD_EFFECT_KINDS


def valid_class_mechanics(mechanics) -> bool:
    """Valida o vocabulário fechado de ``mecanica_classe`` das Cartas v4."""
    if mechanics is None:
        return True
    if not isinstance(mechanics, dict) or set(mechanics) - CLASS_MECHANIC_FIELDS:
        return False
    auto_dano = mechanics.get("auto_dano")
    if auto_dano is not None and (isinstance(auto_dano, bool)
                                  or not isinstance(auto_dano, int)
                                  or auto_dano <= 0):
        return False
    for field in ("pico", "resfria_caldeira"):
        if field in mechanics and not isinstance(mechanics[field], bool):
            return False
    if "decadencia" in mechanics and mechanics["decadencia"] not in _DECAY_KINDS:
        return False
    return True


def _entropy_cost(player: dict, card: dict) -> int:
    """Custo efetivo, incluindo a consequência determinística Dependência."""
    import combat_mechanics as cm
    base = int(card.get("custo_entropia", 0) or 0)
    return cm.dependencia_cost(player, base)


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


def effective_card(player: dict, card_id: str, *, ruptura: bool = False) -> Optional[dict]:
    """Carta efetiva após evolução A/B e, opcionalmente, Ruptura. Retorna cópia;
    nunca altera o catálogo autoral."""
    base = get_card(card_id)
    if not base:
        return None
    card = copy.deepcopy(base)
    caminho = str((player.get("evolved_cards") or {}).get(card_id, "")).upper()
    if caminho in ("A", "B"):
        evo = (card.get("evolucao") or {}).get(f"caminho_{caminho.lower()}") or {}
        if evo.get("efeito"):
            card["efeito"] = copy.deepcopy(evo["efeito"])
        if evo.get("ruptura"):
            card["_ruptura_evoluida"] = copy.deepcopy(evo["ruptura"])
    if ruptura:
        effect = card.pop("_ruptura_evoluida", None)
        if effect is None:
            raw = card.get("ruptura") or {}
            # Catálogo autoral usa caminho_a/caminho_b antes de uma evolução.
            effect = raw.get("caminho_a") if isinstance(raw, dict) else None
        if effect:
            card["efeito"] = copy.deepcopy(effect)
    return card


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

    custo_base = int(card.get("custo_entropia", 0) or 0)
    custo = _entropy_cost(player, card)
    if custo > int(player.get("entropy", 0) or 0):
        return {"ok": False,
                "error": f"Entropia insuficiente ({player.get('entropy', 0)}/{custo}).", "log": ""}

    if custo:
        player["entropy"] = int(player.get("entropy", 0)) - custo
    for k in _ALL_COUNTERS:
        entry[k] = int(entry.get(k, 0)) + 1
    return {
        "ok": True,
        "error": None,
        "log": f"Usa {card.get('name', card_id)}" + (f" (-{custo} Entropia)" if custo else ""),
        "cost": custo,
        "base_cost": custo_base,
        "dependencia_applied": custo > custo_base,
    }


def can_use_card(player: dict, card_id: str) -> bool:
    """Consulta pura da mesma economia de `use_card`, para HUD/harness."""
    card = get_card(card_id)
    # Só Cartas ativas ocupam a Ação. Passivas, utilitárias, reações e Cartas de
    # Virtude entram pelos respectivos gatilhos, nunca como um ataque disfarçado.
    if not card or card.get("tipo") != "ativa":
        return False
    prepared = set(player.get("prepared_cards") or [])
    virtude_ids = {vc.get("card_id") for vc in (player.get("virtue_cards") or [])}
    if card_id not in prepared and card_id not in virtude_ids:
        return False
    counter = FREQ_COUNTER.get(str(card.get("frequencia", "livre")))
    if counter and int(((player.get("card_usage") or {}).get(card_id) or {}).get(counter, 0)) >= 1:
        return False
    return _entropy_cost(player, card) <= int(player.get("entropy", 0) or 0)


def enemy_card_ids(actor: dict) -> List[str]:
    """IDs autorais fechados da ficha inimiga; payload inline nunca vira regra."""
    out: List[str] = []
    for entry in (actor.get("cartas") or actor.get("enemy_cards") or []):
        card_id = entry.get("id") if isinstance(entry, dict) else entry
        card_id = str(card_id or "").strip()
        if card_id and card_id not in out and get_card(card_id):
            out.append(card_id)
    return out


def can_use_enemy_card(actor: dict, card_id: str, *,
                       expected_type: Optional[str] = None) -> bool:
    """Economia própria do inimigo, independente do deck preparado do player."""
    if card_id not in set(enemy_card_ids(actor)):
        return False
    card = get_card(card_id)
    if not card or (expected_type and card.get("tipo") != expected_type):
        return False
    counter = FREQ_COUNTER.get(str(card.get("frequencia", "livre")))
    usage = (actor.get("enemy_card_usage") or {}).get(card_id) or {}
    if counter and int(usage.get(counter, 0) or 0) >= 1:
        return False
    return int(card.get("custo_entropia", 0) or 0) <= int(
        actor.get("entropy", 0) or 0
    )


def use_enemy_card(actor: dict, card_id: str) -> dict:
    """Consome Carta do bestiário sem consultar ou alterar o player."""
    card = get_card(card_id)
    if not card or card_id not in set(enemy_card_ids(actor)):
        return {"ok": False, "error": f"Carta inimiga '{card_id}' indisponível.", "log": ""}
    if not can_use_enemy_card(actor, card_id):
        return {"ok": False, "error": f"'{card.get('name', card_id)}' já usada ou sem Entropia.", "log": ""}
    cost = int(card.get("custo_entropia", 0) or 0)
    actor["entropy"] = max(0, int(actor.get("entropy", 0) or 0) - cost)
    usage = actor.setdefault("enemy_card_usage", {})
    entry = usage.setdefault(card_id, {key: 0 for key in _ALL_COUNTERS})
    for key in _ALL_COUNTERS:
        entry[key] = int(entry.get(key, 0) or 0) + 1
    return {
        "ok": True,
        "error": None,
        "log": f"Usa {card.get('name', card_id)}" + (
            f" (-{cost} Entropia)" if cost else ""
        ),
    }


def reset_enemy_card_usage(actor: dict, scope: str) -> None:
    for entry in (actor.get("enemy_card_usage") or {}).values():
        for key in _RESET_CASCADE.get(scope, ()):
            entry[key] = 0


def combat_card_suggestions(player: dict, enemies: List[dict],
                            combat: Optional[dict]) -> List[str]:
    """Chips transitórios até a UI de Cartas (conflito-16): Cartas preparadas
    utilizáveis + poção + fuga. Zero dependência do catálogo d20 antigo."""
    active = [e for e in (enemies or []) if isinstance(e, dict)
              and e.get("status") == "ativo" and not e.get("dead")]
    if not (combat or {}).get("active") or not active:
        return []
    ready = [get_card(cid) for cid in (player.get("prepared_cards") or [])
             if can_use_card(player, cid)]
    ready = [c for c in ready if c]
    ready.sort(key=lambda c: (str(c.get("patamar", "")), str(c.get("name", ""))))
    chips = [str(c.get("name", c.get("id"))) for c in ready[:3]]
    from gamedata import ARTIFACTS_DB
    from inventory import item_display
    potion = next((
        item_display(e) for e in (player.get("inventory") or [])
        if isinstance(e, dict)
        and str((ARTIFACTS_DB.get(e.get("id", "")) or {}).get("type", "")).lower()
        in ("consumable", "potion")
    ), None)
    if potion and len(chips) < 4:
        chips.append(f"Beber {potion}")
    import combat_mechanics as cm
    if not cm.has_control(player, "root") and len(chips) < 5:
        chips.append("Fugir")
    return chips


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
