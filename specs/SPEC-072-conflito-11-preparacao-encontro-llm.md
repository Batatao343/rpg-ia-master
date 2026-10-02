# SPEC — Conflito v2 #11: Preparação de Encontro pela LLM

> **Status:** `done` (2026-07-23) — motor puro + geração LLM com guard
> (`services/encounter_preparation.py` + `data/potency_by_level.json`); a mudança
> de GRAFO (mover `_spawn_enemies_integrated` pra fora do `combat_node`; NPC nascer
> com ficha completa em `agents/npc.py`) é o cutover `conflito-13`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-23
> **Depende de:** `conflito-02-cartas-acervo-preparacao`, `conflito-03-zonas-cena-objetos`,
> `conflito-08-comportamento-tatico-companheiros`, `conflito-10-abismo-em-conflito`
> (todas `done` antes de iniciar)
> **Desbloqueia:** `conflito-13` (cutover troca o roteamento pra usar este fluxo)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Hoje `_spawn_enemies_integrated` (`agents/combat.py:98-165`) roda **dentro** do
1º round de combate: `EncounterScanner` extrai nomes, `generate_new_enemy` busca/
cria cada inimigo, `encounter_budget` faz clamp determinístico. Não existe conceito
de zonas, objetos, Nível do Encontro nem eventos do Abismo preparados.

`docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md` §3+5 e
`02_..._MIGRACAO.md` §4.3 movem essa responsabilidade pra **antes** do conflito
começar: a LLM transforma a cena narrativa em cena jogável (zonas, objetos,
inimigos do bestiário regional, NPCs, reforços, eventos do Abismo possíveis),
usando só o catálogo fechado e categorias de potência — nunca números livres. Essa
é a última peça de "preparação"; depois disso a cena congela (`conflito-03` R8) e
o combate roda 100% sem LLM.

## 2. Requisitos

- **R1** — A LLM considera o contexto real do momento: local, descrição já
  apresentada, objetos já mencionados, participantes presentes, estado físico,
  relações/intenções, região, perigo do lugar, evento que iniciou o conflito,
  clima/iluminação, objetivos dos envolvidos, acontecimentos externos coerentes.
- **R2** — A LLM prepara: zonas da cena + ligações, posições iniciais,
  Engajamentos iniciais, inimigos selecionados do bestiário regional, NPCs
  presentes, objetos interativos + interações possíveis, coberturas/obstáculos/
  rotas, condições ambientais, reforços + gatilhos possíveis, objetivos especiais
  do conflito, condições especiais de encerramento, possíveis eventos do Abismo
  (`conflito-10`).
- **R3** — Depois que a cena é aceita e o conflito começa, a LLM **não** pode
  ampliar ou reinterpretar (reforça `conflito-03` R8 — cena congelada).
- **R4** — Efeitos mecânicos usam só o catálogo fechado (`EffectSpec.kind` de
  `conflito-03` R6) — descrição livre, efeito nunca inventado.
- **R5** — Potência por categoria em vez de números livres: **Fraco / Moderado /
  Forte / Devastador**. O valor real correspondente depende do **Nível do
  Encontro** (tabela determinística, não escolhida pela LLM).
- **R6** — Nível do Encontro depende do local, periculosidade real da região, tipo
  de evento, importância do conflito, ameaças únicas presentes — **não** depende
  do nível da party (perigo absoluto, decisão fechada do épico). Jogador nunca vê
  esse número.
- **R7** — Seleção de criatura respeita a região: associada à região, justificada
  pelo evento, presente em variante autorizada, ou explicitamente introduzida por
  acontecimento canônico. Criatura fora de região exige razão de mundo, não
  conveniência de balanceamento.
- **R8** — Objeto interativo só é criado se coerente com a cena já narrada (ex.
  alavanca/ponte instável/barris de óleo/sino/estátua rachada — não inserir arma
  de cerco ou saída secreta sem base).
- **R9** — Falha de validação: tentar outro provider na cadeia (`ROUTES`
  existente, `llm_setup.get_llm`). Se todos falharem, existe uma **cena
  simplificada de segurança** determinística (sem zonas/objetos elaborados, sem
  inventar nada fora das regras) — conflito nunca trava sem começar.
- **R10** — NPC gerado durante o roleplay (`agents/npc.py`) já nasce com ficha de
  combate completa (não mais `combat_stats` rudimentar) — reusa o schema de
  `EnemyStats`/`TacticalProfile` (`conflito-08`) desde a criação, não só quando
  vira alvo de combate.

### Fora de escopo

Resolução do conflito em si (specs 03-10); geração do perfil tático do
arquétipo/NPC (`conflito-08`, aqui só consome); conteúdo real do bestiário
(`conflito-15`).

## 3. Design técnico

**Arquivos alterados:**
- `agents/combat.py` — `_spawn_enemies_integrated` (`:98-165`) é **removido do
  nó de combate** e reaparece como etapa de preparação antes do `dm_router`
  chamar o combate (provável novo nó `encounter_preparation` ou extensão do
  `storyteller`/`dm_router` — decisão de arquitetura fica pro coding agent, mas o
  ponto de corte é: depois de preparado, `combat_node` só lê `ConflictScene`
  pronta e congelada).
- `agents/npc.py` — `NPCSchema.combat_stats` vira ficha completa desde a criação
  (não mais dict rudimentar `{hp,ac,attacks}`).

**Arquivos novos:**
- `services/encounter_preparation.py` — `prepare_encounter(narrative_context) ->
  ConflictScene` (Pydantic com todo o resultado de R1-R2), `validate_preparation
  (scene) -> ValidationResult` (checa R4/R7/R8), `fallback_safe_scene(context) ->
  ConflictScene` (R9, determinístico), `compute_encounter_level(location, region,
  event_type) -> int` (R6, Python puro).
- `data/potency_by_level.json` — tabela Fraco/Moderado/Forte/Devastador × Nível do
  Encontro → valor numérico real (dano/dificuldade/duração/reforços).

## 4. Plano passo a passo

### Etapa 1 — Nível do Encontro (Python puro)
1. **Testes** (`tests/test_conflito_preparacao.py`): `test_nivel_encontro_nao_depende_do_nivel_da_party`;
   `test_nivel_encontro_deriva_de_local_regiao_evento`.
2. **Implementação:** `compute_encounter_level`.

### Etapa 2 — Schema `ConflictScene` preparada + validação de catálogo fechado
1. **Testes:** `test_preparacao_valida_aceita`; `test_efeito_fora_do_catalogo_rejeitado`
   (reusa `conflito-03`); `test_objeto_sem_base_narrativa_rejeitado`.
2. **Implementação:** `services/encounter_preparation.py`.

### Etapa 3 — Seleção de criatura por região
1. **Testes:** `test_criatura_da_regiao_aceita`; `test_criatura_fora_da_regiao_sem_justificativa_rejeitada`.
2. **Implementação:** idem, reusa `regions` do bestiário.

### Etapa 4 — Potência por categoria
1. **Testes:** `test_fraco_moderado_forte_devastador_mapeiam_valor_por_nivel`.
2. **Implementação:** `data/potency_by_level.json` + lookup.

### Etapa 5 — Fallback entre providers + cena simplificada
1. **Testes:** `test_provider_invalido_tenta_proximo_da_cadeia`; `test_todos_falham_usa_cena_simplificada_de_seguranca`.
2. **Implementação:** `fallback_safe_scene` + integração com `llm_setup.ROUTES`.

### Etapa 6 — NPC nasce com ficha de combate completa
1. **Testes:** `test_npc_gerado_tem_enemystats_completo_desde_criacao`.
2. **Implementação:** `agents/npc.py`.

## 5. Critérios de aceite

- [x] Encontro é preparado inteiramente antes do combate começar; cena congela
  depois (`prepare_encounter` → `validate_preparation`; congelamento é a fiação do cutover 13).
- [x] Nível do Encontro não considera nível/força da party (`compute_encounter_level` sem param de party).
- [x] Falha de preparação sempre resolve (fallback de provider via `RoutedLLM`/`ROUTES`
  → cena simplificada `fallback_safe_scene`), nunca trava o jogo.
- [x] NPC gerado no roleplay já nasce pronto pra combate (`build_npc_combat_sheet`).
- [x] `uv run pytest` verde — **1223 passed** (+11 `test_conflito_preparacao`).

## 6. Smoke test com LLM real

1. Cena real com objeto coerente (ex. alavanca) → confirmar preparação aceita e
   objeto sem base narrativa é recusado num segundo teste.
2. Forçar falha do provider preferido (ou usar região com poucas criaturas) e
   confirmar fallback funciona sem crash.
3. Confirmar que o Nível do Encontro não muda com personagem nível 1 vs nível 8
   no mesmo local.

## 7. Riscos & compatibilidade

- É o ponto de maior mudança arquitetural do fluxo do grafo LangGraph (onde a
  preparação acontece em relação ao `dm_router`) — decidir com cuidado onde este
  nó entra sem quebrar `campaign_manager`/`storyteller` existentes.
- Reusa `ROUTES`/`get_llm` — nunca instanciar provider direto (convenção do
  projeto).
- `EncounterScanner`/`encounter_budget` atuais (`agents/combat.py`) têm lógica de
  clamp valiosa — não descartar, adaptar pro novo formato de `ConflictScene`.
