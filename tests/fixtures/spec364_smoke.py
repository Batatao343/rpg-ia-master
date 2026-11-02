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

# Resumo REAL do staging (smoke 4, conta A, `A_end.message`, trecho de prosa; sem segredos): a queda antiga
# do Goblin (rodada 3) contada no presente na vitória da rodada 5.
REAL_BAD = (
    "A Espada Gasta desce duas vezes contra o Minotauro Esqueleto, abrindo um ferimento crítico na perna "
    "e outro grave no braço da criatura — e então o Sangramento que já corria por dentro dos ossos termina "
    "o que a lâmina começou. O colosso desaba e não se levanta mais, enquanto o Goblin também tomba sem "
    "vida ao seu lado. A Última Ação do inimigo ainda te alcança num acerto crítico, deixando um ferimento "
    "leve no seu braço, mas é tarde demais para mudar o desfecho. Você permanece de pé, à beira do "
    "colapso, respirando o ar frio do amanhecer sobre as Montanhas Afiadas — e o campo é seu."
)
# Texto correto escrito à mão: mesma prosa, queda antiga no passado.
GOOD = REAL_BAD.replace(
    "enquanto o Goblin também tomba sem vida ao seu lado",
    "enquanto o Goblin, que já tinha tombado, jaz ao seu lado",
)
