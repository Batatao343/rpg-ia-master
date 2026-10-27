# SPEC-335 — Cartas #08: Expansão do Acervo, onda 1 (identidade por Postura, +220 cartas)

> **Status:** `draft`
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
