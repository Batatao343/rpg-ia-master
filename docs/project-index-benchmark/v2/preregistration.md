# SPEC-175 — pré-registro v2 auditável

Registrado antes de qualquer sessão v2. A rodada v1 e sua revisão bloqueada não
entram nos cálculos v2.

## Desenho

- Duas réplicas Terra High por condição, sessões novas: A1/B2 em B01→B08 e
  A2/B1 em B08→B01.
- Prompt-base idêntico e versionado em `base-prompt.txt`; somente o bloco de
  condição, ID de sessão e ordem diferem.
- Budget idêntico: 12 discovery calls, 50.000 source bytes e 120 segundos por
  tarefa. O harness deriva todas as medidas; contadores informados pelo agente
  são ignorados.
- Toda descoberta usa exclusivamente `scripts/project_index_ab_harness.py`.
  O wrapper impede Project Index em A, exige consulta ao índice antes da fonte
  em B e bloqueia Git, docs, specs, AGENTS, ESTADO, artifacts e ground truth.
- O trace guarda operação, parâmetros, path, bytes, sequência e timestamp. A
  sessão guarda model, effort, budget, prompt hashes, árvore, índice e ordem.
- Nenhum run edita produto ou executa testes.

## Tarefas

B01 morte falsa após `player_downed`; B02 aliases/identidade de NPC; B03 reward
versus receipt canônico; B04 ação em inconsciência/`death_pending`; B05 JSON raw
structured recuperável; B06 persistência dos dois campos de arte; B07 replay
idempotente/payload divergente; B08 logout mobile duplicado/sobreposto.

## Métricas

- `resolved`: pelo menos um core file e os dois sinais funcionais comprometidos;
- `localization_hit_before_edit`: core file entre os três primeiros;
- arquivos irrelevantes fora dos core files (test paths não contam);
- recall dos tests após remover `::test_name`;
- calls, source bytes e wall time derivados do trace.

Usa-se média das duas réplicas por tarefa e mediana das 16 observações por
condição. Uma tarefa tem `cost_win` se B reduz calls ou bytes sem piorar a outra
dimensão mais de 10%. Redução global exige pelo menos 20% em uma mediana, sem
piora acima de 10% na outra.

## Decisão congelada

- **Obrigatório:** B não reduz resolved/localization, não aumenta irrelevantes,
  reduz uma mediana em pelo menos 20% e vence custo em 6/8 tarefas.
- **Seletivo:** B não reduz resolved e vence custo em pelo menos 4/8 tarefas,
  sem cumprir todo o critério obrigatório.
- **Remover do fluxo padrão:** B reduz resolved, ou vence menos de 4/8 tarefas
  sem ganho de localização suficiente para justificar a complexidade.

Wall time é observacional. O ground truth factual v2 foi revisado antes do selo
e permanece oculto durante os runs. JSON canônico comprometido:
`sha256:fc7facdf29e1eeaed440f97b4649d66ccfde181e36900f3bfb1a55204a054330`.
O arquivo de compromisso não será regravado no reveal.
