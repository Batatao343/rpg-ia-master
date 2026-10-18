# SPEC-217 — Reavaliação do Jev/TypeSafe no router: estruturação (J1) + A/B confirmatório (J2)

> **Status:** `approved` — dono aprovou a execução em 2026-10-18 ("concordo com sua opção de especialista. teste o JEV agora."), incluindo chamadas reais Jev + CLASSIFY dentro do teto da §6, e pediu uma fase de melhoria da estruturação do Jev antes do teste ("vê se vc não consegue estruturar o JEV de uma maneira melhor para ele acertar mais também"). Reescrita em 2026-10-18 após o `NO_GO` da SPEC-214.
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-200 `done` (baseline de latência) · SPEC-177, SPEC-178, SPEC-179, SPEC-180 `done` (adapter, A/Bs anteriores, rollout `off|shadow|primary`)
> **Desbloqueia:** nada obrigatório
> **Origem:** pacote `proximas-specs/…`, prompt 13; reescrita por decisão do dono em 2026-10-18
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — congelamento da estrutura ao fim da J1, regra de decisão, raw/summary e calibração antes de qualquer `shadow`/`primary`
> **EVAL_AUTHORING_REQUIRED:** `true` — corpora DEV e FROZEN, sem sobreposição e com hash, autorados em tarefa SEPARADA antes da J1; especificação em [handoffs/SPEC-217-eval-authoring.md](../handoffs/SPEC-217-eval-authoring.md)

Rótulos: **[F]** fato observado · **[D]** decisão do dono · **[H]** hipótese · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** SPEC-177..180 `done`. `services/jev_decision.py` (adapter Choice/Noul/Score, DTO `DecisionState`, deadline total, erro fechado) e `services/jev_rollout.py` (`RPG_JEV_ROUTER_MODE` default `off`; `shadow` observa sem mudar a rota; `primary` exige `RPG_JEV_ROUTER_PRIMARY_APPROVED=1` **e** `PRIMARY_CALIBRATION=(evidence_id, limiar)` congelado em código — hoje `None`; kill switch `decision_backend:jev` em `services/kill_switches.py`, SPEC-196). No contrato `primary` atual só `storyteller`/`none` confiantes são aceitos; qualquer rota que precise de target/loot cai para CLASSIFY.

**[F]** Evidência anterior: SPEC-178 — rota CLASSIFY 48/48 vs Jev 46/48 nos elegíveis (3 réplicas), latência p50 do backend 1.367,5 ms vs 265,5 ms; as duas divergências foram `FALO COM CORVO` (variante em maiúsculas) → `combat_agent` com confiança 0,30/0,27. SPEC-179 — target representável CLASSIFY 5/8 vs Jev 6/8 (Jev perde os acertos `alias` e `enemy` de A). SPEC-180 — `NO_GO`: regressão pareada sem fallback seguro; só 2/16 (12,5 %) elegíveis ao contrato `primary`.

**[F]** Estrutura usada até aqui (`evals/experiments/jev_router_ab.py`): uma única Choice de 5 opções cujas `instructions` falam em `COMBAT/NPC/LOOT/STORY` enquanto as chaves são `combat_agent/npc_actor/loot/storyteller/none` (rótulos inconsistentes); descrições de uma linha; `DecisionState` envia só `action`, `location_id`, `in_combat` e `active_npc` — sem a lista de NPCs em cena, sem último interlocutor e sem sinais de verbo extraídos em Python. Rota e alvo nunca foram decididos em dois estágios.

**[F]** Baseline real (SPEC-214, [gate-real-2026-10-17](../docs/spec214/gate-real-2026-10-17.md), DeepSeek + Jina, 20 turnos SSE em staging): TTLT p50 10.487 ms; fase `router` p50/p95 1.473/2.023 ms, **13,4 %** do TTLT. A pré-condição de gargalo da versão anterior (decisão ≥ 10 % do TTLT p50) está atendida para o router.

**[D]** SPEC-214 fechou `NO_GO` por medição (2026-10-18): a hipótese "(a) memória de cena vs RAG profundo" sai do escopo. O dono autorizou testar o Jev no router agora e pediu antes uma tentativa de estruturar melhor a decisão para o Jev acertar mais.

**Hipótese [H].** Com uma decisão melhor estruturada (J1) e Jev usado só quando confiante, com CLASSIFY nos demais casos, a latência do router cai ~1,1 s/turno no p50 sem perda relevante de acurácia. O ganho só existe na fração de turnos resolvida pelo Jev; nos turnos de fallback o Jev **soma** latência (chamadas sequenciais).

**Objetivo.** (J1) iterar a estrutura da decisão Jev num corpus DEV com orçamento pequeno e registrar cada variante; (J2) rodar **uma vez** um A/B pareado e pré-registrado no corpus FROZEN, nunca visto na J1, que decide GO/NO_GO para congelar `PRIMARY_CALIBRATION` e para um passo opcional de `shadow` em staging. `primary` em produção continua exigindo aprovação separada do dono.

## 2. Requisitos

### Corpora e separação

- **R1 — Dois corpora sem sobreposição.** Autorados e congelados (SHA-256 + commit) por tarefa separada **antes** da J1, conforme o handoff: **DEV** (casos de desenvolvimento já vistos — rota da regressão `routing_actions`, corpus SPEC-179 — mais sintéticos novos) e **FROZEN** (confirmatório, só casos novos). Um verificador checa ausência de sobreposição por `id`, por ação normalizada (casefold, sem acento/pontuação) e por fixture. O executor da J1/J2 não lê o conteúdo do FROZEN antes do run J2 (só o hash e a contagem) e não altera nenhum dos dois.
  **Selo (autoria concluída):** DEV sha256 `256d24bd53a8eda63daf0d6cd15d413ddd2c844b5f57771df8753ce6e5305f3d`, FROZEN sha256 `442725e5dca9be7ed71c9abaa730cc7b61fd15180a04d4a290545794621d9d48`; detalhes em [docs/spec217/corpus.md](../docs/spec217/corpus.md). O executor da J1 **não deve ler** `evals/experiments/data/spec217_frozen.jsonl`.

### J1 — estruturação do Jev (DEV)

- **R2 — Diagnóstico primeiro.** `docs/spec217/j1-diagnostico.md` analisa os erros conhecidos (SPEC-178: caso `CORVO` em maiúsculas; SPEC-179: `alias`, `enemy`, `over20`, `missing_id`) a partir de `docs/spec178`, `docs/spec179`, raws em `evals/runs/jev-router-ab/` e `evals/runs/jev-target-loot/` quando presentes localmente (gitignored; se ausentes, registrar e usar os relatórios), e do payload/Choice efetivamente enviados. Sem chamada live.
- **R3 — Espaço de variantes.** Cada variante é uma combinação declarada de, entre outras: (a) rótulos e descrições por rota consistentes com as chaves, com exemplos positivos e contra-exemplos curtos; (b) features determinísticas mínimas derivadas em Python do estado público — NPCs em cena (IDs/nomes visíveis, limitado), combate ativo, último interlocutor, flags de verbo explícito (falar/perguntar, atacar, pegar/comprar/vender, ir/viajar, observar), ação normalizada de caixa; (c) decisão em dois estágios: rota grossa e depois alvo numa Choice fechada sobre os candidatos em cena (≤ 20, sem truncar; acima disso ou sem ID canônico ⇒ CLASSIFY); (d) abstenção explícita (`none`/confiança < τ) ⇒ CLASSIFY; (e) gates Python sempre antes do Jev. Campos novos no `DecisionState` são permitidos só se derivados de estado público, limitados em tamanho, sem segredo/PII/lore oculto, com teste.
- **R4 — Registro de variantes.** `docs/spec217/j1-variantes.md` lista cada variante tentada: ID, descrição, diff/commit, chamadas gastas, score DEV (acurácia de rota, acurácia de alvo quando aplicável, cobertura = fração resolvida pelo Jev com confiança ≥ τ, escaladas inseguras, p50/p95 de latência) e a decisão de manter/descartar. Nenhuma variante é omitida.
- **R5 — Orçamento J1.** ≤ **60 chamadas externas** (Jev + CLASSIFY) no total da J1, dentro do teto geral da §6. A maioria da iteração deve usar avaliação offline (features, gates, contagem de representáveis) antes de gastar chamadas.
- **R6 — Congelamento ao fim da J1.** Escolhida a melhor variante pelo score DEV, congelar em commit: estrutura (perguntas, opções, descrições, features), política híbrida e limiar `τ` (default 0,50; pode ser ajustado **somente** com dados DEV). Revisão Astra do congelamento antes da J2. Se nenhuma variante melhorar a baseline da SPEC-178 no DEV, a J2 ainda roda com a melhor disponível (resultado `NO_GO` é válido).
  **Selo J1 (2026-10-18, revisão Astra APPROVED com emenda — [parecer](../handoffs/SPEC-217-ASTRA-J1-review.md)):** variante `plain+target+guard@0.50` — pergunta de rota `plain` (rótulos coerentes com as chaves) + estágio de alvo restrito aos candidatos de cena na **mesma** requisição, features `scene`/`last_speaker`/`verbs` + ação em minúsculas, `τ = 0,50`, **com guarda de combate** (emenda Astra: `combat_agent` só com verbo de ataque ou combate ativo; empatou no DEV), `loot` ⇒ CLASSIFY; `FROZEN_J1_POLICY` em `evals/experiments/jev_router_hybrid.py`, hash de estrutura `sha256:80225d161ff31f226919c67b34195bdd864d5aece3c5dfc95f411093f3dd10f5` (agora inclui o código das features/política; o hash anterior `950917…4b81` foi superado). DEV: rota standalone 52/52, cobertura 35/52, 0 erro coberto, 0 escalada insegura; 60/60 chamadas J1. Detalhes em [docs/spec217/j1-variantes.md](../docs/spec217/j1-variantes.md) e [docs/spec217/README.md](../docs/spec217/README.md). Na J2 cada caso elegível custa 1 Jev + 1 CLASSIFY (`4 + 16×2×3 = 100`).

### J2 — A/B confirmatório (FROZEN, uma vez)

- **R7 — Braços.** A = caminho atual (gates Python → CLASSIFY, contrato completo do router). B = política híbrida congelada na J1, calculada a partir das mesmas chamadas: gates Python iguais; Jev; se confiante e representável na estrutura congelada, usa Jev; senão usa o resultado CLASSIFY do mesmo caso e réplica. Latência de B no fallback = soma das chamadas Jev + CLASSIFY. Se a estrutura tiver dois estágios, os dois contam na latência e no orçamento.
- **R8 — Réplicas e pareamento.** 3 réplicas; em cada réplica cada caso elegível recebe as chamadas de ambos os braços na mesma ordem embaralhada por seed declarada; casos resolvidos por gate Python fazem 0 chamadas. O FROZEN é usado uma única vez; repetir exige nova autorização do dono e é reportado como tal.
- **R9 — Regra de decisão (pré-registrada, todas obrigatórias para GO):**
  1. **Não-inferioridade de rota:** `acc(B) ≥ acc(A) − 2,5 pp` sobre as observações elegíveis pareadas (casos × 3 réplicas) **e** no máximo 1 perda pareada (B erra onde A acerta).
  2. **Alvo (se a estrutura decide alvo):** `acc_alvo(B) ≥ acc_alvo(A)` nos casos com alvo; nenhum alvo fora dos candidatos em cena.
  3. **Escalada insegura = 0:** nenhuma decisão final de B igual a `combat_agent` com oráculo diferente.
  4. **Ganho de latência:** `p50(lat_router(A)) − p50(lat_router(B)) ≥ 500 ms` nos elegíveis **e** `p95(lat_router(B)) ≤ 1,10 × p95(lat_router(A))`.
  5. **Gates Python:** 100 % dos casos de gate Python com a mesma rota em A e B e zero chamadas.
  6. **Sem erro de provider:** zero HTTP 4xx/5xx, timeout, quota ou resposta inválida (ver R10). Run interrompido não gera GO.
  Falhou qualquer item ⇒ `NO_GO`. Custo é reportado (real ou `unavailable` explícito) mas não conta como evidência de economia.

### Comuns

- **R10 — Teto e parada.** Total da spec (J1 + J1b + J2, incluindo sanidade): **190 chamadas externas** e **US$ 1,90** de reserva (era 160/US$ 1,60; emenda de 2026-10-18, ver §6) (US$ 0,01/chamada, regra de parada — não é custo real). Qualquer erro HTTP, de autenticação, quota, timeout ou resposta inválida, inclusive se a cascata de fallback do CLASSIFY "salvar" a resposta, **interrompe o run** sem score. Retomada só com nova autorização do dono, contando contra o mesmo teto.
- **R11 — Artifacts.** Raw gravado antes do score; summary reproduzível offline a partir do raw; SHA-256 em `docs/spec217/README.md`, como na SPEC-178/179. Gravar em diretório temporário fora do OneDrive e copiar para `evals/runs/jev-router-hybrid/<timestamp>/` (gitignored) conferindo hashes. Vale para cada execução da J1 e para a J2.
- **R12 — Fronteira.** Só o DTO `DecisionState` cruza para a TypeSafe: sem segredo, PII, lore oculto ou texto de prompt interno. Jev nunca decide fato canônico, aplica evento, move ouro/HP ou libera segredo; validação Python mantém precedência.
- **R13 — Produção intacta.** Default `RPG_JEV_ROUTER_MODE=off`; nenhuma mudança de schema de save; J1/J2 não alteram o comportamento de `services/jev_rollout.py` nem rotas de produção. Estruturas novas vivem no experimento; portar para o rollout só após GO.
- **R14 — Calibração (só se GO).** Portar a estrutura congelada para `services/jev_rollout.py` (atrás de `off`) e congelar `PRIMARY_CALIBRATION = ("SPEC-217-<run_id>", τ)` em commit separado, revisado por Astra. Sem GO, permanece `None`.
- **R15 — Shadow em staging (opcional, só se GO).** `RPG_JEV_ROUTER_MODE=shadow` em staging por ≥ 50 turnos reais; mede concordância Jev × rota efetiva sem mudar rotas. Exige autorização própria de teto (fora da §6). Critério para pedir `primary`: concordância ≥ 95 % nos turnos que o Jev resolveria **e** zero escalada insegura. `primary` em produção = aprovação separada do dono.

### Fora de escopo
Hipótese (a) cache de cena vs RAG profundo (descartada: SPEC-214 `NO_GO`); evento material vs menção casual; classificação de segredo (`services/secret_signatures.py` segue única autoridade); `loot_context`/`item_ref` pelo Jev; outros callsites CLASSIFY (`EncounterScanner`, `PlayerMove`, `EntityMatch`, `TradeIntent`); streaming; hospedar Jev.

## 3. Design técnico

- **Runner:** módulo `evals/experiments/jev_router_hybrid.py` (reaproveitando `jev_router_ab.py`, SPEC-178) parametrizado por `--corpus dev|frozen` e `--variant <id>`; valida o hash do corpus antes da primeira chamada, recusa `frozen` sem estrutura congelada (commit/ID registrado) e recusa `frozen` uma segunda vez sem flag de autorização explícita. Política híbrida, cálculo de features e regra R9 são funções puras testáveis sem rede.
- **Features:** extraídas por Python a partir da fixture/estado público (nunca pelo LLM); a mesma função será a usada pelo rollout se houver GO.
- **Latência:** wall time da chamada do adapter/LLM, como na SPEC-178. **[F]** Medida da estação de trabalho, não de `gru1`; o shadow (R15) mede no ambiente real.
- **Degradação:** erro em qualquer braço ⇒ parada (R10); em produção nada muda (R13).

## 4. Plano passo a passo

1. **Eval authoring (tarefa separada):** DEV + FROZEN, verificador de não-sobreposição, hashes/commit. Sem chamada live.
2. **Testes primeiro (sem rede, backend falso):** `test_hybrid_policy_uses_jev_only_when_confident_and_representable`; `test_fallback_latency_is_sum_of_all_calls`; `test_two_stage_target_restricted_to_scene_candidates`; `test_features_are_deterministic_and_public_only`; `test_decision_rule_no_go_on_unsafe_combat_escalation`; `test_decision_rule_no_go_on_latency_gain_below_500ms`; `test_python_gate_cases_make_zero_calls`; `test_run_stops_on_provider_error_even_with_cascade_fallback`; `test_budget_caps_j1_60_and_total_160`; `test_corpus_hash_mismatch_aborts_before_first_call`; `test_frozen_refused_without_frozen_structure_and_on_second_run`; `test_dev_frozen_no_overlap`; `test_summary_reproducible_from_raw`.
3. **J1:** diagnóstico (R2) → variantes offline → chamadas DEV dentro de ≤ 60 → registro (R4) → congelamento + revisão Astra (R6).
4. **Sanidade J2:** 2 chamadas por braço (4) num caso fora dos dois corpora; qualquer erro ⇒ parar.
5. **J2:** A/B FROZEN uma vez (R7–R9), artifacts (R11).
6. **Decisão** GO/NO_GO em `docs/spec217/README.md`; revisão Astra independente.
7. **Se GO:** porte + calibração (R14); propor shadow (R15). **Se NO_GO:** spec `done` com a decisão; Jev permanece `off`.

## 5. Critérios de aceite

- [ ] DEV e FROZEN congelados antes da J1, sem sobreposição verificada; executor não os alterou e não leu o FROZEN antes da J2.
- [ ] Diagnóstico J1 e registro completo de variantes com score DEV e chamadas gastas.
- [ ] Estrutura e `τ` congelados em commit antes da J2, com revisão Astra.
- [ ] Testes do passo 2 verdes; `uv run pytest` verde.
- [ ] J1 ≤ 60 chamadas; total ≤ 160 chamadas e ≤ US$ 1,60 de reserva, ou interrupção por R10 registrada.
- [ ] Raw/summary com SHA-256; summary reproduzido offline.
- [ ] Decisão GO/NO_GO aplicando a R9 sem reinterpretação; revisão Astra aprovada.
- [ ] Default `off` preservado; nenhuma mudança de schema/rotas de produção.

## 6. Smoke / orçamento

- **Offline:** testes do passo 2 + summary reproduzido do raw.
- **Live (autorizado pelo dono em 2026-10-18):** teto **190 chamadas / US$ 1,90** no total desta spec. Divisão: **J1 ≤ 60**; **J1b ≤ 30** (estágio de fonte do loot, [SPEC-238](SPEC-238-jev-loot-source.md), só DEV); **J2 ≤ 100** (4 de sanidade + réplicas), inalterada.
- **Emenda de orçamento (2026-10-18):** o dono aprovou +30 chamadas (~US$ 0,30) para a J1b — "boa, cria uma spec para o jev cobrir o loot e vamos usar ele também" — elevando o teto de 160/US$ 1,60 para 190/US$ 1,90. O saldo da J1b não migra para a J2. Com estrutura de um estágio, `4 + N × 2 × 3 ≤ 100` ⇒ **N ≤ 16 casos elegíveis** no FROZEN; com dois estágios, contar a chamada extra por caso com alvo. O handoff dimensiona o FROZEN para caber; se a estrutura congelada exigir mais chamadas do que cabem, reduzir casos do FROZEN **antes** de qualquer leitura de conteúdo (por seleção determinística por seed declarada), nunca réplicas. Saldo não usado da J1 não aumenta a J2 sem registro explícito.
- **Shadow em staging (R15):** fora deste teto; exige autorização própria.

## 7. Riscos & compatibilidade

- Saves: sem alteração.
- Overfitting à DEV: mitigado pelo FROZEN novo, nunca visto, usado uma vez.
- FROZEN pequeno (≤ 16 casos × 3 réplicas): baixo poder estatístico; a regra é conservadora (≤ 1 perda, zero escalada insegura) e `NO_GO` é resultado válido.
- Cobertura baixa (SPEC-180: 2/16 representáveis): se poucos casos caem na estrutura do Jev, o ganho líquido p50 tende a zero ou negativo — a R9.4 captura isso.
- Latência medida fora do datacenter de produção: o shadow (R15) é a confirmação real.
- Dependência de terceiro (TypeSafe): kill switch e fallback obrigatórios.

## 8. Pontos de decisão do dono

1. Teto: **decidido** — 160 chamadas / US$ 1,60 no total (J1 ≤ 60) (2026-10-18); **emendado** para 190 / US$ 1,90 com J1b ≤ 30 (SPEC-238, 2026-10-18).
2. Fase J1 de estruturação: **decidida** (2026-10-18).
3. Shadow em staging (R15): teto a autorizar só se a J2 der GO.
4. `primary` em produção: aprovação separada após o shadow.

## 9. Evidência requerida

Hashes/commit de DEV e FROZEN e relatório de não-sobreposição, `docs/spec217/j1-diagnostico.md`, `docs/spec217/j1-variantes.md`, commit da estrutura congelada, raw/summary com SHA-256, `docs/spec217/README.md` com a aplicação da R9, pareceres Astra (congelamento e resultado), saída de `uv run pytest`.
