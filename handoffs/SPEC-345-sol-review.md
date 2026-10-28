# SPEC-345 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (final, `56cd5793`): todos os P1/P2 e o R-1 estão fechados; resta 1 P3 de 1 linha (F-1, botão Ruptura), não bloqueante. Ver § Re-review final.
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `6f24a7aa` (1ª) · `27f2720c` (re-review) · `56cd5793` (final)

## Escopo

Branch `spec-345` (`main...6f24a7aa`, 5 commits: 12ec9557 → 6f24a7aa). Revisei backend (`api.py::_combat_block`,
`services/turn_outcome.py`, `services/conflict_summary.py`, `services/presentation_history.py`,
`services/combat_preview.py`, `agents/loot.py`, `agents/combat.py`), front (`TargetChip.tsx`,
`OnboardingHint.tsx`, `ChatSurface.tsx`, `Workspace.tsx`/`fightChip.ts`, `App.tsx`, `ForjaPanel.tsx`,
`styles.css`, `workspace.css`, `tabs.css`), os testes novos e os prints `docs/spec345/prints/depois/`.
Ficaram fora: smoke real (§6), R12 (perf 3×) e suíte completa (coordenador).

O que está correto:
- **R2/R3 (`api.py:2808-2812, 2845-2850, 2976-2980`)**: o filtro usa o mesmo predicado de `alive`, só na view
  (o teste `test_estado_nao_muda` prova o deepcopy). `encounter_view` fica intacto (R2.4). Inimigo com Vitalidade 0
  e sem `dead`/status de saída continua em `enemies`, `positions` e presságio (`test_inimigo_vitalidade_zero_continua_no_combate`).
- **R1 (`TargetChip.tsx:30-37, 62-63`)**: `spent` só para `role === "enemy"` com `vit === 0 && max > 0`. Jogador e aliados
  não mudam, e nenhum dado novo é exposto. O print `depois/on-360_07` mostra "sem Vitalidade".
- **R4 (`conflict_summary.py:321-346`, `loot.py:54-61`, `combat.py:2282`)**: `canonical_summary_text` não muda e segue no
  prompt (`loot.py:509-517`) e no arquivista. A política anti-invenção fica igual.
- **R5.4/R5.5**: `history_page` limpa só as linhas `role == "narrator"` numa cópia, sem tocar o registro persistido.
  As linhas do jogador não passam pela limpeza. A mensagem interna mantém o `[SISTEMA]`. Também não há interação com
  a SPEC-344: o embrulho `<entrada_do_jogador>` só existe nas mensagens que vão ao LLM, e o estado e o histórico não o carregam.
- **R6 (`combat_preview.py:180-201`, `combat.py:2342`)**: `allies` existe no escopo (`combat.py:1909`). O fallback é `Alguém`.
- **R7–R11**: o e2e `spec345-layout` passou. A linha de base win32 da 342 (`deck-342-baseline`) também continua verde
  (diferença < 1 %), então não precisa regravar. Snapshots e e2e de linha de base continuam com `skip` fora de win32, então o CI Linux não é afetado.
- Nenhum `with_structured_output` novo. Nenhum campo novo em `GameState`. Nada em `evals/`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/turn_outcome.py:83` | **Regressão da SPEC-199 R7 / 316 P1-1.** O regex antigo (`[ \t]*\[RESULTADO\][^\r\n]*`, sem âncora) removia o recibo **no meio da linha**. O novo exige `^`. Medido: `strip_system_tags("Fim. [RESULTADO] +50 XP")` devolve `'Fim. [RESULTADO] +50 XP'` (antes devolvia `"Fim."`). Um recibo forjado pelo LLM na mesma linha da prosa volta a chegar ao jogador no POST, no SSE antecipado e no `/history`. O streaming (`services/narrative_sink.py:96`) continua tirando o recibo, então o delta e a mensagem final passam a divergir. O `^` vem do §3 da spec, mas o contrato anterior era mais forte. Pelo mesmo motivo, `[SISTEMA]` no meio da linha (`Prosa [SISTEMA] Adaga`) também não é removido. | Manter a remoção da linha inteira e depois aplicar o padrão inline antigo (`[ \t]*\[RESULTADO\][^\r\n]*` → `""`) e `[ \t]*\[SISTEMA\][ \t]*` → `" "` em qualquer posição. Teste: `strip_system_tags("Fim. [RESULTADO] +50 XP") == "Fim."` e `"A [SISTEMA] B"` sem a tag. Registrar o desvio do regex no §3. |
| P1-2 | P1 | `web/src/styles.css:151-152` vs `:159` | **O item 9b ("sem opacity") não vale para `.btn--primary`.** A regra pré-existente `.btn--primary:disabled { opacity: 0.5 }` (`:159`) tem a mesma especificidade (0,2,0) de `.btn:disabled` (`:151`) e vem depois, então vence. O primário desabilitado (enviar, Nova jornada etc.) agora junta fundo `surface-2`, texto `muted`, borda tracejada **e** opacidade 0,5. O contraste estimado do texto cai de ~5,1:1 para ~4,2:1, o contrário do objetivo do item. | Tirar `opacity: 0.5` de `:159` (ou juntar as duas regras `.btn--primary:disabled` numa só, com `opacity: 1`). O teste e2e de contraste deve cobrir também um primário desabilitado, por exemplo o botão de envio vazio. |
| P2-1 | P2 | `web/src/styles.css:151` + `components/SaveScreen.tsx:172` | `.btn--danger` desabilitado (Apagar saga com `busy`) mantém o fundo `--danger`, porque `background-image: none` não tira `background-color`, e ganha texto `--muted`. O contraste estimado fica em ~2,3:1. Antes era ~3,9:1. | `.btn--danger:disabled { background: var(--surface-2); border-color: var(--danger); }` ou `color: var(--on-danger)` nesse caso. |
| P2-2 | P2 | `web/src/styles.css:151` + `.btn--ghost` (`:160`) | O ghost desabilitado tem a mesma cor do habilitado (`--muted`). Só a borda tracejada diferencia os dois estados, e o sinal de "indisponível" é fraco. O motivo novo da Forja (`ForjaPanel.tsx:101-105`) ajuda só ali. | Aceitável como está. Se quiser reforçar, use `--faint` só para o ghost desabilitado, conferindo ≥ 3:1. |
| P2-3 | P2 | `docs/spec345/prints/depois/` | Os prints "depois" não cumprem R13 nem os critérios de aceite: (a) `off-360_06-jogo.png` mostra a tela "Continuar jornada" em fade, não o 1º turno, então não prova R10; (b) `on-360_07` e `off-360_08` são **byte-idênticos** (md5 `57ed7ad5…`); (c) faltam `on-360_09-mao`, `off-360_12-desfecho`, `on-1440_12-r1-pos` e `off-1440_13-desfecho`, que os critérios R4/R5/R7/R8 citam; (d) as capturas usam o backend fake, não o roteiro do achado (API MockLLM, `off` e `on`). | Recapturar com o roteiro real, ou registrar no §8 que os prints de fixture substituem o roteiro e marcar os critérios que ficam sem print. Esperar o 1º turno renderizar antes do `screenshot`. |
| P2-4 | P2 | `web/e2e/spec345-layout.spec.ts:85` | `preparacao_sem_faixa` fica vazio se `.deck__head` não renderizar (`if (await head.count())`). Do mesmo jeito, `.deck__msg:empty` com `.catch(() => 0)` passa sem o elemento. Esse teste cobre também o SSR `deck_msg_montado_vazio` que não foi escrito (desvio (c)). | `await expect(head).toBeVisible()` antes de medir, e exigir `.deck__msg` montado com `aria-live="polite"`. |
| P2-5 | P2 | `tests/test_spec345_mech_log.py`, `tests/test_spec345_player_text.py` | Faltam dois testes do plano: `test_integra_no_no` (mech log pelo `combat_node` com deck `on` e aliado de cena, o único que prova o `*allies` em `combat.py:2342`) e `test_loot_tesouro_sem_id_nem_rotulo` com `item_id="adaga_ferro"` pela fronteira `format_response`. O teste atual usa `item_id=None`. | Escrever os dois, ou registrar o desvio no §8. |
| P2-6 | P2 | `web/src/workspace/Workspace.tsx:297` | O leitor de tela anuncia "R1" e depois "Em combate, rodada 1" (redundante). Há também duas chamadas a `fightChipLabel` por render. | `<span aria-hidden="true">R{n}</span>` + o `sr-only`, com uma única chamada guardada numa variável. |
| P2-7 | P2 | `services/narrative_sink.py:96` | O streaming de deltas (stream `on` no staging) só remove `[RESULTADO]`. Um `[SISTEMA]` escrito pelo próprio LLM aparece no delta e some na mensagem final. Está fora do texto de R5.2, mas vale ter uma fonte única. | Follow-up: o sink usa a mesma rotina inline de `turn_outcome`, sem colapsar o esvaziamento em `EMPTY_NARRATION_TEXT` no meio do stream. |

Notas sem severidade:
- `workspace.css:180` (`overflow: visible` + `clamp(0.68rem, …)`): a 360 px a fonte resolve em ~11,5 px (≥ 11, D4). Abaixo de ~340 px o piso de 10,9 px pode levar à sobreposição de rótulos. A spec só exige 360, então fica como observação.
- `api.py:2808`: `gone_ids` usa `id or name`. Se dois inimigos sem id tiverem o mesmo nome e um deles cair, o vivo também some da view. As fichas reais têm `id`, então isso não precisa de ação.
- Os critérios da §5 continuam desmarcados. R12 (perf 3×) e o smoke §6 não têm registro no branch. Ficam com o coordenador ou o executor.

## Correções aplicadas

Commits `529c4258` (código + testes) e `27f2720c` (prints da API local MockLLM). Conferência por item em § Re-review.

## Pendências

- P1-1 e P1-2: executor da SPEC-345, antes do pouso.
- P2-1 a P2-6: no mesmo ciclo, se for barato; senão, follow-up na própria 345 ou numa spec de polimento do front.
- P2-7: follow-up (unificar o sink com `strip_system_tags`).
- R12, smoke §6 e suíte completa: coordenador. 316 F-1 só fecha depois do P1-1.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec345_{combat_view,player_text,mech_log}.py tests/test_review_high_integration.py tests/test_combat_xp_outside_prose.py tests/test_pre_matrix_contracts.py tests/test_turn_delivery.py tests/test_turn_outcome_endpoints.py tests/test_combat_preview.py tests/test_encounter_manifest.py tests/test_combat_targeting.py tests/test_stream_structured.py tests/test_loot_voice.py tests/test_transicoes_criticas_b1.py → 182 passed (rc=0)
node --test web/tests/spec345-components.test.mjs → 5/5 pass
RPG_E2E_PORT=4988 npx playwright test e2e/spec345-layout.spec.ts e2e/deck-342-baseline.spec.ts --workers=1 → 13 passed, 1 skipped (prints opt-in)
py.sh -c "strip_system_tags('Fim. [RESULTADO] +50 XP')" → 'Fim. [RESULTADO] +50 XP' (main: 'Fim.')  [P1-1]
md5sum docs/spec345/prints/depois/*.png → on-360_07 == off-360_08  [P2-3]
```

## Re-review (2026-10-27, `1a967b4b..27f2720c`, branch rebaseada na `main` com a 342)

| Achado | Status | Evidência |
|---|---|---|
| P1-1 | **fechado** | `turn_outcome.py:83-86` sem âncora: `"Fim. [RESULTADO] +50 XP"` → `"Fim."`, `"Prosa [SISTEMA] Adaga"` → `"Prosa Adaga"`. Desvio (0) registrado no §8. |
| P1-2 | **fechado** | `styles.css`: uma regra única `.btn:disabled, .btn--primary:disabled, .btn--danger:disabled`, especificidade (0,2,0), com `opacity: 1`, fundo `--bg-deep`, `--muted` e borda tracejada. A regra antiga com opacity 0,5 saiu. `contrast.test.mjs` prova `--muted`/`--bg-deep` ≥ 4,5 e nenhuma `.btn*:disabled` com opacity < 1. |
| P2-1 | **fechado** | `.btn--danger:disabled` entra na mesma regra e perde o fundo vermelho (`.btn--danger` em `:978` tem especificidade 0,1,0). |
| P2-2 | **fechado** | O ghost desabilitado ganha fundo `--bg-deep` e borda tracejada `--line` e já se distingue do habilitado (transparente, borda sólida). |
| P2-3 | **fechado** | Os 8 prints `depois/` foram regravados pela API local MockLLM, todos com md5 distinto. `off-360_06` mostra o 1º turno com a dica recolhida e a narração visível. `on-360_07`/`09` mostram o chip `R2` e o lugar inteiro. `off-360_12` mostra a Preparação sem faixa preta. `on-1440_12` mostra o roster sem o Bandido 1 derrotado. |
| P2-4 | **fechado** | `spec345-layout.spec.ts:85-97`: `toBeVisible()` no cabeçalho e `toBeAttached()` em `.deck__msg:empty`, sem `catch`. |
| P2-5 | **fechado** | `test_integra_no_no_de_combate_com_aliado` (nó real, deck `on`, aliado de cena: `last_mech_log` começa com "Mestre Aldric", sem `?`) e teste de loot com item pela fronteira em `test_spec345_player_text.py`. |
| P2-6 | **fechado** | `Workspace.tsx:297`: `R{n}` com `aria-hidden="true"` e por extenso em `sr-only`. As duas chamadas ficaram, mas a função é pura e trivial; sem ação. |
| P2-7 | **fechado** | `narrative_sink.py:19-22,166` usa os mesmos padrões de `turn_outcome`, então o stream sai igual ao texto final. |
| R14/R15 (extra) | **ok** | `DeckCombat.tsx:104-107` (`scrollIntoView` nearest ao armar) + `.aimbar { scroll-margin-block-end }`. A ≤ 640 px o resumo da faixa de cena mostra só rodada e relógio (`workspace.css:411-415`, `SceneStrip.tsx:39`). `spec345-mobile390.spec.ts` está verde. |

### Achado novo

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R-1 | P2 (bloqueia o pouso pela regra "zero pendência" do dono) | `services/turn_outcome.py:83-85` (também usado em `narrative_sink.py:166`) | Sem âncora, o padrão consome o `\r?\n` final mesmo quando o recibo está **no meio** da linha. Com isso, a prosa da linha seguinte cola na anterior. Medido: `strip_system_tags("A estrada. [RESULTADO] +5\nVoce segue.")` → `'A estrada.Voce segue.'`. Só acontece com recibo forjado inline pelo LLM, mas aí o texto chega ao jogador corrompido no POST, no SSE e no `/history`. | Separar em dois padrões: (a) linha inteira, ancorado, consumindo a quebra: `^[ \t]*\[RESULTADO\][^\r\n]*\r?\n?` (MULTILINE); (b) inline, sem consumir a quebra: `[ \t]*\[RESULTADO\][^\r\n]*`. Teste: `"A. [RESULTADO] x\nB."` → `"A.\nB."`. |

### P3 restantes (nenhum bloqueia; listados a pedido do dono)

- **P3-1.** Controles fora de `.btn` continuam desabilitados por opacity: `.death-btn` (`styles.css:891`), `.placechip` (`:951`), `.combat-card button` (`:1000`), `.actionchip` (`:1039`), `.ws-bar .iconbtn` (`workspace.css:26`), `.msg__offer` (`:282`) e `.play-queue__ops button` (`:371`). Estão fora do item 9b, que tratava só do `.btn` global, e o WCAG isenta controle desabilitado. Se o dono quiser uniformidade, cabe numa spec de polimento da 322.
- **P3-2.** `--tabbar-h` vale sempre `0px` (`styles.css:71`; nenhum TS o define), então o `scroll-margin` da `.aimbar` é só `5rem`. O e2e passa a 390, mas o nome sugere uma altura dinâmica que não existe (pré-existente, também em `.pending-operation`/`.outcome-toast`).
- **P3-3.** Os prints da API não mostram o texto do desfecho com espólio ("Vasculho o corpo") nem um inimigo "sem Vitalidade": no MockLLM o Bandido 1 caiu direto, com excedente. R4/R5 e R1 estão provados por teste (pytest, SSR e e2e), não por print. Esse texto é o foco do smoke real do §6.
- **P3-4.** Na Arena do Véu (simulação de combate) a narração em MockLLM mostra a conta mecânica crua ("dano 7×2=14; Proteção (efeito) -1 -> 13; Vitalidade 10 -> 0 (excedente 3)"; prints `on-1440_12`, `on-360_07`). É pré-existente e fora desta spec. Vale conferir no smoke real se o mesmo bloco chega à narração fora da arena.
- **P3-5.** `npm run lint`: 1 warning pré-existente (diretiva `eslint-disable` sem uso em `src/hooks/useTypewriter.ts:65`), num arquivo que a spec não toca.
- Fora da revisão e com o coordenador: R12 (perf 3×), o smoke com LLM real do §6, a suíte completa e a marcação dos critérios da §5 / 316 F-1.

### Comandos (re-review)

```text
py.sh -m pytest -q -n 2 (14 arquivos da 1ª rodada + test_spec319_shadow_replay + test_streaming) → 233 passed, sem falhas
node --test tests/spec345-components.test.mjs tests/contrast.test.mjs → 10/10 pass
RPG_E2E_PORT=4988 npx playwright test spec345-layout spec345-mobile390 deck-342-baseline --workers=1 → 15 passed, 1 skipped (prints opt-in); porta liberada
npm run typecheck → limpo · npm run lint → 0 erros, 1 warning pré-existente
py.sh -c strip_system_tags("A estrada. [RESULTADO] +5\nVoce segue.") → 'A estrada.Voce segue.'  [R-1]
```

## Re-review final (2026-10-27, `9031452f..56cd5793`)

| Item | Status | Evidência |
|---|---|---|
| R-1 | **fechado** | `turn_outcome.py:83-93`: padrão ancorado para a linha inteira (consome a quebra) + `_RECEIPT_TAIL` para o meio da linha (não consome a quebra), juntos em `remove_receipts`. `"A estrada. [RESULTADO] +5\nVoce segue."` → `"A estrada.\nVoce segue."`. `narrative_sink.py:20,166` usa a mesma função. O teste `test_stream_e_final_iguais_com_recibo_no_meio` prova a paridade entre stream e texto final. |
| P3-1 | **fechado, com 1 resto** | Os 7 controles citados e `.actionchip[aria-disabled]`/`.play-queue__submit[aria-disabled]` agora usam o padrão do 9b: `opacity: 1`, `--bg-deep`, `--muted` e borda tracejada. `contrast.test.mjs` varre os dois CSS. A face `.combat-card[aria-disabled]` (`styles.css:1260`) segue com 0,5, o que aceito porque o motivo vem escrito. O resto está em F-1. |
| P3-2 | **retirado (contestação aceita)** | Errei: `--tabbar-h` é definido em `workspace.css:216` (`calc(48px + env(safe-area-inset-bottom))` no mobile). O meu grep estava truncado por `head -3`. O e2e `tabbar_h_definido_no_mobile` mede ≥ 48 px. |
| P3-3 | **mantido como nota** | Prints da API sem o texto de espólio e sem "sem Vitalidade". Já está coberto por teste e é o roteiro do smoke real do §6, que é do coordenador. Não é pendência de código. |
| P3-4 | **retirado (contestação aceita)** | A conta crua só sai no ramo `elif is_simulation:` (`agents/combat.py:2238-2240`, "Vitória no laboratório"). O jogo real passa por `_narrate`. É superfície de dev, fora do texto ao jogador. |
| P3-5 | **fechado** | A diretiva sem uso saiu de `useTypewriter.ts`. `npm run lint` ficou sem problemas. |

### Follow-up restante (P3, não bloqueia; correção de 1 linha)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| F-1 | P3 | `web/src/styles.css:1263` + `web/tests/contrast.test.mjs` (filtro `!/\.combat-card/`) | `.combat-card__rupture[aria-disabled="true"] { opacity: 0.45 }` continua com a opacidade antiga. É um botão vivo (`CardHand.tsx:75-78`, "Ruptura" quando não está pronta ou durante `busy`). O filtro do teste exclui qualquer linha com `.combat-card`, então pega também o `__rupture`, quando só a face da carta deveria ficar de fora. | Trocar pelo padrão do 9b (`opacity: 1; background: var(--bg-deep); color: var(--muted); border: 1px dashed var(--line)`) e estreitar o filtro do teste para `/\.combat-card\[aria-disabled/`. |

Pendências fora do código, com o coordenador: smoke com LLM real (§6), R12 (perf 3×), suíte completa no pouso, marcação da §5 e do 316 F-1.

### Comandos (final)

```text
py.sh -m pytest -q -n 2 (11 arquivos: spec345 ×3, xp_outside_prose, pre_matrix, turn_delivery, turn_outcome_endpoints, stream_structured, spec319_shadow_replay, streaming, review_high_integration) → 162 passed, 0 falhas
node --test tests/spec345-components.test.mjs tests/contrast.test.mjs → 11/11 pass
RPG_E2E_PORT=4988 npx playwright test spec345-layout spec345-mobile390 deck-342-baseline --workers=1 → 16 passed, 1 skipped (prints opt-in); nada escutando na 4988 depois
npm run lint → limpo
```
