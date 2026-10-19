# SPEC-284 — revisão (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (coordenador, revisão independente) · **Data:** 2026-10-19 · **Commit revisado:** `57b763c`

## Escopo

Branch `spec-284`, `git diff main...spec-284` (1 commit, 45 arquivos). O foco foi achar mudanças de
comportamento escondidas nas correções de lint e de tipagem: refs "último valor", `visited` do
Workspace, `luDismissed` do PlayScreen, backdrop/foco do `ArtworkDialog`, foco do `ImageQuoteDialog`,
cards de raça/classe, `onKeyDown` da Arena e o CI. Também conferi R1–R4. Não revisei as 15+ supressões
`set-state-in-effect`/`exhaustive-deps` uma a uma: elas não mudam código, só silenciam a regra, e o
comportamento ficou idêntico ao da main.

## Análise dos pontos de risco

- **Refs "último valor" em `useEffect` sem deps** (useTypewriter, Turnstile, useModalFocus, useVoiceInput,
  ArtworkDialog, Workspace `surfaceRef`/`showChatRef`): **sem regressão.** Nenhum desses refs é lido
  durante o render nem em `useLayoutEffect`. Onde o ref é lido dentro de um efeito no mesmo commit
  (Turnstile `onTokenRef.current("")`, Typewriter `doneRef.current?.()`), o efeito que atualiza o ref
  vem declarado antes e roda primeiro. Os outros só são lidos em eventos/callbacks assíncronos
  (keydown, back bridge, transcript, widget), depois do commit.
- **`visited` como state com setState no render:** a guarda `!visited.has(tab)` impede loop. O React
  descarta o render e refaz antes de commitar, então a aba monta no mesmo commit, como antes. A
  identidade do Set só muda quando uma aba é adicionada, e `ContextSurface` só usa `visited.has`.
- **`luDismissed = luDismissedKey === pendingKey`:** comportamento equivalente. Os IDs de escolha são
  únicos por nível (`lvl{N}-carta`, `lvl3-subclass`…, `progression.py`) e o nível só sobe, então uma chave
  dispensada não volta. Tem até uma melhora: antes, a reabertura numa chave nova esperava um render
  (o efeito resetava a flag depois de pintar); agora a reabertura vale já no primeiro render.
- **`ArtworkDialog`:** sondei com Playwright temporário (apagado): o foco inicial vai para "Fechar
  imagem" (o `showModal` focou o botão), clicar na imagem não fecha, clicar no backdrop fecha e o foco
  volta para "Ampliar". Ao reabrir, nada se acumula: o listener é removido no cleanup.
- **`ImageQuoteDialog`:** a sonda confirmou o foco inicial em "Cancelar". Agora o foco também é
  reposto quando o `quote_id` troca, o que é aceitável.
- **Cards de raça/classe:** clique e teclado continuam selecionando: `effects.spec` choice.select
  passou, com clique na área da arte e Enter no botão. Exceção: ver P2-1.
- **Arena:** o `onKeyDown` foi para `.arena__zones`, que já contém todos os `button[data-target]`;
  as setas funcionam igual (F23 combat_gesture_keyboard verde).
- **R3:** os passos `typecheck:e2e`/`lint` saíram do `continue-on-error`. **R4:** o
  `client-error-dedupe.spec.ts` dispara a mesma assinatura 3 vezes e espera exatamente 1 POST (verde).
- Sem mudança em `web/e2e/contracts` ou `evals/`. Os arquivos de e2e alterados não têm hash travado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `web/src/components/CreateScreen.tsx:226-250` + `styles.css:1231` | Sem o `onClick` do `<article>`, clicar na **linha de chips de traço** do card de raça não seleciona mais a raça. `.card__chips` tem `z-index: 1`, fica acima do `::after` do `card__select` e o `elementFromPoint` cai no `<span class="chip">`. O resto do card (arte, tagline, descrição) e o teclado seguem selecionando. | Aceito: o chip é informativo e tem `title`. Corrigi a frase da spec §3 que dizia "cobre o card inteiro". Se o dono quiser o comportamento antigo: `.card__chips { pointer-events: none } .card__chips .chip { pointer-events: auto }` cobre os vãos, mas o clique no chip continua sem selecionar. |
| P2-2 | P2 | `docs/spec209/evidence/*.png` (4) | O commit trouxe as capturas de evidência da SPEC-209 regeradas. O `deck-character.spec.ts:145` regrava arquivos versionados a cada execução, e isso não tem relação com a SPEC-284. | Revertidas para a main neste review. O fato de um teste regravar evidência versionada é pré-existente; fica de follow-up (gravar só com `RPG_CAPTURE_EVIDENCE=1`). |
| P2-3 | P2 | `web/src/combat/Arena.tsx:77` | O `role="toolbar"` sugere o padrão WAI-ARIA de uma parada de Tab (roving), mas cada alvo segue tabulável. Não é erro de axe (todos verdes); é só uma semântica imprecisa. | Follow-up opcional: roving tabindex nos alvos ou `role="group"` (com a regra jsx-a11y ajustada). |

## Correções aplicadas

- Revertidas as 4 PNGs de `docs/spec209/evidence/` para a versão da main (P2-2).
- Spec §3 corrigida quanto à cobertura do `::after` nos cards (P2-1).
- (No mesmo commit de review.)

## Pendências

- P2-2: evitar que `deck-character.spec.ts` regrave evidência versionada fora de captura explícita (dono: frontend; spec futura de higiene de e2e).
- P2-3: semântica do toolbar da Arena (opcional, sem spec).
- Flake sob carga: `effects.spec.ts:276` (card.arm @1280) falhou 1x no lote e passou 2/2 isolado.
- Flake sob carga: `dossiers.spec.ts:57` falhou 1 vez no lote de 74 testes e passou 2 vezes isolado.
  Não tem relação com o diff (o DossierBrowser só ganhou supressões de lint e um `if/else` no lugar do ternário).

## Comandos rodados

```text
npm test → 148/148 pass
npm run lint → 0 achados
npm run typecheck:e2e → 0 erros ; npm run typecheck → 0 erros
CI=1 npx playwright test client-error-dedupe combat-gesture combat-outcome image-quote portrait-overlay visual-surfaces workspace-shell voice-input deck-character dossiers map-tab consent --project=chromium → 72 passed, 1 skipped, 1 flaky (dossiers:57; isolado 5/5 e 1/1 verde)
CI=1 npx playwright test critical-journeys --project=chromium → 37/37 passed
CI=1 npx playwright test effects --project=chromium → 41 passed, 7 skipped, 1 flaky (card.arm @1280, linha 276; isolado 2/2 verde)
sondas Playwright temporárias (ArtworkDialog foco/backdrop/reabrir; ImageQuote foco; hit-test do card de raça) → confirmado acima; arquivos removidos
```
