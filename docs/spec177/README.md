# SPEC-177 — Jev decision backend adapter (`done`)

> **Correção 2026-10-05 — prevalece sobre o registro original abaixo.** O
> usuário forneceu uma chave da TypeSafe, não de jevmodel.org. O endpoint
> correto é `POST https://api.typesafe.ai/v1/systemone`, com
> `TYPESAFE_API_KEY` canônica e `JEVMODEL_API_KEY` aceita como alias local.
> Score oficial inclui `legend` e `probabilities`; retries documentados são
> 429/529. A API oficial não documenta deduplicação por `Idempotency-Key`.
> Uma chamada live ao host correto retornou `jev-1.13.0`, Choice válido e
> usage 394/58. O 401 anterior não testou autenticação na TypeSafe, mas a
> primeira chamada expôs a chave como Bearer ao host errado.
> Os limites locais de estado/perguntas/critérios são conservadores; não são
> os limites anunciados pela API oficial. A chave enviada ao host errado será
> revogada/substituída antes de novas chamadas live.
> Evidência: [Quick start](https://docs.typesafe.ai/introduction/quickstart),
> [API reference](https://docs.typesafe.ai/api).

## Registro histórico da primeira implementação

O texto abaixo descreve o contrato de `jevmodel.org` usado em 2026-10-02;
endpoint, autenticação, limites e retries citados ali não se aplicam à chave
TypeSafe do usuário. A correção acima e o adapter atual são a referência para
novas chamadas.

Executor nesta sessão: Sol High, em substituição a Terra High com autorização
expressa do usuário. Revisão independente Sol High: `/root/spec176_reviewer`,
decisão **APPROVED técnico local** após corrigir três gaps de segurança do
primeiro patch. A spec continua limitada a um adapter server-side; nenhuma rota
do jogo importa `services/jev_decision.py`.

Contrato consultado em 2026-10-02: [Jev API documentation](https://jevmodel.org/docs/).
O endpoint do serviço hospedado é `POST https://jevmodel.org/v1/systemone`,
Bearer `JEVMODEL_API_KEY`, estado serializado até 8.000 caracteres, 1–8
perguntas por request, Choice com 2–20 opções, Score com 2–10 níveis,
critérios serializados até 2.000 caracteres e instruções até 1.800. A API
documenta retry de 429/502 com a mesma `Idempotency-Key`.

## Implementação

- `DecisionBackend`/`JevDecisionBackend` isolam o provedor do `RoutedLLM`.
  `DecisionState` permite apenas ação, local, flag de combate e NPC ativo;
  rejeita o GameState integral e campos extras.
- Choice, Noul e Score são tipos fechados de request/response. A resposta
  exige nomes e tipos correspondentes, opções conhecidas, probabilidades e
  valores em faixa. Coerções de bool/string para números são rejeitadas.
- 401, 402, 422, 429, 5xx, timeout, transporte e resposta incompatível geram
  erros tipados. Só 429/502 recebem retry interno, com a mesma chave; erro
  nunca retorna uma decisão válida.
- O prazo total cobre HTTP, leitura/parse JSON e validação. Se uma operação
  remota sobreviver ao timeout, ela fica em quarentena: máximo de um worker
  por backend e oito globalmente até terminar. O timeout não cancela a
  operação no provedor; um retry lógico externo deve reutilizar sua chave.
  `close()` impede novas chamadas e fecha o client que o adapter criou.
- Telemetria opcional informa correlation ID, modelo resolvido, latência,
  usage e código de erro sem state/prompt/segredo. Custo por chamada fica
  `None` porque o endpoint não o reporta no contrato consultado.
- `.env.example` contém somente `JEVMODEL_API_KEY=`. `JEV_API_KEY` legado
  sozinho produz instrução explícita de migração; duas chaves divergentes
  falham fechado. `httpx` foi declarado dependência direta.

## Verificação

- 22 testes offline focados passaram, incluindo fixture sintética,
  respostas inválidas, erros HTTP, timeout de transporte e parse, quarentena
  de worker, idempotência e mutação posterior do request.
- Reviewer Sol High executou os 22 testes de forma independente e aprovou o
  patch técnico após duas rodadas de correção.
- `agents/router.py`, `llm_setup.py` e paths de eval protegidos permanecem
  byte-identical à base. `JEVMODEL_API_KEY` não aparece em `web/` ou `android/`.
- Governance dos seis datasets e Project Index check passaram. O índice foi
  regenerado somente porque o CI ainda exige freshness de artefatos após
  adicionar source/testes; não foi consultado como contexto nem teve
  `eval_map` alterado.
- Smoke live não foi executado: não há `JEVMODEL_API_KEY` local e a chamada
  real é opt-in na spec. O adapter não faz fallback silencioso.
- Suíte completa no clone com basetemp ASCII: **1.920 passed, 35 skipped,
  15 deselected**. A primeira tentativa com basetemp sob `Área de Trabalho`
  falhou em oito testes de FAISS/arte por caminho Unicode/comprido; os testes
  afetados passaram isoladamente em `%TEMP%` e a suíte completa também.
- Ruff passou; `git diff --check` passou. Parecer do reviewer em
  `handoffs/SPEC-177-SOL-independent-review.md`.

Commit publicado: `31ec7779570b13b746f52c3e5b1f00cfed2f6908` no
[PR #13](https://github.com/Batatao343/rpg-ia-master/pull/13), empilhado
sobre o PR #12. Os runs GitHub `validate` 37142521573 e `eval-gates`
37142521566 terminaram `success`. O gate protegido foi `skipped`, pois
nenhum path protegido mudou nesta spec. Este registro de fechamento altera
somente documentação/índice da spec; o novo commit deve repetir CI verde.
