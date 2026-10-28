"""SPEC-330 D-3: equivalência das 308 Cartas legadas contra o motor ANTERIOR.

Este módulo usa SÓ APIs que já existiam antes da SPEC-330 (nada de
`services.card_effects`), para poder rodar também no código da `main` pré-330 e
gerar o golden commitado em `tests/fixtures/spec330_legacy_golden.json`:

    bash scripts/dev/py.sh tests/spec330_equivalence.py  # grava o golden

O teste (`test_card_effects_grammar.py`) roda o mesmo cenário no motor novo e exige
o mesmo hash por Carta. Chaves de contabilidade introduzidas pela SPEC-330 que não
mudam resultado (`_cartas_rodada`) ficam fora da comparação.
"""

import hashlib
import json
import os
import random
import sys

GOLDEN = os.path.join(os.path.dirname(__file__), "fixtures", "spec330_legacy_golden.json")
_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}
_BOOKKEEPING = {"_cartas_rodada", "ferimento", "ticks", "scene_logs"}  # SPEC-346: só registro


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in _BOOKKEEPING}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


# P2-4 (revisao Sol): alem da seed 7 (acerto garantido pela Mira), duas seeds SEM Mira
# exercitam erro, acerto e critico; passivas disparam `on_hit`/`on_attack`; utilitarias
# passam por `cards.use_card`. A chave `extra` guarda esses cenarios.
EXTRA_SEEDS = (2, 13, 21)  # erro, critico, acerto (sem Mira)


def run_card(card: dict, seed: int = 7, mira: bool = True) -> dict:
    """Resolve a Carta como o motor faz (por tipo) e devolve {sha, logs}."""
    import combat_mechanics as cm
    from services import cards
    from services import conflict_orchestrator as orch
    from services import conflict_scene as cs
    from services import conflict_turn as ct

    def actor(aid, **kw):
        base = {"id": aid, "name": aid, "virtudes": dict(_V)}
        base.update(kw)
        return orch.ensure_combat_sheet(base, is_player=(aid == "player"))

    random.seed(11 if seed == 7 else seed)  # fórmulas de dado usam o `random` global
    cid = card["id"]
    player = actor(
        "player",
        class_name=card.get("classe") or "Devoto do Abismo",
        known_cards=[cid],
        prepared_cards=[cid],
        entropy=99,
        max_entropy=99,
        level=20,
    )
    if mira:
        cm.apply_condition(
            player, {"name": "Mira", "dot": 0, "duration": 9, "stat": "attack", "delta": 40}
        )
    actors = {
        "player": player,
        "e": actor("e"),
        "ally": actor("ally", categoria="companheiro", transient=True),
    }
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    tipo = card.get("tipo")
    kind = str((card.get("efeito") or {}).get("kind"))
    out: dict = {"logs": [], "deaths": [], "terminal": []}
    if tipo == "ativa":
        target = "player" if kind in ct._SUPPORT_EFFECTS else "e"
        out = ct.resolve_turn(
            scene,
            actors,
            ct.TurnDeclaration(
                actor_id="player", acao=ct.TurnStep(kind="card", card_id=cid, target_id=target)
            ),
            state={"player": player},
            sides={"hero": ["player", "ally"], "enemy": ["e"]},
            rng=random.Random(seed),
        )
        out = {k: v for k, v in out.items() if k != "cards_used"}
    elif tipo == "reacao":
        orch._resolve_reaction_effect(
            scene, player, "player", cards.get_card(cid), "e", actors, out, rng=random.Random(seed)
        )
    else:
        # Só os stats não-nulos: a SPEC-330 acrescenta stats novos (zerados) ao dict.
        out["mods"] = {k: v for k, v in cm.combat_modifiers(player).items() if v}
        out["passives"] = cm.player_passives(player)
        if seed == 7:  # gatilhos on_hit/on_attack (passiva/virtude) e uso da utilitaria
            trig: dict = {"logs": []}
            for trigger in ("on_attack", "on_hit"):
                fired = ct._fire_triggered_passive(player, trigger, trig)
                trig[trigger] = fired
            if tipo == "utilitaria":
                trig["uso"] = cards.use_card({"player": player}, cid)
            trig["usage"] = player.get("card_usage")
            out["gatilhos"] = trig
    blob = json.dumps(_strip([out, actors, scene]), sort_keys=True, default=str, ensure_ascii=False)
    return {
        "sha": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "logs": out.get("logs", []),
        "res": [a.get("resultado") for a in out.get("attacks") or []],
    }


def run_card_full(card: dict) -> dict:
    """Cenario base (seed 7, Mira) + `extra` (seeds sem Mira)."""
    res = run_card(card)
    res["extra"] = {f"s{sd}": run_card(card, seed=sd, mira=False) for sd in EXTRA_SEEDS}
    return res


def legacy_cards() -> dict:
    """As Cartas do golden (308): filtra pelas CHAVES do golden, não por `origem` (cartas
    novas de specs posteriores não exigem editar este helper)."""
    from services import cards

    with open(GOLDEN, encoding="utf-8") as f:
        keys = set(json.load(f))
    return {cid: c for cid, c in cards.all_cards().items() if cid in keys}


def build_golden() -> dict:
    return {cid: run_card_full(c) for cid, c in sorted(legacy_cards().items())}


if __name__ == "__main__":
    os.environ.setdefault("RPG_FORCE_MOCK", "1")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    golden = build_golden()
    with open(GOLDEN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(golden, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(f"{len(golden)} Cartas gravadas em {GOLDEN}")
