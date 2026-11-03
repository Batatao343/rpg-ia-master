"""SPEC-371 R19: arena "a luta ensina" (offline, MockLLM, seeded).

Reproduzir:
    bash scripts/dev/py.sh scripts/fauna/arena_saber.py --regiao nova_arcadia --seeds 20 \
        --md docs/spec371/arena-saber-nova_arcadia.md --json docs/spec371/arena-saber-nova_arcadia.json

Para cada (criatura, Postura, seed) luta duas vezes com a MESMA seed: a luta 1 com
``bestiary_knowledge`` vazio; o ``bk`` que o produto real devolve (``fauna_saber.absorb`` por
rodada e ``fauna_saber.finish_combat`` ao fim, mais ``discovery.record_encounter/kills``) entra
na luta 2, com o ator carimbado por ``fauna_saber.stamp_actor`` (R8). O bot ``leitor`` age sobre
a linha pública do Presságio; sem saber ele e o bot ``cartas`` (a luta 2 so difere da 1 pelo
saber, entao a luta 1 e o controle exato de cada par).

AVALIADOR CONGELADO (D7): os limiares abaixo e este arquivo nao mudam depois do commit da
Etapa 1. Se E2/E3 falharem, o resultado vai ao dono (SPEC-371 §9); nunca se ajusta o avaliador.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("RPG_FORCE_MOCK", "1")
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Limiares congelados (R19 / D8) -----------------------------------------------------------
E1_MIN_REVELADOS = 0.30  # fracao de pares com saber_revelado depois da luta 1
E2_MIN_GANHO_PP = 3.0  # vitoria luta 2 - luta 1, nos pares revelados (agregado)
E3_MAX_RAZAO_VIT = 0.92  # Vitalidade perdida luta 2 / luta 1 (revelados e vencidos nas duas)
E4_MAX_VITORIA_2 = 0.92  # vitoria agregada da luta 2
E4_MAX_PIOR_PP = 2.0  # nenhuma criatura com luta 2 pior que a 1 em mais de 2 pp
LEVEL = 3
TURN_1, TURN_2 = 10, 20
MAX_ROUNDS = 20
FLAGS_ON = {
    "RPG_ENEMY_DECKS": "on",
    "RPG_ENEMY_INTENT": "on",
    "RPG_FAUNA_SABER": "on",
}

_A = None


def _arena():
    """Carrega a arena da SPEC-285 pelo recorte da SPEC-332 (como scripts/bestiario/arena.py)."""
    global _A
    if _A is None:
        spec = importlib.util.spec_from_file_location(
            "arena332", ROOT / "docs" / "spec332" / "arena_familias.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _A = mod.A
    return _A


def configure_env() -> None:
    for k, v in FLAGS_ON.items():
        os.environ[k] = v


def _fs():
    """Produto da SPEC-371; ausente (antes da implementacao), o saber nunca se revela."""
    try:
        from services import fauna_saber

        return fauna_saber
    except ImportError:
        return None


# --- Populacao --------------------------------------------------------------------------------
def population(regiao: str, ids: list[str] | None = None) -> list[str]:
    """Nao-chefe da regiao com assinatura e contra_jogo na ficha (fichas nao-retro)."""
    from services import bestiary_lint as bl

    A = _arena()
    out: list[str] = []
    for bid, ficha in sorted(bl.load_fichas(regiao).items()):
        if ficha.get("status") == "retro" or ficha.get("categoria") in ("chefe", "nomeado"):
            continue
        if not str(ficha.get("contra_jogo") or "").strip():
            continue
        if ids and bid not in ids:
            continue
        inst = A._instances(A.template_by_id(bid, encounter_level=A.DANGER_BY_LEVEL[LEVEL]), 1)[0]
        from services import enemy_decks as edk

        if edk.assinatura_of(inst):
            out.append(bid)
    return out


# --- Bot ---------------------------------------------------------------------------------------
def _triggers(rows: list[dict], player: dict) -> bool:
    vit = int(player.get("vitalidade", 0) or 0)
    for row in rows:
        if not row.get("prenuncio"):
            continue
        est = row.get("valor_estimado")
        if row.get("contra_jogo") or (est is not None and est >= 0.30 * vit):
            return True
    return False


def leitor_decl(player: dict, target_id: str, rows: list[dict]):
    """Defensiva so quando a linha publica pede: reacao preparada > Guardar > (nada mais)."""
    from services import cards
    from services import conflict_turn as ct

    A = _arena()
    base = A.hero_decl("cartas", player, target_id)
    if not _triggers(rows, player):
        return base
    for cid in player.get("prepared_cards") or []:
        card = cards.get_card(cid) or {}
        if card.get("tipo") == "reacao" and cards.can_use_card(player, cid):
            base.reaction_card_id = cid
            return base
    return ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="maneuver", maneuver="guardar")
    )


# --- Luta --------------------------------------------------------------------------------------
def fight(bid: str, n: int, cls: str, seed: int, bk: dict, turn: int) -> dict:
    """Uma luta completa; devolve desfecho, Vitalidade perdida e o ``bk`` resultante."""
    from services import conflict_orchestrator as orch
    from services import conflict_scene as cs
    from services import discovery as disc
    from services import enemy_decks as edk
    from services import enemy_intent as ei

    A = _arena()
    fs = _fs()
    random.seed(f"saber|{LEVEL}|{cls}|{bid}|{n}|{seed}")
    player = A.hero(cls, LEVEL)
    start_vit = int(player.get("vitalidade", 0) or 0)
    enemies = A._instances(A.template_by_id(bid, encounter_level=A.DANGER_BY_LEVEL[LEVEL]), n)
    bk = disc.record_encounter(dict(bk or {}), enemies, turn)
    if fs is not None:
        for e in enemies:
            fs.stamp_actor(e, bk)
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    rng = random.Random(seed)
    state = {"player": player}

    def forecast() -> tuple[dict, list[dict], int]:
        rnd_exec = cs.tactical_round(scene) + 1
        frozen = ei.forecast_round(
            scene, actors, sides, rng, scene_state={"_rodada_decisao": rnd_exec}
        )
        return frozen, ei.public_round(frozen, actors, rnd_exec), rnd_exec

    frozen, rows, _ = forecast()
    outcome = "timeout"
    for _rnd in range(1, MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            outcome = "win"
            break
        decl = leitor_decl(player, alive[0]["id"], rows)
        out = orch.run_round(
            scene,
            actors,
            sides,
            state,
            declarations={"player": decl},
            initiator=None,
            rng=rng,
            pressagios=frozen,
        )
        dead_player = bool(
            player.get("dead")
            or player.get("estado_terminal")
            or out.get("player_dead")
            or int(player.get("vitalidade", 0) or 0) <= 0
        )
        if fs is not None:
            bk, _logs = fs.absorb(bk, scene, actors, not dead_player, turn)
        if dead_player:
            outcome = "death"
            break
        if out.get("ended"):
            outcome = "win"
            break
        frozen, rows, rnd_exec = forecast()
        for row in rows:
            if row.get("prenuncio") and row.get("actor_id") in actors:
                edk.record_promise(scene, actors[row["actor_id"]], rnd_exec)
    dead = [e for e in enemies if e.get("dead") or int(e.get("vitalidade", 0) or 0) <= 0]
    bk = disc.record_kills(bk, dead, turn)
    if fs is not None:
        bk, _logs = fs.finish_combat(bk, enemies, turn)
    lost = max(0, start_vit - max(0, int(player.get("vitalidade", 0) or 0)))
    return {"outcome": outcome, "lost": lost, "bk": bk}


def run_pair(bid: str, cls: str, seed: int) -> dict:
    A = _arena()
    fichas_cat = _categoria(bid)
    n = A.group_size(fichas_cat, LEVEL)
    f1 = fight(bid, n, cls, seed, {}, TURN_1)
    revelado = bool((f1["bk"].get(bid) or {}).get("saber_revelado"))
    f2 = fight(bid, n, cls, seed, f1["bk"], TURN_2)
    return {
        "id": bid,
        "classe": cls,
        "seed": seed,
        "win1": f1["outcome"] == "win",
        "win2": f2["outcome"] == "win",
        "lost1": f1["lost"],
        "lost2": f2["lost"],
        "revelado": revelado,
    }


_CAT: dict[str, str] = {}


def _categoria(bid: str) -> str:
    if not _CAT:
        from services import bestiary_lint as bl

        for regiao_ficha in bl.load_fichas().values():
            _CAT[str(regiao_ficha["id"])] = str(regiao_ficha["categoria"])
    return _CAT[bid]


# --- Agregacao e veredito ----------------------------------------------------------------------
def _rate(xs: list[bool]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def aggregate(pairs: list[dict]) -> dict:
    rev = [p for p in pairs if p["revelado"]]
    both = [p for p in rev if p["win1"] and p["win2"]]
    por_criatura: dict[str, dict] = {}
    for p in pairs:
        c = por_criatura.setdefault(p["id"], {"n": 0, "w1": 0, "w2": 0, "rev": 0})
        c["n"] += 1
        c["w1"] += p["win1"]
        c["w2"] += p["win2"]
        c["rev"] += p["revelado"]
    pior = {
        bid: round((c["w2"] - c["w1"]) / c["n"] * 100, 1) for bid, c in sorted(por_criatura.items())
    }
    w1r, w2r = _rate([p["win1"] for p in rev]), _rate([p["win2"] for p in rev])
    l1 = sum(p["lost1"] for p in both) / len(both) if both else None
    l2 = sum(p["lost2"] for p in both) / len(both) if both else None
    return {
        "pares": len(pairs),
        "revelados": len(rev),
        "e1_frac_reveladas": round(len(rev) / len(pairs), 4) if pairs else 0.0,
        "e2_ganho_pp": round((w2r - w1r) * 100, 2) if rev else None,
        "e3_razao_vit": round(l2 / l1, 4) if both and l1 else None,
        "e3_pares": len(both),
        "e4_vitoria_2": round(_rate([p["win2"] for p in pairs]) or 0.0, 4),
        "e4_pior_pp": min(pior.values()) if pior else 0.0,
        "por_criatura_delta_pp": pior,
    }


def verdict(agg: dict) -> dict[str, bool]:
    e2 = agg["e2_ganho_pp"]
    e3 = agg["e3_razao_vit"]
    return {
        "E1": agg["e1_frac_reveladas"] >= E1_MIN_REVELADOS,
        "E2": e2 is not None and e2 >= E2_MIN_GANHO_PP,
        "E3": e3 is not None and e3 <= E3_MAX_RAZAO_VIT,
        "E4": agg["e4_vitoria_2"] <= E4_MAX_VITORIA_2 and agg["e4_pior_pp"] >= -E4_MAX_PIOR_PP,
    }


def run(regiao: str, seeds: int, ids: list[str] | None = None, classes: list[str] | None = None):
    configure_env()
    A = _arena()
    pop = population(regiao, ids)
    pairs: list[dict] = []
    for bid in pop:
        for cls in classes or list(A.CLASSES):
            for seed in range(seeds):
                pairs.append(run_pair(bid, cls, seed))
    agg = aggregate(pairs)
    return {
        "regiao": regiao,
        "seeds": seeds,
        "populacao": pop,
        "classes": classes or list(A.CLASSES),
        "agregado": agg,
        "veredito": verdict(agg),
        "pares": pairs,
    }


def relatorio(payload: dict) -> str:
    a, v = payload["agregado"], payload["veredito"]

    def mark(k: str) -> str:
        return "OK" if v[k] else "FALHA"

    e2 = "-" if a["e2_ganho_pp"] is None else f"{a['e2_ganho_pp']:+.2f} pp"
    e3 = "-" if a["e3_razao_vit"] is None else f"{a['e3_razao_vit']:.3f}x"
    linhas = [
        f"# Arena SPEC-371 - a luta ensina ({payload['regiao']})",
        "",
        f"{len(payload['populacao'])} criaturas x {len(payload['classes'])} Posturas x "
        f"{payload['seeds']} seeds = {a['pares']} pares; nivel {LEVEL}; MockLLM; bot `leitor`; "
        "flags `RPG_ENEMY_DECKS`, `RPG_ENEMY_INTENT`, `RPG_FAUNA_SABER` = on. "
        "Gerado por `scripts/fauna/arena_saber.py` (avaliador congelado).",
        "",
        "| Metrica | Resultado | Limiar | OK |",
        "|---|---|---|---|",
        f"| E1 fracao revelada | {a['e1_frac_reveladas']:.1%} ({a['revelados']}/{a['pares']}) "
        f"| >= {E1_MIN_REVELADOS:.0%} | {mark('E1')} |",
        f"| E2 ganho de vitoria (revelados) | {e2} | >= +{E2_MIN_GANHO_PP:.0f} pp | {mark('E2')} |",
        f"| E3 Vitalidade perdida 2/1 ({a['e3_pares']} pares) | {e3} "
        f"| <= {E3_MAX_RAZAO_VIT}x | {mark('E3')} |",
        f"| E4 vitoria luta 2 / pior criatura | {a['e4_vitoria_2']:.1%} / {a['e4_pior_pp']:+.1f} pp "
        f"| <= {E4_MAX_VITORIA_2:.0%} e >= -{E4_MAX_PIOR_PP:.0f} pp | {mark('E4')} |",
        "",
        "| Criatura | delta vitoria luta 2 - luta 1 (pp) |",
        "|---|---|",
    ]
    for bid, d in a["por_criatura_delta_pp"].items():
        linhas.append(f"| `{bid}` | {d:+.1f} |")
    return "\n".join(linhas) + "\n"


def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regiao", default="nova_arcadia")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--ids", default="", help="so estes ids (virgula)")
    ap.add_argument("--classes", default="", help="so estas Posturas (virgula)")
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    t0 = time.time()
    payload = run(
        args.regiao,
        args.seeds,
        [i for i in args.ids.split(",") if i] or None,
        [c for c in args.classes.split(",") if c] or None,
    )
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(dumps(payload), encoding="utf-8", newline="\n")
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(relatorio(payload), encoding="utf-8", newline="\n")
    print(relatorio(payload))
    print(f"elapsed {time.time() - t0:.0f}s", file=sys.stderr)
    return 0 if all(payload["veredito"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
