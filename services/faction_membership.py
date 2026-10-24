"""SPEC-301 — Fações com patente: entrar, subir, sair, trair (e mover o mundo).

Dono único de ``GameState.faction_membership`` e de ``Faction.influence``. Núcleo puro e
determinístico: nada aqui chama LLM. O LLM só *propõe* a intenção (join/leave/ask_mission);
requisito, patente, mérito, perk, missão e traição são resolvidos em Python e registrados
como eventos ``faction_membership_changed`` (``source="engine"``).

Regra de ouro (VISAO): os rivais só passam a odiar o jogador depois de *saberem* (chegada à
região deles ou notícia via SPEC-215). Mérito, influência e ``rival_awareness`` nunca saem
pela API (``membership_view`` devolve só texto e rótulos).

Contrato com a SPEC-302 (motor de mundo): ela lê ``Faction.influence`` (quadro de membros)
e ``faction_membership``; as regras de R13/R14 ficam aqui.
"""

from __future__ import annotations

import copy
import json
import logging
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("rpg.faction_membership")
_DATA = Path(__file__).resolve().parent.parent / "data"

EVENT_TYPE = "faction_membership_changed"
ACTIONS = ("joined", "promoted", "left", "betrayed", "dissolved", "expelled")
INTENT_ACTIONS = ("join", "leave", "ask_mission")
PERK_TYPES = ("desconto", "intendente", "abrigo", "informacao", "passagem", "intercessao")
MISSION_KINDS = ("apoio", "sabotagem", "rito")
EXIT_POLICIES = ("livre", "desonra", "traicao")
ACCEPTS = ("sim", "condicional", "nao")
# Enum fechado de recusa de entrada (R3). ``exclusiva`` leva sufixo ``:<fid>``.
JOIN_REASONS = (
    "fechada",
    "ja_membro",
    "traidor_recente",
    "limite_membros",
    "exclusiva",
    "raca",
    "classe",
    "origem",
    "reputacao",
    "caminho",
    "procurado",
    "local",
    "rito_pendente",
)
STANDING_LABELS = (
    "recém-chegado",
    "visto com bons olhos",
    "a liderança nota seu trabalho",
    "sob suspeita",
    "expulso",
    "traidor",
    "ex-membro",
    "fação dissolvida",
    "em rito de entrada",
)

MAX_MEMBERSHIPS = 2
REP_STEP = 10  # "passo" de reputação: a largura de uma faixa de faction_tier
MISSION_PROGRESS = {1: 3, 2: 5, 3: 8}
MISSION_INFLUENCE = {1: 2, 2: 3, 3: 4}
PROGRESS_PUSH_CAP = 99  # missão nunca ascende a fação: só o tick de tempo (R13)
SUSPICION_WINDOW_DAYS = 5
COOLDOWN_BETRAY_DAYS = 30
COOLDOWN_HONOR_DAYS = 10
COOLDOWN_EXPELLED_DAYS = 20
HOSTILE_AT = -40  # = world_utils._HOSTIL_AT (limiar hostil da reputação)

ACTIVE_STATUSES = ("ativo", "suspeito")
OPEN_STATUSES = ("ativo", "suspeito", "rito_pendente")
_HISTORY_STATUSES = ("ex_membro", "expulso", "traidor", "dissolvida")

_PERK_TEXT = {
    "desconto": "desconto nos mercadores da fação",
    "intendente": "acesso ao intendente",
    "abrigo": "abrigo no quartel-general",
    "informacao": "informações da liderança",
    "passagem": "passagem livre no território da fação",
    "intercessao": "intercessão junto à lei",
}
_REFUSAL_TEXT = {
    "fechada": "{f} não aceita novos membros.",
    "ja_membro": "Você já pertence a {f}.",
    "traidor_recente": "{f} ainda não esqueceu como você partiu; as portas seguem fechadas por ora.",
    "limite_membros": "Você já carrega vínculos demais para assumir mais um.",
    "exclusiva": "{f} não aceita quem serve a outra bandeira.",
    "raca": "{f} não aceita alguém do seu povo.",
    "classe": "{f} não tem lugar para o seu ofício.",
    "origem": "{f} só abre as portas a quem veio de um certo lugar.",
    "reputacao": "{f} ainda não confia em você o bastante.",
    "caminho": "{f} não tem um caminho aberto para você.",
    "procurado": "Você é procurado demais para ser aceito em {f}.",
    "local": "Não há ninguém de {f} aqui para tratar da sua entrada.",
    "rito_pendente": "O rito de entrada em {f} ainda não foi cumprido.",
    "missoes_cheias": "Você já carrega missões demais para aceitar outra.",
    "nao_membro": "Você não pertence a {f}.",
    "sem_missao": "{f} não tem nada a confiar a você agora.",
    "missao_ativa": "Você já tem uma missão de {f} em andamento.",
}


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _fold(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).strip().casefold()


def _world(state: Mapping) -> dict:
    w = state.get("world") if isinstance(state, Mapping) else None
    return w if isinstance(w, dict) else {}


def _day(state: Mapping) -> int:
    clock = _world(state).get("world_clock") or {}
    return max(1, _int(clock.get("day"), 1))


def _turn(state: Mapping) -> int:
    return _int(_world(state).get("turn_count"))


def _here(state: Mapping) -> str:
    return str(_world(state).get("current_location_id") or "")


def _player(state: Mapping) -> dict:
    p = state.get("player") if isinstance(state, Mapping) else None
    return p if isinstance(p, dict) else {}


@lru_cache(maxsize=1)
def _load_catalog_cached() -> dict[str, dict]:
    try:
        raw = json.loads((_DATA / "faction_membership.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _LOG.warning("catálogo de membership ilegível: %s", type(exc).__name__)
        return {}
    return raw if isinstance(raw, dict) else {}


def load_catalog() -> dict[str, dict]:
    """Catálogo curado (uma entrada por fação de ``data/factions.json``). Só leitura."""
    return _load_catalog_cached()


def _cat(fid: str) -> dict:
    row = load_catalog().get(str(fid))
    return row if isinstance(row, dict) else {}


def _records(state: Mapping) -> dict[str, dict]:
    rows = state.get("faction_membership") if isinstance(state, Mapping) else None
    return rows if isinstance(rows, dict) else {}


def _record(state: Mapping, fid: str) -> dict:
    row = _records(state).get(str(fid))
    return row if isinstance(row, dict) else {}


def active_memberships(state: Mapping) -> dict[str, dict]:
    """fid -> registro, só vínculos vivos (ativo|suspeito)."""
    return {
        fid: rec
        for fid, rec in _records(state).items()
        if isinstance(rec, dict) and rec.get("status") in ACTIVE_STATUSES
    }


def is_member(state: Mapping, fid: str) -> bool:
    return _record(state, fid).get("status") in ACTIVE_STATUSES


def _faction_row(state: Mapping, fid: str) -> dict:
    for f in state.get("factions") or []:
        if isinstance(f, dict) and f.get("id") == fid:
            return f
    return {}


def faction_name(state: Mapping, fid: str) -> str:
    name = _faction_row(state, fid).get("name")
    if name:
        return str(name)
    try:
        import gamedata

        for f in gamedata.seed_factions():
            if f.get("id") == fid:
                return str(f.get("name") or fid)
    except Exception as exc:  # silent-ok: nome é cosmético; cai para o id
        _LOG.debug("faction_name fallback: %s", type(exc).__name__)
    return str(fid)


def _faction_known(state: Mapping, fid: str) -> bool:
    return bool(((state.get("faction_intel") or {}).get(fid) or {}).get("known"))


def _display_name(state: Mapping, fid: str) -> str:
    """Nome só se o jogador conhece a fação (não-onisciência); senão 'a facção'."""
    return faction_name(state, fid) if _faction_known(state, fid) else "a facção"


def rank_list(fid: str) -> list[dict]:
    ranks = _cat(fid).get("ranks")
    return [r for r in ranks if isinstance(r, dict)] if isinstance(ranks, list) else []


def rank_of(fid: str, index: int) -> dict:
    ranks = rank_list(fid)
    if not ranks:
        return {}
    return ranks[max(0, min(len(ranks) - 1, _int(index)))]


def rank_cap_index(state: Mapping, fid: str) -> int:
    """Índice máximo de patente que ESTE jogador pode alcançar (R8)."""
    top = max(0, len(rank_list(fid)) - 1)
    cls = str(_player(state).get("class_name") or "")
    cap = top
    for rule in _cat(fid).get("rank_cap") or []:
        if not isinstance(rule, dict):
            continue
        except_classes = rule.get("classes_except")
        applies = False
        if except_classes is not None:
            applies = cls not in except_classes
        elif rule.get("classes"):
            applies = cls in rule["classes"]
        if applies:
            cap = min(cap, _int(rule.get("max_index"), top))
    return cap


def _event(fid: str, action: str, *, rank_id: str = "", rank_name: str = "", **extra: Any) -> dict:
    payload = {"action": action, "rank_id": rank_id, "rank_name": rank_name, **extra}
    return {
        "type": EVENT_TYPE,
        "actor_id": "player",
        "target_id": fid,
        "detail": f"{action}:{fid}",
        "payload": payload,
        "source": "engine",
    }


def _rep_event(fid: str, applied: dict, reason: str) -> dict:
    return {
        "type": "reputation_changed",
        "actor_id": "player",
        "target_id": fid,
        "payload": {
            "delta": applied["delta"],
            "new_value": applied["reputation"],
            "reason": reason,
            "deed_id": "membership",
        },
        "source": "engine",
    }


# --------------------------------------------------------------------------- #
# Área de trabalho (cópias) — as funções públicas devolvem só o que mudou
# --------------------------------------------------------------------------- #
_WORK_KEYS = ("faction_membership", "factions", "faction_intel", "quests", "player")


def _work(state: Mapping) -> dict[str, Any]:
    return {
        "faction_membership": copy.deepcopy(dict(_records(state))),
        "factions": copy.deepcopy([dict(f) for f in (state.get("factions") or []) if f]),
        "faction_intel": copy.deepcopy(dict(state.get("faction_intel") or {})),
        "quests": copy.deepcopy([dict(q) for q in (state.get("quests") or []) if q]),
        "player": copy.deepcopy(dict(_player(state))),
        "_state": state,
        "_events": [],
        "_notes": [],
    }


def _updates(work: dict, state: Mapping) -> dict:
    out: dict[str, Any] = {}
    for key in _WORK_KEYS:
        before = state.get(key)
        if key in ("faction_membership", "faction_intel"):
            before = dict(before or {})
        elif key == "player":
            before = dict(before or {})
        else:
            before = [dict(x) for x in (before or []) if x]
        if work[key] != before:
            out[key] = work[key]
    return out


def _finish(work: dict, state: Mapping) -> tuple[dict, list[dict], str]:
    return _updates(work, state), list(work["_events"]), " ".join(work["_notes"]).strip()


def _wstate(work: dict) -> dict:
    """Visão de estado sobre a área de trabalho (para reaproveitar os getters)."""
    base = dict(work["_state"])
    for key in _WORK_KEYS:
        base[key] = work[key]
    return base


def _set_record(work: dict, fid: str, **fields: Any) -> dict:
    rec = dict(work["faction_membership"].get(fid) or {"faction_id": fid})
    rec.update(fields)
    work["faction_membership"][fid] = rec
    return rec


def _faction_idx(work: dict, fid: str) -> int:
    for i, f in enumerate(work["factions"]):
        if f.get("id") == fid:
            return i
    return -1


def _shift_reputation(work: dict, fid: str, delta: int, reason: str) -> None:
    """Aplica ``delta`` (assinado) na reputação da fação via API de world_utils."""
    if not delta:
        return
    from world_utils import apply_reputation

    direction = "ajudou" if delta > 0 else "prejudicou"
    new_list, ev = apply_reputation(work["factions"], fid, direction, abs(delta))
    if ev:
        work["factions"] = [dict(f) for f in new_list]
        work["_events"].append(_rep_event(fid, ev, reason))


def _force_reputation_at_most(work: dict, fid: str, ceiling: int) -> None:
    idx = _faction_idx(work, fid)
    if idx < 0:
        return
    cur = _int(work["factions"][idx].get("reputation"))
    if cur > ceiling:
        _shift_reputation(work, fid, ceiling - cur, "prejudicou")


def _abandon_faction_quests(work: dict, fid: str) -> None:
    for q in work["quests"]:
        if q.get("faction_id") == fid and q.get("status") == "active":
            q["status"] = "failed"
            q["resolved_turn"] = _turn(work["_state"])


def _mark_intel_known(work: dict, fid: str) -> None:
    rec = dict(work["faction_intel"].get(fid) or {})
    rec["known"] = True
    rec["knows_goal"] = True
    work["faction_intel"][fid] = rec


# --------------------------------------------------------------------------- #
# Requisitos de entrada (R2/R3/R5)
# --------------------------------------------------------------------------- #
def _is_wanted(state: Mapping, region: str) -> bool:
    """Gancho da SPEC-299 (procurado na região). No-op enquanto ela não existir."""
    return False


def _recruiter_present(state: Mapping, cat: dict) -> bool:
    from services.entity_identity import find_runtime_npc_key

    npcs = state.get("npcs") or {}
    for nid in cat.get("recruiter_npc_ids") or []:
        key = find_runtime_npc_key(npcs, str(nid))
        row = npcs.get(key) if key is not None else None
        if isinstance(row, dict) and row.get("in_scene") and row.get("alive", True) is not False:
            return True
    return False


def _npc_met(state: Mapping, npc_id: str) -> int:
    from services.entity_identity import find_runtime_npc_key

    npcs = state.get("npcs") or {}
    key = find_runtime_npc_key(npcs, str(npc_id))
    row = npcs.get(key) if key is not None else None
    return _int((row or {}).get("interaction_count")) if isinstance(row, dict) else 0


def _path_open(state: Mapping, cond: Mapping) -> bool:
    kind = str(cond.get("kind") or "")
    fid = str(cond.get("faction") or "")
    rec = _record(state, fid)
    if kind == "traidor_de":
        return rec.get("status") == "traidor"
    if kind == "ex_membro_desonra":
        return rec.get("status") in ("ex_membro", "expulso") and _int(rec.get("left_day")) > 0
    if kind == "reputation_at_least":
        return _int(_faction_row(state, fid).get("reputation")) >= _int(cond.get("value"))
    if kind == "npc_met":
        return _npc_met(state, str(cond.get("npc_id") or "")) >= _int(cond.get("min"), 1)
    return False


def _conversion_ok(state: Mapping, cat: dict, other: str) -> bool:
    """Entrar traindo ``other`` (R18): só se a fação aceita conversão dele e o caminho abre."""
    req = cat.get("requirements") or {}
    if other not in (req.get("converts_from") or []):
        return False
    conds = req.get("requires_any") or []
    return any(
        _path_open(state, c)
        for c in conds
        if isinstance(c, Mapping) and c.get("kind") in ("npc_met", "reputation_at_least")
    )


def entry_rite_for(state: Mapping, fid: str) -> dict | None:
    """Rito de entrada aplicável a ESTE jogador (classe/origem), ou ``None``."""
    rite = (_cat(fid).get("requirements") or {}).get("entry_rite")
    if not isinstance(rite, dict):
        return None
    classes = rite.get("classes")
    if classes and str(_player(state).get("class_name") or "") not in classes:
        return None
    exempt = rite.get("exempt_origins") or []
    if exempt and str(_player(state).get("origin_region_id") or "") in exempt:
        return None
    return rite


def can_join(state: Mapping, faction_id: str) -> tuple[bool, str]:
    """Primeiro motivo de recusa (enum fechado) ou ``(True, "")``. R2/R3/R5."""
    fid = str(faction_id or "")
    cat = _cat(fid)
    if cat.get("accepts") not in ("sim", "condicional") or not cat.get("ranks"):
        return False, "fechada"
    row = _faction_row(state, fid)
    if row.get("defeated"):
        return False, "fechada"
    rec = _record(state, fid)
    if rec.get("status") in ACTIVE_STATUSES:
        return False, "ja_membro"
    if _day(state) < _int(rec.get("cooldown_until_day")):
        return False, "traidor_recente"
    others = [
        o for o, r in _records(state).items() if o != fid and r.get("status") in OPEN_STATUSES
    ]
    if len(others) >= MAX_MEMBERSHIPS:
        return False, "limite_membros"
    req = cat.get("requirements") or {}
    for other in others:
        ocat = _cat(other)
        conflict = other in (cat.get("exclusive_with") or []) or fid in (
            ocat.get("exclusive_with") or []
        )
        if not conflict:
            continue
        orec = _record(state, other)
        if ocat.get("secret") and not orec.get("exposed"):
            continue  # espião duplo: o vínculo secreto não pesa na exclusividade
        if _conversion_ok(state, cat, other):
            continue
        return False, f"exclusiva:{other}"
    for banned in req.get("never_member_of") or []:
        if _record(state, banned):
            return False, f"exclusiva:{banned}"
    player = _player(state)
    from services import reputation as rep

    race = rep.player_race_id(player)
    allowed_races = req.get("races_allowed") or []
    if (allowed_races and race not in allowed_races) or race in (req.get("races_denied") or []):
        return False, "raca"
    allowed_classes = req.get("classes_allowed") or []
    if allowed_classes and str(player.get("class_name") or "") not in allowed_classes:
        return False, "classe"
    allowed_origins = req.get("origins_allowed") or []
    if allowed_origins and str(player.get("origin_region_id") or "") not in allowed_origins:
        return False, "origem"
    steps = _int(req.get("min_reputation_steps"))
    need = steps * REP_STEP if steps > 0 else -(REP_STEP - 1)  # 0 passos = "neutro" ou melhor
    if _int(row.get("reputation")) < need:
        return False, "reputacao"
    if req.get("requires_intel") and not _faction_known(state, fid):
        return False, "reputacao"
    any_of = req.get("requires_any") or []
    if any_of and not any(_path_open(state, c) for c in any_of if isinstance(c, Mapping)):
        return False, "caminho"
    region = str(req.get("not_wanted_in_region") or "")
    if region and _is_wanted(state, region):
        return False, "procurado"
    if _here(state) not in (cat.get("hq_location_ids") or []) and not _recruiter_present(
        state, cat
    ):
        return False, "local"
    if rec.get("status") == "rito_pendente":
        return False, "rito_pendente"
    return True, ""


def refusal_note(state: Mapping, fid: str, reason: str) -> str:
    code = reason.split(":", 1)[0]
    tmpl = _REFUSAL_TEXT.get(code, "{f} não aceita você agora.")
    return tmpl.format(f=_display_name(state, fid))


# --------------------------------------------------------------------------- #
# Entrar / rito (R4/R6/R16)
# --------------------------------------------------------------------------- #
def _queue_rival_awareness(work: dict, fid: str, delta: int) -> None:
    rec = dict(work["faction_membership"].get(fid) or {})
    pend = dict(rec.get("rival_awareness") or {})
    for rival in _cat(fid).get("rivals") or []:
        if rival != fid and _faction_idx(work, rival) >= 0:
            pend[rival] = delta
    rec["rival_awareness"] = pend
    work["faction_membership"][fid] = rec


def _finalize_join(work: dict, fid: str, *, rite: dict | None = None) -> None:
    """Registra o vínculo e emite ``joined``. Converte (trai) o vínculo exclusivo, se houver."""
    state = work["_state"]
    cat = _cat(fid)
    day = _day(state)
    prev = _record(state, fid)
    marks = list(prev.get("marks") or [])
    if rite:
        cost = _int(rite.get("gold_cost"))
        if cost:
            gold = _int(work["player"].get("gold"))
            work["player"]["gold"] = max(0, gold - cost)  # R4: custo do rito, piso 0
        if rite.get("wound"):
            from services.conflict_damage import apply_wound

            apply_wound(
                work["player"], str(rite["wound"]), str(rite.get("wound_region") or "corpo")
            )
        if rite.get("mark"):
            marks.append(str(rite["mark"]))
    # conversão: entrar traindo o vínculo exclusivo (R18)
    for other, orec in list(_records(_wstate(work)).items()):
        if (
            other != fid
            and orec.get("status") in ACTIVE_STATUSES
            and other in ((cat.get("requirements") or {}).get("converts_from") or [])
        ):
            _betray(work, other)
    _set_record(
        work,
        fid,
        faction_id=fid,
        status="ativo",
        rank_index=0,
        merit=0,
        joined_day=day,
        left_day=0,
        cooldown_until_day=0,
        offenses=[],
        exposed=False,
        rival_awareness={},
        last_info_day=0,
        rite_quest_id="",
        marks=marks,
    )
    _mark_intel_known(work, fid)
    first = rank_of(fid, 0)
    work["_events"].append(
        _event(fid, "joined", rank_id=first.get("id", ""), rank_name=first.get("name", ""))
    )
    if not cat.get("secret"):
        _queue_rival_awareness(work, fid, -1)
    work["_notes"].append(
        f"[FAÇÃO] Você agora é {first.get('name', 'membro')} de {faction_name(work['_state'], fid)}."
    )


def join(state: Mapping, faction_id: str) -> tuple[dict, list[dict], str]:
    """Entra na fação (ou abre o rito de entrada). Nunca levanta."""
    fid = str(faction_id or "")
    ok, reason = can_join(state, fid)
    if not ok:
        return {}, [], refusal_note(state, fid, reason)
    work = _work(state)
    rite = entry_rite_for(state, fid)
    if rite is None:
        _finalize_join(work, fid)
        return _finish(work, state)
    from services import faction_missions

    quests, quest, note = faction_missions.rite_quest(state, fid)
    if quest is None:
        return {}, [], note or refusal_note(state, fid, "missoes_cheias")
    work["quests"] = quests
    _set_record(
        work,
        fid,
        faction_id=fid,
        status="rito_pendente",
        rank_index=0,
        merit=0,
        left_day=0,
        rite_quest_id=quest["id"],
    )
    work["_notes"].append(
        f"[FAÇÃO] Para entrar em {faction_name(state, fid)}, antes é preciso cumprir um rito: "
        f'"{quest.get("title", "")}".'
    )
    return _finish(work, state)


# --------------------------------------------------------------------------- #
# Sair / trair / expulsar / dissolver (R17/R18/R19)
# --------------------------------------------------------------------------- #
def _betray(work: dict, fid: str) -> None:
    state = work["_state"]
    day = _day(state)
    cat = _cat(fid)
    rec = work["faction_membership"].get(fid) or {}
    _set_record(
        work,
        fid,
        status="traidor",
        left_day=day,
        cooldown_until_day=day + COOLDOWN_BETRAY_DAYS,
        merit=0,
        exposed=bool(cat.get("secret")) or bool(rec.get("exposed")),
    )
    _force_reputation_at_most(work, fid, HOSTILE_AT)
    _abandon_faction_quests(work, fid)
    _queue_rival_awareness(work, fid, +1)
    work["_events"].append(
        _event(
            fid,
            "betrayed",
            rank_id=rank_of(fid, _int(rec.get("rank_index"))).get("id", ""),
            exposed=bool(cat.get("secret")),
        )
    )
    work["_notes"].append(f"[FAÇÃO] Você traiu {faction_name(state, fid)}; eles não esquecerão.")


def leave(state: Mapping, faction_id: str) -> tuple[dict, list[dict], str]:
    fid = str(faction_id or "")
    rec = _record(state, fid)
    if rec.get("status") not in ACTIVE_STATUSES and rec.get("status") != "rito_pendente":
        return {}, [], refusal_note(state, fid, "nao_membro")
    work = _work(state)
    if rec.get("status") == "rito_pendente":
        _abandon_faction_quests(work, fid)
        _set_record(work, fid, status="ex_membro", left_day=_day(state), rite_quest_id="")
        work["_notes"].append(f"[FAÇÃO] Você desiste de entrar em {faction_name(state, fid)}.")
        return _finish(work, state)
    policy = str(_cat(fid).get("exit_policy") or "livre")
    day = _day(state)
    if policy == "traicao":
        _betray(work, fid)
        return _finish(work, state)
    steps = 2 if policy == "desonra" else 1
    _shift_reputation(work, fid, -steps * REP_STEP, "prejudicou")
    _abandon_faction_quests(work, fid)
    cooldown = day + COOLDOWN_HONOR_DAYS if policy == "desonra" else 0
    _set_record(work, fid, status="ex_membro", left_day=day, cooldown_until_day=cooldown, merit=0)
    work["_events"].append(
        _event(fid, "left", rank_id=rank_of(fid, _int(rec.get("rank_index"))).get("id", ""))
    )
    work["_notes"].append(f"[FAÇÃO] Você deixa {faction_name(state, fid)}.")
    return _finish(work, state)


def register_offense(
    state: Mapping, faction_id: str, kind: str = "prejudicou"
) -> tuple[dict, list[dict], str]:
    """Ofensa contra a PRÓPRIA fação (R18): 1ª = suspeito; 2ª na janela = traição."""
    fid = str(faction_id or "")
    rec = _record(state, fid)
    if rec.get("status") not in ACTIVE_STATUSES:
        return {}, [], ""
    work = _work(state)
    _register_offense(work, fid)
    return _finish(work, state)


def _register_offense(work: dict, fid: str) -> None:
    state = work["_state"]
    day = _day(state)
    rec = work["faction_membership"].get(fid) or {}
    offenses = [d for d in (rec.get("offenses") or []) if isinstance(d, int)]
    recent = [d for d in offenses if day - d <= SUSPICION_WINDOW_DAYS]
    if rec.get("status") == "suspeito" and recent:
        _betray(work, fid)
        return
    _set_record(work, fid, status="suspeito", offenses=[day])
    work["_notes"].append(
        "[FAÇÃO] Seus superiores andam calados com você; algo no seu comportamento não passou despercebido."
    )


def check_expulsion(state: Mapping) -> tuple[dict, list[dict], str]:
    """Membro cuja reputação com a fação despencou ao limiar hostil é expulso."""
    work = _work(state)
    changed = False
    for fid, rec in list(active_memberships(state).items()):
        if _int(_faction_row(state, fid).get("reputation")) <= HOSTILE_AT:
            day = _day(state)
            _set_record(
                work,
                fid,
                status="expulso",
                left_day=day,
                cooldown_until_day=day + COOLDOWN_EXPELLED_DAYS,
                merit=0,
            )
            _abandon_faction_quests(work, fid)
            work["_events"].append(
                _event(
                    fid, "expelled", rank_id=rank_of(fid, _int(rec.get("rank_index"))).get("id", "")
                )
            )
            work["_notes"].append(
                f"[FAÇÃO] {faction_name(state, fid)} expulsa você de suas fileiras."
            )
            changed = True
    return _finish(work, state) if changed else ({}, [], "")


def on_faction_defeated(state: Mapping, faction_id: str) -> tuple[dict, list[dict], str]:
    fid = str(faction_id or "")
    rec = _record(state, fid)
    if rec.get("status") not in OPEN_STATUSES:
        return {}, [], ""
    work = _work(state)
    _set_record(work, fid, status="dissolvida", left_day=_day(state), merit=0)
    _abandon_faction_quests(work, fid)
    work["_events"].append(_event(fid, "dissolved"))
    work["_notes"].append(
        f"[FAÇÃO] {faction_name(state, fid)} foi destruída; seu vínculo se desfez com ela."
    )
    return _finish(work, state)


def ascension_member_note(state: Mapping, faction_events: list[dict]) -> str:
    """Linha ``[FAÇÃO]`` para o membro cuja fação acabou de ascender (R19)."""
    lines = []
    for ev in faction_events or []:
        fid = str((ev or {}).get("id") or "")
        if is_member(state, fid):
            lines.append(
                f"[FAÇÃO] {faction_name(state, fid)}, a sua fação, concretizou seu intento — "
                "e você estava lá dentro quando aconteceu."
            )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Missões: mérito, promoção, contra-jogo (R7/R12/R13)
# --------------------------------------------------------------------------- #
def _bump_influence(work: dict, fid: str, delta: int) -> None:
    from world_utils import clamp_influence

    idx = _faction_idx(work, fid)
    if idx < 0 or not delta:
        return
    f = dict(work["factions"][idx])
    f["influence"] = clamp_influence(_int(f.get("influence")) + delta)
    work["factions"][idx] = f


def _push_progress(work: dict, fid: str, delta: int) -> None:
    idx = _faction_idx(work, fid)
    if idx < 0:
        return
    f = dict(work["factions"][idx])
    if f.get("completed") or f.get("defeated"):
        return
    cur = _int(f.get("progress"))
    if delta > 0:
        f["progress"] = cur if cur >= PROGRESS_PUSH_CAP else min(PROGRESS_PUSH_CAP, cur + delta)
    else:
        f["progress"] = max(0, cur + delta)
    work["factions"][idx] = f


def bump_influence(factions: list, faction_id: str, delta: int) -> list:
    """Cópia da lista de fações com a influência de ``faction_id`` somada a ``delta`` (R15)."""
    from world_utils import clamp_influence

    out = []
    for f in factions or []:
        f = dict(f or {})
        if f.get("id") == faction_id:
            f["influence"] = clamp_influence(_int(f.get("influence")) + delta)
        out.append(f)
    return out


def _try_promote(work: dict, fid: str) -> None:
    state = _wstate(work)
    rec = work["faction_membership"].get(fid) or {}
    ranks = rank_list(fid)
    idx = _int(rec.get("rank_index"))
    nxt = idx + 1
    if nxt >= len(ranks) or nxt > rank_cap_index(state, fid):
        return
    target = ranks[nxt]
    level = _int(_player(state).get("level"), 1)
    if _int(rec.get("merit")) >= _int(target.get("merit")) and level >= _int(
        target.get("min_level"), 1
    ):
        _set_record(work, fid, rank_index=nxt)
        work["_events"].append(
            _event(fid, "promoted", rank_id=target.get("id", ""), rank_name=target.get("name", ""))
        )
        work["_notes"].append(
            f"[FAÇÃO] {faction_name(state, fid)} promove você a {target.get('name', '')}."
        )


def on_mission_completed(state: Mapping, quest: Mapping) -> tuple[dict, list[dict], str]:
    """Missão de fação concluída: mérito, promoção, progresso/influência, rito (R7/R12/R13)."""
    fid = str((quest or {}).get("faction_id") or "")
    if not fid or fid not in load_catalog():
        return {}, [], ""
    rec = _record(state, fid)
    kind = str(quest.get("mission_kind") or "apoio")
    tier = max(1, min(3, _int(quest.get("mission_tier"), 1)))
    work = _work(state)
    if kind == "rito":
        if rec.get("status") == "rito_pendente" and rec.get("rite_quest_id") == quest.get("id"):
            ok, _reason = _rite_can_finish(state, fid)
            if ok:
                _finalize_join(work, fid, rite=entry_rite_for(state, fid) or {})
            else:
                _set_record(work, fid, status="ex_membro", left_day=_day(state), rite_quest_id="")
                work["_notes"].append(
                    f"[FAÇÃO] Com o rito cumprido, {faction_name(state, fid)} ainda assim não te aceita."
                )
            return _finish(work, state)
        return {}, [], ""
    if rec.get("status") not in ACTIVE_STATUSES:
        return {}, [], ""
    gain = tier + (1 if kind == "sabotagem" else 0)
    cap = rank_cap_index(_wstate(work), fid)
    cur_idx = _int(rec.get("rank_index"))
    if cur_idx < cap:
        _set_record(work, fid, merit=_int(rec.get("merit")) + gain)
    if kind == "sabotagem":
        target = str(quest.get("target_faction_id") or "")
        _push_progress(work, target, -MISSION_PROGRESS[tier])
        _bump_influence(work, target, -MISSION_INFLUENCE[tier])
        if is_member(_wstate(work), target):
            _register_offense(work, target)
    else:
        _push_progress(work, fid, MISSION_PROGRESS[tier])
        _bump_influence(work, fid, MISSION_INFLUENCE[tier])
        if work["faction_membership"][fid].get("status") == "suspeito":
            _set_record(work, fid, status="ativo", offenses=[])
            work["_notes"].append(
                f"[FAÇÃO] O serviço prestado apaga as suspeitas de {faction_name(state, fid)}."
            )
    if work["faction_membership"][fid].get("status") in ACTIVE_STATUSES:
        _try_promote(work, fid)
    return _finish(work, state)


def _rite_can_finish(state: Mapping, fid: str) -> tuple[bool, str]:
    # Re-checa só o limite e a exclusividade: o resto foi checado ao abrir o rito.
    others = [
        o for o, r in _records(state).items() if o != fid and r.get("status") in OPEN_STATUSES
    ]
    if len(others) >= MAX_MEMBERSHIPS:
        return False, "limite_membros"
    return True, ""


def on_mission_failed(state: Mapping, quest: Mapping) -> dict:
    """Missão de fação falha (origem morta etc.): -1 de mérito, piso 0, sem rebaixar."""
    fid = str((quest or {}).get("faction_id") or "")
    rec = _record(state, fid)
    if not fid or rec.get("status") not in ACTIVE_STATUSES:
        return {}
    records = copy.deepcopy(dict(_records(state)))
    records[fid] = {**rec, "merit": max(0, _int(rec.get("merit")) - 1)}
    return {"faction_membership": records}


# --------------------------------------------------------------------------- #
# Rivais odeiam ao saber (R16)
# --------------------------------------------------------------------------- #
def _heard_by_rival_npc(state: Mapping, fid: str, rival: str) -> bool:
    try:
        from services import npc_knowledge
        from services.reputation import npc_faction_id

        if npc_knowledge.mode() != "on":
            return False
        ids = {
            str(e.get("event_id"))
            for e in state.get("event_log") or []
            if isinstance(e, dict) and e.get("type") == EVENT_TYPE and e.get("target_id") == fid
        }
        if not ids:
            return False
        for key, row in (state.get("npcs") or {}).items():
            if isinstance(row, dict) and npc_faction_id(row) == rival:
                known = npc_knowledge.known_subject_ids(dict(state), str(key))
                if ids & (known["heard"] | known["observed"] | known["believed"]):
                    return True
    except Exception as exc:  # silent-ok: notícia é bônus; falha = rival segue sem saber
        _LOG.debug("heard_by_rival falhou: %s", type(exc).__name__)
    return False


def apply_rival_awareness(
    state: Mapping, location_id: str = "", *, arrived: bool = True
) -> tuple[dict, list[dict], str]:
    """Aplica as pendências cujo rival ficou sabendo (chegada à região dele ou notícia)."""
    pend_any = any(
        isinstance(r, dict) and r.get("rival_awareness") for r in _records(state).values()
    )
    if not pend_any:
        return {}, [], ""
    import gamedata

    loc = gamedata.get_location(location_id) or {}
    region = str(loc.get("region") or "")
    controlled = (_world(state).get("controlled") or {}).get(location_id)
    work = _work(state)
    changed = False
    for fid, rec in list(work["faction_membership"].items()):
        pend = dict((rec or {}).get("rival_awareness") or {})
        for rival, delta in list(pend.items()):
            rrow = _faction_row(_wstate(work), rival)
            aware = _heard_by_rival_npc(state, fid, rival)
            if arrived and (
                (region and region == str(rrow.get("region") or "")) or controlled == rival
            ):
                aware = True
            if not aware:
                continue
            pend.pop(rival, None)
            changed = True
            _shift_reputation(
                work, rival, _int(delta) * REP_STEP, "ajudou" if delta > 0 else "prejudicou"
            )
            if _faction_known(state, rival):
                verb = (
                    "passou a ver você com bons olhos"
                    if delta > 0
                    else "passou a desconfiar de você"
                )
                work["_notes"].append(f"[FAÇÃO] {faction_name(state, rival)} {verb}.")
        if pend != (rec or {}).get("rival_awareness"):
            work["faction_membership"][fid] = {**rec, "rival_awareness": pend}
    return _finish(work, state) if changed else ({}, [], "")


# --------------------------------------------------------------------------- #
# Intenção proposta pelo LLM, validada em Python (R20)
# --------------------------------------------------------------------------- #
def apply_intent(state: Mapping, action: str, faction_id: str) -> tuple[dict, list[dict], str]:
    """-> (updates parciais do GameState, propostas source=engine, nota narrável)."""
    act = str(action or "").strip().lower()
    fid = str(faction_id or "").strip()
    if act not in INTENT_ACTIONS:
        return {}, [], ""
    if fid not in load_catalog() or not _faction_row(state, fid):
        # id fora da lista (LLM alucinou): recusa narrável, estado intacto
        return {}, [], ("[FAÇÃO] Não há ninguém com quem tratar disso." if fid else "")
    if act == "join":
        return join(state, fid)
    if act == "leave":
        return leave(state, fid)
    return _ask_mission(state, fid)


def _ask_mission(state: Mapping, fid: str) -> tuple[dict, list[dict], str]:
    from services import faction_missions

    if not is_member(state, fid):
        return {}, [], refusal_note(state, fid, "nao_membro")
    quests, quest, note = faction_missions.offer_mission(state, fid)
    work = _work(state)
    if quest is not None:
        work["quests"] = quests
    work["_notes"].append(note)
    _grant_information(work, fid)
    return _finish(work, state)


def _grant_information(work: dict, fid: str) -> None:
    """Perk ``informacao``: 1×/dia revela o objetivo de um rival (R9)."""
    state = _wstate(work)
    if not any(p.get("type") == "informacao" for p in perks_for(state, fid)):
        return
    day = _day(state)
    rec = work["faction_membership"].get(fid) or {}
    if _int(rec.get("last_info_day")) >= day:
        return
    from world_utils import apply_faction_reveal

    for rival in _cat(fid).get("rivals") or []:
        intel = work["faction_intel"].get(rival) or {}
        if _faction_idx(work, rival) >= 0 and not intel.get("knows_goal"):
            work["faction_intel"] = apply_faction_reveal(
                work["faction_intel"], work["factions"], rival, "objetivo", _turn(state)
            )
            _set_record(work, fid, last_info_day=day)
            work["_notes"].append(
                f"[FAÇÃO] A liderança lhe confia o que sabe sobre {faction_name(state, rival)}."
            )
            return


# --------------------------------------------------------------------------- #
# Perks, intendente, desconto (R9/R10)
# --------------------------------------------------------------------------- #
def perks_for(state: Mapping, faction_id: str) -> list[dict]:
    """Perks em vigor (acumulados até a patente atual). Suspeito perde intendente/desconto (D7)."""
    rec = _record(state, faction_id)
    if rec.get("status") not in ACTIVE_STATUSES:
        return []
    by_rank = _cat(faction_id).get("perks_by_rank") or {}
    out: list[dict] = []
    for i in range(_int(rec.get("rank_index")) + 1):
        for perk in by_rank.get(str(i)) or []:
            if isinstance(perk, dict) and perk.get("type") in PERK_TYPES:
                out.append(perk)
    if rec.get("status") == "suspeito":
        out = [p for p in out if p.get("type") not in ("intendente", "desconto")]
    return out


def has_perk(
    state: Mapping, perk_type: str, *, location_id: str = "", faction_id: str = ""
) -> bool:
    """Algum vínculo ativo dá ``perk_type``? Com ``location_id``, exige o QG da fação."""
    for fid in active_memberships(state):
        if faction_id and fid != faction_id:
            continue
        if location_id and location_id not in (_cat(fid).get("hq_location_ids") or []):
            continue
        if any(p.get("type") == perk_type for p in perks_for(state, fid)):
            return True
    return False


def passage_factions(state: Mapping) -> frozenset[str]:
    """Fações cujo território o jogador atravessa sem contar como 'dominado por hostil'."""
    return frozenset(
        fid for fid in active_memberships(state) if has_perk(state, "passagem", faction_id=fid)
    )


def discount_mult(state: Mapping, location_id: str) -> float:
    """Menor multiplicador de ``desconto`` nos QGs da(s) fação(ões) do jogador (≤ 1.0)."""
    best = 1.0
    for fid in active_memberships(state):
        if location_id not in (_cat(fid).get("hq_location_ids") or []):
            continue
        for perk in perks_for(state, fid):
            if perk.get("type") == "desconto":
                try:
                    best = min(best, max(0.1, min(1.0, float(perk.get("mult", 1.0)))))
                except (TypeError, ValueError):
                    continue
    return best


QUARTERMASTER_QTY = 5


def quartermaster_items(state: Mapping, location_id: str) -> tuple[str | None, dict[str, int]]:
    """Itens liberados pelo intendente da fação no QG (min_rank <= patente atual)."""
    from gamedata import ARTIFACTS_DB

    for fid, rec in active_memberships(state).items():
        cat = _cat(fid)
        if location_id not in (cat.get("hq_location_ids") or []):
            continue
        if not any(p.get("type") == "intendente" for p in perks_for(state, fid)):
            continue
        rank = _int(rec.get("rank_index"))
        items = {
            iid: QUARTERMASTER_QTY
            for iid, min_rank in (cat.get("quartermaster") or {}).items()
            if iid in ARTIFACTS_DB and _int(min_rank) <= rank
        }
        if items:
            return fid, items
    return None, {}


# --------------------------------------------------------------------------- #
# Visão pública e prompt (R21/R22)
# --------------------------------------------------------------------------- #
def standing_label(state: Mapping, faction_id: str) -> str:
    rec = _record(state, faction_id)
    status = rec.get("status")
    if status == "suspeito":
        return "sob suspeita"
    if status == "expulso":
        return "expulso"
    if status == "traidor":
        return "traidor"
    if status == "ex_membro":
        return "ex-membro"
    if status == "dissolvida":
        return "fação dissolvida"
    if status == "rito_pendente":
        return "em rito de entrada"
    top = max(0, len(rank_list(faction_id)) - 1)
    idx = _int(rec.get("rank_index"))
    if idx <= 0:
        return "recém-chegado"
    if idx >= top:
        return "a liderança nota seu trabalho"
    return "visto com bons olhos"


def active_mission_id(state: Mapping, faction_id: str) -> str:
    for q in state.get("quests") or []:
        if (
            isinstance(q, dict)
            and q.get("faction_id") == faction_id
            and q.get("status") == "active"
            and q.get("mission_kind") != "rito"
        ):
            return str(q.get("id") or "")
    return ""


def membership_view(state: Mapping, faction_id: str) -> dict | None:
    """Bloco ``membership`` da API: só rótulos e texto (nunca mérito/influência)."""
    rec = _record(state, faction_id)
    if not rec or not _cat(faction_id):
        return None
    status = str(rec.get("status") or "")
    return {
        "status": status,
        "rank_name": str(rank_of(faction_id, _int(rec.get("rank_index"))).get("name") or ""),
        "standing_label": standing_label(state, faction_id),
        "perks": [_PERK_TEXT[p["type"]] for p in perks_for(state, faction_id)],
        "active_mission_id": active_mission_id(state, faction_id),
    }


def is_secret_event(event: Mapping) -> bool:
    """Evento de fação secreta ainda não exposta (não vira notícia nem contexto de NPC)."""
    payload = event.get("payload") or {}
    cat = _cat(str(event.get("target_id") or ""))
    return bool(cat.get("secret")) and not payload.get("exposed")


def event_text(event: Mapping) -> str:
    """Frase determinística do evento para o contexto; vazia p/ fação secreta não exposta."""
    if is_secret_event(event):
        return ""
    return chronicle_text(event, short=True)


def chronicle_text(event: Mapping, *, short: bool = False) -> str:
    """Texto do milestone da crônica (o diário é do próprio jogador: inclui as secretas)."""
    fid = str(event.get("target_id") or "")
    payload = event.get("payload") or {}
    action = str(payload.get("action") or "")
    name = faction_name({}, fid)
    rank = str(payload.get("rank_name") or "")
    if short:
        verbs = {
            "joined": "entrou em",
            "promoted": "foi promovido em",
            "left": "deixou",
            "betrayed": "traiu",
            "dissolved": "perdeu o vínculo, com a destruição de",
            "expelled": "foi expulso de",
        }
        verb = verbs.get(action)
        return f"[turno {event.get('turn', 0)}] O jogador {verb} {name}." if verb else ""
    if action == "joined":
        return f"O herói ingressou em {name}" + (f" como {rank}." if rank else ".")
    if action == "promoted":
        return (
            f"O herói foi promovido a {rank} em {name}."
            if rank
            else f"O herói subiu de posto em {name}."
        )
    if action == "left":
        return f"O herói deixou {name}."
    if action == "betrayed":
        return f"O herói traiu {name}."
    if action == "dissolved":
        return f"{name} foi destruída, e o vínculo do herói com ela se desfez."
    if action == "expelled":
        return f"{name} expulsou o herói de suas fileiras."
    return ""


def prompt_block(state: Mapping) -> str:
    """``<FAÇÃO_DO_JOGADOR>`` — nome, patente, status, missão e perks em texto (sem números)."""
    lines: list[str] = []
    for fid, rec in active_memberships(state).items():
        rank = rank_of(fid, _int(rec.get("rank_index"))).get("name", "")
        status = "suspeito" if rec.get("status") == "suspeito" else "ativo"
        line = f"- {faction_name(state, fid)}: {rank} ({status})"
        mid = active_mission_id(state, fid)
        if mid:
            q = next((x for x in state.get("quests") or [] if x.get("id") == mid), {})
            line += f'. Missão ativa: "{q.get("title", "")}" — {q.get("description", "")}'
        perks = [_PERK_TEXT[p["type"]] for p in perks_for(state, fid)]
        if perks:
            line += f". Benefícios: {', '.join(dict.fromkeys(perks))}"
        lines.append(line)
    if not lines:
        return ""
    return (
        "<FAÇÃO_DO_JOGADOR>\n"
        + "\n".join(lines)
        + "\nUse esses fatos como estão; não invente patente, missão ou benefício, e não cite números.\n"
        "</FAÇÃO_DO_JOGADOR>"
    )
