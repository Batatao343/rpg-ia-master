"""SPEC-325 R18: bots que EXERCITAM as capacidades de conflito (nao so a neutralidade da fiacao).

Os perfis atuais nunca declaram "sem matar", abordagem de fuga, "deixo <nome>", objeto de cena
nem ordem a aliado; por isso os gates R17 so provam que a fiacao nao muda o resultado. Cada
estrategia daqui monta um combate pre-armado (`seed_*`, idempotente) e roteiriza as acoes por
turno (`decide`). O uso e pelos cenarios de `playtest/scenarios.py` (`--scenario <nome>`);
`PROFILES`/`--all` ficam intactos (integridade de medida).
"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable

from playtest.profiles import ProfileDecision

PASS_DECLARATION = {"actor_id": "player", "acao": {"kind": "pass"}}
PHYSICAL = ["cortante", "perfurante", "impactante", "contundente", "igneo"]
OBJECT_ID = "pilar_rachado"
OBJECT_NAME = "Pilar Rachado"
OBJECT_LABEL = "derrubar"


def harmless(eid: str, name: str, **over) -> dict:
    """Inimigo resistente que nunca acerta o heroi (o cenario mede escolhas, nao letalidade)."""
    enemy = {
        "id": eid,
        "name": name,
        "type": "Minion",
        "categoria": "lacaio",
        "hp": 40,
        "max_hp": 40,
        "vitalidade": 40,
        "max_vitalidade": 40,
        "defense": 0,
        "esquiva": 0,
        "status": "ativo",
        "virtudes": {"forca": 0, "agilidade": 0, "corpo": 0, "mente": 0, "carisma": 0},
        "active_conditions": [],
        "ferimento_espacos": {"leve": 9, "grave": 9, "critico": 9},
        "attacks": [{"name": "Golpe", "bonus": -20, "damage": "1d1"}],
        "attack_mod": 0,
    }
    enemy.update(over)
    return enemy


def _start_combat(state: dict, enemies: list[dict]) -> None:
    state["enemies"] = enemies
    state["combat"] = {"round": 1, "active": True}
    state["combat_target"] = enemies[0]["name"]


def _in_active_combat(state: dict) -> bool:
    return bool((state.get("combat") or {}).get("active"))


def seed_resistencia(state: dict) -> None:
    from agents.bestiary import template_by_id

    base = template_by_id("enemy_iniciado_chama_azul") or {}
    # arquétipo único por execução: o bestiário legado persiste revelações entre campanhas,
    # e o cenário precisa observar a PRIMEIRA revelação (contagem determinística).
    unique = f"enemy_iniciado_chama_azul_{uuid.uuid4().hex[:8]}"
    enemy = harmless(
        "enemy_iniciado_chama_azul_1",
        str(base.get("name") or "Iniciado da Chama Azul"),
        archetype_id=unique,
        immunities=list(PHYSICAL),
    )
    _start_combat(state, [enemy])


def seed_nao_letal(state: dict) -> None:
    enemy = harmless(
        "soldado_1",
        "Soldado",
        hp=6,
        max_hp=6,
        vitalidade=6,
        max_vitalidade=6,
        archetype_id="soldado",
    )
    _start_combat(state, [enemy])


def seed_perseguidor(state: dict) -> None:
    chaser = harmless(
        "perseguidor_1",
        "Perseguidor",
        archetype_id="perseguidor",
        tactical_profile={"pursuit_policy": "persegue", "priorities": []},
    )
    _start_combat(state, [chaser])


def seed_companheiro_fuga(state: dict) -> None:
    from playtest import scenarios

    seed_perseguidor(state)
    for comp_id, soul in (state.get("companion_souls") or {}).items():
        if comp_id == scenarios.RECRUIT_NPC_ID:
            soul["approval"] = 80  # leal o bastante para ofertar o sacrificio
            soul["values"] = {**(soul.get("values") or {}), "coragem": 1}


def seed_objeto(state: dict) -> None:
    seed_perseguidor(state)  # alvo duravel; o objeto entra na cena apos a 1a rodada


def inject_object(state: dict) -> bool:
    """Apos a cena congelada (rodada 1), coloca o objeto interativo nela. Idempotente."""
    from services import encounter_preparation as prep

    scene = (state.get("combat") or {}).get("scene")
    if not isinstance(scene, dict) or scene.get("objects"):
        return False
    target = str((state.get("enemies") or [{}])[0].get("id") or "")
    effect = prep.materialize_effect(
        {"kind": "damage", "potency": "fraco", "params": {"target": target}},
        1,
        valid_targets={"player", target},
    )
    scene["objects"] = [
        {
            "id": OBJECT_ID,
            "name": OBJECT_NAME,
            "base_narrativa": "no centro da sala",
            "uses_remaining": 1,
            "interactions": [{"label": OBJECT_LABEL, "cost": "acao", "effect": effect}],
        }
    ]
    return True


def seed_reforco(state: dict) -> None:
    leader = harmless(
        "enemy_soldado_legiao_ferro_1",
        "Capitao da Legiao",
        categoria="elite",
        arquetipo="lider_matilha",
        faction="legiao_ferro",
        archetype_id="enemy_soldado_legiao_ferro",
        hp=14,
        max_hp=30,
        vitalidade=14,
        max_vitalidade=30,
    )
    _start_combat(state, [leader])
    player = copy.deepcopy(state.get("player") or {})
    player["level"] = max(5, int(player.get("level", 1) or 1))
    state["player"] = player
    # o perigo 3 vem do local do cenario (`scenarios.prepare` move para montanhas_afiadas)


# --- decisoes por turno ------------------------------------------------------
def _text(text: str) -> ProfileDecision:
    return ProfileDecision(text=text, mode="free_text")


def decide_resistencia(turn: int, state: dict) -> ProfileDecision:
    return _text("Ataco o Iniciado da Chama Azul.")


def decide_nao_letal(turn: int, state: dict) -> ProfileDecision:
    return _text("Derrubo o Soldado sem matar.")


def decide_foge_com_abordagem(turn: int, state: dict) -> ProfileDecision:
    script = (
        "Fujo pelos atalhos.",
        "Ataco o Perseguidor.",
        "Atiro uma flecha de longe no Perseguidor.",
        "Fujo correndo.",
    )
    return _text(script[(turn - 1) % len(script)])


def decide_deixa_companheiro(turn: int, state: dict) -> ProfileDecision:
    chase = (state.get("combat") or {}).get("chase") or {}
    if chase.get("sacrifice_offer"):
        return _text("Aceito o sacrifício.")
    if any(int(v) < 0 for v in (chase.get("last_luck") or {}).values()):
        return _text("Fujo e deixo a Brunna para trás.")
    return _text("Fujo do combate.")


def decide_usa_objeto(turn: int, state: dict) -> ProfileDecision:
    scene = (state.get("combat") or {}).get("scene") or {}
    if any(int(o.get("uses_remaining", 0) or 0) > 0 for o in scene.get("objects") or []):
        return _text(f"{OBJECT_LABEL.capitalize()} {OBJECT_NAME}.")
    return _text("Ataco o Perseguidor.")


def decide_ordena_aliado(turn: int, state: dict) -> ProfileDecision:
    orders = ("Brunna, proteger.", "Brunna, atacar.", "Brunna, recuar.")
    return _text(orders[(turn - 1) % len(orders)])


def decide_aguarda_reforco(turn: int, state: dict) -> ProfileDecision:
    return ProfileDecision(
        text="Aguardo e observo.", mode="declaration", declaration=PASS_DECLARATION
    )


# estrategia -> (seed, decide, capacidades exercitadas)
STRATEGIES: dict[str, tuple[Callable, Callable, tuple[str, ...]]] = {
    "combate_resistencia": (seed_resistencia, decide_resistencia, ("reveal_resist",)),
    "combate_nao_letal": (seed_nao_letal, decide_nao_letal, ("nonlethal",)),
    "fuga_escolhas": (
        seed_perseguidor,
        decide_foge_com_abordagem,
        ("chase_approach", "chase_attack"),
    ),
    "fuga_abandono": (seed_companheiro_fuga, decide_deixa_companheiro, ("chase_abandon",)),
    "combate_objeto": (seed_objeto, decide_usa_objeto, ("objects",)),
    "combate_ordem": (seed_companheiro_fuga, decide_ordena_aliado, ("companion_orders",)),
    "combate_reforco": (seed_reforco, decide_aguarda_reforco, ("reinforcements",)),
}
NAMES: tuple[str, ...] = tuple(STRATEGIES)


def decision_for(name: str, turn: int, state: dict) -> ProfileDecision:
    """Arma o combate quando nao ha um ativo (1o turno ou apos o desfecho do anterior, para o
    cenario nao derivar para encontros sorteados) e roteiriza a acao do turno."""
    seed, decide, _caps = STRATEGIES[name]
    if not _in_active_combat(state):
        seed(state)
    if name == "combate_objeto":
        inject_object(state)
    return decide(turn, state)


def required_capabilities(name: str) -> tuple[str, ...]:
    return STRATEGIES[name][2]
