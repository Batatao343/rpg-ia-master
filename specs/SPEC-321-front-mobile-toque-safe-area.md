# SPEC-321 — Front: casca mobile, alvos de toque e safe-area

> **Status:** `in-progress` (aprovada 25/10; implementada + revisão Sol (P1 de 1 linha + 7 P2 corrigidos em `af5579c6`, e2e verdes); pousada na main 25/10; falta smoke §6 no staging + Enter com IME em Android real)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** SPEC-320 (a linha de status do compositor já existe; o banner já sai do topo)
> **Desbloqueia:** SPEC-198 (wrapper Android: o app precisa caber e ser tocável no celular), SPEC-322

---

## 1. Contexto & Objetivo

No celular a narração, que é o produto, fica com a menor fatia da tela. A 360–390 px de largura, empilham-se:

- `.image-offers` ("Cotar retrato" / "Cotar cena épica"), renderizada **antes e fora** do `.play-shell` (`web/src/App.tsx:776-785`; CSS em `web/src/workspace.css:155-156` e `web/src/styles.css:1138-1139`);
- a topbar, forçada a duas linhas em ≤ 480 px por `.topbar__right { flex: 1 1 100% }` (`styles.css:1020`);
- `.ws-mhead` (`workspace.css:108`);
- `.placesbar` (`web/src/workspace/ChatSurface.tsx:38-52`);
- `.scene-art` com 132 px (`styles.css:1025`);
- o compositor com `.voice-status`;
- a `.mtabbar` de 48 px + safe-area (`workspace.css:120-131`).

O nome do local aparece em três lugares.

Os alvos de toque ficam abaixo de 44 px:
- `.iconbtn` ~30 px (`styles.css:353-357`, fonte 0,66rem no celular em `:1018`); só `.ws-bar .iconbtn` tem `min-height: 32px` (`workspace.css:25`);
- `.placechip` ~30 px (`styles.css:907`), e cada toque nele gasta um turno;
- `.inv__equip` ~20 px (`:889`);
- `.codex-cat` (`:750`);
- `.lvlup__evolve button` (`:869`);
- `.combat-card__rupture/__play` (`:953`);
- `.art-expand` (`:366`);
- os nós do `WorldMap` de fallback (`styles.css:589-591`).

A topbar põe "☰ Ficha", "Nova" e "Sair" no mesmo estilo (`web/src/components/PlayScreen.tsx:91-97`), e "Nova" sai da partida com um toque (`App.tsx:677-684`).

`web/index.html:5` não tem `viewport-fit=cover`, então `env(safe-area-inset-bottom)` (`styles.css:1029`, `workspace.css:122`) vale 0 no iOS e no WebView edge-to-edge. Também não há `theme-color`.

Outros problemas da casca:
- `.pending-operation` (`styles.css:372`, fixed `bottom: 5rem`, z 100) e `.outcome-toast` (`:1167`, fixed `bottom: 5.5rem`) podem cair sobre o compositor.
- `.account-shell-link` usa `right: 15rem` mágico (`:1057`).
- O compositor é um `<input>` de uma linha (`ChatSurface.tsx:123`), e o placeholder longo trunca.
- O vocabulário da casca diz "Chat" (`web/src/workspace/mobileSurface.ts:12`), "Dividido" (`web/src/workspace/Workspace.tsx:296`) e "Chat da aventura" (`ChatSurface.tsx:37`).

**Objetivo:** história com ≥ 55 % da altura no celular, todo controle tocável com ≥ 44 px, safe-area funcionando e ações perigosas protegidas. Pré-requisito do wrapper Android (SPEC-198).

## 2. Requisitos

- **R1 — cabeça única no celular.** Em `< 900px`, a topbar e o `ws-mhead` viram uma cabeça só, com ≤ 52 px: nome do local (truncado), Vitalidade/Entropia e um botão "⋯ Menu". O local aparece uma vez.
- **R2 — menu.** O menu (sheet ou popover com foco preso, reaproveitando `useModalFocus`) contém Conta (com saldo), "Nova jornada", Sair e Laboratório quando existir. No desktop, "Nova" vira "Nova jornada" e fica no mesmo menu ou separado de "Ficha".
- **R3 — confirmação de saída.** "Nova jornada" pede confirmação quando há turno em andamento (`busy`) ou ação pendente; sem isso, vai direto (o save já existe).
- **R4 — arte de cena recolhível.** `.scene-art` recolhe para ≤ 72 px quando o jogador rola a história para baixo, ou depois do 1º beat num mesmo local; um toque expande de novo. Respeita reduced-motion (sem animação de altura; usar `transform`/troca de classe).
- **R5 — locais atrás de um chip.** Os `.placechip` ficam atrás de um único chip "Locais daqui ▾", que abre a lista. No desktop a barra pode continuar aberta.
- **R6 — ofertas de imagem fora do topo.**
  - "Cotar retrato" vai para o painel Personagem.
  - Ofertas de cena e de NPC (`data.art_offers`) viram um chip discreto na entrada de narração correspondente (ou na mais recente), e não ficam acima do jogo.
  - `.image-generations` vai para o painel Personagem/Codex.
  - A 1440×900 não pode haver scroll de documento.
- **R7 — piso de toque.** Em `@media (pointer: coarse)`, todo controle interativo da tela de jogo tem área ≥ 44×44 px. A área cresce por padding ou `::before`; o visual pode continuar menor.
- **R8 — viewport.**
  - `index.html`: `viewport-fit=cover` e `<meta name="theme-color">` com o valor sRGB do `--bg`.
  - `capacitor.config.ts`: status bar escura.
  - Cabeça e `.mtabbar` usam `env(safe-area-inset-*)`.
- **R9 — toasts sem sobreposição.**
  - `.outcome-toast` e `.pending-operation` ficam ancorados acima do compositor por `--composer-h` (medido com `ResizeObserver`) e não sobrepõem o input a 360 px.
  - Sem `right: 15rem`; o link de conta vai para uma linha flex.
  - Z-index pela escala `--z-*` (`styles.css:58`).
- **R10 — compositor multilinha.**
  - `<textarea rows=1>` que cresce até 4 linhas; Enter envia e Shift+Enter quebra linha (em IME/composição, Enter não envia).
  - Placeholder curto: "O que você faz?". Os exemplos ficam na dica de onboarding.
  - O placeholder de simulação ("Texto livre executa um ataque básico…", `ChatSurface.tsx:138`) vira a dica abaixo do input.
- **R11 — rótulos da casca.** "Chat" → "Crônica", "Dividido" → "Lado a lado", "Chat da aventura" → "Crônica da aventura". Os ids de surface, os `data-testid` e as rotas não mudam.
- **R12 — orçamento vertical.** Na tela de jogo, a 360×740 e a 390×844, a área visível da `.story` é ≥ 55 % da altura do viewport no 2º turno num local (fora de combate e sem onboarding).

### Fora de escopo

- Tokens de cor, raio, ícones e tipografia (SPEC-322). Aqui o "⋯" e o "▾" são glifos provisórios, trocados pela família de ícones na 322.
- Marginália do jogador e listas do HUD (SPEC-323).
- O wrapper Android em si (SPEC-198).

## 3. Design técnico

**Arquivos novos**
- `web/src/components/PlayMenu.tsx`: o menu ⋯, com Conta, Nova jornada, Sair e Laboratório; tem foco preso e fecha com `Esc`.
- `web/src/hooks/useComposerHeight.ts`: `ResizeObserver` no `.ws-composer` que publica `--composer-h` em `:root`.

**Arquivos alterados**
- `web/src/components/PlayScreen.tsx:71-99`: a topbar deixa a linha de ações para o `PlayMenu`; no celular só o local e o menu.
- `web/src/workspace/Workspace.tsx`: a `ws-mhead` absorve local, stats e o botão de menu; os rótulos em `:282-298` mudam.
- `web/src/workspace/mobileSurface.ts:12`: `chat: "Crônica"`.
- `web/src/workspace/ChatSurface.tsx`: `textarea`; o chip "Locais daqui"; `aria-label` da section.
- `web/src/App.tsx:776-791`: remove `.image-offers` e `.image-generations` do topo; passa `openImageQuote` e `art_offers` para `PlayScreen` → painel Personagem e `StoryLog`; confirmação de "Nova jornada" (`:677-684`).
- `web/src/components/StoryLog.tsx`: chip de oferta inline (`entry.visual` / `art_offers`).
- `web/src/components/SceneArtwork.tsx` (ou onde mora `.scene-art`): estado `collapsed`.
- `web/src/styles.css` e `web/src/workspace.css`:
  - bloco `@media (pointer: coarse)` com o piso de 44 px;
  - remove `flex: 1 1 100%` (`styles.css:1020`);
  - `.outcome-toast`/`.pending-operation` com `bottom: calc(var(--composer-h) + …)`;
  - remove `right: 15rem` (`:1057`).
- `web/index.html:5`: viewport e theme-color. `web/capacitor.config.ts`: status bar.

## 4. Plano passo a passo

### Etapa 1 — viewport e safe-area
1. **Testes:** `web/tests/build.test.mjs` (estender): `index.html` contém `viewport-fit=cover` e `name="theme-color"`.
2. **Implementação:** `index.html`, `capacitor.config.ts`, `env()` na cabeça.

### Etapa 2 — piso de toque
1. **Testes:** e2e `web/e2e/touch-targets.spec.ts` (novo), em projeto mobile (`hasTouch`, 390×844): na tela de jogo, aba Personagem, Codex, Combate e mapa, todo `button, [role=button], select, a` visível tem bounding box ≥ 44×44 px (somando o `::before` pela checagem de `elementFromPoint` nas bordas, ou pelo `min-height` computado).
2. **Implementação:** bloco `pointer: coarse`.

### Etapa 3 — cabeça única e menu
1. **Testes:**
   - e2e `web/e2e/workspace-shell.spec.ts` e `mobile-single-pane.spec.ts` (adaptar): no celular existe uma cabeça com altura ≤ 52 px; o menu abre e fecha com `Esc`; "Nova jornada" pede confirmação com turno em andamento.
   - unit `web/tests/mobileSurface.test.mjs`: o rótulo `chat` é "Crônica".
2. **Implementação:** `PlayMenu`, `PlayScreen`, `Workspace`, rótulos.

### Etapa 4 — arte recolhível e locais
1. **Testes:** e2e: depois de rolar a `.story` 200 px, a `.scene-art` fica com altura ≤ 72 px; o chip "Locais daqui" abre a lista e um toque num local envia `Entro em …`.
2. **Implementação:** `SceneArtwork`, `ChatSurface`.

### Etapa 5 — ofertas de imagem
1. **Testes:** e2e `web/e2e/image-quote.spec.ts` (adaptar): "Cotar retrato" está no painel Personagem; a oferta de cena aparece como chip na narração; a 1440×900, `document.scrollingElement.scrollHeight <= innerHeight`.
2. **Implementação:** `App`, `PlayScreen`/`CharacterTab`, `StoryLog`.

### Etapa 6 — toasts e compositor
1. **Testes:**
   - e2e `outcome-toast.spec.ts` / `pending-discard.spec.ts` (estender): a bounding box do toast não intersecta a do compositor a 360×740.
   - unit: Enter envia, Shift+Enter não envia, `isComposing` não envia.
2. **Implementação:** `useComposerHeight`, CSS, `textarea`.

### Etapa 7 — orçamento vertical
1. **Testes:** e2e `web/e2e/mobile-budget.spec.ts` (novo): a 360×740 e a 390×844, no 2º turno a altura visível da `.story` / `innerHeight` ≥ 0,55.
2. **Verificação:**
   - `cd web && npm test && npm run lint && npm run test:e2e -- touch-targets mobile-budget workspace-shell mobile-single-pane image-quote outcome-toast pending-discard visual-surfaces`.
   - Screenshots 390×844 e 1440×900, antes e depois.

## 5. Critérios de aceite

- [x] História ≥ 55 % da altura a 360×740 e a 390×844 (e2e mede).
- [x] Cabeça única ≤ 52 px no celular; Conta, "Nova jornada" e Sair no menu ⋯; "Nova jornada" confirma com turno em andamento.
- [x] `.scene-art` recolhe para ≤ 72 px; um toque expande.
- [x] `pointer: coarse`: todo controle da tela de jogo com ≥ 44×44 px (e2e).
- [x] Ofertas de imagem fora do topo; a 1440×900 sem scroll de documento e com o compositor visível.
- [x] `viewport-fit=cover` + `theme-color`; status bar escura no Capacitor.
- [x] Toast e barra pendente sem sobrepor o compositor; sem `right: 15rem`; z-index pela escala.
- [x] Compositor em `textarea` (1–4 linhas, Enter/Shift+Enter, IME seguro), placeholder curto.
- [x] "Crônica"/"Lado a lado" na UI; ids e test-ids inalterados.
- [ ] `npm test` e o e2e do escopo verdes; `uv run pytest` verde.

## 6. Smoke test real

Staging, conta logada, ~3 turnos.

1. **Antes:** screenshots da tela de jogo a 390×844 (DevTools e, se possível, um Android real pelo Chrome) e a 1440×900, no 2º turno de um local.
2. **Depois do deploy:** os mesmos screenshots, para medir visualmente a fatia da história.
3. Tocar no menu ⋯, abrir "Nova jornada" com um turno em andamento e confirmar o pedido de confirmação.
4. Cotar retrato pelo painel Personagem, até a cotação e sem confirmar a compra.
5. No iPhone/Android real, se houver: conferir que a `mtabbar` não fica sob a barra de gestos.
6. Anexar os screenshots antes/depois ao handoff.
7. Android real: digitar uma palavra com autocorreção (Gboard) e tocar Enter/Enviar uma só vez; deve enviar sem inserir quebra de linha (IME, R10).

## 7. Riscos & compatibilidade

- **Não rodar em paralelo com a SPEC-322:** as duas mexem pesado em `styles.css` e `workspace.css`. Ordem: 320 → 321 → 322.
- **SPEC-198 (Android):** esta spec é pré-requisito. Se a 198 começar antes, combinar o `capacitor.config.ts` (status bar) para não haver conflito.
- **Receita das imagens:** tirar a oferta do topo pode reduzir cliques (D1). Medir pelos eventos de cotação existentes antes e depois.
- **Testes e2e existentes:** `workspace-shell`, `mobile-single-pane`, `image-quote` e `visual-surfaces` vão precisar de ajuste de seletor. Seletores em `web/e2e/contracts` são caminho protegido (`/eval-publish`).
- **IME no textarea:** checar `isComposing` para não enviar no meio da composição (teclados Android).
- **Saves e backend:** sem impacto; mudança só de front.

## 8. Decisões do dono

- **D1 — ofertas de imagem paga fora do topo.** **Recomendado: sim. Retrato no painel Personagem e cena/NPC como chip inline na narração que a originou.** Alternativa: manter uma barra, mas dentro da coluna de jogo e recolhida.
- **D2 — rótulos da casca.** **Recomendado: "Crônica" no lugar de "Chat" e "Lado a lado" no lugar de "Dividido"; manter "Ficha" e "Painel".**

---

## 9. Histórico de mudanças

- **2026-10-26 · correções do smoke visual de staging (`e9b5f00`; toca 320/323/324 só em UI).**
  - **R9/SPEC-320:** `.pending-operation` não renderiza com o turno em voo (`stage` waiting/narrated); só aparece para ação pendente real (falha pós-narração, recarga com pendência), ancorada em `--composer-h` e compacta. e2e novo em `turn-wait.spec.ts` (sem `.pending-operation` em voo).
  - **Compositor ocupado:** textarea com `min-width: 7rem`; botão "Aguardando o narrador" com elipse (`max-width`), sem vazar em 360/390 (e2e: largura do textarea e sem overflow horizontal).
  - **Tela "Continuar jornada" (celular):** Conta/Encerrar entram no fluxo (`position: static`) em vez de flutuar sobre o título. O skip link NÃO vira 1º Tab ali: a SPEC-324 R5 o restringe à tela de jogo.
  - **Ficha (celular):** retrato com altura máx. `min(46dvh, 360px)` e sem a legenda sobreposta (nome/classe já estão no cabeçalho).
  - **SPEC-323 (mapa):** `placeLabels` (abaixo/direita/esquerda/acima; esconde o rótulo de menor prioridade que não cabe, nome fica em `aria-label`/`title`); e2e verifica rótulos visíveis sem interseção.
  - **Desktop:** a borda superior da história esmaece sob a faixa da cena (sem cortar linha); ofertas "Cotar retrato" deduplicadas por NPC e com o nome (`/game/state` `art_offers` ganha `subject_id`/`label` só para NPC, já saneados).
- **2026-10-25 · implementação (branch `spec-321`).** Desvios em relação ao texto acima, todos decididos na implementação:
  - **R2/desktop:** em ≥ 900 px a topbar mantém Conta, Ficha, Sair inline (os e2e de conta/checkout dependem deles); só "Nova" virou "Nova jornada" (com confirmação). O menu ⋯ (`PlayMenu`) existe só no celular (< 900 px), onde substitui a topbar.
  - **R1:** a cabeça única mora no `Workspace` (`.ws-mhead`: local + rótulo da superfície + Vitalidade/Entropia + ações); no celular o `header.topbar` não é renderizado. O banner (SPEC-320) entra logo abaixo dela.
  - **R3:** o botão "Nova jornada" continua desabilitado durante `busy` (o `handleNew` tem guarda de sessão e destravar no meio do turno deixaria `busy` preso). A confirmação cobre os estados reais de risco: ação pendente não resolvida e turno `narrated`/`failed-after-narration`.
  - **R4:** "rolar" conta só gesto do jogador (roda/toque/teclado), nunca o auto-scroll para o fim; o toque na faixa alterna e vale até mudar de local.
  - **R9 + SPEC-320:** a barra `.pending-operation` deixou de duplicar "Tentar de novo": com `failed-after-narration` ela só oferece "Descartar ação pendente" (o `is-raised` saiu); em todos os casos fica ancorada por `--composer-h` + `--tabbar-h`. `Conta`/`Sair` das telas sem partida ficam numa linha flex (`.shell-actions`).
  - **R7:** o e2e novo mede a caixa real dos controles (≥ 43,5 px) nas superfícies Crônica, Personagem, Codex, Combate e Mapa a 390×844 com `isMobile`/`hasTouch`.
  - **R8:** além do `capacitor.config.ts` (`StatusBar` DARK), `AppTheme.NoActionBar` do Android ganhou `statusBarColor`/`windowLightStatusBar`, porque o plugin `@capacitor/status-bar` não está instalado (SPEC-198).
  - Testes e2e antigos adaptados aos novos nomes (`Crônica`, `Lado a lado`, `Crônica da aventura`), ao `textarea` do compositor e ao novo lugar de "Cotar retrato" (painel Personagem).
- **2026-10-25 · correções da revisão (sol).** `voice-input`/`image-quote` usam "Nova jornada"; chips de oferta só fora de laboratório/memorial e com `aria-live="off"`; texto da confirmação diz que a ação pendente fica guardada; `scrolled` reinicia ao mudar de local; Enter com `keyCode 229` sem composição ativa envia (Android); cabeça mobile mostra "⚔ Combate · rodada N"; e2e de Conta/Sair no menu ⋯ (`account.spec`).
- **2026-10-26 · regressão do orçamento vertical (R4).** O e2e `mobile-budget` falhava (360×740: história 46,8 %; 390×844: 53,4 %): o aviso warn/info (ex.: "Modo simulado…", ~97 px) estava no fluxo da `.ws-root` e roubava altura da história; o follow-up de staging (`c8e61257`) não era a causa (mesma medição antes dele). Correção: no celular (≤ 600 px) o aviso transitório `is-warn`/`is-info` (some em 9 s) flutua sobre o topo da história, logo abaixo da cabeça; erro persistente continua no fluxo (`workspace.css`). Flake `workspace-shell` (divisor por ponteiro): o teste agora espera o divisor assentar antes de medir/arrastar.
