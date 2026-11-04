"""services/reinforcement_cards.py - "Chamado do Bando" no tabuleiro de cartas (SPEC-391).

Fluxo de Carta do reforco de `lider_matilha` (alternativa ao aviso do R16 da SPEC-325, que
continua em `services/reinforcements.py` para o baralho `off`). Python decide, nunca LLM:

- rodada N: o lider cruza 50 % -> telegrafo (Carta no baralho, promessa na cena, Pressagio);
- rodada N+1: o lider joga `inf_chamado_do_bando` (ocupa o turno) -> estagio `called`;
- fim de N+2: se o lider ainda age, chega 1 reforco `distante`.
Nao jogar a Carta (lider caido, fugido, atordoado...) ou cair antes da chegada cancela.

`advance` e a porta do no de combate (escolhe legado x Carta); `advance_card_flow` e a do fluxo
de Carta, usada tambem pela arena do gate (`docs/spec391/arena_reforco_cartas.py`).
"""

from __future__ import annotations

import json
from typing import Any

from observability.telemetry import log_event as _log_event
from services import conflict_scene as cs
from services import reinforcements as rf

CALL_CARD = "inf_chamado_do_bando"
PROMISE_KIND = "chamado"
VIA = "carta"
_DEFAULT_NATURE = "fera"
_data_cache: dict | None = None


def _data() -> dict:
    """`natureza_por_id` e `telegrafos` de `data/cards/inimigos/chamados.json` (cache)."""
    global _data_cache
    if _data_cache is None:
        from services import enemy_decks as edk

        try:
            raw = json.loads((edk._DIR / "chamados.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        _data_cache = raw if isinstance(raw, dict) else {}
    return _data_cache


def eligible(mode: str | None = None) -> bool:
    """R1: reforco `on` (ou `shadow`) + baralho de cartas `on` + baralhos de inimigo `on`."""
    from services import card_piles, combat_flags
    from services import enemy_decks as edk

    mode = combat_flags.mode("reinforcements") if mode is None else mode
    return mode in ("on", "shadow") and card_piles.mode() == "on" and edk.mode() == "on"


def telegraph_text(leader: dict) -> str:
    """Frase publica do chamado (fera x humanoide pelo mapa `natureza_por_id`)."""
    data = _data()
    nature = str((data.get("natureza_por_id") or {}).get(rf._base_id(leader)) or _DEFAULT_NATURE)
    texts = data.get("telegrafos") or {}
    texto = str(texts.get(nature) or texts.get(_DEFAULT_NATURE) or "{nome} chama o bando.")
    return texto.format(nome=str(leader.get("name") or leader.get("id") or "O líder"))


def _key(actor: dict) -> str:
    return str(actor.get("id") or actor.get("name"))


def _promise_of(scene: dict | None, key: str) -> dict:
    promises = scene.get("prenuncios") if isinstance(scene, dict) else None
    promise = promises.get(key) if isinstance(promises, dict) else None
    return promise if isinstance(promise, dict) else {}


def pending_call(scene: dict | None, actor: dict, rnd: int) -> dict | None:
    """Promessa de chamado do lider para a rodada `rnd` (precedencia R4/R5), ou `None`."""
    from services import combat_flags

    if combat_flags.mode("reinforcements") != "on":  # flag off com chamado pendente: não joga
        return None
    promise = _promise_of(scene, _key(actor))
    if promise.get("tipo") == PROMISE_KIND and int(promise.get("rnd", 0) or 0) == int(rnd):
        return promise
    return None


def on_declaration(scene: dict | None, actor_id: str, card_id: str | None, rnd: int) -> None:
    """R7: a declaracao efetiva do lider jogou o Chamado. Grava na CENA (o orquestrador nao tem o
    `combat_meta`); `advance_card_flow` consome a marca ao fim da rodada."""
    if isinstance(scene, dict) and card_id == CALL_CARD:
        scene["chamado_jogado"] = {"leader_id": str(actor_id), "rnd": int(rnd)}


def telegraph(scene: dict, leader: dict, combat_meta: dict, round_: int, trig: dict) -> None:
    """R3 (a-c): registra o chamado, poe a Carta no baralho do lider e grava a promessa na cena."""
    lid = str(leader.get("id"))
    cartas = list(leader.get("cartas") or [])
    if CALL_CARD not in cartas:
        cartas.append(CALL_CARD)
    leader["cartas"] = cartas
    scene.setdefault("prenuncios", {})[lid] = {
        "carta": CALL_CARD,
        "rnd": int(round_) + 1,
        "fase_idx": int(leader.get("fase_idx", 0) or 0),
        "tipo": PROMISE_KIND,
    }
    combat_meta["reinforcement"] = {
        "trigger_id": trig["id"],
        "leader_id": lid,
        "via": VIA,
        "stage": "telegraphed",
        "telegraphed_round": int(round_),
        "call_round": int(round_) + 1,
        "arrival_round": int(round_) + 2,
        "fired": False,
    }
    _log_event("combat", "reinforcements_telegraphed", level="info", via=VIA)


def _cancel(
    scene: dict, combat_meta: dict, state: dict, cause: str, leader: dict | None = None
) -> None:
    if leader and state.get("stage") == "telegraphed":  # nunca jogada: não sobra proteção avulsa
        leader["cartas"] = [c for c in leader.get("cartas") or [] if c != CALL_CARD]
    state.update(cancelled=True, cause=cause)
    combat_meta["reinforcement"] = state
    lid = str(state.get("leader_id"))
    if _promise_of(scene, lid).get("tipo") == PROMISE_KIND:
        del scene["prenuncios"][lid]
    scene.pop("chamado_jogado", None)
    _log_event("combat", "reinforcements_cancelled", level="info", via=VIA, cause=cause)


def _called(scene: dict, state: dict, leader: dict, played: dict, res: dict) -> None:
    """R7: o Chamado foi jogado. `warned_round` espelha `called_round` (R10: o aviso legado)."""
    state.update(stage="called", called_round=int(played["rnd"]), warned_round=int(played["rnd"]))
    scene.pop("chamado_jogado", None)
    res["warned"] = True
    res["logs"].append(f"{leader.get('name', 'O líder')} chama o bando: passos ao longe.")
    _log_event("combat", "reinforcements_warned", level="info", via=VIA)


def _slack() -> int:
    """SPEC-391 L1 (gate 1 reprovou): a chegada só com folga de orçamento para +1 Lacaio."""
    import encounter_budget as eb

    return int(eb.CATEGORIA_COST["lacaio"])


def _fire(
    scene: dict,
    enemies: list[dict],
    actors_by_id: dict,
    sides: dict,
    combat_meta: dict,
    *,
    state: dict,
    leader: dict,
    round_: int,
    res: dict,
) -> None:
    trigs = scene.get("reinforcement_triggers") or []
    trig = next((t for t in trigs if t.get("id") == state["trigger_id"]), None)
    new = (
        rf.spawn(trig, combat_meta, enemies, deck_seed=leader.get("deck_seed"), slack=_slack())
        if trig
        else []
    )
    if not new:
        _cancel(scene, combat_meta, state, "sem_folga")
        return
    pos = rf._arrival_position(scene, str(state["leader_id"]))
    for enemy in new:
        enemy["chegou_na_rodada"] = int(round_)  # R12: padrao/assinatura contam daqui
        trig.setdefault("participants", {})[enemy["id"]] = dict(pos)
    cs.fire_reinforcement(scene, str(trig["id"]))
    for enemy in new:
        enemies.append(enemy)
        actors_by_id[enemy["id"]] = enemy
        sides.setdefault("enemy", []).append(enemy["id"])
        res["logs"].append(f"{enemy.get('name', 'Um inimigo')} chega correndo, vindo de longe.")
    res["spawned"] = new
    combat_meta["reinforcement"] = {**state, "fired": True}
    _log_event("combat", "reinforcements_fired", level="info", via=VIA)


def _progress(
    scene: dict,
    enemies: list[dict],
    actors_by_id: dict,
    sides: dict,
    combat_meta: dict,
    state: dict,
    round_: int,
    res: dict,
) -> None:
    leader = actors_by_id.get(str(state.get("leader_id"))) or {}
    if state.get("stage") == "telegraphed":
        played = scene.get("chamado_jogado")
        if (
            isinstance(played, dict)
            and played.get("leader_id") == state.get("leader_id")
            and rf.acts(leader)
        ):
            _called(scene, state, leader, played, res)
        elif int(round_) >= int(state.get("call_round", 0) or 0):
            res["logs"].append(f"{leader.get('name', 'O líder')} não chega a chamar o bando.")
            _cancel(scene, combat_meta, state, "frustrado", leader)
            return
    if state.get("stage") == "called":
        if not rf.acts(leader):
            _cancel(scene, combat_meta, state, "lider_caido")
            return
        if int(round_) >= int(state.get("arrival_round", 0) or 0):
            _fire(
                scene,
                enemies,
                actors_by_id,
                sides,
                combat_meta,
                state=state,
                leader=leader,
                round_=round_,
                res=res,
            )
            return
    combat_meta["reinforcement"] = state


def _would_telegraph(enemies: list[dict]) -> bool:
    return any(rf.is_leader(e) and rf.acts(e) and rf._ratio(e) <= rf.WARN_RATIO for e in enemies)


def advance_card_flow(
    scene: dict,
    enemies: list[dict],
    actors_by_id: dict,
    sides: dict,
    combat_meta: dict,
    round_: int,
    *,
    mode: str = "on",
) -> dict[str, Any]:
    """Fim de rodada do fluxo de Carta. Mesmo contrato de `reinforcements.advance`, mais
    `telegraphed`. `shadow` so registra (nada muda)."""
    res: dict[str, Any] = {"logs": [], "spawned": [], "warned": False, "telegraphed": False}
    state = dict(combat_meta.get("reinforcement") or {})
    if mode == "shadow":
        if not state and _would_telegraph(enemies):
            _log_event("combat", "reinforcements_shadow", phase="would_telegraph")
        return res
    if mode != "on" or state.get("fired") or state.get("cancelled"):
        return res
    if state:
        _progress(scene, enemies, actors_by_id, sides, combat_meta, state, round_, res)
        return res
    for trig in scene.get("reinforcement_triggers") or []:
        leader = actors_by_id.get(str(trig.get("leader_id")))
        if trig.get("kind") != rf.ARCHETYPE or not rf.acts(leader):
            continue
        if rf._ratio(leader) <= rf.WARN_RATIO:
            telegraph(scene, leader, combat_meta, round_, trig)
            res["telegraphed"] = True
            break
    return res


def advance(
    scene: dict,
    enemies: list[dict],
    actors_by_id: dict,
    sides: dict,
    combat_meta: dict,
    round_: int,
    *,
    mode: str = "on",
) -> dict[str, Any]:
    """Porta do no de combate: fluxo de Carta quando R1 vale (ou o estado e dele); senao o legado.
    O despacho e por `via == "carta"`, nunca por `warned_round` (espelhado em `called`)."""
    state = combat_meta.get("reinforcement") or {}
    use_cards = state.get("via") == VIA if state else eligible(mode)
    runner = advance_card_flow if use_cards else rf.advance
    return runner(scene, enemies, actors_by_id, sides, combat_meta, round_, mode=mode)


def payload_fields(meta: dict | None) -> dict[str, Any]:
    """Campos publicos do bloco de combate: `reinforcement_warning` (so depois do aviso: regra de
    ouro do R16) e `reinforcement` (fluxo de Carta). Nada do template do reforco antes da chegada."""
    from services import combat_flags

    if not combat_flags.active("reinforcements"):
        return {}
    state = (meta or {}).get("reinforcement") or {}
    out: dict[str, Any] = {}
    if (
        state.get("warned_round") is not None
        and not state.get("fired")
        and not state.get("cancelled")
    ):
        out["reinforcement_warning"] = True
    view = public_view(meta)
    if view:
        out["reinforcement"] = view
    return out


def public_view(combat_meta: dict | None) -> dict | None:
    """R10: objeto publico minimo entre o telegrafo e a chegada/cancelamento (nada do template)."""
    state = (combat_meta or {}).get("reinforcement") or {}
    if state.get("via") != VIA or state.get("fired") or state.get("cancelled"):
        return None
    called = state.get("stage") == "called"
    return {
        "stage": "called" if called else "telegraphed",
        "leader_id": state.get("leader_id"),
        "chega_na_rodada": int(state["arrival_round"]) if called else None,
    }
