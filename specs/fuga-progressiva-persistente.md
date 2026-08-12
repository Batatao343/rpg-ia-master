# SPEC — Fuga progressiva persistente

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** `conflito-09` e `combate-lifecycle` (`done`)
> **Desbloqueia:** playtests longos com agência defensiva confiável

---

## 1. Contexto & Objetivo

O playtest de jogador normal mostrou seis tentativas consecutivas de fuga sem
qualquer progresso observável. A trilha já existia, mas cada turno recriava a
perseguição em `pressionado`, tornando `afastado → quase_livre → escapou`
inatingível quando a cena começava próxima.

Esta spec torna a fuga uma decisão progressiva persistida em `combat.chase`,
mantendo toda resolução numérica em Python.

## 2. Requisitos

- **R1** — Uma perseguição válida deve ser retomada no turno seguinte, sem reiniciar a trilha.
- **R2** — Sucessos consecutivos devem alcançar `escapou`; falha deve regredir uma posição e `pressionado` pode resultar em `alcancado`.
- **R3** — Perseguição terminal, de outro fugitivo ou de outro conjunto de perseguidores não pode ser reutilizada.
- **R4** — `combat.last_player_action.result` deve distinguir `flee_progress`, `flee_failed` e `fled`.
- **R5** — O log deve informar avanço, regressão ou alcance, sem afirmar que o inimigo alcançou durante progresso válido.

### Fora de escopo

Balancear a dificuldade por criatura ou redesenhar a interface de perseguição.

## 3. Design técnico

- **`services/chase.py`** — validar se um snapshot de perseguição pode ser retomado.
- **`agents/combat.py`** — fornecer `combat.chase` à resolução, persistir o resultado e classificar a ação canônica.
- **`tests/test_fuga_progressiva_persistente.py`** — regressões unitárias e integração curta.
- O schema continua aditivo e tolerante: saves sem `combat.chase` iniciam uma perseguição normalmente.

## 4. Plano passo a passo

### Etapa 1 — Contrato de retomada

1. **Testes:** provar retomada, descarte de snapshot incompatível e três resultados canônicos.
2. **Implementação:** adicionar validação pura e reutilizar a trilha existente.
3. **Verificação:** testes direcionados verdes.

## 5. Critérios de aceite

- [x] Dois sucessos após `afastado` encerram a fuga.
- [x] Uma falha não apaga progresso sem aplicar a regressão prevista.
- [x] Telemetria diferencia progresso, falha e escape.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Nenhum structured output/LLM novo.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Entrar em combate próximo e pedir fuga até três vezes.
2. Confirmar trilha progressiva no estado e coerência entre narração e resultado.

Executado no smoke real `20260812-172526-505951`; fluxo de combate iniciou sem
erro de contrato. A progressão completa tem oráculo determinístico dedicado.

## 7. Riscos & compatibilidade

- Saves antigos não possuem `chase` e seguem pelo caminho de inicialização.
- Nenhum request ou custo de LLM adicional.
