"""
world_utils.py
Mecânica de mundo da Fase 0: relógio, viagem entre locais (fog of war) e descanso.
Tudo determinístico (sem LLM) — funciona igual no modo simulado.
"""
from typing import Optional, Tuple

import gamedata

PERIODS = ["Amanhecer", "Manhã", "Tarde", "Anoitecer", "Noite"]

# Pistas de intenção
_REST_WORDS = ["descans", "dormir", "durmo", "acamp", "repous", "pernoit", "descabel"]
_TRAVEL_CUES = ["vou", "viaj", "ir para", "ir até", "ir a", "sigo para", "sigo até",
                "caminho para", "rumo a", "parto", "vamos para", "seguir para",
                "me dirijo", "atravesso para", "voltar para", "volto para", "viajo"]


def ensure_world(world: dict) -> dict:
    """Backfill dos campos novos (compat com saves antigos). Retorna cópia."""
    world = dict(world or {})
    if not world.get("world_clock"):
        world["world_clock"] = {"day": 1, "period": PERIODS[0]}
    world.setdefault("visited", [])

    if not world.get("current_location_id"):
        loc = gamedata.find_location_by_name(world.get("current_location", ""))
        world["current_location_id"] = loc.get("id") if loc else gamedata.START_LOCATION_ID

    cid = world.get("current_location_id")
    if cid and cid not in world["visited"]:
        world["visited"] = world["visited"] + [cid]

    # Fase 2.5b (R10): alertas de fuga (inimigo fugido pode voltar com reforços)
    world.setdefault("threat_alerts", [])

    # mantém o nome em sincronia, se possível
    loc = gamedata.get_location(cid) if cid else {}
    if loc:
        world.setdefault("current_location", loc["name"])
        world.setdefault("danger_level", loc.get("danger", 1))
    return world


def advance_clock(world: dict, steps: int = 1) -> dict:
    """Avança o relógio em N períodos, virando o dia quando passa da Noite."""
    clock = dict(world.get("world_clock") or {"day": 1, "period": PERIODS[0]})
    idx = PERIODS.index(clock["period"]) if clock.get("period") in PERIODS else 0
    idx += max(0, steps)
    clock["day"] = clock.get("day", 1) + idx // len(PERIODS)
    clock["period"] = PERIODS[idx % len(PERIODS)]
    world["world_clock"] = clock
    world["time_of_day"] = clock["period"]
    return world


def is_rest(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in _REST_WORDS)


def _fold_txt(s: str) -> str:
    """lower + sem acento — 'Pantano' tem que casar 'Pântano' (smoke 2026-07-05)."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def find_travel_destination(world: dict, text: str) -> Optional[dict]:
    """
    Se o texto cita um local CONECTADO ao atual (com ou sem verbo de movimento),
    retorna o nó de destino; senão None. Case/acento-insensitive.
    """
    t = _fold_txt(text)
    cur_id = world.get("current_location_id")
    for dest in gamedata.get_connections(cur_id):
        if _fold_txt(dest["name"]) in t or dest["id"] in t:
            return dest
    return None


def travel_cost(world: dict, dest: dict) -> int:
    """Custo em períodos da conexão atual->dest (spec mapa-sublocais).

    `travel_times` do nó atual decide; fallback simétrico (destino define p/
    o atual); sem entrada = 1. Interior sempre 0 (entrar num prédio/masmorra
    não vira o relógio).
    """
    if dest.get("kind") == "interior":
        return 0
    cur_id = world.get("current_location_id")
    cur = gamedata.get_location(cur_id) or {}
    if cur.get("kind") == "interior" and dest.get("id") == cur.get("parent_id"):
        return 0  # sair do interior para o pai também é grátis
    times = cur.get("travel_times") or {}
    if dest.get("id") in times:
        return max(0, int(times[dest["id"]]))
    times_dest = dest.get("travel_times") or {}
    if cur_id in times_dest:
        return max(0, int(times_dest[cur_id]))
    return 1


def apply_travel(world: dict, dest: dict) -> dict:
    """Move o jogador para um destino: revela, sincroniza nome/perigo, gasta tempo.

    Custo 0 (intra-cidade/interior) NÃO vira relógio nem transiciona clima —
    mecânica da spec mapa-sublocais (R2).
    """
    world = dict(world)
    cost = travel_cost(world, dest)
    world["current_location_id"] = dest["id"]
    world["current_location"] = dest["name"]
    visited = list(world.get("visited", []))
    if dest["id"] not in visited:
        visited.append(dest["id"])
    world["visited"] = visited
    world["danger_level"] = dest.get("danger", world.get("danger_level", 1))
    if cost > 0:
        advance_clock(world, cost)
        # Fase 6.5: período mudou -> clima transiciona; clima bravo encarece a viagem
        advance_weather(world)
        extra = weather_effects(world, dest).get("travel_cost_extra", 0)
        if extra:
            advance_clock(world, extra)
    return world


def apply_rest(player: dict, world: dict) -> Tuple[dict, dict]:
    """Descanso: recupera ~metade dos recursos e avança 2 períodos.
    Fase 6.5: clima com `rest_block` (miasma etc.) NEGA o descanso ao relento —
    o tempo passa (1 período de tentativa), mas nada recupera."""
    world = dict(world)
    blocked = weather_effects(world).get("rest_block", False)
    if blocked:
        advance_clock(world, 1)
        advance_weather(world)
        return dict(player), world
    player = dict(player)
    for res, mx in (("hp", "max_hp"), ("mana", "max_mana"), ("stamina", "max_stamina")):
        if mx in player:
            ceiling = player.get(mx, 0)
            healed = player.get(res, 0) + max(1, ceiling // 2)
            player[res] = min(ceiling, healed)
    advance_clock(world, 2)
    advance_weather(world)
    # Fações avançam no tempo off-screen: o storyteller chama advance_factions(2)
    # após o descanso (2 períodos). world_simulator narrado virá no próximo slice.
    return player, world


# --- Fase 2: fações com objetivos próprios (mundo vivo, determinístico) ---

def ensure_factions(factions) -> list:
    """Backfill/normaliza a lista de fações (compat com saves sem o campo)."""
    if not factions:
        return gamedata.seed_factions()
    out = []
    for f in factions:
        f = dict(f or {})
        f.setdefault("progress", 0)
        f.setdefault("pace", 3)
        f.setdefault("disposition", "neutro")
        f.setdefault("reputation", 0)
        f.setdefault("completed", False)
        out.append(f)
    return out


def advance_factions(factions, periods: int = 1) -> Tuple[list, list]:
    """
    Avança o progresso de cada facção em `pace * periods` (determinístico, sem RNG).
    Marca como concluída ao cruzar 100 e devolve eventos das que ACABARAM de concluir.

    Retorna (novas_factions, eventos) — eventos é lista de dicts
    {id, name, goal, disposition} prontos para virar evento de mundo/narração.
    """
    factions = ensure_factions(factions)
    periods = max(0, int(periods))
    if periods == 0:
        return factions, []

    new_list, events = [], []
    for f in factions:
        f = dict(f)
        if not f.get("completed", False) and not f.get("defeated", False):
            f["progress"] = min(100, f.get("progress", 0) + f.get("pace", 3) * periods)
            if f["progress"] >= 100 and not f.get("completed", False):
                f["completed"] = True
                events.append({
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "goal": f.get("goal", ""),
                    "disposition": f.get("disposition", "neutro"),
                })
        new_list.append(f)
    return new_list, events


# --- Fase 2 / Etapa B: ascensão — concluir objetivo muda o MUNDO (determinístico) ---

def _raise_danger(world: dict, loc_id: str) -> None:
    """Sobe o perigo de um local em +1 (teto 4), via override de runtime."""
    overrides = dict(world.get("danger_overrides") or {})
    base = overrides.get(loc_id)
    if base is None:
        loc = gamedata.get_location(loc_id) or {}
        base = loc.get("danger", 1)
    overrides[loc_id] = min(4, int(base) + 1)
    world["danger_overrides"] = overrides
    if world.get("current_location_id") == loc_id:
        world["danger_level"] = overrides[loc_id]


def resolve_faction_completions(factions, world, events, intel) -> Tuple[list, dict, str]:
    """
    Aplica a ASCENSÃO de cada facção que concluiu o objetivo (`events` vem de `advance_factions`):
    o mundo muda de verdade (domina local, expande região, eleva perigo, invoca entidade, elimina
    rival). Determinístico — efeito autorado em `data/factions.json` (campo `ascension`).

    Não-onisciência: a nota de narração NOMEIA a facção só se o jogador a conhece (intel.known);
    senão descreve apenas a CONSEQUÊNCIA sentida (`perceived`), sem nome.

    Retorna (factions, world, nota).
    """
    factions = ensure_factions(factions)
    world = dict(world or {})
    intel = ensure_faction_intel(intel)
    if not events:
        return factions, world, ""

    by_id = {f.get("id"): f for f in factions}
    notes = []
    for ev in events:
        fid = ev.get("id")
        f = by_id.get(fid)
        if not f:
            continue
        asc = f.get("ascension") or {}
        atype = asc.get("type")
        perceived = asc.get("perceived", "")

        if atype == "expandir_regiao":
            f["region"] = asc.get("region", f.get("region"))
            if asc.get("next_goal"):
                f["goal"] = asc["next_goal"]
            f["progress"] = 0
            f["completed"] = False  # cadeia de escalada: continua evoluindo na nova frente
        elif atype == "dominar_local":
            tgt = asc.get("target")
            if tgt:
                ctrl = dict(world.get("controlled") or {})
                ctrl[tgt] = fid
                world["controlled"] = ctrl
        elif atype == "elevar_perigo":
            if asc.get("target"):
                _raise_danger(world, asc["target"])
        elif atype == "invocar_entidade":
            if asc.get("threat"):
                world["looming_threat"] = asc["threat"]
            if asc.get("target"):
                _raise_danger(world, asc["target"])
        elif atype == "eliminar_faccao":
            tgt = asc.get("target")
            if tgt and tgt in by_id:
                by_id[tgt]["defeated"] = True

        if intel.get(fid, {}).get("known"):
            notes.append(f"[MUNDO MUDA] {f.get('name')} concretizou seu intento: {perceived}")
        elif perceived:
            notes.append(f"[MUNDO MUDA] {perceived}")

    note = ""
    if notes:
        note = ("\n".join(notes) +
                "\nNarre estas consequências como algo que o jogador PERCEBE no mundo; "
                "NÃO revele nomes de facções que ele ainda não conhece.")
    return list(by_id.values()), world, note


# --- Fase 2: conhecimento do jogador sobre fações (não-onisciência) ---
# O jogador só sabe o que aprendeu (via NPC). Camadas: existência → objetivo → progresso (snapshot).

_REVEAL_LEVELS = ("existencia", "objetivo", "progresso")


def ensure_faction_intel(intel) -> dict:
    """Normaliza o mapa de inteligência (faction_id -> conhecimento). Default vazio."""
    if not isinstance(intel, dict):
        return {}
    out = {}
    for fid, rec in intel.items():
        rec = dict(rec or {})
        rec.setdefault("known", False)
        rec.setdefault("knows_goal", False)
        out[fid] = rec
    return out


def apply_faction_reveal(intel, factions, faction_id: str, level: str,
                         turn: int = 0) -> dict:
    """
    Aplica uma revelação de NPC ao conhecimento do jogador (determinístico, em camadas).
    level: 'existencia' | 'objetivo' | 'progresso'. id fora das fações = no-op.
    Retorna NOVO dict de intel.
    """
    intel = ensure_faction_intel(intel)
    lvl = (level or "").strip().lower()
    known_ids = {f.get("id") for f in ensure_factions(factions)}
    if not faction_id or faction_id not in known_ids or lvl not in _REVEAL_LEVELS:
        return intel

    rec = dict(intel.get(faction_id) or {})
    rec["known"] = True
    if lvl in ("objetivo", "progresso"):
        rec["knows_goal"] = True
    if lvl == "progresso":
        cur = next((f for f in ensure_factions(factions) if f.get("id") == faction_id), {})
        rec["progress_seen"] = int(cur.get("progress", 0))
        rec["intel_turn"] = int(turn)
    rec.setdefault("knows_goal", rec.get("knows_goal", False))
    intel = dict(intel)
    intel[faction_id] = rec
    return intel


# --- Fase 2: reputação muda por AÇÃO do jogador (determinístico) ---
# Convenção: a IA só identifica fação + direção; o VALOR do delta é fixo aqui.

REP_STEP = 12                       # delta fixo por ação (Python decide, não o LLM)
REP_MIN, REP_MAX = -100, 100
_ALIADO_AT, _HOSTIL_AT = 40, -40    # limiares de disposição derivada da reputação

_POS_CUES = ("ajud", "ajudo", "ajudou", "alia", "aliar", "favor", "apoi", "salv", "defend", "+")
_NEG_CUES = ("prejud", "trai", "traiu", "sabot", "atac", "rouba", "mata", "destr", "contra", "-")


def _disposition_for(rep: int) -> str:
    if rep >= _ALIADO_AT:
        return "aliado"
    if rep <= _HOSTIL_AT:
        return "hostil"
    return "neutro"


def _direction_sign(direction: str) -> int:
    """+1 para ajuda, -1 para prejuízo, 0 (no-op) se ambíguo/desconhecido."""
    d = (direction or "").strip().lower()
    if any(c in d for c in _POS_CUES):
        return 1
    if any(c in d for c in _NEG_CUES):
        return -1
    return 0


def apply_reputation(factions, faction_id: str, direction: str,
                     step: int = REP_STEP) -> Tuple[list, Optional[dict]]:
    """
    Aplica delta FIXO de reputação a uma fação identificada pelo id.
    direction: 'ajudou' (+) | 'prejudicou' (-). Clampa em [-100, 100] e
    re-deriva a disposition por limiar. id desconhecido ou direção ambígua → no-op.

    Retorna (novas_factions, evento|None). evento =
    {id, name, reputation, disposition, direction, delta} — para narração/crônica.
    """
    factions = ensure_factions(factions)
    sign = _direction_sign(direction)
    if not faction_id or sign == 0:
        return factions, None

    new_list, event = [], None
    for f in factions:
        f = dict(f)
        if f.get("id") == faction_id:
            old = int(f.get("reputation", 0))
            delta = sign * int(step)
            new_rep = max(REP_MIN, min(REP_MAX, old + delta))
            f["reputation"] = new_rep
            f["disposition"] = _disposition_for(new_rep)
            event = {
                "id": f.get("id"), "name": f.get("name"),
                "reputation": new_rep, "disposition": f["disposition"],
                "direction": "ajudou" if sign > 0 else "prejudicou",
                "delta": new_rep - old,
            }
        new_list.append(f)
    return new_list, event


# --- Fase 2 / Encontros: o mundo perigoso/dominado/ameaçado gera combate (determinístico) ---

_ENCOUNTER_COOLDOWN = 2  # turnos mínimos entre encontros automáticos (anti-spam)


def _effective_danger(world: dict, loc_id: str) -> int:
    """Perigo atual do local: override de ascensão (se houver) senão o base do mapa."""
    overrides = world.get("danger_overrides") or {}
    if loc_id in overrides:
        return int(overrides[loc_id])
    loc = gamedata.get_location(loc_id) or {}
    return int(loc.get("danger", world.get("danger_level", 1)))


def _hostile_ruler(world: dict, factions, loc_id: str):
    """Retorna a facção HOSTIL que domina o local atual, ou None."""
    fid = (world.get("controlled") or {}).get(loc_id)
    if not fid:
        return None
    for f in ensure_factions(factions):
        if f.get("id") == fid and f.get("disposition") == "hostil":
            return f
    return None


_ALERT_TTL = 6  # turnos de validade de um alerta de fuga


def register_flee_alert(world: dict, fled_hint: str, faction_id=None, turn: int = 0,
                         enemy_id: str = "") -> dict:
    """
    Fase 2.5b (R10): registra que um inimigo FUGIU do combate — ele pode voltar
    com reforços. O alerta vale para a REGIÃO atual por ~_ALERT_TTL turnos e é
    consumido quando dispara um encontro.

    Fase 3.2 (R3): `enemy_id` (id canônico do bestiário, se resolvido) viaja com o
    alerta para que o encontro de reforços possa registrar rumor determinístico.
    """
    world = dict(world or {})
    loc = gamedata.get_location(world.get("current_location_id", "")) or {}
    # nome-base sem sufixo de instância ("Soldado da Legião 2" -> "Soldado da Legião")
    import re as _re
    hint = _re.sub(r"\s+\d+$", "", str(fled_hint or "o fugitivo")).strip()
    alerts = list(world.get("threat_alerts") or [])
    alerts.append({
        "region_id": loc.get("region_id", world.get("current_location_id", "")),
        "hint": hint,
        "faction_id": faction_id,
        "turn": int(turn),
        "enemy_id": enemy_id or "",
    })
    world["threat_alerts"] = alerts
    return world


def _pop_active_alert(world: dict, loc: dict, turn: int):
    """Alerta válido para a região atual (consome-o e descarta expirados). Muta world."""
    region_id = (loc or {}).get("region_id", world.get("current_location_id", ""))
    fresh, hit = [], None
    for a in world.get("threat_alerts") or []:
        if turn - int(a.get("turn", -99)) > _ALERT_TTL:
            continue  # expirado
        if hit is None and a.get("region_id") == region_id:
            hit = a  # consome o primeiro alerta da região
            continue
        fresh.append(a)
    world["threat_alerts"] = fresh
    return hit


def _bestiary_by_faction(faction_id: str):
    """Combatente de uma facção no bestiário (campo `faction` — Fase 2.5b)."""
    for entry in (gamedata.BESTIARY or {}).values():
        if entry.get("faction") == faction_id:
            return entry
    return None


def pick_encounter_enemy(loc: dict, danger: int, turn: int = 0, faction_id: str = "",
                         *, bestiary_knowledge: dict = None, projection: dict = None,
                         rng=None):
    """
    Fase 2.5b (R11): sorteio DETERMINÍSTICO de criatura concreta do bestiário.
    - facção informada -> combatente daquela facção (se curado);
    - senão, criatura com `regions` contendo a região do local, com porte
      compatível com o perigo (1-2: Minion; 3: Minion/Elite; 4: Elite). BOSS nunca
      sai em encontro aleatório.

    Fase 6.3: com `bestiary_knowledge`/`projection`, o sorteio é PONDERADO —
    pressão de caça rebaixa a criatura farmada, criatura da fação que controla o
    local pesa x2, e fauna local rareada abre vaga p/ 1 migrante de região
    conectada (rotas bloqueadas da 6.1 barram). Sem os dados -> comportamento
    legado (round-robin por turno), retrocompatível.
    Retorna a ENTRADA do bestiário ou None (chamador cai no hint genérico).
    """
    if faction_id:
        entry = _bestiary_by_faction(faction_id)
        if entry:
            return entry

    region_id = (loc or {}).get("region_id", "")
    if not region_id:
        return None
    pool = [e for e in (gamedata.BESTIARY or {}).values()
            if region_id in (e.get("regions") or []) and "BOSS" not in str(e.get("type", "")).upper()]
    if not pool:
        return None

    def tier(e):
        return "elite" if "elite" in str(e.get("type", "")).lower() else "minion"

    if danger <= 2:
        filtered = [e for e in pool if tier(e) == "minion"]
    elif danger == 3:
        filtered = pool
    else:
        filtered = [e for e in pool if tier(e) == "elite"] or pool
    pool = sorted(filtered or pool, key=lambda e: e.get("id", ""))

    if bestiary_knowledge is None and projection is None:
        return pool[int(turn) % len(pool)]  # legado: determinístico por turno

    # --- Fase 6.3: sorteio ponderado -------------------------------------
    from services import ecology as eco3
    loc_id = (loc or {}).get("id", "")
    weights = [eco3.hunt_pressure(e.get("id", ""), bestiary_knowledge, turn)
               * eco3.faction_boost(e, loc_id, projection)
               for e in pool]

    # fauna local rareada -> no máx. 1 migrante entra no sorteio (peso 0.5)
    avg = sum(weights) / max(1, len(weights))
    if avg < eco3.MIGRANT_THRESHOLD + 0.2:
        migrants = eco3.migrant_candidates(loc, gamedata.BESTIARY or {}, projection)
        migrants = [m for m in migrants if tier(m) == "minion" or danger >= 3]
        if migrants:
            m = sorted(migrants, key=lambda e: e.get("id", ""))[int(turn) % len(migrants)]
            pool = pool + [m]
            weights = weights + [eco3.MIGRANT_WEIGHT]

    return eco3.weighted_pick(pool, weights, rng)


_APEX_TAG = "apex"

_SAFE_LOC_TAGS = {"cidade", "urbano", "abrigo", "seguro"}


def last_safe_location(world: dict) -> str:
    """spec balanceamento-early-game (R3): onde o herói SAQUEADO acorda.
    Último local VISITADO com danger <= 1; fallback: o próprio local se for
    cidade/interior; senão o nó mais seguro da região atual (hub)."""
    visited = list(world.get("visited") or [])
    for loc_id in reversed(visited):
        loc = gamedata.get_location(loc_id) or {}
        if loc and int(loc.get("danger", 9) or 9) <= 1:
            return loc_id

    cur_id = world.get("current_location_id") or ""
    cur = gamedata.get_location(cur_id) or {}
    if cur.get("kind") == "interior" or _SAFE_LOC_TAGS & set(cur.get("tags") or []):
        return cur_id

    region = cur.get("region")
    candidates = [l for l in gamedata.WORLD_MAP.get("locations", [])
                  if l.get("region") == region and l.get("kind") != "interior"]
    if candidates:
        best = min(candidates,
                   key=lambda l: (int(l.get("danger", 9) or 9), not l.get("start")))
        return best["id"]
    return cur_id or gamedata.START_LOCATION_ID


def forced_encounter_danger(loc: dict, danger_real: int, player_level: int) -> int:
    """R5 (fix-playtest-achados): a FORÇA de um encontro FORÇADO escala com o nível
    — mesmo knob `danger` que `pick_encounter_enemy`/`encounter_budget` consomem —,
    pra viajar sub-nivelado não ser sentença de morte pior que atacar tudo de frente.
    RESSALVA: zona `apex` (proibida/endgame) NÃO escala — perigo CHEIO, sub-nível
    morre (você não pertence aqui). O TRIGGER do encontro segue no danger real
    (zona perigosa ainda embosca); só a força do que aparece é limitada."""
    danger_real = max(1, int(danger_real or 1))
    if _APEX_TAG in (loc.get("tags") or []):
        return danger_real
    lvl = max(1, int(player_level or 1))
    return max(1, min(danger_real, (lvl + 3) // 2))


def check_encounter(world: dict, factions, intel, turn: int = 0,
                    bestiary_knowledge: dict = None, projection: dict = None,
                    player_level: int = 1):
    """
    Gatilho DETERMINÍSTICO de encontro ao entrar/descansar num local perigoso.
    Dispara se: alerta de fuga ativo na região (reforços — R10); OU looming_threat
    ativo + perigo>=3; OU local dominado por facção hostil; OU perigo efetivo >= 4.
    Respeita cooldown (`world.last_encounter_turn`).

    Não-onisciência: a dica do inimigo só NOMEIA a facção dominante se o jogador a conhece.
    O hint traz o NOME EXATO de uma criatura do bestiário quando possível (R11) —
    o spawn cai no cache em vez de gerar via LLM.
    Retorna {hint, flavor, reason} ou None.
    """
    world = world or {}
    intel = ensure_faction_intel(intel)
    if turn - int(world.get("last_encounter_turn", -99)) < _ENCOUNTER_COOLDOWN:
        return None

    loc_id = world.get("current_location_id", "")
    danger = _effective_danger(world, loc_id)
    threat = world.get("looming_threat")
    ruler = _hostile_ruler(world, factions, loc_id)
    loc = gamedata.get_location(loc_id) or {}
    region = loc.get("region", world.get("current_location", "a região"))

    # R5: o TRIGGER usa danger real (acima); a FORÇA (criatura + budget) usa `eff`
    # escalado pelo nível — salvo zona apex. Carimba p/ o combat spawn consumir
    # (one-shot, como encounter_surprise). Deliberado/scripted não passa por aqui.
    eff = forced_encounter_danger(loc, danger, player_level)
    world["encounter_eff_danger"] = eff

    # R10: reforços — o fugitivo voltou, e não veio sozinho.
    alert = _pop_active_alert(world, loc, turn)
    if alert:
        hint = alert.get("hint", "os que fugiram")
        return {"hint": hint,
                "flavor": f"Eles voltaram — e não vieram sós. {hint} lidera o grupo que te cerca.",
                "reason": "reinforcements",
                "enemy_id": alert.get("enemy_id", "")}

    if ruler:
        fid = ruler.get("id")
        entry = pick_encounter_enemy(loc, eff, turn, faction_id=fid,
                                     bestiary_knowledge=bestiary_knowledge,
                                     projection=projection)
        if intel.get(fid, {}).get("known"):
            who = ruler.get("name")
            hint = f"{entry['name']} ({who})" if entry else f"asseclas armados da {who}"
            flavor = f"Aço da {who} barra o caminho — eles cobram a passagem em sangue."
        else:
            hint = entry.get("name") if entry else "homens armados sob uma bandeira que você não reconhece"
            flavor = "Homens armados sob uma bandeira estranha cercam você sem dar explicações."
        return {"hint": hint, "flavor": flavor, "reason": "controlled",
                "enemy_id": entry.get("id", "") if entry else ""}

    if threat and danger >= 3:
        return {"hint": f"criatura ligada a: {threat}", "flavor": str(threat),
                "reason": "looming_threat", "enemy_id": ""}

    if danger >= 4:
        entry = pick_encounter_enemy(loc, eff, turn,
                                     bestiary_knowledge=bestiary_knowledge,
                                     projection=projection)
        hint = entry.get("name") if entry else f"feras/perigos de {region}"
        return {"hint": hint, "enemy_id": entry.get("id", "") if entry else "",
                "flavor": f"O perigo de {region} se materializa: algo hostil avança sobre você.",
                "reason": "high_danger"}

    return None


# ---------------------------------------------------------------------------
# Fase 6.5 — Clima com efeito real (cadeias por região; efeito é LEITURA,
# nunca condição gravada — mudou o clima, mudou o efeito, zero limpeza)
# ---------------------------------------------------------------------------
_SHELTER_TAGS = {"cidade", "urbano", "abrigo", "seguro"}


def _weather_table(region_id: str) -> dict:
    from gamedata import load_json_data
    db = load_json_data("weather.json") or {}
    return db.get(region_id) or db.get("default") or {}


def advance_weather(world: dict, rng=None) -> dict:
    """Transição de clima (cadeia de Markov por região) — chamar quando o
    PERÍODO do relógio muda (viagem/descanso). Muta e retorna world."""
    import random as _random
    rng = rng or _random
    from gamedata import get_location
    loc = get_location(world.get("current_location_id", "")) or {}
    table = _weather_table(loc.get("region_id", "default"))
    states = table.get("states") or {}
    if not states:
        return world
    cur = world.get("weather_state")
    if cur not in states:
        cur = table.get("start") or next(iter(states))
    trans = states[cur].get("transitions") or {cur: 100}
    nxt = rng.choices(list(trans.keys()),
                      weights=[max(0, int(w)) for w in trans.values()], k=1)[0]
    world["weather_state"] = nxt if nxt in states else cur
    world["weather"] = states[world["weather_state"]].get("label", world["weather_state"])
    # fenômeno global expira por períodos restantes
    g = world.get("weather_global")
    if g:
        g = dict(g)
        g["periods_left"] = int(g.get("periods_left", 0)) - 1
        world["weather_global"] = g if g["periods_left"] > 0 else None
    return world


def weather_effects(world: dict, loc: dict = None) -> dict:
    """Efeitos mecânicos do clima ATUAL (leitura pontual, Fase 6.5).
    Local com tag de abrigo/urbano anula dot_outdoor e rest_block."""
    from gamedata import get_location
    loc = loc if loc is not None else (get_location(world.get("current_location_id", "")) or {})
    table = _weather_table((loc or {}).get("region_id", "default"))
    state = (table.get("states") or {}).get(world.get("weather_state") or "", {})
    g = world.get("weather_global") or {}
    if g:
        from gamedata import load_json_data
        gdef = ((load_json_data("weather.json") or {}).get("global_events") or {}) \
            .get(g.get("id", ""), {})
        state = {**state, **{k: v for k, v in gdef.items()
                             if k in ("perception_mod", "combat_attack_mod",
                                      "dot_outdoor", "rest_block", "travel_cost_extra", "label")}}
    sheltered = bool(_SHELTER_TAGS & set((loc or {}).get("tags") or []))
    return {
        "label": state.get("label", world.get("weather", "")),
        "perception_mod": int(state.get("perception_mod", 0) or 0),
        "combat_attack_mod": int(state.get("combat_attack_mod", 0) or 0),
        "travel_cost_extra": int(state.get("travel_cost_extra", 0) or 0),
        "rest_block": bool(state.get("rest_block")) and not sheltered,
        "dot_outdoor": 0 if sheltered else int(state.get("dot_outdoor", 0) or 0),
    }


def trigger_global_weather(world: dict, event_id: str) -> tuple:
    """Fenômeno global da LISTA CURADA (weather.json). Id fora da lista -> (world,
    None). Gancho p/ clímax de campanha; sem canal LLM ainda (desvio da spec)."""
    from gamedata import load_json_data
    gdef = ((load_json_data("weather.json") or {}).get("global_events") or {}).get(event_id)
    if not gdef:
        return world, None
    world["weather_global"] = {"id": event_id,
                               "periods_left": int(gdef.get("duration_periods", 2))}
    return world, gdef.get("desc", gdef.get("label", event_id))


# ---------------------------------------------------------------------------
# Fase 6.4 — Encontros sistêmicos: detecção, tipo, armadilha, rastro
# ---------------------------------------------------------------------------
_ENCOUNTER_TYPES_LOW = (("combat", 50), ("track", 30), ("social", 20))
_ENCOUNTER_TYPES_HIGH = (("combat", 60), ("trap", 20), ("social", 10), ("track", 10))
TRAP_DODGE_XP = 25


def detection_check(player: dict, danger: int, rng=None,
                    perception_mod: int = 0) -> dict:
    """Fase 6.4 (R1): d20 + mod WIS (+ bônus racial de save WIS) vs DC 8+2×danger.
    Percebeu -> vantagem (embosca); falhou -> surpreendido (inimigo age antes).
    Fase 6.5: `perception_mod` do clima (neblina -3 etc.) soma na rolagem."""
    import random as _random
    rng = rng or _random
    from combat_mechanics import attr_mods
    wis = attr_mods(player.get("attributes", {})).get("wis", 0)
    wis += int((player.get("racial_save_bonus") or {}).get("wis", 0) or 0)
    roll = rng.randint(1, 20) + wis + int(perception_mod or 0)
    dc = 8 + 2 * max(1, min(4, int(danger or 1)))
    return {"perceived": roll >= dc, "roll": roll, "dc": dc}


def roll_encounter_type(danger: int, rng=None) -> str:
    """Fase 6.4 (R2): nem todo perigo é combate. Distribuição por danger."""
    import random as _random
    rng = rng or _random
    table = _ENCOUNTER_TYPES_LOW if int(danger or 1) <= 2 else _ENCOUNTER_TYPES_HIGH
    kinds, weights = zip(*table)
    return rng.choices(list(kinds), weights=list(weights), k=1)[0]


def resolve_trap(player: dict, loc: dict, danger: int, rng=None) -> tuple:
    """Fase 6.4 (R3): armadilha 100%% Python — save vs DC 10+2×danger; falha =
    {danger}d6 + condição temática da região (data/traps.json); sucesso = XP de
    esquiva. Retorna (player_atualizado, logs, trap_dict)."""
    import random as _random
    rng = rng or _random
    import combat_mechanics as cm
    from gamedata import load_json_data

    traps_db = load_json_data("traps.json") or {}
    region = (loc or {}).get("region_id", "")
    pool = traps_db.get(region) or traps_db.get("default") or []
    if not pool:
        return player, [], None
    trap = pool[rng.randint(0, len(pool) - 1)] if len(pool) > 1 else pool[0]

    p = dict(player)
    danger = max(1, min(4, int(danger or 1)))
    dc = 10 + 2 * danger
    stat = cm.normalize_attr(trap.get("save_stat", "dex"))
    mod = cm.attr_mods(p.get("attributes", {})).get(stat, 0)
    mod += int((p.get("racial_save_bonus") or {}).get(stat, 0) or 0)
    roll = rng.randint(1, 20) + mod
    logs = [f"⚠ {trap['name']}! {trap.get('desc', '')}"]
    if roll >= dc:
        from progression import grant_xp
        p, lvl_events = grant_xp(p, TRAP_DODGE_XP)
        logs.append(f"{p.get('name', 'O herói')} ESQUIVA (save {roll} vs CD {dc}) — +{TRAP_DODGE_XP} XP.")
        return p, logs, {"trap": trap, "dodged": True, "level_up_events": lvl_events}
    dmg, detail = cm.roll_dice_numeric(f"{danger}d6")
    p["hp"] = max(0, int(p.get("hp", 0)) - dmg)
    logs.append(f"{p.get('name', 'O herói')} falha (save {roll} vs CD {dc}): "
                f"{dmg} de dano (HP {p['hp']}) [{detail}]")
    cond = trap.get("condition")
    if cond and p["hp"] > 0:
        p.setdefault("active_conditions", [])
        logs.append(cm.apply_condition(p, dict(cond)))
    return p, logs, {"trap": trap, "dodged": False, "level_up_events": []}


def resolve_track(state_bk: dict, loc: dict, danger: int, turn: int, rng=None) -> tuple:
    """Fase 6.4 (R4): rastro — revela criatura regional no Codex (grau rumor, 3.2)
    e/ou marca pista de tesouro (próximo TREASURE da região rola banda alta).
    Retorna (bestiary_knowledge, note, treasure_hint: bool)."""
    from services import discovery as disc
    entry = pick_encounter_enemy(loc, danger, turn)
    note = "Você encontra rastros antigos, ilegíveis."
    bk = state_bk or {}
    if entry:
        bk = disc.record_rumor(bk, entry.get("id", ""), turn)
        note = (f"Rastros frescos de {entry.get('name', 'algo grande')} — "
                "você grava os sinais na memória (Codex atualizado).")
    treasure = bool((rng or __import__('random')).randint(0, 1))
    if treasure:
        note += " Entre as marcas, sinais de carga abandonada — algo valioso ficou para trás por perto."
    return bk, note, treasure


def clock_label(world: dict) -> str:
    c = world.get("world_clock") or {}
    return f"Dia {c.get('day', 1)} · {c.get('period', PERIODS[0])}"


def starting_world(region_name: str, level: int) -> dict:
    """Monta o WorldState inicial a partir do local de início da região escolhida."""
    loc = gamedata.start_location_for_region(region_name) or {}
    loc_id = loc.get("id") or gamedata.START_LOCATION_ID
    # Fase 6.5: clima canônico da região desde o turno 0
    table = _weather_table(loc.get("region_id", "default"))
    wstate = table.get("start") or "limpo"
    wlabel = ((table.get("states") or {}).get(wstate) or {}).get("label", "Nublado")
    return {
        "current_location": loc.get("name") or region_name,
        "current_location_id": loc_id,
        "visited": [loc_id] if loc_id else [],
        "world_clock": {"day": 1, "period": PERIODS[0]},
        "time_of_day": PERIODS[0],
        "turn_count": 0,
        "danger_level": loc.get("danger", level),
        "weather": wlabel,
        "weather_state": wstate,
        "quest_plan": [],
        "quest_plan_origin": None,
    }
