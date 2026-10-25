"""SPEC-306 - expansão das tabelas de semente de NPC (+25 por tabela). Offline, só dados."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import unicodedata
from functools import lru_cache
from itertools import combinations

import pytest

from gamedata import DATA_DIR
from services import npc_seed as ns
from services.codex_loader import CODEX_DIR, parse_codex_file
from services.content_validator import validate_npc_seed_tables

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ORIGINAL_SIZES = {
    "professions": 36,
    "desires": 20,
    "fears": 20,
    "secrets": 19,
    "contradictions": 17,
    "mannerisms": 20,
}
EXPECTED_SIZES = {key: size + 25 for key, size in ORIGINAL_SIZES.items()}
# sha256 das linhas originais (json.dumps sort_keys, ensure_ascii=False), congelado da main 02bcf0e1
ORIGINAL_HASHES = {
    "professions": "85aa507c0de36c24ed3ab784347c77e668d551cf4386774e4d7dbc6008383c74",
    "desires": "e2ec4882ac4f0811865930f59d85c2b593dc344552de777c805ad2f0b99b6f13",
    "fears": "3d17f8307f7bc5de0be70e2bc0e1a1fbf802eb02c8dc647db8e95c4020ee7ea8",
    "secrets": "7a7cceef5b455af4e98a8cffdc3c89cbbc83cc411c6ebc99bf8b56dc2ba3aee9",
    "contradictions": "dc0d92f8593651799cf122345dfb70ecbb48b80d64e52cbae738eb0f49ee370d",
    "mannerisms": "e26cdeed2228597041d8a1f63cd1290b6dc16af186144c61b8d1e4438af2ea0f",
}
PREFIX = {
    "professions": "prof_",
    "desires": "des_",
    "fears": "fear_",
    "secrets": "sec_",
    "contradictions": "con_",
    "mannerisms": "man_",
}
# mínimos de R6 entre as 25 novas: (universais, restritas, raça, facção)
MIX_FLOOR = (6, 10, 2, 1)
REGIONS = [
    "nova_arcadia",
    "pantano_melancolia",
    "deserto_zhur",
    "floresta_sussurros",
    "selva_xylos",
    "skallgard",
    "aethelgard",
    "ophidia",
    "costa_negra",
    "montanhas_afiadas",
    "pradaria_ruinas",
    "brekmar",
]
REGION_FLOOR = {"professions": 3, "desires": 2, "fears": 2, "secrets": 2, "con+man": 2}
STOPWORDS = {
    "de", "do", "da", "dos", "das", "o", "a", "os", "as", "um", "uma", "que", "e", "em",
    "no", "na", "nos", "nas", "por", "para", "com", "se", "seu", "sua", "ao", "à",
}  # fmt: skip
# Pares com rótulos parecidos de propósito (id_a, id_b) -> motivo. No máximo 5.
_SIMILAR_OK: dict[tuple[str, str], str] = {}


def _read(name: str) -> dict:
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _tables() -> dict:
    return _read("npc_seed_tables.json")


def _new_rows(table: str) -> list[dict]:
    return _tables()[table][ORIGINAL_SIZES[table] :]


def _all_rows():
    for table in ns.TABLE_KEYS:
        for row in _tables()[table]:
            yield table, row


def _norm(text: str) -> str:
    base = unicodedata.normalize("NFD", text.casefold())
    base = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", base)).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if t not in STOPWORDS}


def _category(row: dict) -> str:
    if row.get("factions"):
        return "facao"
    if row.get("races"):
        return "raca"
    if row.get("regions"):
        return "regional"
    return "universal"


def test_table_sizes_after_expansion():
    sizes = {key: len(_tables()[key]) for key in ns.TABLE_KEYS}
    assert sizes == EXPECTED_SIZES


@pytest.mark.parametrize("table", ns.TABLE_KEYS)
def test_original_rows_untouched(table):
    rows = _tables()[table][: ORIGINAL_SIZES[table]]
    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False)
    assert hashlib.sha256(blob.encode("utf-8")).hexdigest() == ORIGINAL_HASHES[table]


@lru_cache(maxsize=1)
def _line_counts() -> dict[str, int]:
    return {}


def _file_lines(rel: str) -> int:
    counts = _line_counts()
    if rel not in counts:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as handle:
            counts[rel] = sum(1 for _ in handle)
    return counts[rel]


@pytest.mark.parametrize("table", ns.TABLE_KEYS)
def test_new_rows_schema(table):
    seen: set[str] = set()
    for row in _new_rows(table):
        rid = row["id"]
        assert re.fullmatch(r"[a-z0-9_]+", rid), rid
        assert rid.startswith(PREFIX[table]), rid
        assert rid not in seen, rid
        seen.add(rid)
        label = row["label"]
        assert 8 <= len(label) <= 80, f"{rid}: tamanho {len(label)}"
        assert label[0].islower() and not label.endswith("."), rid
        for field in ("regions", "races", "factions"):
            if field in row:
                assert row[field], f"{rid}: {field} vazio"
        match = re.fullmatch(r"((?:lore_nova|data)/[\w.]+):(\d+)", row.get("source", ""))
        assert match, f"{rid}: source inválido"
        assert 1 <= int(match.group(2)) <= _file_lines(match.group(1)), rid
        # Pendente = review:"dono"; depois de `npc_seed_review.py approve` a marca sai (dono, 24/10).
        assert row.get("review") in ("dono", None), rid


@pytest.mark.parametrize("table", ns.TABLE_KEYS)
def test_new_rows_mix(table):
    rows = _new_rows(table)
    cats = [_category(r) for r in rows]
    universal, restricted = cats.count("universal"), len(cats) - cats.count("universal")
    assert universal >= MIX_FLOOR[0], f"{table}: universais {universal}"
    assert restricted >= MIX_FLOOR[1], f"{table}: restritas {restricted}"
    assert cats.count("raca") >= MIX_FLOOR[2], f"{table}: raça {cats.count('raca')}"
    assert cats.count("facao") >= MIX_FLOOR[3], f"{table}: facção {cats.count('facao')}"


def test_race_coverage_new_rows():
    counts = {race: 0 for race in ns.lore_ids()["races"]}
    for table in ns.TABLE_KEYS:
        for row in _new_rows(table):
            for race in row.get("races") or []:
                counts[race] += 1
    short = {race: n for race, n in counts.items() if n < 2}
    assert not short, f"raças com < 2 linhas novas: {short}"


def _region_count(tables: dict, region: str, table: str) -> int:
    return sum(
        1
        for row in tables[table]
        if region in (row.get("regions") or []) and not row.get("factions")
    )


@pytest.mark.parametrize("region", REGIONS)
@pytest.mark.parametrize("table", list(REGION_FLOOR))
def test_regional_floor(region, table):
    tables = _tables()
    if table == "con+man":
        got = _region_count(tables, region, "contradictions") + _region_count(
            tables, region, "mannerisms"
        )
    else:
        got = _region_count(tables, region, table)
    need = REGION_FLOOR[table]
    assert got >= need, f"{region}/{table}: {got} linhas, faltam {need - got}"


def test_region_ids_match_lore():
    assert sorted(REGIONS) == sorted(ns.lore_ids()["regions"])


def _reachable(row: dict) -> bool:
    lore = ns.lore_ids()
    for region in sorted(lore["regions"]):
        for race in sorted(lore["races"]):
            for faction in [None, *ns.compatible_factions(region)]:
                if (
                    ns._allowed(row, "regions", region)
                    and ns._allowed(row, "races", race)
                    and ns._allowed(row, "factions", faction)
                ):
                    return True
    return False


def test_every_row_reachable():
    dead = [row["id"] for _, row in _all_rows() if not _reachable(row)]
    assert not dead, f"linhas inalcançáveis: {dead}"


def test_no_semantic_duplicates():
    assert len(_SIMILAR_OK) <= 5
    assert all(reason.strip() for reason in _SIMILAR_OK.values())
    problems: list[str] = []
    for table in ns.TABLE_KEYS:
        rows = _tables()[table]
        for a, b in combinations(rows, 2):
            if (a["id"], b["id"]) in _SIMILAR_OK or (b["id"], a["id"]) in _SIMILAR_OK:
                continue
            if _norm(a["label"]) == _norm(b["label"]):
                problems.append(f"{a['id']} == {b['id']} (rótulo igual)")
                continue
            ta, tb = _tokens(a["label"]), _tokens(b["label"])
            if not ta or not tb:
                continue
            jaccard = len(ta & tb) / len(ta | tb)
            contained = min(len(ta), len(tb)) >= 3 and (ta <= tb or tb <= ta)
            if jaccard >= 0.6 or contained:
                problems.append(f"{a['id']} ~ {b['id']} (jaccard {jaccard:.2f})")
    assert not problems, problems


@lru_cache(maxsize=1)
def _place_index() -> dict:
    origins = _read("origins.json")
    factions = _read("factions.json")
    world = _read("world_map.json")
    region_by_name = {r["name"]: r["id"] for r in origins["regions"]}
    places: dict[str, str] = {}  # nome normalizado -> region_id
    for region in origins["regions"]:
        places[_norm(region["name"])] = region["id"]
    for loc in world["locations"]:
        name = re.sub(r"^(a|o|as|os)\s+", "", _norm(loc.get("name", "")))
        if loc.get("region_id") and (len(name.split()) >= 2 or len(name) >= 6):
            places.setdefault(name, loc["region_id"])
    fac: dict[str, tuple[str, str]] = {}  # nome norm -> (faction_id, region_id)
    for fid, data in factions.items():
        name = re.sub(r"^(a|o|as|os)\s+", "", _norm(data.get("name", "")))
        fac[name] = (fid, region_by_name.get(data.get("region", ""), ""))
    return {"places": places, "factions": fac}


def _has_phrase(text: str, phrase: str) -> bool:
    return bool(phrase) and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def test_place_names_require_filters():
    index = _place_index()
    problems: list[str] = []
    for _, row in _all_rows():
        text = _norm(row["label"])
        for place, region in index["places"].items():
            if _has_phrase(text, place) and region not in (row.get("regions") or []):
                problems.append(f"{row['id']}: cita '{place}' sem regions ∋ {region}")
        for name, (fid, region) in index["factions"].items():
            if _has_phrase(text, name) and not (
                fid in (row.get("factions") or []) or region in (row.get("regions") or [])
            ):
                problems.append(f"{row['id']}: cita facção '{name}' sem filtro coerente")
    assert not problems, problems


@lru_cache(maxsize=1)
def _public_words() -> set[str]:
    words: set[str] = set()
    for dirpath, _, files in os.walk(os.path.join(ROOT, CODEX_DIR)):
        for name in files:
            if not name.endswith(".md"):
                continue
            meta, body = parse_codex_file(os.path.join(dirpath, name))
            if str(meta.get("visibility", "public")).lower() == "public":
                words.update(re.findall(r"\w+", body))
    for fname, key in (
        ("origins.json", "regions"),
        ("origins.json", "races"),
        ("factions.json", ""),
    ):
        data = _read(fname)
        items = data[key] if key else list(data.values())
        for item in items:
            words.update(re.findall(r"\w+", item.get("name", "")))
    return words


def test_proper_nouns_from_public_codex():
    public = _public_words()
    problems: list[str] = []
    for _, row in _all_rows():
        for position, raw in enumerate(row["label"].split()):
            word = re.sub(r"^\W+|\W+$", "", raw)
            if position == 0 or not word or not word[0].isupper():
                continue
            for part in re.findall(r"\w+", word):
                if part not in public:
                    problems.append(f"{row['id']}: '{part}' fora do Codex público")
    assert not problems, problems


def test_validator_green():
    assert validate_npc_seed_tables() == []


def test_validator_flags_unreachable_and_dup_label(tmp_path):
    tables = copy.deepcopy(_tables())
    tables["fears"].append(
        {
            "id": "fear_teste_morto",
            "label": "linha que nunca pode ser sorteada",
            "regions": ["brekmar"],
            "factions": ["legiao_ferro"],
        }
    )
    tables["desires"].append({"id": "des_teste_a", "label": "Querer o mesmo que outro"})
    tables["desires"].append({"id": "des_teste_b", "label": "querer  o MESMO que outro"})
    tables["secrets"].append({"id": "x_sem_prefixo", "label": "rótulo com id de prefixo errado"})
    path = tmp_path / "tables.json"
    path.write_text(json.dumps(tables, ensure_ascii=False), encoding="utf-8", newline="\n")
    messages = {(f.entity_id, f.message) for f in validate_npc_seed_tables(str(path))}
    text = " | ".join(f"{eid}: {msg}" for eid, msg in messages)
    assert "fear_teste_morto" in text and "inalcançável" in text
    assert "des_teste_b" in text and "rótulo duplicado" in text
    assert "x_sem_prefixo" in text and "prefixo" in text
