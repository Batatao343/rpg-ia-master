# SPEC-175 — pré-registro do benchmark A/B

Registrado em 2026-09-30 antes de qualquer run A/B.

## Pergunta e unidade

O Project Index reduz o custo de descoberta em oito tarefas históricas
cross-file do Valoria sem reduzir a capacidade de localizar e propor a correção
adequada? A unidade pareada é `task × réplica`; são duas réplicas por condição,
16 observações A e 16 B.

## Condições

- **A:** Terra High, ferramentas normais (`rg`, leitura localizada), sem abrir
  `project_index/**`, sem usar seu CLI ou mapas derivados.
- **B:** Terra High, mesmo prompt, budget e ferramentas; deve consultar o CLI do
  Project Index antes da busca normal.
- Réplica 1: A em B01→B08; B em B08→B01.
- Réplica 2: A em B08→B01; B em B01→B08.
- Cada réplica usa sessão nova com `fork_turns=none`. Runs não editam arquivos,
  não executam testes e não veem resultados de outro run.
- Proibidos: `git log/show/blame`, docs históricos, specs, artifacts deste
  benchmark e qualquer busca por patch/commit anterior.

## Tarefas fornecidas aos agentes

1. **B01 — morte falsa:** após `player_downed`, sem evento terminal, o
   arquivista aceita “Ari morreu” como fato canônico. Localize a causa e indique
   a regressão mínima.
2. **B02 — alias de NPC:** falar com o mesmo NPC por aliases diferentes cria
   identidade/memória separada e a recuperação canônica falha. Localize a causa
   e indique a regressão mínima.
3. **B03 — reward/outcome:** a narração afirma ouro/XP que não existe no recibo
   canônico do turno. Localize a fronteira correta de validação/finalização.
4. **B04 — lifecycle:** protagonista inconsciente ou com `death_pending`
   ainda consegue atacar/viajar. Localize o gate e a regra canônica.
5. **B05 — structured output:** provider devolve JSON válido no conteúdo raw,
   sem tool call, e o sistema cai em fallback mesmo sendo recuperável. Localize
   o caminho de recuperação e o teste.
6. **B06 — persistência de arte:** `art_generation_ledger` e
   `art_arc_budgets` somem após save/load. Localize schema, escrita, leitura e
   regressão round-trip.
7. **B07 — replay idempotente:** repetir uma operação concluída pode executar a
   mutação de novo ou aceitar o mesmo ID com payload diferente. Localize os
   contratos local/Postgres e os testes de replay.
8. **B08 — logout mobile:** o controle de logout fica duplicado/sobreposto aos
   controles da HUD em viewport estreita. Localize renderização, estilo e teste
   responsivo.

## Saída e métricas

Para cada tarefa, o agente retorna JSON com no máximo cinco `files`, três
`tests`, um `resolution`, `discovery_calls`, `source_bytes_read` e
`wall_seconds`. `files` deve estar na ordem em que foram localizados; o agente
conta apenas chamadas e bytes anteriores à resposta da tarefa.

- `resolved`: arquivos incluem ao menos um core file e o plano contém os dois
  sinais funcionais comprometidos no ground truth;
- `localization_hit_before_edit`: um core file aparece entre os três primeiros;
- `irrelevant_files_touched`: arquivos propostos fora de core files e arquivos
  auxiliares permitidos;
- `relevant_tests_selected`: recall sobre o conjunto de testes comprometido;
- `discovery_calls`, `source_bytes_read`, `wall_seconds`: valores informados no
  protocolo; tempo é observacional.

O score de `resolved` será aplicado ao texto sem reabrir o repositório e antes
da conclusão: exige um core file e os dois sinais funcionais do ground truth.
A revisão Sol audita cada decisão. Para agregação, usa-se a média das duas
réplicas por tarefa e a mediana das 16 observações por condição. Uma tarefa tem
`cost_win` se B reduz calls ou bytes e a outra dimensão não piora mais de 10%.
O requisito de redução global de 20% vale para pelo menos uma das duas medianas,
também sem piora maior que 10% na outra.

O ground truth foi serializado em JSON canônico antes dos runs. Compromisso:
`sha256:d9a8ce2b087d7eb59ace5677b6cede18868e28d121a78b9ac5f20adcda957e39`.
O conteúdo só será publicado depois de todas as quatro sessões Terra fecharem.

## Decisão pré-registrada

- **Obrigatório:** B não reduz `resolved` nem `localization_hit_before_edit`, não
  aumenta arquivos irrelevantes, e reduz em pelo menos 20% a mediana pareada de
  `discovery_calls` ou `source_bytes_read`, com melhora em pelo menos 6/8
  tarefas únicas.
- **Seletivo:** B não reduz `resolved`, melhora custo em pelo menos 4/8 tarefas,
  mas não alcança todos os critérios de obrigatório ou o ganho se concentra em
  tarefas cross-file.
- **Remover do fluxo:** B reduz `resolved`, ou melhora custo em menos de 4/8
  tarefas sem ganho de localização que justifique a complexidade.

Wall time não decide sozinho. Empate exato em custo conta como empate. Nenhum
threshold será alterado depois dos resultados.
