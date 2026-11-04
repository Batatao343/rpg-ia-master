# SPEC-391 — Resultado do gate de letalidade §8 (04/11, coordenador)

Arena congelada `481a0774` · 20 sementes · L3/L5/L8 · 5 Posturas · pool de 7 líderes ·
`RPG_CARD_DECK=on RPG_ENEMY_DECKS=on RPG_ENEMY_INTENT=on`; única diferença: `RPG_COMBAT_REINFORCEMENTS`.

| Gate | Código | Δ morte agregado | Pior Postura | countered/tel |
|---|---|---|---|---|
| 1 | sem alavanca (`8a2c0a36`) | +19,6 pp | Corruptor +31,7 | 34,4 % |
| 2 | L1 folga (`c5e7c921`) | +10,6 pp | Corruptor +17,9 | 55,6 % |
| 3 | L1+L2 fôlego (`eb1cabf1`) | +10,4 pp | Corruptor +17,4 | 55,6 % |
| 4 | L1+L2+L3 Capanga (`044d608c`) | +10,4 pp | Corruptor +17,4 | 55,6 % |

Critério (opção 2, D-391-4): Δ ≤ +8 pp agregado e ≤ +12 pp por Postura; vitória ON 45–85 %; countered/tel ≥ 25 %.
**Reprovado após as três alavancas → `RPG_COMBAT_REINFORCEMENTS` fica `off`; decisão do dono (D-391-5).**
Neutralidade: células da arena 285 e JSON da 368 idênticos com a flag on/off.

Leitura: L1 zera chegadas em L3 (orçamento justo), mas L5/L8 seguem com Δ ≈ +26/+10 pp; L2 e L3 quase não pesam
(L3 só muda o líder da `legiao_ferro`, 1 de 7). Vitória ON por Postura fica em 57–79 % (passaria na opção 3).

Gate 4 detalhado:

```
L3|lider_matilha death off 25.1 on 19.9 | tel 690 countered 672 fired 0 cancelled 448
L5|lider_matilha death off 27.3 on 53.3 | tel 689 countered 168 fired 516 cancelled 11
L8|lider_matilha death off 10.0 on 20.4 | tel 653 countered 289 fired 360 cancelled 3
AGG death on 31.2 off 20.8 delta 10.4pp | countered/tel 55.6%
  Arcanista Cinzento   delta 10.0pp  win_on 62.9%  timeout_on 0.0%
  Corruptor            delta 17.4pp  win_on 63.6%  timeout_on 0.0%
  Devoto do Abismo     delta 10.5pp  win_on 75.5%  timeout_on 1.0%
  Médico de Campo      delta 10.2pp  win_on 57.4%  timeout_on 4.8%
  Sangromante          delta 3.8pp  win_on 79.0%  timeout_on 0.0%
```
