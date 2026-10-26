# SPEC-322 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (papel Sol, spec-reviewer) · **Data:** 2026-10-26 · **Commit revisado:** `5d29aa78` (branch `spec-322`)

## Escopo

`git diff main...spec-322` (38 arquivos, só `web/` + `NOTICE` + spec): tokens/contraste (`styles.css`,
`tokens.css/ts`, `scripts/contrast.mjs`), lint de CSS em Node (`tests/css-lint.test.mjs`), ícones
(`design/icons.tsx`, trocas nos TSX), licenças (`NOTICE`, `legal/credits.md`, `/creditos/`), tipografia
`--label`, registry de efeitos, `e2e/workspace-shell.spec.ts`. Fora: Playwright/axe/build (RAM baixa,
por instrução) — os itens visuais a 360 px e o axe ficam sem verificação nesta revisão. A spec segue
`in-progress` e já declara pendentes preload, axe em todas as abas e o sistema de botões 3×3.

Conferido e OK: os pares de `REQUIRED` passam (o mais justo: `--faint`/`--surface-2` = 4,69;
`--field-border`/`--surface` = 3,17). Não sobrou hex/rgb em CSS nem em TSX. As únicas `var()` sem
definição são `--composer-h`, `--ws-ratio` e `--app-vh`, que o JS define em runtime. `--mana`,
`--stamina`, `--sans` e `--ease-spring-soft` não aparecem em `src/`, `e2e/`, `tests/` nem `scripts/`.
Os botões só com ícone mantêm nome acessível (`aria-label` em fechar, exportar, custo, toggle de
arte e dispensar dica). Ícones decorativos ficam com `aria-hidden`; o "Único" é `role=img` com
rótulo. Sem CDN: os SVGs estão vendored. A atribuição CC BY 3.0 tem autor, link da licença e "sem
alterações", e o MIT do Phosphor está no NOTICE, nos créditos e no cabeçalho de `icons.tsx`;
`/creditos/` tem link no rodapé do `App.tsx:1051`. Todos os rótulos `--label` com caixa-alta estão
≥ 0,8rem, e Cinzel só aparece em títulos ≥ 1rem. As barras trocadas para `scaleX` têm `width:100%`
e `transform-origin:left`. `card.arm` passou a usar `ease-out`; `e2e/effects.spec.ts` não testa
easing, e o `hit.feedback` continua com `data-pct` e 0,24 s em `.tchip__bar > span`
(`styles.css:1295`). A edição em `workspace-shell.spec.ts:319-323` é legítima: o nome acessível
perdeu o "⬆". `web/e2e/contracts` e `evals/` não foram tocados.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/tests/icons.test.mjs:15` | O teste "zero emoji" apaga as faixas U+2600–27BF, U+2300–23FF e U+2B00–2BFF antes de testar `\p{Extended_Pictographic}`. São exatamente os glifos que viram emoji colorido no Android: ⚔ ⚠ ⬆ ⚰ ☠ (medido: todos são EP e todos caem na faixa apagada). O teste não pega a regressão que a R9 quer impedir. ❧ ✦ ✧ ✓ → nem são EP, então a remoção é desnecessária (medido: sem ela, a árvore atual já passa com 0 ocorrências). | Remover o `.replace(...)`. Se precisar de allowlist, que seja explícita e por caractere (`❧✦✧`), nunca por faixa. Acrescentar um caso negativo (string com "⚔" precisa falhar). |
| P1-2 | P1 | `web/src/styles.css:1025`; `web/src/components/tabs/tabs.css:11`; `web/src/styles.css:969` | Há campos de formulário fora da R3. (a) `.chron-search` é `type="search"` (`Hud.tsx:324-326`), não entra no seletor base de `styles.css:203` e usa borda `--line-soft` sobre `--surface-2`, ≈ 1,3:1. (b) `.deck__sub select` sobrescreve com `--line` sobre `--surface` = 1,89. (c) `.card-hand__target select` usa `--line` sobre `--bg-deep` = 2,21. Todos falham o 1.4.11 (3:1). Além disso, `--field-border` sobre `--surface-2` dá 2,86, e `contrast.mjs:61` não testa esse fundo. | Usar `var(--field-border)` nos três; incluir `input[type="search"]` no seletor base. Pôr `--surface-2` na lista de fundos de `--field-border` em `contrast.mjs:61` e subir o token para L ≈ 0,54 se precisar. |
| P2-1 | P2 | `web/src/styles.css:848`, `:960` | `.btn--danger` e o primário em combate têm texto `oklch(0.98 0.02 30)` sobre um degradê `--danger-bright`→`--danger`. No topo, sobre `--danger-bright`, o contraste é 3,73. O texto (0,96rem, peso 600) não conta como "grande", então falha 4,5. O problema já existia antes, mas cai no "contraste AA em todo texto". O `contrast.mjs` não cobre pares de botão (`--on-accent`/`--accent` = 7,84 passa; o vermelho não). | Criar token `--on-danger` e acrescentar a `REQUIRED` os pares de botão (`--on-accent`/`--accent`, `--accent-strong`, `--on-danger`/`--danger-bright`). Escurecer o topo do degradê ou usar `--danger` sólido. |
| P2-2 | P2 | `web/src/components/Hud.tsx:320` | Ficou um glifo de controle, "⤓ .txt", e o ícone `download` já existe em `ICONS`. Não é EP, então nenhum teste pega. | `<Icon name="download" /> .txt`. |
| P2-3 | P2 | `web/tests/css-lint.test.mjs:27`, `:18` | Pontos em que o lint em Node não equivale ao stylelint (desvio R6 documentado). (a) Linhas com `data:image/svg` são puladas inteiras, então um hex na mesma declaração passa. (b) `fonts.css` fica fora de todas as regras. (c) Não vê `border-start-*-radius` lógico. (d) `oklch()` literal fora de `:root` passa (`styles.css:291, 660, 848, 960`; `workspace.css` mtabbar `oklch(0.13 …/0.96)`): não é hex, mas a cor vaza do token. (e) Roda em `npm test`, não em `npm run lint`. | Em (a), tirar a URL `data:` da linha antes de testar em vez de pular. Em (d), mover os literais para tokens ou, no mínimo, registrar uma allowlist. Em (e), confirmar que o CI roda `npm test` em `web/`. |
| P2-4 | P2 | `web/src/workspace.css:137-141` (`.mtabbar__btn` 0,66→0,8rem, `white-space: nowrap`), `.ws-mhead .ws-stat--fight` 0,6→0,75rem, título do mhead 0,95→1,06rem | Risco de regressão da SPEC-321 a 360 px: seis abas em nowrap a 13,6 px somam ≈ 350 px. Os botões têm `min-width: 44px`, não `min-content`, então o texto pode cortar ou vazar. A coluna de status do mhead também cresceu. Não foi verificado (sem Playwright). | Antes de `done`, rodar `mobile-single-pane`, `touch-targets` e `workspace-shell` a 360×800, com screenshot. Se estourar, usar ícone com rótulo curto ou `font-size: clamp(...)`. |
| P2-5 | P2 | `web/scripts/contrast.mjs:35-38` | `parseOklch` ignora alpha (`/ a`) e não lê `color-mix()` (lança erro). Hoje nenhum token de `REQUIRED` tem alpha, mas um token translúcido usado como texto passaria como opaco. | Recusar alpha < 1 em token de texto (erro explícito). |
| P2-6 | P2 | spec §Histórico, desvio 4–5 | Ainda pendentes: preload dos woff2, axe `color-contrast` em todas as abas, sistema de botões 3×3 + chip + seg, screenshots de antes e depois. A spec não pode ir para `done` sem eles ou sem um desvio aprovado. | Fechar ou registrar como desvio aprovado pelo dono antes do pouso. |

Nota de licença (sem achado): a autoria por ícone, com Lorc em 11, Delapouite em `scroll-quill` e
Skoll em `diamonds`, não pôde ser checada offline: o pacote iconify não traz o autor por ícone.
Vale conferir em game-icons.net antes do pouso.

## Correções aplicadas

Nenhuma (revisão só leitura).

## Pendências

- P1-1 e P1-2: o executor da SPEC-322 corrige na branch antes do pouso.
- P2-1 a P2-6: P2-2 e P2-4 entram nesta spec. P2-1, P2-3 e P2-5 podem ir para a SPEC-323 se o coordenador aceitar.

## Comandos rodados

```text
git diff main...spec-322 --stat → 38 files, +730/-327
cd web && npm test → 190 pass, 0 fail
cd web && npx tsc --noEmit → exit 0
node (scratch) contraste extra → field-border/surface-2 2.86; line/bg-deep 2.21; line/surface 1.89; branco/danger-bright 3.73
node (scratch) EP sem o strip → 0 ocorrências na árvore; ⚔ ⚠ ⬆ ⚰ ☠ são EP e caem nas faixas removidas pelo teste
```
