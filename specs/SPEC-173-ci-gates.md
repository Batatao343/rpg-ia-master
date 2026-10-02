# SPEC-173 — CI, Protected Gates e Execução Seletiva

> **Status:** `done`
> **Depende de:** SPEC-172 `done`
> **Modelo executor mínimo:** Terra Medium/High
> **Revisão:** Sol se a semântica de segurança/protected paths mudar

## Entregas

- PR deterministic gate;
- path-selective backend/frontend evals;
- holdout privado fora do repo público;
- real-provider short gate manual/protected;
- artifacts para debugging;
- post-deploy smoke parametrizado.

## Proibição

Nenhum workflow automático executa 100/200-turn ou matriz 10x200.

## Model routing

Luna pode gerar reports/artifact indexes. Terra implementa workflows. Se protected-path bypass, secrets, permissions ou trust boundary forem alterados, revisão Sol obrigatória.

## Aceite

- [x] long-run ausente dos required gates;
- [x] protected evaluator/datasets não podem ser silenciosamente alterados;
- [x] failures não viram pass por unavailable dependency;
- [x] artifacts incluem manifest compatível.

## Execução — 2026-09-30

- Aprovada pelo pedido do usuário para executar as specs draft em ordem, com
  SPEC-104 cloud mantida on hold.
- Implementação iniciada após SPEC-172 `done` e seus gates offline/browser.
- `.github/workflows/eval-gates.yml` executa governança/index/harness e os sete
  suites determinísticos de produto; paths relevantes ativam jobs curtos de
  backend e frontend. Nenhum required gate usa provider real, `--real`, 100/200
  turnos ou matriz longa.
- Mudanças em paths protegidos ativam `eval-governance`, exigem reviewer do
  GitHub Environment e `EVALUATOR_CHANGE_APPROVED=true`. Falta de artifact,
  dependência, chave ou aggregate válido falha fechado.
- `.github/workflows/eval-protected.yml` oferece somente execuções manuais:
  contrato real curto com teto duro pré-request de 20 chamadas/US$ 0,20 e
  holdout em repositório privado com export apenas agregado. O gate pago não
  foi executado nesta spec.
- `post-deploy-smoke.yml` é manual, read-only, exige HTTPS e confere o SHA
  exposto por `/health`; não cria jogo nem chama LLM.
- Evidência local: governança com 6 datasets; calibração 25/25; sete suites de
  produto verdes (`exact_match`, routing, state, context e claims nos gates);
  frontend artifact 16/16 com identidade compatível; playtest offline 14 perfis
  x 3 turnos com zero erro/violação. O executor de budget e os contratos CI
  passaram nos testes focados. Zero provider pago, cloud ou long-run.
