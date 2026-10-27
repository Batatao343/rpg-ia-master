# SPEC-336 — Cartas #09: Esteira contínua de autoria de cartas (sempre crescer, nunca repetir)

> **Status:** `draft`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-330 (gramática + `power_score` + `render_card_text`), SPEC-090/285 (arena/simulação de combate)
> **Desbloqueia:** SPEC-335, SPEC-332 (volume), ondas futuras (onda 2, 3…)
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente · **[R]** recomendação.

---

## 1. Contexto & Objetivo

O dono quer **"aumentar o número de cartas sempre"**, com cada uma soando individual. Sem processo, volume vira repetição e power creep.

[F] Já existem: `scripts/gen_cards_v4.py` (gerador das cartas v4), `services/content_validator.py` (valida `mecanica_classe` etc.), `scripts/validate_content.py`, a arena/simulação de combate (SPEC-090, SPEC-285) e o `playtest/` com telemetria.

[R] Pesquisa §2/§5: Slay the Spire e Monster Train balancearam por **taxa de escolha e taxa de vitória por carta**; "gerar milhares e cortar o refugo"; vocabulário fechado; toda carta precisa de um momento.

Objetivo: uma **esteira** reprodutível — rascunho → lint → simulação → curadoria → pool — com metas por onda e métricas de uso que mandam cortar ou reforçar.

## 2. Requisitos

**Guia e template**
- **R1** — `docs/guias/CARTAS.md`: roda das Posturas (SPEC-335), regras de raridade, voz, glossário, orçamento, checklist do `momento`, exemplos bons/ruins. `docs/templates/carta.json` com todos os campos.

**Rascunho**
- **R2** — `scripts/cards/draft.py --postura X --subclasse Y --n 24 --raridades ...`: usa `get_llm(tier=SMART)` com structured output (guard FallbackLLM) para propor cartas **só no vocabulário fechado**, recebendo glossário, roda das Posturas, cartas existentes da subclasse (nomes + `momento`) e 3 trechos de lore via `query_rag`. Saída em `data/cards/_rascunhos/` (fora do pool). Sem chave → modo vazio com aviso (nunca inventa offline).

**Lint determinístico**
- **R3** — `scripts/cards/lint.py`: schema; vocabulário; orçamento (`power_score` na faixa de raridade × custo); **redundância** — assinatura mecânica `(kinds, palavras-chave, gatilho, condição, custo)` + similaridade de `momento` (embeddings já usados no RAG) acima de limiar → "provável duplicata de X"; nome único no acervo; voz (≤ 4 palavras, sem número na descrição, sem termos fora do glossário de lore `data/cards/_lexico_valoria.txt`); color pie (efeito "Nunca" da Postura = erro).

**Simulação**
- **R4** — `scripts/cards/sim.py --lote <arquivo>`: injeta as cartas do lote em baralhos de teste da Postura e roda N conflitos de arena determinísticos por encontro-padrão; relata por carta: **taxa de uso quando na mão**, **delta de vitória com/sem a carta**, dano/proteção por Fôlego. Marca "carta em branco" (uso < 5 %) e "dominante" (uso > 60 % ou delta > +8 pp).

**Curadoria e promoção**
- **R5** — `scripts/cards/promote.py`: move do rascunho para o pool só cartas com lint verde e sim sem bandeira, registra em `data/cards/_ondas.yaml` (`onda, data, autor, revisor_voz`). Revisão de voz do dono é o último passo [D? — o dono quer revisar todas ou só amostra de 20 %?].

**Telemetria em jogo real**
- **R6** — Eventos `card_offered`, `card_picked`, `card_played`, `card_exhausted` no trace (SPEC-251) e no `playtest/`; `scripts/cards/metrics.py` gera tabela por carta (pick rate, play rate, vitória) a partir de playtests e do staging.
- **R7** — Regra de corte/ajuste por onda: cartas com pick rate < 5 % em ≥ 200 ofertas → reescrever ou cortar; > 60 % → nerf. Mudança sempre por nova versão da carta (`versao`), nunca edição silenciosa — saves guardam id, motor lê versão vigente.

**Metas**
- **R8** — Cadência proposta [D?]: **1 onda por mês**, ≥ +60 cartas de jogador e +20 de inimigo por onda, cortes permitidos. Meta de 12 meses: ~1 200 cartas de jogador. Painel simples `docs/cartas/PAINEL.md` gerado (contagem por Postura/raridade/tier/kind/palavra-chave).
- **R9** — Expansão do léxico: no máximo **2 palavras-chave novas por onda**, cada uma com ≥ 6 cartas na mesma onda (evita keyword com 2 cartas — armadilha citada na pesquisa).

### Fora de escopo
Geração de arte por carta (pode reaproveitar SPEC-326 depois). Editor visual de cartas.

## 3. Design técnico
- **Novos** `scripts/cards/{draft,lint,sim,promote,metrics,painel}.py`; `data/cards/_rascunhos/`, `_ondas.yaml`, `_lexico_valoria.txt`.
- `content_validator` reusa as regras do lint (fonte única) para o CI.
- CI: `lint.py` roda em todo PR que toca `data/cards/`.

## 4. Plano (TDD)
1. `tests/test_card_lint.py` — duplicata detectada; color pie violado; número na descrição; nome repetido.
2. `tests/test_card_sim.py` — sim determinística; marca carta em branco e dominante em lote sintético.
3. `tests/test_card_draft.py` — guard FallbackLLM; saída só no vocabulário (MockLLM).
4. Primeira onda real = SPEC-335.

## 5. Critérios de aceite
- [ ] Esteira roda ponta a ponta num lote de 10 cartas sintéticas
- [ ] CI falha em carta duplicada/fora do orçamento
- [ ] `docs/guias/CARTAS.md` publicado; `uv run pytest` verde

## 6. Smoke real
`draft.py` com chave real gera 12 cartas do Médico de Campo `boticario`; lint corta ≥ 1; sim roda; 1 carta promovida e jogada num conflito real.

## 7. Riscos
- LLM tende a cartas parecidas: o prompt recebe as existentes + lint de redundância + "gerar 2× e cortar".
- Custo LLM do rascunho: SMART, offline, sob demanda (não roda no jogo).
