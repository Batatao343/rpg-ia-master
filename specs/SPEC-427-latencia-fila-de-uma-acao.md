# SPEC-427 — latencia-fila-de-uma-acao

> **Status:** `approved` (coordenador, 22/11, por delegação do dono: "faz tudo ai… eu autorizo a fazer tudo que vc pode fazer, deixa de pendente só o q vc nao pode mesmo"; flag `off` por padrão, `on` só no staging; veto do dono possível)
> **Criada:** 2026-11-22 · **Atualizada:** 2026-11-22
> **Depende de:** SPEC-420 (código na `main` desde 22/11; o fluxo "envio novo sem consulta" é a base do autoenvio). SPEC-316 e SPEC-320 `done`.
> **Desbloqueia:** item L1b de `docs/auditorias/latencia-turno-2026-11-12.md:135-138`; a promoção da flag para todos os jogadores (spec curta de seguimento, depois do §6).
> **Risco:** `alto` (proposto). O autoenvio dispara um turno sem clique no instante do envio: um bug gasta saldo do jogador (turno cobrado), pode mandar ação para um estado que mudou (combate, morte) e mexe na idempotência por `operation_id` e na retomada da SPEC-320. Revisão `spec-reviewer` (Opus). Mínimo aceitável: `médio` com revisor Sonnet, se o coordenador considerar que a flag desligada por padrão basta como contenção.
> **Requer:** staging (flag `on` só lá; smoke §6 depois do deploy do staging, que em 22/11 está com a sessão `rpg-ia-master-82`: migrações 413/410 aplicadas e rate cards publicados, falta o deploy). Sem chave nova. Sem `web:`.
> **Domínios de revisão:** concorrência (fluxos de UI invalidados por `turnToken`/`seq`; os itens de `asyncio` do guia não se aplicam, ver §3 Concorrência), api (chave nova em `/auth/config` e leitura da flag: item "valores quase válidos" do guia)
> **Evidência:** e2e Playwright com o SSE controlado: com o `state` do turno 1 segurado, Enter com texto → 0 envios a mais até o `state`; depois do `state`, exatamente 1 `POST /game/action/stream` do turno 2 com aquele texto e `action_id` novo. Hoje o Enter é ignorado e o 2º envio nunca acontece (falha antes). Um e2e por caso de devolução ao rascunho (§2 R10). Com a flag desligada, os e2e atuais de `turn-wait`/`turn-retry`/`turn-preflight` passam sem edição.

---

## 1. Contexto & Objetivo

Depois que a narração aparece (evento `narrative` com `done`), o turno ainda não acabou: o servidor roda arquivista, `enrich` e o save, e só então manda o `state` e fecha o stream (`web/src/api.ts:225,242,257-262`). Nesse intervalo o cliente mostra o selo "registrando…" (`web/src/workspace/TurnStatus.tsx:34,49-50`), o botão fica desabilitado com "Aguardando o narrador" (`web/src/workspace/ChatSurface.tsx:246-247`) e o Enter é ignorado (`ChatSurface.tsx:187`, `if (busy || blocked) return;`). `busy` só cai no `finally` de `handleAction` (`web/src/App.tsx:603-608`). A medição de 13/11 no staging (n=60) mostrou que esse intervalo é "sim ou não": em 39 de 60 turnos o envio libera 0,24 s depois do texto; em **21 de 60 o jogo fica 4,4 s travado** (mediana; até 9,6 s), em todo descanso, em quase toda fala com NPC já criado e na viagem a região nova (`docs/auditorias/latencia-turno-medicao-2026-11-13.md:53`).

A L1b da auditoria (`docs/auditorias/latencia-turno-2026-11-12.md:135-138`) propõe uma **fila de uma ação**: nesse intervalo o jogador digita e dá Enter; o texto fica num chip "na fila" e o cliente envia sozinho quando o `state` chega e o pending do turno é limpo. Ler e digitar passam a se sobrepor ao fechamento do turno. **Não reduz tempo de servidor**; reduz a espera percebida entre turnos. Se a SPEC-422 (arquivista sem IA, `in-progress`, flag `off`) for ligada, a janela encolhe e o ganho da fila também; as duas não se excluem.

**Isto muda uma regra aprovada pelo dono** e é tratado de frente na §8 D1:

- SPEC-316 D2 (`specs/SPEC-316-latencia-narracao-antes-do-arquivista.md:221-223`): "selo discreto … ; **input bloqueado até `state`**". A alternativa **rejeitada** ali foi "liberar input na narração", com o motivo literal: "o próximo turno esperaria o lock e a mensagem do jogador entraria antes do save".
- SPEC-320 R13 (`specs/SPEC-320-front-espera-typewriter-banner.md:52-53`): "o envio continua travado até o `state`". E R4 (`:42`): botão `disabled` + `aria-busy` durante o turno.
- SPEC-420 (`specs/SPEC-420-latencia-cliente-sem-getoperation.md:22,40`) registrou em 13/11 que a fila não estava aprovada naquele momento.

A fila **não** é a alternativa rejeitada. Nada vai ao servidor antes do `state` do turno anterior: o texto fica só na memória da página até o turno fechar com o save confirmado, e o envio é o mesmo `handleAction` de um Enter manual, com o mesmo guarda de `busy`. O motivo da rejeição (mensagem do jogador antes do save; turno esperando o lock) continua impossível, e isso vira invariante com teste (I1, I2). O que muda é só a UX: o campo deixa de "ignorar" o Enter nessa janela. Por isso a mudança entra **atrás de flag, desligada por padrão, ligada só no staging** (§8 D1), e a regra antiga vale byte a byte com a flag desligada (I6).

## 2. Requisitos

### Flag

- **R1 — flag no servidor.** `RPG_ACTION_QUEUE=off|on`, default `off`, lida por `action_queue_on()` em `services/latency_flags.py` com o `env_choice` que o módulo já usa (`services/latency_flags.py:17-23`: strip + lower; valor fora da lista = default). Registrada em `config/flags.yaml` com `kind: release`, `default: "off"`, `spec: SPEC-427`, `expires: 2027-02-28` (padrão de `config/flags.yaml:176-181`).
- **R2 — exposição ao cliente pelo mecanismo que já existe.** `/auth/config` (`routes/auth.py:31-64`) inclui `"action_queue": True` **só** quando `action_queue_on()`; desligada, a chave fica ausente. É o mesmo padrão de `client_latency_report` (`routes/auth.py:61-62`, SPEC-200 R10), lido no bootstrap sem requisição extra e servido com `no-store` (`tests/test_surfaces_221.py:90`). Não existe hoje nenhuma flag de build no front (`import.meta.env`/`VITE_*`: zero ocorrências em `web/src`); não se cria uma.
- **R3 — leitura no cliente.** `api.getAuthConfig` (`web/src/api.ts:49-52`) chama `setActionQueueEnabled(config.action_queue === true)` ao lado de `setClientLatencyReport`. `AuthConfig` (`api.ts:39-47`) ganha `action_queue?: boolean`. Qualquer valor diferente de `true` (ausente, `"true"`, `1`) = desligado.

### Comportamento com a flag ligada

- **R4 — quando o Enter enfileira.** Um submit do compositor (Enter pelo `shouldSubmitOnKey`, `ChatSurface.tsx:218-223`, ou clique/toque no botão primário) **enfileira** em vez de ser ignorado se e somente se, no render do submit: flag ligada; `busy === true`; `turn.stage === "narrated"` (narração entregue, `state` ainda não chegou: `App.tsx:534-535`, `web/src/turnWait.ts:52-55`); `!blocked` (`web/src/components/PlayScreen.tsx:65`); sem combate ativo (`!data.combat?.active`); fora do simulador (`!data.combat_simulation?.enabled`); tabuleiro fechado (`!deckLocked`, `ChatSurface.tsx:204`); `text.trim()` não vazio. Em qualquer outro estágio (`waiting`, `failed-after-narration`) o submit faz o que faz hoje (ignorado, o texto fica no campo). Justificativa do recorte em `narrated`: é a janela medida; antes da narração o jogador ainda não leu o desfecho, e o estágio `waiting` tem "Tentar de novo"/"Continuar esperando" (`TurnStatus.tsx:56-62`), que conflitariam com uma ação esperando.
- **R5 — o que o jogador vê.**
  - Ao enfileirar, o campo esvazia (como num envio normal, `ChatSurface.tsx:192`) e aparece, dentro do compositor e acima do campo, o chip `.queued-action` (`role="group"`, `aria-label="Ação na fila"`): rótulo visível "Na fila:" + o texto em uma linha com reticências; o nome acessível do grupo contém o texto inteiro.
  - O chip tem um botão "Tirar da fila" (nome acessível = texto visível; área ≥ 44×44 px).
  - Com a flag ligada e `turn.stage === "narrated"`, o botão primário fica **habilitado**, sem `aria-busy`, com o texto "Pôr na fila" (nome acessível = texto visível, SPEC-320 R4/SPEC-201 A13). Nos demais estágios do turno, o botão é o de hoje.
  - O selo "registrando…" continua igual.
- **R6 — uma ação só; segundo submit substitui.** Com uma ação na fila, um novo submit com texto não vazio **substitui** o texto da fila (o anterior é descartado) e anuncia "Ação na fila substituída." Submit com campo vazio não faz nada. Nunca há duas ações na fila (§8 D3).
- **R7 — tirar da fila.** "Tirar da fila" remove o chip, devolve o texto ao rascunho por `mergeDraft` (R10.1), põe o foco no campo com o cursor no fim e anuncia "Ação tirada da fila; o texto voltou ao campo." Nada é enviado.
- **R8 — autoenvio.** Quando o turno da `seq` em que a ação entrou na fila fecha (`busy === false`) com `turn.delivered === true` (R9) e nenhuma condição de R10 vale, o compositor chama `onAction(texto, { reaction_card_id: reactionCardId })`, as mesmas opções do submit manual (`ChatSurface.tsx:193`), **exatamente uma vez**, **a partir de um efeito** (`useEffect`) do render em que `busy` já é `false`. Nunca de dentro de callback do stream nem do `finally` de `handleAction`: o `busy` do closure ficaria velho e o guarda de `App.tsx:473` recusaria o envio (armadilha registrada em `latencia-turno-2026-11-12.md:138`). Antes de chamar `onAction`, o efeito limpa a fila (estado e ref), de modo que uma segunda execução do efeito não acha nada para enviar. O chip some; o eco do jogador é o que `handleAction` empurra (`App.tsx:516`).
- **R9 — sinal positivo `delivered`.** `TurnWait` (`turnWait.ts:62-75`) ganha `delivered: boolean`, `false` em `IDLE_TURN`. Em `handleAction`:
  - Uma variável local `replaced` começa `false` e vira `true` em `onReplace` e `onReset` (`App.tsx:539-540`).
  - No caminho de sucesso do stream, depois de `if (!active()) return;` e de `setPending(null)` (`App.tsx:544-545`), `setTurn(t => ({ ...t, delivered: hadChunks && !replaced }))`.
  - O fallback `POST /game/action` (`App.tsx:575-586`) **nunca** marca `delivered`.
  - O `finally` (`App.tsx:607`) preserva `delivered` ao voltar a `idle`, como já preserva `error`.
  - `submit` (`App.tsx:478`) e `resetTurn` (`App.tsx:73`, usado em `retryTurnInner`, `discardPending` e `useSaves`) zeram `delivered` (já zeram, por partir de `IDLE_TURN`).
  - A fila só envia com o sinal positivo. Qualquer fechamento sem ele devolve o texto ao rascunho (R10). Assim não é preciso enumerar cada caminho de falha para estar correto; a lista de R10 é a cobertura de teste.
- **R10 — devolução ao rascunho.** Nos casos abaixo a fila **não** envia: o texto volta ao campo (R10.1), aparece uma nota visível curta abaixo do campo (`.composer-hint`, `aria-hidden`; some no próximo submit ou na próxima edição do campo) e a região viva única anuncia "A ação na fila não foi enviada: <motivo>. O texto voltou ao campo." Cada linha vira um teste (§4 Etapa 3).

  | # | Caso | Como o cliente detecta | Motivo na nota |
  |---|---|---|---|
  | a | Combate começou no turno | `state` com `combat.active` | "começou um combate" |
  | b | Desfecho de combate no turno | `combat_result.result_event_id` diferente do valor no momento do enfileiramento | "o combate mudou a cena" |
  | c | Morte / tela de morte / memorial | `death_pending` ou `game_over` no `state` | "a Roda do Abismo aguarda sua escolha" |
  | d | Escolha de nível nova | `player_stats.pending_choices[0].id` diferente do valor no enfileiramento (o modal abre, `PlayScreen.tsx:68-71,86`) | "há uma escolha de nível" |
  | e | Erro do turno sem narração mostrada | fechou com `delivered === false` e `turn.error` preenchido (`App.tsx:593-596`) | "o turno falhou" |
  | f | Falhou depois de narrar ("não salvo") | `turn.stage === "failed-after-narration"` com `busy === false` (`App.tsx:551-561`) | "o turno não foi registrado" |
  | g | `replace` ou `reset` da narração | `delivered === false` porque `replaced` (R9) | "a narração mudou" |
  | h | Stream caiu depois da narração e o fallback POST concluiu | `delivered === false` (R9; a narração lida foi removida em `App.tsx:575-577` e trocada por `onTurn`) | "a narração mudou" |
  | i | Pending não limpo | `loadPending(owner, gid) !== null` no momento do envio (outra aba ou `clearPendingIfOwn` sem efeito) | "há uma ação pendente" |
  | j | Turno invalidado por `turnToken` | `seq` mudou antes do fechamento, ou fechou por `resetTurn` (retry `completed`/`unknown`, `App.tsx:630,637,642,650`) → `delivered === false` | "o turno foi retomado" (um `resetTurn` no mesmo `seq` anuncia "a narração mudou": os dois são inalcançáveis pela UI com a fila cheia, texto aceito) |
  | k | Sem rede no momento do envio | `navigator.onLine === false` quando o efeito decide | "sem conexão" |
  | l | Troca de partida | o compositor da partida desmonta (`Workspace key={game_id}`, `PlayScreen.tsx:124`) | ver R11 |
  | m | Reload, logout, sessão expirada | a página ou o compositor some | ver R11 |

  - **R10.1 — `mergeDraft(fila, campo)`:** campo vazio (só espaços) → texto da fila; senão `fila + "\n" + campo` (a fila primeiro, porque foi escrita antes). Grava no rascunho por `setInput` (`ChatSurface.tsx:150-156`), o que já atualiza o `chatSessionStore`.
  - **R10.2 — foco:** se o foco estava no botão "Tirar da fila" (que some) ou no `body`, vai para o campo; senão não se move.
- **R11 — nada persiste; sem ressurreição.** A fila vive na memória do compositor e no `chatSessionStore` (campo novo `queued?: string` por `game_id`, `web/src/workspace/chatSessionStore.ts:2-7`), nunca em `localStorage` (mesma regra do rascunho, SPEC-204 R7/R8, `chatSessionStore.ts:1`). Escreve-se `queued` ao enfileirar ou substituir e apaga-se ao enviar, tirar ou devolver. **Não há escrita no desmontar** (evita repor texto depois de `forgetAllChatSessions` no logout, `App.tsx:43-47`). Um compositor que monta com `queued` gravado (voltou à partida) faz `mergeDraft` para o rascunho, apaga `queued` e mostra a nota "A ação na fila não foi enviada: você saiu da partida." **Montar nunca envia.** Reload perde a fila e o rascunho, como hoje perde o rascunho.
- **R12 — voz fora.** A voz (SPEC-187) não enfileira. O botão de voz continua desabilitado durante o turno (`ChatSurface.tsx:239`). O submit que enfileira cancela uma captura ativa como o submit de hoje (`ChatSurface.tsx:191`); na prática ela não existe com `busy`. Motivo: a transcrição é assíncrona (upload + STT), e um ditado que termina depois do `state` criaria uma segunda origem de texto disputando a fila.
- **R13 — cartas, combate e atalhos fora.** Jogada de carta e ações básicas (`web/src/workspace/tabs/CombateTab.tsx`, mira em `web/src/combat/targeting.ts:71`), atalhos de lugar (`ChatSurface.tsx:78,84`), sugestões de contexto (`ChatSurface.tsx:202`) e a barra de ação pendente (`App.tsx:800-813`) continuam desabilitados com `busy`, sem fila. Motivos: a jogada carrega alvo e custo validados contra o estado **atual** (`valid_targets`, Entropia); o `state` do turno seguinte muda esse estado e a jogada enfileirada viraria `invalid_target` (SPEC-205 R9, `App.tsx:599-601`). Além disso, a rodada do baralho é resolvida sem IA e não tem a janela de 4,4 s.
- **R14 — acessibilidade e mobile.**
  - Anúncios só pela **região viva única** do compositor (`TurnStatus.tsx:43`, SPEC-320 R1), que ganha a prop `queueNote?: string`, concatenada ao texto vivo do estágio. Nenhum `aria-live` novo. Textos: ao enfileirar, "Ação na fila: será enviada quando o turno for registrado."; e os de R6, R7 e R10.
  - Chip e botão operáveis por teclado (Tab chega ao botão; Enter/Espaço acionam) e por toque; área ≥ 44×44 px (`web/e2e/touch-targets.spec.ts`); axe sem violação `serious`/`critical` com o chip visível, em 1440×900 e 390×844.
  - O botão "Pôr na fila" segue a regra label-in-name (`web/e2e/a11y-label-in-name.spec.ts`).
  - No mobile com o compositor fora da superfície (`offSurface`, `Workspace.tsx:365`), o compositor continua montado e a fila envia normalmente: o jogador confirmou com Enter e foi olhar outra aba durante a espera, que é o uso esperado.
- **R15 — tamanho.** `web/src/App.tsx` tem 961 linhas (`wc -l`, 22/11) e o gate é 1.000 (`scripts/dev/size_budget.py`). A mudança em `App.tsx` é no máximo +8 linhas líquidas (`replaced`, `delivered`, `finally`, a prop da flag se necessária). A lógica nova vai em `web/src/queuedAction.ts` (puro) e `web/src/hooks/useQueuedAction.ts`. `ChatSurface.tsx` (268 linhas) só consome o hook e renderiza o chip.
- **R16 — servidor.** Só a flag: `services/latency_flags.py`, `routes/auth.py` (1 linha), `config/flags.yaml`, preset do staging (§3). Nenhuma rota de turno, SSE, idempotência ou persistência muda.

### Fora de escopo

- Qualquer mudança no servidor além da flag (R16): rotas de turno, SSE, `/operations/{op}`, lock, arquivista.
- Liberar o envio antes do save ou resolver o cliente no `state` antes de o stream fechar (L2 da auditoria, SPEC-213). A fila e a L2 se substituem para o jogador rápido (`latencia-turno-2026-11-12.md:138`).
- Fila com mais de uma ação, ou fila no estágio `waiting`.
- Narração menor (SPEC-428) e arquivista sem IA (SPEC-422).
- Cartas, ações de combate, atalhos de lugar, sugestões e voz (R12, R13).
- Telemetria de uso da fila (quantos enfileiramentos/devoluções): pediria campo novo no beacon de latência (servidor). Fica para a spec de promoção, se o dono quiser números.
- Promover a flag para todos e aposentá-la: spec de seguimento depois do §6 e da decisão do dono (§8 D6).
- Extração de `handleAction` para hook (SPEC-392, `draft`). Se ela pousar antes, `replaced`/`delivered` vão para o hook equivalente com o mesmo contrato.

### Invariantes

- **I1 — nada vai ao servidor antes do `state` do turno anterior.** Com o `state` do turno 1 segurado e a ação na fila, o número de `POST /game/action/stream` e `POST /game/action` não muda até o `state` ser entregue e o stream fechar. (e2e `fila: nada sai antes do state; 1 envio depois`; unit `decideQueued só envia com delivered e busy falso`.)
- **I2 — no máximo um turno em voo.** O guarda é uma trava SÍNCRONA (`web/src/turnLock.ts`: `lockTurn(token)` em `handleAction`, antes de qualquer `await`; `unlockTurn(token)` no `finally` e `unlockTurn()` em `auth-expired` e no ramo `completed` do retry, em `App.tsx` junto do `setBusy(false)`; o ramo `unknown` não solta, reescreve a trava com o token do reenvio), não só o `busy` do closure: depois do commit do `state` há duas janelas em que o DOM já mostra `busy=false` e o `busy` do closure ainda deixa passar (entre o commit e o efeito da fila, e entre o efeito e o re-render do `setBusy(true)`); o `pending` não protege (grava depois de um `await`). Achado na revisão (P1-1): Enter manual no commit do `state` com a fila cheia saía com 3 streams. **Prioridade: o envio manual vence e a fila devolve** — o autoenvio, ao achar a trava presa, devolve o texto da fila ao rascunho com a nota "outro envio saiu antes"; um submit do compositor com a trava presa e `busy` ainda falso é ignorado e o texto fica no campo. Nunca se perde texto nem se cobra dois turnos. Depois do `state`, há exatamente 1 envio a mais, nunca 2, mesmo com re-render e StrictMode. (e2e `I2 corrida` com a fila ligada e desligada; e2e "trava solta" para erro de rede, HTTP 422, `auth-expired` e retry `unknown` e `completed` (este com a flag off e on: sem o unlock o 2º envio nunca chega); unit `turnLock`, `efeito não envia duas vezes` por e2e.)
- **I3 — idempotência por `operation_id` preservada.** A ação da fila ganha o seu `operation_id` só no envio, por `preparePendingWithOrigin` com `created === true` (`App.tsx:483`; SPEC-420 R1): o `action_id` do turno 2 é diferente do turno 1 e igual ao pending gravado durante o voo. O pending do turno 1 já foi limpo antes (`App.tsx:542`). O autoenvio faz 0 consultas a `/game/{game}/operations/{op}` (SPEC-420 R2). (e2e `fila: action_id novo e 0 consultas`.)
- **I4 — sem eco duplicado nem eco órfão.** Enquanto está na fila, o texto não entra no log (0 `article.msg--player` com o texto); depois do envio, 1. Na devolução, 0. (e2e de envio e de cada devolução.)
- **I5 — retomada intacta.** `retryTurn`/`retryTurnInner` (`App.tsx:614-658`), `resumeSession` (`App.tsx:132-152`), abertura de save com pending (`web/src/hooks/useSaves.ts`) e o fluxo "não salvo" + "Tentar de novo" não mudam. Com a fila ligada, "Tentar de novo" depois de `failed-after-narration` reenvia o **mesmo** `action_id` e a fila devolvida **não** dispara depois do sucesso do retry. (e2e `fila: não salvo devolve e o retry não leva a fila`; e2e existentes `turn-wait.spec.ts:195`, `turn-retry.spec.ts`, `turn-preflight.spec.ts` sem edição.)
- **I6 — flag desligada = comportamento de hoje.** Sem `action_queue` no `/auth/config`: Enter em `narrated` ignorado, botão desabilitado com "Aguardando o narrador", texto vivo "registrando…", nenhum `.queued-action` no DOM, `chatSessionStore` sem `queued`. (e2e existente `turn-wait.spec.ts:163` "envio travado até o state" sem edição; novo `fila desligada: Enter ignorado como hoje`.)
- **I7 — sem ressurreição de texto.** Logout e sessão expirada com ação na fila → 0 envios e o texto não reaparece para o próximo dono na mesma aba. (e2e `fila: sessão expirada não envia nem guarda`.)

## 3. Design técnico

**Arquivos novos**

- `web/src/queuedAction.ts` (puro, sem React), com testes unitários:
  - `setActionQueueEnabled(on: boolean): void` / `actionQueueEnabled(): boolean`: variável de módulo, mesmo padrão de `setClientLatencyReport` (`web/src/lib/turnLatency.ts:132-135`).
  - `interface QueuedAction { text: string; seq: number; gid: string; combatResultId: string | null; choiceId: string | null }`.
  - `interface QueueSnapshot { enabled: boolean; busy: boolean; stage: TurnStage; seq: number; delivered: boolean; error: boolean; gid: string | null; blocked: boolean; fighting: boolean; simulation: boolean; deckLocked: boolean; combatResultId: string | null; choiceId: string | null; deathOrOver: boolean; pendingStored: boolean; online: boolean }`.
  - `canEnqueue(s: QueueSnapshot, text: string): boolean`: R4.
  - `type QueueDecision = { kind: "wait" } | { kind: "send" } | { kind: "return"; reason: ReturnReason }`.
  - `decideQueued(q: QueuedAction, s: QueueSnapshot): QueueDecision`: `wait` enquanto `s.seq === q.seq && s.busy`; `return` com o motivo da tabela R10 (ordem de prioridade: j, f, e, g/h, a, b, c, d, i, k); `send` só com `s.seq === q.seq && !s.busy && s.stage === "idle" && s.delivered` e nenhuma condição de devolução.
  - `mergeDraft(queued: string, draft: string): string`: R10.1.
  - `returnNote(reason: ReturnReason): string` e as constantes de texto de R5–R7 e R10.
- `web/src/hooks/useQueuedAction.ts`: `useQueuedAction({ snapshot, gameId, owner, onAction, reactionCardId, setInput, focusInput }): { queued: string | null; enqueue(text): boolean; remove(): void; note: string | null; liveNote: string | null }`.
  - Guarda `onAction` num ref atualizado a cada render (padrão de `ChatSurface.tsx:59-61`) e decide num `useEffect` com dependências `[snapshot.busy, snapshot.seq, snapshot.stage, snapshot.delivered, queued]`.
  - Lê `loadPending(owner, gid)` e `navigator.onLine` dentro do efeito.
  - Limpa a fila (state + ref `sentSeq`) antes de chamar `onAction`.
  - Faz a conversão `queued`→rascunho no mount (R11).
- `web/tests/queuedAction.test.mjs`: unit (Etapa 1), no mesmo formato de `web/tests/pending.test.mjs:1-10` (esbuild → data URL).
- `web/e2e/action-queue.spec.ts`: e2e (Etapas 2–3), nas duas viewports como `turn-wait.spec.ts:68-70`.
- `web/e2e/sseControl.ts`: extrai `installControlledSse`, `ev`, `push`, `closeSse`, `sseReqs`, `waitSseReqs`, `finalState` de `web/e2e/turn-wait.spec.ts:34-66` sem mudar o código. `turn-wait.spec.ts` passa a importar dali, sem mudar nenhuma asserção. Limite conhecido: o fake guarda um stream controlável por vez (`w.__sse` é sobrescrito a cada requisição, `:50`), o que basta, porque o turno 2 só precisa ser contado e lido em `__sseReqs`.

**Arquivos alterados**

- `services/latency_flags.py`: `def action_queue_on() -> bool: return _choice("RPG_ACTION_QUEUE", ("off", "on"), "off") == "on"` + linha na docstring (`:1-11`).
- `routes/auth.py:61-62`: `**({"action_queue": True} if action_queue_on() else {}),` (import local, como os vizinhos).
- `config/flags.yaml`: entrada `RPG_ACTION_QUEUE` (R1), em ordem alfabética.
- `scripts/staging/vercel_env.py`: `"RPG_ACTION_QUEUE",  # SPEC-427: off|on (ausente = off)` em `WORLD_FLAGS` (`:147-160`) e na lista de variáveis gerenciadas (`:80-117`).
- `scripts/staging/staging_flags.json`: `"RPG_ACTION_QUEUE": "on"` em `flags` (`:10-37`) e uma entrada datada em `_updated`: "22/11 SPEC-427: fila de uma ação on só no staging, decisão do coordenador por delegação do dono (22/11), veto possível".
- `web/src/api.ts`: R3.
- `web/src/turnWait.ts`: `delivered: boolean` em `TurnWait` e `IDLE_TURN` (`:62-75`).
- `web/src/App.tsx` (`handleAction`): `let hadChunks = false, replaced = false;` (`:518`); `onReset`/`onReplace` marcam `replaced` (`:539-540`); `setTurn(... delivered ...)` depois de `setPending(null)` (`:545`); `finally` preserva `delivered` (`:607`). Nada mais.
- `web/src/workspace/chatSessionStore.ts`: `queued?: string` em `ChatSession`.
- `web/src/workspace/ChatSurface.tsx` (`Composer`): monta o `QueueSnapshot` com o que já recebe (`data`, `busy`, `blocked`, `turn`, `deckLocked`) mais `owner` (prop nova, vinda de `Workspace.tsx:364`, que já tem `owner`); `submit` (`:185-194`) vira `if (blocked) return; if (busy) { if (queue.enqueue(text)) setInput(""); return; }` (com a flag desligada, `enqueue` devolve `false` e o caminho é o de hoje); renderiza o chip e a nota; `Pressable` com `disabled`/`pending`/rótulo de R5 só quando `actionQueueEnabled() && turn.stage === "narrated"`.
- `web/src/workspace/TurnStatus.tsx`: prop `queueNote?: string` no texto vivo (`:34-36,43`).
- `web/src/workspace/Workspace.tsx:364`: passa `owner` ao `Composer`.
- `web/src/styles.css`: `.queued-action` (uma linha, reticências, botão ≥ 44 px, tokens existentes; sem cor nova).
- `web/e2e/fixtures.ts:299`: `actionQueue = false` no `DeterministicBackend`; `/auth/config` inclui `action_queue: true` quando ligado.
- `tests/test_latency_client_endpoint.py` (onde mora o teste de `/auth/config` com flag, `:39-52`): casos de R2.

**Sem schema novo, sem mudança de formato no `localStorage` ou no save.**

**Fluxo com a flag ligada (exemplo):** Enter "olho o céu" em `narrated` → `canEnqueue` → chip + `queued` gravado no store → `narrative replace`? não → `state` → stream fecha → `setPending(null)` + `delivered: true` → `finally`: `busy=false`, `stage=idle` (mesmo batch) → render → efeito: `decideQueued` = `send` → limpa a fila → `onAction("olho o céu", {…})` → `handleAction` do render atual (`busy` falso) → `preparePendingWithOrigin` `created === true` → eco → `POST /game/action/stream`.

### Concorrência

Sem thread nem `asyncio`. O que existe é corrida de fluxos de UI e de renders React, invalidados por `turnToken`, `session`, `gameId` e `seq`.

| Evento | Estado no momento | Resultado esperado | Teste |
|---|---|---|---|
| `state` chega; `setPending(null)`, `setBusy(false)` e `stage=idle` no mesmo tick | fila com a `seq` atual | um render com `busy=false`; efeito envia 1× pelo `handleAction` desse render | e2e `fila: nada sai antes do state; 1 envio depois` |
| Efeito roda 2× (re-render, StrictMode) | fila já limpa pelo 1º | 2ª execução acha `queued === null`; ref `sentSeq` impede reenvio | unit `efeito não envia duas vezes`; e2e conta 2 streams no fim do turno 2 |
| Envio manual (Enter, sugestão, atalho) no commit do `state` com a fila cheia | `busy` do DOM falso, trava presa pelo manual | o autoenvio devolve a fila ao rascunho ("outro envio saiu antes"); 1 só turno em voo | e2e `I2 corrida` |
| `replace` chega depois da fila | `narrated`, fila gravada | `replaced=true` → `delivered=false` → devolução "a narração mudou" | e2e caso g |
| Stream cai depois da narração; fallback POST conclui | fila gravada | `delivered=false` → devolução; 1 POST (o do fallback) e nenhum stream a mais | e2e caso h |
| "Tentar de novo" (`completed`/`unknown`) | `turnToken++`, `resetTurn` | `delivered=false` ou `seq` nova → devolução; o reenvio do retry é o único envio | e2e caso j |
| Erro com `narrative_shown` → "Tentar de novo" | `failed-after-narration`, `busy=false` | devolução no fechamento; o retry reenvia o mesmo `action_id`; a fila não dispara depois | e2e `não salvo devolve e o retry não leva a fila` |
| Sessão expira com fila (`rpg:auth-expired`, `App.tsx:100-111`) | `session++`, tela `auth` | compositor desmonta; 0 envios; nada reescrito no store | e2e I7 |
| Troca de partida com fila | `Workspace` remonta | 0 envios; ao voltar, o texto está no rascunho com a nota | e2e caso l |
| Outra aba grava pending do mesmo jogo | `loadPending !== null` no envio | devolução "há uma ação pendente"; nenhum envio | e2e caso i (pending injetado no `localStorage` antes do `state`) |
| `navigator.onLine === false` no envio | `state` entregue pelo SSE controlado com o contexto offline | devolução "sem conexão" | e2e caso k (`context.setOffline(true)` antes de empurrar o `state`) |

Itens de `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § concorrência (`:16-21`): tratam de `await to_thread`/cancelamento Python e não se aplicam, exceto "espera em teste sempre com teto": usar `expect.poll`/`toBeVisible` com o timeout do Playwright; `waitForTimeout` nunca é o oráculo de "não enviou". A prova de "não enviou" é a contagem antes de soltar o `state` e de novo depois do fim do turno 2. § api (`:33-36`): o item "guard mais largo que o uso documentado" vira o caso parametrizado de R2 (`"1"`, `"true"`, `"yes"` → ausente; `"on"`, `" ON "` → presente). Os demais itens de api (smoke de "não exposto", guard de boot de produção, inventário AST de rota) não se aplicam: não há rota nova.

## 4. Plano passo a passo

### Etapa 0 — caracterização (antes de editar produto)

1. Ler `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § concorrência e § api; registrar no hand-back o que não se aplica.
2. Extrair `web/e2e/sseControl.ts` (puro movimento) e rodar `turn-wait.spec.ts` verde.
3. Escrever o e2e principal da Etapa 2 com `backend.actionQueue = true` e rodar contra o código atual. Esperado **antes**: o chip não aparece e `__sseReqs` fica em 1 depois do `state` (o Enter foi ignorado). Colar a mensagem de falha no hand-back. Se passar antes, parar: a premissa da spec está errada.
4. Rodar contra o código atual `fila desligada: Enter ignorado como hoje`: deve **passar antes e depois** (controle).

### Etapa 1 — flag e lógica pura

1. **Testes primeiro.**
   - `tests/test_latency_client_endpoint.py`: `test_auth_config_action_queue_absent_by_default`; `test_auth_config_action_queue_on` (`on` e `" ON "` → `action_queue is True`); `test_auth_config_action_queue_near_valid_values_stay_off` parametrizado (`"1"`, `"true"`, `"yes"`, `""` → chave ausente).
   - `web/tests/queuedAction.test.mjs`:
     - `canEnqueue` só em `narrated` com `busy`; falso em `waiting`, `failed-after-narration`, `idle`, `blocked`, `fighting`, `simulation`, `deckLocked`, texto vazio e flag desligada.
     - `decideQueued`: `wait` durante `busy`; `send` só com `delivered && !busy && stage idle && seq igual`; `return` com o motivo certo para cada linha a–k de R10; prioridade quando duas condições valem juntas (j antes de a).
     - `mergeDraft`: campo vazio, só espaços, campo com texto.
     - Flag: `actionQueueEnabled()` falso por padrão.
2. **Implementação:** R1–R3 no servidor e no `api.ts`; `queuedAction.ts`.
3. **Verificação:** `bash scripts/dev/pt.sh tests/test_latency_client_endpoint.py tests/test_flag_registry.py` (o gate de flags) e `cd web && npm test`.

### Etapa 2 — envio pela fila (e2e que falha antes)

1. **Testes** (`web/e2e/action-queue.spec.ts`, SSE controlado, 1440×900 e 390×844):
   - `fila: nada sai antes do state; 1 envio depois`: abre o jogo; Enter "olho ao redor"; empurra `ack` + chunks + `narrative done`; espera "registrando…"; o botão diz "Pôr na fila" e está habilitado; preenche "olho o céu" + Enter; chip "Na fila: olho o céu" visível; campo vazio; `__sseReqs` = 1; 0 `POST /game/action`; 0 eco "olho o céu". Empurra `state` + fecha. `waitSseReqs(2)`; `__sseReqs[1].input_text === "olho o céu"`; chip some; 1 eco "olho o céu". Empurra o turno 2 completo; no fim, `__sseReqs` = 2 e 0 `POST /game/action`.
   - `fila: action_id novo e 0 consultas`: no mesmo roteiro, `__sseReqs[1].action_id` ≠ `__sseReqs[0].action_id` e igual ao `operation_id` do pending no `localStorage` durante o voo do turno 2; 0 requisições a `/^\/game\/[^/]+\/operations\/[^/]+$/` (SPEC-420 I1).
   - `fila: segundo Enter substitui`: duas entradas na fila; só a segunda é enviada; região viva anunciou "Ação na fila substituída."
   - `fila: tirar da fila devolve sem enviar`: clique em "Tirar da fila" (e, noutro caso, Tab até o botão + Enter); o texto está no campo com foco; `state` → `__sseReqs` continua 1.
   - `fila: Enter em waiting é ignorado como hoje`: Enter antes de qualquer chunk → nenhum chip e o texto continua no campo.
   - `fila desligada: Enter ignorado como hoje` (I6): `actionQueue = false`; Enter em `narrated` → nenhum chip, botão desabilitado "Aguardando o narrador", texto continua no campo, 1 stream depois do `state`.
   - Acessibilidade: axe com o chip visível; região viva = 1 (`turn-wait.spec.ts:80`); anúncio "Ação na fila: …" na região única; botão do chip ≥ 44×44 px.
2. **Implementação:** `turnWait.ts`, `App.tsx` (R9), `useQueuedAction.ts`, `ChatSurface.tsx`, `TurnStatus.tsx`, `Workspace.tsx`, CSS, `fixtures.ts`.
3. **Verificação:** `cd web && npm run typecheck && npm run lint && npm test`; e2e do escopo com `--workers=2`: `e2e/action-queue.spec.ts e2e/turn-wait.spec.ts e2e/turn-retry.spec.ts e2e/turn-preflight.spec.ts e2e/pending-discard.spec.ts e2e/latency.spec.ts e2e/touch-targets.spec.ts e2e/a11y-label-in-name.spec.ts e2e/mobile-single-pane.spec.ts e2e/voice-input.spec.ts`. `bash scripts/dev/py.sh scripts/dev/size_budget.py` verde.

### Etapa 3 — devolução ao rascunho (um e2e por caso)

1. **Testes** (`action-queue.spec.ts`). Em cada um: ação na fila em `narrated` → o evento do caso → asserções comuns: 0 envios a mais (contagem conferida depois do fechamento do turno 1 e de novo depois de um `expect` visível posterior); chip ausente; texto da fila no campo (`mergeDraft`); nota visível com o motivo; anúncio na região viva; 0 eco do texto.
   - a `state` com `combat.active` (usar `armCombat` no estado final, `fixtures.ts:136`).
   - b `state` com `combat_result.result_event_id` novo.
   - c `state` com `death_pending: true`; depois, `game_over: true`.
   - d `state` com `pending_choices` novo.
   - e `error` sem `narrative_shown` depois do `narrative done` (o stream fecha com erro; o fallback POST falha com `failNextTurn`).
   - f `error` com `narrative_shown: true` → "não salvo" → devolução; clicar "Tentar de novo" → `__sseReqs[1].action_id === __sseReqs[0].action_id`; depois do `state` do retry, `__sseReqs` = 2 (a fila não disparou).
   - g `narrative` com `replace: true` depois da fila; e um caso com `reset: true`.
   - h fechar o SSE sem `state` depois da narração (o cliente cai no fallback POST, que conclui): 1 `POST /game/action`, nenhum stream novo, devolução.
   - i gravar no `localStorage` um pending de outra operação para o mesmo dono/jogo antes de empurrar o `state`.
   - j turno 1 pendurado: com `page.clock`, avançar até "Tentar de novo" (`turn-wait.spec.ts:89-107`), com a fila criada depois da narração e antes do retry; consulta roteada `completed` → devolução e nenhum envio da fila.
   - k `context.setOffline(true)` antes de empurrar o `state`.
   - l trocar de partida pelo menu com a fila ativa (depois do `state` com falha, para liberar a troca) e voltar: o texto está no rascunho com a nota; 0 envios.
   - I7: disparar `rpg:auth-expired` com a fila → 0 envios; logar de novo como outro dono na mesma aba → campo vazio.
   - Reload com a fila → 0 envios depois do reload (a operação do turno 1 é restaurada pela retomada normal, sem eco duplicado: SPEC-420 I3).
2. **Implementação:** ajustes do hook até todos passarem; nenhum caso pode exigir mudança fora dos arquivos de §3.
3. **Verificação:** igual à Etapa 2.

### Etapa 4 — pouso

1. Coordenador: `npm run build`, `npm run test:e2e` completo 1× e suíte Python completa 1× (só a flag mudou no servidor).
2. Revisão `spec-reviewer` (risco `alto`), com foco em I1, I2, I5, R9 e na lista de R10.

## 5. Critérios de aceite

- [ ] Com o `state` segurado, Enter em `narrated` enfileira; 0 envios até o `state`; exatamente 1 envio depois, com o texto da fila e `action_id` novo (e2e, 2 viewports).
- [ ] Um e2e verde por caso a–l de R10, mais I7 e reload; em todos, 0 envios da fila e o texto volta ao campo.
- [ ] "Não salvo" + "Tentar de novo" com a fila ligada: mesmo `action_id`, e a fila não dispara depois.
- [ ] Flag desligada: e2e existentes (`turn-wait`, `turn-retry`, `turn-preflight`, `pending-discard`, `latency`) sem edição de asserção e verdes; `fila desligada` verde.
- [ ] `/auth/config`: chave ausente por padrão e com valores quase válidos; `true` com `on` (pytest).
- [ ] Região viva única; axe sem `serious`/`critical`; alvos ≥ 44 px; label-in-name.
- [ ] `npm run typecheck`, `npm run lint`, `npm test`, e2e do escopo, `size_budget.py` verdes; `App.tsx` ≤ 969 linhas.
- [ ] Suíte completa no pouso (coordenador).
- [ ] Guard de FallbackLLM: não se aplica (sem `with_structured_output` novo).
- [ ] Saves antigos continuam carregando: não há mudança de save nem de `localStorage`.
- [ ] Smoke §6 registrado no staging com a flag `on`.

## 6. Smoke test real

Staging depois do deploy, com `RPG_ACTION_QUEUE=on` (preset `staging_flags.json` + `vercel_env.py`), conta logada, DeepSeek, cerca de 8 turnos (centavos). Registrar o estado de `RPG_ARCHIVE_RECORD` (SPEC-422) no relato, porque ele muda o tamanho da janela. DevTools → Network, filtro `action`.

1. **Descanso** (janela longa: 8/8 turnos de descanso travavam, `latencia-turno-medicao-2026-11-13.md:53`): mandar "descanso até o amanhecer"; quando aparecer "registrando…", digitar "olho o céu" + Enter. Conferir: chip "Na fila"; nenhuma linha nova no Network até o 1º `POST /game/action/stream` terminar; depois, 1 `POST` novo cujo início vem **depois** do fim do 1º (cascata do Network), com `input_text` = "olho o céu".
2. **Fala com NPC já conhecido**: mesma coisa, mas usar "Tirar da fila" antes do fim; o texto volta ao campo e nada é enviado.
3. **Substituição**: enfileirar duas vezes; só a segunda vai.
4. **Devolução por combate**: uma ação que provoque luta ("ataco o guarda") + enfileirar "sigo pela rua" → o combate abre, o texto volta ao campo com a nota e nada é enviado.
5. **Celular real em 390 px**: tocar "Pôr na fila" e "Tirar da fila"; o teclado não fecha nem pula; o chip não cobre o botão.
6. **Flag desligada**: com `RPG_ACTION_QUEUE` removida e novo deploy (ou na produção, onde a variável não existe), o Enter em "registrando…" é ignorado como hoje.

**O que o dono experimenta para decidir se liga para todos** (§8 D6): jogar uns 15 minutos com a fila no staging e responder (1) se em algum momento algo foi enviado sem que ele esperasse; (2) se alguma devolução ao campo confundiu (e qual); (3) se a espera entre turnos pareceu menor nos descansos e nas falas; (4) se prefere com ou sem. Critério recomendado para promover: nenhum envio inesperado, nenhuma devolução incompreensível e preferência do dono pela fila.

Registrar o resultado (prints do Network dos itens 1 e 4 e as respostas do dono) no handoff da revisão ou em `docs/spec427/smoke.md`.

## Não rodou e por quê

- **Escrita da spec (22/11):** o autor não executou nada além de leitura (`git`, `wc`, `spec_index.py show`). O comportamento "antes" (Enter ignorado em `narrated`) vem do source: `ChatSurface.tsx:187`, `App.tsx:473,603-608`, e do e2e existente `turn-wait.spec.ts:163-193`, que afirma o botão desabilitado nesse estágio. O executor confirma na Etapa 0.
- **Smoke §6:** depende de deploy no staging. Em 22/11 as migrações 413/410 já estão aplicadas e os rate cards publicados (`88a5373f`); o deploy está com a sessão `rpg-ia-master-82`. Até lá a spec fica `in-progress` depois do pouso, como a SPEC-420.
- **Ganho de latência percebida:** não é medido por esta spec (a fila não muda nenhum tempo de servidor e não há telemetria de uso; ver Fora de escopo). A base é a medição de 13/11 (21 de 60 turnos com 4,4 s travados), não remedida.

## 7. Riscos & compatibilidade

- **Saves e pending antigos:** formatos inalterados. `queued` mora só no `chatSessionStore` (memória da página).
- **MockLLM / FallbackLLM:** não se aplica; o servidor só ganha a leitura da flag.
- **Custo para o jogador:** cada envio da fila é um turno cobrado, como um Enter manual. O risco é enviar algo que o jogador não queria mais. Mitigações: o envio exige sinal positivo (R9); devolução em toda mudança de cena relevante (R10); "Tirar da fila" sempre à vista; flag só no staging até o dono decidir.
- **Mudança visível com a flag ligada:** o botão em `narrated` fica habilitado com "Pôr na fila", o que contraria SPEC-320 R4 só nesse estágio e só com a flag. Com a flag desligada, R4 vale como está.
- **Interação com a SPEC-422:** se `RPG_ARCHIVE_RECORD=on` encolher a janela, a fila fica rara, mas continua correta: janela curta só quer dizer que o envio sai logo.
- **Interação com a L2/SPEC-213:** se um dia o cliente liberar no `state` antes de o stream fechar, `delivered` precisa continuar significando "save confirmado"; a spec da L2 revisa R9.
- **Tamanho:** `App.tsx` +≤ 8 linhas (961 → ≤ 969), abaixo do gate de 1.000.
- **Decisões fixas:** nenhuma linha de `docs/guias/DECISOES_FIXAS.md` (D-01 a D-38) trata da fila, do compositor ou de `/auth/config`. D-31 (contrato front↔back adiado) não é contrariada: a chave nova é opcional e lida com `=== true`. D-14 (`scripts/staging/*` mantidos) é respeitada; só se acrescenta uma flag ao preset.

## 8. Decisões

- **D1 — mudar a regra "input bloqueado até `state`" (SPEC-316 D2, SPEC-320 R13), atrás de flag.**
  - **Decidida em 22/11 pelo coordenador, por delegação do dono, com veto do dono possível.** Histórico: em 13/11 o dono ouviu a explicação ("você digita e dá Enter enquanto o jogo ainda fecha o turno, e a ação é enviada sozinha quando liberar; isso muda uma regra que você aprovou antes: campo travado até o fim") e a recomendação do coordenador de fazer, sem responder item a item. Em 22/11 disse "faz tudo ai… eu autorizo a fazer tudo que vc pode fazer, deixa de pendente só o q vc nao pode mesmo".
  - O coordenador decidiu executar pela recomendação, com a condição: **flag `RPG_ACTION_QUEUE` com default `off`; `on` só no staging**, para o dono experimentar antes de chegar ao jogador.
  - Fato novo em relação à fonte da regra (SPEC-316, 25/10): a medição de 13/11 (`docs/auditorias/latencia-turno-medicao-2026-11-13.md:53`) mostrou 4,4 s travados em 1 de cada 3 turnos, e a fila não é a alternativa rejeitada em 25/10 (nada vai ao servidor antes do save; I1, I2).
  - SPEC-316 D2 e SPEC-320 R13 continuam valendo com a flag desligada e na produção.
- **D2 — fila só no estágio `narrated`** (R4). Recomendado e adotado pelo coordenador. Alternativa: também em `waiting`. Rejeitada: o jogador ainda não leu o desfecho, a espera pode passar de 25 s com retry, e a medição é da janela depois do texto.
- **D3 — segundo Enter substitui** (R6). Recomendado e adotado. Alternativas: ignorar (o Enter volta a "não fazer nada", o mesmo problema que a spec resolve) ou concatenar (vira duas ações num turno, que o narrador interpretaria mal). Substituir é o "mudei de ideia" natural; o anúncio torna a troca explícita.
- **D4 — cartas, combate e voz fora** (R12, R13). Recomendado e adotado. Motivos em R12/R13: estado de mira velho, rodada sem IA e sem janela, e transcrição assíncrona.
- **D5 — devolução põe a fila antes do que o jogador digitou depois** (`mergeDraft`, R10.1). Recomendado e adotado. Alternativa: descartar o texto da fila em devolução. Rejeitada: perde o que o jogador escreveu.
- **D6 — ligar para todos (fica com o dono).** Depois do §6, o dono diz se a fila vai para a produção. Gatilho: as respostas do roteiro do §6. Promover é uma spec curta (flag `on` por padrão e, depois, aposentadoria da flag antes de `expires: 2027-02-28`). Até lá a produção fica como hoje.
- **D7 — risco `alto`** (cabeçalho). Proposto pelo autor; o coordenador pode baixar para `médio` (revisor Sonnet) se considerar a flag desligada contenção suficiente.

- **22/11, coordenador:** spec aprovada para execução. O dono ouviu a explicação e a recomendação em 13/11, não respondeu item a item e em 22/11 delegou ("deixa de pendente só o q vc nao pode mesmo"). D1–D5 e D7 ficam como recomendado pelo autor; risco `alto`, revisão `spec-reviewer`. D6 (ligar para todos) continua do dono, depois de ele experimentar no staging.
