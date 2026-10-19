# Auditoria de BUGS FUNCIONAIS — relatório consolidado (2026-10-15)

> **Status deste arquivo:** CONCLUÍDO (8/8 áreas auditadas; 11 specs em staging nesta pasta).
> Escopo: correção funcional (não segurança — ver `../seguranca/`). HEAD de referência: `d6af933` + working tree.
> Brief: `scratchpad/brief_auditoria.md` (coordenador) + `subagent_brief_bugs.md` (subagentes).
> Verificação do orquestrador: todos os achados **alta** foram re-verificados pelo orquestrador — re-execução offline
> dos scripts de repro (MockLLM, `RPG_FORCE_MOCK=1`) e/ou leitura dos trechos exatos; coluna "Verif." abaixo.

## 1. Cobertura por área

| # | Área | Arquivo de achados | Resultado |
|---|------|--------------------|-----------|
| 01 | Grafo / ciclo do turno | `achados/01-grafo-turno.md` | 3 A / 5 M / 3 B |
| 02 | Combate (motor v2 + nó) | `achados/02-combate.md` | 8 A / 6 M / 6 B |
| 03 | Economia / loot / inventário / progressão | `achados/03-economia-loot-progressao.md` | 3 A / 6 M / 3 B |
| 04 | Persistência / migrações / concorrência | `achados/04-persistencia-concorrencia.md` | 1 A / 4 M / 3 B (+4 obs) |
| 05 | Memória / RAG / contexto / arquivista / crônica | `achados/05-memoria-rag-contexto.md` | 3 A / 7 M / 6 B |
| 06 | Mundo (viagem, relógio, clima, luz, NPC, fações, quests, eventos) | `achados/06-mundo.md` | 2 A / 9 M / 6 B |
| 07 | API / frontend | `achados/07-api-frontend.md` | 1 A / 4 M / 4 B |
| 08 | Billing / wallet / jobs / workers | `achados/08-billing-jobs.md` | 2 A / 4 M / 3 B |

**Totais (01–08):** ~104 achados brutos · **crítica 0** · **alta 23 (21 únicas**; 02-01≡03-01, 06-01≡01-03) ·
**média 45** (3 duplicatas cruzadas: 06-06≡03-12, 06-07≡02-17, 07-03≡01-06) · **baixa 34** (+2 observações).
Todas as altas foram re-verificadas pelo orquestrador (execução e/ou leitura do trecho exato); nenhuma alta foi
descartada como falso positivo.

**Incidente de processo:** o subagente da área 01 fez UMA chamada real de geração de NPC (`RPG_NO_MOCK=1` carregou
`.env`), custo desprezível; todas as demais reproduções usaram MockLLM/stubs. As ondas seguintes receberam instrução
explícita de nunca usar `RPG_NO_MOCK`. O subagente da área 07 criou e removeu um diretório `data/saves_memory/<uuid>`.

## 2. Tabela de achados

Sev.: A=alta · M=média · B=baixa. Verif.: ✅exec = re-executado pelo orquestrador; ✅leitura = trecho conferido
pelo orquestrador; sub = confiança declarada pelo subagente (sev ≤ média, não re-verificado).

### Área 01 — grafo/turno
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 01-01 | Beat concluído no turno da viagem sobrescreve o jogador com o achado/baú (loot some, baú consumido) | A | ✅exec gold 40→0 | SPEC-226 |
| 01-02 | `generate_new_npc` sem `isinstance` → `AIMessage` vira ficha `role/persona None` persistida no cache | A | ✅exec + ✅leitura npc.py:262 | SPEC-230 |
| 01-03 | `is_travel_intent` casa movimento local → recusa "Não há rota direta", turno perdido | A | ✅exec 3/5 frases | SPEC-229 |
| 01-04 | `_EXPLICIT_STORY_RE` (`viaj\w*`, `acamp\w*`) vence hostilidade/NPC/loot | M | sub exec | SPEC-229 |
| 01-05 | Exceção no storyteller devolve só `messages`: narra descanso/achado sem aplicar | M | sub exec | SPEC-233 |
| 01-06 | Laboratório de combate encerrado → ações caem em router/NPC/RAG reais (grafo) | M | sub exec | SPEC-233 |
| 01-07 | NPC morto por `npc_killed` continua `in_scene`/conversável | M | sub leitura | SPEC-230 |
| 01-08 | Planejador falho troca plano bom por beats genéricos, reabre XP de beat | M | sub leitura | SPEC-226 |
| 01-09 | `npc_fallback_hint` nunca limpo (CLI/harness) | B | sub | SPEC-230 |
| 01-10 | `danger_shift=-1` eleva perigo 0→1 | B | sub leitura | SPEC-233 |
| 01-11 | Guard `reward_delta` compara frase com delta líquido | B | sub hipótese | SPEC-226 |

### Área 02 — combate
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 02-01 | XP/`defeated`/`npc_killed` re-concedidos a cada rodada para mortos (≡03-01) | A | ✅exec xp 50/100/150 | SPEC-226 |
| 02-02 | `_stabilizer_for` só olha `hero=[player]` → aliado nunca estabiliza o protagonista | A | ✅exec stabilizer None + ✅leitura :1059 | SPEC-231 |
| 02-03 | Companheiro vira `categoria padrao` (sem Última Ação/Terminal) + política de inimigo | A | ✅exec full_flow False | SPEC-231 |
| 02-04 | Snapshot `scene_allies` não atualizado → aliado transitório cura/ressuscita por rodada | A | ✅exec 8/8 na rodada 2 | SPEC-231 |
| 02-05 | Condições `stat/delta` (attack/ac/damage) não afetam rolagens — buffs/debuffs inertes | A | ✅exec +20 sem efeito + ✅leitura consumidores | SPEC-232 |
| 02-06 | Passivas de árvore/Virtude/efeito de Reação sem consumidor; `learned_passives` → `[]` (regressão SPEC-047) | A | ✅leitura :194-200, :572 | SPEC-232 |
| 02-07 | `last_stand_resolved`/`stabilization_attempts` nunca zerados → 2º quase-morte mata na hora | A | ✅exec dead True pending False | SPEC-231 |
| 02-08 | Regex de fuga sem borda (`recu|retir|escap`) → "recuperar/retirar/recusar" viram fuga | A | ✅exec + ✅leitura :741 | SPEC-229 |
| 02-09 | Carta cobrada antes de validar alvo/mira | M | sub exec | SPEC-232 |
| 02-10 | `guarding` nunca expira | M | sub leitura | SPEC-232 |
| 02-11 | DoT/clima atravessam armadura (`defensavel=False` inerte) | M | sub exec | SPEC-232 |
| 02-12 | `validate_narrative_text` descarta narração por falso positivo ("escapa" perto de morto) | M | sub exec | SPEC-229 |
| 02-13 | `prepare_encounter` nunca chamado: objetos/Abismo/reforços/fim não existem em combate real | M | sub leitura | SPEC-232 (D-A) |
| 02-14 | Engajamento nunca criado → AoO inerte; Desengajar+mover leva AoO | M | sub leitura | SPEC-232 |
| 02-15 | `_early_game_reaction_initiator` vale 2 rodadas | B | sub | SPEC-232 |
| 02-16 | Carta `estabilizar` não registra `scars_pending` | B | sub | SPEC-231 |
| 02-17 | `relationship == 0` tratado como 5 (≡06-07) | B | sub | SPEC-230 |
| 02-18 | `encounter_budget.tier_cost` por `type` legado | B | sub exec | SPEC-226 |
| 02-19 | `_maybe_abyss` gasta Carga antes de validar efeito | B | sub | SPEC-232 |
| 02-20 | `_default_card_target` sem `reduzir_carga_aliado` (adendo SPEC-199 R12) | B | sub | SPEC-232 |

### Área 03 — economia/loot/progressão
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 03-01 | XP de kill re-concedido a cada rodada (≡02-01) | A | ✅exec | SPEC-226 |
| 03-02 | `quest_completed` duplicado no lote paga XP 2× (ouro 1×) | A | ✅exec xp 400 gold 20 | SPEC-226 |
| 03-03 | Vender 2+ não-empilháveis paga ouro sem remover (ouro infinito); craft idem | A | ✅exec + ✅leitura `remove_item` | SPEC-227 |
| 03-04 | Item vendido continua equipado | M | sub exec | SPEC-227 |
| 03-05 | `sell` sem mercador | M | ✅exec | SPEC-227 |
| 03-06 | Único vendido some no `restock` | M | sub exec | SPEC-227 |
| 03-07 | Vender `item_desconhecido` remove outro item | M | sub exec | SPEC-227 |
| 03-08 | `/game/new` nível>1 acima do cap de Entropia, sem escolhas | M | sub exec | SPEC-227 |
| 03-09 | `use_item_in_combat` consome sem efeito | M | sub exec | SPEC-227 |
| 03-10 | `xp_for_kills` ignora `categoria` | B | sub leitura | SPEC-226 |
| 03-11 | Inventário de sabor resolve para único sem claim | B | sub provável | SPEC-227 |
| 03-12 | Fingerprint de quest conta pontuação (≡06-06) | B | sub leitura | SPEC-226 |

### Área 04 — persistência/concorrência
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 04-01 | "Continuar" na morte sem checkpoint utilizável revive no lugar (API nunca passa `initial_state`) | A | ✅exec + ✅leitura api.py:3382 | SPEC-228 |
| 04-02 | Heartbeat do lease pós-commit → `LeaseHeld` em turno salvo | M | sub simulado | SPEC-236 |
| 04-03 | `PostgresJobQueue.lease` sem teto de tentativas (poison loop) | M | sub leitura | SPEC-236 |
| 04-04 | Checkpoint depois do save; falha → save+500 e `last_checkpoint_turn` mentiroso | M | sub leitura | SPEC-228 |
| 04-05 | `needs_replan` não persistido | M | sub exec | SPEC-228 |
| 04-06 | Lock `"__latest__"` não serializa com UUID | B | sub provável | SPEC-228 |
| 04-07 | `messages` perde ToolMessage/kwargs no round-trip | B | sub exec | SPEC-228 |
| 04-08 | Jobs `dead`/`cancelled` nunca reenfileirados | B | sub provável | SPEC-236 |
| obs-04-a/b | `schema_version>8` aceito; `last_checkpoint_turn` ausente assume atual | B | sub leitura | SPEC-228 |

### Área 05 — memória/RAG/contexto
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 05-01 | Resumo congela para sempre enquanto a escrita RAG falha (retorno antecipado do archivist) | A | ✅exec 3 turnos + ✅leitura :313-329 | SPEC-234 |
| 05-02 | Chaves de `SECRET_SIGNATURES` ≠ IDs de entidade → reveal aceito nunca libera | A | ✅exec + ✅leitura + grep entities | SPEC-234 |
| 05-03 | `RPG_EMBEDDINGS` override: escrita OK, reabertura desativa o índice | A | ✅exec write2 False + ✅leitura :416-443,:519-540 | SPEC-234 |
| 05-04 | Resumo vira `""` quando todas as frases são rejeitadas | M | sub exec | SPEC-234 |
| 05-05 | "Quem controla X" nunca emitido (nome×ID); conserto ingênuo vazaria `hidden` | M | sub exec | SPEC-234 |
| 05-06 | `search_chronicle` `KeyError` (500) com candidato stale | M | sub exec | SPEC-234 |
| 05-07 | Budget descarta fatos recentes/RAG relevante antes de antigos | M | sub exec | SPEC-234 |
| 05-08 | `FallbackLLM` grava erro como resumo | M | sub exec | SPEC-234 |
| 05-09 | pgvector perde rótulos de proveniência | M | sub leitura | SPEC-234 |
| 05-10 | `embedding_profile_id` não identifica provider/modelo | M | sub hipótese | SPEC-234 |
| 05-11..16 | `revealed_corpus` chave errada; dedupe ledger; exceções RAG sem log; parágrafos; `npc.memory` sem teto; alias Jina | B | sub | SPEC-234 |

### Área 06 — mundo
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 06-01 | `is_travel_intent` casa "sigo em frente"/"volto a falar" (≡01-03) | A | ✅exec | SPEC-229 |
| 06-02 | "Vou ao <local>" não é viagem; LLM pode narrar chegada sem mover | A | ✅exec False + dest encontrado | SPEC-229 |
| 06-03 | Eventos derivados do `rule_engine` com `turn=0` | M | sub exec | SPEC-226 |
| 06-04 | `apply_travel` ignora `danger_overrides` | M | sub exec | SPEC-233 |
| 06-05 | Revisitar baú curado re-sorteia achado (86/200) | M | sub exec | SPEC-226 |
| 06-06 | Quest conclui com pontuação (≡03-12) | M | sub exec | SPEC-226 |
| 06-07 | `relationship` 0 → 5 (≡02-17) | M | sub exec | SPEC-230 |
| 06-08 | `relationship_change` sem teto | M | sub leitura | SPEC-230 |
| 06-09 | Tag `dark` inexistente; masmorras com `abrigo` nunca escuras | M | sub exec | SPEC-233 |
| 06-10 | `disabled_edges` não afeta `dynamic_edges` | M | sub exec | SPEC-233 |
| 06-11 | NPC morto em `npcs_for_context`/`npcs_in_scene` | M | sub exec | SPEC-230 |
| 06-12 | Party morta/em espera conversa em qualquer local | M | sub leitura | SPEC-230 |
| 06-13 | Reputação N× por turno vs log 1× | B | sub provável | SPEC-226 |
| 06-14 | `encounter_eff_danger` grudado | B | sub exec | SPEC-233 |
| 06-15 | Alerta de reforços consumido e suprimido | B | sub provável | SPEC-233 |
| 06-16 | Clima conta chamadas, não períodos; fações 2× | B | sub leitura | SPEC-233 |
| 06-17 | `danger_shift` sem decaimento/piso | B | sub provável | SPEC-233 |

### Área 07 — API/frontend
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 07-01 | Soft-lock de ação pendente (op `failed` + versão do jogo mudou → 409 eterno; cliente só limpa em 400/422) | A | ✅leitura postgres_turns:89-91, App.tsx:540-544, `version+1` no commit | SPEC-235 |
| 07-02 | 422 vira "[object Object]" | M | sub exec | SPEC-235 |
| 07-03 | Simulação finalizada aceita ações via API (XP/viagem/RAG) (≡01-06 lado API) | M | sub exec | SPEC-233 |
| 07-04 | Export da crônica 500 com nome fora de latin-1 | M | sub exec | SPEC-235 |
| 07-05 | `localStorage` sem guarda → tela branca | M | sub hipótese | SPEC-235 |
| 07-06 | 404/409 deixam pending preso | B | sub provável | SPEC-235 |
| 07-07 | Typewriter cortado em 300 ms (POST) | B | sub leitura | SPEC-235 |
| 07-08 | Chip do Abismo do Médico com Carga 0 | B | sub leitura | SPEC-235 |
| 07-09 | `backstory: null` → "None" | B | sub leitura | SPEC-235 |

### Área 08 — billing/wallet/jobs
| ID | Título | Sev | Verif. | Spec |
|----|--------|-----|--------|------|
| 08-01 | Tentativa LLM falha sem `usage` gravada como US$ 1,00 e somada no teto diário/FinOps/custo do turno | A | ✅exec 1.000000000 + ✅leitura usage_metering:166-171, daily_spend_cap:124 | SPEC-236 |
| 08-02 | Override manual do teto diário aceita trip do sistema de ontem → teto de hoje não re-dispara | A | ✅leitura :75-84 (`rows[1:]` sem data) | SPEC-236 |
| 08-03 | Nenhuma varredura libera reservas de wallet órfãs (`recover` só no request de STT) | M | sub leitura | SPEC-236 |
| 08-04 | STT: tentativa não-exata (até 429 definitivo) retém a reserva inteira em `uncertain`, sem CLI/cron | M | sub leitura+teste | SPEC-236 |
| 08-05 | Stripe: refund PARCIAL antes do `checkout.session.completed` marca `refunded` e nunca credita | M | sub leitura | SPEC-236 |
| 08-06 | Rate cards de imagem/STT expiram em 7 dias fixos (bloqueio em 2026-10-19) | M | sub leitura | SPEC-236 |
| 08-07 | `settle_usage` LLM acima do teto trava em `effect_started` sem anomalia | B | sub hipótese | SPEC-236 |
| 08-08 | Job de imagem adiado por kill switch segura reserva sem TTL | B | sub provável | SPEC-236 |
| 08-09 | Kill switches falham abertos em cold start com store ilegível | B | sub leitura | SPEC-236 |

### Descartados (motivo no arquivo de cada área)
01: arestas condicionais, reducer `messages`, `turn_count` 2×, snapshot do finalizer, guards (exceto npc.py),
replan por viagem, `action_guard`, `receipt_id`. 02: crítico/dupla 2d10, Vantagem 3d10, ordem de dano R8, sacrifício,
frequência das Cartas, reações (limite), patamares de Carga, potência 1–20, HP↔Vitalidade, simulação (XP), chase.
03: ouro negativo em compra/craft, `_round5`, tabelas de loot, cap 20, `entropy_max_bonus`. 04: `getctime`, chaves
transitórias, eviction do ledger, lock SSE. 05: isolamento FAISS/pgvector, visibilidade, `compact_summary`, dedupe
por replay, librarian, crônica duplicada, compressão. 06: `blocked_routes` (SPEC-017), mapa (ids/arestas/alcance),
rollover do relógio, fuga com destino, quest sem `reached` (design), weather.json, 2º evento de clima, `apply_rest`.
07: types.ts × payload (só campos extras), `xp_next_level` no cap, duplo clique, replay legacy, modais, voice,
`player_reaction_card_id`, saves arquivados na lista. 08: settle/release 2×, arredondamento Decimal/ceil, reconciliador
fora de ordem/duplicado, fulfillment sem re-cotação, `new_purchases` × crédito, cron 58 s. Já cobertos por
SPEC-199/200/203/204/205/206/210/211/213/214/215.

## 3. Mapeamento achado → spec

| Spec (staging) | Tema | Sev máx | Achados | Depende de |
|---|---|---|---|---|
| `SPEC-226-contabilidade-recompensas-xp.md` | XP/quest/beat/achado/reputação/eventos 1× por fato | A | 03-01/02-01, 03-02, 01-01, 01-08, 06-05, 06-06/03-12, 03-10/02-18, 06-13, 06-03, 01-11 | — |
| `SPEC-227-economia-inventario-integridade.md` | venda/craft/equipamento/únicos/consumíveis/criação nível alto | A | 03-03..03-09, 03-11 | — |
| `SPEC-228-morte-checkpoint-persistencia.md` | morte sem checkpoint, ordem save/checkpoint, `needs_replan`, lock, schema | A | 04-01, 04-04, 04-05, 04-06, 04-07, obs-04-a/b | — |
| `SPEC-229-intencao-viagem-fuga-router.md` | parsers de viagem/fuga/router/validador de prosa | A | 01-03/06-01, 06-02, 01-04, 02-08, 02-12 | — |
| `SPEC-230-npc-ciclo-de-vida-guard.md` | guard de geração, NPC morto, party, relação | A | 01-02, 01-07, 06-11, 06-12, 06-07/02-17, 06-08, 01-09 | — |
| `SPEC-231-combate-morte-aliados.md` | estabilização por aliado, categoria companheiro, scene_allies, flags terminais | A | 02-02, 02-03, 02-04, 02-07, 02-16 | — |
| `SPEC-232-combate-modificadores-passivas-reacoes.md` | condições/passivas/reações inertes, custo de Carta, Guarda, DoT, engajamento, preparação | A | 02-05, 02-06, 02-09, 02-10, 02-11, 02-13, 02-14, 02-15, 02-19, 02-20 | SPEC-231 (mesmos arquivos) |
| `SPEC-233-mundo-perigo-clima-luz-storyteller.md` | perigo efetivo, luz, controle dinâmico, flags, clima, exceção do storyteller, laboratório | M | 06-04, 06-09, 06-10, 06-14, 06-15, 06-16, 06-17, 01-10, 01-05, 01-06/07-03 | — |
| `SPEC-234-memoria-rag-arquivista-resiliencia.md` | arquivista resiliente, segredos por ID, pin/override, contexto, crônica, pgvector | A | 05-01..05-16 | — (coordenar com SPEC-213/214) |
| `SPEC-235-api-frontend-pending-erros.md` | soft-lock de pending, 422 legível, export unicode, storage, chip/typewriter/backstory | A | 07-01, 07-02, 07-04..07-09 | — |
| `SPEC-236-finops-wallet-jobs-reprocesso.md` | custo fantasma de falhas, teto diário cross-day, reservas órfãs, STT incerto, refund parcial, rate cards, lease pós-commit, poison jobs | A | 08-01..08-09, 04-02, 04-03, 04-08 | — (Astra recomendada em R1/R2/R5) |

## 4. Ordem recomendada de execução

Duas trilhas independentes (arquivos disjuntos), executáveis em paralelo por executores distintos:

**Trilha A — gameplay (bloqueadores do beta de jogabilidade, SPEC-212):**
1. `SPEC-227` economia/inventário — exploit de ouro infinito + venda sem mercador (A; núcleo em 2 arquivos, rápido).
2. `SPEC-226` contabilidade de recompensas — XP inflado por rodada/quest, baú perdido (A; pré-requisito do `turn_outcome` da SPEC-199).
3. `SPEC-229` parsers de intenção — "Entro na taverna" recusado, "Vou ao X" não viaja, "recuperar" vira fuga (A; o mais visível em jogo).
4. `SPEC-228` morte/checkpoint/persistência — ressurreição grátis sem checkpoint, `needs_replan` (A).
5. `SPEC-231` combate: morte com aliados → 6. `SPEC-232` combate: modificadores/passivas/reações (A; sequenciais, mesmos arquivos; `SPEC-232` é regressão de SPEC-047 e desbloqueia o balanceamento SPEC-049).
7. `SPEC-230` NPC: guard + ciclo de vida (A; pequeno).
8. `SPEC-234` memória/RAG (A; coordenar com SPEC-213/214 — corrigir o hot path ANTES de reprojetar).
9. `SPEC-233` mundo (M).

**Trilha B — dinheiro/operação (antes de ativar cobrança real, SPEC-197/198):**
1. `SPEC-236` FinOps/wallet/jobs — custo fantasma (US$ 1 por falha) e override do teto são bloqueadores da beta paga; o achado 08-06 (rate cards expiram em 2026-10-19) é URGENTE operacionalmente mesmo antes da spec.
2. `SPEC-235` API/frontend — soft-lock do pending no perfil durável (A) e 422 ilegível.

Specs que só devem seguir DEPOIS destas: SPEC-199 (depende de SPEC-226), SPEC-205/209 (SPEC-232), SPEC-210 (SPEC-229),
SPEC-212 (toda a trilha A), SPEC-213/214 (SPEC-234), SPEC-049 balanceamento (SPEC-232).

## 5. Áreas não auditadas / limitações

- **Não executado contra Postgres/Supabase real nem provider real** (por regra): achados dos perfis `local/hosted`
  (04-02/03/08, 05-06/09/10, 07-01, 08-03/04/05) são por leitura + simulação do componente Python; confiança marcada em cada um.
- **Não cobertos por tempo (detalhe nos cabeçalhos dos arquivos de área):** 01 `agents/archivist.py` (coberto pela 05),
  modo `RPG_TURN_EXECUTION=concurrent`; 02 geração/normalização de `tactical_profile`, validação de cena em
  `encounter_preparation`, `abyss_events.can_trigger`; 03 `party.py` (ouro), `services/cards.py` (aquisição),
  `objectives.py`; 04 `local_adapters.py`, `runtime.py`, `contracts.py`, `restore_effects.py`, `turn_effects.py`;
  05 `checkpoints` × FAISS, `discovery.py`; 06 `discovery.py`, `world_rules.json` regra a regra, views de mapa/fações
  em `api.py`; 07 `purchases/*`, `native/*`, `AuthScreen`, dialogs/endpoints de arte, abas Pessoas/Facções/Crônica do
  Hud, `ReactionPrompt/SceneZones/WoundTrack`; 08 `stripe_checkout.py`, `google_play.py` (cliente HTTP), triggers de
  debt/hold em `20261015140000`.
- **Duplicatas cruzadas** consolidadas numa única spec (ver mapeamento); IDs originais preservados nos arquivos de área.
- **Interseção com segurança** (citada, não detalhada): 07-05 (storage), 08-09 (fail-open), 05-05 (vazamento latente
  de controlador `hidden` se corrigido ingenuamente — tratado em SPEC-234 R6).
- **Scripts de repro** estão no scratchpad da sessão (`r*.py`, `repro*.py`, `combate/`, `death.py`, `rt.py`, `lease.py`,
  `m.py`, `cap_repro.py`); cada spec exige transcrevê-los como testes de reprodução ANTES da correção.


## Numeração final (coordenador)

- SEC-01 → SPEC-218 (`specs/SPEC-218-fail-closed-perfil-config-hosted.md`)
- SEC-02 → SPEC-219 (`specs/SPEC-219-cota-por-owner-rate-limit-proxy.md`)
- SEC-03 → SPEC-220 (`specs/SPEC-220-sessao-logout-lockout-oidc.md`)
- SEC-04 → SPEC-221 (`specs/SPEC-221-superficies-operacionais-headers.md`)
- SEC-05 → SPEC-222 (`specs/SPEC-222-privacidade-lgpd-logs-retencao.md`)
- SEC-06 → SPEC-223 (`specs/SPEC-223-llm-autoridade-mecanica-prompt-injection.md`)
- SEC-07 → SPEC-224 (`specs/SPEC-224-rls-efetivo-role-minimo-storage.md`)
- SEC-08 → SPEC-225 (`specs/SPEC-225-supply-chain-ci-release-hygiene.md`)
- BUG-01 → SPEC-226 (`specs/SPEC-226-contabilidade-recompensas-xp.md`)
- BUG-02 → SPEC-227 (`specs/SPEC-227-economia-inventario-integridade.md`)
- BUG-03 → SPEC-228 (`specs/SPEC-228-morte-checkpoint-persistencia.md`)
- BUG-04 → SPEC-229 (`specs/SPEC-229-intencao-viagem-fuga-router.md`)
- BUG-05 → SPEC-230 (`specs/SPEC-230-npc-ciclo-de-vida-guard.md`)
- BUG-06 → SPEC-231 (`specs/SPEC-231-combate-morte-aliados.md`)
- BUG-07 → SPEC-232 (`specs/SPEC-232-combate-modificadores-passivas-reacoes.md`)
- BUG-08 → SPEC-233 (`specs/SPEC-233-mundo-perigo-clima-luz-storyteller.md`)
- BUG-09 → SPEC-234 (`specs/SPEC-234-memoria-rag-arquivista-resiliencia.md`)
- BUG-10 → SPEC-235 (`specs/SPEC-235-api-frontend-pending-erros.md`)
- BUG-11 → SPEC-236 (`specs/SPEC-236-finops-wallet-jobs-reprocesso.md`)
