# SPEC-376 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (Sol, `spec-reviewer`) · **Data:** 2026-11-04 · **Commit revisado:** `9bab10ab` (base `main` = `9468d058`)

## Escopo

Branch `spec-376`, `git diff main...HEAD` (15 commits, 29 arquivos): A1/A2 (geradores apagados), A5
(`migrate_bestiary_v4 --write`), B1 (3 scripts de staging), C1–C4 (código sem chamador e stubs `ImportError`),
docs (`CARTAS.md`, `CLASSES.md`, `HANDOFF-PROXIMA-SESSAO.md`), adendos nas SPEC-012/074/302/313, testes
(`test_mvp`, `test_cutover_audit`, docstring de `test_conflito_autoria_cartas`, `test_spec376_fonte_dados`
novo), `ruff-baseline.toml` e `tests/size_budget.json`.
Fora desta revisão, porque o pouso é parcial e a spec fica `in-progress`: A3 (`AUTORIA.md` e adendo da SPEC-273),
que espera a SPEC-374; A4, cancelada pela D2; C5, que não se aplica pela D5. O `handoffs/SPEC-376-independent-review.md`
(revisão da spec) não foi tocado.

## W7 refeito pelo revisor

1. **Deriva, `gen_cards_v4.py`.** Fiz o procedimento num diretório do scratchpad fora de qualquer repo
   (`git rev-parse` falha, `test ! -d .git`). O `data/` veio de `git archive main data` e o script de
   `git show main:scripts/gen_cards_v4.py`. Rodei com `RPG_ROOT="$PWD"` e o `python -I` do venv principal.
   - Sozinho: nas 153 Cartas dos 5 JSON de classe, remove `tier`, `level_req`, `apex`, `momento` e
     `raridade` de todas, mais 1 `reacao_inicial` (Corruptor). Nenhuma Carta a mais ou a menos.
   - Seguido de `gen_tiers_5_plus.py --write`: a cadeia devolve `tier`, `level_req` e `apex`, mas
     **continua removendo `momento` e `raridade` (153 cada) e `reacao_inicial` (1)**.
   - Bate com `docs/spec376/deriva.md`. A deriva destrutiva é real, então o apagamento atende à D1.
   - Snapshot `git status --porcelain -- data/ scripts/` do checkout principal: vazio antes e depois.
     O diretório temporário foi apagado.
2. **W2 (evals A/B).** Rodei as 12 suítes do `eval-gates.yml` com `--seed 7`, `RPG_FORCE_MOCK=1`:
   A no worktree destacado da `main` (`9468d058`), B no HEAD da branch (`9bab10ab`, com C1–C4 juntos).
   `evals compare`: `passed: true`, `regressions: []`, todos os 27 deltas `0.0`, `hard_failures: []`
   nos dois.
3. **R23, matriz de import depois da C4.** Em subprocess novo, com 8 ordens (`∅`, `rag`, `main`, `api`,
   `agents.librarian`, `agents.bestiary`, `agents.npc`, `agents.world_simulator`), as 6 identidades deram
   `True` em todas.
4. **`ruff-baseline.toml`.** O diff da branch é **só** a remoção das 2 linhas dos scripts apagados (R14 ok).
   - Num worktree limpo da `main` (`9468d058`), `ruff_baseline.py --check` dá **stale** (exit 1). Regerar só
     **encolhe** a baseline: `agents/archivist.py` perde `F841` e `services/prologue.py` sai. Essa dívida já
     foi paga na `main`.
   - `uv run ruff check .` dá "All checks passed!" na `main` e na branch.
   - **O CI não roda `ruff_baseline.py --check`.** `.github/workflows/validate.yml:61-62` roda só
     `ruff check .` e `ruff format --check .`. Então **a `main` não está vermelha no CI**; o "stale" é só
     ajuste pendente, sem efeito no gate.
   - Na branch, regerar também tiraria `E741` de `tests/test_mvp.py`. Essa dívida foi paga pela C1: o teste
     apagado usava `l`.
5. **Re-grep dos símbolos.** Rodei `git grep -w` no repo inteiro, inclusive `web/` e `scripts/`, excluindo
   `specs/`, `handoffs/`, `docs/historico/`, `docs/specNNN/` e `project_index/`. Os símbolos foram:
   `tick_conditions`, `escort_stop`, `region_pressure`, `faction_relation`, `relation_label`, `_overlay_path`,
   `_npc_db_path`, `_infer_tier_from_name` e os 3 scripts de B1.
   - **Nenhum chamador vivo.** Os hits que sobram são todos esperados:
     - docstring de `services/conflict_orchestrator.py:358-359`, que a R17 manda manter;
     - `docs/spec376/README.md`;
     - `_meta` "Gerado por scripts/gen_cards_v4.py" nos 5 JSON de classe (A4, cancelada);
     - `docs/descricao_projeto/fontes/exploracao/explore_0{2,6}*.md`, que é snapshot descritivo;
     - `docs/spec217/primary-staging-2026-10-18.md:34`, que é evidência histórica.
   - Stubs `ImportError`: os 7 arquivos com `monkeypatch.setattr(npc, "RAG_AVAILABLE", False)` passam
     (`RAG_AVAILABLE = True` continua como constante).
6. **`migrate_bestiary_v4` sem `--write`.**
   - `main()` sai 2 antes de qualquer `open(..., "w")` (`scripts/migrate_bestiary_v4.py:1314-1322`; as
     escritas estão em `:1337` e `:1344`).
   - `__main__` usa `raise SystemExit(main())`.
   - O teste `test_migrate_bestiary_sem_write_nao_grava` chama o `main([])` real sobre `tmp_path` e confirma
     duas coisas: o arquivo fica intacto e `cards/` não é criado. Ou seja, testa o comportamento real, não um mock.
   - Os 3 testes que carregam o módulo (287/290/295) passam.

## Achados

Sem P0 nem P1.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `tests/test_spec376_fonte_dados.py:1` | O arquivo de teste novo se chama `test_specNNN_*.py`, o que `docs/guias/BRIEF_SUBAGENTE.md` § Testes proíbe. Os dois primeiros testes leem arquivo de doc/fonte, fora do caso (c). | Mover `test_migrate_bestiary_sem_write_nao_grava` para um teste de feature (ex.: `tests/test_bestiary_migration.py`). Os testes de "doc não manda rodar gerador" podem ir para `tests/test_cutover_audit.py`, que já faz auditoria estática, ou sair. Pode ser feito junto da A3. |
| P2-2 | P2 | commits `3c3af618` / `0ea5c14a` / `13e1e6de` | A C3 ficou em 3 commits. O `3c3af618` acrescentou comentário que estourou o size budget, e os dois seguintes são fixups. Reverter só o `3c3af618` conflita com os outros, e o `3c3af618` sozinho deixa `test_size_budget` vermelho. Isso fere a W4 ("cada commit revertível sozinho"). | Sem force-push (W8), aceitar e registrar. Na próxima etapa, juntar o fixup no próprio commit antes de seguir. |
| P2-3 | P2 | `docs/spec376/README.md:20,17` | Faltam evidências: a base da C0 está como `61dxxxx` (placeholder), e o R3 pede "saída do re-grep no README", mas há só o resumo "R3 limpo". | Pôr o SHA real (`90becbce`) e colar a saída curta do `git grep -w` por símbolo. Pode ir no commit da A3. |
| P2-4 | P2 | `ruff-baseline.toml` (critério §5 "`--check` verde") | O critério não fecha: o `--check` segue stale por deriva só de encolhimento que já existia na `main` (archivist/prologue), mais `E741` de `tests/test_mvp.py`, paga por esta spec. O CI não depende disso. | O coordenador regera a baseline em commit próprio na `main` (só remoções; conferir que o diff só encolhe), ou anota que o critério vale "diff só das linhas apagadas". |
| P2-5 | P2 | `tests/size_budget.json` (commit `daf7e835`) | Ajuste fora de escopo: `services/card_effects.py` 1828→1826 (só ratchet para baixo, arquivo que a SPEC-377 também mexe). Também `migrate_bestiary_v4.py` 1354→1365 (+11): arquivo acima de 1.000 linhas que cresceu, mas a D3/R11 exige a mudança. | Inofensivo. Registrar para não haver conflito com a 377 no pouso. O +11 é aceito pela D3. |
| P2-6 | P2 | `docs/design/CARTAS.md:112-115` | A frase "Pendências de cutover" ficou truncada ("trocar … para as Cartas iniciais (R9) e remover `data/player_abilities.json` e o caminho `known_abilities` foram removidos"). | Reescrever em uma frase: "Cutover concluído: `player_abilities.json` e `known_abilities` foram removidos e não devem ser recriados." |

## Correções aplicadas

Nenhuma. A revisão só escreveu este arquivo.

## Pendências

- A3 (`docs/guias/AUTORIA.md`, seção "Cartas e classes") e o adendo datado na SPEC-273 (R8): esperam a SPEC-374
  (executor, na mesma etapa).
- A4 (`_meta` dos 5 JSON de classe): cancelada pela D2. Os 5 `_meta` ainda dizem "Gerado por
  scripts/gen_cards_v4.py" (o coordenador decide se reabre depois das 367/369).
- R15: candidatos de cascata `jev_shadow_measure` e `projection_measure` (spec futura).
- P2-4: regerar `ruff-baseline.toml` na `main`, só com remoções (coordenador).
- Suíte completa 1× no pouso (coordenador). Os critérios "suíte verde" e "Sol APPROVED" da §5 fecham no pouso
  final, depois da A3.

## Comandos rodados

```text
gen_cards_v4 (main) em dir isolado sobre git archive main data → 153 Cartas perdem momento/raridade; +gen_tiers --write mantém a perda
git status --porcelain -- data/ scripts/ (principal) antes/depois → vazio/vazio
evals run 12 suítes --seed 7 (A=main 9468d058, B=9bab10ab) + evals compare → passed, regressions [], deltas 0
R23 matriz 8 ordens (subprocess, RPG_FORCE_MOCK=1) → 6 identidades True em todas
ruff_baseline.py --check (worktree limpo da main) → stale (só encolhe: archivist F841, prologue)
ruff check . (main e branch) → All checks passed!
grep ruff .github/workflows/validate.yml → só `ruff check .` e `ruff format --check .` (sem --check da baseline)
git grep -w <símbolos removidos> → sem chamador vivo
dup_helpers.py --diff main...HEAD → nenhuma função nova com nome repetido
pt.sh 17 arquivos (spec376, mvp, cutover_audit, autoria_cartas, size_budget, 7 de RAG_AVAILABLE, 287/290/295, 355, handoff_names) → 295 passed
pt.sh fase0, fase25, persistence_logs, card_effects_grammar, mecanica_orfa, itens_vivos, conflito_virtudes, world_sim/faction/npc_world → 257 passed
```
