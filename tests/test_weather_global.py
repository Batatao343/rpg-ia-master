"""Suíte da spec weather-global-vivo — trigger determinístico de fenômenos globais.

Offline/determinístico. Ver specs/weather-global-vivo.md.
"""
import random

import world_utils as wu


class _Rng:
    """rng determinístico: random() devolve um valor fixo; choice pega o 1º."""
    def __init__(self, r=0.0):
        self._r = r

    def random(self):
        return self._r

    def choice(self, seq):
        return seq[0]

    def choices(self, population, weights=None, k=1):
        return [population[0]]


def _world(danger=1, loc="nova_arcadia"):
    return {"current_location_id": loc, "danger_level": danger,
            "weather_state": None, "weather_global": None}


def test_inicia_com_rng_favoravel():
    w = _world()
    wu.advance_weather(w, _Rng(0.0))          # random()=0 < chance → inicia
    g = w.get("weather_global")
    assert g and g.get("id") and int(g.get("periods_left", 0)) > 0


def test_nao_inicia_com_rng_alto():
    w = _world()
    wu.advance_weather(w, _Rng(0.99))         # random()=0.99 ≥ chance → nada
    assert not w.get("weather_global")


def test_nao_sobrepoe_ativo():
    w = _world()
    w["weather_global"] = {"id": "tempestade_de_eter", "periods_left": 3}
    wu.advance_weather(w, _Rng(0.0))          # ativo → só decrementa, não troca
    g = w["weather_global"]
    assert g["id"] == "tempestade_de_eter"
    assert g["periods_left"] == 2             # ticou


def test_chance_escala_com_danger():
    # amostra: quantas vezes inicia em N períodos, danger baixo vs alto (mesma seed)
    def inicios(danger):
        n = 0
        for seed in range(200):
            w = _world(danger=danger)
            wu.advance_weather(w, random.Random(seed))
            if w.get("weather_global"):
                n += 1
        return n
    assert inicios(4) > inicios(1)


def test_evento_afeta_weather_effects():
    w = _world()
    wu.trigger_global_weather(w, "tempestade_de_eter")
    fx = wu.weather_effects(w)
    assert "Éter" in fx["label"] or "ter" in fx["label"]
    # tempestade_de_eter tem combat_attack_mod/dot_outdoor/perception_mod não-zero
    assert (fx["combat_attack_mod"] or fx["dot_outdoor"] or fx["perception_mod"])


def test_expira_e_pode_reiniciar():
    w = _world()
    w["weather_global"] = {"id": "noite_sem_estrelas", "periods_left": 1}
    wu.advance_weather(w, _Rng(0.99))         # tick → 0 → None (rng alto não reinicia)
    assert not w.get("weather_global")


def test_maybe_start_isolada():
    w = _world(danger=1)
    desc = wu.maybe_start_global_weather(w, _Rng(0.0))
    assert desc and w.get("weather_global")
    # com evento já ativo, retorna None (R2)
    assert wu.maybe_start_global_weather(w, _Rng(0.0)) is None


def test_api_expoe_rotulo_global_efetivo():
    from api import _world_block
    w = _world()
    wu.trigger_global_weather(w, "tempestade_de_eter")

    block = _world_block(w)

    assert "ter" in block["weather"]
    assert block["weather_global"]["id"] == "tempestade_de_eter"
