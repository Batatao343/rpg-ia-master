# SPEC — Smokes dirigidos de recrutamento e comércio

> **Status:** `done` (2026-08-03 — dois oráculos reais verdes)
> **Criada:** 2026-08-03 · **Atualizada:** 2026-08-03
> **Depende de:** `aliados-em-combate`, Fase 4.4 (`done`)
> **Desbloqueia:** aceite real observável das duas verticais

---

## 1. Contexto & Objetivo

Na matriz real, o recrutador passou 30 turnos sem aliado e o comerciante
terminou com o ouro inicial. As unidades provam a fiação, mas o smoke dependia
de o mundo sortear as pré-condições adequadas.

Esta spec acrescenta cenários do harness que preparam estado canônico mínimo,
executam uma ação explícita e falham se o efeito mecânico não aparecer.

## 2. Requisitos

- **R1** — cenário `recrutamento` inicia com NPC conhecido, em cena, não hostil
  e acima do gate de relação; ação pede sua entrada no grupo.
- **R2** — oráculo exige esse NPC na party ativa ao final.
- **R3** — cenário `comercio` inicia em local com mercador, estoque de poção,
  ouro suficiente e baseline de inventário conhecido; ação compra uma poção.
- **R4** — oráculo exige ouro reduzido e poção adicionada.
- **R5** — falha de oráculo vira violação `error`, persiste em JSONL/summary e
  faz a CLI retornar código não-zero.
- **R6** — a CLI aceita `--scenario recrutamento|comercio`; perfis normais e
  `--all` não mudam.

### Fora de escopo

- Tornar recrutamento ou comércio automáticos no jogo.
- Balancear preços/relação ou adicionar UI.
- Incluir os cenários dirigidos na matriz `--all` paga.

## 3. Design técnico

- `playtest/scenarios.py` — catálogo, mutadores, ações e oráculos puros.
- `playtest/runner.py` — parâmetro opcional `scenario`, aplicação após startup e
  auditoria ao final.
- `playtest/__main__.py` — seleção mutuamente exclusiva do cenário.
- `tests/test_playtest_scenarios.py` — preparação, ações, oráculos e integração.

## 4. Plano passo a passo

### Etapa 1 — cenários puros

1. **Testes primeiro:** fixtures cumprem gates; ação é inequívoca; oráculo passa
   e falha nos estados correspondentes.
2. **Implementação:** catálogo fechado em `playtest/scenarios.py`.
3. **Verificação:** testes unitários.

### Etapa 2 — runner e CLI

1. **Testes primeiro:** cenário offline percorre o grafo e falha alto se não
   observar efeito; parser aceita ambos.
2. **Implementação:** runner, telemetria e CLI.
3. **Verificação:** dois smokes reais de um turno.

## 5. Critérios de aceite

- [x] R1–R6 cobertos por testes.
- [x] Recrutamento real adiciona o NPC esperado.
- [x] Comércio real altera ouro e inventário como esperado.
- [x] `uv run pytest` verde (1377 passed, 1 skipped, 14 deselected).
- [x] Guards de structured output existentes preservados.
- [x] Saves antigos continuam carregando.

## 6. Smoke test com LLM real

1. `uv run python -m playtest run --scenario recrutamento --turns 1 --real`.
2. `uv run python -m playtest run --scenario comercio --turns 1 --real`.
3. Ambos: zero erro/violação `error`, `mock=false` e oráculo satisfeito.

## 7. Riscos & compatibilidade

- Cenários usam IDs reais (`na_anel_dourado`, `pocao_cura`) e são validados
  contra os mesmos serviços do jogo.
- Não entram em `--all`, portanto não aumentam custo de regressão comum.
- Duas campanhas de um turno adicionam apenas o custo do smoke opt-in.

## 8. Evidência de conclusão

- Recrutamento `20260803-114339-651827`: Brunna Ponte-Alta entrou na party;
  1/1, `mock=false`, zero erro/violação, US$ 0,0021.
- Comércio `20260803-114423-833666`: 1x Poção de Cura Menor, ouro 200→140;
  1/1, `mock=false`, zero erro/violação, US$ 0,0027.
- Os mesmos cenários percorrem o grafo offline em testes permanentes e os
  oráculos viram violação `error` quando o efeito não aparece.
