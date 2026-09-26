# SPEC — Gates de integração e regressões da auditoria

> **Status:** `in-progress`
> **Criada:** 2026-09-22 · **Atualizada:** 2026-09-26
> **Aprovação:** usuário pediu “transforma tudo em specs e começa a executar”.
> **Depende de:** Specs da auditoria: gates adicionados incrementalmente, não esperar todas concluírem
> **Desbloqueia:** fechamento da auditoria de consistência e frontend.

## 1. Contexto & Objetivo

A suíte passou 1721 testes enquanto reproduções expuseram falhas nas fronteiras. Build e ausência de overflow horizontal não detectam recorte da arte, identidade perdida ou replay divergente. O CI atual não executa stack/browser autenticados.

## 2. Requisitos

- **R1** — Corpus offline independente cobre bugs da auditoria com positivos/negativos; oráculo não chama o mesmo sanitizador para obter valor esperado.
- **R2** — CI obrigatório: offline + build + testes cliente; CI de integração local provisiona Postgres/auth/storage compatíveis e browser, sem segredos/cloud/pagamento.
- **R3** — Gates medem imagens (bounds/fit), sessão autenticada/SSE, replay, restore da memória e workers longos. Screenshots/JSON de evidência como artifacts sem dados reais.
- **R4** — Gate indisponível é skipped/pending com motivo, nunca passed. Matriz LLM B é aceite global posterior, não substituto de integração curta.
- **R5** — Cronometrar testes e separar smoke de PR de bateria noturna/manual. Não remover testes para melhorar contagem.

### Fora de escopo

Deploy, migração de dados reais, nova campanha paga e mudança de provider. Implementar Python para domínio/infra; TypeScript apenas para interface.

## 3. Design técnico

.github/workflows/validate.yml: separar jobs offline/client/infra-browser; scripts reaproveitáveis Python em scripts/ e marcadores existentes infra_local/browser_local/chaos_local. Adicionar fixtures de estado e respostas provider adversas; tests frontend podem usar Node nativo já disponível ou Playwright Python. Sem adicionar Jest/Vitest apenas para testes de rede se Node resolver. Relatório consolidado JSON com gate, status, duration_ms, evidence_paths, reason.

## 4. Plano passo a passo

1. Cada bug novo recebe reprodução que falha antes do fix.
2. Adicionar smoke UI que detecta cover indevido e overflow interno mesmo quando scrollWidth==clientWidth.
3. Provisionamento local isolado e teardown; rodar jobs reais antes de exigir status no CI.
4. Documentar comandos e atualizar ESTADO_ATUAL/ROADMAP com gates realmente executados.

## 5. Critérios de aceite

- [ ] Offline, build e testes cliente automáticos.
- [ ] Infra/browser executados no CI ou explicitamente pendentes.
- [ ] Artefatos reproduzíveis e matriz B separada.

## 6. Smoke test com LLM real / integração aplicável

Não roda LLM paga no CI. Suíte llm_contract/llm_playtest continua opt-in e com orçamento autorizado.

## 7. Riscos & compatibilidade

Instalações locais baixam dependências mas não contratam serviços. Manter lockfiles. Não declarar “production ready” por contagem de testes.

## Execução — 26/09 (prevalece sobre as pendências históricas)

CI existente agora roda npm test e instala extra postgres. Workflow audit-local separado, manual (workflow_dispatch), provisiona stack/browser e roda scripts/audit_local_gate.py. Runner local final: **25 testes verdes**, zero skip, com JUnit, `summary.json` e screenshots 390/1440 em `readiness_artifacts/audit/`, sem providers pagos. Inclui kill/restart, rollback de arte, disputa simultânea de mutações, resposta tardia e refresh. O teste de corrida encontrou deadlock PostgreSQL por ordem de locks; corrigido com ordem global `game -> operation`. Infra no GitHub ainda não executada nem promovida a gate obrigatório de PR; isso exige autorização para consumir quota do GitHub Actions. Matriz B e contratos pagos continuam separados.
