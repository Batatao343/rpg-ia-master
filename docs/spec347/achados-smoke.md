# SPEC-347 — achados de layout do smoke com LLM real (27/10, main fae9a4e5)

Mesmo smoke da SPEC-346 (API local legacy, flags de cartas on, DeepSeek). Esta spec cobre só front/layout. Prints em `smoke/`.

1. P2 — 390: "Cancelar" da barra de mira coberto pela barra fixa "Sem matar | Encerrar a rodada". `DeckCombat.tsx` aimbar + barra fixa, CSS `.deck-combat`. `smoke/1874135-Brannoc-r3-390-2-previa.png`.
2. P2 — 390, fila cheia: "Sem matar" quebra em 2 linhas; "ENCERRAR A RODADA" e "2 CARTAS" quase colados; "DESFAZER FILA" em 2 linhas; faixa do presságio quebra "3–\n6". `PlayQueue.tsx` + CSS. `smoke/1877078-Brannoc-r3-390-3-fila.png`.
3. P2 — 1440, Arena com 3 zonas: zonas vazias ("Veio de Calcário", "Boca do Abismo") ocupam 2/3; chips dos inimigos espremidos (nome em 3 linhas, "sem Vitalidade" em 2); mão empurrada para fora da dobra. Grade da Arena (`web/src/combat/Arena.tsx` + CSS). `smoke/2364091-Ysolde-r5-1440-0-inicio.png`.
4. P3 — 1440 com mira armada: "Jogar em X" abaixo da dobra (só a prévia aparece). `smoke/1654717-Brannoc-r1-1440-2-previa.png`.
5. P3 — Faixa de iniciativa inconsistente: "Heróis → Inimigos" mas inimigos agiram primeiro no mech_log da rodada 1; chips "0 · Inimigos / 0 · Heróis"; "Rodada N" duplicado (faixa + iniciativa).
6. P3 — Tooltip de palavra-chave no Espólio cobre o botão "Levar …" da própria carta. `smoke/1996090-Brannoc-esp-1440-2-tooltip.png`.
7. P3 — Forja: "Esquecer (descanso)" e "Esquecer no templo (25 de ouro)" desabilitados sem motivo visível (só o Afiar diz). `smoke/1998419-Brannoc-esp-1440-5-forja-row.png`.
8. P3 — Pós-vitória o painel abre rolado; chip de desfecho com "CONTINUAR" cortado no topo; rótulo "UTILITARIA" sem acento no acervo. `smoke/1722832-Brannoc-r2-1440-4-pos-combate.png`.
9. P3 — Prévia mistura "64,9 %"/"56,8 %" com "76 %"/"82 %" (padronizar inteiro).
10. P3 — Ao reabrir o save em 1440, o Livro abre no prólogo em vez da última narração.
11. Não coberto no smoke: confirmação inline da Forja (sem material/descanso), ponto `has-loot` na aba móvel — cobrir com teste.
