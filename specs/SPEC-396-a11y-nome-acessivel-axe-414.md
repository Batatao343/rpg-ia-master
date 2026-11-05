# SPEC-396 — A11y: nome acessível contém o texto visível (destrava axe-core 4.14, PR #55)

> **Status:** `done` (05/11: estratégia E reprovou no axe → fallback D-396-1 (b), nome pelo conteúdo + `.sr-inline`; `Encerrar sessão` visível; bump do PR #55 aplicado à mão (branch do PR sumiu), pin `^4.14.0`; e2e completo verde em `--workers=2` para as falhas de carga; revisão [SPEC-396-review](../handoffs/SPEC-396-review.md) APPROVED_WITH_FOLLOWUPS: P2-1 smoke com leitor de tela real no iOS/VoiceOver (`font-size:0`), P2-2 `PlayQueue` perdeu o sufixo "Abrir/Fechar opções". Aprovada 05/11, dono "ok defaults": D-396-1 a→b, D-396-2 a, D-396-3 a, D-396-4 não acionada)
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Origem:** PR #55 do Dependabot (lote npm: `@axe-core/playwright` 4.10.2→4.14.0, `typescript-eslint` 8.72.1, `vite` 8.3.5). Com o 4.14, a regra `label-content-name-mismatch` (WCAG 2.5.3 *Label in Name*) passa a valer: 87 falhas no e2e completo (04/11), **todas** dessa regra; 354 passam. Exemplos: `effects.spec.ts` (ctrl.pending, mira, card.arm, tab.indicator, map.marker), `combat-gesture.spec.ts`, `critical-journeys.spec.ts` F06/F35.
> **Escopo:** corrigir os `aria-label` que não contêm o texto visível (ou trocar por `aria-labelledby`/texto visível) e pousar o bump do PR #55 junto, com o pin `tests/test_eval_frontend.py` (`^4.14.0`). Sem desligar a regra.
> **Depende de:** nada · **Desbloqueia:** PR #55
> **Risco:** `médio` (UI pública; sem mudança de comportamento de jogo) → revisor Sonnet
> **Evidência:** e2e novo `web/e2e/a11y-label-in-name.spec.ts` (só a regra `label-content-name-mismatch`) falha com axe 4.14 antes e passa depois; e2e completo com axe 4.14: 0 violação `label-content-name-mismatch`.

---

## 1. Contexto & Objetivo

O axe-core 4.14 passa a reprovar (impacto `serious`) todo controle cujo nome acessível
vem de `aria-label`/`aria-labelledby` e **não contém** o texto visível do próprio
controle. Os helpers `a11y()` dos e2e (ex.: `web/e2e/effects.spec.ts:32-36`,
`web/e2e/critical-journeys.spec.ts:7`, `web/e2e/combat-gesture.spec.ts:130`) rodam
`new AxeBuilder({ page }).analyze()` na **página inteira** e barram `serious`/`critical`.
Por isso o nome do teste que falha (ex.: `map.marker`) não aponta o componente culpado:
basta um controle errado na tela para todos os testes daquela tela caírem. As 87 falhas
são poucos componentes repetidos em muitas telas.

A regra (WCAG 2.5.3) existe para quem usa comando de voz ("clicar em Sair") e para quem
vê a tela e ouve o leitor ao mesmo tempo: o que está escrito precisa estar no nome. No
repo há dois padrões que a violam: (a) botões-carta e botões-alvo compostos (nome curto em
`aria-label`, mas o botão mostra custo, descrição, estado, condições); (b) botões cujo
texto visível é outra palavra (`Sair` × `Encerrar sessão`).

Objetivo: zerar a regra sem desligá-la, mudando o mínimo de nomes acessíveis, porque
~45 locators de e2e e 3 testes unitários dependem dos prefixos atuais (`Jogar Carta X`,
`Alvo: X`, `Encerrar sessão`, `Encerrar a rodada, 2 cartas`), e então pousar o bump do
PR #55.

### Como a regra compara (hipótese a confirmar na Etapa 0)

Pelo código do axe (`label-content-name-mismatch-evaluate`): nome acessível e texto
"visível" do conteúdo do controle passam por minúsculas, remoção de pontuação e de
símbolos Unicode (setas, geométricos como `●`, `‹ ›`), colapso de espaços; passa se o
texto visível inteiro for **substring** do nome. Texto visível vazio ou "não
interpretável" (um símbolo só, `x`, `i`, `?`) não reprova. Elemento sem papel de widget
que tira nome do conteúdo (section, group, nav, article, region, list, img, dialog,
tablist, radiogroup, separator) fica fora da regra. **Duas dúvidas** que a Etapa 0
resolve medindo: (1) filhos `aria-hidden` entram no "texto visível"? (2) texto `sr-only`
dentro do botão entra? A estratégia preferida (E, §3) depende de (1) = não.

## 2. Requisitos

- **R1** — Com `@axe-core/playwright` `^4.14.0`, nenhum e2e reporta violação
  `label-content-name-mismatch` (e2e completo, projetos `chromium` e `chromium-motion`).
- **R2** — A regra não é desligada nem filtrada: nenhum `disableRules`/`exclude`/filtro
  por id novo em `web/e2e/**`.
- **R3** — Nomes acessíveis preservados nos controles de combate: carta legada continua
  começando por `Jogar Carta <nome>` (`CardHand.tsx:51`); chip de alvo válido continua
  `Alvo: <nome>…` e inválido `<nome>: alvo inválido…` (`TargetChip.tsx:116-119`); carta do
  baralho continua `<nome>, N de Fôlego…` (`Hand.tsx:75`); carta do Acervo continua
  `<nome>, <tipo>, N de Entropia, <estado>…` (`DeckCard.tsx:65`); botão de fim de rodada
  continua `Encerrar a rodada, N cartas` (`PlayQueue.tsx:113`). Os asserts existentes
  `web/tests/spec345-components.test.mjs:33` e `web/tests/spec347-components.test.mjs:32`
  passam sem edição.
- **R4** — Nenhuma informação some para leitor de tela: todo texto visível retirado do
  cálculo do nome continua anunciado, via nome ou via `aria-describedby`
  (assert `toHaveAccessibleDescription` no e2e da Etapa 1).
- **R5** — O botão de sair da conta tem nome acessível `Encerrar sessão` **e** texto
  visível contido nele, nos dois lugares (`PlayScreen.tsx:117-118`, `PlayMenu.tsx:38-41`),
  sem editar os locators de `account.spec.ts:58,108`, `critical-journeys.spec.ts:37,279,281`,
  `turn-retry.spec.ts:54` e `tests/test_audit_browser_local.py:131,141` (salvo D-396-2 ≠ a).
- **R6** — `package.json`/`package-lock.json` com o lote do PR #55 e
  `tests/test_eval_frontend.py:143` exigindo `"^4.14.0"`.
- **R7** — Sem mudança visual: o leiaute das cartas, chips e fila não muda (e2e de efeitos
  e `visual-surfaces` verdes; nenhum snapshot novo).
- **R8** — Nada em `web/e2e/contracts/` (protegido em `evals/protected-paths.txt:14`; hoje
  o diretório **não existe**) nem em outro caminho protegido é tocado.

### Fora de escopo

- Outras regras do axe ou novas regras experimentais; auditoria manual completa de WCAG.
- Reescrever a copy dos controles além do botão de sair (R5) e do botão `×` (Etapa 3).
- Os ~70 `aria-label` de elementos não-widget (section/group/nav/region/list/img/dialog),
  que a regra não cobre.
- Alterar locators de e2e por gosto; só se uma decisão D-396-n escolher a opção que muda
  nome (e então na mesma etapa, listados no commit).
- PR #42 (TypeScript 7) e qualquer outro bump fora do lote do PR #55.
- i18n: o app não tem camada de tradução (strings pt-BR inline); nada a mudar.

## 3. Design técnico

### Estratégias de correção

- **E (preferida, preserva nomes)** — manter o `aria-label`; marcar `aria-hidden="true"`
  nos trechos visíveis secundários do controle (custo, descrição, estado, condições) e
  ligá-los por `aria-describedby` (ids estáveis por `useId`/id do item). Referência
  direta por `aria-describedby` inclui conteúdo `aria-hidden` na descrição, então o leitor
  continua ouvindo tudo (R4). O texto visível que sobra para a regra é o nome da carta/
  alvo, que já está dentro do `aria-label`. Precedente no repo: `Hand.tsx:79-85` já
  esconde custo/descrição/estado e descreve por `aria-describedby`.
- **A (fallback)** — remover o `aria-label`; nome vem do conteúdo; prefixos/sufixos que
  não estão na tela entram como `<span className="sr-only">`. Muda nomes → exige
  atualizar locators (lista em §7).
- **T (copy)** — trocar o texto visível para conter o nome (botão de sair).
- **S (espaço)** — só inserir `{" "}` entre spans inline para o texto visível casar.

### Inventário (grep `aria-label=` em `web/src`: 104 ocorrências em 47 arquivos)

**Grupo 1 — prováveis violações (11 ocorrências, 9 componentes):**

| # | Arquivo:linha | Controle | Texto visível × nome | Correção proposta |
|---|---|---|---|---|
| 1 | `web/src/components/CardHand.tsx:51` | carta legada (`card.arm`) | visível: `2E`, frequência, nome, descrição, estado (`:57-66`); nome `Jogar Carta X, 2 de Entropia, um clique` | **E**: `aria-hidden` em `__top`, `__desc`, `__state`; `aria-describedby` = `detailId` + id da descrição/estado |
| 2 | `web/src/components/combat/Hand.tsx:75` | carta do baralho | visível: nome (`:82`); `sr-only` `:85` **dentro** do botão | se Etapa 0 mostrar que `sr-only` conta: mover o `<span id={descId} className="sr-only">` para irmão do botão (fora dele); `aria-describedby` igual |
| 3 | `web/src/components/combat/Hand.tsx:95` | Descartar | visível `Descartar (2 Fôlego)` (`:97`); nome `Descartar X por 2 de Fôlego` | reescrever nome: `Descartar (2 Fôlego): X` + `. Indisponível: …`; nenhum e2e usa esse nome |
| 4 | `web/src/combat/TargetChip.tsx:121` | chip de alvo (`mira`/`target.valid`) | visível: nome, `5/10`, Esquiva/Proteção, Engajado, condições, Revelado, presságio (`:78-103`); nome `Alvo: X, Vitalidade 5 de 10. Presságio: …` | **E**: `aria-hidden` em `tchip__top` (exceto `<strong>` do nome), `__meta`, `__tags`, `__omen`, prenúncio/saber; `aria-describedby` com ids por `p.id`; `aria-label` inalterado (R3) |
| 5 | `web/src/components/combat/PlayQueue.tsx:71` | item da fila | visível `1 Golpe → Orc` (`:73-74`); nome `1º: Golpe em Orc. Abrir opções` (`º` e `em` quebram) | **A** local: remover `aria-label`; conteúdo `1<sr-only>º:</sr-only> Golpe <span aria-hidden>→</span><sr-only> em</sr-only> Orc`; "abrir/fechar" já vem de `aria-expanded`. Nenhum e2e/unit usa esse nome (grep `º:`/`Abrir opções` vazio) |
| 6 | `web/src/components/combat/PlayQueue.tsx:113` | Encerrar a rodada | visível `<span>Encerrar a rodada</span><small>2 cartas</small>` sem espaço entre spans (`:115-118`); nome `Encerrar a rodada, 2 cartas` | **S**: `{" "}` entre o `<span>` e o `<small>`; nome intacto (`spec347-mobile.spec.ts:60`, `spec347-components.test.mjs:32`) |
| 7 | `web/src/components/tabs/DeckCard.tsx:65` | carta do Acervo (preparável) | visível: tipo, `2E (base 3)`, nome, descrição, chips, estado (`:31-51`); nome `X, Ataque, 2 de Entropia, No Acervo, Enter para preparar` | **E**: `aria-hidden` em `__top`, `__desc`, `__meta`, `__state`; `aria-describedby` para desc+chips |
| 8 | `web/src/components/PlayScreen.tsx:118` | sair (topbar) | visível `Sair`; nome `Encerrar sessão` | **T** (D-396-2): texto visível `Encerrar sessão` e remover `aria-label` (já é a copy de `App.tsx:813`) |
| 9 | `web/src/components/PlayMenu.tsx:39` | sair (menu) | idem `:40` | idem #8 |
| 10 | `web/src/workspace/ContextSurface.tsx:95` | fechar ficha | visível `×` (U+00D7, talvez "interpretável" para o axe); nome `Fechar ficha` | a confirmar na Etapa 0; se reprovar: `<Icon name="close" />` como `Banner.tsx:34` |
| 11 | `web/src/components/SupportCode.tsx:19` | copiar código | visível `Copiado` após clicar (`:20`); nome fixo `Copiar código de suporte` | nome condicional `Código de suporte copiado` quando `copied`; estado inicial intacto (`support-code.spec.ts:25`) |

**Grupo 2 — widgets que devem passar (confirmar na Etapa 0, sem mudança prevista):**
`MapTab.tsx:140` e `WorldMap.tsx:141` (visível = ícone `aria-hidden` + nome, que abre o
nome; `?` do nó inexplorado é não-interpretável; `effects.spec.ts:413` e
`copy.test.mjs:39` dependem desses nomes — não mexer), `ChatSurface.tsx:240` (`Voz`/`Parar`
⊂ nome), `SceneArtwork.tsx:37` e `VisualArtwork.tsx:37` (`Ampliar` ⊂ nome),
`SceneArtwork.tsx:40`, `StoryLog.tsx:196`, `SaveScreen.tsx:96,107`,
`OnboardingHint.tsx:28`, `Banner.tsx:34`, `PlayQueue.tsx:78-80`,
`GeneratedArtCard.tsx:54`, `GeneratedPortrait.tsx:49` (só ícone/imagem, sem texto),
`Workspace.tsx:321,323` (`‹`/`›` são pontuação removida), `PlayMenu.tsx:21` (`⋯` em
`aria-hidden`), `Workspace.tsx:348` (separator), `DeckCard.tsx:72` (`div` sem papel de
widget). Abas (`RovingTablist.tsx:49-64`, `MobileTabBar.tsx:16-23`) e `Pressable`
(`primitives.tsx:11-19`, `ctrl.pending`) **não têm** `aria-label`: nome = conteúdo, fora
da regra.

**Grupo 3 — fora da regra (não-widget):** as demais ~70 ocorrências (section, group,
nav, region, article, list, img, dialog, tablist, radiogroup).

Se a Etapa 0 achar alvo fora desta tabela, ele entra no grupo 1 com a mesma regra de
decisão (E se o nome é usado por teste; A se não; T se o texto visível é outra palavra) e
a spec é atualizada no mesmo commit.

### Dependências de nomes em testes (nenhuma em caminho protegido)

- `Jogar Carta …`: `combat-gesture.spec.ts:44`, `effects.spec.ts:262,279,331,593,656`,
  `critical-journeys.spec.ts:154,596,616`, `mobile-single-pane.spec.ts:74,303`,
  `vertical-journey.spec.ts:327,338`, `workspace-shell.spec.ts:291,296`.
- `Alvo: …`/`alvo inválido`: `combat-gesture.spec.ts:57,79,113,115,126`,
  `effects.spec.ts:316-317` (`toHaveAttribute("aria-label")`), `deck-combat-342.spec.ts:21,41,48,58,230,358-360`,
  `critical-journeys.spec.ts:157,597,625,705,790`, `mobile-single-pane.spec.ts:279,304,330`,
  `spec364-409.spec.ts:19,22,25`, `spec363-board.spec.ts:71,74`, `web/tests/spec345-components.test.mjs:33`.
- `Encerrar sessão`: ver R5. `Encerrar a rodada, 2 cartas`: ver #6. `Cancelar Golpe`
  (`deck-components.test.mjs:66`) e `Exportar sessão de …` (`vertical-journey.spec.ts:510`):
  inalterados. `Custo deste turno…` (`account.spec.ts:43,54,118`): inalterado.
- `web/e2e/contracts/` não existe; nada exige `/eval-publish`.

### Arquivos

- **Novo** `web/e2e/a11y-label-in-name.spec.ts` — percorre as telas que hoje reprovam
  (lista de jornadas, jogo logado com topbar e menu aberto, combate legado com carta
  armada e alvos, combate do baralho com descarte e fila com 2 itens, Acervo, aba Mapa,
  ficha de contexto aberta, código de suporte antes/depois de copiar) e roda
  `new AxeBuilder({ page }).withRules(["label-content-name-mismatch"]).analyze()`,
  esperando `violations` = `[]` com o `target` de cada nó na mensagem. Mais asserts de
  R3/R4: `toHaveAccessibleName` dos prefixos e `toHaveAccessibleDescription` não vazio
  em carta/alvo/carta do Acervo. Reusa fixtures de `web/e2e/fixtures.ts` e helpers
  `deck-342-helpers.ts`.
- **Alterados** — os 9 componentes do grupo 1; `web/package.json` e
  `web/package-lock.json` (lote do PR #55); `tests/test_eval_frontend.py:143`;
  unit `web/tests/deck-components.test.mjs`/`spec345-components.test.mjs` só com asserts
  **novos** (não editar os existentes).
- Sem schema, sem API, sem estado de jogo.

## 4. Plano passo a passo

### Etapa 0 — bump e medição (oráculo)

1. No worktree: aplicar o lote do PR #55 (`web/package.json` + `web/package-lock.json`
   do branch do Dependabot), `npm ci` em `web/`, e `tests/test_eval_frontend.py:143` →
   `"^4.14.0"`.
2. Escrever `web/e2e/a11y-label-in-name.spec.ts` (§3). Rodar **só ele**: deve falhar,
   listando os `target` dos nós. Registrar no §8 desta spec a lista real
   (componente → seletor) e as respostas às duas dúvidas (aria-hidden; sr-only), com um
   spike mínimo em `CardHand` (um `aria-hidden` no `__desc`) para provar a estratégia E.
3. Se E não satisfaz o axe: anotar no §8 e cair para A nos itens 1/4/7 (ver D-396-1).
4. **Verificação:** `bash scripts/dev/pt.sh tests/test_eval_frontend.py` verde; o e2e novo
   vermelho com alvos que batem com o grupo 1.

### Etapa 1 — cartas e alvos (itens 1, 2, 4, 7)

1. **Testes primeiro:** no e2e novo, `toHaveAccessibleName(/^Jogar Carta Golpe do Véu/)`,
   `/^Alvo: Saqueador/`, `/^Ayla: alvo inválido/`, nome da carta do Acervo, e
   `toHaveAccessibleDescription` não vazio contendo a descrição da carta e uma condição
   do alvo; unit novo em `web/tests/deck-components.test.mjs` asserta que o markup de
   `TargetChip`/`DeckCard` tem `aria-describedby` cujos ids existem no mesmo markup.
2. **Implementação:** estratégia E (ou A, conforme Etapa 0) nos itens 1, 2, 4, 7.
3. **Verificação:** e2e novo verde nessas telas; `npx playwright test effects combat-gesture
   deck-combat-342 critical-journeys --workers=2` verde; `npm test` (unit) verde.

### Etapa 2 — fila e descarte (itens 3, 5, 6)

1. **Testes primeiro:** e2e novo com fila de 2 itens e descarte disponível;
   `toHaveAccessibleName("Encerrar a rodada, 2 cartas")` continua; nome do item da fila
   contém `Golpe` e o alvo.
2. **Implementação:** #3 nome reescrito, #5 estratégia A local, #6 `{" "}`.
3. **Verificação:** `spec347-mobile`, `deck-combat-342`, `spec363-board`, `spec364-409` verdes.

### Etapa 3 — sair, fechar, copiar (itens 8–11)

1. **Testes primeiro:** e2e novo com usuário logado (topbar e menu aberto) e
   `support-code` depois do clique; `getByRole("button", { name: "Encerrar sessão" })`
   visível nos dois lugares.
2. **Implementação:** #8/#9 conforme D-396-2; #10 só se a Etapa 0 reprovou; #11 nome
   condicional.
3. **Verificação:** `account`, `critical-journeys`, `turn-retry`, `support-code`,
   `touch-targets` (largura do topbar em 320 px) verdes;
   `bash scripts/dev/pt.sh tests/test_audit_browser_local.py tests/test_frontend_visual_contracts.py`.

### Etapa 4 — fechamento

1. `npm run lint`, `npm run typecheck`, `npm run build`, `npm test`.
2. e2e completo **1×** pelo coordenador no pouso (não pelo subagente): 0
   `label-content-name-mismatch`, contagem total ≥ 354 + novos.
3. `uv run pytest` completo pelo coordenador no `/spec-land`.
4. Após pouso na `main`, fechar o PR #55 como incorporado (ou deixar o Dependabot
   fechar ao detectar a versão), conforme D-396-3.

## 5. Critérios de aceite

- [ ] R1: e2e completo com axe 4.14 → 0 violação `label-content-name-mismatch` (saída anexada no §8)
- [ ] R2: `git diff main -- web/e2e` sem `disableRules`/`exclude` novos
- [ ] R3: asserts existentes de nome (`spec345-components.test.mjs:33`, `spec347-components.test.mjs:32`, locators `Jogar Carta`/`Alvo:`) passam sem edição
- [ ] R4: `toHaveAccessibleDescription` verde em carta legada, carta do baralho, carta do Acervo e chip de alvo
- [ ] R5: `Encerrar sessão` visível e nome igual nos 2 botões; locators intactos
- [ ] R6: `package.json` `^4.14.0` + lock; `tests/test_eval_frontend.py` verde
- [ ] R7: e2e de efeitos e visuais verdes, sem snapshot novo
- [ ] R8: `git diff --name-only main` sem caminho de `evals/protected-paths.txt`
- [ ] `npm run lint` + `typecheck` + `build` + `npm test` verdes
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Revisão independente Sonnet (risco médio)

## 6. Smoke test real

Sem LLM nem infra nova: o smoke é de navegador/AT.

1. CI do PR da branch: job e2e verde com axe 4.14 (o `ci-watcher` vigia).
2. Manual, `npm run build` + `uvicorn` local: com NVDA (ou o leitor do Windows/Narrador),
   focar uma carta, um alvo e a carta do Acervo e confirmar que nome **e** descrição são
   lidos (custo, efeito, condições). Registrar no §8 em 3 linhas.
3. Comando de voz (opcional): Acesso por Voz do Windows, "clicar em Encerrar sessão" e
   "clicar em Saqueador" acionam o controle.

## 7. Riscos & compatibilidade

- **Leitor de tela:** E troca leitura de conteúdo por descrição; alguns leitores leem a
  descrição com atraso ou só sob comando. Mitigação: `aria-label` já carrega o essencial
  (nome, custo, estado/indisponibilidade); descrição leva o detalhe. A ordem de leitura
  em modo de navegação (fora do foco) perde o texto `aria-hidden` do botão; como fica
  dentro de um botão, o leitor já o anunciaria só como nome. Aceitável; smoke §6.2 confere.
- **Fallback A muda nomes:** se cair para A nos itens 1/4/7, os ~45 locators de §3
  quebram (ex.: `^Jogar Carta Golpe do Véu` passa a vir depois do custo no DOM). Por isso
  E é preferida e a Etapa 0 decide antes de qualquer rollout.
- **Testes que usam nome:** listados em §3; nenhum em caminho protegido;
  `web/e2e/contracts/` não existe → sem `/eval-publish`.
- **Visual:** `aria-hidden`/`aria-describedby` e `{" "}` não mudam leiaute, salvo o espaço
  de #6 (1 caractere entre spans; `touch-targets`/`visual-surfaces` conferem); a copy
  `Encerrar sessão` alarga o botão do topbar (conferir 320 px).
- **i18n:** não há camada de tradução; strings pt-BR inline.
- **Lote do PR #55:** traz também `typescript-eslint` 8.72.1 e `vite` 8.3.5; lint/build
  verdes na Etapa 4 cobrem o risco.
- **Saves, MockLLM/FallbackLLM, quota:** não se aplicam (só frontend).

### Decisões do dono

- **D-396-1 — Estratégia para cartas e alvos (itens 1, 4, 7).** (a) E: manter `aria-label`,
  esconder secundários com `aria-hidden` e descrever por `aria-describedby` (preserva os
  ~45 locators e os nomes que o leitor já usa); (b) A: tirar `aria-label`, nome = conteúdo
  (nome longo; reescrever locators); (c) botão "esticado" só com o nome e o resto como
  irmão (mexe em CSS dos efeitos). **Recomendação: (a)**, com (b) como fallback automático
  se a Etapa 0 provar que o axe conta `aria-hidden`.
- **D-396-2 — Botão de sair (itens 8, 9).** (a) texto visível `Encerrar sessão` e sem
  `aria-label` (mesma copy de `App.tsx:813`; zero locator alterado); (b) manter `Sair`
  visível e nome `Sair` (atualizar 6 locators e-2e + 2 em `tests/test_audit_browser_local.py`);
  (c) visível `Sair`, nome `Sair (encerrar sessão)` (locators viram regex). **Recomendação: (a)**;
  se não couber no topbar em 320 px, (c).
- **D-396-3 — Onde pousa o bump.** (a) o lote do PR #55 entra no branch desta spec e o
  PR é fechado como incorporado; (b) pousar só as correções e depois mergear o PR #55
  (com o pin `tests/test_eval_frontend.py` corrigido à parte). **Recomendação: (a)** — o e2e
  só prova R1 com o 4.14 instalado.
- **D-396-4 — Botão `×` da ficha (item 10).** Se a Etapa 0 reprovar: trocar por ícone
  `close` (padrão de `Banner.tsx:34`) — **recomendação** — ou manter `×` em `aria-hidden`.

## 8. Medições (preencher na execução)

- Etapa 0: alvos reais reprovados pelo axe 4.14 (componente → seletor), respostas às
  dúvidas `aria-hidden`/`sr-only`.
- Etapa 4: contagem do e2e completo (passou/falhou) e 0 violação da regra.
- §6.2: nota do smoke com leitor de tela.

### Registro da execução (05/11)

- **Etapa 0.** Vermelho confirmado em `button[aria-label="Encerrar sessão"]` (#8/#9) e `button[data-card=…]` (#1). Dúvida 1: filhos `aria-hidden` **entram** no "texto visível" do axe (usa `isVisibleOnScreen`) -> a estratégia E **reprovou**; D-396-1 caiu para o fallback (b).
- **Fallback aplicado (A).** Itens 1, 2, 3, 4, 5, 6, 7: sem `aria-label`; o nome vem do conteúdo (regra N/A), decoração em `aria-hidden` e o texto falado em `<span class="sr-inline">` dentro do elemento do nome. Nova classe `.sr-inline` (`font-size:0`): o `.sr-only` (absolute) bloca o nome e o Playwright injeta espaço (`Golpe do Véu , 1 …`), quebrando regex `^Golpe do Véu,` de ~45 locators. Nomes preservados byte a byte, exceto `Descartar (1 Fôlego) : X` (botão flex, aceita `\s*`). `aria-describedby` do Acervo (`useId`) e das cartas do baralho mantido.
- **Dúvida 2** (`sr-only` no botão): não medida; o `descId` das cartas do baralho foi movido para irmão do botão por segurança.
- #6: o selo `.play-queue__count` virou `aria-hidden` e o texto "`, N cartas`" vai em `sr-inline` (a 390 px o count está `display:none` e o nome perderia "2 cartas"); nome acessível exato `Encerrar a rodada, 2 cartas` mantido.
- #8/#9: texto visível `Encerrar sessão` (D-396-2 a). #10 (`×`) passou no axe: sem mudança. #11: `aria-label` condicional `Código de suporte copiado`.
- **Desvio:** asserts existentes editados porque dependiam do markup antigo: `effects.spec.ts` (`toHaveAttribute("aria-label")` -> `toHaveAccessibleName`), `spec345-components`/`spec347-components` (aria-label -> sr-inline), `deck-components` (2 regex). Bump: o branch do PR #55 foi apagado e estava defasado (removia `overrides`); aplicados à mão os 3 pins em `web/package.json` + `npm install` local.
- **Evidência:** e2e novo (5 testes) + 15 specs tocadas: 202 passed / 16 skipped / 0 failed (`--project=chromium`); `npm test` 315/315; lint 0 erro; typecheck e build ok; `pytest tests/test_eval_frontend.py tests/test_audit_browser_local.py` 9 passed.
