# SPEC-238 — Jev decide a fonte do loot (J1b da SPEC-217)

> **Status:** `approved` — dono, 2026-10-18: "boa, cria uma spec para o jev cobrir o loot e vamos usar ele também". A aprovação inclui a execução e o aumento de orçamento proposto: **+30 chamadas live (~US$ 0,30)**, teto total da SPEC-217 de 160/US$ 1,60 para **190/US$ 1,90**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-217 J1 congelada (`plain+target+guard@0.50`, digest `sha256:80225d16…10f5`, revisão Astra APPROVED)
> **Desbloqueia:** J2 da SPEC-217 com a política que cobre loot (se adotada)
> **EXECUTOR_MODEL:** `Sol` (≡ Opus) · **REVIEW_MODEL:** `Astra` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `true` — o novo congelamento muda a política que a J2 testa
> **EVAL_AUTHORING_REQUIRED:** `false` — reusa DEV/FROZEN da SPEC-217; o oráculo de fonte do DEV vem dos datasets de origem (ver R3)

Rótulos: **[F]** fato · **[D]** decisão do dono · **[H]** hipótese · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Na J1 da SPEC-217 a política congelada manda todo `loot` para o CLASSIFY (`loot_context_out_of_scope`), porque o router exige, além da rota, a fonte do loot: `RouterDecision.loot_context ∈ {TREASURE, SHOP, CRAFT}` vira `loot_source` no payload (`agents/router.py`; ausente ⇒ `TREASURE`). No DEV isso custou 13/52 elegíveis de cobertura (35/52 cobertos). **[F]** SPEC-179 mediu a fonte do loot pelo Jev: 4/4 nos dois braços (amostra pequena).

**[D]** O dono pediu que o Jev cubra o loot também.

**Objetivo.** Um estágio de fonte do loot na **mesma** requisição Jev da J1 (sem chamada extra): quando o Jev roteia `loot` com confiança e a fonte passa o guard Python, B usa a decisão do Jev; senão cai no CLASSIFY, como na J1. Medir no DEV (J1b) e adotar só se não houver nenhum erro.

## 2. Requisitos

- **R1 — Estágio na mesma requisição.** A requisição J1b = requisição congelada da J1 (pergunta de rota `plain` + alvo, mesmas features) + uma pergunta `loot_source` (chaves `treasure|shop|craft|none`) + duas features públicas. Uma chamada por caso, como na J1.
- **R2 — Features públicas e determinísticas.** `merchant_here` = existe mercador do catálogo `data/merchants.json` no local atual (`services.economy.merchants_at`); `craft_station` = o nó do mapa tem `craft_tags`. Local desconhecido ⇒ `None` (fora do fio). Os sinais de verbo (`trade`, `craft`, `take`) são os da J1. Nada de NPC, segredo, PII ou lore oculto. `DecisionState` ganha os dois campos opcionais; o payload do rollout de produção não muda (teste).
- **R3 — Oráculo de fonte.** O DEV selado não tem `loot_source`. O oráculo dos 13 casos DEV de loot fica em `evals/experiments/data/spec238_loot_oracle.json` (SHA-256 `129ac6fb…0493`), com proveniência por caso: 7 de `routing_actions.jsonl`, 3 do corpus SPEC-179 (teste confere contra a fonte) e 3 sintéticos do próprio rationale do DEV (`buy/sell` ⇒ SHOP, `pick` ⇒ TREASURE). O DEV e o FROZEN não mudam. O FROZEN não é aberto.
- **R4 — Política.** Gates Python e a decisão J1 primeiro (nada muda para não-loot). Só quando a J1 devolveria `loot_context_out_of_scope`: `loot_source` ausente/`none` ⇒ CLASSIFY; confiança < τ_loot ⇒ CLASSIFY; **guard de loot** (opcional na grade): exige verbo de item (`take|trade|craft`); `SHOP` exige `trade` ou `merchant_here`; `CRAFT` exige `craft` ou `craft_station`; `TREASURE` exige ausência de `trade` e `craft`. Falhou ⇒ CLASSIFY.
- **R5 — Pré-registro.** Amostra, grade, métricas e regra de adoção em [docs/spec217/j1b-loot.md](../docs/spec217/j1b-loot.md), commitados antes de qualquer chamada live.
- **R6 — J1b live (só DEV).** ≤ 30 chamadas Jev, zero CLASSIFY; ledger compartilhado da SPEC-217 (`j1b_calls` ≤ 30, total ≤ 190); qualquer erro de provider para o run sem score; `max_retries=0`. Raw antes do score; summary reproduzível offline; hashes registrados; cópia dos artifacts para o scratchpad.
- **R7 — Adoção.** Adota se existir variante com **0 erro de fonte coberto, 0 erro de rota/alvo coberto, 0 escalada insegura e cobertura > baseline** (a política J1 sem estágio, sobre as mesmas respostas). Adotada ⇒ congelar `FROZEN_J1B_POLICY` + digest (inclui o digest J1 e o código do estágio) com teste, atualizar docs e handoff Astra. Não adotada ⇒ a política J1 aprovada continua sendo a da J2, com o porquê documentado.
- **R8 — J2.** Não rodar a J2 aqui. Orçamento da J2 inalterado (≤ 100; uma chamada Jev por caso). Se adotada, a J2 acrescenta (pré-registrado agora): **R9.7** — nos casos FROZEN em que B cobre `loot`, a fonte de B deve igualar a `loot_context` do CLASSIFY (braço A) do mesmo caso/réplica, 0 divergência; e, se o FROZEN tiver oráculo de fonte, 0 erro. Falhou ⇒ `NO_GO`.
- **R9 — Produção intacta.** `RPG_JEV_ROUTER_MODE` default `off`, `PRIMARY_CALIBRATION=None`, `services/jev_rollout.py` sem mudança de comportamento; nenhuma mudança de schema de save.

### Fora de escopo
`item_ref`/quantidades, `TradeIntent`, `EncounterScanner` e outros callsites CLASSIFY; abrir o FROZEN; rodar a J2.

## 3. Design técnico

- `evals/experiments/spec238_loot.py`: features, pergunta `loot_source`, `j1b_request`, `LootPolicy`, `loot_hybrid_decision` (envolve `hybrid_decision` da J1 sem editá-lo — o digest J1 aprovado continua válido), amostra, score/seleção, `J1bLedger`, runner (`--phase run|summarize`).
- `services/jev_decision.py`: `DecisionState.merchant_here`/`craft_station` opcionais (`None` fora do fio).
- `tests/test_spec238_loot.py`: política, guard, features, oráculo, amostra, ledger, parada por erro, summary reproduzível, seleção.

## 4. Critérios de aceite

- [ ] Spec, pré-registro e testes commitados antes da primeira chamada live.
- [ ] J1b ≤ 30 chamadas; total ≤ 190; ou parada por erro registrada.
- [ ] Raw/summary com SHA-256; summary reproduzido offline.
- [ ] Decisão de adoção aplicando a R7 sem reinterpretação; se adotada, novo digest travado por teste e handoff Astra.
- [ ] `uv run pytest` e `ruff` verdes (exceto falhas conhecidas documentadas).
- [ ] Default `off` preservado.

## 5. Riscos

- DEV pequeno (13 loot) e já visto: a confirmação é a J2 no FROZEN (3 casos loot), com a R9.7.
- A pergunta extra pode mudar as respostas de rota; por isso a amostra inclui 17 casos não-loot (8 críticos + 9 por seed) e qualquer erro coberto bloqueia a adoção.
