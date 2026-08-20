# SPEC — Retry semântico de structured output no mesmo provider

> **Status:** `in-progress`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A1 DeepSeek `20260820-181149-643772`
> **Depende de:** `playtest-real-llm-fail-closed`

## 1. Contexto & objetivo

No primeiro turno da A1, seis invocações reais funcionaram, mas uma resposta
`WorldPulse` retornou `None` apesar de usar tool calling. O `RoutedLLM` reconheceu
corretamente o retorno estruturado inválido e o jogo aplicou seu no-op resiliente;
o contrato LLM-only também encerrou corretamente a matriz. O erro é recuperável
por uma nova geração, não por fallback determinístico.

`max_retries=0` permanece obrigatório no client: erros de rede, quota e saldo não
devem repetir. Esta spec permite até três gerações totais apenas após respostas
de rede bem-sucedidas cujo structured output seja inválido. Ela usa o mesmo
provider/modelo, acrescenta uma instrução humana curta e mantém a telemetria
como uma única invocação lógica.

O primeiro limite de duas gerações foi insuficiente no turno 150 do run
`20260820-182003-393045`: ambas retornaram `None`, enquanto um replay imediato
do mesmo planner/save teve sucesso e produziu cinco beats. Isso caracteriza
falha transitória e justifica a terceira geração sem relaxar o fail-closed.

## 2. Requisitos

- **R1:** structured output Pydantic inválido recebe no máximo dois retries no
  mesmo provider/modelo antes de avançar para o próximo candidato.
- **R2:** o retry acrescenta uma mensagem humana pedindo apenas a tool call
  estruturada e não muta o input original.
- **R3:** sucesso após duas falhas retorna a instância Pydantic e emite eventos
  `invalid_structured` → `invalid_structured` → `success`, índices 0 → 1 → 2.
- **R4:** se as três gerações forem inválidas, o próximo provider é tentado com
  índice 3; esgotar todos preserva o `AIMessage` e o guard existente.
- **R5:** `invoke_error`, rate limit, quota, build error e chamadas plain não
  recebem retry no mesmo provider.
- **R6:** `fell_back` só é verdadeiro ao mudar de provider; retries locais não
  falseiam a métrica de fallback.
- **R7:** a política vale no roteador do produto e no playtest; não altera
  mecânica nem adiciona fallback determinístico.

### Fora de escopo

- Retry de falhas HTTP/rede.
- Mais de duas regenerações semânticas.
- Relaxar o fail-closed da matriz real.

## 3. Design técnico

- **Alterado:** `llm_setup.py` — contador monotônico por invocação, loop local
  de no máximo três gerações structured e helper de input corretivo.
- **Alterado:** `tests/test_routing.py` — sucesso no retry, esgotamento/fallback,
  input imutável e ausência de retry para plain/exception.
- A API pública de `get_llm()` e `RoutedLLM` não muda.

## 4. Plano passo a passo

1. Criar regressões de roteamento e confirmar falha antes da implementação.
2. Implementar o retry semântico limitado no `RoutedLLM.invoke`.
3. Rodar testes focados, suíte completa e preflight real.
4. Reiniciar A1 desde o par 1.

## 5. Critérios de aceite

- [x] Dois `None` seguidos de payload válido concluem sem fallback de provider.
- [x] Três payloads inválidos avançam uma única vez ao próximo candidato.
- [x] Input original permanece inalterado e retry termina em `HumanMessage`.
- [x] Falha HTTP e plain invoke continuam fail-fast.
- [x] Contagem de invocação terminal permanece correta.
- [x] `uv run pytest` verde.
- [ ] A1 não volta a encerrar por um primeiro `invalid_structured` recuperado.

## 6. Smoke test com LLM real

1. Repetir o preflight DeepSeek nos três tiers.
2. Reiniciar A1 com fail-closed.
3. Confirmar em telemetria que qualquer retry recuperado pertence à mesma
   invocação e que nenhum fallback determinístico foi aceito.

## 7. Riscos & compatibilidade

- Um retorno inválido pode custar até duas chamadas adicionais; o teto do
  playtest contabiliza cada tentativa.
- O retry não se aplica a 429/5xx/timeout e preserva a decisão fail-fast do
  projeto.
- Saves e schemas persistidos não mudam.
