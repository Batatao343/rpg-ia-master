# SPEC-335 — Cartas #08: Expansão do Acervo, onda 1 (identidade por Postura, +220 cartas)

> **Status:** `in-progress` (Lote 0 parcial + Lote 1 Arcanista pousados em 27/10 após re-revisão Sol APPROVED; voz do Lote 1 `pendente-dono` — bloqueia release; faltam Lotes 2–6 e `test_card_variety`)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-330 (gramática, glossário, orçamento), SPEC-336 (esteira de autoria e lint). Etapa 1 (reparo do acervo atual) pode começar só com SPEC-330.
> **Desbloqueia:** SPEC-333 (espólio precisa de pool largo)
> **EXECUTOR_MODEL:** `Terra` por lote (≤ 40 cartas) · **REVIEW_MODEL:** `Sol` (mecânica) + **dono** (nomes/voz) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] Acervo de jogador: 5 Posturas × ~52 cartas espalhadas em 9 tiers (≈ 6 por tier por classe) — no nível 1–3 o jogador vê poucas opções. 62 das 308 cartas são `dano` simples; 35 sem `descricao`; as 80 de `tiers_5_plus.json` têm `descricao`/`contrapartida` genéricas ("converte risco acumulado em uma decisão mecânica de fim de campanha").

[R] Pesquisa §2: identidade vem de (a) **color pie** — o que cada Postura faz, faz às vezes e **nunca** faz; (b) **raridade = complexidade** (comum: 1 linha, ≤ 1 interação; rara pode ser "espetada"); (c) **toda carta tem um momento em que é a melhor jogada** — escrito junto com a carta; (d) **gerar muito e cortar**.

## 2. Requisitos

**Roda das Posturas (color pie de Valoria)** [D? — proposta para o dono aprovar antes do 1º lote]

| Postura | Primário | Secundário | Nunca |
|---|---|---|---|
| Devoto do Abismo | Vigília, provocar, dano ao ser atingido, Entropia por dor | Interromper, cura própria pequena | comprar muitas cartas, Esconder |
| Sangromante | Sacrifício, Sangria, Eco, dano alto barato | Ressoar, roubo de Vitalidade | Vigília grande, cura de aliado |
| Corruptor | Rachadura, Torpor, Fardo **no inimigo**, decadência por domínio | Marca do Abismo, controle de zona | cura, proteção a aliado |
| Arcanista Cinzento | Chamado, comprar/descartar, Vazão (caldeira), dano em área | Ressoar, Guardar | Sacrifício, provocar |
| Médico de Campo | cura, purgar, Guardar, reduzir Carga de aliado | Torpor, estabilizar, comprar | dano alto, Rachadura |

- **R1** — Cada Postura recebe **+36 cartas** (12 por subclasse: `consagrado/zeloso/enlutado`, `exposto/avaro/silencioso`, `biologia/alma/inorganica`, `calibrado/descoberto/improvisador`, `cirurgiao_trincheira/boticario/cirurgiao_ferro`) = **180**.
- **R2** — **+40 cartas neutras de Valoria** (`data/cards/valoria_neutras.json`), obtidas só por espólio/loja/quest, ancoradas no lore: armas e técnicas regionais (Nova Arcádia, Ermo, Brekmar, Saídas Baixas, Kahen), itens de `lore_nova/items.txt` como cartas (ex.: frasco, pólvora, relíquia), cada uma com `origem_lore: <id do codex>`.
- **R3** — **Raridade** nova `raridade ∈ {comum, incomum, rara, abissal}`; distribuição por lote 50/30/15/5. Comum: ≤ 1 efeito + ≤ 1 palavra-chave; incomum: ≤ 2; rara: livre dentro do orçamento; abissal: custo explícito em Entropia/Vitalidade e efeito que quebra uma regra (com Exaurir).
- **R4** — **Campo obrigatório `momento`**: uma frase "melhor jogada quando…" (não exibida ao jogador; usada pela revisão e pelo lint de redundância). Carta sem `momento` distinto de todas as outras da mesma Postura = rejeitada.
- **R5** — **Reparo do acervo atual**: preencher as 35 `descricao` vazias; reescrever `descricao`/`contrapartida` das 80 cartas de `tiers_5_plus.json` com sabor real; reclassificar as 308 em `raridade` e preencher `momento`. 0 % de mudança mecânica nesta etapa (teste de equivalência da SPEC-330).
- **R6** — **Variedade mínima por tier**: em cada faixa de nível, cada Postura oferece ≥ 10 cartas, ≥ 4 `kind`s distintos e ≥ 3 palavras-chave distintas.
- **R7** — **Voz**: nome ≤ 4 palavras, PT-BR, sem anglicismo; `descricao` ≤ 140 caracteres, concreta, sensorial, de Valoria (Abismo, cinza, ferro, sangue, éter); proibido citar número na descrição (número vem do `render_card_text`).
- **R8** — Lotes de ≤ 40 cartas; cada lote passa no lint (SPEC-336), na arena por Postura (taxa de vitória ±10 % da linha de base) e na revisão de voz do dono antes de entrar no pool.

### Fora de escopo
Cartas de inimigo (SPEC-332), Cartas de Cena (SPEC-331), status/maldições (SPEC-333).

## 3. Design técnico
- Arquivos novos por subclasse: `data/cards/posturas/<classe>_<subclasse>.json`; neutras em `data/cards/valoria_neutras.json`. Carregamento via o mesmo loader de `data/cards/` (glob recursivo).
- Campos novos: `raridade`, `momento`, `origem_lore?`, `efeitos` (SPEC-330).
- Sem mudança de motor nesta spec.

## 4. Plano
1. **Lote 0 — reparo (R5)**, sem mudança mecânica.
2. **Lotes 1–5** — uma Postura por lote (36 cartas), na ordem que o dono preferir [D?].
3. **Lote 6** — 40 neutras de Valoria.
4. Após cada lote: lint, arena, revisão do dono, `uv run python scripts/validate_content.py`, reindex RAG se o codex for tocado.

## 4.1 Andamento (decisões do dono 27/10: roda como na tabela; ordem D9 Arcanista → Sangromante → Devoto → Corruptor → Médico; voz por amostra de 20 %)

- [~] **Lote 0 (R5) — PARCIAL** — 35 `descricao` vazias preenchidas; 80 de `tiers_5_plus.json` com `descricao` e `contrapartida` próprias (80 únicas); `raridade` (derivada do `patamar`; inimigos=comum) e `momento` nas 308; zero mudança mecânica (golden da 330 e snapshot intactos). **O `momento` das 4 Posturas (Devoto, Sangromante, Corruptor, Médico), dos inimigos e das virtudes é placeholder** (`momento_placeholder: true`, 255 cartas): tem duplicatas e pares acima do limiar e é reescrito no lote de cada Postura (2–5); só o Arcanista está completo. Lint recusa a frase-modelo de `descricao` e de `contrapartida`; `gen_tiers_5_plus.py` preserva o texto existente (só `--force` sobrescreve).
- [x] **Lote 1 — Arcanista Cinzento** (`data/cards/posturas/arcanista_cinzento_{calibrado,descoberto,improvisador}.json`, onda 1, `_ondas.yaml`): 36 Cartas, 12 por subclasse, raridade 16/13/5/2 (comum/incomum/rara/abissal — 10 comuns viraram 1 efeito ou subiram para incomum após `check_raridade`, R3). Lint verde; arena no **protocolo de lote** (`--protocolo lote`, v. `docs/guias/CARTAS.md`) sem bandeira — relatório, comando e limitações em `docs/spec335/RELATORIO-arena-lote1.md`. **Voz pendente do dono**: `_ondas.yaml` grava `revisor_voz: null` + `voz_status: pendente-dono`; o `validate_content` avisa. Amostra (7): `arc1_cal_estilhaco`, `arc1_cal_mares`, `arc1_cal_quadrante`, `arc1_cal_segunda_medicao`, `arc1_des_brasa`, `arc1_des_caldeira_sem_fundo`, `arc1_imp_ultima_gambiarra`.
- Registros da re-revisão Sol: **P2-7** a distribuição de raridade do Lote 1 (16/13/5/2) está fora da R3 (50/30/15/5) por tolerância de ±2 por faixa, **compensada nos Lotes 2–5** (mais comuns, menos incomuns). **P2-10** `arc1_des_palma` (Eco) e `arc1_des_faisca` (Ressoar) só têm o orçamento como freio: a arena não mede Eco/Ressoar. **P2-11 (follow-up na SPEC-336)**: protocolo da arena (testar também a `level_req`+3 contra o baralho do nível seguinte), bandeira `fraca` (delta ≤ −10 pp com amostra suficiente) e bot que defende antes de ser ferido.
- [ ] Lotes 2–5 (Sangromante, Devoto, Corruptor, Médico) e Lote 6 (40 neutras).
- [ ] R6 (`tests/test_card_variety.py`) — só fecha quando as 5 Posturas tiverem os lotes.

Desvios/achados (revisão Sol aplicada): (1) o protocolo de arena é do coordenador/336, não do executor; o poder das cartas de golpe continua em efeitos secundários que a arena não mede (limitação registrada no relatório; o orçamento é o freio). (2) O `orcamento` lê `raridade: abissal` (faixa `abissal` = `epica`; legadas inalteradas). (3) Defensivas com delta negativo não são bandeira; follow-up 336 (bandeira `fraca`, bot que defende antes, arena medindo efeitos secundários). (4) `tests/test_card_lint.py` (contagem do legado fixa em 323; ondas e `inf_` fora) e `tests/test_mecanica_orfa.py` (vigilia/revelar/mover_alvo_zona por Carta real; comprar/ganhar_folego reaproveitam os testes de pilhas da 330) atualizados.

## 5. Critérios de aceite
- [ ] Acervo de jogador ≥ 520 cartas (308 + 180 + 40 − cortes)
- [ ] R6 verdadeiro para todas as Posturas e tiers (teste `tests/test_card_variety.py`)
- [ ] 0 descrições vazias/genéricas (lint)
- [ ] Nenhuma Postura com taxa de vitória fora de 45–75 % na arena padrão
- [ ] `uv run pytest` verde

## 6. Smoke real
Criar personagem de cada Postura, jogar 1 conflito com LLM real: narração usa o sabor da carta, não inventa efeito.

## 7. Riscos
- Volume × qualidade: "gerar muito e cortar" — a esteira rascunha ~2× o necessário e corta.
- Power creep: orçamento + arena por lote.
- Lore: o executor consulta o codex por Grep (nunca lê lore inteiro).
