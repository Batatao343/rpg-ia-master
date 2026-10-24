"""npc_seed_review.py - revisão do dono das tabelas de semente de NPC (SPEC-306).

Só lê dados (zero LLM, zero rede). Subcomandos:

  build                        regrava docs/revisao/SPEC-306-sementes-npc.md
  check                        sai com 1 se a página gerada difere da versionada
  approve --ids a b | --all    remove `review` das linhas e regrava JSON + página
  sample --region R [--n N]    sorteia N sementes offline da região R

Uso: bash scripts/dev/py.sh scripts/npc_seed_review.py build
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Literal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services import npc_seed  # noqa: E402

SEED_TABLES_PATH = npc_seed.SEED_TABLES_PATH
REVIEW_PATH = os.path.join(ROOT, "docs", "revisao", "SPEC-306-sementes-npc.md")
TABLE_KEYS = npc_seed.TABLE_KEYS
ROW_KEYS = ("id", "label", "regions", "races", "factions", "source", "review")
CATEGORIES = ("universal", "regional", "raca", "facao")
CATEGORY_NAMES = {
    "universal": "universais",
    "regional": "regionais",
    "raca": "raça",
    "facao": "facção",
}
SAMPLE_GAME_ID = "review-306"
SAMPLES_PER_REGION = 10


def load_tables(path: str = SEED_TABLES_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _row_line(row: dict) -> str:
    ordered = {key: row[key] for key in ROW_KEYS if key in row}
    for key, value in row.items():  # chaves futuras não se perdem
        ordered.setdefault(key, value)
    return json.dumps(ordered, ensure_ascii=False)


def dump_tables(tables: dict) -> str:
    """Formato canônico (R17): uma linha por entrada, 2/4 espaços, LF, newline final."""
    out: list[str] = ["{"]
    keys = [k for k in tables if k not in TABLE_KEYS]
    head = [k for k in keys if k in ("_comment", "version")]
    tail = [k for k in keys if k not in head]
    blocks: list[str] = []
    for key in head + list(TABLE_KEYS) + tail:
        if key not in tables:
            continue
        value = tables[key]
        if key in TABLE_KEYS:
            lines = ",\n".join(f"    {_row_line(row)}" for row in value)
            blocks.append(f"  {json.dumps(key)}: [\n{lines}\n  ]")
        else:
            blocks.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}")
    out.append(",\n".join(blocks))
    out.append("}")
    return "\n".join(out) + "\n"


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def classify(row: dict) -> Literal["universal", "regional", "raca", "facao"]:
    if row.get("factions"):
        return "facao"
    if row.get("races"):
        return "raca"
    if row.get("regions"):
        return "regional"
    return "universal"


def regional_matrix(tables: dict, regions: list[str] | None = None) -> dict[str, dict[str, int]]:
    """região -> tabela -> linhas com a região em `regions` e sem `factions` (R7)."""
    if regions is None:
        regions = list(npc_seed.lore_ids()["regions"])
        regions.sort()
    matrix: dict[str, dict[str, int]] = {}
    for region in regions:
        matrix[region] = {
            table: sum(
                1
                for row in tables.get(table, [])
                if region in (row.get("regions") or []) and not row.get("factions")
            )
            for table in TABLE_KEYS
        }
    return matrix


def _names() -> dict[str, dict[str, str]]:
    from gamedata import DATA_DIR

    def read(name: str) -> dict:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as handle:
            return json.load(handle)

    origins = read("origins.json")
    factions = read("factions.json")
    return {
        "regions": {r["id"]: r["name"] for r in origins.get("regions", [])},
        "races": {r["id"]: r["name"] for r in origins.get("races", [])},
        "factions": {fid: f.get("name", fid) for fid, f in factions.items()},
    }


def _filters_text(row: dict, names: dict[str, dict[str, str]]) -> str:
    parts: list[str] = []
    for field, title in (("regions", "regiões"), ("races", "raças"), ("factions", "facções")):
        values = row.get(field) or []
        if values:
            shown = ", ".join(names[field].get(v, v) for v in values)
            parts.append(f"{title}: {shown}")
    return "; ".join(parts) if parts else "universal"


def sample(region: str, n: int = SAMPLES_PER_REGION) -> list[dict[str, str]]:
    lore = npc_seed._lore()
    locations = lore["locations_by_region"].get(region) or []
    if not locations:
        raise ValueError(f"região sem local: {region}")
    return [
        npc_seed.seed_labels(
            npc_seed.roll_npc_seed(game_id=SAMPLE_GAME_ID, turn=turn, location_id=locations[0])
        )
        for turn in range(n)
    ]


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_review(tables: dict) -> str:
    names = _names()
    regions = list(names["regions"])
    lines: list[str] = [
        "# SPEC-306 - Revisão das sementes de NPC",
        "",
        "> Gerado por `scripts/npc_seed_review.py build` a partir de "
        "`data/npc_seed_tables.json`. **Não edite à mão.**",
        f"> Versão das tabelas: {tables.get('version', '?')}.",
        "",
        "Marque `[x]` o que aprova e anote o que deve mudar. Para aprovar: diga "
        '"aprovo as sementes" (ou a lista de ids) e o coordenador roda '
        "`npc_seed_review.py approve`. Ids recusados são reescritos, nunca apagados.",
        "",
        "## Totais",
        "",
        "| Tabela | Total | Pendentes | "
        + " | ".join(CATEGORY_NAMES[c] for c in CATEGORIES)
        + " |",
        "|---|---|---|" + "---|" * len(CATEGORIES),
    ]
    for table in TABLE_KEYS:
        rows = tables.get(table, [])
        counts = {c: sum(1 for r in rows if classify(r) == c) for c in CATEGORIES}
        pending = sum(1 for r in rows if r.get("review"))
        cells = " | ".join(str(counts[c]) for c in CATEGORIES)
        lines.append(f"| {table} | {len(rows)} | {pending} | {cells} |")
    lines += [
        "",
        "## Cobertura regional (linhas sem facção por região)",
        "",
        "| Região | " + " | ".join(TABLE_KEYS) + " |",
        "|---|" + "---|" * len(TABLE_KEYS),
    ]
    matrix = regional_matrix(tables, regions)
    for region in regions:
        cells = " | ".join(str(matrix[region][t]) for t in TABLE_KEYS)
        lines.append(f"| {names['regions'][region]} | {cells} |")
    for table in TABLE_KEYS:
        pending_rows = [r for r in tables.get(table, []) if r.get("review")]
        lines += ["", f"## {table} - pendentes de leitura ({len(pending_rows)})", ""]
        if not pending_rows:
            lines.append("_Nenhuma linha pendente._")
            continue
        lines += ["| OK | id | rótulo | filtros | fonte |", "|---|---|---|---|---|"]
        for row in pending_rows:
            lines.append(
                f"| [ ] | `{row['id']}` | {_cell(row['label'])} | "
                f"{_cell(_filters_text(row, names))} | `{row.get('source', '')}` |"
            )
    lines += [
        "",
        f"## Exemplos sorteados (game_id `{SAMPLE_GAME_ID}`, turnos 0 a {SAMPLES_PER_REGION - 1})",
        "",
    ]
    for region in regions:
        lines += [f"### {names['regions'][region]}", ""]
        for index, labels in enumerate(sample(region, SAMPLES_PER_REGION)):
            race = names["races"].get(labels["raca"], labels["raca"])
            faction = (
                names["factions"].get(labels["faccao"], "") if labels["faccao"] else "sem facção"
            )
            lines.append(
                f"{index + 1}. {race} ({faction}) - {labels['profissao']}; "
                f"quer {labels['desejo']}; teme {labels['medo']}; "
                f"segredo: {labels['segredo_pessoal']}; "
                f"contradição: {labels['contradicao']}; "
                f"maneirismo: {labels['maneirismo']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def approve(tables: dict, ids: set[str] | None) -> dict:
    """Remove `review` das linhas (ids=None => todas). Devolve cópia nova."""
    result = {k: v for k, v in tables.items() if k not in TABLE_KEYS}
    for table in TABLE_KEYS:
        new_rows = []
        for row in tables.get(table, []):
            row = dict(row)
            if ids is None or row.get("id") in ids:
                row.pop("review", None)
            new_rows.append(row)
        result[table] = new_rows
    return {k: result[k] for k in tables}


def _read_review_file() -> str:
    try:
        with open(REVIEW_PATH, encoding="utf-8", newline="") as handle:
            return handle.read()
    except OSError:
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("check")
    p_ap = sub.add_parser("approve")
    p_ap.add_argument("--ids", nargs="+", default=[])
    p_ap.add_argument("--all", action="store_true")
    p_sm = sub.add_parser("sample")
    p_sm.add_argument("--region", required=True)
    p_sm.add_argument("--n", type=int, default=SAMPLES_PER_REGION)
    args = parser.parse_args(argv)

    if args.cmd == "build":
        write_text(REVIEW_PATH, render_review(load_tables()))
        print(f"gerado: {os.path.relpath(REVIEW_PATH, ROOT)}")
        return 0
    if args.cmd == "check":
        if _read_review_file() != render_review(load_tables()):
            print("página de revisão desatualizada: rode `npc_seed_review.py build`")
            return 1
        print("página de revisão em dia")
        return 0
    if args.cmd == "approve":
        if not args.all and not args.ids:
            parser.error("informe --ids ... ou --all")
        tables = load_tables()
        known = {r["id"] for t in TABLE_KEYS for r in tables.get(t, [])}
        unknown = sorted(set(args.ids) - known)
        if unknown:
            print(f"ids desconhecidos: {', '.join(unknown)}")
            return 1
        updated = approve(tables, None if args.all else set(args.ids))
        write_text(SEED_TABLES_PATH, dump_tables(updated))
        write_text(REVIEW_PATH, render_review(updated))
        print("aprovado; JSON e página regravados")
        return 0
    for labels in sample(args.region, args.n):
        print(json.dumps(labels, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
