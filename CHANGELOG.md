# CHANGELOG — histórico de sessões

> Histórico detalhado das sessões de desenvolvimento. NÃO é carregado automaticamente
> no contexto — consultar sob demanda. Estado atual: `ESTADO_ATUAL.md`.

---

## 2026-10-20/23 — iniciativa mundo vivo (auditoria + entrevista + onda 0)

- **20/10 — auditoria + entrevista do dono:** 5 exploradores (combate, NPCs, simulação, narração, lore/playtest); visão e ~40 decisões em [docs/mundo-vivo/VISAO.md](docs/mundo-vivo/VISAO.md). Specs reservadas 296–305 (296 onda 0; 297 pool entre mundos; 298 reputação 4 níveis; 299 lei/crime; 300 companheiros; 301 patentes; 302 motor de mundo; 303 calendário; 304 NPCs off-screen; 305 quests de mundo). Todas `approved` em 23/10 (decisões no fim de cada spec).
- **23/10 — SPEC-236 `done`:** §6.2 dia 2 verde no staging (override manual não vaza entre dias; trip `system:finops` 23/10 com `manual_override` vazio). Dia 2 refeito em 23/10 (deploy bloqueado por permissão em 20/10).
- **23/10 — SPEC-296 `done`:** alerta de fuga → reforços (1/encontro; não em fuga do herói/derrota/rendição), bloco `<AMBIENTE>` único (período, clima local/global, luz, perigo em palavras, abrigo, saídas) no narrador/NPC/combate, `world.news` + `<OUVIU_DIZER>` + "Ouvi dizer" na Crônica. Staging `RPG_NPC_KNOWLEDGE=on` (`vercel_env.py --npc-knowledge`). Combate 200 Mock: letalidade 0,44, 0 `no_progress`.
- **23/10 — SPEC-298 `done`:** `services/reputation.py` único escritor (relação de NPC, reputação de fação via `faction_deed` validado e testemunhado, fama por local só por testemunha/SPEC-215, raça/origem em `data/race_attitudes.json`), keeper de mercador (preço/estoque por relação), intimidar/sondar/favores; UI só rótulos. Revisão Sol 2 rodadas.
- **23/10 — SPEC-302 `done`:** motor de mundo diário determinístico (pressões guerra/fome/praga/Abismo por região, diretor com aviso ≥2 dias e teto de crises, estados de local, relações fação-fação, percepção pela regra de ouro, 1 narração LLM/dia). Calibração 60 seeds em `docs/spec302/`. Staging `on`.
- **23/10 — SPEC-297 na main (`in-progress`):** pool compartilhado entre mundos atrás de `RPG_SHARED_POOL` (hold 24 h, validadores, dedupe, avaliação LLM fail-closed, RLS + SECURITY DEFINER p/ PII do dono). Revisão Sol 3 rodadas; Postgres local validado; migração aplicada no staging; `shadow`.
- **23/10 — main/CI:** pillow 13.0.0 + certifi 2026.10.23 (pip-audit); project index regenerado com LF (CRLF de scripts Python no Windows divergia do CI — usar `newline=""`).

## 2026-10-19 — onda: workspace, logs P2/P3, frontend majors, staging (222/236/279/280)

- **19/10 — SPEC-294 `done`:** oráculo de fação oculta casa por palavra inteira (acento/espaço/hífen/plural; "Azulado" não acusa; símbolo colado como `™` agora acusa — NFD); inimigo de save legado sem `id` ganha id opaco `enemy_legacy_<n>` no load, refs do combate migram junto; 5 casos novos de eval `player_knowledge` com mutação do oráculo (lock regenerado, aprovado no `eval-governance`). Laboratório de combate mantém o bestiário canônico (decisão do coordenador). Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-294-review.md)).

- **19/10 — SPEC-293 `done`:** quem ainda não conhece a fação vê o combatente só pelo papel ("Iniciado"; "Combatente desconhecido" quando o nome é a própria fação) em HUD, POST/SSE/state, manifesto público, desfecho, log, histórico, crônica, Codex e dossiês. Rótulo calculado na leitura (`services/faction_display.py`); canônico segue no save/ids; após a revelação o nome completo aparece em tudo. Oráculo `assert_no_player_leak` ganhou a checagem (e). Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-293-review.md)).

- **19/10 — SPEC-292 `done`:** pressão de caça da 6.3 mistura o pool regional do mesmo porte quando a criatura temática rareia (determinístico; população intacta = SPEC-289); encontro ganha `public_hint`/`concealed_faction` e o narrador de combate chama combatente de fação desconhecida só pelo papel ("Iniciado"), validado com DeepSeek e Groq reais. Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-292-review.md)). Follow-up P1 (pré-existente): HUD/manifesto público/log/Bestiário ainda mostram o nome com o radical da fação → spec de rótulo de exibição por observador.

- **19/10 — SPEC-291 `done`:** falhas esporádicas do divisor do split no CI (F17 e `workspace-shell`, valor travado em 50) eram leitura sem espera após o arrasto com CPU carregada; os dois testes usam `expect.poll` (sem sleep, app intacto). 10× cada no chromium, 0 falhas.

- **19/10 — SPEC-289 `done`:** a criatura do encontro `looming_threat` acompanha o tema da ameaça, sem LLM: a ascensão grava a fação (save antigo resolve pelo texto); dentro da região da ameaça sai criatura ligada a ela (combatente da fação ou mesmo radical do nome), porte estrito, nunca Chefe; fora, mesma criatura e flavor "eco distante". Ex.: Corvane nas Ruínas Submersas → Faísca da Destilação / Afogado de Aethelgard. Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-289-review.md)).

- **19/10 — SPEC-290 `done`:** o bônus de sobrevivência de Chefe/Nomeado por Nível do Encontro (SPEC-287) vale também para Chefes gerados pelo LLM (default canônico 12 em Python pela `categoria` fechada; bestiário runtime guarda a base, não acumula) e para o laboratório de combate (cópia, bestiário global intacto). Ex.: `mon_urso_tita` 16 → 40 no laboratório. Revisão Opus APPROVED ([parecer](handoffs/SPEC-290-review.md)).

- **19/10 — SPEC-287 `done`:** escala de encontro nível 5+ corrigida na causa: piso do orçamento conta corpos de forma superlinear (`floor_cost`, economia de ações) e Chefe/Nomeado ganham +12 de Vitalidade por Nível do Encontro acima de 2 (gerador oficial, teto de 2 passos). Arena níveis 5–8: horda de Lacaio 0,52–0,61 → 0,32–0,36; Lacaio < Padrão < Elite e Lacaio < Chefe; níveis 1–4 idênticos. Playtest morte/combate 0,541 → 0,497, 0 `no_progress`. Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-287-review.md)). Chefe segue abaixo de Padrão/Elite (já era assim no 1–4; "Chefe no topo" = mudança de design, fica como pergunta ao dono).

- **19/10 — SPEC-288 `done`:** causa-raiz no produto: o encontro `looming_threat` criava inimigo com o texto do gancho como nome; agora resolve criatura do bestiário da região (`pick_encounter_enemy`, fonte `systemic` do manifesto), o texto da ameaça segue como flavor da narração. `player_downed` ganha `killer` (espécie) e `killer_id`; crônica e playtest registram a espécie (armadilha → "armadilha"). Seed 21: 0 causas-gancho (antes 4/11). Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-288-review.md)); follow-up: criatura ligada ao tema da ameaça.

- **19/10 — SPEC-285 `done`:** letalidade pós-232/275/283 com meta ancorada na 283/056: proteção do jogador num aliado ganha +1 turno como a do inimigo; controle tático genérico nega 1 turno (não 2 — prendia o alvo); Toque Gélido 5→3 pelo gerador + guarda "carta inimiga não mata sozinha herói cheio de 18". Playtest morte/combate 0,588 → 0,532, 1ª queda mediana 28,5 → 35, matriz SPEC-056 22 → 24, 0 `no_progress`. Revisão Opus APPROVED com 1 P1 corrigido ([parecer](handoffs/SPEC-285-review.md)). Follow-ups: escala de encontro nível 5+ (SPEC-287), causa da morte (SPEC-288).

- **19/10 — SPEC-286 `done`:** o perfil de playtest `combate` não viaja mais com o herói inconsciente (declara descanso, que o action_guard aceita — o jogo já tinha saída válida); recusa do guard grava `route="action_guard"` + `guard_code` no JSONL, sem marcar contrato inválido. `combate --turns 200` seeds 21/23/24: exit 0, 0 turnos perdidos (antes 23/24 saíam exit 1).

- **19/10 — SPEC-284 `done`:** `typecheck:e2e` e ESLint do `web/` zerados (4 + 93) com correção real de a11y/hooks; os dois passos agora bloqueiam o CI; teste Playwright de dedupe do beacon (1 POST por erro forçado); prints de evidência da SPEC-209 só com `RPG_SPEC209_SHOTS`. Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-284-review.md)).

- **19/10 — SPEC-283 `done`:** IA inimiga usa as 8 Cartas de suporte ativas do bestiário (proteção/buffs/reposicionar) em si ou num aliado do lado inimigo; determinística, alvo validado, custo/frequência cobrados; nunca mira o jogador; pulada sob silêncio/Provocação/quebra de impasse; suporte no próprio lado não abre Reação. `combate --turns 200` 9 seeds: 0 `no_progress`. Letalidade playtest 0,564 → 0,598, arena 0,707 → 0,730. Revisão Opus CHANGES_REQUIRED → corrigida ([parecer](handoffs/SPEC-283-review.md)). Achado: herói inconsciente prende o perfil `combate` (JSONL `route ''`).

- **19/10 — Ruff degraus 2–3:** `I` e `UP` (py313, só fixes seguros; 173 restantes no baseline gerado) + `ruff format` no repo (~720 arquivos) e `ruff format --check` no CI/pre-commit. Fora do format e de I/UP: régua de eval, `evals/experiments` (digests congelados das SPEC-217/238 hasheiam o código-fonte), `data/`, `lore_nova/`, `faiss_*`; `merchants_at` com `fmt: off`; `# silent-ok` mantidos na linha anterior ao `except`.

- **19/10 — SPEC-259 `done` + staging `65c0f23`:** a versão do app Android agora chega no access log (`app_version=1.0.0+1`, `client=android`): a leitura do plugin `App` tenta de novo por até 3 s sem bloquear o boot. Smoke no AVD `rpg34` verde. Staging redeployado em `65c0f23` (Jev `primary`, teto R$ 5; post_deploy/vercel_smoke/e2e verdes); 1ª chamada Jev pós-deploy 285 ms, sem timeout (SPEC-281).

- **19/10 — SPEC-282 `done`:** o "timeout do axe" no M07 mobile não era a11y nem app: cada jornada leva 4–12 s sozinha e estourava o teto default de 30 s com a CPU disputada. Teto de 90 s no arquivo `mobile-single-pane` (asserções serious/critical intactas); 14/14 em 3 repetições. Achado: nesta máquina o Playwright completo leva ~8 min e timeouts de 30 s aparecem em outras specs sob carga; no CI passa.

- **19/10 — SPEC-225 `done`:** CI verde com secret-scan/pip-audit/npm audit, Dependabot ativo, 4 environments só `main` + reviewer (`post-deploy-smoke` ganhou reviewer); 1º scan semanal do gitleaks tinha 3 falsos positivos (caminhos renomeados) → `.gitleaksignore`, 568 commits limpos. Critério da compra de license tester movido para a SPEC-198. **SPEC-259 reaberta:** no AVD `rpg34` R1–R3 ok, mas o app nunca envia `X-RPG-App-Version` (plugin do Capacitor registra ~200 ms depois da leitura).

- **19/10 — SPEC-281 `done`:** o client HTTP do Jev é construído antes do prazo de 1 s (1º turno de instância fria não dá mais timeout falso); falha ao construir o client ou ao importar a política congelada cai no CLASSIFY em vez de derrubar o turno; `off` intacto. Revisão Opus APPROVED com 1 P1 corrigido ([parecer](handoffs/SPEC-281-review.md)). Vale no staging no próximo deploy.

- **19/10 — Workspace, 2ª passada:** CI em Node 22 (`web/.nvmrc`) e runners fixos `ubuntu-24.04`; porta do Playwright por checkout (`RPG_E2E_PORT`), dois worktrees rodam e2e juntos; push só de docs pula a suíte pesada (job `docs-only`; `eval-gates` intacto); Dependabot agrupa minor/patch; lint de nome de handoff; `proximas-specs/` → `docs/historico/proximas-specs/`. Achado: M07 mobile (timeout do axe) já falhava na main.

- **19/10 — SPEC-277 `done`:** CLI de evals mostra no stderr suite, `case_id` e traceback (≤ 40 linhas, só frames + classe, **sem a mensagem**, para não vazar caso do holdout no log do Actions); JSON ganha `errors:[{case_id,error_type}]`. Relock só dos 2 hashes; revisão Opus APPROVED com 1 correção ([parecer](handoffs/SPEC-277-review.md)). Flake do teste Jev sem chave sob xdist corrigido.

- **19/10 — SPEC-279 e SPEC-280 `done` (aplicadas no staging, 31/31):** apagar campanha não apaga mais o gasto (`usage_events.game_id` → NULL, `operation_id` opaco, `operation_kind` por trigger, reuso de id de operação apagada recusado). Apagar usuário no Auth apaga os jogos dele por trigger (sem FK: perfis OIDC e donos sintéticos), pulando exclusão de conta registrada (SPEC-190). `scripts/admin_orphan_games.py` (dry-run → `--apply --expect N`) limpou os 13 órfãos do staging com gasto e 9 tabelas financeiras idênticos. Revisões Opus com P1 corrigidos → APPROVED ([279](handoffs/SPEC-279-review.md), [280](handoffs/SPEC-280-review.md)).

- **19/10 — SPEC-278 `done`:** React/react-dom 19.3.1 (+ tipos); bundle +12,7 % bruto / +12,5 % gzip, aceito pelo dono (teto de 5 % da 276 não vale para o React). Nenhuma API removida em uso; build, typecheck, 147 Node, audit 0, Playwright Chromium verdes; flake de timing de `account-lifecycle` corrigido (baseline do poll após a tela de conta sair). Revisão Opus APPROVED ([parecer](handoffs/SPEC-278-review.md)). Dependabot #40/#41 obsoletos.

- **19/10 — Logs P2/P3 no staging:** migration `cron_run_state` aplicada (29/29, upsert do cron via `rpg_admin` ok); deploy `da6186b` com Jev `primary`, teto R$ 5; post_deploy/vercel_smoke/e2e verdes; eventos confirmados: `cron.*` com `run_id`, `client_build`/`build_skew`, `client.error` (Origin cruzada 403), `http.body_too_large`, `abuse.blocked`, `combat.summary`, `economy.trade`. Deploy pela CLI exige `-b GIT_SHA` (skill corrigida).
- **19/10 — SPEC-276 `done` parcial:** Playwright 1.64 + Vite 8 (bundle +2,5 % bruto / −0,5 % gzip), `npm audit` 0 e `npm-audit-full` bloqueante; fixture e2e aceita o beacon `client-error` (3 jornadas voltaram). TypeScript 7 bloqueado (typescript-eslint exige TS < 6.1) e React 19 bloqueado pelo teto de bundle (+15,7 %) — decisão do dono. Revisão Opus APPROVED_WITH_FOLLOWUPS ([parecer](handoffs/SPEC-276-review.md)). Dependabot #35/#37 obsoletos.

- **19/10 — Logging P2/P3 `done`** (SPEC-244/246/251/252/253/256/258/259/260/261): beacon de erro do cliente (`client.error`, endpoint público fechado, 4 KiB, rate limit `telemetry`, ids normalizados, amostrado) + ErrorBoundary; build id ponta a ponta (`X-RPG-Build`, `build_skew`); 429/413 com rótulo fechado; trace mecânico do combate (`combat.summary`, `audit_trace.mechanics`); `reason_code` fechado em rejeições; cron com `run_id` + `app.cron_run_state`; `provider.attempt` STT/imagem/Jina; billing Android com códigos. Revisão Opus CHANGES_REQUIRED → 10+1 correções → APPROVED ([parecer](handoffs/LOGS-P2P3-review.md)). Pendente: migration `20261019100000_cron_run_state.sql` + deploy + smoke no staging; AVD da 259; SPEC-277 (R2 da 260, relock de evals) `draft`.

- **19/10 — Workspace `done`:** melhorias de `docs/melhorias_workspace/` (10 recs + bônus): ESTADO ≤ 8 KB e ROADMAP só plano (histórico em `docs/historico/`), cabeçalho da spec como fonte única (`scripts/spec_index.py`), Project Index só de arquivos rastreados, skills/agents versionados, LF/UTF-8, pytest-xdist + timeout, Ruff incremental com baseline, `AGENTS.md` fonte única. Pendente do dono: variável `EVALUATOR_CHANGE_APPROVED` no environment `eval-governance`.
- **19/10 — Staging:** SPEC-222 R6 verde (retrato real OpenAI US$ 0,011; `DELETE /game/save` apagou os 2 objetos do bucket no cron seguinte). 222 pendente só de compra fake (sem chave Stripe test) e domínio de produção. SPEC-236 §6.2 dia 1: trip real do teto diário em `2026-10-19T12:12:37Z`; staging restaurado (teto R$ 5, Jev `primary`, `e2e_session` verde). Dia 2 a partir de 20/10 00:00 BRT pelo [roteiro](docs/staging-wave-2026-10-17/spec236-s62-plano.md). Achados: `usage_events` cai em cascata ao apagar a campanha (some do teto/FinOps, contra a retenção da 222); `app.games` sem FK para `auth.users` (13 órfãos no staging).

---

## 2026-07-14→16 (16) — DeepSeek primário em tudo + playtest longo 3×100t + 8 specs `draft`

**Roteamento:** DeepSeek promovido a candidato Nº 1 em TODOS os tiers
(`llm_setup.ROUTES`) em dois passos: 2026-07-14 (principal no SMART — já era —
+ 1º fallback do FAST) e 2026-07-16 (primário também em CLASSIFY e FAST, decisão
do usuário). Groq free segue fallback vivo; sanity real: 3 tiers respondendo
via `deepseek-chat` sem fallback. CLAUDE.md (tabela de tiers) atualizado.

**Playtest longo REAL** — 3 perfis × 100 turnos (runs `20260714-044513`
explorador, `20260714-050009` combate, `20260714-050339` quester; ~$0.25 total,
zero erro de turno, CLASSIFY com override `RPG_ROUTES` runtime p/ não estourar
o free do Groq). Análise completa: `docs/playtests/playtest-longrun-2026-07-14.md`.
- **Bom:** prosa DeepSeek muito acima dos free anteriores; arco da Thrace
  (quester t51–58) com fracasso de quest tratado narrativamente; 7/7 quests,
  level 5; "O Saque" disparou como projetado; custo ~$0.001/turno vivo.
- **Defeitos:** (A) harness não para no game_over — 140/300 turnos repetindo
  memorial; (B) espiral pós-Saque: 2ª queda fatal em 2–4 turnos nos 2 perfis
  que caíram; (C) combate zumbi — `combat.active` 59 turnos no quester,
  explorador viajou 2× durante combate; (D) beat do campaign_manager vazou
  segredo (pacto Valerius+Daruun) — canal fora do `max_visibility`;
  (E) "Ninguém responde." 7+ turnos, até com Gorim (party) em cena; (F) beat
  em inglês; (G) NPC "Sobrevivente moribundo" reciclado 3× em 6 turnos;
  (I) telemetria de rota vazia em combate/pós-morte.
- **Faltas:** quester ficou 100 turnos num único local (quests não puxam pro
  mundo); exploração sem recompensa mecânica (23 locais → 0 quests, 0 ouro);
  economia invisível; aliados sem presença mecânica.

**Embeddings:** Google 429 "prepayment credits depleted" durante os runs — RAG
global + memória de sessão mortos. Pesquisa 2026-07-16: DeepSeek NÃO oferece
embeddings (doc oficial); recomendação **Jina v3** ($0.02/M, 10M tokens grátis,
89 línguas) > OpenAI 3-small ($0.02/M) > Ollama `bge-m3` local grátis.

**8 specs `draft` criadas** (todos os achados + embeddings):
playtest-stop-gameover (A+I) · combate-lifecycle (C) · pos-saque-recuperacao
(B) · npc-fallback-sem-alvo (E) · beats-visibilidade-ptbr (D+F) ·
encontros-dedupe (G) · polish-prosa (H) · embeddings-provider. Aguardando
aprovação do usuário; suíte 769 offline verde intacta (cache
`bestiary.json`/`npc_database.json` sujado pelos runs reais/suíte — restaurado
via `git checkout`, pendência de isolamento segue aberta).

## 2026-07-13 (15) — Ciclo de produto EXECUTADO: 3 specs `done` (729 → 769 verdes)

As 3 specs `approved` da sessão 14 foram implementadas de ponta a ponta na ordem
1 → 2 → 3 (registro de execução detalhado no §8 de cada spec):

**1. balanceamento-early-game `done`** — Etapa 1: métricas de balanço na
telemetria do harness (`first_death_turn`/`downed_count`/`avg_hp_pct_after_combat`/
`replan_count` + campos crus no JSONL + colunas e deltas no report); baseline
gravado ANTES do tuning: mock `20260713-160458` (combate morria t6, agressivo t7
nível 1; **replan em TODO turno** — MockLLM devolve location fora do mapa) e real
seed 7 (`combate` t5 por 2× Zumbi Blindado — burst de elites; `agressivo` t10;
`secret_rusher` 30t real **confirmou o fix do Verme**: 0 vazamentos). Etapa 2
(knobs data-driven): máx 1 elite no nível 1 (`clamp_encounter(player_level=1)`) +
piso de HP das classes frágeis (Arcanista 16→22, Sombra 20→25, Batedor 22→27,
Médico 24→28); cap `4+3×nível` PULADO (nas mortes medidas o budget já era
mínimo). Etapa 3 (**"O Saque"**): `death_outcome`/`apply_downed` em
combat_mechanics (1ª queda fora de apex/boss = downed: acorda 1 dia depois em
`last_safe_location`, HP 25%, ouro 0, inventário/slots zerados menos
`starting_equipment[0]` equipada; únicos → `unique_item_lost` holder="world" e
voltam ao pool via `is_unique_available`; relógio +1 dia + fações avançam +
clima re-rola; narração FAST com fallback determinístico; milestone na crônica);
evento `player_downed` no pipeline 2.6 com gate `source="combat"` e 1x por
campanha (validator + invariante 5.2 `downed.repeated`/`downed.in_apex`/
`downed.vs_boss`). Etapa 4: `_should_replan` só replaneja em viagem quando a
REGIÃO muda E (≥1 beat done OU arco sem beats); intervalo 10→15; local
irresolvível não conta. Rodada final `20260713-201438`: replans −450 (explorador
50→4, −92%), downed ≤1 em todos, hp% pós-combate 12–44% (dói), 0 erros/violações.
Nota: `agressivo` ainda morre nível 1 na **2ª** queda (combate deliberado sem
cura — "por conta e risco", fora de escopo por decisão da spec).
`test_morte_gera_evento_e_memorial` (4.6) atualizado: memorial agora exige
`player_downed` prévio.

**2. streaming-turno-sse `done`** — Etapa 1: caracterização do
`app.stream(stream_mode=["updates","values"])` (ordem dos nós; estado final ==
invoke). Etapa 2: miolo do turno extraído em `_run_turn` (compartilhado). Etapa
3: `POST /game/action/stream` — generator síncrono com o grafo numa thread +
`queue.Queue` (keepalive `: ping` a cada 10s), eventos accepted → phase/route →
narrative (chunks de 80 chars) → state; memorial = evento `error` com `code:
409`; rate limit/game_id/teto de input/sanitização A6 valem. Etapa 4: telemetria
de produção — hook `set_llm_telemetry_hook` global do api.py acumulando em
`ContextVar`; log `rpg.turn` ganhou `llm_calls/llm_providers/fell_back/
cost_usd_est` (dev-only; MockLLM = 0). Etapa 5: frontend — `sendActionStream`
(parser SSE manual sobre fetch+ReadableStream), textos curados por fase,
chunks alimentam `useTypewriter` (agora continua quando o texto cresce),
fallback automático e silencioso pro POST (remove entrada parcial órfã).
**Smoke real:** turno de 20.2s → `accepted` 0.09s, `phase` 0.11s, `route` 0.66s;
log real: 5 calls, groq×3/gemini×2, ~$0.0036. 9 testes novos (`test_streaming.py`).

**3. polish-sessao `done`** — `persistence.list_saves()` (tolerante a corrompido)
e `delete_save()` (remove `data/saves_memory/{id}` junto); endpoints `GET
/game/saves`, `DELETE /game/save/{id}` (400/404; no rate limit), `GET
/game/chronicle/export` (.txt attachment com separadores);
`combat_mechanics.combat_suggestions()` pura (habilidades fora de cooldown/com
recurso por tier desc, "Beber <poção>", "Fugir" se não enredado; máx 5) exposta
em `combat.suggestions`. Frontend: `SaveScreen.tsx` (lista/continua/exclui com
confirmação pelo nome; badge ⚰; memorial abre em leitura — overlay ganhou "Ler a
crônica" e input desabilitado), chips de combate no PlayScreen (click → onAction),
`OnboardingHint.tsx` (5 comandos + dica dos chips; localStorage por game_id),
busca local + download na aba Crônica, passe mobile @480px (1 coluna, actionbar
sticky c/ safe-area, HUD gaveta 100vw, sem overflow-x). **Smokes:** Playwright
14/14 (desktop + 390×844, overflow 0px) + real: parser mapeou o chip
"Estocada Renal" → `estocada_renal` (o mapeamento que o MockLLM esconde).
14 testes novos (`test_polish_sessao.py`).

**Observação operacional:** suíte/smokes gravam cache runtime em
`data/bestiary.json`/`npc_database.json` (entradas mock, HP regredido) —
revertido via `git checkout` antes do commit; anotado como pendência.

---

## 2026-07-13 (14) — Auditoria de segurança (A1–A8) + sync de docs + ciclo de produto (3 specs)

**Sync de docs com o estado real:** ESTADO_ATUAL/ROADMAP/CLAUDE.md tinham 8+
divergências (contagem 703/712 vs 715 real; header dizia "smoke pendente" com spec
`done`; ROADMAP afirmava "Groq só em CLASSIFY" — falso desde o fix
`function_calling`; "80 traits" vs 40 reais; tabela de bugs 2026-06-26 com 4 bugs
JÁ fechados; Fase 11 listada como futura). Tudo corrigido; suíte verificada de
verdade (junitxml — a linha de resumo do pytest não imprime neste terminal).

**Auditoria de bugs/vulnerabilidades — 8 achados, TODOS corrigidos na sessão**
(+14 testes `tests/test_audit_fixes.py`; 715 → **729 verdes**):

| # | Achado (estado ANTES do fix) | Local | Severidade |
|---|---|---|---|
| A1 | `/game/new` não validava `level`: negativo → ouro NEGATIVO (`50×level`); DTO agora `Field(ge=1, le=20)` + tetos de tamanho em name/race/class/region/backstory | `api.py` | média |
| A2 | `/game/equip`/`/game/levelup` sem gate de `game_over` (memorial editável) e fora do rate limit → helper `_reject_memorial` (409) + ambos na janela | `api.py` | baixa-média |
| A3 | `save_game_state` montava caminho com `game_id` CRU → UUID via `save_path()`; legado sanitizado (alnum/-/_) — nunca escreve fora de `saves/` | `persistence.py` | baixa-média |
| A4 | flag `simulated` só olhava GOOGLE_API_KEY (jogo real no Groq aparecia simulado) → novo `llm_setup.is_simulated()` espelha o get_llm | `api.py`/`llm_setup.py` | baixa |
| A5 | bind default `0.0.0.0` (LAN sem auth) → `127.0.0.1`; expor = opt-in `RPG_HOST` (.env.example) | `api.py` | média |
| A6 | 500 devolvia `str(e)` → genérico; detalhe só no log do servidor | `api.py` | baixa |
| A7 | `input_text` sem teto → `max_length=2000` | `api.py` | baixa |
| A8 | dict do rate limit sem teto por IP → poda de janelas vencidas ao passar de 1000 | `api.py` | baixa |

Verificado LIMPO: XSS (mdLite escapa `&<>` antes de formatar, nos 2 frontends);
path traversal (borda `save_path` UUID); guards 12/12 nos `with_structured_output`;
zero `eval`/`exec`/`pickle`/`yaml.load` inseguro; `.env`/saves fora do git;
`hidden_traits`/segredos não saem pela API. `allow_dangerous_deserialization=True`
no FAISS é necessário e documentado.

**Ciclo de produto (3 specs `approved`, refinadas com o usuário via brainstorming):**
balanceamento-early-game (baseline → tuning de spawn → derrota narrada "O Saque"
1x/campanha: acorda 1 dia depois, mundo andou, perde TUDO menos 1 arma básica,
únicos voltam ao pool, 2ª queda = memorial → replan só por REGIÃO nova + intervalo
15 — achado: `campaign_manager._should_replan` replanejava em TODA viagem);
streaming-turno-sse (SSE de FASES do grafo via `app.stream`, zero LLM extra;
token-a-token descartado; carona: telemetria da 5.3 no log `rpg.turn` de produção,
dev-only); polish-sessao (GET/DELETE de saves + tela "Continuar jornada", chips de
COMBATE 100% mecânicos — zero schema LLM novo —, export .txt + busca local da
crônica, onboarding painel dismissible, passe mobile 390px). Decisões estratégicas:
pós-ciclo (arte vs público) DECIDE-SE com dados do playtest; backlog v2 enxuto
(só Crônica avançada; descartados chips de exploração LLM, prólogo guiado,
dificuldade configurável).

## 2026-07-13 (13) — fix-playtest-achados: 6 defeitos do transcrito real + fuga do jogador

Novo `playtest transcript <run_id>` (ação→narração por turno) expôs defeitos que o
mock escondia. 703 → **715 verdes** (+12 `tests/test_fixes_playtest.py`); smoke real
executado; spec `done`.
- **R1 beats em pt-BR:** schema/prompt do campaign_manager em inglês → beats em
  inglês. `Field(description)` pt-BR + regra IDIOMA + exemplo traduzido.
- **R2 NPC não repete:** `npc.py` injeta `<SUA_ULTIMA_FALA>` + regra anti-repetição.
- **R3 perfil `quester` objetivo curto:** `_objetivo_curto` (1ª frase ≤80; ação ≤160).
- **R4 gate de `game_over` no grafo:** morto continuava jogando fora da API →
  `main.py` gate condicional START→END; invariante `lifecycle.acts_after_game_over`.
- **R5 letalidade viagem (B+apex+fuga):** `world_utils.forced_encounter_danger`
  escala a FORÇA do encontro forçado (`eff = min(danger, (nível+3)//2)`); 5 zonas
  `apex` não escalam (sub-nível morre); combate deliberado/boss = perigo cheio.
  **Fuga do jogador era VESTIGIAL** → implementada (`hero_fled` encerra combate,
  golpe de despedida de quem age antes; perfis `fujao`/`quester` = 11º/12º).
  Smoke real: beats pt-BR ✓; NPC variou ✓; morto congelou ✓; nível-1 pegou minions ✓;
  fujao fugiu e sobreviveu ✓.

## 2026-07-06/07 (12) — Fase 5 INTEIRA: playtest agêntico (5.1 harness · 5.2 invariantes · 5.3 telemetria)

656 → **699 verdes** (+43 `tests/test_fase51/52/53.py`); 3 specs `done`; pacote novo
`playtest/`.
- **5.1 harness:** `runner.py` (`run_campaign` via `app.invoke` — MESMO caminho da
  API; saves isolados `saves_playtest/` por monkeypatch; RNG semeado; exceção de
  turno não derruba campanha) + `profiles.py` (10 perfis determinísticos:
  agressivo/explorador/comerciante/diplomatico/troll/mapa_breaker/combate/npc_only/
  loot_abuser/secret_rusher). CLI `python -m playtest run/report`.
- **5.2 invariantes:** `invariants.py` puro — vitals/economia/entidades/mundo/
  conhecimento (assinaturas dos 4 segredos canônicos)/roundtrip save→load; plugado
  no runner (`--invariants` ON; `error` conta no exit code).
- **5.3 telemetria:** JSONL 1 linha/turno (provider/modelo/tier/`fell_back`/
  `cost_usd`) + `summary.json` + `report.py` (agregado + `--baseline`) +
  `pricing.py` (custo estimado). Tetos `--max-requests`/`--max-cost` no `--real`.
- **Smoke real:** secret_rusher 4t real — 0 erros, 0 violações, R5 vigiou o narrador;
  fallback vivo (minimax 402/qwen 401 → próximo). Rodada mock 50t seed 42: 10/10
  perfis limpos.
- **Suíte `-m llm_playtest`:** 10 perfis no LLM real (~US$0.10) → **bug real:**
  rota `NONE` → `KeyError('none')` no troll (invisível offline — MockLLM nunca
  escolhe NONE). Fix: router normaliza NONE→STORY + regressão offline.
- **Switch 4 VITAIS × 30 turnos real (2026-07-07):** explorador/combate/diplomatico/
  secret_rusher, todos completaram, 0 erros. Achados: vazamento do Verme-Primordial
  (curadoria: doc público de fação nomeava o segredo + bug de parse do migrate
  dumpava 337 criaturas num doc público + Legião afirmava o pacto — fontes curadas,
  Verme `hidden` via overrides, reindex verificado); quests não fechavam (perfil
  `quester` + MockLLM propõe `quest_completed`); letalidade (teto de sobrevivência
  `cap = 5 + 3×nível + 2×aliados` no `encounter_budget`); Groq 100k TPD esgota em
  sessão longa (lição: playtest real grande = tier pago ou espalhar por dias).
  703 verdes ao fim.

## 2026-07-06 (11) — Roteamento multi-provider (spec `done`, smoke real)

629 → **656 verdes** (+26). `llm_setup.py` reescrito: `ModelTier` ganhou CLASSIFY;
`get_llm(tier)` devolve `RoutedLLM` (lista ordenada de candidatos `ROUTES`, cai pro
próximo em QUALQUER falha; esgotou → `AIMessage` vazio, NUNCA levanta — convenção
crítica intacta). `_build_openai` parametrizado (Groq/Qwen/GLM/MiniMax/Kimi/DeepSeek);
`_build_anthropic` novo (extra opt-in). Overrides: `RPG_FORCE_MOCK`/`LLM_PROVIDER`/
`RPG_ROUTES`. Telemetria: `set_llm_telemetry_hook`. Migração de tiers por nó
(`test_routing_tiers.py`). Achados do smoke: **Groq strict json_schema** →
`RoutedLLM._apply` injeta `method="function_calling"` p/ OpenAI-compat → Groq
GRÁTIS em todos os tiers (jogo roda 100% free); Anthropic rejeita `temperature` e
prefill; kimi 404. ROUTES final: CLASSIFY groq→gemini-lite; FAST minimax→qwen→groq→
gemini-flash; SMART deepseek→groq→anthropic→gemini-pro. Contas: minimax/deepseek 402,
qwen 401 (opcional; Groq cobre). `LLM_PROVIDER=gemini` força só-Gemini.

## 2026-07-06 (10) — Fase 10 local + Fase 11 contratos + mapa interiores + NPCs 3 camadas

581 → **629 verdes** + 9 contratos verdes no Gemini real.
- **Fase 10 (local):** `save_path()` UUID anti-traversal; `schema_version` +
  `_MIGRATIONS` (v0→v1 consolida backfills; v1→v2 campos de NPC); CORS por env;
  rate limit por IP; log JSON por turno (`rpg.turn`). Postgres/auth = 10b.
- **Fase 11:** `pytest -m llm_contract` = 9 contratos reais (router×2, StoryUpdate
  banal, combate, NPC não-onisciente, TradeIntent, e2e+archivist, loot, fallback);
  substitui `tests/test_real_llm.py`.
- **Mapa:** `travel_times` por conexão (anéis custo 0 — relógio parado) + 5 nós
  `kind: interior` (abrigo, sem encontro, fora do mapa-múndi; chips "Locais daqui").
- **NPCs 3 camadas:** `services/npc_layers.py` + `data/traits.json` (40, lote 1) —
  traits seeded, revelação por interação, `trait_dc_modifier` no recrutamento;
  gate camada 3 (`in_scene=False` → "X não está aqui" SEM LLM — fecha o bug "NPC
  errado responde"); `hidden_traits` nunca sai pela API.

## 2026-07-05 (9) — Fase 7 INTEIRA: pipeline de autoria + validação

520 → **581 verdes**; lint do repo 0 erros; smoke real de não-vazamento.
7.1 lint (`services/content_validator.py` + CLI + gate + CI validate.yml);
7.2 curadoria migration-safe (`codex_overrides.yaml`, `curated: true`, 6 templates,
`docs/guias/AUTORIA.md`, `reindex_global()` com gate de lint); 7.3 segredos de NPC
(migrate divide por rótulo → doc `hidden` paralelo; 141 NPCs, 14 c/ segredo;
auditoria fechou vazamento real do pacto Valerius↔Daruun na fonte).

## 2026-07-05 (8) — Fase 6 INTEIRA: conteúdo sistêmico

461 → **520 verdes**; smoke real executado; 3 fixes de robustez achados
(StoryUpdate.narrative default; _narrate normaliza parts; fold de acentos na viagem).
6.1 economia viva (rotas bloqueadas, escassez por BFS); 6.2 itens únicos (20, claim
engine, gates nos 4 caminhos); 6.3 migração de monstros (pressão de caça com decay);
6.4 encontros sistêmicos (detection_check, armadilha/social/rastro em Python);
6.5 clima mecânico (Markov por região; miasma nega descanso; efeito é leitura).

## 2026-07-04/05 (7) — Fase 4 INTEIRA: Gameplay Core

313 → **461 verdes**; 7 specs `done`; smoke real com 4 bugs de integração achados
e corrigidos (equipment descartado no /game/new; XP de beat no prólogo; _narrate
sem HumanMessage; `game_over` fora do GameState → update descartado pelo grafo).
4.1 progressão (XP kill/beat/quest, level up, ids canônicos, gate anti-LLM);
4.1b árvores de Valoria (10 classes × 2 ramos, 111 habilidades); 4.2 buffs
mecânicos (condition_modifiers nos 2 lados, 9/10 passivas data-driven);
4.3 inventário `{id, qty}` + slots + poção em combate (3 bugs históricos fechados);
4.4 economia determinística (`services/economy.py`, TradeIntent, mercadores com
restock); 4.5 party (gate determinístico, N vs N, alvo tático); 4.6 dificuldade/IA/
morte (encounter_budget, habilidades de elite/boss com fases, morte = fecho de
saga + memorial 409).

## 2026-07-03 (6) — Fase 3.4: Visualização de estado (`done`) — Fase 3 completa

- **`services/state_views.py`** (novo, puro): `reputation_history` (últimos 20 eventos
  `reputation_changed` da fação, cronológico), `stability_label` (3 rótulos por
  limiares ascendentes sobre `projection.entities[fid].stability` — o número NUNCA sai
  da API), `recent_control_changes` (`location_control_changed` dos últimos 30 turnos,
  só locais `visited` — fog of war), `active_threats` (leitura de `world.threat_alerts`
  não expirados, mesmo TTL de `world_utils._ALERT_TTL`, sem consumir o alerta),
  `visible_controllers` (local visitado → NOME de quem domina).
- **`graph_resolver.get_current_controller`** ganha `include_hidden: bool = True`
  (default retrocompatível) — `visible_controllers` chama com `False` pra visão do
  jogador, sem duplicar a lógica "dynamic edge vence base".
- **Evento `reputation_changed`** entra no pipeline 2.6 mas é **gerado 100% em Python**
  (`agents/storyteller.py`, no loop que já chama `apply_reputation` — usa `event["id"]/
  ["delta"]/["reputation"]/["direction"]` que a função já devolvia e descartava antes).
  Zero campo estruturado novo no LLM, zero guard de `FallbackLLM` necessário.
- **Achado que simplificou a etapa 2 inteira:** `services/event_processor.py` não
  precisou de NENHUMA mudança. `apply_event` já tem fallthrough (tipo sem `elif` →
  projection intocada) e `_chronicle_milestone` já pula tipo fora de
  `CHRONICLE_EVENT_TYPES` — `reputation_changed` fica de fora do set de propósito
  (timeline da fação é o lugar dela, não a crônica) e os dois comportamentos pedidos
  pelo R1 (no-op na projection + não vira milestone) já existiam de graça.
- **`api.py`:** `_world_block` ganha `map_overlays` (`control_changes`/`threats`/
  `looming_threat`) e `controlled` passa a vir de `visible_controllers` (NOME, não
  mais id de fação — e agora respeitando fog of war por local visitado, o que a
  versão antiga não fazia). `_factions_block` ganha `history`/`stability_label` por
  fação já filtrada por `intel.known` (timeline nunca vaza fação desconhecida).
- **Frontend:** `WorldMap` ganha badge `is-contested` (controle mudou há ≤10 turnos),
  ícone ⚠ por `region_id` (locais agrupam por região — `MapLocation.region_id`, campo
  que já vinha cru de `GET /data/map` mas faltava no tipo TS) e banner de
  `looming_threat`. `FactionsTab` ganha sparkline SVG inline (`<polyline>`, sem lib) +
  rótulo de estabilidade colorido + últimas 3 mudanças de reputação.
- **Suíte:** 290 → **313 verdes** (+23 em `tests/test_fase34.py`, ids reais —
  `nova_arcadia`/`legiao_ferro`/`mao_sombria`).  `npm run build` ok, `smoke_api.sh` ok.
- **Smoke com LLM real:** confirmado `map_overlays`/`controlled` corretos num jogo real
  (`controlled: {"nova_arcadia": "Lorde Protetor Valerius"}` — nome do controlador
  canônico, não id de fação). A criação do evento `reputation_changed` em si não
  depende de nenhum schema LLM novo (Python puro) — risco "MockLLM esconde bug de
  mapeamento" não se aplica aqui, já coberto por teste de integração determinístico
  (`test_pipeline_reputation_changed_completo`).
- **Fase 3 (Clareza de campanha) fecha nesta sessão** — 3.1/3.2/3.3/3.4 todas `done`.

---

## 2026-07-03 (5) — Fase 3.3: Quest log (`done`)

- **`state.py`:** `Quest(TypedDict, total=False)` (`id/title/description/status/
  origin_name/origin_entity_id/location_id/created_turn/resolved_turn/reward_hint`);
  `GameState.quests: List[Quest]` (só side quests — main quest continua view pura do
  `campaign_plan`, zero estado novo).
- **`services/structured_outputs.py`:** `ProposedQuest` — schema de CRIAÇÃO de side
  quest. Conclusão não ganhou schema novo: reusa `ProposedWorldEvent(type=
  "quest_completed", target_id=quest_id, payload={"quest_id": ...})`, mesmo canal já
  usado por `npc_killed`/`secret_revealed` desde a 2.6.
- **`services/quest_log.py`** (novo, puro): `register_proposed_quests` (dedupe por
  `difflib.SequenceMatcher≥0.75` contra ativas, zera `location_id`/`origin_entity_id`
  inválidos em vez de rejeitar a quest, teto `MAX_ACTIVE_QUESTS=8`), `complete_quest`,
  `fail_orphan_quests` (gera `GameEvent` `quest_failed`, `source="system"`),
  `quest_markers`.
- **Hooks nos agentes:** `StoryUpdate`/`NPCResponse` ganham `proposed_quests`, lidos
  dentro dos trys já existentes (mesmo guard de `proposed_events`/`faction_reveals`).
  No `npc_actor`, `origin_name`/`origin_entity_id` são SOBRESCRITOS em Python
  (`_canonical_npc_id`, match por nome no grafo) — o LLM só controla title/description/
  location_id/reward_hint. `storyteller` ganha bloco de prompt `<QUESTS_ATIVAS>`
  (análogo a `<ENTIDADES_CANONICAS>`, Fase 2.6).
- **`services/world_validators.py`:** `_v_quest_completed` ganha branch `payload.
  quest_id` no topo (checa `state.quests` ativas); ausência de `quest_id` cai no modo
  beat original (Fase 2.6, sem mudança — `test_fase26.py` continua verde).
- **`services/event_processor.py`:** `apply_event` ficou INTOCADO (contrato "só mexe
  em projection" preservado — quest completion/failure não é efeito de projection).
  `process_pending_events` ganha variável local `quests`/`quests_changed`, mesmo
  padrão de `chronicle`/`chronicle_changed`: ao aplicar `quest_completed` com
  `quest_id`, embute `payload["quest_title"]` (lookup em `state.quests`) ANTES do
  milestone; ao aplicar `npc_killed`, chama `fail_orphan_quests` e anexa os
  `quest_failed` resultantes ao `event_log`.
- **`services/chronicle.py`:** `quest_failed` entra em `CHRONICLE_EVENT_TYPES`/
  `CHRONICLE_TEMPLATES`; `render_milestone` usa `payload.get("quest_title") or
  _name(target_id)` — `target_id` de quest é um uuid (quest_id), não id de grafo,
  `_name()` não resolveria (mudança no-op pros outros tipos de evento).
  `_v_npc_killed` só aceita NPC canônico → falha sistêmica (R4) só existe pra quests
  com origem no grafo; NPC gerado em runtime nunca falha quest por essa via (aceitável).
- **API/frontend:** `_quest_block(plan, quests)` vira `{main, side, markers}` (main =
  shape antigo + `arc_title`; side = ativas + até 5 resolvidas mais recentes; markers =
  `[{quest_id, location_id}]` pro mapa). Achado da exploração: o bloco `quest` antigo
  NUNCA teve componente React consumindo — aba "Missões" (`QuestsTab.tsx`) é
  greenfield puro, não migração. `WorldMap` ganha prop `markers` (selo ◆ no local).
- **Suíte:** 258 → **290 verdes** (+32 em `tests/test_fase33.py`, ids reais de
  `data/graph/entities.json` — `npc_valerius`/`npc_grum`/`nova_arcadia`). `npm run
  build` ok. `smoke_api.sh` ok.
- **Smoke com LLM real executado e verde** (4 requests): NPC "Valdir" (Gemini SMART)
  propôs quest real ("A Sede do Quebrado") com `origin_name` corretamente sobrescrito
  pelo código a partir do `npc_data`, `origin_entity_id=""` (NPC runtime, não
  canônico — comportamento esperado); turno seguinte concluiu a quest via
  `quest_completed` proposto pelo LLM com `quest_id` correto; milestone na crônica
  mostrou "A missão "A Sede do Quebrado" foi concluída." — título, não uuid.
  Confirma mapeamento correto de `proposed_quests` nos DOIS agentes (risco clássico
  "MockLLM esconde bug de mapeamento" — mitigado).

---

## 2026-07-03 (4) — Fase 3.2: Codex do jogador + bestiário progressivo (`done`)

- **`state.py`:** `BestiaryKnowledge(TypedDict, total=False)` (`seen/fought/defeated/
  first_seen_turn/last_update_turn`); `GameState.bestiary_knowledge: Dict[str,
  BestiaryKnowledge]` (chave = id de `data/bestiary.json`).
- **`services/discovery.py`** (novo, puro): `normalize_bestiary_id` (id de instância
  `{bestiary_id}_{N}` → id real, valida contra `gamedata.BESTIARY`), `record_encounter`/
  `record_kills`/`record_rumor` (contadores aditivos, dict novo), `knowledge_tier`
  (`BESTIARY_TIERS`: 1 Rumores/seen≥1, 2 Encontrada/fought≥1, 3 Estudada/defeated≥3,
  4 Dominada/defeated≥7), `bestiary_view` (campos crescentes por grau: nome+regiões →
  +descrição/tipo → +HP/defesa/nomes de ataque → +dano/behavior/loot), `player_codex`
  (agrega locations/factions/characters/creatures/secrets — 100% derivado do save já
  existente, zero estado novo para essas 4 categorias).
- **`services/codex_loader.py`:** `codex_index()` (cache módulo-level, id→path, mesmo
  padrão de `os.walk` de `load_codex`) e `codex_body(entity_id)` (corpo truncado a
  2000 chars, `""` se `visibility != "public"` ou id não achado — não-onisciência).
- **Hooks de combate (`agents/combat.py`):** spawn (`is_combat_start and not active`) →
  `record_encounter` (1x/combate, contorna dupla contagem por round); bloco de `dead`
  (fim de round) → `record_kills`.
- **Rumor sem combate (R3) — desvio da spec original:** a leitura literal ("threat_alert
  cria rumor") não fechava — a criatura que fugiu já teria `fought≥1` nesse combate,
  contradizendo "seen sem fought". Resolvido em `check_encounter` (`world_utils.py`):
  os branches que NOMEIAM uma criatura concreta ANTES do combate (reforços consumindo
  `threat_alert.enemy_id`; `ruler`/`danger>=4` via `pick_encounter_enemy`) agora
  retornam `enemy_id`; `agents/storyteller.py` (onde o `SystemMessage("COMBAT START")`
  é montado) chama `record_rumor` só quando `enemy_id` existe — antes do spawn real.
  `register_flee_alert` ganhou parâmetro `enemy_id` (opcional, retrocompatível) pra
  carregar o id do bestiário no alerta até o consumo.
- **Persistência/API:** `bestiary_knowledge` com default `{}` em save/load (sem
  migração — save antigo simplesmente não tem o campo); `initial_state` em
  `game_engine.py` E `api.py::new_game` (duas cópias independentes); `_world_block`
  ganhou `turn_count` (não existia — necessário pro refetch da aba); `GET /game/codex`
  segue o padrão real de `/game/state` (`f"saves/{game_id}.json"`, não
  `load_game_state(game_id)` como a spec sugeria de forma simplificada).
- **Frontend:** `CodexTab.tsx` (novo) — 5 categorias com sub-nav, selo I–IV por
  criatura (silhueta CSS em cinza no grau 1), corpo do Codex renderizado via `mdLite`;
  primeira aba do HUD com fetch próprio (`useEffect` + `getCodex`), refeito quando
  `world.turn_count` muda com a aba aberta (`ChronicleTab`, por comparação, só usa
  props — não tinha esse padrão antes).
- **Suíte:** 228 → **258 verdes** (+30 em `tests/test_fase32.py`, usando ids reais de
  `data/bestiary.json`/`data/codex/` — zero fixture inventada, evita mascarar bug de
  id/path). `npm run build` ok. `smoke_api.sh` com checagem nova de `/game/codex`
  (200 OK) — smoke completo verde numa API local (mock, sem chave).
- **Zero LLM na fase** — sem guard de `FallbackLLM` necessário (100% Python
  determinístico). Detalhe completo dos desvios: `specs/fase-3.2-conhecimento-
  revelavel.md` §8.

---

## 2026-07-03 (3) — Fase 3.1: Diário + Crônica por capítulos (`done`)

- **`services/chronicle.py`** (novo, puro): `CHRONICLE_EVENT_TYPES` (npc_killed,
  location_control_changed, quest_completed, secret_revealed — faction_relation_changed
  fica FORA por ruído), `CHRONICLE_TEMPLATES` voltados ao jogador, `render_milestone`
  (nome canônico via `context_builder._name`; `{by_player}` derivado de
  `actor_id == "player"`), `append_entry`/`open_chapter` puros,
  `default_chapter_title(region)`.
- **Schema:** `ChronicleEntry`/`ChronicleChapter` em `state.py`;
  `GameState.chronicle: List[ChronicleChapter]`; `CampaignPlan.arc_title`.
- **event_processor:** todo evento APLICADO (base + cascata da rules engine) de tipo
  crônica gera milestone determinístico com `event_id` auditável; chave `chronicle`
  só entra nos updates quando houve mudança.
- **archivist:** prosa (`chronicle_entry`) vira entrada `kind="prose"` appendada SOBRE
  o chronicle já atualizado pelos milestones (merge `{**event_updates, **updates}` —
  ordem invertida de propósito); prompt instrui a não repetir fatos secos.
- **campaign_manager:** `CampaignPlanModel.arc_title` (mesmo call do planner, zero
  request extra) com instrução de persistência; título novo → `open_chapter`; fallback
  mantém arco atual (não fragmenta por erro de LLM). MockLLM devolve
  `"A Verdade Enterrada"` estável.
- **Persistência:** backfill em `load_game_state` — `chronicle: List[str]` antigo vira
  capítulo único "Crônica da jornada" (entradas `prose`, turn 0).
- **API/frontend:** `GameResponse.chronicle` = capítulos (`_chronicle_block` filtra
  entradas vazias); `/game/new` e `game_engine.py` criam capítulo 1 no turno 0
  (`default_chapter_title`); `ChronicleTab` renderiza capítulos reversos com header
  (título + "desde o turno N"), milestone = ⚔ + `chron--milestone`, prosa = ❧.
- **Suíte:** 211 → **228 verdes** (+17 em `tests/test_fase31.py`). `npm run build` ok.
  Smoke API real ok (capítulo inicial + capítulo novo no primeiro replan). Falha do
  `smoke_api.sh` no /game/new é encoding de acento do curl do Git Bash (ambiente,
  não código — body ASCII passa).
- **Smoke com LLM real executado** (mesma sessão, 2 req gemini-pro direto em
  `_build_plan`): sem arco anterior o planner inventou "Fagulhas na Chuva Fria"
  (mapeamento do campo novo ok); com arco "A Sombra sobre Nova Arcádia" e mesma
  situação, MANTEVE o título (persistência ok). Ver spec §6.
- **Fix `scripts/smoke_api.sh`:** curl do Git Bash no Windows corrompe UTF-8 inline
  (`-d` com "Nova Arcádia" → bytes cp1252 → 422 "error parsing the body"); body do
  `/game/new` agora vai via `--data-binary @arquivo`. SMOKE OK completo.

---

## 2026-07-03 (2) — Faxina de código morto + auditoria de gameplay → Fase 4

- **Removidos** (zero importadores em produção, verificado por grep): `agents/ruler_completo.py`
  (CLAUDE.md alegava uso pelo storyteller — falso), `engine_utils.py` + `dice_system.py`
  (só testes importavam), `COMMON_LOOT_TABLE` (gamedata.py). 5 testes órfãos de
  `test_mvp.py` removidos junto. Suíte 216 → **211 verdes**.
- **Mantidos de propósito:** `XP_TABLE` (consumidor chega na 4.1), `party`/`CompanionState`
  (4.5), `frontend/` vanilla (fallback VIVO no api.py quando `web/dist` não existe).
- **Docs corrigidos:** CLAUDE.md (estrutura de pastas, storyteller sem "ruler",
  `world_lore.txt` fantasma, `world_map.json` → Valoria 30 nós), README.md, comentários
  mortos em `storyteller.py`/`mock_llm.py`.
- **Auditoria de jogabilidade** (achados-chave): `XP_TABLE` sem consumidor — xp nunca
  incrementa, NÃO existe progressão; buffs/passivas só texto (dano/AC não leem
  `active_conditions`; só DoT funciona); party só schema (combate é 1×N estrito);
  craft/shop/loot 100% LLM (sem receitas/estoque/drop tables); poção inutilizável em
  combate (parser só resolve habilidades); inventário inicial com nomes livres que o
  `ARTIFACTS_DB` não resolve; spawn narrativo sem teto de CR; campo `abilities` de
  inimigo decorativo; morte do player sem narrativa.
- **ROADMAP:** nova **Fase 4 — Gameplay Core** em 6 fatias `draft` (4.1 progressão/XP/
  árvore de habilidades · 4.2 buffs/passivas mecânicos · 4.3 inventário/equip/itens
  usáveis · 4.4 economia determinística · 4.5 party · 4.6 dificuldade/IA/morte).
  Fases antigas renumeradas (playtest 4→5 ... contract tests 10→11). Backlog consolidado:
  Party→4.5, Crafting→4.4, Lore Multi-Índice obsoleto (Codex 2.5 cobre), Mapa robusto
  reduzido ao restante (sub-locais, tempo de viagem variável, economy_tags).

## 2026-07-03 — Fase 2.8: Context builder com orçamento de tokens

Entregas (spec `specs/SPEC-005-fase-2.8-context-builder.md`):
- `services/context_builder.py` — `estimate_tokens` (chars/4), `score_fact`
  (0.35 rel + 0.25 local + 0.20 entidade + 0.10 impacto + 0.10 recência), `render_event`
  (`EVENT_TEMPLATES`; nome canônico via `gr.get_entity`, não id cru), `collect_dynamic_facts`,
  `_assemble` (budget por seção + carry), `assemble_pack`, `build_context_pack`.
- Correções vs spec (aplicadas): evento usa `turn` (não `day`), `actor_id`/`target_id`;
  sem `visibility` no evento (lore filtra por `query_rag(max_visibility)`; `secret_revealed`
  só via `revealed_facts`); `location_summaries`/`revealed_facts` moram em `world_projection`;
  `build_context_pack` ganhou `game_id`/`npc_id` opcionais.
- Agentes: `agents/storyteller.py`, `agents/npc.py`, `agents/combat.py`,
  `agents/campaign_manager.py` — `query_rag`+`narrative_summary` manuais → pack.
- Suíte na época: 216 verdes (201 baseline + 15 da 2.8). Smoke LLM real pendente de quota.

## 2026-07-02 — Fase 2.7: Rules engine sistêmica

Entregas (spec `specs/SPEC-004-fase-2.7-rules-engine.md`):
- `services/rule_engine.py` — `resolve_path` seguro (só literais/`event.`/`target.`/
  `component:`; dunder + expressão arbitrária → `RuleActionError`), `check_conditions`,
  `execute_action` (ops: set_entity_state, adjust_faction_stability, disable_controls_edges,
  create_dynamic_edge, emit_event), `run_rules` (dona da cascata + anti-loop depth 2).
- `data/graph/world_rules.json` (5 regras) + `data/graph/components.json` (overlay
  `power_vacuum_trigger` em 22 líderes/governantes). Overlay é **migration-safe**
  (`migrate_lore_nova.py` sobrescreve entities.json com `components:{}`), mergeado por
  `graph_resolver.load_entities`.
- Modelo HÍBRIDO: estrutura (líder/controle/rival) DERIVADA dos edges (`leads`/`controls`/
  `enemy_of`/`operates_in`); componente só carrega delta/sucessor/override + é o discriminador.
- `event_processor.process_pending_events` chama `run_rules` após cada `apply_event`.

## 2026-07-02 — Fase 2.6: Structured world changes

Entregas (spec `specs/SPEC-003-fase-2.6-structured-events.md`):
- `services/structured_outputs.py` — `ProposedWorldEvent` / `WorldChangeProposal` (Pydantic).
- `services/world_validators.py` — `validate_proposal(dict, state)` → `ValidationResult(ok, reason)`;
  regras por tipo (npc_killed, secret_revealed, location_control_changed, quest_completed,
  faction_relation_changed) via `graph_resolver`; revalida do zero (dict malformado = rejeitado).
- `services/event_processor.py` — `process_pending_events` (valida→GameEvent→append→aplica→limpa fila)
  + `apply_event` puro (efeito direto na projection, SEM cascata — isso é a 2.7).
- `storyteller` propõe via `StoryUpdate.proposed_events` + bloco `<ENTIDADES_CANONICAS>` no prompt.
- `combat` gera `npc_killed` **determinístico** (`_kill_events`) p/ inimigo canônico — sem LLM.

## 2026-07-02 — DX: tooling do Claude Code (auditoria de fricção)

Auditoria de 20 sessões de transcripts achou: prefixo de PATH repetido 180×, ~36KB de
docs carregados toda sessão, leituras de lore de 30–56KB, 120 runs de pytest verbosos.
Entregas:

- **Docs de sessão em dieta:** `@REFERENCE.md` removido do auto-load do `CLAUDE.md`
  (leitura sob demanda); `ESTADO_ATUAL.md` de 13.3KB → ~5.5KB; histórico de sessões
  movido para este `CHANGELOG.md` (não carregado). Economia ~6-7K tokens/sessão.
- **Skills de projeto:** `/qa` (pytest token-lean, só falhas + resumo; `--lf` p/ iteração)
  e `/wrap-up` (ritual de fim de tarefa: suíte + docs + commit via caveman-commit).
- **`scripts/smoke_api.sh`:** smoke da API (health, options, map, /game/new, /game/state,
  /game/action + limpeza do save) — substitui loops de curl reescritos a cada sessão.
- **Hook `reindex-reminder.js`** (PostToolUse Edit|Write): editar `lore_nova/`,
  `data/codex/` ou `data/rules.txt` injeta lembrete de rodar `uv run python rag.py`
  (1x por sessão). Ativação junto com a allowlist em `.claude/settings.proposed.json`
  (renomear para `settings.json` após revisão — escrita direta bloqueada em auto mode).
- **Regra anti-leitura-gigante** no `CLAUDE.md`: lore/codex/JSONs grandes = Grep ou
  Read parcial, nunca Read inteiro.
- Pendente (ação manual, bloqueada em auto mode): PATH permanente do uv —
  `[Environment]::SetEnvironmentVariable('Path', "$env:APPDATA\Python\Python314\Scripts;" + [Environment]::GetEnvironmentVariable('Path','User'), 'User')`.

## 2026-07-02 — Fase 2.5b: Valoria nos dados mecânicos + combate com comportamento

- **Mapa** (`data/world_map.json`): 30 nós — 12 macro-regiões do grafo + 18 sublocais
  (anéis de Nova Arcádia, Fortaleza de Vorr, O Trono...). Grafo conexo (teste BFS),
  `region_id` em todo nó, 1 `start: true` por região. Start global: `nova_arcadia`.
- **Fações** (`data/factions.json`): 18 fações de Valoria (legiao_ferro, mao_sombria,
  filhos_chama_azul, tribos_devoradores_sol...) com goal/pace/ascension derivados do
  Codex; targets de ascensão apontam para o mapa novo.
- **Raças** (`data/origins.json`): 6 jogáveis (Humano, Elfo, Anão da Fuligem, Vrel,
  Cinzéu, Osshari) com **traits mecânicos** da lore — `apply_racial_traits()` em
  `character_creator.py` aplica bônus de atributo/recursos/defesa/ouro/itens em Python;
  `condition_resists` (ex.: Anão ignora veneno) e `racial_save_bonus` respeitados por
  `combat_mechanics`. Ficha ganha `racial_traits`/`condition_resists`/`racial_save_bonus`
  (`state.py`; saves antigos: campos ausentes = sem efeito, sem crash).
- **Bestiário** (`data/bestiary.json`): 84 entradas curadas com `regions` e `behavior`;
  criaturas do grafo usam `mon_<slug>`, combatentes de fação `enemy_<slug>` + campo
  `faction` (mapeia fação → soldado no encontro).
- **Combate com personalidade (R8):** perfis `tatico` (escolhe ataque por situação, foge
  por moral — `flee_below`/`pack_morale`), `feroz` (maior dano, frenesi +2 com HP<50%,
  NUNCA foge — urso-titã), `covarde` (foge cedo), `implacavel` (rotaciona ataques, nunca
  foge) — determinístico em `combat_mechanics.py` (`choose_enemy_attack`, `check_morale`,
  `get_behavior`). Status novo `"fugiu"`: não conta como vitória nem loot; combate sem
  mortos (todos fugiram) NÃO roteia para loot. Ataques de inimigo aplicam condições
  embutidas na string de dano ("+ veneno" → Condition no player, respeitando resist racial).
- **Fuga → alerta (R10):** `world["threat_alerts"]` (`world_utils.register_flee_alert`,
  chamado pelo combat_node); alerta ativo na REGIÃO dispara encontro de reforços 1x
  (validade 6 turnos, consumido ao disparar, expira sozinho). Backfill em `ensure_world`.
- **Encontro por região (R11):** `world_utils.pick_encounter_enemy()` sorteia criatura
  CONCRETA do bestiário por região/perigo/fação (BOSS nunca sai aleatório) —
  `check_encounter` devolve hint com o nome exato → spawn cai no cache (menos 1 LLM call).
- **Identidade:** `data/graph/entities_extra.json` (curadoria manual: sublocais +
  combatentes de fação; `migrate_lore_nova.py` NÃO o toca) mergeado em
  `graph_resolver.load_entities()` — canônico vence conflito. Teste de integridade
  cruzada cobre os 4 JSONs mecânicos.
- **Limpeza (R5):** `data/world_lore.txt` REMOVIDO; `mock_llm.py` agora usa `legiao_ferro`
  como fação simulada (era `selo_palido`).
- Testes: `tests/test_fase25b.py` (novo, 24 testes: integridade, mapa conexo, traits,
  moral/fuga/frenesi, alertas, sorteio regional) + repin de `test_fase0`/`test_fase2`/
  `test_world_sim` para os dados novos.

## 2026-07-02 — Limpeza de deps

Removidas do `pyproject.toml` deps sem nenhum `import` no código — `chromadb`, `graphviz`,
`kuzu`, `langchain-chroma`, `langchain-experimental`, `langsmith`, `streamlit` — leftovers
de planejamento anterior à 2.5 (o grafo de mundo virou JSON puro em
`services/graph_resolver.py`, não kuzu). `uv sync` + `uv run pytest` (116 verdes)
confirmaram nada quebrou. `stream_ctx.py` intocado — infra planejada pela spec 2.5b/2.8
(streaming futuro), não código morto.

## 2026-07-02 — Timeline de Valoria no Codex

`lore_nova/timeline_completa.txt` (Codex Omnia — 8 eras, da criação ao presente) ingerido
no Codex. Novo handler `parse_timeline()` em `scripts/migrate_lore_nova.py` gera
`data/codex/timeline/*.md` (1 doc por run de visibilidade, `type: timeline`, NÃO registra
entidade no grafo). Os 4 clusters de reveal que `secrets.txt` já protege (aprendiz→Arauto,
Rei Subterrâneo, pacto Valerius↔Daruun, Rede Carmesim) saem como `visibility: hidden` —
não vazam ao narrador público (`query_rag(max_visibility="public")`); o resto da história
é `public`. Curadoria explícita em `_TIMELINE_HIDDEN_CLUSTERS` (pares frase-inicial→
frase-final). 4 testes novos em `tests/test_fase25.py`. Codex reindexado (2579 chunks).

## 2026-07-02 — Fase 2.5: Codex + grafo de mundo

Lore REESCRITO em `lore_nova/` (universo **Valoria**, ~690KB), SUBSTITUI o lore antigo.
Spec `specs/SPEC-001-fase-2.5-codex-world-state.md` → `done`:

- `scripts/migrate_lore_nova.py` → gera `data/codex/` (635 .md com frontmatter
  `id/type/name/tags/visibility`) + `data/graph/entities.json` (558 entidades: 12 regiões,
  28 fações, 141 NPCs, 10 raças, 340 monstros, 27 artefatos únicos).
  ⚠️ Re-rodar o script SOBRESCREVE curadoria manual no codex/entities.
- `data/graph/edges.json` (~70 edges curadas à mão) + `relation_types.json` (7 tipos).
  Estes o script NÃO toca.
- `services/graph_resolver.py` — edges efetivas = base − disabled + dynamic, com
  visibilidade; `get_current_controller`, `is_alive`. `services/codex_loader.py` —
  ingestão FAISS com metadados. `query_rag(..., max_visibility="public")` filtra
  `hidden`/`secret` do contexto do narrador (default preserva comportamento).
- `GameState` ganhou `event_log` / `world_projection` / `pending_world_events`
  (persistidos em `persistence.py`; saves antigos carregam com defaults vazios).
- Smoke real OK: reindex do Codex (2297 chunks), 1 turno real narrando lore de Valoria,
  chunks `secret` fora do contexto público.

## 2026-07-01 — Projeto vira spec-driven

`specs/` + convenção no `CLAUDE.md`; specs 2.5–2.8 criadas.

## 2026-06-26 — Multi-provider LLM + typewriter

- `get_llm()` suporta Gemini, Ollama, OpenAI e endpoints OpenAI-compatíveis (Qwen,
  LM Studio) via `LLM_PROVIDER` + vars no `.env`. Sem tocar nos agentes.
- Narrativa com efeito typewriter (palavra a palavra) no frontend React.
- `stream_ctx.py` criado com ContextVar SSE (infra para streaming real futuro).
- `MockLLM.stream()` adicionado para compatibilidade.

## 2026-06-26 — Otimização de turno

Turno reduzido de ~5-6 para ~2-3 LLM calls (commit `fcb14c0`).
