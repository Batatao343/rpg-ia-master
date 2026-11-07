# SPEC-400 — revisão sol (review)

> **Veredito:** `APPROVED`
> **Revisor:** Opus 5.5 / Sol (`spec-reviewer`) · **Data:** 2026-11-07 · **Commit revisado:** `d4db977a`

## Escopo

`git diff main...HEAD` no worktree `rpg-spec-400`, em 6 commits:
- avaliador (autor de eval): `f7fdac05` (R3/R4: `ficha_vs_base`, assert curado) e `221e9051` (adendo 13 do `SPEC-373-eval-authoring.md`);
- produto (executor): `9214cc90` (testes vermelhos), `ad775c34` (R1/R2), `42cc4276` (simplificação de `resolve_action_key`, spec `in-review`, smoke) e `d4db977a` (R6).

Ficaram fora: rodar de novo o `snapshot.py` e as mutações M0/M7/M9/M10. Reli a evidência do autor e o smoke. O portão de snapshot da 373 (`test_snapshot_off_existe_e_bate`) fica verde no HEAD.

## Verificação por ponto

1. **R1 (`services/tactical_profile.py:565-577`).** A chave gravada só cai quando três coisas valem juntas: ela está em `_NO_RETREAT_ACTIONS`, é igual ao valor cru da tabela (`actions.get(trigger, fallback)`) e a prioridade é `absoluta`. Fora disso, o `continue` mantém a chave explícita (D1). Idempotência: a primeira passada grava `fallback` ou `attack`, que nunca é fuga. Na segunda, `stored != key` ou `stored` não é fuga, então dá `continue`, e a função é pura sobre a tabela. O teste `test_absoluta_remontada_nao_mantem_fuga_da_tabela` afirma `normalize(normalize(p)) == normalize(p)` para `absoluta` e `flexivel`. `test_portao_salvo_antes_da_395_nao_foge` passa por `ensure_combat_sheet` duas vezes, com o `flee` reinjetado. O smoke faz `json.dumps/loads` entre as montagens. Não há writer novo: o perfil continua gravado por `ensure_combat_sheet`, como antes. O efeito colateral aceito da D1 (um `flee` explícito igual ao da tabela numa `absoluta` vira ataque) é exatamente o que o código faz. Um `surrender` explícito numa `absoluta` cujo gatilho a tabela leva a `flee` continua valendo, como a D1 manda.
2. **R2 (`tactical_profile.py:595-602`; `conflict_orchestrator.py:650`).** O orquestrador troca 1 linha por 1, com saldo 0. `explicit_action` continua definido e usado em `:694`, que separa `tactic flee` de `move afastar`. `resolve_action_key` só converte em `attack` quando não há `action_key`, a dica legada dá fuga/rendição e `decision["resistance"] == "absoluta"` (`pick_action` devolve `resistance`, `:396`). Na `flexivel`, a dica "foge" continua dando `move afastar` (2ª metade de `test_legado_absoluta_sem_arquetipo_nao_foge`). O smoke mostra o lacrador `flexivel` fugindo.
3. **Guarda do P2-7.** `chave_absoluta_esperada` vem da tabela, não de `normalize_runtime_profile` (D2), então é honesta. Arquétipo fora da tabela reprova em vez de aceitar tudo. O assert curado (R3) exige a chave de `sempre` só onde a tabela levaria a fuga. O adendo 13 registra que a M9 passa em `fca76cda` e reprova em `f7fdac05`. Isso continua valendo depois do R1, porque `flank` é diferente da chave da tabela e a remontagem não o toca. Aceito sem refazer.
4. **Snapshot / R6.** O `_ajustes.yaml` muda exatamente 3 linhas, só `arena`. `data/bestiary.json`, `docs/spec394/`, `arena.py`, `test_spec373_artefatos.py`, `test_bestiario_calibragem.py` e `evals/` ficam sem diff. O snapshot da 373 bate. O desvio no texto do odre (`=` no lugar de `:`, que quebraria o YAML sem aspas) está registrado na spec §9.
5. **Produto contra avaliador.** Os commits de produto mexem só em `tests/test_tactical_archetypes_runtime.py` (os 3 testes dele, em `9214cc90`, antes do avaliador), `services/`, `data/bestiario/mecanica/_ajustes.yaml`, `docs/spec400/` e na spec. Nenhum toca em `tests/test_spec373_montagem.py` nem em caminho de `evals/protected-paths.txt`.

Prova de vermelho: num worktree descartável em `9214cc90` (testes sem correção), os 3 testes novos falham (`3 FAILED`). O worktree foi removido.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| — | — | — | Nenhum P0/P1/P2. | — |
| N-1 | nota | `tests/test_tactical_archetypes_runtime.py:540` | O assert R3 usa o `trigger` cru. O produto aplica `_normalize_archetype` antes (`tactical_profile.py:565`). Hoje os gatilhos curados já vêm normalizados (o teste passa), mas um gatilho com caixa ou acento diferente escaparia da exigência em silêncio. | Opcional, do autor de eval: normalizar o gatilho no assert. |
| N-2 | nota | `specs/SPEC-400-tatica-absoluta-followups.md` §4 passo 2 / §9 | O plano dava o assert R3 ao executor, mas ele saiu no commit do autor de eval (`f7fdac05`). É mais estrito, não mais frouxo, mas o §9 não registra a troca. | Uma linha no §9 no pouso (coordenador). |

## Correções aplicadas

Nenhuma (não houve achado bloqueante).

## Pendências

Nenhuma obrigatória. N-1 é opcional e fica para o autor de eval numa próxima mudança da guarda.

## Comandos rodados

```text
git diff main...HEAD --stat → 8 arquivos, +210/-15
git diff --exit-code main...HEAD -- evals/ arena.py docs/spec394 data/bestiary.json tests/test_spec373_artefatos.py tests/test_bestiario_calibragem.py → limpo
bash scripts/dev/pt.sh (-n 2) test_tactical_archetypes_runtime test_conflito_tatica test_spec373_{acao_extra,artefatos,cartas,montagem} test_bestiario_calibragem test_enemy_decks test_size_budget → 142 passed
worktree descartável @9214cc90, pytest -k "remontada or salvo_antes or legado_absoluta" → 3 FAILED (vermelho confirmado; worktree removido)
ruff check (4 arquivos alterados) → All checks passed
dup_helpers.py --diff main...HEAD → nenhuma função nova com nome repetido
```
