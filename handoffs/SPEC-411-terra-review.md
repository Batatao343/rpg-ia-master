# SPEC-411 — revisão terra (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sonnet independente · **Data:** 2026-11-11 · **Commit revisado:** `0205b85d` (base `3f89816a`)

## Escopo

`git diff 3f89816a...HEAD` (R6 `2787cc3a`, R2 `5973360e`, R3 `16484218`, R1 `ef6e4a8c`, R4 `0205b85d`).
R5 fora da rodada. Nada em `evals/`, `docs/guias/*`, `AGENTS.md`, `CLAUDE.md` (conferido por `--name-only`).

## Tabela de falha fechada (R1)

Guard: `_truthy(flag)` = valor com strip/lower fora de `{"", "0", "false", "no"}`; marcador: `strip().lower() == "staging"` (igualdade, não prefixo).
Ponto de uso (`infrastructure/google_play_payments.py:36`): `== "1"` estrito.

- flag "1" / "true" / " 1 " / "yes" / "on": guard considera ligada (mais LARGO que o uso) → só falso bloqueio (inofensivo), nunca buraco. Único valor que liga de fato (`"1"`) está sempre coberto.
- flag ausente / "0" / "false" / "no" / vazio: guard não exige marcador; uso também desligado. Consistente.
- marcador ausente, vazio, "production", "prod", "stagingx": recusado (testado). "staging", "Staging", " staging ": aceito; por igualdade após normalização, sem prefixo. Seguro.
- perfis: `hosted` e `hosted-supabase` levantam `ValueError(hosted_config_insecure…)` em `RuntimeConfig.from_env` (runtime.py:292); `portable` exposto levanta por `assert_boot_policy` (runtime.py:676); `legacy`/`local` não passam por `hosted_security_problems` (testado: flag=1 sobe). `is_hardened` fica false com o problema.
- `RPG_ALLOW_INSECURE_HOSTED=1`: pula o raise (runtime.py:292) e deixa `hardened=false`; com flag + sem marcador a compra de teste fica aceita. É comportamento herdado, igual aos outros requisitos: `RPG_ALLOW_INSECURE_HOSTED` está em `FORBIDDEN_IN_HOSTED` (runtime.py:473), logo em `FORBIDDEN_IN_PROD`, e o checklist de release já reprova a presença do NOME em produção. O R1 não abre brecha nova.
- vercel_env: `RPG_DEPLOY_ENV=staging` está em `NON_SECRET_LITERALS` (só `production` dict do script, que é o projeto de staging); teste novo prova ausência no `preview`. Nenhum outro script monta env de produção a partir dele (`grep`: só `vercel_env.py` e `checklist.py` referenciam o mapa).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `scripts/release/checklist.py:56-63, 293` | `check_env_names` não recusa `RPG_DEPLOY_ENV` em produção. Se o env do staging (com o marcador) for copiado para produção, o guard de boot do R1 deixa de proteger. Hoje a flag `RPG_PLAY_ACCEPT_TEST_PURCHASES` continua em `FORBIDDEN_IN_PROD`, então o checklist ainda barra a combinação; a defesa fica de uma camada só. O pedido do dono (checklist recusar o marcador em produção) não foi coberto nem registrado como adiado. | Incluir `"RPG_DEPLOY_ENV"` em `FORBIDDEN_IN_PROD` (o leitor só vê nomes; produção não precisa do marcador) e ampliar o conjunto permitido no `test_requirements_parity_with_release_checklist` (`tests/test_boot_policy.py:~251`) mais um teste de `check_env_names` com o nome presente. |
| P3-1 | P3 | `tests/test_sql_identifier_allowlists.py:~41-50` | Para `account_lifecycle` o teste só valida regex e unicidade; a spec/README dizem que "trava" as tabelas, mas inclusão de nome novo válido passa. Só `_UPDATABLE` é conjunto exato. | Fixar os conjuntos esperados de `PRIVATE_TABLES`/`FINANCIAL_TABLES` como em `KNOWN_UPDATABLE`, ou ajustar o texto da spec/README. |
| P3-2 | P3 | `.github/workflows/validate.yml:~158` | Job `workflow-lint` sem `timeout-minutes` (os demais têm). `permissions: contents: read` herdado do topo; sem contexto perigoso; versões fixadas (zizmor 1.32.0, SHAs). | Adicionar `timeout-minutes: 10`. |
| P3-3 | P3 | `tests/test_boot_policy.py:~465` | Testes não cobrem flag "true"/" 1 " (guard mais largo que o uso). Documenta o falso bloqueio como decisão. | Opcional: um caso parametrizado. |
| P3-4 | P3 | `docs/spec411/README.md:4` | Diz "19 checkouts"; há 20 (9 já tinham + 11 agora, contando os 5 de eval-gates). Cosmético. | Ajustar número. |

Sem P0/P1.

## Verificações por requisito

- R6: `_client_ip` → `services/abuse_policy.client_ip`: com `VERCEL` usa `x-vercel-forwarded-for`/`x-real-ip` (sobrescritos pela plataforma); com `RPG_TRUSTED_PROXY_HOPS=N` usa o N-ésimo valor da DIREITA do XFF; senão `client.host`. Sem proxy confiável o XFF é ignorado, então forjar header não ganha balde novo (testes 3 e 4 provam). Fora da Vercel/sem hops, header forjado não muda nada; piora em relação ao antes: não. Obs.: `except Exception: pass` no helper é pré-existente (não alterado).
- R4b: seleção `S324,S602,S604,S605,S105,S106,S107`; exclusões `tests/**`, `scripts/**`, `evals/**`, `playtest/**`, `.claude/**` (lacuna declarada). `usedforsecurity=False` não altera o digest (conferido: SHA-1 idêntico); em `agents/combat.py` `fate_seed` é `entry["pending_fate"]["seed"].encode()` avaliado depois de `seal_fate` (linha 510), mesma fonte e mesma ordem que antes em ambos os ramos; `import hashlib` movido ao topo sem efeito. `services/scene_cards.py` idem (mesmos bytes). Os 4 `noqa: S105` têm motivo e estão na linha do match. `ruff-baseline.toml`: só remoções (entradas F401/I001 limpas/arquivos removidos); nenhum acréscimo.
- R2/R3/R4a: 20 `actions/checkout` com `persist-credentials: false` (conferido por contagem); nenhum workflow usa `gh`/`git push`/`git pull`. `scripts/ci_eval_scope.py` roda só `git diff-tree`/`git diff base...head` sobre o histórico já buscado (`fetch-depth: 0` no job `scope`), sem credencial; `verify_protected_eval_change.py` não chama git de rede. `dependabot.yml`: `cooldown.default-days: 7` válido nos 3 ecossistemas. `uvx --from zizmor==1.32.0 zizmor .github/workflows/` rodado localmente (modo offline): "No findings" (29 suprimidos pelo próprio zizmor); o modo online do CI pode achar mais, risco aceito.
- `config/flags.yaml`: `RPG_DEPLOY_ENV` registrado (`kind: config`); `.env.example` documentado. Hoje só a flag de compra de teste depende do marcador; escopo não ampliado.
- Funções novas: `_test_purchases_problem` com 8 linhas. Sem helper duplicado novo.

## Correções aplicadas

Nenhuma (revisão só leitura).

## Pendências

P2-1 (recomendo corrigir na própria 411 antes do pouso, é uma linha); P3 opcionais.

## Comandos rodados

```text
pytest -n 2 (19 arquivos: boot_policy, spec192_vercel_env, surfaces_221, abuse_policy, sql_identifier_allowlists, flag_registry, spec197_checklist, spec194_google_play, workflows_contract, size_budget, ruff_protected_exempt, testes de fate/scene_cards/chase) → rc=0, todos verdes
ruff check . → All checks passed
ruff format --check . → só specs/SPEC-410-*.md (já corrigido na main, ignorado)
scripts/dev/size_budget.py → rc=0
zizmor 1.32.0 local → sem achados
```
