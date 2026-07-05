"""
Testes da Fase 2 — mundo vivo: fações com objetivos próprios (offline, sem API key).
Núcleo determinístico: seed, avanço por tempo, backfill, persistência, integração no grafo.
"""
from langchain_core.messages import HumanMessage

import gamedata
import world_utils as wu


# --------------------------------------------------------------------------
# Seed / dados
# --------------------------------------------------------------------------
def test_factions_data_loads():
    assert gamedata.FACTIONS, "factions.json deve carregar"
    assert "legiao_ferro" in gamedata.FACTIONS


def test_seed_factions_fresh_copy():
    a = gamedata.seed_factions()
    b = gamedata.seed_factions()
    assert isinstance(a, list) and len(a) >= 4
    # cada facção começa zerada e não concluída
    for f in a:
        assert f["progress"] == 0 and f["completed"] is False
        assert f["pace"] >= 1 and f["disposition"] in ("hostil", "neutro", "aliado")
    # cópias independentes (mutar uma não afeta a outra)
    a[0]["progress"] = 99
    assert b[0]["progress"] == 0


# --------------------------------------------------------------------------
# advance_factions
# --------------------------------------------------------------------------
def test_advance_factions_progresses_by_pace():
    factions = [{"id": "x", "name": "X", "goal": "g", "progress": 0,
                 "pace": 5, "disposition": "neutro", "completed": False}]
    out, events = wu.advance_factions(factions, periods=2)
    assert out[0]["progress"] == 10  # 5 * 2
    assert events == []


def test_advance_factions_zero_periods_noop():
    factions = [{"id": "x", "name": "X", "progress": 7, "pace": 5, "completed": False}]
    out, events = wu.advance_factions(factions, periods=0)
    assert out[0]["progress"] == 7 and events == []


def test_advance_factions_clamps_and_completes():
    factions = [{"id": "x", "name": "Culto", "goal": "despertar", "progress": 96,
                 "pace": 5, "disposition": "hostil", "completed": False}]
    out, events = wu.advance_factions(factions, periods=2)
    assert out[0]["progress"] == 100
    assert out[0]["completed"] is True
    assert len(events) == 1
    assert events[0]["id"] == "x" and events[0]["disposition"] == "hostil"


def test_completed_faction_does_not_readvance():
    factions = [{"id": "x", "name": "X", "progress": 100, "pace": 5, "completed": True}]
    out, events = wu.advance_factions(factions, periods=3)
    assert out[0]["progress"] == 100
    assert events == []  # já concluída → sem evento duplicado


def test_ensure_factions_backfills_empty():
    out = wu.ensure_factions([])
    assert out and all("progress" in f and "completed" in f for f in out)


def test_ensure_factions_backfills_missing_fields():
    out = wu.ensure_factions([{"id": "y", "name": "Y", "goal": "g"}])
    f = out[0]
    assert f["progress"] == 0 and f["pace"] >= 1
    assert f["disposition"] == "neutro" and f["completed"] is False


# --------------------------------------------------------------------------
# Persistência (round-trip)
# --------------------------------------------------------------------------
def test_factions_persist_round_trip(tmp_path, monkeypatch):
    import os
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    state = {
        "game_id": "fase2_persist",
        "narrative_summary": "", "archivist_last_run": 0, "chronicle": [],
        "messages": [], "player": {}, "world": {},
        "factions": gamedata.seed_factions(),
        "party": [], "enemies": [], "npcs": {}, "campaign_plan": {},
    }
    state["factions"][0]["progress"] = 42
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(os.path.join(str(tmp_path), "fase2_persist.json"))
    assert loaded["factions"][0]["progress"] == 42


# --------------------------------------------------------------------------
# Integração no grafo (modo simulado): descanso avança as fações
# --------------------------------------------------------------------------
def _state_for_graph(user_text: str):
    return {
        "game_id": "fase2_test",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "chronicle": [],
        "messages": [HumanMessage(content=user_text)],
        "next": "storyteller",
        "player": {
            "name": "T", "class_name": "Guerreiro", "race": "Humano",
            "hp": 10, "max_hp": 30, "mana": 5, "max_mana": 5,
            "stamina": 5, "max_stamina": 10, "gold": 10, "level": 1, "xp": 0,
            "alignment": "Neutro",
            "attributes": {"str": 12, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "inventory": [], "known_abilities": [], "defense": 10,
            "attack_bonus": 0, "active_conditions": [],
        },
        "world": wu.starting_world("Nova Arcádia", 1),
        "factions": gamedata.seed_factions(),
        "campaign_plan": {}, "needs_replan": False,
        "enemies": [], "party": [], "npcs": {}, "active_npc_name": None,
        "combat_target": None, "loot_source": None,
    }


def test_graph_rest_advances_factions():
    from main import app
    result = app.invoke(_state_for_graph("vou descansar e acampar aqui"))
    factions = result.get("factions") or []
    assert factions, "estado deve conter fações após o turno"
    # descanso = 2 períodos → ao menos uma facção progrediu além de 0
    assert any(f["progress"] > 0 for f in factions), "descanso deve avançar fações"


# --------------------------------------------------------------------------
# Reputação por ação do jogador (IA identifica, Python resolve)
# --------------------------------------------------------------------------
def _reps():
    return [
        {"id": "selo_palido", "name": "Ordem", "progress": 0, "pace": 4,
         "disposition": "neutro", "reputation": 0, "completed": False},
        {"id": "culto_clareira", "name": "Culto", "progress": 0, "pace": 5,
         "disposition": "hostil", "reputation": 0, "completed": False},
    ]


def test_apply_reputation_increments_and_clamps():
    out, ev = wu.apply_reputation(_reps(), "selo_palido", "ajudou")
    f = next(x for x in out if x["id"] == "selo_palido")
    assert f["reputation"] == wu.REP_STEP
    assert ev and ev["delta"] == wu.REP_STEP and ev["direction"] == "ajudou"
    # outras fações intactas
    assert next(x for x in out if x["id"] == "culto_clareira")["reputation"] == 0

    # clamp no teto e no piso
    high = [{"id": "selo_palido", "name": "O", "reputation": 95, "disposition": "aliado"}]
    out_h, _ = wu.apply_reputation(high, "selo_palido", "ajudou")
    assert out_h[0]["reputation"] == wu.REP_MAX
    low = [{"id": "selo_palido", "name": "O", "reputation": -95, "disposition": "hostil"}]
    out_l, _ = wu.apply_reputation(low, "selo_palido", "prejudicou")
    assert out_l[0]["reputation"] == wu.REP_MIN


def test_apply_reputation_flips_disposition():
    # de neutro a aliado ao cruzar +40
    base = [{"id": "selo_palido", "name": "O", "reputation": 36, "disposition": "neutro"}]
    out, _ = wu.apply_reputation(base, "selo_palido", "ajudou")  # 36 + 12 = 48 >= 40
    assert out[0]["disposition"] == "aliado"
    # de neutro a hostil ao cruzar -40
    base2 = [{"id": "selo_palido", "name": "O", "reputation": -32, "disposition": "neutro"}]
    out2, _ = wu.apply_reputation(base2, "selo_palido", "prejudicou")  # -32 - 12 = -44 <= -40
    assert out2[0]["disposition"] == "hostil"


def test_apply_reputation_unknown_id_noop():
    reps = _reps()
    out, ev = wu.apply_reputation(reps, "nao_existe", "ajudou")
    assert ev is None
    assert all(f["reputation"] == 0 for f in out)


def test_apply_reputation_invalid_direction_noop():
    out, ev = wu.apply_reputation(_reps(), "selo_palido", "olhou de lado")
    assert ev is None
    assert all(f["reputation"] == 0 for f in out)


def test_graph_help_faction_changes_reputation():
    from main import app
    # jogador precisa CONHECER a fação para poder agir sobre ela (não-onisciência)
    st = _state_for_graph("ajudo a Legião de Ferro na sua causa")
    st["faction_intel"] = {"legiao_ferro": {"known": True, "knows_goal": True}}
    result = app.invoke(st)
    factions = result.get("factions") or []
    alvo = next((f for f in factions if f["id"] == "legiao_ferro"), None)
    assert alvo is not None
    assert alvo["reputation"] > 0, "ajudar uma fação conhecida deve elevar sua reputação"


# --------------------------------------------------------------------------
# Não-onisciência: conhecimento de fação em camadas (só via NPC)
# --------------------------------------------------------------------------
def test_faction_intel_starts_empty():
    assert wu.ensure_faction_intel(None) == {}
    assert wu.ensure_faction_intel({}) == {}


def test_apply_faction_reveal_layers():
    facs = gamedata.seed_factions()
    # existência: só known
    intel = wu.apply_faction_reveal({}, facs, "legiao_ferro", "existencia", turn=1)
    assert intel["legiao_ferro"]["known"] is True
    assert intel["legiao_ferro"].get("knows_goal") is False
    # objetivo: known + knows_goal
    intel = wu.apply_faction_reveal(intel, facs, "legiao_ferro", "objetivo", turn=2)
    assert intel["legiao_ferro"]["knows_goal"] is True
    # progresso: congela snapshot do progress atual + turno
    facs2 = [dict(f, progress=37) if f["id"] == "legiao_ferro" else f for f in facs]
    intel = wu.apply_faction_reveal(intel, facs2, "legiao_ferro", "progresso", turn=5)
    assert intel["legiao_ferro"]["progress_seen"] == 37
    assert intel["legiao_ferro"]["intel_turn"] == 5


def test_apply_faction_reveal_unknown_id_noop():
    facs = gamedata.seed_factions()
    intel = wu.apply_faction_reveal({}, facs, "nao_existe", "objetivo", turn=1)
    assert intel == {}


def test_factions_block_hides_unknown_and_uses_snapshot():
    from api import _factions_block
    facs = [{"id": "selo_palido", "name": "Ordem", "goal": "centralizar", "region": "Arc",
             "progress": 80, "disposition": "neutro", "reputation": 0, "completed": False}]
    # sem intel → nada aparece
    assert _factions_block(facs, {}, turn=3) == []
    # conhece existência mas não o plano → goal vazio, progress None
    intel = {"selo_palido": {"known": True, "knows_goal": False}}
    out = _factions_block(facs, intel, turn=3)
    assert len(out) == 1 and out[0]["goal"] == "" and out[0]["knows_goal"] is False
    assert out[0]["progress"] is None
    # snapshot de progresso defasado → usa o snapshot (não o ao vivo 80) e marca stale
    intel = {"selo_palido": {"known": True, "knows_goal": True, "progress_seen": 20, "intel_turn": 1}}
    out = _factions_block(facs, intel, turn=9)
    assert out[0]["progress"] == 20 and out[0]["intel_stale"] is True


def test_factions_block_hides_defeated():
    from api import _factions_block
    facs = [{"id": "x", "name": "X", "defeated": True}]
    intel = {"x": {"known": True, "knows_goal": True}}
    assert _factions_block(facs, intel, turn=1) == []


# --------------------------------------------------------------------------
# Etapa B: ascensão — concluir objetivo muda o mundo (determinístico)
# --------------------------------------------------------------------------
def _complete_one(fid, world=None, intel=None):
    """Leva a fação `fid` à conclusão e resolve a ascensão. Retorna (factions, world, note, events)."""
    facs = [dict(f, progress=99) if f["id"] == fid else f for f in gamedata.seed_factions()]
    facs, events = wu.advance_factions(facs, 1)  # >=100 → completa
    facs, world, note = wu.resolve_faction_completions(facs, world or {}, events, intel or {})
    return facs, world, note, events


def test_ascension_dominar_local():
    _, world, _, _ = _complete_one("legiao_ferro")
    assert world.get("controlled", {}).get("na_anel_lama") == "legiao_ferro"


def test_ascension_expandir_regiao():
    facs, _, _, _ = _complete_one("mao_sombria")
    f = next(x for x in facs if x["id"] == "mao_sombria")
    assert f["region"] == "Brekmar"
    assert f["progress"] == 0 and f["completed"] is False  # cadeia: volta a evoluir
    assert "sindicato" in f["goal"].lower()  # next_goal aplicado


def test_ascension_elevar_perigo_clamps():
    _, world, _, _ = _complete_one("druidas_renegados")
    assert world.get("danger_overrides", {}).get("pantano_melancolia") == 4  # base 3 + 1 (teto 4)


def test_ascension_invocar_entidade():
    _, world, _, _ = _complete_one("filhos_chama_azul")
    assert world.get("looming_threat")
    assert "na_anel_dourado" in world.get("danger_overrides", {})


def test_ascension_eliminar_faccao():
    facs, _, _, _ = _complete_one("ultimos_anoes_reino")
    alvo = next(x for x in facs if x["id"] == "goblins_mineiros")
    assert alvo.get("defeated") is True


def test_advance_skips_defeated():
    facs = [{"id": "x", "name": "X", "progress": 50, "pace": 5, "defeated": True, "completed": False}]
    out, events = wu.advance_factions(facs, 2)
    assert out[0]["progress"] == 50 and events == []


def test_completion_note_names_only_known():
    # desconhecida → consequência sem nome
    _, _, note_unknown, _ = _complete_one("legiao_ferro", intel={})
    assert note_unknown and "A Legião de Ferro" not in note_unknown
    # conhecida → narrador nomeia
    _, _, note_known, _ = _complete_one("legiao_ferro", intel={"legiao_ferro": {"known": True}})
    assert "A Legião de Ferro" in note_known


# --------------------------------------------------------------------------
# Encontros: o mundo perigoso/dominado/ameaçado vira combate (determinístico)
# --------------------------------------------------------------------------
def test_encounter_high_danger_triggers():
    world = {"current_location_id": "pr_ruinas_assombradas"}  # perigo 4 no mapa
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10)
    assert enc and enc["reason"] == "high_danger"


def test_encounter_looming_threat_triggers():
    world = {"current_location_id": "floresta_sussurros",  # perigo 3
             "looming_threat": "Algo desperta sob a floresta."}
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10)
    assert enc and enc["reason"] == "looming_threat"


def test_encounter_hostile_controlled_triggers():
    world = {"current_location_id": "pradaria_ruinas",  # perigo 2: só o domínio dispara
             "controlled": {"pradaria_ruinas": "bandos_nomades"}}  # facção hostil
    enc = wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10)
    assert enc and enc["reason"] == "controlled"


def test_encounter_safe_zone_no_trigger():
    world = {"current_location_id": "pradaria_ruinas"}  # perigo 2, sem ameaça/domínio
    assert wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10) is None


def test_encounter_cooldown_blocks():
    world = {"current_location_id": "pr_ruinas_assombradas", "last_encounter_turn": 9}
    assert wu.check_encounter(world, gamedata.seed_factions(), {}, turn=10) is None  # 1 < cooldown 2


def test_encounter_hint_respects_intel():
    world = {"current_location_id": "pradaria_ruinas",
             "controlled": {"pradaria_ruinas": "bandos_nomades"}}
    facs = gamedata.seed_factions()
    # desconhecida → não nomeia a facção
    enc = wu.check_encounter(world, facs, {}, turn=10)
    assert "Bandos Nômades" not in enc["hint"]
    # conhecida → nomeia
    enc2 = wu.check_encounter(world, facs, {"bandos_nomades": {"known": True}}, turn=10)
    assert "Bandos Nômades" in enc2["hint"]


def test_graph_rest_in_danger_triggers_combat():
    from main import app
    st = _state_for_graph("vou descansar e acampar aqui")
    st["world"]["current_location_id"] = "pr_ruinas_assombradas"
    st["world"]["current_location"] = "Ruínas Assombradas"
    st["world"]["danger_level"] = 4
    import random
    random.seed(3)  # Fase 6.4: tipo de encontro é roleta — semeia p/ determinismo
    result = app.invoke(st)
    enemies = result.get("enemies") or []
    world_out = result.get("world") or {}
    # Fase 6.4: perigo 4 DISPARA encontro, mas nem todo encontro é combate
    # (armadilha/rastro/social também contam). O que NÃO pode: nada acontecer.
    encounter_fired = bool(enemies) or         int(world_out.get("last_encounter_turn", -99)) >= 0
    assert encounter_fired, "descansar em perigo 4 deve disparar um encontro (combate OU armadilha/rastro/social)"


def test_npc_reveals_faction_to_player():
    from langchain_core.messages import HumanMessage
    from agents.npc import npc_actor_node
    state = {
        "game_id": "intel_test",
        "active_npc_name": "Guarda Bran",
        "npcs": {"Guarda Bran": {"name": "Guarda Bran", "role": "Guarda", "persona": "rude",
                                  "location": "Portão", "relationship": 5, "memory": []}},
        "factions": gamedata.seed_factions(),
        "faction_intel": {},
        "world": {"turn_count": 4, "current_location": "Portão"},
        "messages": [HumanMessage(content="pergunto ao guarda sobre a Legião de Ferro")],
    }
    out = npc_actor_node(state)
    intel = out.get("faction_intel") or {}
    assert intel.get("legiao_ferro", {}).get("known") is True
