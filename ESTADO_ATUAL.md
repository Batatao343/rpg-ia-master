# ESTADO_ATUAL.md — Handoff para a próxima sessão de código

> **✅ SESSÃO 35 (2026-08-11): hardening de persistência/SSE `done`.** A spec
> [hardening-persistencia-sse-idempotencia](specs/hardening-persistencia-sse-idempotencia.md)
> corrigiu o vazamento de `*.checkpoint.json` na listagem/latest, exclusão agora
> remove save+checkpoint+memória e JSON usa temp+`fsync`+`os.replace`. Falha de
> escrita deixou de responder sucesso falso na API/CLI.
>
> Turnos do mesmo `game_id` são serializados no processo e `action_id` UUID fica
> num ledger limitado no save. Stream e fallback POST compartilham o ID; o worker
> SSE é dono do lock/save e conclui mesmo se o consumidor desconectar. Telemetria
> da API não cobra mais `build_error`/`circuit_open`; criação rejeita classe/raça/
> região fora dos catálogos. O lint Ruff encontrou e corrigiu `CLASSES` sem import
> no wizard CLI.
>
> A suíte inteira agora isola `saves/` e `data/saves_memory/` em `tmp_path`.
> Os **1.390 arquivos históricos** (431 checkpoints; majoritariamente fixtures
> `Streamer`) foram preservados porque podem estar misturados a campanhas reais;
> não houve limpeza destrutiva. CI ganhou Ruff, lint de conteúdo e build web.
>
> **Gate:** `uv run pytest` = **1398 passed, 1 skipped, 14 deselected**; Ruff
> verde; conteúdo **0 erros/0 avisos**; Vite **454 módulos**; `git diff --check`
> verde. Specs funcionais: **92 `done`**, nenhuma aprovada pendente.

> **✅ SESSÃO 34 (2026-08-03): laboratório de combate no frontend `done`.** A
> spec [modo-simulacao-combate](specs/modo-simulacao-combate.md) criou entrada
> “Simular combate” nas telas iniciais, configuração de classe/nível/inimigo/
> quantidade e arena direta usando a UI tática e o motor determinístico reais.
>
> O modo `combat_simulation` persiste por UUID, mas pula campaign planning,
> preparação/narração LLM, RAG, archivist, loot, XP e checkpoints. Cartas,
> Reações, Ruptura, manobras, Vitalidade, Ferimentos, zonas e IA inimiga seguem
> os mesmos serviços de produção; texto livre degrada para ataque básico sem
> provider. Saves de laboratório recebem selo próprio e podem ser reiniciados.
>
> **Smoke browser:** `9f3193bd-2f42-4ad9-a24d-a76661846960`; desktop confirmou
> Sangromante nível 3 × 2 Cães de Rebite com Carta+Reação e estado mecânico;
> mobile 390×844 confirmou carrossel, topbar e Guardar. Console/page errors = 0;
> axe WCAG A/AA = 0 violações. **Gate:** `uv run pytest` = **1388 passed,
> 1 skipped, 14 deselected**; build Vite = 454 módulos; lint = 0/0.

> **✅ SESSÃO 33 (2026-08-03): revisão geral encontrou e corrigiu 2 bugs do
> hardening de playtest.** A spec
> [fix-playtest-liveness-telemetria-circuito](specs/fix-playtest-liveness-telemetria-circuito.md)
> foi criada `approved`, executada testes-first e fechada `done`.
>
> **Bug 1 — falso stale:** recovery usava apenas `created_at`; uma matriz real
> legítima de 8,4 h podia virar `aborted` quando outra run começasse após 6 h.
> Manifesto v3 agora grava owner (`pid`, `host`) + `heartbeat_at`; CLI toca o
> heartbeat por turno. PID vivo no host atual sempre vence idade; host remoto
> com heartbeat recente também. PID morto/heartbeat antigo e v2 legado ainda
> são recuperados como `aborted/stale_running_manifest`.
>
> **Bug 2 — telemetria falsa:** `circuit_open` era contado como request/custo e
> falha embora pulasse a rede. Agora normaliza `network_attempted=false`, não
> entra em provider/custo/network/failure e fica auditável em `llm_skipped`
> (inclusive startup).
>
> **Smoke:** `20260803-130102-999691` = 2/2 offline, manifesto schema v3 com
> owner/heartbeat e `complete`. **Gate:** `uv run pytest` = **1382 passed,
> 1 skipped, 14 deselected**; compileall e `git diff --check` verdes.
> Nenhuma spec funcional aprovada ficou pendente.

> **✅ SESSÃO 32 (2026-08-03): remediações dos relatos de gameplay `done`.**
> Três specs novas foram aprovadas e executadas em ordem:
> [polish-prosa-v2](specs/polish-prosa-v2.md),
> [hardening-playtest-watchdog](specs/hardening-playtest-watchdog.md) e
> [smoke-dirigido-recrutamento-comercio](specs/smoke-dirigido-recrutamento-comercio.md).
>
> **Prosa:** a fronteira Python remove `Contexto do local`, `[ECOS DO MUNDO]`
> e imperativos ecoados; repetição literal recebe transição neutra determinística
> sem nova request. O smoke também encontrou ouro fantasma: o parágrafo monetário
> rejeitado agora é removido mesmo com `15` no schema e “quinze” na prosa, e a
> correção visível deixou de usar `[SISTEMA]` (a auditoria permanece em
> `narrative_rejections`). Invariante nova: `narrative.meta_leak` (`error`).
>
> **Harness real:** `--turn-timeout` cobre startup e turno; timeout aborta a
> campanha e fecha manifesto `aborted`. Runs `running` antigas viram `aborted`
> após 6 h; a órfã `20260803-014405-602783` foi recuperada com
> `stale_running_manifest`. Falha permanente de provider abre circuit breaker
> até a próxima campanha e registra outcome `circuit_open`.
>
> **Smokes reais:** prosa `20260803-114646-799077` = 3/3, zero marcador/erro/
> violação, p95 16,4 s, US$ 0,0039; recrutamento `20260803-114339-651827` =
> Brunna Ponte-Alta na party; comércio `20260803-114423-833666` = Poção de Cura
> Menor e ouro 200→140. Os dois cenários têm oráculos `error` e rodam via
> `--scenario recrutamento|comercio`, sem aumentar `--all`.
>
> **Gate:** `uv run pytest` = **1377 passed, 1 skipped, 14 deselected**.
> Nenhuma spec funcional aprovada ficou pendente.

> **✅ SESSÃO 31 (2026-08-02): volume do Mundo Vivo `done`; épico v2 fechado.**
> A spec
> [conflito-17-volume-conteudo-mundo-vivo](specs/conflito-17-volume-conteudo-mundo-vivo.md)
> elevou o acervo para **153 Cartas de jogador + 40 inimigas**, o bestiário para
> **124 criaturas** (40 novas) e o elenco para **36 NPCs novos** (3 por cada um
> dos 12 hubs). As 15 subclasses têm 5–6 Cartas próprias e Superior; toda região
> tem ≥6 criaturas com Lacaio + Elite/Chefe. Guardas anti-reskin e relatório de
> cobertura agora fazem parte do lint.
>
> **Dados/RAG:** 36 documentos curados com papel/facção/gancho, entidades e
> arestas `located_in`; Codex Jina reindexado (2.239 chunks), consulta de NPC novo
> confirmada. Lint = **0 erros/0 avisos**. Relatório:
> [`docs/content-coverage-2026-08-02.md`](docs/content-coverage-2026-08-02.md).
>
> **Smoke real:** run `20260803-025211-710980` = 3/3 turnos, 4 locais/3 regiões,
> `mock=false`, 0 erro/violação, 18 requests Groq (16 sucessos), US$ 0,010528.
> Smoke dirigido confirmou `mon_guardiao_basalto` com Cartas regionais e Brunna
> Ponte-Alta na rota NPC. **Gate:** `uv run pytest` = **1358 passed, 1 skipped,
> 14 deselected**.
>
> **Próxima:** nenhuma spec funcional aprovada ficou pendente; escolher o próximo
> item de produto/ROADMAP antes de abrir uma nova spec.

> **✅ SESSÃO 30 (2026-08-02): frontend tático de Cartas `done`.** A spec
> [conflito-16-frontend-combate-cartas](specs/conflito-16-frontend-combate-cartas.md)
> entregou contrato API e UI React para mão preparada, custo/frequência/Ruptura,
> escolha de Reação, zonas, Vitalidade/Ferimentos, conhecimento progressivo do
> inimigo, perseguição e morte rica. O level-up legado também foi alinhado às
> escolhas v4 de Carta/evolução/Virtude.
>
> **Smoke browser + real:** build Vite (453 módulos), desktop e mobile 390 px,
> console limpo e axe WCAG 2 A/AA com 0 violações. Campanha real
> `1d9ba1e6-1483-49d5-af01-890c21dea5a1`, `simulated=false`: criação → Carta +
> Reação → Ferimentos → morte/loot → narrativa e, em novo encontro, fuga com
> trilha `escapou`. DeepSeek primário e fallback Groq funcionaram sem erro de
> turno. **Gate:** `uv run pytest` = **1353 passed, 1 skipped, 14 deselected**.
>
> **Próxima spec por ordem:**
> [conflito-17-volume-conteudo-mundo-vivo](specs/conflito-17-volume-conteudo-mundo-vivo.md).

> **✅ SESSÃO 29 (2026-08-02): proveniência de memória `done`.** A spec
> [hardening-memoria-proveniencia](specs/hardening-memoria-proveniencia.md)
> fechou o ledger narrativo: `canonical_event | player_observation | npc_claim |
> inference | legacy_unverified`, confiança derivada pelo motor, fonte/turno,
> metadata no FAISS, retry idempotente e contexto rotulado. Inferência da LLM é
> sempre `speculative`; fala de NPC é `reported`; apenas fonte mecânica aplicável
> pode ser `confirmed`. Assinatura `hidden/secret` sem `secret_revealed` aceito
> para o mesmo ID não entra no contexto.
>
> **Smoke real aceito (3×30):** `secret_rusher`
> `20260802-184026-492723`, `diplomatico` `20260802-234057-869414` e `npc_only`
> `20260802-235207-031964` = 90/90 turnos, `mock=false`, zero erro/violação
> `error`, 226/227 invokes, US$ 0,06370 e 0 falhas RAG. O `npc_only` provou 15
> writes `npc_claim`; nenhum rumor/inferência virou `confirmed`.
>
> **Achado operacional:** uma run real ficou presa no fallback SMART porque
> Anthropic/Gemini não recebiam `LLM_TIMEOUT_SECONDS`. Os builders agora usam
> `timeout`/`request_timeout`, com regressão dedicada; a repetição fechou 30/30.
> **Gate:** `uv run pytest` = **1349 passed, 1 skipped, 14 deselected**.
>
> **Próxima spec por ordem:**
> [conflito-16-frontend-combate-cartas](specs/conflito-16-frontend-combate-cartas.md),
> seguida de `conflito-17-volume-conteudo-mundo-vivo`.

> **✅ SESSÃO 28 (2026-08-02): `conflito-13` E REMEDIAÇÕES `done`.** Os achados
> do smoke real `20260725-101933` viraram sete specs, foram corrigidos e aceitos
> numa nova matriz real de 13 perfis × 30 turnos. Relatório completo:
> [`docs/smoke-correcoes-conflito-v4-2026-08-02.md`](docs/smoke-correcoes-conflito-v4-2026-08-02.md).
>
> **Evidência aceita:** matriz offline `20260802-154317-705789` = 390/390,
> zero erro/violação. Matriz real composta = 390/390, `mock=false`, 0 erro, 0
> violação `error`, 1.119 sucessos de rede, 13 falhas LLM observáveis,
> US$ 0,328488, 148 operações RAG/0 falha, 10 inícios/13 finais de conflito,
> 4 reações, 28 táticas, 7 mortes e zero divergência HP↔Vitalidade. Sanity
> pós-fix de telemetria `20260802-154332-961894` = 5/5 e 24/24 sucessos de rede.
>
> **Correções centrais:** Vitalidade/terminal canônicos; decisão atômica no
> playtest; manifesto e telemetria fail-loud; structured output/sentinelas/path
> Unicode endurecidos; entradas mecânicas fechadas em Python; lifecycle do
> `ConflictSummary`; reações inimigas efetivas. Durante a validação também foram
> corrigidos o deadlock de sobrevivente inconsciente, o cliente Jina sem timeout
> e o vazamento de `resolved_action` antiga no JSONL.
>
> **Pendências naquele fechamento:** a proveniência de memória (fechada na
> sessão 29), smoke dirigido de recrutamento/transação comercial e 44 warnings
> de abertura repetida. `conflito-16` e `conflito-17` ainda eram `draft`.
>
> **Verificação final desta sessão:** `uv run pytest` = **1296 passed, 1 skipped,
> 14 deselected**; lint de conteúdo = **0 erro/0 aviso**; build TypeScript/Vite
> verde (449 módulos). Revisão React também confirmou Vitalidade/estado terminal
> canônicos e eliminou colisão de keys nas listas de party/inimigos.

## Histórico — handoff da sessão 25 (antes do cutover)

> **⚠️ RETOMANDO DA SESSÃO 24?** EM CURSO o **épico Migração do Sistema de
> Conflitos (Valoria v2)** — 16 specs `conflito-01..16` em `specs/` (fonte
> funcional em `docs/valoria_conflict_migration_v2/`). Substitui o combate atual
> por um jogo tático de cartas 100% determinístico; **cutover atômico** só na
> `conflito-13` (jogo fica injogável no meio, por design). **`conflito-01`
> (fundação de dados) `done`** + **`conflito-02` (Cartas) `done`**.
> **01:** 5 Virtudes (0-5), Vitalidade/Ferimentos por Corpo, nível máx 10,
> migração v3→v4 (saves antigos ARQUIVADOS — corte deliberado), `attributes`/
> mana/stamina fora do jogador via ponte `actor_mods` (+30 testes).
> **02:** sistema de Cartas (`services/cards.py` — Acervo/Preparação/frequência/
> Ruptura/evolução A-B; `data/cards/` exemplos; criação 6+4+2; level-up escolhe
> Carta), convive com `known_abilities` até o cutover (+25 testes).
> **03:** cena posicional (`services/conflict_scene.py` — zonas não-grid, eixos
> Distância/Postura/Ocultação, Engajamento separado, objetos com catálogo FECHADO
> de efeitos, cena congelada + reforços), aditivo puro em `combat["scene"]` (+13).
> **04:** motor de resolução (`services/conflict_resolution.py` — iniciativa por
> lado, ataque 2d10+Virtude vs Esquiva, Crítico/Super por dupla, Vantagem 3d10,
> testes gerais Ímpeto+Presságio, Ruptura=Vantagem). ADITIVO — fiação no nó
> (Pré/Ação/Pós) + remoção do motor antigo vão no **cutover conflito-13** (+19).
> **05:** dano→Ferimentos (`services/conflict_damage.py` — ordem fixa R8: dano×
> crítico → res/vuln/imunidade → Proteção → Integridade → Vitalidade/Gravidade →
> Ferimentos; 3 físicos + 6 sobrenaturais; armadura/escudo/Comprometida; Ferimento
> localizado agrava/escala; sacrifício Sangromante; recuperação). Aditivo (+26).
> **06:** Reações/movimento tático (`services/reactions.py` — janela sobre ação
> declarada, cadeia com limite de 1 reação COMUM por personagem, reação-responde-
> reação, ordem alvo→aliados→Agilidade, Ataque de Oportunidade UNIVERSAL fora do
> limite; `conflict_scene.py` ganhou orçamento por turno Pré/Ação/Pós + manobras
> Engajar/Desengajar/Guardar/Esconder-se/Procurar/alertar + ocultação RELATIVA por
> observador `hidden_from`/`approx_from`). Aditivo — fiação no cutover 13 (+18).
> **07:** morte rica (`services/death_flow.py` — último Crítico dispara Última
> Ação com Vantagem extrema/ignora recursos ausentes/pode Ruptura → Estado
> Terminal → morte imediata sem aliado ou até 2 estabilizações (kit/Médico/poção
> = auto metade Vitalidade); Cicatriz OBRIGATÓRIA via LLM+guard `FallbackLLM`;
> consciência pós-conflito por Ferimento; categorias de inimigo Lacaio/Padrão/
> Elite/Chefe/Nomeado; golpe não-letal; rendição 100% determinística por perfil;
> encerramento sem interpretação livre). Aditivo — cutover 13 reconcilia com
> `checkpoints.py`/`death_pending` (+20).
> **08:** perfil tático (`services/tactical_profile.py` — `TacticalProfile` de
> prioridades ORDENADAS; `pick_action` decide IA de inimigo por precedência sem
> LLM em combate; `validate_companion_order` valida ordem contra Restrição/
> resistência Flexível/Resistente/Absoluta/Autônoma sem crashar; controle de party
> por perda-de-comando explícita; `generate_tactical_profile` 1× via LLM+guard,
> cacheado) + info revelada (`services/bestiary_knowledge.py` — painel só-público
> R7, revelação de Cartas/Resistências que PERSISTE no bestiário via overlay
> `data/runtime/`, exclusiva de variante fica oculta). Aditivo — remoção de
> `get_behavior` e fiação no cutover 13 (+16).
> **09:** fuga/perseguição (`services/chase.py` — trilha Pressionado→Afastado→
> Quase Livre→Escapou derivada da distância; perseguidor só segue se o
> `TacticalProfile` mandar; condutor sempre o protagonista + Virtude por
> abordagem; Teste de Sorte 1d10 por companheiro com cap ±1; abandono separa o
> NPC e resolve o destino por SIMULAÇÃO determinística por seed ∈ {fuga/captura/
> rendição/esconderijo/combate/morte/reencontro}; sacrifício voluntário só com
> traço; ataques em perseguição). Aditivo — substitui `combat_flee_*` no cutover
> 13 (+17).
> **10:** Abismo em conflito (`services/abyss_events.py` — eventos preparados pela
> LLM ANTES do combate com `base_na_cena` OBRIGATÓRIA; carregamento 100%
> determinístico/seed em combate por Cargas+gatilho+prioridade+usos, ZERO LLM;
> proibições rígidas R4/R6 — não desfaz sucesso, não controla mente, não cria/
> agrava Ferimento direto, catálogo fechado da conflito-03; assinatura visual fixa
> + gasto de Carga reportado). Camada COMPLEMENTAR aos gatilhos de classe (não
> substitui). Aditivo — consumidor de `abyss_charge` no cutover 13 (+13).
> **11:** preparação de encontro (`services/encounter_preparation.py` +
> `data/potency_by_level.json` — Nível do Encontro ABSOLUTO em Python puro, sem
> nível de party; potência por categoria Fraco/Moderado/Forte/Devastador × nível;
> `validate_preparation` exige catálogo fechado + base narrativa por objeto + base
> na cena por evento do Abismo; seleção de criatura por região; `prepare_encounter`
> via LLM+guard → `fallback_safe_scene` determinística quando a cadeia falha;
> `build_npc_combat_sheet` dá ficha de combate completa ao NPC). Aditivo — mudança
> de GRAFO no cutover 13 (+11).
> **12:** loot + resumo canônico (`services/conflict_summary.py` —
> `ConflictSummary` de 18 campos montado do estado FINAL já resolvido SEM LLM
> [mortos/rendidos/fugitivos/capturados/inconscientes/Ferimentos/Cicatrizes/
> Cartas+resistências reveladas/objetos usados/fatos de relação/loot/party];
> `loot_context` passa o Nível do Encontro como `danger` com `economy.roll_loot`
> INTACTA; `validate_narrative_consistency` proíbe reverter morte→fuga/soltar
> capturado/restaurar cenário sem novo acontecimento; `summary_facts` p/ archivist).
> Aditivo — consumo em loot/archivist no cutover 13 (+7).
> **13 (CUTOVER, `in-progress`):** decisão R6 fechada = **Opção A** (death_flow
> resolve Última Ação/Estado Terminal/estabilização no conflito; só a morte REAL
> aciona `death_pending`/tela Continuar-Aceitar da sessão 23; sobreviver aplica
> Cicatriz e o combate segue). **Etapa 1 (auditoria MORRE/SOBREVIVE de
> `combat_mechanics.py` + `tests/test_cutover_audit.py`) `done`.** **Etapa 2
> (`services/conflict_turn.py` — `TurnDeclaration` + orquestrador de turno Pré/Ação/
> Pós compondo os motores 01-12, 100% determinístico) `done` (+7).** FALTA o "big
> bang": reescrever `combat_node`+`main.py` pro motor novo, remover as funções
> d20+AC, reescrever o playtest (declaração estruturada) e auditar ~199 testes de
> combate — leva a suíte ao vermelho, exige passo dedicado (não iniciado).
> **DECISÃO DO USUÁRIO (2026-07-23):** o "big bang" do cutover fica ADIADO. Antes
> dele, fazer **conflito-14 (autoria de Cartas)** e **conflito-15 (autoria de
> bestiário/perfis)** — rodam em paralelo, NÃO quebram nada, mantêm o repo verde.
> **14 `done`** (80 Cartas autorais na escala nova, 16/classe: 7 tronco + 3×3
> subclasse; catálogo fechado `CARD_EFFECT_KINDS`; Ruptura+Evolução A/B nas 15
> centrais; parity `dano_base/custo ∈ [1.5,4.0]`; `docs/CARTAS.md`;
> `scripts/gen_cards_v4.py`; +16 testes). **15 `done`** (84 criaturas migradas pro
> schema v4 via `scripts/migrate_bestiary_v4.py` — categoria canônica, Virtudes
> 0-5, Vitalidade×Corpo, resistências tipadas, 10 arquétipos táticos ricos com
> regra de fuga/rendição, 18 Cartas de inimigo com assinatura OCULTA por criatura;
> ADITIVO — motor antigo intacto; +17 testes). Lint da Fase 7 estendido
> (`validate_cards`/`validate_bestiary`). **PRÓXIMA: o cutover `conflito-13`**
> (big bang) agora que 14/15 fecharam. **Suíte 1273 verde.** Última atualização:
> 2026-07-23 (sessão 25).
> Ordem completa no ROADMAP § Migração. Histórico anterior: abaixo e `CHANGELOG.md`.

---

## TL;DR — sessão 23 (2026-07-20): letalidade v2 + specs do run + parity de classes

Run de validação `20260720-093014` fechado (17 campanhas reais, 0 erro, $1.74).
Achado dominante nos logs: **combate/explorador morrem por AUSÊNCIA de recovery**
(HP travado ~40% por 5–7 turnos; viagem não cura; descanso em zona de perigo vira
combate) — não por dano alto. Quester sobrevive só evitando luta.

**Decisões do usuário → entregas:**
1. **[letalidade-early-game-v2](specs/letalidade-early-game-v2.md) Etapa 2
   IMPLEMENTADA** (`approved`) — 4 alavancas determinísticas: (1) **descanso/viagem
   recuperam** — descanso de early-game (nível ≤3) em zona não-apex de perigo ≤3
   NÃO sorteia encontro (`world_utils.recovery_rest_safe` + fio no storyteller) +
   cooldown de encontro +2 turnos no early-game; (2) **+1 poção inicial** por classe
   (Médico=3), via gerador; (3) **+HP base** nas frágeis (Arcanista 22→26,
   Sangromante/Corruptor/Médico →30, Devoto →40), via gerador; (4) **+dano de
   early-game** runtime (`combat_mechanics.early_game_damage_bonus`: +2 nível 1–2,
   +1 nível 3, 0 do 4+, só o herói). **+9 testes.**
2. **[fix-explorador-loop-navegacao](specs/fix-explorador-loop-navegacao.md)
   `done`** (B) — perfil Explorador oscilava cidade↔interior quando tudo já foi
   visitado (interior tem 1 saída) → bounce + `loot-exploracao` nunca dispara. Fix
   = memória anti-backtrack + fronteira primeiro (`_recent`, reset por campanha no
   runner). **+6 testes.**
3. **[checkpoints-morte](specs/checkpoints-morte.md) `in-progress`** (C) — 8
   decisões RESOLVIDAS (§2.1; memorial = escolha voluntária na tela de morte,
   nunca imposto; sem permadeath; restore do início se sem checkpoint). **FUNDAÇÃO
   + VERTICAL DE MORTE `done`:** `services/checkpoints.py` + `persistence`
   refatorado (fonte única + `save/load/has_checkpoint`); combat→`death_pending`
   (sem Saque; `_narrate_fall` + evento `player_downed`); `main.py` gate;
   `runner` auto-restore + `deaths_log`; `api` (`maybe_write` + checkpoint inicial
   + `POST /game/death` + 409 com queda pendente + `GameResponse.death_pending`);
   `DeathModal` no frontend (`npm run build` verde) + prompt CLI. **HIGIENE `done`:**
   "O Saque" + `pos-saque` INTEGRALMENTE aposentados (`apply_downed`/`death_outcome`/
   `_death_template`/`_narrate_downed`/beat de recuperação/`downed_grace`/invariantes
   `check_downed`+`check_downed_recovery`/campo `downed_grace_until_day` removidos;
   `test_pos_saque` deletado). **Spec C `done`.** **Smoke real** (run
   `20260721-042146`, combate 25t, DeepSeek $0.051, 0 erro): morreu 4× (1ª t13),
   **auto-restaurou e seguiu até t25** (antes abortava no t13) — vertical validado
   no LLM real. Bug pego pelo smoke: `vitals.dead_no_game_over` falso-disparava na
   morte (hp=0 vem com `death_pending`) → corrigido + teste.
4. **Fix D — `secret_leak` ignora segredo já conhecido pelo jogador**
   (`services/secret_signatures.revealed_corpus` inclui `narrative_summary` +
   `player.known_secrets`): a Velha Magda revelara o pacto ao player; a narração
   repetindo virava falso-positivo. **+4 testes.**

5. **Parity ESTÁTICA das habilidades `done`** (pedido do usuário: "nenhuma muito
   mais forte que a outra") —
   [balanceamento-classes-pos-playtest §10](specs/balanceamento-classes-pos-playtest.md).
   Insight: parity MECÂNICA é número → medida direto do catálogo
   (`player_abilities.json`), **sem playtest**. Métrica = dano-efetivo/custo-real
   (`custo = Entropia + self_harm/2`; conta DoT/efeito). Achado: roster **bem
   balanceado por papel** (tank Devoto baixo por design; DoT do Corruptor
   compensa dado com DoT; Médico baixo é lacuna de medição — cura não pontua, NÃO
   buffar). Falso-alarme corrigido: "Toque Cru" parecia 7.0/E mas tem
   `self_harm:4` (glass-cannon). **Único outlier real: `fervor_ritual`** (2d6 vs
   2d8 dos irmãos) → fix `2d6→2d8` no gerador. **+2 testes-guarda de parity**
   (`test_arvores_classes`: banda 1.5–4.0 dano/E p/ dano puro; trava do fix).

**Suíte: 1001 → 1039 → 1019 → 1020 offline verdes** (+38 do trabalho novo, −20 da
higiene do Saque, +1 do fix do smoke; 1 skip). `npm run build` verde. Baseline de letalidade mudou (A) → run
`20260720-093014` STALE p/ decidir NÚMEROS de Entropia/Carga; tuning dos 8 knobs
pede rodada real DEDICADA pós-A (parity de dano já resolvida).

**Próximos passos:** (1) rodada real pós-A p/ o tuning dos knobs de Entropia/Carga
(o baseline mudou); (2) medir se as 4 alavancas de A reduziram a letalidade de
fato (comparar `first_death_turn` com `20260720-093014`).

---

## TL;DR — sessão 22 (2026-07-20): 5 specs do playtest longo IMPLEMENTADAS

Análise do run `20260719-160014` + decisões do usuário → 5 specs `approved` e
implementadas (TDD, suíte **970 → 1001 offline verdes**, +31; 1 skip):

1. **[playtest-agente-curioso-entropia](specs/playtest-agente-curioso-entropia.md)
   `done` — o BLOQUEADOR do balanceamento.** Raiz achada: os perfis de combate
   só mandavam "Ataco X" → as 101 habilidades NUNCA rodavam → Entropia travava em
   16/16 (flooding=100%/starvation=0% era artefato disso + do snapshot). Fix em 2
   frentes: (a) **agente curioso** — `Agressivo`/`Combate`/`Recrutador` leem
   `known_abilities` e nomeiam habilidade de Entropia ("Uso {nome} em {alvo}"),
   curam com HP baixo, descansam em zona segura; (b) **telemetria de GASTO** —
   `combat_mechanics.resolve_player_action` carimba `_last_entropy_spent`/
   `_last_ability_id`/`_last_used_active` (transitório); runner lê gated por rota;
   `summary.entropy` reescrito (spent_total, %ativa, starvation/flooding
   redefinidos por gasto, não snapshot); report ganhou `%ativa`/`gasto/turno`.
2. **[npc-in-scene-viagem](specs/npc-in-scene-viagem.md) `done`** — os 43
   `recycled_npc`: fuga de combate aplicava viagem SEM `reset_scene` → flag zumbi.
   Fix: [combat.py:726](agents/combat.py) reseta cena na fuga; invariante mede
   vazamento real (`npcs_for_context`), não flag crua; party excluída.
3. **[aliados-em-combate](specs/aliados-em-combate.md) `done`** — motor de combate
   já incluía party ativa; faltava ponte NPC-amigo-em-cena → combatente. Novo
   `party.scene_allies` (in_scene + rel≥6 + fação não-hostil → aliado TRANSITÓRIO,
   não vira party permanente, dano reflete no NPC); `combat_party` na iniciativa/
   resolução; `encounter_budget` conta transitórios; invariante `combat.phantom_ally`.
   **Perfil `recrutador` novo** (faz o máx. de amigos).
4. **[loot-exploracao](specs/loot-exploracao.md) `done`** — explorar recompensa
   (escada de raridade): novo `services/exploration.py` reusa `economy.roll_loot`
   (raridade por perigo, claim de único); achado na 1ª visita (fog of war) NUNCA
   único; **baú curado** (`treasure` no world_map: `pm_profundezas`,
   `ae_ruinas_submersas`) one-shot via `world.looted_locations`, pode ter único.
   Fiado no storyteller (nota no prompt + claim no pending).
5. **[letalidade-early-game-v2](specs/letalidade-early-game-v2.md) `approved`
   (medir→decidir)** — sem código novo: instrumentação já existe; a Etapa 1
   (baseline com agente corrigido) É o playtest desta sessão; tuning decidido
   DEPOIS com o usuário.

**Em curso:** playtest real de 17 campanhas (15 balanceamento das 5 classes ×
{combate,explorador,quester} + 1 comerciante + 1 recrutador) p/ validar as
mudanças e gerar os novos achados. **Backlog `comerciante`** endereçado no run.

---

## TL;DR — Em que pé está

**Sessão 2026-07-19 (20): REVISÃO DE CÓDIGO/ROADMAP — 3 specs novas, 2 `done` +
1 instrumentada.** Auditoria do épico de classes (sessão 19) achou bugs que o
mock/testes de unidade escondiam:

1. **[fiacao-regras-orfas-classes](specs/fiacao-regras-orfas-classes.md) `done`
   — 3 mecânicas de classe estavam MORTAS** (função pronta + testada em unidade,
   NUNCA chamada pelo fluxo de jogo): (a) **taunt do Devoto** — `pick_target`
   ignorava a condição `control:"taunt"`; o tank não tankava. (b)
   **Transformação do Corruptor** — `apply_transformacao` sem callsite; única
   consequência de Carga que não rodava. (c) **Purga da Carga do Médico** —
   efeito `reduce_ally_abyss` descartado em silêncio por `_split_typed_effects`.
   Fix + **R4 anti-órfão**: `combat_mechanics.HANDLED_KINDS` + teste que varre
   os JSONs gerados e exige handler p/ todo kind/trigger (teria pego os 3).
   **+11 testes.**
2. **[isolar-cache-runtime](specs/isolar-cache-runtime.md) `done` — bug
   recorrente das sessões 15/16.** `bestiary.json`/`npc_database.json`/
   `custom_artifacts.json` eram gravados em runtime nos arquivos versionados
   (exigia `git checkout` manual; run real gravou "Afogado" e derrubou testes).
   Agora: overlay gitignored `data/runtime/` (`gamedata.runtime_cache_path`,
   env resolvida no call), curadoria READ-ONLY (vence no merge); suíte→tmp,
   playtest→`saves_playtest/runtime/`. `git rm --cached data/npc_database.json`.
   **+8 testes; suíte e playtest deixam `data/` limpo.**
3. **[balanceamento-classes-pos-playtest](specs/balanceamento-classes-pos-playtest.md)
   `in-progress` — instrumentação `done`, tuning adiado.** Harness ganhou
   `--class`, telemetria de Entropia/Carga por turno e seção **Classes** no
   report. Baseline mock (40 campanhas, 0 erro) + real parcial capturados. Os 8
   knobs `[BALANCEAR]` PERMANECEM marcados: mock não mede economia de Entropia
   (só ataque básico → flooding 100% é artefato) e o real ficou fino (combate
   morre nível 1). Tuning exige rodada real dedicada e mais longa. **+8 testes.**
4. **Tarefas menores do backlog:** **traits lote 2** (40→**80** em
   `data/traits.json`, regiões subrepresentadas reforçadas); **curadoria da Rede
   Carmesim** (pendência da Fase 7) — decisão: nome/monitoramento = conhecimento
   comum do norte, iminência/natureza = `hidden`; suavizado o over-share real em
   `factions.txt` ("O segredo:" num doc `public`), migrate + **reindex do lore**
   (2203 chunks, vazamento sumiu) + assinatura de iminência em
   `secret_signatures`. `validate.yml` verde no último push (confirmado via `gh`).
5. **Suíte: 918 → 945 offline verdes** (+27) + 1 skip.

**Trabalho concorrente (enquanto rodava o playtest longo de balanceamento) —
auditoria de mecânica-morta + 2 decisões do usuário:**
6. **Auditoria "dado declara capacidade, motor não fia" além das classes** (o
   padrão dos 3 bugs). Scan estático de funções públicas sem callsite de
   produção: 9 candidatas → maioria falso-positivo (Pydantic validator, cache-
   clearers do runner) ou stub trivial. **1 achado real:** o **gating narrativo
   por classe** (`agents/class_themes.py`) estava MORTO desde a deleção do Ruler
   (faxina 2026-07-03), mas CLAUDE.md ainda o anunciava.
7. **Gating de classe APOSENTADO** (decisão do usuário: "mecânica é toda Python
   agora, gate por LLM não faz falta"). Removido `agents/class_themes.py` + 2
   testes + stub `archive_narrative`; `class_themes.json` fica só p/ flavor do
   prólogo; CLAUDE.md corrigido.
8. **[weather-global-vivo](specs/weather-global-vivo.md) `in-progress`** (o
   usuário QUIS: "acho bem legal ter e que impactasse no jogo"). A máquina de
   clima GLOBAL estava 90% pronta (tick+efeitos fiados) mas nada iniciava
   eventos. Novo trigger **determinístico** em `advance_weather`
   (`maybe_start_global_weather`: chance base 6% + 3%/perigo, sem canal LLM);
   Tempestade de Éter / Noite Sem Estrelas agora varrem Valoria e impactam
   combate/percepção/descanso/viagem. **+7 testes.** Suíte **945 → 950**.
9. **[itens-vivos-e-luz](specs/itens-vivos-e-luz.md) `in-progress`** (3 perguntas
   do usuário: itens aplicam habilidades? passivas? tem luz? — **as 3 eram
   NÃO**). Fiado: **passiva de item** entra em `player_passives` (era ignorada);
   **item ativo ofensivo** (`use_item_in_combat` com alvo — stun/sono/dot/medo no
   inimigo com save); **sistema de LUZ** (`light_level`: noite/masmorra sem luz
   penaliza percepção −3 e acerto −1; tocha/lanterna anula; cidade iluminada).
   **+22 itens** ancorados na lore (4 luz, 9 passivas, 6 ativos, 3 suportes);
   bloco `<AMBIENTE_DE_LUZ>` no narrador + chip de luz no HUD. Bug colateral:
   `corda` tinha passiva-string (filtrado). **+20 testes. Suíte 950 → 970.**
   Falta só o smoke real (adiado — Jina em uso pelo playtest).

---

## TL;DR — sessão 19 (épico de classes)

**Sessão 2026-07-19 (19): SISTEMA DE CLASSES REFATORADO — 5 POSTURAS DIANTE DO
ABISMO** ([spec `done`](specs/refatoracao-sistema-classes.md); mecânica em
[docs/CLASSES.md](docs/CLASSES.md), narrativa em
[docs/CLASSES_NARRATIVA.md](docs/CLASSES_NARRATIVA.md)):
1. **10 classes → 5 classes × 3 subclasses.** Devoto do Abismo (tank/ama) ·
   Sangromante (dano/negocia) · Corruptor (DoT/trabalha junto) · Arcanista
   Cinzento (dist/manipula) · Médico de Campo (suporte/nega). Cada classe é uma
   postura filosófica diante do Abismo.
2. **Dois recursos novos.** **Entropia** = pool único (substitui mana+stamina do
   jogador; recompõe INTEGRAL no descanso). **Carga do Abismo** = longo prazo (não
   cai no descanso; patamares leve/moderado/severo). `state.py`/creator/api/runner
   backfillam `entropy`/`max_entropy`/`abyss_charge`.
3. **Gatilhos + regras + consequências por classe (100% Python, `combat_mechanics`).**
   Gatilhos: on_damage_taken/on_self_harm/on_decay_nearby/on_channel/on_ally_suffer
   (`apply_entropy_trigger`, respeita `per_turn_cap`/round). Regras especiais:
   taunt-escala-com-Entropia / blood_leak / boiler (caldeira estoura) / reduce_ally_abyss
   (só Médico). Consequências: Insônia (descanso rende menos) / Cicatriz (−max_hp
   permanente) / Transformação (debuff por domínio) / Dependência (custo dobra) /
   Recidiva (oculta até colapso). Fiados no loop de combate + `apply_rest`.
4. **Árvore MÍNIMA jogável (41 habilidades).** `scripts/gen_classes_v2.py` gera
   `classes.json`+`player_abilities.json` **alinhados ao schema do motor** (effects
   `kind`, cura via `damage_type:"Cura"`). A árvore RICA (~100 hab, passivas) é a
   spec #2 `arvores-habilidade-classes` (Fable).
5. **Migração `_migrate_v2_to_v3` (schema v3):** classe antiga → nova + backfill de
   Entropia + descarte de habilidades mortas. Saves antigos ficam órfãos (arquivar).
6. **HUD:** barra Entropia (roxo-abissal) + chip Carga do Abismo por patamar; Médico
   oculta o número (Recidiva). `npm run build` verde.
7. **Testes:** 881 → **898 offline verdes** (+34 `test_classes_refactor`; ~40 testes
   de classes antigas migrados/reescritos: passivas extintas viraram gatilhos de
   Entropia). Playtest runner default = Devoto do Abismo (sobrevive no mock).
8. **Smoke real 4/4** (DeepSeek): Sangromante criado no LLM real com Entropia
   mapeada (16/16) + mana/stamina 0; auto-dano somou Entropia+Carga; descanso
   recompôs Entropia sem baixar Carga; Devoto apanhou → on_damage_taken.

**Segunda spec do épico — [arvores-habilidade-classes](specs/arvores-habilidade-classes.md)
`done` (mesma sessão, autoria em Fable):**
9. **Árvore RICA: 101 habilidades** (41 ativas + **35 passivas + 25 utilitárias**),
   geradas por `scripts/gen_classes_v2.py`. Cada tronco: 2 ativas + 2 utilitárias
   do doc-fonte + 1 passiva; cada uma das 15 subclasses: 2 ativas encadeadas +
   2 passivas + 1 utilitária.
10. **Passiva na árvore funciona:** `ability_kind` no schema;
    `combat_mechanics.player_passives` (classe + aprendidas) em TODOS os callsites
    do jogador; 5 triggers novos: `entropy_max_bonus` (no `apply_choice`) ·
    `entropy_on_kill` · `entropy_cost_reduction` (piso 1) · `charge_discount`
    (piso 0) · `carga_embrace` (patamar de Carga vira bônus). Inimigo NÃO ganha
    passiva de árvore (teste dedicado).
11. **Utilitária = capacidade fora de combate:** `out_of_combat`
    {label/scope/prompt_hint}; gate determinístico + bloco `<CAPACIDADES_DO_HEROI>`
    no prompt do storyteller (`utility_context_block`). Passiva/utilitária FORA
    dos chips e do catálogo do parser de combate; HUD com selo ✦/⚒ (ficha +
    LevelUpModal).
12. **Suíte:** 898 → **918 offline verdes** (+20 `test_arvores_classes`).
    **Smoke real 4/4:** elegibilidade lvl2 com utilitárias/passivas; `juros_do_corpo`
    somou "+1 passiva" no dano; `cofre_de_sangue` subiu max_entropy 16→19; o
    storyteller REAL narrou "Avaliação de Preço" citando a capacidade injetada;
    `reduce_ally_abyss` purgou Carga de aliado.

**🏁 O ÉPICO DO SISTEMA DE CLASSES ESTÁ 100% `done` (as 2 specs).** Próximo
natural: balanceamento dos números `[BALANCEAR]` após playtest; tiers 5+
(nível 9–20) de fast-follow.

---

## TL;DR — sessões anteriores

**Sessão 2026-07-17 (18): 10 SPECS APROVADAS + ORDEM + EMBEDDINGS MULTI-PROVIDER** —
1. **Todas as specs pendentes viraram `approved` com ordem de dev cravada no
   header de cada uma.** Duas fases:
   - **Sistema de classes (2 specs, ordem #1→#2):**
     [refatoracao-sistema-classes](specs/refatoracao-sistema-classes.md) →
     [arvores-habilidade-classes](specs/arvores-habilidade-classes.md)
     (a 2ª depende do motor de Entropia/Carga da 1ª).
   - **Playtest longo (8 specs, ordem #1→#8):**
     [embeddings-provider](specs/embeddings-provider.md) →
     [playtest-stop-gameover](specs/playtest-stop-gameover.md) →
     [combate-lifecycle](specs/combate-lifecycle.md) →
     [pos-saque-recuperacao](specs/pos-saque-recuperacao.md) →
     [npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) →
     [beats-visibilidade-ptbr](specs/beats-visibilidade-ptbr.md) →
     [encontros-dedupe](specs/encontros-dedupe.md) →
     [polish-prosa](specs/polish-prosa.md).
2. **[embeddings-provider](specs/embeddings-provider.md) `done`:** `rag.py`
   ganhou cadeia multi-provider
   `EMBEDDING_ROUTES = [jina, openai, ollama, gemini]` (Gemini é o ÚLTIMO
   fallback). Cada índice FAISS grava `embeddings_meta.json` e fica **PINADO**
   ao provider que o gerou (nunca mistura vetores); provider indisponível →
   índice DESATIVADO com warning (nunca crash). `RPG_EMBEDDINGS=<p>` força.
   `get_embeddings_for(p)` abre índice pinado; write deriva provider de
   `_resolve_provider()` (puro, sem global vazável). `codex_loader.ingest_codex`
   grava meta também. **+12 `test_embeddings_provider`**; seam de
   `test_npc_memory` migrado p/ `_EMBEDDING_BUILDERS` (pin não passa mais por
   `get_embeddings`). `.env.example` ganhou `JINA_API_KEY`/`RPG_EMBEDDINGS`.
   **RAG VIVO:** re-index real com Jina executado (lore 2203 chunks + regras,
   meta jina); smoke §6 3/3 (queries PT-BR sem 429 + memória de sessão).
   ⚠️ Free tier Jina = **100k tokens/min**: re-index do Codex esgota o minuto,
   regras precisaram de ~70s de espera (não é erro).
3. **[playtest-stop-gameover](specs/playtest-stop-gameover.md) `done`:**
   harness agora PARA no `game_over` (turno da morte é o
   último; `aborted_reason="player_death (turno N)"`) — antes rodava 140/300
   turnos mortos poluindo p50/rotas/custo. **Rota fiel:** `_run_turn` captura a
   decisão do `dm_router` via streaming multi-modo (`updates`+`values`), não o
   `next` final (combate/loot sobrescreviam); combate ativo na entrada = rota
   `combat_agent`. Fallback pro `invoke` quando o grafo não tem `.stream`
   (wrappers de teste). `telemetry` ganhou `death_location`/`death_cause`;
   `report` ganhou seção **Mortes** (turno/local/causa). **+8
   `test_playtest_harness`.** Validação mock: 12 perfis × 50t = **552 turnos
   vivos, 0 rota vazia** (antes o perfil `combate` registrava só storyteller).
   ⚠️ Fix colateral: run mock agora desliga embeddings reais
   (`_offline_embeddings`) — com Jina viva no `.env`, o archivist batia na API a
   cada turno (rede/rate limit → timeout). **Smoke §6 real 3/3:** combate morreu
   no t14, run PAROU (aborted player_death), routes com combat_agent=6, p50=14s
   sem turnos de 1ms, $0.04 (deepseek 49 + groq 5).
4. **[combate-lifecycle](specs/combate-lifecycle.md) `done`:**
   o router ganhou **gate determinístico de combate**
   (`_combat_gate`): com `combat.active`, viagem NÃO teleporta — vira tentativa
   de fuga (R1: flag `combat_flee_attempt`+destino; sucesso aplica
   `apply_travel` no mesmo turno, enredado falha e inimigos agem); npc/loot são
   bloqueados → `combat_agent` (R2); combate órfão (idle_turns) expira em 3
   turnos (R3). `combat_node` zera `idle_turns` e SEMPRE zera `active` no fim
   (R5 — antes fuga com inimigo vivo deixava flag zumbi). Nova invariante
   `combat.zombie` (R4, `error`, idle≥5). `state.py` documenta `combat.idle_turns`
   + `combat_flee_attempt`/`combat_flee_destination`. **+10
   `test_combat_lifecycle`.** Harness mock 12×50t: **492 turnos, 0 combat.zombie,
   maior sequência de combate ativo = 4t (era 59)**. Smoke §6 real: "Viajo para
   X" em combate → narrou FUGA e viajou só após escapar (nunca teleporte),
   combate limpo.
5. **[pos-saque-recuperacao](specs/pos-saque-recuperacao.md) `done`:** o Saque
   deixa de ser espiral de morte. `apply_downed` agora deixa **1 poção de cura**
   (R1) + marca `downed_recente` (R4) + **carência de 1 dia** no local seguro
   (`downed_grace_until_day`, R2: storyteller não sorteia encontro em zona segura
   durante a carência; ir pro perigo cancela). `campaign_manager` prefixa um
   **beat de recuperação determinístico** ("Recupere forças em {local}", R3);
   `apply_rest` remove a marca; storyteller ganha cláusula de prompt de
   recuperação (R4). Invariante `downed.no_recovery_path` (R5, warning).
   **+13 `test_pos_saque`.** Harness 3 seeds: 0 violações, sobrevivência muito
   além do baseline 1-4t. Smoke real: poção+beat+narração ✓.
6. **[npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) `done`:** rota NPC
   sem alvo não devolve mais "Ninguém responde." (o quester perdia 7+ turnos).
   `npc_layers.npcs_in_scene` resolve alvo (NPC em cena → aliado presente, R1);
   sem candidato → `npc_actor` delega ao `storyteller` (nova aresta condicional
   em main.py) que narra a ausência + gancho (R2); pergunta sobre missão injeta
   o beat atual no contexto do NPC (R4, `_mission_hint_block`). **+9
   `test_npc_fallback`.** Mock quester/npc_only 50t: **0 "Ninguém responde"**.
   Smoke real: aliado cita objetivo; sozinho → gancho rico.
7. **[beats-visibilidade-ptbr](specs/beats-visibilidade-ptbr.md) `done`:**
   segredo não vaza mais pelo BEAT + beats sempre pt-BR. Novo módulo
   `services/secret_signatures.py` (R1: assinaturas + rumor público + heurística
   de idioma) consumido pelo invariante E pelo planner. `campaign_manager`
   sanitiza beat/climax/arc_title (R2), re-tenta 1x se detectar inglês e mantém
   plano anterior na 2ª falha (R4), com instrução anti-segredo no prompt (R3).
   Invariante `knowledge.secret_leak` agora checa o texto dos BEATS (R5).
   **Achado F resolvido:** o "beat em inglês" era o **fallback template** (estava
   em inglês) — traduzido. **+11 `test_beats_visibilidade`.** Smoke real: 3
   planos pt-BR sem segredo.
8. **[encontros-dedupe](specs/encontros-dedupe.md) `done`:** NPC gerado não
   vira mais carrossel de template ('Sobrevivente moribundo' em 3 locais em 6
   turnos). `npc_layers.npcs_for_context` filtra o contexto do narrador por
   vínculo de local (`home_location_id`) + in_scene/party (R1) — usado pelo
   storyteller e pelo `context_builder`; `_with_new_npc` carimba
   `created_turn`/`last_seen_turn`. R3: storyteller não repete o mesmo template
   de encontro 2× no mesmo local (`world.last_encounter_id`). Invariante
   `narrative.recycled_npc` (R4). **+7 `test_encontros_dedupe`.** Smoke real: NPC
   gerado preso ao local (não vaza p/ outro).
9. **[polish-prosa](specs/polish-prosa.md) `done`:** três tiques de prosa do
   playtest resolvidos. Novo `services/prose_guard.py` (aberturas, repeats,
   openings_clause, log). Storyteller e combat recebem as 2 últimas aberturas e
   pedem variação (R1); morte/downed exigem 2ª pessoa, proibindo "o herói/
   viajante/aventureiro" (R2); storyteller fecha com 2-3 opções "— …" + "Ou
   outra ação" fora de combate (R3); telemetria `rpg.prose` de repetição (R4);
   invariante `narrative.repeated_opening` (R5, filtrada em mock no runner).
   **+8 `test_prose_guard`.** Smoke real: 4 aberturas distintas + menu; downed
   em 2ª pessoa.
10. **Pós-review (2026-07-18):** (a) **archivist fix** — `important_facts` como
    dict não perde mais memória (`field_validator`; +5 `test_archivist_facts`;
    smoke real 3 turnos ok); (b) **NPC relocável** — re-introdução em outro local
    relocaliza o `home_location_id` (viajar junto/mandado em missão); seguro pois
    R1 já bloqueia reuso passivo; (c) **sistema de classes Etapa 1/8 `done`** —
    recurso Entropia (+5 `test_classes_refactor`).
11. **Suíte:** 862 → **881 offline verdes** + 1 skip.

**🏁 AS 8 SPECS DO PLAYTEST LONGO ESTÃO `done`** + archivist fix + NPC relocável.

**Próximo — ÉPICO DO SISTEMA DE CLASSES (retomar em sessão limpa):** leia
**[docs/HANDOFF-sistema-classes.md](docs/HANDOFF-sistema-classes.md)** — Etapa
1/8 done; Etapa 2 pronta em `scripts/gen_classes_v2.py` (aplicar derruba 41
testes em 10 arquivos, inventariados no handoff); faltam etapas 2-8. Depois:
[arvores-habilidade-classes](specs/arvores-habilidade-classes.md) (árvore rica,
autoria em Fable).

---

**Sessão 2026-07-17 (17): CRIAÇÃO DE PERSONAGEM IMERSIVA ENTREGUE** —
1. **[onboarding-valoria](specs/onboarding-valoria.md) `done`:** criação virou
   wizard de 5 passos com lore curado — `data/onboarding.json` (intro de
   Valoria + 12 regiões + 10 classes + 6 raças; cards de região com
   `name`/`bonus` espelhados de `origins.json`, teste anti-drift),
   `GET /data/onboarding`, `CreateScreen.tsx` reescrito (cards clicáveis,
   stepper com navegação livre, fallback pro form clássico se o endpoint
   faltar). Smoke de UI: **15/15 checks** via Playwright (estado preservado ao
   voltar, "Pular introdução", mobile 390px sem overflow). Autoria dos cards:
   `docs/AUTORIA.md` § Fluxo D.
2. **[inicio-personalizado](specs/inicio-personalizado.md) `done`:**
   `POST /game/prologue` (1 chamada SMART + guard → template determinístico,
   nunca 500; entra no rate-limit) gera prólogo confirmável;
   `/game/new` com `scenario` (re-validado na borda — 422 p/ excedente) semeia
   `campaign_plan` pessoal que sobrevive ao 1º invoke, capítulo 1 da crônica
   com o arco pessoal, NPCs `in_scene`/`known_by_player` (alvo válido da rota
   NPC no turno 1) e a `HumanMessage` de abertura com o brief da cena. Passo 6
   do wizard: loading temático + **Refinar** + **Começar a jornada**. Sem
   scenario = fluxo clássico byte a byte (CLI intacta).
3. **Achado do smoke real (padrão p/ TODO schema novo de structured output):**
   `max_length` duro no schema voltado ao LLM derruba TODOS os candidatos por
   validação — DeepSeek escreveu `climax` > 300, Anthropic `attitude` livre
   ("ambígua e transacional"), Groq 400 `tool_use_failed` — e o guard caía
   sempre no template. Fix: schema do LLM com tamanho só na *description*;
   truncagem/normalização determinística em `_normalize`; limites ESTRITOS só
   na borda da API (`StartScenarioIn`). **MockLLM não pega isso** (fixture
   sempre válida) — validar schema novo com chave real segue obrigatório.
4. **Suíte:** 769 → **792 offline verdes** (+10 `test_onboarding`, +13
   `test_prologue`; 1 skip pré-existente). `npm run build` verde. Smoke real
   §6 no DeepSeek executado (~$0.02): arco "O Nome Manchado" com 2 NPCs,
   abertura NA cena do brief, NPC semeado responde no turno 1.

**Sessão 2026-07-14→16 (16): DEEPSEEK PRIMÁRIO + PLAYTEST LONGO + 8 SPECS** —
1. **Roteamento:** DeepSeek agora é o candidato Nº 1 em **TODOS os tiers**
   (`llm_setup.ROUTES`; decisão do usuário pós-playtest — prosa muito melhor,
   ~$0.001/turno). Groq free segue de fallback vivo em todos.
2. **Playtest longo REAL** (explorador/combate/quester × 100 turnos, ~$0.25,
   zero erro de turno): análise completa em
   **[docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md)**.
   Destaque: quester 7/7 quests, level 5, arco da Thrace excelente — mas 1
   local em 100 turnos. 7 defeitos priorizados (harness sem stop no game_over,
   espiral pós-Saque, combate zumbi 59 turnos, segredo vazando via beat,
   "Ninguém responde." com aliado em cena, beat em inglês, NPC reciclado).
3. **Todos os achados viraram specs `draft` (aguardando aprovação):**
   [playtest-stop-gameover](specs/playtest-stop-gameover.md) ·
   [combate-lifecycle](specs/combate-lifecycle.md) ·
   [pos-saque-recuperacao](specs/pos-saque-recuperacao.md) ·
   [npc-fallback-sem-alvo](specs/npc-fallback-sem-alvo.md) ·
   [beats-visibilidade-ptbr](specs/beats-visibilidade-ptbr.md) ·
   [encontros-dedupe](specs/encontros-dedupe.md) ·
   [polish-prosa](specs/polish-prosa.md) ·
   [embeddings-provider](specs/embeddings-provider.md).
4. **Embeddings:** Google 429 "prepayment credits depleted" desde 2026-07-14 —
   RAG global + memória de sessão MORTOS. Pesquisa feita (DeepSeek NÃO tem
   embeddings): recomendação = **Jina v3** ($0.02/M + 10M tokens grátis,
   PT-BR forte) com opção local Ollama `bge-m3` — spec embeddings-provider.

5. **Criação de personagem imersiva (2026-07-16): 2 specs `approved`** —
   viraram `done` na sessão 17 (ver TL;DR acima).

**Histórico recente** (detalhe SÓ no `CHANGELOG.md`):
- 2026-07-13 (15): ciclo de produto EXECUTADO — balanceamento-early-game
  ("O Saque" + tuning nível 1 + replan por região) · streaming-turno-sse ·
  polish-sessao, todas `done`; 729 → 769 offline verdes
- 2026-07-13 (14): sync de docs + auditoria A1–A8 corrigida (729 verdes) +
  3 specs do ciclo refinadas com o usuário e `approved`
- 2026-07-13 (13): fix-playtest-achados `done` — 6 defeitos do transcrito real +
  fuga do jogador implementada; 715 verdes; perfis 11º/12º (`quester`/`fujao`)
- 2026-07-06/07 (12): **Fase 5 inteira** (harness 12 perfis + invariantes +
  telemetria); suíte `-m llm_playtest` (4 VITAIS × 30t); bugs reais: rota NONE,
  vazamento do Verme (curado), teto de sobrevivência no budget
- 2026-07-06 (11): **roteamento multi-provider** — `RoutedLLM`/`ROUTES`, Groq
  grátis em TODOS os tiers (`function_calling`), telemetria por invoke
- 2026-07-06 (10): Fase 10 local (UUID/migrations/CORS/rate-limit/log) + Fase 11
  (9 contratos LLM reais) + mapa interiores + NPCs 3 camadas
- 2026-07-05 (9/8): Fase 7 (autoria+validação) · Fase 6 (conteúdo sistêmico)
- 2026-07-04/05 (7): Fase 4 (gameplay core, 7 specs)

**⚠️ Saves pré-2.5b:** carregam sem crash (migrations), mas locais/fações antigos
não existem mais no mapa — sessões antigas ficam narrativamente órfãs. Arquivar.

---

## Como rodar (ambiente deste Windows)

`python` global é 3.14 (WindowsApps) — **errado** (projeto exige 3.13). Use sempre `uv`.

`uv` **não está no PATH** — fica em `%APPDATA%\Python\Python314\Scripts`. Em PowerShell:

```powershell
$env:Path = "$env:APPDATA\Python\Python314\Scripts;$env:Path"
uv sync                              # cria .venv com Python 3.13
copy .env.example .env               # cole GOOGLE_API_KEY no .env (NUNCA na .env.example)
uv run pytest                        # 1398 passed, 1 skipped, 14 deselected (LLM real opt-in)
uv run pytest -m llm_contract -v -s  # 9 contratos contra o Gemini REAL (~13 req; requer chave)
uv run pytest -m llm_playtest -v -s  # Fase 5: 4 perfis VITAIS × 30 turnos no LLM REAL (RPG_PLAYTEST_TURNS encurta)
uv run python game_engine.py         # CLI
uv run uvicorn api:app --port 8000   # API + frontend web (http://localhost:8000)
uv run python -m playtest run --all --turns 50   # Fase 5: harness offline (MockLLM, 13 perfis)
uv run python -m playtest report <run_id>        # Fase 5: relatório agregado
uv run python -m playtest transcript <run_id>    # transcrito ação→narração (julgar prompt)
uv run python rag.py                 # reindexar lore (data/codex/) + regras (data/rules.txt)
uv run python scripts/migrate_lore_nova.py  # regerar Codex de lore_nova/ (SOBRESCREVE curadoria)
bash scripts/smoke_api.sh [porta]    # smoke da API (health, map, /game/new, /game/action)
```

**Frontend:** `cd web && npm install && npm run build` → gera `web/dist` (servido na
raiz). Dev: `npm run dev` (:5173 com proxy para :8000).

**LLM providers:** default = `ROUTES` multi-provider com fallback —
**DeepSeek `deepseek-v4-flash` é o primário em TODOS os tiers**. O alias
`deepseek-chat` foi substituído após HTTP 400 no smoke de 2026-07-24; V4 roda
com thinking desabilitado e timeout OpenAI-compat configurável por
`LLM_TIMEOUT_SECONDS` (default 90s). No run 13×30: ~$0,00080/turno estimado;
Groq free é o fallback vivo. `LLM_PROVIDER=gemini` força
só-Gemini; sem chave nenhuma → MockLLM (jogável sem rede). Contas: minimax 402,
qwen 401 — OPCIONAL resolver (assumem quando tiverem saldo/key; não é bug).
Ver `.env.example`.

**Quota:** Gemini free = 20 req/dia por modelo; Groq free = 100k tokens/dia (esgota
numa sessão real longa — espalhar por dias ou tier pago). `get_llm()` é fail-fast
(`max_retries=0`). **MockLLM esconde bugs de mapeamento** — validar nós novos com
chave real.

---

## O que funciona

- Criação de personagem (CLI + `/game/new`) — resiliente sem chave
- Loop completo: `campaign_manager → dm_router → (storyteller|combat|npc|loot) → archivist → save`
- **Combate:** IA identifica/narra; Python resolve tudo (`combat_mechanics.py`) —
  iniciativa, DoT/condições, custos, cooldowns, saves + perfis de comportamento (2.5b)
  + fuga do jogador real (fix-playtest)
- **Mundo:** mapa de Valoria 35 nós (30 + 5 interiores), relógio, viagem (fog of war),
  descanso, gating por classe; raças com traits mecânicos (2.5b); clima mecânico (6.5)
- **Fase 2/2.5:** fações com objetivos/reputação/ascensão, memória de NPC, Codex
  Valoria + grafo (558 entidades) + `event_log`/`world_projection` + RAG com
  visibilidade (`secret`/`hidden` não vaza)
- **Fase 3 (completa):** crônica por capítulos, codex do jogador + bestiário
  progressivo, quest log, visualização de estado (controladores/ameaças/reputação)
- **Fase 4 (completa):** progressão/XP/level-up (111 habilidades, 20 ramos), buffs
  mecânicos, inventário `{id,qty}`+slots, economia determinística, party,
  dificuldade/morte digna (memorial 409)
- **Fase 6 (completa):** economia viva (rotas/escassez), 20 itens únicos (claim
  engine), migração de monstros, encontros sistêmicos, clima com efeito
- **Fase 7 (completa):** lint de conteúdo + CI, curadoria migration-safe
  (`codex_overrides.yaml`), segredos de NPC em docs `hidden`
- **Fase 5 (completa):** playtest agêntico (`playtest/`, 13 perfis), invariantes
  por turno, telemetria JSONL + relatório com custo, `--real` com tetos,
  `transcript` por turno
- **Fase 10 local + Fase 11:** UUID/migrations/CORS/rate-limit/log JSON; 9 contratos
  LLM reais (`-m llm_contract`)
- **Roteamento multi-provider:** 3 tiers, fallback vivo, Groq grátis em todos;
  NPCs 3 camadas com traits
- **Ciclo de produto (sessão 15):** "O Saque" (1ª queda ≠ memorial) + tuning de
  spawn nível 1 + replan por região; streaming SSE do turno (fases + chunks +
  fallback) com custo real no log; tela de saves (listar/continuar/excluir),
  chips mecânicos de combate, export/busca da crônica, onboarding, mobile 390px
- **Criação imersiva (sessão 17):** wizard 5 passos com lore curado de Valoria
  (`data/onboarding.json` + `GET /data/onboarding`) + prólogo confirmável
  (`POST /game/prologue`) que semeia arco pessoal, NPCs da história e cena de
  abertura no `/game/new` — fluxo sem scenario/CLI intactos
- Multi-provider LLM + typewriter no frontend React; memória híbrida (resumo + RAG
  por sessão); persistência JSON por `game_id`

---

## Convenção CRÍTICA de resiliência

`FallbackLLM.with_structured_output(X).invoke()` devolve `AIMessage`, **não** instância
de `X`. Acessar `resultado.campo` **estoura** sem guard.

**Regra obrigatória em todo nó com `with_structured_output`:**
1. `try/except` no acesso aos campos, **ou**
2. `isinstance(resultado, SeuModelo)` antes de usar.

Auditoria 2026-07-13: **12/12 sites de produção blindados** (verificado).

---

## Bugs conhecidos

Bugs históricos: TODOS fechados (4 da sessão 2026-06-26 → Fases 4.3/4.6 e spec
npcs-3-camadas; 6 do transcrito real → fix-playtest-achados; 8 da auditoria de
segurança → sessão 14, tabela completa no `CHANGELOG.md`).

**Corrigido (2026-07-18):** o archivist recebia `MemoryUpdate.important_facts`
como lista de **dicts** (`{fato,type}`/`{role,content}`) e caía no fallback de
texto, PERDENDO os fatos do turno. Fix: `field_validator(mode="before")` coage
dict→string antes da validação (`+5 test_archivist_facts`). Smoke real: 3 turnos,
fatos salvos limpos, zero erro.

**Refino (2026-07-18) — NPC preso ao local (spec encontros-dedupe):** o vínculo
NÃO engaiola o NPC quando faz sentido sair — viajar junto (recrutar→party) ou
ser re-introduzido em outro local pela narrativa/player (relocaliza o
`home_location_id`). Seguro porque o R1 já bloqueia o reuso PASSIVO.

**Pendências abertas (não são bugs de código):**

- Tiers 5+ das classes (nível 9–20) — fast-follow do épico.
- Playtest longo do perfil `comerciante`; o smoke dirigido validou uma compra,
  mas ainda não mediu economia emergente em campanha longa.
- Fases 8/9 (arte e audiovisual), crônica avançada e Fase 10b (Postgres/auth/
  isolamento por usuário/locks distribuídos). O tuning dos oito knobs e a
  letalidade v2 já estão `done`; referências antigas a `approved` são histórico.
- 1 flaky isolado na suíte (sessão 8; 3 runs verdes depois — observar)
- ~~Action `validate.yml`~~ ✅ verde (confirmado via `gh run list`).
- ~~Lote 2 de traits~~ ✅ 80 traits (sessão 20).
- ~~Curadoria Rede Carmesim~~ ✅ resolvida (sessão 20): over-share em
  `factions.txt` suavizado + reindex; nome=público, iminência=`hidden`.
- ~~Cache runtime gravado em `data/`~~ ✅ isolado em `data/runtime/` (sessão 20,
  spec isolar-cache-runtime).
- **Achados do playtest longo (sessão 16)** — 7 defeitos/melhorias priorizados
  em [docs/playtest-longrun-2026-07-14.md](docs/playtest-longrun-2026-07-14.md):
  harness sem stop no game_over · espiral pós-Saque · combate zumbi (59 turnos
  ativo) / viagem durante combate · vazamento de segredo via beat do
  campaign_manager · "Ninguém responde." com aliado em cena · beat em inglês ·
  encontro reciclado. **Todos viraram specs `draft` em 2026-07-16** (ver TL;DR).
- **Embeddings:** ✅ RESOLVIDO (spec embeddings-provider `done`). Jina é o
  primário; índices lore/regras re-indexados com meta jina, RAG vivo. Free tier
  Jina = 100k tokens/min (re-index do Codex esgota o minuto — espaçar). Trocar
  provider = re-rodar `uv run python rag.py`.

Fechadas na sessão 15: confirmação real do Verme ✔ · mortes nível 1 do
`combate`/`agressivo` ✔ (spec balanceamento; nota: 2ª queda DELIBERADA sem cura
segue matando — por design) · replan em toda viagem ✔ · **spec 2.5b virou
`done`** (2026-07-14: smoke real §6 3/3 — raça Cinzéu com traits, viagem com
lore de Skallgard, tático foge com HP baixo + alerta; era a última spec não-done).

## Limitações conhecidas

- **Concorrência:** serializada por `game_id` dentro de um processo; múltiplos
  workers/hosts ainda exigem transação/lock distribuído na Fase 10b.
- **Sem autenticação/isolamento por usuário** — manter bind local; Postgres+auth = Fase 10b.
- **Runtime legado local:** `saves/` ainda contém fixtures históricas misturadas a
  campanhas reais; a suíte não cria novas desde a sessão 35, mas limpeza requer
  seleção humana ou ferramenta de migração com preview.
- **Saves antigos** carregam via `schema_version` + `_MIGRATIONS` (v0→v2);
  pré-2.5b ficam narrativamente órfãos — arquivar
- **Free tier não sustenta playtest real longo** — Groq 100k tokens/dia; espalhar
  por dias ou tier pago
- **Latência real:** p50 ≈ 15s, p95 33-46s por turno — o custo do LLM continua,
  mas o streaming SSE (spec `done`) mostra fase em <1s e narra em chunks; a
  espera cega acabou

---

## Checklist ao começar a próxima tarefa

0. Feature/fase nova? **Spec primeiro** — `specs/` (CLAUDE.md § spec-driven)
1. `/qa` verde antes de mexer
2. Nó novo com `with_structured_output`? Guard de fallback (seção CRÍTICA)
3. Mudou schema do player/estado? Atualizar `state.py` + `game_engine.py` + `api.py` + creator
4. Novo agente no grafo? Conectar ao `archivist` no fim (REFERENCE.md)
5. Editou `lore_nova/`, `data/codex/` ou `data/rules.txt`? Rodar `uv run python rag.py`
6. Mecânica nova (números)? Python determinístico, não LLM
7. **Ao finalizar:** `/wrap-up` — suíte completa verde + ESTADO_ATUAL.md + ROADMAP.md + commit
