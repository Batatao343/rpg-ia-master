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
_TRAVEL_CUES = [
    "vou",
    "viaj",
    "ir para",
    "ir até",
    "ir a",
    "sigo para",
    "sigo até",
    "caminho para",
    "rumo a",
    "parto",
    "vamos para",
    "seguir para",
    "me dirijo",
    "atravesso para",
    "voltar para",
    "volto para",
    "viajo",
]


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
        # SPEC-233 R1: perigo efetivo (override de ascensão/drift), não só o base.
        # SPEC-233: perigo efetivo é derivado; save antigo com valor velho é corrigido no load.
        world["danger_level"] = _effective_danger(world, cid)
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


_TRAVEL_VERBS = (
    r"vou|vamos|ir|viaj(?:o|ar|amos)|sigo|seguir|caminho|caminhar|parto|partir|"
    r"me\s+dirijo|atravesso|atravessar|volto|voltar|retorno|retornar|fujo|fugir|"
    r"entro|entrar|saio|sair"
)
_TRAVEL_PREPS = r"rumo\s+a|em\s+direcao\s+a|para|pra|pro|ate|aos|ao|as|a|em|nos|nas|no|na"
_ARTICLES = {"o", "a", "os", "as", "do", "da", "dos", "das", "um", "uma"}
_TRAVEL_RE = None


def looks_like_toponym(words: list) -> bool:
    """Palavras (texto ORIGINAL, após a preposição) iniciam um nome próprio?

    Só olha as 2 primeiras palavras de conteúdo (pulando artigos): "a fogueira com
    Grum" não é topônimo; "o Pântano da Melancolia" é.
    """
    content = [w for w in words if _fold_txt(w) not in _ARTICLES][:2]
    return any(w[:1].isupper() for w in content)


def _all_location_names() -> list:
    return [
        (_fold_txt(loc.get("name", "")), loc.get("id", ""))
        for loc in (gamedata.WORLD_MAP.get("locations") or [])
        if loc.get("name")
    ]


def is_travel_intent(text: str, world: dict | None = None) -> bool:
    """True somente para ordem explícita de deslocamento a um DESTINO.

    SPEC-229 R1: verbo fechado + preposição + (destino que resolve no mapa OU
    topônimo capitalizado). Movimento dentro da cena ("entro na taverna",
    "sigo em frente", "vou até a fogueira") NÃO é viagem.
    """
    import re

    global _TRAVEL_RE
    if _TRAVEL_RE is None:
        _TRAVEL_RE = re.compile(
            r"\b(?:"
            + _TRAVEL_VERBS
            + r")\b((?:\s+\w+){0,3}?)\s+(?:"
            + _TRAVEL_PREPS
            + r")\b(?P<rest>(?:\s+\w+)*)"
        )
    orig_words = re.findall(r"\w+", str(text or ""))
    folded = " ".join(_fold_txt(w) for w in orig_words)
    if not folded:
        return False
    if re.match(
        r"^(?:o\s+que|quem|qual|quais|como|onde|conte|fale|explique|"
        r"voce\s+sabe|sabe\s+algo|posso|poderia)\b",
        folded,
    ):
        return False
    folded_words = folded.split()
    # tenta cada ocorrência de preposição (a 1ª pode ser só um "a" de "volto a falar")
    for m in _TRAVEL_RE.finditer(folded):
        rest = m.group("rest").split()
        if not rest:
            continue
        rest_text = " ".join(rest)
        for name, loc_id in _all_location_names():
            if (name and name in rest_text) or (loc_id and loc_id in rest):
                return True
        idx = len(folded_words) - len(rest)
        if looks_like_toponym(orig_words[idx:]):
            return True
    return False


def invalid_travel_message(world: dict, text: str) -> str:
    """Recusa determinística para destino explícito que não é uma saída válida."""
    if not is_travel_intent(text, world) or find_travel_destination(world, text) is not None:
        return ""
    current = gamedata.get_location(world.get("current_location_id", "")) or {
        "name": world.get("current_location", "local atual")
    }
    exits = gamedata.get_connections(world.get("current_location_id"))
    labels = ", ".join(str(loc.get("name", loc.get("id", "?"))) for loc in exits)
    if not labels:
        labels = "nenhuma saída conhecida"
    return (
        f"Não há rota direta a partir de {current.get('name', 'seu local atual')}. "
        f"Saídas conectadas: {labels}."
    )


def find_travel_destination(world: dict, text: str) -> dict | None:
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
        base = max(0, int(times[dest["id"]]))
    else:
        times_dest = dest.get("travel_times") or {}
        base = max(0, int(times_dest[cur_id])) if cur_id in times_dest else 1
    return base + _seasonal_pass_extra(world, cur_id, dest.get("id"))


def _seasonal_pass_extra(world: dict, a: str, b: str) -> int:
    """SPEC-303 R11: passo de montanha fechado pela estação = travessia cara (nunca recusa)."""
    from services import world_calendar

    return world_calendar.pass_extra_periods() if world_calendar.pass_closed(world, a, b) else 0


def apply_travel(world: dict, dest: dict) -> dict:
    """Move o jogador para um destino: revela, sincroniza nome/perigo, gasta tempo.

    Custo 0 (intra-cidade/interior) NÃO vira relógio nem transiciona clima —
    mecânica da spec mapa-sublocais (R2).
    """
    world = dict(world)
    cost = travel_cost(world, dest)
    crossed_closed_pass = False
    if cost > 0:
        from services import world_calendar

        crossed_closed_pass = world_calendar.pass_closed(
            world, str(world.get("current_location_id") or ""), str(dest.get("id") or "")
        )
    world["current_location_id"] = dest["id"]
    world["current_location"] = dest["name"]
    visited = list(world.get("visited", []))
    if dest["id"] not in visited:
        visited.append(dest["id"])
    world["visited"] = visited
    # SPEC-233 R1: perigo EFETIVO do destino (danger_overrides vence o base do mapa).
    world["danger_level"] = (
        _effective_danger(world, dest["id"])
        if dest.get("id")
        else dest.get("danger", world.get("danger_level", 1))
    )
    if cost > 0:
        advance_clock(world, cost)
        # Fase 6.5: período mudou -> clima transiciona; clima bravo encarece a viagem
        # SPEC-233 R7: a duração do clima global conta períodos avançados, não chamadas.
        for _ in range(cost):
            advance_weather(world)
        if crossed_closed_pass:
            _force_snow(world, dest)
        extra = weather_effects(world, dest).get("travel_cost_extra", 0)
        if extra:
            advance_clock(world, extra)
    return world


def _force_snow(world: dict, dest: dict) -> None:
    """SPEC-303 R11: ao chegar por passo fechado o clima do destino vira a neve da região."""
    states = _weather_table(dest.get("region_id", "default")).get("states") or {}
    if "nevasca" in states:
        world["weather_state"] = "nevasca"
        world["weather"] = states["nevasca"].get("label", "nevasca")


def apply_rest(player: dict, world: dict, allies: list = None) -> tuple[dict, dict]:
    """Descanso: recupera ~metade dos recursos e avança 2 períodos.
    Fase 6.5: clima com `rest_block` (miasma etc.) NEGA o descanso ao relento —
    o tempo passa (1 período de tentativa), mas nada recupera.
    spec refatoracao-sistema-classes (R6): Devoto — Insônia faz o descanso render
    MENOS HP conforme a Carga do Abismo; aliado ativo mitiga (−1 de Carga)."""
    world = dict(world)
    blocked = weather_effects(world).get("rest_block", False)
    if blocked:
        advance_clock(world, 1)
        advance_weather(world)
        blocked_player = dict(player)
        if blocked_player.get("vitalidade") is not None:
            gamedata.sync_legacy_hp_aliases(blocked_player)
        return blocked_player, world
    player = dict(player)
    # Insônia (Devoto): fração de cura da Vitalidade cai por patamar de Carga.
    import combat_mechanics as cm

    hp_factor = 1.0
    _ab = cm.entropy_config(player).get("abyss") or {}
    if _ab.get("consequence") == "insonia":
        _tier = cm.abyss_tier(player)
        _pen = float((_ab.get("params", {}).get("rest_penalty") or {}).get(_tier, 0) or 0)
        hp_factor = max(0.0, 1.0 - _pen)
        if _ab.get("mitigable_by_ally") and allies:
            player["abyss_charge"] = max(0, int(player.get("abyss_charge", 0) or 0) - 1)
    is_v4 = player.get("vitalidade") is not None or isinstance(player.get("virtudes"), dict)
    if is_v4:
        gamedata.sync_vitality(player)
        ceiling = int(player.get("max_vitalidade", 0) or 0)
        recover = max(1, ceiling // 2)
        recover = max(1, int(recover * hp_factor)) if hp_factor > 0 else 0
        player["vitalidade"] = min(ceiling, int(player.get("vitalidade", 0) or 0) + recover)
        from services import conflict_damage

        conflict_damage.rest_treat_wounds(
            player,
            rest="longo",
            has_kit=any(
                (entry.get("id") if isinstance(entry, dict) else entry) == "kit_medico"
                for entry in (player.get("inventory") or [])
            ),
            is_medic="medico" in _fold_txt(player.get("class_name", "")),
        )
        for defense in (player.get("armor"), player.get("shield")):
            if defense:
                conflict_damage.recover_integrity(defense, "longo")
        from services import cards

        cards.reset_card_usage({"player": player}, "descanso_longo")
        from services import death_flow

        recovery_state = death_flow.post_combat_consciousness(player)
        # Um Crítico continua exigindo tratamento especializado para ser removido,
        # mas o descanso longo em segurança que devolveu Vitalidade é uma
        # intervenção suficiente para o sobrevivente recobrar a consciência. Sem
        # esta transição, personagens solo ficavam presos para sempre entre
        # conflitos: inconscientes, vivos e sem uma ação possível de tratamento.
        if recovery_state == "inconsciente" and int(player.get("vitalidade", 0) or 0) > 0:
            recovery_state = "tratavel"
        player["post_combat_state"] = recovery_state
        if recovery_state in ("acordado", "tratavel"):
            player["conscious"] = True
            player["incapacitated"] = False
        elif recovery_state == "inconsciente":
            player["conscious"] = False
        gamedata.sync_legacy_hp_aliases(player)

    if not is_v4 and "max_hp" in player:
        # Compatibilidade isolada com fichas arquivadas.
        ceiling = int(player.get("max_hp", 0) or 0)
        recover = max(1, ceiling // 2)
        recover = max(1, int(recover * hp_factor)) if hp_factor > 0 else 0
        player["hp"] = min(ceiling, int(player.get("hp", 0) or 0) + recover)
    # spec refatoracao-sistema-classes (R2): Entropia recompõe INTEGRAL no
    # descanso (diferente do HP, que fica em ~metade). Carga do Abismo NÃO cai.
    if "max_entropy" in player:
        player["entropy"] = player.get("max_entropy", 0)
    advance_clock(world, 2)
    for _ in range(2):  # 2 períodos -> 2 ticks (R7)
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
        # SPEC-301 R23: contra-jogo do jogador; save antigo = 0 (relógio linear de sempre).
        f.setdefault("influence", 0)
        f.setdefault("influence_periods", 0)
        out.append(f)
    return out


# SPEC-301 R14: influência do jogador sobre o relógio de uma fação.
INFLUENCE_MAX = 9
INFLUENCE_PACE_DIV = 3  # +-9 de influência => +-3 de pace
INFLUENCE_DECAY_PERIODS = 4  # a cada N períodos avançados a influência recua 1 rumo a 0


def clamp_influence(value) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = 0
    return max(-INFLUENCE_MAX, min(INFLUENCE_MAX, v))


def effective_pace(faction: dict) -> int:
    """Pace efetivo = pace + influência/3 (truncado rumo a 0), piso 0. Influência 0 = legado."""
    infl = clamp_influence(faction.get("influence", 0))
    return max(0, int(faction.get("pace", 3)) + int(infl / INFLUENCE_PACE_DIV))


def advance_factions(factions, periods: int = 1) -> tuple[list, list]:
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
            infl = clamp_influence(f.get("influence", 0))
            if infl == 0:
                f["influence_periods"] = 0
                f["progress"] = min(100, f.get("progress", 0) + f.get("pace", 3) * periods)
            else:
                # SPEC-301 R14: pace efetivo + decadência da influência (acumulador de períodos).
                for idx in range(periods):
                    f["progress"] = min(100, f.get("progress", 0) + effective_pace(f))
                    acc = int(f.get("influence_periods", 0) or 0) + 1
                    if acc >= INFLUENCE_DECAY_PERIODS:
                        acc = 0
                        f["influence"] = infl = infl - (1 if infl > 0 else -1)
                    f["influence_periods"] = acc
                    if infl == 0:
                        f["influence_periods"] = 0
                        rest = periods - (idx + 1)
                        f["progress"] = min(100, f.get("progress", 0) + f.get("pace", 3) * rest)
                        break
            if f["progress"] >= 100 and not f.get("completed", False):
                f["completed"] = True
                events.append(
                    {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "goal": f.get("goal", ""),
                        "disposition": f.get("disposition", "neutro"),
                    }
                )
        new_list.append(f)
    return new_list, events


# --- Fase 2 / Etapa B: ascensão — concluir objetivo muda o MUNDO (determinístico) ---


def _raise_danger(world: dict, loc_id: str) -> None:
    """Sobe o perigo de um local em +1 (teto 4), via override de runtime."""
    overrides = dict(world.get("danger_overrides") or {})
    base = _effective_danger(world, loc_id, with_state=False)  # sem o delta do estado de local
    overrides[loc_id] = min(4, int(base) + 1)
    world["danger_overrides"] = overrides
    # SPEC-233 R2: ascensão assume o override — o drift do world_simulator não decai.
    if loc_id in (world.get("danger_shift_turns") or {}):
        shifts = dict(world["danger_shift_turns"])
        shifts.pop(loc_id, None)
        world["danger_shift_turns"] = shifts
    if world.get("current_location_id") == loc_id:
        world["danger_level"] = overrides[loc_id]


def resolve_faction_completions(factions, world, events, intel) -> tuple[list, dict, str]:
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
                world["looming_threat_faction"] = fid  # SPEC-289 R1
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
        note = (
            "\n".join(notes)
            + "\nNarre estas consequências como algo que o jogador PERCEBE no mundo; "
            "NÃO revele nomes de facções que ele ainda não conhece."
        )
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


def apply_faction_reveal(intel, factions, faction_id: str, level: str, turn: int = 0) -> dict:
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


# --- Fase 2: reputação de fação (SPEC-298: dono é services.reputation) ---
# O VALOR do delta vem da DEED_TABLE de services.reputation (Python decide, não o LLM);
# aqui só a aritmética pura e a derivação de `disposition` (hostil/neutro/aliado).

REP_MIN, REP_MAX = -100, 100
_ALIADO_AT, _HOSTIL_AT = 40, -40  # limiares de disposição derivada da reputação


def _disposition_for(rep: int) -> str:
    """`factions[*].disposition` (hostil|neutro|aliado), consumido por economy.
    NÃO confundir com a faixa de NPC (`npc_tier`) nem com `faction_tier` (SPEC-298 D8)."""
    if rep >= _ALIADO_AT:
        return "aliado"
    if rep <= _HOSTIL_AT:
        return "hostil"
    return "neutro"


def apply_reputation(
    factions, faction_id: str, direction: str, delta: int
) -> tuple[list, dict | None]:
    """
    Aplica `delta` (magnitude positiva, vinda da tabela de feitos) a uma fação.
    direction: SÓ 'ajudou' (+) | 'prejudicou' (-) exatos; qualquer outro valor,
    id desconhecido ou delta 0 = no-op. Clampa em [-100, 100] e re-deriva a
    disposition por limiar.

    Retorna (novas_factions, evento|None). evento =
    {id, name, reputation, disposition, direction, delta}.
    """
    factions = ensure_factions(factions)
    if direction == "ajudou":
        sign = 1
    elif direction == "prejudicou":
        sign = -1
    else:
        return factions, None
    try:
        magnitude = abs(int(delta))
    except (TypeError, ValueError):
        return factions, None
    if not faction_id or magnitude == 0:
        return factions, None

    new_list, event = [], None
    for f in factions:
        f = dict(f)
        if f.get("id") == faction_id:
            old = int(f.get("reputation", 0))
            new_rep = max(REP_MIN, min(REP_MAX, old + sign * magnitude))
            f["reputation"] = new_rep
            f["disposition"] = _disposition_for(new_rep)
            event = {
                "id": f.get("id"),
                "name": f.get("name"),
                "reputation": new_rep,
                "disposition": f["disposition"],
                "direction": direction,
                "delta": new_rep - old,
            }
        new_list.append(f)
    return new_list, event


# --- Fase 2 / Encontros: o mundo perigoso/dominado/ameaçado gera combate (determinístico) ---

_ENCOUNTER_COOLDOWN = 2  # turnos mínimos entre encontros automáticos (anti-spam)

# spec letalidade-early-game-v2 (alavanca 1): o early-game morria por falta de
# laço de recuperação (HP travado, descanso interrompido por encontro). Nível
# baixo ganha: descanso CONFIÁVEL em zona não-apex de perigo baixo + cadência de
# encontro mais espaçada (espaço pra viajar/curar entre lutas). Determinístico.
EARLY_GAME_LEVEL = 3  # até este nível (inclusive) valem as regras de recuperação
RECOVERY_SAFE_DANGER = 3  # descanso NÃO sorteia encontro se danger <= isto (e não-apex)
_EARLY_COOLDOWN_BONUS = 2  # +turnos no cooldown de encontro quando nível <= EARLY_GAME_LEVEL


def recovery_rest_safe(player_level: int, danger_now: int, loc: dict) -> bool:
    """True se um DESCANSO de early-game deve recuperar sem sortear encontro:
    nível <= EARLY_GAME_LEVEL, zona NÃO-apex e perigo <= RECOVERY_SAFE_DANGER.
    Zona apex ou perigo 4+ segue rolando — descansar na boca do lobo é risco
    escolhido."""
    if int(player_level or 1) > EARLY_GAME_LEVEL:
        return False
    if _APEX_TAG in ((loc or {}).get("tags") or []):
        return False
    return int(danger_now or 1) <= RECOVERY_SAFE_DANGER


def _effective_danger(world: dict, loc_id: str, *, with_state: bool = True) -> int:
    """Perigo atual do local: override de ascensão (se houver) senão o base do mapa.
    `danger_overrides[loc]` pode ser int (legado) ou dict {value,...} (SPEC-233)."""
    overrides = world.get("danger_overrides") or {}
    if loc_id in overrides:
        v = overrides[loc_id]
        if isinstance(v, dict):
            v = v.get("value", 1)
        base = int(v)
    else:
        loc = gamedata.get_location(loc_id) or {}
        base = int(loc.get("danger", world.get("danger_level", 1)))
    return _with_state_delta(world, loc_id, base) if with_state else base


def _with_state_delta(world: dict, loc_id: str, base: int) -> int:
    """SPEC-302 R19: soma o `danger_delta` do estado de local (cache derivado escrito pelo
    motor de mundo no modo `on`), com clamp [0, 4]; nunca rebaixa um perigo > 4."""
    deltas = world.get("location_danger_delta")
    if not deltas:
        return base
    from services import world_engine

    if world_engine.mode() != "on":
        return base
    loc = gamedata.get_location(loc_id) or {}
    key = loc.get("parent_id") if loc.get("kind") == "interior" else loc_id
    delta = int(deltas.get(key or loc_id, 0) or 0)
    if not delta:
        return base
    return max(base, min(4, base + delta)) if delta > 0 else max(0, base + delta)


def effective_danger(world: dict) -> int:
    """SPEC-233 R1: helper ÚNICO — perigo efetivo do local ATUAL (encontros, mapa, descanso)."""
    world = world or {}
    loc_id = world.get("current_location_id", "")
    if not loc_id:
        return int(world.get("danger_level", 1) or 1)
    return _effective_danger(world, loc_id)


DANGER_DECAY_TURNS = 10  # SPEC-233 R2 (D-A default): decai 1 rumo ao base a cada 10 turnos


def decay_danger_overrides(world: dict) -> dict:
    """SPEC-233 R2: drift de perigo (world_simulator) decai 1 em direção ao base a cada
    DANGER_DECAY_TURNS sem novo shift. Overrides sem carimbo (ascensão) não decaem."""
    shifts = dict(world.get("danger_shift_turns") or {})
    if not shifts:
        return world
    overrides = dict(world.get("danger_overrides") or {})
    now = int(world.get("turn_count", 0) or 0)
    for loc_id, last in list(shifts.items()):
        if loc_id not in overrides:
            shifts.pop(loc_id, None)
            continue
        if now - int(last) < DANGER_DECAY_TURNS:
            continue
        base = int((gamedata.get_location(loc_id) or {}).get("danger", 1))
        # SPEC-302 review F-1: decai o override CRU — o delta do estado de local (crise)
        # é somado na leitura; incluí-lo aqui o carimbaria no override (conta dupla).
        cur = _effective_danger(world, loc_id, with_state=False)
        cur += (base > cur) - (base < cur)
        if cur == base:
            overrides.pop(loc_id, None)
            shifts.pop(loc_id, None)
        else:
            overrides[loc_id] = cur
            shifts[loc_id] = now
    world["danger_overrides"] = overrides
    world["danger_shift_turns"] = shifts
    if world.get("current_location_id"):
        world["danger_level"] = _effective_danger(world, world["current_location_id"])
    return world


def _hostile_ruler(world: dict, factions, loc_id: str, exempt=()):
    """Retorna a facção HOSTIL que domina o local atual, ou None.

    ``exempt``: ids de fações cujo domínio não conta como hostil (SPEC-301 perk
    ``passagem`` — o membro atravessa o território da própria fação)."""
    fid = (world.get("controlled") or {}).get(loc_id)
    if not fid or fid in (exempt or ()):
        return None
    for f in ensure_factions(factions):
        if f.get("id") == fid and f.get("disposition") == "hostil":
            return f
    return None


_ALERT_TTL = 6  # turnos de validade de um alerta de fuga


def register_flee_alert(
    world: dict, fled_hint: str, faction_id=None, turn: int = 0, enemy_id: str = ""
) -> dict:
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
    alerts.append(
        {
            "region_id": loc.get("region_id", world.get("current_location_id", "")),
            "hint": hint,
            "faction_id": faction_id,
            "turn": int(turn),
            "enemy_id": enemy_id or "",
        }
    )
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


def _theme_stems(text: str) -> set:
    """SPEC-289 R3b: radicais de palavras (sem acento/caixa, >=5 letras, sem `s`
    final, 6 primeiras letras). Determinístico — base do casamento ameaça↔criatura."""
    import re
    import unicodedata

    norm = "".join(
        c
        for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    out = set()
    for w in re.findall(r"[a-z]+", norm):
        w = w[:-1] if w.endswith("s") else w
        if len(w) >= 5:
            out.add(w[:6])
    return out


def threat_faction(world: dict, factions) -> dict | None:
    """SPEC-289 R1: fação que invocou a `looming_threat` — campo gravado na ascensão;
    save antigo: casa o texto com `ascension.threat` das fações vivas, depois dos seeds."""
    world = world or {}
    threat = str(world.get("looming_threat") or "").strip()
    fid = world.get("looming_threat_faction") or ""
    for pool in (list(factions or []), gamedata.seed_factions()):
        for f in pool:
            if not isinstance(f, dict):
                continue
            asc = f.get("ascension") or {}
            if asc.get("type") != "invocar_entidade":
                continue
            if fid and f.get("id") == fid:
                return f
            if not fid and threat and str(asc.get("threat") or "").strip() == threat:
                return f
    return None


def threat_sphere(faction: dict) -> set:
    """SPEC-289 R2: regiões onde a ameaça se manifesta — região do local-alvo da
    ascensão ∪ região de origem da fação (nome de exibição -> region_id)."""
    out = set()
    asc = (faction or {}).get("ascension") or {}
    tgt = gamedata.get_location(asc.get("target") or "") or {}
    if tgt.get("region_id"):
        out.add(tgt["region_id"])
    home = (faction or {}).get("region") or ""
    for loc in gamedata.WORLD_MAP.get("locations", []):
        if home and loc.get("region") == home and loc.get("region_id"):
            out.add(loc["region_id"])
    return out


def threat_theme_match(faction: dict, threat_text: str):
    """SPEC-289 R3: pontua a afinidade de uma criatura com a ameaça —
    2 = combatente da fação; 1 = nome casa radical do texto (atual ou autorado da
    ascensão); 0 = sem tema."""
    fid = (faction or {}).get("id") or ""
    canon = ((faction or {}).get("ascension") or {}).get("threat") or ""
    stems = _theme_stems(threat_text) | _theme_stems(canon)  # texto atual ∪ autorado

    def score(entry: dict) -> int:
        if fid and (entry or {}).get("faction") == fid:
            return 2
        if stems and _theme_stems((entry or {}).get("name", "")) & stems:
            return 1
        return 0

    return score


_CONCEALED_HINT = "combatente de uma ordem que você não reconhece"


def concealed_faction(entry, factions, intel) -> str:
    """SPEC-292 (P2-3): id da fação que o NOME da criatura exporia ao jogador que ainda
    não a conhece (`intel[fid].known`), reusando a regra de não-onisciência da Fase 2.
    Só conta se o nome casa radicais do nome da fação; senão ""."""
    fid = str((entry or {}).get("faction") or "")
    if not fid or ensure_faction_intel(intel).get(fid, {}).get("known"):
        return ""
    fac = next(
        (
            f
            for pool in (list(factions or []), gamedata.seed_factions())
            for f in pool
            if isinstance(f, dict) and f.get("id") == fid
        ),
        None,
    )
    if fac and _theme_stems(entry.get("name", "")) & _theme_stems(fac.get("name", "")):
        return fid
    return ""


def public_encounter_hint(entry, factions, intel):
    """(public_hint, concealed_faction_id) — o `hint` canônico segue p/ spawn/dedupe."""
    if not entry:
        return None, ""
    fid = concealed_faction(entry, factions, intel)
    return (_CONCEALED_HINT if fid else entry.get("name")), fid


def unknown_faction_names(faction_ids, factions, intel) -> list:
    """SPEC-292: nomes de exibição das fações (entre `faction_ids`) que o jogador não conhece."""
    intel = ensure_faction_intel(intel)
    out = []
    for fid in dict.fromkeys(str(x) for x in faction_ids if x):
        if intel.get(fid, {}).get("known"):
            continue
        for pool in (list(factions or []), gamedata.seed_factions()):
            f = next((x for x in pool if isinstance(x, dict) and x.get("id") == fid), None)
            if f:
                out.append(str(f.get("name") or fid))
                break
    return out


def pick_encounter_enemy(
    loc: dict,
    danger: int,
    turn: int = 0,
    faction_id: str = "",
    *,
    bestiary_knowledge: dict = None,
    projection: dict = None,
    rng=None,
    theme=None,
    season: str | None = None,
):
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
    SPEC-289: `theme` (callable entry->int, de `threat_theme_match`) restringe o
    sorteio às criaturas temáticas (pontuação > 0) no porte ESTRITO do perigo
    (<=2 Minion; 3 qualquer; >=4 Elite); no sorteio ponderado a pontuação multiplica
    o peso (fação x2). Sem nenhuma temática -> sorteio normal. Sem migrantes.
    Retorna a ENTRADA do bestiário ou None (chamador cai no hint genérico).
    """
    if faction_id:
        entry = _bestiary_by_faction(faction_id)
        if entry:
            return entry

    region_id = (loc or {}).get("region_id", "")
    if not region_id:
        return None
    from encounter_budget import is_boss  # SPEC-287: categoria canônica, não `type`

    pool = [
        e
        for e in (gamedata.BESTIARY or {}).values()
        if region_id in (e.get("regions") or []) and not is_boss(e)
    ]
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
    themed = False
    regional = list(filtered or pool)  # SPEC-292: pool não-temático (mistura sob pressão de caça)
    if theme is not None:
        strict = filtered if danger <= 3 else [e for e in pool if tier(e) == "elite"]
        hits = [e for e in strict if theme(e) > 0]
        if hits:
            filtered = hits
            themed = True
    pool = sorted(filtered or pool, key=lambda e: e.get("id", ""))

    if bestiary_knowledge is None and projection is None:
        return pool[int(turn) % len(pool)]  # legado: determinístico por turno

    # --- Fase 6.3: sorteio ponderado -------------------------------------
    from services import ecology as eco3

    loc_id = (loc or {}).get("id", "")

    def _base(candidates):
        return [
            eco3.hunt_pressure(e.get("id", ""), bestiary_knowledge, turn)
            * eco3.faction_boost(e, loc_id, projection)
            for e in candidates
        ]

    base = _base(pool)
    if themed and sum(base) / max(1, len(base)) < eco3.MIGRANT_THRESHOLD + 0.2:
        # SPEC-292 (P2-2): a pressão de caça rareou as temáticas -> o pool regional
        # (mesmo porte, sem BOSS) volta ao sorteio; sem isso a Fase 6.3 ficaria inócua.
        ids = {e.get("id") for e in pool}
        extra = [e for e in regional if e.get("id") not in ids]
        pool = sorted(pool + extra, key=lambda e: e.get("id", ""))
        base = _base(pool)
    weights = [
        b
        * (
            (theme(e) or 1) if themed else 1
        )  # SPEC-289: combatente da fação pesa x2 (extras SPEC-292 x1)
        for b, e in zip(base, pool)
    ]
    if season:  # SPEC-303 R14b: estação redistribui pesos DENTRO do porte (só caminho ponderado)
        from services import world_calendar

        smult = world_calendar.encounter_multipliers(region_id, season)
        if smult:
            weights = [w * float(smult.get(e.get("id", ""), 1.0)) for w, e in zip(weights, pool)]

    # fauna local rareada -> no máx. 1 migrante entra no sorteio (peso 0.5)
    avg = sum(weights) / max(1, len(weights))
    if not themed and avg < eco3.MIGRANT_THRESHOLD + 0.2:
        migrants = eco3.migrant_candidates(loc, gamedata.BESTIARY or {}, projection)
        migrants = [m for m in migrants if tier(m) == "minion" or danger >= 3]
        if migrants:
            m = sorted(migrants, key=lambda e: e.get("id", ""))[int(turn) % len(migrants)]
            pool = pool + [m]
            weights = weights + [eco3.MIGRANT_WEIGHT]

    return eco3.weighted_pick(pool, weights, rng)


_APEX_TAG = "apex"


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


def check_encounter(
    world: dict,
    factions,
    intel,
    turn: int = 0,
    bestiary_knowledge: dict = None,
    projection: dict = None,
    player_level: int = 1,
    law_hint: dict | None = None,
    exempt_factions=(),
):
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
    # spec letalidade-early-game-v2 (alavanca 1): cooldown maior no early-game —
    # menos combate forçado de volta-a-volta, espaço pra recuperar entre lutas.
    cooldown = _ENCOUNTER_COOLDOWN + (
        _EARLY_COOLDOWN_BONUS if int(player_level or 1) <= EARLY_GAME_LEVEL else 0
    )
    world.pop("encounter_eff_danger", None)  # SPEC-233 R5: flag one-shot nunca gruda
    if turn - int(world.get("last_encounter_turn", -99)) < cooldown:
        return None

    loc_id = world.get("current_location_id", "")
    danger = _effective_danger(world, loc_id)
    threat = world.get("looming_threat")
    ruler = _hostile_ruler(world, factions, loc_id, exempt_factions)
    loc = gamedata.get_location(loc_id) or {}
    region = loc.get("region", world.get("current_location", "a região"))

    # R5: o TRIGGER usa danger real (acima); a FORÇA (criatura + budget) usa `eff`
    # escalado pelo nível — salvo zona apex. Carimba p/ o combat spawn consumir
    # (one-shot, como encounter_surprise). Deliberado/scripted não passa por aqui.
    eff = forced_encounter_danger(loc, danger, player_level)
    from services import world_calendar

    season_id = world_calendar.active_season(world)  # SPEC-303 R14b (neutro sem calendário)

    # SPEC-233 R5: só carimba quando devolve um encontro (ver _stamp).
    def _stamp(result):
        world["encounter_eff_danger"] = eff
        return result

    # R10: reforços — o fugitivo voltou, e não veio sozinho.
    alert = _pop_active_alert(world, loc, turn)
    if alert:
        hint = alert.get("hint", "os que fugiram")
        return _stamp(
            {
                "hint": hint,
                "flavor": f"Eles voltaram — e não vieram sós. {hint} lidera o grupo que te cerca.",
                "reason": "reinforcements",
                "enemy_id": alert.get("enemy_id", ""),
            }
        )

    # SPEC-299 R18: caçadores de recompensa (nível `cacado` + sinal já mostrado). A força vem
    # do preço pela cabeça (`eff_danger`), NUNCA do nível do jogador. Sem `law_hint`: idêntico.
    if law_hint:
        world["encounter_eff_danger"] = int(law_hint.get("eff_danger") or eff)
        return {
            "hint": law_hint.get("hint", "caçadores de recompensa"),
            "flavor": law_hint.get("flavor", "Caçadores de recompensa cercam você."),
            "reason": "bounty_hunters",
            "enemy_id": law_hint.get("enemy_id", ""),
            "jurisdiction_id": law_hint.get("jurisdiction_id", ""),
        }

    if ruler:
        fid = ruler.get("id")
        entry = pick_encounter_enemy(
            loc,
            eff,
            turn,
            faction_id=fid,
            bestiary_knowledge=bestiary_knowledge,
            projection=projection,
            season=season_id,
        )
        if intel.get(fid, {}).get("known"):
            who = ruler.get("name")
            hint = f"{entry['name']} ({who})" if entry else f"asseclas armados da {who}"
            flavor = f"Aço da {who} barra o caminho — eles cobram a passagem em sangue."
        else:
            hint = (
                entry.get("name")
                if entry
                else "homens armados sob uma bandeira que você não reconhece"
            )
            flavor = "Homens armados sob uma bandeira estranha cercam você sem dar explicações."
        res = {
            "hint": hint,
            "flavor": flavor,
            "reason": "controlled",
            "enemy_id": entry.get("id", "") if entry else "",
            "public_hint": hint,
        }
        if entry and not intel.get(fid, {}).get("known"):
            ph, cf = public_encounter_hint(entry, factions, intel)
            res["public_hint"] = ph
            if cf:
                res["concealed_faction"] = cf
        return _stamp(res)

    if threat and danger >= 3:
        # SPEC-288: a criatura é canônica (bestiário); o texto da ameaça é só flavor.
        # SPEC-289: dentro da esfera da ameaça, prefere criatura TEMÁTICA da região;
        # fora dela, fauna local e o texto vira eco distante (não cola o tema na fera).
        tfac = threat_faction(world, factions)
        in_sphere = bool(tfac) and loc.get("region_id") in threat_sphere(tfac)
        theme = threat_theme_match(tfac, str(threat)) if in_sphere else None
        entry = pick_encounter_enemy(
            loc,
            eff,
            turn,
            bestiary_knowledge=bestiary_knowledge,
            projection=projection,
            theme=theme,
            season=season_id,
        )
        flavor = str(threat)
        if tfac and not in_sphere:
            flavor = f"Ecos de uma ameaça distante: {threat} Aqui, porém, o perigo é outro."
        elif theme is not None and entry and theme(entry) == 0:
            # revisão P2-1: na esfera, mas sem criatura temática no porte (fallback).
            flavor = (
                f"A ameaça ronda a região: {threat} O que te ataca agora, porém, é outra coisa."
            )
        hint = entry.get("name") if entry else f"feras/perigos de {region}"
        public, cf = public_encounter_hint(entry, factions, intel) if entry else (hint, "")
        res = {
            "hint": hint,
            "public_hint": public,
            "flavor": flavor,
            "reason": "looming_threat",
            "enemy_id": entry.get("id", "") if entry else "",
        }
        if cf:
            res["concealed_faction"] = cf
        return _stamp(res)

    if danger >= 4:
        entry = pick_encounter_enemy(
            loc,
            eff,
            turn,
            bestiary_knowledge=bestiary_knowledge,
            projection=projection,
            season=season_id,
        )
        hint = entry.get("name") if entry else f"feras/perigos de {region}"
        return _stamp(
            {
                "hint": hint,
                "enemy_id": entry.get("id", "") if entry else "",
                "flavor": f"O perigo de {region} se materializa: algo hostil avança sobre você.",
                "reason": "high_danger",
            }
        )

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


# spec weather-global-vivo: chance sistêmica de iniciar um fenômeno GLOBAL por
# período sem evento ativo (determinístico via rng; escala com danger_level).
GLOBAL_WEATHER_BASE_CHANCE = 0.06  # [BALANCEAR] por período sem evento ativo
GLOBAL_WEATHER_DANGER_STEP = 0.03  # [BALANCEAR] +chance por nível de perigo >1


def maybe_start_global_weather(world: dict, rng=None) -> str | None:
    """R1/R2: SEM evento global ativo, rola p/ iniciar um da lista curada
    (weather.json:global_events). Chance = base + step×(danger−1). Determinístico
    via `rng`. Reusa trigger_global_weather. Retorna a desc do evento ou None."""
    import random as _random

    rng = rng or _random
    if world.get("weather_global"):
        return None
    from gamedata import load_json_data

    events = list(((load_json_data("weather.json") or {}).get("global_events") or {}).keys())
    if not events:
        return None
    danger = max(1, min(4, int(world.get("danger_level", 1) or 1)))
    chance = GLOBAL_WEATHER_BASE_CHANCE + GLOBAL_WEATHER_DANGER_STEP * (danger - 1)
    if rng.random() >= chance:
        return None
    _world, desc = trigger_global_weather(world, rng.choice(events))
    return desc


def advance_weather(world: dict, rng=None, *, steps: int = 1) -> dict:
    """Transição de clima (cadeia de Markov por região) — chamar quando o
    PERÍODO do relógio muda (viagem/descanso). Muta e retorna world.

    spec weather-global-vivo: também tica/expira o fenômeno GLOBAL e, sem evento
    ativo, rola p/ iniciar um novo (determinístico). SPEC-233 R7: `steps` = períodos
    realmente avançados — repete o tick por período (viagem de 3 = 3 ticks)."""
    for _ in range(max(1, int(steps or 1)) - 1):
        _advance_weather_once(world, rng)
    return _advance_weather_once(world, rng)


def _advance_weather_once(world: dict, rng=None) -> dict:
    import random as _random

    rng = rng or _random
    from gamedata import get_location

    loc = get_location(world.get("current_location_id", "")) or {}
    table = _weather_table(loc.get("region_id", "default"))
    states = table.get("states") or {}
    # fenômeno global expira por períodos restantes (independe do clima local)
    g = world.get("weather_global")
    if g:
        g = dict(g)
        g["periods_left"] = int(g.get("periods_left", 0)) - 1
        world["weather_global"] = g if g["periods_left"] > 0 else None
    # sem evento global ativo → chance sistêmica de iniciar um (R1/R2)
    maybe_start_global_weather(world, rng)
    if not states:
        return world
    cur = world.get("weather_state")
    if cur not in states:
        cur = table.get("start") or next(iter(states))
    trans = states[cur].get("transitions") or {cur: 100}
    weights = [max(0, int(w)) for w in trans.values()]
    from services import world_calendar

    mult = world_calendar.weather_multipliers(
        loc.get("region_id", "default"), world_calendar.active_season(world)
    )
    if mult:  # SPEC-303 R8: estação multiplica os pesos de transição (soma 0 -> pesos crus)
        scaled = [max(0, int(round(w * float(mult.get(k, 1.0))))) for k, w in zip(trans, weights)]
        weights = scaled if sum(scaled) > 0 else weights
    nxt = rng.choices(list(trans.keys()), weights=weights, k=1)[0]
    world["weather_state"] = nxt if nxt in states else cur
    world["weather"] = states[world["weather_state"]].get("label", world["weather_state"])
    return world


# spec itens-vivos-e-luz: sistema de LUZ determinístico.
DARK_PERIODS = {"Anoitecer", "Noite"}
_DARK_TAGS = {"dark", "masmorra", "caverna", "subterraneo"}
DARK_PERCEPTION_PENALTY = -3  # [BALANCEAR] escuro sem luz: percepção
DARK_COMBAT_PENALTY = -1  # [BALANCEAR] escuro sem luz: acerto (simétrico)


def _has_light_source(player: dict) -> bool:
    """True se o herói carrega/veste uma fonte de luz: item com passiva
    `{trigger:"light"}` OU tag `luz` (tocha/lanterna) no equipamento OU inventário
    (diferente das passivas de combate, que só contam equipadas — luz você carrega)."""
    import combat_mechanics as _cm

    db = _cm.ARTIFACTS_DB
    ids = []
    eq = player.get("equipment")
    if isinstance(eq, dict):
        ids += [v for v in eq.values() if v]
    ids += [e.get("id") if isinstance(e, dict) else e for e in (player.get("inventory") or [])]
    for iid in ids:
        item = db.get(iid) or {}
        if "luz" in (item.get("tags") or []) or "luz" in (item.get("economy_tags") or []):
            return True
        if any(
            isinstance(pe, dict) and pe.get("trigger") == "light"
            for pe in (item.get("mechanics") or {}).get("passive_effects") or []
        ):
            return True
    return False


def light_level(world: dict, player: dict) -> dict:
    """R3: estado de LUZ do herói agora. Escuro = período noturno OU local com tag
    `dark`, E não abrigado/urbano (cidade tem tochas). Fonte de luz anula o escuro.
    Retorna {dark, lit, perception_mod, combat_mod, label}. Puro (sem RNG)."""
    from gamedata import get_location

    loc = get_location(world.get("current_location_id", "")) or {}
    tags = set(loc.get("tags") or [])
    sheltered = bool(_SHELTER_TAGS & tags)
    period = world.get("time_of_day") or (world.get("world_clock") or {}).get("period") or ""
    # SPEC-233 R3: masmorra/caverna/subterrâneo são escuros — `abrigo` protege do clima,
    # não ilumina (escuridão estrutural tem precedência sobre o abrigo).
    structurally_dark = bool(_DARK_TAGS & tags)
    naturally_dark = (period in DARK_PERIODS) or structurally_dark
    dark = naturally_dark and (structurally_dark or not sheltered)
    if dark and _has_light_source(player):
        return {
            "dark": False,
            "natural_dark": True,
            "lit": True,
            "perception_mod": 0,
            "combat_mod": 0,
            "label": "iluminado pela sua luz",
        }
    if dark:
        return {
            "dark": True,
            "natural_dark": True,
            "lit": False,
            "perception_mod": DARK_PERCEPTION_PENALTY,
            "combat_mod": DARK_COMBAT_PENALTY,
            "label": "escuridão",
        }
    return {
        "dark": False,
        "natural_dark": False,
        "lit": True,
        "perception_mod": 0,
        "combat_mod": 0,
        "label": "claro",
    }


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

        gdef = ((load_json_data("weather.json") or {}).get("global_events") or {}).get(
            g.get("id", ""), {}
        )
        state = {
            **state,
            **{
                k: v
                for k, v in gdef.items()
                if k
                in (
                    "perception_mod",
                    "combat_attack_mod",
                    "dot_outdoor",
                    "rest_block",
                    "travel_cost_extra",
                    "label",
                )
            },
        }
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
    world["weather_global"] = {"id": event_id, "periods_left": int(gdef.get("duration_periods", 2))}
    return world, gdef.get("desc", gdef.get("label", event_id))


# ---------------------------------------------------------------------------
# Fase 6.4 — Encontros sistêmicos: detecção, tipo, armadilha, rastro
# ---------------------------------------------------------------------------
_ENCOUNTER_TYPES_LOW = (("combat", 50), ("track", 30), ("social", 20))
_ENCOUNTER_TYPES_HIGH = (("combat", 60), ("trap", 20), ("social", 10), ("track", 10))
TRAP_DODGE_XP = 25


def detection_check(player: dict, danger: int, rng=None, perception_mod: int = 0) -> dict:
    """Fase 6.4 (R1): d20 + mod WIS (+ bônus racial de save WIS) vs DC 8+2×danger.
    Percebeu -> vantagem (embosca); falhou -> surpreendido (inimigo age antes).
    Fase 6.5: `perception_mod` do clima (neblina -3 etc.) soma na rolagem."""
    import random as _random

    rng = rng or _random
    from combat_mechanics import actor_mods, player_passives

    # spec conflito-01: percepção usa Mente (Virtude) via ponte actor_mods -> "wis".
    wis = actor_mods(player).get("wis", 0)
    save_b = player.get("racial_save_bonus") or {}
    wis += int(save_b.get("mente", save_b.get("wis", 0)) or 0)
    # spec itens-vivos-e-luz (R2): passiva `perception` de classe/habilidade/item
    perc = sum(
        int(pe.get("delta", 0) or 0)
        for pe in player_passives(player)
        if pe.get("trigger") == "perception"
    )
    roll = rng.randint(1, 20) + wis + perc + int(perception_mod or 0)
    dc = 8 + 2 * max(1, min(4, int(danger or 1)))
    return {"perceived": roll >= dc, "roll": roll, "dc": dc}


def roll_encounter_type(danger: int, rng=None) -> str:
    """Fase 6.4 (R2): nem todo perigo é combate. Distribuição por danger."""
    import random as _random

    rng = rng or _random
    table = _ENCOUNTER_TYPES_LOW if int(danger or 1) <= 2 else _ENCOUNTER_TYPES_HIGH
    kinds, weights = zip(*table)
    return rng.choices(list(kinds), weights=list(weights), k=1)[0]


def resolve_trap(
    player: dict, loc: dict, danger: int, rng=None, *, helper: dict | None = None
) -> tuple:
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
    is_v4 = p.get("vitalidade") is not None or isinstance(p.get("virtudes"), dict)
    if is_v4:
        from services.conflict_resolution import virtude_value

        virtue = {
            "str": "forca",
            "dex": "agilidade",
            "con": "corpo",
            "int": "mente",
            "wis": "mente",
            "cha": "carisma",
        }.get(stat, stat)
        mod = virtude_value(p, virtue)
    else:
        mod = cm.attr_mods(p.get("attributes", {})).get(stat, 0)
    mod += int((p.get("racial_save_bonus") or {}).get(stat, 0) or 0)
    roll = rng.randint(1, 20) + mod
    logs = [f"⚠ {trap['name']}! {trap.get('desc', '')}"]
    if roll >= dc:
        from progression import grant_xp

        p, lvl_events = grant_xp(p, TRAP_DODGE_XP)
        logs.append(
            f"{p.get('name', 'O herói')} ESQUIVA (save {roll} vs CD {dc}) — +{TRAP_DODGE_XP} XP."
        )
        return p, logs, {"trap": trap, "dodged": True, "level_up_events": lvl_events}
    if is_v4:
        gamedata.sync_vitality(p)
        from services.conflict_damage import resolve_damage_and_wounds

        # Conversão categórica da escala d6 antiga para a escala Vitalidade 6–16.
        dmg = {1: 2, 2: 3, 3: 4, 4: 5}[danger]
        dres = resolve_damage_and_wounds(
            p,
            damage_base=dmg,
            damage_type=str(trap.get("damage_type") or "perfurante"),
            directed_region=None,
            rng=rng,
        )
        logs.append(
            f"{p.get('name', 'O herói')} falha (save {roll} vs CD {dc}): "
            f"{dmg} de dano (Vitalidade {p['vitalidade']}); " + "; ".join(dres["log"])
        )
        from services import death_flow

        terminal_triggered = False
        stabilization = None
        if death_flow.should_trigger_last_stand(p):
            terminal_triggered = True
            death_flow.trigger_last_stand(p)
            death_flow.enter_terminal_state(p)
            stabilization = death_flow.attempt_stabilization(
                p,
                helper,
                rng=rng,
                has_kit=bool((helper or {}).get("has_kit")),
                is_medico="medic" in str((helper or {}).get("class_name", "")).lower(),
            )
            if p.get("estado_terminal") and not stabilization.get("dead"):
                stabilization = death_flow.attempt_stabilization(
                    p,
                    helper,
                    rng=rng,
                    has_kit=bool((helper or {}).get("has_kit")),
                    is_medico="medic" in str((helper or {}).get("class_name", "")).lower(),
                )
            logs.append(
                stabilization.get("log")
                or stabilization.get("cause")
                or "A armadilha dispara o fluxo terminal."
            )
        trap_result = {
            "trap": trap,
            "dodged": False,
            "level_up_events": [],
            "terminal_triggered": terminal_triggered,
            "dead": bool(p.get("dead")),
            "stabilization": stabilization,
        }
    else:
        dmg, detail = cm.roll_dice_numeric(f"{danger}d6")
        p["hp"] = max(0, int(p.get("hp", 0)) - dmg)
        logs.append(
            f"{p.get('name', 'O herói')} falha (save {roll} vs CD {dc}): "
            f"{dmg} de dano (HP {p['hp']}) [{detail}]"
        )
    cond = trap.get("condition")
    if cond and not p.get("dead"):
        p.setdefault("active_conditions", [])
        logs.append(cm.apply_condition(p, dict(cond)))
    if is_v4:
        return p, logs, trap_result
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
        note = (
            f"Rastros frescos de {entry.get('name', 'algo grande')} — "
            "você grava os sinais na memória (Codex atualizado)."
        )
    treasure = bool((rng or __import__("random")).randint(0, 1))
    if treasure:
        note += (
            " Entre as marcas, sinais de carga abandonada — algo valioso ficou para trás por perto."
        )
    return bk, note, treasure


def clock_label(world: dict, calendar: dict | None = None) -> str:
    """Relógio exibido. SPEC-307 R13: com calendário v2 (modo `on`) ou vista `world["date"]`
    fresca, mostra a data de Valoria; senão o texto legado `Dia N · Período` (byte a byte)."""
    c = world.get("world_clock") or {}
    period = c.get("period", PERIODS[0])
    from services import world_calendar

    date_text = world_calendar.clock_date_label(world, calendar)
    if date_text:
        return f"{date_text} · {period}"
    return f"Dia {c.get('day', 1)} · {period}"


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
