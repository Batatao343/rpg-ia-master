# SPEC-331 — Cartas #04: A LLM monta a cena, a cena vira tabuleiro (Cartas de Cena, Objetivo e Relógio)

> **Status:** `done` (04/11, coordenador, autorização do dono "manda bala"; fechamento na nota final)
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
- **R7** — Todo conflito tem **Relógio do Abismo**: a partir da rodada `R0 = 5` (D6), no início de cada rodada todos os participantes que têm Carga ganham +1 Carga do Abismo (D-331-4: não Entropia) e a Carta de Cena mais forte dispara de novo. Narrado como "o Abismo se aproxima". Substitui o empate silencioso por pressão crescente; `_stalemate_guard` fica como rede de segurança.

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
- [x] R1–R9 com teste; 24 Cartas de Cena revisadas pelo dono
- [x] Arena: duração p95 do conflito ≤ 10 rodadas
- [x] `uv run pytest` verde; saves sem os campos novos carregam

## 6. Smoke real
1. Luta no Ermo: LLM escolhe *Névoa Cinza*; presságio aparece; efeito bate. 2. Escolta com `proteger`: NPC sobrevive → desfecho próprio. 3. Rodada 6+: Relógio narrado.

## 7. Riscos
- LLM escolher Carta de Cena incoerente com a prosa: filtro por região/tags + sabor no prompt.
- Relógio pune build defensiva: calibrar R0 na arena.

## 8. Notas de implementação (executor, 2026-10-27)

- **Flag** `RPG_SCENE_CARDS=off|shadow|on` (padrão `off`, fora de `combat_flags.CAPS`). Com `off`: schema, prompt e rodada idênticos (`PreparedScene` só vira `PreparedSceneWithCards` com shadow/on).
- **Catálogo** `data/combat/cartas_de_cena.json` (24, voz de Valoria, revisão do dono pendente) com campos `quando` (+`n`/`desde`/`uma_vez`), `escopo` (todos|herois|inimigos), `filtro` (visivel|zona_inicial), `efeitos` (gramática SPEC-330 + `aplicar_condicao` nomeada) e `acoes` cena-específicas fechadas (`entropia`, `deslocar`, `objeto_cai`).
- **Desvio D-331-1:** *Sinos de Nova Arcádia* dá Vigília 2 aos heróis a cada 3 rodadas em vez de reforço da guarda (reforços foram descartados pelo dono na SPEC-325 D).
- **Desvio D-331-2:** o teto de 12 rodadas é `scene_cards.clock_hard_stop`: na rodada 12 os hostis `fled` ("recuam diante do Abismo") e `combat_should_end` fecha; só com `on`.
- **Desvio D-331-3:** a LLM só escolhe Cartas/Objetivo no caminho que já chama a preparação (`_wants_prepared_scene`); encontros sem preparação seguem sem Cartas de Cena.
- **R5:** `out["objetivo"]={tipo,resultado}` + `scene["objetivo_resultado"]`; `_encounter_outcome` mapeia cumprido→`victory`, falhou→`defeat`. Espólio (SPEC-333) lê `objetivo_resultado`.
- **R6:** `scene_cards.sync_hand` (só `on` + `RPG_CARD_DECK=on`) injeta no catálogo em memória cartas `cena_<obj>_<hash>` (Exaurir, Fôlego 1, `frequencia: cena`) para `damage`/`apply_condition`; sai da mão ao sair da zona e nunca entra em compra/descarte.
- **Presságio de cena:** `combat["pressagios_cena"]` = lista pública `{id,nome,pressagio,quando,rodada}` da próxima rodada (SPEC-334 consome).

## 9. Correções da revisão Sol (2026-10-27)

- **D-331-4 (R7 corrigido, decisão do coordenador):** o Relógio do Abismo dá **+1 Carga do Abismo** por rodada, a partir da rodada 5, a todo participante que tem Carga (jogador e fichas que já a carregam), disparando `ao_entrar_carga`; o Abismo dispara pelo caminho normal (`_maybe_abyss`). Entropia é combustível das Cartas, então **não** é mais ganha pelo Relógio. A ação de cena `entropia` virou `carga` (3 cartas do catálogo). Mantém o redisparo da Carta de Cena mais forte.
- P1-1: `sync_hand` roda no início do nó; CLASSIFY aceita `cena_*` da mão; temporárias em registro separado (`cards.register_temp_card`, limpo por `reload_cards`), fora de `cards_for_class`/catálogo (P2-4).
- P1-3: a view de combate da API expõe `pressagios_cena` e `objetivo` (`tipo`, `alvo_nome`, `n`, `rodada`, `resultado`) com a flag `on`.
- P2-1: objetivo falho = `victory=False` (sem espólio) e `defeat`. P2-2: dano/efeito de ambiente sem fonte (sem retaliação/Marca/crédito de queda). P2-3: `shadow` não grava `cena_estado` nem `pressagios_cena`. P2-6: o prompt lista alvos válidos. P2-7: `forecast` prevê o redisparo do Relógio.
- **Follow-ups da re-revisão:** F-1 teste de objetivo falho com inimigo derrubado; F-2 registro temporário em LRU (sem limpeza total); F-3 validador só aceita os `kind` que `_apply_ambient` aplica. **F-4 (calibração):** a Carga do Relógio é do jogador e sobrevive ao fim do conflito, como a dos gatilhos de classe; confirmar na calibração da arena (R0 e p95 ≤ 10 rodadas).

## 10. Evidência: duração do conflito (SPEC-368 R9, 02/11)

`docs/spec368/metricas_epico.py`, 1800 conflitos (sementes 0–19, cartas `on`; arena sem as Cartas de cena): **p95 = 12 rodadas no total** (Devoto 11 · Sangromante 8 · Corruptor 9 · Arcanista 9 · **Médico de Campo 19**, 4,4 % de timeouts em 20 rodadas). O critério "p95 ≤ 10 rodadas" **não** foi atingido, só por causa do Médico (bot de cura longa); as demais Posturas ficam ≤ 11. Registrado sem mudar o critério (D-368-1); follow-up: relógio do Abismo/clock da 331 na arena e recalibrar o Médico.

- **Fechamento:** Auditoria de fechamento (04/11, coordenador; auditor só leitura cruzou cada critério com evidência): revisão Sol final aprovada (`handoffs/SPEC-331-sol-review.md` quando existe), suíte completa verde nos pousos, smokes reais: `docs/spec363/achados-smoke3.md`, `docs/spec364/achados-smoke4.md`, `docs/spec364/smoke-final.md`, `docs/spec367/smoke-{local,staging}.md`, `docs/spec368/smoke-local.md`, `docs/spec387/smoke-{local,staging}.md`, `docs/spec389/smoke{,-local}.md`, `docs/spec390/smoke.md`. Métricas não atingidas do épico ficam registradas (D-368-1) e seguem para a SPEC-369. Objeto de cena no smoke 3; escolta em 368 item 4, 387 item 9 e falha narrada pela causa em 389 item 7; Carta de cena serverless corrigida na 387 (S6-1). p95 12 → SPEC-369. Cartas de Cena aprovadas em bloco (27/10).

- **SPEC-369 (04/11):** duração com p95 total 10 e Médico 15, com timeout de 2,2 % sob o limite registrado de 3,3 % (D-369-13). No jogo, o Relógio do Abismo encerra na rodada 12. Números finais em docs/spec369/CONFIRMACAO.md (confirmação única, sementes 260–339).
