# SPEC — Beats sem spoiler e sempre em PT-BR (campaign_manager)

> **Status:** `draft`
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** Fase 7.3 segredos (`done`), Fase 2.8 context builder (`done`)
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

Playtest longo 2026-07-14 (achados D+F):

1. **Vazamento de segredo pelo planejador.** Turno 14 do quester: o BEAT do
   plano continha a verdade oculta "o pacto de Valerius com Daruun é a ponta do
   iceberg". O perfil ecoa o beat como ação, o narrador confirma → violação
   `knowledge.secret_leak`. O canal: `campaign_manager` monta contexto via
   `build_context_pack(purpose="planning")` (campaign_manager.py:114) — o RAG
   estava até MORTO (429); o segredo veio do contexto/conhecimento do planner.
   O filtro `max_visibility` do `query_rag` não cobre esse caminho, e o texto
   do beat chega ao jogador (objetivo na UI, ação dos perfis).
2. **Beat em inglês.** Turno 60: "Explore the mysteries of Nova Arcádia." —
   quebra de imersão num jogo 100% PT-BR.

Nota de design: o planner PODE conhecer segredos (planejar arcos em volta
deles é desejável). O que não pode é o TEXTO do beat — que vaza pro jogador —
conter a verdade oculta. Logo a defesa certa é **sanitização determinística do
beat**, não cegar o planner.

## 2. Requisitos

- **R1** — As frases-assinatura de segredo (`_SECRET_SIGNATURES`,
  playtest/invariants.py:194) movem para um módulo compartilhado
  (`services/secret_signatures.py`), consumido pelo invariante E pelo motor.
- **R2** — Sanitizador determinístico de beat: todo beat/climax/arc_title novo
  do `campaign_manager` passa por `sanitize_beat(text, state) -> str`;
  se contém assinatura de segredo NÃO revelado (mesmo corpus de revelação do
  invariante), o beat é substituído por versão neutra ("Investigue os rumores
  sobre {entidade pública relacionada}" — mapa assinatura→rumor público no
  módulo R1) e o incidente é logado (`rpg.campaign` warning).
- **R3** — Prompt do campaign_manager ganha: (a) instrução explícita de nunca
  colocar verdades ocultas no texto de beat (defesa em profundidade);
  (b) "SEMPRE responda em português brasileiro".
- **R4** — Validação de idioma barata e determinística: beat que bate em
  heurística de inglês (regex de stopwords `the|of|and|explore|mysteries`
  ≥2 hits e ausência de acentos/stopwords PT) é rejeitado → re-tenta 1x com
  instrução reforçada; 2ª falha → mantém plano anterior (`needs_replan` fica).
- **R5** — Invariante `knowledge.secret_leak` também checa o TEXTO dos beats
  do `campaign_plan` (hoje só narração).

### Fora de escopo

- Cegar o planner para lore hidden (decisão: ele pode saber).
- Tradução automática de conteúdo do Codex.
- Detector de idioma por LLM (mecânica é Python).

## 3. Design técnico

- **`services/secret_signatures.py`** (novo) — `SECRET_SIGNATURES: dict`,
  `PUBLIC_RUMOR: dict[secret_id, str]`, `find_unrevealed(text, state) ->
  Optional[tuple[secret_id, phrase]]`, `sanitize_beat(text, state) -> str`,
  `looks_english(text) -> bool`. `playtest/invariants.py` importa daqui
  (compat: manter alias `_SECRET_SIGNATURES`).
- **`agents/campaign_manager.py`** — pós-structured-output (com o guard de
  FallbackLLM existente): mapear `sanitize_beat` sobre
  `beats[].description`, `climax`, `arc_title`; aplicar R4 antes de aceitar o
  plano.
- **`playtest/invariants.py`** — R5: iterar beats do estado no check de
  conhecimento.

## 4. Plano passo a passo

### Etapa 1 — módulo compartilhado
1. **Testes** (`tests/test_secret_signatures.py`):
   `test_find_unrevealed_detecta_pacto`; `test_revelado_nao_dispara` (corpus de
   revelação no estado); `test_invariants_usa_o_modulo` (import).
2. **Implementação:** mover + alias.
3. `uv run pytest` verde (nenhum teste 5.2 existente quebra).

### Etapa 2 — sanitizador no planner
1. **Testes** (`tests/test_campaign_sanitize.py`):
   `test_beat_com_segredo_e_neutralizado` (mock devolvendo beat sujo via
   monkeypatch); `test_beat_limpo_passa_intacto`;
   `test_climax_e_arc_title_tambem`.
2. **Implementação:** hook no campaign_manager_node.
3. `uv run pytest` verde.

### Etapa 3 — idioma
1. **Testes:** `test_looks_english_detecta_beat_ingles` (o beat real do t60);
   `test_pt_com_nomes_proprios_nao_dispara` ("Explore as ruínas de Skallgard"
   não é falso-positivo); `test_replan_retenta_e_desiste`.
2. **Implementação:** R4 + R3 no prompt.
3. `uv run pytest` verde.

## 5. Critérios de aceite

- [ ] R1–R5 com testes
- [ ] Replay do beat do turno 14 (texto real do transcrito `20260714-050339`)
  → beat sanitizado, zero violação
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM preservado no campaign_manager
- [ ] Saves antigos continuam carregando (plano antigo não é re-sanitizado — só
  beats novos)

## 6. Smoke test com LLM real

1. 10 turnos de quester real: nenhum beat com assinatura de segredo, nenhum
   beat em inglês (`transcript` + estado salvo).
2. Log `rpg.campaign` mostra sanitização quando forçada (prompt de teste
   pedindo pro planner citar o pacto).

## 7. Riscos & compatibilidade

- Falso-positivo do sanitizador esconde beat legítimo pós-revelação → o corpus
  de revelação (já usado pelo invariante) cobre isso; testes de regressão.
- Heurística de inglês: conservadora (2+ stopwords EN sem sinal de PT) para
  não punir nomes próprios; falso-negativo é aceitável (defesa em camadas com
  R3).
- MockLLM devolve beats fixos PT — suíte offline não muda de comportamento.
