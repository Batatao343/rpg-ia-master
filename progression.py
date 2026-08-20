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
MAX_LEVEL = gamedata.NIVEL_MAX

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


def _entropy_gain_for(class_name: str, level: int, classes_db: Optional[Dict]) -> int:
    if level <= 10:
        return _level_gains_for(class_name, classes_db)["entropy"]
    db = classes_db if classes_db is not None else CLASSES
    curve = (db.get(class_name) or {}).get("late_entropy_curve") or {}
    return int((curve.get("gains") or {}).get(str(level), 0) or 0)


def _entropy_cap_for(class_name: str, classes_db: Optional[Dict]) -> Optional[int]:
    db = classes_db if classes_db is not None else CLASSES
    cap = ((db.get(class_name) or {}).get("late_entropy_curve") or {}).get("cap")
    return int(cap) if cap is not None else None


def _append_choice_once(player: Dict, choice: Dict) -> None:
    if not any(row.get("id") == choice["id"] for row in player["pending_choices"]):
        player["pending_choices"].append(choice)


def _apex_card_id(player: Dict) -> Optional[str]:
    from services.cards import cards_for_class
    branch = player.get("subclass")
    if not branch:
        return None
    matches = [card["id"] for card in cards_for_class(
        str(player.get("class_name", "")), str(branch))
        if card.get("apex") and card.get("subclasse") == branch]
    return matches[0] if len(matches) == 1 else None


def grant_apex_if_due(player: Dict, new_level: int) -> Tuple[Dict, Optional[str]]:
    p = dict(player)
    p["known_cards"] = list(p.get("known_cards") or [])
    p["progression_grants"] = list(p.get("progression_grants") or [])
    if new_level != 20:
        return p, None
    card_id = _apex_card_id(p)
    if not card_id:
        return p, None
    ledger = f"lvl20:apex:{card_id}"
    if ledger not in p["progression_grants"]:
        if card_id not in p["known_cards"]:
            p["known_cards"].append(card_id)
        p["progression_grants"].append(ledger)
        return p, card_id
    return p, None


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

    class_name = str(p.get("class_name", ""))
    gains = _level_gains_for(class_name, classes_db)
    while True:
        threshold = xp_to_next(int(p.get("level", 1) or 1))
        if threshold is None or p["xp"] < threshold:
            break
        new_level = int(p.get("level", 1) or 1) + 1
        p["level"] = new_level
        # Vitalidade não escala com nível: somente Corpo (escolha separada)
        # altera seu teto. Entropia mantém a curva por classe.
        entropy_delta = _entropy_gain_for(class_name, new_level, classes_db)
        if entropy_delta:
            maximum = int(p.get("max_entropy", 0) or 0) + entropy_delta
            entropy_cap = _entropy_cap_for(class_name, classes_db)
            p["max_entropy"] = min(maximum, entropy_cap) if entropy_cap else maximum
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
        if new_level == 3 and not p.get("subclass"):
            _append_choice_once(
                p, {"id": "lvl3-subclass", "level": 3, "kind": "subclass"})
        if new_level != 20:
            _append_choice_once(
                p, {"id": f"lvl{new_level}-carta", "level": new_level, "kind": "carta"})
        # R3: níveis 2/4/6/8/10 dão +1 numa Virtude (escolha do jogador)
        if new_level in gamedata.NIVEIS_GANHO_VIRTUDE:
            _append_choice_once(
                p, {"id": f"lvl{new_level}-virtude", "level": new_level, "kind": "virtude"})
        if new_level in gamedata.NIVEIS_MAESTRIA_VIRTUDE:
            _append_choice_once(p, {
                "id": f"lvl{new_level}-virtue-mastery", "level": new_level,
                "kind": "virtue_mastery",
            })
        apex_id = None
        if new_level == 20:
            p, apex_id = grant_apex_if_due(p, new_level)
        events.append({
            "type": "level_up", "actor_id": "player", "target_id": "player",
            "detail": f"{p.get('name', 'O herói')} alcançou o nível {new_level}",
            "payload": {"new_level": new_level}, "source": "progression",
        })
        if apex_id:
            events.append({
                "type": "class_apex_unlocked", "actor_id": "player", "target_id": apex_id,
                "detail": f"Ápice de classe desbloqueado: {apex_id}",
                "payload": {"new_level": 20, "card_id": apex_id}, "source": "progression",
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


def eligible_subclasses(player: Dict) -> List[Dict]:
    class_data = CLASSES.get(str(player.get("class_name", ""))) or {}
    result = []
    for subclass_id, branch in (class_data.get("branches") or {}).items():
        result.append({
            "id": subclass_id,
            "name": branch.get("name", subclass_id),
            "identity": branch.get("identity", ""),
            "playstyle": branch.get("playstyle", ""),
            "tradeoff": branch.get("tradeoff", ""),
            "preview_card_ids": list(branch.get("preview_card_ids") or []),
        })
    return result


def eligible_cards(player: Dict) -> List[str]:
    """Cartas ainda não conhecidas da classe e da subclasse já escolhida."""
    from services import cards
    known = set(player.get("known_cards") or [])
    branch = str(player.get("subclass") or "") or None
    level = int(player.get("level", 1) or 1)
    subclass_pending = any(
        row.get("kind") == "subclass" for row in player.get("pending_choices") or [])
    return [
        c["id"] for c in cards.cards_for_class(str(player.get("class_name", "")), branch or "")
        if c["id"] not in known
        and int(c.get("level_req", 1) or 1) <= level
        and not c.get("apex")
        and (not c.get("subclasse") or (
            level >= 3 and branch and not subclass_pending and c.get("subclasse") == branch))
    ]


def effective_virtue_card_stage(card_choice: Dict) -> int:
    return max(1, min(5, int(card_choice.get("estagio", 1) or 1)
                      + int(card_choice.get("mastery", 0) or 0)))


def normalize_player_progression(player: Dict) -> Dict:
    """Backfill aditivo/idempotente para saves anteriores ao cap 20."""
    p = dict(player)
    p["known_cards"] = list(p.get("known_cards") or [])
    p["pending_choices"] = [dict(row) for row in p.get("pending_choices") or []]
    p["progression_grants"] = list(dict.fromkeys(p.get("progression_grants") or []))
    p["virtue_cards"] = [
        {**dict(row), "mastery": max(0, min(2, int(row.get("mastery", 0) or 0)))}
        for row in p.get("virtue_cards") or []
    ]
    level = max(1, min(MAX_LEVEL, int(p.get("level", 1) or 1)))
    p["level"] = level
    if level >= 3 and not p.get("subclass"):
        inferred = player_branch(p)
        if inferred:
            p["subclass"] = inferred
            p["progression_grants"].append(f"legacy:subclass:{inferred}")
        else:
            _append_choice_once(
                p, {"id": "lvl3-subclass", "level": 3, "kind": "subclass"})
    if level < 3:
        p.pop("subclass", None)
    for mastery_level in gamedata.NIVEIS_MAESTRIA_VIRTUDE:
        prefix = f"lvl{mastery_level}:virtue-mastery:"
        pending_id = f"lvl{mastery_level}-virtue-mastery"
        if (level >= mastery_level
                and not any(key.startswith(prefix) for key in p["progression_grants"])
                and not any(row.get("id") == pending_id for row in p["pending_choices"])):
            _append_choice_once(p, {
                "id": pending_id, "level": mastery_level, "kind": "virtue_mastery",
            })
    if 11 <= level < 20:
        _append_choice_once(
            p, {"id": f"lvl{level}-carta", "level": level, "kind": "carta"})
    if level == 20:
        p, _ = grant_apex_if_due(p, level)
    p["progression_grants"] = list(dict.fromkeys(p["progression_grants"]))
    return p


def apply_choice(player: Dict, choice_id: str, *,
                 ability_id: Optional[str] = None,
                 attr: Optional[str] = None,
                 virtude: Optional[str] = None,
                 card_id: Optional[str] = None,
                 evolve_card_id: Optional[str] = None,
                 caminho: Optional[str] = None,
                 virtue_card_id: Optional[str] = None,
                 subclass_id: Optional[str] = None,
                 abilities_db: Optional[Dict] = None) -> Tuple[Dict, Optional[str]]:
    """Valida e consome UMA pending_choice. Retorna (player, erro|None).

    Erro deixa o player ORIGINAL intocado (validação server-side do /game/levelup)."""
    pending = list(player.get("pending_choices") or [])
    choice = next((c for c in pending if c.get("id") == choice_id), None)
    if choice is None:
        return player, f"Escolha '{choice_id}' não está pendente."

    first_required = next(
        (row for row in pending if row.get("kind") == "subclass"), None)
    if first_required and choice.get("kind") != "subclass":
        return player, "Escolha a subclasse antes das demais opções deste nível."

    p = dict(player)
    if choice.get("kind") == "subclass":
        if p.get("subclass"):
            return player, "A subclasse já foi escolhida e é irreversível."
        options = {row["id"] for row in eligible_subclasses(p)}
        if subclass_id not in options:
            return player, f"Subclasse '{subclass_id}' inválida para esta classe."
        p["subclass"] = subclass_id
        grants = list(p.get("progression_grants") or [])
        grants.append(f"lvl3:subclass:{subclass_id}")
        p["progression_grants"] = list(dict.fromkeys(grants))
        p["progression_events"] = list(p.get("progression_events") or []) + [{
            "type": "subclass_chosen", "subclass_id": subclass_id,
            "level": int(p.get("level", 3) or 3),
        }]
    elif choice.get("kind") == "virtude":
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
    elif choice.get("kind") == "virtue_mastery":
        virtue_cards = [dict(row) for row in p.get("virtue_cards") or []]
        selected = next(
            (row for row in virtue_cards if row.get("card_id") == virtue_card_id), None)
        if not selected:
            return player, "Escolha uma das Cartas de Virtude permanentes."
        mastery = int(selected.get("mastery", 0) or 0)
        total = sum(int(row.get("mastery", 0) or 0) for row in virtue_cards)
        if mastery >= 2 or total >= 3:
            return player, "Maestria máxima atingida para esta distribuição."
        selected["mastery"] = mastery + 1
        p["virtue_cards"] = virtue_cards
    else:
        return player, f"Tipo de escolha desconhecido: {choice.get('kind')!r}."

    p["pending_choices"] = [c for c in pending if c.get("id") != choice_id]
    grants = list(p.get("progression_grants") or [])
    if choice.get("kind") == "virtue_mastery":
        grants.append(f"lvl{choice.get('level')}:virtue-mastery:{virtue_card_id}")
    else:
        grants.append(f"choice:{choice_id}")
    p["progression_grants"] = list(dict.fromkeys(grants))
    if choice.get("kind") == "subclass" and int(p.get("level", 1) or 1) >= 20:
        p, apex_id = grant_apex_if_due(p, 20)
        if apex_id:
            p["progression_events"] = list(p.get("progression_events") or []) + [{
                "type": "class_apex_unlocked", "card_id": apex_id, "level": 20,
            }]
    return p, None
