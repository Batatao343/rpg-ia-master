"""services/reactions.py — janela de reação, cadeia e Ataques de Oportunidade (spec conflito-06).

Mecânica PURA (dict-based, serializável) das Cartas de Reação e da interrupção do
conflito v2. NÃO decide QUANDO o inimigo reage (perfil tático é conflito-08) nem
desenha a UI (conflito-16): aqui só o motor —

    ação declarada → janela de reação → ofertas validadas (gatilho + limite de
    1 reação COMUM por cadeia + Entropia) → resolução em ordem,

mais o Ataque de Oportunidade UNIVERSAL, que fica FORA do limite de cadeia comum.

ADITIVO como 03/04/05: entrega o motor puro + testes; a fiação no nó de combate
(consulta da janela antes de resolver o ataque) acontece no cutover (conflito-13).
"""
from typing import Dict, List, Optional

# Gatilhos reconhecidos (R1/R2). Carta de reação declara `gatilho`; a ação em curso
# (ou uma reação anterior, R2) precisa casar. Vocabulário FECHADO — gatilho fora
# dele nunca casa (mesma filosofia do catálogo de efeitos da conflito-03).
GATILHOS = frozenset({
    "sempre", "ao_ser_atacado", "ao_ser_alvo", "aliado_atacado",
    "inimigo_se_move", "inimigo_ataca", "ao_sofrer_dano",
})


# --------------------------------------------------------------------------
# Casamento de gatilho
# --------------------------------------------------------------------------
def gatilho_matches(card: dict, action: dict, reactor_id: str) -> bool:
    """True se o `gatilho` da Carta de reação casa com a ação em curso (R1/R2).

    `action` descreve o que está sendo reagido: {"kind", "actor", "targets"[, ...]}.
    Pode ser a ação ORIGINAL declarada ou uma reação anterior (reação responde
    reação, R2). Gatilho ausente = "sempre"."""
    g = str(card.get("gatilho") or "sempre").strip().lower()
    if g not in GATILHOS:
        return False
    kind = str(action.get("kind") or "").lower()
    targets = action.get("targets") or []
    if g == "sempre":
        return True
    if g in ("ao_ser_atacado", "ao_sofrer_dano"):
        return kind == "attack" and reactor_id in targets
    if g == "ao_ser_alvo":
        return reactor_id in targets
    if g == "aliado_atacado":
        allies = (action.get("allies_of") or {}).get(reactor_id, [])
        return kind == "attack" and any(t in allies for t in targets)
    if g == "inimigo_se_move":
        return kind in ("move", "disengage_fail", "flee")
    if g == "inimigo_ataca":
        return kind == "attack" and action.get("actor") not in (
            (action.get("allies_of") or {}).get(reactor_id, []) + [reactor_id])
    return False


# --------------------------------------------------------------------------
# Janela / cadeia de reação
# --------------------------------------------------------------------------
def open_reaction_window(declared_action: dict) -> dict:
    """R1: abre a janela sobre uma ação JÁ declarada (alvos/escolhas/custos fixos).
    A declaração original não muda mais depois disso."""
    return {
        "triggering_action": dict(declared_action or {}),
        "used_common_reaction": [],   # participant_ids que já gastaram a comum (R3)
        "used_cards": [],             # [participant_id, card_id] — não repete na cadeia (R3)
        "links": [],                  # reações resolvidas, na ordem oferecida
        "closed": False,
    }


def _reaction_action(card: dict, participant_id: str) -> dict:
    """A 'ação' que uma reação representa — pode virar gatilho de outra reação (R2)."""
    return {
        "kind": "reaction",
        "actor": participant_id,
        "card_id": card.get("id"),
        "effect": card.get("efeito"),
        "targets": [],
    }


def offer_reaction(chain: dict, participant_id: str, card_id: str, *,
                   card: Optional[dict] = None, reactor: Optional[dict] = None,
                   respond_to_link: Optional[int] = None) -> bool:
    """Oferece uma reação COMUM na cadeia. Valida, nesta ordem (R1/R2/R3):
      1. cadeia aberta;
      2. Carta existe e é `tipo == "reacao"`;
      3. gatilho casa com a ação-alvo (original, ou a reação de `respond_to_link`);
      4. limite de 1 reação COMUM por personagem por cadeia;
      5. a MESMA Carta não repete na cadeia (salvo `repetivel`);
      6. Entropia suficiente (se `reactor` informado) — debitada no sucesso.
    Retorna True e registra o link; False sem efeito colateral."""
    if chain.get("closed"):
        return False
    c = card if card is not None else _get_card(card_id)
    if not c or c.get("tipo") != "reacao":
        return False

    # ação-alvo do casamento: reação anterior (R2) ou a ação original (R1)
    if respond_to_link is not None:
        links = chain.get("links") or []
        if not (0 <= respond_to_link < len(links)):
            return False
        target_action = links[respond_to_link].get("action") or {}
    else:
        target_action = chain.get("triggering_action") or {}
    if not gatilho_matches(c, target_action, participant_id):
        return False

    if participant_id in chain.get("used_common_reaction", []):
        return False
    pair = [participant_id, card_id]
    if not c.get("repetivel") and pair in chain.get("used_cards", []):
        return False

    custo = int(c.get("custo_entropia", 0) or 0)
    if reactor is not None and custo:
        if int(reactor.get("entropy", 0) or 0) < custo:
            return False
        reactor["entropy"] = int(reactor.get("entropy", 0)) - custo

    chain["links"].append({
        "participant": participant_id, "card_id": card_id, "custo": custo,
        "common": True, "action": _reaction_action(c, participant_id),
    })
    chain["used_common_reaction"].append(participant_id)
    chain["used_cards"].append(pair)
    return True


def resolve_chain(chain: dict) -> List[dict]:
    """R3: fecha a cadeia (ninguém mais reage) e devolve as reações resolvidas na
    ordem em que foram oferecidas. Idempotente."""
    chain["closed"] = True
    return list(chain.get("links") or [])


# --------------------------------------------------------------------------
# Ordem de reação (R4)
# --------------------------------------------------------------------------
def reaction_order(candidates: List[str], action: dict, *,
                   stats_by_id: Optional[Dict[str, dict]] = None,
                   target_allies: List[str] = (), actor_allies: List[str] = ()) -> List[str]:
    """R4: ordena candidatos por prioridade — alvo direto → aliados do alvo →
    aliados do ator → maior Agilidade → id (desempate estável)."""
    targets = set(action.get("targets") or [])
    ta, aa = set(target_allies), set(actor_allies)
    stats = stats_by_id or {}

    def tier(c: str) -> int:
        if c in targets:
            return 0
        if c in ta:
            return 1
        if c in aa:
            return 2
        return 3

    def agilidade(c: str) -> int:
        v = ((stats.get(c) or {}).get("virtudes") or {})
        try:
            return int(v.get("agilidade", 0) or 0)
        except (TypeError, ValueError):
            return 0

    return sorted(candidates, key=lambda c: (tier(c), -agilidade(c), str(c)))


# --------------------------------------------------------------------------
# Ataque de Oportunidade (R5) — universal, FORA do limite de cadeia comum
# --------------------------------------------------------------------------
def trigger_opportunity_attack(scene: dict, leaving_id: str, *,
                               allies: List[str] = (),
                               stats_by_id: Optional[Dict[str, dict]] = None) -> List[dict]:
    """R5: quem abandona um Engajamento SEM Desengajar provoca um Ataque de
    Oportunidade de CADA inimigo Engajado, consciente e capaz. Não conta pro limite
    de reação comum — cada apto faz o seu. Vale nos dois sentidos (party ou inimigo
    que abandona o Engajamento). Retorna uma lista de descritores de AoO."""
    positions = scene.get("positions") or {}
    pos = positions.get(leaving_id)
    if not pos:
        return []
    stats = stats_by_id or {}
    ally_set = set(allies)
    out: List[dict] = []
    for other in pos.get("engaged_with", []):
        if other in ally_set or other == leaving_id:
            continue
        if other not in positions:
            continue
        s = stats.get(other) or {}
        if not s.get("conscious", True) or s.get("incapacitated"):
            continue
        out.append({
            "attacker": other, "target": leaving_id,
            "kind": "opportunity_attack", "counts_common": False,
        })
    return out


# --------------------------------------------------------------------------
# Carga preguiçosa da Carta (evita ciclo de import com services.cards)
# --------------------------------------------------------------------------
def _get_card(card_id: str) -> Optional[dict]:
    from services import cards
    return cards.get_card(card_id)
