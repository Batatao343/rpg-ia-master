"""SPEC-369 R7 - bot leitor de Pressagio, PRE-REGISTRADO (a regra da spec e o oraculo).

So importa: `docs/spec368/metricas_epico.py` (e por ele `scripts/cards/sim.py`) e
`services.enemy_intent`. Nada aqui altera avaliador, catalogo ou motor.

Regra (SPEC-369 §2 R7), implementada como esta escrita:
  1. le `enemy_intent.public_intent(intent, knowledge_level(enemy, carta_id), actors_by_id=...)`
     por intencao: o bot ve o que o jogador ve (faixa so com `conhecida`/`estudada`);
  2. ameaca prevista = soma, nas intencoes `ataque`/`ataque_multiplo` com `alvo_id == "player"`,
     de `(faixa[0] + faixa[1]) / 2`; sem faixa, cada ataque vale `ct._DANO_BASICO_DEFAULT`
     (Etapa 0: o valor e 3, `services/conflict_turn.py:233`; a spec citava 4);
  3. seria se >= 25 % da Vitalidade atual OU se deixaria o heroi abaixo de 50 % da maxima;
  4. seria -> TROCA o ataque de menor dano da declaracao de `sim.full_deck_decl` pela defesa
     (`sim._DEFENSE_KINDS`) de maior `valor` na mao; nao cabe no Folego -> mantem a declaracao;
  5. sem ameaca seria -> mira o inimigo que vai atacar o heroi e que o dano previsto das jogadas
     mata (Vitalidade <= soma); senao segue `alive[0]`;
  6. nada mais muda (mesma cura, mesma ordem, sem Pacto).
"""

from __future__ import annotations

import importlib.util
import os
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def _load_metricas_368():
    name = "metricas_epico_369"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "docs", "spec368", "metricas_epico.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


ME = _load_metricas_368()
sim = ME.sim
A = ME.A

from services import card_effects as fx  # noqa: E402
from services import (  # noqa: E402
    card_piles,
    cards,
    enemy_intent,
)
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_turn as ct  # noqa: E402

LIMIAR_VIT_ATUAL = 0.25
LIMIAR_VIT_MAXIMA = 0.50
_TIPOS_ATAQUE = ("ataque", "ataque_multiplo")

cego_decl = sim.full_deck_decl


def visoes(forecast: dict, actors: dict) -> list[dict]:
    """R7.1: a visao publica de cada intencao, no nivel de conhecimento do jogador."""
    out = []
    for aid, intents in (forecast or {}).items():
        enemy = actors.get(aid) or {"id": aid}
        for it in intents:
            level = enemy_intent.knowledge_level(enemy, it.get("carta_id"))
            out.append(enemy_intent.public_intent(it, level, actors_by_id=actors))
    return out


def ameaca_prevista(forecast: dict, actors: dict) -> float:
    """R7.2: dano previsto contra o heroi (meio da faixa; sem faixa, o dano padrao)."""
    total = 0.0
    for v in visoes(forecast, actors):
        if v.get("tipo") not in _TIPOS_ATAQUE or v.get("alvo_id") != "player":
            continue
        faixa = v.get("faixa")
        total += (faixa[0] + faixa[1]) / 2 if faixa else ct._DANO_BASICO_DEFAULT
    return total


def ameaca_seria(ameaca: float, player: dict) -> bool:
    """R7.3."""
    vit = int(player.get("vitalidade", 0) or 0)
    mx = int(player.get("max_vitalidade", 1) or 1)
    return ameaca >= LIMIAR_VIT_ATUAL * vit or (vit - ameaca) < LIMIAR_VIT_MAXIMA * mx


def _dano_passo(step: ct.TurnStep) -> int | None:
    """Dano de uma jogada de ataque; ``None`` se a jogada nao e ataque."""
    if step.kind == "attack":
        return ct._DANO_BASICO_DEFAULT
    if step.kind == "card" and sim._kind(step.card_id or "") in ct._ATTACK_EFFECTS:
        return A._card_damage(step.card_id or "")
    return None


def _valor_defesa(cid: str) -> int:
    return fx.base_value((cards.get_card(cid) or {}).get("efeito") or {})


def trocar_por_defesa(player: dict, piles: dict, decl: ct.TurnDeclaration, seen: dict | None):
    """R7.4: o ataque de menor dano (empate: o ultimo) vira a defesa de maior valor da mao."""
    steps = list(decl.jogadas)
    danos = [(d, -i) for i, s in enumerate(steps) if (d := _dano_passo(s)) is not None]
    if not danos:
        return decl
    idx = -min(danos)[1]
    usados = [s.card_id for s in steps if s.kind == "card"]
    resto = list(piles["mao"])
    for cid in usados:
        if cid in resto:
            resto.remove(cid)
    defesas = [c for c in resto if sim._kind(c) in sim._DEFENSE_KINDS and ME._usable(player, c)]
    if not defesas:
        return decl
    best = max(defesas, key=lambda c: (_valor_defesa(c), -resto.index(c)))
    novo = ct.TurnStep(kind="card", card_id=best, target_id="player")
    trial = [*steps[:idx], novo, *steps[idx + 1 :]]
    plan = card_piles.plan_plays(piles, player, trial)
    if not (plan["ok"] and plan["emprestado"] == 0):
        return decl
    if seen is not None:
        old = steps[idx]
        if old.kind == "card" and old.card_id in seen:
            seen[old.card_id][1] -= 1
        seen.setdefault(best, [0, 0])[1] += 1
    return ct.TurnDeclaration(actor_id="player", jogadas=trial)


def mirar(decl: ct.TurnDeclaration, alive: list[dict], forecast: dict) -> ct.TurnDeclaration:
    """R7.5: troca o alvo dos ataques para quem ameaca o heroi e morre com as jogadas."""
    if not alive:
        return decl
    atacam = {
        it.get("actor_id")
        for intents in (forecast or {}).values()
        for it in intents
        if it.get("tipo") in _TIPOS_ATAQUE and it.get("alvo_id") == "player"
    }
    dano = sum(d for s in decl.jogadas if (d := _dano_passo(s)) is not None)
    old = alive[0]["id"]
    for e in alive:
        if e["id"] in atacam and int(e.get("vitalidade", 0) or 0) <= dano:
            if e["id"] == old:
                return decl
            steps = [
                s.model_copy(update={"target_id": e["id"]}) if s.target_id == old else s
                for s in decl.jogadas
            ]
            return ct.TurnDeclaration(actor_id="player", jogadas=steps)
    return decl


def leitor_faixa_decl(player, piles, actors, sides, scene, forecast, seen) -> ct.TurnDeclaration:
    """R7 inteiro. ``scene`` fica na assinatura (contrato da spec); o bot nao a usa."""
    del scene
    alive = [actors[e] for e in sides.get("enemy", []) if orch._can_act(actors[e])]
    target = alive[0]["id"] if alive else "player"
    decl = sim.full_deck_decl(player, piles, target, seen)
    if ameaca_seria(ameaca_prevista(forecast, actors), player):
        return trocar_por_defesa(player, piles, decl, seen)
    return mirar(decl, alive, forecast)
