# SPEC-322 — Front: tokens de cor, contraste, raio, ícones e tipografia

> **Status:** `in-progress` (aprovada 25/10; implementada + revisão Sol (2 P1 + 6 P2 corrigidos em `150cc87e`, e2e verdes); pousada na main 26/10; falta axe nas abas, botões 3×3, tokens dos 57 oklch literais e conferência visual no staging)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** SPEC-321 (não rodar em paralelo: mesmos arquivos CSS)
> **Desbloqueia:** SPEC-323 (que usa os ícones e tokens novos)

---

## 1. Contexto & Objetivo

O sistema de tokens OKLCH existe (`web/src/styles.css:11-59`, `web/src/design/tokens.css`), mas vaza. Contrastes medidos (OKLCH → sRGB, WCAG):

| Texto | Fundo | Razão | |
|---|---|---|---|
| `--faint` `oklch(0.58 0.026 78)` (`styles.css:26`) | `--surface` (fundo do `.tabpanel`, `:495`) | 4,09 | falha 4,5 |
| `--faint` | `--surface-2` | 3,68 | falha |
| `--danger` `oklch(0.54 0.20 25)` (`:35`) | `--surface` | 3,13 | falha |
| `--danger` | `--bg-deep` | 3,64 | falha |
| `--danger-bright` (`:36`) | `--surface` | 4,35 | falha |
| `--line-soft` (borda de campo, `:21`) | `--surface` / `--bg-deep` | 1,33 / 1,55 | falha 3:1 (1.4.11) |

`--faint` é usado como texto em metadados de painel: status e prazo de missão, fação, pessoa, codex, `.worldmap__label` (`:591`), `.thinking` (`:462`) e outros. `--danger` como texto aparece justamente nos avisos (prazo urgente, missão falha, fação hostil). Há remendos pontuais (`workspace.css:100-102`, `tabs.css:264-271`), o que mostra que a causa é o token.

Outros vazamentos:
- **Cores:** 30 literais hex em `styles.css`. A família Entropia/Abismo está em hex (`:522, 526-533, 883, 947-962, 1207, 1220`; `workspace.css:208`), e há outro roxo em `workspace.css:18`.
- **Tokens indefinidos:** `var(--gold)` (`styles.css:674`; a borda do `.chron-digest` nunca aparece), `var(--text, #eadcc4)` (`:1133`), `var(--ink-faint, #8a7a6c)` (`:853`) e `var(--ink-soft, #cbc6ba)` (`:907`).
- **Tokens não usados:** `--mana`/`--stamina` (`:40-41`) e `--sans` (`:52`).
- **Raio:** os tokens são `--r-sm` 4 e `--r-md` 8, mas há literais de 2, 3, 6, 10 e 12 px, e 25 usos de pílula, inclusive em ações (`.placechip` `:907`, `.actionchip` `:994`, `.codex-cat` `:750`).
- **Tipografia:** Cinzel caixa-alta e espaçada em 0,58–0,74rem em `.hud__label` (`:504-507`, 0,66rem), `.tab` (`:790`, 0,62rem), `.iconbtn` (`:353-357`), `.msg__role` (`:406`), `.worldmap__label` (0,6rem), `.mtabbar__btn` e `.laboratory-flag` (0,58rem).
- **Ícones:**
  - emoji em strings: `web/src/App.tsx:46-54` (⚔️ 🗣️ 💰) e `web/src/components/PlayScreen.tsx:39-41` (🌑 🔦);
  - glifos Unicode soltos: ☰ ⌂ ↩ ◉ ☗ ◆ ⚠ em `PlayScreen.tsx`, `workspace/ChatSurface.tsx`, `components/MapTab.tsx`, `components/DeckCard.tsx` e `components/WorldMap.tsx`.
  - No Android, ⚔ e ⚠ podem virar emoji colorido.
- **Duplicatas:** `.combat-card` definido duas vezes com `grid-template-rows`/`min-height` conflitantes (`styles.css:945` e `:1209`); `.tab` em `:478` e `:790`; dois keyframes de pulso (`prologue-pulse` `:330`, `pulse` `:645`); ~15 famílias de botão e chip.
- **Movimento:**
  - `transition: width` em `:518, 555, 718, 732, 900`; `.tchip__bar` já usa `scaleX`;
  - `--ease-spring-soft` com overshoot (`tokens.css:14`, usado em `styles.css:1289`);
  - durações fixas nas transições de tela do `App.tsx`.
- **Z-index:** a escala `--z-*` (`styles.css:58`) é ignorada, por exemplo em `.pending-operation` z 100 (`:372`).
- **Decoração:** 19 faixas laterais (`border-left` 2–3 px) e glow em quase todo estado selecionado.

**Objetivo:**
- contraste AA em todo texto;
- zero hex fora dos tokens;
- uma regra de forma;
- Cinzel só em títulos;
- uma família de ícones;
- um sistema de botões;
- o lint impede a regressão.

## 2. Requisitos

- **R1 — `--faint`.** `oklch(0.64 0.026 78)` ou mais claro, com ≥ 4,5:1 sobre `--surface`, `--surface-2` e `--bg-deep` (`L 0,64` medido = 4,69 sobre `--surface-2`).
- **R2 — `--danger-text`.** Novo token, `oklch(0.70 0.17 27)` (medido 5,50 sobre `--surface-2`), para todo texto vermelho. `--danger`/`--danger-bright` ficam só para preenchimento e borda.
- **R3 — `--field-border`.** Novo token com ≥ 3:1 sobre o fundo do compositor e dos painéis (em torno de L 0,50). É aplicado a `input`, `textarea` e `select`.
- **R4 — família `--abyss`.**
  - `--abyss` (preenchimento, em torno de `oklch(0.55 0.09 300)`), `--abyss-dim` (fundo), `--abyss-line` (borda) e `--abyss-text` (texto, ≥ 4,5:1, em torno de `oklch(0.74 0.09 300)`).
  - Substituem todos os roxos hex e o `oklch(0.78 0.11 305)` de `workspace.css:18`.
  - Sem glow roxo (borda interna de 1 px no lugar).
- **R5 — sem tokens órfãos.** Zero tokens indefinidos (`--gold`, `--text`, `--ink-faint`, `--ink-soft`) e zero literais hex/rgb fora de `design/tokens.css` e `styles.css :root`. `--mana`/`--stamina` são usados ou removidos.
- **R6 — stylelint.** Configurado com `color-no-hex` (exceto nos arquivos de token) e `declaration-property-value-disallowed-list` para `border-radius` literal, rodando em `npm run lint`.
- **R7 — regra de forma (D2).** Tokens `--r-sharp` (2 px: controles, painéis, inputs), `--r-sm` (4 px: cards), `--r-md` (modais) e `--r-pill` (**só** tags de status). Sem literais de raio.
- **R8 — tipografia.**
  - Cinzel só em títulos ≥ 1rem: local, títulos de painel, títulos de modal, telas de morte e level-up.
  - Controles, abas, rótulos e stats em EB Garamond small caps (`font-variant-caps: all-small-caps`; conferir que o subset tem `smcp`/`c2sc` e, se não tiver, usar `--sans`), com piso de 0,8rem.
  - Metadados não interativos podem ter 0,75rem.
  - Cinzel Decorative só na capitular de abertura (SPEC-320 R11) e na tela de morte.
  - Preload dos dois woff2 críticos em `index.html`.
- **R9 — ícones (D1).**
  - Uma família em SVG com `currentColor`, servida como componentes (`web/src/design/icons.tsx`).
  - Zero emoji em strings da UI.
  - Glifos tipográficos da fonte (❧ ✦ ✧) só como ornamento, nunca como ícone de controle.
  - A atribuição vai na página legal se a licença exigir.
- **R10 — sistema de controles.**
  - Três tamanhos (sm/md/lg) × três variantes (primary/secondary/ghost) + um chip + um segmented control.
  - As classes antigas viram aliases ou são removidas.
  - Um único `.combat-card`, um único `.tab` e um único keyframe de pulso.
- **R11 — movimento.** Barras com `transform: scaleX`; `--ease-spring-soft` removido ou sem overshoot; durações via `transitionFor()`.
- **R12 — z-index.** Escala `--z-hud < --z-toast < --z-banner < --z-overlay` usada em **todo** `position: fixed/sticky` com z-index.
- **R13 — decoração.** Faixas laterais removidas ou com um único significado documentado ("hostil/urgente"). Glow só no estado "armado/selecionado agora". O traço decorativo de `.hud__label::after` sai.

### Fora de escopo

- Mudar a estrutura dos painéis ou das listas do HUD (SPEC-323). Headings semânticos (SPEC-324).
- Trocar as famílias de fonte principais (EB Garamond fica).
- O mapa pintado (SPEC-323, opcional).

## 3. Design técnico

**Arquivos novos**
- `web/src/design/icons.tsx`: componentes `<Icon name="menu|place|exit|map|warning|quest|abyss|sword|voice|close|check|…" />`, `aria-hidden` por padrão, `currentColor`.
- `web/.stylelintrc.json`: regras de R6.
- `web/scripts/contrast.mjs`: lê os tokens de `:root`, converte OKLCH → sRGB e valida uma tabela de pares texto/fundo exigidos (falha com exit 1). Chamado por `web/tests/contrast.test.mjs`.

**Arquivos alterados**
- `web/src/styles.css`, `web/src/workspace.css`, `web/src/tabs.css`, `web/src/map.css`, `web/src/design/tokens.css`: tokens novos e substituições.
- `web/src/App.tsx:42-56`: fases sem emoji. Isso também é feito pela SPEC-320; aqui fica a varredura final.
- `web/src/components/PlayScreen.tsx:39-41,81-97`, `web/src/workspace/ChatSurface.tsx`, `web/src/components/MapTab.tsx`, `web/src/components/DeckCard.tsx`, `web/src/components/WorldMap.tsx`, `web/src/components/Hud.tsx`, `web/src/components/CreateScreen.tsx`: glifos → `<Icon>`.
- `web/package.json`: `stylelint` + `stylelint-config-standard` em devDependencies; `lint` passa a incluir `stylelint "src/**/*.css"`.
- `web/index.html`: `<link rel="preload" as="font" type="font/woff2" crossorigin>` para os dois woff2 críticos.
- `web/src/design/effects.registry.ts` + `web/e2e/effects.spec.ts`: remover os glows desligados, mover as barras para `scaleX`.

## 4. Plano passo a passo

### Etapa 1 — contraste no token (maior ganho, menor risco)
1. **Testes:** `web/tests/contrast.test.mjs`:
   - pares exigidos: `--ink`/`--muted`/`--faint`/`--danger-text`/`--abyss-text` sobre `--surface`, `--surface-2`, `--bg-deep` e `--bg` com ≥ 4,5;
   - `--field-border` sobre o fundo do compositor e `--surface` com ≥ 3,0.
   - Começa vermelho.
2. **Implementação:** tokens novos e substituição de `color: var(--danger)` → `var(--danger-text)` nos seletores de texto.
3. **Verificação:** `npm test`; e2e axe (`color-contrast`) em **todas** as abas de contexto (Personagem, Combate, Codex com todas as categorias, Bestiário, Mapa), estendendo `web/e2e/visual-surfaces.spec.ts` ou um novo `a11y-contrast.spec.ts`.

### Etapa 2 — família `--abyss`, hex e tokens órfãos
1. **Testes:**
   - `web/tests/design.test.mjs` (estender): nenhum `#[0-9a-f]{3,8}` nem `rgb(a)(` fora dos arquivos de token;
   - nenhum `var(--x` sem definição (parse simples de `--x:` vs `var(--x`).
2. **Implementação:** substituições. Depois, stylelint no `lint`.

### Etapa 3 — raio e sistema de controles
1. **Testes:** stylelint (raio só por token); `design.test.mjs`: um único bloco `.combat-card {`, um único `.tab {` e um único keyframe de pulso.
2. **Implementação:** consolidar as classes; pílula só em tags de status.

### Etapa 4 — tipografia
1. **Testes:** e2e (`visual-surfaces`): em todo `button, [role=tab], .hud__label`, o `font-size` computado é ≥ 13,6 px (0,8rem com raiz de 17 px) e `font-family` não começa com "Cinzel", exceto títulos com `data-title`.
2. **Implementação:** CSS + preload.

### Etapa 5 — ícones
1. **Testes:** `web/tests/no-emoji.test.mjs`: varre `web/src/**/*.tsx|ts` (exceto testes) por `\p{Extended_Pictographic}` em literais de string/JSX, com zero ocorrências permitidas fora de uma allowlist (❧ ✦ ✧ como ornamento).
2. **Implementação:** `icons.tsx` e as trocas; atribuição em `web/legal` se aplicável.

### Etapa 6 — movimento, z-index, decoração
1. **Testes:** `design.test.mjs`: sem `transition: width`; todo `z-index` numérico literal fora de `:root` é rejeitado. `e2e/effects.spec.ts` atualizado junto com o registry.
2. **Implementação:** `scaleX`, escala `--z-*`, remoção das faixas e dos glows.

**Verificação final:**
- `cd web && npm test && npm run lint && npm run test:e2e -- visual-surfaces effects a11y-contrast workspace-shell`.
- Screenshots 390×844 e 1440×900 de cada aba, antes e depois.

## 5. Critérios de aceite

- [ ] `contrast.test.mjs` verde: `--faint`, `--danger-text` e `--abyss-text` ≥ 4,5:1 sobre todas as superfícies; `--field-border` ≥ 3:1. `--danger` não é usado como cor de texto.
- [ ] axe sem violação de `color-contrast` em todas as abas de contexto.
- [ ] Zero hex/rgb fora dos tokens; zero tokens indefinidos; stylelint no `npm run lint` (CI).
- [ ] Raio só por token; pílula só em tag de status.
- [ ] Cinzel só em títulos ≥ 1rem; controles e rótulos ≥ 0,8rem; preload dos woff2.
- [ ] Zero emoji em strings da UI; uma família de ícones SVG `currentColor`; atribuição se exigida.
- [ ] Um único `.combat-card`/`.tab`/keyframe de pulso; sistema de botões 3×3 + chip + seg.
- [ ] Barras com `scaleX`, sem overshoot, durações por token; escala `--z-*` em todo fixed.
- [ ] Faixas laterais removidas ou com significado único documentado; glow só em "armado agora".
- [ ] `effects.registry.ts` e `e2e/effects.spec.ts` atualizados juntos; `npm test` e e2e do escopo verdes; `uv run pytest` verde.

## 6. Smoke test real

Staging, conta logada, 2–3 turnos (um em combate).

1. **Antes do deploy:** screenshots a 390×844 e 1440×900 de: história, Personagem, Combate (com carta de Ruptura/Abismo visível), Codex/Missões (com missão urgente ou falha, se houver), Mapa.
2. **Depois do deploy:** os mesmos screenshots. Conferir que os metadados estão legíveis com o brilho baixo do celular.
3. Abrir no Chrome Android, se disponível: ícones monocromáticos e nenhum emoji colorido.
4. Rodar o axe (extensão ou o e2e contra staging, se houver profile) numa sessão real.
5. Anexar os pares antes/depois ao handoff.

## 7. Riscos & compatibilidade

- **Não rodar em paralelo com a 321** (mesmos CSS). A 323 depende desta.
- **Regressão visual ampla:** a mudança é grande em CSS. Mitigar com screenshots por aba e com etapas pequenas e commitáveis (contraste primeiro).
- **Nova devDependency (stylelint):** `npm install` no worktree; atenção à RAM da máquina (rodar fora de outras suítes).
- **Licença dos ícones:** game-icons.net é CC BY 3.0 e exige atribuição; Phosphor é MIT. Registrar no `web/legal`.
- **Small caps do EB Garamond:** se o subset self-hosted não tiver `smcp`, o navegador sintetiza versaletes feias. Conferir o arquivo de fonte e, se faltar a feature, usar `--sans` nos controles.
- **Contratos e2e protegidos:** asserções de seletor ou texto em `web/e2e/contracts` passam pelo `/eval-publish`.
- **Backend e saves:** sem impacto.

## 8. Decisões do dono

- **D1 — família de ícones.** **Recomendado: híbrido, com Phosphor (MIT) na casca/UI e game-icons.net (CC BY 3.0, com atribuição) em itens, cartas e estados do mundo, mantendo um peso de traço por contexto.** Alternativas: só game-icons (mais temático, com atribuição) ou só Phosphor (mais neutro).
- **D2 — regra de forma.** **Recomendado: cantos vivos (2 px) em controles e painéis, 4 px em cards, pílula só em tags de status.** Alternativa: manter 4–8 px em tudo, só tokenizado.
- **D3 — tipografia de controles.** **Recomendado: EB Garamond small caps com piso de 0,8rem; Cinzel só em títulos ≥ 1rem.** Alternativa: sans do sistema (`--sans`) para HUD e números.

## Histórico de mudanças

- 2026-10-26 · implementação: tokens (`--faint`, `--danger-text`, `--field-border`, `--abyss*`, `--r-sharp`, `--label`), `scripts/contrast.mjs` + testes, lint de CSS em Node (`tests/css-lint.test.mjs`), ícones vendored (`design/icons.tsx`), créditos/NOTICE.
- **Desvios:** (1) em vez de stylelint (instalar mexeria no node_modules compartilhado) o R6 é um teste Node equivalente; (2) o subset do EB Garamond não tem `smcp`/`c2sc` (medido nos woff2): rótulos usam Garamond em CAIXA-ALTA verdadeira via `--label`, não versaletes sintetizados nem `--sans`; (3) `--mana`/`--stamina`/`--sans` e `--ease-spring-soft` removidos; (4) preload dos woff2 e axe em todas as abas ainda pendentes; (5) sistema de botões 3x3 não consolidado (só duplicatas `.combat-card`/`.tab`/pulso).
- 2026-10-26 · correções da revisão (sol): teste de emoji agora cobre ⚔ ⚠ ⬆ ⚰ ☠ (allowlist ❧ ✦ ✧ + caso must-fail); `--field-border` L 0,55 e aplicado a `.chron-search` e aos selects (≥ 3:1 também sobre `--surface-2`); botões preenchidos de perigo usam `--on-danger` sobre `--danger` (5,20) com pares em `contrast.mjs`; `parseOklch` recusa alpha < 1; ícone `download` no ".txt"; lint de CSS cobre fonts.css, payload `data:`, raios lógicos e tem catraca de `oklch()` literal (≤ 57, migrar para tokens = follow-up) e roda em `npm run lint`; abas mobile com ellipsis; preload dos woff2 (EB Garamond latin e Cinzel latin).
- Pendente/follow-up: `a11y-contrast.spec.ts` (axe em todas as abas), sistema de botões 3x3 e migração dos 57 `oklch()` literais. Pré-lançamento: reconferir autores game-icons em game-icons.net (autores aqui vieram do repositório oficial game-icons/icons: Lorc, Delapouite, Skoll).
