# SPEC-342 — Cartas: acabamento do front do combate por cartas (destrava as flags)

> **Status:** `approved` (dono, 27/10: "destrave isso"; as escolhas abertas estão em §8 com a recomendação adotada)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-321, 322, 323, 324 (`done`: toque, tokens, voz, headings/atalhos); SPEC-328, 329, 331, 333, 334 (`in-progress`, pousadas atrás de flag `off`). Esta spec fecha as pendências de front da 334 (§5 "Conferido em 390/1440", R1 faixa da 331, R7 medição) e a lacuna de UI da 331 (P1-3 já expõe dados que o front ignora).
> **Desbloqueia:** `RPG_CARD_DECK=on` no staging e, em seguida, `RPG_ENEMY_INTENT`, `RPG_SCENE_CARDS`, `RPG_CARD_REWARDS` e `RPG_COMBAT_NONLETHAL` em conjunto com o deck.
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — os Playwright daqui são testes de produto (`web/e2e/`, fora de `evals/protected-paths.txt`), escritos pelo executor e conferidos pelo revisor.
> **Precisa de backend:** **sim, pequeno e atrás de flag** — (a) bloco `cena` na view de combate (R2); (b) "Sem matar" vale para todas as jogadas da rodada (R1). Nenhuma chamada LLM nova.

Rótulos: **[F]** fato no source (worktree `rpg-spec-342`, `main` pós-SPEC-339) · **[R]** recomendação · **[D]** decisão tomada (ver §8).
Insumo único dos problemas: [docs/spec342/achados-auditoria.md](../docs/spec342/achados-auditoria.md) (F-1..F-14, T-1..T-16). Cada achado foi conferido no source abaixo.

---

## 1. Contexto & Objetivo

[F] O combate por cartas (328–336) está pousado atrás de flags `off`. Com `RPG_CARD_DECK=on`, a aba Combate troca `CardHand` por `DeckCombat` (`web/src/workspace/tabs/CombateTab.tsx:97,232-235`, `deckMode = !!combat?.pilhas`). Duas auditorias só-leitura (lentes *impeccable* e *taste*) encontraram 3 bloqueantes funcionais, 1 regressão de toque, um fluxo de alvo duplicado e um mobile pesado demais. A SPEC-334 ficou `in-progress` justamente por falta da conferência em 390/1440 e da faixa de cena.

[F] Os bloqueantes: (1) o chip "Sem matar" aparece e alterna no modo Baralho, mas "Encerrar turno" não o envia (golpe não-letal inerte, regressão off→on); (2) as Cartas de Cena, o Objetivo e o Relógio do Abismo (331) não aparecem: a API já manda `pressagios_cena` e `objetivo` (`api.py:2959-2964`), mas o front não tem nem o tipo (`web/src/types.ts:376-395`) e `SceneStrip` só recebe `round` (`DeckCombat.tsx:123`); (3) existem dois fluxos de alvo (Arena + `aimbar` para manobras; chips `deck-target` para cartas); (4) no celular a aba empilha 10+ blocos.

Objetivo: deixar o combate por cartas **claro, tocável e coerente com a casca da 321–324**, sem mudar nada visível no caminho `off`, para que o dono ligue as flags no staging. Princípio: *mecânica é Python*; o front só mostra o que a API manda (nenhuma regra de jogo duplicada no cliente, exceto a fila local já existente).

## 2. Requisitos

Cada requisito cita os achados que fecha. Todo texto de interface está em §8 (D-342-7, tabela de microcopy) e é **literal** (os testes assertam as strings).

### Etapa 1 — bloqueantes (F-1, T-1, T-2, T-3, F-2, F-3)

- **R1 — "Sem matar" funciona no Baralho (F-1).** [F] `CombateTab.tsx:235` monta `onEnd` sem `SPARE_TEXT`/`spareOn` (compare com `:147,154`); no servidor `_mark_nonlethal` só marca `decl.acao` (`agents/combat.py:130-143,2049`), isto é, a 1ª jogada.
  - R1.1 — Com `spareOn`, o texto enviado por "Encerrar a rodada" termina com `Sem matar.` (`SPARE_TEXT`, que `death_flow.NONLETHAL_RE` reconhece) e `spare` volta a `false` depois do envio.
  - R1.2 — No modo Baralho, o chip "Sem matar" sai do `<details>` de manobras e fica na barra de envio, ao lado de "Encerrar a rodada" (`aria-pressed`). Enquanto estiver ligado, a fila mostra a nota "Nesta rodada, golpes derrubam sem matar.".
  - R1.3 — **Backend:** `_mark_nonlethal` marca `params["nao_letal"]` em **toda** jogada `attack`/`card` de `decl.jogadas` (não só em `decl.acao`). Com a flag `nonlethal` `off`, nada muda.
- **R2 — Faixa de cena visível (T-1).** [F] A API manda `pressagios_cena` (só a previsão da próxima rodada, `services/scene_cards.py:314-338`) e `objetivo` (`public_objective`, `:733-760`), mas **não** manda a lista das Cartas de Cena ativas nem o estado do Relógio (`ABYSS_CLOCK_START=5`, `ABYSS_CLOCK_HARD_CAP=12`, `:32-33`; disparo em `conflict_orchestrator.py:2286-2291,2540` com `cs.tactical_round(scene)`).
  - R2.1 — **Backend:** com `scene_cards.active()`, a view de combate ganha `cena = {cartas: [{id, nome, sabor}], relogio: {desde, teto, rodada, ativo}}`. `cartas` vem de `scene_cards_of(scene)` (0–2), **sem** `efeitos`/`acoes`/`quando`/`n`. `rodada` = `cs.tactical_round(scene)` (o mesmo contador do motor); `ativo = rodada >= desde`. Com a flag `off`/`shadow`, a chave não existe (payload idêntico ao de hoje).
  - R2.2 — `web/src/types.ts`: `CombatBlock` ganha `pressagios_cena?`, `objetivo?` e `cena?` (tipos em §3).
  - R2.3 — `SceneStrip` vira um `<details className="scene-strip">`. O `summary` é uma linha só: `Rodada N` · nomes das Cartas de Cena · objetivo curto · estado do Relógio. O corpo traz o `sabor` de cada carta, o objetivo por extenso e a regra do Relógio. É 1 elemento interativo no total.
  - R2.4 — O presságio de cena da próxima rodada fica **fora** do `details`, sempre visível, numa linha com ícone (`abyss` quando `quando === "relogio"`, `warning` nos outros casos) e o texto `pressagio` da API.
  - R2.5 — Sem `cena`, sem `objetivo` e sem `pressagios_cena` (scene cards `off`), a faixa mostra só `Rodada N`, como hoje, e não vira `details`.
- **R3 — Um só fluxo de alvo (T-2).** [D-342-2] A Arena é o **único** lugar para escolher alvo, tanto para manobra quanto para carta do Baralho.
  - R3.1 — Os chips `.deck-target [data-target-pick]` (`DeckCombat.tsx:127-148`) deixam de existir.
  - R3.2 — Armar uma carta que pede alvo marca na Arena os alvos válidos (`aimMarks`, como em `CombateTab.tsx:107-117`). Isso vale para `alvo: "aliado"` também (o jogador e o grupo ficam válidos). Tocar num alvo válido fixa o alvo.
  - R3.3 — Uma única `aimbar` (a de `CombateTab.tsx:226-231`) serve a carta e a manobra. Antes do alvo: "Mirando {carta}: escolha o alvo na arena." + Cancelar. Depois do alvo: prévia (R7) + "Jogar em {alvo}" + "Outro alvo" (este só com mais de 1 alvo válido).
  - R3.4 — Armar uma carta cancela a mira de manobra, e vice-versa. Esc e "Cancelar" desarmam os dois.
  - R3.5 — Com 1 alvo válido só, o alvo é fixado direto (comportamento atual de `DeckCombat.tsx:83`) e o foco vai para "Jogar em {alvo}".
- **R4 — Mobile enxuto (T-3; fecha a medição pendente da SPEC-334 R7).** A 390×844 (`isMobile`, `hasTouch`), em combate no modo Baralho com 2 inimigos, 5 cartas na mão e a fila vazia:
  - R4.1 — Ordem dos blocos: faixa de cena → presságio de cena → Arena (com presságios, R8) → mão (o título traz o Fôlego, R11) → `aimbar` (só com carta armada) → fila → barra de envio → reação → Manobras (fechado) → Dados da rodada (fechado). Saem como blocos próprios: `EnemyStrip`, a linha de `FolegoPips` e `.deck-target`.
  - R4.2 — No máximo **12** elementos interativos visíveis em `.ws-combat`. Visível = renderizado, fora de `details` fechado e com a caixa cruzando a largura do viewport (o trilho rolável conta só as cartas à vista). Rolar na vertical é permitido.
  - R4.3 — Em `max-width: 640px`, a barra de envio (`.play-queue__end`: Sem matar + Encerrar a rodada + Desfazer) é `position: sticky; bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom))`, com `z-index: var(--z-hud)`, e fica visível ao rolar a aba.
  - R4.4 — Na primeira pintura da aba (painel no topo), a 1ª `.deck-card` aparece inteira no viewport.
- **R5 — Piso de toque no Baralho (F-2; regressão da 321 R7).** [F] A regra `@media (pointer: coarse)` em `web/src/workspace.css:283-293` não cobre os controles novos (`:323,326,341,346,349,350,352` usam 2.2–2.6rem). Em `pointer: coarse`, estes controles ficam com caixa ≥ 44×44 px: `.deck-hand__piles`, `.deck-hand__list button`, `.play-queue__item`, `.play-queue__ops button`, `.play-queue__clear`, `.play-queue__submit`, `.mech-log summary`, `.ws-combat__fold summary`, `.scene-strip summary`, o chip "Sem matar" na barra e os botões da `aimbar`. A área pode crescer por padding ou `::before` (321 R7).
- **R6 — Regras das palavras-chave sem corte (F-3).** [F] `.kw__tip` é `position: absolute` dentro de `.deck-hand__rail` com `overflow-x: auto` (`workspace.css:329,332-333`; `KeywordTip.tsx:18`). Fica cortado e sai da tela a 360 px.
  - R6.1 — Com ponteiro fino, o tooltip é renderizado em portal (`document.body`), `position: fixed`, posicionado pela caixa da palavra e limitado ao viewport (margem de 8 px), com `z-index: var(--z-toast)`.
  - R6.2 — Com toque, não há tooltip. As regras aparecem na `aimbar` (R9.1).

### Etapa 2 — clareza, voz e a11y (T-4..T-10, T-12, F-4..F-8)

- **R7 — Hierarquia visual (T-4).** [F] `.enemy-strip`, `.preview-chip`, `.play-queue` e `.deck-hand__piles` são caixas iguais de 1px (`workspace.css:310,323,335,337`). A prévia, que é a informação que decide a jogada, está em 0.9rem.
  - R7.1 — A prévia perde a borda. O número da chance usa `var(--display)` em 1.25rem com `font-variant-numeric: tabular-nums`, e o resto da linha usa o corpo. O rótulo passa a ser "Seu golpe" (D-342-7).
  - R7.2 — A fila perde a caixa (fica só um filete superior `var(--line-soft)`). O botão de pilhas vira botão de texto (`.btn--ghost` sm).
  - R7.3 — "Encerrar a rodada" é a única ação primária da aba: `.btn.btn--primary` (322 R10), com o número de cartas como sublinha ("2 cartas"), e não mais "(N)" junto com "Enter" no rótulo (T-9). O atalho fica em `aria-keyshortcuts` + `title`.
- **R8 — Presságio com ícone e número, dentro do chip do inimigo (T-5, T-6).** [D-342-3] [F] Hoje o presságio é só texto numa faixa própria (`EnemyStrip.tsx:11`, `deck.ts:106-111`).
  - R8.1 — No modo Baralho, `Arena` recebe `omens` e cada chip de inimigo mostra uma linha de presságio: ícone por `tipo` (mapa em §3, só com ícones que já existem em `design/icons.tsx`, sem SVG novo), o `sinal` e o número em `tabular-nums` (`~6` ou `4–8`). A carta aparece só quando `carta_nome` vier.
  - R8.2 — O nome acessível do chip inclui o presságio por extenso.
  - R8.3 — Se `pressagios_publicos` existir (flag `on`) e um inimigo ativo não tiver entrada, ou vier com `tipo === "desconhecido"`, o chip mostra "Intenção velada" com o ícone `dark` (T-6). Se `pressagios_publicos` não existir, não aparece nada (sem ruído com a flag `off`).
  - R8.4 — Fora do modo Baralho, `Arena` não recebe `omens` e fica idêntica.
- **R9 — Afordância de regras e custo (T-7, F-9).**
  - R9.1 — [D-342-4] Com toque (`touch`), tocar numa carta sempre a **arma**, inclusive `alvo: "si"`. A `aimbar` mostra então o texto da carta e, abaixo, uma linha por palavra-chave ("**Sangria**: …"), mais "Jogar" (ou o alvo, R3). Não há mais toque longo: saem o timer de 450 ms e o `onContextMenu` de `KeywordTip.tsx:12-17`.
  - R9.2 — Em `pointer: coarse`, `.deck-card` usa `-webkit-touch-callout: none; user-select: none`.
  - R9.3 — Com mouse/teclado, cartas `si` continuam indo direto para a fila (sem passo extra).
  - R9.4 — Custo de Fôlego por extenso: na carta, os pips ganham o numeral visível ao lado ("●● 2"). O bloco de Fôlego do título da mão mostra "Fôlego 2 de 3" em texto, e os pips viram `aria-hidden` (o texto é a fonte acessível).
- **R10 — Voz de Valoria no texto de sistema (T-8, F-13).** Toda string de `BLOCK_TEXT` (`deck.ts:35-41`), `PreviewChip.tsx:9-10,14`, `MechLog.tsx:6`, `PlayQueue.tsx:21,49,53`, os anúncios de `DeckCombat.tsx:77,82,96,114` e a `aimbar` do Baralho passam a usar exatamente as strings da tabela D-342-7.
  - R10.1 — No modo Baralho, a unidade de tempo é sempre **rodada**: nenhuma string visível dos componentes de `web/src/components/combat/` contém "turno".
  - R10.2 — O texto enviado ao servidor passa a ser `Encerro a rodada: {cartas}.` (+ ` Sem matar.`). É a marginália da jogada (SPEC-323 R1, 1ª pessoa). O servidor não depende desse texto: a semântica vem de `jogadas`.
- **R11 — Pilhas e Exaurida explicadas (T-12).** O botão mostra `Pilhas` + o ícone `caret-down`/`caret-up` conforme `aria-expanded`, com as contagens numa sublinha `--faint` ("Compra 12 · Descarte 3 · Exaurida 1"). A lista aberta mostra, sob a aba Exaurida, a nota da tabela D-342-7.
- **R12 — Famílias de botão e cartões (T-10).**
  - R12.1 — Na aba Combate: ação primária = `.btn--primary`, secundárias fora de luta = `.btn--ghost` sm, e `.actionchip` só para manobra, alvo e chips de luta.
  - R12.2 — As ofertas do Espólio usam o `.combat-card` único (322 R10), como `article` (não `button`), com o botão "Levar {carta}" dentro.
  - R12.3 — Forja: a linha do Baralho é selecionável (`aria-pressed`), e **uma** barra de ações abaixo da lista age sobre a carta selecionada. Os botões deixam de se repetir em cada linha. Afiar e Purgar seguem o mesmo padrão.
- **R13 — Nome acessível completo da carta (F-4).** [F] `Hand.tsx:51-52` troca o conteúdo pelo `aria-label`, e o texto da carta só chega ao leitor de tela quando há palavra-chave (`:46,51,62`). Toda `.deck-card` tem `aria-describedby` apontando para um `sr-only` com o texto da carta sem `**`, as regras das palavras-chave (se houver) e o motivo de bloqueio (se houver). O `aria-label` fica com nome + custos.
- **R14 — Contraste do motivo de bloqueio (F-5).** [F] `.deck-card.is-dim { opacity: .5 }` (`workspace.css:330`) apaga também o motivo. A opacidade passa a valer só para `.combat-card__name`, `.combat-card__desc` e os pips. `.combat-card__state` fica com opacidade 1 e cor `--muted` ou mais forte (≥ 4,5:1).
- **R15 — Foco e anúncio (F-6).**
  - R15.1 — Armar carta com vários alvos: o foco vai para o 1º alvo válido da Arena e o anúncio diz "Mirando {carta}: escolha o alvo na arena.". Com 1 alvo, o foco vai para "Jogar em {alvo}".
  - R15.2 — "Encerrar a rodada" durante `busy` usa `aria-disabled="true"` (não `disabled`), mantém o foco e ignora o clique.
  - R15.3 — Remover um item da fila move o foco para o item seguinte, ou para o anterior, ou para a 1ª carta da mão se a fila ficar vazia.
  - R15.4 — Na troca de rodada (`roundKey`), o foco só vai para a 1ª carta se ele já estava dentro de `.deck-combat`.
- **R16 — Mão vazia ou toda bloqueada (F-7).** [F] `Hand.tsx:42-65` não tem estado vazio, e a única saída fica num `details` fechado (`CombateTab.tsx:33-36`).
  - R16.1 — Mão vazia, ou todas as cartas com `reason`: aparece o aviso da tabela D-342-7 (`role="note"`), e o `details` "Manobras e ações" abre sozinho (`open`). O jogador pode fechá-lo, e ele não reabre na mesma rodada.
- **R17 — Confirmação na Forja (F-8).** [F] Esquecer, Esquecer no templo (ouro) e Tratar/Purgar disparam no 1º clique (`ForjaPanel.tsx:43-49,76-81`). Toda ação que remove carta ou custa ouro pede um 2º passo **inline**: o botão vira a frase de confirmação + "Confirmar" + "Cancelar", sem modal. Esc ou "Cancelar" desfaz e devolve o foco ao botão original. "Afiar" não pede confirmação (só consome material e é anunciado).

### Etapa 3 — polimento (P3: F-9..F-14, T-11, T-13..T-16)

- **R18 — Atalhos só com a aba visível e listados (F-10).** [F] Os painéis já visitados ficam montados com `hidden` (`ContextSurface.tsx:93-104`), então o `keydown` global de `DeckCombat.tsx:103-119` vale com a aba oculta.
  - R18.1 — O handler sai sem agir se `rootRef.current` estiver dentro de um ancestral `[hidden]` ou tiver `offsetParent === null`.
  - R18.2 — `ShortcutsSheet` ganha a seção "No combate com Baralho" (strings na tabela D-342-7), renderizada **só** quando a partida atual tem `combat.pilhas`. Com a flag `off`, a folha fica idêntica.
- **R19 — Espólio com glossário e sinal fora da aba (F-11/T-11).** [F] `EspolioPanel.tsx:12,46` usa `NO_GLOSSARY`.
  - R19.1 — Um hook `useGlossary()` (com cache em módulo, 1 fetch por sessão) serve `DeckCombat` e `EspolioPanel`.
  - R19.2 — Com `espolio_pendente` e a aba Combate inativa, a aba (`ContextSurface`) e o botão do `MobileTabBar` ganham a classe `has-loot` (um ponto `--accent`) e o sufixo acessível " — espólio à espera".
- **R20 — Fôlego legível (F-12/T-14).** [F] Vazio e reservado se distinguem só pela opacidade (`workspace.css:314-316`). Por isso, livre = disco cheio `--accent`; reservado = anel `--accent` de 2px sem preenchimento; vazio = anel tracejado `--field-border` (≥ 3:1, 322 R3). O `role="status"` do Pacto fica sempre montado (vazio quando `borrowed === 0`), para que o texto seja anunciado ao aparecer.
- **R21 — Headings e escala (F-14, T-16).** [F] O painel já tem `h2` (`ContextSurface.tsx:103`), e "Sua mão", "Espólio" e "Forja do Baralho" também são `h2` (`Hand.tsx:22`, `EspolioPanel.tsx:34`, `ForjaPanel.tsx:35`).
  - R21.1 — Os três passam a `h3`, com o estilo de rótulo de seção da 324 R1 (`--label` small caps, piso 0.8rem; 322 R8). "Afiar" e "Cicatrizes no Baralho" passam a `h4`. Nenhum nível é pulado (axe `heading-order` limpo).
  - R21.2 — `.espolio__title`/`.forja__title` deixam o `1.1rem` solto.
- **R22 — Trilho da mão no celular (T-13).** [F] `.deck-hand__rail` usa `72vw` em ≤ 640px (`workspace.css:354-356`), e `.combat-card` herda `min-height: 185px` (`styles.css:1073`).
  - R22.1 — Em ≤ 640px, o trilho usa `grid-auto-columns: minmax(9.5rem, 46vw)` (≈ 2 cartas à vista a 390).
  - R22.2 — `.deck-card` usa `min-height: auto`, e o texto da carta fica limitado a 3 linhas (`line-clamp`). O texto inteiro segue em R13/R9.1.
- **R23 — Dados da rodada (T-15).** `MechLog` mostra no `summary` "Os dados da rodada {N}". Cada linha vira `<li>` com o ator (o trecho antes do 1º ` · `) em `--label` e o resto em `tabular-nums`. O separador por rodada é esse cabeçalho (a API manda só a última rodada, `agents/combat.py:2332-2334`).

### Transversais

- **R24 — Caminho `off` sem mudança visível.** Sem `combat.pilhas`, sem `cena`, sem `pressagios_*`, sem `espolio_pendente`/`forja`: os screenshots Playwright a 360×740, 390×844 e 1440×900 (fora de combate, em combate e no desfecho) batem com a linha de base capturada **antes** da Etapa 1, com `maxDiffPixelRatio` ≤ 0,01 (mesmo limiar da 324 R2).
- **R25 — Só tokens da 322.** Todo CSS novo ou alterado usa só `var(--…)` definidos em `web/src/design/tokens.css`/`styles.css :root`. Sem hex/rgb, sem raio literal (`npm run lint`, stylelint da 322 R6) e sem token novo.
- **R26 — Conferência com flags.** Os prints ficam em `docs/spec342/` (nomes em §5) a 360, 390 e 1440 px, com flags on (payload com `pilhas`, `pressagios_publicos`, `cena`, `objetivo`, `pressagios_cena`, `nonlethal_available`, `espolio_pendente`, `forja`) e off.

### Fora de escopo

- R9 da SPEC-334 (mostrar a fila resultante do texto livre antes de enviar): exige endpoint de parse e fica para outra spec.
- Arte de carta, animações novas além das de `motion` já usadas, mapa visual de zonas.
- Mudança de regra de jogo, de cálculo da prévia, de catálogo de Cartas de Cena ou de presságio. Fora R1.3 e R2.1, nada muda no backend.
- Ligar as flags no staging. Isso é ato do coordenador/dono depois do `done`: esta spec só destrava.
- Reescrever `CardHand`/caminho `off` ou o `CombatTab` do HUD.
- Calibração da arena (339/341) e balanço por Postura.

## 3. Design técnico

**Arquivos alterados (front)**

| Arquivo | Mudança | Requisitos |
|---|---|---|
| `web/src/types.ts` | `CombatBlock.pressagios_cena?`, `objetivo?`, `cena?` (abaixo) | R2.2 |
| `web/src/workspace/tabs/CombateTab.tsx` | estado do Baralho armado sobe para cá (`useDeckArm`); `aimMarks`/`pick` servem carta e manobra; `aimbar` única; "Sem matar" na barra de envio e `SPARE_TEXT` no `onEnd`; `ManeuverFold` controlado (`open`) | R1, R3, R16 |
| `web/src/combat/useDeckArm.ts` (**novo**) | `{armed, arm(index, targets), setTarget(id), disarm()}`, puro de React (sem fetch); exclusão mútua com `useTargeting` | R3.4 |
| `web/src/components/combat/DeckCombat.tsx` | vira controlado (`armed`, `onArm`); sem `.deck-target`; foco/anúncio; guarda de aba oculta; texto `Encerro a rodada: …` | R3, R10, R15, R18.1 |
| `web/src/combat/Arena.tsx` + `TargetChip` | prop opcional `omens?: Record<string, OmenView>` (só no Baralho) | R8 |
| `web/src/components/combat/SceneStrip.tsx` | `details` com cena/objetivo/relógio + linha de presságio de cena | R2.3–R2.5 |
| `web/src/components/combat/EnemyStrip.tsx` | removido do Baralho; a lógica de `pressagioLine` vira `omenView()` em `deck.ts` | R4.1, R8 |
| `web/src/components/combat/Hand.tsx` | `h3`; Fôlego no título; `aria-describedby` sempre; `is-dim` restrito; aviso de mão vazia; botão Pilhas | R9.4, R11, R13, R14, R16, R21 |
| `web/src/components/combat/KeywordTip.tsx` | portal `fixed` (mouse); sem toque longo | R6, R9.1 |
| `web/src/components/combat/PreviewChip.tsx` | "Seu golpe", número em `--display` | R7.1, R10 |
| `web/src/components/combat/PlayQueue.tsx` | `.btn--primary`, `aria-disabled`, foco ao remover, nota "sem matar", barra sticky | R1.2, R4.3, R7, R15 |
| `web/src/components/combat/FolegoPips.tsx` | estados por forma; `status` sempre montado; texto "Fôlego N de M" | R9.4, R20 |
| `web/src/components/combat/MechLog.tsx` | título e linhas com ator | R23 |
| `web/src/components/combat/EspolioPanel.tsx` / `ForjaPanel.tsx` | `h3`/`h4`; `.combat-card`; glossário; confirmação inline; barra única da Forja | R12, R17, R19, R21 |
| `web/src/combat/useGlossary.ts` (**novo**) | cache de módulo de `api.getGlossary()` | R19.1 |
| `web/src/combat/deck.ts` | `BLOCK_TEXT` novo; `previewParts()`; `omenView()`; `objectiveLine()`; `clockLine()`; `endText(queue, spare)`; `OMEN_ICON` | R2, R8, R10 |
| `web/src/workspace/ContextSurface.tsx`, `components/MobileTabBar.tsx` | `has-loot` | R19.2 |
| `web/src/components/ShortcutsSheet.tsx` | seção condicional do Baralho | R18.2 |
| `web/src/workspace.css` | bloco coarse (R5), tooltip, sticky, hierarquia, pips, trilho, `is-dim`, títulos — só tokens | R4–R7, R14, R20–R22 |

**Arquivos alterados (backend)**

- `api.py::_combat_block` (perto de `:2959-2964`): dentro de `if _scene_cards.active():`, `view["cena"] = _scene_cards.public_scene(meta.get("scene"))` quando não for `None`.
- `services/scene_cards.py`: nova `public_scene(scene: dict | None) -> dict | None`. Devolve `None` sem `active()` ou sem `dict`. A lista `cartas` pode vir vazia, e o `relogio` vem sempre que `active()`, porque todo conflito tem Relógio (331 R7).
- `agents/combat.py::_mark_nonlethal`: itera `decl.jogadas or [decl.acao]`.

**Tipos (TS)**

```ts
export interface ScenePressagioView { id: string; nome: string; pressagio: string; quando: "inicio_rodada" | "fim_rodada" | "a_cada_n_rodadas" | "relogio"; rodada: number }
export interface SceneObjectiveView { tipo: "sobreviver_n_rodadas" | "proteger" | "alcancar_zona" | "destruir_objeto" | "interromper_ritual" | "capturar_vivo"; alvo_nome?: string; n?: number; rodada: number; resultado: "cumprido" | "falhou" | null }
export interface SceneCardsView { cartas: { id: string; nome: string; sabor: string }[]; relogio: { desde: number; teto: number; rodada: number; ativo: boolean } }
// CombatBlock: pressagios_cena?: ScenePressagioView[]; objetivo?: SceneObjectiveView; cena?: SceneCardsView;
export interface OmenView { icon: IconName; text: string; num: string | null; card: string | null; veiled: boolean; spoken: string }
```

**Formato real (exemplo com ids canônicos)**

```json
"cena": {
  "cartas": [{"id": "nevoa_cinza_do_ermo", "nome": "Névoa Cinza do Ermo",
              "sabor": "No Ermo o frio é o Abismo drenando calor; a névoa que sobe dele apaga os contornos de quem se expõe."}],
  "relogio": {"desde": 5, "teto": 12, "rodada": 3, "ativo": false}
}
```

**Ícone do presságio por `tipo`** (`services/enemy_intent.py:26-36`; só ícones existentes, sem crédito novo):
`ataque → card-active` · `ataque_multiplo → combat` · `defesa → card-reaction` · `reforco_proprio → card-passive` · `enfraquecer → warning` · `mover → arrow-right` · `fugir → exit` · `render-se → blocked` · `desconhecido`/velada `→ dark`. Ícone `aria-hidden`; o texto carrega o sentido.

**Assinaturas puras (testáveis com `node --test`)**

```ts
export function endText(queue: QueuedPlay[], spare: boolean): string;           // "Encerro a rodada: A, B." [+ " Sem matar."]
export function omenView(p: PressagioView | null, name: string): OmenView;       // null → velada
export function objectiveLine(o: SceneObjectiveView): string;                     // strings D-342-7
export function clockLine(r: SceneCardsView["relogio"]): string;                  // strings D-342-7
export function previewParts(p: PreviewResult): { chance: string; rest: string }; // substitui previewLine no chip
```

## 4. Plano passo a passo

Python sempre via `bash scripts/dev/py.sh -m pytest <arquivos> -q` (no máximo `-n 2`). Web: `cd web && npm test` (runner do repo: `node --test tests/*.test.mjs`) e `npm run test:e2e -- <spec> --workers=1`. Antes de mexer em qualquer coisa:

### Etapa 0 — linha de base `off`

1. `web/e2e/deck-342-baseline.spec.ts`: com `DeterministicBackend` sem `pilhas`/`cena`/`pressagios_*`, captura `toHaveScreenshot` a 360×740, 390×844 e 1440×900 (fora de combate, em combate e desfecho). A linha de base é gerada **no commit anterior à Etapa 1** e commitada (snapshots do Playwright). Esse mesmo spec vira o teste de R24.

### Etapa 1 — bloqueantes

1. **Testes primeiro**
   - `tests/test_spec342_nonlethal_jogadas.py`:
     - `test_spare_marks_every_attack_play`: `decl.jogadas=[defesa, ataque]` + texto com "Sem matar." e flag `on` → as duas `attack`/`card` têm `nao_letal`.
     - `test_spare_off_flag_untouched`: flag `off` → nenhum `params` muda.
     - `test_second_card_kill_becomes_down`: integração com o orquestrador; o golpe letal na 2ª jogada derruba sem matar.
   - `tests/test_spec342_scene_view.py`:
     - `test_cena_absent_when_off`: `off` e `shadow` → sem chave `cena` e payload igual ao de hoje.
     - `test_cena_lists_only_public_fields`: chaves exatamente `{id,nome,sabor}`; nenhum `efeitos`/`acoes`/`quando`.
     - `test_relogio_matches_engine_round`: rodar rodadas até `out["abyss_clock"]` aparecer → a view daquele request tem `ativo=True` e `rodada>=5`; antes, `False`.
     - `test_cena_relogio_present_without_cards`: cena sem cartas → `cartas == []` e `relogio` presente.
   - `web/tests/deck-342-logic.test.mjs`:
     - `endText` com e sem `spare` (string exata).
     - `objectiveLine` para os 6 tipos, mais cumprido/falhou.
     - `clockLine`: antes/no limiar/ativo/teto.
     - `omenView`: velada (`null` e `desconhecido`), faixa, valor e carta.
     - `OMEN_ICON` cobre todos os `TIPOS` e só usa chaves de `ICONS`.
   - `web/tests/deck-342-components.test.mjs` (SSR):
     - `SceneStrip` sem dados = "Rodada N" e sem `details`.
     - `SceneStrip` com `cena`/`objetivo`/`pressagios_cena` = `details` + linha de presságio fora dele.
     - `PlayQueue` com `spare` mostra a nota.
     - Nenhum `.deck-target` em `DeckCombat`.
   - `web/e2e/deck-combat-342.spec.ts` (Playwright, fixture com payload `on`):
     - `spare reaches request`: liga "Sem matar", enfileira 2 cartas, encerra → o corpo do POST tem `input_text` terminando em "Sem matar." e `jogadas` com 2 itens; o chip volta a `aria-pressed=false`.
     - `single targeting flow`: armar carta → chips da Arena com `.is-valid`, foco no 1º → escolher → prévia → "Jogar em X" → item na fila; não existe `[data-target-pick]`.
     - `ally card targets allies in arena`.
     - `maneuver and card aim are exclusive`.
     - `scene strip shows cards, objective, clock and next-round omen`.
     - `mobile budget 390`: ≤ 12 interativos visíveis (R4.2) e 1ª carta inteira no viewport (R4.4).
     - `end bar sticky 390`: após rolar até o fim, `[data-end-turn]` está no viewport.
     - `coarse targets ≥ 44`: a 390×844 com `isMobile`/`hasTouch`, toda caixa dos seletores de R5 tem ≥ 43,5 px (mesmo critério da 321).
     - `keyword tip inside viewport 360`: hover em palavra-chave na 3ª carta → caixa do `[role=tooltip]` inteira no viewport e fora de `.deck-hand__rail`.
2. **Implementação:** R1, R2, R3, R4, R5, R6, nessa ordem. O backend (R1.3, R2.1) vai antes do front que o consome.
3. **Verificação:** os testes acima verdes, mais os já existentes do escopo: `tests/test_scene_cards_node.py`, `tests/test_spec325_nonlethal.py`, `tests/test_api_jogadas.py`, `web/tests/deck*.test.mjs`, `web/e2e/combat-gesture.spec.ts`. As strings antigas em `web/tests/deck-components.test.mjs` são atualizadas para as da D-342-7, no mesmo commit (não é eval protegido).

### Etapa 2 — clareza, voz, a11y

1. **Testes primeiro**
   - `deck-342-logic.test.mjs`:
     - `BLOCK_TEXT` e `previewParts` iguais à D-342-7.
     - Nenhuma string exportada de `deck.ts` contém `/turno/i`.
   - `deck-342-components.test.mjs`:
     - `.deck-card` sempre com `aria-describedby`, e o alvo contém o texto sem `**`.
     - `is-dim` não põe opacidade no `.combat-card__state`: confere que a regra CSS tem seletor restrito, por leitura do CSS.
     - Mão toda bloqueada → aviso `role=note`.
     - "Encerrar a rodada" é `.btn--primary`, sem "(N)" e sem "Enter" no texto.
     - Pilhas com `aria-expanded` e a nota de Exaurida.
     - Espólio com `article.combat-card`.
     - Forja: 1º clique em Esquecer mostra a frase de confirmação e não chama `onForge`.
     - Arena com `omens` → ícone e número; sem `omens` → markup idêntico ao de hoje (snapshot de string).
   - `deck-combat-342.spec.ts`:
     - `focus after arm/single target/remove/end busy` (R15).
     - `touch tap arms si card and shows rules in aimbar` (R9.1, `hasTouch`).
     - `all blocked opens maneuvers` (R16).
     - `forge confirm inline + Esc restores focus` (R17).
     - `veiled intent only when intent flag on` (R8.3).
     - axe sem violação `serious`/`critical` em `.ws-combat` a 390 e 1440.
2. **Implementação:** R7–R17.
3. **Verificação:** a mesma da Etapa 1, mais `npm run lint` (stylelint/eslint).

### Etapa 3 — polimento

1. **Testes primeiro**
   - `deck-342-components.test.mjs`:
     - `ShortcutsSheet` com `deck` lista as 3 linhas; sem `deck`, o markup fica igual.
     - `FolegoPips` com `borrowed=0` já tem o `role=status` vazio.
     - Headings: `h3`/`h4` nas posições de R21.
     - `MechLog` com o título "Os dados da rodada N".
   - `deck-combat-342.spec.ts`:
     - `shortcuts inert when combat tab hidden`: com a aba Personagem ativa, a tecla "1" não arma carta.
     - `loot badge on tab` (R19.2).
     - `heading-order` limpo pelo axe.
     - Trilho a 390 com ≥ 2 cartas visíveis (R22).
   - `web/tests/deck-tokens-342.test.mjs`: todo `var(--x)` do bloco SPEC-334/342 de `workspace.css` existe em `tokens.css`/`:root`, e não há literal de cor ou de raio (R25).
2. **Implementação:** R18–R23.
3. **Verificação:** escopo verde; `npm run build`.

### Etapa 4 — conferência e prints (R24, R26)

1. `deck-342-baseline.spec.ts` (off) verde contra a linha de base da Etapa 0.
2. `web/e2e/deck-342-prints.spec.ts` (fora do CI default, `test.skip` sem `RPG_SPEC342_PRINTS=1`) grava em `docs/spec342/` os prints abaixo. O coordenador confere à mão e registra o resultado na §9.

## 5. Critérios de aceite

- [ ] R1–R23 com teste nomeado verde (`node --test`, Playwright e pytest do escopo).
- [ ] R24: screenshots `off` dentro de `maxDiffPixelRatio` 0,01 contra a linha de base pré-Etapa 1, a 360/390/1440.
- [ ] R25: `npm run lint` verde e `deck-tokens-342.test.mjs` verde; nenhum token novo.
- [ ] R5: alvos ≥ 44 px em `pointer: coarse` medidos pelo Playwright.
- [ ] R4.2: ≤ 12 interativos visíveis a 390 (fecha a 334 R7).
- [ ] Prints em `docs/spec342/`: `on-360-combate.png`, `on-390-combate.png`, `on-390-mira.png`, `on-390-fila-sticky.png`, `on-1440-combate.png`, `on-1440-mira.png`, `on-390-espolio.png`, `on-1440-forja.png`, `off-360-combate.png`, `off-390-combate.png`, `off-1440-combate.png`.
- [ ] Axe sem `serious`/`critical` em `.ws-combat` (on) a 390 e 1440.
- [ ] `npm run build` e `npm test` verdes; e2e do escopo `--workers=1` verde.
- [ ] `uv run pytest` verde (suíte completa: coordenador, no pouso).
- [ ] Saves antigos carregam (nenhum campo de save novo; `cena` é só view).
- [ ] Smoke real (§6) executado e registrado.
- [ ] SPEC-334 §5 "Conferido em 390 px e 1440 px" pode ser marcada com os prints daqui (o coordenador atualiza a 334).

## 6. Smoke test com LLM real (staging, flags `on` só na sessão de teste)

Não há structured output novo. O smoke confere que os campos reais chegam ao front e que o não-letal funciona ponta a ponta. São 3–5 requests no provider default (DeepSeek), dentro do orçamento do staging.

1. Preset do staging com `RPG_CARD_DECK=on`, `RPG_ENEMY_INTENT=on`, `RPG_SCENE_CARDS=on`, `RPG_COMBAT_NONLETHAL=on` e `RPG_CARD_REWARDS=on`, numa sessão de teste. Iniciar um conflito num local com Cartas de Cena elegíveis (Ermo ou Skallgard, para cair na *Névoa Cinza do Ermo*). Conferir a faixa: nome da carta, objetivo (se houver) e "Relógio do Abismo: desperta na rodada 5".
2. Ler o presságio no chip do inimigo → armar uma carta → escolher o alvo na Arena → conferir a prévia → "Jogar em X" → mais uma carta → ligar "Sem matar" → "Encerrar a rodada". Conferir no log mecânico e no estado: o inimigo derrubado fica `incapacitado` (não `morto`), e a marginália diz "Encerro a rodada: …. Sem matar.".
3. Chegar à rodada 5+ (ou usar um save de arena já nela) → "O Abismo se aproxima" na faixa e na narração.
4. Terminar o conflito → Espólio com tooltip de palavra-chave e ponto `has-loot` na aba ao trocar de aba.
5. Repetir os passos 1–2 no celular real (ou no emulador do Chrome em 390, com toque) e registrar 1 print em `docs/spec342/smoke-390.png`.

## 7. Riscos & compatibilidade

- **Saves:** nada novo é persistido. `cena` é derivado de `meta["scene"]`, que já existe (331). Saves sem `cartas_de_cena` → `cartas: []`.
- **Flag `off`:** cada mudança de UI é condicionada a `deckMode`, a `cena`/`pressagios_*` presentes, a `espolio_pendente`/`forja` ou à prop `deck` da folha de atalhos. R24 prova por screenshot. Risco residual: o CSS compartilhado. Mitigação: seletores novos só com classes do Baralho, e o bloco coarse só acrescenta seletores (não altera os existentes).
- **Mudança de semântica do "Sem matar" (R1.3):** antes, no caminho texto, valia só para a 1ª jogada. Agora vale para a rodada inteira. No caminho `off` (1 ação por request) o efeito é o mesmo. Risco: o jogador ligar "Sem matar" e uma carta de dano em área também não matar; isso é o esperado e a nota da fila avisa.
- **MockLLM/FallbackLLM:** sem impacto (nenhum nó LLM novo). O texto `Encerro a rodada:` chega ao narrador como ação do jogador. Conferir no smoke que a narração não o trata como pedido de fim de combate (o router recebe `jogadas`; `test_api_jogadas.py` cobre o roteamento).
- **Latência/quota:** zero request novo. O glossário passa a ser 1 fetch por sessão (hoje é 1 por montagem de `DeckCombat`).
- **Elevar o estado de armar para `CombateTab`:** é o maior refactor da spec. Mitigação: `useDeckArm` puro e testado, e `combat-gesture.spec.ts` (caminho `off`) precisa seguir verde sem edição.
- **Prints/linha de base:** fontes e antialiasing variam entre máquinas. A linha de base e a comparação rodam no mesmo ambiente (o CI, porta 4173) e os prints de `docs/spec342/` são só documentação.

## 8. Decisões (tomadas pelo autor sob o "destrave isso" do dono; o dono pode reverter qualquer uma)

- **D-342-1 — "Sem matar" no Baralho vale para a rodada inteira (backend mínimo).** Alternativa: só front, valendo para a 1ª jogada da fila (como o servidor faz hoje). Rejeitada porque, se a carta de dano for a 2ª, o golpe mata mesmo com o chip ligado, que é o bug do F-1 com outra cara. **Recomendado e adotado:** R1.3.
- **D-342-2 — Fica o fluxo de alvo da Arena** (o mesmo das manobras e do caminho `off`, SPEC-204/205). Os chips `deck-target` saem. Motivo: um gesto só ("arma → toca no alvo"), a Arena já tem nomes, Vitalidade e motivo de alvo inválido, e o presságio passa a morar nela (D-342-3). Custo: elevar o estado de armar para `CombateTab`.
- **D-342-3 — O presságio mora no chip do inimigo na Arena** (estilo Slay the Spire), não numa faixa própria. Tira 1 bloco do mobile e liga a intenção ao alvo. Só no Baralho (`omens`); fora dele a Arena não muda.
- **D-342-4 — Toque: tocar arma, e as regras aparecem na barra de mira.** Sem toque longo (F-9) e sem tooltip no toque (F-3, T-7). Mouse/teclado: tooltip em portal, e carta `si` vai direto à fila.
- **D-342-5 — Barra de envio fixa (sticky) no celular** com "Sem matar" + "Encerrar a rodada" + "Desfazer". É o que garante a ação principal à vista sem rolar (T-3, T-9).
- **D-342-6 — Unidade de tempo = "rodada"** em toda a UI do Baralho. O botão vira "Encerrar a rodada", e a marginália enviada vira "Encerro a rodada: …". "Turno" continua só onde já existe fora do combate.
- **D-342-8 — Runner de teste web = `node --test`** (o do repo, `web/package.json:9`). O pedido citou Vitest, mas o repo não o tem. Introduzir um 2º runner só por esta spec não compensa. Playwright como já existe.
- **D-342-9 — Backend da cena = bloco `cena` aditivo** (R2.1), em vez de o front deduzir o Relógio a partir de `round` e de constantes copiadas. O motivo é que o motor conta por `tactical_round`, que pode divergir de `combat.round`, e duplicar `5`/`12` no cliente violaria "mecânica é Python".
- **D-342-7 — Microcopy (strings literais, voz de Valoria; a coluna "Hoje" cita a fonte):**

| Onde | Hoje | Proposto |
|---|---|---|
| `BLOCK_TEXT.fardo` (`deck.ts:36`) | Fardo: não pode ser jogada | Fardo: pesa na mão, não se joga |
| `BLOCK_TEXT.sem_folego` (`:37`) | Sem Fôlego | Falta fôlego |
| `BLOCK_TEXT.limite` (`:38`) | Fila cheia | Não cabe mais nada nesta rodada |
| `BLOCK_TEXT.ja_na_fila` (`:39`) | Já está na fila | Já vai na fila |
| `BLOCK_TEXT.entropia` (`:40`) | Entropia insuficiente | A Entropia não basta |
| anúncio bloqueada (`DeckCombat.tsx:77`) | {carta}: indisponível. | {carta}: {motivo}. |
| anúncio sem alvo (`:82`) | {carta}: sem alvo válido. | {carta}: ninguém ao alcance. |
| anúncio enfileirou (`:96`) | {carta} entrou na fila. | {carta} vai na fila, em {n}º. |
| anúncio Esc (`:114`) | Fila limpa. | Fila desfeita. |
| prévia rótulo (`PreviewChip.tsx:14`) | Prévia | Seu golpe |
| prévia carregando (`:9`) | Calculando… | Lendo os sinais… |
| prévia erro (`:10`) | Prévia indisponível — a jogada continua valendo. | Os sinais não se deixam ler agora — a jogada vale do mesmo jeito. |
| fila vazia (`PlayQueue.tsx:21`) | Escolha cartas da mão: elas entram na fila e só valem ao encerrar o turno. | Escolha cartas da mão. Elas esperam aqui e só valem quando você encerrar a rodada. |
| botão principal (`:49`) | Encerrar turno (N) | Encerrar a rodada · sublinha "{n} carta(s)" |
| limpar (`:53`) | Limpar fila / Limpar (Esc) | Desfazer fila / Desfazer (Esc) |
| nota "sem matar" (novo) | — | Nesta rodada, golpes derrubam sem matar. |
| marginália enviada (`DeckCombat.tsx:100`) | Encerrar turno: A, B. | Encerro a rodada: A, B. [+ " Sem matar."] |
| mira (aimbar, Baralho) | Mirando {X}: escolha um alvo | Mirando {X}: escolha o alvo na arena. |
| confirmar alvo | Jogar em {alvo} | Jogar em {alvo} (mantém) · carta sem alvo: "Jogar" |
| log (`MechLog.tsx:6`) | Números da rodada (N) | Os dados da rodada {rodada} |
| pilhas (`Hand.tsx:25`) | Compra 12 · Descarte 3 · Exaurida 1 | Pilhas (sublinha: Compra 12 · Descarte 3 · Exaurida 1) |
| nota Exaurida (novo) | — | Exaurida: cartas gastas que só voltam depois do conflito ou de um descanso. |
| lista vazia (`Hand.tsx:37`) | Vazia. | Nada aqui. |
| mão vazia (novo) | — | Sua mão está vazia nesta rodada. Recorra às manobras abaixo, ou passe a vez. |
| mão bloqueada (novo) | — | Nenhuma carta responde agora. Recorra às manobras abaixo, ou passe a vez. |
| Fôlego (`FolegoPips.tsx:20`) | Fôlego | Fôlego {livre} de {máx} |
| Pacto (`:23`) | Pacto do Abismo: N emprestado — custa Entropia e +1 Carga. | O Abismo empresta {N} de fôlego: custa Entropia e +1 Carga. |
| presságio velado (novo) | — | Intenção velada |
| objetivo `sobreviver_n_rodadas` | — | Resista até a rodada {n} (faltam {n − rodada}) |
| objetivo `proteger` | — | Mantenha {alvo} de pé |
| objetivo `alcancar_zona` | — | Alcance {alvo} |
| objetivo `destruir_objeto` | — | Destrua {alvo} |
| objetivo `interromper_ritual` | — | Derrube {alvo} antes da rodada {n}, ou o ritual se completa |
| objetivo `capturar_vivo` | — | Leve-os vivos (use "Sem matar") |
| objetivo cumprido / falhou | — | Objetivo cumprido / Objetivo perdido |
| relógio antes | — | Relógio do Abismo: desperta na rodada {desde} |
| relógio ativo | — | O Abismo se aproxima: +1 Carga por rodada |
| relógio (corpo do details) | — | Da rodada {desde} em diante, quem carrega o Abismo ganha +1 Carga a cada rodada e a cena mais forte volta a agir. Na rodada {teto}, os inimigos recuam diante do Abismo. |
| presságio de cena (linha) | — | Na próxima rodada: {pressagio} |
| Forja esquecer (confirmação) | (sem) | {carta} sai do Baralho (segue no Acervo). Confirmar · Cancelar |
| Forja templo (confirmação) | (sem) | {carta} sai do Baralho no templo: {rótulo com custo}. Confirmar · Cancelar |
| Forja purgar (confirmação) | (sem) | Purgar {cicatriz}: {rótulo}. Confirmar · Cancelar |
| aba com espólio (acessível) | — | " — espólio à espera" |
| atalhos (folha, seção "No combate com Baralho") | — | `1–5` Armar a carta da mão · `Enter` Encerrar a rodada · `Esc` Desarmar ou desfazer a fila |

**O que o dono precisa decidir:** nada bloqueia a execução. Ele pode reverter D-342-1 (semântica do "Sem matar"), D-342-3 (presságio na Arena) ou qualquer string da D-342-7, de preferência antes da Etapa 2, quando as strings viram assert.

## 9. Notas de implementação

**Adições do coordenador (achados do navegador, 27/10)** — implementadas com teste:
- **R27 (B-1)** o chip de ganhos (`.outcome-toast`) fica contido na coluna do chat no desktop (`position: absolute` em `.ws-chat`); `outcome-toast.spec.ts` confere a contenção a 1440.
- **R28 (B-3)** inimigos homônimos ganham nomes distintos na Arena ("Bandido 1/2": usa `enemy.name`, e numera se ainda empatar); presságio sem prefixo redundante; "Jogar em Bandido 2".
- **R29 (B-4)** cabeçalho do HUD de combate: "Combate · Rodada N" (era "Round", sem espaço). Vale também com as flags `off` (texto visível; baseline R24 segue dentro de 1%).
- **R30 (B-6)** desktop (≥ 641 px): a mão quebra em grade e mostra todas as cartas; o trilho rolável fica só no celular.
- **R31 (B-13c)** celular: Espólio/Forja sem moldura dupla.
- **B-8a (não alterado):** "Aguentar" (`tipo: utilitaria`, `descanso_curto`) entra na mão porque `utilitaria` é tipo de baralho por design (`cards._DECK_TIPOS`, SPEC-328). Mudar isso é decisão de regra/autoria, fora do front: fica para outra spec.

**Desvios do executor**
- `test_second_card_kill_becomes_down` (integração com o orquestrador) não foi escrito: cobri R1.3 com testes unitários de `_mark_nonlethal` (todas as jogadas attack/card marcadas, off intocado) e o caminho do nó segue coberto por `test_spec325_nonlethal.py`.
- R24: baseline cobre fora de combate e em combate a 360/390/1440; o "desfecho" não foi capturado.
- Texto enviado: backend não depende de "Encerrar turno" (conferido em `api.py`, `agents/`, MockLLM); nenhuma compatibilidade extra foi necessária. `Encerro a rodada:` é só marginália.
- Mobile 390: a barra de envio sticky cobre parte da base das cartas no 1º paint (a carta está inteira no viewport, mas a barra a sobrepõe); ver `docs/spec342/on-390-combate.png`.
- Smoke real (§6) NÃO executado pelo executor (exige staging/provider real; fica com o coordenador antes do `done`).

**Correções da revisão Sol (P1-1, P2-1..P2-7)**
- P1-1: `deck-342-baseline.spec.ts` só roda em win32 (snapshots `*-chromium-win32.png`). **R24 é prova local (win32), não gate de CI Linux.** A frase da §7 ("a comparação roda no CI") vale como prova local no ambiente do executor/coordenador.
- P2-1: no celular a faixa de cena é 1 linha (truncada), a barra de envio é compacta (1 linha, fundo `--surface-2`); teste com `elementFromPoint` prova que a 1ª carta e a instrução de mira não ficam cobertas. P2-2: Esc com mira de manobra só cancela a mira (fila mantida). P2-3: `gap` no rótulo do HUD + teste de distância medida. P2-4: botões da barra de mira medidos ≥ 44 px. P2-5: integração com o nó real (2ª jogada letal + "Sem matar" → incapacitado; sem declarar → morto) e relógio de cena comparado ao `run_round`. P2-6: "Pilhas" dentro da borda a 390.
- P2-7: desfecho no baseline R24 não capturado (pendência registrada).

