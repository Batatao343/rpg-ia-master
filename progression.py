"""
progression.py
Núcleo DETERMINÍSTICO de progressão — Python puro, sem IA (Fase 4.1).

XP entra por kill/beat/quest (valores fixos abaixo), level up aplica curvas por
classe (`classes.json` -> level_gains) e gera escolhas pendentes que o jogador
resolve quando quiser (pending_choices não bloqueia o loop).

Árvore de habilidades: `player_abilities.json` ganha classes/branch/tier/
level_req/requires (conteúdo autorado na spec 4.1b). Ramo = subclasse mutuamente
exclusiva, DERIVADA de known_abilities (player_branch) — zero campo novo de estado.

Convenções:
- Funções NÃO mutam o player recebido: devolvem cópia atualizada.
- Evento level_up segue o shape de proposta do pipeline 2.6 (gerado 100% em
  Python, padrão reputation_changed da 3.4 — o validator rejeita se o LLM propuser).
"""
import unicodedata
from typing import Dict, List, Optional, Tuple

import gamedata
from gamedata import ABILITIES, CLASSES, XP_TABLE

XP_BY_TIER = {"minion": 50, "elite": 200, "boss": 1000}
XP_PER_BEAT = 150
XP_PER_QUEST = 200
# spec conflito-01 R3: nível máximo passa de 20 para 10.
MAX_LEVEL = gamedata.NIVEL_MAX  # 10

# Curva usada se a classe não tiver level_gains (classe custom/save antigo).
# spec conflito-01: jogador ganha hp + Entropia por nível (mana/stamina saíram).
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
    return {k: int(gains.get(k, 0) or 0) for k in ("hp", "entropy")}


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
    events: List[Dict] = []

    gains = _level_gains_for(str(p.get("class_name", "")), classes_db)
    while True:
        threshold = xp_to_next(int(p.get("level", 1) or 1))
        if threshold is None or p["xp"] < threshold:
            break
        new_level = int(p.get("level", 1) or 1) + 1
        p["level"] = new_level
        # spec conflito-01: jogador sobe hp + Entropia (mana/stamina saíram do schema)
        for res, field in (("hp", "max_hp"), ("entropy", "max_entropy")):
            delta = gains.get(res, 0)
            if delta:
                p[field] = int(p.get(field, 0) or 0) + delta
                p[res] = min(p[field], int(p.get(res, 0) or 0) + delta)
        p["pending_choices"].append(
            {"id": f"lvl{new_level}-ability", "level": new_level, "kind": "ability"})
        # R3: níveis 2/4/6/8/10 dão +1 numa Virtude (escolha do jogador)
        if new_level in gamedata.NIVEIS_GANHO_VIRTUDE:
            p["pending_choices"].append(
                {"id": f"lvl{new_level}-virtude", "level": new_level, "kind": "virtude"})
        events.append({
            "type": "level_up", "actor_id": "player", "target_id": "player",
            "detail": f"{p.get('name', 'O herói')} alcançou o nível {new_level}",
            "payload": {"new_level": new_level}, "source": "progression",
        })
    return p, events


# ---------------------------------------------------------------------------
# Árvore / subclasse (ramo)
# ---------------------------------------------------------------------------
def player_branch(player: Dict, *, abilities_db: Optional[Dict] = None) -> Optional[str]:
    """Subclasse derivada: branch da primeira habilidade conhecida que tem branch.
    None = ainda no tronco comum. Sem campo novo de estado (à prova de save antigo)."""
    db = abilities_db if abilities_db is not None else ABILITIES
    for aid in player.get("known_abilities") or []:
        br = (db.get(aid) or {}).get("branch")
        if br:
            return str(br)
    return None


def eligible_abilities(player: Dict, *,
                       abilities_db: Optional[Dict] = None) -> List[str]:
    """Ids elegíveis na árvore (R5 + R5b da spec 4.1).

    Elegível = da classe (ou "all") ∧ nível >= level_req ∧ requires ⊆ conhecidas
    ∧ não conhecida ∧ não pertence a ramo rival (lock de subclasse).
    """
    db = abilities_db if abilities_db is not None else ABILITIES
    known = set(player.get("known_abilities") or [])
    class_name = str(player.get("class_name", ""))
    level = int(player.get("level", 1) or 1)
    branch = player_branch(player, abilities_db=db)

    out: List[str] = []
    for aid, a in db.items():
        if aid in known:
            continue
        classes = a.get("classes") or []
        if "all" not in classes and class_name not in classes:
            continue
        if level < int(a.get("level_req", 1) or 1):
            continue
        if not set(a.get("requires") or []) <= known:
            continue
        a_branch = a.get("branch")
        if a_branch and branch and a_branch != branch:
            continue  # ramo rival trancado para sempre nesta ficha
        out.append(aid)
    return out


def apply_choice(player: Dict, choice_id: str, *,
                 ability_id: Optional[str] = None,
                 attr: Optional[str] = None,
                 virtude: Optional[str] = None,
                 abilities_db: Optional[Dict] = None) -> Tuple[Dict, Optional[str]]:
    """Valida e consome UMA pending_choice. Retorna (player, erro|None).

    Erro deixa o player ORIGINAL intocado (validação server-side do /game/levelup)."""
    pending = list(player.get("pending_choices") or [])
    choice = next((c for c in pending if c.get("id") == choice_id), None)
    if choice is None:
        return player, f"Escolha '{choice_id}' não está pendente."

    p = dict(player)
    if choice.get("kind") == "ability":
        if not ability_id:
            return player, "Escolha de habilidade exige ability_id."
        if ability_id not in eligible_abilities(player, abilities_db=abilities_db):
            return player, f"Habilidade '{ability_id}' não é elegível para esta ficha."
        p["known_abilities"] = list(p.get("known_abilities") or []) + [ability_id]
        # spec arvores-habilidade-classes: passiva entropy_max_bonus aplica no
        # APRENDIZADO (permanente) — max_entropy e entropy sobem juntos.
        from combat_mechanics import entropy_max_bonus_of
        db = abilities_db if abilities_db is not None else ABILITIES
        bonus = entropy_max_bonus_of(db.get(ability_id) or {})
        if bonus:
            p["max_entropy"] = int(p.get("max_entropy", 0) or 0) + bonus
            p["entropy"] = int(p.get("entropy", 0) or 0) + bonus
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
    else:
        return player, f"Tipo de escolha desconhecido: {choice.get('kind')!r}."

    p["pending_choices"] = [c for c in pending if c.get("id") != choice_id]
    return p, None


# ---------------------------------------------------------------------------
# Backfill de saves antigos (R8): known_abilities texto-livre -> ids canônicos
# ---------------------------------------------------------------------------
def _fold(s: str) -> str:
    """lower + sem acento, p/ casar nome livre com nome canônico."""
    nfkd = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def canonicalize_known_abilities(player: Dict, *,
                                 abilities_db: Optional[Dict] = None) -> Dict:
    """Converte known_abilities texto-livre em ids canônicos (in-place-safe: cópia).

    - id já canônico: mantém
    - "[Passiva] ..." : descarta (passiva vive em CLASSES[class]["passive"])
    - nome que casa (case/acento-insensitive) com name de habilidade: vira o id
    - não-mapeável: descartado (nunca funcionou mecanicamente antes)
    - garante 'ataque_basico' e defaults de pending_choices/xp/level
    """
    db = abilities_db if abilities_db is not None else ABILITIES
    by_name = {_fold(a.get("name", "")): aid for aid, a in db.items()}

    p = dict(player)
    out: List[str] = []
    for entry in p.get("known_abilities") or []:
        e = str(entry)
        if e.startswith("[Passiva]"):
            continue
        if e in db:
            if e not in out:
                out.append(e)
            continue
        mapped = by_name.get(_fold(e))
        if mapped and mapped not in out:
            out.append(mapped)
    if "ataque_basico" not in out:
        out.insert(0, "ataque_basico")
    p["known_abilities"] = out
    p.setdefault("pending_choices", [])
    p.setdefault("xp", 0)
    p.setdefault("level", 1)
    return p
