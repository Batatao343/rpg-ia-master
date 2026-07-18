"""
npc_layers.py — NPCs em 3 camadas + traits ocultos (spec npcs-3-camadas-traits).

Camada 1 = todos os NPCs da sessão (GameState.npcs); camada 2 = conhecidos pelo
jogador (`known_by_player`); camada 3 = presentes na cena (`in_scene` — gate do
npc_actor). Traits são 100% Python: sorteio seeded por (npc_id, game_id),
revelação por contagem de interações, DC modifiers somados de hidden+revealed
(o mundo é real antes de ser conhecido).

Funções puras — nenhum LLM, nenhum estado global além do cache do catálogo.
"""

from __future__ import annotations

import hashlib
import random
from typing import Dict, List, Optional, Tuple

from gamedata import load_json_data

_traits_cache: Optional[Dict[str, dict]] = None

# Contextos canônicos de DC (R2). Novos contextos = decisão de spec.
DC_CONTEXTS = ("persuasao", "intimidacao", "comercio", "insight")


def traits_catalog() -> Dict[str, dict]:
    """Catálogo id -> trait de data/traits.json (cache em módulo)."""
    global _traits_cache
    if _traits_cache is None:
        data = load_json_data("traits.json") or {}
        _traits_cache = {t["id"]: t for t in data.get("traits", []) if t.get("id")}
    return _traits_cache


def clear_traits_cache() -> None:
    global _traits_cache
    _traits_cache = None


def roll_hidden_traits(npc_id: str, game_id: str,
                       k_range: Tuple[int, int] = (1, 3),
                       region_tag: str = "") -> List[str]:
    """Sorteio determinístico de traits ocultos (R3).

    Seed = sha256(npc_id + game_id): mesmo NPC no mesmo save sorteia IGUAL
    (replay estável). Traits com tag da região do NPC entram com peso dobrado.
    """
    catalog = traits_catalog()
    if not catalog:
        return []
    seed = int(hashlib.sha256(f"{npc_id}|{game_id}".encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)
    k = rng.randint(*k_range)

    pool: List[str] = []
    for tid, trait in sorted(catalog.items()):
        peso = 2 if region_tag and region_tag in (trait.get("tags") or []) else 1
        pool.extend([tid] * peso)
    escolhidos: List[str] = []
    while pool and len(escolhidos) < k:
        pick = rng.choice(pool)
        escolhidos.append(pick)
        pool = [p for p in pool if p != pick]
    return escolhidos


def ensure_npc_fields(npc: dict, game_id: str, home_location_id: str = "",
                      in_scene: Optional[bool] = None) -> dict:
    """Backfill idempotente dos campos de camada (R1). Não sobrescreve existentes.

    `in_scene=None` preserva o valor atual (ausente = legado, tratado como
    presente pelo gate — compat com saves no meio de uma cena).
    """
    npc = dict(npc)
    npc.setdefault("home_location_id", home_location_id)
    npc.setdefault("revealed_traits", [])
    npc.setdefault("interaction_count", 0)
    npc.setdefault("known_by_player", True)
    npc.setdefault("knowledge_source", "met")
    if "hidden_traits" not in npc:
        npc_id = npc.get("id") or npc.get("name", "npc")
        npc["hidden_traits"] = roll_hidden_traits(
            str(npc_id), str(game_id), region_tag=str(home_location_id))
    if in_scene is not None:
        npc["in_scene"] = in_scene
    return npc


def is_in_scene(npc: dict) -> bool:
    """Gate da camada 3: só `in_scene=False` EXPLÍCITO bloqueia (ausente =
    legado presente — save antigo no meio de cena não fica órfão)."""
    return bool(npc.get("in_scene", True))


def npcs_in_scene(state: Dict) -> List[str]:
    """spec npc-fallback-sem-alvo (R1): interlocutores DISPONÍVEIS agora —
    NPCs `in_scene` no dict `npcs` + membros de party PRESENTES (ativos, não
    `waiting`). Ordem: NPCs da cena primeiro, depois aliados. Usado para
    resolver alvo quando o router não nomeou ninguém."""
    out: List[str] = []
    for name, npc in (state.get("npcs") or {}).items():
        if isinstance(npc, dict) and is_in_scene(npc) and name not in out:
            out.append(name)
    for c in state.get("party") or []:
        if (isinstance(c, dict) and c.get("active")
                and c.get("status", "ativo") == "ativo"
                and c.get("name") and c.get("name") not in out):
            out.append(c["name"])
    return out


# spec encontros-dedupe (R2): NPC gerado descartável não reaparece por N turnos.
ENCOUNTER_COOLDOWN_TURNS = 20


def npcs_for_context(state: Dict) -> List[str]:
    """spec encontros-dedupe (R1/R2): NPCs elegíveis para o CONTEXTO do narrador.
    Entram: quem está `in_scene`, membros de party, e NPCs VINCULADOS ao local
    atual (`home_location_id`). Um NPC gerado por encontro fica preso ao local
    onde surgiu — não vaza para outras cenas (era o carrossel de templates:
    'Sobrevivente moribundo' em 3 locais em 6 turnos). NPC sem vínculo
    (`home_location_id` vazio) só aparece se `in_scene`/party."""
    world = state.get("world") or {}
    loc = world.get("current_location_id", "") or ""
    party_names = {c.get("name") for c in (state.get("party") or [])
                   if isinstance(c, dict)}
    out: List[str] = []
    for name, npc in (state.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        if is_in_scene(npc) or name in party_names:
            out.append(name)
            continue
        home = npc.get("home_location_id") or ""
        if home and loc and home == loc:
            out.append(name)
    return out


def reset_scene(npcs: Dict[str, dict]) -> Dict[str, dict]:
    """Viagem: ninguém teleporta junto — in_scene=False para todos (R5).
    (Companions de party têm estado próprio e não vivem neste dict.)"""
    return {
        nome: {**npc, "in_scene": False} if isinstance(npc, dict) else npc
        for nome, npc in npcs.items()
    }


def tick_interaction(npc: dict) -> Tuple[dict, List[str]]:
    """Fim de turno de conversa bem-sucedida (R7): incrementa contagem e move
    traits maduros (interaction_count >= reveal_after) para revealed.
    Retorna (npc_atualizado, ids_revelados_NESTE_turno)."""
    npc = dict(npc)
    npc["interaction_count"] = int(npc.get("interaction_count", 0)) + 1
    catalog = traits_catalog()
    revelados: List[str] = []
    hidden = list(npc.get("hidden_traits") or [])
    revealed = list(npc.get("revealed_traits") or [])
    for tid in list(hidden):
        after = int((catalog.get(tid) or {}).get("reveal_after", 5))
        if npc["interaction_count"] >= after:
            hidden.remove(tid)
            revealed.append(tid)
            revelados.append(tid)
    npc["hidden_traits"] = hidden
    npc["revealed_traits"] = revealed
    return npc, revelados


def trait_dc_modifier(npc: dict, contexto: str) -> int:
    """Soma dc_modifiers dos traits do NPC (hidden + revealed) no contexto (R6)."""
    catalog = traits_catalog()
    total = 0
    for tid in list(npc.get("hidden_traits") or []) + list(npc.get("revealed_traits") or []):
        total += int(((catalog.get(tid) or {}).get("dc_modifiers") or {}).get(contexto, 0))
    return total


def trait_names(trait_ids: List[str]) -> List[dict]:
    """[{id, name, description}] p/ prompt/frontend — só o que foi passado
    (chame com revealed_traits; hidden nunca sai daqui pra cima)."""
    catalog = traits_catalog()
    out = []
    for tid in trait_ids or []:
        trait = catalog.get(tid)
        if trait:
            out.append({"id": tid, "name": trait.get("name", tid),
                        "description": trait.get("description", "")})
    return out


def visible_npc_view(npcs: Dict[str, dict]) -> List[dict]:
    """Camada 2 para a API (R8/R9): só conhecidos, SEM hidden_traits."""
    out = []
    for key, npc in (npcs or {}).items():
        if not isinstance(npc, dict):
            continue
        if not npc.get("known_by_player", True):
            continue
        mem = npc.get("memory") or []
        out.append({
            "name": npc.get("name", key),
            "role": npc.get("role", ""),
            "location": npc.get("location", ""),
            "home_location_id": npc.get("home_location_id", ""),
            "relationship": npc.get("relationship", 5),
            "knowledge_source": npc.get("knowledge_source", "met"),
            "in_scene": bool(npc.get("in_scene", False)),
            "revealed_traits": trait_names(npc.get("revealed_traits") or []),
            "last_memory": mem[-1] if isinstance(mem, list) and mem else "",
        })
    return out
