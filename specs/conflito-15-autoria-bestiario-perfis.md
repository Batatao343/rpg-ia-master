# SPEC — Conflito v2 #15: Autoria Completa do Bestiário e Perfis Táticos

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-05-armadura-dano-ferimentos`, `conflito-08-comportamento-tatico-companheiros`
> (`done` — schema de perfil tático + armadura/resistência precisa existir antes
> de autorar conteúdo real)
> **Desbloqueia:** `conflito-13` (cutover), `conflito-11` (preparação de
> encontro real usa este bestiário)
> **Épico:** Migração do Sistema de Conflitos de Valoria
> **Nota:** pedido explícito do usuário (2026-07-22) — autoria de conteúdo entra
> nesta leva de specs. Pode rodar em paralelo às specs `conflito-06` a
> `conflito-12`, mas só entra em produção depois do `conflito-13`.

---

## 1. Contexto & Objetivo

`data/bestiary.json` hoje tem 3962 linhas / dezenas de criaturas no schema antigo
(`hp/ac/attacks[]` com dano embutido como string, `behavior.profile` = 1 de 4
perfis fixos). A migração exige que **cada criatura** tenha: Virtudes+Vitalidade+
Ferimentos (`conflito-01`/`05`), Cartas próprias (`conflito-02`), armadura/
resistências tipadas (`conflito-05`), regras de fuga/perseguição
(`conflito-09`), e principalmente um **perfil tático completo** no formato de
`TacticalProfile` (`conflito-08`) — prioridades ordenadas, tipos de
comportamento, resistência a ordens.

Isso é autoria de conteúdo em escala grande (dezenas de criaturas × schema muito
mais rico que o atual) — mesmo padrão dos épicos anteriores do projeto (autoria
dedicada após o motor validado).

## 2. Requisitos

- **R1** — Toda criatura curada em `data/bestiary.json` migra pro schema novo:
  `virtudes`, Vitalidade/Ferimentos por Corpo (`conflito-01`), `armor`/`shield`
  opcional, `resistencias/vulnerabilidades/imunidades` tipadas por tipo de dano
  (`conflito-05` R3), `cartas: List[card_id]` (próprias ou reusadas de
  `conflito-14` quando fizer sentido narrativo — ex. NPC com Cartas de classe),
  `categoria` (`"lacaio"|"padrao"|"elite_chefe"|"nomeado"`, `conflito-07` R7).
- **R2** — `TacticalProfile` completo por criatura/arquétipo (não mais 4 perfis
  fixos genéricos) — prioridades ordenadas cobrindo ação/alvo/recursos/reação/
  fuga/perseguição/rendição/restrição moral, coerentes com a descrição/
  personalidade já existente de cada criatura.
- **R3** — Regras de fuga/perseguição por criatura/arquétipo (predador persegue,
  guardião não abandona posto, etc. — exemplos do doc 01 §33) refletidas nas
  prioridades do perfil, não como campo separado solto.
- **R4** — Cartas ocultas até uso (`conflito-08` R7-R9): cada criatura com pelo
  menos 1 Carta especial não-óbvia, coerente com o arquétipo, pra validar o
  sistema de revelação progressiva.
- **R5** — `regions` mantido (associação de região já existe e funciona — não
  reautorar, só carregar no schema novo).
- **R6** — Migração automatizada onde possível (script que converte o que dá pra
  inferir — nome/descrição/regions/type/loot) + revisão manual obrigatória pra
  tudo que exige julgamento (perfil tático, Cartas, Virtudes).
- **R7** — Categorias por tipo de criatura: a maioria das entradas atuais tipo
  `"Minion"` vira `"lacaio"` (Vitalidade simplificada, sem Última Ação); tipo
  `"Elite"`/`"BOSS"` vira `"elite_chefe"` (sistema completo); NPCs nomeados
  existentes viram `"nomeado"`.

### Fora de escopo

Motor de perfil tático/Cartas em si (`conflito-02`/`08`); geração de NPC/criatura
nova em tempo real via LLM (`conflito-11`, essa spec só autora o bestiário
curado pré-existente); UI.

## 3. Design técnico

**Arquivos alterados:**
- `data/bestiary.json` — migração de schema completa (script + revisão manual).
- `scripts/migrate_bestiary_v4.py` (novo) — converte campos inferíveis
  automaticamente, deixa placeholder claro (`"TODO_REVISAO_MANUAL"`) pros campos
  que exigem autoria (perfil tático, Cartas).

**Processo sugerido:** 1) rodar migração automática pros campos triviais; 2)
autoria dedicada (possivelmente Fable, mesmo padrão de `arvores-habilidade-classes`)
pra perfis táticos + Cartas de cada criatura; 3) validação via
`scripts/validate_content.py` estendido (`conflito-13`/Fase 7 lint) pra garantir
que todo `TacticalProfile` tem pelo menos 1 prioridade Obrigatória de
sobrevivência básica (nenhuma criatura sem regra de fuga/rendição definida).

## 4. Plano passo a passo

### Etapa 1 — Migração automática dos campos triviais
1. **Testes** (`tests/test_conflito_autoria_bestiario.py`): `test_todas_criaturas_tem_categoria_valida`;
   `test_regions_preservado_da_migracao`.
2. **Implementação:** `scripts/migrate_bestiary_v4.py`.

### Etapa 2 — Autoria de perfil tático completo
1. **Testes:** `test_toda_criatura_tem_pelo_menos_uma_prioridade_obrigatoria`;
   `test_nenhuma_criatura_sem_regra_de_fuga_ou_rendicao_explicita`.
2. **Implementação:** conteúdo autoral, revisão manual criatura a criatura (ou em
   lotes por região/tipo).

### Etapa 3 — Virtudes/Vitalidade/armadura/resistências
1. **Testes:** `test_vitalidade_da_criatura_bate_com_tabela_de_corpo`;
   `test_resistencias_usam_tipos_validos_de_dano`.
2. **Implementação:** idem.

### Etapa 4 — Cartas por criatura + ocultação
1. **Testes:** `test_criatura_tem_pelo_menos_uma_carta_especial`;
   `test_carta_comeca_oculta_ate_primeiro_uso` (integração com `conflito-08`).
2. **Implementação:** idem.

### Etapa 5 — Validação de lint estendida
1. **Testes:** CLI `scripts/validate_content.py` cobre os campos novos
   (perfil tático mínimo, Virtudes válidas 0-5, categoria válida).
2. **Implementação:** extensão do validador existente (Fase 7.1).

## 5. Critérios de aceite

- [ ] 100% das criaturas curadas migradas pro schema novo, sem placeholder
  `TODO_REVISAO_MANUAL` remanescente.
- [ ] Todo perfil tático tem prioridade de fuga/rendição definida (nenhuma
  criatura "burra até a morte" sem ser intencional, ex. Lacaio fanático).
- [ ] Lint (`scripts/validate_content.py`) valida os campos novos.
- [ ] `uv run pytest` verde.

## 6. Smoke test com LLM real

N/A — conteúdo estático. Validar em combate real (`conflito-13` smoke) que os
perfis autorados produzem comportamento coerente (guardião não abandona posto,
predador persegue, etc.).

## 7. Riscos & compatibilidade

- Volume grande (dezenas de criaturas) — considerar priorizar as mais usadas em
  playtest primeiro (early-game/regiões iniciais) e completar o resto
  incrementalmente, sem bloquear o `conflito-13` por 100% de cobertura se um
  subconjunto já é suficiente pra smoke test.
- Overlay runtime (`data/runtime/bestiary_runtime.json`, `isolar-cache-runtime`)
  não deve ser confundido com a curadoria — migração é só no arquivo curado.
