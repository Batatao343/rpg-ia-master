# SPEC-354 — achados de tela do smoke 2 (28/10, main 7c084cfc, SPEC-346/347 pousadas)

Mesmo smoke da SPEC-353 (LLM real, flags de cartas on, 390×844 e 1440×900). Prints em `smoke/`. Motor/backend vai para a SPEC-353.

1. P2 — O Livro não reabre na última narração (falha da SPEC-347 §6.4/R11): ao reabrir o save, `.story` fica em scrollTop 130 de 3146 (1440) e 0 de 4203 (390) — prólogo. StoryLog/PlayScreen; o `resetBookScroll` da 347 não resolve o caso real. Reproduzir com e2e de reabrir save. `smoke/5067793-Haldor-a1-1440-0-inicio.png`.
2. P2 — 390 com fila cheia: "Desfazer fila" e a nota do "Sem matar" ficam por baixo da barra fixa. `smoke/4780731-Haldor-r2-390-3-fila.png`.
3. P2 — 1440: a mão fica abaixo da dobra com RoundBoard + 2 inimigos (347 §6.2 pede a mão sem rolar). `smoke/5692211-Mirela-v1-1440-top.png`.
4. P3 — 390: a aba Combate mostra só "Vitória" e o espólio após a vitória; o registro da última rodada e o resumo da IA só aparecem na Crônica. Mostrar o resumo final e o último registro no painel de Combate. `smoke/4857228-Haldor-v3-390-top.png`.
5. P3 — RoundBoard a 1440 em duas colunas embaralha a ordem de leitura; DoT aparece entre as jogadas e com rótulo "Você" como se fosse ataque do jogador; ataque que aplica DoT mostra "Acerto" sem valor; "Bandido morre" e o efeito do presságio cumprido não entram no painel. `smoke/Haldor-v1-390-full.png`.
6. P3 — Sem retrato nem ícone de família nos chips de inimigo com RPG_CREATURE_ART off e sem arte curada (`_enemy_portrait` em `api.py:2796` devolve None) — diverge do combinado (arte curada OU ícone da família sempre). O ícone da família deve aparecer independente da flag.
7. P3 — 1440: toasts de recompensa da vitória (+100 XP, +20 ouro, +1 Corda) cobrem o texto do Livro por um instante. `smoke/6282120-Haldor-k4-1440-4-pos-combate.png`. Abas e botões do cabeçalho a 1440 com 37–38 px (relevante só com toque no desktop — alinhar a 44 em `pointer: coarse`).
8. P2 (front do item 7 da 353) — id `npc_ketil` exibido na Arena na rodada 0 (`smoke/4661367-Haldor-t1-390-combate.png`): o front deve sempre preferir o nome exibível e nunca mostrar id cru (defesa em profundidade, mesmo após o fix da API).
