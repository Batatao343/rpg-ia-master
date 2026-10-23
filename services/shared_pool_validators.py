"""shared_pool_validators.py — validadores determinísticos do pool (SPEC-297 R14).

Puro: zero LLM/rede. Cada validador devolve `list[Finding(code, field)]`; QUALQUER
Finding reprova a entrada (fail-closed). Roda ANTES de qualquer avaliação LLM
(R18) e nunca ecoa o conteúdo reprovado nos achados (só código e campo).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache

from gamedata import DATA_DIR
from services.shared_pool_models import (
    DOCUMENT_ALLOWLIST,
    TEXT_LIMITS,
    PoolNamespace,
    SharedPoolEntry,
    fold_name,
)

SHINGLE_SIZE = 6
CORPUS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests",
    "fixtures",
    "prompt_injection",
    "corpus.json",
)
_TOKEN = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class Finding:
    code: str
    field: str = ""


# --------------------------------------------------------------------------- #
# Shingles (R9/R14 literal_player_text)
# --------------------------------------------------------------------------- #
def shingles(text: object, size: int = SHINGLE_SIZE) -> list[str]:
    """Hashes `sha256[:16]` dos n-gramas normalizados de tokens. Nunca o texto."""
    tokens = _TOKEN.findall(fold_name(text))
    if len(tokens) < size:
        return []
    out = []
    for i in range(len(tokens) - size + 1):
        gram = " ".join(tokens[i : i + size])
        out.append(hashlib.sha256(gram.encode("utf-8")).hexdigest()[:16])
    return out


def input_shingles(player_inputs: Iterable[str], *, cap: int = 200) -> list[str]:
    seen: dict[str, None] = {}
    for text in list(player_inputs)[-3:]:
        for item in shingles(text):
            seen.setdefault(item, None)
    return list(seen)[:cap]


# --------------------------------------------------------------------------- #
# Texto da entrada
# --------------------------------------------------------------------------- #
_ID_FIELDS = frozenset(
    {
        "id",
        "pool_entry_id",
        "race_id",
        "origin_region_id",
        "faction_id",
        "profession_id",
        "parent_location_id",
        "region",
    }
)
_ID_RE = re.compile(r"^[a-z0-9_]{1,80}$")


def _text_fields(entry: SharedPoolEntry) -> dict[str, str]:
    fields: dict[str, str] = {"name": entry.name, "legend": entry.legend}
    for key, value in entry.document.items():
        if key in _ID_FIELDS:
            continue  # identificadores são checados em validate_schema
        if isinstance(value, str):
            fields[key] = value
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            fields[key] = " ".join(value)
    return {k: v for k, v in fields.items() if v}


# --------------------------------------------------------------------------- #
# schema
# --------------------------------------------------------------------------- #
def validate_schema(entry: SharedPoolEntry) -> list[Finding]:
    findings: list[Finding] = []
    allowed = DOCUMENT_ALLOWLIST[entry.namespace]
    for key in entry.document:
        if key not in allowed:
            findings.append(Finding("schema_extra_field", str(key)[:40]))
    if entry.namespace == PoolNamespace.CREATURE and entry.document.get("categoria") not in {
        "lacaio",
        "padrao",
        "elite",
    }:
        findings.append(Finding("creature_category", "categoria"))
    for key in _ID_FIELDS:
        value = entry.document.get(key)
        if value is not None and not (isinstance(value, str) and _ID_RE.match(value)):
            findings.append(Finding("schema_bad_id", key))
    for key, limit in TEXT_LIMITS.items():
        value = entry.document.get(key)
        if key == "name":
            value = entry.name
        if key == "legend":
            value = entry.legend
        if isinstance(value, str) and len(value) > limit:
            findings.append(Finding("schema_too_long", key))
    return findings


# --------------------------------------------------------------------------- #
# lore_refs
# --------------------------------------------------------------------------- #
def validate_lore_refs(entry: SharedPoolEntry) -> list[Finding]:
    from services.npc_seed import lore_ids

    ids = lore_ids()
    findings: list[Finding] = []
    # item sem região (produtor futuro) é aceito; NPC/criatura/local exigem região real.
    region_optional = entry.namespace == PoolNamespace.ARTIFACT and not entry.region_id
    if entry.region_id not in ids["regions"] and not region_optional:
        findings.append(Finding("lore_unknown_region", "region_id"))
    parent = entry.document.get("parent_location_id")
    if parent and parent not in ids["locations"]:
        findings.append(Finding("lore_unknown_location", "parent_location_id"))
    seed = entry.seed
    if seed is not None:
        if seed.race_id not in ids["races"]:
            findings.append(Finding("lore_unknown_race", "seed.race_id"))
        if seed.origin_region_id not in ids["regions"]:
            findings.append(Finding("lore_unknown_region", "seed.origin_region_id"))
        if seed.faction_id is not None and seed.faction_id not in ids["factions"]:
            findings.append(Finding("lore_unknown_faction", "seed.faction_id"))
        if seed.home_location_id not in ids["locations"]:
            findings.append(Finding("lore_unknown_location", "seed.home_location_id"))
        findings.extend(_seed_table_refs(seed))
    return findings


def _seed_table_refs(seed) -> list[Finding]:
    from services.npc_seed import load_seed_tables

    tables = load_seed_tables()
    pairs = (
        ("professions", seed.profession_id),
        ("desires", seed.desire_id),
        ("fears", seed.fear_id),
        ("secrets", seed.secret_id),
        ("contradictions", seed.contradiction_id),
        ("mannerisms", seed.mannerism_id),
    )
    findings = []
    for table, ident in pairs:
        if ident not in {row["id"] for row in tables.get(table, [])}:
            findings.append(Finding("lore_unknown_seed_id", f"seed.{table}"))
    return findings


# --------------------------------------------------------------------------- #
# pii
# --------------------------------------------------------------------------- #
def validate_pii(entry: SharedPoolEntry, *, owner_values: Sequence[str] = ()) -> list[Finding]:
    from services.audit_redaction import scan_pii

    findings = []
    for field, text in _text_fields(entry).items():
        if scan_pii(text, owner_values=tuple(owner_values)):
            findings.append(Finding("pii", field))
    return findings


# --------------------------------------------------------------------------- #
# injection
# --------------------------------------------------------------------------- #
_MARKUP = re.compile(r"[<>{}]|https?://|www\.|\bdata:", re.IGNORECASE)
_INSTRUCTION = re.compile(
    r"""
      \b(?:ignor\w*|esquec\w*|desconsider\w*)\b.{0,40}\b(?:regra|instruc|prompt|anterior|sistema)
    | \b(?:revele|registre|conceda|conclua|marque|defina|adicione|suba|junte-se|odeie|ordeno)\b
    | \bdiga\s+em\b
    | \b(?:system|sistema|instrucao|prompt|narrador|assistant|jogador)\s*[:\]]
    | \[\s*instrucao
    | \b[a-z]+(?:_[a-z0-9]+)+\b
    | [=:]\s*["']?[-+]?\d
    | \bbase64\b
    | \blembre\s+para\s+sempre\b
    | \bvoce\s+me\s+ama\b
    | \bouro\s+do\s+jogador\b
    | \bminh[ao]s?\b.{0,30}\b(?:reputacao|missoes|missao|nivel)\b
    | \bao\s+maximo\b
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


@lru_cache(maxsize=1)
def _corpus_texts() -> tuple[str, ...]:
    """Textos hostis do corpus SPEC-223 (best-effort; os marcadores acima cobrem sem ele)."""
    path = CORPUS_PATH
    if not os.path.exists(path):
        return ()
    try:
        with open(path, encoding="utf-8") as handle:
            cases = json.load(handle).get("cases", [])
    except (OSError, ValueError):
        return ()
    texts = []
    for case in cases:
        for key in ("player_input", "name", "backstory"):
            value = case.get(key)
            if isinstance(value, str) and len(fold_name(value)) >= 12:
                texts.append(fold_name(value))
    return tuple(texts)


def validate_injection(entry: SharedPoolEntry) -> list[Finding]:
    findings = []
    for field, text in _text_fields(entry).items():
        folded = fold_name(text)
        if (
            _MARKUP.search(text)
            or _INSTRUCTION.search(folded)
            or any(sample in folded for sample in _corpus_texts())
        ):
            findings.append(Finding("injection", field))
    return findings


# --------------------------------------------------------------------------- #
# literal_player_text
# --------------------------------------------------------------------------- #
def validate_literal_player_text(entry: SharedPoolEntry) -> list[Finding]:
    if not entry.input_shingles:
        return []
    blocked = set(entry.input_shingles)
    findings = []
    for field, text in _text_fields(entry).items():
        if any(item in blocked for item in shingles(text)):
            findings.append(Finding("literal_player_text", field))
    return findings


# --------------------------------------------------------------------------- #
# secrets
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _secret_names() -> frozenset[str]:
    names: set[str] = set()
    try:
        with open(os.path.join(DATA_DIR, "secret_entities.json"), encoding="utf-8") as handle:
            groups = json.load(handle)
        with open(os.path.join(DATA_DIR, "graph", "entities.json"), encoding="utf-8") as handle:
            entities = json.load(handle)
    except (OSError, ValueError):
        return frozenset()
    for key, ids in groups.items():
        if key.startswith("_") or not isinstance(ids, list):
            continue
        for ident in ids:
            name = (entities.get(ident) or {}).get("name")
            if name:
                names.add(fold_name(name))
    return frozenset(n for n in names if n)


def validate_secrets(entry: SharedPoolEntry) -> list[Finding]:
    from services.content_validator import NPC_SECRET_LABELS

    label_pattern = re.compile(
        r"(?:^|[.\n;])\s*(?:" + "|".join(re.escape(x) for x in sorted(NPC_SECRET_LABELS)) + r")\s*:"
    )
    findings = []
    for field, text in _text_fields(entry).items():
        folded = fold_name(text)
        if label_pattern.search(folded) or any(
            re.search(rf"\b{re.escape(name)}\b", folded) for name in _secret_names()
        ):
            findings.append(Finding("secrets", field))
    return findings


# --------------------------------------------------------------------------- #
# uniqueness_exact
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def curated_names() -> frozenset[str]:
    """Nomes dobrados de entidades curadas: grafo, bestiário e artefatos."""
    names: set[str] = set()

    def read(*parts: str) -> dict:
        try:
            with open(os.path.join(DATA_DIR, *parts), encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    for fname in ("entities.json", "entities_extra.json"):
        for ent in read("graph", fname).values():
            if isinstance(ent, dict):
                names.add(fold_name(ent.get("name", "")))
    for fname in ("bestiary.json", "artifacts.json"):
        for ent in read(fname).values():
            if isinstance(ent, dict):
                names.add(fold_name(ent.get("name", "")))
    names.discard("")
    return frozenset(names)


def validate_uniqueness_exact(
    entry: SharedPoolEntry, promoted: Iterable[SharedPoolEntry] = ()
) -> list[Finding]:
    findings = []
    if entry.name_fold in curated_names():
        findings.append(Finding("duplicate_curated", "name"))
    for other in promoted:
        if other.entry_id == entry.entry_id or other.namespace != entry.namespace:
            continue
        if other.name_fold == entry.name_fold:
            findings.append(Finding("duplicate_name", "name"))
            break
    for other in promoted:
        if (
            entry.seed_signature
            and other.entry_id != entry.entry_id
            and other.namespace == entry.namespace
            and other.seed_signature == entry.seed_signature
        ):
            findings.append(Finding("duplicate_signature", "seed"))
            break
    return findings


# --------------------------------------------------------------------------- #
# Agregado
# --------------------------------------------------------------------------- #
def run_validators(
    entry: SharedPoolEntry,
    *,
    promoted: Iterable[SharedPoolEntry] = (),
    owner_values: Sequence[str] = (),
) -> list[Finding]:
    promoted = list(promoted)
    findings: list[Finding] = []
    findings += validate_schema(entry)
    findings += validate_lore_refs(entry)
    findings += validate_pii(entry, owner_values=owner_values)
    findings += validate_injection(entry)
    findings += validate_literal_player_text(entry)
    findings += validate_secrets(entry)
    findings += validate_uniqueness_exact(entry, promoted)
    if entry.namespace == PoolNamespace.NPC and entry.seed is None:
        findings.append(Finding("schema_missing_seed", "seed"))
    return findings
