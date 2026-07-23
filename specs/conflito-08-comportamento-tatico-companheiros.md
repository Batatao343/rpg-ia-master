# SPEC — Conflito v2 #08: Perfil Tático, Companheiros e Informação Revelada

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-02-cartas-acervo-preparacao`, `conflito-04-turnos-iniciativa-ataques`,
> `conflito-05-armadura-dano-ferimentos`, `conflito-07-morte-rendicao-captura`
> (todas `done` antes de iniciar)
> **Desbloqueia:** `conflito-11` (preparação de encontro seleciona por perfil),
> `conflito-15` (autoria do bestiário preenche o perfil real)
> **Épico:** Migração do Sistema de Conflitos de Valoria

---

## 1. Contexto & Objetivo

Hoje o comportamento inimigo é 4 perfis fixos (`tatico/feroz/covarde/implacavel`,
`combat_mechanics.get_behavior`/`choose_enemy_attack`/`check_morale`) — sem
prioridades ordenadas nem distinção entre "obrigatório" e "restrição". Party é
controlada 100% pelo jogador sem validação contra personalidade do companheiro.

`docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md` §29-30+28 substitui isso
por um **perfil tático persistido** (gerado 1x por uma LLM robusta, salvo na
ficha) com prioridades ordenadas e tipos de comportamento (Obrigatório/Oferta/
Restrição/Autônomo) + resistência a ordens (Flexível/Resistente/Absoluta/
Autônoma) — a mesma estrutura de dados serve tanto pra decidir a IA de um inimigo
quanto pra **validar as ordens do jogador sobre companheiros**. Define também a
informação do inimigo exibida progressivamente (painel inicial + cartas/
resistências reveladas ao uso, persistindo no bestiário).

## 2. Requisitos

- **R1** — `TacticalProfile`: `priorities: List[Priority]` ordenada — a primeira
  prioridade cujo gatilho é válido prevalece. `Priority = {trigger, tipo
  ("obrigatorio"|"oferta"|"restricao"|"autonomo"), action_hint, resistance
  ("flexivel"|"resistente"|"absoluta"|"autonoma")}`.
- **R2** — Perfil cobre: escolha de ações, escolha de alvos, uso de recursos, uso
  de reações, fuga, perseguição, rendição, restrições morais/instintivas,
  desempates.
- **R3** — Tipos de comportamento: **Obrigatório** (executa quando o gatilho
  ocorre, sem escolha), **Oferta** (apresenta escolha ao jogador — ex. sacrifício
  de companheiro), **Restrição** (impede ordem incompatível), **Autônomo**
  (assume controle quando um estado retira o comando do jogador).
- **R4** — Resistência a ordens: **Flexível** (contrariável normalmente),
  **Resistente** (exige lealdade/efeito apropriado), **Absoluta** (nunca
  contrariável — ex. paladino recusa assassinar inocente), **Autônoma** (quando
  ativada, executa sem esperar ordem).
- **R5** — Geração do perfil: 1 chamada de LLM robusta (tier `SMART`) por
  arquétipo/NPC, **na criação**, nunca em tempo real de combate. Resultado
  persiste na ficha (bestiário curado ou `data/runtime/` overlay pra NPCs
  gerados — mesmo padrão de `isolar-cache-runtime`).
- **R6** — Controle de party: jogador controla protagonista+companheiros+ordem+
  cartas+alvos+movimento+equipamento+recursos. Toda ordem é validada contra
  `TacticalProfile` do companheiro; ordem recusada (Restrição Absoluta/Resistente
  sem efeito) devolve a escolha ao jogador sem crash. Perfil só assume o turno
  quando o personagem sai de controle por condição explícita (medo/confusão/
  controle mental/inconsciência/separação não acompanhada). Jogador mantém
  controle da party enquanto alguém consciente estiver no conflito, mesmo com
  protagonista fora.
- **R7** — Informação exibida do inimigo — inicial (sempre visível): Vitalidade
  atual/máxima, Esquiva, Proteção, Integridade atual/máxima, recursos visíveis,
  estados/condições, posição, Engajamentos. Oculto até descoberto: Cartas não
  usadas, reações não usadas, Virtudes, perfil tático, prioridades, espaços
  internos de Ferimento, recursos não perceptíveis, resistências/vulnerabilidades/
  imunidades ainda não ativadas.
- **R8** — Carta revelada: ao ser usada pelo inimigo, mostra efeito/custo/alcance/
  frequência/gatilhos/disponibilidade completos, permanece revelada pelo resto do
  combate, **entra no bestiário** e começa revelada em encontros futuros com o
  mesmo arquétipo (variantes podem ter Cartas exclusivas ainda ocultas).
- **R9** — Resistência/Vulnerabilidade/Imunidade revelada quando afeta uma
  resolução — permanece visível e entra no bestiário (mesmo mecanismo de
  persistência de R8).

### Fora de escopo

Conteúdo real dos perfis de cada criatura/NPC do bestiário (`conflito-15`);
seleção de criaturas por região pra um encontro (`conflito-11`); UI do painel de
inimigo (`conflito-16`).

## 3. Design técnico

**Arquivos novos:**
- `services/tactical_profile.py` — `TacticalProfile` (Pydantic), `pick_action
  (profile, scene_state) -> ActionDecision` (substitui `choose_enemy_attack`/
  `pick_target`/`check_morale`), `validate_companion_order(companion, order) ->
  ValidationResult` (mesma estrutura de dados, dois consumidores).
- `services/bestiary_knowledge.py` — `reveal_card(bestiary_entry, card_id)`,
  `reveal_resistance(bestiary_entry, resistance_type)`, persiste em
  `data/runtime/` overlay (não no arquivo curado, mesmo padrão de
  `isolar-cache-runtime`).

**Arquivos alterados:**
- `combat_mechanics.py` — remove `get_behavior`/perfis fixos hardcoded; consome
  `TacticalProfile` via `services/tactical_profile.py`.
- `agents/bestiary.py` — `generate_new_enemy` passa a gerar também o
  `TacticalProfile` (1 chamada LLM robusta a mais, ou combinada no mesmo schema
  de `EnemySchema` — decidir na implementação).

**Schema:**
```python
class Priority(TypedDict):
    trigger: str
    tipo: Literal["obrigatorio","oferta","restricao","autonomo"]
    action_hint: str
    resistance: Literal["flexivel","resistente","absoluta","autonoma"]

class TacticalProfile(TypedDict):
    priorities: List[Priority]  # ordem = precedência
```

## 4. Plano passo a passo

### Etapa 1 — Schema `TacticalProfile` + `pick_action`
1. **Testes** (`tests/test_conflito_tatica.py`): `test_primeira_prioridade_valida_prevalece`;
   `test_prioridade_obrigatoria_executa_sem_escolha`; `test_prioridade_oferta_pergunta_ao_jogador`.
2. **Implementação:** `services/tactical_profile.py`.

### Etapa 2 — Resistência a ordens (companheiros)
1. **Testes:** `test_ordem_flexivel_aceita`; `test_ordem_absoluta_recusa_sempre`
   (paladino não assassina inocente); `test_ordem_recusada_devolve_escolha_ao_jogador`.
2. **Implementação:** `validate_companion_order`.

### Etapa 3 — Controle de party e perda de controle
1. **Testes:** `test_jogador_controla_party_com_protagonista_fora`; `test_perfil_assume_turno_so_com_condicao_explicita`;
   `test_medo_confusao_controle_mental_tiram_comando`.
2. **Implementação:** integração com `active_conditions`/`control` já existente.

### Etapa 4 — Geração do perfil (LLM 1x, persistido)
1. **Testes:** guard de `with_structured_output` (isinstance/try-except); teste
   de persistência (perfil gerado 1x, reusado em encontros seguintes sem nova
   chamada).
2. **Implementação:** `agents/bestiary.py`.

### Etapa 5 — Informação revelada progressiva
1. **Testes:** `test_painel_inicial_mostra_so_campos_publicos`; `test_carta_usada_revela_e_persiste_no_bestiario`;
   `test_resistencia_ativada_revela_e_persiste`; `test_variante_pode_ter_carta_exclusiva_ainda_oculta`.
2. **Implementação:** `services/bestiary_knowledge.py`.

## 5. Critérios de aceite

- [ ] Perfil tático decide ação/alvo/reação/fuga/rendição por prioridade ordenada,
  sem LLM em tempo real de combate.
- [ ] Ordem de companheiro é validada contra o perfil; recusa nunca crasha, sempre
  devolve escolha ao jogador.
- [ ] Cartas/resistências reveladas persistem no bestiário entre encontros.
- [ ] Painel inicial do inimigo mostra só os campos públicos definidos em R7.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

1. Gerar perfil tático real (LLM robusta) pra 1 arquétipo novo, confirmar
   schema válido + persistência (`isinstance` guard testado).
2. Combate real: inimigo usa Carta nova, confirmar revelação persiste num 2º
   encontro com o mesmo arquétipo (sem nova chamada de LLM pro perfil).
3. Companheiro recusa ordem incompatível (traço Absoluto) em combate real narrado.

## 7. Riscos & compatibilidade

- Mesma estrutura de dados serve dois consumidores (IA de inimigo E validação de
  ordem de companheiro) — resistir à tentação de duplicar; qualquer divergência
  de comportamento entre os dois usos deve ser explícita no design, não acidental.
- Geração de perfil é custo de LLM novo por arquétipo — cachear agressivamente
  (mesmo padrão de `find_existing_entity`/dedupe semântico já usado em
  `agents/bestiary.py`).
- `check_morale`/perfis fixos atuais têm ~199 testes de combate em cima — auditar
  quais migram vs. são substituídos integralmente.
