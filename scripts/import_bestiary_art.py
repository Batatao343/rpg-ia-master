"""SPEC-347 R13.2: importa a arte do bestiario para o catalogo curado (`data/visual_assets.json`).

Pasta de entrada::

    <pasta>/criaturas/{id_do_bestiario}.png     # ex.: criaturas/enemy_goblin.png  (ou bst:{pool_entry_id} -> bst_{id}.png)
    <pasta>/familias/{familia}.png              # ex.: familias/bruto.png  (familias de services/enemy_decks.FAMILIAS)

Uso::

    bash scripts/dev/py.sh scripts/import_bestiary_art.py <pasta>

Gera as variantes WebP (`asset_pipeline.process_image`) em `web/public/art/bestiario/`, calcula `sha256`
e grava as entradas (`visibility: public`). Falha se o id nao existir em `data/bestiary.json` / `FAMILIAS`.
Idempotente: reimportar o mesmo arquivo (mesmo sha256) nao muda nada.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import asset_pipeline  # noqa: E402
from services.enemy_decks import FAMILIAS  # noqa: E402

CATALOG = ROOT / "data" / "visual_assets.json"
BESTIARY = ROOT / "data" / "bestiary.json"
OUT_DIR = ROOT / "web" / "public" / "art" / "bestiario"
URL_BASE = "/art/bestiario"
VARIANT_NAME = {"thumb": "thumbnail", "full": "display"}
EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class ImportErrorArt(ValueError):
    pass


def _bestiary_ids(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: str(v.get("name") or k) for k, v in data.items() if isinstance(v, dict)}


def _subject_for(kind: str, stem: str, names: dict[str, str]) -> tuple[str, str, str]:
    """(subject_type, subject_id, titulo). Valida contra o bestiario / familias."""
    if kind == "familias":
        if stem not in FAMILIAS:
            raise ImportErrorArt(f"familia desconhecida: {stem!r} (validas: {', '.join(FAMILIAS)})")
        return "creature_family", stem, stem.replace("_", " ").capitalize()
    subject = "bst:" + stem[4:] if stem.startswith("bst_") else stem
    if not subject.startswith("bst:") and subject not in names:
        raise ImportErrorArt(f"criatura inexistente em data/bestiary.json: {stem!r}")
    return "creature", subject, names.get(subject, subject)


def import_folder(
    folder: Path,
    *,
    catalog_path: Path = CATALOG,
    bestiary_path: Path = BESTIARY,
    out_dir: Path = OUT_DIR,
    url_base: str = URL_BASE,
) -> dict[str, int]:
    names = _bestiary_ids(bestiary_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries: dict[tuple[str, str], dict[str, Any]] = {
        (a["subject_type"], a["subject_id"]): a for a in catalog["assets"]
    }
    stats = {"added": 0, "unchanged": 0}
    for kind in ("criaturas", "familias"):
        for src in sorted((folder / kind).glob("*") if (folder / kind).is_dir() else []):
            if src.suffix.lower() not in EXTS:
                continue
            subject_type, subject_id, title = _subject_for(kind, src.stem, names)
            payload = src.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            current = entries.get((subject_type, subject_id))
            if current and (current.get("source") or {}).get("sha256") == digest:
                stats["unchanged"] += 1
                continue
            slug = subject_id.replace(":", "-")
            target = out_dir / ("familias" if kind == "familias" else "criaturas") / slug
            target.mkdir(parents=True, exist_ok=True)
            variants: dict[str, Any] = {}
            for item in asset_pipeline.process_image(payload):
                name = f"{digest[:12]}.{item.variant}.webp"
                (target / name).write_bytes(item.payload)
                variants[VARIANT_NAME[item.variant]] = {
                    "url": f"{url_base}/{'familias' if kind == 'familias' else 'criaturas'}/{slug}/{name}",
                    "width": item.width,
                    "height": item.height,
                    "bytes": len(item.payload),
                    "sha256": item.sha256,
                }
            asset = {
                "asset_id": f"VAL-BST-{'FAM' if kind == 'familias' else 'CRI'}-{slug.upper()}-001",
                "subject_type": subject_type,
                "subject_id": subject_id,
                "title": title,
                "alt": f"Retrato de {title}",
                "visibility": "public",
                "source": {
                    "bundle": "BESTIARY_ART",
                    "relative_path": f"{kind}/{src.name}",
                    "sha256": digest,
                },
                "variants": variants,
                "placeholder_color": "#241d1a",
            }
            entries[(subject_type, subject_id)] = asset
            stats["added"] += 1
    if stats["added"]:
        catalog["assets"] = _stable(catalog_path, list(entries.values()))
        catalog_path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return stats


def _stable(catalog_path: Path, merged: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordem original das entradas existentes; as novas entram no fim, ordenadas."""
    original = json.loads(catalog_path.read_text(encoding="utf-8"))["assets"]
    order = {(a["subject_type"], a["subject_id"]): i for i, a in enumerate(original)}
    keyed = {(a["subject_type"], a["subject_id"]): a for a in merged}
    old = sorted((k for k in keyed if k in order), key=lambda k: order[k])
    new = sorted(k for k in keyed if k not in order)
    return [keyed[k] for k in old + new]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    args = parser.parse_args(argv)
    try:
        stats = import_folder(args.folder)
    except ImportErrorArt as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    print(f"importado: {stats['added']} · sem mudanca: {stats['unchanged']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
