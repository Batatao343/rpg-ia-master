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
_BOOKKEEPING = {"_cartas_rodada"}


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in _BOOKKEEPING}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def run_card(card: dict) -> dict:
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

    random.seed(11)  # fórmulas de dado usam o `random` global
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
    out: dict = {"logs": []}
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
            rng=random.Random(7),
        )
        out = {k: v for k, v in out.items() if k != "cards_used"}
    elif tipo == "reacao":
        orch._resolve_reaction_effect(
            scene, player, "player", cards.get_card(cid), "e", actors, out, rng=random.Random(7)
        )
    else:
        # Só os stats não-nulos: a SPEC-330 acrescenta stats novos (zerados) ao dict.
        out["mods"] = {k: v for k, v in cm.combat_modifiers(player).items() if v}
        out["passives"] = cm.player_passives(player)
    blob = json.dumps(_strip([out, actors, scene]), sort_keys=True, default=str, ensure_ascii=False)
    return {"sha": hashlib.sha256(blob.encode("utf-8")).hexdigest(), "logs": out.get("logs", [])}


def legacy_cards() -> dict:
    from services import cards

    # As básicas da SPEC-328 (origem `cartas-328`) chegaram depois do golden.
    return {
        cid: c
        for cid, c in cards.all_cards().items()
        if "efeitos" not in c and c.get("origem") != "cartas-328"
    }


def build_golden() -> dict:
    return {cid: run_card(c) for cid, c in sorted(legacy_cards().items())}


if __name__ == "__main__":
    os.environ.setdefault("RPG_FORCE_MOCK", "1")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    golden = build_golden()
    with open(GOLDEN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(golden, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(f"{len(golden)} Cartas gravadas em {GOLDEN}")
