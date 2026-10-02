"""
chronicle.py — Crônica por capítulos: milestones determinísticos + prosa (Fase 3.1).

"LLM propõe, motor aplica": todo GameEvent APLICADO cujo tipo está em
`CHRONICLE_EVENT_TYPES` vira uma entrada `milestone` no capítulo atual, via template
Python (zero LLM) — o jogador nunca perde um evento importante porque o menestrel
esqueceu. A prosa do archivist (`kind="prose"`) entra pelo mesmo `append_entry`.
Capítulos abrem quando o `arc_title` do campaign_manager muda.

Funções são PURAS (agentes retornam dict parcial do GameState): `append_entry` e
`open_chapter` devolvem cópia, nunca mutam a lista recebida.

Spec: specs/SPEC-006-fase-3.1-diario-cronica.md §3.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List
from uuid import NAMESPACE_URL, uuid5

from services.context_builder import _name

# Tipos que merecem crônica (alto impacto). faction_relation_changed fica FORA
# (ruído — mudanças de relação são frequentes e já aparecem via reputação/2.7).
CHRONICLE_EVENT_TYPES = {
    "npc_killed", "location_control_changed", "quest_completed", "quest_failed",
    "secret_revealed", "level_up", "player_died", "player_downed",
    "unique_item_claimed", "subclass_chosen", "class_apex_unlocked",
}

# Templates voltados ao JOGADOR (prosa curta), diferentes dos EVENT_TEMPLATES
# telegráficos do context_builder (que servem ao LLM).
CHRONICLE_TEMPLATES: Dict[str, str] = {
    "npc_killed": "{target} tombou{by_player}.",
    "location_control_changed": "{controller} tomou o controle de {target}.",
    "quest_completed": "A missão \"{target}\" foi concluída.",
    "quest_failed": "A missão \"{target}\" fracassou.",
    "secret_revealed": "Um segredo veio à luz: {fact}",
    "level_up": "O herói alcançou o nível {new_level}.",
    "player_died": "Aqui termina a saga: {detail}.",
    "player_downed": "O herói caiu; seu destino ainda aguarda uma escolha. {detail}.",
    "unique_item_claimed": "{item} agora pertence ao herói — não há outro no mundo.",
    "subclass_chosen": "A senda {detail} foi escolhida.",
    "class_apex_unlocked": "O Ápice {detail} foi alcançado.",
}

_DEFAULT_TITLE = "Crônica da jornada"


def render_milestone(event: Dict, projection: Dict) -> str:
    """1 frase de milestone para o jogador. Tipo fora de CHRONICLE_EVENT_TYPES → ""."""
    etype = event.get("type")
    if etype not in CHRONICLE_EVENT_TYPES:
        return ""
    tmpl = CHRONICLE_TEMPLATES.get(etype)
    if not tmpl:
        return ""
    payload = event.get("payload", {}) or {}

    if etype == "level_up":
        n = payload.get("new_level")
        return tmpl.format(new_level=n) if isinstance(n, int) else ""

    if etype == "player_died":
        detail = payload.get("detail", "") or "o herói caiu"
        return tmpl.format(detail=detail)

    if etype == "player_downed":
        detail = payload.get("detail", "") or "A jornada foi interrompida"
        return tmpl.format(detail=detail)

    if etype == "unique_item_claimed":
        # holder != player (mercador etc.) não é feito do herói — sem milestone
        if payload.get("holder", "player") != "player":
            return ""
        from gamedata import ARTIFACTS_DB
        item = (ARTIFACTS_DB.get(event.get("target_id", "")) or {}).get(
            "name", event.get("target_id", ""))
        return tmpl.format(item=item)

    if etype in ("subclass_chosen", "class_apex_unlocked"):
        detail = payload.get("name") or payload.get("card_id") or event.get("target_id", "")
        return tmpl.format(detail=detail)

    if etype == "secret_revealed":
        facts = (projection or {}).get("revealed_facts", {}) or {}
        fact = (facts.get(event.get("event_id", ""), {}) or {}).get("fact", "")
        fact = fact or payload.get("detail", "")
        if not fact:
            return ""
        return tmpl.format(fact=fact)

    by_player = " pelas mãos do herói" if event.get("actor_id") == "player" else ""
    # Fase 3.3: target_id de quest_completed/quest_failed é um quest_id (não id de
    # grafo) — payload.quest_title (embutido pelo event_processor) tem prioridade.
    return tmpl.format(
        target=payload.get("quest_title") or _name(event.get("target_id")),
        controller=_name(payload.get("new_controller_id")),
        by_player=by_player,
    )


def _new_chapter(title: str, turn: int, location: str) -> Dict:
    seed = f"valoria:chronicle:{title}:{turn}:{location}"
    return {"chapter_id": uuid5(NAMESPACE_URL, seed).hex, "title": title,
            "started_turn": turn, "location": location, "entries": []}


def ensure_chronicle_ids(chronicle: List[Dict], *, game_id: str = "legacy") -> List[Dict]:
    """Backfill puro/idempotente de IDs sem usar título como identidade runtime."""
    chapters: List[Dict] = []
    for chapter_index, raw_chapter in enumerate(chronicle or []):
        chapter = dict(raw_chapter)
        chapter_seed = hashlib.sha256(
            f"{game_id}:{chapter_index}:{chapter.get('started_turn', 0)}:{chapter.get('title', '')}".encode()
        ).hexdigest()
        chapter.setdefault("chapter_id", uuid5(NAMESPACE_URL, chapter_seed).hex)
        entries = []
        for entry_index, raw_entry in enumerate(chapter.get("entries") or []):
            entry = dict(raw_entry)
            entry_seed = hashlib.sha256(
                f"{chapter['chapter_id']}:{entry_index}:{entry.get('turn', 0)}:{entry.get('kind', '')}:{entry.get('event_id', '')}:{entry.get('text', '')}".encode()
            ).hexdigest()
            entry.setdefault("entry_id", uuid5(NAMESPACE_URL, entry_seed).hex)
            entries.append(entry)
        chapter["entries"] = entries
        chapters.append(chapter)
    return chapters


def append_entry(chronicle: List[Dict], *, text: str, turn: int,
                 kind: str, event_id: str = "") -> List[Dict]:
    """PURO: retorna cópia com a entrada no capítulo atual (cria capítulo se vazio)."""
    chapters = list(chronicle or [])
    if not chapters:
        chapters = [_new_chapter(_DEFAULT_TITLE, 0, "")]
    last = dict(chapters[-1])
    entries = list(last.get("entries") or [])
    entry: Dict = {"text": text, "turn": turn, "kind": kind}
    if event_id:
        entry["event_id"] = event_id
    seed = f"{last.get('chapter_id', '')}:{len(entries)}:{turn}:{kind}:{event_id}:{text}"
    entry["entry_id"] = uuid5(NAMESPACE_URL, seed).hex
    entries.append(entry)
    last["entries"] = entries
    chapters[-1] = last
    return chapters


def open_chapter(chronicle: List[Dict], *, title: str, turn: int,
                 location: str) -> List[Dict]:
    """Abre capítulo novo. Mesmo título do capítulo atual → no-op (lista original)."""
    if chronicle and (chronicle[-1].get("title") or "") == title:
        return chronicle
    return list(chronicle or []) + [_new_chapter(title, turn, location)]


def default_chapter_title(region: str) -> str:
    """Título do capítulo 1 (determinístico, sem LLM)."""
    region = (region or "").strip()
    return f"O início da jornada — {region}" if region else _DEFAULT_TITLE
