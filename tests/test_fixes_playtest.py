"""Suíte da spec fix-playtest-achados — 5 correções achadas no playtest real.
Offline (MockLLM). Spec: specs/fix-playtest-achados.md."""
from langchain_core.messages import AIMessage, HumanMessage


# --- R1 — beats em pt-BR -----------------------------------------------------

def test_r1_campaign_beats_field_pt():
    from agents.campaign_manager import CampaignPlanModel
    desc = CampaignPlanModel.model_fields["beats"].description or ""
    assert "pt-br" in desc.lower() or "português" in desc.lower()


# --- R3 — quester objetivo curto --------------------------------------------

def test_r3_quester_acao_curta():
    from playtest.profiles import Quester
    import random
    beat_longo = ("O amanhecer pinta o céu de laranja sobre as chaminés do Distrito "
                  "Industrial. Você observa operários e patrulhas da Legião de Ferro "
                  "enquanto um grupo carrega um barril lacrado para um depósito. " * 3)
    st = {"campaign_plan": {"beats": [{"description": beat_longo}], "current_step": 0},
          "quests": []}
    for seed in range(8):
        acao = Quester().next_action(st, random.Random(seed))
        assert len(acao) <= 160, f"ação longa ({len(acao)}): {acao[:80]}"


# --- R2 — NPC anti-repetição ------------------------------------------------

def test_r2_npc_prompt_anti_repeticao(monkeypatch):
    import agents.npc as npc_mod
    from gamedata import seed_factions

    capturado = {}

    class _Rec:
        def with_structured_output(self, model, *a, **k):
            self._model = model
            return self

        def with_retry(self, *a, **k):
            return self

        def invoke(self, msgs):
            capturado["sys"] = str(getattr(msgs[0], "content", ""))
            from mock_llm import MockLLM
            return MockLLM().with_structured_output(self._model).invoke(msgs)

    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: _Rec())
    fala_antiga = '**Guarda Bran:** "A região está tensa, amigo."\n*(olha em volta)*'
    state = {
        "game_id": "r2", "active_npc_name": "Guarda Bran",
        "npcs": {"Guarda Bran": {"name": "Guarda Bran", "role": "Guarda", "persona": "rude",
                                 "location": "Portão", "relationship": 5, "memory": []}},
        "factions": seed_factions(), "faction_intel": {},
        "world": {"turn_count": 4, "current_location": "Portão"},
        "messages": [AIMessage(content=fala_antiga),
                     HumanMessage(content="pergunto de novo sobre a região")],
    }
    npc_mod.npc_actor_node(state)
    sys = capturado.get("sys", "")
    assert "A região está tensa" in sys, "última fala do NPC não entrou no prompt"
    assert "NÃO REPITA" in sys, "regra anti-repetição ausente do prompt"


# --- R4 — gate de game_over -------------------------------------------------

def test_r4_grafo_gate_game_over():
    from main import app
    from playtest.runner import _build_initial_state
    st = _build_initial_state("gate", 0)
    st["game_over"] = True
    n_msgs = len(st["messages"])
    turn0 = (st.get("world") or {}).get("turn_count", 0)
    out = app.invoke(st)
    assert len(out["messages"]) == n_msgs          # nenhuma narração nova
    assert (out.get("world") or {}).get("turn_count", 0) == turn0  # relógio parado


def test_r4_invariante_acts_after_game_over():
    from playtest import invariants as inv
    prev = {"game_over": True, "world": {"turn_count": 5}}
    cur = {"game_over": True, "world": {"turn_count": 6}}
    ids = {v.check_id for v in inv.check_all(cur, prev, turn=6)}
    assert "lifecycle.acts_after_game_over" in ids


# --- R5 — perigo efetivo por nível + apex -----------------------------------

def test_r5_eff_danger_escala_por_nivel():
    from world_utils import forced_encounter_danger
    loc = {"tags": ["pântano"]}
    assert forced_encounter_danger(loc, 4, 1) == 2   # (1+3)//2
    assert forced_encounter_danger(loc, 4, 3) == 3
    assert forced_encounter_danger(loc, 4, 5) == 4
    assert forced_encounter_danger(loc, 4, 9) == 4   # nunca acima do real
    assert forced_encounter_danger(loc, 2, 1) == 2   # eff nunca > danger real


def test_r5_apex_nao_escala():
    from world_utils import forced_encounter_danger
    apex = {"tags": ["caverna", "apex"]}
    assert forced_encounter_danger(apex, 4, 1) == 4  # proibido: perigo cheio


def test_r5_zonas_apex_no_mapa():
    from gamedata import get_location
    for lid in ("cn_o_trono", "ma_boca", "dz_borda_do_vazio",
                "sx_profundezas", "sk_fortaleza_vorr"):
        assert "apex" in (get_location(lid).get("tags") or []), lid


def test_r5_forcado_carimba_eff_danger():
    import gamedata
    from world_utils import check_encounter
    # local danger>=4 não-apex → encontro forçado carimba eff escalado
    loc = next(l for l in gamedata._LOCATIONS_BY_ID.values()
               if l.get("danger", 0) >= 4 and "apex" not in (l.get("tags") or []))
    world = {"current_location_id": loc["id"], "danger_level": loc["danger"],
             "last_encounter_turn": -99}
    check_encounter(world, [], {}, turn=10, player_level=1)
    assert world.get("encounter_eff_danger") == 2   # nível-1 → (1+3)//2


# --- R5 (fuga) — jogador foge de verdade -------------------------------------

def test_fujao_foge_quando_em_combate():
    from playtest.profiles import Fujao
    import random
    st = {"combat": {"active": True}, "enemies": [{"status": "ativo", "hp": 5}]}
    for seed in range(5):
        acao = Fujao().next_action(st, random.Random(seed)).lower()
        assert any(k in acao for k in ("fujo", "recuo", "escapo", "corro"))


def _combat_player():
    return {"name": "Kael", "class_name": "Guerreiro", "hp": 30, "max_hp": 30,
            "stamina": 12, "max_stamina": 12, "mana": 0,
            "attributes": {"str": 16, "dex": 14, "con": 12},
            "inventory": [], "attack_bonus": 0, "known_abilities": ["ataque_basico"],
            "active_conditions": [], "ability_cooldowns": {}}


def _enemy(hp=12):
    return {"id": "goblin_1", "name": "Goblin 1", "hp": hp, "max_hp": hp, "defense": 11,
            "status": "ativo", "attributes": {"dex": 12, "con": 10},
            "attacks": [{"name": "Adaga", "bonus": 3, "damage": "1d4+1"}],
            "active_conditions": []}


def test_flee_encerra_combate_e_sobrevive():
    """R5: fuga do jogador ENCERRA o combate (antes o texto virava um ataque)."""
    import random
    import agents.combat as combat
    random.seed(2)
    state = {
        "game_id": "flee", "narrative_summary": "",
        "messages": [HumanMessage(content="fujo dessa luta e corro para longe daqui")],
        "player": _combat_player(), "enemies": [_enemy(hp=14)], "combat": {},
        "world": {"current_location": "Ermo", "current_location_id": "pantano_melancolia",
                  "turn_count": 3, "danger_level": 2},
        "party": [],
    }
    out = combat.combat_node(state)
    # combate encerrado (inimigos limpos / inativo)
    assert out.get("enemies") == [] or not out.get("combat", {}).get("active")
    # herói vivo, sem game_over, sem espólio (fuga não é vitória)
    assert not out.get("game_over")
    assert int(out["player"]["hp"]) > 0
    assert out.get("next") != "loot"
    # (a narração do FOGE só aparece no LLM real; o MockLLM devolve flavor enlatado
    # ignorando os logs — o smoke real confirma o texto.)
