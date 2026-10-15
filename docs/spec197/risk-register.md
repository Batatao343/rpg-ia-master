# SPEC-197 - Registro de riscos para o beta pago fechado

Consolida follow-ups e limitacoes conhecidas de SPEC-190..196 (READMEs e reviews). Gate: **zero P0/P1 aberto**
(`scripts/release/checklist.py` le as linhas da tabela abaixo: coluna 2 = severidade, coluna 5 = status; status
`fechado` ou `aceito` fecham a linha). P2 so fecha com **aceite assinado** na secao final. Classificacao feita
honestamente a partir da evidencia dos READMEs; o usuario pode reclassificar, mas deve registrar a razao.

Severidade: P0 = perda de dinheiro/dados ou vazamento ativo; P1 = bloqueia cobrar usuarios reais ou viola
requisito R1-R8 da SPEC-197; P2 = degradacao tolerada com mitigacao conhecida.
Status: `aberto`, `mitigado` (codigo/runbook existe, falta verificar), `fechado` (verificado), `aceito` (P2 assinado).

| ID | Sev | Risco | Dono | Status | Origem | Mitigacao / acao para fechar |
|---|---|---|---|---|---|---|
| R-01 | P1 | Turnstile com chaves de TESTE (always-pass): anti-bot nao validado com token real | usuario + Terra | aberto | 191(c) | Criar site/secret reais no Cloudflare; aplicar `auth_config apply` e `RPG_TURNSTILE_SITE_KEY` em prod; reexecutar `auth_burst_recover` provando 400 sem token e 200 com token real |
| R-02 | P1 | SMTP embutido do Supabase (limite de e-mails, 429 `over_email_send_rate_limit`); `rate_limit_email_sent` nao aplicavel | usuario + Terra | aberto | 191(d), 192, 190 | Configurar SMTP customizado (R4) e aplicar `rate_limit_email_sent`; testar signup+confirmacao+reset ponta a ponta. Alternativa: aceite explicito R4 (so convites, <=N usuarios) |
| R-03 | P1 | Plano Free sem backups gerenciados/PITR; unico mecanismo e export logico manual | usuario | aberto | 191 follow-ups | Producao em plano Pro (backups diarios) ou cron de `backup_restore export` + armazenamento externo; drill de restore (R5) com evidencia |
| R-04 | P1 | Restore nunca testado com wallet/pagamentos nem metadados de owner do Storage | Terra | mitigado | 191(h) | Drill em copia de producao: restaurar wallet/ledger, verificar `verify_restore`, reconciliar saldo; documentar re-upload do Storage **Atualizacao 15/10:** Drill de restore COM wallet/debito feito (staging -> export -> lab zerado -> restore): saldo, soma do ledger e divida identicos, contagens de todas as tabelas `app` iguais (`evidence/restore_wallet.json`). Falta: re-upload de Storage no lab (storage-api 1.69.11 devolve 500/42P10 em qualquer upload apos reset; so checksum do manifest) e repetir em copia de PRODUCAO quando existir (R-07). |
| R-05 | P1 | Role privilegiada (`postgres`) do pooler exposta ao runtime Vercel; RLS so como defesa em profundidade | Terra | aberto | 191(i) | Criar role de login dedicada com menor privilegio (somente `rpg_api` + grants necessarios); trocar `DATABASE_URL` de producao; rodar suite de integracao contra a role |
| R-06 | P1 | Vercel Hobby (plano gratuito, uso nao comercial) nao serve a produto pago | usuario | aberto | 192 medidas | Projeto de producao em Vercel Pro; revisar limites (maxDuration, bundle 500 MB, cron/pg_net) **Atualizacao 15/10:** Medido no staging: `vercel rollback` para algo mais antigo que o deploy anterior falha com 402 "upgrade to pro" no Hobby (`incident_drill.json`). |
| R-07 | P1 | Producao Supabase/Vercel inexistente; org Free tem 2 projetos ativos | usuario | aberto | 197 R1 | Aprovar criacao de projeto prod (Pro ou pausar outro); ver `external-inputs.md` |
| R-08 | P1 | SPEC-194/195/196 ainda `approved` no indice: trabalho nao commitado, sem review Sol, migrations 20261015130000/140000/150000/151000 nao aplicadas ao staging | Terra + Sol | fechado | indice/tree | Commit, CI verde, review Sol, aplicar migrations (`migrations push`), rodar testes Postgres locais (`RPG_TEST_DATABASE_URL`) e smoke staging **Atualizacao 15/10:** SPEC-176..196 `done` no indice, drift de migrations 22/22 sem pendencia (`checklist-*.json`), testes Postgres do lab 194-196 verdes (18 passed), smoke staging de dois usuarios verde (`two_user_smoke.json`). CI/review Sol ficam em R-14. |
| R-09 | P1 | Stripe live nunca exercitado; webhook/reconciliacao so em test mode | usuario + Terra | aberto | 197 R2 | Chaves live + webhook secret; smoke de valor pequeno explicitamente aprovado (valor, SKU, estorno depois); reconciliar ledger |
| R-10 | P1 | Paginas legais (privacidade, termos, reembolso, suporte) nao publicadas; e-mail de suporte indefinido | usuario | aberto | 197 R3 | Revisar rascunhos em `legal/`, definir titular/dominio/contato, publicar URLs, `checklist --legal-url` verde **Atualizacao 15/10:** Paginas /privacidade /termos /reembolso /suporte agora servidas pelo app (build estatico, banner RASCUNHO, links no rodape) com o texto-rascunho; falta o usuario preencher `<...>`, revisar e publicar na URL final. |
| R-11 | P1 | Limites de gasto provider-side (DeepSeek/Groq/Jina/OpenAI/STT/imagem) nao configurados; saldo DeepSeek ja zerou antes (HTTP 402) | usuario | aberto | 197 R7, matriz B | Definir caps nos dashboards (ver `runbooks/budget.md`), alertas de saldo, kill switches testados em staging **Atualizacao 15/10:** Corte automatico diario implementado: `RPG_DAILY_SPEND_CAP_BRL` (sem valor = desligado) liga `image_generation` + `stt_fallback_expensive` via cron finops (ator `system:finops`, auditado, idempotente, nunca religa). Falta o USUARIO: tetos nos dashboards dos provedores + definir o valor do cap; e agendar o cron (R-12). |
| R-12 | P1 | Crons FinOps/watchdog (`/internal/cron/finops`, `finops-watchdog`) e `retry_unconsumed` Google nao agendados | Sonnet | fechado (staging) | 196 F7, 194 | Agendar via `schedule_cron.py`/pg_cron; provar `app.finops_evaluations` fresco e alerta `FinopsEvaluationStale` **Atualizacao 15/10:** O cron finops agora tambem aplica o cap diario; segue sem agendamento no staging/prod (`schedule_cron.py`). **Atualizacao 15/10 (orquestrador):** staging tem `rpg-cron-finops` (horario) e `rpg-cron-reconciliation` (15 min, chama `retry_unconsumed`) ativos em `cron.job`, mais o watchdog `rpg-cron-health`; producao repete o mesmo `schedule_cron.py` ao ser criada. |
| R-13 | P1 | Smoke de dois usuarios com compra web, wallet, texto, voz, quote de imagem, logout/delete nao executado em ambiente de producao | Terra | aberto | 197 R6 | Executar `docs/spec197/runbooks/production-promotion.md` passo "smoke" e anexar evidence **Atualizacao 15/10:** Smoke de 2 usuarios no STAGING verde (isolamento, wallet sync, 2 turnos, quote de imagem, refresh/logout/delete). Nao exercitados: voz (`not_configured`), compra Stripe (`blocked: stripe_test_keys_missing`), geracao de imagem paga. Producao nao existe. |
| R-14 | P1 | Gate de release depende de CI verde do SHA candidato e de aprovacao humana de `eval-governance`/push (token `gh` ja foi invalido) | usuario | aberto | estado 02/10 | Reautenticar `gh`, push, CI verde, approval eval-governance **Atualizacao 15/10:** CI do HEAD 1fe88de esta VERMELHO: `validate` e `eval-gates` falham por `project index is stale` (indice do Project Index precisa ser regenerado no proximo commit). `gh` ja autentica agora; falta approval `eval-governance`. |
| R-15 | P2 | Pooler `aws-1-sa-east-1` com IP intermitente (54.232.77.43): cauda ~3,2 s, 8/60 failovers em 1 run | Terra | mitigado | 191 | Failover em ~3,2 s ja implementado; abrir chamado no suporte Supabase; reexecutar `smoke_ab --per-ip` semanalmente |
| R-16 | P2 | Thread do turno SSE continua apos desconexao; na Vercel pode ser congelada | Terra | mitigado | 192 F3 | Lease + cron `/internal/cron/operations` + retry idempotente por `action_id` (evidencia `sse_disconnect.json`) |
| R-17 | P2 | IP de egress compartilhado nos limites nativos de Auth; `Sb-Forwarded-For` nao enviado | Terra | mitigado | 191(c), 190 | Limiter app-level por usuario/IP + teto nativo; monitorar 429 legitimos |
| R-18 | P2 | Header `X-RPG-Client: android` e declarativo: concede cookie de refresh/CSRF de 14 dias e recusa Stripe; qualquer cliente pode forja-lo | Terra | mitigado | 193, 194 | Politica (nao fronteira de seguranca): forjar so estende a sessao do proprio usuario; revisitar se Stripe-no-Android virar requisito de seguranca |
| R-19 | P2 | Google Play: compra paga recusada com `new_purchases` off fica sem credito (sem estado `held`); reembolso automatico do Play em ~3 dias | Terra | mitigado | 196 F4 | Runbook em `incident.md`: religar o switch antes de 3 dias; app reenvia o token. Estado `held` fica para pos-beta |
| R-20 | P2 | `charge.refund.updated` (refund failed/canceled) nao consumido: claim permanece ate intervencao manual | Terra | mitigado | 195 L1 | `admin_wallet_adjust.py credit --reference <incidente>`; monitorar refunds failed no painel Stripe |
| R-21 | P2 | Orfaos Google (void de order nunca creditada) viram `orphaned`, sem recuperacao automatica | Terra | mitigado | 195 | Revisao manual semanal de `orphaned`; baixo volume no beta |
| R-22 | P2 | Linhas sinteticas de wallet em staging sao append-only e nao removiveis | Terra | mitigado | 191 | Apenas staging; nao migrar para producao **Atualizacao 15/10:** Staging agora tambem retem: pricing version `spec197-restore`/`-b`, SKU, profile de imagem sintetico, cotacoes e ledger do owner sintetico (pseudonimizado; usuario Auth apagado). |
| R-23 | P2 | Cold start ~6 s apos deploy; bundle Python 315 MB (limite 500 MB) | Terra | mitigado | 192 medidas | Aquecer com `/health` apos promote; monitorar tamanho do bundle |
| R-24 | P2 | Evidencias `db_reset_from_zero`, `pgtap`, `restore_verify` sao transcricao manual | Terra | mitigado | 191(g) | Regerar com scripts quando houver CI de staging |
| R-25 | P2 | Dados financeiros pseudonimizados retidos apos exclusao de conta (UUID, wallet, eventos Stripe sanitizados) | usuario | mitigado | 190 | Declarado na politica de privacidade; revisao juridica da base legal (obrigacao legal/fiscal) |
| R-26 | P2 | `check` do microfone (`Permissions-Policy`) exigia redeploy e reteste no WebView | Terra | mitigado | 193 | Cobrir no smoke de voz (R6); fechar apos evidencia |
| R-27 | P2 | Android/Play Billing (SPEC-198) fora do beta web: SKUs Play sem teste real | usuario | mitigado | 194, 198 | Beta pago inicia somente web; Android em internal testing separado |
| R-28 | P2 | Margem por compra e atribuida pro rata por dono, nao por compra individual | Terra | mitigado | 196 | Aceitar para beta; revisar apos 30 dias de dados |

## Aceite de risco P2 (assinar antes de abrir o beta)

Cada linha abaixo vale como aceite do risco P2 correspondente, **somente depois** de o usuario preencher data e
nome. Enquanto vazio, o checklist lista o item em `p2_awaiting_acceptance`.

| ID | Texto do aceite | Assinado por | Data |
|---|---|---|---|
| R-15 | Aceito cauda de latencia de ate ~3,2 s do pooler com failover automatico. | | |
| R-16 | Aceito que turnos SSE interrompidos dependam de retry idempotente/cron para concluir. | | |
| R-17 | Aceito limites nativos de Auth compartilhados por egress, com limiter proprio por usuario/IP. | | |
| R-18 | Aceito que `X-RPG-Client: android` seja politica declarativa, nao controle de seguranca. | | |
| R-19 | Aceito reembolso automatico do Google (~3 dias) para compra paga durante `new_purchases` off. | | |
| R-20 | Aceito reversao manual de refund Stripe failed/canceled. | | |
| R-21 | Aceito revisao manual de orfaos Google. | | |
| R-22 | Aceito residuo sintetico apenas em staging. | | |
| R-23 | Aceito cold start de ~6 s apos deploy. | | |
| R-24 | Aceito evidencias manuais ate haver CI de staging. | | |
| R-25 | Aceito retencao pseudonimizada do ledger apos exclusao, conforme politica de privacidade. | | |
| R-26 | Aceito fechar apos o smoke de voz da R6. | | |
| R-27 | Aceito beta somente web; Android fora do escopo. | | |
| R-28 | Aceito atribuicao pro rata de margem durante o beta. | | |

Ao fechar uma linha P2 como `aceito` na tabela principal, copie aqui a assinatura. Linhas P1 nao podem ser
aceitas: devem ser `fechado` com evidencia (excecao: R-02, onde a SPEC-197 R4 permite "risco aceito
explicitamente"; nesse caso registrar no campo Mitigacao e mudar o status para `aceito`).
