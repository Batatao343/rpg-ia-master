# SPEC-269 — Apagar símbolos e módulos mortos de infraestrutura

> **Status:** `done` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES (`file_blob.py` e `sweep_synthetic_users` saem da lista; ver §8)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** —
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Mesmo método da SPEC-268, aplicado a `infrastructure/`, `observability/`, `services/` de
plataforma e `scripts/staging/`. Itens com **zero** referência fora da definição:

| Item | Local | Linhas |
|---|---|---|
| módulo `infrastructure/testing.py` (`WriteRecorder`): nenhum import em código nem em teste | arquivo inteiro | 27 |
| `FinopsReader` (Protocol com uma implementação real + um fake) | `infrastructure/finops_reader.py:31` | 9 |
| `ensure_binary_stream`, `require_unique_document_ids` | `infrastructure/contracts.py:309,329` | ~8 |
| `PersistenceUnavailable` | `infrastructure/contracts.py:95` | 2 |
| `timeline_scope`, `MARKS` | `observability/latency.py:274,41` | ~7 |
| `NO_SPEND_SQL` | `infrastructure/usage_events.py:46` | 1 |
| `GOOGLE_STATE_RETAINED_KEYS` | `infrastructure/account_lifecycle.py:27` | 1 |
| `STRIPE_STATES`, `GOOGLE_STATES` | `services/purchase_reconciliation.py:13,15` | 3 |
| `EXTRA_ERROR_CODES` | `services/audit_trace.py:39` | 2 |
| `DAILY_CLASSES` | `services/abuse_policy.py:49` | 1 |
| `SHARD_MILLI_PER_SHARD` | `services/shard_pricing.py:21` | 1 |

Total estimado: **~62 linhas**, 1 arquivo a menos.

*(revisão 2026-10-18)* Removidos da lista: `infrastructure/file_blob.py` **é importado por 5
testes** (`test_blob_contract.py:10`, `test_dynamic_art_jobs.py:4`, `test_dynamic_art_local.py:9`,
`test_game_delete_purges_blobs.py:75`, `test_image_quotes_local.py:13`) e o docstring o declara "nome
estável do adapter BlobStore em filesystem"; apagar quebra a coleta da suíte. `sweep_synthetic_users`
é ferramenta manual de limpeza do staging ("após erro de transporte no meio do run"), mesma
categoria de `scripts/staging/*` que o relatório manda preservar.

**Fica de fora, de propósito:** `wallet_spend_scope` (`infrastructure/wallet.py:687`), que
não tem chamador hoje mas é o gancho planejado para ligar reserve→settle às jogadas
(pendência da SPEC-185); os adapters `portable`/OIDC/S3 (perfil documentado e suportado).

## 2. Requisitos

- **R1** — Mesmo R1 da SPEC-268 (grep registrado, inclusive SQL em `supabase/` e strings).
- **R2** — As constantes de estado (`STRIPE_STATES`, `GOOGLE_STATES`) podem estar ali como
  documentação da máquina de estados: se o revisor achar que documentam algo que o SQL
  impõe, trocar por um comentário de uma linha em vez de apagar sem rastro.
- **R2b** *(revisão)* — `infrastructure/testing.py` é citado como fonte de fakes por SPEC-235:47
  (`done`) e SPEC-236:19 (`in-progress`), mas nenhum teste o importa (os testes usam
  `infrastructure.local_adapters`). Pode sair; registrar no PR que a citação da SPEC-236 é
  descritiva e não dependência de código.
- **R3** — `docs/descricao_projeto/fontes/exploracao/explore_05_infra.md` cita
  `PersistenceUnavailable`/`require_unique_document_ids`: atualizar a frase ou deixar
  (é retrato histórico); não criar link quebrado.

## 3–4. Design e plano

Remoção; `uv run ruff check .`; suíte.

## 5. Critérios de aceite

- [ ] `uv run ruff check .` e `uv run pytest` verdes
- [ ] `uv run pytest -m infra_local` verde com a stack local, se disponível (senão registrar "não rodado")
- [ ] `scripts/vercel_bundle_check.py` sem crescimento
- [ ] Project Index regenerado em checkout limpo

## 6. Smoke

`/health` e `/metrics` (com token) no uvicorn local.

## 7. Riscos & compatibilidade

Risco **baixo**. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES.**

Achados:
1. **`infrastructure/file_blob.py` é importado por 5 testes** (`tests/test_blob_contract.py:10`,
   `test_dynamic_art_jobs.py:4`, `test_dynamic_art_local.py:9`, `test_game_delete_purges_blobs.py:75`,
   `test_image_quotes_local.py:13`). A afirmação "ninguém importa" do relatório está errada; apagar quebraria a
   coleta do pytest. Saiu da lista.
2. `sweep_synthetic_users` é ferramenta manual de limpeza do staging (usuários `spec192-*` órfãos após erro de
   transporte); mesma classe de `scripts/staging/*` que o relatório preserva. Saiu da lista.
3. `infrastructure/testing.py` é citado como fonte de fakes por SPEC-235 (`done`) e SPEC-236 (`in-progress`),
   mas nenhum teste o importa; pode sair (R2b).
4. `timeline_scope`: o contexto de latência tem outro setter (`observability/latency.py:294`), então apagar
   não desliga a instrumentação da SPEC-200.
- Demais itens confirmados com `git grep -nw` (inclusive `supabase/`, SQL e strings): só a definição.
