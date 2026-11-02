"""SPEC-364 R13: resumo real do staging (smoke 4, conta A) e um texto correto escrito a mao."""

from __future__ import annotations

PLAYER = {"name": "Smoke4A", "vitalidade": 9, "max_vitalidade": 18, "ferimentos": {}}
NAMES = {"enemy_mino": "Minotauro Esqueleto", "enemy_goblin": "Goblin"}
SUMMARY = {
    "participantes": ["Smoke4A", "Goblin", "Minotauro Esqueleto"],
    "mortos": ["Goblin", "Minotauro Esqueleto"],
    "caidos": [],
    "inconscientes": [],
}
# O Goblin morreu na rodada 3; a vitoria veio na 5 (Minotauro Esqueleto).
LAST_OUT = {
    "final_blows": [{"target_id": "enemy_mino", "kind": "ataque", "by_actor_id": "player"}],
    "deaths": ["enemy_mino"],
}

# Trecho real (staging, A_end): a queda antiga contada no presente.
REAL_BAD = (
    "Seu golpe termina o serviço: o Minotauro Esqueleto desaba em pedaços. "
    "O Goblin também tomba sem vida ao seu lado."
)
GOOD = (
    "Seu golpe termina o serviço: o Minotauro Esqueleto desaba em pedaços. "
    "O Goblin, que já tinha tombado, jaz ao seu lado."
)
