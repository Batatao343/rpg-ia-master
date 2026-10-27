"""services/card_effects.py — gramática de efeitos e palavras-chave de Valoria (SPEC-330).

Intérprete FECHADO e determinístico de efeitos de Carta. Zero LLM: a IA só narra.

Formato (R1/R2): a Carta pode ter ``efeitos: list[Efeito]`` além do ``efeito``
legado. ``normalize(card)`` devolve sempre a lista; o catálogo
(``services.cards``) deriva ``efeito`` (o efeito principal) de ``efeitos``
quando só a lista existe, então todo consumidor legado continua funcionando.

``Efeito = {kind, alvo?, valor?, ..., quando?, se?, escala?, chamado?}``:

- ``quando`` (R3): gatilho fechado em ``GATILHOS``; ausente = ``ao_jogar``.
  Efeito com outro gatilho não roda ao jogar: ARMA na cena e responde a
  ``fire(...)`` até o fim do conflito (Cartas passivas ficam sempre armadas).
- ``se`` (R4): dict de condições fechadas em ``CONDICOES`` (todas precisam valer).
- ``escala``: ``{por, fator, max}`` soma ao valor a partir de um contador fechado.
- ``chamado: k`` — palavra-chave **Chamado**: o efeito só vale com Entropia ≥ k.

Palavras-chave (R5/R6) moram em dois lugares: as que são EFEITO viram ``kind``
(``rachadura``, ``torpor``, ``sangria``, ``vigilia``, ``marca_do_abismo``); as que
são PROPRIEDADE da Carta ficam em ``palavras_chave`` (``sacrificio``,
``interromper``, ``exaurir``, ``guardar``, ``eco``, ``ressoar``, ``fardo``,
``vazao``). O glossário (``data/cards/_glossario.json``) é a fonte única do texto.

Ordem de resolução (R11): custos (Sacrifício) → ``se`` → efeitos na ordem da
lista → gatilhos disparados numa fila FIFO com profundidade máxima 3 (anti-loop,
mesmo princípio de ``services/rule_engine.py``).

Os kinds legados delegam aos ramos atuais de ``conflict_turn`` — sem reescrever
o que já funciona. O Grupo B (pilhas) depende da SPEC-328: validado aqui, mas o
efeito no motor só registra ``pendente_pilhas`` até as pilhas existirem.
"""

from __future__ import annotations

import contextvars
import copy
import json
import math
import os
import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field

import gamedata

# --------------------------------------------------------------------------
# Vocabulário fechado
# --------------------------------------------------------------------------
GATILHO_PADRAO = "ao_jogar"
GATILHOS = frozenset(
    {
        "ao_jogar",
        "inicio_rodada",
        "fim_rodada",
        "ao_comprar",
        "ao_descartar",
        "ao_exaurir",
        "ao_receber_dano",
        "ao_derrubar",
        "ao_aliado_sofrer",
        "ao_pressagio_frustrado",
        "ao_entrar_carga",
    }
)

# nome -> tipo do argumento ("cond" = nome de condição, "int", "pct", "tipo",
# "classe", "bool", "tag", "familia").
CONDICOES: dict[str, str] = {
    "alvo_tem": "cond",
    "eu_tenho": "cond",
    "entropia_min": "int",
    "vitalidade_max_pct": "pct",
    "cartas_jogadas_na_rodada_min": "int",
    "ultima_carta_tipo": "tipo",
    "ultima_carta_postura": "classe",
    "engajado": "bool",
    "zona_tem_objeto": "tag",
    "alvo_familia": "familia",
}

ALVOS = frozenset({"alvo", "eu", "inimigos", "aliados"})
ESCALA_POR = frozenset(
    {"entropia", "carga", "cartas_jogadas_na_rodada", "ferimentos_alvo", "condicoes_alvo"}
)

# Palavras-chave que são EFEITO (kind) — Grupo A.
KEYWORD_KINDS = frozenset({"rachadura", "torpor", "sangria", "vigilia", "marca_do_abismo"})
# Efeitos novos que não exigem pilhas (R7).
SCENE_KINDS = frozenset({"copiar_ultima", "mover_alvo_zona", "revelar"})
# Efeitos novos que exigem as pilhas da SPEC-328 (R7, Grupo B).
PILE_KINDS = frozenset({"comprar", "descartar", "ganhar_folego", "gerar_carta", "purgar_fardo"})
NEW_KINDS = KEYWORD_KINDS | SCENE_KINDS | PILE_KINDS

# Interpretados por este módulo (não pelos ramos legados de conflict_turn).
HOSTILE_KINDS = frozenset(
    {"rachadura", "torpor", "sangria", "marca_do_abismo", "mover_alvo_zona", "revelar"}
)
SELF_KINDS = frozenset({"vigilia", "copiar_ultima"}) | PILE_KINDS

# Palavras-chave que são PROPRIEDADE da Carta (``palavras_chave``) -> tipo do valor.
CARD_KEYWORDS: dict[str, str] = {
    "sacrificio": "int",
    "interromper": "bool",
    "exaurir": "bool",
    "guardar": "bool",
    "eco": "bool",
    "ressoar": "int",
    "fardo": "bool",
    "vazao": "bool",
}
KEYWORDS_GRUPO_A = ("rachadura", "torpor", "sangria", "vigilia", "marca_do_abismo")
KEYWORDS_GRUPO_A += ("interromper", "sacrificio", "chamado")
KEYWORDS_GRUPO_B = ("exaurir", "guardar", "eco", "ressoar", "fardo", "vazao")
KEYWORDS = KEYWORDS_GRUPO_A + KEYWORDS_GRUPO_B  # as 14 de Valoria (v1)

REVELAR_CAMPOS = frozenset({"resistencias", "cartas", "vitalidade", "intencao"})

# Listas de evento que o turno (`conflict_turn`) devolve e a rodada agrega.
TURN_EVENT_KEYS = (
    "keywords",
    "gatilhos",
    "gatilhos_descartados",
    "pendente_pilhas",
    "revelacoes",
    "extra_hits",
    "class_mechanics",
)

MAX_DEPTH = 3  # R11: profundidade máxima da fila de gatilhos

# Rachadura/Torpor: ±25 % de dano (R5).
RACHADURA_PCT = 25
TORPOR_PCT = -25


def _legacy_kinds() -> frozenset:
    from services.cards import CARD_EFFECT_KINDS

    return CARD_EFFECT_KINDS


def all_kinds() -> frozenset:
    """Catálogo fechado completo: os 31 kinds legados + os novos (R7)."""
    return _legacy_kinds() | NEW_KINDS


def _fold(text) -> str:
    raw = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "_", raw.strip().lower())


# --------------------------------------------------------------------------
# R1 — normalização
# --------------------------------------------------------------------------
def normalize(card: dict | None) -> list[dict]:
    """Lista de efeitos da Carta (cópias). ``efeito`` legado vira ``[efeito]``."""
    if not card:
        return []
    raw = card.get("efeitos")
    if isinstance(raw, list) and raw:
        return [copy.deepcopy(e) for e in raw if isinstance(e, dict)]
    eff = card.get("efeito")
    return [copy.deepcopy(eff)] if isinstance(eff, dict) and eff else []


def gatilho(eff: dict) -> str:
    return str(eff.get("quando") or GATILHO_PADRAO)


def _is_plain_play(eff: dict) -> bool:
    return gatilho(eff) == GATILHO_PADRAO and not eff.get("se") and not eff.get("chamado")


def primary_index(card: dict | None) -> int | None:
    """Índice do efeito PRINCIPAL: o que dirige a resolução legada (rolagem de
    ataque, suporte). Primeiro efeito incondicional ``ao_jogar`` de kind legado;
    senão o primeiro incondicional ``ao_jogar`` de qualquer kind."""
    effects = normalize(card)
    legacy = _legacy_kinds()
    for i, eff in enumerate(effects):
        if _is_plain_play(eff) and str(eff.get("kind")) in legacy:
            return i
    for i, eff in enumerate(effects):
        if _is_plain_play(eff):
            return i
    return None


def primary_effect(card: dict | None) -> dict | None:
    idx = primary_index(card)
    return None if idx is None else normalize(card)[idx]


def extra_effects(card: dict | None) -> list[dict]:
    """Efeitos ``ao_jogar`` além do principal, na ordem da lista."""
    idx = primary_index(card)
    return [e for i, e in enumerate(normalize(card)) if i != idx and gatilho(e) == GATILHO_PADRAO]


def triggered_effects(card: dict | None) -> list[dict]:
    """Efeitos com gatilho diferente de ``ao_jogar`` (armam ao jogar)."""
    return [e for e in normalize(card) if gatilho(e) != GATILHO_PADRAO]


def keywords(card: dict | None) -> dict:
    """Palavras-chave de propriedade da Carta (``palavras_chave``)."""
    raw = (card or {}).get("palavras_chave") or {}
    if isinstance(raw, list):
        return {str(k): True for k in raw}
    return dict(raw) if isinstance(raw, dict) else {}


def materialize(card: dict) -> dict:
    """Garante ``efeito`` (principal) numa Carta que só declara ``efeitos``.
    Usado pelo catálogo no carregamento; não muta a Carta de entrada."""
    if card.get("efeito") or not isinstance(card.get("efeitos"), list):
        return card
    out = dict(card)
    prim = primary_effect(card)
    if prim is not None:
        out["efeito"] = prim
    return out


# --------------------------------------------------------------------------
# Contexto de rodada + fila de gatilhos (R11)
# --------------------------------------------------------------------------
@dataclass
class Ctx:
    scene: dict
    actors_by_id: dict
    sides: dict | None = None
    rng: object = None
    # SPEC-329: presságios congelados da rodada (`actor_id -> [intent]`) e o cursor de
    # quantas ações de cada inimigo já foram consumidas. Só com RPG_ENEMY_INTENT=on.
    pressagios: dict | None = None
    intent_cursor: dict | None = None
    # SPEC-325: modo não-letal do golpe declarado pelo ator do turno corrente.
    nonlethal: str = ""
    nonlethal_actor: str | None = None
    queue: deque = field(default_factory=deque)
    depth: int = 0
    draining: bool = False
    dropped: int = 0


_CTX: contextvars.ContextVar[Ctx | None] = contextvars.ContextVar("card_effects_ctx", default=None)


def bind(scene, actors_by_id, sides=None, *, rng=None, pressagios=None, intent_cursor=None):
    """Liga o contexto da rodada (``run_round``). Devolve o token p/ ``unbind``.
    ``pressagios``/``intent_cursor`` são os de ``run_round`` (SPEC-329)."""
    return _CTX.set(
        Ctx(
            scene=scene,
            actors_by_id=actors_by_id,
            sides=sides,
            rng=rng,
            pressagios=pressagios,
            intent_cursor=intent_cursor,
        )
    )


def unbind(token) -> None:
    _CTX.reset(token)


def current() -> Ctx | None:
    return _CTX.get()


def _ctx_for(scene, actors_by_id, sides=None, rng=None) -> Ctx:
    ctx = current()
    if ctx is not None and (ctx.actors_by_id is actors_by_id or ctx.scene is scene):
        return ctx
    return Ctx(scene=scene, actors_by_id=actors_by_id, sides=sides, rng=rng)


# --------------------------------------------------------------------------
# Leitura de ficha
# --------------------------------------------------------------------------
def _name(actor: dict | None, fallback: str = "") -> str:
    return str((actor or {}).get("name") or fallback or "Alvo")


def _alive(actor: dict | None) -> bool:
    if not actor:
        return False
    return not (
        actor.get("dead")
        or actor.get("estado_terminal")
        or actor.get("incapacitated")
        or actor.get("fled")
    )


def is_down(actor: dict | None) -> bool:
    """Caiu (morto, terminal, incapacitado, Última Ação pendente) ou atordoado."""
    if not actor:
        return True
    import combat_mechanics as cm

    return (
        (not _alive(actor))
        or bool(actor.get("last_stand_pending"))
        or cm.has_control(actor, "stun")
    )


_CONTROL_BY_NAME = {
    "atordoado": "stun",
    "dominado": "stun",
    "enredado": "root",
    "enraizado": "root",
    "medo": "fear",
    "amedrontado": "fear",
    "silenciado": "silence",
}


def known_condition_names() -> frozenset:
    """Catálogo fechado do argumento de ``alvo_tem``/``eu_tenho`` (R2/R4): condições
    nomeadas, controles, ``marca``/``sangramento`` e as palavras-chave de efeito."""
    import combat_mechanics as cm

    return frozenset(
        {_fold(n) for n in cm.NAMED_CONDITIONS}
        | set(_CONTROL_BY_NAME)
        | {"marca", "sangramento"}
        | set(KEYWORD_KINDS)
    )


def has_fallen(actor: dict | None) -> bool:
    """CAIU de verdade (R3 `ao_derrubar`, Interromper): morto, Estado Terminal,
    incapacitado, fugiu ou Última Ação pendente. Atordoar NÃO é cair."""
    if not actor:
        return True
    return (not _alive(actor)) or bool(actor.get("last_stand_pending"))


def has_condition(actor: dict | None, name: str) -> bool:
    want = _fold(name)
    aliases = {want}
    control = _CONTROL_BY_NAME
    for c in (actor or {}).get("active_conditions", []) or []:
        if _fold(c.get("name")) in aliases or _fold(c.get("keyword")) in aliases:
            return True
        if c.get("control") and control.get(want) == c.get("control"):
            return True
        if want == "marca" and c.get("control") == "marca":
            return True
    return False


def _played(actor: dict) -> list[dict]:
    return actor.setdefault("_cartas_rodada", [])


def record_play(actor: dict, card: dict, target_id: str | None) -> None:
    """Registra a Carta jogada nesta rodada (condições ``ultima_carta_*``, Eco)."""
    _played(actor).append(
        {
            "card_id": card.get("id"),
            "tipo": card.get("tipo"),
            "classe": card.get("classe"),
            "target_id": target_id,
        }
    )


def reset_round(actor: dict) -> None:
    actor["_cartas_rodada"] = []


def _side_of(actor_id: str, sides: dict | None) -> str | None:
    for side, ids in (sides or {}).items():
        if actor_id in ids:
            return "heroes" if side in ("hero", "ally") else side
    return None


def _opponents(ctx: Ctx, actor_id: str) -> list[str]:
    mine = _side_of(actor_id, ctx.sides)
    if mine is None:
        actor = ctx.actors_by_id.get(actor_id) or {}
        mine = "heroes" if actor.get("is_player") or actor.get("player") else "enemy"
    out = []
    for aid, a in ctx.actors_by_id.items():
        side = _side_of(aid, ctx.sides)
        if side is None:
            side = "heroes" if a.get("is_player") or a.get("player") else "enemy"
        if side != mine and _alive(a):
            out.append(aid)
    return sorted(out)


def _allies(ctx: Ctx, actor_id: str) -> list[str]:
    opp = set(_opponents(ctx, actor_id))
    return sorted(aid for aid, a in ctx.actors_by_id.items() if aid not in opp and _alive(a))


# --------------------------------------------------------------------------
# R4 — condições
# --------------------------------------------------------------------------
def check(se: dict | None, ctx: Ctx, actor_id: str, target_id: str | None) -> bool:
    """True se TODAS as condições de ``se`` valem (vocabulário fechado)."""
    if not se:
        return True
    actor = ctx.actors_by_id.get(actor_id) or {}
    target = ctx.actors_by_id.get(target_id) if target_id else None
    for key, arg in se.items():
        if not _check_one(key, arg, ctx, actor, actor_id, target):
            return False
    return True


def _check_one(key, arg, ctx: Ctx, actor: dict, actor_id: str, target: dict | None) -> bool:
    if key == "alvo_tem":
        return has_condition(target, arg)
    if key == "eu_tenho":
        return has_condition(actor, arg)
    if key == "entropia_min":
        return int(actor.get("entropy", 0) or 0) >= int(arg)
    if key == "vitalidade_max_pct":
        vmax = int(actor.get("max_vitalidade", 0) or 0)
        return vmax > 0 and int(actor.get("vitalidade", 0) or 0) * 100 <= int(arg) * vmax
    if key == "cartas_jogadas_na_rodada_min":
        return len(actor.get("_cartas_rodada") or []) >= int(arg)
    if key == "ultima_carta_tipo":
        last = (actor.get("_cartas_rodada") or [None])[-1]
        return bool(last) and last.get("tipo") == arg
    if key == "ultima_carta_postura":
        last = (actor.get("_cartas_rodada") or [None])[-1]
        return bool(last) and _fold(last.get("classe")) == _fold(arg)
    if key == "engajado":
        pos = (ctx.scene.get("positions") or {}).get(actor_id) or {}
        return bool(pos.get("engaged_with")) == bool(arg)
    if key == "zona_tem_objeto":
        zone = ((ctx.scene.get("positions") or {}).get(actor_id) or {}).get("zone_id")
        for obj in ctx.scene.get("objects") or []:
            if obj.get("destroyed") or (obj.get("secret") and not obj.get("discovered")):
                continue
            if obj.get("zone_id") and zone and obj.get("zone_id") != zone:
                continue
            tags = {_fold(t) for t in obj.get("tags") or []} | {_fold(obj.get("id"))}
            if _fold(arg) in tags:
                return True
        return False
    if key == "alvo_familia":
        if not target:
            return False
        fams = {
            _fold(target.get(k))
            for k in ("familia", "family", "arquetipo", "type")
            if target.get(k)
        }
        return _fold(arg) in fams
    return False


# --------------------------------------------------------------------------
# Valor + escala
# --------------------------------------------------------------------------
def base_value(eff: dict) -> int:
    for key in ("valor", "dano_base", "n"):
        if eff.get(key) is not None:
            try:
                return max(0, int(eff.get(key) or 0))
            except (TypeError, ValueError):
                return 0
    return 1


def scaled_value(eff: dict, ctx: Ctx | None, actor: dict, target: dict | None) -> int:
    value = base_value(eff)
    esc = eff.get("escala")
    if not isinstance(esc, dict):
        return value
    por = esc.get("por")
    count = 0
    if por == "entropia":
        count = int(actor.get("entropy", 0) or 0)
    elif por == "carga":
        count = int(actor.get("abyss_charge", 0) or 0)
    elif por == "cartas_jogadas_na_rodada":
        count = len(actor.get("_cartas_rodada") or [])
    elif por == "ferimentos_alvo":
        fer = (target or {}).get("ferimentos") or {}
        count = sum(len(fer.get(c) or []) for c in ("leve", "grave", "critico"))
    elif por == "condicoes_alvo":
        count = len((target or {}).get("active_conditions") or [])
    bonus = int(math.floor(float(esc.get("fator", 1) or 0) * count))
    if esc.get("max") is not None:
        bonus = min(bonus, int(esc["max"]))
    return max(0, value + bonus)


# --------------------------------------------------------------------------
# Palavras-chave de efeito (Grupo A) — condições estruturadas
# --------------------------------------------------------------------------
def rachadura_condition(n: int, source: str = "") -> dict:
    return {
        "name": "Rachadura",
        "keyword": "rachadura",
        "dot": 0,
        "duration": max(1, int(n)),
        "stat": "dano_recebido_pct",
        "delta": RACHADURA_PCT,
        "source": source,
    }


def torpor_condition(n: int, source: str = "") -> dict:
    return {
        "name": "Torpor",
        "keyword": "torpor",
        "dot": 0,
        "duration": max(1, int(n)),
        "stat": "dano_causado_pct",
        "delta": TORPOR_PCT,
        "source": source,
    }


def sangria_condition(n: int, source: str = "") -> dict:
    n = max(1, int(n))
    return {
        "name": "Sangria",
        "keyword": "sangria",
        "dot": n,
        "duration": n,
        "decai": 1,
        "damage_type": "cortante",
        "source": source,
    }


def add_vigilia(actor: dict, n: int, source: str = "") -> str:
    """Vigília N: Proteção que NÃO se dissipa no fim da rodada; acumula e só
    some quando consumida pelo dano."""
    n = max(0, int(n))
    for c in actor.setdefault("active_conditions", []):
        if c.get("keyword") == "vigilia":
            c["delta"] = int(c.get("delta", 0) or 0) + n
            return f"{_name(actor)}: Vigília sobe para {c['delta']}."
    actor["active_conditions"].append(
        {
            "name": "Vigília",
            "keyword": "vigilia",
            "dot": 0,
            "duration": 1,
            "stat": "vigilia",
            "delta": n,
            "persistente": True,
            "source": source,
        }
    )
    return f"{_name(actor)}: ganha Vigília {n}."


def absorb_vigilia(target: dict, dano: int) -> int:
    """Consome Vigília contra ``dano``; devolve quanto absorveu."""
    absorbed = 0
    survivors = []
    for c in target.get("active_conditions", []) or []:
        if c.get("keyword") == "vigilia" and dano - absorbed > 0:
            pool = int(c.get("delta", 0) or 0)
            take = min(pool, dano - absorbed)
            absorbed += take
            c["delta"] = pool - take
            if c["delta"] <= 0:
                continue
        survivors.append(c)
    if absorbed:
        target["active_conditions"] = survivors
    return absorbed


def damage_pct(entity: dict | None, which: str) -> int:
    """Soma de ``dano_recebido_pct`` (``taken``) ou ``dano_causado_pct`` (``dealt``)."""
    if not entity:
        return 0
    import combat_mechanics as cm

    stat = "dano_recebido_pct" if which == "taken" else "dano_causado_pct"
    return int(cm.combat_modifiers(entity).get(stat, 0) or 0)


def apply_pct(dano: int, pct: int) -> int:
    """Arredonda meio-para-cima: 4×1,25=5; 3×1,25=4; 4×0,75=3; 3×0,75=2."""
    if not pct or dano <= 0:
        return dano
    return max(0, (int(dano) * (100 + int(pct)) + 50) // 100)


def marca_abismo_condition(x: int, source: str = "", source_actor_id: str = "") -> dict:
    return {
        "name": "Marca do Abismo",
        "keyword": "marca_do_abismo",
        "dot": 0,
        "duration": 3,
        "control": "marca",
        "abismo_bonus": max(0, int(x)),
        "source": source,
        "source_actor_id": source_actor_id,
    }


def consume_marca_abismo(attacker: dict | None, target: dict | None, out: dict | None) -> int:
    """Próximo dano no alvo Marcado: +X de dano e +1 Entropia para quem acertou.
    Consome a Marca. Devolve o bônus de dano (0 se não havia Marca)."""
    if not target:
        return 0
    conds = target.get("active_conditions") or []
    mark = next((c for c in conds if c.get("keyword") == "marca_do_abismo"), None)
    if mark is None:
        return 0
    conds.remove(mark)
    bonus = int(mark.get("abismo_bonus", 0) or 0)
    if attacker is not None and attacker.get("max_entropy") is not None:
        cap = int(attacker.get("max_entropy", 0) or 0)
        attacker["entropy"] = min(cap, int(attacker.get("entropy", 0) or 0) + 1)
    if out is not None:
        out.setdefault("logs", []).append(
            f"A Marca do Abismo em {_name(target)} se abre: +{bonus} de dano"
            f" e +1 Entropia para {_name(attacker)}."
        )
        out.setdefault("keywords", []).append(
            {"keyword": "marca_do_abismo", "target": target.get("id"), "bonus": bonus}
        )
    return bonus


# --------------------------------------------------------------------------
# Aplicação de um efeito (sem rolagem: a rolagem é do efeito principal)
# --------------------------------------------------------------------------
def _targets_for(eff: dict, ctx: Ctx, actor_id: str, target_id: str | None) -> list[str]:
    alvo = str(eff.get("alvo") or "")
    kind = str(eff.get("kind") or "")
    if alvo == "eu" or (not alvo and kind in SELF_KINDS):
        return [actor_id]
    if not alvo and kind in _support_kinds():
        # Suporte sem alvo explícito nunca atinge o inimigo declarado.
        if target_id and target_id in ctx.actors_by_id:
            if target_id not in _opponents(ctx, actor_id):
                return [target_id]
        return [actor_id]
    if alvo == "inimigos":
        return _opponents(ctx, actor_id)
    if alvo == "aliados":
        return _allies(ctx, actor_id)
    opp = _opponents(ctx, actor_id)
    if target_id and target_id in opp:
        return [target_id]
    # Hostil sem alvo explícito numa Carta de suporte (alvo = si/aliado) nunca
    # cai no conjurador nem no aliado: vai para o 1º oponente.
    return opp[:1]


def _support_kinds() -> set:
    from services import conflict_turn as ct

    return set(ct._SUPPORT_EFFECTS)


def apply_effect(
    ctx: Ctx,
    eff: dict,
    actor_id: str,
    target_id: str | None,
    out: dict,
    *,
    card: dict | None = None,
) -> None:
    """Resolve UM efeito já validado (``se`` checado antes). Kinds legados
    delegam aos ramos de ``conflict_turn``; os novos são resolvidos aqui."""
    actor = ctx.actors_by_id.get(actor_id) or {}
    card = card or {}
    for tid in _targets_for(eff, ctx, actor_id, target_id):
        target = ctx.actors_by_id.get(tid)
        if target is None:
            continue
        _apply_on(ctx, eff, actor, actor_id, target, tid, out, card)


def _apply_on(ctx, eff, actor, actor_id, target, tid, out, card) -> None:
    import combat_mechanics as cm
    from services import conflict_turn as ct

    kind = str(eff.get("kind") or "")
    value = scaled_value(eff, ctx, actor, target)
    source = str(card.get("id") or card.get("name") or kind)
    logs = out.setdefault("logs", [])

    def _kw(name: str, **extra) -> None:
        out.setdefault("keywords", []).append(
            {"keyword": name, "actor_id": actor_id, "target_id": tid, **extra}
        )

    if kind == "rachadura":
        logs.append(cm.apply_condition(target, rachadura_condition(value, source)))
        _kw("rachadura", n=value)
    elif kind == "torpor":
        logs.append(cm.apply_condition(target, torpor_condition(value, source)))
        _kw("torpor", n=value)
    elif kind == "sangria":
        logs.append(cm.apply_condition(target, sangria_condition(value, source)))
        _kw("sangria", n=value)
    elif kind == "vigilia":
        logs.append(add_vigilia(target, value, source))
        _kw("vigilia", n=value)
    elif kind == "marca_do_abismo":
        logs.append(cm.apply_condition(target, marca_abismo_condition(value, source, actor_id)))
        _kw("marca_do_abismo", n=value)
    elif kind == "mover_alvo_zona":
        from services import conflict_scene as cs

        res = cs.move_distance(ctx.scene, tid, str(eff.get("direcao") or "afastar"))
        logs.append(res.get("log") or res.get("error", ""))
    elif kind == "revelar":
        campo = str(eff.get("campo") or "resistencias")
        revealed = target.setdefault("_revelado", [])
        if campo not in revealed:
            revealed.append(campo)
        out.setdefault("revelacoes", []).append({"target_id": tid, "campo": campo})
        logs.append(f"{_name(actor)} lê {_name(target)}: {campo} à mostra.")
    elif kind == "copiar_ultima":
        _copy_last(ctx, actor, actor_id, out)
    elif kind in PILE_KINDS:
        # SPEC-328 (pilhas) ainda não pousou: registra, sem efeito no motor.
        out.setdefault("pendente_pilhas", []).append(
            {"kind": kind, "actor_id": actor_id, "valor": value, "card_id": card.get("id")}
        )
    elif kind == "dano":
        dtype = str(eff.get("dano_tipo") or "cortante")
        dano = value + consume_marca_abismo(actor, target, out)
        from services.conflict_damage import resolve_damage_and_wounds

        dres = resolve_damage_and_wounds(
            target,
            damage_base=max(0, dano),
            damage_type=dtype,
            dealt_pct=damage_pct(actor, "dealt"),
            rng=ctx.rng,
        )
        logs.append("; ".join(dres["log"]))
        out.setdefault("extra_hits", []).append(
            {"actor_id": actor_id, "target_id": tid, "dano_final": dres.get("dano_final", 0)}
        )
        # Mesmo desfecho de um golpe: Lacaio cai, full-flow arma a Última Ação.
        from services import conflict_orchestrator as orch

        nonlethal = ctx.nonlethal if ctx.nonlethal_actor == actor_id else ""
        orch._check_terminal(
            target,
            tid,
            _ensure_turn_out(out),
            damage_applied=True,
            nonlethal=nonlethal,
            by=actor_id,
        )
        on_damage(ctx, tid, actor_id, int(dres.get("dano_final", 0) or 0), out)
    elif kind in ct._SUPPORT_EFFECTS:
        step = ct.TurnStep(kind="card", card_id=card.get("id"), target_id=tid)
        ct._resolve_support_card(
            ctx.scene, actor, actor_id, ctx.actors_by_id, step, {**card, "efeito": eff}, out
        )
    elif kind in ct._ATTACK_EFFECTS:
        ct._apply_attack_card_effect(
            ctx.scene, actor, actor_id, target, tid, {**card, "efeito": eff}, out
        )
    else:
        logs.append(f"{card.get('name', source)}: efeito sem resolução fora de turno ({kind!r}).")


def _ensure_turn_out(out: dict) -> dict:
    out.setdefault("terminal", [])
    out.setdefault("deaths", [])
    out.setdefault("logs", [])
    return out


def _copy_last(ctx: Ctx, actor: dict, actor_id: str, out: dict) -> None:
    from services import cards

    last = (actor.get("_cartas_rodada") or [None])[-1]
    if not last:
        out.setdefault("logs", []).append(f"{_name(actor)}: nenhuma Carta para repetir.")
        return
    card = cards.get_card(str(last.get("card_id") or "")) or {}
    effects = [
        e
        for e in normalize(card)
        if gatilho(e) == GATILHO_PADRAO and str(e.get("kind")) != "copiar_ultima"
    ]
    out.setdefault("logs", []).append(f"{_name(actor)} repete {card.get('name', 'a Carta')}.")
    for eff in effects:
        if check(eff.get("se"), ctx, actor_id, last.get("target_id")) and _chamado_ok(eff, actor):
            apply_effect(ctx, eff, actor_id, last.get("target_id"), out, card=card)


def _chamado_ok(eff: dict, actor: dict) -> bool:
    k = eff.get("chamado")
    return k is None or int(actor.get("entropy", 0) or 0) >= int(k)


# --------------------------------------------------------------------------
# R11 — custos → se → efeitos → gatilhos
# --------------------------------------------------------------------------
def pay_costs(ctx: Ctx, card: dict, actor_id: str, out: dict) -> None:
    """Custos adicionais da Carta (palavra-chave **Sacrifício N**): paga N de
    Vitalidade ANTES dos efeitos, pelo mesmo caminho do auto-dano (gatilho
    ``on_self_harm`` da Postura)."""
    n = int(keywords(card).get("sacrificio", 0) or 0)
    actor = ctx.actors_by_id.get(actor_id)
    if n <= 0 or actor is None:
        return
    from services import conflict_orchestrator as orch
    from services.conflict_damage import sacrifice_vitality

    before = int(actor.get("vitalidade", 0) or 0)
    sacrifice_vitality(actor, n)
    actor["_self_harmed_round"] = True
    out.setdefault("logs", []).append(
        f"{_name(actor)} paga Sacrifício {n} (Vit {actor.get('vitalidade', 0)})."
    )
    out.setdefault("keywords", []).append({"keyword": "sacrificio", "actor_id": actor_id, "n": n})
    out.setdefault("class_mechanics", []).append(
        {
            "kind": "self_harm",
            "amount": n,
            "vitality_delta": int(actor.get("vitalidade", 0) or 0) - before,
        }
    )
    if actor.get("is_player"):
        orch._entropy_event(actor, {"kind": "on_self_harm", "amount": n}, out)
    out.setdefault("terminal", [])
    orch._check_terminal(actor, actor_id, out, damage_applied=True)


def resolve_extras(ctx: Ctx, card: dict, actor_id: str, target_id: str | None, out: dict) -> None:
    """Depois do efeito principal: efeitos adicionais ``ao_jogar`` na ordem da
    lista (cada um com seu ``se``/Chamado), arma os gatilhos da Carta e aplica
    Interromper. Gatilhos disparados no caminho entram na fila FIFO."""
    actor = ctx.actors_by_id.get(actor_id) or {}
    for eff in extra_effects(card):
        if not _chamado_ok(eff, actor):
            continue
        if not check(eff.get("se"), ctx, actor_id, target_id):
            continue
        if eff.get("chamado") is not None:
            out.setdefault("keywords", []).append(
                {"keyword": "chamado", "actor_id": actor_id, "k": int(eff["chamado"])}
            )
        apply_effect(ctx, eff, actor_id, target_id, out, card=card)
    arm(ctx, card, actor_id)
    if keywords(card).get("interromper") and target_id:
        interrupt(ctx, actor_id, target_id, out)
    drain(out, ctx=ctx)


def resolve_card(ctx: Ctx, card: dict, actor_id: str, target_id: str | None, out: dict) -> list:
    """Resolve a Carta inteira SEM rolagem (cartas de efeito puro, testes,
    Cartas de Cena). Ordem R11: custos → efeitos (principal + extras) → gatilhos.
    Devolve os eventos de palavra-chave produzidos."""
    before = len(out.get("keywords") or [])
    pay_costs(ctx, card, actor_id, out)
    actor = ctx.actors_by_id.get(actor_id) or {}
    prim = primary_effect(card)
    if prim is not None and check(prim.get("se"), ctx, actor_id, target_id):
        apply_effect(ctx, prim, actor_id, target_id, out, card=card)
    resolve_extras(ctx, card, actor_id, target_id, out)
    record_play(actor, card, target_id)
    return list((out.get("keywords") or [])[before:])


# --------------------------------------------------------------------------
# Interromper (SPEC-329)
# --------------------------------------------------------------------------
ATTACK_INTENT_TIPOS = frozenset({"ataque", "ataque_multiplo"})


def pending_intent(ctx: Ctx, actor_id: str) -> dict | None:
    """Próximo presságio AINDA NÃO executado do ator nesta rodada (SPEC-329:
    ``combat["pressagios"]`` congelado + cursor de ``run_round``)."""
    lst = (ctx.pressagios or {}).get(actor_id) or []
    i = int((ctx.intent_cursor or {}).get(actor_id, 0) or 0)
    return lst[i] if i < len(lst) and isinstance(lst[i], dict) else None


def interrupt(ctx: Ctx, actor_id: str, target_id: str, out: dict) -> bool:
    """**Interromper**: se o alvo tem presságio de ataque pendente e caiu/foi
    atordoado, o presságio conta como frustrado POR este ator: marca
    ``interrompido_por`` (o ``run_round`` registra o frustrado com ``via``) e dispara
    ``ao_pressagio_frustrado`` agora."""
    intent = pending_intent(ctx, target_id)
    target = ctx.actors_by_id.get(target_id)
    if intent is None or intent.get("tipo") not in ATTACK_INTENT_TIPOS:
        return False
    if intent.get("interrompido_por"):
        return False
    if not has_fallen(target):
        # Atordoar só nega a 1ª ação da rodada (SPEC-295: controle no meio da
        # rodada vale para a próxima); ação extra pendente segue de pé.
        stunned = is_down(target)
        first = int((ctx.intent_cursor or {}).get(target_id, 0) or 0) == 0
        if not (stunned and first):
            return False
    intent["interrompido_por"] = actor_id
    out.setdefault("keywords", []).append(
        {"keyword": "interromper", "actor_id": actor_id, "target_id": target_id}
    )
    fire("ao_pressagio_frustrado", sujeito_id=actor_id, alvo_id=target_id, out=out, ctx=ctx)
    return True


def on_damage(ctx: Ctx, victim_id: str, source_id: str | None, amount: int, out: dict) -> None:
    """Dano real em ``victim_id``: ``ao_receber_dano`` para a vítima e
    ``ao_aliado_sofrer`` para os aliados dela. Fontes: golpe (``_hit_events``), efeito
    extra, dano disparado por gatilho e DoT. Disparo aninhado ganha profundidade +1
    (o teto 3 da fila corta laços)."""
    if amount <= 0 or victim_id not in ctx.actors_by_id:
        return
    fire("ao_receber_dano", sujeito_id=victim_id, alvo_id=source_id, out=out, ctx=ctx, valor=amount)
    for ally_id in _allies(ctx, victim_id):
        if ally_id != victim_id:
            fire("ao_aliado_sofrer", sujeito_id=ally_id, alvo_id=victim_id, out=out, ctx=ctx)


# --------------------------------------------------------------------------
# Gatilhos (R3) — armar, disparar, drenar
# --------------------------------------------------------------------------
def arm(ctx: Ctx, card: dict, actor_id: str) -> None:
    """Efeitos com ``quando`` ≠ ``ao_jogar`` armam na cena até o fim do conflito."""
    effs = triggered_effects(card)
    if not effs:
        return
    armed = ctx.scene.setdefault("gatilhos_armados", [])
    for eff in effs:
        armed.append({"owner_id": actor_id, "card_id": card.get("id"), "efeito": eff})


def _passive_listeners(actor: dict) -> list[tuple[dict, dict]]:
    from services import cards

    ids = list(actor.get("known_cards") or []) + list(actor.get("cartas") or [])
    out = []
    for cid in ids:
        card = cards.get_card(str(cid))
        if not card or card.get("tipo") not in ("passiva", "virtude"):
            continue
        for eff in triggered_effects(card):
            out.append((card, eff))
    return out


def listeners(ctx: Ctx, gatilho_: str, sujeito_id: str) -> list[tuple[dict, dict]]:
    actor = ctx.actors_by_id.get(sujeito_id)
    if actor is None:
        return []
    from services import cards

    found = []
    for entry in ctx.scene.get("gatilhos_armados") or []:
        if entry.get("owner_id") == sujeito_id and gatilho(entry.get("efeito") or {}) == gatilho_:
            card = cards.get_card(str(entry.get("card_id") or "")) or {"id": entry.get("card_id")}
            found.append((card, entry["efeito"]))
    for card, eff in _passive_listeners(actor):
        if gatilho(eff) == gatilho_:
            found.append((card, eff))
    return found


def fire(
    gatilho_: str,
    *,
    sujeito_id: str,
    out: dict,
    alvo_id: str | None = None,
    ctx: Ctx | None = None,
    **kw,
) -> None:
    """Enfileira o gatilho ``gatilho_`` para os ouvintes de ``sujeito_id``.
    Sem contexto ligado (fora de ``run_round``) é no-op. Fila FIFO; disparos
    aninhados ganham profundidade +1; acima de ``MAX_DEPTH`` são descartados."""
    ctx = ctx or current()
    if ctx is None or gatilho_ not in GATILHOS:
        return
    depth = ctx.depth + 1
    if depth > MAX_DEPTH:
        ctx.dropped += 1
        out.setdefault("gatilhos_descartados", []).append(
            {"gatilho": gatilho_, "sujeito_id": sujeito_id, "profundidade": depth}
        )
        return
    ctx.queue.append((gatilho_, sujeito_id, alvo_id, depth, out, kw))
    if not ctx.draining:
        drain(out, ctx=ctx)


def drain(out: dict | None = None, *, ctx: Ctx | None = None) -> None:
    ctx = ctx or current()
    if ctx is None or ctx.draining:
        return
    ctx.draining = True
    try:
        while ctx.queue:
            gat, sujeito_id, alvo_id, depth, ev_out, _kw = ctx.queue.popleft()
            ctx.depth = depth
            for card, eff in listeners(ctx, gat, sujeito_id):
                actor = ctx.actors_by_id.get(sujeito_id) or {}
                if not _alive(actor) and gat != "ao_receber_dano":
                    continue
                if not _chamado_ok(eff, actor) or not check(
                    eff.get("se"), ctx, sujeito_id, alvo_id
                ):
                    continue
                ev_out.setdefault("gatilhos", []).append(
                    {
                        "gatilho": gat,
                        "sujeito_id": sujeito_id,
                        "card_id": card.get("id"),
                        "kind": eff.get("kind"),
                        "profundidade": depth,
                    }
                )
                apply_effect(ctx, eff, sujeito_id, alvo_id, ev_out, card=card)
    finally:
        ctx.depth = 0
        ctx.draining = False


# --------------------------------------------------------------------------
# R10 — glossário
# --------------------------------------------------------------------------
_GLOSSARIO: dict | None = None
_ORCAMENTO: dict | None = None


def _load_json(name: str) -> dict:
    with open(os.path.join(gamedata.DATA_DIR, "cards", name), encoding="utf-8") as f:
        return json.load(f)


def glossary() -> dict[str, dict]:
    """``palavra-chave -> {nome, grupo, regra, sabor, parametro}`` (fonte única)."""
    global _GLOSSARIO
    if _GLOSSARIO is None:
        _GLOSSARIO = _load_json("_glossario.json").get("palavras_chave") or {}
    return _GLOSSARIO


def glossary_for_prompt(keys) -> str:
    """Bloco curto para o prompt do narrador: só as palavras-chave em jogo."""
    g = glossary()
    lines = [f"- {g[k]['nome']}: {g[k]['regra']}" for k in keys if k in g]
    return "\n".join(lines)


def card_keyword_ids(card: dict) -> list[str]:
    """Palavras-chave presentes na Carta (efeito e propriedade), sem repetição."""
    found: list[str] = []
    for eff in normalize(card):
        kind = str(eff.get("kind") or "")
        if kind in KEYWORD_KINDS and kind not in found:
            found.append(kind)
        if eff.get("chamado") is not None and "chamado" not in found:
            found.append("chamado")
    for key in keywords(card):
        if key in CARD_KEYWORDS and key not in found:
            found.append(key)
    return found


# --------------------------------------------------------------------------
# R8 — texto gerado
# --------------------------------------------------------------------------
_STAT_LABEL = {
    "buff_defesa": "Defesa",
    "buff_acerto": "Acerto",
    "buff_dano": "Dano",
    "buff_cura": "Cura",
    "buff_dot": "dano contínuo",
    "buff_iniciativa": "Iniciativa",
    "buff_esquiva": "Esquiva",
    "perception": "Percepção",
}
_STAGE_LABEL = {
    "bonus_dano_por_estagio": ("Dano", "Força"),
    "bonus_percepcao_por_estagio": ("Percepção", "Mente"),
    "bonus_vitalidade_por_estagio": ("Vitalidade máxima", "Corpo"),
    "bonus_iniciativa_por_estagio": ("Iniciativa", "Agilidade"),
    "bonus_social_por_estagio": ("testes sociais", "Carisma"),
    "bonus_esquiva_por_estagio": ("Esquiva", "Agilidade"),
    "bonus_cura_por_estagio": ("Cura", "Mente"),
}
_GATILHO_LABEL = {
    "inicio_rodada": "No início da rodada",
    "fim_rodada": "No fim da rodada",
    "ao_comprar": "Ao ser comprada",
    "ao_descartar": "Ao ser descartada",
    "ao_exaurir": "Ao ser exaurida",
    "ao_receber_dano": "Ao receber dano",
    "ao_derrubar": "Ao derrubar um alvo",
    "ao_aliado_sofrer": "Quando um aliado sofre dano",
    "ao_pressagio_frustrado": "Ao frustrar um presságio",
    "ao_entrar_carga": "Ao ganhar Carga do Abismo",
}
_ALVO_LABEL = {"eu": "em você", "inimigos": "em todos os inimigos", "aliados": "nos aliados"}
_CONDICAO_LABEL = {
    "exposto": "Exposto",
    "amedrontado": "Medo",
    "atordoado": "Atordoado",
    "enraizado": "Enredado",
    "desmoralizado": "Desmoralizado",
    "cego": "Cego",
    "desarmado_risco": "Desarme",
    "silenciado": "Silêncio",
}
_ESCALA_LABEL = {
    "entropia": "Entropia",
    "carga": "Carga do Abismo",
    "cartas_jogadas_na_rodada": "Carta jogada nesta rodada",
    "ferimentos_alvo": "Ferimento do alvo",
    "condicoes_alvo": "condição no alvo",
}


def _kw_bold(key: str, n=None) -> str:
    nome = (glossary().get(key) or {}).get("nome") or key.capitalize()
    return f"**{nome}**" + (f" {n}" if n is not None else "")


def _rodadas(n: int) -> str:
    return f"{n} rodada" + ("" if n == 1 else "s")


def _amount_text(eff: dict) -> str:
    if eff.get("dano_base") is not None:
        return str(int(eff["dano_base"]))
    if eff.get("valor") is not None:
        return str(int(eff["valor"]))
    if eff.get("formula"):
        return str(eff["formula"])
    return "1"


def _effect_text(eff: dict) -> str:
    kind = str(eff.get("kind") or "")
    amt = _amount_text(eff)
    dur = int(eff.get("duracao", eff.get("duration", 0)) or 0)
    por = f" por {_rodadas(dur)}" if dur > 1 else ""
    if kind == "dano":
        tipo = f" {eff['dano_tipo']}" if eff.get("dano_tipo") else ""
        return f"Causa {amt} de dano{tipo}"
    if kind == "contra_ataque":
        return f"Revida com {amt} de dano"
    if kind == "dot":
        tipo = f" {eff['dano_tipo']}" if eff.get("dano_tipo") else ""
        return f"Causa {amt} de dano{tipo} por rodada durante {_rodadas(max(1, dur))}"
    if kind == "cura":
        return f"Recupera {amt} de Vitalidade"
    if kind == "estabilizar":
        return "Estabiliza um aliado em Estado Terminal"
    if kind == "protecao":
        return f"Concede {amt} de Proteção{por}"
    if kind == "taunt":
        return f"Provoca o alvo{por}: ele precisa atacar você"
    if kind == "marca":
        return f"Marca o alvo{por}: ataques contra ele têm Vantagem"
    if kind == "empurrao":
        return "Empurra o alvo para longe"
    if kind == "reposicionar":
        return "Reposiciona o alvo no campo"
    if kind == "esconder":
        return "Some das vistas: fica Escondido"
    if kind == "aplicar_condicao":
        cond = _fold(eff.get("condicao"))
        label = _CONDICAO_LABEL.get(cond) or str(eff.get("condicao") or "uma condição")
        return f"Aplica {label}{por}"
    if kind == "purga_condicao":
        return "Remove uma condição nociva"
    if kind == "vantagem":
        return f"Concede Vantagem{por}"
    if kind in _STAT_LABEL:
        return f"+{amt} de {_STAT_LABEL[kind]}{por}"
    if kind == "utilitaria":
        hint = str(eff.get("prompt_hint") or "").strip()
        return f"Fora de combate: {hint}" if hint else "Uso fora de combate"
    if kind == "reduzir_carga_aliado":
        return f"Reduz {amt} de Carga do Abismo de um aliado"
    if kind in _STAGE_LABEL:
        stat, virt = _STAGE_LABEL[kind]
        return f"+{amt} de {stat} por Estágio de {virt}"
    # palavras-chave de efeito
    if kind in KEYWORD_KINDS:
        return f"Aplica {_kw_bold(kind, int(base_value(eff)))}"
    if kind == "comprar":
        n = base_value(eff)
        return f"Compra {n} Carta" + ("" if n == 1 else "s")
    if kind == "descartar":
        n = base_value(eff)
        quem = "à sua escolha" if eff.get("escolha") else "ao acaso"
        return f"Descarta {n} Carta" + ("" if n == 1 else "s") + f" {quem}"
    if kind == "ganhar_folego":
        return f"Ganha {base_value(eff)} de Fôlego"
    if kind == "gerar_carta":
        from services import cards

        cid = str(eff.get("id") or eff.get("card_id") or "")
        nome = (cards.get_card(cid) or {}).get("name") or cid or "uma Carta"
        pilha = {"mao": "na mão", "compra": "no monte", "descarte": "no descarte"}.get(
            str(eff.get("pilha") or "mao"), "na mão"
        )
        return f"Gera {nome} {pilha}"
    if kind == "purgar_fardo":
        n = base_value(eff)
        return f"Purga {n} {_kw_bold('fardo')}"
    if kind == "copiar_ultima":
        return "Repete a última Carta jogada nesta rodada"
    if kind == "mover_alvo_zona":
        dirc = "para perto" if str(eff.get("direcao")) == "aproximar" else "para longe"
        return f"Move o alvo {dirc}"
    if kind == "revelar":
        return f"Revela {eff.get('campo') or 'resistencias'} do alvo"
    return kind


def _cond_text(se: dict) -> str:
    parts = []
    for key, arg in (se or {}).items():
        if key == "alvo_tem":
            parts.append(f"o alvo tem {_cond_name(arg)}")
        elif key == "eu_tenho":
            parts.append(f"você tem {_cond_name(arg)}")
        elif key == "entropia_min":
            parts.append(f"sua Entropia é {arg} ou mais")
        elif key == "vitalidade_max_pct":
            parts.append(f"sua Vitalidade está em {arg}% ou menos")
        elif key == "cartas_jogadas_na_rodada_min":
            parts.append(f"você já jogou {arg} Carta(s) nesta rodada")
        elif key == "ultima_carta_tipo":
            parts.append(f"a última Carta foi {arg}")
        elif key == "ultima_carta_postura":
            parts.append(f"a última Carta foi de {arg}")
        elif key == "engajado":
            parts.append("você está engajado" if arg else "você não está engajado")
        elif key == "zona_tem_objeto":
            parts.append(f"há {arg} na zona")
        elif key == "alvo_familia":
            parts.append(f"o alvo é {arg}")
    return " e ".join(parts)


def _cond_name(arg) -> str:
    key = _fold(arg)
    if key in glossary():
        return f"**{glossary()[key]['nome']}**"
    return _CONDICAO_LABEL.get(key, str(arg))


def render_effect(eff: dict) -> str:
    text = _effect_text(eff)
    alvo = _ALVO_LABEL.get(str(eff.get("alvo") or ""))
    if alvo:
        text += f" {alvo}"
    esc = eff.get("escala")
    if isinstance(esc, dict) and esc.get("por") in _ESCALA_LABEL:
        fator = esc.get("fator", 1)
        fator_txt = str(int(fator)) if float(fator).is_integer() else str(fator).replace(".", ",")
        text += f" (+{fator_txt} por {_ESCALA_LABEL[esc['por']]}"
        text += f", máx. +{int(esc['max'])})" if esc.get("max") is not None else ")"
    if eff.get("se"):
        text = f"Se {_cond_text(eff['se'])}: {text[0].lower()}{text[1:]}"
    if eff.get("chamado") is not None:
        text = f"{_kw_bold('chamado', int(eff['chamado']))} — {text}"
    g = gatilho(eff)
    if g != GATILHO_PADRAO:
        text = f"{_GATILHO_LABEL.get(g, g)}: {text[0].lower()}{text[1:]}"
    return text


def render_card_text(card: dict) -> str:
    """Texto de regra da Carta gerado dos efeitos (PT-BR, palavras-chave em
    negrito). A ``descricao`` fica só como sabor — o texto nunca mente."""
    parts: list[str] = []
    kws = keywords(card)
    for key in ("sacrificio", "ressoar"):
        if kws.get(key):
            parts.append(_kw_bold(key, int(kws[key])))
    for key in ("interromper", "exaurir", "guardar", "eco", "fardo", "vazao"):
        if kws.get(key):
            parts.append(_kw_bold(key))
    head = ". ".join(parts)
    body = ". ".join(render_effect(e) for e in normalize(card))
    text = ". ".join(p for p in (head, body) if p)
    return (text + ".") if text else ""


# --------------------------------------------------------------------------
# R9 — orçamento de poder
# --------------------------------------------------------------------------
def budget_config() -> dict:
    global _ORCAMENTO
    if _ORCAMENTO is None:
        _ORCAMENTO = _load_json("_orcamento.json")
    return _ORCAMENTO


def reload() -> None:
    """Descarta caches de glossário/orçamento (testes)."""
    global _GLOSSARIO, _ORCAMENTO
    _GLOSSARIO = None
    _ORCAMENTO = None


def raridade(card: dict) -> str:
    cfg = budget_config()
    return str(cfg["raridade_por_patamar"].get(str(card.get("patamar") or ""), "comum"))


def custo_folego(card: dict) -> int:
    """Custo de Fôlego: explícito no JSON ou a regra default da SPEC-328 R6."""
    if card.get("custo_folego") is not None:
        return max(0, min(3, int(card["custo_folego"])))
    eff = primary_effect(card) or {}
    freq = str(card.get("frequencia") or "livre")
    dano = int(eff.get("dano_base", 0) or 0) if eff.get("kind") == "dano" else 0
    if card.get("apex") or freq == "descanso_longo":
        return 3
    if int(card.get("tier", 0) or 0) >= 3 or dano >= 8:
        return 2
    if freq == "livre" and eff.get("kind") != "dano":
        return 0
    return 1


def _formula_avg(formula: str) -> float:
    total = 0.0
    for sign, num, faces, flat in re.findall(r"([+-]?)\s*(?:(\d*)d(\d+)|(\d+))", str(formula)):
        s = -1 if sign == "-" else 1
        if faces:
            total += s * int(num or 1) * (int(faces) + 1) / 2
        elif flat:
            total += s * int(flat)
    return total


def _effect_power(eff: dict, w: dict) -> float:
    kind = str(eff.get("kind") or "")
    dur = max(1, int(eff.get("duracao", eff.get("duration", 1)) or 1))
    if eff.get("formula") and eff.get("dano_base") is None and eff.get("valor") is None:
        amt = _formula_avg(eff["formula"])
    else:
        amt = float(base_value(eff))
    pw = w["kind"]
    if kind in ("dano", "contra_ataque"):
        p = amt * pw[kind]
    elif kind == "dot":
        p = amt * dur * pw["dot"]
    elif kind == "sangria":
        p = amt * (amt + 1) / 2 * pw["dot"]
    elif kind in ("rachadura", "torpor"):
        p = amt * pw[kind]
    elif kind == "aplicar_condicao":
        p = dur * w["condicao"].get(_fold(eff.get("condicao")), w["condicao"]["_default"])
    elif kind in ("protecao", "cura", "vigilia", "reduzir_carga_aliado"):
        p = amt * pw[kind]
    elif kind == "vantagem":
        p = dur * pw["vantagem"]  # Vantagem é binária: o valor não escala
    elif kind in _STAT_LABEL:
        p = amt * dur * pw.get(kind, pw["_buff"])
    elif kind == "marca_do_abismo":
        p = pw["marca_do_abismo"] + amt * pw["dano"]
    elif kind in _STAGE_LABEL:
        p = max(1.0, amt) * pw["_estagio"]
    else:
        p = pw.get(kind, pw["_flat"]) * (amt if kind in PILE_KINDS else 1)
    mult = w["multiplicador"]
    if str(eff.get("alvo") or "") in ("inimigos", "aliados"):
        p *= mult["area"]
    if eff.get("se") or eff.get("chamado") is not None:
        p *= mult["condicional"]
    if gatilho(eff) != GATILHO_PADRAO:
        p *= mult["gatilho"]
    esc = eff.get("escala")
    if isinstance(esc, dict) and esc.get("max") is not None:
        p += float(esc["max"]) * pw.get(kind, 1.0) * mult["escala"]
    return p


def power_score(card: dict) -> float:
    """Poder determinístico da Carta: efeitos − custos, pesos em
    ``data/cards/_orcamento.json``. Usado pelo validador e pela SPEC-336."""
    cfg = budget_config()
    w = cfg["pesos"]
    power = sum(_effect_power(e, w) for e in normalize(card))
    if card.get("tipo") == "passiva":
        power *= w["multiplicador"]["passiva"]
    kws = keywords(card)
    power += float(kws.get("ressoar", 0) or 0) * w["palavra_chave"]["ressoar"]
    for key in ("interromper", "eco", "guardar", "vazao"):
        if kws.get(key):
            power += w["palavra_chave"][key]
    cost = int(card.get("custo_entropia", 0) or 0) * w["custo"]["entropia"]
    cost += float(kws.get("sacrificio", 0) or 0) * w["custo"]["sacrificio"]
    cost += w["custo"]["frequencia"].get(str(card.get("frequencia") or "livre"), 0.0)
    if kws.get("exaurir"):
        cost += w["custo"]["exaurir"]
    if kws.get("fardo"):
        cost += w["custo"]["fardo"]
    return round(power - cost, 2)


def budget_band(card: dict) -> tuple[float, float] | None:
    """Faixa ``(min, max)`` de ``power_score`` para (raridade, custo_folego).
    ``None`` = Carta fora do orçamento (utilitária/virtude)."""
    cfg = budget_config()
    if card.get("tipo") in set(cfg.get("tipos_isentos") or []):
        return None
    faixa = cfg["faixas"].get(raridade(card)) or {}
    band = faixa.get(str(custo_folego(card)))
    return None if band is None else (float(band[0]), float(band[1]))


def budget_error(card: dict) -> str | None:
    band = budget_band(card)
    if band is None:
        return None
    score = power_score(card)
    if band[0] <= score <= band[1]:
        return None
    return (
        f"fora do orçamento: power_score {score} fora da faixa "
        f"{raridade(card)}/Fôlego {custo_folego(card)} = [{band[0]}, {band[1]}]"
    )


# --------------------------------------------------------------------------
# R2 — validação do vocabulário (consumida por content_validator)
# --------------------------------------------------------------------------
def _int_like(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _validate_se(se, where: str) -> list[str]:
    errs = []
    if not isinstance(se, dict) or not se:
        return [f"{where}: `se` precisa ser dict não vazio"]
    for key, arg in se.items():
        kind = CONDICOES.get(key)
        if kind is None:
            errs.append(f"{where}: condição {key!r} fora do catálogo")
        elif kind in ("int", "pct") and not (_int_like(arg) and arg >= 0):
            errs.append(f"{where}: {key} exige inteiro ≥ 0")
        elif kind == "pct" and arg > 100:
            errs.append(f"{where}: {key} exige 0..100")
        elif kind == "bool" and not isinstance(arg, bool):
            errs.append(f"{where}: {key} exige booleano")
        elif kind in ("cond", "tipo", "classe", "tag", "familia") and not (
            isinstance(arg, str) and arg.strip()
        ):
            errs.append(f"{where}: {key} exige texto")
        elif kind == "cond" and _fold(arg) not in known_condition_names():
            errs.append(f"{where}: {key} {arg!r} fora do catálogo de condições")
    return errs


def validate_effect(eff, where: str = "efeito") -> list[str]:
    errs: list[str] = []
    if not isinstance(eff, dict):
        return [f"{where}: efeito precisa ser objeto"]
    kind = str(eff.get("kind"))
    if kind not in all_kinds():
        errs.append(f"{where}: kind {eff.get('kind')!r} fora do catálogo fechado")
    q = eff.get("quando")
    if q is not None and q not in GATILHOS:
        errs.append(f"{where}: gatilho {q!r} fora do catálogo")
    if eff.get("se") is not None:
        errs += _validate_se(eff["se"], where)
    alvo = eff.get("alvo")
    if alvo is not None and alvo not in ALVOS:
        errs.append(f"{where}: alvo {alvo!r} fora do catálogo")
    esc = eff.get("escala")
    if esc is not None:
        if not isinstance(esc, dict) or esc.get("por") not in ESCALA_POR:
            errs.append(f"{where}: escala.por fora do catálogo")
        elif not isinstance(esc.get("fator", 1), int | float) or (
            esc.get("max") is not None and not _int_like(esc.get("max"))
        ):
            errs.append(f"{where}: escala.fator/max inválidos")
    ch = eff.get("chamado")
    if ch is not None and not (_int_like(ch) and ch >= 1):
        errs.append(f"{where}: Chamado exige inteiro ≥ 1")
    if kind in KEYWORD_KINDS | PILE_KINDS and eff.get("valor") is not None:
        if not (_int_like(eff["valor"]) and eff["valor"] >= 0):
            errs.append(f"{where}: valor de {kind} exige inteiro ≥ 0")
    if kind == "revelar" and eff.get("campo", "resistencias") not in REVELAR_CAMPOS:
        errs.append(f"{where}: revelar.campo fora do catálogo")
    if kind == "mover_alvo_zona" and eff.get("direcao", "afastar") not in ("aproximar", "afastar"):
        errs.append(f"{where}: mover_alvo_zona.direcao inválida")
    if kind == "gerar_carta" and not (eff.get("id") or eff.get("card_id")):
        errs.append(f"{where}: gerar_carta exige id")
    return errs


def validate_card(card: dict) -> list[str]:
    """Erros de gramática da Carta (vazio = ok). Não inclui orçamento."""
    errs: list[str] = []
    raw = card.get("efeitos")
    if raw is not None:
        if not isinstance(raw, list) or not raw:
            errs.append("efeitos precisa ser lista não vazia")
        else:
            for i, eff in enumerate(raw):
                errs += validate_effect(eff, f"efeitos[{i}]")
            prim = primary_effect(card)
            if prim is None and card.get("tipo") not in ("passiva", "virtude"):
                # Passiva pode ser só gatilhos; Carta jogável precisa do principal.
                errs.append("efeitos sem efeito principal (ao_jogar, sem condição)")
            elif card.get("efeito") and card["efeito"] != prim:
                errs.append("efeito legado diverge do principal de efeitos")
    elif card.get("efeito") is not None:
        eff = card["efeito"]
        if isinstance(eff, dict) and any(k in eff for k in ("quando", "se", "escala", "chamado")):
            errs += validate_effect(eff, "efeito")
    kws = card.get("palavras_chave")
    if kws is not None:
        if not isinstance(kws, dict):
            errs.append("palavras_chave precisa ser objeto")
        else:
            for key, val in kws.items():
                kind = CARD_KEYWORDS.get(key)
                if kind is None:
                    errs.append(f"palavra-chave {key!r} fora do glossário")
                elif kind == "int" and not (_int_like(val) and val >= 1):
                    errs.append(f"palavra-chave {key} exige inteiro ≥ 1")
                elif kind == "bool" and val is not True:
                    errs.append(f"palavra-chave {key} exige true")
            if kws.get("vazao") and not any(gatilho(e) == "ao_descartar" for e in normalize(card)):
                errs.append("Vazão exige um efeito com quando=ao_descartar")
    return errs
