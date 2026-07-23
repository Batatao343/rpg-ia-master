"""Suíte do orquestrador de turno do motor novo (spec conflito-13, Etapa 2).

Compõe Pré-Ação/Ação/Pós-Ação sobre os motores puros das specs 01-12, 100%
determinístico. rng fixo (min/max) para acerto/erro exatos."""

import gamedata
from services import conflict_turn as ct
from services import conflict_scene as cs


class _Rng:
    """rng determinístico por sequência de valores DISTINTOS — evita dupla acidental
    (que viraria Crítico pela regra do conflito-04) ao forçar acerto/erro."""
    def __init__(self, values):
        self.values = values
        self.i = 0

    def randint(self, a, b):
        v = self.values[self.i % len(self.values)]
        self.i += 1
        return v


def _hit():
    return _Rng([10, 8, 9, 7])     # totais altos, sem dupla → acerto limpo


def _miss():
    return _Rng([1, 3, 2, 4])      # totais baixos, sem dupla → erro limpo


def _combatant(name, corpo=2, agi=1, **over):
    espacos = gamedata.espacos_ferimento_para_corpo(corpo)
    c = {"id": name, "name": name,
         "virtudes": {"corpo": corpo, "agilidade": agi, "forca": 3, "mente": 1, "carisma": 1},
         "vitalidade": gamedata.vitalidade_para_corpo(corpo),
         "max_vitalidade": gamedata.vitalidade_para_corpo(corpo),
         "ferimento_espacos": espacos, "ferimentos": {"leve": [], "grave": [], "critico": []},
         "active_conditions": []}
    c.update(over)
    return c


def _scene_with(*ids):
    s = cs.new_scene()
    for i in ids:
        cs.place(s, i, distance_state="proximo")
    return s


# ==========================================================================
# Ataque básico
# ==========================================================================
def test_ataque_basico_acerta_e_aplica_dano():
    heroi, orc = _combatant("heroi"), _combatant("orc")
    scene = _scene_with("heroi", "orc")
    decl = {"actor_id": "heroi",
            "acao": {"kind": "attack", "target_id": "orc",
                     "params": {"formula": "2d6"}}}
    out = ct.resolve_turn(scene, {"heroi": heroi, "orc": orc}, decl, rng=_hit())
    assert out["attacks"] and out["attacks"][0]["acerto"] is True
    assert orc["vitalidade"] < orc["max_vitalidade"]      # tomou dano


def test_ataque_erra_com_rolagem_baixa():
    heroi, orc = _combatant("heroi"), _combatant("orc", agi=5)
    scene = _scene_with("heroi", "orc")
    decl = {"actor_id": "heroi", "acao": {"kind": "attack", "target_id": "orc"}}
    out = ct.resolve_turn(scene, {"heroi": heroi, "orc": orc}, decl, rng=_miss())
    assert out["attacks"][0]["acerto"] is False
    assert orc["vitalidade"] == orc["max_vitalidade"]     # intacto


# ==========================================================================
# Pré-Ação (manobra) + Ação (ataque) no mesmo turno
# ==========================================================================
def test_pre_acao_engajar_depois_ataca():
    heroi, orc = _combatant("heroi"), _combatant("orc")
    scene = _scene_with("heroi", "orc")
    decl = {"actor_id": "heroi",
            "pre_acao": {"kind": "maneuver", "maneuver": "engajar", "target_id": "orc"},
            "acao": {"kind": "attack", "target_id": "orc"}}
    out = ct.resolve_turn(scene, {"heroi": heroi, "orc": orc}, decl, rng=_hit())
    assert cs.is_engaged(scene, "heroi", "orc")
    assert out["attacks"][0]["acerto"] is True


# ==========================================================================
# Guarda impõe Desvantagem nos dois lados (conflito-06)
# ==========================================================================
def test_alvo_guardando_da_desvantagem_ao_atacante():
    heroi, orc = _combatant("heroi"), _combatant("orc")
    scene = _scene_with("heroi", "orc")
    cs.guard(scene, "orc")                                # orc Guardando
    decl = {"actor_id": "heroi", "acao": {"kind": "attack", "target_id": "orc"}}
    out = ct.resolve_turn(scene, {"heroi": heroi, "orc": orc}, decl, rng=_hit())
    # advantage do ataque reflete a Desvantagem da Guarda do alvo
    assert out["attacks"][0]["advantage"] <= 0


# ==========================================================================
# Ocultação: alvo escondido sem posição não pode ser mirado (conflito-06)
# ==========================================================================
def test_alvo_escondido_sem_posicao_nao_pode_ser_mirado():
    heroi, orc = _combatant("heroi"), _combatant("orc")
    scene = _scene_with("heroi", "orc")
    cs.hide(scene, "orc", source="fumaça", observers=["heroi"])
    decl = {"actor_id": "heroi", "acao": {"kind": "attack", "target_id": "orc"}}
    out = ct.resolve_turn(scene, {"heroi": heroi, "orc": orc}, decl, rng=_hit())
    assert not out["attacks"]                             # não rolou ataque
    assert any("não pode mirar" in log for log in out["logs"])


# ==========================================================================
# Morte: último Crítico dispara Estado Terminal (conflito-07)
# ==========================================================================
def test_ultimo_critico_marca_estado_terminal():
    heroi = _combatant("heroi", corpo=5)
    espacos = gamedata.espacos_ferimento_para_corpo(1)
    # alvo frágil já com todos os Críticos menos 1 e Vitalidade baixa
    orc = _combatant("orc", corpo=1, vitalidade=1, is_player=False, categoria="chefe")
    orc["ferimento_espacos"] = espacos
    orc["ferimentos"]["critico"] = [{"regiao": f"r{i}", "categoria": "critico"}
                                    for i in range(espacos["critico"] - 1)]
    scene = _scene_with("heroi", "orc")
    decl = {"actor_id": "heroi",
            "acao": {"kind": "attack", "target_id": "orc", "params": {"formula": "6d6"}}}
    out = ct.resolve_turn(scene, {"heroi": heroi, "orc": orc}, decl, rng=_hit())
    assert "orc" in out["terminal"] and orc["estado_terminal"] is True


# ==========================================================================
# Custo de Carta debita Entropia via state (conflito-02)
# ==========================================================================
def test_ataque_com_carta_debita_entropia():
    heroi = _combatant("heroi")
    heroi.update({"entropy": 5, "prepared_cards": ["raio_cinza"], "known_cards": ["raio_cinza"],
                  "card_usage": {}, "level": 1})
    orc = _combatant("orc")
    scene = _scene_with("heroi", "orc")
    state = {"player": heroi, "combat": {"scene": scene}}
    decl = {"actor_id": "heroi",
            "acao": {"kind": "card", "card_id": "raio_cinza", "target_id": "orc"}}
    out = ct.resolve_turn(scene, {"heroi": heroi, "orc": orc}, decl, state=state, rng=_hit())
    assert heroi["entropy"] == 4                          # raio_cinza custa 1 Entropia
    assert out["attacks"]
