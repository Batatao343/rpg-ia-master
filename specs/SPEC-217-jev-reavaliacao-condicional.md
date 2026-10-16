# SPEC-217 — Reavaliação condicional do Jev/TypeSafe

> **Status:** `draft` (CONDICIONAL — não pode ser aprovada sem as pré-condições da §1)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-200 `done` (baseline), SPEC-214 `done` (memória hierárquica) · SPEC-177..180 `done` (ordem final 2026-10-15)
> **Desbloqueia:** nada obrigatório (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/…`, prompt 13
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — evals congelados por hipótese, em tarefa separada ANTES do A/B.

---

## 1. Contexto & Objetivo

[F] SPEC-177..180 `done`. `services/jev_decision.py` (adapter Choice/Noul/Score) e `services/jev_rollout.py` (`RPG_JEV_ROUTER_MODE` default `off`; `primary` bloqueado por `PRIMARY_CALIBRATION=None` e por `RPG_JEV_ROUTER_PRIMARY_APPROVED`; kill switch `decision_backend:jev` em `services/kill_switches.py`, SPEC-196). `docs/spec180/README.md`: **NO_GO** — rota A 48/48 vs Jev 46/48, só 2/16 elegíveis (12,5%) para `primary`, custo real indisponível.

[D] Não adicionar classificador Jev automaticamente; avaliar só depois de medir TTFT/TTLT e custo (na SPEC-200: TTFMC/TTLT; TTFT ≡ TTFMC só enquanto `pseudo_streaming=true`). Nenhuma hipótese substitui evento canônico, e Choice nunca usa lista aberta arbitrária. Classificação público/privado de segredo é PROIBIDA de substituir `services/secret_signatures.py`.

**Pré-condições para aprovar esta spec (todas):**
1. Baseline da SPEC-200 `done` mostrando gargalo (latência ou custo) em decisão onde classificação fechada plausivelmente ajuda — critério [R]: a fase da decisão-alvo (`phase_ms.router` para (b); `phase_ms.context` para (a)) ≥ 10 % do p50 de `ttlt_server_ms` em `typical`, **ou** custo da decisão-alvo ≥ 10 % de `cost_usd` do turno com `cost_basis` ≠ `unavailable`.
2. Relatório de callsites (§3) com pelo menos uma hipótese `Jev Choice fechado`.
3. SPEC-214 `done` **com decisão `GO`** e o modo `on`/`shadow` existente, para a hipótese (a) ter alvo concreto. Se SPEC-214 fechar `NO_GO`, a hipótese (a) é descartada e a spec só prossegue com (b).
4. Teto de custo do A/B autorizado pelo dono.
Sem isso a spec fica `draft` ou é descartada (§8).

## 2. Requisitos

- **R1** — Relatório de callsites por hipótese, cada linha classificada `Python determinístico | Jev Choice fechado | LLM necessário`, com contrato de saída, candidatos fechados e dados enviados.
- **R2** — Hipóteses mínimas: (a) gate de memória de cena vs RAG profundo (SPEC-214); (b) evento material vs menção casual; (c) público/privado de segredo — registrada como `Python determinístico` (`secret_signatures`) e excluída do A/B.
- **R3** — Evals congelados (hash, registry, lock) criados em tarefa SEPARADA e anterior; o executor do A/B não os altera.
- **R4** — A/B pareado, mesmo corpus, 3 réplicas, baseline = caminho atual (Python/CLASSIFY). Métricas: acurácia crítica, taxa de fallback, vazamento de segredo (hard gate = 0), p50/p95, custo total incluindo a chamada extra.
- **R5** — Regra de decisão pré-declarada antes do run: qualquer vazamento de segredo, regressão pareada de acerto crítico sem fallback seguro, ou piora de custo/latência >10% sem ganho de qualidade = NO_GO.
- **R6** — Default `off`; integração nova segue o padrão `off|shadow|primary` de `services/jev_rollout.py`, respeita o kill switch `decision_backend:jev`, deadline total e erro fechado; `primary` exige calibração congelada e aprovação separada.
- **R7** — Jev nunca decide fato canônico, aplica evento, move ouro/HP ou libera segredo; a saída só roteia/pré-filtra e a validação Python mantém precedência.
- **R8** — Payload mínimo (DTO `DecisionState`), sem segredo, PII ou lore oculto cruzando a fronteira.
- **R9** — Sem provider real sem autorização e teto explícitos de chamadas/USD; custo `unavailable` não vale como evidência de economia.
- **R10** — Nenhuma mudança de schema de save.

### Fora de escopo
Reabrir SPEC-177..180; promover `primary` do router; substituir `secret_signatures`; streaming; migrar callsites `mixed/free_form` (`EncounterScanner`, `TradeIntent.item_ref`); hospedar Jev.

## 3. Design técnico

- **Entregável inicial (sem produto)**: `docs/spec217/callsite-report.md` com tabela `hipótese | callsite | classificação | candidatos fechados | evidência | risco`. [H] Partir do inventário de cinco callsites CLASSIFY em `docs/spec180/README.md`.
- **(a) memória de cena vs RAG profundo**: Choice `{scene_cache, deep_rag}`; fallback sempre `deep_rag` (seguro). Depende dos pontos de decisão da SPEC-214.
- **(b) evento material vs menção casual**: Choice `{material, casual}`; `material` não cria evento, só habilita o pipeline existente (`services/world_validators.py`, `services/event_processor.py`); erro → caminho atual.
- **(c) segredo**: apenas documentada; `services/secret_signatures.py` segue única autoridade.
- **Se aprovada para implementação**: módulo de rollout análogo a `services/jev_rollout.py`, telemetria sem payload, flag `RPG_JEV_<HIPOTESE>_MODE=off`.
- **Eval** (tarefa separada): corpus por hipótese com oráculo fixture-authored, casos negativos de vazamento, congelado via governança `evals/`.
- **Degradação**: timeout, 4xx/5xx, chave ausente, kill switch → caminho atual, sem mudança de GameState.

## 4. Plano passo a passo

1. **Verificar pré-condições** (humano): SPEC-200/214 `done`, baseline lida. Se falhar, parar e aplicar §8.
2. **Relatório de callsites** (somente doc); revisão Astra.
3. **Handoff de eval** (tarefa separada): corpus + registry + lock; sem produto.
4. **Aprovação do dono** com teto de custo; spec vira `approved`.
5. **Testes primeiro** de rollout (`tests/test_jev_<hipotese>_rollout.py`, adapter falso, sem rede):
   `test_off_makes_zero_calls`; `test_shadow_never_changes_decision`; `test_kill_switch_forces_baseline`
   (`decision_backend:jev`); `test_timeout_and_http_error_fall_back_closed`; `test_choice_candidates_closed`
   (candidato fora da lista → erro fechado); `test_payload_has_no_secret_or_pii` (DTO `DecisionState`
   sanitizado, assinaturas de `secret_signatures` ausentes); `test_primary_refused_without_calibration`.
   Comando: `uv run pytest tests/test_jev_*_rollout.py tests/test_jev_rollout.py -q` e suíte completa.
6. **Implementação** apenas em `off`/`shadow`.
7. **A/B pareado** com teto, regra R5 pré-declarada, custo real ou `unavailable` explícito.
8. **Decisão** GO/NO_GO registrada; `primary` só em spec seguinte.

## 5. Critérios de aceite

- [ ] Pré-condições §1 documentadas e verificadas.
- [ ] Relatório de callsites com classificação por hipótese; segredo = Python.
- [ ] Evals congelados antes do A/B; hashes registrados; executor não os alterou.
- [ ] A/B pareado concluído dentro do teto; zero vazamento de segredo.
- [ ] Default `off` preservado; kill switch testado; `uv run pytest` verde.
- [ ] Guard de FallbackLLM em todo structured output novo.
- [ ] Decisão GO/NO_GO com regra pré-declarada e revisão Astra aprovada.

## 6. Smoke

Offline: testes de rollout com adapter falso (`uv run pytest tests/test_jev_*_rollout.py`); A/B offline de sanidade do runner com respostas gravadas (sem rede). Provider real somente opt-in, com autorização, teto de chamadas e USD declarados e chave Jev presente; nunca por padrão.

## 7. Riscos & compatibilidade

- Saves: sem alteração.
- Risco de repetir o NO_GO da SPEC-180 (corpus pequeno, custo indisponível) — mitigado por R4/R5/R9.
- A chamada extra aumenta latência; só vale se a economia a jusante superar.
- Dependência de terceiro (TypeSafe): kill switch e fallback obrigatórios.

## 8. Pontos de decisão do dono

1. Autorizar teto de custo do A/B (default: não autorizado até a pré-condição 1).
2. **Critérios para descartar a spec** (default: descartar se qualquer um ocorrer):
   - baseline SPEC-200 não mostrar gargalo em decisão fechada;
   - relatório de callsites não achar hipótese `Jev Choice fechado` além do já NO_GO;
   - elegibilidade projetada <80% sem fallback seguro;
   - custo real não puder ser medido;
   - SPEC-214 resolver o gargalo em Python determinístico;
   - dono não autorizar teto.
3. Evolução só até `shadow` (default) ou permitir `primary` em spec posterior.

## 9. Evidência requerida

Baseline SPEC-200, `docs/spec217/callsite-report.md`, hashes de evals congelados, raw/summary do A/B, relatório de custo, parecer Astra, saída de `uv run pytest`.
