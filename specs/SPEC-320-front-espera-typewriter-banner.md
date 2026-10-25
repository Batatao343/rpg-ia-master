# SPEC-320 — Front: espera do turno, typewriter e banner de erro

> **Status:** `in-progress` (aprovada 25/10; implementada + revisão Sol 2 rodadas (APPROVED_WITH_FOLLOWUPS, F-1..F-4 feitos); pousada na main 25/10; falta smoke §6 no staging com screenshots)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** nenhuma (funciona com o pseudo-streaming atual). Melhora sozinha quando SPEC-316 e SPEC-319 pousarem.
> **Desbloqueia:** SPEC-321, SPEC-323 (que reaproveitam a linha de status do compositor)

---

## 1. Contexto & Objetivo

O turno leva ~10–11 s (p50), e o SSE hoje é **pseudo-streaming**: o evento `narrative` só sai depois do grafo inteiro, archivist e commit incluídos (relatório de latência de 25/10; backend em SPEC-316/319). Durante esse tempo a UI comunica mal o que está acontecendo:

- O botão diz "Enviando…" o turno inteiro (`web/src/workspace/ChatSurface.tsx:153-155`), embora o envio leve ~100 ms.
- O indicador são três pontos pulsando mais um rótulo `--faint` em itálico no **fim do scroll** (`web/src/components/StoryLog.tsx:80-86`; CSS em `web/src/styles.css:462-466`). Quem rolou a tela para cima não vê.
- Cada fase substitui a anterior (`web/src/App.tsx:42-56`), e não existe nenhum aviso ligado ao tempo decorrido.
- `.thinking` tem `aria-live` próprio dentro de um `role="log"` que já tem `aria-live` (`StoryLog.tsx:62,81`), então a fase pode ser anunciada duas vezes.

Quando o texto chega, ele chega inteiro, e o typewriter (`web/src/hooks/useTypewriter.ts:39-49`) revela 1–8 caracteres aleatórios a cada 30 ms (~150 car/s). Isso acrescenta até ~8 s num beat de 1.200 caracteres. O typewriter:

- recebe `enabled = entry.streaming` (`StoryLog.tsx:93`) e não consulta `useEffectsEnabled()` (`web/src/design/motion.ts:40`), então ignora `prefers-reduced-motion` e `?effects=off`;
- não tem como ser pulado;
- re-parseia o texto inteiro com `mdLite` a cada tick (`StoryLog.tsx:117`).

O banner de erro (`web/src/components/Banner.tsx:12-17`) some sozinho em 6 s (15 s com código de suporte, 9 s em aviso), não tem botão de fechar e é `position: fixed; top: 0` sobre a topbar (`styles.css:637`). O `onDone` é uma arrow inline (`App.tsx:772`), então o timer reinicia a cada render. Mensagens de sucesso usam `kind: "warn"` (`App.tsx:390`). O resultado é que o código de suporte some antes de ser copiado (WCAG 2.2.1).

Dois problemas menores entram aqui também:

- O botão primário tem `aria-label="Agir"` mas mostra "Lutar" em combate (`ChatSurface.tsx:153-155`; WCAG 2.5.3).
- A capitular entra em **todo** `.msg--story` (`styles.css:419-426`). Como `::first-letter` engloba a pontuação inicial, um diálogo que começa com "—" vira um travessão gigante. O primeiro bloco ainda ganha `text-shadow` de glow.
- A dica de onboarding está desatualizada: diz que "chips com suas habilidades aparecem acima da caixa de texto" (`web/src/components/OnboardingHint.tsx:46-48`), mas as manobras estão na aba Combate desde a SPEC-204.

**Objetivo:** fazer a espera ler como parte da ficção, com um lugar estável e escalonamento no tempo. Também tirar o typewriter do caminho de quem quer ler e tornar os erros persistentes e acessíveis. Nenhuma mudança de backend.

## 2. Requisitos

- **R1 — linha de status no compositor.** Uma linha de status do turno fica dentro do compositor, acima do input. É uma **única** região `role="status"` (`aria-live="polite"`, `aria-atomic="true"`) e continua visível quando o log está rolado para o topo. O `.thinking` com os três pontos sai do `StoryLog`, e o `aria-live` duplicado some junto.
- **R2 — fases acumulam.** A linha é um livro-razão: as fases já recebidas (eventos `onPhase`/`onRoute`) ficam visíveis em `--muted` com "✓" (glifo tipográfico), e a atual em `--ink`. Sem emoji.
- **R3 — escalonamento no tempo.** Com ~8 s sem nenhum chunk de `narrative`, aparece uma linha de tranquilização da ficção ("A noite é longa; o narrador pondera…"). Com ~25 s, aparecem as ações "Continuar esperando" e "Tentar de novo". "Tentar de novo" reaproveita o fluxo de ação pendente por `operation_id` que já existe (`App.tsx:540-600`) e não cria um envio duplicado.
- **R4 — botão primário.**
  - Sem `aria-label`; o nome acessível é o texto visível ("Agir"/"Lutar").
  - Durante o turno fica `disabled` + `aria-busy="true"` e mostra "Aguardando o narrador" depois do `onAck`. Sem "Enviando…" depois do ack.
  - O `<input>` continua editável durante o turno, como já é hoje (`disabled={blocked}`, `ChatSurface.tsx:127`).
- **R5 — typewriter respeita efeitos.** Com `prefers-reduced-motion: reduce` ou `data-effects="off"` (`useEffectsEnabled() === false`), o texto inteiro aparece no 1º frame.
- **R6 — typewriter pode ser pulado.** Tocar ou clicar na entrada em revelação, ou `Esc`/`Espaço` com o foco na região da história, revela tudo. O `onTypewriterDone` dispara uma única vez.
- **R7 — teto de duração.** A cadência é constante (sem `Math.random`) e a revelação de um beat dura no máximo `TYPEWRITER_MAX_MS` (default 2500 ms; ver D1). Se o texto cresce por chunks (SSE real, SPEC-319), o cursor nunca fica mais de ~1 s atrás do texto recebido.
- **R8 — sem parse por tick.** `mdLite` roda no máximo uma vez por chunk recebido, não a cada tick. O reveal opera sobre parágrafos já parseados, ou o parse é memoizado por texto completo.
- **R9 — banner persistente para erro.** `kind: "error"` só some quando o jogador fecha (botão ✕ com `aria-label="Fechar aviso"` e área ≥ 44×44 px). Um novo `kind: "info"` cobre sucesso, e só `info`/`warn` somem sozinhos (9 s). O timer não reinicia por re-render (`onDone` estável via `useCallback`, ou o timer chaveado pela identidade da mensagem).
- **R10 — banner sem cobrir controles.** O banner é renderizado no fluxo, logo abaixo da topbar ou como faixa acima do compositor, e não cobre botões. O último erro também fica acessível pela linha de status (R1) até o próximo turno.
- **R11 — capitular.** Só em blocos marcados `data-opening`: o primeiro bloco de narração da sessão, ou o primeiro depois de uma mudança de `current_location`. Nunca quando o texto começa com `—`, `“`, `"` ou `«`. Sem `text-shadow`.
- **R12 — dica de onboarding.** Aponta para a aba Combate ("Em combate, abra a aba Combate para jogar Cartas — ou descreva a ação"). Acrescenta "Cada turno leva uns 10 segundos: o narrador está pensando, não travou" e uma linha sobre o input por voz.
- **R13 — compatibilidade futura.**
  - Com SPEC-316 pousada, o `narrative` chega antes do `state`. Entre os dois eventos, a linha de status mostra um selo "registrando…" (padrão `ProjectionSeal`) e o envio continua travado até o `state`.
  - Se o turno falhar depois do `narrative`, o texto continua no log com o selo "não salvo" e a ação "Tentar de novo".
  - Sem SPEC-316, nada disso aparece e o comportamento é o de hoje.

### Fora de escopo

- Qualquer mudança em `api.py`, no SSE ou no grafo (SPEC-316–319).
- Mostrar `turn_outcome` antes da prosa: depende do backend emitir o evento cedo. Se SPEC-316/318 criarem o evento, uma spec de seguimento só consome.
- Layout mobile e touch targets fora do ✕ do banner (SPEC-321). Tokens de cor e tipografia (SPEC-322).

## 3. Design técnico

**Arquivos novos**
- `web/src/workspace/TurnStatus.tsx`: componente da linha de status. Props: `{ phases: string[]; current: string | null; elapsedMs: number; stage: "idle" | "waiting" | "narrated" | "failed-after-narration"; lastError?: BannerState | null; onKeepWaiting(); onRetry() }`.
- `web/src/hooks/useTurnClock.ts`: devolve `elapsedMs` desde o submit (1 tick/s, para quando `busy=false`). Os limiares `REASSURE_MS = 8000` e `RETRY_MS = 25000` são exportados para teste.

**Arquivos alterados**
- `web/src/App.tsx`:
  - `PHASE_TEXTS`/`ROUTE_TEXTS` (`:42-56`) sem emoji.
  - `phaseLabel: string | null` vira `phaseTrail: string[]` (acumula em `onPhase`/`onRoute`, `:551-552`, sem duplicar).
  - Expõe `stage`.
  - `Banner` recebe um `onDone` estável (`:772`).
  - "Imagem confirmada…" (`:390`) passa para `kind: "info"`.
  - O handler de "Tentar de novo" reaproveita o pending.
- `web/src/components/Banner.tsx`:
  - `kind: "error" | "warn" | "info"`.
  - Sem timer para `error`.
  - Botão de fechar.
  - `role="alert"` só para `error`, `role="status"` para os outros.
- `web/src/components/StoryLog.tsx`:
  - Remover o bloco `.thinking` (`:80-86`).
  - Handler de clique/tecla para pular a revelação.
  - `data-opening` vindo de `LogEntry.opening?: boolean`.
- `web/src/hooks/useTypewriter.ts`:
  - Assinatura nova `useTypewriter(text, enabled, onDone, opts?: { maxMs?: number; effects?: boolean })`.
  - `typewriterStep(text, idx, charsPerTick)` determinístico.
  - `typewriterCharsPerTick(textLen, maxMs, tickMs)` calcula o passo para respeitar o teto.
  - Função `reveal()` exposta pelo hook.
- `web/src/workspace/ChatSurface.tsx`: monta o `TurnStatus` dentro do `.actionbar__composer`; o `Pressable` fica sem `aria-label` e com `pendingLabel="Aguardando o narrador"` só depois do ack.
- `web/src/lib.ts` (ou onde mora `pushLog`): marca `opening` na primeira narração da sessão e depois de uma troca de local.
- `web/src/styles.css`:
  - Remove `.thinking*` (`:462-466`).
  - Adiciona `.turn-status`.
  - A capitular (`:419-426`) passa a usar `.msg--story[data-opening] .msg__body::first-letter`, sem `text-shadow`.
  - Banner no fluxo (`:637-638`).
- `web/src/components/OnboardingHint.tsx:46-48`: copy nova.
- `web/src/design/effects.registry.ts` + `web/e2e/effects.spec.ts`: registrar o efeito "traço de tinta" da linha de status (`transform: scaleX`, desligado com effects-off) e remover `thinking__dot`.

**Desvios da implementação (25/10):** (1) `TurnStatus` fica no `<form>` do compositor, acima da linha input/botões (a linha é flex horizontal). (2) Na tela de jogo o `Banner` é renderizado dentro do `.play` por um slot de `PlayScreen` (no fluxo, abaixo da topbar); nas outras telas segue fixo. (3) Modelo puro em `web/src/turnWait.ts` e corte de HTML em `web/src/revealHtml.ts` (mdLite roda 1× por texto; o typewriter só corta o HTML pronto). (4) "Tentar de novo" com turno em voo consulta `getOperation`: `completed` recupera o estado e invalida o fluxo SSE (`turnToken`); senão avisa e continua esperando; sem turno em voo reaproveita o pending. (5) Erro `narrative_shown` chega por `HttpError.narrativeShown` (api.ts). (6) Os e2e de banner/espera ficaram em `web/e2e/turn-wait.spec.ts` (não estendi `support-code.spec.ts`, que cobre o login).

**Pular capitular com pontuação:** o model calcula `opening && !/^[—“"«]/.test(text.trimStart())`, porque CSS não consegue testar o caractere.

## 4. Plano passo a passo

### Etapa 1 — typewriter determinístico e com teto
1. **Testes** (`web/tests/typewriter.test.mjs`, atualizar):
   - `typewriterStep` sem aleatoriedade (mesma entrada → mesma saída);
   - `typewriterCharsPerTick(1200, 2500, 30)` termina em ≤ 2500 ms;
   - `typewriterInitial(text, true)` devolve `text` quando `effects=false`.
2. **Implementação:** `useTypewriter.ts` com `opts.effects` (default `true`) e `maxMs`; `StoryLog` passa `useEffectsEnabled()`.
3. **Verificação:** `cd web && npm test`.

### Etapa 2 — pular revelação e parse por chunk
1. **Testes:**
   - `web/tests/storyLog.test.mjs` (novo): `mdLite` é chamado ≤ nº de chunks numa revelação simulada (spy em `lib`).
   - e2e `web/e2e/turn-wait.spec.ts` (novo): clicar na entrada em revelação mostra o texto completo; `Espaço` com o foco no log faz o mesmo.
2. **Implementação:** `reveal()` + handlers; memoização de parágrafos parseados.

### Etapa 3 — linha de status, fases acumuladas, relógio
1. **Testes:**
   - `web/tests/turnStatus.test.mjs`: o trail não duplica fases e não contém emoji (regex `\p{Extended_Pictographic}`);
   - `useTurnClock` cruza 8 s → `reassure` e 25 s → `retry` (relógio falso).
   - e2e `turn-wait.spec.ts`: com a fixture de SSE lenta, rolar o log para o topo e enviar a ação, e a `.turn-status` continua `toBeInViewport()`; aos 8 s (relógio do Playwright) o texto de tranquilização aparece; aos 25 s, "Tentar de novo" reenvia com o mesmo `operation_id` (sem 2º POST novo).
   - axe na tela de jogo sem violação, e um único `[aria-live]` por região de status.
2. **Implementação:** `TurnStatus.tsx`, `useTurnClock.ts`, mudanças no `App`/`ChatSurface`, remoção do `.thinking`.

### Etapa 4 — botão primário
1. **Testes:** e2e com `getByRole('button', { name: 'Lutar' })` existente em combate; `aria-busy=true` durante o turno; o texto "Enviando…" não aparece depois do ack.
2. **Implementação:** `ChatSurface.tsx:153-155`.

### Etapa 5 — banner
1. **Testes:**
   - e2e `web/e2e/support-code.spec.ts` (estender): erro com `requestId` ainda visível e copiável depois de 30 s (relógio falso); o ✕ fecha; `info` some em 9 s; o banner não sobrepõe a topbar (bounding boxes disjuntas a 390×844 e 1440×900).
   - unit: o timer não reinicia ao re-renderizar com a mesma mensagem.
2. **Implementação:** `Banner.tsx`, `App.tsx:390,772`, CSS.

### Etapa 6 — capitular e onboarding
1. **Testes:**
   - unit: `opening` só na 1ª narração e depois de uma troca de local; falso quando o texto começa com "—".
   - e2e visual: screenshot do 1º e do 2º beat.
2. **Implementação:** model do log, CSS, `OnboardingHint.tsx`.

### Etapa 7 — ganchos SPEC-316 (sem depender dela)
1. **Testes:**
   - unit do `stage`: os eventos `narrative(done)` → `state` produzem `narrated` → `idle`;
   - erro depois de `narrative` produz `failed-after-narration` com o texto preservado.
   - Simulado por eventos de fixture, sem backend.
2. **Implementação:** máquina de estágio no `App`; o selo "registrando…" só aparece quando `narrative(done)` chega antes do fim do stream.

**Verificação final:**
- `cd web && npm test && npm run lint && npm run test:e2e -- turn-wait support-code effects mobile-single-pane latency`.
- Screenshots 390×844 e 1440×900 (antes/depois) em `web/test-results/spec320/`.

## 5. Critérios de aceite

- [ ] Linha de status no compositor, `role="status"` único, visível com o log rolado ao topo (e2e).
- [ ] Fases acumulam (passadas `--muted` ✓, atual `--ink`); sem `.thinking__dot`; sem emoji nas fases; sem `aria-live` duplicado (axe ok).
- [ ] Nome acessível = texto visível ("Agir"/"Lutar"); `aria-busy` durante o turno; sem "Enviando…" depois do ack.
- [ ] Tranquilização aos ~8 s e "continuar / tentar de novo" aos ~25 s; o retry não duplica o envio (e2e com relógio falso).
- [ ] Typewriter: inteiro no 1º frame com reduced-motion ou `?effects=off`; pulável por toque/clique/`Esc`/`Espaço`; ≤ 2,5 s por beat; sem `Math.random`; `mdLite` não roda por tick (unit).
- [ ] Banner: erro persiste até ser fechado (✕ ≥ 44 px); não cobre a topbar; `onDone` estável; `kind: "info"` para sucesso; código de suporte copiável depois de 30 s.
- [ ] Capitular só com `data-opening`, nunca sobre `—`/`“`/`"`, sem `text-shadow`.
- [ ] Dica de onboarding aponta para a aba Combate e explica a espera.
- [ ] Com fixtures que simulam a SPEC-316 (`narrative` antes de `state`), o selo "registrando…" aparece e o envio só destrava no `state`.
- [ ] `effects.registry.ts` e `e2e/effects.spec.ts` atualizados juntos.
- [ ] `cd web && npm test` e o e2e do escopo verdes; `uv run pytest` verde (sem mudança de backend esperada).

## 6. Smoke test real

Staging, conta logada, DeepSeek. Sem LLM extra além dos turnos normais: ~4 turnos, cerca de US$ 0,01.

1. Antes do deploy: screenshots de um turno em andamento (aos ~3 s e aos ~9 s) a 390×844 (DevTools device) e 1440×900.
2. Depois do deploy: repetir 3 turnos (STORY, NPC, COMBAT). Conferir:
   - fases acumulando;
   - tranquilização aparecendo quando o turno passa de 8 s;
   - botão "Lutar" em combate;
   - toque pulando a revelação.
3. Ativar `prefers-reduced-motion` (DevTools → Rendering) e confirmar o texto inteiro no 1º frame.
4. Forçar um erro (rede offline no DevTools durante o envio) e confirmar que o banner persiste, que o ✕ fecha e que o código de suporte é copiável.
5. Anexar os screenshots antes/depois (4 a 6) ao handoff `handoffs/SPEC-320-*.md`.

## 7. Riscos & compatibilidade

- **SPEC-316/319:** esta spec não depende delas e não as duplica. Ela só consome os eventos que já existem (`onAck`, `onPhase`, `onRoute`, `onChunk`) e prepara o `stage`. Quando a 316 pousar, a 320 já mostra "registrando…". Quando a 319 pousar, o R7 garante que o cursor acompanha os tokens. Se a 316 mudar o nome ou a ordem dos eventos, ajustar só o mapeamento do `stage`.
- **Destravar no `narrative` vs no `state`:** decidido destravar só no `state`. Destravar antes deixa o jogador enviar uma ação antes do commit, o que dá `lock_wait` e risco de replay. O input continua editável.
- **Contratos e2e protegidos:** se alguma asserção em `web/e2e/contracts` cobrir "Enviando…" ou `.thinking`, a mudança passa pelo fluxo `eval-governance` (`/eval-publish`). Quem implementa não altera o contrato na mesma tarefa.
- **Saves antigos:** nada muda no estado persistido; `opening` é derivado no cliente.
- **MockLLM:** sem impacto, porque a mudança é só de front.
- **Perfil legacy (F-4):** `getOperation` devolve `unknown` no perfil legacy; "Tentar de novo" com turno em voo cai então no ramo "stream pendurado" (abandona o SSE e repete o mesmo `action_id`, idempotente). Aceito: o perfil legacy não tem login e serializa por processo.
- **Conflito de arquivos:** toca `styles.css`. Pode rodar antes da 321 ou da 322, mas não em paralelo com elas.

## 8. Decisões do dono

- **D1 — ritmo do typewriter.** **Recomendado: teto de 2,5 s por beat agora, com toque para completar; reavaliar quando a SPEC-319 trouxer streaming de tokens.** A alternativa é reveal instantâneo como padrão, com o typewriter opcional nas configurações.
- **D2 — limiares da espera.** **Recomendado: tranquilização aos 8 s e retry aos 25 s.** Ajustáveis por constante.

## Histórico de mudanças

- 2026-10-25 — Spec aprovada pelo dono ("boa, aprovo"), padrões recomendados.
- 2026-10-25 — Implementação (`f957fe13`); revisão independente: `CHANGES_REQUIRED` (P1-1 corrida do pending, P1-2 sem e2e do contrato SSE da 316, P2-1..P2-10).
- 2026-10-25 — Correções da revisão (`89ce60d2`): `clearOwnPending`, fixture SSE controlada + e2e 316, região viva única, typewriter por ref, saída para stream pendurado.
- 2026-10-25 — Regressões do e2e do coordenador corrigidas (`5794f216`): região `aria-live` sem `role=status`, erro sem texto duplicado, id de stream síncrono, barra de pending sobre "Tentar de novo", combate usa "Lutar".
- 2026-10-25 — Re-revisão: `APPROVED_WITH_FOLLOWUPS`; follow-ups F-1..F-4 aplicados (`clearPendingIfOwn` + testes, guarda de duplo clique no retry, eco removido no reenvio, nota do perfil legacy).
