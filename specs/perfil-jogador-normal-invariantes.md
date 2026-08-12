# SPEC — Perfil Jogador Normal, invariantes e SLOs

> **Status:** `done`
> **Criada:** 2026-08-12 · **Atualizada:** 2026-08-12
> **Depende de:** Fase 5 (`done`) e cinco correções deste pacote
> **Desbloqueia:** regressão longa representativa de comportamento humano

---

## 1. Contexto & Objetivo

Os perfis existentes são especializados. O diagnóstico precisou de um script
ad hoc para alternar exploração, conversa, combate, descanso, comércio, viagem,
fuga e progressão. Esta spec transforma essa jornada em cobertura permanente e
adiciona observabilidade para os bugs encontrados.

## 2. Requisitos

- **R1** — Registrar `normal` em `PROFILES` e incluí-lo em `--all`.
- **R2** — O perfil deve alternar objetivos, explorar, conversar, viajar, lutar, fugir/curar sob risco, descansar e interagir com loot/comércio.
- **R3** — O runner deve resolver escolhas pendentes do perfil por APIs determinísticas de progressão e registrar as escolhas.
- **R4** — Invariantes devem cobrir resumo, grounding regional, fuga progressiva e contradição de recompensa.
- **R5** — Turnos reais acima de 45 s geram warning de SLO; acima de 90 s geram error.
- **R6** — Telemetria agregada deve contar violações de latência e diversidade de rotas/ações.

### Fora de escopo

Usar um segundo LLM como jogador, alterar preços/providers ou tornar warnings de latência bloqueantes no mock.

## 3. Design técnico

- **`playtest/profiles.py`** — `NormalProfile` determinístico e stateful por campanha.
- **`playtest/runner.py`** — aplicar escolhas de progressão opt-in e registrar `progression_choices`.
- **`playtest/invariants.py`** — checks adicionais com contexto de decisão/latência.
- **`playtest/telemetry.py`** — métricas de diversidade e SLO no summary.
- **`tests/test_perfil_normal_invariantes.py`** — política, escolhas, checks e agregação.

## 4. Plano passo a passo

1. **Testes:** provar variedade e reação a estados de risco/cena.
2. **Implementação:** perfil `normal` e reset por campanha.
3. **Testes:** escolhas pendentes, novos invariantes e limiares de latência.
4. **Implementação:** integração no runner e summary.
5. **Verificação:** campanha mock de 50 turnos e suíte completa.

## 5. Critérios de aceite

- [x] `uv run python -m playtest run --profile normal --turns 50` completa offline.
- [x] Perfil exercita ao menos três rotas numa campanha longa determinística.
- [x] Escolhas pendentes não ficam abandonadas.
- [x] Warnings/errors de SLO aparecem nos limites corretos.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Nenhum structured output/LLM novo.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. Rodar `normal` por 30–40 turnos com teto de custo/request.
2. Gerar report e inspecionar diversidade, SLOs e zero violações de erro funcionais.

Aceites: mock `20260812-172231-913670` (50/50, quatro rotas, três escolhas,
0 erro/violação) e real `20260812-172526-505951` (5/5, quatro rotas, p95 37,3 s,
US$ 0,00686, 0 erro/violação).

## 7. Riscos & compatibilidade

O perfil é determinístico dado o seed, mas a campanha real varia com o provider. O SLO usa warning entre 45–90 s para não mascarar correção funcional.
