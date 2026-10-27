# SPEC-345 — achados do teste no navegador (27/10, main 4abb270b)

API local MockLLM, flags de cartas off e on, 360×800 e 1440×900. Prints em `prints/`.
Itens só do front das cartas (mão cortada, "ROUND", homônimos no deck, chip sobre o Espólio, "Aguentar" na mão, borda dupla) foram para a SPEC-342.
e2e: 289 passed, 1 failed (`effects.spec.ts:540` perf long task 259 > 250 ms, máquina com 1,9 GB livre — provável ruído; reconfirmar).

1. Inimigo morto segue no combate (ambos os modos): Bandido 0/8 listado como combatente "Engajado…", ainda com presságio (on). Prints `on-360_07-conflito-inicio.png`, `off-360_08-conflito-painel-mobile.png`. Provável: roster do painel / `encounter_view` e `pressagios_publicos` sem filtrar HP 0.
2. Homônimos no roster comum: "Bandido"/"Bandido" no roster enquanto "Engajado: Bandido 1" e log usam números (ambos os modos). `on-360_09-mao.png`.
3. Texto interno cru na narração (ambos): "Espólio: 12 ouro, 1x adaga_ferro.", "1x pocao_cura" (ids em vez de nomes) e "[SISTEMA] Adaga de Ferro (incomum) e +12 de ouro" (tag crua, mesma família de 316 F-1 `[RESULTADO]`). `on-1440_12-r1-pos.png`, `off-1440_13-desfecho.png`. Fonte: mensagem de loot/kill no backend.
4. Mech log com ator "?": `"? → Bandido 2 · 2d10 2 + 8 +1 = 11 vs 12 · erro"` (provável ataque de companheiro, Mestre Aldric). `combat.mech_log` da API.
5. Faixa preta vazia com "PREPARAÇÃO 4/4" após o combate (ambos). `off-360_12-desfecho.png`, `off-1440_13-desfecho.png`.
6. Mobile 360: tab bar inferior apertada — "Personagem" e "Combate" encostam; ponto vermelho de notificação cortado. `on-360_09-mao.png`, `off-360_06-jogo.png`. `MobileTabBar.tsx`.
7. Mobile 360: header corta o lugar para "NOVA A…" em combate por causa do chip "COMBATE · RODADA N". `on-360_07-conflito-inicio.png`. `Hud.tsx`.
8. Mobile 360: banner de modo simulado + dica de onboarding cobrem ~60 % da tela no 1º turno. `off-360_06-jogo.png`. `Banner.tsx` + `OnboardingHint.tsx`.
9. Menores: trilha de ferimentos quebra a 4ª caixa "Leve" em linha própria a 360 (`on-360_19-r3-pos.png`, `WoundTrack.tsx`); botões "Afiar …" da Forja desabilitados com baixo contraste e motivo pouco visível (`on-1440_12-r1-pos.png`).
10. Carta de Espólio com "Causa 2d6 de dano" num sistema 2d10 com dano fixo (dado de carta; investigar origem, não mudar número sem decisão).
