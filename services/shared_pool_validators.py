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


# SPEC-361 R23: campos de criatura que são enum/id (checados em `_validate_creature_enums`),
# não texto livre; sem isso `corpo_a_corpo`/`deserto_zhur` contavam como "injeção" (snake_case).
_CREATURE_ENUM_FIELDS = frozenset({"categoria", "arquetipo", "estilo_ataque", "region_tags"})
# SPEC-361 R23 (P1-1): allowlist de CAMINHOS da ficha (exatamente a forma de
# `creature_gen.ficha_runtime`). Fail-closed: caminho desconhecido, tipo errado, lista de não-str
# ou profundidade além do esperado viram Finding. Só os caminhos "text" vão para a varredura de
# PII/injeção/segredo; os "ident" são validados por forma (`_ID_RE`).
#   tipo: "text" | "ident" (str id ou None) | "idents" (lista de ids) | "int" | "dict"
FICHA_PATHS: dict[str, str] = {
    "id": "ident",
    "nome": "text",
    "status": "ident",
    "familia": "ident",
    "origem_lore": "dict",
    "origem_lore.fonte": "ident",
    "origem_lore.detalhe": "ident",
    "origem_lore.refs": "idents",
    "anatomia": "dict",
    "anatomia.plano_corporal": "ident",
    "anatomia.material": "ident",
    "anatomia.escala": "ident",
    "anatomia.locomocao": "ident",
    "anatomia.percepcao": "ident",
    "anatomia.texto": "text",
    "silhueta": "text",
    "comportamento": "text",
    "papel_tatico": "ident",
    "arquetipo": "ident",
    "categoria": "ident",
    "faccao": "ident",
    "estilo_ataque": "ident",
    "nome_ataque": "text",
    "mecanica_assinatura": "dict",
    "mecanica_assinatura.frase": "text",
    "contra_jogo": "text",
    "gancho": "text",
    "habitat": "idents",
    "padrao": "idents",
    "a_cada_n": "int",
    "telegrafo": "text",
    "description": "text",
    "aparencia": "text",
    "arte": "dict",
    "arte.visual": "text",
    "arte.evitar": "text",
    "autor": "ident",
    "revisao": "ident",
    "regiao": "ident",
}


def _ficha_walk(ficha: dict) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """(textos por caminho, problemas [(código, caminho)]) segundo ``FICHA_PATHS``."""
    textos: dict[str, str] = {}
    problemas: list[tuple[str, str]] = []

    def walk(prefix: str, node: dict) -> None:
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            kind = FICHA_PATHS.get(path)
            if kind is None:
                problemas.append(("schema_unknown_field", path))
            elif kind == "dict":
                if isinstance(value, dict):
                    walk(path, value)
                else:
                    problemas.append(("schema_bad_value", path))
            elif kind == "text":
                if value is None:
                    continue
                if not isinstance(value, str):
                    problemas.append(("schema_bad_value", path))
                else:
                    # `{nome}` do telegrafo é o único marcador permitido (sai antes do markup)
                    textos[path] = value.replace("{nome}", "")
            elif kind == "int":
                if not (isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9):
                    problemas.append(("schema_bad_value", path))
            elif not _is_ident_value(value) or (kind == "ident" and isinstance(value, list)):
                problemas.append(("schema_bad_value", path))

    walk("", ficha)
    return textos, problemas


def _walk_text(prefix: str, value: object, out: dict[str, str], depth: int = 0) -> None:
    """SPEC-361 R23: textos livres da ficha (só os caminhos ``text`` da allowlist)."""
    del depth
    if isinstance(value, dict):
        textos, _ = _ficha_walk(value)
        out.update({f"{prefix}.{k}": v for k, v in textos.items()})


def _text_fields(entry: SharedPoolEntry) -> dict[str, str]:
    fields: dict[str, str] = {"name": entry.name, "legend": entry.legend}
    creature = entry.namespace == PoolNamespace.CREATURE
    for key, value in entry.document.items():
        if key in _ID_FIELDS:
            continue  # identificadores são checados em validate_schema
        if creature and key in _CREATURE_ENUM_FIELDS:
            continue  # enums de criatura: `_validate_creature_enums`
        if isinstance(value, str):
            fields[key] = value
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            fields[key] = " ".join(value)
        elif key == "ficha" and isinstance(value, dict):
            _walk_text("ficha", value, fields)
    return {k: v for k, v in fields.items() if v}


# SPEC-361 R23: tetos dos textos da ficha (os do schema FichaCriaturaGerada, R14).
FICHA_TEXT_LIMITS: dict[str, int] = {
    "ficha.nome": 40,
    "ficha.anatomia.texto": 600,
    "ficha.silhueta": 160,
    "ficha.comportamento": 400,
    "ficha.nome_ataque": 40,
    "ficha.telegrafo": 120,
    "ficha.mecanica_assinatura.frase": 200,
    "ficha.contra_jogo": 200,
    "ficha.gancho": 240,
    "ficha.description": 200,
    "ficha.aparencia": 300,
    "ficha.arte.visual": 500,
    "ficha.arte.evitar": 200,
}
_FICHA_TEXT_DEFAULT = 120


def _validate_ficha(entry: SharedPoolEntry) -> list[Finding]:
    ficha = entry.document.get("ficha")
    if ficha is None:
        return []
    if not isinstance(ficha, dict):
        return [Finding("schema_bad_value", "ficha")]
    textos, problemas = _ficha_walk(ficha)
    findings = [Finding(code, f"ficha.{path}"[:40]) for code, path in problemas]
    findings += [
        Finding("schema_too_long", f"ficha.{path}"[:40])
        for path, text in textos.items()
        if len(text) > FICHA_TEXT_LIMITS.get(f"ficha.{path}", _FICHA_TEXT_DEFAULT)
    ]
    return findings


def _is_ident_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return bool(_ID_RE.match(value))
    if isinstance(value, list):
        return len(value) <= 20 and all(isinstance(v, str) and _ID_RE.match(v) for v in value)
    return False


def _validate_creature_enums(entry: SharedPoolEntry) -> list[Finding]:
    if entry.namespace != PoolNamespace.CREATURE:
        return []
    from agents.bestiary import _ATTACK_TYPE, _VIRTUDE_TEMPLATES, ARQUETIPO_VIRTUDE

    doc = entry.document
    findings = []
    arq = doc.get("arquetipo")
    if arq is not None and arq not in {*_VIRTUDE_TEMPLATES, *ARQUETIPO_VIRTUDE}:
        findings.append(Finding("schema_bad_value", "arquetipo"))
    estilo = doc.get("estilo_ataque")
    if estilo is not None and estilo not in _ATTACK_TYPE:
        findings.append(Finding("schema_bad_value", "estilo_ataque"))
    if not _is_ident_value(doc.get("region_tags")):
        findings.append(Finding("schema_bad_value", "region_tags"))
    return findings


# --------------------------------------------------------------------------- #
# schema
# --------------------------------------------------------------------------- #
_ATTRIBUTE_KEYS = frozenset({"str", "dex", "con", "int", "wis", "cha"})


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_typed_fields(entry: SharedPoolEntry) -> list[Finding]:
    """P2-2: campos não-texto do documento (tipo e faixa)."""
    doc = entry.document
    findings: list[Finding] = []
    attrs = doc.get("attributes")
    if attrs is not None:
        if not (
            isinstance(attrs, dict)
            and set(attrs) <= _ATTRIBUTE_KEYS
            and all(_is_int(v) and 1 <= v <= 30 for v in attrs.values())
        ):
            findings.append(Finding("schema_bad_attributes", "attributes"))
    rel = doc.get("initial_relationship")
    if rel is not None and not (_is_int(rel) and -100 <= rel <= 100):
        findings.append(Finding("schema_bad_value", "initial_relationship"))
    for key in ("unique", "stackable"):
        if key in doc and not isinstance(doc[key], bool):
            findings.append(Finding("schema_bad_value", key))
    tags = doc.get("tags", doc.get("region_tags"))
    if tags is not None and not (
        isinstance(tags, list) and len(tags) <= 20 and all(isinstance(t, str) for t in tags)
    ):
        findings.append(Finding("schema_bad_value", "tags"))
    return findings


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
    findings += _validate_typed_fields(entry)
    findings += _validate_ficha(entry)
    findings += _validate_creature_enums(entry)
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
