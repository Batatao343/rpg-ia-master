# SPEC-262 — Runbook “como debugar X”, ferramenta de pseudônimo e decisão de retenção/drain de logs da Vercel

> **Status:** `done` — revisão Sol APPROVED + smoke staging (2026-10-19, [handoff](../handoffs/LOGS-P1-SOL-review.md)). Retenção: **default (só Vercel, sem drain) pendente de confirmação do dono**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239, SPEC-240 (o runbook descreve os campos); pode ser escrito em paralelo e atualizado a cada spec de log entregue
> **Desbloqueia:** operação do beta
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true — decisão de retenção/terceiro (LGPD)`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Não existe roteiro para investigar um relato. `docs/spec197/runbooks/incident.md:41` só cita `npx vercel logs --environment production --since 10m --query level:error`; `docs/operacao/OPERACAO_LOCAL.md` cobre só a stack local (Prometheus/Grafana/Tempo). Logs usam pseudônimos HMAC (`owner_id_ref`, `game_id_ref`) mas não há script para calcular o pseudônimo de um usuário a partir do id (o operador precisaria chamar `pseudonym()` com o segredo de produção à mão). Nenhuma decisão documentada sobre retenção dos runtime logs da Vercel (plano Hobby retém pouco tempo) nem sobre log drain; `docs/spec222/retencao.md` cobre só o banco.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `docs/operacao/RUNBOOK_DEBUG.md` com receitas passo a passo: (a) usuário reporta erro com código de suporte; (b) turno falhou/lento (por `action_ref`); (c) pagamento não creditado (Stripe/Play); (d) e-mail de auth não chegou (GoTrue/SMTP); (e) login/recuperação falhando (`auth.*` reasons); (f) provider LLM fora/caro; (g) job/cron travado; (h) deploy novo quebrou (`runtime.boot`, `build_skew`). Cada receita: comando exato (`vercel logs --query`, SQL read-only no Supabase, `/metrics`), campos a olhar, próximo passo.
- **R2** — `scripts/log_ref.py <owner|game|action> <id>` imprime o pseudônimo usando `RPG_TELEMETRY_SECRET` do ambiente (lido do `.env`/stdin, nunca argumento de linha de comando), para buscar em logs; recusa rodar sem o segredo.
- **R3** — `docs/operacao/LOGS_RETENCAO.md`: limites atuais da Vercel no plano em uso (retenção, tamanho de linha, linhas/s) medidos/citados com data; decisão (dono) entre ficar só na Vercel ou ativar log drain (destino, custo, operador declarado na política de privacidade — SPEC-222 R8); política de níveis/amostragem por área (tabela `area → nível default`).
- **R4** — Catálogo de eventos `docs/operacao/EVENTOS_DE_LOG.md` gerado de um registro em código (`observability/events.py` lista `area.event` + campos) e teste de frescor; teste falha se `log_event` usar evento não registrado.
- **R5** — `incident.md` aponta para o runbook.

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Implantar o drain (spec própria após a decisão do dono).

## 3. Design técnico

- **Novos:** `docs/operacao/RUNBOOK_DEBUG.md`, `docs/operacao/LOGS_RETENCAO.md`, `docs/operacao/EVENTOS_DE_LOG.md`, `scripts/log_ref.py`, `observability/events.py`, `tests/test_log_event_registry.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_log_ref.py` (mesmo resultado que `pseudonym()`; recusa sem segredo; não aceita segredo por argv); `tests/test_log_event_registry.py` (todo `log_event` literal está registrado; doc fresco).

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde; revisão do runbook por quem não escreveu (dry-run de cada receita em staging).

## 5. Critérios de aceite

- [ ] Cada receita executada uma vez em staging com o resultado anotado.
- [ ] Decisão de retenção/drain registrada pelo dono.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Simular relato: provocar erro no web, copiar código de suporte, achar a linha em `vercel logs` em < 2 min seguindo só o runbook.

## 7. Riscos & compatibilidade

- Ativar drain envia logs a terceiro: precisa constar na política de privacidade antes (SPEC-222).
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `docs/operacao/RUNBOOK_DEBUG.md` (8 receitas a–h, com comandos `vercel logs --query`, SQL somente-leitura e métricas), `scripts/log_ref.py` (pseudônimo owner|game|action; segredo só do ambiente/.env/--stdin, recusa sem segredo e por argv), `docs/operacao/LOGS_RETENCAO.md` (níveis por área, volume por turno, **decisão com o default da spec: ficar só na Vercel, sem log drain** — não é decisão do dono; limites da Vercel marcados como não verificados por falta de rede), catálogo `observability/events.py` + `docs/operacao/EVENTOS_DE_LOG.md` gerados por `scripts/gen_event_catalog.py` (varredura AST + wrappers; teste falha se um evento literal novo não estiver registrado ou se o doc estiver velho), `incident.md` aponta para o runbook. Testes: `tests/test_log_ref.py`, `tests/test_log_event_registry.py`. Pendentes (dependem do operador/staging): dry-run de cada receita em staging, medição real de linhas/turno, decisão formal do dono sobre retenção/drain.
