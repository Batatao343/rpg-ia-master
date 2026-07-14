"""playtest/invariants.py — invariantes de estado pós-turno (Fase 5.2).

As regras IMPLÍCITAS do motor viram funções puras `check_*(state, prev, turn)`
que devolvem `Violation`s. `check_all` roda todas; o harness 5.1 pluga isto no
fim de cada turno (audita a campanha inteira) e `assert_invariants` deixa usar
os mesmos checks em teste avulso.

Um check que crasha NUNCA derruba a auditoria (é engolido) — invariante é rede
de segurança, não fonte de novo crash. Severidade `error` reprova o estado;
`warning` sinaliza sem reprovar (R5 começa em warning — §7 da spec).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Literal, Optional

Severity = Literal["error", "warning"]


@dataclass
class Violation:
    check_id: str
    severity: Severity
    turn: int
    message: str
    details: dict = field(default_factory=dict)


def _V(check_id, severity, turn, message, **details) -> Violation:
    return Violation(check_id=check_id, severity=severity, turn=turn,
                     message=message, details=details)


# --- R1 vitals --------------------------------------------------------------

def check_vitals(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    p = state.get("player", {}) or {}

    def bounds(entity, kind, name):
        for res, cap in (("hp", "max_hp"), ("mana", "max_mana"), ("stamina", "max_stamina")):
            cur = entity.get(res)
            mx = entity.get(cap)
            if cur is None or mx is None:
                continue
            if cur < 0 or cur > mx:
                out.append(_V(f"vitals.{res}_bounds", "error", turn,
                              f"{name}: {res}={cur} fora de [0, {mx}]",
                              entity=name, res=res, value=cur, max=mx, kind=kind))

    bounds(p, "player", p.get("name", "herói"))
    for c in state.get("party", []) or []:
        if isinstance(c, dict) and c.get("active"):
            bounds(c, "companion", c.get("name", "aliado"))
    for e in state.get("enemies", []) or []:
        if isinstance(e, dict) and e.get("status") == "ativo":
            bounds(e, "enemy", e.get("name", "inimigo"))

    if int(p.get("hp", 1) or 0) == 0 and not state.get("game_over"):
        out.append(_V("vitals.dead_no_game_over", "error", turn,
                      "player com hp=0 mas game_over não está setado", hp=0))
    return out


# --- R2 economia ------------------------------------------------------------

def _unique_ids() -> set:
    from gamedata import ARTIFACTS_DB
    return {iid for iid, a in ARTIFACTS_DB.items() if isinstance(a, dict) and a.get("unique")}


def _inv_ids(entity: dict) -> List[dict]:
    return [e for e in (entity.get("inventory") or []) if isinstance(e, dict)]


def check_economy(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    p = state.get("player", {}) or {}

    if int(p.get("gold", 0) or 0) < 0:
        out.append(_V("economy.gold_negative", "error", turn,
                      f"ouro negativo: {p.get('gold')}", gold=p.get("gold")))

    for e in _inv_ids(p):
        if int(e.get("qty", 1) or 0) < 1:
            out.append(_V("economy.qty_invalid", "error", turn,
                          f"item {e.get('id')} com qty {e.get('qty')} < 1",
                          item=e.get("id"), qty=e.get("qty")))

    eq = p.get("equipment") or {}
    equipped = [v for v in eq.values() if v]
    if len(equipped) != len(set(equipped)):
        out.append(_V("economy.equip_dupe", "error", turn,
                      f"mesmo item em mais de um slot: {equipped}", equipped=equipped))

    # Item único: no máximo 1 lugar no mundo (inventários + estoques de mercador).
    uniques = _unique_ids()
    world = state.get("world", {}) or {}
    for uid in uniques:
        places = 0
        for e in _inv_ids(p):
            if e.get("id") == uid:
                places += 1
                if int(e.get("qty", 1) or 1) > 1:
                    places += 1  # unique não empilha
        for c in state.get("party", []) or []:
            if isinstance(c, dict) and any(x.get("id") == uid for x in _inv_ids(c)):
                places += 1
        for stock in (world.get("merchant_stocks") or {}).values():
            if isinstance(stock, dict) and int(stock.get(uid, 0) or 0) > 0:
                places += 1
        if places > 1:
            out.append(_V("economy.unique_dupe", "error", turn,
                          f"item único {uid} existe em {places} lugares", item=uid, places=places))
    return out


# --- R3 entidades -----------------------------------------------------------

def _killed_ids(state: dict) -> set:
    return {ev.get("target_id") for ev in (state.get("event_log") or [])
            if isinstance(ev, dict) and ev.get("type") == "npc_killed" and ev.get("target_id")}


def check_entities(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    killed = _killed_ids(state)
    if not killed:
        return out
    from services.npc_layers import is_in_scene

    for name, data in (state.get("npcs") or {}).items():
        if not isinstance(data, dict):
            continue
        ids = {data.get("id"), data.get("origin_id"), name}
        if ids & killed and is_in_scene(data):
            out.append(_V("entities.dead_npc_in_scene", "error", turn,
                          f"NPC morto '{name}' ainda está em cena", npc=name))

    for c in state.get("party", []) or []:
        if not isinstance(c, dict) or not c.get("active"):
            continue
        ids = {c.get("id"), c.get("origin_id"), c.get("name")}
        if ids & killed:
            out.append(_V("entities.dead_companion_active", "error", turn,
                          f"companion morto '{c.get('name')}' segue ativo na party", npc=c.get("name")))
    return out


# --- R4 mundo ---------------------------------------------------------------

def check_world(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    from gamedata import get_location
    from services.graph_resolver import get_current_controller

    world = state.get("world", {}) or {}
    projection = state.get("world_projection", {}) or {}

    cur = world.get("current_location_id", "")
    if cur and not get_location(cur):
        out.append(_V("world.location_unknown", "error", turn,
                      f"current_location_id '{cur}' não existe no grafo", loc=cur))

    for loc in world.get("visited", []) or []:
        if not get_location(loc):
            out.append(_V("world.visited_unknown", "error", turn,
                          f"local visitado '{loc}' não existe no grafo", loc=loc))

    defeated = {f.get("id") for f in (state.get("factions") or [])
                if isinstance(f, dict) and f.get("defeated")}
    if defeated:
        for loc in world.get("visited", []) or []:
            controller = get_current_controller(loc, projection, include_hidden=True)
            if controller in defeated:
                out.append(_V("world.defeated_controls", "error", turn,
                              f"fação derrotada '{controller}' ainda controla '{loc}'",
                              loc=loc, faction=controller))

    if prev:
        prev_day = ((prev.get("world") or {}).get("world_clock") or {}).get("day")
        cur_day = (world.get("world_clock") or {}).get("day")
        if isinstance(prev_day, int) and isinstance(cur_day, int) and cur_day < prev_day:
            out.append(_V("world.clock_regressed", "error", turn,
                          f"relógio voltou: dia {prev_day} → {cur_day}",
                          prev_day=prev_day, day=cur_day))
    return out


# --- R5 conhecimento --------------------------------------------------------

# Frases-assinatura da VERDADE oculta de cada segredo canônico (não do rumor
# público — 7.3 separou os dois). Curadas a partir dos docs `visibility: hidden`.
_SECRET_SIGNATURES = {
    "pacto_valerius": [
        "pacto com valerius", "pacto com daruun", "consumiu a família",
        "cedeu a família", "em troca de imortalidade",
    ],
    "rede_carmesim": [
        "rede carmesim pode despertar", "despertar dentro de uma geração",
    ],
    "arauto_identidade": [
        "aprendiz élfico que destruiu aethelgard", "fundido com a energia liberada",
        "almas das vítimas das câmaras",
    ],
    "rei_subterraneo": [
        "verme-primordial das raízes do mundo", "medo do verme",
        "rei se aquietou por medo",
    ],
}


def _revealed_corpus(state: dict) -> str:
    """Texto do que JÁ foi revelado (event_log secret_revealed + facts da
    projection) — desarma a assinatura correspondente."""
    parts: List[str] = []
    for ev in state.get("event_log", []) or []:
        if isinstance(ev, dict) and ev.get("type") == "secret_revealed":
            parts.append(str(ev.get("payload", {})))
            parts.append(str(ev.get("target_id", "")))
    facts = (state.get("world_projection", {}) or {}).get("facts", {}) or {}
    for f in facts.values():
        parts.append(str(f))
    return " ".join(parts).lower()


def check_knowledge(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    text = _last_narration(state).lower()
    if not text:
        return out
    revealed = _revealed_corpus(state)
    for secret_id, phrases in _SECRET_SIGNATURES.items():
        for ph in phrases:
            if ph in text and ph not in revealed:
                out.append(_V("knowledge.secret_leak", "warning", turn,
                              f"narração vazou segredo '{secret_id}': “{ph}”",
                              secret=secret_id, phrase=ph))
                break
    return out


def _last_narration(state: dict) -> str:
    for msg in reversed(state.get("messages", []) or []):
        content = getattr(msg, "content", "")
        if content and getattr(msg, "type", "") != "human":
            return str(content)
    return ""


# --- R6 roundtrip (fora do loop por-turno: faz I/O de disco) ----------------

_ROUNDTRIP_FIELDS = ["player", "world", "party", "enemies", "factions",
                     "faction_intel", "bestiary_knowledge", "npcs", "quests",
                     "campaign_plan", "event_log", "world_projection", "game_over"]


def check_roundtrip(state: dict, prev: Optional[dict] = None, turn: int = 0) -> List[Violation]:
    """save → load → compara campos persistidos. NÃO entra em CHECKS (I/O)."""
    import json
    import persistence

    try:
        persistence.save_game_state(state)
        reloaded = persistence.load_game_state(persistence.save_path(state.get("game_id", "")))
    except Exception as e:
        return [_V("save.roundtrip", "error", turn, f"roundtrip falhou: {e!r}")]
    out: List[Violation] = []
    for k in _ROUNDTRIP_FIELDS:
        a = json.dumps(state.get(k), sort_keys=True, default=str, ensure_ascii=False)
        b = json.dumps((reloaded or {}).get(k), sort_keys=True, default=str, ensure_ascii=False)
        if a != b:
            out.append(_V("save.roundtrip", "warning", turn,
                          f"campo '{k}' difere após save→load", field=k))
    return out


# --- orquestração -----------------------------------------------------------

def check_downed(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """spec balanceamento-early-game (R5): O Saque é 1x por campanha e NUNCA em
    zona apex nem contra boss — 2º `player_downed`, ou downed ilegal, é `error`."""
    out: List[Violation] = []
    downs = [ev for ev in (state.get("event_log") or [])
             if isinstance(ev, dict) and ev.get("type") == "player_downed"]
    if len(downs) > 1:
        out.append(_V("downed.repeated", "error", turn,
                      f"player_downed {len(downs)}x na mesma campanha (máx 1)",
                      count=len(downs)))
    from gamedata import get_location
    for ev in downs:
        payload = ev.get("payload", {}) or {}
        loc = get_location(payload.get("location_id", "")) or {}
        if "apex" in (loc.get("tags") or []):
            out.append(_V("downed.in_apex", "error", turn,
                          f"player_downed em zona apex '{payload.get('location_id')}'",
                          loc=payload.get("location_id")))
        if payload.get("boss_present"):
            out.append(_V("downed.vs_boss", "error", turn,
                          "player_downed em luta com boss presente"))
    return out


def check_lifecycle(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """R4 (fix-playtest-achados): save morto é terminal. Se o turno ANTERIOR já
    estava com game_over e mesmo assim o relógio avançou, um morto agiu — o gate
    do grafo (main.py) deveria ter barrado."""
    if not prev or not prev.get("game_over"):
        return []
    prev_turn = (prev.get("world") or {}).get("turn_count")
    cur_turn = (state.get("world") or {}).get("turn_count")
    if isinstance(prev_turn, int) and isinstance(cur_turn, int) and cur_turn > prev_turn:
        return [_V("lifecycle.acts_after_game_over", "error", turn,
                   f"turno processado após game_over (turn {prev_turn} → {cur_turn})",
                   prev_turn=prev_turn, turn_count=cur_turn)]
    return []


Check = Callable[[dict, Optional[dict], int], List[Violation]]

CHECKS: List[Check] = [
    check_vitals, check_economy, check_entities, check_world, check_knowledge,
    check_lifecycle, check_downed,
]


def check_all(state: dict, prev_state: Optional[dict] = None,
              turn: int = 0) -> List[Violation]:
    out: List[Violation] = []
    for fn in CHECKS:
        try:
            out.extend(fn(state, prev_state, turn) or [])
        except Exception:
            # um invariante quebrado não pode derrubar a auditoria da campanha
            continue
    return out


def assert_invariants(state: dict) -> None:
    """Uso em testes: levanta AssertionError legível com TODAS as violações."""
    violations = check_all(state)
    if violations:
        linhas = "\n".join(f"  [{v.severity}] {v.check_id}: {v.message}" for v in violations)
        raise AssertionError(f"{len(violations)} invariante(s) violado(s):\n{linhas}")
