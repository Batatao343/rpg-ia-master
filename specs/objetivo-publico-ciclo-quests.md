# SPEC — Objetivo público e ciclo verificável de missões

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `fase-3.3-quest-log` (`done`)
> **Desbloqueia:** avaliação quantitativa de campanhas longas por objetivo

---

## 1. Contexto & Objetivo

O frontend expunha literalmente o beat privado do `CampaignPlan`, embora ele seja
uma instrução de direção para o narrador. A campanha também registrava criação e
conclusão de side quests, mas não deixava auditável se houve progresso e entrega
real da recompensa.

Esta spec separa a direção privada da informação segura ao jogador e transforma
o ciclo pedido → missão → progresso → conclusão → recompensa em estado mecânico
e telemetria. A LLM continua propondo conteúdo; visibilidade e recompensa são
decididas em Python.

## 2. Requisitos

- **R1** — A API jamais usa `CampaignBeat.description` como objetivo público.
- **R2** — O objetivo público é derivado deterministicamente do arco, local e da
  side quest ativa, sem revelar beats futuros ou clímax.
- **R3** — Toda quest criada tem `progress_log` iniciado por `created`.
- **R4** — Chegar ao local-alvo registra progresso idempotente `location_reached`.
- **R5** — Concluir uma quest registra `completed` e entrega uma recompensa fixa,
  auditável e idempotente em ouro pelo motor Python.
- **R6** — O playtest mede quests criadas, com progresso, concluídas e recompensadas.

### Fora de escopo

- Reescrever beats existentes com LLM; balancear individualmente recompensas;
  alterar fallback de provider.

## 3. Design técnico

- `services/objectives.py`: `public_objective(plan, quests, world) -> dict`.
- `services/quest_log.py`: ledger de progresso, sincronização por local e
  conclusão com recompensa; `QUEST_REWARD_GOLD = 20`.
- `api.py`: passa o mundo à view e expõe apenas o objetivo público.
- `state.py`: amplia `Quest` com `progress_log`, `reward_gold` e `reward_delivered`.
- `playtest/runner.py` e `playtest/telemetry.py`: métricas do funil completo.

## 4. Plano passo a passo

1. Escrever testes unitários da view pública, progresso e recompensa.
2. Implementar os serviços puros e conectá-los ao storyteller/event processor.
3. Cobrir serialização/API e telemetria.
4. Rodar testes focados, smoke offline e suíte completa.

## 5. Critérios de aceite

- [x] Beat privado não aparece no objetivo público nem na orientação social.
- [x] Progresso por local e recompensa são idempotentes.
- [x] Funil completo aparece no resumo do playtest.
- [x] Saves antigos continuam carregando.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Reutilizar o relatório real já capturado para validar o formato e executar uma
campanha curta somente se houver chaves/cota disponíveis. Nenhuma chamada nova é
necessária para validar a mecânica, que é integralmente determinística.

Executado smoke MockLLM `20260813-001000-370465`: 12/12 turnos, zero erro e
zero violação; quests e funil presentes no summary.

## 7. Riscos & compatibilidade

Campos ausentes em quests antigas recebem defaults nas funções puras. A recompensa
fixa só é concedida quando uma transição ativa→concluída realmente acontece.
