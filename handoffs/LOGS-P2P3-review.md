# Revisão independente — logs P2/P3 (branch `logs-p2p3`)

Escopo: `git diff main...logs-p2p3` (SPEC-244, 246, 251, 252, 253, 256, 258, 259, 260, 261). Revisor que não escreveu o código. Data: 19/10.

## Veredito: **CHANGES_REQUIRED** (2 correções pequenas, achados 1 e 2; o resto pode ser follow-up)

Nenhum log mudou fluxo de jogo, RNG, ordem de combate, contrato de resposta ou fail-open/fail-closed. Os bloqueios são: a migration nova não funciona com a role que o código usa, e uma métrica nova tem cardinalidade aberta numa superfície pública.

## Achados

1. **(média) A migration `cron_run_state` não dá acesso ao `rpg_admin`, então o R3 da SPEC-256 nunca funciona.**
   - **Onde:** `supabase/migrations/20261019100000_cron_run_state.sql:10-12`.
   - **Problema:** a tabela fica com `enable` + `force row level security` e nenhuma policy. O `rpg_admin` é NOBYPASSRLS (migration 20261017120000). Com isso o upsert de `_bump_persisted` (`services/cron_internal.py:68-88`) será sempre recusado por RLS. O efeito: `cron.state_unavailable` a cada execução e o contador volta a ser só em memória. As migrations anteriores com FORCE RLS (`20261016120000`, `20261017110000`) terminam com `select app.grant_runtime_access();`, que cria `admin_all`/`runtime_all`. O teste `test_consecutive_failures_persisted` usa uma conexão falsa e não exercita SQL nem RLS.
   - **Correção:** acrescentar `select app.grant_runtime_access();` no fim da migration, antes de aplicá-la no staging (depois de aplicada ela fica imutável). Idealmente, um teste de integração local que faça o upsert como `rpg_admin`.

2. **(média) A métrica `rpg_http_body_too_large_total{route}` tem cardinalidade aberta.**
   - **Onde:** `services/body_limit.py:12-27,57`.
   - **Problema:** o rótulo vem do path cru da requisição. O limite default (256 KiB) vale para todo POST, inclusive em paths inexistentes. Basta um `Content-Length` acima de 256 KiB, sem nem enviar o corpo, para o 413 sair imediatamente. Assim, qualquer cliente anônimo cria uma série nova por path aleatório. `observability/metrics.py` não tem teto de séries. O campo `route` do log também carrega texto arbitrário (até 120 caracteres). O `route_label` só converte UUIDs em template.
   - **Correção:** usar como rótulo a chave de `per_path` quando casar e, nos demais casos, o template da rota resolvida pelo app ou `"other"`. Aplicar o mesmo valor no campo do log.

3. **(baixa) O endpoint público do beacon confia no formato que o cliente envia.**
   - **Onde:** `api.py` `ClientErrorReport` (`route`, `request_id`) e `client_error`.
   - **Problema:**
     - O servidor aceita `route` como `/game/<uuid>` cru, porque o regex não impõe template. Um cliente antigo ou com bug, ou um call site futuro sem `routeTemplate`, poria o `game_id` em claro no log.
     - O `request_id` é livre: um terceiro pode "plantar" linhas no código de suporte de outra pessoa.
     - `client.error` sai em toda requisição: 30 warnings/min por IP, e sem teto com IPs distribuídos.
   - **Correção:**
     - Validator que rejeite (ou converta em template) segmentos hex com 16 ou mais caracteres e segmentos só de dígitos.
     - Amostrar `client.error` por (`ip_ref`, `kind`, `code`), como já se faz em `abuse.blocked`. A métrica continua contando tudo.

4. **(baixa) Uma exceção no `sendBeacon` derruba o envio sem tentar o fallback.**
   - **Onde:** `web/src/lib/clientErrors.ts` `transmit`.
   - **Problema:** se `navigator.sendBeacon` lançar exceção, o `fetch keepalive` não é tentado. Algumas versões do Chromium recusam Blob com tipo `application/json`, que não é CORS-safelisted. O erro fica contado no dedupe e no teto de 20 sem ter sido entregue.
   - **Correção:** `try { if (sendBeacon(...)) return; } catch {}` e cair no `fetch`.

5. **(baixa) O logcat de release leva a `debugMessage`, contra o R2 da SPEC-259.**
   - **Onde:** `PlayBillingPlugin.java` `fail()`.
   - **Problema:** o código registra `debugMessage=<saneada>` no logcat também em release. O R2 da SPEC-259 pede só código + `responseCode`, e o javadoc de `BillingErrors.logLine` diz "nunca … debugMessage". O texto é saneado (24 ou mais caracteres opacos, até 120), então o risco é baixo, mas pode conter `productId`.
   - **Correção:** tirar a mensagem do `Log.w` (ela segue no objeto para o JS) ou condicioná-la a `BuildConfig.DEBUG`. Alinhar o comentário e a nota da spec.

6. **(baixa) O catálogo de eventos está incoerente com o código.**
   - **Onde:** `observability/events.py` e `docs/operacao/EVENTOS_DE_LOG.md:86`.
   - **Problema:** os dois arquivos listam `event.proposal_rejected` com "—", porque os campos vêm por `**fields`. O código e o runbook (l. 158) usam `type`, `reason_code`, `source` e `target_ref`.
   - **Correção:** adicionar a entrada em `OVERRIDES` de `scripts/gen_event_catalog.py` e regerar o catálogo.

7. **(baixa) O escopo do trace mecânico é mais amplo do que o documentado.**
   - **Onde:** `services/audit_trace.py:52-61`.
   - **Problema:**
     - O escopo fica aberto o turno inteiro. Passos de nós fora do combate entram em `audit_trace.mechanics` de turnos sem conflito, por exemplo `general_test` no storyteller ou `resolve_damage_and_wounds` em `world_utils.py:1111` (viagem/clima). Isso contradiz `docs/auditoria/README_SCHEMA.md` ("só turnos com conflito").
     - Esses passos também entram no `combat.mechanics` se houver combate no mesmo turno.
     - O R3 só é testado chamando `combat_node` direto. Não há teste via grafo/API provando que o contextvar atravessa o executor do LangGraph até `record_turn_trace`.
   - **Correção:** ajustar a doc (ou gravar só se o combate rodou) e adicionar um teste de turno via `_run_turn` com combate.

8. **(baixa) O `reason` de `campaign.replan` é impreciso e há linhas com estilo quebrado.**
   - **Onde:** `agents/campaign_manager.py` `_replan_reason`.
   - **Problema:**
     - `periodic` mistura o intervalo de replanejamento com "beats esgotados" (ramo `finished` de `_should_replan`).
     - O motivo é calculado depois de `_build_plan`.
     - Há linhas com uma sequência longa de espaços no meio (continuação colapsada), aqui e em `services/world_validators.reason_code`. Código válido, mas ilegível.
   - **Correção:** acrescentar `arc_finished`, calcular o motivo antes de `_build_plan` e quebrar essas linhas.

9. **(baixa) Os códigos de motivo dependem de trechos de mensagens em PT.**
   - **Onde:** `services/economy.trade_reason_code` e `world_validators.reason_code`.
   - **Problema:** se alguma mensagem mudar, o código vira `other` silenciosamente.
   - **Correção:** um teste que percorra as mensagens reais de recusa e dos validadores e exija que nenhuma caia em `other`.

10. **(baixa) Tooling.**
    - O R2 da SPEC-260 (evals) não foi implementado. O desvio está justificado (régua protegida com relock), mas precisa de uma spec de follow-up registrada.
    - O payload de falha de setup do `post_deploy_smoke.main` não tem `failed_checks`/`base_origin`, então o schema v2 fica inconsistente entre os dois caminhos.

## O que verifiquei e está ok

- **Privacidade (SPEC-222):**
  - IDs passam por `pseudonym` em todos os pontos novos: `game_ref`, `owner_ref`, `ip_ref`, `item_ref`, wallet/conta.
  - Exceções só como `type(exc).__name__` e `safe_stack`. Nenhum `str(exc)` em logs de produção; no playtest local é proposital (R1).
  - `provider.attempt` não leva áudio, prompt, texto embeddado nem URL (as sentinelas cobrem STT, imagem, Jina e o kill switch).
  - `rag.meta_unreadable` usa o nome lógico do índice, não o caminho.
  - `economy.trade.item_id` só aparece se estiver em `ARTIFACTS_DB`; `target_ref` só se for id de catálogo.
  - Trace mecânico: refs por regex de catálogo, sem nomes (teste `test_no_names_in_trace`). O export continua com allowlist `MECHANICS_STEP_SPEC` e scan de PII fail-closed; a chave extra é descartada.
  - Beacon: `extra=forbid`, enums e regex estreitas, e o cliente remove mensagem, query e origem do stack. Testes web e Python têm sentinelas de e-mail e token.
  - logcat do console do WebView só em `BuildConfig.DEBUG`.
- **Comportamento:**
  - O wrapper `combat_node` → `_combat_node` preserva a assinatura.
  - `record_step` só lê valores já calculados e nunca levanta (o teste de paridade com a mesma seed passa).
  - `scope()` reaproveita o escopo externo e faz `reset` em `finally`, sem vazar entre turnos.
  - `resolve_damage_and_wounds(**kwargs)` é compatível com todos os chamadores (todos usam keyword).
  - O fail-open do limiter e da cota foi mantido.
  - O comportamento do cron não muda se a tabela faltar (fallback em memória).
  - O POST de compra e as rejeições do plugin seguem propagando como antes.
- **Endpoint público:**
  - Classe `telemetry` com 30/min por IP nos dois perfis.
  - Teto de 4 KiB no `BodyLimitMiddleware`.
  - Origin cruzada → 403; kill switch → 404.
  - Ficar fora da fronteira de sessão/CSRF é aceitável: o endpoint não tem efeito de estado e não lê cookie/owner, e o desvio está documentado.
- **Métricas:** `rpg_client_errors_total{kind}`, `rpg_rate_limiter_errors_total{site}` e `rpg_provider_*{capability,provider,outcome}` estão registradas em `LABELS`, com valores fechados (exceção: achado 2).
- **Build id:** formato fechado no servidor (fora do formato vira `other`), `build_skew` por prefixo e `deploy_args` com `GIT_SHA` em runtime e build. O `@capacitor/app` está instalado no shell, então o R4 de versão funciona.
- **Testes:** os arquivos novos e afetados passam (91 Python + 12 Node): `test_abuse_logging`, `test_api_access_log`, `test_client_error_beacon`, `test_cron_logging`, `test_mechanics_trace`, `test_persistence_logs`, `test_provider_logging`, `test_world_rejection_logs`, `test_post_deploy_smoke`, `test_spec192_cron_endpoints`, `test_log_event_registry`, além de `clientErrors`, `build` e `nativeLogs` (`.mjs`). A suíte completa não foi rodada por mim (estava em execução pelo coordenador).

## Correções e 2ª revisão (segundo revisor Opus, 19/10)

Conferi cada achado no código; todos procedem. Veredito após as correções: **APPROVED** (os achados 1 e 2 bloqueavam; 3–10 também foram corrigidos).

| # | Correção | Commit |
|---|---|---|
| 1 | `select app.grant_runtime_access();` no fim de `20261019100000_cron_run_state.sql` (cria `admin_all`/`runtime_all`; o padrão das migrations vizinhas). A migration continua idempotente: `create table if not exists`, e a função só cria policy ausente. Teste de integração com `rpg_admin` real **não** foi feito: não há Postgres local nesta sessão. Validar no `supabase db reset` local ou no apply do staging. | `38e1128` |
| 2 | `body_limit.route_label` agora é fechado: chave de `per_path`, ou template da rota registrada no app (`{param}`→`{id}`; ignora o `Mount` da SPA, que casa qualquer path), ou `other`. O mesmo valor vai no campo `route` do log. O middleware lê as rotas de `scope["app"]`; os 413 internos (stripe/STT) passam `routes=app.routes`. Teste novo: POST de 256 KiB+1 em paths aleatórios produz só `route="other"`, na métrica e no log. | `38e1128` |
| 3 | `ClientErrorReport.route` passa por validator no servidor: segmento hex/uuid ≥ 16 ou só dígitos vira `{id}`. `client.error` sai 1×/min por (`ip_ref`, `kind`, `code`, `error_name`, `route`, `request_id`), com teto global de 600 linhas/min contra IPs distribuídos; a métrica `rpg_client_errors_total` conta tudo. O `request_id` entra na assinatura para não esconder o código de suporte de outra falha. O "plantio" de `request_id` alheio fica aceito: a linha é rotulada `client.error` e nada é escrito fora dela. Testes: route com uuid, repetição amostrada e contada, teto global. | `fb9b457` |
| 4 | `transmit`: `sendBeacon` que lança cai no `fetch keepalive`. O teste antigo ("falha do beacon nunca gera outro beacon") foi ajustado: agora uma tentativa de fetch, rejeição engolida, nada recursa. Teste novo do fallback. | `fb9b457` |
| 5 | `PlayBillingPlugin.fail`: a `debugMessage` no logcat só sai em `BuildConfig.DEBUG`; no objeto para o JS ela continua. Spec 259 (critério e nota) alinhada. Teste estático em `nativeLogs.test.mjs`: toda chamada `Log.*` com `debugMessage` exige `BuildConfig.DEBUG`. O APK não foi recompilado aqui; `BuildConfig` é do mesmo pacote, já usado pela `MainActivity`. | `fb9b457` |
| 6 | `event.proposal_rejected` em `OVERRIDES` de `gen_event_catalog.py` (`reason_code`, `source`, `target_ref`, `type`), com o catálogo regerado (`events.py` + `EVENTOS_DE_LOG.md`). Nenhuma outra entrada mudou. | `eb92d4e` |
| 7 | O trace mecânico só grava dentro do `combat_node`. O coletor do turno (`audit_trace.collecting`) abre o escopo com `recording=False`; o escopo do combate liga a gravação e a restaura ao sair. Passos de storyteller e viagem/clima não entram mais, então a doc "só turnos com conflito" fica verdadeira. Testes novos: (a) passos fora do escopo de combate são ignorados; (b) via `StateGraph` do LangGraph, o contextvar atravessa o executor até `record_turn_trace`. A paridade por seed segue verde. | `eb92d4e` |
| 8 | `_replan_reason` ganhou `arc_finished`, separado de `periodic`, e é calculado antes de `_build_plan`. As continuações colapsadas foram quebradas em `campaign_manager` e `world_validators.reason_code`. | `4eb95ad` |
| 9 | Testes AST percorrem as mensagens reais de recusa (`ValidationResult(False, …)` em `world_validators`/`event_processor` e `{"ok": False, "reason": …}` em `economy`) e exigem que nenhuma caia em `other`. Os prefixos constantes são resolvidos. Hoje todas mapeiam. | `4eb95ad` |
| 10 | Spec de follow-up `specs/SPEC-277-evals-cli-traceback.md` (`draft`, `EVAL_AUTHORING_REQUIRED`), linkada na nota da SPEC-260. O número precisa ser confirmado pelo coordenador no `index.yaml`. O payload de setup do `post_deploy_smoke` ganhou `failed_checks: ["setup"]` + `base_origin`. | `e4d9c2e` |

**Achado extra da 2ª revisão (corrigido em `e4d9c2e`):** `post_deploy_smoke.run` gravava `base_origin` como `scheme://netloc`. Uma URL com `user:senha@` vazaria a credencial no JSON de evidência, que sobe como artifact do CI. Agora sai só `scheme://host[:port]`, com teste.

**Passe próprio — ok:** labels de `provider.attempt` vêm de literais/config fechada (`openai`, `jina`, candidatos STT); o `model` só vai ao log, nunca à métrica. Os novos `record_block` (`metrics`, `audit_export`, `stt`) usam classe literal. O CORS ganhou só os dois headers de build/versão. O body do beacon (20 frames × 120 caracteres) cabe em 4 KiB.

**Pendente:** smoke da migration com `rpg_admin` real (Postgres local ou apply no staging) e build do APK.
