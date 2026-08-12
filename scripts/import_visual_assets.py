"""Importa o handoff aprovado de arte para derivados web auditáveis.

Uso:
  uv run python scripts/import_visual_assets.py --source-root <VALORIA_GAME_ART_HANDOFF>
  uv run python scripts/import_visual_assets.py --source-root <...> --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "visual_assets.json"
OUTPUT_ROOT = ROOT / "web" / "public" / "art" / "v1"

RACE_SOURCES = {
    "race_humanos": "VAL-ANCHOR-CULT-HUMANO_URBANO-001__female.png",
    "race_elfos": "VAL-ANCHOR-RACE-ELFO-001__female.png",
    "race_anoes_fuligem": "VAL-ANCHOR-RACE-ANAO_FULIGEM-001__female.png",
    "race_vrel": "VAL-ANCHOR-RACE-VREL-001__female.png",
    "race_cinzeus": "VAL-ANCHOR-RACE-CINZEU-001__female.png",
    "race_osshari": "VAL-ANCHOR-CULT-OSSHARI_MAR-001__female.png",
}

CLASS_SOURCES = {
    "Devoto do Abismo": "VAL-P4-CLS-DEVOTO_ABISMO-001.png",
    "Sangromante": "VAL-P4-CLS-SANGROMANTE-001.png",
    "Corruptor": "VAL-P4-CLS-CORRUPTOR-001.png",
    "Arcanista Cinzento": "VAL-P4-CLS-ARCANISTA_CINZENTO-001.png",
    "Médico de Campo": "VAL-P4-CLS-MEDICO_CAMPO-001.png",
}

LOCATION_SOURCES = {
    "nova_arcadia": "VAL-ANCHOR-LOC-NOVA_ARCADIA-001.png",
    "na_anel_dourado": "VAL-ANCHOR-LOC-ANEL_DOURADO-001.png",
    "na_anel_ferro": "VAL-ANCHOR-LOC-ANEL_DE_FERRO-001.png",
    "na_anel_lama": "VAL-ANCHOR-LOC-ANEL_DE_LAMA-001.png",
    "pantano_melancolia": "VAL-ANCHOR-LOC-PANTANO_MELANCOLIA-001.png",
    "deserto_zhur": "VAL-ANCHOR-LOC-ZHUR-001.png",
    "floresta_sussurros": "VAL-P2-LOC-FLORESTA_CORACAO-001.png",
    "selva_xylos": "VAL-ANCHOR-LOC-XYLOS-001.png",
    "skallgard": "VAL-ANCHOR-LOC-SKALLGARD-001.png",
    "sk_fortaleza_vorr": "VAL-P3-LOC-FORTALEZA_VORR_INTERIOR-001.png",
    "sk_farol_chama_negra": "VAL-P2-LOC-FAROL_CHAMA_NEGRA-001.png",
    "aethelgard": "VAL-ANCHOR-LOC-AETHELGARD-001.png",
    "ae_ruinas_submersas": "VAL-P2-LOC-CATEDRAL_AFUNDADA-001.png",
    "ophidia": "VAL-P2-LOC-OPHIDIA_HORIZONTE-001.png",
    "costa_negra": "VAL-P2-LOC-CEMITERIO_LEVIATAS-001.png",
    "cn_o_trono": "VAL-P2-LOC-TRONO_RESPIRA-001.png",
    "montanhas_afiadas": "VAL-ANCHOR-LOC-MONTANHAS_AFIADAS-001.png",
    "pradaria_ruinas": "VAL-ANCHOR-LOC-PRADARIA_RUINAS-001.png",
    "pr_vaelorn": "VAL-P2-LOC-VAELORN-001.png",
    "pr_solvhen": "VAL-P2-LOC-SOLVHEN-001.png",
    "brekmar": "VAL-ANCHOR-LOC-BREKMAR-001.png",
    "ae_camara_seca": "VAL-P2-LOC-AETHELGARD_ENTRADA_SECA-001.png",
}

LOCATION_FALLBACKS = {
    "pm_profundezas": "pantano_melancolia",
    "dz_borda_do_vazio": "deserto_zhur",
    "fs_fronteira_xylos": "floresta_sussurros",
    "sx_cidades_hospedeiros": "selva_xylos",
    "sx_profundezas": "selva_xylos",
    "ma_saidas_baixas": "montanhas_afiadas",
    "ma_boca": "montanhas_afiadas",
    "pr_ruinas_assombradas": "pradaria_ruinas",
    "bk_docas_velhas": "brekmar",
    "na_taverna_javali": "na_anel_lama",
    "pm_cripta_afogada": "pantano_melancolia",
    "sk_salao_do_jarl": "skallgard",
    "ma_forja_profunda": "montanhas_afiadas",
}

NPC_SOURCES = {
    "npc_aelwin_o_ultimo_conselheiro": "VAL-P2-NPC-AELWIN-001.png",
    "npc_arcante_gresh": "VAL-P2-NPC-ARCANTE_GRESH-001.png",
    "npc_astrin_veia_fina": "VAL-P2-NPC-ASTRIN-001.png",
    "npc_grum": "VAL-P2-NPC-GRUM-001.png",
    "npc_kahen": "VAL-P2-NPC-KAHEN-001.png",
    "npc_khatarn_olhos_de_obsidiana": "VAL-P2-NPC-KHATARN-001.png",
    "npc_lady_aerwen": "VAL-P2-NPC-LADY_AERWEN-001.png",
    "npc_velha_magda": "VAL-P2-NPC-MAGDA_PUBLICA-001.png",
    "npc_onda_profunda": "VAL-P2-NPC-ONDA_PROFUNDA-001.png",
    "npc_doutor_silas_vane": "VAL-P2-NPC-SILAS_VANE-001.png",
    "npc_valerius": "VAL-P2-NPC-VALERIUS-001.png",
    "npc_vehkr_punho_de_gelo": "VAL-P2-NPC-VEHKR-001.png",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_entry(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise ValueError(f"fonte ausente: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256.lower():
        raise ValueError(f"SHA-256 divergente em {path}: {actual} != {expected_sha256}")


def _slug(value: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _find_row(rows: list[dict[str, Any]], filename: str) -> dict[str, Any]:
    matches = [row for row in rows if Path(row["handoff_relative_path"]).name == filename]
    if len(matches) != 1:
        raise ValueError(f"esperada uma entrada para {filename}; encontradas {len(matches)}")
    return matches[0]


def _save_webp(image: Image.Image, path: Path, max_width: int, ceiling: int) -> dict[str, Any]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if image.width > max_width:
        height = round(image.height * max_width / image.width)
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    minimum_width = 320 if max_width <= 640 else 512
    while True:
        for quality in range(82, 37, -4):
            image.save(path, "WEBP", quality=quality, method=6, exif=b"")
            if path.stat().st_size <= ceiling:
                break
        if path.stat().st_size <= ceiling or image.width <= minimum_width:
            break
        next_width = max(minimum_width, round(image.width * 0.9))
        next_height = round(image.height * next_width / image.width)
        image = image.resize((next_width, next_height), Image.Resampling.LANCZOS)
    if path.stat().st_size > ceiling:
        raise ValueError(f"derivado excede teto de {ceiling} bytes: {path}")
    return {
        "url": "/" + path.relative_to(ROOT / "web" / "public").as_posix(),
        "width": image.width,
        "height": image.height,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _build_asset(row: dict[str, Any], subject_type: str, subject_id: str,
                 source_root: Path, output_root: Path) -> dict[str, Any]:
    source = (source_root / row["handoff_relative_path"]).resolve()
    if source_root.resolve() not in source.parents:
        raise ValueError(f"fonte fora da raiz: {source}")
    if row.get("status") != "approved" or row.get("visibility") != "public":
        raise ValueError(f"asset não público/aprovado: {row.get('asset_id')}")
    verify_source_entry(source, str(row["sha256_expected"]))
    source_sha = sha256_file(source)
    slug = _slug(subject_id)
    kind_dir = output_root / subject_type
    thumb_width = 640 if subject_type == "location" else 384
    display_width = 1280 if subject_type == "location" else 768
    display_ceiling = 400_000 if subject_type == "location" else 300_000
    with Image.open(source) as image:
        thumb_path = kind_dir / f"{slug}.{source_sha[:12]}.thumb.webp"
        display_path = kind_dir / f"{slug}.{source_sha[:12]}.webp"
        thumbnail = _save_webp(image, thumb_path, thumb_width, 120_000)
        display = _save_webp(image, display_path, display_width, display_ceiling)
    title = str(row.get("suggested_game_subject") or row.get("title") or subject_id)
    return {
        "asset_id": row["asset_id"],
        "subject_type": subject_type,
        "subject_id": subject_id,
        "title": title,
        "alt": f"Arte de {title}",
        "visibility": "public",
        "source": {
            "bundle": "VALORIA_GAME_ART_HANDOFF",
            "relative_path": row["handoff_relative_path"],
            "sha256": source_sha,
        },
        "variants": {"thumbnail": thumbnail, "display": display},
        "placeholder_color": "#241d1a",
    }


def import_assets(source_root: Path, catalog_path: Path = CATALOG_PATH,
                  output_root: Path = OUTPUT_ROOT, *, check: bool = False,
                  prune: bool = False) -> dict[str, Any]:
    source_root = source_root.resolve()
    rows = json.loads((source_root / "manifests" / "game_art_manifest.json").read_text(
        encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("manifesto deve ser uma lista")
    selections: list[tuple[str, str, str]] = []
    selections += [("race", sid, filename) for sid, filename in RACE_SOURCES.items()]
    selections += [("class", sid, filename) for sid, filename in CLASS_SOURCES.items()]
    selections += [("location", sid, filename) for sid, filename in LOCATION_SOURCES.items()]
    selections += [("npc", sid, filename) for sid, filename in NPC_SOURCES.items()]

    temp_parent = output_root.parent
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="visual-import-", dir=temp_parent) as tmp:
        temp_output = Path(tmp) / "v1"
        # Por padrão preserva derivados de uma futura família ainda fora deste
        # catálogo. Remoção de sobras só acontece com --prune explícito.
        if output_root.exists() and not prune:
            shutil.copytree(output_root, temp_output)
        assets = [
            _build_asset(_find_row(rows, filename), kind, subject_id, source_root, temp_output)
            for kind, subject_id, filename in selections
        ]
        # URLs foram montadas contra web/public; corrigimos a raiz temporária.
        for asset in assets:
            for variant in asset["variants"].values():
                name = Path(variant["url"]).name
                variant["url"] = f"/art/v1/{asset['subject_type']}/{name}"
        by_subject = {(a["subject_type"], a["subject_id"]): a["asset_id"] for a in assets}
        catalog = {
            "schema_version": 1,
            "assets": sorted(assets, key=lambda a: (a["subject_type"], a["subject_id"])),
            "creation": {
                "races": {sid: by_subject[("race", sid)] for sid in RACE_SOURCES},
                "classes": {sid: by_subject[("class", sid)] for sid in CLASS_SOURCES},
            },
            "location_fallbacks": LOCATION_FALLBACKS,
            "unmapped_source_assets": [
                {"asset_id": "VAL-P2-NPC-VRETHIS-001", "reason": "NPC ausente do grafo canônico"},
            ],
        }
        rendered = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        if check:
            if not catalog_path.is_file() or catalog_path.read_text(encoding="utf-8") != rendered:
                raise ValueError("catálogo/derivados diferem do import determinístico")
            for asset in assets:
                for variant in asset["variants"].values():
                    final = ROOT / "web" / "public" / variant["url"].removeprefix("/")
                    generated = temp_output / asset["subject_type"] / Path(variant["url"]).name
                    if not final.is_file() or sha256_file(final) != sha256_file(generated):
                        raise ValueError(f"derivado divergente: {final}")
            return catalog
        backup_output = Path(tmp) / "previous-v1"
        if output_root.exists():
            os.replace(output_root, backup_output)
        try:
            os.replace(temp_output, output_root)
            catalog_tmp = Path(tmp) / "visual_assets.json"
            catalog_tmp.write_text(rendered, encoding="utf-8")
            os.replace(catalog_tmp, catalog_path)
        except Exception:
            if output_root.exists():
                shutil.rmtree(output_root)
            if backup_output.exists():
                os.replace(backup_output, output_root)
            raise
        return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()
    catalog = import_assets(args.source_root, check=args.check, prune=args.prune)
    print(json.dumps({"ok": True, "assets": len(catalog["assets"]), "check": args.check}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
