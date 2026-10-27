"""SPEC-336 R5: promove Cartas do rascunho para o pool (`data/cards/posturas/`).

    bash scripts/dev/py.sh scripts/cards/promote.py data/cards/_rascunhos/<lote>.json \
        --onda 1 --autor claude --revisor-voz <nome> --sim-report sim.json

Só entram Cartas com lint verde (contra o pool e o próprio lote) E simulação sem
bandeira (`em_branco`/`dominante`). A revisão de voz do dono é por AMOSTRA de 20 %
(decisão D8): o script sorteia a amostra (determinística pela onda), a imprime e a
registra em `data/cards/_ondas.yaml` junto com `onda, data, autor, revisor_voz`.
`--revisor-voz <identificador>` é obrigatório e só vale para quem REVISOU; sem revisão,
`--voz-pendente` grava `revisor_voz: null` + `voz_status: pendente-dono` (o `validate_content`
avisa). `--dry-run` só mostra o que passaria. Sem `--sim-report` roda o protocolo de lote.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import gamedata  # noqa: E402
from services import card_effects as fx  # noqa: E402
from services import card_lint  # noqa: E402

CARDS_DIR = os.path.join(gamedata.DATA_DIR, "cards")
AMOSTRA_VOZ = 0.20


def ondas_path(cards_dir: str = CARDS_DIR) -> str:
    return os.path.join(cards_dir, "_ondas.yaml")


def load_ondas(cards_dir: str = CARDS_DIR) -> list[dict]:
    path = ondas_path(cards_dir)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list((yaml.safe_load(f) or {}).get("ondas") or [])


def voice_sample(ids: list[str], onda: int, fraction: float = AMOSTRA_VOZ) -> list[str]:
    """Amostra determinística (≥ 1) de ``fraction`` das cartas para a revisão de voz."""
    if not ids:
        return []
    k = max(1, round(len(ids) * fraction))
    ranked = sorted(ids, key=lambda c: hashlib.sha256(f"{onda}:{c}".encode()).hexdigest())
    return sorted(ranked[:k])


def _target_file(card: dict, cards_dir: str) -> str:
    name = f"{fx._fold(card.get('classe'))}_{fx._fold(card.get('subclasse') or 'neutra')}.json"
    return os.path.join(cards_dir, "posturas", name)


def evaluate(
    batch: list[dict], sim_report: dict, pool: list[dict], *, exigir_momento: bool = True
) -> tuple[list[dict], dict[str, list[str]]]:
    """(aprovadas, motivos_da_recusa por id)."""
    lint = card_lint.lint_batch(batch, pool, exigir_momento=exigir_momento)
    ok: list[dict] = []
    recusadas: dict[str, list[str]] = {}
    for card in batch:
        cid = card["id"]
        motivos = [str(i) for i in card_lint.errors(lint.get(cid, []))]
        sim = sim_report.get(cid)
        if sim is None:
            motivos.append("sem simulação (rode sim.py)")
        else:
            bandeiras = [
                b
                for b in sim.get("bandeiras", [])
                if b not in ("amostra_insuficiente", "uso_nao_medido")
            ]
            if bandeiras:
                motivos.append(f"simulação sinalizou: {', '.join(bandeiras)}")
        if motivos:
            recusadas[cid] = motivos
        else:
            ok.append(card)
    # R9: palavras-chave novas da onda valem para o conjunto que vai entrar
    for issue in card_lint.lint_wave(ok):
        recusadas.setdefault("__onda__", []).append(str(issue))
    return ok, recusadas


_REVISOR_REAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,39}$")
_REVISOR_FALSO = ("pendente", "posterior", "amostra", "depois", "tbd", "todo", "null", "none")


def revisor_valido(nome: str | None) -> bool:
    """Revisor real = um identificador (``dono``, ``guilherme``), nunca texto livre nem promessa."""
    nome = (nome or "").strip()
    return bool(_REVISOR_REAL.match(nome)) and not any(f in nome.lower() for f in _REVISOR_FALSO)


def promote(
    lote_path: str,
    sim_report: dict,
    *,
    onda: int,
    autor: str,
    revisor_voz: str | None = None,
    voz_pendente: bool = False,
    cards_dir: str = CARDS_DIR,
    dry_run: bool = False,
    data: str | None = None,
) -> dict:
    with open(lote_path, encoding="utf-8") as f:
        raw = json.load(f)
    batch = [fx.materialize(c) for c in raw.get("cards") or []]
    pool = card_lint.load_pool(cards_dir)
    ok, recusadas = evaluate(batch, sim_report, pool)
    if "__onda__" in recusadas:  # regra da onda: nada entra se ela falha
        ok = []
    ids = [c["id"] for c in ok]
    amostra = voice_sample(ids, onda)
    result = {"promovidas": ids, "recusadas": recusadas, "amostra_voz": amostra}
    if dry_run or not ok:
        return result
    # P1-1 (Sol): ninguém é registrado como revisor sem ter revisado. Sem revisor real, só com a
    # bandeira explícita `voz_pendente`: grava `revisor_voz: null` + `voz_status: pendente-dono`.
    if voz_pendente and revisor_voz:
        result["erro"] = "voz_pendente e revisor_voz são excludentes"
    elif not voz_pendente and not revisor_valido(revisor_voz):
        result["erro"] = (
            "revisor_voz precisa ser um revisor real (identificador, sem texto livre); "
            "sem revisão ainda, use --voz-pendente"
        )
    if result.get("erro"):
        result["promovidas"] = []
        return result
    by_file: dict[str, list[dict]] = {}
    for card in raw["cards"]:
        if card["id"] in ids:
            by_file.setdefault(_target_file(card, cards_dir), []).append({**card, "onda": onda})
    for path, novas in by_file.items():
        existing = {"_meta": "Cartas promovidas pela esteira SPEC-336.", "cards": []}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        existing["cards"] = list(existing.get("cards") or []) + novas
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
            f.write("\n")
    raw["cards"] = [c for c in raw["cards"] if c["id"] not in ids]
    with open(lote_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
        f.write("\n")
    ondas = load_ondas(cards_dir)
    ondas.append(
        {
            "onda": onda,
            "data": data or dt.date.today().isoformat(),
            "autor": autor,
            "revisor_voz": None if voz_pendente else revisor_voz.strip(),
            "voz_status": "pendente-dono" if voz_pendente else "aprovada",
            "amostra_voz": amostra,
            "cartas": ids,
        }
    )
    with open(ondas_path(cards_dir), "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump({"ondas": ondas}, f, allow_unicode=True, sort_keys=False)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lote")
    ap.add_argument("--onda", type=int, required=True)
    ap.add_argument("--autor", default="claude")
    ap.add_argument("--revisor-voz", default="")
    ap.add_argument(
        "--voz-pendente",
        action="store_true",
        help="promove sem revisão de voz: grava revisor_voz null e voz_status pendente-dono",
    )
    ap.add_argument("--sim-report", help="JSON de `sim.py --json`; sem ele roda a simulação")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.sim_report:
        with open(args.sim_report, encoding="utf-8") as f:
            sim_report = json.load(f)
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sim

        sim_report = sim.simulate_protocolo_lote(card_lint.load_batch(args.lote))
    res = promote(
        args.lote,
        sim_report,
        onda=args.onda,
        autor=args.autor,
        revisor_voz=args.revisor_voz or None,
        voz_pendente=args.voz_pendente,
        dry_run=args.dry_run,
    )
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if res.get("erro") or res["recusadas"] else 0


if __name__ == "__main__":
    sys.exit(main())
