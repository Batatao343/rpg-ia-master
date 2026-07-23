# SPEC — Conflito v2 #14: Autoria Completa das Cartas de Classe e Subclasse

> **Status:** `done` (2026-07-23, sessão 25)
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-23
> **Depende de:** `conflito-02-cartas-acervo-preparacao` (`done` — schema de Carta
> precisa existir antes de autorar conteúdo real)
> **Desbloqueia:** `conflito-13` (cutover só remove `player_abilities.json` antigo
> com conteúdo novo pronto pra substituí-lo)
> **Épico:** Migração do Sistema de Conflitos de Valoria
> **Nota:** pedido explícito do usuário (2026-07-22) — autoria de conteúdo entra
> nesta leva de specs, não fica indefinidamente adiada. Pode rodar em paralelo às
> specs `conflito-03` a `conflito-12` (só depende do schema da `02`), mas só entra
> em produção depois do `conflito-13`.

---

## 1. Contexto & Objetivo

`conflito-02` define o **schema** de Carta e cria só 3-5 cartas de exemplo por
classe pra validar o motor. Esta spec é a **autoria completa**: converter/
reautorar as 101 habilidades atuais (`data/player_abilities.json` — 41 ativas +
35 passivas + 25 utilitárias) para o schema novo de Carta, cobrindo as 5 classes
(Devoto do Abismo/Sangromante/Corruptor/Arcanista Cinzento/Médico de Campo) × 3
subclasses cada, com Acervo suficiente pra preencher os patamares Inicial/
Avançado/Superior (níveis 1-3/4-6/7-10), 2 Cartas de Virtude sugeridas por
combinação, Ruptura Caminho A/B a partir do nível 4, e as categorias de potência
(Fraco/Moderado/Forte/Devastador) referenciadas por `conflito-11` pra efeitos de
cena.

Precedente direto no projeto: `arvores-habilidade-classes` (autoria em Fable,
sessão 19) — mesma escala de trabalho (101 habilidades), mesmo padrão de "motor
primeiro, depois autoria dedicada".

## 2. Requisitos

- **R1** — Cobertura completa: cada uma das 5 classes tem cartas de tronco
  (compartilhadas) + cada uma das 15 combinações classe×subclasse tem cartas
  próprias, suficiente pra um Acervo de 6+ cartas no nível 1 crescendo até o teto
  do nível 10 (7 preparadas, Acervo maior).
- **R2** — Toda carta ativa tem `damage_formula` na escala do sistema novo (dano-
  base 3/4/6/8 por categoria de arma, `conflito-05` R1) — não reaproveitar as
  fórmulas antigas (`2d6` etc.) sem revisão, escala mudou.
- **R3** — Toda carta segue o catálogo fechado de `EffectSpec.kind`
  (`conflito-03` R6) — nenhum efeito textual sem correspondência mecânica.
- **R4** — Frequência (Livre/turno/cena/descanso curto/longo) definida por carta,
  coerente com o papel dela (ex. Ruptura de classe pesada não deveria ser Livre).
- **R5** — Evolução Caminho A/B definida a partir do nível 4 pra cartas centrais de
  cada subclasse (substitui o efeito normal E a Ruptura base).
- **R6** — 2 Cartas de Virtude sugeridas por combinação classe/subclasse (jogador
  pode escolher livremente na criação — isso é motor, `conflito-02`; aqui é
  conteúdo de exemplo/recomendação).
- **R7** — Tabela `data/potency_by_level.json` (`conflito-11`) preenchida com
  valores reais Fraco/Moderado/Forte/Devastador por Nível do Encontro 1-10+.
- **R8** — Parity entre classes: reusar o critério já validado no projeto
  (`balanceamento-classes-pos-playtest` §10 — dano-efetivo/custo-real, banda
  1.5-4.0 dano/Entropia pra dano puro) adaptado à nova escala 2d10+Virtude —
  nenhuma classe deve ficar destoante sem justificativa de papel (tank baixo por
  design é aceitável, outlier não).
- **R9** — `data/classes.json` atualizado: `starting_abilities`→cartas iniciais no
  formato novo; `branches` (subclasses) referenciam as cartas próprias.
- **R10** — As habilidades devem ser variadas entre si e devem seguir a identidade de Valoria, tendo relação com o mundo que foi construido. Não reaproveitar habilidades apenas alterando a quantidade de dano. 

### Fora de escopo

Motor de Cartas em si (`conflito-02`); bestiário/perfis táticos de inimigos
(`conflito-15`); UI de gestão de mão (`conflito-16`).

## 3. Design técnico

**Arquivos novos/alterados:**
- `scripts/gen_cards_v4.py` (nome sugerido, seguindo o precedente
  `scripts/gen_classes_v2.py`) — gera `data/cards/*.json` a partir de uma fonte
  autoral (documento/planilha) no schema de `conflito-02`.
- `data/cards/` — arquivo final por classe ou consolidado (decisão de
  implementação), substituindo `data/player_abilities.json`.
- `data/classes.json` — `base_stats`/`branches`/`starting_abilities` atualizados.
- `data/potency_by_level.json` — preenchido (R7).
- `docs/CARTAS.md` (novo, espelhando `docs/CLASSES.md`) — referência viva do
  catálogo de Cartas, mecânica + narrativa.

## 4. Plano passo a passo

### Etapa 1 — Fonte autoral + gerador
1. **Testes** (`tests/test_conflito_autoria_cartas.py`): `test_todas_as_15_combinacoes_tem_cartas_proprias`;
   `test_todas_as_cartas_usam_effectspec_kind_valido`.
2. **Implementação:** `scripts/gen_cards_v4.py` + fonte autoral (documento
   estruturado, possivelmente autorado em sessão dedicada como
   `arvores-habilidade-classes`).

### Etapa 2 — Damage formula na escala nova
1. **Testes:** `test_dano_base_das_cartas_ativas_bate_com_categoria_de_arma`.
2. **Implementação:** revisão de todas as fórmulas.

### Etapa 3 — Ruptura Caminho A/B
1. **Testes:** `test_cartas_centrais_tem_ruptura_com_dois_caminhos`.
2. **Implementação:** conteúdo.

### Etapa 4 — Cartas de Virtude sugeridas
1. **Testes:** `test_cada_combinacao_tem_pelo_menos_duas_cartas_de_virtude_sugeridas`.
2. **Implementação:** conteúdo.

### Etapa 5 — Potência por nível
1. **Testes:** `test_potency_by_level_cobre_niveis_1_a_10_para_as_4_categorias`.
2. **Implementação:** `data/potency_by_level.json`.

### Etapa 6 — Guarda de parity
1. **Testes:** teste-guarda equivalente ao de `test_arvores_classes` (banda de
   dano/custo) — adaptado à escala 2d10+Virtude.
2. **Implementação:** medição determinística, sem playtest necessário (mesmo
   método já validado no projeto).

## 5. Critérios de aceite

- [x] Todas as 5 classes × 3 subclasses têm Acervo completo até nível 10
  (80 Cartas autorais, 16/classe = 7 tronco + 3×3 subclasse; patamares
  inicial/avançado/superior).
- [x] Nenhuma carta usa efeito fora do catálogo fechado
  (`services.cards.CARD_EFFECT_KINDS`; lint + teste).
- [x] Guarda de parity passa (`dano_base/custo ∈ [1.5, 4.0]` p/ dano puro custeado).
- [x] `data/player_abilities.json` antigo **pode** ser removido com segurança —
  a remoção em si + `classes.json.starting_abilities → Cartas` (R9) ficam pro
  **cutover conflito-13** (trocar agora quebraria o caminho antigo
  `known_abilities`; Cartas iniciais recomendadas em `STARTING_RECOMENDADO`).
- [x] `uv run pytest` verde (1254 → +16 desta spec).

### Notas de implementação (desvios da spec, R do CLAUDE.md)

- **R3 (catálogo fechado):** a spec referencia a conflito-03 R6
  (`conflict_scene.EFFECT_KINDS`), que é o catálogo de **cena/objeto**. Cartas
  têm vocabulário próprio de efeito (resolvido pela conflito-04/05), então foi
  criado o catálogo canônico **`services.cards.CARD_EFFECT_KINDS`** (mesmo
  princípio: fechado, lintado). É esse que a autoria e o lint usam.
- **R2 (escala):** dano é **flat** por categoria de arma (doc 01 §19: Leve 3 /
  Marcial 4 / Versátil 6 / Pesada 8), não dado. `efeito.kind=="dano"` carrega
  `categoria_arma` + `dano_base` (≥ base). Fórmulas `2d6` antigas eliminadas.
- **R7 (potência):** `data/potency_by_level.json` já vinha preenchido (conflito-11);
  teste garante cobertura 1-10 × 4 categorias + escada monotônica.
- **Convivência:** as Cartas de EXEMPLO do motor (conflito-02,
  `data/cards/exemplos*.json`) permanecem — os testes do motor dependem delas.
  As autorais são marcadas `origem: "conflito-14"` e ficam em
  `data/cards/{devoto,sangromante,corruptor,arcanista,medico}.json`.
- **Arquivos:** `scripts/gen_cards_v4.py` (fonte autoral + gerador) ·
  `data/cards/*.json` (gerado) · `data/cards/virtude_sugeridas.json` (R6) ·
  `services/cards.py` (catálogo + helpers `cards_at_patamar`/
  `suggested_virtue_cards`) · `services/content_validator.py::validate_cards`
  (Etapa 5) · `docs/CARTAS.md` · `tests/test_conflito_autoria_cartas.py` (16).

## 6. Smoke test com LLM real

N/A — conteúdo estático, sem LLM em runtime (a não ser que a autoria em si use
LLM pra gerar rascunho de texto, caso em que aplica-se o guard de
`with_structured_output` na geração, não no uso em jogo).

## 7. Riscos & compatibilidade

- Trabalho de autoria em escala comparável à `arvores-habilidade-classes`
  (101 habilidades) — considerar mesmo padrão de delegação usado lá (autoria
  especializada, possivelmente em sessão dedicada tipo Fable).
- Rebalancear TUDO na nova escala (2d10+Virtude vs d20+AC) é trabalho novo, não
  conversão mecânica — não presumir que "gemer o dado antigo x1.5" basta.
