# SPEC-354 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (re-revisão; 1ª rodada: `CHANGES_REQUIRED` em `0e8fd841`)
> **Revisor:** Opus 5.5 / papel Sol · **Data:** 2026-10-28 · **Commit revisado:** `0e8fd841` (1ª) → `495e36ee` (re-revisão, rebase sobre a SPEC-353)

## Escopo

Branch `spec-354` (`main...spec-354`, 5 commits `d73fdfa3..0e8fd841`): `api.py` (`_enemy_portrait`, `_combat_block`),
`web/src/**` (RoundBoard, deck.ts, displayName.ts, Arena, CombateTab, ContextSurface/Workspace, ChatSurface/OutcomeToast,
DeckCombat/PlayQueue, workspace.css), testes novos (`tests/test_spec354_*`, `web/tests/spec354-*`, `web/e2e/spec354-*`) e
os testes antigos alterados. Ficaram fora: o smoke real (§6, não executado pelo executor) e os prints de `smoke/` (só conferi
que existem).

Pontos do coordenador:
1. **Item 1 (Livro reaberto):** a investigação **não foi suficiente**. O defeito reproduz (ver P1-1).
2. **Sobreposições sem rolar:** R2.4 e R3.4 medem por `elementFromPoint`, sem rolar. Mas a medição do R3.4 é feita **sem retrato**, e o retrato agora vai sempre. Com retrato, R3.4 falha (P1-2). O R4.5 rola antes de medir "Continuar" (P2-2).
3. **RoundBoard:** uma coluna, "Jogadas" e "Efeitos da rodada", `tipo` opcional com inferência (`deck.ts::roundEntryKind`). Funciona com e sem `tipo`, e o SSR cobre os dois casos. OK.
4. **`_combat_block` pós-combate:** não vaza entre combates nem entre jogos. O conflito novo cria um `combat_meta` novo (`agents/combat.py:2080`), e `combat` no `GameState` é substituído inteiro (`state.py:1021`, sem reducer). Ressalva em P2-1.
5. **`_enemy_portrait` sem a flag:** não chama nada pago. Ele não passa `registry` nem `quote_price` (cai no `EmptyRegistry`), então `gerar` fica `None`, e `portrait_for` só lê o catálogo curado. OK.
6. **Toast fora do Livro:** está no fluxo e não intersecta mais o Livro. Ressalva em P2-3.
7. **displayName:** é aplicado na Arena (jogador, inimigo, aliado e engajados), no RoundBoard e no `nameOf` (presságio). A regra "parece id" está correta. Ressalva em P2-4.
8. **Testes antigos alterados:** todos têm justificativa (detalhe abaixo). Só o 224→192 depende de P1-2.
9. **Baseline 342:** verde sem regerar. Só tokens `var(--…)`, e `deck-tokens-342` e `npm run lint` estão verdes. O piso de 44 px em `coarse` vale para "Ler na Crônica" e para o summary do RoundBoard.

Testes antigos alterados:
- `spec347-desktop` (≥ 224 → ≥ 192 px): a spec autoriza explicitamente a R3.3(c) `minmax(12rem)`. A justificativa vale, mas só foi medida sem retrato (P1-2).
- `spec347-components` (o desktop passa a mostrar 4 + `details`): é a D-354-2, que revisa a 347 R14.3. Justificado.
- `combat-outcome` / M05 (escopo `region "Narrativa"`): a narração final agora aparece também no painel "O desfecho", e o strict mode pegaria duas. A asserção continua a provar que a narração está no chat. Justificado.
- `test_spec347_creature_art` (sem chave → marcador/pronto): é a D-354-C / R6.3. Justificado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/e2e/spec354-livro.spec.ts:60-86`; `web/playwright.config.ts:44` | **O item 1 reproduz.** A config do Playwright força `reducedMotion: "reduce"`, e o smoke e o jogador real rodam com movimento ligado. Rodei os mesmos testes com `reducedMotion: "no-preference"` (config temporária só no scratchpad, nada no worktree), e os dois ficam **vermelhos na branch e na `main` `1b769c9f`** (worktree temporário, já removido). 1440: `scrollTop 4475 de 21738` (gap 16842; na branch, 4416/21702, também com `SPEC354_COMBAT=1`). 390: `scrollTop 3788 de 30885` (gap 26609). A última `.msg` fica fora da vista. Junto vem um `console.error: Maximum update depth exceeded` (laço de setState em efeito) ao reabrir com movimento ligado. Esse erro já existe na `main` e provavelmente está ligado à causa. Logo, a parada por D-354-B foi prematura: H1 (altura cresce depois do `scrollTop = scrollHeight`; também a transição `grid-template-columns` de `.ws--split` e o `panel-in`, que só existem em `no-preference`) não foi testada. | Pôr `test.use({ reducedMotion: "no-preference" })` em `reabrir_save_real_1440/390` (vermelhos agora) e registrar os valores na §9. Achar a origem do "Maximum update depth" (o fixture de console já o pega) e confirmar a causa real. Depois, implementar R1.2 (preso ao fim + `ResizeObserver`) até os dois ficarem verdes com movimento ligado. Manter também a variante `reduce`. |
| P1-2 | P1 | `web/e2e/spec354-desktop.spec.ts:19-37`; `web/src/workspace.css:514`; `api.py:2796-2817` | O R3.4 é medido com inimigos **sem `retrato`**, mas o R6 agora manda `retrato` sempre (nos dois modos). Fiz uma sonda (cópia do teste no scratchpad, com marcador nos 2 inimigos): a 1ª `.deck-card` fica em `y 835, h 117`, com `inView:false` e `free:false`. **A mão volta para baixo da dobra** no layout real. O e2e `retrato_marcador_sem_flag` exigido pela R6.3 ("R3.4 continua verde com os retratos") não foi escrito. O ≥ 192 px do `arena_tres_zonas_1440` também só foi medido sem retrato. | Escrever `retrato_marcador_sem_flag` (1440 e 390) e pôr `retrato` na fixture do R3.4 e do `arena_tres_zonas_1440`. Ajustar o layout (por exemplo, R3.3(a)/(b), que ainda não foram usados, ou o retrato menor no `.arena--compact`) até a 1ª carta caber com retrato, e a `.tchip__vit` continuar numa linha. |
| P1-3 | P1 | `web/e2e/spec354-livro.spec.ts:89-104` | `subir_e_receber_narracao_nao_puxa` é fraco: ele injeta um `<article>` direto no DOM. O React não vê entrada nova, o efeito de `StoryLog.tsx:48-58` nunca roda, e o teste passa com qualquer lógica. Ele só prova que o navegador não rola sozinho (`overflow-anchor: none`). É justamente o guarda que a R1.2 ("preso ao fim") pode quebrar. | Gerar a narração pelo backend da fixture: enviar ação com resposta atrasada (`page.route` com delay), rolar com a roda durante o "pensando" e conferir `scrollTop` inalterado quando a narração chega. Incluir uma variante com movimento ligado. Obrigatório antes de pousar a R1.2. |
| P2-1 | P2 | `api.py:3025-3033` | O ramo pós-combate usa `phase == "ended" or _combat_result(state)`. O `or` é redundante (`result_view` já exige `phase == "ended"`), e o `registro_rodada` segue na view em **todo** turno depois do conflito, até o próximo. Não aparece na tela (o front filtra por `combatResult`), mas não é o "enquanto `combat_result` for o do conflito que acabou" da R4.1. | Trocar por `_combat_result(state)` (o turno de término e o reload antes de "Continuar") e acrescentar ao `test_spec354_final_round_view.py` um caso de turno seguinte sem `registro_rodada`. |
| P2-2 | P2 | `web/e2e/spec354-pos-combate.spec.ts:36` | `cont.scrollIntoViewIfNeeded()` antes de `measure`: quebra a regra de medição (§2) que a R4.5 pede para "Continuar". | Medir sem rolar. Se "Continuar" não couber sem rolar, aplicar o R8 da 347 (o desfecho rola para a vista) e medir depois dele. |
| P2-3 | P2 | `web/src/workspace/ChatSurface.tsx:107`; `web/src/workspace.css:515` | O toast no fluxo encolhe o `.story` (`flex`) depois de o Livro ter rolado para o fim. Com `overflow-anchor: none` e sem a R1.2, as últimas ~1–2 linhas descem para fora da área visível por 4,5 s. Não estão cobertas, mas não aparecem. A R7.2 contava com a R1.2. O `toast_nao_cobre_livro_1440` só mede interseção. | Junto com a R1.2: o `ResizeObserver` do modo preso ao fim também segura o encolhimento pelo toast. Acrescentar ao R7.3 que a última `.msg` continua intersectando a área visível do `.story` com o toast à vista. |
| P2-4 | P2 | `web/src/workspace/Workspace.tsx:168-169` | `lastNarration` pula a narração em fluxo e pega a **anterior**. Durante o stream (ou se a narração final falhar), "O desfecho" mostra o texto de antes do combate. A R4.3 diz: "Sem narração (ainda em fluxo, ou erro), a seção não aparece". | Pegar a última entrada de narrador. Se ela estiver em `streaming`, ou se for anterior ao turno do resultado (`combat_result`/`turn_outcome.turn`), devolver `undefined`. |
| P2-5 | P2 | `web/src/combat/displayName.ts:30-33` | A busca procura no `party` primeiro, inclusive para **inimigo**, e casa pelo 1º nome (`split(/\s+/)[0] === guess`). Um inimigo `enemy_lobo_1` com nome cru casaria com o aliado "Lobo Cinzento". | Na busca de inimigo, pular o `party` (passar `ctx` sem `party` no ramo de inimigo de `buildParticipants`) ou exigir igualdade do nome completo humanizado. |
| P2-6 | P2 | `web/src/components/combat/RoundBoard.tsx:58` | O `sr-only` anuncia "N jogadas" contando também os efeitos. | Usar `plays.length` e, se houver efeitos, acrescentar "e M efeitos". |
| P2-7 | P2 | spec §9 / `docs/spec354/depois/` | Faltam o smoke real (§6), os prints `*-reaberto` e `*-pos-combate` (`depois/` tem 3 de 7) e o e2e `retrato_marcador_sem_flag`. A R6.3 pedia um "registro falso que falha se chamado", e ele não foi feito (risco baixo: não há registro passado hoje). | Completar antes do `done`. Os critérios de aceite da §5 estão todos desmarcados. |

Sem achado em: guard de structured output (nenhuma chamada LLM nova), valor do LLM sem validação (não há), writer persistente (nenhum; a mudança é só de view), segredo em log ou fixture (`save-real.json` sem e-mail nem token), `evals/` (intocado).

## Correções aplicadas

Re-revisão em `495e36ee` (commits `375e07e4..495e36ee`, depois do rebase sobre a SPEC-353):

| Achado | Commit | Conferido |
|---|---|---|
| P1-1 | `375e07e4` | **Resolvido.** A causa real: `useTypewriter(plain, entry.streaming, …)` recebia `undefined` nas entradas do histórico, e o default `enabled = true` fazia **toda** entrada reaberta ser redigitada com o movimento ligado. Somado a isso, cada entrada assinava os próprios listeners em `useEffectsEnabled`, o que dava o "Maximum update depth". Correções: `entry.streaming === true` (`StoryLog.tsx:155`), uma assinatura compartilhada em `design/motion.ts` e a R1.2 (modo preso ao fim, `ResizeObserver` em `.log`/`.story`, solta só com gesto, `StoryLog.tsx:37-94`). `reabrir_save_real_1440/390` rodam com `no-preference`. Com movimento ligado + `SPEC354_COMBAT=1` + `SPEC354_SLOW=1`: 1440 `24288/24768` (gap 0) e 390 `30394/30885` (gap 0), sem erro de console. |
| P1-2 | `9917595e` | **Resolvido.** O R3.4 e o `arena_tres_zonas_1440` agora medem com retrato marcador nos 2 inimigos. O retrato passa a ocupar 3 linhas, e as tags e o presságio usam a largura toda (`workspace.css:523-526`, só `var(--…)`). Os dois verdes, também com movimento ligado. |
| P1-3 | `375e07e4` | **Resolvido.** `subir_e_receber_narracao_nao_puxa_{movimento_ligado,movimento_reduzido}` usa a narração real do backend da fixture (`delayStream`/`releaseStream`), um gesto de roda durante a espera e `scrollTop` inalterado depois que a narração chega. |
| P2-1 | `58032dcc` | **Resolvido.** Um caminho só em `api.py` (`_final_board` = inativo + `last_round_board` + `_combat_result(state)`), junto com a R54 da 353. O `test_spec353_misc.py::test_view_keeps_round_board_after_conflict_ends` ganhou `result`/recibo e o caso "turno seguinte sem registro". **Desvio a registrar:** a R54 da 353 dizia "quando `last_round_board` existe, com ou sem pilhas". Agora vale só no turno de término e no reload antes de "Continuar". O front já filtrava por `combatResult`, então ninguém perde nada visível, mas o texto da 353 R54 e a §9 da 354 devem registrar isso. |
| P2-2 | `031ecb59` | Resolvido: o `scrollIntoViewIfNeeded` saiu, e "Continuar" é medido sem rolar, verde a 390 e a 1440. |
| P2-3 | `375e07e4` | Resolvido: o `ResizeObserver` no `.story` segura o encolhimento pelo toast. Teste `ultima_linha_visivel_com_toast` (gap ≤ 48, última `.msg` visível). |
| P2-4 | `031ecb59` | Resolvido: só a última entrada do Livro, e só se for narração pronta (`Workspace.tsx:168-171`). |
| P2-5 | `031ecb59` | Resolvido: no ramo de inimigo, `displayName` roda sem `party`/`npcs` (`Arena.tsx:17,31`). Teste SSR novo. |
| P2-6 | `031ecb59` | Resolvido: "N jogadas e M efeitos". |
| P2-7 | `031ecb59`/`495e36ee` | Parcial. Os 8 prints estão em `depois/`. A R6.3 tem o teste com `_enemy_portrait` sem `registry`/`quote_price` (o `Boom` nunca é passado, então é guarda de assinatura, suficiente). O `retrato_marcador_sem_flag` mora em `spec354-prints.spec.ts`, que fica em `skip` sem `RPG_SPEC354_PRINTS`. A cobertura de gate vem do R3.4 e do 347 com marcador. O smoke real (§6) segue pendente. |
| extra | `031ecb59` | `fora_de_combate` (motivo novo da 353 R37, `services/combat_targeting.py:115`) entrou em `InvalidReason`/`REASON_TEXT` com teste `spec354-reason.test.mjs`. OK. |


## Pendências

Follow-ups da re-revisão (nenhum bloqueia o pouso; os dois primeiros antes do `done`):

- **F-1 (P2, executor/coordenador): a §9 da spec está desatualizada.** Ainda diz "R1 — NÃO reproduzido; nenhuma correção feita" e "Não feito: R1.2…", enquanto os critérios da §5 estão marcados (inclusive "vermelho registrado na §9 + causa real"). Atualizar a §9 com: o vermelho (1440 `4475/21738`, 390 `3788/30885`, com movimento ligado), a causa real (redigitação do histórico + assinatura por entrada), R3.3 com o retrato em 3 linhas, o desvio da 353 R54 e o R6.3.
- **F-2 (coordenador):** smoke real (§6). O critério segue `[ ]`.
- **F-3 (P2):** com `SPEC354_COMBAT=1`, os testes R7/toast de `spec354-livro` caem por timeout no `#composer`, que fica travado no Baralho. É limitação da sonda opcional, não do produto. Pular esses testes quando a variável estiver ligada.
- **F-4 (nit):** `position_initial_atBottom` (`StoryLog.tsx:17`) em snake_case. Renomear ou embutir.

Da 1ª rodada:

- P1-1/P1-3 reabrem a Etapa 1 (R1.1 vermelho com movimento ligado → R1.2). O "Maximum update depth exceeded" já existe na `main`: se a causa sair do escopo do Livro, abrir follow-up próprio.
- Contrato `tipo`/`efeito` com a SPEC-353: o front aceita a ausência. Nada a fazer aqui.

## Comandos rodados

```text
py.sh -m pytest tests/test_spec354_final_round_view.py tests/test_spec354_portrait_always.py tests/test_spec347_creature_art.py tests/test_api_jogadas.py -n 2 → 49 passed
py.sh -m pytest (12 arquivos de view/combate que chamam _combat_block) -n 2 → 250 passed, 4 skipped
node --test tests/*.test.mjs → 271 pass, 0 fail ; npm run lint → rc 0
playwright --project=chromium --workers=1 spec354-{desktop,mobile,pos-combate,livro} spec347-{desktop,retrato,mobile} combat-outcome deck-342-baseline livro → 42 passed
playwright --project=mobile-390 -g M05 → 1 passed
playwright spec354-livro com reducedMotion "no-preference" (config temporária no scratchpad), branch → 3 failed (gap 16806 / 6519–26609; Maximum update depth)
idem na main 1b769c9f (worktree temporário, removido) → mesmos vermelhos: o defeito é anterior à branch
sonda R3.4 com retrato marcador nos 2 inimigos (cópia no scratchpad) → 1ª carta y 835 h 117, inView false
```

Re-revisão (`495e36ee`):

```text
py.sh -m pytest (spec354_final_round_view, spec354_portrait_always, spec347_creature_art, spec353_misc, api_jogadas, spec345_combat_view, spec342_scene_view, combat_targeting, encounter_manifest, conflito16_frontend) -n 2 → 118 passed
node --test tests/*.test.mjs → 274 pass, 0 fail ; npm run lint → rc 0 ; npm run build → ok
playwright --project=chromium --workers=1 spec354-{desktop,mobile,pos-combate,livro} spec347-{desktop,retrato,mobile,board-only} combat-outcome deck-342-baseline livro → 53 passed (baseline 342 sem regerar)
playwright com reducedMotion "no-preference" (config temporária no scratchpad): spec354-{desktop,mobile,pos-combate,livro} livro spec347-desktop combat-outcome → 25 passed
idem, só spec354-livro com SPEC354_COMBAT=1 SPEC354_SLOW=1 → reabrir 1440/390 verdes (gap 0); 3 testes R7/toast caem por timeout no #composer travado em combate (F-3)
```
