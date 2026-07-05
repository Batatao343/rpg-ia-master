# SPEC — Fase 6.1: Economia viva — rotas, escassez e eventos no comércio

> **Status:** `in-progress` — Etapas 1–5 implementadas (2026-07-05, 475 testes); falta smoke real (§6).
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fase 4.4 (economia determinística, `done`) · Fase 2.6 (pipeline de eventos, `done`)
> **Desbloqueia:** 6.2 (itens únicos), 6.3 (migração de monstros) — mesmo padrão de view derivada

---

## 1. Contexto & Objetivo

A 4.4 fez preço/estoque determinísticos, mas ESTÁTICOS diante do mundo: o único
acoplamento com o estado vivo é "controlador hostil" (preço +50%, sem raros).
Bloquear um porto, cortar uma estrada ou uma guerra regional não mudam NADA no
comércio — o critério antigo da Fase 6 ("bloquear porto → peixe some, preço
explode") continua aberto.

Esta spec liga o comércio ao `event_log`: **rotas comerciais** derivadas das
`connections` do mapa, evento estruturado `route_blocked`/`route_cleared`
(pipeline 2.6 — LLM propõe, motor valida contra o grafo), e **escassez/abundância**
calculadas por alcançabilidade: item produzido numa região que ficou inalcançável
fica escasso (×1.8, some do estoque); produzido ali mesmo segue abundante (×0.6,
já na 4.4). Tudo view derivada + eventos auditáveis — zero simulação oculta.

## 2. Requisitos

- **R1 (rota como fato do mundo)** — Novos tipos no pipeline 2.6: `route_blocked`
  e `route_cleared`, com `target_id` = local A e `payload.other_location_id` =
  local B. Validator exige: ambos existem no `world_map` E são `connections`
  diretas. Proponível pelo LLM (desabamento, bloqueio militar) E gerável pelo
  motor. Aplicado na projection: `blocked_routes: [{a, b, event_id}]`
  (`route_cleared` remove o par). Duplicata de par no mesmo estado é rejeitada.
- **R2 (alcançabilidade)** — `services/economy.py::is_reachable(loc_a, loc_b,
  projection) -> bool`: BFS nas `connections` do mapa MENOS as `blocked_routes`
  da projection. Puro, determinístico, cacheável por turno.
- **R3 (escassez)** — `supply_factor(item_id, location_id, projection) -> float`:
  - item com `economy_tags` produzido AQUI (tag do local ∩ tag do item): **0.6**
    (comportamento 4.4 preservado);
  - produzido só em regiões *alcançáveis*: **1.0**;
  - todas as regiões produtoras *inalcançáveis* (rotas bloqueadas): **1.8** e o
    item **some do estoque** dos mercadores locais (compra; venda continua).
  - Região produtora de um item = locais cujo `economy_tags` intersecta o do item.
  - Item sem `economy_tags`: sempre 1.0 (não participa).
- **R4 (preço)** — `price()` da 4.4 troca `regional_modifier` por `supply_factor`
  (retrocompatível: sem rota bloqueada, resultados idênticos aos atuais).
- **R5 (estoque)** — `merchant_stock()` filtra itens escassos (R3) — o mercador
  não tem o que não chega. Restock NÃO repõe item escasso enquanto a rota estiver
  bloqueada; `route_cleared` normaliza no restock seguinte.
- **R6 (rule_engine)** — regra declarativa em `world_rules.json`:
  `location_control_changed` para fação hostil num local com tag `porto` →
  emite `route_blocked` nas conexões aquáticas/da cidade (cascata 2.7, auditável,
  `source="rule_engine"`). Fecha o critério: porto tomado → peixe/importados
  somem nas cidades que dependiam dele.
- **R7 (visibilidade)** — jogador vê o efeito: narrador recebe nota no context
  pack quando o local atual tem rota bloqueada ("a estrada para X está fechada");
  aba de mapa marca a conexão bloqueada (overlay 3.4).
- **R8** — Offline-testável: BFS, supply, estoque, regra do porto — zero LLM.

### Fora de escopo

- Simulação de caravanas/fluxo contínuo de mercadorias (isto é view derivada,
  não agentes econômicos).
- Contrabando/mercado negro em rota bloqueada (ótimo gancho narrativo — backlog).
- Viagem do PLAYER bloqueada por `route_blocked` (decisão: rota bloqueada afeta
  COMÉRCIO; o herói pode forçar passagem — narrativa decide; mecanizar isso é
  outra spec).
- Preço dinâmico por demanda (só oferta/alcançabilidade).

## 3. Design técnico

### Arquivos alterados (sem módulo novo — evolução da economy)

| Arquivo | Mudança |
|---|---|
| `services/structured_outputs.py` | `route_blocked`/`route_cleared` no `EventType` |
| `services/world_validators.py` | `_v_route_blocked` / `_v_route_cleared` (conexão direta existe; par não duplicado) |
| `services/event_processor.py` | `apply_event`: mantém `projection["blocked_routes"]` |
| `services/economy.py` | `is_reachable`, `supply_factor`, `producing_locations(item_id)`; `price`/`merchant_stock` consomem |
| `services/rule_engine.py` + `data/graph/world_rules.json` | regra porto-hostil → route_blocked (R6) |
| `services/context_builder.py` | template de evento p/ `route_blocked`/`cleared` (narrador fica ciente) |
| `services/state_views.py` + `api.py` + `web/` | `blocked_routes` no world block; WorldMap tracejado na conexão bloqueada |
| `tests/test_fase61.py` | suíte |

### Formatos

Proposta (LLM ou motor):

```json
{"type": "route_blocked", "target_id": "brekmar",
 "payload": {"other_location_id": "nova_arcadia"},
 "detail": "Deslizamento fecha a estrada costeira"}
```

Projection:

```json
"blocked_routes": [{"a": "brekmar", "b": "nova_arcadia", "blocked_by_event": "..."}]
```

Regra (world_rules.json, mesmo vocabulário declarativo da 2.7):
gatilho `location_control_changed` + alvo com tag `porto` + controlador hostil →
`route_blocked` para cada connection do alvo (profundidade da cascata já limitada a 2).

### Decisões

1. **Par não-direcionado** — bloqueio vale nos dois sentidos; `is_reachable`
   trata `{a,b}` como aresta removida.
2. **Escassez binária por alcançabilidade** (0.6 / 1.0 / 1.8) — nada de floats
   contínuos; três estados legíveis, auditáveis pelo event_log.
3. **`route_cleared` também proponível** — mundo se cura (exército reabre
   estrada); validator exige que o par esteja de fato bloqueado.
4. **Retrocompatibilidade da 4.4**: sem bloqueio, `supply_factor` ≡
   `regional_modifier` — testes existentes não mudam de expectativa.

## 4. Plano passo a passo

### Etapa 1 — Evento de rota no pipeline (TDD)

1. **Testes:** `test_route_blocked_valida_conexao_direta` (par não conectado →
   rejeitado); `test_route_blocked_aplica_na_projection`;
   `test_route_cleared_remove`; `test_par_duplicado_rejeitado`;
   `test_llm_pode_propor` (sem gate de source — é proponível).
2. **Implementação:** EventType + validators + apply_event.

### Etapa 2 — Alcançabilidade + supply

1. **Testes:** `test_is_reachable_bfs`; `test_bloqueio_corta_caminho_unico`;
   `test_caminho_alternativo_mantem_alcance`; `test_supply_factor_local_produtor`;
   `test_supply_factor_escasso_18`; `test_item_sem_tags_neutro`.
2. **Implementação:** `is_reachable`/`producing_locations`/`supply_factor`.

### Etapa 3 — Preço + estoque reagem

1. **Testes:** `test_price_explode_com_rota_bloqueada` (critério: ×1.8);
   `test_estoque_some_item_escasso`; `test_restock_nao_repoe_escasso`;
   `test_route_cleared_normaliza`.
2. **Implementação:** `price`/`merchant_stock`/`restock`.

### Etapa 4 — Regra do porto (2.7)

1. **Testes:** `test_porto_hostil_bloqueia_rotas` (control_changed em brekmar →
   route_blocked nas connections, source=rule_engine);
   `test_criterio_fase6_porto_peixe` (e2e: porto tomado → item `porto` some do
   estoque de cidade vizinha e preço ×1.8).
2. **Implementação:** regra declarativa + componente/tag.

### Etapa 5 — Visibilidade (context pack + mapa)

1. **Testes:** `test_context_builder_menciona_rota`; `test_world_block_expoe_blocked_routes`.
2. **Implementação:** templates + api + WorldMap (traço na aresta bloqueada).
3. **Verificação:** suíte completa + `npm run build` + smoke_api.

## 5. Critérios de aceite

- [ ] Bloquear o porto → item de tag `porto` some das lojas dependentes e preço ×1.8 (e2e determinístico)
- [ ] Caminho alternativo existente → sem escassez (BFS de verdade, não flag)
- [ ] `route_cleared` restaura preço/estoque no restock seguinte
- [ ] LLM propõe `route_blocked` inválido (locais não conectados) → rejeitado
- [ ] Mapa mostra conexão bloqueada; narrador cita a rota fechada
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: N/A (zero structured output novo — tipos entram no schema existente)
- [ ] Saves antigos carregam (`blocked_routes` default `[]`)

## 6. Smoke test com LLM real

1. Narrar situação que implique bloqueio ("a ponte desabou atrás de você") →
   storyteller propõe `route_blocked` com par canônico válido (mapeamento real).
2. Ir à loja dependente → preço/estoque refletem; narração menciona a escassez.
3. Turno banal → nenhuma proposta de rota espúria.

(≈ 3 requests.)

## 7. Riscos & compatibilidade

- **Saves antigos:** `blocked_routes` ausente = `[]`; sem migração.
- **MockLLM:** tipos novos entram no Literal — mock genérico cobre; e2e offline
  passa proposta como dict direto.
- **LLM spammar bloqueios:** dup-check por par + validator de conexão direta +
  (2.6) rejeição não quebra o turno; observar no playtest.
- **BFS custo:** mapa tem 30 nós — irrelevante; ainda assim cachear por
  (turno, frozenset de rotas) se aparecer no profile.
