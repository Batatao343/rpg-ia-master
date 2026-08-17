# SPEC — Continuidade temporal, autoridade de memória e consequência da morte

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `checkpoints-morte`, `hardening-memoria-proveniencia` (`done`)
> **Desbloqueia:** campanhas ramificadas auditáveis

---

## 1. Contexto & Objetivo

Restaurar checkpoint recua o turno canônico, mas hoje apaga a evidência da morte e
confunde ações efetivamente jogadas com a posição atual da linha do tempo. A memória
também precisa mostrar sua autoridade agregada para que inferências não dominem o
contexto sem diagnóstico.

## 2. Requisitos

- **R1** — O estado possui `continuity` com `session_action_count`,
  `timeline_epoch` e `death_history` limitado.
- **R2** — Cada invoke incrementa ações da sessão e o turno canônico continua em
  `world.turn_count`; restore preserva ações, incrementa época e registra perda.
- **R3** — O registro de morte informa origem/destino, turnos perdidos, o que foi
  mantido e o que foi revertido; API e modal o tornam legível.
- **R4** — Save schema v7 migra saves v6 sem perda.
- **R5** — Telemetria diferencia ação da sessão, turno canônico e época.
- **R6** — O summary mede proporção de memória confirmada, relatada e especulativa,
  além de inferências antigas ainda não promovidas.
- **R7** — Promoção de memória continua exigindo evidência de maior autoridade;
  repetição especulativa, sozinha, não confirma fatos.

### Fora de escopo

- Permadeath, cicatriz mecânica nova, mudança de FAISS/provider ou fallback.

## 3. Design técnico

- `state.py`: `ContinuityState` e `GameState.continuity`.
- `services/continuity.py`: normalização, incremento e merge pós-restore.
- `persistence.py`: schema v7 e backfill.
- `services/checkpoints.py`: preserva metatempo e cria consequência.
- API/frontend: bloco `continuity` e detalhe na tela de morte.
- Telemetria: três relógios e índice de autoridade da memória.

## 4. Plano passo a passo

1. Testar normalização/migração e restore após morte.
2. Integrar incremento no campaign manager e persistência.
3. Expor API/modal e telemetria.
4. Testar autoridade sem promoção indevida.
5. Rodar suíte completa.

## 5. Critérios de aceite

- [x] Restore não apaga morte nem contagem de ações da sessão.
- [x] Consequência informa exatamente o intervalo revertido.
- [x] Saves v6 migram idempotentemente para v7.
- [x] Inferência repetida não vira fato confirmado.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Não exige LLM: morte, restore, migração e métricas são Python determinístico. Um
smoke da API valida a representação pública.

Validado por testes de restore/migração/API e build Vite; smoke de 12 turnos
registrou separadamente ação 13, turno canônico 13 e época 0.

## 7. Riscos & compatibilidade

Checkpoints v6 são migrados ao carregar. `death_history` é metadado de sessão e,
por design, vence o valor antigo contido no snapshot restaurado.
