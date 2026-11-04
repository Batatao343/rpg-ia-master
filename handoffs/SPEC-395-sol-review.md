# SPEC-395 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / Sol (`spec-reviewer`) · **Data:** 2026-11-04 · **Commit revisado:** `b422ef34`

## Escopo

Branch `spec/395` no worktree `rpg-spec-395`, `git diff main...HEAD`:
- `b27fbbcc`: testes primeiro.
- `cc3ec58b`: correção R1 em `services/tactical_profile.py`.
- `ee117fdd`: recalibração das 4 criaturas, medições `docs/spec395/*` e `RELATORIO.md`.
- `b422ef34`: commit do autor de eval, revisado a pedido do coordenador. Ele trouxe a seção `fichas` em `docs/bestiario/recalibracoes_posteriores.json` e mudou os portões da 373.

Ficaram fora a suíte completa (é do coordenador, no pouso) e o smoke §6 com API.

## Verificação por pergunta

1. **R1 (`tactical_profile.py:545-572`).** A correção está certa e é determinística. Ela não lê prosa, só `resistance == "absoluta"` e a tabela.
   - Conferi por sonda. Uma `absoluta` com `muito_ferido` dá `attack` em abissal, bruto, predador e tatico. Dá `control` no conjurador, `flank` no covarde e `support` no líder de matilha. Um `sozinho` com `absoluta` no covarde dá `flank` e deixa de render-se.
   - Um `action_key` explícito tem precedência, como pede a R1: `{"action_key": "flee", "resistance": "absoluta"}` continua `flee`.
   - O efeito fica restrito a `absoluta`: `flexivel` com abissal ainda dá `flee`, que é a D1.
   - A tabela não mudou (R2).
   - Saves antigos carregam: `ensure_combat_sheet` renormaliza (`conflict_orchestrator.py:132`). A ressalva está em P2-1.
2. **Outros caminhos de fuga.**
   - `enemy_declaration` (`conflict_orchestrator.py:646-705`) só foge por `action_key == "flee"`. A tática `flee` em `:1778` só vem daí. O `forced_attack` e o baralho não criam fuga (`:664`, `:672`).
   - O legado `move afastar` (`:702-705`) só é alcançado quando falta o `action_key`. Isso exige um arquétipo fora da tabela. O teste curado garante que todo arquétipo do bestiário está nela.
   - Resta um caminho só para atores sem arquétipo tabelado com dica "foge", e ele está fora do escopo declarado (P2-5).
3. **Testes.**
   - Recriei `b27fbbcc` num worktree descartável. Os 3 testes ficam vermelhos ali: `test_todo_bestiario_curado...`, `test_absoluta_nao_vira_fuga_pela_tabela` e `test_portao_ferido_nao_foge`. No HEAD ficam verdes.
   - O assert novo do bestiário curado é honesto. Ele percorre toda prioridade `absoluta` real e não afrouxa o assert anterior.
   - `test_portao_ferido_nao_foge` barra tanto a tática `flee` quanto o `move`, ou seja, também barra o legado.
4. **R3 e recalibração.**
   - Comparei os hashes. `fix-snapshot` dá 365 ids idênticos à base, e as 8 ausências são exatamente o conjunto A. `final-snapshot` dá 361 ids idênticos ao `fix`.
   - O diff de `bestiary.json` só toca as 4 criaturas de F, que também são as únicas recalibradas, mais as Cartas de `nova_arcadia`.
   - Os dials registrados no `_ajustes.yaml` estão dentro de ±7, e o maior é o `corpo -5` do sorvedouro. Houve 1 execução de `calibrar.py`.
   - Ressalva: o snapshot `on` só cobre 55 ids com baralho. O Portão só tem `off`. É uma limitação do `snapshot.py` da 394, não deste diff.
5. **`mon_odre_de_oleo`.** "Variância de amostra" não é aceitável como explicação (P2-2). A confirmação foi feita uma vez e sem reajuste, como a R7 pede.
6. **Caminhos protegidos.** `git diff main...HEAD` dá zero em `arena.py`, `calibrar.py`, `test_bestiario_calibragem.py` e `evals/`. Nenhum commit de produto toca linha de `evals/protected-paths.txt`. O registro protegido e os testes da 373 só mudam em `b422ef34`, que é do autor de eval.

## Commit `b422ef34` (seção `fichas`): desenho e mutação

O desenho é sólido nas guardas e afrouxa o R2 só para as 4 ids registradas.

`test_registro_de_posteriores_valido` reprova de verdade. Fiz cada mutação à mão num worktree descartável e restaurei com `git checkout`:

| Mutação em `fichas` | Resultado |
|---|---|
| M1 `mon_odre_de_oleo` → `mon_odre_x` (id inexistente) | registro **F** e snapshot R2 **F** (`:386`) |
| M2 id real não citada (`mon_abafador_de_candeias`) | registro **F** (não consta no relatório nem na spec) |
| M3 `mon_sorvedouro_do_codigo` (dial mudado) movida para `fichas` | registro **F** (`:390`, interseção com ids de dial mudado) |
| M4 `mon_lencol_de_chamine` removida de `fichas` | snapshot R2 **F** (hash `e5a8…` ≠ `3734…`), ou seja, a seção é necessária e o oráculo morde |
| M5 `spec` trocada para `SPEC-373` | registro **F** |
| M6 `motivo` vazio | registro **F** |

Onde afrouxa: `test_spec373_montagem.py:44` tira a id **inteira** do snapshot R2, não só o `action_key` da prioridade `absoluta`.
- Com `mon_odre_de_oleo` registrada, editei à mão `max_vitalidade` de 12 para 99. Os 43 testes de `test_spec373_artefatos`, `test_spec373_montagem` e `test_bestiario_calibragem` passaram.
- A mesma edição numa id não registrada reprova o R2.
- Esse HP grosseiro ainda é pego por `test_conflito_autoria_bestiario` (vitalidade × tabela de corpo) e por `test_spec349_mecanica`. Uma mudança sutil, como Carta, padrão ou outra prioridade do perfil, passaria.

Ver P2-3.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/tactical_profile.py:565`; `specs/SPEC-395-abissal-nao-foge.md:101,112` | A §7 diz que um ator já montado "mantém o `flee` até a próxima montagem". Na prática, a remontagem **também** mantém. `ensure_combat_sheet` grava o perfil normalizado em `actor["tactical_profile"]` (`conflict_orchestrator.py:132`), e na remontagem o `flee` já materializado conta como explícito (`:565`) e prevalece. Um save com o inimigo já montado foge pelo resto da vida daquele ator. O efeito é só de balanço, sem corromper o save. | Corrigir o texto da §7 e do critério de saves. Opcional, em spec futura: marcar a origem da chave (`action_key_source: "table"`) para a renormalização poder refazer, ou migrar na carga. |
| P2-2 | P2 | `docs/spec395/RELATORIO.md:37-38`; spec §9 | Chamar o odre de "variância de amostra" não se sustenta. Ele estava em 68/76 antes da correção, caiu para 56,5/53 nas sementes 0–39 e foi a 37,2/45,8 nas 40–119. Somando as 120 sementes, o `off` fica em ≈43,6 %, fora da faixa, e o `on` em ≈48,2 %. A queda de 19 pp entre as janelas passa de 4 erros-padrão com lutas independentes e fica em ≈2σ agrupando por semente. É um efeito real da correção: o odre perdeu ~12–23 pp e ficou na borda. | Registrar como exceção nominal de confirmação, com o número somado, e o motivo "a correção R1 tirou a fuga, margem pequena". Abrir follow-up de recalibração por dial (a R7 proíbe fazer nesta spec). A D2 da 394 pede o registro do dono. |
| P2-3 | P2 | `tests/test_spec373_montagem.py:44` (commit `b422ef34`) | `fichas` cega o R2 da id inteira, como a mutação M7 mostrou. O oráculo da 373 fica mais frouxo do que a R3 da 395, que pede que só o `action_key` da `absoluta` mude. | Em spec de eval: gravar em `fichas` o hash `off` esperado depois da correção e comparar com ele, sem pular a id. Outra opção é refazer o snapshot com o `action_key` das prioridades `absoluta` mascarado. |
| P2-4 | P2 | `data/bestiario/mecanica/_ajustes.yaml:633,779,890` | As leituras `arena:` de fervente (74/81), lençol (69/74) e odre (68/76) são de antes da correção. Hoje elas valem 58,5/68, 60/60 e 56,5/53. A próxima calibração vai ler número velho. | Atualizar só o campo `arena` dessas 3 entradas. Não mexe em dial, mas é preciso conferir que `ids_com_dial_mudado` ignora o campo. |
| P2-5 | P2 | `services/conflict_orchestrator.py:650,702-705` | Um ator sem arquétipo tabelado, com prioridade `absoluta` e dica "foge/recua", ainda recebe `legacy_action_key` igual a `flee` e passa ao `move afastar`. Hoje nenhum curado está nesse caso, porque o teste exige arquétipo tabelado. Falta conferir os gerados por `creature_gen` e `creature_variants`. | Está fora do escopo declarado (§2). Fica como follow-up: aplicar `_NO_RETREAT_ACTIONS` também ao legado quando a prioridade for `absoluta`. |
| P2-6 | P2 | `specs/SPEC-395-abissal-nao-foge.md:133-134` (commit `b422ef34`) | O autor de eval escreveu na spec de produto a citação das ids que a guarda dele exige. A guarda passa porque o próprio autor da guarda escreveu o texto, que deveria vir do executor. O conteúdo está correto e bate com a R3. | Aceitável desta vez. Daqui em diante, a citação deve vir do executor, no `RELATORIO.md`. |

Não há P0 nem P1.

Na qualidade:
- A função cresceu 3 linhas.
- `dup_helpers` não acusa nada.
- O `tactical_profile.py` tem 620 linhas.
- `test_size_budget` está verde.
- `validate_content`: 0 erros, 29 avisos já existentes.
- Nenhum structured output e nenhum valor vindo do LLM.

## Correções aplicadas

Nenhuma. O revisor não edita o produto.

## Pendências

- P2-1 e P2-4: texto e leituras, com o executor, antes do pouso ou num follow-up curto.
- P2-2: exceção nominal do odre, com o número somado, e spec de recalibração. Precisa do registro do dono (D2 da 394).
- P2-3 e P2-6: com o autor de eval, numa spec de eval própria (fixar o hash em `fichas`).
- P2-5: spec própria sobre o caminho legado com `absoluta`.

## Comandos rodados

```text
pt.sh test_tactical_archetypes_runtime test_conflito_tatica test_conflito_autoria_bestiario test_enemy_decks test_spec349_mecanica test_bestiario_calibragem → 643 passed
worktree @b27fbbcc: pytest -k "absoluta or portao or todo_bestiario_curado" → 3 failed (vermelho antes da correção)
pt.sh test_spec373_artefatos test_spec373_montagem (HEAD b422ef34) → 39 passed
mutações M1–M6 em fichas (worktree descartável) → todas reprovam; restauradas
M7 HP do odre 12→99 com fichas → 43 passed em 373+calibragem (afrouxamento); controle em id não registrada → R2 F
snapshot base×fix×final (python) → 365/361 idênticos; ausentes = A / A∪4 abissais
git diff --exit-code main...HEAD -- arena.py calibrar.py test_bestiario_calibragem.py evals/ → limpo
dup_helpers --diff main...HEAD → nada; validate_content → 0 erros
```

## Rodada 2 (2026-11-04, commit revisado `3532d6bc`)

**Veredito:** `APPROVED_WITH_FOLLOWUPS`. O P2-3 está fechado. Fica um resíduo menor, o P2-7.

Em `test_spec373_montagem.py`, a função `ficha_vs_base` deixou de pular as ids de `fichas`:
- devolve ao valor da base (`flee`) só o `action_key` das prioridades `absoluta`;
- exige o hash original de `docs/spec373/base/snapshot-off.json`;
- reprova quando não existe prioridade `absoluta`;
- reprova quando a `absoluta` ainda sai `flee` ou `surrender`.

Uma `absoluta` nova acrescentada à ficha também muda o hash e reprova. Não vi brecha nova: as demais ids seguem no hash estrito, e o `_doc` do registro foi atualizado.

Mutações num worktree descartável em `3532d6bc`, restauradas e removidas depois:

| Mutação | Resultado |
|---|---|
| M0 linha de base | 40 passed |
| M7 HP do odre 12→99 (em `fichas`) | **F** `mon_odre_de_oleo`. O afrouxamento da rodada 1 está fechado. |
| M8 prosa (`action_hint`) da prioridade `sempre` do odre | **F** |
| M10 correção R1 revertida no produto | **F** (a `absoluta` volta a `flee`) |
| M9 `action_key` da `absoluta` do odre forçado a `flank` (errado; o certo é `control`) | **passa** nos portões da 373 |

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-7 | P2 | `tests/test_spec373_montagem.py` (`ficha_vs_base`) | A função aceita qualquer chave que não seja fuga na `absoluta`. Ela não confere que a chave é a de `sempre` do arquétipo. `test_todo_bestiario_curado...` também só barra `flee` e `surrender`. Hoje o bestiário não tem `action_key` explícito, então a chave vem sempre da tabela e o risco é baixo. | Opcional, numa próxima mexida de eval: exigir `action_key == _ENEMY_ARCHETYPE_ACTIONS[arq].get("sempre", "attack")`, ou o valor de `tp.normalize_runtime_profile` sobre a ficha crua. |

```text
worktree @3532d6bc: pytest -n 2 test_spec373_montagem test_spec373_artefatos → M0 40 passed; M7/M8/M10 1 failed (odre); M9 40 passed
```
