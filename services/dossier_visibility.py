"""Allowlist de campos dos dossiês do Codex/Bestiário (SPEC-211).

Os modelos abaixo SÃO a allowlist: `extra="forbid"` faz qualquer campo novo
falhar alto em vez de vazar por acidente. `assert_no_private_fields` roda sobre
o payload completo (testes + modo debug do endpoint) como defesa em
profundidade — nunca como única barreira (a barreira é a projeção em
`services/dossiers.py` + `services/player_knowledge.py`).

Vocabulário de conhecimento = SPEC-206 (`KnowledgeStamp`), reutilizado literal.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, ValidationError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeStampModel(_Strict):
    knowledge_kind: Literal["fact", "report", "rumor", "suspicion", "perception"]
    certainty: str
    source_kind: str
    source_ref: str
    label: str
    first_seen_turn: Optional[int] = None
    last_updated_turn: Optional[int] = None
    stale: bool = False


class NoteModel(KnowledgeStampModel):
    memory_id: str
    text: str


class ArtModel(_Strict):
    asset_id: str
    alt: str
    placeholder_color: Optional[str] = None
    variants: Any = None


class ClaimModel(_Strict):
    text: str
    knowledge: KnowledgeStampModel


class EncounterModel(_Strict):
    turn: int
    location_id: str = ""
    outcome: str
    encounter_id: Optional[str] = None


class _DossierBase(_Strict):
    id: str
    kind: str
    title: str
    last_updated_turn: int
    version: int
    art: Optional[ArtModel] = None
    knowledge: KnowledgeStampModel
    notes: List[NoteModel] = []


class NpcDossierModel(_DossierBase):
    role: str = ""
    location: str = ""
    status: str = ""
    relationship: int = 5
    disposition_label: str = ""
    knowledge_source: str = "met"
    revealed_traits: List[Dict[str, Any]] = []
    claims: List[ClaimModel] = []
    appears_to_know: List[ClaimModel] = []
    encounters: List[EncounterModel] = []
    last_seen_turn: Optional[int] = None
    body: str = ""


class LocationDossierModel(_DossierBase):
    body: str = ""
    region: str = ""
    npcs: List[str] = []
    creatures: List[str] = []
    events: List[EncounterModel] = []


class FactionDossierModel(_DossierBase):
    body: str = ""
    goal: str = ""
    knows_goal: bool = False
    region: str = ""
    disposition: str = ""
    reputation: int = 0
    progress: Optional[int] = None
    intel_stale: bool = False
    stale_label: str = ""


class SecretDossierModel(_DossierBase):
    fact: str = ""
    entity_id: str = ""
    turn: int = 0


class CreatureDossierModel(_DossierBase):
    tier: int
    tier_name: str
    regions: List[str] = []
    rarity_note: Optional[str] = None
    first_seen_turn: Optional[int] = None
    description: Optional[str] = None
    type: Optional[str] = None
    max_hp: Optional[int] = None
    defense: Optional[int] = None
    attacks: Optional[List[Any]] = None
    behavior: Optional[Dict[str, Any]] = None
    loot: Optional[List[Any]] = None
    revealed_cards: Optional[List[Dict[str, str]]] = None
    revealed_resistances: Optional[List[str]] = None


class ChronicleChapterIndexModel(_Strict):
    chapter_id: str = ""
    arc_title: str = ""
    started_turn: int = 0
    location: str = ""
    entry_count: int = 0
    entity_ids: List[str] = []


class DossierSectionsModel(_Strict):
    npcs: List[NpcDossierModel]
    locations: List[LocationDossierModel]
    factions: List[FactionDossierModel]
    secrets: List[SecretDossierModel]
    chronicle_index: List[ChronicleChapterIndexModel]


class DossiersResponseModel(_Strict):
    version: int
    generated_at_turn: int
    sections: DossierSectionsModel
    bestiary: List[CreatureDossierModel]
    meta: Dict[str, Any]


# Chaves de estado privado que NUNCA podem aparecer em nenhum nível do payload.
FORBIDDEN_KEYS = frozenset({
    "hidden_traits", "memory", "last_memory", "npc_secrets", "secret",
    "secrets_known", "variant_exclusive_cards", "tactical_profile",
    "cartas", "resistances", "vulnerabilities", "immunities", "virtudes",
})


def _walk(value: Any, path: str, out: List[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_KEYS:
                out.append(f"forbidden_key:{path}.{key}")
            _walk(child, f"{path}.{key}", out)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", out)


def assert_no_private_fields(payload: Mapping) -> List[str]:
    """[] = ok. Allowlist estrita (modelo `extra=forbid`) + chaves proibidas."""
    problems: List[str] = []
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
