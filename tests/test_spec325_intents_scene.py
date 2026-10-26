"""SPEC-325 Fase C - intents puras: objeto de cena (R14) e ordem a companheiro (R15)."""

import pytest

from services.combat_intents import companion_order, object_step

VISIBLE = [
    {
        "id": "pilar",
        "name": "Pilar Rachado",
        "interactions": [{"label": "derrubar", "cost": "acao"}, {"label": "escalar"}],
    },
    {"id": "tocha", "name": "Tocha", "interactions": [{"label": "apagar"}]},
]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Derrubar Pilar Rachado.", ("pilar", "derrubar")),
        ("derrubo o pilar rachado", ("pilar", "derrubar")),
        ("apago a tocha", ("tocha", "apagar")),
        ("escalo o pilar rachado", ("pilar", "escalar")),
    ],
)
def test_object_step_positive(text, expected):
    assert object_step(text, VISIBLE) == expected


@pytest.mark.parametrize(
    "text",
    [
        "ataco o goblin",
        "derrubo o goblin",  # rótulo sem objeto
        "olho o pilar rachado",  # objeto sem rótulo
        "não derrubo o pilar rachado",  # negação
        "derrubo o altar",  # objeto inexistente
        "",
    ],
)
def test_object_step_negative(text):
    assert object_step(text, VISIBLE) is None


def test_object_step_only_visible():
    assert object_step("abro o alçapão", VISIBLE) is None
    assert object_step("derrubo o pilar rachado", []) is None


ALLIES = {"npc_brunna": "Brunna Ponte-Alta", "npc_kael": "Kael"}
ENEMIES = [
    {"id": "e1", "name": "Goblin", "status": "ativo"},
    {"id": "e2", "name": "Rendido", "status": "rendido", "surrendered": True},
    {"id": "e3", "name": "Caido", "status": "incapacitado", "incapacitated": True},
]


@pytest.mark.parametrize(
    "text, ally, verb, target, tags",
    [
        ("Brunna, atacar o Goblin", "npc_brunna", "atacar", "e1", []),
        ("Brunna, ataque o Rendido.", "npc_brunna", "atacar", "e2", ["atacar_rendido"]),
        ("Kael: ataque o caido", "npc_kael", "atacar", "e3", ["atacar_incapacitado"]),
        ("Brunna, proteger.", "npc_brunna", "proteger", None, []),
        ("Kael, recue!", "npc_kael", "recuar", None, ["abandonar_posto"]),
        ("Brunna Ponte-Alta, cure o grupo", "npc_brunna", "curar", None, []),
        ("Ataco o ogro. Kael, proteja", "npc_kael", "proteger", None, []),
    ],
)
def test_companion_order_positive(text, ally, verb, target, tags):
    order = companion_order(text, ALLIES, ENEMIES)
    assert order == {"ally_id": ally, "verb": verb, "target_id": target, "tags": tags}


@pytest.mark.parametrize(
    "text",
    [
        "Brunna, não ataque o Goblin",
        "Ataco o goblin",
        "Brunna ataca o goblin",  # sem vírgula: não é ordem fechada
        "Zé, proteger",  # não é aliado
        "Brunna, dança",  # verbo fora da lista
        "Brunna, talvez",
        "",
    ],
)
def test_companion_order_negative(text):
    assert companion_order(text, ALLIES, ENEMIES) is None


def test_companion_order_needs_allies():
    assert companion_order("Brunna, proteger", {}, ENEMIES) is None
