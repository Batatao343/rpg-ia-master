# SPEC-175 — pré-registro v3 auditável

Registrado antes de qualquer sessão v3. V1 foi bloqueada pela revisão Sol; as
duas tentativas v2, preservadas em `../v2/aborted/`, não produziram quatro runs
completos e ficam integralmente fora dos cálculos. O ground truth factual e os
thresholds permanecem idênticos ao compromisso v2.

## Desenho

- Duas réplicas Terra High por condição, em agentes novos sem histórico: A1/B2
  em B01→B08 e A2/B1 em B08→B01.
- O prompt exato de cada sessão está congelado em `session-prompts/`; seu hash
  integra a attestation e o arquivo de sessão.
- Budget simétrico: 12 discovery calls, 50.000 source bytes e 300 segundos por
  tarefa. O limite de tempo foi elevado antes dos runs porque a tentativa v2
  mostrou que 120 segundos incluíam latência do agente/CLI e interrompiam uma
  tarefa antes do resultado. Wall time continua apenas observacional.
- Toda descoberta usa `scripts/project_index_ab_harness.py`. A pode usar
  search/read em arquivos ou diretórios permitidos; B deve consultar o índice
  primeiro e confirmar no source. Git, docs, specs, instruções, benchmark e
  ground truth são bloqueados.
- O harness deriva calls, bytes e wall time do trace. Nenhum contador declarado
  pelo agente entra no resultado. Nenhum run edita produto ou executa testes.

## Tarefas e métricas

B01 morte falsa após `player_downed`; B02 aliases/identidade de NPC; B03 reward
versus receipt canônico; B04 ação em inconsciência/`death_pending`; B05 JSON raw
structured recuperável; B06 persistência dos dois campos de arte; B07 replay
idempotente/payload divergente; B08 logout mobile duplicado/sobreposto.

- `resolved`: pelo menos um core file e os dois sinais funcionais comprometidos;
- `localization_hit_before_edit`: core file entre os três primeiros;
- arquivos irrelevantes fora dos core files, sem contar tests;
- recall dos tests após remover `::test_name`;
- calls, source bytes e wall time derivados do trace.

Usa-se média das réplicas por tarefa e mediana das 16 observações por condição.
Uma tarefa tem `cost_win` se B reduz calls ou bytes sem piorar a outra dimensão
mais de 10%. Redução global exige pelo menos 20% em uma mediana, sem piora acima
de 10% na outra.

## Decisão congelada

- **Obrigatório:** B não reduz resolved/localization, não aumenta irrelevantes,
  reduz uma mediana em pelo menos 20% e vence custo em 6/8 tarefas.
- **Seletivo:** B não reduz resolved e vence custo em pelo menos 4/8 tarefas,
  sem cumprir todo o critério obrigatório.
- **Remover do fluxo padrão:** B reduz resolved, ou vence menos de 4/8 tarefas
  sem ganho de localização suficiente para justificar a complexidade.

O ground truth permanece oculto e comprometido pelo mesmo JSON canônico factual
revisado após o bloqueio v1:
`sha256:fc7facdf29e1eeaed440f97b4649d66ccfde181e36900f3bfb1a55204a054330`.
O compromisso não será regravado no reveal.
