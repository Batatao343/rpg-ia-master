# Análise do pacote "próxima onda" — 2026-10-15

Pacote extraído em `docs/historico/proximas-specs/pacote-prompts-rpg-beta-2026-10-15/` (manifest SHA-256 43/43 OK).
Natureza: 16 prompts de **autoria de specs**, não specs. Nenhum número do pacote é SPEC-ID.
`historico-nao-executar/` usa IDs 176–183 que colidem com specs reais (Jev, hosted, metering…) — só contexto.

Método: auditoria read-only do HEAD por 5 subagentes Sonnet (grupos de prompts), Haiku (manifest + inventário
do índice), Opus (plano). [F] = fato observado no código; [H] = hipótese.

## Estado do repositório

- `specs/index.yaml`: SPEC-001..198. 197 `in-progress` (beta pago fechado — infra/negócio), 198 `approved`
  (Google Play), 104 `draft` (cloud). Sem SPEC-199+. Próximo livre provável = **199** — reconferir a cada draft
  (197 ainda mexe no índice).
- HEAD avançou durante a análise (`45f84bc` → `6b94f66`; trabalho da 197 commitado em `45c3681`).
- Nota stale no ESTADO_ATUAL chamando SPEC-077 de `draft` (índice diz `done`).

## Achados por prompt

### 01 — Diagnóstico / matriz de efeitos UX
- [F] motion ^12.42, `MotionConfig reducedMotion="user"` (App.tsx), bloco reduced-motion global (styles.css),
  tokens OKLCH, hover mínimo. Nenhuma matriz de efeitos.
- Parcial: SPEC-054, 157, 077, 172. **Draft novo. Sem dependência; pré-requisito do 05.**
- Atenção: prompt cita "tela de mapa" — não existe, mapa é aba do Hud. Arsenal visual do pacote não é a
  seleção original do dono.

### 02 — Shell: abas, split-view, full-screen
- [F] Layout atual: 2 colunas, `.stage` = `minmax(0,1fr) 360px` (styles.css:352) — chat + Hud fixo.
  Hud.tsx tem 8 abas (ficha|combate|personagens|mapa|faccoes|missoes|cronica|codex), auto-troca para combate.
  CardHand/SceneZones embutidos na coluna do chat. Draft = `useState` no PlayScreen. Sem split/resize.
- **Maior lacuna arquitetural. Draft novo (opus).** Precisa de decisões D1/D2 antes.

### 03 — Combate card battler (uma ação por gesto)
- [F] Cutover conflito-13 feito; motor determinístico único. API já estruturada (`ActionRequest`: card_id,
  target_id, ruptura, reaction_card_id, action_kind, action_id).
- [F] CardHand usa `<select>` de alvo + botão; sem mira por clique, sem Esc/teclado, sem tooltip de limites;
  inimigos não clicáveis; SceneZones é lista textual.
- Falta contrato `valid_targets` por carta (aditivo). **Draft novo como evolução da SPEC-077.** Depende do 02.

### 04 — Combate: elenco fixo, estados, encerramento
- **[F] Bug real:** `agents/combat.py:929` `logs.append(f"+{xp} XP…")` → logs alimentam `_narrate`/
  `_narrate_fall`; fallback (l.940) imprime logs como narração. XP vaza para prosa, violando "chat recebe
  desfecho; UI recebe XP". `types.ts` sem evento XP.
- [F] Spawn via LLM `EncounterScanner` sobre `messages[-2:]` (combat.py ~162-218, 651). Sem manifesto canônico
  de identidade/espécie/facção. IDs estáveis após spawn.
- **Dividir:** 04a (fix XP + evento estruturado, pequeno) e 04b (manifesto do encontro + tela de desfecho;
  provar bug de identidade por repro antes).

### 05 — Design system e efeitos (implementação)
- Nenhuma spec cobre. **Adiar até 01 aprovada e 02/03 conciliadas.** Medir bundle atual primeiro.

### 06 — Menus Codex/Personagem/Combate/Bestiário/Mapa
- [F] CodexTab (bestiário por tiers), FichaTab, WorldMap (fog/viagem), arte gerada. Sem deck fora de combate.
  UI sem fato/suspeita/rumor/percepção.
- **Dividir em 3:** 06a Combate-fora-de-encontro + Personagem; 06b Codex+Bestiário (dossiês, depende 12a);
  06c Mapa.

### 07 — Interlocutor automático (voz já existe)
- [F] `agents/router.py` `dm_router_node`; `active_npc_name` cai em `decision.target` cru — NPC ausente/
  alucinado passa. Nenhuma regra "pergunta ao narrador sobre NPC". Frontend sem seletor (alinhado).
  Voz (186/187) ok.
- **Draft novo (opus):** ambiguidade, meta-pergunta, NPC ausente, múltiplos NPCs, `speaker_id` canônico.
  Sem chamada LLM extra. HTML v01 tem seletor explícito — descartar.

### 08 — Exportar sessões para agente juiz
- [F] Reaproveitável: `/game/chronicle/export`, `/game/saves`, `/account/export` (SPEC-190, owner-bound),
  `services/game_transfer.py`, `playtest/telemetry.py` (sintético). Sem export de sessão com state_deltas/
  knowledge_visibility; sem redaction PII genérico.
- ~~[H] `/game/chronicle/export` talvez sem checagem de dono~~ — **verificado: falso alarme.** Nos perfis DB o
  middleware `_session_boundary` exige auth em `/game*` e `load_game_state` usa `store.get(principal, …)`
  (escopo por dono). Perfil legacy é loopback sem login por design.
- **Draft novo (opus)** após decisão D4 (consentimento/retenção).

### 09 — Latência baseline
- **[F] SSE é pseudo-streaming:** grafo roda inteiro, depois mensagem pronta é fatiada. TTFT percebido ≈ fim do
  grafo + archivist. `rpg_sse_first_event_seconds` mede o `accepted` (~0 s) — métrica enganosa.
- **Draft novo; adiantar instrumentação (09a)** — barata, transversal, alimenta 08 e 15.

### 10 — Arquivista e projeções em segundo plano
- [F] `archive_node` inline; workers/jobs já existem (embedding, chronicle, art). Sem separação canônico vs
  derivado, sem estados stale.
- **Risco crítico:** `validate_narrative` roda no archivist — sair do hot path deixa prosa não validada chegar ao
  jogador (decisão D5). **Adiar até baseline do 09.**

### 11 — Hierarquia de memória / cache de cena
- [F] `context_builder` (budget 3500, concorrência 3), summary 1200 chars, FAISS+pgvector. Sem snapshot de cena.
- **Adiar** (depende 09, de preferência 10). Ganho pode ser pequeno se gargalo é LLM.

### 12 — Conhecimento NPC, rumores, segredos
- [F] `secret_signatures`, `memory_provenance` (confirmed/reported/speculative), `max_visibility`. Nenhum modelo
  por-NPC (`observed_by`/`told_to` = 0 hits), sem propagação.
- **Dividir:** 12a taxonomia visível ao jogador mapeada sobre provenance (antes dos dossiês do 06b);
  12b conhecimento por NPC + propagação (P2, migração de save).

### 13 — Jev
- [F] SPEC-180 NO_GO, modo `off`, primary bloqueado. **Não escrever spec.** Só reavaliar com baseline 09 +
  relatório de callsites.

### 14 — Mobile single-pane
- [F] Hud vira gaveta <900px; Capacitor (193). **Adiar** até 02 implementado. Risco: SPEC-198 (Play) pressionar
  mobile antes do desktop.

### 15 — Vertical slice / gate mínimo de beta
- [F] SPEC-197 = beta **pago** fechado (infra/negócio); não cobre jornada de gameplay. F01–F16 existem via SPEC-172.
- **Spec nova "beta-gameplay-gate" que consome 197 sem editá-la.** Fecha a onda.

## Fila de autoria recomendada (uma spec por execução)

| Ordem | Spec | Tier autoria | Paralelo |
|---|---|---|---|
| 1 | 04a fix XP fora da prosa + evento XP estruturado | sonnet | com 2, 3 |
| 2 | 09a instrumentação TTFT/TTLT/ack + baseline offline | sonnet | com 1, 3 |
| 3 | 01 matriz de efeitos UX | sonnet | com 1, 2 |
| 4 | 07 política do interlocutor | opus | com 5 |
| 5 | 04b manifesto do encontro + desfecho | opus | com 4 |
| 6 | 02 shell split/abas | opus | após D1/D2 |
| 7 | 03 combate por gesto | sonnet | — |
| 8 | 08 export de sessão | opus | após D4 |
| 9 | 12a taxonomia de visibilidade | opus | com 8 |
| 10 | 05 efeitos | sonnet | após D7 |
| 11 | 06a / 06c / 06b menus | sonnet | 06a ∥ 06c |
| 12 | 15 gate de gameplay | sonnet | — |
| depois | 10 → 11 (se baseline justificar), 12b, 14; 13 descartado | — | — |

"Paralelo" vale para redação; alocação de ID e commit do índice sempre em série.

## Decisões do dono antes de redigir

- **D1 (02):** 5 abas pedidas — Facções, Missões, Crônica viram seções do Codex ou saem?
- **D2 (02):** modo só-chat mostra indicador global mínimo (HP/relógio/combate)? CardHand sai do chat para aba
  Combate (altera contrato da SPEC-077)?
- **D3 (09a):** streaming real de tokens no escopo da beta, ou só medir o pseudo-streaming?
- **D4 (08):** consentimento entra no legal da 197? Retenção? Só o próprio dono exporta? Redaction PII
  obrigatório? Persistir "contexto visto pelo NPC" por turno (custo de storage)?
- **D5 (10):** `validate_narrative` pode sair do hot path?
- **D6 (15):** "beta jogável desktop" é pré-requisito do "beta pago fechado" (197)? 198 não puxa mobile antes.
- **D7 (05):** recuperar arsenal visual original ou oficializar o arsenal-base do pacote?

## Riscos transversais

- Merge com SPEC-197 em `App.tsx`/`styles.css`/índice: implementar 02 só com 197 `done` ou CSS isolado.
  Preservar reduced-motion global.
- Integridade de eval: 04a, 04b, 07, 09a, 15 exigem evals novos → `EVAL_AUTHORING_REQUIRED` em task separada.
- Custo: baseline offline; provider real só opt-in com teto; 07 sem chamada LLM extra.
- Saves: 04b e 12a/12b podem mudar estado salvo → teste save/reload com saves antigos.
- Protótipos HTML são mock (danos/cartas/falas); v01 contradiz decisão (seletor explícito); v03 substitui v02.

## Specs geradas (2026-10-15) — todas `draft`, registradas em `specs/index.yaml`

| Ordem | SPEC | Prompt | Executor/Review | Depende de |
|---|---|---|---|---|
| 1 | 199 combate-xp-fora-da-prosa (+ fix cura-no-inimigo) | 04a | Terra / — | — |
| 1 | 200 latencia-baseline-ttft-ttlt | 09 | Terra / Sol | — |
| 1 | 201 diagnostico-matriz-efeitos-ux | 01 | Terra / — | — |
| 1 | 202 interlocutor-automatico-narrador-npc | 07 | Sol / Astra | — |
| 1 | 206 taxonomia-conhecimento-visivel-jogador | 12a | Sol / Astra | — |
| 2 | 203 manifesto-encontro-elenco-desfecho | 04b | Sol / Astra | 199 |
| 2 | 204 shell-chat-contexto-split-abas | 02 | Sol / Sol | 201 (approved) |
| 3 | 205 combate-gesto-alvo-direto | 03 | Terra / Sol | 199, 203, 204 |
| 3 | 207 export-sessao-auditoria-beta | 08 | Sol / Astra | 200, 206 |
| 4 | 208 design-system-efeitos-implementacao | 05 | Terra / — | 201, 204, 205 |
| 5 | 209 menu-combate-deck-personagem | 06a | Terra / — | 203, 204, 205, 208 |
| 5 | 210 menu-mapa-viagem | 06c | Terra / — | 204, 208 |
| 5 | 211 menu-codex-bestiario-dossies | 06b | Terra / Sol | 204, 206, 208 |
| 6 | 212 beta-gameplay-gate-desktop | 15 | Terra / Sol | 199–207, 209–211 |
| P1 | 213 arquivista-projecoes-assincronas (gate: baseline 200) | 10 | Sol / Astra | 200 |
| P1 | 214 memoria-hierarquica-cache-cena (gate: baseline 200) | 11 | Sol / Astra | 200, 213 |
| P2 | 215 conhecimento-por-npc-propagacao | 12b | Sol / Astra | 202, 206, 214 |
| depois | 216 mobile-single-pane | 14 | Terra / — | 204, 205, 212 |
| condicional | 217 jev-reavaliacao-condicional | 13 | Sol / Astra | 200, 214 |

Mesma "Ordem" = pode implementar em paralelo. Specs de onda 1 não dependem de nenhuma decisão aberta, exceto
seção 8 de cada uma (defaults recomendados já escritos).

### Achados extras durante a autoria (verificados no source)
- **Bug:** carta benéfica sem alvo cura o inimigo (`api.py::_apply_action_options` ~l.3178 preenche 1º inimigo;
  `agents/combat.py` ~l.843 só corrige alvo inválido). Movido para SPEC-199 R12.
- **Vazamento extra de XP:** `services/turn_outcome.py::render_player_message` anexa `[RESULTADO] +N XP` ao chat
  em todo turno com ganho (SPEC-199).
- **Fog do mapa só no cliente:** `GET /data/map` envia nome/lore/perigo de locais não descobertos (SPEC-210 propõe
  `GET /game/map` server-side).
- **NPC onisciente:** `build_context_pack(purpose="npc")` injeta event_log global, mortes e `revealed_facts` de
  qualquer lugar (SPEC-215).
- **Codex lista nome/contagem de entidades ocultas** (corpo escondido, nome não) e `player.known_secrets` é lido mas
  nunca escrito (SPEC-206).
- **Métrica enganosa:** `rpg_sse_first_event_seconds` mede antes do `accepted` (SPEC-200).
- `PlayScreen` não é keyed por `game_id` — rascunho pode vazar entre jogos [H] (SPEC-204 R8).
- `CodexTab` usa `dangerouslySetInnerHTML` via `mdLite` — confirmar escape de HTML [H] (SPEC-211).
- Coordenação: SPEC-203/207/213/215 propõem migração de save; usam o próximo `SCHEMA_VERSION` livre em ordem.
