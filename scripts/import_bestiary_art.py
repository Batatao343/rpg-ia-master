"""SPEC-347 R13.2: importa a arte do bestiario para o catalogo curado (`data/visual_assets.json`).

Pasta de entrada::

    <pasta>/criaturas/{id_do_bestiario}.png     # ex.: criaturas/enemy_goblin.png  (pool: bst_{id}.png -> `bst:{id}`)
    <pasta>/familias/{familia}.png              # ex.: familias/bruto.png  (familias de services/enemy_decks.FAMILIAS)

Uso::

    bash scripts/dev/py.sh scripts/import_bestiary_art.py <pasta> [--force]

Gera `thumbnail` (384 px) e `display` (<= 768 px, dentro do teto de 300 KB do validador) em
`web/public/art/v1/bestiario/`, calcula `sha256` e grava as entradas (`visibility: public`) no mesmo formato do
resto do catalogo (`validate_visual_assets` passa sem mudar mais nada). Idempotente: reimportar o mesmo arquivo
nao muda nada. Trocar a arte de um id exige `--force`. Tudo e validado e codificado ANTES de escrever
qualquer arquivo (falha = nada gravado).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import asset_pipeline  # noqa: E402
from services.enemy_decks import FAMILIAS  # noqa: E402

CATALOG = ROOT / "data" / "visual_assets.json"
BESTIARY = ROOT / "data" / "bestiary.json"
OUT_DIR = ROOT / "web" / "public" / "art" / "v1" / "bestiario"
URL_BASE = "/art/v1/bestiario"
BUNDLE = "BESTIARY_ART"
EXTS = {".png", ".jpg", ".jpeg", ".webp"}
THUMB_CEILING = 120_000
DISPLAY_CEILING = 300_000
DISPLAY_BOUNDS = (768, 768)
BST_RE = re.compile(r"^bst_[a-z0-9][a-z0-9_-]*$")


class ImportErrorArt(ValueError):
    pass


def _bestiary_ids(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: str(v.get("name") or k) for k, v in data.items() if isinstance(v, dict)}


def _subject_for(kind: str, stem: str, names: dict[str, str]) -> tuple[str, str, str]:
    if kind == "familias":
        if stem not in FAMILIAS:
            raise ImportErrorArt(f"familia desconhecida: {stem!r} (validas: {', '.join(FAMILIAS)})")
        return "creature_family", stem, stem.replace("_", " ").capitalize()
    if stem.startswith("bst_"):
        if not BST_RE.match(stem):
            raise ImportErrorArt(f"id de criatura do pool invalido: {stem!r} (use bst_[a-z0-9_-]+)")
        return "creature", "bst:" + stem[4:], stem[4:].replace("_", " ").capitalize()
    if stem not in names:
        raise ImportErrorArt(f"criatura inexistente em data/bestiary.json: {stem!r}")
    return "creature", stem, names[stem]


def _encode_display(payload: bytes) -> tuple[bytes, int, int]:
    """WebP `display` (<= 768 px) abaixo do teto do validador; baixa a qualidade ate caber."""
    with Image.open(BytesIO(payload)) as src:
        image = src.convert("RGB")
    image.thumbnail(DISPLAY_BOUNDS, Image.Resampling.LANCZOS)
    for quality in (88, 80, 72, 64, 56, 48, 40):
        out = BytesIO()
        image.save(out, format="WEBP", quality=quality, method=6, exif=b"")
        if out.tell() <= DISPLAY_CEILING:
            return out.getvalue(), image.width, image.height
    raise ImportErrorArt(f"imagem nao cabe no teto de {DISPLAY_CEILING} bytes do display")


def _plan(
    folder: Path, names: dict[str, str], entries: dict[tuple[str, str], dict[str, Any]], force: bool
) -> tuple[list[dict[str, Any]], int]:
    """Valida e codifica tudo em memoria. Nada e escrito aqui."""
    plans: list[dict[str, Any]] = []
    unchanged = 0
    for kind in ("criaturas", "familias"):
        directory = folder / kind
        for src in sorted(directory.glob("*") if directory.is_dir() else []):
            if src.suffix.lower() not in EXTS:
                continue
            subject_type, subject_id, title = _subject_for(kind, src.stem, names)
            payload = src.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            current = entries.get((subject_type, subject_id))
            if current and (current.get("source") or {}).get("sha256") == digest:
                unchanged += 1
                continue
            if current and not force:
                curated = (current.get("source") or {}).get("bundle") != BUNDLE
                raise ImportErrorArt(
                    f"{subject_type}:{subject_id} ja tem arte"
                    f"{' CURADA a mao' if curated else ''}; use --force para trocar"
                )
            try:
                processed = {p.variant: p for p in asset_pipeline.process_image(payload)}
            except ValueError as exc:
                raise ImportErrorArt(f"{src.name}: {exc}") from exc
            thumb = processed["thumb"]
            if len(thumb.payload) > THUMB_CEILING:
                raise ImportErrorArt(f"{src.name}: thumbnail excede {THUMB_CEILING} bytes")
            display, w, h = _encode_display(payload)
            plans.append(
                {
                    "kind": kind,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "title": title,
                    "src": src.name,
                    "digest": digest,
                    "files": {
                        "thumbnail": (thumb.payload, thumb.width, thumb.height),
                        "display": (display, w, h),
                    },
                }
            )
    return plans, unchanged


def import_folder(
    folder: Path,
    *,
    catalog_path: Path = CATALOG,
    bestiary_path: Path = BESTIARY,
    out_dir: Path = OUT_DIR,
    url_base: str = URL_BASE,
    force: bool = False,
) -> dict[str, int]:
    names = _bestiary_ids(bestiary_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    original = catalog["assets"]
    entries = {(a["subject_type"], a["subject_id"]): a for a in original}
    plans, unchanged = _plan(folder, names, entries, force)
    if not plans:
        return {"added": 0, "unchanged": unchanged}
    written: list[Path] = []
    stale: list[Path] = []
    try:
        for plan in plans:
            slug = plan["subject_id"].replace(":", "-")
            sub = "familias" if plan["kind"] == "familias" else "criaturas"
            target = out_dir / sub / slug
            target.mkdir(parents=True, exist_ok=True)
            variants: dict[str, Any] = {}
            previous = entries.get((plan["subject_type"], plan["subject_id"]))
            for old in (
                (previous or {}).get("variants") or {}
            ).values():  # --force: some o WebP antigo
                rel = str(old.get("url", "")).removeprefix(url_base).lstrip("/")
                if rel and (out_dir / rel).is_file():
                    stale.append(out_dir / rel)
            for role, (data, w, h) in plan["files"].items():
                suffix = "thumb" if role == "thumbnail" else "display"
                name = f"{plan['digest'][:12]}.{suffix}.webp"
                (target / name).write_bytes(data)
                written.append(target / name)
                variants[role] = {
                    "url": f"{url_base}/{sub}/{slug}/{name}",
                    "width": w,
                    "height": h,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            entries[(plan["subject_type"], plan["subject_id"])] = {
                "asset_id": f"VAL-BST-{'FAM' if sub == 'familias' else 'CRI'}-{slug.upper()}-001",
                "subject_type": plan["subject_type"],
                "subject_id": plan["subject_id"],
                "title": plan["title"],
                "alt": f"Retrato de {plan['title']}",
                "visibility": "public",
                "source": {
                    "bundle": BUNDLE,
                    "relative_path": f"{plan['kind']}/{plan['src']}",
                    "sha256": plan["digest"],
                },
                "variants": variants,
                "placeholder_color": "#241d1a",
            }
        order = {(a["subject_type"], a["subject_id"]): i for i, a in enumerate(original)}
        keys = sorted(entries, key=lambda k: (order.get(k, len(order)), k))
        catalog["assets"] = [entries[k] for k in keys]
        catalog_path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for path in stale:
            path.unlink(missing_ok=True)
    except Exception:
        for path in written:  # sem WebP orfao quando algo falha no meio
            path.unlink(missing_ok=True)
        raise
    return {"added": len(plans), "unchanged": unchanged}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument(
        "--force", action="store_true", help="troca a arte de um id que ja tem entrada"
    )
    args = parser.parse_args(argv)
    try:
        stats = import_folder(args.folder, force=args.force)
    except ImportErrorArt as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    print(f"importado: {stats['added']} · sem mudanca: {stats['unchanged']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
