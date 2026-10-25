"""SPEC-310: o NPC sabe de si (fação, patente, agenda, motivações e o que ouviu).

Módulo PURO e determinístico: sem LLM, rede, RAG nem escrita; nunca muta `state`/`npc_row`.
Monta três blocos de prompt para o `npc_actor` — `<SOBRE_VOCE>`, `<MOTIVACOES_INTERNAS>` e o
complemento de `<O_QUE_VOCE_SABE>` — com orçamento fixo e corte por linha inteira.

Regra de ouro (NPC): ele só sabe o que viveu (a própria posição/fação/o lugar onde está) ou
ouviu (ledger da SPEC-215). Nunca recebe pressões, severidade, fase do diretor, números de
relação, `world.news` (notícias do JOGADOR) nem a verdade de outros NPCs. O segredo da semente
nunca aparece literal: vira só "há um assunto que você evita: X".

Kill switch: `RPG_NPC_SELF=on|off` (default `on`).
"""

from __future__ import annotations

import json
import os
from collections.abc import Collection
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from services import npc_world

SELF_MAX_CHARS = 700
MOTIVES_MAX_CHARS = 450
KNOWS_MAX_CHARS = 800
MAX_RELATION_LINES = 2
TOTAL_MAX_CHARS = 1950  # soma dos 3 blocos + separadores

_TAG_SELF = "SOBRE_VOCE"
_TAG_MOTIVES = "MOTIVACOES_INTERNAS"
_TAG_KNOWS = "O_QUE_VOCE_SABE"
_MOTIVES_FOOTER = "Isso guia o que você faz e evita; não recite estas linhas."

_ARCHETYPE_PHRASES = {
    "sedentario": "Você raramente sai daqui.",
    "mercador_itinerante": "Você vive de levar mercadoria às regiões vizinhas.",
    "patrulheiro": "Você faz ronda pela região.",
    "peregrino": "Você peregrina entre santuários.",
    "mensageiro": "Você leva recados de um lugar a outro.",
    "lider_residente": "Você governa daqui.",
    "lider_em_campanha": "Você conduz sua gente em campanha.",
}


def mode() -> Literal["on", "off"]:
    raw = os.getenv("RPG_NPC_SELF", "on").strip().lower()
    return "off" if raw == "off" else "on"


@dataclass(frozen=True)
class NpcSelfBlocks:
    sobre_voce: str = ""
    motivacoes: str = ""
    o_que_sabe: str = ""

    def text(self) -> str:
        return "\n".join(b for b in (self.sobre_voce, self.motivacoes, self.o_que_sabe) if b)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _day(state: dict) -> int:
    return npc_world._day_of((state or {}).get("world"))


def _loc_name(location_id: str) -> str:
    import gamedata

    return str((gamedata.get_location(str(location_id or "")) or {}).get("name") or "")


def _ref(npc_key: str, row: dict) -> str:
    return npc_world.npc_ref(str(npc_key), row)


def _faction_row(state: dict, fid: str) -> dict:
    for f in (state or {}).get("factions") or []:
        if isinstance(f, dict) and f.get("id") == fid:
            return f
    return {}


def _defeated(state: dict, fid: str) -> bool:
    return bool(_faction_row(state, fid).get("defeated"))


def _faction_known(state: dict, fid: str) -> bool:
    return bool((((state or {}).get("faction_intel") or {}).get(fid) or {}).get("known"))


def _faction_is_secret(fid: str) -> bool:
    from services import faction_gate

    return faction_gate.is_secret(fid)  # SPEC-314: regra única


def _faction_name(state: dict, fid: str) -> str:
    from services import faction_membership as fm

    return fm.faction_name(state, fid)


# --------------------------------------------------------------------------- #
# Fação e patente (R7, R8, R12)
# --------------------------------------------------------------------------- #
def self_faction(state: dict, npc_key: str, row: dict) -> str:
    """Resolvedor único: projection (troca de lado) > faction_id > faction > grafo > leads > member_of."""
    from services import graph_resolver as gr

    row = row if isinstance(row, dict) else {}
    ref = _ref(npc_key, row)
    proj = (state or {}).get("world_projection") or {}
    cands = [
        (proj.get("npc_affiliations") or {}).get(ref),
        row.get("faction_id"),
        row.get("faction"),
        (((npc_world.graph_entity(ref) or {}).get("components")) or {}).get("faction"),
        npc_world.leaders().get(ref),
    ]
    for cand in cands:
        fid = str(cand or "")
        if fid and npc_world._is_faction(fid):
            return fid
    for e in gr.resolve_edges(proj, entity_id=ref, edge_type="member_of", include_hidden=True):
        fid = str(e.get("target") or "")
        if e.get("source") == ref and fid and npc_world._is_faction(fid):
            return fid
    return ""


def self_rank(state: dict, ref: str, row: dict, faction_id: str) -> str:
    """Patente derivada (nada é gravado): líder > nome de patente do catálogo no `role` > membro."""
    from services import faction_membership as fm

    if npc_world.leaders().get(ref) == faction_id:
        return "líder"
    role = npc_world._fold((row or {}).get("role"))
    if role:
        for rank in fm.rank_list(faction_id):
            name = str(rank.get("name") or "")
            if name and npc_world._fold(name) in role:
                return name
    return "membro"


def _identity_lines(state: dict, npc_key: str, row: dict) -> list[str]:
    fid = self_faction(state, npc_key, row)
    if not fid:
        return []
    known = _faction_known(state, fid)
    name = _faction_name(state, fid)
    if _defeated(state, fid):
        return [f"Você servia a {name}, que caiu."]
    if _faction_is_secret(fid):
        from services import reputation

        if reputation.npc_tier((row or {}).get("relationship")) == "leal":  # SPEC-314 R15
            return [f"Você serve em segredo a {name}; só admita a quem confia de verdade."]
        if not known:
            return [
                "Você serve em segredo a uma irmandade que não pode ser nomeada; nunca admita isso."
            ]
        return [f"Você serve em segredo a {name}; nunca admita isso a estranhos."]
    rank = self_rank(state, _ref(npc_key, row), row, fid)
    if rank == "líder":
        return [f"Você lidera {name}."]
    if rank == "membro":
        return [f"Você é membro de {name}."]
    return [f"Você serve em {name} como {rank}."]


# --------------------------------------------------------------------------- #
# Agenda e lugar (R9, R10)
# --------------------------------------------------------------------------- #
def _arrived_phrase(since: int, today: int) -> str:
    delta = today - since
    if delta <= 0:
        return "há pouco"
    return "ontem" if delta == 1 else "há dias"


def _return_phrase(ret: int, today: int) -> str:
    return "amanhã" if ret - today <= 1 else "em poucos dias"


def agenda_lines(state: dict, npc_key: str, row: dict) -> list[str]:
    row = row if isinstance(row, dict) else {}
    ref = _ref(npc_key, row)
    comp = npc_world._party_by_id(state).get(ref)
    if comp is not None and comp.get("active"):
        return ["Você viaja com o herói."]
    archetype = _ARCHETYPE_PHRASES.get(npc_world.archetype_for(state, ref), "")
    today = _day(state)
    entry = None
    if npc_world.mode() == "on":
        entry = (((state or {}).get("npc_sim") or {}).get("npcs") or {}).get(ref)
    if isinstance(entry, dict) and entry.get("pos"):
        pos = entry["pos"]
        home = str(entry.get("home") or "")
        home_name = _loc_name(home)
        here = str(pos.get("location_id") or "")
        out: list[str] = []
        if pos.get("refugee_from"):
            lost = _loc_name(str(pos["refugee_from"])) or home_name
            if lost:
                from services import location_states, world_engine

                cause = (
                    location_states.public_label(
                        location_states.location_state(state, str(pos["refugee_from"]))
                    )
                    if world_engine.mode() == "on"
                    else ""
                )
                out.append(f"Você fugiu de {lost}" + (f" por causa de: {cause}." if cause else "."))
        elif here and here == home:
            if home_name:
                out.append(f"Você vive aqui, em {home_name}.")
            if archetype:
                out.append(archetype)
        elif here and home_name:
            line = (
                f"Você está de passagem; mora em {home_name} e chegou "
                f"{_arrived_phrase(int(pos.get('since_day') or today), today)}."
            )
            if pos.get("return_day") is not None:
                line += f" Pretende voltar {_return_phrase(int(pos['return_day']), today)}."
            out.append(line)
        elif home_name:
            out.append(f"Você vive em {home_name}.")
        if str(entry.get("status") or "") == "ferido":
            out.append("Você ainda se recupera de um ferimento.")
        return out
    home_name = _loc_name(str(row.get("home_location_id") or ""))
    out = []
    if home_name:
        out.append(f"Você vive em {home_name}.")
    if archetype and home_name:
        out.append(archetype)
    return out


def place_lines(state: dict) -> list[str]:
    """Só o local ATUAL da cena (percebido por ambos): rótulo público + data de hoje."""
    from services import location_states, world_calendar, world_engine

    world = (state or {}).get("world") or {}
    cur = str(world.get("current_location_id") or "")
    label = ""
    if cur and world_engine.mode() == "on":
        label = location_states.public_label(location_states.location_state(state, cur))
    date = world_calendar.clock_date_label(
        world, ((state or {}).get("world_sim") or {}).get("calendar")
    )
    parts: list[str] = []
    if label:
        parts.append(f"Aqui, agora: {label}.")
    if date:
        parts.append(f"Hoje é {date}.")
    return parts


# --------------------------------------------------------------------------- #
# Relações da fação (R11)
# --------------------------------------------------------------------------- #
def relation_lines(
    state: dict, ref: str, faction_id: str, ledger_id: str | None = None
) -> list[str]:
    if not faction_id or _defeated(state, faction_id):
        return []
    if _faction_is_secret(faction_id) and not _faction_known(state, faction_id):
        return []
    from services import faction_relations as fr
    from services import npc_knowledge, world_director

    sim = (state or {}).get("world_sim") or {}
    bands = sim.get("relation_bands") or {}
    leader = npc_world.leaders().get(ref) == faction_id
    today = _day(state)
    game_id = str((state or {}).get("game_id") or "")
    event_ids = {
        str(e.get("event_id"))
        for e in (state or {}).get("event_log") or []
        if isinstance(e, dict) and e.get("event_id")
    }
    heard: set[str] | None = None
    ranked: list[tuple[int, str, str]] = []
    for key, band in bands.items():
        if band not in ("guerra", "alianca"):
            continue
        a, b = fr.split_key(str(key))
        if faction_id not in (a, b):
            continue
        other = b if a == faction_id else a
        if _defeated(state, other):
            continue
        if _faction_is_secret(other) and not _faction_known(state, other):
            continue
        if not leader:
            eid = world_director.event_id(game_id, "faction_relation_changed", today, a, b)
            if eid in event_ids:
                if heard is None:
                    heard = set().union(
                        *npc_knowledge.known_subject_ids(state, ledger_id or ref).values()
                    )
                if eid not in heard:
                    continue  # mudou hoje: o membro comum ainda não sabe
        ranked.append((0 if band == "guerra" else 1, other, band))
    out: list[str] = []
    for _prio, other, band in sorted(ranked)[:MAX_RELATION_LINES]:
        name = _faction_name(state, other)
        out.append(
            f"Sua fação está em guerra com {name}."
            if band == "guerra"
            else f"Sua fação é aliada de {name}."
        )
    return out


# --------------------------------------------------------------------------- #
# Motivações da semente (R13–R16)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _secret_topics() -> dict[str, str]:
    from services import npc_seed

    path = os.path.join(os.path.dirname(npc_seed.SEED_TABLES_PATH), "npc_secret_topics.json")
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):  # silent-ok: sem arquivo = nenhuma linha de segredo (fail-closed)
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, str) and k != "_doc"}


def _table_label(table: str, ident: str) -> str:
    from services import npc_seed

    for row in npc_seed.load_seed_tables().get(table, []):
        if row.get("id") == ident:
            return str(row.get("label") or "")
    return ""


def motive_lines(row: dict) -> list[str]:
    motives = (row or {}).get("seed_motives")
    if not isinstance(motives, dict):
        return []
    out: list[str] = []
    for key, table, fmt in (
        ("desire_id", "desires", "Você deseja: {}."),
        ("fear_id", "fears", "Você teme: {}."),
        ("contradiction_id", "contradictions", "Sua contradição: {}."),
        ("mannerism_id", "mannerisms", "Seu jeito: {}."),
    ):
        label = _table_label(table, str(motives.get(key) or ""))
        if label:
            out.append(fmt.format(label))
    secret = str(motives.get("secret_id") or "")
    topic = _secret_topics().get(secret) if _table_label("secrets", secret) else None
    if topic:
        out.append(
            f"Há um assunto que você evita: {topic}. "
            "Se o jogador tocar nele, desconverse ou se irrite."
        )
    return out


# --------------------------------------------------------------------------- #
# Montagem e orçamento (R1–R5)
# --------------------------------------------------------------------------- #
def _render(tag: str, lines: list[str]) -> str:
    return f"<{tag}>\n" + "\n".join(lines) + f"\n</{tag}>"


def _fit(tag: str, lines: list[str], cap: int, *, keep_last: int = 0) -> tuple[str, bool]:
    """Corta linhas inteiras do fim para o começo até caber em `cap` (tags incluídas).
    `keep_last` linhas finais (rodapé fixo) só saem junto com o bloco inteiro."""
    lines = [ln for ln in lines if ln]
    body, tail = lines[: len(lines) - keep_last], lines[len(lines) - keep_last :]
    if not body:
        return "", False
    truncated = False
    while body and len(_render(tag, body + tail)) > cap:
        body.pop()
        truncated = True
    return (_render(tag, body + tail) if body else ""), truncated


def _knows_lines(state: dict, knowledge_id: str, exclude: Collection[str]) -> list[str]:
    from services import npc_knowledge

    if npc_knowledge.mode() != "on" or not knowledge_id:
        return []
    block = npc_knowledge.npc_knowledge_block(state, knowledge_id, exclude_ids=exclude)
    if not block:
        return []
    return [ln for ln in block.splitlines()[1:-1] if ln.strip()]


def npc_self_blocks(
    state: dict,
    npc_key: str,
    npc_row: dict,
    *,
    pack_evidence_ids: Collection[str] = (),
    knowledge_id: str | None = None,
) -> NpcSelfBlocks:
    """Nunca levanta: qualquer falha vira blocos vazios + `log_fallback` (R3)."""
    if mode() == "off":
        return NpcSelfBlocks()
    try:
        row = npc_row if isinstance(npc_row, dict) else {}
        ref = _ref(npc_key, row)
        fid = self_faction(state, npc_key, row)
        self_lines = [
            *_identity_lines(state, npc_key, row),
            *agenda_lines(state, npc_key, row),
            *place_lines(state),
            *relation_lines(state, ref, fid, knowledge_id or str(row.get("id") or ref)),
        ]
        motives = motive_lines(row)
        knows = _knows_lines(
            state, knowledge_id or str(row.get("id") or npc_key), pack_evidence_ids
        )
        sobre, t1 = _fit(_TAG_SELF, self_lines, SELF_MAX_CHARS)
        mot_cap = min(MOTIVES_MAX_CHARS, TOTAL_MAX_CHARS - len(sobre) - (1 if sobre else 0))
        mot, t2 = _fit(
            _TAG_MOTIVES,
            [*motives, _MOTIVES_FOOTER] if motives else [],
            mot_cap,
            keep_last=1,
        )
        used = len(sobre) + len(mot) + (1 if sobre and mot else 0)
        sabe_cap = min(KNOWS_MAX_CHARS, TOTAL_MAX_CHARS - used - (1 if used else 0))
        sabe, t3 = _fit(_TAG_KNOWS, knows, sabe_cap)
        blocks = NpcSelfBlocks(sobre_voce=sobre, motivacoes=mot, o_que_sabe=sabe)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("npc", "self_block_failed", exc)
        return NpcSelfBlocks()
    from observability.telemetry import log_event

    sections = [n for n, b in (("self", sobre), ("motives", mot), ("knows", sabe)) if b]
    log_event(
        "npc", "self_block", sections=sections, chars=len(blocks.text()), truncated=t1 or t2 or t3
    )
    return blocks
