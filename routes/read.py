"""SPEC-381: rotas de read (movidas de api.py, sem mudanca)."""

import uuid
from copy import deepcopy
from typing import Any
from fastapi import APIRouter, HTTPException, Response
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
import gamedata
from character_creator import create_player_character
from gamedata import CLASSES, load_json_data
from services.discovery import player_codex
from services.visual_catalog import creation_visuals
from world_utils import starting_world
import api_core
from api_core import _fail_operation
from api_models import CombatSimulatorRequest, GameResponse
from api_presenters import _simulation_manifest, format_response

router = APIRouter()


def combat_simulator_options() -> dict[str, Any]:
    """Catálogo público mínimo do laboratório, derivado dos dados canônicos."""
    allowed = {"lacaio", "padrao", "elite", "chefe", "nomeado"}
    enemies = []
    for enemy_id, raw in gamedata.BESTIARY.items():
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("categoria") or "padrao").strip().lower()
        if category not in allowed:
            continue
        enemies.append(
            {
                "id": str(enemy_id),
                "name": str(raw.get("name") or enemy_id),
                "category": category,
                "regions": [str(region) for region in (raw.get("regions") or [])],
            }
        )
    enemies.sort(
        key=lambda enemy: (
            {"lacaio": 0, "padrao": 1, "elite": 2, "nomeado": 3, "chefe": 4}[enemy["category"]],
            enemy["name"].casefold(),
        )
    )
    return {
        "classes": list(gamedata.CLASSES),
        "levels": [1, 3, 5, 10],
        "quantities": [1, 2, 3],
        "enemies": enemies,
    }


def _build_combat_simulator_state(req: CombatSimulatorRequest) -> dict:
    """Cria arena isolada com fichas de produção e zero acesso a LLM/RAG."""
    from services import conflict_orchestrator as orchestrator
    from services import conflict_scene

    player = create_player_character(
        {
            "name": "Combatente de Teste",
            "class_name": req.class_name,
            "race": "Humano",
            "region": "Nova Arcádia",
            "backstory": "Laboratório mecânico de combate.",
            "level": req.level,
        },
        use_llm_flavor=False,
    )
    player.update(
        {
            "gold": 0,
            "alignment": "Neutro",
            "active_conditions": [],
            "dead": False,
            "estado_terminal": False,
            "last_stand_pending": False,
            "last_stand_resolved": False,
        }
    )
    orchestrator.ensure_combat_sheet(player, is_player=True)

    template = gamedata.BESTIARY[req.enemy_id]
    category = str(template.get("categoria") or "padrao").lower()
    danger = {
        "lacaio": 1,
        "padrao": 2,
        "elite": 4,
        "nomeado": 5,
        "chefe": 6,
    }.get(category, 2)
    # SPEC-290: mesmo bônus de sobrevivência de Chefe/Nomeado do jogo real.
    from agents.bestiary import apply_encounter_survival
    from services.encounter_preparation import compute_encounter_level

    encounter_level = compute_encounter_level(location_danger=danger, region_danger=danger)
    enemies = []
    for index in range(1, req.quantity + 1):
        enemy = deepcopy(template)
        enemy["archetype_id"] = req.enemy_id
        enemy["id"] = f"{req.enemy_id}__sim_{index}"
        if req.quantity > 1:
            enemy["name"] = f"{template.get('name', req.enemy_id)} {index}"
        enemy.update(
            {
                "status": "ativo",
                "dead": False,
                "fled": False,
                "surrendered": False,
                "conscious": True,
                "active_conditions": [],
                "ferimentos": {"leve": [], "grave": [], "critico": []},
            }
        )
        apply_encounter_survival(enemy, encounter_level)
        enemy["vitalidade"] = int(enemy.get("max_vitalidade") or enemy.get("vitalidade") or 1)
        enemies.append(orchestrator.ensure_combat_sheet(enemy))

    scene = conflict_scene.new_scene(
        [
            {"id": "arena", "name": "Arena do Véu", "connections": []},
        ]
    )
    conflict_scene.place(scene, "player", zone_id="arena", distance_state="proximo")
    for enemy in enemies:
        conflict_scene.place(scene, enemy["id"], zone_id="arena", distance_state="proximo")
    conflict_scene.freeze(scene)

    world = starting_world("Nova Arcádia", req.level)
    world["current_location"] = "Arena do Véu"
    world["danger_level"] = danger
    game_id = str(uuid.uuid4())
    enemy_label = str(template.get("name") or req.enemy_id)
    return {
        "game_id": game_id,
        "processed_action_ids": [],
        "visual_seen_entity_ids": [],
        "visual_cue_ledger": [],
        "narrative_summary": "Laboratório isolado de combate.",
        "archivist_last_run": 0,
        "archive_due": False,
        "chronicle": [],
        "combat_simulation": {
            "enabled": True,
            "enemy_id": req.enemy_id,
            "quantity": req.quantity,
        },
        "player": player,
        "world": world,
        "messages": [
            AIMessage(
                content=(
                    f"⚔️ Laboratório iniciado: {req.class_name} nível {req.level} contra "
                    f"{req.quantity}× {enemy_label}. Escolha uma Carta ou manobra."
                )
            )
        ],
        "party": [],
        "enemies": enemies,
        "factions": [],
        "faction_intel": {},
        "bestiary_knowledge": {},
        "quests": [],
        "npcs": {},
        "campaign_plan": {
            "location": "Arena do Véu",
            "beats": [{"description": "Concluir o teste de combate.", "status": "pending"}],
            "climax": "Resultado do laboratório",
            "current_step": 0,
            "last_planned_turn": 0,
            "arc_title": "Laboratório de Combate",
        },
        "needs_replan": False,
        "next": "combat_agent",
        "combat_target": enemy_label,
        "loot_source": None,
        "combat": {
            "round": 0,
            "active": True,
            "scene": scene,
            "idle_turns": 0,
            "encounter_level": world["danger_level"],
            # SPEC-203: paridade de fase/manifesto (sem manifesto narrativo).
            "phase": "active",
            "outcome": None,
            "instance_id": f"{game_id}:sim",
            "encounter": _simulation_manifest(enemies, game_id, scene),
        },
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
        "event_rejections": [],
        "consumed_conflict_ids": [],
        "memory_facts": [],
        "pending_memory_facts": [],
        "memory_rejections": [],
        "memory_promotions": [],
        "pending_npc_memory": [],
        "narrative_rejections": [],
        "rejected_item_claims": [],
        "game_over": False,
        "death_pending": False,
        "continuity": {
            "session_action_count": 0,
            "timeline_epoch": 0,
            "last_checkpoint_turn": 0,
            "death_history": [],
        },
    }


@router.get("/data/combat-simulator")
def get_combat_simulator_options():
    return combat_simulator_options()


@router.post("/game/combat-simulator", response_model=GameResponse)
def new_combat_simulator(req: CombatSimulatorRequest):
    claim, _request_hash, prior = api_core._begin_create_operation(req)
    if prior is not None:
        return prior
    try:
        state = _build_combat_simulator_state(req)
        response = format_response(state)
        if claim is not None:
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            version, _receipt = get_runtime().turn_coordinator.commit_create(
                current_principal(),
                claim,
                state,
                receipt={"response": response.model_dump(mode="json")},
                checkpoint=True,
            )
            state["_storage_version"] = version
        elif not api_core.save_game_state(state):
            raise RuntimeError("falha ao persistir laboratório")
        return response
    except Exception as exc:
        _fail_operation(claim, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível criar o laboratório.",
        ) from exc


@router.get("/data/options")
def get_creation_options():
    origins = load_json_data("origins.json")
    return {
        "races": [r["name"] for r in origins.get("races", [])],
        # Fase 2.5b: raças completas (desc + traits) p/ o frontend exibir na criação
        "races_full": origins.get("races", []),
        "classes": list(CLASSES.keys()),
        "regions": [r["name"] for r in origins.get("regions", [])],
        "visuals": creation_visuals(),
    }


@router.get("/data/onboarding")
def get_onboarding():
    """Spec onboarding-valoria (R4): lore curado do wizard de criação.

    Conteúdo estático de data/onboarding.json — zero LLM, zero RAG.
    """
    data = load_json_data("onboarding.json")
    if not data:
        raise HTTPException(status_code=404, detail="Conteúdo de onboarding indisponível.")
    return data


@router.get("/game/map")
def get_game_map(game_id: str | None = None):
    """SPEC-210: mapa do JOGO com fog server-side (só visitados + adjacentes).

    Mesmo guard de save de /game/state (UUID validado; 404 sem save; em perfis
    com banco o carregamento já é escopado ao dono). Fail-closed: nenhum nome,
    perigo, lore ou arte de local não alcançado sai daqui."""
    from services.map_view import build_map_view

    state = api_core._load_unlocked_or_locked(api_core._resolve_save_file(game_id), game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return build_map_view(state)


@router.get("/data/map")
def get_world_map(game_id: str | None = None):
    """Grafo de locais (Fase 0) para o mapa com fog of war no frontend.

    spec mapa-sublocais (R7): interiores NÃO aparecem no mapa-múndi —
    são expostos como "Locais daqui" no bloco `world` de /game/state.

    SPEC-210: com `game_id` devolve o mesmo formato, mas SÓ com os locais que
    o jogador descobriu (visitados + adjacentes, sem lore/perigo dos adjacentes).
    Sem `game_id` é o grafo global estático (CLI/smoke/legado).
    """
    if game_id:
        from services.map_view import legacy_filtered_map

        state = api_core._load_unlocked_or_locked(api_core._resolve_save_file(game_id), game_id)
        if not state:
            raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
        return legacy_filtered_map(state)
    data = dict(load_json_data("world_map.json") or {})
    data["locations"] = [loc for loc in data.get("locations", []) if loc.get("kind") != "interior"]
    return data


@router.get("/game/state")
def get_current_state(game_id: str | None = None):
    """
    Carrega o jogo. Se game_id for passado, carrega aquele especifico.
    Caso contrario, carrega o ultimo modificado.
    """
    # A lógica de carregar arquivo especifico deve ser implementada no persistence futuramente
    # Por enquanto, load_game_state carrega o mais recente se não passarmos nada
    # Se você implementou o load_game_state(specific_file), usaria aqui

    file_to_load = None
    file_to_load = api_core._resolve_save_file(game_id)

    state = api_core._load_unlocked_or_locked(file_to_load, game_id)

    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return format_response(state)


class CombatPreviewRequest(BaseModel):
    """SPEC-334 R4: pré-visualização de uma jogada. Puro: sem LLM e sem tocar o save."""

    model_config = {"extra": "forbid"}
    game_id: str | None = None
    card_id: str | None = Field(default=None, max_length=128)
    target_id: str = Field(max_length=128)


@router.post("/game/combat/preview")
def combat_preview(req: CombatPreviewRequest, response: Response):
    """Chance de acerto (2d10 exato), faixa de dano e ferimento provável do seu lado.
    Nunca expõe resistência/imunidade do alvo. Não grava nada."""
    from services import combat_preview as _preview

    state = api_core.load_game_state(api_core._resolve_save_file(req.game_id))
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    if not (state.get("combat") or {}).get("active"):
        raise HTTPException(
            409, detail={"code": "preview_no_combat", "message": "Não há conflito em andamento."}
        )
    try:
        result = _preview.preview(state, req.card_id, req.target_id)
    except ValueError as exc:
        code = str(exc)
        if code not in (
            "card_unknown",
            "card_not_in_hand",
            "card_not_active",
            "target_unknown",
            "not_offensive",
        ):
            raise
        raise HTTPException(
            409,
            detail={
                "code": "preview_invalid",
                "invalid_reason": code,
                "message": "Essa jogada não tem prévia (carta ou alvo inválido).",
            },
        ) from exc
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get("/data/cards/glossario")
def cards_glossary(response: Response):
    """SPEC-334: glossário de palavras-chave (tooltip do front); estático e cacheável."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    return load_json_data("cards/_glossario.json") or {}


@router.get("/game/codex")
def get_player_codex(game_id: str | None = None):
    """Codex do jogador (Fase 3.2) — locais/fações/personagens/criaturas/segredos
    já registrados no save. On-demand (fora do GameResponse) para não inchar o turno."""
    file_to_load = api_core._resolve_save_file(game_id)
    state = api_core.load_game_state(file_to_load)

    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    return player_codex(state)


@router.get("/game/codex/dossiers")
def get_codex_dossiers(response: Response, game_id: str | None = None):
    """SPEC-211 — dossiês vivos (NPC/local/facção/segredo/crônica + bestiário).
    Projeção somente leitura sobre o save, sobre a projeção player-facing da
    SPEC-206 (fail-closed). `GET /game/codex` segue inalterado."""
    from services.dossier_visibility import DossiersResponseModel
    from services.dossiers import build_dossiers

    file_to_load = api_core._resolve_save_file(game_id)
    state = api_core.load_game_state(file_to_load)
    if not state:
        raise HTTPException(status_code=404, detail="Nenhum jogo salvo encontrado.")
    response.headers["Cache-Control"] = "private, no-store"
    # exclude_unset: chave acima do tier (R6) fica AUSENTE do JSON, nunca `null`.
    return DossiersResponseModel.model_validate(build_dossiers(state)).model_dump(
        exclude_unset=True
    )


@router.get("/game/history")
def game_history(game_id: str, cursor: str | None = None, limit: int = 50):
    state = api_core.load_game_state(api_core._resolve_save_file(game_id))
    if not state:
        raise HTTPException(404, "Jogo não encontrado.")
    from services.presentation_history import history_page

    try:
        page = history_page(state, cursor=cursor, limit=limit)
        # Enrichment must never mutate a presentation_history row held by the
        # loaded GameState, even transiently.
        page["entries"] = [dict(entry) for entry in page["entries"]]
    except (ValueError, TypeError) as exc:
        raise HTTPException(409, "history_cursor_stale") from exc
    from services.faction_display import conceal_for

    page["entries"] = conceal_for(state, page["entries"])  # SPEC-293 R3
    # Financial data is an optional read projection. A failed query must never
    # hide the narrative or invent zero spend.
    if api_core._database_profile() and page["entries"]:
        try:
            from infrastructure.account_read_model import PostgresAccountReader
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            reader = PostgresAccountReader(get_runtime().game_store.pool)
            costs = reader.history_costs(current_principal(), uuid.UUID(game_id), page["entries"])
            for entry in page["entries"]:
                if entry.get("role") == "narrator":
                    entry.update(
                        costs.get(
                            entry["id"],
                            {
                                "cost_milli": None,
                                "technical_cost_usd": None,
                                "technical_cost_basis": None,
                                "technical_cost_exact": False,
                            },
                        )
                    )
        except Exception:
            for entry in page["entries"]:
                if entry.get("role") == "narrator":
                    entry["cost_milli"] = None
                    entry["technical_cost_usd"] = None
                    entry["technical_cost_basis"] = None
                    entry["technical_cost_exact"] = False
    return page
