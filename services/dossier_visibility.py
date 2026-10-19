"""Allowlist de campos dos dossiês do Codex/Bestiário (SPEC-211).

Os modelos abaixo SÃO a allowlist: `extra="forbid"` faz qualquer campo novo
falhar alto em vez de vazar por acidente. `assert_no_private_fields` roda sobre
o payload completo (testes + modo debug do endpoint) como defesa em
profundidade — nunca como única barreira (a barreira é a projeção em
`services/dossiers.py` + `services/player_knowledge.py`).

Vocabulário de conhecimento = SPEC-206 (`KnowledgeStamp`), reutilizado literal.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, ValidationError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeStampModel(_Strict):
    knowledge_kind: Literal["fact", "report", "rumor", "suspicion", "perception"]
    certainty: str
    source_kind: str
    source_ref: str
    label: str
    first_seen_turn: int | None = None
    last_updated_turn: int | None = None
    stale: bool = False


class NoteModel(KnowledgeStampModel):
    memory_id: str
    text: str


class ArtModel(_Strict):
    asset_id: str
    alt: str
    placeholder_color: str | None = None
    variants: Any = None


class ClaimModel(_Strict):
    text: str
    knowledge: KnowledgeStampModel


class EncounterModel(_Strict):
    turn: int
    location_id: str = ""
    outcome: str
    encounter_id: str | None = None


class _DossierBase(_Strict):
    id: str
    kind: str
    title: str
    last_updated_turn: int
    version: int
    art: ArtModel | None = None
    knowledge: KnowledgeStampModel
    notes: list[NoteModel] = []


class NpcDossierModel(_DossierBase):
    role: str = ""
    location: str = ""
    status: str = ""
    relationship: int = 5
    disposition_label: str = ""
    knowledge_source: str = "met"
    revealed_traits: list[dict[str, Any]] = []
    claims: list[ClaimModel] = []
    appears_to_know: list[ClaimModel] = []
    encounters: list[EncounterModel] = []
    last_seen_turn: int | None = None
    body: str = ""


class LocationDossierModel(_DossierBase):
    body: str = ""
    region: str = ""
    npcs: list[str] = []
    creatures: list[str] = []
    events: list[EncounterModel] = []


class FactionDossierModel(_DossierBase):
    body: str = ""
    goal: str = ""
    knows_goal: bool = False
    region: str = ""
    disposition: str = ""
    reputation: int = 0
    progress: int | None = None
    intel_stale: bool = False
    stale_label: str = ""


class SecretDossierModel(_DossierBase):
    fact: str = ""
    entity_id: str = ""
    turn: int = 0


class CreatureDossierModel(_DossierBase):
    tier: int
    tier_name: str
    regions: list[str] = []
    rarity_note: str | None = None
    first_seen_turn: int | None = None
    description: str | None = None
    type: str | None = None
    max_hp: int | None = None
    defense: int | None = None
    attacks: list[Any] | None = None
    behavior: dict[str, Any] | None = None
    loot: list[Any] | None = None
    revealed_cards: list[dict[str, str]] | None = None
    revealed_resistances: list[str] | None = None


class ChronicleChapterIndexModel(_Strict):
    chapter_id: str = ""
    arc_title: str = ""
    started_turn: int = 0
    location: str = ""
    entry_count: int = 0
    entity_ids: list[str] = []


class DossierSectionsModel(_Strict):
    npcs: list[NpcDossierModel]
    locations: list[LocationDossierModel]
    factions: list[FactionDossierModel]
    secrets: list[SecretDossierModel]
    chronicle_index: list[ChronicleChapterIndexModel]


class DossiersResponseModel(_Strict):
    version: int
    generated_at_turn: int
    sections: DossierSectionsModel
    bestiary: list[CreatureDossierModel]
    meta: dict[str, Any]


# Chaves de estado privado que NUNCA podem aparecer em nenhum nível do payload.
FORBIDDEN_KEYS = frozenset({
    "hidden_traits", "memory", "last_memory", "npc_secrets", "secret",
    "secrets_known", "variant_exclusive_cards", "tactical_profile",
    "cartas", "resistances", "vulnerabilities", "immunities", "virtudes",
})


def _walk(value: Any, path: str, out: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_KEYS:
                out.append(f"forbidden_key:{path}.{key}")
            _walk(child, f"{path}.{key}", out)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", out)


def assert_no_private_fields(payload: Mapping) -> list[str]:
    """[] = ok. Allowlist estrita (modelo `extra=forbid`) + chaves proibidas."""
    problems: list[str] = []
    try:
        DossiersResponseModel.model_validate(payload)
    except ValidationError as exc:
        for err in exc.errors():
            problems.append(f"schema:{'.'.join(str(p) for p in err['loc'])}:{err['type']}")
    _walk(payload, "$", problems)
    return problems


def leak_view(payload: Mapping) -> dict:
    """Visão 'forma de Codex' do payload para o oráculo `assert_no_player_leak`
    (SPEC-206): mesmas categorias, contagens já filtradas. Mantém o payload
    original no blob para que o scan textual cubra TODO o JSON."""
    sections = payload.get("sections") or {}
    view = dict(payload)
    view["locations"] = list(sections.get("locations") or [])
    view["factions"] = list(sections.get("factions") or [])
    view["characters"] = list(sections.get("npcs") or [])
    view["creatures"] = list(payload.get("bestiary") or [])
    view["secrets"] = list(sections.get("secrets") or [])
    view["meta"] = {"counts": {
        "locations": len(view["locations"]), "factions": len(view["factions"]),
        "characters": len(view["characters"]), "creatures": len(view["creatures"]),
        "secrets": len(view["secrets"]),
    }}
    return view
