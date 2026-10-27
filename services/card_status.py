"""services/card_status.py - Ferimentos e Carga do Abismo como Cartas DENTRO do conflito (SPEC-333).

Ganchos puros chamados por `agents/combat.py` entre as rodadas, so com
`RPG_CARD_REWARDS=on` E o Baralho `on` (sem pilhas nao ha o que inserir):

- R7  Ferimento novo -> carta de status no TOPO do monte (chega na mao da proxima rodada):
      leve `sts_dor_surda`, grave `sts_membro_falho`, critico `sts_sangue_olhos`. Vivem so nas
      pilhas do conflito, entao saem sozinhas no fim dele (`combat["pilhas"]` e descartado).
- R9  Carga do Abismo >= patamar `moderado` da classe -> 1 `sus_sussurro_abismo` por cena
      (jogavel a 0 de Folego, +2 de Entropia). Nao jogada em 2 rodadas, vira o Fardo base.
- `ao_comprar_status` (vocabulario fechado, JSON da Carta): `exaurir_fim_rodada`, `folego`,
  `condicao`+`rodadas`.
"""

from __future__ import annotations

import combat_mechanics as cm
from services import card_piles, card_rewards, cards

WOUND_CARDS = {
    "leve": "sts_dor_surda",
    "grave": "sts_membro_falho",
    "critico": "sts_sangue_olhos",
}
SUSSURRO_ID = "sus_sussurro_abismo"
SUSSURRO_ROUNDS = 2
_HIGH_TIERS = ("moderado", "severo")


def active() -> bool:
    return card_rewards.mode() == "on" and card_piles.mode() == "on"


def wound_counts(player: dict) -> dict[str, int]:
    fer = player.get("ferimentos") or {}
    return {cat: len(fer.get(cat) or []) for cat in WOUND_CARDS}


def new_wounds(before: dict[str, int], player: dict) -> list[str]:
    """Categorias de cada Ferimento aberto desde `before` (uma entrada por Ferimento novo)."""
    now = wound_counts(player)
    out: list[str] = []
    for cat in WOUND_CARDS:
        out += [cat] * max(0, now[cat] - int(before.get(cat, 0) or 0))
    return out


def _spec(card_id: str) -> dict:
    spec = (cards.get_card(card_id) or {}).get("ao_comprar_status")
    return spec if isinstance(spec, dict) else {}


def _name(card_id: str) -> str:
    return str((cards.get_card(card_id) or {}).get("name", card_id))


def _abyss_high(player: dict) -> bool:
    return cm.abyss_tier(player) in _HIGH_TIERS


def _insert_sussurro(piles: dict, player: dict, pilha: str, logs: list[str]) -> None:
    if not card_piles.add_card(piles, SUSSURRO_ID, pilha):
        return
    piles["sussurro"] = {"rodadas": 0, "ativo": True}
    player["cartas_cena"] = list(
        dict.fromkeys(list(player.get("cartas_cena") or []) + [SUSSURRO_ID])
    )
    logs.append("O Abismo sussurra: uma Carta nova se oferece ao seu Baralho.")


def on_hand_drawn(piles: dict, player: dict) -> list[str]:
    """Efeitos `ao_comprar_status` das Cartas que chegaram a mao na ultima compra."""
    logs: list[str] = []
    drawn = list(piles.get("comprou") or [])
    piles["comprou"] = []
    for cid in drawn:
        spec = _spec(cid)
        if not spec:
            continue
        if spec.get("folego"):
            piles["folego"] = max(0, int(piles.get("folego", 0) or 0) + int(spec["folego"]))
            logs.append(
                f"{_name(cid)}: o corpo cobra {-int(spec['folego'])} de Fôlego nesta rodada."
            )
        if spec.get("condicao"):
            nome = str(spec["condicao"]).capitalize()
            turns = max(1, int(spec.get("rodadas", 1) or 1))
            cond = {"name": nome, "dot": 0, "duration": turns, "source": cid}
            cond.update(cm.NAMED_CONDITIONS.get(str(spec["condicao"]).lower(), {}))
            logs.append(cm.apply_condition(player, cond))
    return logs


def on_start(piles: dict, player: dict) -> list[str]:
    """Inicio do conflito: Sussurro se a Carga ja esta alta; efeitos da mao inicial."""
    if not active():
        return []
    player.pop("cartas_cena", None)  # sobra de conflito interrompido
    logs: list[str] = []
    if _abyss_high(player):
        _insert_sussurro(piles, player, "mao", logs)
    return logs + on_hand_drawn(piles, player)


def on_round_end(piles: dict, player: dict, wounds_before: dict[str, int]) -> list[str]:
    """Fim da rodada do jogador, ANTES de `begin_round` (que descarta a mao e compra)."""
    if not active():
        return []
    logs: list[str] = []
    # Dor Surda: pesou na mao uma rodada e sai do ciclo (exaurida ate o fim do conflito).
    for cid in list(piles["mao"]):
        if _spec(cid).get("exaurir_fim_rodada"):
            card_piles.exhaust(piles, cid)
            card_piles._forget(piles, cid)
    for cat in new_wounds(wounds_before, player):
        cid = WOUND_CARDS[cat]
        if card_piles.add_card(piles, cid, "compra"):
            logs.append(f"O ferimento abre espaço no Baralho: {_name(cid)}.")
    state = piles.get("sussurro")
    if isinstance(state, dict) and state.get("ativo"):
        if SUSSURRO_ID in piles["exaurida"]:  # foi jogada: tentacao paga, nada apodrece
            state["ativo"] = False
            player["cartas_cena"] = [
                c for c in (player.get("cartas_cena") or []) if c != SUSSURRO_ID
            ]
        else:
            state["rodadas"] = int(state.get("rodadas", 0) or 0) + 1
            if state["rodadas"] >= SUSSURRO_ROUNDS:
                _rot_sussurro(piles, player, logs)
    elif state is None and _abyss_high(player):
        _insert_sussurro(piles, player, "compra", logs)
    return logs


def _rot_sussurro(piles: dict, player: dict, logs: list[str]) -> None:
    """A tentacao que ninguem ouviu apodrece: vira o Fardo base em qualquer pilha."""
    for key in ("mao", "compra", "descarte"):
        piles[key] = [card_piles.FARDO_ID if c == SUSSURRO_ID else c for c in piles.get(key) or []]
    piles["retidas"] = [c for c in piles.get("retidas") or [] if c != SUSSURRO_ID]
    piles["fardos"] = int(piles.get("fardos", 0) or 0) + 1
    piles["sussurro"]["ativo"] = False
    player["cartas_cena"] = [c for c in (player.get("cartas_cena") or []) if c != SUSSURRO_ID]
    logs.append("O sussurro ignorado apodrece: vira um Estilhaço de Cinza no seu Baralho.")


def cleanup(player: dict) -> None:
    """Fim do conflito: as Cartas temporarias saem (as pilhas somem em `combat.py`)."""
    player.pop("cartas_cena", None)
