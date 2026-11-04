"""SPEC-381: DTOs Pydantic compartilhados da API (movidos de api.py, sem mudanca)."""

import uuid
from typing import Annotated, Any, Literal
from pydantic import BaseModel, Field, field_validator
import gamedata
from gamedata import load_json_data
from services.prologue import StartScenarioIn


# --- MODELOS DE DADOS (DTOs) ---
class CreateCharacterRequest(BaseModel):
    # Auditoria A1: level sem bound permitia ouro NEGATIVO (50×level) e ficha
    # absurda; A7: campos livres viram prompt de LLM — tamanho limitado na borda.
    name: str = Field(min_length=1, max_length=80)
    race: str = Field(max_length=40)
    class_name: str = Field(max_length=40)
    region: str = Field(max_length=60)
    level: int = Field(1, ge=1, le=20)
    backstory: str | None = Field("", max_length=2000)  # null -> "" (SPEC-235 R9)
    appearance: str = Field("", max_length=1000)
    visual_exclusions: str = Field("", max_length=500)
    # spec inicio-personalizado (R4): cenário aprovado no passo de prólogo.
    # StartScenarioIn re-valida na borda (limites de campo, beats ≤ 5, npcs ≤ 2
    # → excedente = 422). None = fluxo clássico, byte a byte o atual (R6).
    scenario: StartScenarioIn | None = None
    # SPEC-351 R15: selo HMAC do cenário (NPC pessoal só vai ao pool se confere).
    scenario_token: str | None = Field(default=None, max_length=1024)
    action_id: str | None = Field(default=None, max_length=36)

    @field_validator("class_name")
    @classmethod
    def _canonical_class(cls, value: str) -> str:
        if value not in gamedata.CLASSES:
            raise ValueError("classe desconhecida")
        return value

    @field_validator("race")
    @classmethod
    def _canonical_race(cls, value: str) -> str:
        names = {
            str(row.get("name")) for row in (load_json_data("origins.json") or {}).get("races", [])
        }
        if value not in names:
            raise ValueError("raça desconhecida")
        return value

    @field_validator("region")
    @classmethod
    def _canonical_region(cls, value: str) -> str:
        names = {
            str(row.get("name"))
            for row in (load_json_data("origins.json") or {}).get("regions", [])
        }
        if value not in names:
            raise ValueError("região desconhecida")
        return value


class PlayStepRequest(BaseModel):
    """Uma jogada da lista `jogadas` (SPEC-328). O motor revalida tudo."""

    model_config = {"extra": "forbid"}
    card_id: str | None = Field(default=None, max_length=128)
    target_id: str | None = Field(default=None, max_length=128)
    ruptura: bool = False
    action_kind: Literal["attack", "maneuver", "pass", "discard"] | None = None
    maneuver: Literal["engajar", "desengajar", "guardar", "esconder", "procurar"] | None = None
    # SPEC-368 R8a: Cartas da mão marcadas para o `descartar` com `escolha`; o motor valida.
    descartar: list[Annotated[str, Field(max_length=128)]] | None = Field(
        default=None, max_length=4
    )


class ActionRequest(BaseModel):
    # Auditoria A7: ação vira prompt — sem teto, request gigante = custo/latência.
    input_text: str = Field(max_length=2000)
    game_id: str | None = None  # Opcional: permite especificar qual save carregar
    action_id: str | None = Field(default=None, max_length=36)
    # conflito-16: seleção tática canônica da UI; o motor revalida tudo.
    card_id: str | None = Field(default=None, max_length=128)
    target_id: str | None = Field(default=None, max_length=128)
    ruptura: bool = False
    reaction_card_id: str | None = Field(default=None, max_length=128)
    # Laboratório/UI tática: ações fechadas evitam parse LLM de chips mecânicos.
    action_kind: Literal["attack", "maneuver", "pass", "flee"] | None = None
    maneuver: Literal["engajar", "desengajar", "guardar", "esconder", "procurar"] | None = None
    # SPEC-328 R13: várias jogadas em ordem num único request ("Encerrar turno").
    jogadas: list["PlayStepRequest"] | None = Field(default=None, max_length=8)

    @field_validator("action_id")
    @classmethod
    def _canonical_action_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(uuid.UUID(value))
        except (ValueError, TypeError):
            raise ValueError("action_id inválido (esperado UUID)")


class ArtBriefRequest(BaseModel):
    name: str = Field(default="Herói", max_length=80)
    race: str = Field(max_length=40)
    class_name: str = Field(max_length=40)
    region: str = Field(default="", max_length=60)
    appearance: str = Field(default="", max_length=1000)
    visual_exclusions: str = Field(default="", max_length=500)


class ArtConfirmRequest(BaseModel):
    model_config = {"extra": "forbid"}
    action_id: str
    quote_id: uuid.UUID
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("confirmed must be the boolean true")
        return value


class ArtQuoteRequest(BaseModel):
    model_config = {"extra": "forbid"}
    image_type: Literal["player", "npc", "scene", "monster"] = "player"
    offer_id: uuid.UUID | None = None
    reformulation: bool = False
    # SPEC-352: id da instancia do inimigo no conflito atual. A chave do retrato NUNCA vem do cliente.
    enemy_id: str | None = Field(default=None, min_length=1, max_length=128)


class ArtQualityRequest(BaseModel):
    approved: bool


class CombatSimulatorRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=40)
    level: Literal[1, 3, 5, 10] = 1
    enemy_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(default=1, ge=1, le=3)
    action_id: str | None = Field(default=None, max_length=36)

    @field_validator("class_name")
    @classmethod
    def _known_class(cls, value: str) -> str:
        if value not in gamedata.CLASSES:
            raise ValueError("classe desconhecida")
        return value

    @field_validator("enemy_id")
    @classmethod
    def _known_enemy(cls, value: str) -> str:
        if value not in gamedata.BESTIARY:
            raise ValueError("inimigo desconhecido")
        return value


class EquipRequest(BaseModel):
    """Fase 4.3: equipa item do inventário (slot deduzido do tipo) ou desequipa slot."""

    item_id: str | None = None  # equipar este item
    unequip_slot: str | None = None  # OU esvaziar este slot
    game_id: str | None = None
    action_id: str | None = Field(default=None, max_length=36)


class PrepareCardsRequest(BaseModel):
    """SPEC-209 R4: prepara/troca Cartas fora de combate (validação 100% Python)."""

    game_id: str | None = None
    prepared: list[str] = Field(default_factory=list, max_length=64)
    action_id: str | None = Field(default=None, max_length=36)


class EspolioRequest(BaseModel):
    """SPEC-333 R1: escolhe 1 Carta do espólio pós-conflito ou recusa (`card_id` vazio)."""

    game_id: str | None = None
    card_id: str | None = Field(default=None, max_length=80)
    action_id: str | None = Field(default=None, max_length=36)


class LojaCartasRequest(BaseModel):
    """SPEC-357 R9: compra 1 Carta neutra da prateleira do mercador do local."""

    game_id: str | None = None
    card_id: str = Field(max_length=80)
    action_id: str | None = Field(default=None, max_length=36)


class ForjaRequest(BaseModel):
    """SPEC-333 R4/R5/R8: ações de forja fora de combate (validação 100% Python)."""

    game_id: str | None = None
    acao: Literal["esquecer", "afiar", "purgar"]
    card_id: str | None = Field(default=None, max_length=80)
    scar_id: str | None = Field(default=None, max_length=80)
    via: Literal["descanso", "templo", "medico"] | None = None
    action_id: str | None = Field(default=None, max_length=36)


class LevelUpRequest(BaseModel):
    """Conflito v2: consome escolha de Carta/evolução ou de Virtude."""

    choice_id: str
    card_id: str | None = None
    evolve_card_id: str | None = None
    caminho: str | None = None
    virtude: str | None = None
    attr: str | None = None
    subclass_id: str | None = None
    virtue_card_id: str | None = None
    game_id: str | None = None
    action_id: str | None = Field(default=None, max_length=36)


class ChronicleSearchRequest(BaseModel):
    game_id: str
    query: str = Field(min_length=2, max_length=300)
    top_k: int = Field(default=5, ge=1, le=10)


class VisualVariantResponse(BaseModel):
    url: str
    width: int
    height: int
    bytes: int
    sha256: str


class VisualVariantsResponse(BaseModel):
    thumbnail: VisualVariantResponse
    display: VisualVariantResponse


class VisualAssetResponse(BaseModel):
    asset_id: str
    subject_type: Literal["race", "class", "location", "npc"]
    subject_id: str
    title: str
    alt: str
    placeholder_color: str
    variants: VisualVariantsResponse


class SceneVisualResponse(BaseModel):
    location_id: str
    location_name: str
    scope: Literal["exact", "regional", "placeholder"]
    asset: VisualAssetResponse | None = None


class VisualCueResponse(BaseModel):
    kind: Literal["npc_first_appearance"]
    subject_id: str
    subject_name: str
    caption: str
    asset: VisualAssetResponse | None = None
    fallback: bool


class VisualResponse(BaseModel):
    scene: SceneVisualResponse
    cue: VisualCueResponse | None = None


class GameResponse(BaseModel):
    timeline_epoch: int = 0
    portrait_generation_id: str | None = None
    game_id: str  # <--- Novo: Frontend precisa saber o ID
    message: str
    message_type: str
    # SPEC-202 R9: quem respondeu — {kind: narrator|npc|system, id, name, reason}.
    speaker: dict[str, str] = {}
    player_stats: dict[str, Any]
    # Fase 4.3: estruturado — {id, name, qty, type, equipped, slot}
    inventory: list[dict[str, Any]]
    current_location: str
    narrative_summary: str  # <--- Novo: Frontend pode mostrar o resumo
    last_turn_log: list[dict[str, Any]]
    simulated: bool = False  # True quando rodando em modo simulado (sem API key)
    world: dict[str, Any] = {}  # location_id, day, period, visited (fog of war), danger
    quest: dict[str, Any] = {}  # objetivo atual, beats (status), clímax, progresso
    combat: dict[str, Any] = {}  # inimigos, condições, iniciativa, round, cooldowns
    npcs: list[
        dict[str, Any]
    ] = []  # NPCs conhecidos (nome, papel, local, relação, última lembrança)
    art_offers: list[dict[str, str]] = []
    art_generations: list[dict[str, str]] = []
    chronicle: list[
        dict[str, Any]
    ] = []  # capítulos: {title, started_turn, location, entries[{text,turn,kind,event_id?}]}
    factions: list[dict[str, Any]] = []  # fações vivas: objetivo, progresso, rótulo de standing
    reputation_notices: list[dict[str, str]] = []  # SPEC-298 R26: avisos do turno (sem números)
    companion_feedback: list[str] = []  # SPEC-300 R29: frases do turno (sem números)
    party: list[
        dict[str, Any]
    ] = []  # Fase 4.5: companheiros {name, hp, max_hp, active, archetype, status}
    death_pending: bool = (
        False  # spec checkpoints-morte: queda letal — abre a tela de morte no cliente
    )
    game_over: bool = False  # memorial/bloqueio definitivo; Vitalidade 0 não basta
    death: dict[str, Any] = {}  # conflito-16: Última Ação/Terminal/estabilização
    continuity: dict[str, Any] = {}
    combat_simulation: dict[str, Any] = {}
    turn_outcome: dict[str, Any] = {}  # SPEC-199: ganhos do turno (XP/ouro/itens/missões)
    combat_result: dict[str, Any] = {}  # SPEC-203: desfecho do encontro (turno de término)
    # SPEC-213 R13: só status/versões das projeções derivadas (nunca conteúdo).
    projections: dict[str, Any] = {}
    visual: VisualResponse
