# SPEC — Structured output com evidência e recuperação orientada à causa

> **Status:** `done` ? aceite local e smoke real DeepSeek verdes em 2026-09-28.
> **Criada/Atualizada:** 2026-08-27
> **Depende de:** `hardening-structured-sentinelas-rag` (`done`)
> **Supera:** retry cego de `structured-output-retry-provider`

## 1. Contexto & Objetivo

A matriz A teve 19 tentativas inválidas recuperadas, quase todas
`CampaignPlanModel=None`; uma execução foi abortada após três respostas assim.
Hoje `RoutedLLM` recebe apenas `None`, perde a mensagem bruta e repete o mesmo
pedido genérico. Precisamos recuperar JSON já válido sem nova chamada e escolher
retry/fallback com evidência, mantendo o retorno público atual.

Referências oficiais: LangChain permite `include_raw=True` e retorna
`raw/parsed/parsing_error` ([structured output](https://docs.langchain.com/oss/python/langchain/models));
DeepSeek suporta `tool_choice` nomeado e strict tool calls apenas no endpoint beta
([tool calls](https://api-docs.deepseek.com/guides/tool_calls/)); JSON mode exige
instrução explícita e schema no prompt ([JSON mode](https://api-docs.deepseek.com/guides/json_mode/)).

## 2. Requisitos

- **R1 — Evidência interna:** para schema Pydantic, o roteador força
  `include_raw=True` internamente, sem alterar o tipo retornado aos callsites.
- **R2 — Classificação:** causa fechada `no_tool_call`, `wrong_tool`,
  `parsing_error`, `schema_validation` ou `transport`; telemetria não contém raw.
- **R3 — Recuperação local:** antes de retry de rede, extrair de
  `AIMessage.content` somente objeto JSON cercado ou bloco JSON e validar com o
  Pydantic solicitado. Sucesso conta como `local_recovery`, não nova request.
- **R4 — Retry orientado:** prompt informa a causa e o nome do schema, sem ecoar
  resposta potencialmente sensível. Máximo existente de três gerações permanece.
- **R5 — Método:** function calling nomeado segue padrão OpenAI-compat. JSON mode
  só pode ser usado como última tentativa DeepSeek quando o client suporta e o
  schema foi injetado; strict beta não é default.
- **R6 — Fail-closed:** esgotamento continua retornando `AIMessage("")`; guards
  dos nós permanecem obrigatórios.
- **R7 — Imutabilidade:** listas de mensagens e kwargs do callsite nunca são
  mutados entre providers/tentativas.
- **R8 — Paridade:** `invoke` e futuro `ainvoke` compartilham classificação,
  validação e telemetria; esta spec não implementa concorrência/async.

### Fora de escopo

Trocar provider/modelo, relaxar schemas, logar prompts/raw ou implementar a spec
de latência.

## 3. Design técnico

- `llm_setup.py`: envelope interno, `StructuredFailureCode`,
  `_recover_structured_from_raw`, `_structured_retry_instruction` e normalização
  do retorno para respeitar `include_raw` solicitado pelo chamador.
- `LLMAttemptEvent`: `structured_failure_code` e `recovery`, ambos opcionais e
  sem conteúdo bruto.
- DeepSeek permanece em function calling por padrão; JSON mode é capability
  explícita, testada com fake client antes de qualquer smoke pago.

## 4. Plano TDD

1. Fake client retorna `parsed=None` com raw contendo JSON válido: uma única
   request e retorno Pydantic.
2. Cobrir raw vazio, markdown JSON, JSON inválido, campo extra/ausente, erro de
   parser e `include_raw=True` solicitado pelo callsite.
3. Cobrir retry reason-aware, fallback de provider, telemetria redigida e input
   imutável.
4. Teste contratual de `CampaignPlanModel` com fixture equivalente ao None real;
   implementar e rodar suíte completa.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

Tool call com nome diferente é `wrong_tool`; JSON presente que não valida é
`schema_validation`; falha de transporte ganha código próprio. Fixtures não
dependem de provocar essas falhas por sorte em campanha longa. Não se ativa
JSON mode nem se muda fallback nesta remediação. Gates separados no
[adendo pré-matriz](SPEC-162-remediacao-local-contratos-pre-matriz.md).

- [x] `CampaignPlanModel=None` tem código causal observável.
- [x] JSON bruto válido é recuperado sem segunda chamada.
- [x] Retry não é genérico nem vaza raw/prompt.
- [x] Contrato de retorno dos callsites permanece byte-compatível.
- [x] Fail-closed e fallback entre providers permanecem.
- [x] Testes cobrem as recorrências sem campanha longa.
- [x] Suíte completa offline verde.
- [x] Contrato real curto (§6) confirma integração com provider; B integral é gate global separado.

## 6. Smoke real

Atualização de 17/09: B integral bloqueada por HTTP 402 DeepSeek. O último
preflight falhou por saldo, não valida a recuperação do build atual; ver
[fechamento local](../docs/fechamento-local-2026-09-17.md).

Executar 10 gerações de CampaignPlan no DeepSeek com telemetria; toda falha deve
ser classificada, recuperada ou cair para provider segundo a política, sem None
opaco.

## 7. Riscos

Parsing permissivo pode aceitar texto estranho. A extração será estrita, limitada
em tamanho, sem `eval`, e toda saída passa pelo Pydantic original.


## Fechamento real ? 2026-09-28

Preflights cobriram os tr?s tiers e a matriz recuperou respostas estruturadas inv?lidas sem None opaco ou invoca??o terminal nas campanhas v?lidas.
Evid?ncia consolidada: [matriz B](../docs/playtest-matriz-b-2026-09-28.md), `20260927-214549-731406` e `20260928-084057-102826`. A matriz global incompleta permanece responsabilidade exclusiva da SPEC-128.
