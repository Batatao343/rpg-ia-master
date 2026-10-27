"""services/enemy_intent.py - Presságio: a intenção do inimigo visível antes da jogada (SPEC-329).

`forecast_round` congela, no início da rodada, a declaração de cada inimigo vivo usando a
MESMA `enemy_declaration` de hoje (sem LLM, sem efeito colateral: roda sobre cópias das
fichas e de uma bifurcação do rng). `public_intent` devolve só o que o jogador pode saber,
por nível de conhecimento do bestiário. `still_possible` diz se o presságio congelado ainda
pode ser executado na hora da resolução (R4).

Flag `RPG_ENEMY_INTENT=off|shadow|on` (default `off`; dono 27/10): `shadow` calcula e
compara com a decisão tardia sem mudar nada; `on` executa o presságio congelado.
"""

from __future__ import annotations

import copy
import json
import os
import random
from pathlib import Path
from typing import Any

_SINAIS_PATH = Path(__file__).resolve().parent.parent / "data" / "combat" / "pressagio_sinais.json"
_MODES = ("off", "shadow", "on")
_sinais_cache: dict | None = None

TIPOS = (
    "ataque",
    "ataque_multiplo",
    "defesa",
    "reforco_proprio",
    "enfraquecer",
    "mover",
    "fugir",
    "render-se",
    "desconhecido",
)

# efeitos de carta -> tipo de presságio (o resto de _ATTACK_EFFECTS vira "ataque")
_CONTROL_EFFECTS = {"aplicar_condicao", "empurrao", "taunt", "marca", "dot"}
_DEFENSE_EFFECTS = {"protecao", "buff_defesa", "esconder"}


def mode() -> str:
    raw = os.getenv("RPG_ENEMY_INTENT", "off").strip().lower()
    return raw if raw in _MODES else "off"


def active() -> bool:
    return mode() == "on"


# --------------------------------------------------------------------------
# Catálogo de sinais
# --------------------------------------------------------------------------
def _sinais() -> dict:
    global _sinais_cache
    if _sinais_cache is None:
        try:
            _sinais_cache = json.loads(_SINAIS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _sinais_cache = {}
    return _sinais_cache


def family_of(enemy: dict) -> str:
    """Família narrativa do inimigo (heurística por id/facção/tipo/nome; default `fera`)."""
    blob = " ".join(
        str(enemy.get(k) or "") for k in ("archetype_id", "id", "faction", "type", "name")
    ).lower()
    rules = (
        (
            "morto_inquieto",
            ("mumia", "múmia", "esquel", "zumbi", "morto", "espectro", "cripta", "fantasma"),
        ),
        ("legiao", ("legiao", "legião", "soldado", "guarda", "mercenario")),
        ("culto", ("culto", "chama_azul", "iniciado", "cultista", "seita")),
        ("abissal", ("abis", "vazio", "cinza", "aberra", "devorador")),
        ("ermo", ("bandid", "saqueador", "escorpi", "deserto", "ermo", "degolador", "vinha")),
    )
    for fam, keys in rules:
        if any(k in blob for k in keys):
            return fam
    return "fera"


def sinal_for(tipo: str, enemy: dict, alvo_nome: str = "", *, key: str = "") -> str:
    """Frase do catálogo por tipo x família; escolha determinística (sem rng)."""
    table = _sinais().get(tipo) or _sinais().get("desconhecido") or {}
    frases = table.get(family_of(enemy)) or table.get("default") or []
    if not frases:
        return ""
    idx = sum(ord(c) for c in f"{key}{enemy.get('id', '')}") % len(frases)
    return str(frases[idx]).format(
        nome=str(enemy.get("name") or enemy.get("id") or "O inimigo"),
        alvo=alvo_nome or "o alvo",
    )


# --------------------------------------------------------------------------
# Previsão
# --------------------------------------------------------------------------
def _fork_rng(rng) -> random.Random:
    """Bifurca o rng (estado copiado): a previsão não consome o rng real da cena."""
    forked = random.Random()
    try:
        forked.setstate((rng or random).getstate())
    except Exception:
        forked.seed(0)
    return forked


def _classify(
    decl, actor: dict, actors_by_id: dict[str, dict]
) -> tuple[str, str | None, str | None]:
    """(tipo, alvo_id, carta_id) a partir da declaração do inimigo."""
    from services import conflict_turn as ct

    acao = decl.acao
    if acao is None or acao.kind == "pass":
        return ("render-se" if actor.get("surrendered") else "desconhecido"), None, None
    if acao.kind == "move":
        return ("fugir" if str(acao.direction or "") == "afastar" else "mover"), None, None
    if acao.kind == "tactic":
        m = str(acao.maneuver or "")
        if m == "flee":
            return "fugir", None, None
        if m == "control":
            return "enfraquecer", acao.target_id, None
        if m == "flank":
            return "mover", acao.target_id, None
        if m == "protect":
            return "defesa", acao.target_id, None
        return "reforco_proprio", acao.target_id, None  # stabilize / support
    if acao.kind == "attack":
        return "ataque", acao.target_id, None
    if acao.kind == "card":
        from services import cards

        card = cards.get_card(acao.card_id or "") or {}
        ef = card.get("efeito") or {}
        kind = str(ef.get("kind") or "")
        if kind in _DEFENSE_EFFECTS:
            return "defesa", acao.target_id, acao.card_id
        if kind in ct._SUPPORT_EFFECTS:
            return "reforco_proprio", acao.target_id, acao.card_id
        if kind in _CONTROL_EFFECTS:
            return "enfraquecer", acao.target_id, acao.card_id
        multi = ef.get("alvos") or ef.get("area")
        if multi and (multi is True or (isinstance(multi, (int, float)) and multi > 1)):
            return "ataque_multiplo", acao.target_id, acao.card_id
        return "ataque", acao.target_id, acao.card_id
    return "desconhecido", acao.target_id, None


def forecast_round(
    scene: dict,
    actors_by_id: dict[str, dict],
    sides: dict[str, list[str]],
    rng=None,
    *,
    scene_state: dict | None = None,
) -> dict[str, list[dict]]:
    """R1/R7: `{actor_id: [intent, ...]}` — uma linha por ação (SPEC-295). Não altera a cena,
    as fichas nem o rng real. Cada intent é JSON-safe e guarda a declaração congelada."""
    import combat_mechanics as cm
    from services import cards as cards_mod
    from services import conflict_orchestrator as orch

    out: dict[str, list[dict]] = {}
    fork = _fork_rng(rng)
    for aid in sides.get("enemy", []):
        real = actors_by_id.get(aid)
        if not real or not orch._can_act(real) or cm.has_control(real, "stun"):
            continue
        intents: list[dict] = []
        for idx in range(1 + orch.extra_actions(real)):
            # Cópia rasa de TODOS os atores: enemy_declaration faz pop/set no inimigo e a
            # Provocação grava `_last_class_mechanics` no provocador (lista copiada também).
            sandbox = {k: dict(v) for k, v in actors_by_id.items()}
            for fic in sandbox.values():
                if isinstance(fic.get("_last_class_mechanics"), list):
                    fic["_last_class_mechanics"] = list(fic["_last_class_mechanics"])
            # run_round zera o uso "por turno" das Cartas do inimigo antes de agir.
            sandbox[aid]["enemy_card_usage"] = copy.deepcopy(real.get("enemy_card_usage") or {})
            cards_mod.reset_enemy_card_usage(sandbox[aid], "turno")
            decl = orch.enemy_declaration(
                scene, aid, sandbox, sides, scene_state=scene_state, rng=fork
            )
            tipo, alvo, carta = _classify(decl, sandbox[aid], actors_by_id)
            intents.append(
                {
                    "actor_id": aid,
                    "idx": idx,
                    "tipo": tipo,
                    "alvo_id": alvo,
                    "carta_id": carta,
                    "declaration": decl.model_dump(),
                }
            )
        out[aid] = intents
    return out


# --------------------------------------------------------------------------
# Visão pública (R2/R3)
# --------------------------------------------------------------------------
def knowledge_level(enemy: dict, carta_id: str | None = None) -> str:
    """`estudada` = a carta do presságio já foi revelada; `conhecida` = o personagem já
    descobriu algo do arquétipo; senão `desconhecida`."""
    from services import bestiary_knowledge as bk

    if carta_id and bk.is_card_revealed(enemy, carta_id):
        return "estudada"
    if enemy.get("revealed_cards") or enemy.get("revealed_resistances") or enemy.get("known"):
        return "conhecida"
    return "desconhecida"


def _base_damage(intent: dict, actor: dict) -> int | None:
    """Dano-base FLAT do golpe (sem rolar dados); None se for fórmula legada."""
    from services import cards
    from services import conflict_turn as ct

    card = cards.get_card(intent.get("carta_id") or "") if intent.get("carta_id") else None
    if card:
        ef = card.get("efeito") or {}
        if ef.get("dano_base") is not None:
            return max(0, int(ef["dano_base"]))
        cat = ef.get("categoria_arma")
        if cat in ct._DANO_BASE_ARMA:
            return ct._DANO_BASE_ARMA[cat]
        if ef.get("formula"):
            return None
    if actor.get("attack_formula"):
        return None
    base = actor.get("dano_base_arma")
    return max(0, int(base)) if base is not None else ct._DANO_BASICO_DEFAULT


def _protection(target: dict | None) -> int:
    if not target:
        return 0
    armor = target.get("armor") or {}
    try:
        return max(0, int(armor.get("protecao", target.get("protecao", 0)) or 0))
    except (TypeError, ValueError):
        return 0


def public_intent(
    intent: dict,
    knowledge_level_: str,
    *,
    actors_by_id: dict[str, dict] | None = None,
) -> dict:
    """Visão do jogador: desconhecida = tipo/alvo; conhecida = + faixa; estudada = + valor
    estimado e nome da carta. `sinal` sempre do catálogo (sem LLM)."""
    actors = actors_by_id or {}
    enemy = actors.get(intent["actor_id"]) or {"id": intent["actor_id"]}
    alvo = actors.get(intent.get("alvo_id") or "") or {}
    tipo = intent["tipo"]
    view: dict[str, Any] = {
        "actor_id": intent["actor_id"],
        "tipo": tipo,
        "alvo_id": intent.get("alvo_id"),
        "valor_estimado": None,
        "faixa": None,
        "carta_nome": None,
        "sinal": sinal_for(tipo, enemy, str(alvo.get("name") or ""), key=tipo),
    }
    if knowledge_level_ == "desconhecida":
        return view
    if tipo in ("ataque", "ataque_multiplo"):
        base = _base_damage(intent, enemy)
        if base is not None:
            prot = _protection(alvo)
            low, high = max(0, base - prot), max(0, 2 * base - prot)  # acerto .. crítico
            view["faixa"] = [low, high]
            if knowledge_level_ == "estudada":
                view["valor_estimado"] = low
    if knowledge_level_ == "estudada" and intent.get("carta_id"):
        from services import cards

        view["carta_nome"] = (cards.get_card(intent["carta_id"]) or {}).get("name")
    return view


def public_round(frozen: dict[str, list[dict]], actors_by_id: dict[str, dict]) -> list[dict]:
    """Lista pública (uma linha por ação, ordem dos inimigos) para `combat.pressagios_publicos`."""
    rows: list[dict] = []
    for aid, intents in frozen.items():
        enemy = actors_by_id.get(aid) or {"id": aid}
        for it in intents:
            rows.append(
                public_intent(
                    it, knowledge_level(enemy, it.get("carta_id")), actors_by_id=actors_by_id
                )
            )
    return rows


# --------------------------------------------------------------------------
# Execução (R4)
# --------------------------------------------------------------------------
def still_possible(intent: dict, actors_by_id: dict[str, dict], scene: dict | None = None) -> bool:
    """O presságio congelado ainda é executável? Impossível = executor incapaz de agir, alvo
    morto/fugiu/rendido/incapacitado, ou carta não mais utilizável."""
    from services import conflict_orchestrator as orch
    from services import conflict_turn as ct

    actor = actors_by_id.get(intent["actor_id"])
    if actor is None or not orch._can_act(actor):
        return False
    alvo_id = intent.get("alvo_id")
    if alvo_id and intent["tipo"] not in ("defesa", "reforco_proprio"):
        if not ct._targetable(actors_by_id.get(alvo_id)):
            return False
    elif alvo_id and alvo_id != intent["actor_id"]:
        target = actors_by_id.get(alvo_id)
        if target is None or target.get("dead") or str(target.get("status", "")) == "morto":
            return False
    carta = intent.get("carta_id")
    if carta and not intent.get("idx"):  # ações extras dividem o limite da Carta (SPEC-295)
        from services import cards

        if not cards.can_use_enemy_card(actor, carta, expected_type="ativa"):
            return False
    return True


def frustrated_line(intent: dict, actors_by_id: dict[str, dict]) -> str:
    """Linha de narração do presságio frustrado (catálogo `_frustrado`)."""
    enemy = actors_by_id.get(intent["actor_id"]) or {"id": intent["actor_id"]}
    return sinal_for("_frustrado", enemy, key="f")
