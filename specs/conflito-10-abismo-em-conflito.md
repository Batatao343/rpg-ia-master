# SPEC — Conflito v2 #10: Cargas e Eventos do Abismo em Conflito

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-01-virtudes-vitalidade` (Cargas), `conflito-03-zonas-cena-objetos`
> (catálogo fechado de efeitos), `conflito-04-turnos-iniciativa-ataques`
> (todas `done` antes de iniciar)
> **Desbloqueia:** `conflito-11` (LLM prepara eventos possíveis do Abismo antes
> do combate)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Carga do Abismo já existe (`abyss_charge`, sistema de classes v3) mas não tem
manifestação própria em combate além dos gatilhos/regras especiais por classe já
implementados (`apply_entropy_trigger`, `arm_boiler`, `apply_transformacao` etc.
em `combat_mechanics.py`). `docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md`
§15+15.1 acrescenta uma camada nova: **eventos do Abismo preparados pela LLM antes
do conflito**, coerentes com a cena, carregáveis **sem LLM durante o combate** via
seed/gatilho/prioridade, com regras rígidas do que o Abismo pode e não pode fazer,
e uma assinatura visual fixa.

## 2. Requisitos

- **R1** — Antes do conflito, a LLM prepara possíveis **eventos do Abismo**
  coerentes com a cena (reusa o catálogo fechado de `EffectSpec.kind` de
  `conflito-03` R6). Cada evento preparado: `{id, gatilho, prioridade,
  cargas_necessarias, effect: EffectSpec, usos_permitidos}`.
- **R2** — Durante o conflito, eventos preparados podem ser carregados
  **deterministicamente ou por seed**, sem chamada de LLM, conforme Cargas
  disponíveis + gatilho + prioridade + estado atual da cena + usos permitidos.
- **R3** — Assinatura visual fixa e recorrente (sempre a mesma, não variada pela
  LLM em tempo real): som ambiente abafado, cores perdem intensidade, fissura
  negra fina aparece, pulso pálido atravessa, realidade muda, fissura desaparece
  mas a mudança permanece. O gasto de Carga é mostrado imediatamente ao jogador.
- **R4** — O Abismo é impessoal — sem moral/objetivo/plano. Age no ponto mais
  frágil da situação atual, **transforma algo que já existe**, nunca cria do
  nada. Pode: revelar, soltar, deformar, acelerar, romper, reposicionar por causa
  existente, transformar permanentemente algo que já existia. **Não pode**:
  desfazer sucesso já resolvido, controlar mentalmente NPC, obrigar alguém contra
  sua personalidade, criar Ferimento diretamente, agravar Ferimento fora do
  combate normal, adicionar elemento sem base na cena.
- **R5** — Evento do Abismo sem preparação prévia correspondente **não pode**
  acontecer (ex.: sem água/reservatório/tubulação na cena, uma Carga gasta não
  pode gerar inundação do nada) — validação idêntica à de `conflito-03` R6/R8.
- **R6** — Uma ação já rolada e resolvida com sucesso não pode ter seu sucesso
  negado por uma intervenção posterior do Abismo — só consequências
  **posteriores** podem ser alteradas (doc 03, Cenário 50).

### Fora de escopo

Geração dos eventos possíveis pela LLM em si — schema e prompt ficam em
`conflito-11` (preparação de encontro); gatilhos/regras/consequências por classe
já existentes (`entropy_trigger`/`special_rule`/`abyss.consequence` em
`combat_mechanics.py`) **não mudam** nesta spec, só ganham a camada de eventos de
cena por cima.

## 3. Design técnico

**Arquivos novos:**
- `services/abyss_events.py` — `PreparedAbyssEvent` (Pydantic), `can_trigger
  (event, scene_state, charges_available, seed) -> bool`, `trigger_event(event,
  scene_state) -> EffectSpec` (delega pro mesmo aplicador de `conflito-03`),
  `validate_event_has_scene_basis(event, scene_objects) -> bool` (R5).

**Arquivos alterados:**
- `combat_mechanics.py` — gatilhos de classe existentes (`apply_entropy_trigger`
  etc.) continuam intocados; `abyss_charge` ganha consumidor novo
  (`trigger_event`) além do que já existe.

**Schema:**
```python
class PreparedAbyssEvent(TypedDict):
    id: str
    gatilho: str
    prioridade: int
    cargas_necessarias: int
    effect: EffectSpec  # conflito-03
    usos_permitidos: int
    base_na_cena: str  # referência ao elemento existente que justifica o evento
```

## 4. Plano passo a passo

### Etapa 1 — Estrutura de evento preparado + validação de base na cena
1. **Testes** (`tests/test_conflito_abismo.py`): `test_evento_sem_base_na_cena_e_rejeitado`;
   `test_evento_com_base_valida_e_aceito`.
2. **Implementação:** `services/abyss_events.py`.

### Etapa 2 — Carregamento determinístico/por seed durante o conflito
1. **Testes:** `test_carrega_evento_quando_cargas_e_gatilho_atendidos_sem_llm`;
   `test_prioridade_decide_entre_eventos_concorrentes`; `test_mesma_seed_mesmo_evento_carregado`.
2. **Implementação:** `can_trigger`/`trigger_event`.

### Etapa 3 — Regras do que o Abismo pode/não pode fazer
1. **Testes:** um teste por proibição de R4 (`test_nao_desfaz_sucesso_ja_resolvido`;
   `test_nao_cria_ferimento_direto`; `test_nao_controla_mentalmente_npc`; etc.).
2. **Implementação:** guard de validação em `trigger_event`.

### Etapa 4 — Assinatura visual + exposição de gasto
1. **Testes:** `test_gasto_de_carga_e_reportado_imediatamente_no_log`.
2. **Implementação:** payload de log/narração determinístico com a assinatura
   fixa (texto-base reutilizável pela LLM na narração pós-evento).

## 5. Critérios de aceite

- [ ] Evento do Abismo só carrega com base preparada na cena — nunca "do nada".
- [ ] Carregamento em combate é 100% determinístico/seedado, zero chamada de LLM.
- [ ] Nenhuma das proibições de R4 é violável pelo motor.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

1. Preparar cena real com 1 elemento explícito (ex. corrente enferrujada) + LLM
   sugere evento do Abismo associado; confirmar validação aceita.
2. Confirmar que durante o combate real nenhuma chamada de LLM acontece para
   carregar o evento (só a narração posterior usa LLM).

## 7. Riscos & compatibilidade

- Fácil de confundir com os gatilhos de classe já existentes
  (`entropy_trigger`/`special_rule`) — documentar claramente que são camadas
  complementares, não substitutas, pra não duplicar/colidir lógica.
- Validação de "base na cena" depende de `conflito-03` estar sólido — não
  paralelizar.
