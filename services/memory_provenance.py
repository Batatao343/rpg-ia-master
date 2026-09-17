"""Proveniência determinística para a memória narrativa da sessão.

A LLM só fornece texto. Confiança e autoridade são derivadas aqui a partir da
origem que o motor conhece; portanto um payload livre nunca consegue se declarar
canônico. O ledger vive no save e os mesmos metadados acompanham os vetores FAISS.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from services.secret_signatures import SECRET_SIGNATURES

MemoryProvenance = Literal[
    "canonical_event",
    "player_observation",
    "npc_claim",
    "inference",
    "legacy_unverified",
]
MemoryConfidence = Literal["confirmed", "reported", "speculative"]

MAX_MEMORY_FACTS = 500
MAX_PENDING_MEMORY_FACTS = 100
MAX_MEMORY_REJECTIONS = 100
MAX_MEMORY_PROMOTIONS = 100

_CONFIDENCE_BY_PROVENANCE: Dict[str, MemoryConfidence] = {
    "canonical_event": "confirmed",
    "player_observation": "reported",
    "npc_claim": "reported",
    "inference": "speculative",
    "legacy_unverified": "speculative",
}
_CONFIDENCE_RANK = {"speculative": 0, "reported": 1, "confirmed": 2}


def _clean_text(value, limit: int = 480) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def _stable_id(values: dict) -> str:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "mem_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


class MemoryFactRecord(BaseModel):
    """Forma persistida fechada de um fato/relato da memória."""

    memory_id: str = ""
    text: str = Field(min_length=1, max_length=480)
    provenance: MemoryProvenance
    confidence: MemoryConfidence = "speculative"
    source_id: Optional[str] = None
    source_turn: Optional[int] = Field(default=None, ge=0)
    canonical_entity_ids: List[str] = Field(default_factory=list)

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value):
        return _clean_text(value)

    @field_validator("source_id", mode="before")
    @classmethod
    def _normalize_source(cls, value):
        cleaned = _clean_text(value, 160)
        return cleaned or None

    @field_validator("canonical_entity_ids", mode="before")
    @classmethod
    def _normalize_entities(cls, value):
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            return []
        return list(dict.fromkeys(
            cleaned
            for item in value
            if (cleaned := _clean_text(item, 120))
        ))[:20]

    @model_validator(mode="after")
    def _derive_authority(self):
        # Confiança é função fechada da proveniência, nunca texto controlado pela LLM.
        self.confidence = _CONFIDENCE_BY_PROVENANCE[self.provenance]
        identity = {
            "text": self.text.casefold(),
            "provenance": self.provenance,
            "source_id": self.source_id,
            "source_turn": self.source_turn,
        }
        self.memory_id = _stable_id(identity)
        return self


def make_memory_fact(
    text: str,
    *,
    provenance: MemoryProvenance,
    confidence: Optional[MemoryConfidence] = None,
    source_id: Optional[str] = None,
    source_turn: Optional[int] = None,
    canonical_entity_ids: Optional[Iterable[str]] = None,
) -> dict:
    """Cria registro e ignora qualquer tentativa de elevar ``confidence``."""
    record = MemoryFactRecord(
        text=text,
        provenance=provenance,
        confidence=confidence or _CONFIDENCE_BY_PROVENANCE[provenance],
        source_id=source_id,
        source_turn=source_turn,
        canonical_entity_ids=list(canonical_entity_ids or []),
    )
    return record.model_dump(mode="json")


def normalize_memory_facts(rows: Iterable | None, *, pending: bool = False) -> List[dict]:
    """Normaliza ledger/fila. Strings antigas viram ``legacy_unverified``."""
    normalized: List[dict] = []
    seen: set[str] = set()
    for raw in rows or []:
        try:
            if isinstance(raw, str):
                record = MemoryFactRecord(
                    text=raw,
                    provenance="legacy_unverified",
                    confidence="speculative",
                )
            elif isinstance(raw, dict):
                data = dict(raw)
                if not data.get("provenance"):
                    data["provenance"] = "legacy_unverified"
                if not data.get("confidence"):
                    data["confidence"] = "speculative"
                record = MemoryFactRecord.model_validate(data)
            else:
                continue
        except Exception:
            continue
        item = record.model_dump(mode="json")
        if item["memory_id"] in seen:
            continue
        seen.add(item["memory_id"])
        normalized.append(item)
    limit = MAX_PENDING_MEMORY_FACTS if pending else MAX_MEMORY_FACTS
    return normalized[-limit:]


def accepted_secret_ids(state: dict) -> set[str]:
    """IDs explicitamente revelados por eventos aceitos, sem usar prosa/resumo."""
    revealed: set[str] = set()
    for event in state.get("event_log", []) or []:
        if not isinstance(event, dict) or event.get("type") != "secret_revealed":
            continue
        payload = event.get("payload") or {}
        for candidate in (
            event.get("target_id"), payload.get("secret_id"), payload.get("id")
        ):
            cleaned = _clean_text(candidate, 120)
            if cleaned:
                revealed.add(cleaned)
    return revealed


def find_strict_unrevealed(text: str, state: dict) -> Optional[str]:
    """Detecta assinatura oculta considerando apenas ``secret_revealed`` aceito."""
    low = str(text or "").casefold()
    revealed = {item.casefold() for item in accepted_secret_ids(state)}
    for secret_id, signatures in SECRET_SIGNATURES.items():
        if secret_id.casefold() in revealed:
            continue
        if any(signature.casefold() in low for signature in signatures):
            return secret_id
    return None


def applicable_source_ids(state: dict) -> set[str]:
    """Fontes que o estado consegue provar sem interpretação semântica."""
    sources: set[str] = set()
    for event in state.get("event_log", []) or []:
        if isinstance(event, dict) and event.get("event_id"):
            sources.add(str(event["event_id"]))
    conflict = state.get("conflict_summary") or {}
    if isinstance(conflict, dict) and conflict.get("conflict_id"):
        cid = str(conflict["conflict_id"])
        sources.update({cid, f"conflict:{cid}"})
    for cid in state.get("consumed_conflict_ids", []) or []:
        sources.update({str(cid), f"conflict:{cid}"})
    for quest in state.get("quests", []) or []:
        if isinstance(quest, dict) and quest.get("id"):
            sources.add(f"quest:{quest['id']}")
    return sources


def source_is_applicable(source_id: Optional[str], state: dict) -> bool:
    if not source_id:
        return False
    if source_id in applicable_source_ids(state):
        return True
    # Prefixos só são emitidos por código determinístico, nunca pelo schema da LLM.
    return source_id.startswith(("engine_policy:", "npc:", "codex:"))


def false_player_death_claim(text: str, state: dict) -> bool:
    """True only for a terminal claim contradicted by canonical player events."""
    player_name = str((state.get("player") or {}).get("name") or "").strip()
    event_types = {
        str(event.get("type") or "")
        for event in (state.get("event_log") or [])
        if isinstance(event, dict)
    }
    if (
        not player_name
        or "player_downed" not in event_types
        or "player_died" in event_types
        or state.get("game_over")
    ):
        return False
    name = re.escape(player_name)
    return bool(re.search(
        rf"(?:{name}.{{0,32}}\b(?:morreu|est[aá]\s+mort[oa])\b|"
        rf"\bmorte\s+(?:definitiva\s+)?de\s+{name}\b)",
        str(text or ""),
        re.IGNORECASE,
    ))


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold()


def canonical_location_contradiction(text: str) -> Optional[dict]:
    """Return an explicit location-to-wrong-region assertion, if present.

    Mere co-occurrence is intentionally insufficient: travel and comparisons
    often mention two valid regions in the same sentence.
    """
    folded = _fold(text)
    if not folded:
        return None
    import gamedata

    locations = [
        row for row in (gamedata.WORLD_MAP.get("locations") or [])
        if row.get("name") and row.get("region")
    ]
    regions = sorted({
        str(row["region"]) for row in locations if row.get("region")
    }, key=len, reverse=True)
    roles = r"(?:bairro|distrito|cidade|porto|assentamento|regiao|aldeia|vila)"
    for location in sorted(
        locations, key=lambda row: len(str(row["name"])), reverse=True,
    ):
        location_name = str(location["name"])
        location_folded = _fold(location_name)
        if location_folded not in folded:
            continue
        expected_region = str(location["region"])
        for wrong_region in regions:
            if _fold(wrong_region) == _fold(expected_region):
                continue
            loc = re.escape(location_folded)
            wrong = re.escape(_fold(wrong_region))
            patterns = (
                rf"\b{loc}\b\s*,?\s*(?:e\s+um|e\s+uma|eh\s+um|eh\s+uma)?\s*"
                rf"{roles}(?:\s+\w+){{0,4}}\s+(?:de|do|da|em|no|na)\s+"
                rf"(?:o\s+|a\s+)?{wrong}\b",
                rf"\b{loc}\b\s+(?:fica|pertence|localiza-se|"
                rf"esta\s+localizad[oa])\s+(?:em|no|na|a|ao)\s+"
                rf"(?:o\s+|a\s+)?{wrong}\b",
                rf"\b{loc}\b\s+(?:de|do|da)\s+{wrong}\b",
            )
            if any(re.search(pattern, folded) for pattern in patterns):
                return {
                    "location_id": str(location.get("id") or ""),
                    "location_name": location_name,
                    "expected_region": expected_region,
                    "claimed_region": wrong_region,
                }
    return None


def sanitize_location_grounding(text: str) -> tuple[str, list[dict]]:
    """Drop contradictory sentences; never invent a corrected replacement."""
    sentences = re.split(r"(?<=[.!?])\s+", _clean_text(text, 4000))
    accepted: list[str] = []
    rejected: list[dict] = []
    for sentence in sentences:
        contradiction = canonical_location_contradiction(sentence)
        if contradiction:
            rejected.append({**contradiction, "text_preview": sentence[:120]})
        elif sentence.strip():
            accepted.append(sentence.strip())
    return " ".join(accepted).strip(), rejected


_NPC_SPECIES = (
    ("goblin", ("goblin",)),
    ("orc", ("orc", "orque")),
    ("anão", ("anao", "ana", "anão", "anã")),
    ("elfo", ("elfo", "elfa")),
    ("humano", ("humano", "humana", "homem", "mulher")),
    ("halfling", ("halfling",)),
    ("tiefling", ("tiefling",)),
)
_NPC_SIZES = (
    ("pequeno", ("pequeno", "pequena", "miudo", "miuda")),
    ("alto", ("alto", "alta", "grande", "gigante")),
)


def _first_identity_label(text: str, catalog) -> Optional[str]:
    folded = _fold(text)
    for label, terms in catalog:
        if any(re.search(rf"\b{re.escape(_fold(term))}\b", folded) for term in terms):
            return label
    return None


def _npc_descriptor(text: str, npc_name: str) -> str:
    folded = _fold(text)
    name = re.escape(_fold(npc_name))
    match = re.search(
        rf"\b{name}\b\s*(?P<descriptor>"
        r"\([^)]{1,180}\)|"
        r"(?:e|era|parece|,|:)\s*(?:um|uma)?\s*[^.!?]{1,180})",
        folded,
    )
    return match.group("descriptor") if match else ""


def npc_identity_contradiction(text: str, state: dict) -> Optional[dict]:
    """Espécie/porte explícitos não podem trocar a ficha canônica do NPC."""
    from services.entity_identity import coalesce_runtime_npcs

    folded = _fold(text)
    for key, npc in coalesce_runtime_npcs(state.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        name = str(npc.get("name") or key)
        if _fold(name) not in folded:
            continue
        descriptor = _npc_descriptor(text, name)
        if not descriptor:
            continue
        anchor = " ".join((
            str(npc.get("appearance") or ""),
            str(npc.get("role") or ""),
        ))
        for field, catalog in (("species", _NPC_SPECIES), ("size", _NPC_SIZES)):
            expected = _first_identity_label(anchor, catalog)
            claimed = _first_identity_label(descriptor, catalog)
            if expected and claimed and claimed != expected:
                return {
                    "npc_key": str(key),
                    "npc_name": name,
                    "field": field,
                    "expected": expected,
                    "claimed": claimed,
                }
    return None


def sanitize_npc_identity_grounding(text: str, state: dict) -> tuple[str, list[dict]]:
    """Remove frases que reescrevem espécie/porte de um NPC conhecido."""
    sentences = re.split(r"(?<=[.!?])\s+", _clean_text(text, 4000))
    accepted: list[str] = []
    rejected: list[dict] = []
    for sentence in sentences:
        contradiction = npc_identity_contradiction(sentence, state)
        if contradiction:
            rejected.append({**contradiction, "text_preview": sentence[:120]})
        elif sentence.strip():
            accepted.append(sentence.strip())
    return " ".join(accepted).strip(), rejected


_PLAYER_POSSESSION = re.compile(
    r"\b(?:o\s+)?(?:viajante|aventureir[oa]|heroi|heroina|personagem)\b"
    r"[^.!?]{0,40}?\b(?:carrega|possui|leva\s+consigo|tem\s+no\s+inventario)\b"
    r"(?P<items>[^.!?]{0,360})",
)


def inventory_possession_contradiction(text: str, state: dict) -> Optional[dict]:
    """Detecta apenas afirmações explícitas de posse do jogador.

    O inventário mecânico prevalece sobre uma recusa antiga: se o objeto foi
    adquirido depois, sua presença atual torna a frase válida.
    """
    folded = _fold(text)
    player = state.get("player") or {}
    player_name = _fold(player.get("name", ""))
    subject_pattern = _PLAYER_POSSESSION
    match = subject_pattern.search(folded)
    if match is None and player_name:
        match = re.search(
            rf"\b{re.escape(player_name)}\b[^.!?]{{0,40}}?\b"
            r"(?:carrega|possui|leva\s+consigo|tem\s+no\s+inventario)\b"
            r"(?P<items>[^.!?]{0,360})",
            folded,
        )
    if match is None:
        return None

    from gamedata import ARTIFACTS_DB
    from inventory import item_display

    inventory = [row for row in (player.get("inventory") or []) if isinstance(row, dict)]
    present_ids = {str(row.get("id") or "") for row in inventory}
    present_names = {
        name
        for row in inventory
        if (name := _fold(item_display(row)))
    }
    clause = match.group("items")

    for rejected in state.get("rejected_item_claims") or []:
        label = _fold(rejected)
        if label and label in clause and label not in present_names:
            return {"item_name": str(rejected), "claim_kind": "rejected_item"}

    for item_id, item in ARTIFACTS_DB.items():
        name = str((item or {}).get("name") or "")
        label = _fold(name)
        if label and label in clause and str(item_id) not in present_ids:
            return {"item_name": name, "item_id": str(item_id), "claim_kind": "absent_canonical_item"}
    return None


def sanitize_inventory_grounding(text: str, state: dict) -> tuple[str, list[dict]]:
    """Remove frases de posse fantasma sem inventar substituição."""
    sentences = re.split(r"(?<=[.!?])\s+", _clean_text(text, 4000))
    accepted: list[str] = []
    rejected: list[dict] = []
    for sentence in sentences:
        contradiction = inventory_possession_contradiction(sentence, state)
        if contradiction:
            rejected.append({**contradiction, "text_preview": sentence[:120]})
        elif sentence.strip():
            accepted.append(sentence.strip())
    return " ".join(accepted).strip(), rejected


def validate_memory_fact(record: dict, state: dict) -> tuple[Optional[dict], Optional[str]]:
    """Falha fechada: segredo não revelado ou confirmação sem prova é recusado."""
    normalized = normalize_memory_facts([record])
    if not normalized:
        return None, "invalid_memory_fact"
    item = normalized[0]
    secret_id = find_strict_unrevealed(item["text"], state)
    if secret_id:
        return None, f"unrevealed_secret:{secret_id}"
    if false_player_death_claim(item["text"], state):
        return None, "player_downed_not_dead"
    contradiction = canonical_location_contradiction(item["text"])
    if contradiction:
        return None, (
            "location_region_contradiction:"
            f"{contradiction['location_id']}:{contradiction['claimed_region']}"
        )
    inventory_contradiction = inventory_possession_contradiction(item["text"], state)
    if inventory_contradiction:
        return None, (
            "inventory_possession_contradiction:"
            f"{inventory_contradiction['item_name']}"
        )
    npc_contradiction = npc_identity_contradiction(item["text"], state)
    if npc_contradiction:
        return None, (
            "npc_identity_contradiction:"
            f"{npc_contradiction['npc_name']}:{npc_contradiction['field']}"
        )
    if item["confidence"] == "confirmed" and not source_is_applicable(
        item.get("source_id"), state
    ):
        return None, "confirmed_without_applicable_source"
    return item, None


def commit_memory_facts(existing: Iterable | None, new: Iterable | None) -> tuple[List[dict], int]:
    """Merge por texto, idempotente, preferindo a versão de maior confiança."""
    ledger = normalize_memory_facts(existing)
    by_text = {item["text"].casefold(): item for item in ledger}
    order = [item["text"].casefold() for item in ledger]
    promotions = 0
    for item in normalize_memory_facts(new):
        key = item["text"].casefold()
        previous = by_text.get(key)
        if previous is None:
            by_text[key] = item
            order.append(key)
            continue
        old_rank = _CONFIDENCE_RANK[previous["confidence"]]
        new_rank = _CONFIDENCE_RANK[item["confidence"]]
        if new_rank > old_rank:
            by_text[key] = item
            promotions += 1
    return [by_text[key] for key in order][-MAX_MEMORY_FACTS:], promotions


def memory_metadata(record: dict) -> dict:
    """Metadados primitivos compatíveis com o docstore do FAISS."""
    item = normalize_memory_facts([record])[0]
    return {
        "memory_id": item["memory_id"],
        "memory_provenance": item["provenance"],
        "memory_confidence": item["confidence"],
        "memory_source_id": item.get("source_id") or "",
        "memory_source_turn": (
            item["source_turn"] if item.get("source_turn") is not None else -1
        ),
        "memory_entity_ids": ",".join(item.get("canonical_entity_ids") or []),
    }


def format_memory_fact(record: dict) -> str:
    item = normalize_memory_facts([record])[0]
    if item["provenance"] == "legacy_unverified":
        return f"[NÃO VERIFICADO | legacy_unverified] {item['text']}"
    label = {
        "confirmed": "CONFIRMADO",
        "reported": "RELATO",
        "speculative": "ESPECULATIVO",
    }[item["confidence"]]
    details = [label, item["provenance"]]
    if item.get("source_id"):
        details.append(f"fonte {item['source_id']}")
    if item.get("source_turn") is not None:
        details.append(f"turno {item['source_turn']}")
    return f"[{' | '.join(details)}] {item['text']}"


def bounded_audit_rows(rows: Iterable | None, *, limit: int) -> List[dict]:
    clean = [dict(row) for row in rows or [] if isinstance(row, dict)]
    return clean[-limit:]
