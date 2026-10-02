# Plano de Evals + Project Index — RPG IA / Valoria (v4)

Pacote de migração **deterministic-first** para `Batatao343/rpg-ia-master`.

## Âncora observada

- branch: `main`
- SHA observado: `b3dcc19da1768fd11f391a13b301124c825ad6e7`
- workflow `validate`: success em 26/09/2026
- long-run: sempre opt-in

## O que mudou na v4

1. novas specs passam a usar a sequência **SPEC-163 -> SPEC-175**;
2. SPEC-163 normaliza retrospectivamente as 162 specs anteriores e cria `specs/index.yaml`;
3. model routing vira política executável: **Luna para mecânico/volume, Terra como executor padrão, Sol para complexidade/review, Astra só para checkpoints conceituais críticos**;
4. nenhum SPEC-176 é reservado antes da baseline;
5. long-run continua fora dos gates automáticos.

## Ordem de leitura para o coding agent

1. `START_HERE_PROMPT.md`
2. `SPEC_EXECUTION_ORDER.md`
3. `12_MODEL_EXECUTION_POLICY.md`
4. `00_ESTADO_ATUAL.md`
5. `00_AGENTS_MD_UPDATE.md`
6. `01_PRINCIPIOS_E_GOVERNANCA.md`
7. `02_ARQUITETURA_ALVO.md`
8. `03_METRICAS_BACKEND_IA.md`
9. `04_DATASETS_E_ORACULOS.md`
10. `05_FRONTEND_EVALS.md`
11. `06_CI_CD_E_GATES.md`
12. `07_ROADMAP_PASSO_A_PASSO.md`
13. `08_CONTRATO_CODING_AGENT.md`
14. `11_INDEXACAO_REPO_E_GRAFOS.md`
15. `09_REFERENCIAS.md`
16. `10_CHECKLIST_APROVACAO.md`

Depois disso, executar `specs/163-...` em ordem estrita.

## Princípios

- source code é a verdade; index é navegação;
- evaluator não pode ser alterado para fazer candidato passar;
- métricas determinísticas têm precedência sobre judges;
- baseline antes de target;
- project index precisa provar valor no próprio Valoria;
- reorganização física de pastas fica para depois da baseline/benchmark;
- usar o **menor modelo suficiente**, e não o maior por padrão;
- review model nunca substitui gate executável;
- long-run somente com autorização explícita do usuário ou futura spec explicitamente aprovada.
