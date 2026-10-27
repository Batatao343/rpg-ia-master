"""services/card_rewards.py - Espolio de Cartas, Forja do baralho e Cicatrizes (SPEC-333).

Puro e deterministico, ZERO LLM: o sorteio usa `random.Random(f"{seed}:espolio")` (seed do
conflito) e o ouro/material so se movem aqui (mecanica e Python). Flag
`RPG_CARD_REWARDS=off|shadow|on` (padrao `off`; valor invalido vira `off`): com `off` o
conflito nao toca loot/XP/saves; `shadow` so mede (telemetria `source=auto`, nada gravado).

Estado no `player` (todos opcionais; save antigo carrega sem eles):
    espolio_pendente   {id, ofertas[3], origem, turno, recusa_ouro}  (expira no proximo conflito)
    forja_esquecer     int   cargas de "Esquecer" ganhas no descanso longo
    afiadas            {card_id: True}   versao `+` permanente (lida por cards.effective_card)
    cicatriz_cartas    [{scar_id, card_id}]   maldicao permanente por Cicatriz (Fardo)
"""

from __future__ import annotations

import os
import random
from typing import Any, Literal

import inventory as inv_mod
from services import card_telemetry, cards

Mode = Literal["off", "shadow", "on"]

OFFER_COUNT = 3
REFUSE_GOLD = 15  # D7: recusar o espolio paga 15 de ouro
SOURCE_WEIGHTS = (("postura", 60), ("neutra", 25), ("saque", 15))
RARITY_WEIGHTS = (("comum", 70), ("incomum", 25), ("rara", 5))
BOSS_RARITY_WEIGHTS = (("comum", 60), ("incomum", 25), ("rara", 10), ("abissal", 5))
FORGET_GOLD = 25  # Esquecer no templo: por ouro, sem limite
PURGE_GOLD = 40  # Purgar uma Cicatriz no templo / com Medico de Campo
RARE_MATERIAL_RARITIES = frozenset({"raro", "rara", "rare", "epico", "lendario"})
_DECK_TIPOS = cards._DECK_TIPOS
_TEMPLE_TAGS = frozenset({"templo", "santuario", "curandeiro", "hospicio"})
_SCAR_CURSE = {
    "cabeca": "mld_cicatriz_cabeca",
    "torso": "mld_cicatriz_torso",
    "braco": "mld_cicatriz_braco",
    "perna": "mld_cicatriz_perna",
}
SCAR_CURSE_DEFAULT = "mld_cicatriz_geral"


def mode() -> Mode:
    raw = str(os.getenv("RPG_CARD_REWARDS", "off") or "off").strip().lower()
    return raw if raw in ("off", "shadow", "on") else "off"  # type: ignore[return-value]


def _fold(text: Any) -> str:
    from services.card_effects import _fold as fold

    return fold(text)


# ==========================================================================
# Sorteio do espolio (R1)
# ==========================================================================
def rarity_of(card: dict) -> str:
    """comum | incomum | rara | abissal. `raridade` explicita vence; senao deriva do patamar
    (epica -> rara; apice -> abissal)."""
    explicit = str(card.get("raridade") or "")
    if explicit in ("comum", "incomum", "rara", "abissal"):
        return explicit
    from services import card_effects as fx

    base = fx.raridade(card)
    return {"epica": "rara", "apice": "abissal"}.get(base, base)


def _is_boss(enemy: dict) -> bool:
    return str(enemy.get("categoria") or enemy.get("type") or "").lower() in {"chefe", "boss"}


def _eligible(card: dict | None, player: dict, *, boss: bool) -> bool:
    if not card or card.get("tipo") not in _DECK_TIPOS or card.get("basica"):
        return False
    if card.get("origem") == "cartas-333" or card.get("tipo") in cards.STATUS_TIPOS:
        return False
    level = int(player.get("level", 1) or 1)
    if int(card.get("level_req", 1) or 1) > level:  # R2: respeita tier/level_req do nivel
        return False
    if (card.get("apex") or rarity_of(card) == "abissal") and not boss:
        return False
    return True


def _pools(player: dict, defeated: list[dict], *, boss: bool, region_ids: set[str]) -> dict:
    import progression

    known = set(player.get("known_cards") or [])
    postura = sorted(
        cid
        for cid in progression.eligible_cards(player)
        if _eligible(cards.get_card(cid), player, boss=boss)
    )
    neutra = sorted(
        cid
        for cid, c in cards.all_cards().items()
        if cid not in known
        and (c.get("classe") in ("", "Neutra", "neutra", None) or c.get("neutra"))
        and not c.get("regiao_exclusiva")
        and _eligible(c, player, boss=boss)
        and (not c.get("regiao") or str(c.get("regiao")) in region_ids)
    )
    saque_ids: set[str] = set()
    for enemy in defeated:
        saque_ids.update(cards.enemy_card_ids(enemy))
    saque = sorted(
        cid
        for cid in saque_ids
        if cid not in known and _eligible(cards.get_card(cid), player, boss=boss)
    )
    return {"postura": postura, "neutra": neutra, "saque": saque}


def _weighted(rng: random.Random, weights: tuple[tuple[str, int], ...], allowed: set[str]) -> str:
    rows = [(k, w) for k, w in weights if k in allowed]
    total = sum(w for _, w in rows)
    roll = rng.uniform(0, total)
    acc = 0.0
    for key, weight in rows:
        acc += weight
        if roll <= acc:
            return key
    return rows[-1][0]


def roll_rewards(
    state: dict,
    conflict_summary: dict | None,
    seed: int,
    *,
    defeated: list[dict] | None = None,
) -> list[str]:
    """3 Cartas do espolio (R1), deterministico pela seed do conflito. 60 % Postura, 25 %
    neutras/regionais, 15 % "Saque de tecnica" (Cartas dos derrotados); raridade 70/25/5;
    Abissal so com chefe derrotado. Pool vazio de uma fonte cai nas outras (nunca repete)."""
    player = state.get("player") or {}
    defeated = [e for e in (defeated or []) if isinstance(e, dict)]
    boss = any(_is_boss(e) for e in defeated)
    world = state.get("world") or {}
    region_ids = {
        str(v)
        for v in (world.get("current_location_id"), world.get("region_id"), world.get("region"))
        if v
    }
    pools = _pools(player, defeated, boss=boss, region_ids=region_ids)
    rng = random.Random(f"{int(seed)}:espolio")
    weights = BOSS_RARITY_WEIGHTS if boss else RARITY_WEIGHTS
    order = [r for r, _ in weights]
    chosen: list[str] = []
    for _ in range(OFFER_COUNT):
        live = {k for k, ids in pools.items() if any(c not in chosen for c in ids)}
        if not live:
            break
        src = _weighted(rng, SOURCE_WEIGHTS, live)
        pool = [c for c in pools[src] if c not in chosen]
        present = {rarity_of(cards.get_card(c) or {}) for c in pool} & set(order)
        want = _weighted(rng, weights, present or set(order))
        exact = [c for c in pool if rarity_of(cards.get_card(c) or {}) == want]
        pick_from = exact or pool
        chosen.append(pick_from[rng.randrange(len(pick_from))])
    return chosen


def grant_after_conflict(
    state: dict,
    player: dict,
    *,
    conflict_id: str,
    seed: int,
    defeated: list[dict],
    objective_result: str | None,
    turn: int,
) -> dict | None:
    """Gancho do fim de conflito (R1/R3). So chamado em vitoria real ou objetivo cumprido.
    `on`: grava `espolio_pendente` no `player`; `shadow`: so mede; `off`: nada."""
    m = mode()
    if m == "off" or objective_result == "falhou":
        return None
    offers = roll_rewards({**state, "player": player}, None, seed, defeated=defeated)
    if not offers:
        return None
    if m == "shadow":
        with card_telemetry.source_scope("auto"):  # nao e escolha do jogador
            card_telemetry.offered(offers)
        return None
    pending = {
        "id": str(conflict_id),
        "ofertas": offers,
        "origem": "objetivo" if objective_result == "cumprido" else "vitoria",
        "turno": int(turn),
        "recusa_ouro": REFUSE_GOLD,
    }
    player["espolio_pendente"] = pending
    return pending


def expire_pending(player: dict) -> None:
    """R3: o espolio nao decidido expira quando o proximo conflito comeca."""
    player.pop("espolio_pendente", None)


# ==========================================================================
# Aceitar / recusar (R1/R2)
# ==========================================================================
def _fail(msg: str, *, conflito: bool = False) -> dict:
    """`conflito` = o estado do jogo impede agora (a API responde 409, nao 400)."""
    return {"ok": False, "error": msg, "log": "", "conflito": conflito}


def _set_prepared_from_deck(player: dict) -> None:
    keep = [
        c
        for c in (player.get("prepared_cards") or [])
        if (cards.get_card(c) or {}).get("tipo") not in _DECK_TIPOS
    ]
    player["prepared_cards"] = list(dict.fromkeys(list(player.get("deck") or []) + keep))


def _deck_room(player: dict, card_id: str) -> bool:
    deck = list(player.get("deck") or [])
    if len(deck) >= cards.DECK_MAX:
        return False
    card = cards.get_card(card_id) or {}
    limit = 2 if card.get("patamar") in cards._COMMON_PATAMARES and not card.get("apex") else 1
    return deck.count(card_id) < limit


def _add_to_deck(player: dict, card_id: str) -> str:
    """R2: Acervo sempre; baralho por padrao (se houver espaco e copias); sem baralho
    (flag do Baralho desligada) vira Preparada quando ha vaga. Devolve onde caiu."""
    known = list(player.get("known_cards") or [])
    if card_id not in known:
        known.append(card_id)
    player["known_cards"] = known
    if player.get("deck"):
        if _deck_room(player, card_id):
            player["deck"] = list(player["deck"]) + [card_id]
            _set_prepared_from_deck(player)
            return "baralho"
        return "acervo"
    prepared = list(player.get("prepared_cards") or [])
    if card_id not in prepared and len(prepared) < cards.prepare_slots_for_level(
        player.get("level", 1)
    ):
        player["prepared_cards"] = prepared + [card_id]
        return "preparadas"
    return "acervo"


def accept(state: dict, card_id: str | None) -> dict:
    """R1: escolhe 1 das ofertas (`card_id`) ou recusa (`None`/""): recusar paga ouro."""
    player = state.get("player") or {}
    pending = player.get("espolio_pendente")
    if not isinstance(pending, dict) or not pending.get("ofertas"):
        return _fail("Não há espólio de Cartas pendente.")
    offers = [str(c) for c in pending["ofertas"]]
    if card_id:
        if str(card_id) not in offers:
            return _fail("Essa Carta não está no espólio.")
        if str(card_id) in set(player.get("known_cards") or []):
            return _fail("Você já conhece essa Carta.")
    with card_telemetry.source_scope("espolio"):
        card_telemetry.offered(offers, picked=str(card_id or ""))
        if card_id:
            card_telemetry.picked(str(card_id))
    player.pop("espolio_pendente", None)
    if not card_id:
        gold = int(pending.get("recusa_ouro", REFUSE_GOLD) or 0)
        player["gold"] = int(player.get("gold", 0) or 0) + gold
        return {
            "ok": True,
            "error": None,
            "card_id": None,
            "gold": gold,
            "destino": "ouro",
            "log": f"Você deixa o espólio e leva {gold} de ouro.",
        }
    where = _add_to_deck(player, str(card_id))
    name = (cards.get_card(str(card_id)) or {}).get("name", card_id)
    return {
        "ok": True,
        "error": None,
        "card_id": str(card_id),
        "gold": 0,
        "destino": where,
        "log": f"{name} entra no seu Acervo" + (" e no Baralho." if where == "baralho" else "."),
    }


# ==========================================================================
# Forja (fora de combate; R4/R5/R6)
# ==========================================================================
def on_long_rest(player: dict) -> None:
    """R4: cada descanso longo concede UMA carga de Esquecer (nao acumula alem de 1)."""
    if mode() == "off":
        return
    player["forja_esquecer"] = 1


def at_temple(state: dict) -> bool:
    """Templo/curandeiro: tag de local `templo`/`santuario`/..., ou cidade segura."""
    import gamedata

    loc_id = (state.get("world") or {}).get("current_location_id")
    loc = gamedata.get_location(str(loc_id)) if loc_id else {}
    tags = {_fold(t) for t in (loc.get("tags") or [])} if isinstance(loc, dict) else set()
    return bool(tags & _TEMPLE_TAGS) or {"cidade", "seguro"} <= tags


def _medic_available(state: dict) -> bool:
    player = state.get("player") or {}
    classes = [player.get("class_name", "")] + [
        m.get("class_name", "") for m in (state.get("party") or []) if m.get("active", True)
    ]
    return any("medico" in _fold(c) for c in classes)


def _pad_with_basics(player: dict) -> None:
    """R6: baralho abaixo do minimo completa com as basicas da Postura."""
    basics = cards.basicas_for_class(str(player.get("class_name", "")))
    pad = (basics["golpe"][:1] + basics["guarda"][:1]) or []
    deck = list(player.get("deck") or [])
    i = 0
    while pad and len(deck) < cards.DECK_MIN:
        deck.append(pad[i % len(pad)])
        i += 1
    player["deck"] = deck


def _guard_forge(state: dict) -> dict | None:
    allowed, reason = cards.reorganize_status(state)
    if not allowed:
        return _fail(reason or "Não é seguro mexer no Baralho agora.", conflito=True)
    if not (state.get("player") or {}).get("deck"):
        return _fail("Você ainda não tem um Baralho de Conflito.")
    return None


def forget(state: dict, card_id: str, via: str) -> dict:
    """R4: tira 1 copia do BARALHO (o Acervo fica). `via`: `descanso` (1 por descanso longo)
    ou `templo` (por ouro, sem limite). Maldicao de Cicatriz so sai com Purgar."""
    if (err := _guard_forge(state)) is not None:
        return err
    player = state["player"]
    deck = list(player.get("deck") or [])
    if card_id not in deck:
        return _fail("Essa Carta não está no seu Baralho.")
    if card_id in cards.scar_curse_ids(player):
        return _fail("Uma Cicatriz não se esquece: só sai com Purgar.")
    basics = {
        c
        for ids in cards.basicas_for_class(str(player.get("class_name", ""))).values()
        for c in ids
    }
    if card_id in basics and len(deck) <= cards.DECK_MIN:
        return _fail("O Baralho já está no mínimo: não há o que afinar nas básicas.")
    gold = 0
    if via == "descanso":
        if int(player.get("forja_esquecer", 0) or 0) < 1:
            return _fail("Só dá para esquecer uma Carta depois de um descanso longo.")
    elif via == "templo":
        if not at_temple(state):
            return _fail("Só um templo ou curandeiro ajuda a esquecer uma Carta.")
        gold = FORGET_GOLD
        if int(player.get("gold", 0) or 0) < gold:
            return _fail(f"Faltam {gold} de ouro para a oferenda.")
    else:
        return _fail("Via de esquecimento inválida.")
    if via == "descanso":
        player["forja_esquecer"] = int(player.get("forja_esquecer", 0) or 0) - 1
    else:
        player["gold"] = int(player.get("gold", 0) or 0) - gold
    deck.remove(card_id)
    player["deck"] = deck
    _pad_with_basics(player)
    _set_prepared_from_deck(player)
    name = (cards.get_card(card_id) or {}).get("name", card_id)
    return {
        "ok": True,
        "error": None,
        "card_id": card_id,
        "gold": gold,
        "log": f"Você esquece {name}: ela continua no Acervo, mas sai do Baralho.",
    }


def can_sharpen_card(card: dict) -> bool:
    """A versao `+` precisa mudar algo (valor numerico do efeito ou custo definido em `afiada`)."""
    import copy

    return cards._apply_afiada(copy.deepcopy(card)) != card


def sharpen_material(player: dict) -> str | None:
    """Primeiro `material` raro do inventario (R5)."""
    from gamedata import ARTIFACTS_DB

    for entry in player.get("inventory") or []:
        item = ARTIFACTS_DB.get(entry.get("id", "")) or {}
        if (
            item.get("type") == "material"
            and str(item.get("rarity") or "").lower() in RARE_MATERIAL_RARITIES
            and int(entry.get("qty", 1) or 1) > 0
        ):
            return str(entry["id"])
    return None


def sharpen(state: dict, card_id: str) -> dict:
    """R5: Carta COMUM do Acervo vira a versao `+`, consumindo 1 material raro."""
    if (err := _guard_forge(state)) is not None:
        return err
    player = state["player"]
    card = cards.get_card(card_id)
    if card is None or card_id not in set(player.get("known_cards") or []):
        return _fail("Essa Carta não está no seu Acervo.")
    if rarity_of(card) != "comum" or card.get("tipo") not in _DECK_TIPOS:
        return _fail("Só Cartas comuns podem ser afiadas.")
    if (player.get("afiadas") or {}).get(card_id):
        return _fail("Essa Carta já foi afiada.")
    if not can_sharpen_card(card):
        return _fail("Essa Carta não tem o que afiar.")
    material = sharpen_material(player)
    if material is None:
        return _fail("Falta um material raro para afiar.")
    player["inventory"], taken = inv_mod.remove_item(list(player.get("inventory") or []), material)
    if not taken:  # defensivo: remove_item devolve o inventario original sem mutar
        return _fail("Falta um material raro para afiar.")
    player.setdefault("afiadas", {})[card_id] = True
    return {
        "ok": True,
        "error": None,
        "card_id": card_id,
        "material": material,
        "log": f"{card.get('name', card_id)} é afiada: nasce a versão +.",
    }


# ==========================================================================
# Cicatriz -> maldicao permanente (R8)
# ==========================================================================
def curse_card_for_scar(scar: dict) -> str:
    origem = _fold(scar.get("origem") or "")
    sid = _fold(scar.get("id") or "")
    for region, cid in _SCAR_CURSE.items():  # a regiao do Ferimento (no id) vence o texto livre
        if f"scar_{region}" in sid:
            return cid
    for region, cid in _SCAR_CURSE.items():
        if region in origem:
            return cid
    return SCAR_CURSE_DEFAULT


def register_scar_curse(player: dict, scar: dict) -> str | None:
    """Liga a Cicatriz a uma maldicao (Fardo) no baralho, permanente ate Purgar. Idempotente
    por `scar.id`. Com a flag `off` nao toca a ficha."""
    if mode() == "off" or not scar.get("id"):
        return None
    rows = list(player.get("cicatriz_cartas") or [])
    if any(r.get("scar_id") == scar["id"] for r in rows):
        return None
    cid = curse_card_for_scar(scar)
    rows.append({"scar_id": str(scar["id"]), "card_id": cid})
    player["cicatriz_cartas"] = rows
    if player.get("deck"):
        player["deck"] = list(player["deck"]) + [cid]
        _set_prepared_from_deck(player)
    return cid


def purge_curse(state: dict, scar_id: str, via: str) -> dict:
    """R8: trata a Cicatriz fora de combate — `templo` ou `medico` (Medico de Campo no
    grupo/ficha), por ouro. Tira a maldicao do baralho; a Cicatriz em si segue na ficha."""
    allowed, reason = cards.reorganize_status(state)
    if not allowed:
        return _fail(reason or "Não é seguro tratar a Cicatriz agora.", conflito=True)
    player = state.get("player") or {}
    rows = list(player.get("cicatriz_cartas") or [])
    row = next((r for r in rows if r.get("scar_id") == scar_id), None)
    if row is None:
        return _fail("Essa Cicatriz não pesa no seu Baralho.")
    if via == "templo":
        if not at_temple(state):
            return _fail("Só um templo ou curandeiro trata uma Cicatriz.")
    elif via == "medico":
        if not _medic_available(state):
            return _fail("Não há um Médico de Campo com você.")
    else:
        return _fail("Via de tratamento inválida.")
    if int(player.get("gold", 0) or 0) < PURGE_GOLD:
        return _fail(f"Faltam {PURGE_GOLD} de ouro para o tratamento.")
    player["gold"] = int(player.get("gold", 0) or 0) - PURGE_GOLD
    rows.remove(row)
    player["cicatriz_cartas"] = rows
    deck = list(player.get("deck") or [])
    if row["card_id"] in deck:
        deck.remove(row["card_id"])
        player["deck"] = deck
        _pad_with_basics(player)
        _set_prepared_from_deck(player)
    return {
        "ok": True,
        "error": None,
        "scar_id": scar_id,
        "gold": PURGE_GOLD,
        "log": "A Cicatriz deixa de pesar no seu Baralho (a marca na pele fica).",
    }


# ==========================================================================
# Visao publica (API) - so quando ha o que mostrar
# ==========================================================================
def card_view(card_id: str) -> dict:
    from services import card_effects as fx

    card = cards.get_card(card_id) or {}
    return {
        "id": card_id,
        "name": card.get("name", card_id),
        "tipo": card.get("tipo"),
        "classe": card.get("classe"),
        "raridade": rarity_of(card),
        "custo_folego": cards.custo_folego(card),
        "custo_entropia": int(card.get("custo_entropia", 0) or 0),
        "texto": fx.render_card_text(card),
        "descricao": card.get("descricao", ""),
    }


def public_pending(player: dict) -> dict | None:
    pending = player.get("espolio_pendente")
    if mode() == "off" or not isinstance(pending, dict) or not pending.get("ofertas"):
        return None
    known = set(player.get("known_cards") or [])
    return {
        "id": pending.get("id"),
        "origem": pending.get("origem"),
        "recusa_ouro": int(pending.get("recusa_ouro", REFUSE_GOLD) or 0),
        "ofertas": [
            {**card_view(cid), "conhecida": cid in known} for cid in pending.get("ofertas") or []
        ],
    }


def public_forge(state: dict) -> dict | None:
    """Bloco `forja` do state: so com a flag ligada e um Baralho ativo. O servidor decide o
    que esta permitido (o front nunca reproduz a regra)."""
    player = state.get("player") or {}
    if mode() != "on" or not player.get("deck"):
        return None
    allowed, reason = cards.reorganize_status(state)
    temple = at_temple(state)
    gold = int(player.get("gold", 0) or 0)
    curses = [
        {
            "scar_id": r.get("scar_id"),
            "card_id": r.get("card_id"),
            "name": (cards.get_card(str(r.get("card_id"))) or {}).get("name", r.get("card_id")),
        }
        for r in (player.get("cicatriz_cartas") or [])
    ]
    counts: dict[str, int] = {}
    for cid in player.get("deck") or []:
        counts[cid] = counts.get(cid, 0) + 1
    protected = set(cards.scar_curse_ids(player))
    baralho = sorted(
        (
            {
                "id": cid,
                "name": (cards.get_card(cid) or {}).get("name", cid),
                "copias": n,
                "esquecivel": cid not in protected,
            }
            for cid, n in counts.items()
        ),
        key=lambda r: (str(r["name"]).lower(), r["id"]),
    )
    afiaveis = sorted(
        cid
        for cid in player.get("known_cards") or []
        if (cards.get_card(cid) or {}).get("tipo") in _DECK_TIPOS
        and rarity_of(cards.get_card(cid) or {}) == "comum"
        and can_sharpen_card(cards.get_card(cid) or {})
        and not (player.get("afiadas") or {}).get(cid)
    )
    return {
        "permitido": allowed,
        "motivo": reason,
        "baralho": baralho,
        "baralho_min": cards.DECK_MIN,
        "esquecer": {
            "descanso": int(player.get("forja_esquecer", 0) or 0) > 0,
            "templo": temple and gold >= FORGET_GOLD,
            "ouro": FORGET_GOLD,
        },
        "afiar": {
            "material": sharpen_material(player),
            "afiaveis": afiaveis,
            "afiadas": sorted((player.get("afiadas") or {}).keys()),
        },
        "cicatrizes": curses,
        "purgar": {
            "templo": temple and gold >= PURGE_GOLD,
            "medico": _medic_available(state) and gold >= PURGE_GOLD,
            "ouro": PURGE_GOLD,
        },
    }
