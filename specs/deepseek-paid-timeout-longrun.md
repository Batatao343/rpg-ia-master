# SPEC — Janela de timeout do DeepSeek no longrun isolado

> **Status:** `done`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A1 `20260820-185627-750638`, par 2, turno 71
> **Depende de:** `matriz-a-capacidade-provider`

## 1. Contexto & objetivo

O preset `deepseek-paid` usa um único provider para provar campanhas 100% LLM.
O timeout de produção do DeepSeek é 12 s para permitir fallback rápido, mas no
turno 71 três invocações diferentes expiraram entre 12,0–12,5 s, enquanto quatro
outras invocações do mesmo turno tiveram sucesso. O watchdog do experimento já
permite 120 s por turno e sucessos anteriores chegaram a 26 s.

O preset de capacidade deve dar ao DeepSeek uma janela de 40 s sem alterar o
default do produto. Não haverá retry HTTP nem outro provider: timeout real após
essa janela continua terminal e fail-closed.

## 2. Requisitos

- **R1:** ativar `deepseek-paid` define `DEEPSEEK_TIMEOUT_SECONDS=40` durante o
  contexto do perfil.
- **R2:** o valor anterior da env é restaurado ao sair, inclusive em exceção.
- **R3:** `groq-free` e execução normal não alteram o timeout DeepSeek.
- **R4:** manifesto A/B continua registrando o mesmo nome de preset; o pareamento
  usa a mesma janela.
- **R5:** `max_retries=0`, watchdog de 120 s e tetos de custo/request não mudam.

### Fora de escopo

- Aumentar timeout de produção.
- Retry de timeout/429/5xx.
- Misturar provider de fallback na matriz.

## 3. Design técnico

- `playtest/provider_profiles.py`: env temporária escopada ao contexto do preset.
- `tests/test_remediacao_matriz_a.py`: aplicação/restauração e isolamento.

## 4. Plano passo a passo

1. Criar regressões de env e confirmar falha.
2. Implementar configuração/restauração no context manager.
3. Rodar testes focados, suíte completa e preflight real.
4. Reiniciar A1 do par 1.

## 5. Critérios de aceite

- [x] DeepSeek isolado usa 40 s.
- [x] Env anterior é restaurada.
- [x] Outros presets não são afetados.
- [x] Suíte completa verde (1608 testes).
- [x] A1 completou quatro campanhas e 81 turnos sem timeout DeepSeek de 12 s;
  a interrupção posterior foi `Connection error`, não timeout.

## 6. Smoke real

Preflight 3/3 seguido da matriz A1 com `--turn-timeout 120`; telemetria deve
mostrar que nenhuma tentativa é cortada no antigo limiar de 12 s.

## 7. Riscos & compatibilidade

Uma chamada lenta pode aumentar a latência do playtest; o watchdog limita o
turno inteiro. Produto, saves e rotas padrão permanecem inalterados.
