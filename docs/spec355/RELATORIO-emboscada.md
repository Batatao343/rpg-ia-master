# SPEC-355 R16/R17 - emboscada realista (f_viagem = 1, cota superior)

`p_emb` = média, em perigo 1-4, de P(d20 + Mente < 8 + 2×perigo). Devoto/Sangromante 0,45-0,50,
Corruptor/Médico 0,30, Arcanista 0,25. Taxa realista = `p_emb × emboscada + (1 - p_emb) × base`.
JSON: `arena-emboscada-0-19.json`, `arena-emboscada-20-99.json`.

| Postura | base 0-19 | emboscada 100 % | **realista 0-19** | base 20-99 | **realista 20-99** |
|---|---|---|---|---|---|
| Devoto do Abismo | 64,2 % | 61,0 % | 62,7 % | 60,9 % | 60,5 % |
| Sangromante | 61,0 % | 55,0 % | 58,0 % | 61,9 % | 57,9 % |
| Corruptor | 45,6 % | 40,8 % | **44,2 %** | 46,5 % | 45,2 % |
| Arcanista Cinzento | 44,4 % | 35,2 % | **42,1 %** | 43,9 % | **42,1 %** |
| Médico de Campo | 52,1 % | 56,9 % | 53,5 % | 56,9 % | 56,1 % |

Corruptor e Arcanista ficam abaixo de 45 % (0-19) → R17 implementado (`_has_vigilia` aceita qualquer Carta
`buff_iniciativa`; as 5 Cartas são `passiva`/`reacao`, fora do baralho da arena, então os números não mudam).
**Exceções pendentes:** Corruptor (sem Carta `buff_iniciativa`; 45,2 % na held-out) e Arcanista (42,1 %, as
duas Cartas dele são passivas fora do baralho de arena). Sem número novo nesta spec.
