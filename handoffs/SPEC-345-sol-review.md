# SPEC-345 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-10-27 · **Commit revisado:** `6f24a7aa`

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

(nenhuma ainda; para o executor: P1-1 e P1-2 bloqueiam o pouso, os P2 podem virar follow-up)

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
