# SPEC-331 — Cartas #04: A LLM monta a cena, a cena vira tabuleiro (Cartas de Cena, Objetivo e Relógio)

> **Status:** `draft`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-072, SPEC-064, SPEC-325 C (objetos), SPEC-330 (palavras-chave usadas pelas Cartas de Cena); **SPEC-328** só para R6 (objeto na mão)
> **Desbloqueia:** SPEC-335 (cartas regionais), SPEC-334 (faixa de cena na UI)
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true` (structured output novo)
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] A preparação de encontro já existe: `services/encounter_preparation.py::PreparedScene` (zonas 1–3, objetos 0–2 com interações, eventos do Abismo, `objectives: list[str]` livres) e congela antes do conflito (SPEC-072). Isso é o "LLM monta o cenário" que o dono quer.

[F] Lacunas: (a) `objectives` são texto livre, sem regra — não mudam o jogo; (b) a cena não age sozinha por rodada (não há "o fogo se espalha", "a maré sobe"); (c) não há relógio: conflitos empatados dependem do `_stalemate_guard` (`STALEMATE_ROUNDS = 6`); (d) objetos de cena só existem como interação, não como cartas.

[R] Modelo Hand of Fate / Inscryption (pesquisa §4): **a LLM escolhe de um catálogo fechado; as cartas decidem; a LLM só narra**. A cena vira um tabuleiro com **Cartas de Cena** visíveis, um **Objetivo** com regra e um **Relógio** que garante fim.

## 2. Requisitos

**Cartas de Cena (ambiente)**
- **R1** — Catálogo `data/combat/cartas_de_cena.json` (~24 na v1), cada uma com `id, nome, regioes[], tags[], efeitos (gramática SPEC-330), quando (inicio_rodada|fim_rodada|a_cada_n_rodadas), pressagio (frase), sabor`. Exemplos de Valoria (nomes propostos, revisão do dono [D?]): *Névoa Cinza do Ermo* (Cego 1 em quem termina a rodada fora de cobertura), *Chão da Fornalha* (Sangria 1 em quem fica na zona quente), *Sinos de Nova Arcádia* (a cada 3 rodadas chega reforço da guarda — usa o mecanismo de reforço), *Maré Baixa de Brekmar* (zona alagada some na rodada 4), *Vigília dos Druidas Cinzentos* (Entropia +1 para todos no fim da rodada), *Telhado que Cede* (objeto vira armadilha na rodada 3).
- **R2** — `PreparedScene` ganha `cartas_de_cena: list[str]` (0–2 ids **do catálogo**, filtrados por região/tags do local). Id fora do catálogo → descartado com log; nunca número livre.
- **R3** — Cartas de Cena aparecem como **presságio de cena** (mesmo contrato público da SPEC-329) uma rodada antes de dispararem.

**Objetivo com regra**
- **R4** — `objectives` passa a aceitar `objetivo: {tipo, alvo?, n?}` com `tipo ∈ {derrotar_todos, sobreviver_n_rodadas, proteger(npc/aliado), alcancar_zona, destruir_objeto, interromper_ritual(n), capturar_vivo}` (catálogo fechado). Sem `objetivo` válido → `derrotar_todos` (comportamento de hoje).
- **R5** — Cumprir o objetivo encerra o conflito com desfecho próprio (`resolve_terminals`) e conta para espólio (SPEC-333) e para a narração final. `capturar_vivo` usa o golpe não-letal da SPEC-325 A.

**Objetos como cartas**
- **R6** — Com SPEC-328 `on`: ao entrar/estar na zona de um objeto com interação, a interação vira **carta temporária** na mão (`gerar_carta`, Exaurir, Fôlego 1). Sai da mão ao sair da zona. Sem SPEC-328, segue o fluxo de interação atual.

**Relógio**
- **R7** — Todo conflito tem **Relógio do Abismo**: a partir da rodada `R0 = 5` [D?], no início de cada rodada todos os participantes ganham +1 Entropia e a Carta de Cena mais forte dispara de novo. Narrado como "o Abismo se aproxima". Substitui o empate silencioso por pressão crescente; `_stalemate_guard` fica como rede de segurança.

**LLM**
- **R8** — O prompt de preparação recebe só os ids/nome/sabor elegíveis (máx. 12) e escolhe; nenhum efeito numérico no prompt. Guard de FallbackLLM: falha → cena sem Cartas de Cena e objetivo padrão.
- **R9** — Zero chamada LLM nova: a escolha entra no structured output de preparação já existente.

### Fora de escopo
Cartas de Cena criadas pela LLM (proibido — só catálogo). Mapa visual de zonas (SPEC-334 mostra a faixa de cena em texto).

## 3. Design técnico
- **Novo** `services/scene_cards.py`: `eligible(location, tags) -> list[dict]`, `forecast(scene, round) -> list[dict]`, `tick(ctx, round)`, `abyss_clock(ctx, round)`, `check_objective(ctx) -> str|None`.
- **Alterado** `encounter_preparation.py` (campos R2/R4 + validação), `conflict_orchestrator.run_round` (tick no início/fim; `check_objective` em `resolve_terminals`).
- **Novo** `data/combat/cartas_de_cena.json` + validador.

## 4. Plano (TDD)
1. `tests/test_scene_cards.py` — elegibilidade por região; id inválido descartado; tick determinístico; presságio 1 rodada antes.
2. `tests/test_objectives.py` — cada `tipo` encerra corretamente; ausência → `derrotar_todos`.
3. `tests/test_abyss_clock.py` — a partir de R0, Entropia +1/rodada; conflito de arena nunca passa de 12 rodadas.
4. R6 após SPEC-328.

## 5. Critérios de aceite
- [ ] R1–R9 com teste; 24 Cartas de Cena revisadas pelo dono
- [ ] Arena: duração p95 do conflito ≤ 10 rodadas
- [ ] `uv run pytest` verde; saves sem os campos novos carregam

## 6. Smoke real
1. Luta no Ermo: LLM escolhe *Névoa Cinza*; presságio aparece; efeito bate. 2. Escolta com `proteger`: NPC sobrevive → desfecho próprio. 3. Rodada 6+: Relógio narrado.

## 7. Riscos
- LLM escolher Carta de Cena incoerente com a prosa: filtro por região/tags + sabor no prompt.
- Relógio pune build defensiva: calibrar R0 na arena.
