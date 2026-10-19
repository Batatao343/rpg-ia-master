# SPEC-176 — Evals de UX e regressões do playtest / contrato JEV

> **Status:** `draft` · **Criada:** 2026-10-12 · **Prioridade:** P0  
> **Depende de:** SPEC-175 `done` · **Desbloqueia:** SPEC-177, 178, 179, 182  
> **Princípio:** construir e congelar a régua antes de corrigir produto.

## 1. Contexto & objetivo

Os evals atuais (`evals/`, F01–F16 em `web/e2e/`) são importantes, mas o último playtest encontrou falhas de percepção, continuidade, recuperação de SSE e progressão de combate não representadas pelos fixtures. Precisamos converter relatos reais em reproduções mensuráveis, separando oráculos determinísticos de avaliação de narrativa. O usuário pediu também retestar o **JEV**; o runner referente à sigla não foi localizado na árvore inspecionada, então o mapeamento JEV é um bloqueio explícito de integração, não uma execução presumida.

## 2. Requisitos

- **R1:** estabelecer dataset imutável de regressões do playtest contendo contexto de entrada, estado canônico, ação, resultado esperado e regra de falha; nunca depender só da saída literária de LLM.
- **R2:** cobrir destinatário narrador/NPC, speaker_id errado, gênero persistente, relação temporal expulsão→convite, bandido/corvo no elenco, ações básicas disponíveis, passivas e reações visíveis, vitória que libera o modo combate, XP somente UI, início de aventura causal, 0-dano suspeito e recuperação de SSE interrompido.
- **R3:** medir `action_ack_ms`, `first_narrative_ms`, `committed_state_ms`, p50/p95 por rota, chamadas/provider/fallback e percentual de operação retomada sem duplicação.
- **R4:** estender matriz frontend F17–F24 (p. ex. F17 combat-mode, F18 basic-action, F19 encounter-roster, F20 victory-transition, F21 people-dossier, F22 recipient, F23 stream-recovery, F24 passives/reactions), incluindo 320/390/768/1440 e a11y.
- **R5:** identificar ferramenta/comando/dataset que o time chama **JEV** antes de produzir score JEV. Registrar versão, provedor, conjunto, seed, custo e produto SHA. Se não identificável, reportar `JEV_RUNNER_UNRESOLVED`.
- **R6:** não alterar os evals/datasets/expected congelados durante uma tarefa de otimização de produto. Esta spec é exclusivamente de avaliação.

## 3. Design técnico

Arquivos-alvo: novos fixtures em `evals/datasets/regression/` **em tarefa de régua isolada**; eventual adapter versionado em `evals/core/adapters.py`; métricas em `evals/metrics-registry.yaml`; casos `web/e2e/critical-journeys.yaml` e `web/e2e/critical-journeys.spec.ts`; documentação de JEV em `docs/`. Toda mudança de avaliador requer versionamento, governance lock e revisão independente conforme `docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md`. A versão de avaliação deve ser congelada antes das SPEC-177+.

Exemplo de oráculo: `given combat.active=true, final_enemy_hp=1; when card_kill; expect combat.active=false, combat_outcome=victory, exit_controls_visible, xp_not_in_prose`. Outro: após SSE/timeout, reenviar consulta do **mesmo** `action_id` não incrementa `turn_count` duas vezes.

## 4. Etapas (testes primeiro)

1. Definir 12–20 fixtures known-good/known-bad e provar que cada caso detecta ao menos uma mutação deliberadamente ruim.
2. Criar novos casos Playwright F17–F24 com API determinística; falhar na branch atual onde o bug é real, sem modificar produto.
3. Registrar baselines, revisão da semântica da régua e lock; mapear JEV ou registrar bloqueio.
4. Após implementação de produto por outras specs, repetir os mesmos casos e comparar versões compatíveis; JEV real só com runner reconhecido, credenciais/custo autorizados.

## 5. Aceite

- [ ] Cobertura declarada de todos os relatos do playtest, com oráculo ou classificação `manual/qualitativo` explícita.
- [ ] Fixtures bons aprovados, ruins reprovados; avaliações de regras sem LLM-as-judge substitutivo.
- [ ] Nenhuma exclusão/denominador oculto; SHA do produto e hash do dataset registrados.
- [ ] F01–F16 continuam passando; F17–F24 exercitados.
- [ ] JEV identificado e rerun reproduzível, **ou** bloqueio documental explícito.
- [ ] `uv run pytest` e `cd web && npm run test:e2e` verdes na execução futura.

## 6. Smoke real e riscos

Smoke real dirigido 3–5 ações por cenário após autorização e orçamento; não lançar automaticamente campanha longa ou matriz 10×200. Risco principal: tentar adaptar o expected à implementação. A regra é congelar o avaliador antes da correção.
