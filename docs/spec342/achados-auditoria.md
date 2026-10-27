# SPEC-342 — achados das auditorias de front (27/10)

Duas auditorias só-leitura do `web/` (main pós-SPEC-339), lentes `impeccable` e `taste`.
Nenhuma rodou build/navegador; a verificação no navegador (prints 360/1440, flags on/off) é anexada depois.

## Lente impeccable (a11y, estados, regressões)

- F-1 P1 `CombateTab.tsx:97,236-239,252-257` + `DeckCombat.tsx` (onEnd): em deckMode o chip "Sem matar" (325) segue visível e alterna, mas `onEnd` monta "Encerrar turno: …" sem `SPARE_TEXT`/`spareOn` → golpe não-letal inerte. Regressão off→on, bloqueia RPG_CARD_DECK.
- F-2 P2 `workspace.css:283-293`: regra `pointer: coarse` não cobre deck novo (`.deck-hand__piles`, `.deck-hand__list button`, `.play-queue__item`, `.play-queue__ops button`, `.play-queue__clear` 2.2rem; `.play-queue__submit` 2.6rem; summaries `.mech-log`/`.ws-combat__fold`). < 44px, regride 321.
- F-3 P2 `workspace.css:325-326`, `Hand.tsx:57-63`: `.kw__tip` absoluto dentro de `.deck-hand__rail` (overflow-x auto) → cortado/scroll; sai da tela em 360px. Portal fixed ou linha fixa.
- F-4 P2 `Hand.tsx:44-46`: aria-label substitui conteúdo; texto da carta só via aria-describedby quando há palavra-chave. Sempre descrever.
- F-5 P2 `workspace.css:324`: `.deck-card.is-dim{opacity:.5}` derruba contraste do motivo de bloqueio. Opacidade só em nome/desc.
- F-6 P2 `DeckCombat.tsx` play/add, `PlayQueue.tsx:44-52`: armar carta com alvo não move foco nem anuncia; Encerrar turno disabled com busy perde foco; remover item da fila desmonta botão focado.
- F-7 P2 `Hand.tsx:30-45`, `PlayQueue.tsx:24-27`: mão vazia/toda bloqueada sem mensagem; saída só no details fechado "Manobras". Mostrar aviso e abrir details.
- F-8 P2 `ForjaPanel.tsx:56-66,81-87`: Esquecer / Esquecer no templo (ouro) / Tratar-Purgar sem confirmação.
- F-9 P3 `KeywordTip.tsx:12-17`: toque — tooltip fecha ao levantar dedo; toque longo pode armar carta no iOS.
- F-10 P3 `ContextSurface.tsx:97` + atalhos `DeckCombat`: atalhos 1–5/Enter/Esc globais valem com aba oculta; ShortcutsSheet não lista.
- F-11 P3 `EspolioPanel.tsx:11,53`: `NO_GLOSSARY` (sem tooltip); sem badge de espólio pendente fora da aba.
- F-12 P3 `FolegoPips.tsx:17-25`, `workspace.css:313-316`: vazio vs reservado indistintos (<3:1); role=status do Pacto montado já com conteúdo.
- F-13 P3 copy mistura "turno"/"rodada"; "Números da rodada" seco.
- F-14 P3 `h2` "Sua mão"/"Espólio"/"Forja do Baralho" possivelmente no nível do h2 do painel (324). Conferir DOM.

Sem achado: caminho off intacto (exceto F-1); CSS novo só tokens; épico sem animação nova; prévia com AbortController e estados; motor revalida.

## Lente taste (coerência visual, clareza, voz)

- T-1 P1 `DeckCombat.tsx:123`: `SceneStrip` só recebe `round`; `extras` nunca alimentado → Cartas de Cena/objetivo/Relógio do Abismo (331) invisíveis. Pode exigir campo na API (`combat.cena`/relógio).
- T-2 P1 dois fluxos de alvo: `aimbar` da Arena (`CombateTab.tsx:~223`) e chips `deck-target` (`DeckCombat.tsx:~131`). Unificar.
- T-3 P1 mobile pesado: ~10+ blocos empilhados (arena, aimbar, ritmo, presságios, Fôlego, mão+pilhas, trilho, alvo/prévia, fila, log, reação, Manobras). 334 R7 (≤12 interativos em 390px) e conferência 390/1440 ainda desmarcadas.
- T-4 P2 casca com cara de app: `.enemy-strip`, `.preview-chip`, `.play-queue`, `.deck-hand__piles` caixas iguais 1px; prévia (decisiva) em 0.9rem. Dar `--display`/tabular à prévia; rebaixar fila/pilhas.
- T-5 P2 presságio só texto (`EnemyStrip.tsx:11`, `deck.ts:106-111`); 334 R1 pede ícone + número. Ícone por `p.tipo` (família `Icon` da 322).
- T-6 P2 presságio oculto sem estado ("intenção velada").
- T-7 P2 palavra-chave sem afordância no mobile; pips de Fôlego `aria-hidden` → custo só visual; acrescentar "Fôlego 2" em texto.
- T-8 P2 microcopy de sistema (`deck.ts:35-41`, `PreviewChip.tsx:10`, `MechLog.tsx:6`, `DeckCombat.tsx`): "Fardo: não pode ser jogada", "Fila cheia", "Já está na fila", "Sem Fôlego", "Entropia insuficiente", "Prévia indisponível…", "Números da rodada", "sem alvo válido". Reescrever na voz de Valoria.
- T-9 P2 "Encerrar turno" sem peso de ação principal; mistura "(N)" e "Enter" (`PlayQueue.tsx:47-53`).
- T-10 P2 três famílias de botão numa aba (`.btn` em Espólio/Forja vs `.actionchip`); Espólio não usa `.combat-card`; Forja repete ações por carta.
- T-11 = F-11.
- T-12 P2 botão "Pilhas" sem pista de que abre lista; "Exaurida" sem explicação.
- T-13 P3 `.deck-hand__rail` 72vw + min-height 150–185px herdado (`workspace.css:355`).
- T-14 = F-12.
- T-15 P3 MechLog texto cru, sem tipografia `--label` nem separador por rodada.
- T-16 P3 `.espolio`/`.forja` 1.1rem solto fora da escala de h2 da 322/324.

Off: sem resíduo visível (deckMode = !!combat?.pilhas).
