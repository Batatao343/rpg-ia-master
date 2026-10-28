# SPEC-347 — Cartas: o tabuleiro do combate depois do smoke real (layout, retrato do inimigo e registro da rodada)

> **Status:** `approved` (o dono mandou "corrigir tudo" em 27/10 e acrescentou o retrato do inimigo e o registro da rodada; decisões em §8)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-342 e SPEC-345 (`in-progress`, mas o código já está na `main`: a linha de base `off` e o `scrollIntoView` da mira vêm delas); SPEC-333/334 (pousadas atrás de flag); SPEC-326 (`done`, pipeline de arte); SPEC-297 (pool compartilhado).
> **Corre em paralelo com:** SPEC-346 (narração/motor; outro worktree). Fronteira em §2 "Fora de escopo" e em D-347-9.
> **Desbloqueia:** com a 346, ligar `RPG_CARD_DECK=on` no staging com o combate como tabuleiro.
> **EXECUTOR_MODEL:** `Terra` (Etapas 1–4) · `Sol` (Etapa 5, retrato: cria um writer persistente compartilhado) · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. Os Playwright e `node --test` daqui são testes de produto (`web/e2e/`, `web/tests/`), fora de `evals/protected-paths.txt`.
> **Precisa de backend:** sim, pequeno e atrás de flag. (a) Rótulo das ações fora de ordem no log mecânico e o registro estruturado da rodada (R5, R14). (b) Motivo de cada via bloqueada da Forja (R7). (c) Campo `retrato` na view do combate e um registro compartilhado de retratos de criatura (R13).

Rótulos: **[F]** fato no source (worktree `rpg-spec-347`, `main` em `1e80f1b6`) · **[H]** hipótese com evidência, que o 1º teste da etapa confirma · **[R]** recomendação · **[D]** decisão (§8).
Insumo: [docs/spec347/achados-smoke.md](../docs/spec347/achados-smoke.md) (itens 1–11) e os prints em `docs/spec347/smoke/`. Cada item foi conferido no source e nos prints.

---

## 1. Contexto & Objetivo

[F] O smoke com LLM real (API local legacy, DeepSeek, flags de cartas `on`, `main` em `fae9a4e5`) jogou três combates a 390 e 1440 px. O motor funcionou, mas a tela de combate tem sobreposições, quebras de linha ruins, informação duplicada ou enganosa e painéis que abrem no lugar errado. A SPEC-346 cuida da narração e do motor. Esta spec cuida só do que o jogador **vê** no combate por cartas.

[F] O dono acrescentou dois pedidos em 27/10. Com a 346, a LLM sai das rodadas e só resume no fim, então o combate vira um **tabuleiro de cartas sem texto livre**. Por isso: (1) cada inimigo no tabuleiro mostra a **imagem** dele, com a do bestiário reaproveitada e uma imagem nova gerada e salva no pool compartilhado quando o inimigo é novo; (2) o **registro das cartas** (quem jogou o quê, em quem, com que resultado) ganha destaque na tela, no lugar da prosa.

Objetivo: o tabuleiro fica legível e tocável a 390 e a 1440 px, sem nada coberto e sem rolar para achar a ação principal. Nada muda no caminho `off`. Princípio: *mecânica é Python*. O front só mostra o que a API manda. O backend novo é só de **view** (rótulos, motivos, retrato, registro) e não muda nenhuma regra de jogo.

## 2. Requisitos

As strings de interface estão em D-347-10 e são **literais** (os testes assertam o texto). Larguras citadas: 390×844 com `isMobile`/`hasTouch` (celular) e 1440×900 (desktop).

**Regra de medição (vale para todo requisito de sobreposição).** O teste mede **sem rolar antes**: nada de `scrollIntoViewIfNeeded`, `hover` ou `click` do Playwright no elemento medido, porque essas ações rolam a página sozinhas. Para armar e mirar, usar o atalho de teclado (`1`–`5`, desktop) ou `locator.dispatchEvent("click")` (celular), que não rolam. A medição usa `getBoundingClientRect` e `document.elementFromPoint(centro)`. "Visível e livre" quer dizer duas coisas: o centro do controle devolve o próprio controle (ou um filho dele) em `elementFromPoint`, e a caixa fica inteira dentro do viewport e da área visível do painel `.ws-panel`. Tooltip tem `pointer-events: none` e por isso é invisível para `elementFromPoint`: no caso dele, o teste usa interseção de retângulos (R6).

### Etapa 1 — sobreposições e quebras a 390 px (itens 1, 2)

- **R1 — Barra de mira livre da barra de envio fixa (item 1, P2).**
  [F] No celular, `.play-queue__end` é `position: sticky` acima da tab bar (`web/src/workspace.css:382`), com fundo opaco (`:416`). A `aimbar` do Baralho põe, nesta ordem, a prévia, "Jogar em X", "Outro alvo", as regras (largura total) e, por último, "Cancelar" com `margin-left: auto` (`DeckCombat.tsx:176-195`; `workspace.css:353-356`). Ou seja, "Cancelar" é o controle mais baixo da mira.
  [F] A SPEC-345 R14 leva a mira para a vista com `scrollIntoView({block: "nearest"})`, num efeito com dependências `[armed.index, armed.targetId]` (`DeckCombat.tsx:104-107`). A `PreviewChip` devolve `null` com estado `idle` (`PreviewChip.tsx:9`), e o estado só vira `loading` no efeito seguinte (`DeckCombat.tsx:84-97`). Então a rolagem acontece **antes** de a linha da prévia existir. A prévia aparece depois, empurra os botões para baixo e "Cancelar" fica sob a barra fixa (print `1874135-…-390-2-previa.png`).
  [F] O teste da 345 só mede os 12 px do topo da mira (`web/e2e/spec345-mobile390.spec.ts:16`), por isso não pegou o problema.
  - R1.1 — Com o alvo fixado, a linha da prévia ocupa espaço desde o 1º render. Se houver `previewKey` e o estado ainda for `idle`, a `PreviewChip` renderiza "Lendo os sinais…" (o mesmo texto de `loading`), sem esperar o efeito.
  - R1.2 — A rolagem da mira roda de novo quando o estado da prévia muda (`idle → loading → ok|error`), sempre com `block: "nearest"`.
  - R1.3 — No celular, a ordem da mira com alvo fixado passa a ser: prévia → linha de ações (`Jogar em X` ocupando o espaço livre + `Cancelar` à direita, sem quebrar) → `Outro alvo` (se houver) → regras. "Cancelar" deixa de ser o último elemento.
  - R1.4 — Enquanto há carta armada (`.deck-combat[data-armed]`), a barra de envio deixa de ser `sticky` no celular e fica no fluxo, abaixo da fila (D-347-2). Desarmou, ela volta a ser fixa.
  - R1.5 — **Teste** a 390 (`hasTouch`) e a 1440, com 1 e com 2 inimigos e a prévia respondendo com 150 ms de atraso no `DeterministicBackend`: depois de `data-preview="ok"`, "Jogar em X" e "Cancelar" ficam visíveis e livres (regra de medição), sem nenhuma rolagem feita pelo teste.
- **R2 — Barra de envio sem quebra com a fila cheia (item 2, P2).**
  [F] A 390, com "Sem matar" + "Encerrar a rodada · 2 cartas" + "Desfazer fila" numa linha `nowrap` (`workspace.css:416-417`), "Sem matar" e "Desfazer fila" quebram em 2 linhas e a contagem encosta no rótulo (print `1877078-…-390-3-fila.png`). As três caixas não cabem em ~366 px: "Encerrar a rodada" sozinho mede ~200 px na fonte de rótulo.
  - R2.1 — Em ≤ 640 px, a barra fixa leva só "Sem matar" (quando existir) e "Encerrar a rodada". "Desfazer fila" sai da barra e vai para a própria fila, como último item da lista (botão `btn--ghost` sm, ≥ 44 px). No desktop, nada muda (D-347-3).
  - R2.2 — Em ≤ 640 px, a contagem vira um selo numérico dentro do botão ("Encerrar a rodada" + selo "2"), com `gap` ≥ 6 px entre o rótulo e o selo. O nome acessível continua "Encerrar a rodada, 2 cartas" (selo `aria-hidden` + texto `sr-only`).
  - R2.3 — `.play-queue__end .actionchip` e os rótulos dos botões da barra levam `white-space: nowrap`.
  - R2.4 — **Teste** a 390 com "Sem matar" disponível e 2 cartas na fila: em todo botão de `.play-queue__end` e no "Desfazer fila", cada nó de texto visível tem `Range.getClientRects().length === 1` (uma linha). A distância horizontal entre o rótulo e o selo é ≥ 6 px. Toda caixa fica dentro da largura da barra e tem ≥ 44 px de altura.
- **R3 — Número do presságio inteiro (item 2).** [F] `.tchip__omen-num` não tem `nowrap` (`workspace.css:352`), e a faixa "3–6" quebra em "3–" / "6" (print `1877078`). A regra ganha `white-space: nowrap`. **Teste:** a 390, com presságio `faixa: [3, 6]`, `.tchip__omen-num` tem 1 linha.

### Etapa 2 — Arena e iniciativa (itens 3, 5)

- **R4 — Arena sem zona vazia ocupando espaço (item 3, P2).**
  [F] `.arena__zones` usa `repeat(auto-fit, minmax(190px, 1fr))` (`web/src/styles.css:1233`). Com 3 zonas e todo mundo na 1ª, as duas vazias ficam com 2/3 da largura. Os chips ficam espremidos em ~190 px: nome em 3 linhas e "sem Vitalidade" em 2. A mão desce para fora da dobra (print `2364091-…-1440-0-inicio.png`).
  - R4.1 — **Só no modo Baralho** (prop nova `compact` em `Arena`, passada pelo render prop de `CombateTab.tsx:256`), as zonas sem ninguém saem da grade. Elas viram uma única linha abaixo: "Também na cena: Veio de Calcário · Boca do Abismo" (`.arena__empty-zones`, cor `--muted`). Sem `compact`, a Arena fica idêntica.
  - R4.2 — Com `compact`, a partir de 641 px, os membros de uma zona ocupam uma grade `repeat(auto-fill, minmax(14rem, 1fr))`. Abaixo disso, ficam empilhados como hoje.
  - R4.3 — `.tchip__vit` ganha `white-space: nowrap`.
  - R4.4 — **Teste** a 1440×900, com fixture de 3 zonas, a 1ª ocupada pelo jogador e 2 inimigos (com presságio e 2 condições cada), 2 presságios de cena e mão de 5 cartas. Todo `.tchip` tem largura ≥ 224 px. Todo `.tchip__vit` tem 1 linha. A 1ª `.deck-card` fica inteira na área visível do painel, com `scrollTop === 0`.
- **R5 — Iniciativa honesta e sem "Rodada" repetida (item 5, P3).**
  [F] **O dado do backend está certo.** `view.order` sai de `meta["initiative"]` (`api.py:2823,2943-2950`), que `agents/combat.py:2337` grava a partir de `out["initiative"]`. Esse valor é a mesma ordem que montou a sequência real da rodada (`services/conflict_orchestrator.py:2445-2455`). A rodada 1 de herói novo é forçada para "heroes" (`agents/combat.py:902-930`), o que bate com "Heróis → Inimigos" no print `1654717`.
  [F] O "inimigos agiram primeiro" do `mech_log` tem outra causa. Contra-ataques e reações de Carta (`conflict_orchestrator.py:1066-1079`), ataques de oportunidade (`:956-957`, `:1624`) e "Última Ação" (`:1932-1940`) passam por `_basic_attack`, que anexa a `out["attacks"]` (`:1216`). A janela de reação abre **antes** do golpe de quem age (`:1636` vs `:1657`). Assim, a linha do inimigo que reage aparece antes da linha do herói, sem nenhum rótulo (`services/combat_preview.py:177-202`).
  [F] Três defeitos de apresentação: (a) "Rodada N" aparece três vezes no modo Baralho (`SceneStrip.tsx:26,36`, `Arena.tsx:95` e o cabeçalho do HUD em `Hud.tsx:456`); (b) a ordem exibida é a da rodada **já resolvida**, mas "Rodada N · iniciativa: X" se lê como a ordem da próxima, e a iniciativa é rolada de novo a cada rodada; (c) os chips "0 · Inimigos / 0 · Heróis" mostram `init: 0`, um valor fixo de compatibilidade (`api.py:2947`, `Hud.tsx:488-498`).
  - R5.1 — **Teste-oráculo backend primeiro** (`tests/test_spec347_initiative_view.py::test_order_matches_resolved_turns`). Rodar `run_round` com rng semeado, sem iniciador e com iniciador `enemy`. A ordem de lados em `view["order"]` é igual à ordem da 1ª aparição de cada lado em `out["resolved_turns"]`. Se este teste falhar (contra a leitura acima), o ajuste mínimo é gravar em `meta["initiative"]` a ordem derivada de `resolved_turns`, em `agents/combat.py:2337`, e registrar o desvio na §9.
  - R5.2 — **Backend mínimo (view):** `_basic_attack` grava `atk["fora_de_turno"] = label` (`conflict_orchestrator.py:1214-1216`; o `label` já existe em toda chamada). `combat_preview.mech_log` usa esse rótulo no lugar do nome da carta, quando houver: `Saqueador · Contra-ataque → Você · …`. Só com o Baralho `on` (o log já é só `on`, `combat_preview.py:209`). Nenhum número muda.
  - R5.3 — **Nos dois modos**, a linha da Arena (`Arena.tsx:95`) deixa de dizer "Rodada N · iniciativa: …" e passa a dizer, sem número de rodada: "Na última rodada, {Heróis|Inimigos} agiram primeiro." (com `title`: "A iniciativa é rolada de novo a cada rodada."). Sem `order`, a linha não aparece.
  - R5.4 — **Nos dois modos**, o "0 ·" some: os chips de `Hud.tsx:488-498` mostram só o lado ("Heróis", "Inimigos"), porque `init` é um valor fixo de compatibilidade e não um dado. Com a Arena visível (`arena` true, `CombateTab.tsx:348`), a lista "Iniciativa" do HUD não aparece, porque a Arena já diz a ordem.
    - Cabeçalho do HUD: no modo Baralho, sem "· Rodada N" (a faixa de cena já mostra), via prop nova `deck` em `Hud.tsx::Combat`. No modo `off`, fica "Combate · Rodada N", que passa a ser a única ocorrência.
    - Resultado: "Rodada" aparece uma vez em cada modo.
  - R5.5 — **Testes:** `node --test` (SSR) confirma que, com e sem `pilhas`, "Rodada" aparece **uma** vez no texto de `.ws-combat`, não há `.initiative` com a Arena visível e nenhum texto casa com `/\b0 · (Heróis|Inimigos)/`. `tests/test_spec347_mech_log.py` confirma que uma reação de Carta e um ataque de oportunidade saem com o rótulo e que um ataque normal fica idêntico ao de hoje.

### Etapa 3 — dobra no desktop, tooltip, Forja, desfecho, prévia, rótulos e Livro (itens 4, 6–10)

- **R6 — Tooltip de palavra-chave fora dos controles (item 6, P3).** [F] `Keyword` põe o tooltip **abaixo** da palavra, a não ser que falte espaço embaixo (`KeywordTip.tsx:16-18`). No Espólio, a regra fica logo acima de "Levar …", e o tooltip cobre o botão da própria carta (print `1996090`).
  - R6.1 — O tooltip passa a abrir **acima** da palavra (`translateY(-100%)`) sempre que houver espaço (`r.top - altura estimada ≥ 8`), e abaixo só como alternativa.
  - R6.2 — **Teste** a 1440: hover com mouse na palavra-chave da 3ª oferta do Espólio e da 1ª carta da mão. O retângulo do `[role=tooltip]` **não intersecta** nenhum `button` do mesmo `.combat-card`. Teste por interseção de retângulos, porque o tooltip é `pointer-events: none`.
- **R7 — Forja diz por que cada via está fechada (item 7, P3).**
  [F] `forgetChoices` desabilita "Esquecer (descanso)" e "Esquecer no templo" só a partir de booleanos (`web/src/cardRewards.ts:17-23`). Os motivos existem apenas como mensagens de erro do servidor (`services/card_rewards.py:382,386,389,392,512,515,519`) e não chegam à view (`forge_view`, `:614-635`). Só o Afiar mostra motivo (`ForjaPanel.tsx:101-105`).
  - R7.1 — **Backend aditivo (view):** `forge_view` ganha `esquecer.motivos = {descanso: str|null, templo: str|null}` e `purgar.motivos = {medico: str|null, templo: str|null}`, com `null` quando a via está aberta. Os textos vêm de constantes de módulo que `forget()`/`purge()` também passam a usar, sem cópia de string. Prioridade para o templo: "não é templo" antes de "falta ouro". Com `permitido = false`, o motivo de toda via é `motivo`.
  - R7.2 — Cada linha do Baralho ganha `bloqueio: str|null`. Básica com o Baralho no mínimo devolve a mensagem de `:382`. Cicatriz continua com `esquecivel: false`.
  - R7.3 — Front: botão de via fechada usa `aria-disabled="true"` + `aria-describedby` apontando para uma linha `.forja__why` abaixo da barra, que lista os motivos ("Esquecer (descanso): Só dá para esquecer uma Carta depois de um descanso longo."). Clicar não faz nada. Com `bloqueio` na linha selecionada, a barra mostra só esse motivo.
  - R7.4 — **Testes:** `tests/test_spec347_forge_reasons.py` (fora do templo, no templo sem ouro, com ouro, sem descanso, com descanso, básica no mínimo, `permitido=false`; o texto do motivo é igual ao do `_fail` da ação correspondente). `node --test` (SSR) da `ForjaPanel` com motivos.
- **R8 — Pós-combate abre no topo (item 8, P3).** [F] O painel guarda o `scrollTop` por aba (`ContextSurface.tsx:63-69,100-102`). Quando o combate acaba, o `CombatOutcomePanel` entra no **topo** (`CombateTab.tsx:237-240`) e o painel continua rolado onde estava (na mão), cortando "Continuar" (print `1722832`).
  - R8.1 — Quando um `combat_result.result_event_id` novo aparece e o painel de Combate está visível, o `CombatOutcomePanel` rola para a vista com `block: "start"`. Isso só acontece uma vez por `result_event_id`.
  - R8.2 — **Teste** a 1440 e 390: rolar o painel até o fim durante o combate, receber a vitória, e "Continuar" fica visível e livre (regra de medição).
- **R9 — Rótulo de tipo com acento (item 8).** [F] `TYPE_LABEL` não tem `utilitaria` (`web/src/components/tabs/DeckCard.tsx:8-11`), então o rótulo cai no id cru e o CSS põe em caixa alta: "UTILITARIA". Entra `utilitaria: "Utilitária"` (ícone: o mesmo fallback de hoje). **Teste `node --test`:** todo tipo de `services/cards.py::_DECK_TIPOS` (`:414`) e `passiva`/`virtude` têm rótulo, e nenhum rótulo é igual ao id cru quando o id tem acento em pt-BR.
- **R10 — Prévia com percentual inteiro (item 9, P3).** [F] O servidor arredonda com 1 casa (`services/combat_preview.py:158`), e `fmtPct` mostra a casa decimal quando ela existe (`web/src/combat/deck.ts:101`): "64,9 %" ao lado de "76 %".
  - R10.1 — `fmtPct(n)` devolve inteiro. `0` e `100` ficam exatos. Para `0 < n < 100`, o valor é `min(99, max(1, round(n)))`, para nunca mostrar "100 %" ou "0 %" para o que não é certo.
  - R10.2 — **Teste `node --test`:** 64.9 → "65 %", 56.8 → "57 %", 99.6 → "99 %", 0.3 → "1 %", 0 → "0 %", 100 → "100 %", e o prefixo `≈ ` continua com `aproximado`.
- **R11 — Livro reaberto mostra a última narração (item 10, P3).**
  [H] A posição de rolagem do Livro fica em memória por `game_id` (`chatSessionStore.ts:9-19`) e é lida uma vez ao montar (`ChatSurface.tsx:41`). Ao reabrir um save **na mesma aba**, o `StoryLog` monta com o log vazio (`App.tsx:756`). Se o jogador tinha subido no Livro antes de sair, ele herda `{top: X, atBottom: false}` (`StoryLog.tsx:32`). Aplicar `scrollTop = X` num log vazio não rola nem dispara `scroll` (`:41-45`). Quando o histórico chega (`App.tsx:764,735`), o efeito de `:48-58` não rola, porque `atBottom` é falso e a última entrada não é do jogador. O Livro fica no topo, isto é, no prólogo. Com F5 isso não acontece (a memória zera).
  - R11.1 — **Teste de reprodução primeiro** (`web/e2e/spec347-livro.spec.ts::reabrir_save_mostra_ultima_narracao`, 1440): abrir o save, rolar o Livro até o topo, voltar ao menu, reabrir o mesmo save. A última `.msg--story` (ou o último narrador) intersecta a área visível de `.story`. Esse teste tem de falhar **antes** da correção. Se não falhar, o executor reproduz o roteiro exato do smoke e registra a causa real na §9, antes de corrigir.
  - R11.2 — Correção: `handleContinueSave` (`App.tsx:746-769`) zera a rolagem guardada do jogo (`setChatSession(gid, {scrollTop: null, atBottom: true})`) antes de montar a tela. A memória de rolagem serve à troca de superfície (SPEC-204 R7), não a reabrir o save. O Livro abre no fim, como numa 1ª abertura (D-347-6).
- **R12 — Coberturas pedidas (item 11).** Testes para o que o smoke não exercitou:
  - R12.1 — Forja: confirmação inline de "Esquecer" com descanso disponível (frase + Confirmar + Cancelar; Esc devolve o foco) e via fechada sem material/descanso (R7.3: `aria-disabled` + motivo, e nenhum request).
  - R12.2 — Celular: com `espolio_pendente` e outra superfície ativa, o botão Combate da `MobileTabBar` tem `.has-loot` e o nome acessível termina com " — espólio à espera". Ao abrir Combate, a classe sai.

### Etapa 4 — o tabuleiro como superfície principal da rodada (pedido do dono)

- **R14 — Registro da rodada em destaque, não em prosa.**
  [F] Hoje o que aconteceu na rodada aparece só (a) na narração do Livro, que a 346 tira das rodadas, e (b) num `details` **fechado** no fim da aba, com linhas de texto ("Os dados da rodada N", `MechLog.tsx:3-17`; `DeckCombat.tsx:204`). O log é uma lista de strings (`combat_preview.py:177-211`) e só tem ataques: carta de defesa, de suporte e de condição não aparece. Os usos de carta ficam em `out["cards_used"]` (`services/conflict_turn.py:473-481`), separados de `out["attacks"]`. A ordem entre os dois se perde.
  - R14.1 — **Backend (view, só com o Baralho `on`):** `_resolve_actor_turn` (`conflict_orchestrator.py:1609-1620`) grava em `out["turn_spans"]` um registro por turno resolvido: `{actor_id, attacks: [i0, i1), cards: [j0, j1)}`, com os índices de `out["attacks"]`/`out["cards_used"]` antes e depois do turno. As ações extras de chefe e o turno negado (`:2475-2498`) também gravam um registro (vazio, com `negado: true`). Nenhum número muda.
  - R14.2 — `combat_preview.round_log(out, actors) -> list[RoundLogEntry]` monta, na ordem dos turnos, uma entrada por carta usada e por ataque. Um ataque com `fora_de_turno` (R5.2) dentro do turno de outro ator vira entrada `origem: "reacao"`. `store_mech_log` passa a gravar também `meta["last_round_log"]` (mesma condição de `:209`), e a view do combate expõe `registro_rodada` só quando `pilhas` existe (`api.py:2990-2995`). O `mech_log` em string continua (compatibilidade e "Os dados").
  - R14.3 — **Front:** `RoundBoard` (novo, `web/src/components/combat/RoundBoard.tsx`) fica **entre a faixa de cena e a Arena**, sempre aberto. Cada entrada é uma linha-ficha: retrato miniatura do ator (R13, ou o selo "Você"), nome, nome da carta como mini-carta (`.combat-card` compacto), seta, alvo, e um chip de resultado (`acerto`/`erro`/`crítico` + "−N" de dano, "+N Proteção", condição aplicada). Reação e oportunidade levam o rótulo ("Contra-ataque"). No celular, aparecem as últimas 4 entradas, com "Ver a rodada inteira (N)" (`details`). No desktop, aparecem todas.
  - R14.4 — "Os dados da rodada N" (`MechLog`) fica como está, fechado, no fim da aba: é o detalhe numérico (dados, modificadores).
  - R14.5 — Anúncio: ao chegar uma rodada nova, o leitor de tela recebe um resumo curto ("Rodada resolvida: 3 jogadas.") em `role=status`, e não a lista inteira.
  - R14.6 — **Testes:** `tests/test_spec347_round_log.py` (ordem igual à de `resolved_turns`; carta de defesa sem ataque aparece; contra-ataque marcado `reacao`; turno negado não gera entrada; com o Baralho `off`, nem `last_round_log` nem `registro_rodada` existem). `node --test` (SSR) do `RoundBoard` (sem entradas não renderiza nada; com 6 entradas a 390 renderiza 4 + `details`). Playwright a 390 e 1440: o `RoundBoard` fica acima da Arena, e a 1440 a 1ª `.deck-card` continua inteira no painel com `scrollTop === 0` com 4 entradas no registro (R4.4 com o registro).

### Etapa 5 — retrato do inimigo no tabuleiro (decisões do dono D-347-B/D/G/H/I; atrás da flag `RPG_CREATURE_ART`)

- **R13 — Cada inimigo mostra a sua imagem.** A fonte principal é a arte do bestiário que o dono está gerando num projeto paralelo. Enquanto ela não existe, aparece um marcador de custo zero (ícone da família). Gerar uma imagem é **opcional e pago pelo jogador**, e o resultado fica no registro compartilhado, para que quem vier depois veja de graça.
  [F] O que existe hoje:
  - A ficha de criatura não tem campo de imagem (`data/bestiary.json`: nenhum `image|portrait|asset_id`; `agents/bestiary.py:137-162`).
  - O catálogo curado de arte (`data/visual_assets.json`, lido por `services/visual_catalog.py:43-67` com `visual_for(subject_type, subject_id)`) tem raças, classes, locais e NPCs, mas **nenhum** `subject_type` de criatura.
  - A arte dinâmica (SPEC-326) é **paga pelo jogador**, por oferta e cotação (`api.py:4564-4576`, `:4637-4700`, `_guard_image_effect` em `:4579-4591`). Ela é gravada em chave privada por dono e jogo: `users/{owner}/games/{game}/{kind}/…`, onde `kind` já aceita `monster` (`services/asset_pipeline.py:35-58`). O único gatilho ligado a inimigo é a cena épica de chefe (`services/art_triggers.py:146-164`).
  - O pool compartilhado (SPEC-297, `RPG_SHARED_POOL=off|shadow|on`, `services/shared_pool.py:8-51`) guarda só o **conceito** da criatura, sem imagem (`agents/bestiary.py:193-209`, "o documento do pool é só CONCEITO"). Cada criatura do pool tem `entry_id` e é promovida por job, com HOLD no jogo de origem.
  - A instância de combate se liga ao bestiário por `services/discovery.py::normalize_bestiary_id` (`:39-61`: `{bestiary_id}_{N}`, `archetype_id`, slug do nome). A família vem de `services/enemy_decks.py::family_key` (`:144-152`; 11 famílias em `:36-48`).
  - O fluxo pago da 326 aceita hoje `image_type ∈ {"player","npc","scene"}` (`api.py:1937`). Ele cota pelo perfil de preço (`services/image_quotes.py`, `image_pricing`/`shard_pricing`), reserva na carteira, confirma (`api.py:4703-4790`), liquida o débito e expõe o status em `GET /game/{id}/art/{generation_id}` (`:4797`).
  - O provedor de imagem fica atrás da porta `ImageGenerator` (`infrastructure/ports.py:27`), com o adapter `infrastructure/openai_images.py`.
  - O sistema de ícones da 322 (`web/src/design/icons.tsx:17-50`) já tem `combat`, `death`, `dark`, `abyss`, `unique`, `exit`, `ruler`, `quest`, `torch`, `card-reaction` e `card-virtue`. Isso basta para um ícone por família, sem SVG novo.
  - Conclusão: não existe imagem de inimigo nem lugar compartilhado onde guardá-la. O mínimo tem três partes: (1) um **ponto de entrada** para a arte do bestiário (catálogo curado, por id de criatura e por família); (2) um **registro de retratos** por chave estável (R13.1), preenchido só por geração paga pelo jogador; (3) o **marcador** de família.
  - R13.0 — **Genérico × importante (regra do dono, D-347-D).** Inimigo genérico reaproveita a arte do **tipo**. Inimigo importante tem arte **própria**, com identidade própria: dois Goblins importantes geram duas artes. O critério é determinístico e só usa campos que já existem:
    [F] Campos disponíveis na instância e no conflito:
    - `categoria` ∈ `lacaio|padrao|elite|chefe` e `type` legado (`agents/bestiary.py:109-142`);
    - `id` = `{bestiary_id}_{N}` / `_r{N}` (`services/encounter_manifest.py:306-308`);
    - `name` e o rótulo de espécie `species_label_for(enemy)` (nome do template, ou o nome sem número final, `:311-319`);
    - `pool_entry_id` (criatura do pool, `agents/bestiary.py:208`);
    - o manifesto do conflito com `source == "npc_in_scene"`, `target_ref = "npc:{nome}"` e `npc_name` (`encounter_manifest.py:271-288`; `agents/router.py:647`).
    - **Não existe** campo de missão nem `unique` no inimigo (grep vazio em `agents/`/`services/` por `quest_id|unique|npc_id` na ficha de inimigo).
    - `is_important(enemy, manifest) -> tuple[bool, str]` (motivo para log e teste). Devolve `True` se **qualquer** destas valer:
      - (a) **Chefe:** `categoria == "chefe"` ou `type ∈ {"boss", "chefe"}`.
      - (b) **NPC hostil:** o manifesto tem `source == "npc_in_scene"` (ou `target_ref` com `npc:`), e o nome da instância bate (casefold) com o `npc_name`/alvo.
      - (c) **Nome próprio:** `fold(name)` sem o sufixo numérico ≠ `fold(species_label_for(enemy))`, e o nome não é só `"{espécie} {N}"`. Exemplo: "Grishnak" num template `enemy_goblin`. Vale para qualquer categoria, inclusive elite com nome.
    - Senão, o inimigo é **genérico**. "Goblin", "Bandido 2" e "Saqueador de Marfim" ad-hoc são genéricos: no ad-hoc, a espécie é o próprio nome, então (c) não dispara.
    - Inimigo de missão só ganha arte própria se cair em (a)–(c) (decisão do dono, D-347-I). Um campo de missão fica fora desta spec.
  - R13.1 — **Chave de cache** (`services/creature_art.py`, novo): `portrait_key(enemy, manifest, *, game_id) -> str`.
    - **Genérico** (chave do tipo, compartilhável), nesta ordem:
      - `tipo:{normalize_bestiary_id(enemy)}`;
      - `tipo:bst:{pool_entry_id}`;
      - `tipo:gen:{slug(species_label_for(enemy))}` (sufixo numérico removido; "Bandido 2" → `tipo:gen:bandido`).
      - Todos os Goblins de `enemy_goblin` (instâncias `enemy_goblin_1`, `_2`, `_r1`) têm a mesma chave.
    - **Importante** (chave do indivíduo):
      - NPC hostil → `npc:{entity_id}` do NPC (`state["npcs"][…]["entity_id"]`), que primeiro usa a arte curada `visual_for("npc", entity_id)` (`visual_catalog.py:66-67`);
      - criatura importante do pool → `unico:bst:{pool_entry_id}:{slug(name)}`;
      - os demais → `unico:{game_id}:{slug(species_label)}:{slug(name)}`.
      - O mesmo chefe nomeado, voltando noutro conflito do mesmo jogo, reaproveita a sua arte. Um 2º Goblin importante com outro nome tem outra chave.
  - R13.2 — **Arte do bestiário: onde entra (fonte principal, D-347-G).** A arte do projeto paralelo do dono entra no **catálogo curado que já existe**, `data/visual_assets.json` (lido por `visual_catalog.py`, com `sha256` conferido por `sha256_file`), com dois `subject_type` novos:
    - `creature` → `subject_id` = id do bestiário (`enemy_goblin`) ou, para criatura do pool, `bst:{pool_entry_id}`;
    - `creature_family` → `subject_id` = família de `enemy_decks.FAMILIAS` (`bruto`, `abissal`, …). É a arte genérica da família, usada quando a criatura não tem arte própria.
    - **Arquivos:** `web/public/art/bestiario/criaturas/{subject_id}/{variant}.webp` e `web/public/art/bestiario/familias/{familia}/{variant}.webp`, com as mesmas variantes do catálogo.
    - **Importação:** script novo `scripts/import_bestiary_art.py <pasta>`. Lê uma pasta no formato `criaturas/{id}.png` + `familias/{familia}.png`, gera as variantes WebP com `asset_pipeline.process_image`, calcula `sha256`, grava as entradas (`visibility: public`, `alt` = "Retrato de {nome do bestiário}") e falha se o id não existir em `data/bestiary.json`/`FAMILIAS`. É idempotente: reimportar o mesmo arquivo não muda nada. O dono só precisa soltar as imagens na pasta e rodar o script; o tabuleiro passa a usá-las sem outra mudança.
    - NPC hostil usa a arte curada de NPC que já existe, `visual_for("npc", entity_id)`.
  - R13.3 — **Resolução** `portrait_for(enemy, manifest, *, game_id) -> {"estado": "pronto"|"gerando"|"marcador", "src": str|None, "familia": str, "icone": IconName, "alt": str, "proprio": bool, "gerar": GerarOffer|None}`. Ordem:
    - (a) **importante** com arte própria: curada (`npc`) ou registro `ready` na chave `unico:`/`npc:`;
    - (b) arte curada `creature` da criatura;
    - (c) registro `ready` da chave `tipo:`;
    - (d) arte curada `creature_family` da família;
    - (e) **marcador**: ícone da família (D-347-H), sem imagem.
    - O importante que ainda não tem arte própria cai em (b)–(e) com `proprio: false`.
    - `estado: "gerando"` quando há geração `pending` para a chave (mostra a melhor arte disponível de (b)–(e) + o selo "Gerando retrato…").
    - `gerar` só vem quando não há arte própria da chave (genérico: nada em (b)/(c); importante: nada em (a)), não há `pending`, a flag está `on` e o perfil tem geração (hosted).
    - `alt` = "Retrato de {nome}". Nunca vaza ficha secreta, prompt nem chave privada.
  - R13.4 — **→ SPEC-352 (transferido; não cumprido nesta spec).** **Registro de retratos** (writer persistente novo; antes de criar, consultar `project_index/state_ownership` e registrar como canonical owner). Uma linha por `portrait_key`: `{portrait_key, escopo: tipo|unico|npc, status: pending|ready|failed, generation_id, asset_id, variants, created_at, origin_game_id, visibility: game|shared}`. A chave é única: uma geração por chave, e quem pagar depois de `pending`/`ready` não paga de novo.
    - Os objetos são copiados, quando a geração fica `ready`, para uma chave **fora** do escopo de dono/jogo: `shared/creatures/{safe_entity_id(key)}/{asset_id}.{variant}.{sha12}.webp` (novo ramo `shared_object_key` em `asset_pipeline.py`, com o mesmo `safe_entity_id` e as mesmas variantes). O original privado da 326 fica onde está.
    - Perfis: `hosted` usa Postgres (`app.creature_portraits`) + o blob store do runtime. `legacy`/`local` não geram e usam só catálogo e marcador.
  - R13.5 — **Visibilidade (segue o pool, SPEC-297 R22).**
    - Genérico de criatura curada ou promovida: retrato `shared`, visível a qualquer jogo.
    - Criatura em HOLD (`own_entries` do jogo): retrato visível só ao jogo de origem até a promoção.
    - Rejeitada no pool: o retrato nunca é exposto a outros jogos; o jogo de origem continua vendo o seu.
    - Importante `unico:{game_id}:…`: sempre `visibility: game`, porque o indivíduo pertence àquele mundo.
    - `unico:bst:…` segue a promoção da entrada do pool.
    - `npc:{entity_id}` segue a visibilidade do NPC: só com `known_by_player`, como em `art_triggers.py:133-138`.
  - R13.6 — **→ SPEC-352 (transferido; não cumprido nesta spec).** **Geração opcional, paga pelo jogador (D-347-B), reusando o fluxo da 326.** Não existe gatilho automático; nada é gerado sem confirmação. Flag nova `RPG_CREATURE_ART=off|on` (`config/flags.yaml`, release, default `off`).
    - **Cotação:** `ArtQuoteRequest.image_type` aceita `"monster"` (`api.py:1937`) com o campo novo `enemy_id`. O servidor recalcula `portrait_key` a partir do estado (o cliente nunca manda a chave) e cria `ArtGenerationRequest("creature_portrait", portrait_key, "monster", portrait_key, None, request_key)`. A cotação usa o mesmo `repository.issue` (`api.py:4687-4695`), o perfil de preço e o `_guard_image_effect` (kill switch `IMAGE`, `require_paid_effect`).
    - **Recusas:** cota com 409 `creature_portrait_exists` se a chave já está `pending` ou `ready`, e com 422 se o inimigo não está no conflito atual.
    - **Confirmação e débito:** o endpoint de confirmação que já existe (`:4703-4790`): reserva → geração → débito liquidado. É idempotente pela `quote_id` + chave única do registro. Na confirmação, a linha do registro vira `pending` (`insert … on conflict do nothing`); se outro jogador chegou antes, a cotação é liberada sem débito e devolve `ja_em_andamento`.
    - **Job:** `generate_dynamic_art_job` (`workers/dynamic_art_jobs.py:152-244`) com `subject_type="monster"`. O brief vem de `services/art_brief.py` (estética de Valoria da 326, recorte de retrato). O genérico leva só espécie + `description` do bestiário. O importante leva também o nome e a `description` do indivíduo. Nunca vai texto livre do jogador.
    - **Fim:** `ready` → copia para a chave compartilhada (R13.4) e grava `variants`. `failed` → o débito segue a política de falha da 326 (estorno) e a linha volta a permitir cotação.
  - R13.7 — **View:** cada item de `combat.enemies` ganha `retrato` (o dict de R13.3) quando `RPG_CREATURE_ART=on` **ou** quando existe arte curada (`creature`/`creature_family`/`npc`). Sem isso, a chave não existe. `gerar = {"preco_estilhas": int, "escopo": "tipo"|"unico"}` vem do mesmo cálculo de preço da cotação, só para mostrar. O débito real é o da cotação.
  - R13.8 — **Front:** `TargetChip` mostra o retrato à esquerda do nome quando `retrato` existe.
    - `pronto` → `<img>` com `alt`, `loading="lazy"`, `decoding="async"`, tamanho fixo (56 px no celular, 72 px no desktop, `aspect-ratio: 1`, `object-fit: cover`, raio `--r-sm`).
    - `marcador` → caixa do mesmo tamanho, com o `Icon` da família (D-347-H; `aria-hidden`; o nome segue no texto), fundo `--surface-2` e borda `--line-soft`.
    - `gerando` → a melhor arte disponível + o selo "Gerando retrato…".
    - Com `gerar`, aparece embaixo do retrato o botão "Gerar retrato ({preço} Estilhas)" (≥ 44 px no toque). Ele abre a **confirmação inline**: "Gerar o retrato de {nome} por {preço} Estilhas? A imagem fica no bestiário e outros jogadores a verão." (importante: "A imagem é só deste {nome}.") + "Gerar" + "Agora não". "Gerar" chama a cotação e depois a confirmação, com o mesmo cliente de `api.ts` usado na arte da 326. O status chega por `GET /game/{id}/art/{generation_id}` (sem polling novo: a próxima resposta de turno, ou a consulta que a 326 já faz).
    - Fora de combate, ou no meio de um envio de rodada (`busy`), o botão fica `aria-disabled`. O jogador e os aliados não mudam.
  - R13.9 — **Provedor trocável (registro da ideia do dono, D-347-J; não implementar).** Toda geração passa pela porta `ImageGenerator` (`infrastructure/ports.py:27`). Nenhum código desta spec chama `openai_images` direto nem depende de campo específico do provider. Isso deixa aberto trocar por um modelo aberto com LoRA de Valoria numa spec futura.
  - R13.10 — **Testes:** `tests/test_spec347_creature_art.py`.
    - `is_important`:
      - **genéricos:** "Goblin" (`enemy_goblin_1`), "Bandido 2", ad-hoc "Saqueador de Marfim", elite sem nome próprio;
      - **importantes:** chefe sem nome; elite "Grishnak" em `enemy_goblin_3`; NPC hostil via manifesto `npc_in_scene`; padrão com nome próprio.
      - Cada caso traz o motivo esperado.
    - **Caminho genérico:** 3 Goblins → 1 chave `tipo:enemy_goblin`. O 1º jogador paga e gera; um 2º jogo (outro dono) vê `pronto` sem `gerar` e sem débito. "Bandido 1" e "Bandido 2" → mesma chave.
    - **Caminho importante:** "Grishnak" e "Ugruk" (os dois `enemy_goblin`) → 2 chaves `unico:…` distintas, cada uma com a sua oferta `gerar`. Pagar a de Grishnak não muda Ugruk nem o tipo. Grishnak noutro conflito do mesmo jogo → mesma chave, `pronto`, sem oferta. Antes de gerar, ele mostra a arte do tipo (`proprio: false`). NPC hostil com arte curada → `npc:{entity_id}`, `pronto`, sem oferta.
    - **Catálogo:** arte `creature` vence o registro; `creature_family` é usada quando falta a da criatura; sem nenhuma → `marcador` com o ícone da família.
    - **Cobrança (fluxo da 326, com o banco de teste dos testes de arte existentes):**
      - a cotação recalcula a chave no servidor (ignora a enviada);
      - chave `pending`/`ready` → 409 `creature_portrait_exists`, sem reserva;
      - duas confirmações simultâneas na mesma chave → 1 débito, e a outra cotação é liberada (`ja_em_andamento`);
      - `failed` → estorno pela política da 326 e nova cotação permitida;
      - kill switch `IMAGE` → 503, sem reserva;
      - `RPG_CREATURE_ART=off` → nenhuma chave `retrato` (exceto arte curada) e cotação `monster` → 404.
    - **Visibilidade:** HOLD visível só à origem; `unico:{game}` nunca aparece em outro jogo.
    - `test_import_bestiary_art.py`: id inexistente falha; reimportar é idempotente; o `sha256` confere.
    - Round-trip do registro (grava, relê, unicidade).
    - **Provedor:** nenhum import de `infrastructure.openai_images` em `services/creature_art.py` (teste de import).
    - `node --test`: `TargetChip` com `pronto`/`marcador`/`gerando`/`gerar`/sem `retrato` (este idêntico ao markup de hoje).
    - Playwright a 390 e 1440 (`web/e2e/spec347-retrato.spec.ts`): "Gerar retrato" → confirmação → "Gerar" faz cotação e confirmação (requests conferidos na fixture); "Agora não" não faz request; o botão tem ≥ 44 px; R4.4 e R1.5 continuam verdes com retratos.

### Etapa 4b — sem texto livre e "Fugir" no tabuleiro (decisões do dono, D-347-E/F)

- **R18 — Com o tabuleiro aberto, não há texto livre.**
  [F] O composer fica sempre montado e, em combate, só troca o placeholder ("O inimigo avança. O que você faz?") e o rótulo do botão ("Lutar") (`web/src/workspace/ChatSurface.tsx:208-233`). No celular ele já some fora da superfície do chat (`offSurface`, `:184`). No desktop, ao lado do tabuleiro, ele continua ativo (prints `2364091`, `1654717`).
  - R18.1 — Com `combat.active && combat.pilhas` (modo Baralho), o `Composer` não renderiza a área de texto, o botão "Voz" nem o botão de envio. No lugar deles aparece uma nota (`role="note"`): "Na luta, você age pelas cartas do tabuleiro." No celular, aparece também o botão "Ir para o combate" (`ChatSurface.tsx:107-111`, mantido).
  - R18.2 — O rascunho guardado (`chatSessionStore`) não se perde. Quando o conflito acaba, ou sem `pilhas`, o composer volta como estava, com o mesmo texto.
  - R18.3 — Enter e os atalhos de foco no composer não fazem nada nesse estado. O atalho de foco (`onFocusInput`) leva ao painel de Combate.
  - R18.4 — Com o Baralho `off` (sem `pilhas`), nada muda: o composer, o placeholder e "Lutar" ficam como hoje. A linha de base `off` prova isso.
- **R19 — Fugir é um botão do tabuleiro, com resultado visível.**
  [F] Hoje a fuga é uma manobra `flee` dentro do `details` "Manobras e ações", que fica fechado no modo Baralho (`CombateTab.tsx:34-45,287-301`). O resultado só aparece na prosa e em `combat.chase` (`api.py:2896-2907`, `escaped`/`caught`).
  - R19.1 — No modo Baralho, um botão "Fugir" (`btn--ghost`, ícone `exit`, ≥ 44×44 px em `pointer: coarse`) fica na barra de envio, à esquerda de "Encerrar a rodada". No celular, ele divide a barra fixa com "Sem matar" e "Encerrar a rodada", sem quebra de linha (o mesmo teste de R2.4). A manobra `flee` sai do `details` no modo Baralho, para não haver dois caminhos.
  - R19.2 — Com cartas na fila, o toque pede confirmação inline (sem modal): "Fugir agora? A fila desta rodada é descartada." + "Fugir" + "Ficar". Esc e "Ficar" desfazem e devolvem o foco. Com fila vazia, não há confirmação. Se a ação `flee` de `basic_actions` vier com `invalid_reason`, o botão fica `aria-disabled` e mostra o motivo (`REASON_TEXT`).
  - R19.3 — Confirmado, o front envia a ação **estruturada** `fugir` no formato que a **SPEC-346 define** na API. O dado é rolado no motor. O texto de marginália é "Tento fugir." O front não decide nada, só envia e mostra o resultado. Enquanto a 346 não pousa, a fixture do Playwright aceita o mesmo payload; o executor confere o nome do campo no contrato da 346 antes de escrever o teste.
  - R19.4 — O resultado vem do servidor e aparece no topo do tabuleiro, numa faixa `role="status"`. Com `chase.escaped` (ou combate encerrado por fuga): "Você escapou." Com a fuga falha (combate segue ativo, sem escape): "Não escapou: o inimigo ainda está no seu encalço." A faixa some na rodada seguinte.
  - R19.5 — Com o Baralho `off`, a manobra `flee` continua onde está e nada novo aparece.
- **R20 — Testes da Etapa 4b.**
  - `web/e2e/spec347-board-only.spec.ts`:
    - `sem_texto_livre_1440` e `sem_texto_livre_390`: com `pilhas`, não existe `#composer` nem botão "Lutar", e existe a nota. No mesmo combate sem `pilhas`, o composer existe com o placeholder de hoje.
    - `rascunho_volta_apos_conflito`.
    - `fugir_envia_acao_estruturada`: o corpo do POST traz a ação `fugir` do contrato da 346 e nenhuma `jogadas`.
    - `fugir_confirma_com_fila`: com 2 cartas na fila, a 1ª ativação mostra a confirmação e não faz request; "Ficar" e Esc devolvem o foco.
    - `fugir_resultado_escapou` e `fugir_resultado_falhou`: a fixture responde com cada desfecho e a faixa mostra o texto literal.
    - `fugir_alvo_44_390`: caixa ≥ 43,5 px, medida sem rolar antes.
    - `barra_sem_quebra_com_fugir_390`: o R2.4 com "Fugir".
  - `spec347-components.test.mjs`: `Composer` com a prop nova `deckLocked` não renderiza a `textarea`; sem ela, o markup fica idêntico ao de hoje.
  - A linha de base `deck-342-baseline.spec.ts` (já regerada em R15.2) continua verde.

### Transversais

- **R15 — Caminho `off`: só a mudança da iniciativa (R5.3/R5.4), com a linha de base regerada à parte.** Fora R5.3/R5.4, toda mudança de componente compartilhado (`Arena`, `TargetChip`, `Hud`, `Composer`) fica atrás de prop nova opcional, e toda regra CSS nova usa seletor que só existe no Baralho (ou `[data-armed]`/`.arena--compact`).
  - R15.1 — **Prova antes:** com R5.3/R5.4 desligados (o commit anterior à Etapa 2), `deck-342-baseline.spec.ts` (win32, `maxDiffPixelRatio` 0,01) está verde. Isso mostra que nada além da iniciativa mexeu no `off`.
  - R15.2 — **Regeração em commit separado:** logo depois do commit de R5.3/R5.4, um commit **só** com os snapshots `web/e2e/deck-342-baseline.spec.ts-snapshots/*-chromium-win32.png` regerados (`npx playwright test e2e/deck-342-baseline.spec.ts --update-snapshots --workers=1`, em win32). Mensagem: `test(e2e): regenerate SPEC-342 off baseline for SPEC-347 R5.3/R5.4`. O corpo lista o que mudou (linha da Arena sem "Rodada N", chips sem "0 ·", lista "Iniciativa" oculta com a Arena) e diz que nenhuma outra diferença era esperada.
  - R15.3 — **Prova depois:** antes de regerar, o executor salva o diff (`test-results/**-diff.png`) de cada snapshot em `docs/spec347/baseline-diff/`. O revisor confere que as regiões alteradas são só a linha de iniciativa e o bloco "Iniciativa" do HUD. Depois disso, a linha de base volta a ser a referência para o resto da spec (Etapas 3–5 sem regerar).
  - R15.4 — A §9 da SPEC-342 recebe uma nota de 1 linha apontando para este commit (o coordenador aplica no pouso).
- **R16 — Só tokens da 322.** CSS novo/alterado usa só `var(--…)` de `web/src/design/tokens.css`/`styles.css :root`: sem hex/rgb/oklch literal, sem raio literal, sem token novo. `web/tests/deck-tokens-342.test.mjs` passa a cobrir também o bloco `/* SPEC-347 */`, e `npm run lint` fica verde.
- **R17 — Alvos ≥ 44 px.** Em `pointer: coarse`, todo controle novo ou movido (Cancelar/Jogar/Outro alvo na linha de ações, "Desfazer fila" na fila, "Ver a rodada inteira", botões da Forja com motivo, "Fugir", "Gerar retrato" e a sua confirmação) tem caixa ≥ 44×44 px, medida pelo Playwright com o mesmo critério da 321/342 (≥ 43,5 px).

### Fora de escopo

- Tudo de narração e motor da SPEC-346 (tirar a LLM das rodadas, o resumo final, o enredo). Isso inclui o nome de inimigo vindo da prosa ("primeira criatura hostil que surgir na galeria", print `2364091`) e o inimigo "sem Vitalidade" ainda de pé na rodada 2 (print `1883475`). Esta spec só lê `out` e mexe em `_basic_attack`/`_resolve_actor_turn` para **anotar** (R5.2, R14.1).
- Renumerar as rodadas, por exemplo mostrar a rodada que está sendo decidida em vez da última resolvida. É semântica de motor/relógio (`tactical_round`).
- Retrato do jogador e dos aliados no tabuleiro. Geração automática de retrato (D-347-B: só por pedido pago do jogador). Treinar ou integrar um LoRA/modelo aberto (D-347-J: só registro). Gerar as imagens do bestiário (projeto paralelo do dono; esta spec só define a entrada, R13.2). Mapa visual de zonas. Animação nova além de `motion`.
- Filtro "Utilitárias" no Acervo (só o rótulo, R9).
- Ligar flags no staging (ato do coordenador/dono depois do `done`).

## 3. Design técnico

**Arquivos alterados (front)**

| Arquivo | Mudança | Req. |
|---|---|---|
| `web/src/components/combat/DeckCombat.tsx` | `data-armed`; prévia pré-semeada; rolagem também em `preview.status`; ordem da mira (ações antes das regras); passa `compact` à Arena; monta `RoundBoard` | R1, R4, R14 |
| `web/src/components/combat/PreviewChip.tsx` | aceita `pending` (renderiza o texto de `loading`) | R1.1 |
| `web/src/components/combat/PlayQueue.tsx` | "Desfazer fila" dentro da fila em ≤ 640 px (classe, sem `matchMedia`: os dois botões existem e o CSS mostra um só), selo numérico + `sr-only` | R2 |
| `web/src/combat/Arena.tsx`, `web/src/combat/TargetChip.tsx` | props opcionais `compact`, `order` no texto honesto (R5.3), `retrato` | R4, R5, R13 |
| `web/src/components/Hud.tsx` | chips de iniciativa sem `init` (os dois modos); lista oculta com `arena`; `Combat` ganha `deck?: boolean` (sem rodada no cabeçalho) | R5.4 |
| `web/src/workspace/tabs/CombateTab.tsx` | passa `deck` ao `CombatTab`; rolagem do desfecho por `result_event_id`; "Fugir" e a faixa de resultado | R5.4, R8, R19 |
| `web/src/workspace/ChatSurface.tsx` (`Composer`) | prop `deckLocked` | R18 |
| `web/src/api.ts` | `quoteImage`/`confirmImage` aceitam `image_type: "monster"` + `enemy_id` | R13.6 |
| `web/src/components/combat/KeywordTip.tsx` | posição preferida acima | R6 |
| `web/src/components/combat/ForjaPanel.tsx`, `web/src/cardRewards.ts`, `web/src/types.ts` | motivos por via e por linha; `aria-disabled` + `aria-describedby` | R7 |
| `web/src/components/tabs/DeckCard.tsx` | `utilitaria` | R9 |
| `web/src/combat/deck.ts` | `fmtPct` inteiro; `roundLogView()` | R10, R14 |
| `web/src/App.tsx` | zera a rolagem guardada em `handleContinueSave` | R11 |
| `web/src/components/combat/RoundBoard.tsx` (**novo**) | registro da rodada | R14 |
| `web/src/combat/familyIcon.ts` (**novo**) | `FAMILY_ICON: Record<familia, IconName>` (só ícones existentes, D-347-H) | R13.8 |
| `web/public/art/bestiario/` (**novo**, vazio + `.gitkeep`) | destino da arte do bestiário importada | R13.2 |
| `web/src/workspace.css` | bloco `/* SPEC-347 */`: `[data-armed]`, linha de ações, selo, `nowrap`, `.arena--compact`, `.arena__empty-zones`, retrato, `RoundBoard` | todos |

**Arquivos alterados (backend)**

- `services/conflict_orchestrator.py`: `_basic_attack` grava `atk["fora_de_turno"] = label` (`:1214`). `_resolve_actor_turn` e o laço de `:2472-2498` gravam `out["turn_spans"]` (R14.1). São só anotações. A 346 mexe neste arquivo: rebase cuidadoso (D-347-9).
- `services/combat_preview.py`: rótulo em `mech_log` (R5.2); `round_log()` e `last_round_log` em `store_mech_log` (R14.2).
- `api.py::_combat_block`: `registro_rodada` (junto de `mech_log`, `:2992-2995`); `retrato` por inimigo (`:2874-2893`).
- `services/card_rewards.py`: constantes de motivo; `forge_view` com `motivos` e `bloqueio` (`:614-635`); `forget`/`purge` usam as constantes.
- `services/creature_art.py` (**novo**): `is_important`, `portrait_key`, `portrait_for`, `gerar_offer` (lê o manifesto em `state["combat"]["encounter"]`). Não importa nenhum provider (R13.9).
- `services/visual_catalog.py`: aceita `creature`/`creature_family`; nenhuma entrada nova nesta spec (o dono importa).
- `scripts/import_bestiary_art.py` (**novo**): importação idempotente (R13.2).
- `services/asset_pipeline.py`: `shared_object_key(asset_kind="monster", entity_id, asset_id, variant, sha256)`.
- Registro de retratos: migration Supabase `app.creature_portraits` (hosted, `portrait_key` único). Em legacy/local não há gravação (só catálogo e marcador).
- `api.py`: `ArtQuoteRequest.image_type` + `"monster"` e `enemy_id` (`:1937`); ramo `monster` em `create_image_quote` (`:4637-4700`) e na confirmação (`:4703-4790`); o status (`:4797`) e a lista de gerações (`:2152-2159`) aceitam `monster`.
- `workers/dynamic_art_jobs.py`: com `subject_type == "monster"` e geração `ready`, copia as variantes para `shared_object_key` e marca a linha do registro como `ready`. A cobrança é a da 326, sem mudança.
- `config/flags.yaml`: `RPG_CREATURE_ART` (release, `off|on`, validade 25/01/2027).

**Tipos**

```python
class RoundLogEntry(TypedDict):
    ator_id: str; ator_nome: str; lado: Literal["heroi", "inimigo", "aliado"]
    carta_id: str | None; carta_nome: str | None        # None = ataque básico
    alvo_id: str | None; alvo_nome: str | None
    origem: Literal["turno", "reacao"]; rotulo: str | None   # "Contra-ataque", "Ataque de Oportunidade"
    resultado: Literal["acerto", "erro", "critico", "supercritico", "efeito"]
    dano: int | None; efeito: str | None                 # "+2 Proteção", "Sangramento"

class CreaturePortrait(TypedDict):
    estado: Literal["pronto", "gerando", "marcador"]
    src: str | None; familia: str; icone: str; alt: str
    proprio: bool          # True = arte do indivíduo (importante); False = arte do tipo/família ou marcador
    gerar: GerarOffer | None

class GerarOffer(TypedDict):
    preco_estilhas: int; escopo: Literal["tipo", "unico"]

def is_important(enemy: dict, manifest: dict | None) -> tuple[bool, str]:   # motivo: "chefe"|"npc"|"nome_proprio"|"generico"
def portrait_key(enemy: dict, manifest: dict | None, *, game_id: str) -> str: # tipo:… | unico:… | npc:…
```

```ts
// CombatBlock: registro_rodada?: RoundLogEntry[];   EnemyView: retrato?: CreaturePortrait;
// ForjaView: esquecer.motivos?: {descanso: string|null; templo: string|null}; purgar.motivos?: {medico: string|null; templo: string|null};
//            baralho[i].bloqueio?: string|null
export function fmtPct(n: number): string;                         // R10
export function roundLogView(e: RoundLogEntry): { who: string; card: string; to: string; chip: string; tone: "hit" | "miss" | "crit" | "fx" };
```

**Exemplo real (ids canônicos)**

```json
"registro_rodada": [
  {"ator_id": "player", "ator_nome": "Brannoc", "lado": "heroi", "carta_id": "golpe_do_penitente",
   "carta_nome": "Golpe do Penitente", "alvo_id": "enemy_saqueador_1", "alvo_nome": "Saqueador de Marfim",
   "origem": "turno", "rotulo": null, "resultado": "acerto", "dano": 5, "efeito": null},
  {"ator_id": "enemy_saqueador_1", "ator_nome": "Saqueador de Marfim", "lado": "inimigo", "carta_id": null,
   "carta_nome": null, "alvo_id": "player", "alvo_nome": "Brannoc", "origem": "reacao",
   "rotulo": "Contra-ataque", "resultado": "erro", "dano": null, "efeito": null}
],
"enemies": [{"id": "enemy_saqueador_1", "name": "Saqueador de Marfim",
  "retrato": {"estado": "marcador", "src": null, "familia": "bruto", "icone": "combat",
              "alt": "Retrato de Saqueador de Marfim", "proprio": false,
              "gerar": {"preco_estilhas": 40, "escopo": "tipo"}}}]
```

O executor confere os ids reais de carta e de criatura (`data/cards/`, `data/bestiary.json`) antes de escrever os testes. Os do exemplo vêm do smoke. O preço `40` é ilustrativo: o valor real sai do perfil de preço.

## 4. Plano passo a passo

Python: `bash scripts/dev/py.sh -m pytest <arquivos> -q` (no máximo `-n 2`). Web: `cd web && npm test` (`node --test`) e `npm run test:e2e -- <spec> --workers=1`. Fixtures: `web/e2e/deck-342-helpers.ts::armDeck` ganha opções `zones`, `previewDelayMs`, `roundLog`, `portraits`. A linha de base `deck-342-baseline.spec.ts` roda antes e depois de cada etapa. Ela é regerada **uma única vez**, na Etapa 2, em commit próprio (R15.2).

### Etapa 1 — 390 px: mira, barra e presságio (R1–R3, R17 parcial)

1. **Testes primeiro.** `web/e2e/spec347-mobile.spec.ts`: `mira_livre_apos_previa_390` e `mira_livre_apos_previa_1440` (R1.5, com 1 e 2 inimigos), `barra_sem_quebra_fila_cheia` (R2.4), `presságio_faixa_inteira` (R3), `alvos_44_mira_e_fila` (R17). `web/tests/spec347-components.test.mjs`: `PreviewChip` com `pending` = texto "Lendo os sinais…"; "Desfazer fila" presente na fila (classe `play-queue__clear--inline`).
2. **Implementação:** R1.1–R1.4, R2, R3.
3. **Verificação:** os testes acima, `spec345-mobile390.spec.ts`, `deck-combat-342.spec.ts` e a linha de base, todos verdes.

### Etapa 2 — Arena e iniciativa (R4, R5)

1. **Testes primeiro.** `tests/test_spec347_initiative_view.py::test_order_matches_resolved_turns` (oráculo; esperado verde, ver R5.1). `tests/test_spec347_mech_log.py`: `test_counter_attack_labeled`, `test_opportunity_labeled`, `test_plain_attack_unchanged`. `spec347-components.test.mjs`: "Rodada" uma vez com e sem `pilhas`, sem `.initiative` com a Arena, sem "0 ·"; `Arena` sem `compact` com markup idêntico ao de hoje, exceto a linha de iniciativa (snapshot de string). `web/e2e/spec347-desktop.spec.ts::arena_tres_zonas_1440` (R4.4).
2. **Implementação:** R5.2 (backend) → R4 → linha de base verde (R15.1) → commit de R5.3/R5.4 → commit separado da regeração (R15.2, com os diffs em `docs/spec347/baseline-diff/`, R15.3).
3. **Verificação:** os testes acima, mais `tests/test_spec334_*`/`tests/test_spec342_*` do log, `web/tests/deck*.test.mjs`, `combat-gesture.spec.ts` e a linha de base regerada.

### Etapa 3 — tooltip, Forja, desfecho, prévia, rótulo, Livro (R6–R12)

1. **Testes primeiro.** `tests/test_spec347_forge_reasons.py` (R7.4). `web/tests/spec347-logic.test.mjs`: `fmtPct` (R10.2), `TYPE_LABEL` (R9). `spec347-components.test.mjs`: `ForjaPanel` com motivos, `aria-disabled` e `aria-describedby`. Playwright: `tooltip_nao_cobre_botao` (R6.2), `desfecho_abre_no_topo` (R8.2, 390 e 1440), `forja_confirmacao_e_via_fechada` (R12.1), `has_loot_mobile` (R12.2), `reabrir_save_mostra_ultima_narracao` (R11.1; **vermelho antes** da correção).
2. **Implementação:** R7 (backend → front), R6, R8, R9, R10, R11.
3. **Verificação:** o escopo verde, `tests/test_spec333_*` da Forja e `npm run lint`.

### Etapa 4 — registro da rodada (R14)

1. **Testes primeiro.** `tests/test_spec347_round_log.py` (R14.6), `RoundBoard` SSR, Playwright `registro_acima_da_arena` (390/1440) e `arena_tres_zonas_1440` com 4 entradas.
2. **Implementação:** R14.1 → R14.2 → view → `RoundBoard` → CSS.
3. **Verificação:** o escopo verde. Conferir que o `mech_log` em string de um save de arena gravado antes não muda (`test_plain_attack_unchanged`).

### Etapa 4b — sem texto livre e "Fugir" (R18–R20)

1. **Testes primeiro:** os de R20. Os de fuga dependem do nome do campo do contrato da 346: se a 346 ainda não pousou, o executor copia o contrato da spec da 346 e registra isso na §9.
2. **Implementação:**
   - `Composer` ganha a prop `deckLocked`, passada por quem monta o composer com `combat.active && !!combat.pilhas`.
   - `PlayQueue` ganha "Fugir" + a confirmação.
   - `CombateTab` esconde o `flee` do `details` no Baralho e monta a faixa de resultado.
3. **Verificação:** o escopo verde, `combat-gesture.spec.ts` (caminho `off`) sem edição e a linha de base.

### Etapa 5 — retrato (R13)

0. Antes de criar o writer, consultar `project_index/state_ownership` (seletivo) e registrar `creature_portraits` como canonical owner, com invariantes: chave única; `ready` é imutável; só o worker de arte muda o status; nada vai para outro jogo antes de valer a regra de visibilidade (R13.5).
1. **Testes primeiro.** `tests/test_spec347_creature_art.py` e `tests/test_import_bestiary_art.py` (R13.10), o round-trip do registro e um teste da migration (padrão dos testes de migration existentes em `tests/`). `TargetChip` SSR. `web/e2e/spec347-retrato.spec.ts`.
2. **Implementação:** `is_important`/`portrait_key` → catálogo `creature`/`creature_family` + script de importação → `portrait_for` + `FAMILY_ICON` → view → ramo `monster` na cotação/confirmação → registro + `shared_object_key` no worker → front (retrato, marcador, "Gerar retrato" com confirmação).
3. **Verificação:** o escopo verde, `tests/test_spec326_*` e os testes da carteira/cotação de imagem existentes, `tests/test_shared_pool*`, a flag registrada (`scripts/flag_registry.py` verde) e a linha de base.

### Etapa 6 — prints e smoke

1. `web/e2e/spec347-prints.spec.ts` (`test.skip` sem `RPG_SPEC347_PRINTS=1`) grava em `docs/spec347/depois/` os mesmos cenários do smoke: `390-previa`, `390-fila`, `1440-inicio-3-zonas`, `1440-previa`, `1440-tooltip-espolio`, `1440-forja`, `1440-pos-combate`, `390-pos-combate`, `1440-registro`, `390-registro`, `1440-retratos`.
2. Smoke real (§6).

## 5. Critérios de aceite

- [ ] R1–R20 com teste nomeado verde (`node --test`, Playwright `--workers=1` e pytest do escopo).
- [ ] Toda medição de sobreposição feita **sem rolar antes**, por `elementFromPoint`/caixa, a 390 e a 1440 (R1.5, R2.4, R4.4, R8.2) e por interseção no tooltip (R6.2).
- [ ] Linha de base `off`: verde antes de R5.3/R5.4 (R15.1); regerada só uma vez, em commit próprio e documentado, com os diffs em `docs/spec347/baseline-diff/` conferidos pelo revisor (R15.2/R15.3); verde em win32 até o fim da spec.
- [ ] Zero pendência no `off`: nenhum "0 ·" e "Rodada" uma vez só (R5.5).
- [ ] Alvos ≥ 44 px em `pointer: coarse` (R17). `npm run lint` e `deck-tokens-342.test.mjs` (com o bloco 347) verdes; nenhum token novo (R16).
- [ ] `test_order_matches_resolved_turns` verde, ou o desvio corrigido e registrado (R5.1).
- [ ] `reabrir_save_mostra_ultima_narracao` vermelho antes e verde depois (R11.1), com o vermelho registrado na §9.
- [ ] **→ SPEC-352 (transferido, NÃO cumprido):** registro `creature_portraits` com canonical owner registrado, round-trip testado e flag `RPG_CREATURE_ART` em `config/flags.yaml`. Nenhuma geração sem cotação confirmada pelo jogador (teste); um débito por chave (teste de concorrência).
- [ ] `scripts/import_bestiary_art.py` documentado em `docs/guias/ARTE_VISUAL.md` (pasta de entrada, nomes de arquivo, como rodar).
- [ ] Prints "depois" em `docs/spec347/depois/` (Etapa 6).
- [ ] `npm run build` e `npm test` verdes. `uv run pytest` verde (suíte completa: coordenador, no pouso).
- [ ] Saves antigos carregam: `last_round_log` ausente → sem registro; nenhum campo novo obrigatório.
- [ ] Smoke real (§6) executado e registrado.

## 6. Smoke test com LLM real

O mesmo roteiro do smoke de origem: API local legacy, DeepSeek, preset com `RPG_CARD_DECK`, `RPG_ENEMY_INTENT`, `RPG_SCENE_CARDS`, `RPG_COMBAT_NONLETHAL` e `RPG_CARD_REWARDS` `on`. Se a 346 já tiver pousado, ela entra junto. São ~8–12 requests de turno, dentro do orçamento.

1. A 390 (emulador com toque): iniciar um conflito em Skallgard; armar "Golpe" → a prévia chega → "Jogar em X" e "Cancelar" visíveis, sem rolar. Enfileirar 2 cartas + "Sem matar" → a barra fica numa linha. Registrar o print.
2. A 1440: um conflito com 3 zonas (Montanhas Afiadas, como no print `2364091`) → a mão aparece sem rolar, os chips ficam legíveis e o registro da rodada fica acima da Arena, com o contra-ataque rotulado, se houver.
3. Vencer → o painel abre no desfecho, com "Continuar" visível; o Espólio com tooltip não cobre "Levar"; a Forja mostra o motivo das vias fechadas; o Acervo mostra "Utilitária".
4. Voltar ao menu e reabrir o save → o Livro abre na última narração.
5. **Retrato (staging, `RPG_CREATURE_ART=on`, conta de teste com Estilhas):**
   - Importar 1 imagem de criatura e 1 de família com o script → os chips usam as duas sem outra mudança.
   - Uma criatura sem arte → marcador da família + "Gerar retrato (X Estilhas)". "Agora não" não cobra. "Gerar" → cotação → confirmação → débito liquidado → a imagem aparece nos dois chips da mesma criatura.
   - Um 2º jogo (outra conta) com a mesma criatura → imagem sem oferta e sem débito.
   - Um chefe nomeado → oferta própria (`unico:`) e, antes dela, a arte do tipo.
   - Registrar custo e tempo da geração.
6. Conferir em `docs/spec347/depois/` os prints equivalentes aos de `smoke/` e anotar na §9.

## 7. Riscos & compatibilidade

- **Saves:** `last_round_log` e `turn_spans` são aditivos e transitórios (o `out` não é salvo; `last_round_log` substitui a cada rodada). Save antigo sem eles → sem registro, sem erro. `forge_view`/`retrato` são só view.
- **Caminho `off`:** só a iniciativa muda (R5.3/R5.4), com a linha de base regerada uma vez, em commit próprio e com os diffs conferidos. Todo o resto entra por prop opcional, e o CSS novo usa seletores do Baralho.
- **Conflito com a 346:** as duas mexem em `conflict_orchestrator.py`. A 347 só **acrescenta** duas anotações (`fora_de_turno`, `turn_spans`). Quem pousar por último faz o rebase. Se a 346 já produzir um registro estruturado da rodada para o resumo final, a 347 o consome em vez de criar outro (D-347-9).
- **Custo do retrato:** zero para a casa. Só gera com cotação confirmada pelo jogador (fluxo da 326: kill switch, preço, reserva, débito liquidado, estorno na falha). Fora do `hosted`, só catálogo e marcador.
- **Corrida entre jogadores:** dois jogadores pedem a mesma chave → a unicidade do registro na confirmação garante 1 débito; o outro recebe `ja_em_andamento`, sem cobrança.
- **Privacidade/segurança do retrato:** a chave compartilhada não leva dono nem jogo, e o brief não leva texto do jogador (só o conceito da criatura e, no importante, o nome e a `description` do indivíduo). O jogador é avisado na confirmação de que o retrato do tipo fica visível a outros. Criatura em HOLD e importante `unico:{game}` não expõem a imagem a outro jogo.
- **Arte do bestiário:** o script de importação recusa id que não existe e confere o `sha256`. A arte entra pelo catálogo público (`visibility: public`); nada de URL externa em runtime.
- **Rolagem automática:** R1.2 e R8.1 rolam o painel por conta própria. A rolagem fica restrita a `block: "nearest"`/`"start"` no próprio painel, só com o painel visível, uma vez por chave, para não brigar com a rolagem do jogador.
- **MockLLM/FallbackLLM:** nenhuma chamada LLM nova (a geração de imagem não usa `get_llm`). O registro e o retrato são deterministas.
- **Latência/quota:** zero request novo por turno. A geração só acontece por pedido do jogador, é assíncrona e fica fora do caminho do turno.

## 8. Decisões

**Do dono (27/10):**

- **D-347-A — Corrigir tudo** o que o smoke achou (itens 1–11), com status `approved` na criação.
- **D-347-B — Retrato do inimigo no tabuleiro; geração opcional e paga pelo JOGADOR** (revisto em 27/10).
  - Não há geração automática nem paga pela casa.
  - No retrato de um inimigo sem imagem aparece "Gerar retrato (X Estilhas)", com confirmação inline. A geração reusa a cotação, a reserva, o débito liquidado e a idempotência da arte dinâmica da SPEC-326, com o preço do perfil existente (R13.6).
  - A imagem vai para o registro compartilhado: genérico na chave do tipo (todos reaproveitam), importante na chave própria. Quem vier depois vê de graça.
- **D-347-D — Genérico reaproveita, importante tem arte própria.**
  - O inimigo genérico ("Goblin", "Bandido 2", tier padrão sem nome próprio) usa a arte do tipo, do bestiário ou do pool.
  - O inimigo importante (chefe, elite com nome, NPC hostil, inimigo nomeado) tem arte própria, com identidade própria. Outro Goblin importante tem outra arte.
  - Critério e chaves em R13.0/R13.1. Antes da arte própria, o importante mostra a do tipo/família (R13.3).
- **D-347-G — A fonte principal é a arte do bestiário que o dono gera em projeto paralelo.** Ela entra pelo catálogo curado (`data/visual_assets.json`, `creature` por id e `creature_family` por família), com os arquivos em `web/public/art/bestiario/` e o script `scripts/import_bestiary_art.py` (R13.2). O tabuleiro usa a arte automaticamente quando ela existe.
- **D-347-H — Sem imagem: marcador simples com o ícone da família**, do sistema de ícones da 322, a custo zero. Sem silhueta e sem SVG novo. Mapa (`web/src/combat/familyIcon.ts`, só ícones existentes): `predador → combat` · `predador_apice → unique` · `bruto → combat` · `covarde_oportunista → exit` · `conjurador → card-virtue` · `morto_vivo_implacavel → death` · `guardiao → card-reaction` · `tatico → ruler` · `lider_matilha → quest` · `emboscador → dark` · `abissal → abyss` · `desconhecida → dark`. O executor pode trocar um ícone por outro já existente, sem criar ícone novo.
- **D-347-I — Inimigo de missão** só tem arte própria se for chefe, NPC hostil ou tiver nome próprio (aceita a recomendação do autor). A antiga "prioridade da fila" deixa de existir, porque não há fila automática.
- **D-347-J — Registro, não implementar:** o dono pensa em treinar um LoRA num modelo aberto para baratear. A geração fica atrás da porta `ImageGenerator` (`infrastructure/ports.py:27`) para trocar de provedor depois (R13.9).
- **D-347-K — Zero pendência no caminho `off`.** O "0 · Heróis/Inimigos" e a "Rodada N" repetida também são corrigidos no `off` (R5.3/R5.4). A linha de base win32 da 342 é regerada em commit separado e documentado (R15.2/R15.3).
- **D-347-E — Sem texto livre com o tabuleiro aberto** (Baralho `on`). O campo "O que você faz" some durante o conflito e volta depois, com o rascunho (R18). Com o Baralho `off`, nada muda.
- **D-347-F — Fugir é um botão do tabuleiro** que manda a ação estruturada `fugir`. A SPEC-346 define o contrato na API e rola o dado no motor. O tabuleiro mostra "Você escapou." / "Não escapou…" (R19). Alvo ≥ 44 px.
- **D-347-C — O tabuleiro é a superfície principal da rodada.** O registro das cartas tem destaque visual, em vez de prosa (complementa a 346, que tira a LLM das rodadas).

**Do autor (recomendadas e adotadas; o dono pode reverter):**

- **D-347-1 — Item 5 não é bug de dado.** A ordem exibida é a real da rodada resolvida. O que engana é o rótulo (presente vs. passado), a repetição de "Rodada" e as reações fora de ordem sem rótulo. O ajuste de backend é só anotar `fora_de_turno` no log. O oráculo R5.1 protege essa leitura.
- **D-347-2 — Com carta armada, a barra de envio sai do modo fixo no celular.** Alternativa: manter a barra fixa e aumentar o `scroll-margin`. Rejeitada porque depende da altura da mira (prévia de 1 ou 2 linhas, regras) e foi justamente o que falhou na 345 R14.
- **D-347-3 — "Desfazer fila" sai da barra fixa no celular e vai para a fila.** Revisa a D-342-5 só em ≤ 640 px. Motivo: três botões não cabem em 366 px sem quebra. Desfazer é operação da fila.
- **D-347-4 — Arena compacta (R4) só no modo Baralho; iniciativa (R5.3/R5.4) nos dois modos** (por D-347-K). Fora a iniciativa, o `off` não muda.
- **D-347-5 — Motivos da Forja vêm do servidor**, com os mesmos textos dos erros de `forget`/`purge`, em vez de o front deduzir pela regra de ouro e templo. Motivo: *mecânica é Python* e uma única fonte de texto.
- **D-347-6 — Livro reaberto abre no fim**, igual a uma 1ª abertura, e não no início da última narração. Correção mínima, sem mudar a regra de auto-rolagem da SPEC-204.
- **D-347-7 — Cópia para a chave compartilhada no fim do job**, mantendo o original privado da 326. Assim nenhum endpoint da 326 muda de semântica, e o registro aponta só para objetos sem dono/jogo.
- **D-347-9 — Fronteira com a 346.** A 347 dona do registro estruturado (`turn_spans`, `round_log`) e do retrato. A 346 consome o registro no resumo final, se precisar. As duas mexem em `conflict_orchestrator.py`; a 347 só acrescenta anotações.
- **D-347-10 — Microcopy (literal):**

| Onde | Texto |
|---|---|
| Arena, iniciativa (Baralho) | Na última rodada, {Heróis\|Inimigos} agiram primeiro. · `title`: A iniciativa é rolada de novo a cada rodada. |
| Arena, zonas vazias | Também na cena: {zona} · {zona} |
| Barra de envio, nome acessível | Encerrar a rodada, {n} carta(s) |
| Fila (celular) | Desfazer fila |
| Prévia pré-semeada | Lendo os sinais… |
| Forja, motivos | os textos de `services/card_rewards.py:382,386,389,392,512,515,519`, prefixados por "{via}: " |
| Tipo de carta | Utilitária |
| Registro, título | O que se jogou na rodada {N} |
| Registro, ver mais (celular) | Ver a rodada inteira ({n}) |
| Registro, anúncio | Rodada resolvida: {n} jogada(s). |
| Registro, chip | Acerto · −{dano} / Erro / Crítico · −{dano} / {efeito} |
| Retrato, alt | Retrato de {nome} |
| Retrato, botão | Gerar retrato ({preço} Estilhas) |
| Retrato, confirmação (genérico) | Gerar o retrato de {nome} por {preço} Estilhas? A imagem fica no bestiário e outros jogadores a verão. · Gerar · Agora não |
| Retrato, confirmação (importante) | Gerar o retrato de {nome} por {preço} Estilhas? A imagem é só deste {nome}. · Gerar · Agora não |
| Retrato, gerando | Gerando retrato… |
| Retrato, já em andamento | Outro jogador já está gerando este retrato. Ele aparece em breve, sem custo. |
| Composer travado (Baralho) | Na luta, você age pelas cartas do tabuleiro. |
| Botão de fuga | Fugir |
| Confirmação de fuga | Fugir agora? A fila desta rodada é descartada. · Fugir · Ficar |
| Marginália da fuga | Tento fugir. |
| Resultado da fuga | Você escapou. / Não escapou: o inimigo ainda está no seu encalço. |

**O que o dono ainda precisa decidir:** nada bloqueia a execução. A Etapa 5 fica nesta spec, atrás de `RPG_CREATURE_ART`, com revisão Sol obrigatória. A única entrega dele é externa e não bloqueia: soltar as imagens do bestiário na pasta de entrada e rodar `scripts/import_bestiary_art.py` (até lá, o tabuleiro mostra o marcador).

## 9. Notas de implementação

Executor (Sonnet, 27-28/10). Status NÃO alterado (segue `approved`); revisão Sol pendente.

**Entregue (com teste):** Etapa 1 (R1–R3, R17 parcial), Etapa 2 (R4, R5), Etapa 3 (R6–R10, R12), Etapa 4 (R14), Etapa 4b (R18–R20) e, da Etapa 5, só o núcleo determinístico de R13 (ver abaixo).

**Oráculo R5.1:** `test_order_matches_resolved_turns` ficou **verde** (18 casos, 3 iniciadores × 6 seeds): a leitura de D-347-1 se confirma, nenhum ajuste em `agents/combat.py:2337`.

**R11 (Livro reaberto):** a hipótese **não foi reproduzida** pela UI web: não existe rota "play → saves" na mesma aba (Conta volta para `play`; "Nova jornada" abre `create`; só o botão nativo do Capacitor leva a `saves`), então o teste vermelho de R11.1 não pôde ser escrito. A correção defensiva de R11.2 (`setChatSession(gid, {scrollTop: null, atBottom: true})` em `handleContinueSave`) está aplicada, **sem teste e2e** (registrar como risco; teste real exige o fluxo nativo).

**R15 (linha de base 342):** a fixture de `deck-342-baseline.spec.ts` não tem `order` na combate, então a linha de iniciativa e o chip "0 ·" **não aparecem** nos snapshots: eles continuam verdes (win32, `maxDiffPixelRatio` 0,01) depois de R5.3/R5.4 e **não houve regeração nem commit de snapshots** (sem diffs em `docs/spec347/baseline-diff/`). A cobertura do `off` fica em `spec347-desktop.spec.ts::off_iniciativa_honesta` + SSR do `Hud`/`Arena`. Se o revisor quiser a prova pixel a pixel, é preciso adicionar `order` à fixture da baseline e regerar (decisão do coordenador). Também foi atualizado `deck-combat-342.spec.ts` ("B-4": o cabeçalho do HUD no Baralho agora é só "Combate", R5.4) e `deck-queue.test.mjs` ("42,5 %" → "43 %", R10).

**Anotações de backend (aditivas, só view):**
- `_basic_attack` grava `atk["fora_de_turno"] = label` **somente quando `out` tem `resolved_turns`** (dentro de uma rodada real). Sem essa guarda o golden de 308 cartas da SPEC-330 (`test_card_effects_grammar::test_equivalencia_…`) mudava de hash nas cartas de reação.
- `_resolve_actor_turn` virou um wrapper fino sobre `_resolve_actor_turn_inner` (corpo intocado) que grava `out["turn_spans"]`; turno negado grava `negado: true` (`_note_denied_span`). Menos linhas tocadas = rebase mais fácil com a 346.
- `store_mech_log(meta, out, actors, enemy_ids=None)` ganhou o 4º parâmetro; `agents/combat.py` passa `{ids dos inimigos}` (1 linha; a 346 também mexe neste arquivo).
- `api.py`: `registro_rodada` na view (só com `last_round_log`), `_enemy_portrait` + `retrato` por inimigo. Dependências da 346: nenhuma no código; o registro estruturado aqui é o `turn_spans`/`round_log` (D-347-9: a 346 pode consumi-lo; ela tem o seu `services/round_log.py` — há duplicidade de nome/propósito a reconciliar no pouso).

**Contrato de "Fugir" (R19.3):** a spec da 346 **não define** uma ação estruturada `fugir`: ela só mantém a fuga por texto (`FLEE_RE`). O front usa o contrato que já existe na API (`ActionRequest.action_kind = "flee"`) com `input_text = "Tento fugir."` e sem `jogadas`. Se a 346 criar outro campo, trocar em `CombateTab.tsx::doFlee`. O resultado vem de `combat.active`/`combat.round`: ao fim do combate com `fleeRound` setado → "Você escapou."; combate ativo e rodada +1 → "Não escapou: …" (sem ler `chase.escaped`, que a view só traz durante a perseguição).

**Decisão do coordenador (28/10): o resto do R13 (R13.4 registro, R13.6 cotação/confirmação `monster`, migration, worker, testes de cobrança/concorrência de R13.10, fiação do botão "Gerar retrato") sai da 347 e vira a SPEC-352; critérios correspondentes marcados "→ SPEC-352", não cumpridos. O botão fica oculto enquanto `gerar` for null (hoje sempre).**

**Etapa 5 (R13) — parcial, ATRÁS de `RPG_CREATURE_ART` (registrada em `config/flags.yaml`):**
- feito: `services/creature_art.py` (`is_important`, `portrait_key`, `portrait_for` com catálogo → registro → marcador, `FAMILY_ICON`, visibilidade game/shared, sem import de provider), `retrato` na view, `scripts/import_bestiary_art.py` (idempotente, valida ids) + doc em `ARTE_VISUAL.md`, `web/public/art/bestiario/`, `familyIcon.ts`, `Portrait` no `TargetChip` (56/72 px, marcador, `gerando`) e a oferta "Gerar retrato" (botão + confirmação inline) **sem fiação** (`onGenerate` não é passado por `CombateTab`).
- **NÃO feito:** cotação/confirmação `monster` (R13.6) em `api.py`, copia para `shared_object_key`, migration `app.creature_portraits` + registro hosted (`PortraitRegistry` só tem o `EmptyRegistry`), ramo `monster` no worker, `gerar` sempre `null` na view, testes de cobrança/concorrência (R13.10). O motivo foi orçamento/risco: isso toca carteira, Postgres e worker, e exige o banco de teste dos testes de arte. Estado seguro: com a flag `off` nada muda; com `on` aparece só o marcador/arte curada e nenhuma oferta.
- `portrait_for` para importante sem registro mostra a arte do tipo (`proprio: false`), conforme R13.3.

**Outros desvios/decisões:** "Rodada N" do `RoundBoard` mostra `round − 1` (rodada já resolvida; assume que `combat.round` já avançou). Zonas vazias só saem da grade no Baralho (`compact`). "Desfazer fila" existe em duas cópias (barra/fila) e o CSS mostra uma só. Rótulos da barra a 390 px usam fonte 0,75 rem (três ações em 366 px; o `clipped` do helper de medição pega corte de texto). O registro da rodada usa `RoundBoard` próprio sem retratos miniatura (selo de ícone para o herói). `spec347-prints.spec.ts` gera `docs/spec347/depois/` (7 prints; inclui também `1440-tooltip-espolio`, `1440-forja`, `390-pos-combate`). Smoke real (§6) **não executado** (sem staging/chave nesta rodada).

**Correções da revisão Sol (28/10):** P1-1/P2-5 importador agora grava em `web/public/art/v1/bestiario/` (`thumbnail` ≤ 120 KB e `display` ≤ 768 px ≤ 300 KB), `validate_visual_assets` aceita `creature` (ids do bestiário e `bst:*`) e `creature_family`, teste roda o validador contra uma CÓPIA do catálogo real; troca de arte exige `--force`, entrada curada à mão é recusada sem ele, `bst_*` é validado, tudo é codificado antes de escrever (sem WebP órfão). P2-1 `creature_art.variant_url` lê o formato real do job (lista com `variant: thumb|full` e `key`); como o job só grava `key`, a conversão chave→URL é da SPEC-352 (sem `url` cai no marcador). P2-2 o resultado da fuga só vale depois que `data` muda; envio que falha mostra "A fuga não chegou ao mestre. Tente de novo.". P2-3 `Composer.onFocusCombat` + e2e `rascunho_volta_apos_conflito`. P2-4 `round_log` em ordem cronológica de `out["attacks"]`. P2-6 print `1440-retratos.png` próprio (arena recortada com retrato). Alvos da barra ≥ 44 px (antes 43,5). F-2: `resetBookScroll` extraído e testado. F-3: o `off` de R5.3/R5.4 tem teste dedicado com fixture com `order` (`off_iniciativa_honesta`) e SSR; a baseline 342 NÃO foi regerada.

**Desvios aceitos (P2-7):** R15.2/R15.3 (regeração da baseline + diffs em `docs/spec347/baseline-diff/`) dispensados porque a fixture da baseline não tem `order` e os snapshots seguem verdes. O smoke real (§6) fica com o coordenador antes de `done`. P1-2 (reconciliar com a 346: rótulo `fora_de_turno` × `label`, `store_mech_log`, renomear `round_log` → `round_board` e incluir os ticks de DoT) fica para quando a 346 pousar.
