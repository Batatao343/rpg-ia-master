"""
progression.py
Núcleo DETERMINÍSTICO de progressão — Python puro, sem IA (Fase 4.1).

XP entra por kill/beat/quest (valores fixos abaixo), level up aplica curvas por
classe (`classes.json` -> level_gains) e gera escolhas pendentes que o jogador
resolve quando quiser (pending_choices não bloqueia o loop).

Progressão de combate usa Cartas: cada nível concede uma escolha de Carta nova
ou evolução A/B; níveis pares concedem Virtude conforme a curva v4.

Convenções:
- Funções NÃO mutam o player recebido: devolvem cópia atualizada.
- Evento level_up segue o shape de proposta do pipeline 2.6 (gerado 100% em
  Python, padrão reputation_changed da 3.4 — o validator rejeita se o LLM propuser).
"""
from typing import Dict, List, Optional, Tuple

import gamedata
from gamedata import CLASSES, XP_TABLE

XP_BY_TIER = {"minion": 50, "elite": 200, "boss": 1000}
XP_PER_BEAT = 150
XP_PER_QUEST = 200
# spec conflito-01 R3: nível máximo passa de 20 para 10.
MAX_LEVEL = gamedata.NIVEL_MAX  # 10

# Curva usada se a classe não tiver level_gains (classe custom/save antigo).
# Vitalidade máxima deriva exclusivamente de Corpo; nível recompõe só recursos
# explicitamente escaláveis.
DEFAULT_LEVEL_GAINS = {"hp": 5, "entropy": 2}


# ---------------------------------------------------------------------------
# XP
# ---------------------------------------------------------------------------
def xp_for_kills(dead_enemies: List[Dict]) -> int:
    """XP por inimigos MORTOS neste round (fugitivo não entra na lista)."""
    total = 0
    for e in dead_enemies or []:
        tier = str(e.get("type", "minion")).strip().lower()
        total += XP_BY_TIER.get(tier, XP_BY_TIER["minion"])
    return total


def xp_to_next(level: int) -> Optional[int]:
    """Limiar de XP acumulado do próximo nível; None se já está no cap."""
    nxt = int(level) + 1
    return XP_TABLE.get(nxt) if nxt <= MAX_LEVEL else None


def _level_gains_for(class_name: str, classes_db: Optional[Dict]) -> Dict[str, int]:
    db = classes_db if classes_db is not None else CLASSES
    gains = (db.get(class_name) or {}).get("level_gains") or DEFAULT_LEVEL_GAINS
    return {
        "hp": int(gains.get("hp", 0) or 0),
        "entropy": int(gains.get("entropy", 0) or 0),
    }


def grant_xp(player: Dict, amount: int, *,
             classes_db: Optional[Dict] = None) -> Tuple[Dict, List[Dict]]:
    """Soma XP e processa level ups (multi-level em sequência).

    Retorna (player_atualizado, eventos level_up). Por nível: máximos sobem pela
    curva da classe e o jogador CURA SÓ O DELTA (level up não é cura grátis);
    escolha de habilidade sempre, ponto de atributo em nível par — ambas viram
    pending_choices (o jogo segue jogável com escolha pendente).
    """
    p = dict(player)
    p["pending_choices"] = list(p.get("pending_choices") or [])
    p["xp"] = int(p.get("xp", 0) or 0) + int(amount or 0)
    is_v4 = p.get("vitalidade") is not None or isinstance(p.get("virtudes"), dict)
    if is_v4:
        gamedata.sync_vitality(p)
    events: List[Dict] = []

    gains = _level_gains_for(str(p.get("class_name", "")), classes_db)
    while True:
        threshold = xp_to_next(int(p.get("level", 1) or 1))
        if threshold is None or p["xp"] < threshold:
            break
        new_level = int(p.get("level", 1) or 1) + 1
        p["level"] = new_level
        # Vitalidade não escala com nível: somente Corpo (escolha separada)
        # altera seu teto. Entropia mantém a curva por classe.
        entropy_delta = gains.get("entropy", 0)
        if entropy_delta:
            p["max_entropy"] = int(p.get("max_entropy", 0) or 0) + entropy_delta
            p["entropy"] = min(
                p["max_entropy"],
                int(p.get("entropy", 0) or 0) + entropy_delta,
            )
        if not is_v4:
            # Compatibilidade de funções puras que ainda exercitam fichas
            # arquivadas; estados jogáveis pré-v4 são recusados na borda.
            hp_delta = gains.get("hp", 0)
            if hp_delta:
                p["max_hp"] = int(p.get("max_hp", 0) or 0) + hp_delta
                p["hp"] = min(
                    p["max_hp"], int(p.get("hp", 0) or 0) + hp_delta)
        # spec conflito-02/13: a cada nível, nova Carta OU evolução.
        p["pending_choices"].append(
            {"id": f"lvl{new_level}-carta", "level": new_level, "kind": "carta"})
        # R3: níveis 2/4/6/8/10 dão +1 numa Virtude (escolha do jogador)
        if new_level in gamedata.NIVEIS_GANHO_VIRTUDE:
            p["pending_choices"].append(
                {"id": f"lvl{new_level}-virtude", "level": new_level, "kind": "virtude"})
        events.append({
            "type": "level_up", "actor_id": "player", "target_id": "player",
            "detail": f"{p.get('name', 'O herói')} alcançou o nível {new_level}",
            "payload": {"new_level": new_level}, "source": "progression",
        })
    if is_v4:
        gamedata.sync_legacy_hp_aliases(p)
    return p, events


# ---------------------------------------------------------------------------
# Acervo / subclasse
# ---------------------------------------------------------------------------
def player_branch(player: Dict, *, abilities_db: Optional[Dict] = None) -> Optional[str]:
    """Subclasse derivada da primeira Carta conhecida que declara subclasse."""
    if player.get("subclass"):
        return str(player["subclass"])
    if abilities_db is None:
        from services.cards import all_cards
        db = all_cards()
    else:
        db = abilities_db
    for cid in player.get("known_cards") or []:
        branch = (db.get(cid) or {}).get("subclasse")
        if branch:
            return str(branch)
    return None


def eligible_cards(player: Dict) -> List[str]:
    """Cartas ainda não conhecidas da classe e da subclasse já escolhida."""
    from services import cards
    known = set(player.get("known_cards") or [])
    branch = player_branch(player)
    return [
        c["id"] for c in cards.cards_for_class(str(player.get("class_name", "")), branch or "")
        if c["id"] not in known and (not branch or c.get("subclasse") in ("", branch))
    ]


def apply_choice(player: Dict, choice_id: str, *,
                 ability_id: Optional[str] = None,
                 attr: Optional[str] = None,
                 virtude: Optional[str] = None,
                 card_id: Optional[str] = None,
                 evolve_card_id: Optional[str] = None,
                 caminho: Optional[str] = None,
                 abilities_db: Optional[Dict] = None) -> Tuple[Dict, Optional[str]]:
    """Valida e consome UMA pending_choice. Retorna (player, erro|None).

    Erro deixa o player ORIGINAL intocado (validação server-side do /game/levelup)."""
    pending = list(player.get("pending_choices") or [])
    choice = next((c for c in pending if c.get("id") == choice_id), None)
    if choice is None:
        return player, f"Escolha '{choice_id}' não está pendente."

    p = dict(player)
    if choice.get("kind") == "virtude":
        # spec conflito-01 R3: +1 numa Virtude, teto 5, recalcula Vitalidade na hora
        key = gamedata.normalize_virtude(virtude or attr or "")
        if key not in gamedata.VIRTUDES:
            return player, (f"Virtude '{virtude or attr}' inválida "
                            f"(use {'/'.join(gamedata.VIRTUDES)}).")
        virts = dict(p.get("virtudes") or {})
        atual = int(virts.get(key, 0) or 0)
        if atual >= gamedata.VIRTUDE_MAX:
            return player, f"Virtude '{key}' já está no máximo ({gamedata.VIRTUDE_MAX})."
        virts[key] = atual + 1
        p["virtudes"] = virts
        if key == "corpo":
            gamedata.sync_player_vitals(p)  # sobe teto de Vitalidade/espaços na hora
    elif choice.get("kind") == "carta":
        # spec conflito-02 R4: UMA escolha por nível — nova Carta XOR evolução
        from services import cards as cards_svc
        if card_id and (evolve_card_id or caminho):
            return player, "Escolha nova Carta OU evolução, não ambas."
        if card_id:
            if card_id not in set(eligible_cards(player)):
                return player, f"Carta '{card_id}' não é elegível para esta ficha."
            known = list(p.get("known_cards") or [])
            if card_id in known:
                return player, f"Carta '{card_id}' já está no Acervo."
            p["known_cards"] = known + [card_id]
        elif evolve_card_id:
            fake = {"player": p}
            res = cards_svc.evolve_card(fake, evolve_card_id, caminho or "")
            if not res["ok"]:
                return player, res["error"]
            p["known_cards"] = list(p.get("known_cards") or [])  # garante presença de campos
        else:
            return player, "Escolha de Carta exige card_id (nova) ou evolve_card_id+caminho."
    else:
        return player, f"Tipo de escolha desconhecido: {choice.get('kind')!r}."

    p["pending_choices"] = [c for c in pending if c.get("id") != choice_id]
    return p, None
