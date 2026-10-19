# SPEC-252 — Rejeições do mundo, guarda narrativa, economia e replanejamento com motivo em log

> **Status:** `done` — aprovada pelo dono em 2026-10-19. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-240, SPEC-250
> **Desbloqueia:** —
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `event.proposal_rejected` (`services/event_processor.py:327`) só tem `type` — o motivo e o alvo ficam no estado (`event_rejections`, `328-333`); `world_validators.validate_proposal` (`355-362`) transforma exceção em motivo textual sem log; rejeições SPEC-223 de pré-validação (`event_processor.py:314-320`, `storyteller.py:888`) e a guarda narrativa (`storyteller.py:1094,1109,1190` → `narrative_rejections`, limpo pelo arquivista `archivist.py:886,975`) não geram linha. Economia: mudanças de ouro (`agents/loot.py:207-211`, `services/economy.py:284`), troca recusada e conflito de item único (`economy.py:161-179`) são silenciosos. Campanha: `_should_replan` (`agents/campaign_manager.py:75-86`) e `needs_replan` (`286`, `306`) sem motivo em log.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `event.proposal_rejected` ganha `reason_code` (enum fechado derivado do validador: `unknown_target|not_in_scene|unproven|cooldown|unique_claimed|malformed|...`), `target_ref` (id de catálogo), `source` (`llm|rule|prevalidation`). Texto livre do motivo continua só no estado.
- **R2** — `narrative.rejected` com `kind` (`item|event|mediation`) e `reason_code`; contagem também no `rpg.turn`.
- **R3** — `economy.trade` (`info`) com `outcome` (`ok|refused`), `reason_code` (`insufficient_gold|not_owned|no_merchant|unique_conflict|...`), `gold_delta`, `item_id`; `economy.unique_claim_conflict` (`warning`).
- **R4** — `campaign.replan` (`info`) com `reason` (`needs_replan|region_change|periodic|first_plan`) e `outcome` (`llm|template|previous_kept`).
- **R5** — Teste com sentinela: nenhum texto de narração/ação do jogador nesses eventos.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Trace de combate (SPEC-251).

## 3. Design técnico

- **Alterados:** `services/event_processor.py`, `services/world_validators.py` (retorna `code` além do texto), `agents/storyteller.py`, `agents/loot.py`, `services/economy.py`, `agents/campaign_manager.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_world_rejection_logs.py`: `test_rejection_has_reason_code`, `test_trade_refused_logged`, `test_unique_conflict_logged`, `test_replan_reason_logged`, `test_no_free_text`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [x] Toda rejeição/recusa tem `reason_code` estável em log.
- [x] Sem texto livre.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: tentar comprar sem ouro e reivindicar quest sem prova ⇒ linhas `economy.trade outcome=refused` e `event.proposal_rejected reason_code=unproven`.

## 7. Riscos & compatibilidade

- Nenhum.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## 8. Notas de implementação (2026-10-19)

- `reason_code` é derivado do texto do validador por `world_validators.reason_code` (enum `REASON_CODES`; desconhecido ⇒ `other`) em vez de mudar `ValidationResult` (contrato/estado intactos). `unique_claimed` fica no enum mas só é emitido em `narrative.rejected`/`economy`.
- `target_ref` só sai se `catalog_ref` achar o id no grafo, mapa ou `ARTIFACTS_DB`; nomes livres e ids de quest são omitidos. `type` agora é saneado para o enum `EventType` (`other` fora dele).
- `rpg.turn` ganhou `narrative_rejected` (`{kind: contagem}`) via `observability.telemetry.count_turn` (contador no bucket do turno).
- Campanha: `_build_plan` aceita `_info` opcional para reportar `outcome` (`llm|template|previous_kept`); `campaign.replan` só é emitido quando o replanejamento é de fato tentado (adiamento por combate ativo não gera linha).
- Eventos novos: `event.proposal_rejected` (campos novos), `narrative.rejected`, `economy.trade`, `economy.unique_claim_conflict`, `campaign.replan`. Métricas novas: nenhuma.
- Smoke de staging sugerido: comprar sem ouro e propor `quest_completed` sem prova ⇒ `economy.trade outcome=refused reason_code=insufficient_gold` e `event.proposal_rejected reason_code=unproven`; conferir `rpg.turn.narrative_rejected`.
