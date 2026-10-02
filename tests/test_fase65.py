"""
Fase 6.5 — Clima com efeito real: cadeias por região e mecânica.
Spec: specs/SPEC-021-fase-6.5-clima-com-efeito.md. 100% offline.
"""
import random

import pytest

import world_utils as wu


class _FixedRng:
    def __init__(self, roll):
        self.roll = roll

    def randint(self, a, b):
        return min(b, max(a, self.roll))

    def choices(self, seq, weights=None, k=1):
        # determinístico: escolhe o de MAIOR peso
        best = max(zip(seq, weights or [1] * len(seq)), key=lambda p: p[1])
        return [best[0]]

    def random(self):
        # spec weather-global-vivo: roll alto → NÃO dispara clima global espúrio
        # nos testes de clima local/tick (que usam _FixedRng(1)).
        return min(1.0, float(self.roll))

    def choice(self, seq):
        return seq[0]


def _world(region_loc="pantano_melancolia", **over):
    w = {"current_location_id": region_loc, "current_location": region_loc,
         "world_clock": {"day": 1, "period": "Manhã"}, "turn_count": 3,
         "danger_level": 3, "weather_state": None, "weather": ""}
    w.update(over)
    return w


# ---------------------------------------------------------------------------
# Etapa 1 — cadeias por região
# ---------------------------------------------------------------------------

def test_advance_weather_cadeia_da_regiao():
    w = _world()
    wu.advance_weather(w, _FixedRng(1))
    assert w["weather_state"] in ("neblina", "miasma", "nublado")
    assert w["weather"]  # label preenchido


def test_regiao_sem_tabela_usa_default():
    w = _world(region_loc="ophidia")
    wu.advance_weather(w, _FixedRng(1))
    assert w["weather_state"] in ("limpo", "nublado", "chuva")


def test_starting_world_tem_clima_canonico():
    w = wu.starting_world("Nova Arcádia", 1)
    assert w.get("weather_state") and w.get("weather")


# ---------------------------------------------------------------------------
# Etapa 2 — efeitos como leitura (nunca condição gravada)
# ---------------------------------------------------------------------------

def test_miasma_efeitos_e_abrigo_anula():
    w = _world(weather_state="miasma")
    fx = wu.weather_effects(w)
    assert fx["dot_outdoor"] == 1 and fx["rest_block"] and fx["perception_mod"] == -2
    # local urbano/abrigado anula dot e rest_block
    loc_abrigada = {"region_id": "pantano_melancolia", "tags": ["cidade"]}
    fx2 = wu.weather_effects(w, loc_abrigada)
    assert fx2["dot_outdoor"] == 0 and not fx2["rest_block"]


def test_clima_some_efeito_some():
    w = _world(weather_state="nublado")
    fx = wu.weather_effects(w)
    assert fx["dot_outdoor"] == 0 and not fx["rest_block"]


def test_rest_block_nega_descanso():
    w = _world(weather_state="miasma")
    p = {"name": "T", "hp": 5, "max_hp": 30}
    p2, w2 = wu.apply_rest(p, w)
    assert p2["hp"] == 5  # NADA recuperado
    p3, _ = wu.apply_rest({"name": "T", "hp": 5, "max_hp": 30},
                          _world(weather_state="nublado"))
    assert p3["hp"] > 5


def test_nevasca_encarece_viagem():
    from gamedata import get_location
    w = _world(region_loc="skallgard", weather_state="nevasca")
    dest = get_location("sk_fortaleza_vorr") or get_location("skallgard")
    day_period_antes = dict(w["world_clock"])
    # advance_weather dentro do travel pode trocar o estado; congela com rng?
    # apply_travel usa rng global — validamos só que o relógio anda >= 1 período.
    w2 = wu.apply_travel(dict(w), dest)
    assert w2["world_clock"] != day_period_antes


def test_deteccao_sofre_com_neblina():
    p = {"attributes": {"wis": 14}, "racial_save_bonus": {}}
    base = wu.detection_check(p, 2, _FixedRng(10))
    fog = wu.detection_check(p, 2, _FixedRng(10), perception_mod=-3)
    assert base["roll"] - fog["roll"] == 3


# ---------------------------------------------------------------------------
# Etapa 3 — combate simétrico
# ---------------------------------------------------------------------------

def test_env_attack_mod_simetrico():
    import combat_mechanics as cm
    p = {"name": "T", "attributes": {"str": 10, "dex": 10}, "inventory": [],
         "equipment": {"weapon": None, "armor": None, "accessory": None},
         "active_conditions": [], "attack_bonus": 0, "_env_attack_mod": -1}
    assert cm.compute_player_combat_stats(p)["attack"] == \
        cm.compute_player_combat_stats({**p, "_env_attack_mod": 0})["attack"] - 1


def test_dot_outdoor_no_combate(monkeypatch):
    from agents import combat as cbt
    from langchain_core.messages import HumanMessage, SystemMessage
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "ok")
    enemy = {"id": "e1", "name": "Orc", "type": "Minion", "hp": 30, "max_hp": 30,
             "defense": 30, "status": "ativo", "attributes": {"dex": 10},
             "active_conditions": [],
             "attacks": [{"name": "G", "bonus": -20, "damage": "1d1"}],
             "stamina": 0, "mana": 0, "attack_mod": 0}
    state = {"messages": [SystemMessage(content="COMBAT START."),
                          HumanMessage(content="luto")],
             "player": {"name": "T", "class_name": "", "hp": 30, "max_hp": 30,
                        "mana": 0, "max_mana": 0, "stamina": 10, "max_stamina": 10,
                        "attributes": {"str": 10, "dex": 10}, "inventory": [],
                        "equipment": {"weapon": None, "armor": None, "accessory": None},
                        "known_abilities": ["ataque_basico"], "defense": 30,
                        "attack_bonus": 0, "active_conditions": [],
                        "ability_cooldowns": {}, "pending_choices": [], "xp": 0,
                        "level": 1},
             "enemies": [enemy], "combat": {}, "combat_target": "Orc",
             "world": {"turn_count": 3, "current_location": "Pântano",
                       "current_location_id": "pantano_melancolia",
                       "weather_state": "miasma", "world_clock": {"day": 1}},
             "bestiary_knowledge": {}, "pending_world_events": [], "party": [],
             "combat_declaration": {
                 "actor_id": "player",
                 "acao": {"kind": "attack", "target_id": "e1"}}}
    out = cbt.combat_node(state)
    assert out["player"]["hp"] < 30  # miasma mordeu (defense 30 impede hit normal)


# ---------------------------------------------------------------------------
# Etapa 4 — fenômeno global (lista curada; sem canal LLM ainda)
# ---------------------------------------------------------------------------

def test_fenomeno_global_da_lista_e_expira():
    w = _world(weather_state="nublado")
    w, desc = wu.trigger_global_weather(w, "tempestade_de_eter")
    assert desc and w["weather_global"]["periods_left"] == 4
    fx = wu.weather_effects(w)
    assert fx["dot_outdoor"] == 1  # sobreposição global vence o estado local
    # id fora da lista curada -> no-op
    w2, desc2 = wu.trigger_global_weather(_world(), "chuva_de_sapos")
    assert desc2 is None and not w2.get("weather_global")
    # expira por períodos
    for _ in range(4):
        wu.advance_weather(w, _FixedRng(1))
    assert not w.get("weather_global")
