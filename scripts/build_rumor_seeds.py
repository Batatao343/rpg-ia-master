"""SPEC-312 R1-R5: gera `data/world/rumor_seeds.json` (sementes de rumor) da lore.

Familias: `lore` (um bloco `[CATEGORIA: RUMOR]` de `lore_nova/rumors.txt`) e `avistamento`
(uma por criatura Minion/Standard/Elite de `data/bestiary.json`). Curadoria manual mora em
`data/world/rumor_seed_overrides.json` e vence o gerado (R4). Deterministico, LF.

Uso: `bash scripts/dev/py.sh scripts/build_rumor_seeds.py [--check]`.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LORE = ROOT / "lore_nova" / "rumors.txt"
BESTIARY = ROOT / "data" / "bestiary.json"
WORLD_MAP = ROOT / "data" / "world_map.json"
OVERRIDES = ROOT / "data" / "world" / "rumor_seed_overrides.json"
OUT = ROOT / "data" / "world" / "rumor_seeds.json"
EXPECTED_LORE = 40
AVISTAMENTO_TYPES = ("Minion", "Standard", "Elite")
OVERRIDE_FIELDS = (
    "truth",
    "gist",
    "fonte_label",
    "public_names",
    "labels",
    "regions",
    "location_id",
    "quest_eligible",
    "disabled",
    "review",
    "subject",
    "creature_label",
)
# Tags da lore sem nome igual ao do mapa -> local (R2).
TAG_ALIASES = {
    "palacio de obsidiana": "na_anel_dourado",
    "dragao bebado": "na_anel_dourado",
    "guilda dos corvos": "nova_arcadia",
    "valerius": "nova_arcadia",
    "arauto da nevoa": "nova_arcadia",
    "cemiterio de leviatas": "costa_negra",
    "ruinas de aethelgard": "ae_ruinas_submersas",
    "thessrak": "ae_ruinas_submersas",
    "fortaleza congelada de vorr": "sk_fortaleza_vorr",
    "o trono": "cn_o_trono",
    "imperio de ophidia": "ophidia",
    "morrakh": "sx_profundezas",
    "borda sul": "dz_borda_do_vazio",
    "rei subterraneo": "ma_boca",
    "hospedeiros": "sx_cidades_hospedeiros",
}
ENTITY_ALIASES = {"valerius": "npc_valerius"}
SUBJECT_BY_TYPE = {"npc": "pessoa", "faction": "faccao", "location": "lugar"}


def fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", str(text or "").lower())
        if not unicodedata.combining(ch)
    ).strip()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", fold(text)).strip("_")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entities() -> dict[str, dict]:
    base = _json(ROOT / "data" / "graph" / "entities.json")
    extra = _json(ROOT / "data" / "graph" / "entities_extra.json")
    return {**extra, **base}


def _strip_article(name: str) -> str:
    return re.sub(r"^(o|a|os|as)\s+", "", fold(name))


def parse_lore() -> list[dict]:
    """Blocos `[CATEGORIA: RUMOR]` com linha (1-based), titulo, fonte, confiabilidade, corpo."""
    lines = LORE.read_text(encoding="utf-8").split("\n")
    out: list[dict] = []
    for i, line in enumerate(lines):
        if not line.startswith("[CATEGORIA: RUMOR]"):
            continue
        tags_raw = lines[i + 1].strip()
        fonte_raw = lines[i + 2].strip()
        j = i + 3
        while j < len(lines) and not lines[j].strip():
            j += 1
        body: list[str] = []
        k = j + 1
        while k < len(lines) and lines[k].strip() != "---":
            body.append(lines[k])
            k += 1
        tags = [t.strip() for t in tags_raw[len("[TAGS:") : -1].split(",")]
        conf = "media"
        plain: list[str] = []
        for t in tags:
            if fold(t).startswith("confiabilidade"):
                conf = fold(t.split(":", 1)[1])
            else:
                plain.append(t)
        out.append(
            {
                "line": i + 1,
                "title": lines[j].strip(),
                "tags": plain,
                "fonte": fonte_raw[len("[FONTE:") : -1].strip(),
                "confiabilidade": conf,
                "body": " ".join(b.strip() for b in body),
            }
        )
    return out


def _location_index() -> tuple[dict[str, str], dict[str, str], dict[str, dict]]:
    locs = _json(WORLD_MAP)["locations"]
    by_id = {loc["id"]: loc for loc in locs}
    by_name = {fold(loc["name"]): loc["id"] for loc in locs}
    by_region = {}
    for loc in locs:
        if loc.get("region") and loc.get("region_id"):
            by_region.setdefault(fold(loc["region"]), loc["region_id"])
    return by_name, by_region, by_id


def resolve_tags(tags: list[str]) -> tuple[list[str], str, list[str]]:
    """(regioes, location_id, tags nao mapeadas) - R2."""
    by_name, by_region, by_id = _location_index()
    regions: list[str] = []
    loc_ids: list[str] = []
    unmapped: list[str] = []
    for tag in tags:
        key = fold(tag)
        lid = TAG_ALIASES.get(key) or by_name.get(key)
        rid = by_region.get(key)
        if lid:
            loc_ids.append(lid)
            reg = by_id[lid].get("region_id")
            if reg and reg not in regions:
                regions.append(reg)
        elif rid:
            if rid not in regions:
                regions.append(rid)
            if rid in by_id:
                loc_ids.append(rid)
        else:
            unmapped.append(tag)
    # local mais especifico: o ultimo mapeado; sem nenhum, o primeiro nao-interior da regiao
    location = loc_ids[-1] if loc_ids else (regions[0] if regions else "")
    if location and by_id.get(location, {}).get("parent_id"):
        location = by_id[location]["parent_id"]
    return regions, location, unmapped


def find_entities(tags: list[str], body: str, location_id: str) -> list[str]:
    ents = _entities()
    names: dict[str, str] = {}
    for eid, ent in ents.items():
        if ent.get("type") in ("npc", "faction") and ent.get("visibility", "public") == "public":
            names[eid] = _strip_article(ent.get("name", ""))
    found: dict[str, int] = {}
    hay = fold(body) + " " + " ".join(fold(t) for t in tags)
    for tag in tags:
        eid = ENTITY_ALIASES.get(fold(tag))
        if eid and eid in ents:
            found[eid] = 99
    for eid, nm in names.items():
        if len(nm) >= 4 and re.search(r"\b" + re.escape(nm) + r"\b", hay):
            found[eid] = found.get(eid, 0) + hay.count(nm)
    ranked = sorted(found, key=lambda e: (-found[e], e))[:4]
    if location_id and location_id in ents and location_id not in ranked:
        ranked.append(location_id)
    return ranked


def _subject(entities: list[str]) -> str:
    ents = _entities()
    for eid in entities:
        sub = SUBJECT_BY_TYPE.get((ents.get(eid) or {}).get("type", ""))
        if sub in ("pessoa", "faccao"):
            return sub
    return "lugar"


def lore_seeds() -> dict[str, dict]:
    seeds: dict[str, dict] = {}
    for blk in parse_lore():
        sid = "rumor_" + slug(blk["title"])
        regions, location, unmapped = resolve_tags(blk["tags"])
        entities = find_entities(blk["tags"], blk["body"], location)
        conf = blk["confiabilidade"]
        label = blk["fonte"].split(",")[0].strip()
        seed = {
            "family": "lore",
            "source": f"lore_nova/rumors.txt:{blk['line']}",
            "title": blk["title"],
            "fonte": blk["fonte"],
            "fonte_label": label[:60],
            "gist": fold(blk["title"]) and blk["title"][:1].lower() + blk["title"][1:],
            "regions": regions,
            "location_id": location,
            "subject": _subject(entities),
            "entities": entities,
            "public_names": [],
            "labels": {},
            "confiabilidade": conf,
            "truth": conf in ("alta", "media"),
            "quest_eligible": True,
            "review": "dono",
        }
        if unmapped:
            seed["tags_unmapped"] = unmapped
        if not regions:
            seed["disabled"] = True
        seeds[sid] = seed
    return seeds


def avistamento_seeds() -> dict[str, dict]:
    lines = BESTIARY.read_text(encoding="utf-8").split("\n")
    line_of = {}
    for n, ln in enumerate(lines, 1):
        m = re.match(r'^  "([a-z0-9_]+)": \{', ln)
        if m:
            line_of[m.group(1)] = n
    out: dict[str, dict] = {}
    for eid, mon in _json(BESTIARY).items():
        if mon.get("type") not in AVISTAMENTO_TYPES or not mon.get("regions"):
            continue
        name = re.sub(r"\s*\(.*?\)", "", str(mon.get("name") or eid)).strip()
        out["rumor_avist_" + eid] = {
            "family": "avistamento",
            "source": f"data/bestiary.json:{line_of.get(eid, 0)}",
            "regions": list(mon["regions"]),
            "subject": "criatura",
            "entities": [eid],
            "creature_label": name[:1].lower() + name[1:],
            "confiabilidade": "media",
            "truth_mode": "regional",
            "quest_eligible": True,
            "review": "dono",
        }
    return out


def load_overrides() -> dict[str, dict]:
    if not OVERRIDES.exists():
        return {}
    return dict(_json(OVERRIDES).get("overrides") or {})


def build() -> tuple[dict, list[str]]:
    seeds = {**lore_seeds(), **avistamento_seeds()}
    lore_count = sum(1 for s in seeds.values() if s["family"] == "lore")
    if lore_count != EXPECTED_LORE:
        raise SystemExit(f"esperava {EXPECTED_LORE} rumores da lore, achei {lore_count}")
    for sid, ov in load_overrides().items():
        if sid in seeds:
            seeds[sid].update({k: v for k, v in ov.items() if k in OVERRIDE_FIELDS})
            if "regions" in ov and seeds[sid].get("disabled") and "disabled" not in ov:
                seeds[sid].pop("disabled", None)
    unmapped = sorted(
        f"{sid}: {', '.join(s['tags_unmapped'])}"
        for sid, s in seeds.items()
        if "tags_unmapped" in s
    )
    doc = {
        "_doc": (
            "GERADO por scripts/build_rumor_seeds.py a partir de lore_nova/rumors.txt e "
            "data/bestiary.json + rumor_seed_overrides.json. Nao editar a mao."
        ),
        "seeds": seeds,
    }
    return doc, unmapped


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    doc, unmapped = build()
    text = render(doc)
    if "--check" in argv:
        current = OUT.read_bytes().decode("utf-8") if OUT.exists() else ""
        if current != text:
            print("rumor_seeds.json diverge do gerado; rode o script sem --check.")
            return 1
        return 0
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"{len(doc['seeds'])} sementes; tags nao mapeadas: {len(unmapped)}")
    for row in unmapped:
        print("  ", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
