# Smoke local (LLM real): SPEC-367 §6 itens 2, 3 e 5

Feito em 03/11/2026, na mesma sessão e no mesmo ambiente de `docs/spec368/smoke-local.md` (cópia `git archive` de `2a6e0945`, perfil `legacy` em `:8756`, preset de `scripts/staging/staging_flags.json` com cartas `on`, DeepSeek `deepseek-v4-flash`). Os itens 1 e 4 (operação e retrato no staging) são do coordenador (`docs/spec367/smoke-staging.md`).

Evidência bruta fora do repo, em `C:/Users/guilh/AppData/Local/Temp/claude/c--Users-guilh-OneDrive--rea-de-Trabalho-rpg-ia-master/f66a5847-73fa-4458-abe7-93e60a175ae9/scratchpad/out/`: `i367-sell.json`, `i367-buy.json`, `i367p-*.png`, `i367q-*.png`, `llm-8756.jsonl`.

## Tabela item → resultado

| Item / R | Resultado | Evidência |
|---|---|---|
| 2a. Loja: "Posso vender a <3 primeiras palavras>?" (R1, R2) | **ok**. Herói Haldor6 (Skallgard, inventário com nomes longos). "Posso vender a Faca de esfolar?" → "Faca de esfolar de osso de vrel: o mercador paga 15 moedas. Diga claramente que vende para confirmar; nada mudou." É a cotação da entrada (nome recortado), sem a consulta inteira e sem transação: ouro 50 → 50. Tipo `LOOT`, 1,4 s. | `out/i367-sell.json` |
| 2b. Loja: compra com saldo final > 0 (R15, R16) | **ok**. Ouro do save ajustado para 80 (a oferta custa 50 e o herói nasce com 50). "Quero comprar a Lança de Gancho da Forja dos Clãs" → "…Skallgard desliza a Carta Lança de Gancho para suas mãos. O ouro escorre: 80 antes, 50 pelo preço, 30 depois…". Números na mensagem: {80, 50, 30}, **iguais** ao conjunto {antes, preço, depois}; nada de "últimas moedas". O ouro final do estado é 30. A V-G **não disparou**: 0 ocorrências de `trade_prose_rejected` no log. Observação: a prosa atribui a ação à cidade ("Skallgard desliza a Carta") e não ao mercador. | `out/i367-buy.json`, `out/server-8756b.log` |
| 3a. Combate: presságio com "você" a 390 e a 1440 (R7, R9) | **ok**. Chip nos dois tamanhos: "Um rosnado baixo, dentes à mostra: Goblin vai saltar sobre você. — Pancada de Tronco". Em todas as rodadas jogadas das seeds, com herói de nome próprio (Hero2, Hero4, Hero13*, Smoke368…), o `sinal` público nunca traz o nome do herói. A 390, na posição de rolagem padrão, a barra fixa cobre a linha do chip; ao rolar, o chip aparece inteiro. | `out/i367q-390-1.png`, `out/i367q-1440-1.png`, `out/i367p-390-1.png` |
| 3b. Condição de inimigo terminando (R13) | **ok**. A frase de R13 saiu no registro e na mensagem: "A condição Defesa Instintiva de Goblin terminou.", "A condição Fúria Acumulada de Goblin 2 terminou.", e, para o herói, "Sua condição Sangramento terminou.". O formato antigo ("Goblin-Mineiro: cego terminou.") **não** apareceu nas campanhas com cartas `on`. | `out/*-auto*.json` |
| 5. Varredura de `/game/history` (R25) | **ok** para as campanhas com cartas `on`. 22 históricos (de 3 a 11 entradas cada): **0** ids em `snake_case` no texto exibido, **0** menções ao nome do herói, **0** `[SISTEMA]`/`[RESULTADO]`, **0** `": … terminou"` cru. Ignorei campos de metadado (`speaker_id`, `technical_context`, `kind`, `card_id` etc.), como no smoke 5. **Exceção, fora do escopo `on`:** o save usado no teste do item 10 do 368 (API `off` com todo o LLM falhando) tem `enemy_goblin_1`, ": Defesa Instintiva terminou" e 8 menções ao nome do herói, vindos do texto de fallback do modo `off`. | `sweep.py` (scratchpad) |

## Chamadas de LLM e custo (esta parte do smoke)

- Os 2 turnos da loja e a compra: DeepSeek `deepseek-v4-flash`; a compra levou 6,0 s (CLASSIFY mais narração). Zero chamadas de CLASSIFY do `loot` na consulta ("Posso vender…").
- Número de chamadas e custo totais do smoke local: ver `docs/spec368/smoke-local.md` (~US$ 0,05 no total).

## Achados

1. **P3: a prosa da compra atribui a ação à cidade** ("Skallgard desliza a Carta Lança de Gancho…") em vez de nomear o mercador/a forja; é a observação A9 da 364 (R9) que continua valendo na prosa. Não move ouro.
2. **P3 (observação):** a 390, a barra fixa do combate cobre a linha do presságio na posição de rolagem padrão (print `i367p-390-1.png`). Não é regressão da 367, mas afeta o que o R7/R9 quer mostrar.

## Não verificado

- R13 em frase para condição de **inimigo** gerada por Carta de cena ou do herói (só vi a forma `a condição X de <inimigo> terminou` em condições naturais do Goblin).
- V-G do ouro (`trade_prose_rejected`) **não foi exercitada**: não disparou no turno de compra.
