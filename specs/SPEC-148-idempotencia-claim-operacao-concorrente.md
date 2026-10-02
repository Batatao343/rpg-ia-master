# SPEC — Claim idempotente sob disputa multiprocesso

> **Status:** `done` (2026-08-28 — regressão offline + `infra_local` 13/13)
> **Criada:** 2026-08-28 · **Atualizada:** 2026-08-28
> **Depende de:** `fase-10b-turnos-duraveis-concorrencia-fila`
> **Desbloqueia:** gate `infra_local` da latência e matriz B

---

## 1. Contexto & Objetivo

O gate local de 2026-08-28 reproduziu uma corrida em que dois processos fazem
claim do mesmo `operation_id`. O `ON CONFLICT (id)` cobria a chave primária, mas
o schema também possuía a restrição redundante `(owner_id, id)`; o segundo
insert podia falhar nessa outra restrição com `UniqueViolation`, em vez de
convergir para `LeaseHeld`/recibo idempotente.

O objetivo é tornar o insert tolerante a qualquer conflito único e remover a
restrição redundante, preservando a validação posterior de owner, hash e payload.

## 2. Requisitos

- **R1** — O insert do claim usa `ON CONFLICT DO NOTHING`, sem alvo restrito.
- **R2** — Após conflito, o registro é lido com lock e owner/hash/operação são
  comparados antes de devolver estado idempotente.
- **R3** — Migration aditiva remove somente `operations_owner_id_id_key`; a PK
  global de `operations.id` permanece.
- **R4** — Dois processos com o mesmo ID produzem um commit e um duplicate com
  exatamente um turno e um recibo.

### Fora de escopo

- Trocar o formato do operation ID ou a política de lease.
- Alterar filas, rate limit ou schemas HTTP.

## 3. Design técnico

- `infrastructure/postgres_turns.py`: conflito sem target; validação existente
  continua sendo a autoridade após o insert.
- `supabase/migrations/20260828163000_drop_redundant_operations_unique.sql`:
  drop idempotente da unique redundante.
- Teste offline protege o contrato SQL; `test_multiworker_local.py` prova a
  corrida em Postgres real local.

## 4. Plano passo a passo

1. Escrever regressão offline para o statement de claim.
2. Alterar o insert e adicionar migration aditiva.
3. Reexecutar o teste multiprocesso e todo `infra_local`.
4. Rodar a suíte completa.

## 5. Critérios de aceite

- [x] Regressão offline passa e falharia com `ON CONFLICT (id)`.
- [x] Migration preserva PK e remove a unique redundante.
- [x] `infra_local` multiprocesso produz um commit + um duplicate.
- [x] Suíte completa offline verde.
- [x] Guard de FallbackLLM: N/A; nenhuma chamada LLM.
- [x] Saves antigos: N/A; mudança restrita ao adapter Postgres.

## 6. Smoke real

Não usa LLM. O smoke obrigatório é o teste multiprocesso contra Supabase local.

## 7. Riscos & compatibilidade

`ON CONFLICT DO NOTHING` pode cobrir uma unique futura, mas nenhuma colisão é
aceita silenciosamente: o select/lock posterior compara owner, hash, game, kind
e versão base e falha fechado em divergência.
