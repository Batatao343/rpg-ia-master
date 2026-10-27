"""services/scene_cards.py - Cartas de Cena, Objetivo com regra e Relogio do Abismo (SPEC-331).

A LLM so ESCOLHE ids de um catalogo fechado (`data/combat/cartas_de_cena.json`); quem
decide e quem aplica sao as Cartas (gramatica da SPEC-330) e este modulo. ZERO LLM aqui.

Flag `RPG_SCENE_CARDS=off|shadow|on` (padrao `off`, invalido tambem vira `off`):
`off` = comportamento anterior byte a byte; `shadow` = a LLM escolhe e o motor registra
(log) o que DISPARARIA, sem mudar a cena nem o estado; `on` = efeito real.

Estado da cena (persistido junto de `combat["scene"]`; ausente em save antigo = sem cartas):
    scene["cartas_de_cena"]  list[str]   0-2 ids do catalogo
    scene["objetivo"]        dict        {tipo, alvo?, n?}   (ausente = derrotar_todos)
    scene["cena_estado"]     dict        {fired: [ids "uma_vez"], clock: int}
    scene["objetivo_resultado"] "cumprido" | "falhou"  (so quando o objetivo resolveu)
"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path
from typing import Any

from observability.telemetry import log_event as _log_event

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "combat" / "cartas_de_cena.json"

MAX_CARTAS = 2
MAX_OPCOES_PROMPT = 12
ABYSS_CLOCK_START = 5  # D6 (dono): Relogio do Abismo a partir da rodada 5
ABYSS_CLOCK_HARD_CAP = 12  # nenhum conflito passa da rodada 12
OBJETIVOS = (
    "derrotar_todos",
    "sobreviver_n_rodadas",
    "proteger",
    "alcancar_zona",
    "destruir_objeto",
    "interromper_ritual",
    "capturar_vivo",
)
MOMENTOS = ("inicio_rodada", "fim_rodada", "a_cada_n_rodadas")
ESCOPOS = ("todos", "herois", "inimigos")
FILTROS = ("visivel", "zona_inicial")
ACOES = ("entropia", "deslocar", "objeto_cai")
TEMP_PREFIX = "cena_"


# ==========================================================================
# Flag
# ==========================================================================
def mode() -> str:
    raw = str(os.getenv("RPG_SCENE_CARDS", "off") or "off").strip().lower()
    return raw if raw in ("off", "shadow", "on") else "off"


def active() -> bool:
    return mode() == "on"


def enabled() -> bool:
    """`shadow` ou `on`: a preparacao pede as escolhas a LLM."""
    return mode() != "off"


# ==========================================================================
# Catalogo + validador
# ==========================================================================
_CATALOG: dict[str, dict] | None = None


def _fold(text: Any) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return "".join(c for c in s if not unicodedata.combining(c))


def validate_catalog(data: dict) -> list[str]:
    """Erros do catalogo (vazio = ok). Reusa a gramatica da SPEC-330 nos efeitos."""
    from services import card_effects as fx

    errs: list[str] = []
    cartas = data.get("cartas")
    if not isinstance(cartas, list) or not cartas:
        return ["catalogo: `cartas` precisa ser lista nao vazia"]
    seen: set[str] = set()
    regions = _known_regions()
    for c in cartas:
        cid = str(c.get("id") or "")
        where = f"carta {cid or '?'}"
        if not cid or cid in seen:
            errs.append(f"{where}: id ausente ou duplicado")
        seen.add(cid)
        for key in ("nome", "pressagio", "sabor"):
            if not str(c.get(key) or "").strip():
                errs.append(f"{where}: `{key}` obrigatorio")
        if c.get("quando") not in MOMENTOS:
            errs.append(f"{where}: quando {c.get('quando')!r} fora do catalogo")
        if c.get("quando") == "a_cada_n_rodadas" and not _is_int(c.get("n"), 2):
            errs.append(f"{where}: a_cada_n_rodadas exige n >= 2")
        if not _is_int(c.get("desde", 1), 1):
            errs.append(f"{where}: desde exige inteiro >= 1")
        if c.get("escopo", "todos") not in ESCOPOS:
            errs.append(f"{where}: escopo fora do catalogo")
        if c.get("filtro") is not None and c.get("filtro") not in FILTROS:
            errs.append(f"{where}: filtro fora do catalogo")
        for reg in c.get("regioes") or []:
            if regions and reg not in regions:
                errs.append(f"{where}: regiao {reg!r} desconhecida")
        efeitos, acoes = c.get("efeitos") or [], c.get("acoes") or []
        if not efeitos and not acoes:
            errs.append(f"{where}: sem efeitos nem acoes")
        for i, eff in enumerate(efeitos):
            errs += fx.validate_effect(eff, f"{where} efeitos[{i}]")
            if eff.get("kind") == "aplicar_condicao":
                from combat_mechanics import NAMED_CONDITIONS

                if _fold(eff.get("condicao")) not in NAMED_CONDITIONS:
                    errs.append(f"{where}: condicao {eff.get('condicao')!r} desconhecida")
        for i, act in enumerate(acoes):
            if act.get("tipo") not in ACOES:
                errs.append(f"{where}: acoes[{i}].tipo fora do catalogo")
    return errs


def _is_int(v: Any, minimum: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= minimum


def _known_regions() -> set[str]:
    try:
        import gamedata

        return {
            str(loc.get("region_id"))
            for loc in gamedata.WORLD_MAP.get("locations", [])
            if loc.get("region_id")
        }
    except Exception:  # noqa: BLE001 - validador degrada: sem mapa nao checa regiao
        _log_event("combat", "scene_cards_regions_unavailable", level="warning")
        return set()


def catalog() -> dict[str, dict]:
    global _CATALOG
    if _CATALOG is None:
        try:
            data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _log_event("combat", "scene_cards_catalog_unavailable", level="warning")
            data = {}
        _CATALOG = {c["id"]: c for c in data.get("cartas") or [] if c.get("id")}
    return _CATALOG


def reload() -> None:
    global _CATALOG
    _CATALOG = None


# ==========================================================================
# Elegibilidade (R2) e saneamento das escolhas da LLM
# ==========================================================================
def location_profile(location: Any) -> tuple[str, set[str]]:
    """(region_id, tags casefold) do local; nome, id ou dict. Desconhecido = ('', {})."""
    import gamedata

    if isinstance(location, dict):
        loc = location
    else:
        loc = gamedata.get_location(str(location or "")) or gamedata.find_location_by_name(
            str(location or "")
        )
    tags = {_fold(t) for t in (loc.get("tags") or [])}
    return str(loc.get("region_id") or ""), tags


def eligible(location: Any, tags: Any = None) -> list[dict]:
    """Cartas do catalogo cujo recorte de regiao E de tags bate com o local."""
    region, loc_tags = location_profile(location)
    if tags:
        loc_tags = loc_tags | {_fold(t) for t in tags}
    out = []
    for card in catalog().values():
        regs = card.get("regioes") or []
        ctags = {_fold(t) for t in card.get("tags") or []}
        if regs and region not in regs:
            continue
        if ctags and not (ctags & loc_tags):
            continue
        out.append(card)
    return out


def prompt_options(location: Any, tags: Any = None) -> list[dict]:
    """Ate 12 opcoes {id, nome, sabor} - nenhum numero de efeito vai ao prompt (R8)."""
    return [
        {"id": c["id"], "nome": c["nome"], "sabor": c["sabor"]}
        for c in eligible(location, tags)[:MAX_OPCOES_PROMPT]
    ]


def sanitize_choices(ids: Any, location: Any, tags: Any = None) -> list[str]:
    """R2: so ids elegiveis do catalogo; o resto e descartado com log. Max 2, sem repetir."""
    allowed = {c["id"] for c in eligible(location, tags)}
    out: list[str] = []
    for raw in ids or []:
        cid = str(raw or "").strip()
        if cid in allowed and cid not in out:
            out.append(cid)
        else:
            _log_event("combat", "scene_card_dropped", level="warning", reason="not_eligible")
    return out[:MAX_CARTAS]


def sanitize_objective(raw: Any, scene: dict) -> dict:
    """R4: objetivo do catalogo fechado; invalido ou ausente = `derrotar_todos`."""
    default = {"tipo": "derrotar_todos"}
    if raw is None:
        return default
    data = raw if isinstance(raw, dict) else getattr(raw, "model_dump", lambda: {})()
    tipo = str(data.get("tipo") or "").strip()
    if tipo not in OBJETIVOS or tipo == "derrotar_todos":
        if tipo not in OBJETIVOS and tipo:
            _log_event("combat", "scene_objective_dropped", level="warning", reason="unknown_type")
        return default
    alvo = str(data.get("alvo") or "").strip() or None
    n = data.get("n")
    n = n if isinstance(n, int) and not isinstance(n, bool) else None
    enemy_ids = [str(e.get("id") or e.get("name")) for e in scene.get("enemies") or []]
    ally_ids = [str(a.get("id") or a.get("name")) for a in (scene.get("npcs") or [])] + [
        str(p) for p in (scene.get("allies") or [])
    ]
    zone_ids = [str(z.get("id")) for z in scene.get("zones") or []]
    object_ids = [str(o.get("id")) for o in scene.get("objects") or []]
    if tipo == "sobreviver_n_rodadas":
        return {"tipo": tipo, "n": min(8, max(2, n or 5))}
    if tipo == "proteger":
        if alvo in ally_ids:
            return {"tipo": tipo, "alvo": alvo}
    elif tipo == "alcancar_zona":
        if alvo in zone_ids:
            return {"tipo": tipo, "alvo": alvo}
    elif tipo == "destruir_objeto":
        if alvo in object_ids:
            return {"tipo": tipo, "alvo": alvo}
    elif tipo == "interromper_ritual":
        target = alvo if alvo in enemy_ids else (enemy_ids[0] if enemy_ids else None)
        if target:
            return {"tipo": tipo, "alvo": target, "n": min(6, max(2, n or 4))}
    elif tipo == "capturar_vivo":
        return {"tipo": tipo}
    _log_event("combat", "scene_objective_dropped", level="warning", reason="invalid_target")
    return default


def attach(
    scene: dict,
    choices: Any,
    objetivo: Any,
    location: Any,
    tags: Any = None,
    allies: Any = None,
) -> dict:
    """Aplica as escolhas ja validadas a cena (modo `on`); `shadow` so registra."""
    ids = sanitize_choices(choices, location, tags)
    obj = sanitize_objective(objetivo, {**scene, "allies": list(allies or [])})
    if mode() == "shadow":
        _log_event(
            "combat",
            "scene_cards_shadow",
            level="info",
            cards=len(ids),
            objective=obj["tipo"],
        )
        return scene
    if mode() == "on":
        scene["cartas_de_cena"] = ids
        if obj["tipo"] != "derrotar_todos":
            scene["objetivo"] = obj
    return scene


# ==========================================================================
# Disparo (R1/R3)
# ==========================================================================
def _state(scene: dict) -> dict:
    return scene.setdefault("cena_estado", {"fired": [], "clock": 0})


def scene_cards_of(scene: dict) -> list[dict]:
    cat = catalog()
    return [cat[i] for i in scene.get("cartas_de_cena") or [] if i in cat]


def _due(card: dict, rnd: int, momento: str, st: dict) -> bool:
    desde = int(card.get("desde", 1) or 1)
    if rnd < desde:
        return False
    if card.get("uma_vez") and card["id"] in st.get("fired", []):
        return False
    q = card.get("quando")
    if q == "a_cada_n_rodadas":
        return momento == "fim_rodada" and (rnd - desde + 1) % int(card.get("n") or 2) == 0
    return q == momento


def forecast(scene: dict, rnd: int) -> list[dict]:
    """R3: cartas que disparam na rodada `rnd`, no mesmo contrato publico do Pressagio
    (so texto: id, nome, pressagio, quando). Nunca revela numeros."""
    if not enabled():
        return []
    st = _state(scene) if scene.get("cartas_de_cena") else {"fired": []}
    out = []
    for card in scene_cards_of(scene):
        if any(_due(card, rnd, m, st) for m in ("inicio_rodada", "fim_rodada")):
            out.append(
                {
                    "id": card["id"],
                    "nome": card["nome"],
                    "pressagio": card["pressagio"],
                    "quando": card["quando"],
                    "rodada": rnd,
                }
            )
    return out


def _alive(actor: dict | None) -> bool:
    from services import card_effects as fx

    return fx._alive(actor)


def _targets(ctx, card: dict) -> list[str]:
    sides = ctx.sides or {}
    heroes = list(sides.get("hero", [])) + list(sides.get("ally", []))
    enemies = list(sides.get("enemy", []))
    scope = card.get("escopo", "todos")
    ids = heroes + enemies if scope == "todos" else heroes if scope == "herois" else enemies
    zones = ctx.scene.get("zones") or [{}]
    first_zone = zones[0].get("id")
    out = []
    for aid in sorted(set(ids)):
        actor = ctx.actors_by_id.get(aid)
        if not _alive(actor):
            continue
        pos = (ctx.scene.get("positions") or {}).get(aid) or {}
        flt = card.get("filtro")
        if flt == "visivel" and pos.get("ocultacao", "visivel") != "visivel":
            continue
        if flt == "zona_inicial" and pos.get("zone_id") != first_zone:
            continue
        out.append(aid)
    return out


def _gain_entropy(actor: dict, n: int) -> int:
    if "entropy" not in actor and not actor.get("is_player"):
        return 0
    before = int(actor.get("entropy", 0) or 0)
    mx = int(actor.get("max_entropy", 0) or 0)
    actor["entropy"] = min(mx, before + n) if mx > 0 else before + n
    return int(actor["entropy"]) - before


def _fire_card(ctx, card: dict, out: dict) -> bool:
    """Aplica UMA Carta de Cena. False = nada aconteceu (ex.: sem objeto para cair)."""
    import combat_mechanics as cm
    from services import card_effects as fx
    from services import conflict_scene as cs

    scene = ctx.scene
    targets = _targets(ctx, card)
    logs = out.setdefault("logs", [])
    nome = card["nome"]
    for act in card.get("acoes") or []:
        if act.get("tipo") == "objeto_cai":
            obj = next((o for o in cs.visible_objects(scene)), None)
            real = next(
                (o for o in scene.get("objects", []) if o.get("id") == (obj or {}).get("id")), None
            )
            if real is None:
                return False
            real["destroyed"] = True
            logs.append(f"{nome}: {real.get('name') or real.get('id')} desaba sobre a cena.")
    if not targets and not card.get("acoes"):
        return False
    logs.append(f"{nome}: {card['sabor']}")
    src = {"id": card["id"], "name": nome}
    for aid in targets:
        actor = ctx.actors_by_id[aid]
        for eff in card.get("efeitos") or []:
            if eff.get("se") and not fx.check(eff["se"], ctx, aid, None):
                continue
            if eff.get("kind") == "aplicar_condicao":
                cond = cm.parse_condition(str(eff.get("condicao")), source=card["id"])
                cond["duration"] = max(1, int(eff.get("duracao", 1) or 1))
                logs.append(cm.apply_condition(actor, cond))
            else:
                fx.apply_effect(ctx, {**eff, "alvo": "eu"}, aid, aid, out, card=src)
        for act in card.get("acoes") or []:
            if act.get("tipo") == "entropia":
                gained = _gain_entropy(actor, int(act.get("n", 1) or 1))
                if gained:
                    logs.append(
                        f"{actor.get('name', aid)} sente o Abismo mais perto (+{gained} Entropia)."
                    )
            elif act.get("tipo") == "deslocar":
                res = cs.move_distance(scene, aid, str(act.get("direcao") or "afastar"))
                if res.get("log"):
                    logs.append(res["log"])
    fx.drain(out, ctx=ctx)
    return True


def tick(ctx, rnd: int, momento: str = "fim_rodada", out: dict | None = None) -> list[dict]:
    """Dispara as Cartas de Cena devidas em `momento` da rodada `rnd`. Determinista.
    `shadow` so registra; `off` nao faz nada. Devolve eventos {event, card_id, rodada}."""
    out = out if out is not None else {}
    if not enabled() or not ctx.scene.get("cartas_de_cena"):
        return []
    st = _state(ctx.scene)
    events: list[dict] = []
    for card in scene_cards_of(ctx.scene):
        if not _due(card, rnd, momento, st):
            continue
        if mode() == "shadow":
            _log_event("combat", "scene_card_shadow", level="info", card_id=card["id"], rnd=rnd)
            continue
        if _fire_card(ctx, card, out):
            events.append({"event": "scene_card_fired", "card_id": card["id"], "rodada": rnd})
        if card.get("uma_vez"):
            st.setdefault("fired", []).append(card["id"])
    if events:
        out.setdefault("scene_cards", []).extend(events)
    return events


# ==========================================================================
# Relogio do Abismo (R7)
# ==========================================================================
def _peso(card: dict) -> int:
    total = len(card.get("acoes") or [])
    for eff in card.get("efeitos") or []:
        total += int(eff.get("valor", eff.get("duracao", 1)) or 1)
    return total


def strongest(scene: dict) -> dict | None:
    cards = scene_cards_of(scene)
    return max(cards, key=lambda c: (_peso(c), c["id"])) if cards else None


def abyss_clock(ctx, rnd: int, out: dict | None = None) -> bool:
    """A partir da rodada R0=5: +1 Entropia a todos e a Carta de Cena mais forte dispara
    de novo. `shadow` so registra. True se o Relogio agiu nesta rodada."""
    out = out if out is not None else {}
    if not enabled() or rnd < ABYSS_CLOCK_START:
        return False
    if mode() == "shadow":
        _log_event("combat", "abyss_clock_shadow", level="info", rnd=rnd)
        return False
    logs = out.setdefault("logs", [])
    logs.append("O Abismo se aproxima.")
    sides = ctx.sides or {}
    for aid in sorted(set(sum((list(v) for v in sides.values()), []))):
        actor = ctx.actors_by_id.get(aid)
        if _alive(actor):
            _gain_entropy(actor, 1)
    card = strongest(ctx.scene)
    if card is not None:
        _fire_card(ctx, card, out)
    _state(ctx.scene)["clock"] = rnd
    out["abyss_clock"] = rnd
    return True


def clock_hard_stop(ctx, rnd: int, out: dict) -> bool:
    """Rede final: na rodada 12 os hostis recuam diante do Abismo (mesmo caminho do
    `_stalemate_guard`: `fled`), entao `combat_should_end` fecha o conflito."""
    if not active() or rnd < ABYSS_CLOCK_HARD_CAP:
        return False
    stopped = False
    for eid in (ctx.sides or {}).get("enemy", []):
        enemy = ctx.actors_by_id.get(eid)
        if _alive(enemy):
            enemy["fled"] = True
            enemy["status"] = "fugiu"
            stopped = True
    if stopped:
        out.setdefault("logs", []).append(
            "O Abismo chega ao campo e os inimigos recuam diante dele."
        )
        out["abyss_clock_hard_stop"] = rnd
    return stopped


# ==========================================================================
# Objetivo com regra (R4/R5)
# ==========================================================================
def _inactive(h: dict | None) -> bool:
    if not h:
        return True
    return bool(
        h.get("dead")
        or h.get("fled")
        or h.get("surrendered")
        or not h.get("conscious", True)
        or h.get("incapacitated")
        or h.get("estado_terminal")
    )


def _name(actor: dict | None, fallback: str) -> str:
    return str((actor or {}).get("name") or fallback)


def check_objective(ctx, rnd: int | None = None) -> str | None:
    """Motivo (pt-BR) se o Objetivo da cena resolveu NESTA rodada, senao None.
    Grava `scene["objetivo_resultado"]`. Sem objetivo = `derrotar_todos` (fluxo de sempre)."""
    scene = ctx.scene
    obj = scene.get("objetivo")
    if not active() or not isinstance(obj, dict) or obj.get("tipo") in (None, "derrotar_todos"):
        return None
    if scene.get("objetivo_resultado"):
        return None
    from services import conflict_scene as cs

    rnd = rnd if rnd is not None else cs.tactical_round(scene)
    tipo, alvo, n = obj["tipo"], obj.get("alvo"), int(obj.get("n") or 0)
    actors = ctx.actors_by_id
    sides = ctx.sides or {}
    hostiles = [actors[i] for i in sides.get("enemy", []) if i in actors]
    all_down = bool(hostiles) and all(_inactive(h) for h in hostiles)
    player = next((a for a in actors.values() if a.get("is_player")), None)

    def done(ok: bool, reason: str) -> str:
        scene["objetivo_resultado"] = "cumprido" if ok else "falhou"
        _log_event("combat", "scene_objective_resolved", level="info", tipo=tipo, ok=ok)
        return reason

    if tipo == "sobreviver_n_rodadas":
        if player is not None and not _inactive(player) and rnd >= n:
            return done(True, f"Vocês resistiram por {n} rodadas.")
        if all_down:
            return done(True, "Os inimigos se foram antes do tempo.")
    elif tipo == "proteger":
        target = actors.get(str(alvo))
        if target is None or _inactive(target):
            return done(False, f"{_name(target, 'O protegido')} não resistiu.")
        if all_down:
            return done(True, f"{_name(target, 'O protegido')} está a salvo.")
    elif tipo == "alcancar_zona":
        pos = (scene.get("positions") or {}).get(
            next((k for k, v in actors.items() if v is player), "")
        )
        if pos and pos.get("zone_id") == alvo:
            return done(True, "Vocês alcançaram o lugar que buscavam.")
    elif tipo == "destruir_objeto":
        o = next((x for x in scene.get("objects", []) if x.get("id") == alvo), None)
        if o is not None and o.get("destroyed"):
            return done(True, f"{o.get('name') or alvo} foi destruído.")
    elif tipo == "interromper_ritual":
        target = actors.get(str(alvo))
        if _inactive(target):
            return done(True, "O ritual foi interrompido.")
        if rnd >= n:
            return done(False, "O ritual se completa.")
    elif tipo == "capturar_vivo" and all_down:
        killed = any(h.get("dead") or h.get("status") == "morto" for h in hostiles)
        fled = any(h.get("fled") for h in hostiles)
        return done(
            not killed and not fled,
            "O inimigo foi capturado."
            if not killed and not fled
            else "Ninguém sobrou para ser capturado.",
        )
    return None


# ==========================================================================
# Objeto vira Carta na mao (R6) - exige SPEC-328 `on`
# ==========================================================================
def _object_card(obj: dict, it: dict) -> dict | None:
    eff = it.get("effect") or {}
    params = eff.get("params") if isinstance(eff.get("params"), dict) else {}
    kind = eff.get("kind")
    if kind == "damage" and int(params.get("amount", 0) or 0) > 0:
        efeito = {
            "kind": "dano",
            "dano_base": int(params["amount"]),
            "dano_tipo": str(params.get("damage_type") or "impactante"),
        }
    elif kind == "apply_condition" and params.get("condition"):
        efeito = {
            "kind": "aplicar_condicao",
            "condicao": str(params["condition"]),
            "duracao": max(1, int(params.get("duration", 1) or 1)),
        }
    else:
        return None
    digest = hashlib.sha1(
        json.dumps([obj.get("id"), it.get("label"), efeito], sort_keys=True).encode()
    ).hexdigest()[:8]
    label = str(it.get("label") or "usar")
    oname = str(obj.get("name") or obj.get("id"))
    return {
        "id": f"{TEMP_PREFIX}{obj.get('id')}_{digest}",
        "name": f"{label.capitalize()} ({oname})",
        "tipo": "ativa",
        "origem": "cena-331",
        "cena": True,
        "custo_entropia": 0,
        "custo_folego": 1,
        "frequencia": "cena",
        "palavras_chave": {"exaurir": True},
        "efeito": efeito,
        "descricao": f"{oname}: {label}. Some da mão quando você sai de perto.",
        "tier": 1,
        "level_req": 1,
        "apex": False,
    }


def object_cards(scene: dict, zone_id: str | None) -> list[dict]:
    """Cartas temporarias das interacoes dos objetos na zona `zone_id` (R6)."""
    out = []
    for obj in scene.get("objects", []):
        if obj.get("destroyed") or (obj.get("secret") and not obj.get("discovered")):
            continue
        if obj.get("zone_id") and zone_id and obj.get("zone_id") != zone_id:
            continue
        if obj.get("uses_remaining") is not None and int(obj["uses_remaining"]) <= 0:
            continue
        for it in obj.get("interactions") or []:
            card = _object_card(obj, it)
            if card is not None:
                out.append(card)
    return out


def sync_hand(scene: dict, piles: dict | None, player_id: str) -> list[str]:
    """R6: poe/tira as Cartas de objeto da mao conforme a zona do jogador. Registra as
    Cartas no catalogo em memoria (reconstruidas a cada sync -> sobrevive a reload).
    So age com SPEC-331 `on` E SPEC-328 `on`. Devolve os ids na mao apos o sync."""
    from services import card_piles, cards

    if not (active() and card_piles.mode() == "on") or not isinstance(piles, dict):
        return []
    pos = (scene.get("positions") or {}).get(player_id) or {}
    wanted = object_cards(scene, pos.get("zone_id"))
    catalog_ = cards._load_cards()
    for c in wanted:
        catalog_[c["id"]] = c
    wanted_ids = [c["id"] for c in wanted]
    for pile in ("compra", "descarte"):  # temporarias nunca viram baralho
        piles[pile] = [i for i in piles.get(pile, []) if not str(i).startswith(TEMP_PREFIX)]
    piles["mao"] = [
        i for i in piles.get("mao", []) if not str(i).startswith(TEMP_PREFIX) or i in wanted_ids
    ]
    for cid in wanted_ids:
        if cid not in piles["mao"] and cid not in piles.get("exaurida", []):
            piles["mao"].append(cid)
    return [i for i in piles["mao"] if str(i).startswith(TEMP_PREFIX)]
