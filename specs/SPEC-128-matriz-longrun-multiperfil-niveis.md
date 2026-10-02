# SPEC — Matriz longrun multiperfil e multinível

> **Status:** `done` — B encerrada em 1.951/2.000 por dispensa explícita do usuário após consumo do saldo DeepSeek.
> **Criada:** 2026-08-20 · **Atualizada:** 2026-09-17
> **Depende de:** `remediacao-playtest-comerciante-real`
> **Desbloqueia:** ciclo pareado de remediação e regressão 10×200 + 10×200

---

## 1. Contexto & Objetivo

O harness só inicia personagens no nível 1. O ciclo solicitado exige dez
campanhas reais de 200 turnos com perfis e níveis variados, correção de todos os
achados e uma segunda matriz pareada que prove as correções sem introduzir erros
novos. Esta spec torna nível inicial um parâmetro determinístico e registra a
matriz como um único experimento comparável.

## 2. Requisitos

- **R1 — Nível inicial real:** `start_level` aceita 1–20. O personagem nasce no
  nível 1 e recebe XP acumulado canônico via `progression.grant_xp`; não há edição
  direta de atributos, Entropia, escolhas, Ápice ou subclasse.
- **R2 — Build completa:** antes do prólogo, o harness resolve deterministicamente
  todas as escolhas possíveis, prepara Cartas válidas até o limite e garante
  subclasse no nível 3+, Carta tardia preparada no nível 9+ e Ápice no 20.
- **R3 — Evidência:** JSONL, summary e manifesto registram nível inicial, classe,
  nível final, escolhas, provider/modelo/custo e completude por campanha.
- **R4 — Matriz A:** 10 perfis únicos, cinco classes e níveis
  `1,3,5,7,9,11,13,15,18,20`, todos com 200 turnos, `mock=false`, invariantes e
  watchdog. Seeds são fixas e versionadas.
- **R5 — Cobertura:** matriz:

  | # | Perfil | Classe | Nível | Seed |
  |---:|---|---|---:|---:|
  | 1 | normal | Devoto do Abismo | 1 | 6200 |
  | 2 | explorador | Arcanista Cinzento | 3 | 6201 |
  | 3 | diplomatico | Médico de Campo | 5 | 6202 |
  | 4 | combate | Sangromante | 7 | 6203 |
  | 5 | comerciante | Corruptor | 9 | 6204 |
  | 6 | quester | Devoto do Abismo | 11 | 6205 |
  | 7 | recrutador | Médico de Campo | 13 | 6206 |
  | 8 | fujao | Arcanista Cinzento | 15 | 6207 |
  | 9 | secret_rusher | Corruptor | 18 | 6208 |
  | 10 | loot_abuser | Sangromante | 20 | 6209 |

- **R6 — Tetos:** CLI real exige `--max-requests` e `--max-cost` positivos por
  campanha e mostra o teto agregado antes de iniciar. Nenhuma imagem é gerada.
- **R7 — Relatório A:** agrega erros, warnings, terminais LLM, latência,
  continuidade, combate, progressão, economia, memória, diversidade e uma
  amostra narrativa estratificada. Todo achado vira spec aprovada antes do fix.
- **R8 — Matriz B pareada:** após os fixes, repete exatamente perfis/classes/
  níveis/seeds/tetos da matriz A. O relatório compara A↔B por campanha e total.
- **R9 — Stop condition:** erro novo, invariante nova, terminal LLM novo,
  regressão de completude ou correção não comprovada na matriz B interrompe o
  ciclo sem terceira rodada/correção automática; decisão volta ao usuário.

### Fora de escopo

- Paralelizar chamadas reais ou mudar preços/dificuldade entre A e B.
- Aceitar campanha parcial como equivalente a 200 turnos.
- Usar MockLLM como evidência final.

## 3. Design técnico

- `playtest/runner.py`: `run_campaign(..., start_level=1)` e seeding por APIs de
  progressão; `CampaignResult.start_level`.
- `playtest/__main__.py`: `--start-level` em `run` e comando `matrix-suite` com a
  tabela fixa, caps por campanha e `--baseline` para B.
- `playtest/telemetry.py`/`report.py`: nível inicial e comparação pareada.
- `tests/test_playtest_start_levels.py`: níveis 1/3/9/20, subclasse, tier tardio,
  Ápice, argumentos inválidos e manifesto.

## 4. Plano passo a passo

### Etapa 1 — Seeding multinível

1. **Testes:** builds 1/3/9/20 usam XP/curvas/escolhas canônicas.
2. **Implementação:** grant de XP + resolução/preparo determinísticos.
3. **Verificação:** testes de progressão e harness verdes.

### Etapa 2 — Orquestrador e telemetria

1. **Testes:** matriz exata, caps obrigatórios, manifestos completos e baseline.
2. **Implementação:** `matrix-suite`, persistência e relatório pareado.
3. **Verificação:** matriz curta MockLLM 10×3.

### Etapa 3 — Ciclo real A/B

1. Rodar A 10×200, produzir relatório e specs de achados.
2. Implementar specs, suíte completa verde.
3. Rodar B 10×200 pareada; aplicar R9 sem exceção.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

`stop_on_error=True` encerra a campanha no primeiro turno com erro/invariante
`error`, preservando a evidência. O orquestrador não inicia o próximo par após
erro, incompletude ou falha de observabilidade. O harness comum mantém coleta
contínua por compatibilidade. Warnings ficam visíveis e requerem revisão.
Fixtures provam a interrupção sem requests; B integral e relatório A/B continuam
sendo a entrega real desta spec. Plano no
[adendo pré-matriz](SPEC-162-remediacao-local-contratos-pre-matriz.md).

- [x] Níveis 1/3/9/20 têm builds coerentes e sem escolhas essenciais pendentes.
- [x] Matriz curta offline 10×3 completa e manifesta os dez pares.
- [x] Matriz A real completa 10×200 e gera relatório curado.
- [x] Todos os achados A viraram specs e foram executados offline.
- [x] Matriz B real cobriu 1.951/2.000 turnos; o usuário dispensou a repetição
  integral do par 10 após o saldo real de US$ 5 ser consumido.
- [x] Zero violação funcional `error` nos 1.951 turnos; warnings e limitações
  foram revisados e registrados no relatório final.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Saves normais e CLI sem `--start-level` preservam nível 1.

## 6. Smoke test com LLM real

**Revisão 17/09:** o run B `20260831-172359-833976` parou em 751/2.000 turnos
com HTTP 402 DeepSeek. A retomada de 16/09 falhou no preflight pelo mesmo motivo.
Após os fixes adicionais, B deve reiniciar do par 1; campanhas parciais anteriores
são histórico, não aceite do build atual. O smoke offline 10×3 de 17/09 passou
sem erros/violações (`20260917-112524-245088`). Detalhes e comando em
[fechamento local](../docs/fechamento-local-2026-09-17.md).

A própria matriz A é o smoke de descoberta e a B é o smoke de regressão. Cada
campanha deve registrar `mock=false`, pelo menos um sucesso de rede no startup e
zero invocação terminal.

## 7. Riscos & compatibilidade

- Custo máximo planejado com US$ 0,25/campanha: US$ 2,50 por matriz e US$ 5,00
  no ciclo A+B; consumo histórico esperado é menor.
- Execução é sequencial para não disputar quota nem caches runtime.
- O seeding usa APIs públicas de progressão e não altera saves existentes.

## Execução B — 2026-09-27/28

A B atual executou **1.951/2.000 turnos válidos** nos runs
`20260927-214549-731406` e `20260928-084057-102826`. As campanhas 1–9
completaram 200 turnos cada, com zero erros, zero violações `error` e zero
invocações LLM terminais. A campanha 10 parou no turno 151 por HTTP 402
`Insufficient Balance`; faltaram 49 turnos observados, mas o aceite exige
repetir o par 10 inteiro desde o turno zero. Em 28/09, o usuário dispensou essa
repetição após informar que os US$ 5 adicionados foram consumidos; a evidência
parcial foi aceita conscientemente como fechamento desta spec.

O custo estimado acumulado foi US$ 1,17628 em 4.201 requests, incluindo
tentativas de rede/provider que falharam. Os 14 warnings observados são todos
`narrative.repeated_opening`, contra 193 na matriz A; a decisão final exige a
campanha 10 completa para uma certificação estrita, limitação aceita no
fechamento. Evidência detalhada:
[matriz B de 28/09](../docs/playtest-matriz-b-2026-09-28.md).
