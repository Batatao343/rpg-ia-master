# SPEC-342 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (1 P1 de CI, correção de 1 linha; o resto são P2 que podem virar follow-up)
> **Revisor:** Sol (Opus, spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `60b2277f`

## Escopo

Branch `spec-342` (`git diff main...spec-342`, 7 commits, de `26df617f` a `60b2277f`). Revisei:

- o backend: `agents/combat.py::_mark_nonlethal`, `api.py::_combat_block` e `services/scene_cards.py::public_scene`, com os 2 testes novos;
- o front: `CombateTab`, `useDeckArm`, `DeckCombat`, `Arena`/`TargetChip`, `deck.ts`, `SceneStrip`, `PlayQueue`, `KeywordTip`, `ForjaPanel`, `Hud`, `ContextSurface`/`MobileTabBar`, `ShortcutsSheet`, `useGlossary` e `workspace.css`;
- os e2e `deck-342-*`/`deck-combat-342`, `playwright.config.ts`, `.github/workflows/eval-gates.yml` e os prints de `docs/spec342/`.

Ficou fora: o smoke real (§6), que não foi executado; ele é do coordenador, antes do `done`.

## Respostas ao foco do coordenador

1. **Caminho `off`:** está intacto. Tudo o que é novo depende de `deckMode`, `omens`, `cena`, `pressagios_*`, `espolio_pendente`/`forja` ou da prop `deck`. O baseline de R24 passa localmente, e `combat-gesture.spec.ts` passa sem edição. Três mudanças aparecem no `off`, e as três são intencionais (§9): "Round" virou "Rodada" (R29), os homônimos ganham número na Arena (R28, `buildParticipants` sem condição de flag) e o chip de ganhos fica contido na coluna do chat no desktop (R27). Aceito as três. A troca para "Rodada" está certa, mas o espaço não aparece (ver P2-3).
2. **Backend atrás de flag:** OK.
   - `_mark_nonlethal` percorre `acao` mais `jogadas`, sem duplicar por identidade. Com `nonlethal=off` não faz nada, e manobras não são marcadas.
   - `view["cena"]` só aparece com `scene_cards.active()` e `scene` em dict. Em `off`/`shadow` a chave não existe.
   - `public_scene` expõe só `{id,nome,sabor}` e o relógio. `rodada` vem de `cs.tactical_round`, o mesmo contador que `conflict_orchestrator.py:2286-2291` passa a `abyss_clock`, e `ativo` usa o mesmo `>= ABYSS_CLOCK_START`.
   - Compatibilidade de texto: `NONLETHAL_RE` reconhece "Sem matar." depois de "Encerro a rodada:" e depois de "Encerrar turno:". O `_CLAUSE_SPLIT_RE` corta no ponto, então um nome de carta com "não" não nega a frase. Com `wrap_player_input` (SPEC-344) também funciona: `test_wrapped_player_input_still_marks_nonlethal` cobre. Nenhum caminho do servidor depende do prefixo `Encerrar turno` (só há um comentário em `api.py:1898`).
   - Nenhuma chamada LLM nova, nenhum structured output novo e nenhum campo de save novo (`cena` é só view).
3. **Risco de CI:** **falha.** Ver P1-1.
4. **Barra sticky a 390:** classifico como **P2** (P2-1). Não quebra função, porque tudo continua alcançável rolando. Mas viola o espírito de R4.4, e o teste não detecta a sobreposição.
5. **Fluxo de alvo, foco e teclado, tooltip, Forja, alvos ≥ 44 px e tokens:**
   - O fluxo de alvo único está correto: `deckTargets` e `aimMarks` vêm de `cardTargets`, `pick` vai para `deckArm.setTarget`, e a exclusão mútua entre carta e manobra funciona nos dois sentidos.
   - Foco: R15.1, R15.3 e R15.4 estão implementados e cobertos.
   - Esc em captura tem uma regressão (P2-2).
   - O tooltip em portal (`fixed`, preso ao viewport, `pointer-events: none`) está OK.
   - A confirmação inline da Forja está OK: Esc e "Cancelar" devolvem o foco à origem, e "Afiar" não pede confirmação.
   - O bloco `pointer: coarse` está OK. O teste não mede os botões da `aimbar` (P2-4).
   - Tokens: todo `var(--…)` novo existe. `--composer-h` é a variável medida em runtime, com fallback, e já era usada em `styles.css:387`. Não há cor literal. `border-radius: 50%` segue o padrão de `.folego__pip`, que já existia.
6. **B-8a ("Aguentar" na mão):** concordo. `utilitaria` é tipo de baralho por design (`cards._DECK_TIPOS`, SPEC-328). Mudar isso é regra/autoria e fica fora desta spec de front.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/e2e/deck-342-baseline.spec.ts:40` | O `playwright.config.ts` não tem `snapshotPathTemplate` nem filtro para este spec, e o job `frontend-selective` (`eval-gates.yml:135`, `ubuntu-24.04`) roda `npm run test:e2e` inteiro. No Linux, o Playwright procura `off-*-chromium-linux.png`, que não existe. Os 6 testes falham com "snapshot doesn't exist" e o gate de front fica vermelho. | Seguir o padrão de `visual-surfaces.spec.ts:6`: `test.skip(process.platform !== "win32", "linha de base R24 gerada em win32 antes da Etapa 1; evidência local")` no topo do spec (ou opt-in por env). Não vale gerar o baseline Linux agora: ele teria de vir do commit `ff4b1234` (pré-Etapa 1) num runner Linux, e o ganho não compensa. Registrar em §9 que a prova de R24 é local (win32) e corrigir a frase de §7 que diz que "a comparação roda no CI". |
| P2-1 | P2 | `web/src/workspace.css:382`; `web/e2e/deck-combat-342.spec.ts:180` | A 390, a barra de envio sticky (com fundo `var(--bg)`, mais escuro que o painel) cobre cerca de 40 % da base das cartas no 1º paint (`on-390-combate.png`). No estado de mira, ela cobre a instrução "Mirando …: escolha o alvo na arena." e o começo das regras (`on-390-mira.png`). `toBeInViewport({ ratio: 1 })` não detecta a sobreposição, então R4.4 passa só na letra. | Antes de ligar `RPG_CARD_DECK=on` no celular: (a) compactar a barra numa linha de 44 px com o fundo da superfície do painel (não `--bg`); (b) encurtar o que vem acima da mão a 390 (o `summary` da cena ocupa 3 linhas em small caps; dá para truncar o objetivo e o relógio em 1 linha); (c) no teste de R4.4, conferir que o canto inferior da 1ª `.deck-card` não está sob `.play-queue__end`, via `elementFromPoint` ou comparação de `getBoundingClientRect`. |
| P2-2 | P2 | `web/src/components/combat/DeckCombat.tsx:148-154` | Regressão do Esc. O listener passou para captura em `document`, e o `useTargeting` (`useTargeting.ts:30`) também escuta em captura no mesmo nó. `stopPropagation` não impede outro listener do mesmo nó, então os dois rodam. Com a mira de **manobra** ativa e a fila com cartas, Esc cancela a mira **e** apaga a fila. Antes, o listener do deck era de bolha e o `stopPropagation` do targeting o barrava. | No handler do deck, sair cedo quando houver mira de manobra: passar `maneuverAiming` como prop, ou fazer o `useTargeting` chamar `preventDefault()` e o deck checar `event.defaultPrevented` (já checa). Acrescentar um caso e2e: fila com 1 carta, mira de manobra, Esc → fila mantém 1 item. |
| P2-3 | P2 | `web/src/components/Hud.tsx:456` (+ `styles.css:526` `.hud__label { display: flex }`) | O B-4 não fecha na tela. O `<span>` vira item flex, e o espaço inicial de `" · Rodada N"` é descartado: o HUD mostra "COMBATE· RODADA 1" (`on-390-fila-sticky.png`). O e2e usa `toContainText`, que lê o `textContent` com espaço, e por isso não pega. | Pôr `gap: 0.4em` em `.combatblock .hud__label` ou `margin-left` no `.muted`; ou mover o " · " para fora do span. Vale também no `off`: refazer o baseline só se passar de 1 %, o que é improvável. |
| P2-4 | P2 | `web/e2e/deck-combat-342.spec.ts:199` | O teste "coarse targets ≥ 44" não mede `.aimbar[data-deck-aim] button` ("Jogar em X", "Outro alvo", "Cancelar"), que R5 exige. O CSS cobre esses botões, mas sem prova. | Medir com a carta armada antes de confirmar, acrescentando o seletor à lista. |
| P2-5 | P2 | `tests/test_spec342_nonlethal_jogadas.py`; `tests/test_spec342_scene_view.py:33` | Desvios aceitos, mas a cobertura ficou só unitária. Não há `test_second_card_kill_becomes_down` (o nó com 2 jogadas, a 2ª letal → `incapacitado`). `test_relogio_matches_engine_round` usa um `meta` sintético, e não "rodar até `out['abyss_clock']`" como o plano pedia. Os helpers estão certos, mas falta a prova de ponta a ponta no motor. | Follow-up: 1 teste de integração de cada, ou cobertura explícita pelo smoke §6, passos 2 e 3. |
| P2-6 | P2 | `web/src/workspace.css:333`; `on-390-combate.png` | A 390 o botão "Pilhas" encosta e quase passa da borda direita do painel (as contagens "… EXAURIDA 1" ficam na borda). | Pôr `max-width: 100%`/`min-width: 0` e quebrar a linha das contagens em ≤ 640 px. |
| P2-7 | P2 | spec §6 / §9 | O smoke real não foi executado, e o "desfecho" do baseline R24 não foi capturado. | O smoke é do coordenador antes do `done`. O desfecho pode ficar como pendência registrada. |

Fora do diff: a faixa escura "PREPARAÇÃO 2/—" sobrepõe "ACERVO (2)" e as cartas acima dela (`on-1440-forja.png`, `on-390-espolio.png`). Não é deste diff (sticky do loadout pré-existente) e merece um bug à parte.

## Correções aplicadas

Nenhuma até aqui. O revisor não edita código.

## Pendências

- **Bloqueia o pouso:** P1-1.
- **Antes de `RPG_CARD_DECK=on` no celular do staging:** P2-1 e P2-2.
- **Podem virar follow-up na própria 342 ou num bugfix curto:** P2-3 a P2-6.
- **Do coordenador:** P2-7 (smoke §6).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec342_nonlethal_jogadas.py tests/test_spec342_scene_view.py tests/test_spec325_nonlethal.py tests/test_scene_cards_node.py tests/test_api_jogadas.py → 60 passed
node --test tests/deck*.test.mjs → 24/24 pass (deck-342-logic 7, deck-components 4, deck-tokens-342 3)
RPG_E2E_PORT=4988 npx playwright test deck-342-baseline deck-combat-342 combat-gesture outcome-toast --workers=1 --project=chromium → 60 passed (win32)
npm run typecheck && npm run typecheck:e2e → 0 erros
npm run lint → 0 erros, 1 warning pré-existente (src/hooks/useTypewriter.ts:65); css-lint/contrast 13/13
```
