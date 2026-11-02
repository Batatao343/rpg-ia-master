"""SPEC-363 R17: textos reais do smoke 3 (rejeitados) e equivalentes corretos (aceitos)."""

from __future__ import annotations

# Morte no staging: nome mutilado, herói 3x, queda antiga no mesmo instante.
DEATH_BAD = (
    "Você tomba. Goblin tomba. SmokeA cai. SmokeA perde os sentidos. "
    "Você carrega ferimento crítico na perna, ferimento crítico no braço."
)
DEATH_GOOD = (
    "Você tomba diante de Minotauro Esqueleto. Antes, Goblin já tinha tombado. "
    "Você carrega ferimento crítico na perna, ferimento crítico no braço."
)

# Vitória sobre o Mímico: o fio de sangue foi do Mímico, o herói saiu ileso.
MIMIC_BAD = (
    "O Mímico recua. O fio de sangue que escorreu pelo seu braço é a única prova do golpe, "
    "e o corpo segue intacto."
)
MIMIC_GOOD = "O Mímico recua, o braço ferido, e foge. Você segue ileso, de pé diante do baú."

# Vitória da Ilsa: tratamento misto tu/você.
ILSA_BAD = "Ficas de pé, com teu cajado firme. Você respira fundo e sente o fôlego voltar."
ILSA_GOOD = "Você fica de pé, com o seu cajado firme, e sente o fôlego voltar."

PLAYER = {"name": "Smoke3A", "ferimentos": {"critico": [{"regiao": "perna"}, {"regiao": "braco"}]}}
HERO_UNHURT = {"name": "Haldor", "vitalidade": 18, "max_vitalidade": 18, "ferimentos": {}}
