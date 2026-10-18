# SPEC-251 — Trace mecânico do conflito (dados, alvos, dano, reações, morte) em debug log e audit_trace

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239, SPEC-240
> **Desbloqueia:** —
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — `audit_trace` entra no export de auditoria (SPEC-207)`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Os módulos que decidem o combate não emitem nada: `services/conflict_orchestrator.py` (1.471 linhas), `conflict_turn.py`, `conflict_resolution.py`, `conflict_damage.py`, `reactions.py`, `death_flow.py`, `chase.py`, `combat_targeting.py`, `combat_mechanics.py`, `progression.py`. Dados/acerto/dano voltam como dados (`conflict_resolution.py:67-77,187`), `out["logs"]` são strings para o jogador (`conflict_turn.py:88,95`). Alvo inválido: `agents/combat.py:1035` escolhe o primeiro inimigo em silêncio. O `audit_trace` (SPEC-207, `services/audit_trace.py:433`) guarda delta/contexto/tempo/rota, mas não rolagens, alvos, reações nem etapas de morte — “por que o jogador morreu?” não tem resposta nos logs.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Estrutura `MechanicsStep` (`kind`: `initiative|attack|save|damage|reaction|condition|death_stage|flee|target_redirect`; `actor_ref`/`target_ref` = ids de catálogo ou índice no manifesto, nunca nome; `dice` (lista de ints), `kept`, `modifier`, `dc_or_defense`, `result`, `amount`, `card_id`). Acumulada por turno num contextvar pelos serviços de conflito.
- **R2** — Fim do turno: `combat.mechanics` (`debug`) com a lista (≤ 64 passos, truncada com contador) e `combat.summary` (`info`) com agregados (`rounds`, `player_damage_taken`, `enemy_damage_dealt`, `reactions`, `death_stage_reached`, `target_redirects`).
- **R3** — `audit_trace` ganha `mechanics` (os mesmos passos, mesmo teto) — campo aditivo, sem bump de schema; export de auditoria inclui.
- **R4** — Alvo inválido redirecionado (`combat.py:1035`) gera passo `target_redirect` com `reason`.
- **R5** — Determinismo preservado: o trace nunca altera RNG nem ordem (teste de paridade: mesma seed ⇒ mesmo estado com e sem trace).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

UI do trace; persistir trace fora do ring buffer existente.

## 3. Design técnico

- **Novo:** `services/mechanics_trace.py` (contextvar + `record_step`). **Alterados:** serviços de conflito listados, `agents/combat.py`, `services/audit_trace.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_mechanics_trace.py`: `test_attack_records_dice_and_result`, `test_death_flow_stages_recorded`, `test_trace_capped`, `test_trace_parity_same_seed`, `test_no_names_in_trace`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde; `uv run python -m playtest run --profile combate --turns 10` sem regressão.

## 5. Critérios de aceite

- [ ] Um combate é reconstruível do `audit_trace` (rolagens → dano → morte).
- [ ] Paridade determinística comprovada.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. Laboratório de combate (`combat_simulation`) em staging: 3 rodadas, `audit-export` contém `mechanics` coerente com o log da UI.

## 7. Riscos & compatibilidade

- Tamanho do `audit_trace` (200 turnos ≈ 208 KB hoje): medir; teto de passos por turno.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
