# SPEC — Conflito v2 #07: Última Ação, Estado Terminal, Cicatrizes e Rendição

> **Status:** `done` (2026-07-23) — motor puro aditivo em `services/death_flow.py`;
> reconciliação com `services/checkpoints.py`/`death_pending`/UI e hook ao vivo no
> pipeline de dano vão no cutover `conflito-13` (pontos marcados)
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-23
> **Depende de:** `conflito-01-virtudes-vitalidade`, `conflito-04-turnos-iniciativa-ataques`,
> `conflito-05-armadura-dano-ferimentos` (todas `done` antes de iniciar)
> **Desbloqueia:** `conflito-08` (rendição é gatilho de perfil tático),
> `conflito-13` (reconciliação final com `services/checkpoints.py`)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

O fluxo de morte atual (`checkpoints-morte`, sessão 23) é: `hp<=0` → `combat_node`
narra queda determinística (`_narrate_fall`) → `death_pending=True` → resolução
fora do combate via `services/checkpoints.resolve_death_choice` (`"accept"` =
memorial, senão restaura checkpoint). Não existe Última Ação, Estado Terminal nem
Cicatriz.

`docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md` §24-27+31-32 substitui
isso por um fluxo mais rico: preencher o **último espaço de Ferimento Crítico**
dispara **Última Ação** imediata (Vantagem extrema, ignora limitações/recursos
ausentes, pode declarar Ruptura) → **Estado Terminal** → morte imediata sem aliado
capaz, ou até 2 tentativas de estabilização com aliado → sobreviver ao fluxo
inteiro gera **Cicatriz obrigatória** (LLM, pós-combate). Golpe final pode ser
não-letal por escolha; inimigos se rendem deterministicamente pelo próprio perfil.

## 2. Requisitos

- **R1** — Preencher o último espaço de Ferimento Crítico (`conflito-01`/`05`)
  dispara **Última Ação** imediatamente, mesmo fora da ordem normal: Vantagem
  extrema (3 dados, mantém o melhor resultado adequado), ignora limitações físicas
  dos Ferimentos, pode usar qualquer Carta preparada mesmo esgotada, ignora falta
  de Entropia/Vitalidade (custo ausente não cria Ferimento novo), pode declarar
  Ruptura (gera Carga normalmente).
- **R2** — Depois da Última Ação, entra em **Estado Terminal**. Cura comum não
  cancela — só uma habilidade específica de sobrevivência/cura cuja Ruptura diga
  isso. Essa Ruptura converte o último Crítico em Grave (ou cria Grave temporário
  acima do limite se os espaços Graves estiverem cheios — Vitalidade não recupera
  por descanso enquanto esse excesso existir).
- **R3** — Sem aliado próximo e capaz: morte imediata. Com aliado capaz: até 2
  tentativas de estabilização (2ª mais difícil ou com prazo menor); 2 falhas =
  morte.
- **R4** — Estabilização: aliado sem item = teste normal; com kit = Vantagem;
  Médico de Campo sem kit = Vantagem; Médico de Campo com kit = reanimação
  automática + metade da Vitalidade máxima (custa 1 carga de kit); poção adequada
  = reanimação automática + metade da Vitalidade máxima. Tratamento improvisado
  retorna com 1 Vitalidade; adequado com metade da máxima. Sem limite artificial
  de reanimações por combate — recursos/aliados/estado da cena decidem o que é
  possível.
- **R5** — Consciência pós-conflito: só Leves = acorda em segurança; algum Grave =
  precisa tratamento, pode acordar em descanso curto; algum Crítico = inconsciente
  até intervenção adequada.
- **R6** — Cicatriz surge **obrigatoriamente** quando o personagem sobrevive ao
  fluxo completo (último Crítico → Última Ação → Estado Terminal). LLM gera a
  Cicatriz depois do conflito com base em local do Ferimento, arma/criatura,
  tratamento, contexto, classe, Memórias, relação com o Abismo. Toda Cicatriz tem
  1 consequência negativa real + 1 habilidade positiva causalmente ligada ao
  trauma. Jogador não pode recusar.
- **R7** — Categorias de inimigo determinam quem usa o fluxo completo: **Lacaio**
  (Vitalidade simplificada, qualquer Ferimento remove do combate, sem Última
  Ação); **Padrão** (Vitalidade+Ferimentos, derrotado ao preencher último Crítico,
  sem Estado Terminal salvo regra explícita); **Elite/Chefe** (sistema completo,
  podem ter fases/Última Ação/sobrevivência específica); **Nomeado/companheiro**
  (sistema completo sempre, aliado ou adversário).
- **R8** — Golpe final pode ser declarado não-letal por quem o desfere (se a forma
  do ataque permitir — destruição total/queda fatal/efeito explicitamente letal
  não convertem sem regra específica). Alvo fica inconsciente/incapacitado em vez
  de morrer.
- **R9** — Rendição é determinística pelo perfil tático do inimigo (gatilhos:
  líder derrotado, Vitalidade muito baixa, aliados insuficientes, rota de fuga
  bloqueada, objetivo impossível, medo/lealdade quebrada). Encerra a hostilidade
  daquele participante salvo recusa/violação/regra específica.
- **R10** — Combate termina quando: um lado não tem hostis ativos, todos os hostis
  fugiram, todos se renderam, o objetivo mecânico foi concluído, ou um gatilho
  preparado encerrou. **Nunca** por interpretação livre de "perderam interesse" —
  precisa estar representado por perfil/objetivo/evento.

### Fora de escopo

Fuga/perseguição em si (`conflito-09`); resumo canônico pós-combate pra LLM
(`conflito-12`); reconciliação definitiva com `services/checkpoints.py`/UI de
morte (`conflito-13`, já que checkpoints hoje cobre um fluxo mais simples — esta
spec define a mecânica nova, a integração final com o sistema de save/restore
acontece no cutover).

## 3. Design técnico

**Arquivos novos:**
- `services/death_flow.py` — `trigger_last_stand(participant) -> LastStandResult`,
  `attempt_stabilization(target, helper, has_kit, is_medico) -> StabilizationResult`,
  `check_scar_required(participant) -> bool`, `resolve_surrender(enemy, profile,
  scene_state) -> bool` (consome perfil tático de `conflito-08`).

**Arquivos alterados:**
- `combat_mechanics.py` — hook no pipeline de dano (`conflito-05`) que detecta
  "último espaço Crítico preenchido" e dispara `trigger_last_stand`.
- `agents/combat.py` — narração de Cicatriz (LLM, pós-combate, guard de
  `with_structured_output` obrigatório) substitui/estende `_narrate_fall`.
- `services/checkpoints.py` — mantido por enquanto; ponto de integração marcado
  com comentário apontando pra `conflito-13`.

**Schema:**
```python
class LastStandResult(TypedDict):
    vantagem_extrema: bool
    acao_declarada: Dict
    ruptura_declarada: bool
    entra_em_estado_terminal: bool

class Scar(TypedDict):
    id: str
    consequencia_negativa: str
    habilidade_positiva_relacionada: str
    origem: str  # local do ferimento/causa
```

## 4. Plano passo a passo

### Etapa 1 — Última Ação
1. **Testes** (`tests/test_conflito_morte.py`): `test_ultimo_critico_dispara_ultima_acao_imediata`;
   `test_ultima_acao_ignora_recurso_ausente_sem_criar_ferimento`; `test_ultima_acao_pode_declarar_ruptura`.
2. **Implementação:** `services/death_flow.py` + hook em `combat_mechanics.py`.

### Etapa 2 — Estado Terminal + morte/estabilização
1. **Testes:** `test_sem_aliado_morte_imediata`; `test_duas_falhas_de_estabilizacao_morte`;
   `test_medico_com_kit_reanima_automatico_metade_vitalidade`; `test_pocao_adequada_reanima_automatico`.
2. **Implementação:** `attempt_stabilization`.

### Etapa 3 — Consciência pós-conflito
1. **Testes:** `test_so_leves_acorda_em_seguranca`; `test_critico_fica_inconsciente_ate_intervencao`.
2. **Implementação:** idem.

### Etapa 4 — Cicatriz obrigatória (LLM)
1. **Testes:** `test_sobreviver_ao_fluxo_completo_marca_scar_pendente`; guard de
   `with_structured_output` testado com `FallbackLLM` (convenção crítica do
   projeto).
2. **Implementação:** schema Pydantic da Cicatriz + prompt pós-combate.

### Etapa 5 — Categorias de inimigo
1. **Testes:** `test_lacaio_removido_por_qualquer_ferimento`; `test_padrao_derrotado_sem_estado_terminal`;
   `test_elite_chefe_usa_sistema_completo`.
2. **Implementação:** campo `categoria` no schema de inimigo (`conflito-15`
   preenche o conteúdo real).

### Etapa 6 — Golpe não-letal + rendição + encerramento
1. **Testes:** `test_golpe_final_pode_ser_nao_letal_se_forma_permitir`;
   `test_rendicao_por_gatilho_de_perfil_sem_llm`; `test_combate_nao_termina_por_interpretacao_livre`.
2. **Implementação:** `resolve_surrender` + checagem de encerramento no
   `combat_node`.

## 5. Critérios de aceite

- [x] Último Crítico dispara Última Ação → Estado Terminal corretamente
  (`critical_spaces_full`/`should_trigger_last_stand`/`trigger_last_stand`).
- [x] Estabilização segue as regras de recurso (kit/Médico/poção) e limite de 2
  tentativas (`attempt_stabilization`).
- [x] Cicatriz é gerada (guardada por `isinstance`/`try-except`) sempre que o fluxo
  completo é sobrevivido, nunca recusável (`generate_scar` + guard testado com `FallbackLLM`).
- [x] Rendição é 100% determinística pelo perfil, sem decisão de LLM (`resolve_surrender`).
- [x] `uv run pytest` verde — **1166 passed** (+20 `test_conflito_morte`).

## 6. Smoke test com LLM real

1. Forçar (seed) um personagem a preencher o último Crítico em combate real,
   confirmar narração da Última Ação + Estado Terminal + reanimação.
2. Confirmar geração real de Cicatriz via LLM (schema Pydantic, guard de
   `FallbackLLM` testado).
3. Confirmar rendição de inimigo por perfil não dispara nenhuma chamada de LLM.

## 7. Riscos & compatibilidade

- Esta spec **substitui conceitualmente** o fluxo de `death_pending`/checkpoints
  atual — decidir explicitamente (não implicitamente) se `death_pending` continua
  existindo como estado de UI enquanto a mecânica interna muda, ou se é
  redesenhado. Documentar a decisão na spec `conflito-13`.
- Cicatriz é o primeiro `with_structured_output` novo do épico — aplicar o guard
  de resiliência (CLAUDE.md, seção crítica) sem exceção.
- Categorias de inimigo (R7) dependem do bestiário ter o campo `categoria`
  preenchido — placeholder aqui, conteúdo real em `conflito-15`.
