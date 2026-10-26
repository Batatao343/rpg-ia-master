"""SPEC-299 — Lei e crime por região.

Dono ÚNICO de ``law_state``. Núcleo puro e determinístico: sem LLM, sem I/O além do
dado curado (``services.law_codes``). O LLM só *classifica* o crime narrado; aqui o
motor valida, decide testemunhas, relato, notoriedade, confronto e consequência.

Regra de ouro: a lei só sabe o que alguém viu e contou. Tudo é decidido por seed
``sha256`` de ids estáveis (R26). O estado da lei NUNCA vai para a API nem para o
prompt do narrador (R17): o narrador só recebe *sinais* diegéticos e fatos de cena.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
import re
import unicodedata
from typing import Any, TypedDict

from observability.telemetry import log_event as _log_event
from services import law_codes

_LOG = logging.getLogger("rpg.law")

MODES = ("off", "shadow", "on")
MAX_CRIMES = 100
MAX_REPORTS = 100
MAX_SIGNALS = 32
MAX_SERVED = 20
MAX_DELIVERED = 100
MAX_SIGNALS_PER_SCENE = 2
MAX_REJECTIONS = 100

# Limiares de nível por heat [BALANCEAR]
LEVEL_THRESHOLDS = (("cacado", 65), ("procurado", 35), ("suspeito", 10))
LEVELS = ("limpo", "suspeito", "procurado", "cacado")
# Chance base de reconhecimento por nível + k × |fama local| [BALANCEAR]
RECOGNITION_BASE = {"limpo": 0.0, "suspeito": 0.05, "procurado": 0.3, "cacado": 0.6}
RECOGNITION_K = 0.01
FAME_DELTA_INFAMY = 6  # infâmia local por crime relatado [BALANCEAR]
HUNTER_BAND_DIVISOR = 50  # eff_danger = 1 + bounty // 50 [BALANCEAR]

# R6.4: léxico por tipo de crime (texto dobrado: minúsculo, sem acento) [BALANCEAR].
# Formas verbais FECHADAS: "furtivamente", "golpe de sorte" ou "fico encantado" não contam.
_LEXICON: dict[str, re.Pattern[str]] = {
    "furto": re.compile(
        r"\b(?:roub(?:o|ar|ei|amos|ando)|furt(?:o|ar|ei|amos|ando)|surrup(?:io|iar|iei|iamos)|"
        r"afan(?:o|ar|ei|amos)|rapin(?:o|ar|ei|amos)|pungu(?:eio|ear)|"
        r"bat(?:o|er)\s+(?:a\s+)?carteira|pego\s+escondid[oa]|levo\s+sem\s+pagar|"
        r"tomo\s+sem\s+pagar|me\s+aposs(?:o|ar))\b"
    ),
    "agressao": re.compile(
        r"\b(?:soco|socar|socamos|esmurr(?:o|ar|amos)|agrid(?:o|ir)|esfaque(?:io|ar|amos)|"
        r"apunhal(?:o|ar|amos)|golpe(?:io|ar|amos)|dou\s+um\s+golpe\s+(?:n[oa]|em)|"
        r"ataco|atacar|atacamos|ataquei|chuto|chutar|estrangul(?:o|ar)|"
        r"dou\s+um\s+(?:tapa|soco|chute|cabecada)|firo|ferir|espanc(?:o|ar)|bato\s+n[oa])\b"
    ),
    "homicidio": re.compile(
        r"\b(?:mato|matar|matei|matamos|matando|assassin(?:o|ar|ei)|degol(?:o|ar|ei)|"
        r"esfaque(?:io|ar)|apunhal(?:o|ar)|execut(?:o|ar)\s+(?:o|a)\s+\w+|"
        r"elimin(?:o|ar)\s+(?:o|a)\s+\w+|tiro\s+a\s+vida|estrangul(?:o|ar))\b"
    ),
    "dano_propriedade": re.compile(
        r"\b(?:quebro|quebrar|quebrei|destruo|destruir|incendeio|incendiar|ponho\s+fogo|"
        r"queimo|queimar|arrombo|arrombar|arrombei|vandaliz(?:o|ar)|racho|derrubo|derrubar)\b"
    ),
    "magia_ilegal": re.compile(
        r"\b(?:lanc(?:o|ar)\s+(?:um\s+|uma\s+)?(?:feitico|magia)|conjuro|conjurar|invoco|invocar|"
        r"(?:uso|usar|canalizo|libero)\s+(?:minha\s+|a\s+|o\s+)?(?:magia|eter)|"
        r"bola\s+de\s+fogo|faco\s+um\s+ritual)\b"
    ),
}

_PAY_RE = re.compile(r"\b(?:pag(?:o|ar|amos|ue)|quit(?:o|ar))\b")
_BRIBE_RE = re.compile(r"\b(?:suborn\w*|propina|molh\w+\s+a\s+mao|ofereco\s+(?:algum\s+)?ouro)\b")
_SURRENDER_RE = re.compile(
    r"\b(?:me\s+rendo|rendo-me|rendo|me\s+entrego|entrego-me|aceito\s+(?:a\s+)?prisao|"
    r"cumpro\s+(?:a\s+)?pena|vou\s+preso|me\s+deixo\s+prender)\b"
)
_ATTACK_RE = re.compile(
    r"\b(?:atac\w*|golpe\w*|apunhal\w*|dispar\w*|saco\s+(?:a|minha|o|meu)?\s*"
    r"(?:arma|espada|arco)|enfrent\w*|lut(?:o|ar|amos)|resist\w*|avanco)\b"
)
_WAIT_RE = re.compile(r"\b(?:esper\w*|aguard\w*|cumpr\w*|fico\s+quiet\w*|medito)\b")
_ESCAPE_RE = re.compile(
    r"\b(?:escap\w*|fug\w*|fuj\w*|arromb\w*|serro|cavo|tento\s+sair|forco\s+a\s+(?:cela|grade))\b"
)
_RESCUE_RE = re.compile(r"\b(?:resgat\w*|chamo\s+(?:meus|os)\s+(?:companheiros|aliados)|socorro)\b")
_LICENSE_RE = re.compile(
    r"\b(?:pe[cç]o|pedir|compro|comprar|pago|pagar|solicito|requeiro|faco|fazer|tiro|tirar)\b"
    r"[^.!?]*\b(?:registro|licenca)\b"
)
# Review P1-4: "peço licença para passar" / "faço o registro na estalagem" não são o registro
# de magia — o pedido só vale com magia/Éter na MESMA frase.
_MAGIC_RE = re.compile(r"\b(?:magi\w*|eter|feiti\w*|arcan\w*|conjur\w*|encantament\w*)\b")
_NEGATORS = frozenset({"nao", "jamais", "nunca", "recuso", "recusar", "recusa", "nem", "evito"})
_CLAUSE_END = re.compile(r"[.!?;,:]|\be\b|\bmas\b")


def _affirmed(pattern: re.Pattern[str], folded: str) -> bool:
    """O léxico casa SEM negação na mesma oração ("não me rendo", "jamais me entrego",
    "me recuso a pagar" não escolhem a opção). Ambiguidade = não escolhe."""
    for m in pattern.finditer(folded):
        clause = _CLAUSE_END.split(folded[: m.start()])[-1]
        words = re.findall(r"[a-z]+", clause)[-4:]
        if not any(w in _NEGATORS for w in words):
            return True
    return False


CRIME_CLAIM_HINT = (
    "Se a AÇÃO do jogador neste turno foi um crime aqui (furto, agressao, homicidio, "
    "dano_propriedade, magia_ilegal), registre em 'crime_claims' (victim = nome EXATO de quem "
    "está na cena, 'local' para propriedade; covert=true só se foi às escondidas). Na dúvida, "
    "deixe vazio. NUNCA acuse o jogador do que ele não tentou."
)


def crime_hint_enabled(state: dict) -> bool:
    """A instrução de ``crime_claims`` só entra no prompt onde há lei (zero token fora)."""
    return _active() and law_codes.code_for_location(_here(state)) is not None


class CrimeCandidate(TypedDict, total=False):
    crime_type: str
    victim_ref: str
    covert: bool
    source: str  # "llm_claim" | "engine"
    location_id: str
    turn: int
    player_text: str
    dedupe_key: str


class PrisonerRef(TypedDict, total=False):
    prisoner_id: str
    name: str
    enemy_id: str
    faction_id: str
    alive: bool


class LawReceipt(TypedDict, total=False):
    ok: bool
    reason: str
    gold: int
    jurisdiction_id: str


# --------------------------------------------------------------------------- #
# Primitivos
# --------------------------------------------------------------------------- #
def mode() -> str:
    raw = str(os.getenv("RPG_LAW", "off") or "").strip().lower()
    return raw if raw in MODES else "off"


def _fold(text: Any) -> str:
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _sha(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _unit(*parts: Any) -> float:
    """Valor determinístico em [0, 1) por seed."""
    return int(_sha(*parts)[:12], 16) / float(16**12)


def _rng(*parts: Any) -> random.Random:
    return random.Random(int(_sha(*parts)[:16], 16))


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _world(state: dict) -> dict:
    return state.get("world") or {}


def _here(state: dict) -> str:
    return str(_world(state).get("current_location_id") or "")


def _turn(state: dict) -> int:
    return _int(_world(state).get("turn_count"))


def _gid(state: dict) -> str:
    return str(state.get("game_id") or "game")


def _clock(state: dict) -> int:
    from services import npc_knowledge

    return npc_knowledge.clock_index(_world(state))


def clock_of(state: dict) -> int:
    """Relógio global (``day*5 + período``) do estado."""
    return _clock(state)


def _periods_per_day() -> int:
    from world_utils import PERIODS

    return len(PERIODS)


# --------------------------------------------------------------------------- #
# Estado (R25, R28)
# --------------------------------------------------------------------------- #
def _empty_wanted(jid: str) -> dict:
    return {
        "jurisdiction_id": jid,
        "heat": 0,
        "bounty": 0,
        "capital": False,
        "last_crime_clock": 0,
        "known_at": {},
        "signals_shown": [],
        "hunters_last_clock": -1,
    }


def _norm_wanted(jid: str, raw: Any) -> dict:
    base = _empty_wanted(jid)
    if not isinstance(raw, dict):
        return base
    known = raw.get("known_at")
    base.update(
        heat=max(0, min(100, _int(raw.get("heat")))),
        bounty=max(0, _int(raw.get("bounty"))),
        capital=bool(raw.get("capital")),
        last_crime_clock=_int(raw.get("last_crime_clock")),
        known_at={str(k): _int(v) for k, v in known.items()} if isinstance(known, dict) else {},
        signals_shown=[str(s) for s in (raw.get("signals_shown") or [])][-MAX_SIGNALS:],
        hunters_last_clock=_int(raw.get("hunters_last_clock"), -1),
    )
    return base


def _dict_rows(raw: Any, key: str) -> list[dict]:
    return [
        dict(r)
        for r in (raw if isinstance(raw, list) else [])
        if isinstance(r, dict) and r.get(key)
    ]


def normalize_law(raw: Any) -> dict:
    """R25: ausente/inválido → estado vazio. Aditivo, sem bump de ``SCHEMA_VERSION``."""
    src = raw if isinstance(raw, dict) else {}
    wanted_raw = src.get("wanted") if isinstance(src.get("wanted"), dict) else {}
    conf = src.get("confrontation")
    notice = src.get("notice")
    return {
        "version": 1,
        "crimes": _dict_rows(src.get("crimes"), "crime_id")[-MAX_CRIMES:],
        "reports": _dict_rows(src.get("reports"), "report_id")[-MAX_REPORTS:],
        "wanted": {str(j): _norm_wanted(str(j), w) for j, w in wanted_raw.items()},
        "confrontation": dict(conf)
        if isinstance(conf, dict) and conf.get("jurisdiction_id")
        else None,
        "served": _dict_rows(src.get("served"), "jurisdiction_id")[-MAX_SERVED:],
        "delivered": [str(p) for p in (src.get("delivered") or [])][-MAX_DELIVERED:],
        "licenses": [str(c) for c in (src.get("licenses") or [])],
        "last_loc": str(src.get("last_loc") or ""),
        "notice": dict(notice) if isinstance(notice, dict) and notice.get("text") else None,
    }


def get_law(state: dict) -> dict:
    return normalize_law(state.get("law_state"))


def _active() -> bool:
    return mode() != "off" and law_codes.is_active()


# --------------------------------------------------------------------------- #
# Notoriedade (R14)
# --------------------------------------------------------------------------- #
def effective_heat(w: dict | None, clock: int) -> int:
    """Decaimento PREGUIÇOSO: função pura de ``(heat, last_crime_clock, clock)``."""
    if not w:
        return 0
    heat = max(0, min(100, _int(w.get("heat"))))
    if w.get("capital"):
        return heat
    code = law_codes.get_code(str(w.get("jurisdiction_id") or "")) or {}
    days = max(0, clock - _int(w.get("last_crime_clock"))) // _periods_per_day()
    return max(0, heat - _int(code.get("decay_per_day"), 3) * days)


def level(w: dict | None, clock: int) -> str:
    heat = effective_heat(w, clock)
    for name, floor in LEVEL_THRESHOLDS:
        if heat >= floor:
            return name
    return "limpo"


def _level_rank(name: str) -> int:
    return LEVELS.index(name) if name in LEVELS else 0


def _wanted_here(state: dict, location_id: str) -> tuple[dict | None, dict | None]:
    code = law_codes.code_for_location(location_id)
    if not code:
        return None, None
    return code, get_law(state)["wanted"].get(code["id"])


# --------------------------------------------------------------------------- #
# Fama por local (SPEC-298) — um único adaptador (R15)
# --------------------------------------------------------------------------- #
class _FameBridge:
    """Único ponto que toca ``services.reputation``. Sem a SPEC-298: 0 e não escreve."""

    @staticmethod
    def read(state: dict, location_id: str) -> int:
        try:
            from services import reputation

            fame = reputation.fame_at(state, location_id)
            return max(abs(_int(fame.get("renown"))), abs(_int(fame.get("infamy"))))
        except Exception:  # silent-ok: sem SPEC-298 a fama conta como 0
            return 0

    @staticmethod
    def write(state: dict, location_id: str, subject_id: str, crime_type: str) -> dict | None:
        """Devolve o novo ``location_fame`` (idempotente por crime) ou None."""
        try:
            from services import reputation

            return reputation.add_location_fame(
                state, location_id, f"crime:{crime_type}:{subject_id}", 0, FAME_DELTA_INFAMY
            )
        except Exception:  # silent-ok: sem SPEC-298 não escreve
            return None


_fame_bridge = _FameBridge


# --------------------------------------------------------------------------- #
# Patrulha (R9)
# --------------------------------------------------------------------------- #
def patrol_present(state: dict, location_id: str, clock: int) -> bool:
    code = law_codes.code_for_location(location_id)
    if not code:
        return False
    density = code.get("patrol_density") or {}
    p = float(density.get(location_id, density.get("default", 0.0)) or 0.0)
    day, period = divmod(int(clock), _periods_per_day())
    return _unit(_gid(state), location_id, day, period, "patrol") < p


def _authority_de(code: dict) -> str:
    """ "da Legião de Ferro" / "do Conselho" / "de Fulano": concordância da autoridade."""
    name = _authority_name(code).strip()
    for art, contr in (("As ", "das"), ("Os ", "dos"), ("A ", "da"), ("O ", "do")):
        if name.startswith(art):
            return f"{contr} {name[len(art) :]}"
    return f"de {name}"


def _authority_name(code: dict) -> str:
    from services import graph_resolver as gr

    ent = gr.get_entity(str(code.get("authority_faction_id") or "")) or {}
    return str(ent.get("name") or code.get("name") or "A lei")


# --------------------------------------------------------------------------- #
# Testemunhas (R8) e furtividade (R10)
# --------------------------------------------------------------------------- #
def _party_holders(state: dict) -> set[str]:
    from services import npc_knowledge as nk

    out: set[str] = set()
    for member in state.get("party") or []:
        if isinstance(member, dict) and member.get("active") and member.get("name"):
            out.add(nk.holder_id(state, str(member["name"])))
    return out


def _npc_row_by_holder(state: dict, hid: str) -> dict | None:
    from services import npc_knowledge as nk

    for key, row in (state.get("npcs") or {}).items():
        if isinstance(row, dict) and nk.holder_id(state, str(key)) == hid:
            return row
    return None


def _scene_holders(state: dict) -> dict[str, str]:
    """``holder_id -> nome`` dos NPCs em cena (sem a party)."""
    from services import npc_knowledge as nk
    from services import npc_layers

    party = _party_holders(state)
    npcs = state.get("npcs") or {}
    out: dict[str, str] = {}
    for name in npc_layers.npcs_in_scene(state):
        row = npcs.get(name)
        if not isinstance(row, dict) or not npc_layers.npc_alive(row):
            continue
        hid = nk.holder_id(state, name)
        if hid and hid not in party:
            out.setdefault(hid, name)
    return out


def _victim_faction(state: dict, victim_ref: str) -> str:
    if not victim_ref.startswith("npc:"):
        return ""
    row = _npc_row_by_holder(state, victim_ref)
    if not row:
        return ""
    try:
        from services import reputation

        return reputation.npc_faction_id(row)
    except Exception:  # silent-ok: sem fação conhecida não há multiplicador
        return ""


def _perceives(state: dict, code: dict, crime_id: str, witness: str, crime_type: str) -> bool:
    """R10: 2d10 + mod ≥ DC (determinístico). A patrulha percebe sempre."""
    from services.conflict_resolution import roll_kept, virtude_value

    dcs = code.get("dc_furtividade") or {}
    dc = _int(dcs.get(crime_type), 13) + virtude_value(state.get("player") or {}, "agilidade")
    row = _npc_row_by_holder(state, witness) or {}
    mod = virtude_value(row, "mente") if row else 0
    kept = roll_kept(0, _rng(_gid(state), crime_id, witness, "stealth"))["kept"]
    return sum(kept) + mod >= dc


# --------------------------------------------------------------------------- #
# Registro de crime (R4–R7)
# --------------------------------------------------------------------------- #
def supports(crime_type: str, player_text: str) -> bool:
    """R6.4: a AÇÃO do jogador tem suporte lexical para o tipo?"""
    pat = _LEXICON.get(crime_type)
    if crime_type == "homicidio":
        from services.death_flow import nonlethal_declared

        if nonlethal_declared(player_text):  # SPEC-325: "sem matar" nao sustenta homicidio
            return False
    return bool(pat and pat.search(_fold(player_text)))


def _crime_id(state: dict, cand: dict) -> str:
    key = cand.get("dedupe_key") or cand.get("turn")
    return _sha(_gid(state), key, cand.get("crime_type"), cand.get("location_id"))[:16]


def register_crime(state: dict, cand: dict) -> tuple[dict, dict | None, str]:
    """Única porta de entrada de crime. Devolve ``(updates, record|None, reason)``.

    ``reason`` é ``"ok"``/``"unwitnessed"``/``"dropped"`` quando há registro, ou o
    motivo da recusa. Nunca levanta; ``off`` não escreve nada.
    """
    if not _active():
        return {}, None, "off"
    ctype = str(cand.get("crime_type") or "")
    loc = str(cand.get("location_id") or _here(state))
    code = law_codes.code_for_location(loc)
    if not code:
        return {}, None, "sem_lei"  # R3
    if ctype not in law_codes.CRIME_TYPES:
        return {}, None, "tipo_invalido"
    row = law_codes.crime_row(code, ctype)
    if not row:
        return {}, None, "tipo_desabilitado"
    llm = cand.get("source") == "llm_claim"
    victim = str(cand.get("victim_ref") or "")
    if llm:
        if ctype not in law_codes.LLM_CRIME_TYPES:
            return {}, None, "tipo_so_do_motor"
        if not supports(ctype, str(cand.get("player_text") or "")):
            return {}, None, "sem_suporte_na_acao"
        if victim.startswith("npc:") and victim not in _scene_holders(state):
            return {}, None, "vitima_fora_de_cena"
        if victim and not victim.startswith("npc:") and victim != "local":
            return {}, None, "vitima_invalida"
    if ctype in ("agressao", "homicidio") and not victim.startswith("npc:"):
        return {}, None, "sem_vitima"
    law = get_law(state)
    jid = code["id"]
    if ctype == "magia_ilegal":
        if jid in law["licenses"]:
            return {}, None, "licenciado"
        if (state.get("combat") or {}).get("active"):
            return {}, None, "em_combate"
    cand = {**cand, "crime_type": ctype, "location_id": loc}
    crime_id = _crime_id(state, cand)
    if any(c.get("crime_id") == crime_id for c in law["crimes"]):
        return {}, None, "duplicado"

    clock = _clock(state)
    covert = bool(cand.get("covert")) and bool(code.get("covert_possible", True))
    colmeia = code.get("witness_mode") == "colmeia"
    civil = [h for h in _scene_holders(state) if not (ctype == "homicidio" and h == victim)]
    if covert and not colmeia:
        civil = [h for h in civil if _perceives(state, code, crime_id, h, ctype)]
    patrol = patrol_present(state, loc, clock)
    witnesses = civil + ([f"patrol:{loc}"] if patrol else [])

    faction = _victim_faction(state, victim)
    mult = float((code.get("victim_multiplier") or {}).get(faction, 1.0) or 1.0)
    record = {
        "crime_id": crime_id,
        "crime_type": ctype,
        "jurisdiction_id": jid,
        "location_id": loc,
        "clock": clock,
        "turn": _int(cand.get("turn"), _turn(state)),
        "victim_ref": victim,
        "victim_faction_id": faction,
        "severity": max(1, int(round(_int(row.get("severity"), 10) * mult))),
        "witnesses": witnesses,
        "covert": covert,
        "source": "llm_claim" if llm else "engine",
        "status": "unwitnessed",
    }
    reports: list[dict] = []
    if witnesses:
        chance = float(code.get("report_chance", 0.7))
        delay = _int(code.get("report_delay_periods"), 1)
        for w in witnesses:
            if w.startswith("patrol:"):
                due = clock
            elif colmeia:
                due = clock
            elif _unit(_gid(state), crime_id, w, "report") < chance:
                due = clock + delay
            else:
                continue
            reports.append(
                {
                    "report_id": _sha(crime_id, w)[:16],
                    "crime_id": crime_id,
                    "jurisdiction_id": jid,
                    "reporter": w,
                    "due_clock": due,
                    "status": "queued",
                }
            )
        record["status"] = "pending_report" if reports else "dropped"
    law["crimes"] = [*law["crimes"], record][-MAX_CRIMES:]
    law["reports"] = [*law["reports"], *reports][-MAX_REPORTS:]
    _log_event(
        "law",
        "crime_registered",
        crime_type=ctype,
        jurisdiction=jid,
        status=record["status"],
        witnesses=len(witnesses),
        reports=len(reports),
    )
    reason = {"unwitnessed": "unwitnessed", "dropped": "dropped"}.get(record["status"], "ok")
    return {"law_state": law}, record, reason


def apply_claims(
    state: dict,
    claims: Any,
    *,
    player_text: str,
    quarantine: bool = False,
    source: str = "llm_claim",
) -> dict:
    """R4(a)/R6/R7: ``CrimeClaim`` do LLM → ``register_crime``. Nunca levanta.

    Devolve updates parciais (``law_state`` e ``event_rejections``). ``claims`` pode
    vir de um ``AIMessage`` (guard de FallbackLLM): não-lista = nenhum crime.
    """
    if not _active() or quarantine or not isinstance(claims, (list, tuple)) or not claims:
        return {}
    work = dict(state)
    out: dict[str, Any] = {}
    rejections: list[dict] = []
    seen: set[str] = set()
    scene = _scene_holders(state)
    by_name = {_fold(n): h for h, n in scene.items()}
    turn = _turn(state)
    for claim in claims:
        ctype = str(_claim_field(claim, "crime_type", "") or "")
        victim_raw = str(_claim_field(claim, "victim", "") or "").strip()
        covert = bool(_claim_field(claim, "covert", False))
        if not ctype:
            continue
        if ctype in seen:  # R6.5: 1 por tipo por turno
            rejections.append(_rejection(turn, ctype, "um_por_tipo"))
            continue
        seen.add(ctype)
        folded = _fold(victim_raw)
        if not folded or folded in ("local", "propriedade"):
            victim_ref = "local" if folded else ""
        elif folded in by_name:
            victim_ref = by_name[folded]
        else:
            victim_ref = "npc:__fora_de_cena__"
        cand = {
            "crime_type": ctype,
            "victim_ref": victim_ref,
            "covert": covert,
            "source": source,
            "location_id": _here(work),
            "turn": turn,
            "player_text": player_text,
        }
        upd, _rec, reason = register_crime(work, cand)
        if upd:
            work = {**work, **upd}
            out.update(upd)
        elif reason not in ("off", "sem_lei"):
            rejections.append(_rejection(turn, ctype, reason))
    if rejections:
        prior = [r for r in (state.get("event_rejections") or []) if isinstance(r, dict)]
        out["event_rejections"] = [*prior, *rejections][-MAX_REJECTIONS:]
        _log_event("law", "claims_rejected", count=len(rejections))
    return out


def _claim_field(claim: Any, name: str, default: Any) -> Any:
    if isinstance(claim, dict):
        return claim.get(name, default)
    return getattr(claim, name, default)


def _rejection(turn: int, ctype: str, reason: str) -> dict:
    return {"turn": turn, "type": "crime_claim", "target_id": ctype, "reason": f"crime:{reason}"}


# --------------------------------------------------------------------------- #
# Detecção do motor (R4b)
# --------------------------------------------------------------------------- #
def _engine_candidates(state: dict) -> list[dict]:
    from services import npc_knowledge as nk
    from services import reputation

    combat = state.get("combat") or {}
    if combat.get("origin") != "player_provoked" or not combat.get("instance_id"):
        return []
    loc = _here(state)
    code = law_codes.code_for_location(loc)
    if not code:
        return []
    target = str((combat.get("encounter") or {}).get("target_ref") or "")
    row = (state.get("npcs") or {}).get(target)
    if not target or not isinstance(row, dict):
        return []
    victim = nk.holder_id(state, target)
    authority = str(code.get("authority_faction_id") or "")
    friendly = reputation.npc_tier(row.get("relationship")) != "hostil"
    if not (friendly or reputation.npc_faction_id(row) == authority):
        return []  # alvo já hostil e fora da autoridade: não é crime
    base = {
        "victim_ref": victim,
        "covert": False,
        "source": "engine",
        "location_id": loc,
        "turn": _turn(state),
        "dedupe_key": str(combat["instance_id"]),
    }
    out = [{**base, "crime_type": "agressao"}]
    turn = _turn(state)
    for ev in (state.get("event_log") or [])[-200:]:
        if (
            isinstance(ev, dict)
            and ev.get("type") == "npc_killed"
            and _int(ev.get("turn")) == turn
            and nk.holder_id(state, str(ev.get("target_id") or "")) == victim
        ):
            # morto: já não pode testemunhar (homicidio exclui a vítima)
            out.append({**base, "crime_type": "homicidio"})
            break
    return out


# --------------------------------------------------------------------------- #
# Entrega de relatos / fim de turno (R11–R13, R19)
# --------------------------------------------------------------------------- #
def _event(etype: str, target_id: str, detail: str, payload: dict) -> dict:
    return {
        "type": etype,
        "actor_id": "player",
        "target_id": target_id,
        "detail": detail,
        "payload": payload,
        "source": "law",
    }


def _loc_name(loc_id: str) -> str:
    import gamedata

    return str((gamedata.get_location(loc_id) or {}).get("name") or loc_id)


def _reporter_alive(state: dict, reporter: str, party: set[str]) -> bool:
    from services import npc_layers

    if reporter.startswith("patrol:"):
        return True
    if reporter in party:  # R12: virou membro da party
        return False
    row = _npc_row_by_holder(state, reporter)
    return bool(row) and npc_layers.npc_alive(row)


def _spread_known_at(w: dict, code: dict, crime_loc: str, due: int) -> None:
    from services import world_distance

    courier = _int(code.get("courier_delay_periods"), 1)
    known = w["known_at"]
    known[crime_loc] = min(known.get(crime_loc, due), due)
    for loc in law_codes.jurisdiction_locations(code["id"]):
        if loc == crime_loc:
            continue
        dist = world_distance.travel_periods(crime_loc, loc)
        if dist is None:
            continue
        arrive = due + dist + courier
        known[loc] = min(known.get(loc, arrive), arrive)


def _open_confrontation(law: dict, jid: str, loc: str, turn: int, reason: str) -> None:
    law["confrontation"] = {
        "jurisdiction_id": jid,
        "location_id": loc,
        "started_turn": turn,
        "talk_turns": 0,
        "reason": reason,
    }


def turn_updates(state: dict) -> dict:
    """Ponto ÚNICO de fim de turno (``turn_finalizer``). ``off`` = ``{}``."""
    m = mode()
    if m == "off" or not law_codes.is_active():
        return {}
    work = dict(state)
    out: dict[str, Any] = {}
    prev = get_law(state)
    for cand in _engine_candidates(work):
        upd, _rec, _why = register_crime(work, cand)
        if upd:
            work = {**work, **upd}
            out.update(upd)

    law = get_law(work)
    clock = _clock(work)
    turn = _turn(work)
    here = _here(work)
    party = _party_holders(work)
    events: list[dict] = []
    by_id = {c["crime_id"]: c for c in law["crimes"]}
    new_patrol: dict | None = None
    fame_update: dict | None = None
    delivered = dropped = 0
    for rep in law["reports"]:
        if rep.get("status") != "queued" or _int(rep.get("due_clock")) > clock:
            continue
        crime = by_id.get(str(rep.get("crime_id")))
        if not crime or crime.get("status") in ("resolved", "dropped"):
            rep["status"] = "dropped"
            dropped += 1
            continue
        reporter = str(rep.get("reporter") or "")
        if not _reporter_alive(work, reporter, party):  # R12
            rep["status"] = "dropped"
            dropped += 1
            continue
        rep["status"] = "delivered"
        delivered += 1
        if crime["status"] == "reported":
            continue
        crime["status"] = "reported"
        jid = crime["jurisdiction_id"]
        code = law_codes.get_code(jid) or {}
        row = (code.get("crimes") or {}).get(crime["crime_type"]) or {}
        w = law["wanted"].get(jid) or _empty_wanted(jid)
        w["heat"] = min(100, effective_heat(w, clock) + _int(crime["severity"]))
        w["last_crime_clock"] = clock
        w["bounty"] = _int(w["bounty"]) + _int(code.get("bounty_per_severity"), 4) * _int(
            crime["severity"]
        )
        w["capital"] = bool(w.get("capital")) or bool(row.get("capital"))
        _spread_known_at(w, code, crime["location_id"], _int(rep.get("due_clock")))
        law["wanted"][jid] = w
        if m == "on":  # shadow só observa: sem fama (narrador/UI) nem evento (SPEC-215)
            loc_fame = _fame_bridge.write(
                {**work, "location_fame": fame_update or work.get("location_fame")},
                crime["location_id"],
                crime["crime_id"],
                crime["crime_type"],
            )
            if loc_fame is not None:
                fame_update = loc_fame
            events.append(
                _event(
                    "crime_witnessed",
                    crime["crime_id"],
                    f"Um crime foi testemunhado em {_loc_name(crime['location_id'])}.",
                    {
                        "crime_id": crime["crime_id"],
                        "crime_type": crime["crime_type"],
                        "jurisdiction_id": jid,
                        "location_id": crime["location_id"],
                    },
                )
            )
        if reporter.startswith("patrol:") and new_patrol is None:
            new_patrol = crime
    in_combat = bool((work.get("combat") or {}).get("active"))
    cur_code = law_codes.code_for_location(here)
    conf = law["confrontation"]
    if conf and conf.get("reason") != "imprisoned":
        if not cur_code or cur_code["id"] != conf.get("jurisdiction_id"):
            law["confrontation"] = conf = None  # R22: sair da jurisdição encerra
    elif conf and here != conf.get("location_id"):
        law["confrontation"] = conf = None  # `imprisoned` não persiste fora da prisão
    if (
        m == "on"
        and not conf
        and not in_combat
        and new_patrol is not None
        and cur_code
        and cur_code["id"] == new_patrol["jurisdiction_id"]
    ):
        _open_confrontation(law, cur_code["id"], here, turn, "patrol_witness")
        conf = law["confrontation"]
    if m == "on" and not conf and not in_combat and law["wanted"] and here != law["last_loc"]:
        law["last_loc"] = here
        if cur_code and recognition_check({**work, "law_state": law}, here, clock):
            _open_confrontation(law, cur_code["id"], here, turn, "recognized")
    law["notice"] = law["notice"] if (law["notice"] or {}).get("turn") == turn else None
    if delivered or dropped or events:
        _log_event(
            "law", "reports", delivered=delivered, dropped=dropped, wanted=len(law["wanted"])
        )
    if law != prev:
        out["law_state"] = law
    if events:
        out["pending_world_events"] = [*(work.get("pending_world_events") or []), *events]
    if fame_update is not None:
        out["location_fame"] = fame_update
    return out


# --------------------------------------------------------------------------- #
# Reconhecimento e sinais (R15–R17)
# --------------------------------------------------------------------------- #
def recognition_check(state: dict, location_id: str, clock: int) -> bool:
    """O rosto procurado (ou famoso) é reconhecido ao entrar? Requer notícia chegada,
    nível ≥ procurado e patrulha na cena. Determinístico por seed."""
    code, w = _wanted_here(state, location_id)
    if not code or not w:
        return False
    lvl = level(w, clock)
    if _level_rank(lvl) < _level_rank("procurado"):
        return False
    if _int(w["known_at"].get(location_id), 1 << 30) > clock:
        return False
    if not patrol_present(state, location_id, clock):
        return False
    chance = RECOGNITION_BASE[lvl] + RECOGNITION_K * _fame_bridge.read(state, location_id)
    return _unit(_gid(state), "recognize", location_id, clock) < min(0.95, chance)


def _bounty_phrase(bounty: int) -> str:
    """D4: faixa vaga, nunca número."""
    if bounty < 100:
        return "uma recompensa modesta"
    if bounty < 300:
        return "uma recompensa gorda"
    return "uma recompensa que faria qualquer um trair a própria mãe"


def _pick(options: tuple[str, ...], *seed: Any) -> str:
    return options[int(_sha(*seed)[:6], 16) % len(options)]


def _signal_candidates(state: dict, law: dict, clock: int, here: str) -> list[tuple[str, str]]:
    """``[(signal_id, texto)]`` em ordem de prioridade. Sinais só existem onde a
    notícia chegou (``known_at[loc] <= clock``)."""
    import gamedata

    code = law_codes.code_for_location(here)
    out: list[tuple[str, str]] = []
    if code:
        w = law["wanted"].get(code["id"])
        if w and _int(w["known_at"].get(here), 1 << 30) <= clock:
            lvl = level(w, clock)
            gid = _gid(state)
            if lvl == "cacado" and "perguntaram_por_voce" not in w["signals_shown"]:
                out.append(
                    (
                        "perguntaram_por_voce",
                        _pick(
                            (
                                "Um mercador comenta, sem olhar para você, que forasteiros armados "
                                "andaram perguntando por alguém com a sua descrição.",
                                "Ouve-se na rua que homens de olhar duro andam perguntando "
                                "por um rosto parecido com o seu.",
                            ),
                            gid,
                            here,
                            "ask",
                        ),
                    )
                )
            tags = gamedata.get_location(here).get("tags") or []
            if _level_rank(lvl) >= _level_rank("procurado") and "cidade" in tags:
                sid = f"cartaz:{here}"
                if sid not in w["signals_shown"]:
                    out.append(
                        (
                            sid,
                            "Um cartaz de procurado, com um rosto que lembra o seu, oferece "
                            f"{_bounty_phrase(_int(w['bounty']))} por quem o entregar.",
                        )
                    )
            if (
                code.get("id") not in law["licenses"]
                and law_codes.crime_row(code, "magia_ilegal")
                and any(
                    c.get("crime_type") == "magia_ilegal"
                    and c.get("jurisdiction_id") == code["id"]
                    and c.get("status") in ("pending_report", "reported")
                    for c in law["crimes"]
                )
                and f"registro:{code['id']}" not in w["signals_shown"]
            ):
                out.append(
                    (
                        f"registro:{code['id']}",
                        "Um escrivão murmura que, sem registro na autoridade, "
                        "Éter à vista de todos dá fogueira por aqui.",
                    )
                )
            day = clock // _periods_per_day()
            if _level_rank(lvl) >= _level_rank("suspeito") and patrol_present(state, here, clock):
                sid = f"olhar:{here}:{day}"
                if sid not in w["signals_shown"]:
                    out.append(
                        (
                            sid,
                            "Os guardas cravam os olhos em você um instante a mais do que deviam.",
                        )
                    )
    return out[:MAX_SIGNALS_PER_SCENE]


def signals_for(state: dict, *, for_npc: str | None = None) -> list[str]:
    """R16: de 0 a 2 frases diegéticas. Puro (não marca como mostrado)."""
    if mode() != "on" or not law_codes.is_active():
        return []
    law, clock, here = get_law(state), _clock(state), _here(state)
    lines = [text for _sid, text in _signal_candidates(state, law, clock, here)]
    if for_npc and len(lines) < MAX_SIGNALS_PER_SCENE:
        warning = _npc_warning(state, law, clock, here, for_npc)
        if warning:
            lines.append(warning)
    return lines[:MAX_SIGNALS_PER_SCENE]


def _npc_warning(state: dict, law: dict, clock: int, here: str, npc_ref: str) -> str:
    from services import npc_knowledge as nk

    code = law_codes.code_for_location(here)
    w = law["wanted"].get(code["id"]) if code else None
    if not w or _level_rank(level(w, clock)) < _level_rank("suspeito"):
        return ""
    if _int(w["known_at"].get(here), 1 << 30) > clock:
        return ""
    row = _npc_row_by_holder(state, nk.holder_id(state, npc_ref)) or (state.get("npcs") or {}).get(
        npc_ref
    )
    if not isinstance(row, dict) or _int(row.get("relationship")) < nk.BELIEF_MIN_RELATIONSHIP:
        return ""
    return (
        "Você tem confiança suficiente com este personagem para ele sussurrar: os guardas "
        "andam de olho em você, e convém sumir da vista deles."
    )


def scene_block(state: dict, *, for_npc: str | None = None) -> tuple[str, dict]:
    """Bloco ``<LEI_NA_CENA>`` do narrador/NPC (R9/R16/R19) + updates (sinais mostrados).

    Só frases de cena: nada de heat, bounty, nível, crimes ou testemunhas (R17).
    Sem nada a dizer devolve ``("", {})`` (zero token).
    """
    if mode() != "on" or not law_codes.is_active():
        return "", {}
    here, clock = _here(state), _clock(state)
    code = law_codes.code_for_location(here)
    if not code:
        return "", {}
    law = get_law(state)
    lines: list[str] = []
    conf = law["confrontation"]
    notice = law["notice"]
    if notice and _int(notice.get("turn"), -1) == _turn(state):
        lines.append(str(notice["text"]))
    if conf and conf.get("reason") == "imprisoned":
        lines.append("Você está preso numa cela; os carcereiros vigiam cada movimento.")
    elif conf:
        lines.append(
            f"Guardas {_authority_de(code)} bloqueiam a saída e exigem que você "
            "responda por seus atos."
        )
    elif patrol_present(state, here, clock):
        lines.append(f"Soldados {_authority_de(code)} patrulham o local à vista de todos.")
    candidates = _signal_candidates(state, law, clock, here)
    updates: dict[str, Any] = {}
    if candidates:
        w = law["wanted"][code["id"]]
        for sid, text in candidates:
            lines.append(text)
            if sid not in w["signals_shown"]:
                w["signals_shown"] = [*w["signals_shown"], sid][-MAX_SIGNALS:]
        updates["law_state"] = law
    if for_npc:
        warning = _npc_warning(state, law, clock, here, for_npc)
        if warning:
            lines.append(warning)
    if not lines:
        return "", {}
    body = "\n".join(f"- {t}" for t in lines)
    return f"<LEI_NA_CENA>\n{body}\n</LEI_NA_CENA>", updates


# --------------------------------------------------------------------------- #
# Caçadores de recompensa (R18)
# --------------------------------------------------------------------------- #
def _nearest_distance(location_id: str, jid: str) -> int | None:
    from services import world_distance

    best: int | None = None
    for loc in law_codes.jurisdiction_locations(jid):
        d = world_distance.travel_periods(location_id, loc)
        if d is not None and (best is None or d < best):
            best = d
    return best


def hunter_encounter(state: dict, location_id: str, clock: int) -> dict | None:
    """Dica ``law_hint`` para ``check_encounter``. A força vem do preço pela cabeça,
    NUNCA de ``player.level``."""
    if mode() != "on" or not law_codes.is_active():
        return None
    law = get_law(state)
    for jid, w in law["wanted"].items():
        code = law_codes.get_code(jid)
        if not code or level(w, clock) != "cacado":
            continue
        dist = _nearest_distance(location_id, jid)
        if dist is None or dist > _int(code.get("hunter_radius_periods"), 4):
            continue
        first = min(w["known_at"].values(), default=1 << 30)
        if clock - first < _int(code.get("hunter_delay_periods"), 5):
            continue
        if "perguntaram_por_voce" not in w["signals_shown"]:
            continue  # telegrafado: o aviso vem antes do caçador
        last = _int(w.get("hunters_last_clock"), -1)
        if last >= 0 and clock - last < _int(code.get("hunter_delay_periods"), 5):
            continue
        if _unit(_gid(state), jid, clock, "hunters") >= float(code.get("hunter_chance", 0.5)):
            continue
        pool = [e for e in code.get("hunter_pool") or []]
        prices = code.get("bounty_by_enemy") or {}
        bounty = _int(w["bounty"])
        allowed = [e for e in pool if _int(prices.get(e), 0) <= bounty]
        if not w["capital"]:
            allowed = [e for e in allowed if _int(prices.get(e), 0) <= 30] or allowed[:1]
        if not allowed:
            continue
        enemy = max(allowed, key=lambda e: _int(prices.get(e), 0))
        eff = max(1, min(5, 1 + bounty // HUNTER_BAND_DIVISOR))
        name = _enemy_name(enemy)
        return {
            "hint": name,
            "flavor": f"{name} e seus comparsas cobram a cabeça que as paredes da lei puseram a prêmio.",
            "reason": "bounty_hunters",
            "enemy_id": enemy,
            "eff_danger": eff,
            "jurisdiction_id": jid,
        }
    return None


def _enemy_name(enemy_id: str) -> str:
    return law_codes.bestiary_name(enemy_id)


def mark_hunters(state: dict, jurisdiction_id: str, clock: int) -> dict:
    law = get_law(state)
    w = law["wanted"].get(jurisdiction_id)
    if not w:
        return {}
    w["hunters_last_clock"] = clock
    _log_event("law", "hunters", jurisdiction=jurisdiction_id)
    return {"law_state": law}


# --------------------------------------------------------------------------- #
# Confronto: gate do router (R19–R22), multa, pena, suborno, fuga
# --------------------------------------------------------------------------- #
def _gold(state: dict) -> int:
    return _int((state.get("player") or {}).get("gold"))


def _unresolved(law: dict, jid: str) -> list[dict]:
    return [c for c in law["crimes"] if c["jurisdiction_id"] == jid and c["status"] == "reported"]


def _clear_wanted(law: dict, jid: str, *, keep_heat: int = 0) -> None:
    w = law["wanted"].get(jid)
    if not w:
        return
    w.update(heat=keep_heat, bounty=0, capital=False)
    if not keep_heat:
        w["known_at"] = {}
        w["signals_shown"] = []
        w["hunters_last_clock"] = -1


def _resolve(law: dict, jid: str, mode_: str, turn: int, crime_ids: list[str]) -> None:
    ids = set(crime_ids)
    for c in law["crimes"]:
        if c["crime_id"] in ids:
            c["status"] = "resolved"
    law["served"] = [
        *law["served"],
        {"jurisdiction_id": jid, "mode": mode_, "turn": turn, "crime_ids": crime_ids},
    ][-MAX_SERVED:]
    law["confrontation"] = None


def _resolved_event(jid: str, mode_: str, crime_ids: list[str]) -> dict:
    return _event(
        "law_resolved",
        jid,
        "A pendência com a lei foi resolvida.",
        {"jurisdiction_id": jid, "mode": mode_, "crime_ids": crime_ids},
    )


def _total_fine(code: dict, crimes: list[dict]) -> int | None:
    total = 0
    for c in crimes:
        row = (code.get("crimes") or {}).get(c["crime_type"]) or {}
        if row.get("capital") or row.get("fine") is None:
            return None
        total += _int(row.get("fine"))
    return total


def resolve_fine(state: dict) -> tuple[dict, bool, str]:
    """R20: ``(updates, ok, reason)``. Ouro debitado pelo caminho da economia."""
    from services.economy import clamp_gold

    law = get_law(state)
    conf = law["confrontation"]
    if not conf:
        return {}, False, "sem_confronto"
    jid = conf["jurisdiction_id"]
    code = law_codes.get_code(jid) or {}
    crimes = _unresolved(law, jid)
    fine = _total_fine(code, crimes)
    if fine is None:
        return {}, False, "capital"
    if _gold(state) < fine:
        return {}, False, "insufficient_gold"
    player = dict(state.get("player") or {})
    player["gold"] = clamp_gold(player, _gold(state) - fine)
    ids = [c["crime_id"] for c in crimes]
    _clear_wanted(law, jid)
    _resolve(law, jid, "fine", _turn(state), ids)
    _log_event("law", "resolved", mode="fine", crimes=len(ids))
    return (
        {
            "law_state": law,
            "player": player,
            "pending_world_events": [
                *(state.get("pending_world_events") or []),
                _resolved_event(jid, "fine", ids),
            ],
        },
        True,
        "ok",
    )


def _exit_location(from_loc: str, jid: str) -> str:
    import gamedata

    conns = [c["id"] for c in gamedata.get_connections(from_loc) if c.get("id")]
    outside = [c for c in conns if (law_codes.code_for_location(c) or {}).get("id") != jid]
    return (outside or conns or [from_loc])[0]


def _move_player(state: dict, dest_id: str, days: int) -> dict:
    import gamedata
    from world_utils import advance_clock, apply_travel

    world = dict(_world(state))
    dest = gamedata.get_location(dest_id)
    if dest and dest_id != _here(state):
        world = apply_travel(world, dest)
    if days > 0:
        advance_clock(world, days * _periods_per_day())
    return world


def _party_wait(state: dict, loc_id: str) -> list[dict]:
    from party import set_waiting

    party = [dict(c) for c in state.get("party") or []]
    for member in list(party):
        if isinstance(member, dict) and member.get("active") and member.get("name"):
            party, _found = set_waiting({**state, "party": party}, str(member["name"]), loc_id)
    return party


def serve_sentence(state: dict) -> dict:
    """R21: pena. Prisão curta é imediata; pena longa (≥ ``prison_phase_days``) deixa o
    jogador PRESO (``confrontation.reason == "imprisoned"``) com saídas: esperar, subornar,
    fugir ou ser resgatado. Sem prisão no código (``multa``/``expulsao``) = expulsão."""
    law = get_law(state)
    conf = law["confrontation"]
    if not conf:
        return {}
    jid = conf["jurisdiction_id"]
    code = law_codes.get_code(jid) or {}
    crimes = _unresolved(law, jid)
    ids = [c["crime_id"] for c in crimes]
    days = min(
        _int(code.get("max_sentence_days"), 60),
        sum(
            _int(((code.get("crimes") or {}).get(c["crime_type"]) or {}).get("sentence_days"))
            for c in crimes
        ),
    )
    prison = code.get("prison_location_id")
    events = [*(state.get("pending_world_events") or [])]
    turn = _turn(state)
    if code.get("punishment") == "multa":
        # Lei branda: render-se = pagar a multa (se puder); sem ouro, expulsão SEM `cacado`.
        upd, ok, _why = resolve_fine(state)
        if ok:
            fine_law = upd["law_state"]
            fine_law["notice"] = {
                "turn": turn,
                "text": "Você se submete à lei local e paga a multa devida.",
            }
            return upd
    if code.get("punishment") == "prisao" and prison:
        world = _move_player(state, str(prison), 0)
        party = _party_wait(state, str(prison))
        clock0 = _clock({**state, "world": world})
        if days >= _int(code.get("prison_phase_days"), 15):
            law["confrontation"] = {
                "jurisdiction_id": jid,
                "location_id": str(prison),
                "started_turn": turn,
                "talk_turns": 0,
                "reason": "imprisoned",
                "release_clock": clock0 + days * _periods_per_day(),
            }
            law["notice"] = {
                "turn": turn,
                "text": "Os guardas arrastam você para uma cela; a pena será longa.",
            }
            return {"law_state": law, "world": world, "party": party}
        world = _move_player({**state, "world": world}, str(prison), days)
        _clear_wanted(law, jid)
        _resolve(law, jid, "sentence", turn, ids)
        events.append(_resolved_event(jid, "sentence", ids))
        law["notice"] = {
            "turn": turn,
            "text": f"Você cumpre {days} dias de pena e é solto, mais pobre de orgulho que de ouro.",
        }
        return {"law_state": law, "world": world, "party": party, "pending_world_events": events}
    # expulsão: movido para fora da jurisdição, ainda "caçado" lá (sem prisão)
    dest = _exit_location(_here(state), jid)
    world = _move_player(state, dest, 0)
    clock = _clock({**state, "world": world})
    _resolve(law, jid, "expulsao", turn, ids)
    w = law["wanted"].get(jid) or _empty_wanted(jid)
    # colmeia: banido e caçado lá fora; lei branda (multa): só `suspeito`, sem caçadores
    heat = 70 if code.get("punishment") == "expulsao" else 30
    w.update(heat=heat, last_crime_clock=clock, bounty=max(_int(w["bounty"]), 1))
    w["known_at"] = {**w["known_at"], dest: clock}
    law["wanted"][jid] = w
    events.append(_resolved_event(jid, "expulsao", ids))
    law["notice"] = {
        "turn": turn,
        "text": f"Você é expulso à força de {_loc_name(_here(state))}, com a ameaça de pior se voltar.",
    }
    return {"law_state": law, "world": world, "pending_world_events": events}


def resolve_bribe(state: dict) -> tuple[dict, bool, str]:
    """D6: suborno como saída mínima [BALANCEAR]. Recusado se o código não aceita ou se
    a vítima era da própria autoridade."""
    from services.economy import clamp_gold

    law = get_law(state)
    conf = law["confrontation"]
    if not conf:
        return {}, False, "sem_confronto"
    jid = conf["jurisdiction_id"]
    code = law_codes.get_code(jid) or {}
    if not code.get("bribe_allowed"):
        return {}, False, "bribe_refused"
    crimes = _unresolved(law, jid)
    authority = str(code.get("authority_faction_id") or "")
    if any(c.get("victim_faction_id") == authority for c in crimes):
        return {}, False, "bribe_refused"
    fine = _total_fine(code, crimes)
    base = fine if fine is not None else _int(code.get("bribe_capital_gold"), 400)
    if fine is None:
        base = sum(
            _int(((code.get("crimes") or {}).get(c["crime_type"]) or {}).get("fine"))
            or _int(code.get("bribe_capital_gold"), 400)
            for c in crimes
        )
    cost = int(math.ceil(base * float(code.get("bribe_multiplier", 2.0))))
    if _gold(state) < cost:
        return {}, False, "insufficient_gold"
    player = dict(state.get("player") or {})
    player["gold"] = clamp_gold(player, _gold(state) - cost)
    ids = [c["crime_id"] for c in crimes]
    w = law["wanted"].get(jid)
    keep = effective_heat(w, _clock(state)) // 2 if w else 0
    _clear_wanted(law, jid, keep_heat=keep)
    if w:
        w["last_crime_clock"] = _clock(state)
    _resolve(law, jid, "bribe", _turn(state), ids)
    return (
        {
            "law_state": law,
            "player": player,
            "pending_world_events": [
                *(state.get("pending_world_events") or []),
                _resolved_event(jid, "bribe", ids),
            ],
        },
        True,
        "ok",
    )


def _escape_prison(state: dict, *, rescued: bool) -> dict:
    """Fuga da cela (rolagem seeded) ou resgate de companheiro que esperava fora."""
    from services.conflict_resolution import roll_kept, virtude_value

    law = get_law(state)
    conf = law["confrontation"] or {}
    jid = conf.get("jurisdiction_id", "")
    code = law_codes.get_code(jid) or {}
    turn = _turn(state)
    if not rescued:
        kept = roll_kept(0, _rng(_gid(state), "escape", turn))["kept"]
        agi = virtude_value(state.get("player") or {}, "agilidade")
        if sum(kept) + agi < _int(code.get("escape_dc"), 16):
            conf["release_clock"] = _int(conf.get("release_clock")) + 2 * _periods_per_day()
            law["confrontation"] = conf
            law["notice"] = {
                "turn": turn,
                "text": "A tentativa de fuga falha; os carcereiros dobram a vigia.",
            }
            return {"law_state": law}
    dest = _exit_location(str(conf.get("location_id") or _here(state)), jid)
    world = _move_player(state, dest, 0)
    law["confrontation"] = None
    law["notice"] = {
        "turn": turn,
        "text": (
            "Seus companheiros abrem a cela e vocês somem na noite."
            if rescued
            else "Você escapa da cela e some na escuridão."
        ),
    }
    upd, rec, _why = register_crime(
        {**state, "law_state": law, "world": world},
        {
            "crime_type": "evasao",
            "victim_ref": "",
            "covert": False,
            "source": "engine",
            "location_id": str(conf.get("location_id") or ""),
            "turn": turn,
            "dedupe_key": f"escape:{turn}",
        },
    )
    if upd:
        law = upd["law_state"]
        law["confrontation"] = None
    out = {"law_state": law, "world": world}
    if rescued:
        out["party"] = [
            {**c, "waiting_at": "", "active": True} if c.get("waiting_at") else c
            for c in (state.get("party") or [])
        ]
    return out


def _guard_row(state: dict, code: dict) -> tuple[str, dict]:
    from services import npc_layers

    name = f"Guarda {_authority_de(code)}"
    loc = _here(state)
    row = {
        "name": name,
        "role": "Guarda da jurisdição",
        "persona": "Autoridade ríspida; cobra explicações e ameaça prender.",
        "location": _loc_name(loc),
        "relationship": 3,
        "memory": [],
        "faction_id": str(code.get("authority_faction_id") or ""),
    }
    existing = (state.get("npcs") or {}).get(name)
    if isinstance(existing, dict):
        row = {**existing, "in_scene": True}
    return name, npc_layers.ensure_npc_fields(row, _gid(state), home_location_id=loc, in_scene=True)


def _combat_payload(state: dict, code: dict, *, reason: str) -> dict:
    from langchain_core.messages import SystemMessage

    enemy = (code.get("guard_pool") or ["enemy_guerreiro_bjorn"])[0]
    name = _enemy_name(enemy)
    return {
        "next": "combat_agent",
        "combat_target": name,
        "combat_encounter_hint": {"enemy_id": enemy, "reason": reason, "hint": name},
        "combat_origin_hint": "law_enforcement",
        "messages": [SystemMessage(content=f"SYSTEM: COMBAT START. TARGET_HINT: {name}")],
    }


def _engine_crime(state: dict, ctype: str, key: str) -> dict:
    upd, _rec, _why = register_crime(
        state,
        {
            "crime_type": ctype,
            "victim_ref": "",
            "covert": False,
            "source": "engine",
            "location_id": _here(state),
            "turn": _turn(state),
            "dedupe_key": key,
        },
    )
    return upd


def _notice(law: dict, state: dict, text: str) -> dict:
    law["notice"] = {"turn": _turn(state), "text": text}
    return law


_TRAVEL_NEG_RE = re.compile(r"\b(?:nao|jamais|nunca)\s+(?:vou|viajo|saio|fujo|irei|sigo)\b")


def _flee_intent(state: dict, text: str, folded: str) -> bool:
    """Fuga explícita ("fujo") ou intenção de viagem a um destino válido, sem negação."""
    from services import chase
    from world_utils import find_travel_destination

    if _affirmed(chase.FLEE_RE, folded):
        return True
    if _TRAVEL_NEG_RE.search(folded):
        return False
    return bool(find_travel_destination(_world(state), text))


def resolve_choice(state: dict, text: str) -> dict:
    """Gate do router (R19). Devolve o payload parcial de rota (``next`` + updates) ou
    ``{}`` se não há confronto. Léxico determinístico; sem LLM."""
    if mode() != "on" or not law_codes.is_active():
        return {}
    law = get_law(state)
    conf = law["confrontation"]
    if not conf:
        return {}
    code = law_codes.get_code(conf["jurisdiction_id"]) or {}
    folded = _fold(text)
    if conf.get("reason") == "imprisoned":
        return _prison_choice(state, law, conf, folded, text)

    story = {"next": "storyteller"}

    def done(upd: dict, text_ok: str) -> dict:
        return {**story, **upd, "law_state": _notice(upd["law_state"], state, text_ok)}

    if _affirmed(_SURRENDER_RE, folded):
        upd = serve_sentence(state)
        return {**story, **upd}
    if _affirmed(_PAY_RE, folded):
        upd, ok, why = resolve_fine(state)
        if ok:
            return done(upd, "Você paga a multa e os guardas dão o assunto por encerrado.")
        msg = (
            "Crime grave: a lei não aceita multa por ele."
            if why == "capital"
            else "Você não tem ouro suficiente para pagar a multa; os guardas não se abalam."
        )
        return {**story, "law_state": _notice(law, state, msg)}
    if _affirmed(_BRIBE_RE, folded):
        upd, ok, why = resolve_bribe(state)
        if ok:
            return done(upd, "O guarda embolsa o ouro sem olhar e vira o rosto.")
        msg = (
            "O guarda recusa a propina com desprezo."
            if why == "bribe_refused"
            else "Você não tem ouro suficiente para convencer o guarda."
        )
        return {**story, "law_state": _notice(law, state, msg)}
    if _affirmed(_ATTACK_RE, folded) and not _flee_intent(state, text, folded):
        upd = _engine_crime(state, "resistencia", f"conf:{conf.get('started_turn')}")
        law2 = upd.get("law_state", law)
        law2["confrontation"] = None
        return {**_combat_payload(state, code, reason="law_confrontation"), "law_state": law2}
    if _flee_intent(state, text, folded):
        upd = _engine_crime(state, "evasao", f"conf:{conf.get('started_turn')}")
        law2 = upd.get("law_state", law)
        law2["confrontation"] = None
        return {**_combat_payload(state, code, reason="law_confrontation"), "law_state": law2}
    if _affirmed(_ATTACK_RE, folded):
        upd = _engine_crime(state, "resistencia", f"conf:{conf.get('started_turn')}")
        law2 = upd.get("law_state", law)
        law2["confrontation"] = None
        return {**_combat_payload(state, code, reason="law_confrontation"), "law_state": law2}
    if _int(conf.get("talk_turns")) >= _int(code.get("max_talk_turns"), 2):
        law["confrontation"] = None
        _notice(law, state, "A paciência dos guardas acaba: eles avançam para prendê-lo.")
        return {**_combat_payload(state, code, reason="law_confrontation"), "law_state": law}
    conf["talk_turns"] = _int(conf.get("talk_turns")) + 1
    name, row = _guard_row(state, code)
    return {
        "next": "npc_actor",
        "active_npc_name": name,
        "npcs": {**(state.get("npcs") or {}), name: row},
        "law_state": law,
    }


def _prison_choice(state: dict, law: dict, conf: dict, folded: str, text: str) -> dict:
    story = {"next": "storyteller"}
    jid = conf["jurisdiction_id"]
    if _affirmed(_BRIBE_RE, folded):
        upd, ok, why = resolve_bribe(state)
        if ok:
            return {
                **story,
                **upd,
                "law_state": _notice(
                    upd["law_state"], state, "O carcereiro destranca a cela e finge não ver."
                ),
            }
        return {
            **story,
            "law_state": _notice(
                law, state, "O carcereiro nega: com esse crime, nem ouro compra a saída."
            ),
        }
    if _affirmed(_RESCUE_RE, folded):
        waiting = [
            c
            for c in (state.get("party") or [])
            if isinstance(c, dict) and c.get("waiting_at") == conf.get("location_id")
        ]
        if waiting:
            return {**story, **_escape_prison(state, rescued=True)}
        return {
            **story,
            "law_state": _notice(
                law, state, "Ninguém virá resgatá-lo: não há companheiros à espera lá fora."
            ),
        }
    # P1-1: preso, intenção de viagem/fuga = tentativa de fuga (rolagem + evasao); nunca
    # uma viagem grátis. O storyteller não reaplica a viagem neste turno (law_gate_consumed).
    if _affirmed(_ESCAPE_RE, folded) or _flee_intent(state, text, folded):
        return {**story, **_escape_prison(state, rescued=False)}
    if _affirmed(_WAIT_RE, folded) or _clock(state) >= _int(conf.get("release_clock")):
        remaining = max(0, _int(conf.get("release_clock")) - _clock(state))
        days = int(math.ceil(remaining / _periods_per_day()))
        crimes = _unresolved(law, jid)
        ids = [c["crime_id"] for c in crimes]
        world = _move_player(state, _here(state), days)
        _clear_wanted(law, jid)
        _resolve(law, jid, "sentence", _turn(state), ids)
        _notice(law, state, f"Você cumpre o restante da pena ({days} dias) e é solto.")
        return {
            **story,
            "law_state": law,
            "world": world,
            "pending_world_events": [
                *(state.get("pending_world_events") or []),
                _resolved_event(jid, "sentence", ids),
            ],
        }
    return {
        **story,
        "law_state": _notice(
            law,
            state,
            "Os dias se arrastam na cela; as saídas são esperar, subornar ou tentar fugir.",
        ),
    }


# --------------------------------------------------------------------------- #
# Licença de magia (D2) e interface de prisioneiros (R23)
# --------------------------------------------------------------------------- #
def buy_license(state: dict) -> tuple[dict, bool, str]:
    """D2: registro/licença que torna o Éter público legal na jurisdição atual. O custo
    é o gancho da SPEC-301 (patente na Legião pode zerá-lo). Não é chamado pelo grafo."""
    from services.economy import clamp_gold

    code = law_codes.code_for_location(_here(state))
    if not code or not law_codes.crime_row(code, "magia_ilegal"):
        return {}, False, "sem_registro"
    law = get_law(state)
    if code["id"] in law["licenses"]:
        return {}, False, "ja_licenciado"
    cost = _int(code.get("license_cost"), 250)
    if _gold(state) < cost:
        return {}, False, "insufficient_gold"
    player = dict(state.get("player") or {})
    player["gold"] = clamp_gold(player, _gold(state) - cost)
    law["licenses"] = [*law["licenses"], code["id"]]
    return {"law_state": law, "player": player}, True, "ok"


def resolve_license_request(state: dict, text: str) -> dict:
    """D2: gesto diegético "peço/compro o registro (licença) do meu Éter" num local com lei
    que o criminaliza. Devolve o payload parcial de rota (router) ou ``{}``."""
    if mode() == "off" or not law_codes.is_active():
        return {}
    folded = _fold(text)
    if not any(
        _MAGIC_RE.search(sentence) and _affirmed(_LICENSE_RE, sentence)
        for sentence in re.split(r"[.!?]", folded)
    ):
        return {}
    code = law_codes.code_for_location(_here(state))
    if not code or not law_codes.crime_row(code, "magia_ilegal"):
        return {}
    upd, ok, why = buy_license(state)
    law = upd.get("law_state") or get_law(state)
    msg = {
        "ok": "Você paga a taxa e o escrivão registra o seu Éter nos livros da autoridade.",
        "ja_licenciado": "O escrivão confere os livros: o seu Éter já está registrado.",
        "insufficient_gold": "O escrivão balança a cabeça: falta ouro para a taxa do registro.",
    }.get(why, "O escrivão não sabe do que você está falando.")
    law["notice"] = {"turn": _turn(state), "text": msg}
    return {"next": "storyteller", **upd, "law_state": law}


def prisoner_bounty(state: dict, prisoner: dict, location_id: str) -> int:
    code = law_codes.code_for_location(location_id)
    if not code:
        return 0
    return max(
        0, _int((code.get("bounty_by_enemy") or {}).get(str(prisoner.get("enemy_id") or "")))
    )


def deliver_prisoner(state: dict, prisoner: dict, location_id: str) -> tuple[dict, dict]:
    """R23: interface para a spec futura de prisioneiros (NENHUM nó do grafo a chama)."""
    from services.economy import clamp_gold

    def receipt(ok: bool, reason: str, gold: int = 0, jid: str = "") -> dict:
        return {"ok": ok, "reason": reason, "gold": gold, "jurisdiction_id": jid}

    code = law_codes.code_for_location(location_id)
    if not code:
        return {}, receipt(False, "sem_lei")
    jid = code["id"]
    pid = str(prisoner.get("prisoner_id") or "")
    if not pid:
        return {}, receipt(False, "prisioneiro_invalido", jid=jid)
    if prisoner.get("alive") is False:
        return {}, receipt(False, "prisioneiro_morto", jid=jid)
    law = get_law(state)
    if pid in law["delivered"]:
        return {}, receipt(False, "ja_entregue", jid=jid)
    gold = prisoner_bounty(state, prisoner, location_id)
    if gold <= 0:
        return {}, receipt(False, "sem_recompensa", jid=jid)
    player = dict(state.get("player") or {})
    player["gold"] = clamp_gold(player, _gold(state) + gold)
    law["delivered"] = [*law["delivered"], pid][-MAX_DELIVERED:]
    return {"law_state": law, "player": player}, receipt(True, "ok", gold, jid)


def daily_tick(state: dict, day: int) -> dict:
    """Gancho da SPEC-302: poda wanted totalmente decaído. O decaimento é preguiçoso."""
    if not _active():
        return {}
    law = get_law(state)
    clock = int(day) * _periods_per_day()
    keep = {
        j: w
        for j, w in law["wanted"].items()
        if effective_heat(w, clock) > 0 or w.get("capital") or w.get("bounty")
    }
    if keep == law["wanted"]:
        return {}
    law["wanted"] = keep
    return {"law_state": law}
