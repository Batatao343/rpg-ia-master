# SPEC-394 — Bestiário: recalibrar as 7 criaturas que derivaram depois da SPEC-387

> **Status:** `draft`
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Épico:** SPEC-349 (bestiário) · SPEC-327 (Cartas)
> **Depende de:** SPEC-373 pousada (`approved`, em voo no worktree `rpg-spec-373`: o R9 dela muda o `on` destas criaturas e ela congela `arena.py`), SPEC-349 `done` (esteira, `calibrar.py`, `_ajustes.yaml`), SPEC-387 `done` (mudanças de motor que causaram a deriva)
> **Desbloqueia:** portão do veredito cheio voltar para perto dos 247 da 349; `RPG_ENEMY_DECKS=on` sem estas exceções
> **Risco:** `médio`. Só mexe nos números de 7 criaturas, pelos dials que já existem. Avaliador congelado, motor intocado. Sobe para `alto` se a Etapa 0 achar causa no motor (D3).
> **Evidência:** `tests/test_bestiario_calibragem.py` (novo) falha antes: os 7 ids estão sem `ok` na medição da Etapa 0. Equivalência: os hashes de `ensure_combat_sheet` (`off` e `on`) das outras 274 criaturas ficam iguais.
> **EXECUTOR_MODEL:** `Terra` (Sonnet) · **REVIEW_MODEL:** revisor Sonnet, outro agente (`Sol`/`spec-reviewer` se D3 acionar) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`. O oráculo é o `veredito` do `scripts/bestiario/arena.py` (faixa 45–85 %, `arena.py:43`, `:62-76`), que segue congelado. Os limiares do portão estão fixados nesta spec, não pelo executor. O teste só lê o `ok` que o `arena.py` gravou e compara hashes.

## 1. Contexto & Objetivo

A base da `main` `9468d058` passa **241 de 281** criaturas no veredito cheio. A 349 tinha registrado 247 (`SPEC-349:672`). Sete criaturas que tinham `ok` na 349 perderam o `ok` (`rpg-spec-373/handoffs/SPEC-373-eval-authoring.md:62-67`, tabela `:104-114`). O dono decidiu em 04/11 tirar essa deriva da 373 e tratá-la numa spec própria (`rpg-spec-373/specs/SPEC-373-bestiario-chefes-familia.md:132`). Os números estão na tabela abaixo: vitória do herói em L3, `off`/`on`, sementes 0–39.

| criatura | região | cat. | 349 (`_ajustes.yaml`) | base `9468d058` | ramo 373 (parcial) | dials hoje |
|---|---|---|---|---|---|---|
| `mon_anzolado_da_casa` | brekmar | padrao | 72,5 / 83,0 | 72,5 / **86,0** | 72 / **91** | c2 d1 f1 s0 (`_ajustes.yaml:174-179`) |
| `mon_lacrador_de_saidas` | deserto_zhur | padrao | 56,0 / 81,5 | 64,5 / **89,0** | 64 / 80 ok | c2 d2 f1 s0 (`:696-701`) |
| `mon_bracos_de_tenaz` | montanhas_afiadas | elite | 59,5 / 72,0 | 59,5 / **87,0** | 60 / 72 ok | c1 d1 s2 (`:258-262`) |
| `mon_armador_de_fosso` | montanhas_afiadas | lacaio | 78,5 / 78,5 | 78,5 / **96,5** | 78 / **96** | c1 d0 s0 (`:192-196`) |
| `mon_portao_que_morde` | nova_arcadia | elite | 61,0 / 63,0 | **91,0 / 93,5** | **91 / 90** | c−2 d−1 (`:948-951`) |
| `mon_carregador_de_ganchos` | pradaria_ruinas | elite | 54,5 / 82,0 | 54,5 / **86,0** | 55 / 70 ok | c5 d5 f4 **s7 (teto)** (`:330-335`) |
| `mon_escuta_do_sinal` | skallgard | lacaio | 46,5 / 83,0 | 46,5 / **89,5** | 46 / **90** | c1 d1 s2 (`:566-570`) |

Fontes da tabela: base em `rpg-spec-373/docs/spec373/base/eval/arena-<r>.md`. Ramo 373 em `rpg-spec-373/docs/spec373/arena-<r>.md` (brekmar:18, deserto_zhur:29, montanhas_afiadas:23/25, nova_arcadia:24, pradaria_ruinas:18, skallgard:19). A 373 ainda não terminou, então esses números podem mudar. Ela não mexe nos dials destas 7 (`rpg-spec-373/data/bestiario/mecanica/_ajustes.yaml:178,196,264,336,580,710,967`, iguais aos da `main`), e nenhuma delas está em `recalibradas.json`.

**Causa provável (não confirmada).** Os commits de motor da 387 vieram depois da 349: `1e208ac9` ("atacante derrubado pela Reação não resolve o ataque", `SPEC-387:609-612`), `03d457dc` e `3f0be849`. A própria 387 registra que "**a arena não foi rodada**" (`SPEC-387:612`). Cinco das sete mudaram só no `on`. Já `portao_que_morde` (+30 pp no `off`) e `lacrador_de_saidas` (+8,5 pp no `off`) apontam para uma segunda causa (`SPEC-373-eval-authoring.md:118-124`).

**Objetivo.** Devolver à faixa do `arena.py`, pelos dials do `calibrar.py`, toda criatura destas 7 que siga fora depois da 373, sem mudar nenhuma outra criatura.

## 2. Requisitos

- **R1 — Avaliador congelado.** Ficam byte-idênticos à `main`: `scripts/bestiario/arena.py`, `scripts/bestiario/calibrar.py`, `docs/spec349/arena-slots-baseline.json`, `docs/spec373/base/eval/`, `tests/test_spec373_artefatos.py` e o restante de `evals/protected-paths.txt`. Prova: `git diff --exit-code main -- <caminhos>`.
- **R2 — Base pós-373 (Etapa 0).** Medir os 7 ids com `arena.py --ids <7> --seeds 40 --modo off,on` na `main` já com a 373 pousada. Saída em `docs/spec394/base.json`/`.md`. O escopo de R4 é o conjunto `F` dos ids sem `ok` nessa medição. Se `F` ficar vazio, a spec fecha só com R2 e R7.
- **R3 — Diagnóstico do `off` do portão e do lacrador.** Antes de recalibrar, `docs/spec394/RELATORIO.md` precisa dizer de onde veio o salto do `off`:
  - diff da ficha, da mecânica e do bestiário gerado entre o commit da 349 e a `main`;
  - um braço com o `if not _can_act(actor): return` da 387 revertido por monkeypatch, só dentro do processo de diagnóstico.

  Isso é diagnóstico, não critério. Se a causa for um **bug** de motor, vale o D3.
- **R4 — Recalibração só pelos dials.** Usar `calibrar.py --regioes <regiões de F> --ids <F> --seeds 40 --rodadas 6`, no máximo 2 execuções. Valem só `corpo`, `dano`, `forca` e `sig`, em ±7, porque as 7 são `nova`. Cada passo fica registrado em `_ajustes.yaml` com a leitura da arena. O bestiário é regenerado por `gerar_mecanica.py`. Nenhuma edição à mão em `data/bestiary.json`, em ficha ou em Carta.
- **R5 — Meta.** Cada id de `F` sai com `ok` no `arena.py`: as duas células L3 (`off` e `on`) em 45–85 %, sementes 0–39, em `docs/spec394/arena-final.json`. Se um id não entrar na faixa depois das 2 execuções, ele fica com o melhor ajuste visto e vai para a §9 com a leitura (D2). A meta continua cumprida para os demais ids de `F`.
- **R6 — Sem regressão nas outras 274.** Hash de `ensure_combat_sheet` com `off` e baralho montado com `on` (sementes 0–11, como `rpg-spec-373/docs/spec373/snapshot_base.py`) de todas as entradas fora de `F`: idênticos antes e depois. Consequência: o veredito cheio fica em `N_373 + |ids de F que passaram|`, sem precisar rodar a arena inteira de novo.
- **R7 — Confirmação.** Uma única rodada, depois do commit final: `arena.py --ids <F> --seed-inicio 40 --seeds 80 --modo off,on --json docs/spec394/confirmacao-40-119.json`. O resultado vai para a §9 sem novo ajuste. É proibido ajustar até a confirmação passar.

### Fora de escopo

- Mudança de motor (`services/conflict_orchestrator.py`, `services/enemy_decks.py`, `cards/*`) e reversão de commit da 387 em produto.
- Cartas novas ou editadas, `cartas_autorais`, `tactical_profile`, texto de ficha ou do Codex.
- As outras 34 criaturas fora do veredito, os chefes (são da 373) e as Posturas (`arena_spec355.py` não usa ids do bestiário).
- Tocar em faixa, delta, sementes ou qualquer avaliador.

## 3. Design técnico

- **Novo:** `docs/spec394/snapshot.py`, cópia enxuta do `snapshot_base.py` da 373, com `--out` e `--excluir`. Gera `docs/spec394/{base,final}-snapshot.json`.
- **Novo:** `docs/spec394/{base,arena-final,confirmacao-40-119}.{json,md}` e `RELATORIO.md`.
- **Novo:** `tests/test_bestiario_calibragem.py` (docstring "SPEC-394"):
  - `test_derivadas_387_com_ok_na_arena` lê `arena-final.json` e asserta `ok` em todo id de `F`, menos as exceções nominais da §9, que precisam constar em `RELATORIO.md`. O teste falha se o artefato não existir; não pula.
  - `test_base_394_tinha_derivadas_fora` asserta que `base.json` tem ≥ 1 id sem `ok`. Isso prova que o portão discrimina.
  - `test_snapshot_fora_de_F_identico` compara os dois snapshots.
  - `test_ajustes_registrados` asserta que todo id de `F` com dial mudado tem `arena` em `_ajustes.yaml` e dials em ±7.
- **Alterado:** `data/bestiario/mecanica/_ajustes.yaml`, só nas entradas de `F`. Também `data/bestiario/mecanica/<regiao>.yaml`, `data/bestiary.json` e o que `gerar_mecanica.gerar` regenera, com diff restrito a `F` (garantido pelo R6).

## 4. Plano passo a passo

### Etapa 0 — base e diagnóstico (nenhum arquivo de produto muda)

1. `snapshot.py --out docs/spec394/base-snapshot.json`.
2. R2: arena dos 7 ids, uma região por vez, em background.
3. R3: diff de dados e braço de diagnóstico. A conclusão vai para `RELATORIO.md`.

### Etapa 1 — testes primeiro

1. Escrever `tests/test_bestiario_calibragem.py` e commitá-lo sozinho. Esperado: `test_base_394_tinha_derivadas_fora` verde; os outros três vermelhos com "artefato ausente".
2. O revisor confere se os limiares do teste batem com o texto de R5/R6.

### Etapa 2 — recalibração

1. R4, com `calibrar.py` sobre `F`. Depois, `snapshot.py --out docs/spec394/final-snapshot.json --excluir <F>`.
2. `arena.py --ids <F> --seeds 40` → `arena-final.json`.
3. Verificação: `bash scripts/dev/pt.sh tests/test_bestiario_calibragem.py tests/test_spec349_mecanica.py tests/test_enemy_decks.py` (`-n 2`) e `validate_content.py` verdes.

### Etapa 3 — confirmação e relatório

R7, uma vez. A §9 recebe a tabela antes/depois, os dials, a confirmação e as exceções.

## 5. Critérios de aceite

- [ ] R1: `git diff --exit-code main --` nos caminhos do avaliador
- [ ] R2/R3: `base.json` e `RELATORIO.md` com a causa do salto do `off` (ou "não achada" com os braços testados)
- [ ] R5: os 4 testes de `tests/test_bestiario_calibragem.py` verdes; exceções nominais na §9
- [ ] R6: snapshot das 274 idêntico em `off` e `on`
- [ ] R7: `confirmacao-40-119.json` gravado, com resultado na §9 sem reajuste
- [ ] `uv run pytest` verde (suíte completa, no pouso, pelo coordenador)
- [ ] Saves antigos carregam (só números de ficha; baralho já montado não remonta, regra da 373 R10)

## 6. Smoke test

Sem LLM: rodadas de Cartas não chamam IA (`combat-cartas-sem-ia`) e a arena é determinística, então a confirmação R7 é o smoke de balanço. Smoke de integração, local e com MockLLM:
1. `uv run uvicorn api:app`.
2. `/game/new` em Nova Arcádia com `RPG_ENEMY_DECKS=on`.
3. Forçar um encontro com `mon_portao_que_morde` (ou o 1º id de `F`) e jogar até o fim. A ficha carregada precisa ter a Vitalidade e o dano do `bestiary.json` novo, e o combate precisa fechar sem erro.

## 7. Riscos & compatibilidade

- **`escuta_do_sinal`:** o `off` está a 1,5 pp do piso e o `on` 4,5 pp acima do teto. Os dials mexem nos dois modos, então talvez não exista ajuste que coloque as duas células na faixa (D2).
- **`carregador_de_ganchos`:** já está com `sig` no teto 7. Se a 373 não o resolver, sobram só `corpo`, `dano` e `forca`.
- **Saves:** a ficha montada guarda os números antigos até remontar. Isso é aceitável porque o efeito é só de balanço.
- **Quota e latência:** nenhuma. A arena leva cerca de 2–3 min por região com 7 ids.

## 8. Decisões abertas (default entre parênteses)

- **D1 — Escopo.** (**`F` = só quem segue fora depois da 373**.) Alternativa: recalibrar os 7 de qualquer jeito, mesmo os que a 373 já devolveu à faixa.
- **D2 — Criatura sem ajuste viável.** (**Melhor ajuste visto + exceção nominal na §9**, como a 349.) Alternativa: abrir uma spec de Carta ou mecânica para ela.
- **D3 — Bug de motor no R3.** (**Parar, registrar e abrir spec própria com Risco `alto`**. Esta spec só recalibra o resto.) Alternativa: corrigir aqui e subir o Risco.
- **D4 — Risco.** (**`médio`, revisor Sonnet**.) Alternativa: `alto` com `spec-reviewer` Opus, por ser combate.
- **D5 — Sementes.** (**Ajuste em 0–39, confirmação em 40–119 uma vez**, como a 373 R3.)

## 9. Resultado

(preenchido pelo executor)
