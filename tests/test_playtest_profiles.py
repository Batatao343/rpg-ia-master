"""Suíte da spec playtest-agente-curioso-entropia (Etapa 2): perfis de combate
usam habilidade de Entropia + curam com HP baixo, sem quebrar o determinismo.

Offline/determinístico. Ver specs/SPEC-059-playtest-agente-curioso-entropia.md.
"""
import random

from playtest.profiles import PROFILES
from playtest.runner import run_campaign


def _combat_state(entropy=16, hp=30, inventory=None):
    return {
        "player": {"name": "K", "class_name": "Devoto do Abismo",
                   "hp": hp, "max_hp": 30, "entropy": entropy, "max_entropy": 16,
                   "known_cards": ["dev_provocacao"],
                   "prepared_cards": ["dev_provocacao"],
                   "inventory": inventory or []},
        "enemies": [{"id": "g1", "name": "Goblin", "status": "ativo"}],
        "combat": {"active": True},
        "world": {"current_location_id": "pantano_melancolia", "danger_level": 2},
        "npcs": {}, "messages": [],
    }


def test_agressivo_usa_habilidade_quando_tem_entropia():
    prof = PROFILES["agressivo"]
    st = _combat_state(entropy=16)
    # alguma seed em [0,20) deve nomear a habilidade (prob. 0.6)
    acoes = {prof.next_action(st, random.Random(s)) for s in range(20)}
    assert any(a.startswith("Uso Provoca") for a in acoes), acoes


def test_agressivo_cai_pro_basico_sem_entropia():
    prof = PROFILES["agressivo"]
    st = _combat_state(entropy=0)   # não paga nenhuma ativa
    for s in range(10):
        a = prof.next_action(st, random.Random(s))
        assert not a.startswith("Uso "), a   # nunca emite ação inválida
        assert "Ataco" in a


def test_perfil_cura_com_hp_baixo():
    prof = PROFILES["agressivo"]
    # HP baixo + poção no inventário → bebe
    st = _combat_state(hp=6, inventory=[{"id": "pocao_cura", "qty": 1}])
    assert prof.next_action(st, random.Random(0)) == "Bebo a poção de cura."
    # HP baixo SEM poção → não trava (ataca/usa habilidade, ação válida)
    st2 = _combat_state(hp=6, inventory=[])
    a = prof.next_action(st2, random.Random(0))
    assert a and isinstance(a, str)


def test_combate_hp_baixo_local_seguro_descansa():
    prof = PROFILES["combate"]
    st = {"player": {"hp": 5, "max_hp": 30, "entropy": 16, "max_entropy": 16,
                     "known_abilities": ["ataque_basico"], "inventory": []},
          "enemies": [], "combat": {"active": False},
          "world": {"current_location_id": "nova_arcadia", "danger_level": 1},
          "npcs": {}, "messages": []}
    assert "Descanso" in prof.next_action(st, random.Random(1))


def test_determinismo_preservado():
    # mesma (profile, seed) → mesma sequência de ações (contrato PURO).
    a = run_campaign("agressivo", turns=6, seed=5)
    b = run_campaign("agressivo", turns=6, seed=5)
    assert [r.action for r in a.history] == [r.action for r in b.history]


def test_medico_mira_cura_no_jogador_e_nao_no_inimigo():
    prof = PROFILES["combate"]
    st = _combat_state(entropy=16, hp=10)
    st["player"].update({
        "class_name": "Médico de Campo",
        "vitalidade": 3,
        "max_vitalidade": 12,
        "prepared_cards": ["med_sutura"],
        "known_cards": ["med_sutura"],
    })

    decisions = [prof.decide(st, random.Random(seed)) for seed in range(20)]
    card_decisions = [
        d for d in decisions
        if ((d.declaration or {}).get("acao") or {}).get("kind") == "card"
    ]

    assert card_decisions
    assert all(
        d.declaration["acao"]["target_id"] == "player"
        for d in card_decisions
    )


def test_medico_nao_desperdica_cura_com_vitalidade_cheia():
    prof = PROFILES["combate"]
    st = _combat_state(entropy=16, hp=30)
    st["player"].update({
        "class_name": "Médico de Campo",
        "vitalidade": 12,
        "max_vitalidade": 12,
        "prepared_cards": ["med_sutura"],
        "known_cards": ["med_sutura"],
    })

    for seed in range(10):
        decision = prof.decide(st, random.Random(seed))
        assert decision.declaration["acao"]["kind"] == "attack"
