# SPEC-175 — revisão independente Sol

```yaml
spec_id: SPEC-175
review_model: gpt-5.6-sol
review_run_id: SPEC-175-SOL-20260930-01
review_status: BLOCKED
threshold_decision: remover
```

## Decisão

**BLOCKED.** Aplicando literalmente os thresholds pré-registrados aos artefatos
publicados, a decisão única é **remover do fluxo obrigatório/contexto padrão**.
Isso não significa apagar `project_index/**`: significa não exigir nem injetar o
índice por padrão em tarefas de coding agent. O código pode permanecer disponível
para consultas seletivas, manutenção e um benchmark futuro corrigido.

A decisão numérica não pode ser promovida a conclusão aprovada da SPEC-175 com a
evidência atual. Os arquivos de run não permitem verificar os controles centrais
do A/B, e o ground truth comprometido inclui conjuntos de testes factualmente
inadequados para algumas tarefas. Por isso a revisão permanece bloqueada, apesar
de a regra de decisão apontar inequivocamente para `remover` se os runs forem
aceitos como verdadeiros.

## Integridade e execução

- O SHA-256 do JSON canônico (UTF-8, `JSON.stringify`, sem whitespace) é
  `d9a8ce2b087d7eb59ace5677b6cede18868e28d121a78b9ac5f20adcda957e39` e
  coincide com o compromisso e com a pré-registração. O hash dos bytes do
  arquivo é diferente (`b5678226...`) apenas porque `ground-truth.json` termina
  com newline; sua forma canônica tem 2.261 bytes e o arquivo tem 2.262.
- A ordem publicada está correta e contrabalançada: A1 B01→B08, B1 B08→B01,
  A2 B08→B01, B2 B01→B08. Cada run contém as oito tarefas exatamente uma
  vez; não há observação ausente nem exclusão pós-hoc visível.
- Os mtimes locais são coerentes com pré-registro → quatro runs → reveal →
  summary. Isso não é uma prova imutável: todos esses arquivos estão untracked,
  o compromisso foi regravado depois dos runs para marcar `revealed: true`, e
  timestamps locais podem ser alterados. O hash escrito no pré-registro é o
  único vínculo preservado, sem commit/attestation anterior aos runs.
- `a1.json`, `a2.json`, `b1.json` e `b2.json` guardam somente respostas finais.
  Não registram model ID, effort, token budget, session/run ID, prompt ou hash do
  prompt, source-tree SHA, project-index SHA nem trace de ferramentas. Assim não
  é possível confirmar `Terra High`, `fork_turns=none`, sessões novas, igualdade
  de prompt/budget, proibição de Git/docs/specs/benchmark, A sem índice, ou B com
  a consulta obrigatória ao CLI antes da busca normal.
- `discovery_calls`, `source_bytes_read` e `wall_seconds` são autodeclarados pelo
  agente. Sem trace dos comandos/reads e timestamps do harness, não são
  auditáveis. Isso afeta exatamente as duas dimensões que determinam a decisão.
- Existe risco de contaminação por contexto do repositório: `AGENTS.md` manda ler
  `ESTADO_ATUAL.md` ao retomar, e esse documento descreve correções históricas.
  A proibição do benchmark poderia prevalecer no prompt dos runs, mas, sem trace
  ou manifesto do prompt, não há como provar que prevaleceu. As tarefas também
  foram escolhidas retrospectivamente entre bugs já corrigidos; isso limita a
  generalização a trabalho novo, embora não favoreça a conclusão observada.

## Auditoria factual do ground truth

Os `core_files` e os dois sinais funcionais são, em geral, sustentados pelo
source atual. Exemplos auditados: morte terminal versus alegação qualificada,
coalescência transitiva de aliases, deltas do recibo, fases de lifecycle,
recuperação de JSON raw com validação Pydantic, round-trip dos dois campos de
arte, binding por request hash/replay antes de mutação e logout único sem
overlap no F16.

O conjunto comprometido de `test_files`, porém, não é factual em pontos que
alteram a métrica `relevant_tests_selected`:

- **B04:** `tests/test_death_flow.py` cobre a borda de `death_pending`, mas
  `tests/test_conflict_summary_lifecycle.py` trata principalmente ciclo de
  resumo/archivista. As regressões diretas do gate de ação estão em
  `tests/test_pre_matrix_contracts.py` e `tests/test_matriz_a_contratos.py`.
- **B05:** a regressão exata de JSON em `raw.content` sem nova request é
  `tests/test_routing.py::test_structured_recupera_json_raw_sem_nova_request`.
  `tests/test_routing_tiers.py` só testa escolha de tiers, e
  `tests/test_contracts_llm.py` testa contratos gerais/reais de structured
  output. O teste mais direto foi excluído do ground truth.
- **B07:** `tests/test_operation_replay_boundaries.py` cobre o receipt Postgres.
  `tests/test_hardening_persistencia_sse.py` cobre dedupe local legado por
  `processed_action_ids`, não a simetria do contrato de receipt entre
  `InProcessTurnCoordinator` e Postgres. No source atual, o coordenador local
  nem expõe `receipt()` e seu `claim()` compara principal/hash, mas não
  `game_id`/`kind` na repetição.
- **B08:** `web/e2e/critical-journeys.spec.ts` F16 é a regressão correta de
  acessibilidade/overlap em 320/390/768/1440 px.
  `tests/test_frontend_visual_contracts.py` cobre somente enquadramento de
  retratos e não deveria compor o denominador dessa tarefa.

Esses erros não mudam a contagem de `cost_win`, mas invalidam a alegação de
recall de testes e mostram que o ground truth não passou por validação factual
independente antes do compromisso.

## `resolved` por observação

Regra aplicada literalmente: pelo menos um `core_file` comprometido e a frase
`resolution` cobrindo semanticamente **ambos** os `resolution_signals`. Arquivos
de teste selecionados não completam uma frase omissa.

| task | A1 | A2 | B1 | B2 |
| --- | --- | --- | --- | --- |
| B01 | FAIL | FAIL | FAIL | FAIL |
| B02 | PASS | FAIL | FAIL | FAIL |
| B03 | FAIL | FAIL | FAIL | FAIL |
| B04 | FAIL | FAIL | FAIL | FAIL |
| B05 | PASS | PASS | PASS | PASS |
| B06 | PASS | PASS | PASS | PASS |
| B07 | FAIL | FAIL | FAIL | PASS |
| B08 | PASS | FAIL | FAIL | PASS |

Totais: **A = 6/16 (0,375)**; **B = 6/16 (0,375)**. B não reduz
`resolved`.

Justificativas somente para os fails:

- **B01/A1:** nenhum `core_file` de B01 foi listado; além disso, a frase omite
  que morte negada ou qualificada deve continuar válida.
- **B01/A2, B1 e B2:** localizam a exigência de evento terminal, mas omitem o
  segundo sinal sobre alegação negada/qualificada.
- **B02/A2, B1 e B2:** cobrem a chave canônica entre aliases, mas não afirmam a
  coalescência **transitiva** de grupos. A2 escolhe um teste com esse nome, mas
  o critério pré-registrado exige que a frase `resolution` cubra o sinal.
- **B03/A1, A2, B1 e B2:** cobrem validação da alegação contra delta canônico,
  mas não dizem que o receipt é derivado **depois das mutações do grafo**.
- **B04/A1, A2, B1 e B2:** cobrem elegibilidade por fase e `death_pending`, mas
  não registram que a fase terminal também bloqueia ações ordinárias.
- **B07/A1:** cobre hash e pede regressão de replay, mas diz que Postgres rejeita
  operação concluída e não descreve recuperar o receipt antes de uma segunda
  mutação.
- **B07/A2 e B1:** diagnosticam explicitamente a falta de receipt/replay local;
  portanto não cobrem o contrato resolvido de replay sem segunda mutação.
- **B08/A2:** cobre não sobreposição, mas não estabelece que existe um único
  controle acessível por layout ativo.
- **B08/B1:** identifica a duplicação e o overlap atuais, mas não propõe a
  remoção/condicionamento do controle duplicado para chegar aos dois sinais.

## Recálculo mecânico e threshold

O recálculo independente a partir dos quatro JSONs reproduz o summary Luna sem
divergência:

| métrica | A | B |
| --- | ---: | ---: |
| observações | 16 | 16 |
| resolved | 6/16 | 6/16 |
| localization hit | 15/16 | 16/16 |
| arquivos irrelevantes | 11 | 10 |
| recall médio de testes (ground truth publicado) | 0,40625 | 0,375 |
| mediana discovery calls | 3 | 4 |
| mediana source bytes | 9.054,5 | 17.027 |
| mediana wall seconds | 2,8 | 10,3 |

As médias por tarefa e a regra de no-máximo +10% na outra dimensão produzem
**0/8 `cost_win`**. Calls pioram 33,33%; bytes pioram 88,05%. Logo:

1. `obrigatório` falha: não há redução global de 20% nem 6/8 wins;
2. `seletivo` falha: há somente 0/8 wins, abaixo de 4/8;
3. `remover` aplica-se: menos de 4/8 wins. O ganho de um hit de localização
   em 16 observações, acompanhado de 0/8 wins e piora grande nas duas medidas
   de custo, não justifica a complexidade no contexto padrão.

Não houve cherry-picking observável **entre os runs publicados**: todas as 32
observações aparecem e o summary inclui todas. A seleção retrospectiva das oito
tarefas, a ausência de trace e a régua de testes incorreta impedem afirmar
ausência de cherry-picking anterior à publicação.

## Reparo mínimo para desbloquear

1. Criar uma pré-registração v2, sem editar os artefatos v1, com ground truth
   factual revisado antes de qualquer novo run. Corrigir ao menos os test sets
   de B04/B05/B07/B08 e manter os dois sinais funcionais explícitos.
2. Comprometer pré-registro, ground truth selado, source-tree SHA e
   project-index SHA em um commit/attestation anterior aos runs. O reveal deve
   criar outro artefato; não deve regravar o compromisso original.
3. Fazer o harness gravar automaticamente, por run: model ID, effort, budget,
   session ID, prompt hash/texto, condição, ordem, timestamps e trace de cada
   chamada/read com caminho e bytes. Derivar calls/bytes/wall do trace, sem
   aceitar contadores autodeclarados.
4. Isolar A de `project_index/**` por permissão real e isolar ambas de
   ground truth, docs históricos, specs e artefatos do benchmark. Registrar uma
   sessão nova verificável por réplica. O prompt-base e budget devem ter hash
   idêntico, salvo o bloco de condição previamente declarado.
5. Reexecutar as quatro sessões completas e recalcular o summary a partir dos
   traces. Não reaproveitar observações v1 nem mudar os thresholds em função
   destes resultados.

Até esse reparo, a SPEC-175 não satisfaz `order/session contamination
controlados`, simetria verificável de prompt/budget nem revisão Sol aprovada.
