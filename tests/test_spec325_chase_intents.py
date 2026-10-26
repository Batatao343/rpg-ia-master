"""SPEC-325 Fase B - regex fechadas da fuga (abordagem, abandono, aceite do sacrificio)."""

import pytest

from services import chase
from services.combat_intents import abandon_target, accepts_sacrifice, chase_approach


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("fujo pelos atalhos", "atalhos"),
        ("Fujo conhecendo as ROTAS da região", "rotas"),
        ("fujo desviando dos golpes", "desviar"),
        ("rompo a fileira e fujo", "romper"),
        ("fujo pelos obstáculos do pântano", "obstaculos"),
        ("fujo com resistência, numa corrida prolongada", "resistencia"),
        ("coordeno o grupo e fujo", "coordenar"),
        ("mobilizo os aldeões para fugir", "mobilizar"),
        ("corro e fujo", "correr"),
    ],
)
def test_approach_keyword_picks_key(text, key):
    assert chase_approach(text) == key
    assert key in chase.APPROACH_VIRTUDE  # chave valida do motor


@pytest.mark.parametrize(
    "text", ["fujo", "recuo", "ataco o goblin", "não desvio, apenas fujo", "nunca uso atalhos"]
)
def test_approach_none_without_keyword_or_negated(text):
    assert chase_approach(text) is None


def test_approach_picks_first_keyword_by_position():
    assert chase_approach("fujo pelos atalhos e depois desvio") == "atalhos"


CANDS = {"npc_brunna": "Brunna Ponte-Alta", "npc_orik": "Orik"}


@pytest.mark.parametrize(
    ("text", "who"),
    [
        ("deixo a Brunna para trás", "npc_brunna"),
        ("Fujo e deixo Brunna Ponte-Alta para trás.", "npc_brunna"),
        ("abandono o Orik", "npc_orik"),
        ("deixo ORIK", "npc_orik"),
    ],
)
def test_abandon_target_positive(text, who):
    assert abandon_target(text, CANDS) == who


@pytest.mark.parametrize(
    "text",
    [
        "abandono o plano",  # falso positivo: nao e candidato
        "deixo a espada no chão",
        "não deixo a Brunna",
        "nunca abandono o Orik",
        "Brunna fica",
        "",
    ],
)
def test_abandon_target_negative(text):
    assert abandon_target(text, CANDS) is None


def test_abandon_only_candidates():
    assert abandon_target("deixo a Brunna", {}) is None
    assert abandon_target("deixo a Brunna", {"npc_orik": "Orik"}) is None


@pytest.mark.parametrize("text", ["Aceito o sacrifício.", "aceito", "Aceitar sacrifício"])
def test_accepts_sacrifice(text):
    assert accepts_sacrifice(text)


@pytest.mark.parametrize("text", ["não aceito", "nunca aceito isso", "fujo", ""])
def test_accepts_sacrifice_negative(text):
    assert not accepts_sacrifice(text)


def test_fate_mapping():
    assert chase.fate_to_companion_fate("captura") == "capturado"
    assert chase.fate_to_companion_fate("rendicao") == "capturado"
    assert chase.fate_to_companion_fate("combate") == "ferido"
    assert chase.fate_to_companion_fate("morte") == "morto"
    for resultado in ("fuga", "esconderijo", "reencontro_futuro", "", "xx"):
        assert chase.fate_to_companion_fate(resultado) == ""


def test_simulate_restricted_outcomes_and_default_unchanged():
    comp = {"id": "c", "name": "C", "vitalidade": 6, "max_vitalidade": 6}
    for i in range(30):
        got = chase.simulate_abandoned_companion(
            comp, {"pursuers": 2}, f"s{i}", outcomes=chase.SACRIFICE_OUTCOMES
        )
        assert got["resultado"] in chase.SACRIFICE_OUTCOMES
    # sem `outcomes` o sorteio e o original (mesma seed, mesmo resultado)
    a = chase.simulate_abandoned_companion(comp, {"pursuers": 2}, "seed-x")
    b = chase.simulate_abandoned_companion(comp, {"pursuers": 2}, "seed-x")
    assert a == b and a["resultado"] in chase.ABANDON_OUTCOMES


def test_sacrifice_eligibility_by_soul_and_trait():
    comp = {"id": "c", "name": "C"}
    assert not chase.can_volunteer_sacrifice(comp)
    assert not chase.can_volunteer_sacrifice(comp, {"approval": 69, "values": {"coragem": 2}})
    assert not chase.can_volunteer_sacrifice(comp, {"approval": 90, "values": {"coragem": 0}})
    assert chase.can_volunteer_sacrifice(comp, {"approval": 70, "values": {"coragem": 1}})
    assert chase.can_volunteer_sacrifice({**comp, "se_sacrifica_pelo_grupo": True})


def test_abandon_candidates_only_formal_active_with_complication():
    party = [
        {"id": "a", "name": "A", "active": True},
        {"id": "b", "name": "B", "active": True},
        {"id": "t", "name": "T", "active": True, "transient": True},
        {"id": "w", "name": "W", "active": False},
        {"id": "s", "name": "S", "active": True, "pending_fate": {"fate": "morto"}},
    ]
    luck = {"last_luck": {"a": -1, "b": 0, "t": -1, "w": -1, "s": -1}}
    assert chase.abandon_candidates(luck, party) == {"a": "A"}
    assert chase.abandon_candidates({}, party) == {}


def test_seal_fate_is_seeded_and_does_not_apply():
    comp = {"id": "c", "name": "C", "active": True, "vitalidade": 6, "max_vitalidade": 6}
    one = chase.seal_fate(comp, instance_id="g:0:1", round_=3, pursuers=2, day=4, location_id="loc")
    other = dict(comp)
    two = chase.seal_fate(
        other, instance_id="g:0:1", round_=3, pursuers=2, day=4, location_id="loc"
    )
    assert one == two and one["seed"] == "g:0:1:c:3"
    assert comp["active"] is False and comp["waiting_at"] == "loc"
    assert comp["pending_fate"] is one
    assert "status" not in comp  # nada aplicado: so selado
