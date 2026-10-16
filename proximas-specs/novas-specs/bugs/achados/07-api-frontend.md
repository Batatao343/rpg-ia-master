# Auditoria de bugs funcionais — Área 07: API / frontend (2026-10-15)

**Cobertos:** `api.py` (modelos, `format_response` e blocos `_*_block`, `/game/new|prologue|action|action/stream|state|saves|death|levelup|equip|chronicle*|history`, `/data/*`, combat-simulator, rate-limit, `_begin_*_operation`), `web/src/{App.tsx,api.ts,http.ts,pendingOperation.ts,lib.ts,types.ts}`, `hooks/useTypewriter.ts`, `components/{PlayScreen,Hud(parcial),StoryLog,CardHand,LevelUpModal,DeathModal,WorldMap,CombatSimulatorScreen,CreateScreen,SaveScreen,CodexTab(effects),AccountScreen(exibição)}`, `voice/{controller,useVoiceInput}`. `npx tsc --noEmit` limpo; `npm test` 34/34.
**Não cobertos (tempo):** `purchases/*`, `native/*`, `AuthScreen`, `ArtworkDialog/ImageQuoteDialog/GeneratedArtCard`, endpoints `art/*` (quote/confirm), render do `CodexTab`, abas Pessoas/Facções/Crônica do `Hud`, `ReactionPrompt/SceneZones/WoundTrack`, Postgres real (achados do perfil durável são por leitura de código).
**Contagem:** crítica 0 · alta 1 · média 4 · baixa 4. types.ts × payload: sem divergência com impacto (apenas campos extras do servidor sem tipo — ver "Descartados").

---

### BUG-07-01 — Soft-lock de ação pendente no perfil durável (op `failed` reenviada após mudança de versão do jogo)
- **Severidade:** alta
- **Categoria:** estado-inconsistente
- **Local:** `web/src/App.tsx:498-515,540-552`, `web/src/pendingOperation.ts:22-25`, `infrastructure/postgres_turns.py:89-91`
- **Evidência:** `handleAction` recusa qualquer texto diferente enquanto existe pending (`"Resolva a ação pendente antes de enviar outra."`), e o único `clearPending` em erro é para HTTP 400/422. No servidor, `claim()` com a MESMA `operation_id` já existente exige `existing["base_game_version"] == base_version` (senão `Conflict("operação divergente")` → 409 `operation_conflict`).
- **Reprodução (por leitura; Postgres não executável offline):** (1) turno falha (500 do LLM / evento SSE `exc`) → op fica `failed`, pending persiste em localStorage; (2) usuário equipa item ou escolhe nível (`/game/equip|levelup` NÃO checam pending e incrementam `version`); (3) reenvio da ação pendente (botão "Consultar / retomar" ou mesmo texto) usa a mesma `operation_id` mas `base_version` novo → 409 permanente. Novo texto é bloqueado pelo guard do cliente. Não há UI para descartar o pending; só limpando localStorage. Também ocorre se o jogador resolver `/game/death` (restore) entre a falha e o retry. Status 409 nunca limpa pending (App.tsx:542 só 400/422).
- **Impacto:** campanha travada (nenhuma ação nova possível) até limpar o storage manualmente.
- **Correção sugerida:** (a) no servidor, `claim` de op `failed` deve reaproveitar a op atualizando `base_game_version` (ou tratar `failed` como inexistente); (b) no cliente, 409 `operation_conflict`/`operation_request_mismatch` → `clearPending` + oferecer "Descartar ação pendente"; (c) bloquear equip/levelup enquanto houver pending ou limpar o pending no sucesso.
- **Confiança:** provável (leitura dos dois lados; sem Postgres para executar)
- **Testes existentes relacionados:** `web/tests/pending.test.mjs` (cobre persistência, não o descarte); nenhum para claim de op `failed` após bump de versão.

### BUG-07-02 — Erros 422 do FastAPI aparecem como "[object Object]" na UI
- **Severidade:** média
- **Categoria:** contrato-api
- **Local:** `web/src/http.ts:21-25` (`errorFor`)
- **Evidência:** `detail = String((await response.json()).detail || detail)`; em 422 o `detail` é uma **lista** de objetos.
- **Reprodução (executada):** `POST /game/new` com `class_name:"Xyz"` → `422 {'detail': [{'type':'value_error','loc':['body','class_name'],'msg':'Value error, classe desconhecida',...}]}`; `node -e 'console.log(String([{type:"x"}]))'` → `[object Object]`. Mesmo para `action_id` inválido em `/game/action`.
- **Impacto:** banners "Falha ao criar personagem: [object Object]" / "Ação não confirmada: [object Object]" (CreateScreen, prólogo, levelup, busca de crônica) — o jogador não sabe o que corrigir.
- **Correção sugerida:** em `errorFor`, se `Array.isArray(detail)` juntar `msg` (e `loc.slice(1)`) dos itens; senão `String`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `web/tests/http.test.mjs` (nenhum caso com detail em lista)

### BUG-07-03 — Simulação de combate FINALIZADA ainda aceita ações via API (XP, viagem, arquivista/RAG)
- **Severidade:** média
- **Categoria:** regra-divergente
- **Local:** `api.py:3319-3339` (`_execute_action`), `api.py:3168-3203` (`_apply_action_options`), `main.py:120-130`
- **Evidência:** o contrato da SPEC-090 ("sem XP, loot, memória ou avanço de campanha") só é imposto no cliente (`simulationFinished` desabilita input). `_execute_action` rejeita memorial/archived/death_pending, mas não `combat_simulation.finished`; com combate inativo `_apply_action_options` retorna cedo e o texto vai ao grafo completo (router→storyteller→archivist).
- **Reprodução (executada, MockLLM, saves em memória):** criar sim (nível 10, Aranha Lobo), `action_kind=attack` até `finished:true outcome:victory` (1 turno); depois `POST /game/action {"input_text":"Viajo para Brekmar e descanso"}` → 200; estado antes `xp 0, loc "Arena do Véu", turn 1` → depois `xp 150, loc "Brekmar", turn 2, archivist_last_run 2`; log: `[RAG] Memória salva ... +1 fatos`, `[ARCHIVIST] Fatos: ['Aranha Lobo se rendeu.']`. (O diretório `data/saves_memory/<id>` criado pela repro foi removido.)
- **Impacto:** o laboratório "isolado" vira campanha real com XP/memória; qualquer cliente de API (ou botão de mapa do HUD se houver nó visitado) rompe o isolamento.
- **Correção sugerida:** em `_execute_action` (e `/game/equip|levelup`): `if combat_simulation.enabled and not combat.active → 409 "Simulação encerrada."`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_combat_simulator.py::test_endpoint_cria_e_turno_livre_usa_ataque_basico_sem_llm_ou_rag` (só turno com combate ativo)

### BUG-07-04 — `/game/chronicle/export` devolve 500 para nomes com caracteres fora de latin-1
- **Severidade:** média
- **Categoria:** exceção-engolida / contrato-api
- **Local:** `api.py:3735-3738`
- **Evidência:** `hero = "".join(c for c in name if c.isalnum())` aceita letras Unicode (cirílico, "ł", CJK…) e vai direto num header `Content-Disposition`; Starlette codifica headers em latin-1.
- **Reprodução (executada):** save com `player.name="Дмитрий"` → `GET /game/chronicle/export?game_id=...` → `UnicodeEncodeError: 'latin-1' codec can't encode characters` → 500 (com "Éowyn" funciona).
- **Impacto:** o botão "Exportar crônica" quebra para qualquer herói com nome fora de latin-1 (nome é texto livre de até 80 chars).
- **Correção sugerida:** `unicodedata.normalize("NFKD")` + manter só ASCII `[A-Za-z0-9]` no `filename=`, e/ou `filename*=UTF-8''<urlquote>`.
- **Confiança:** confirmado por execução
- **Testes existentes relacionados:** `tests/test_polish_sessao.py` (export só com nomes latin-1)

### BUG-07-05 — localStorage sem guarda: tela branca / jogo impossível quando o storage está bloqueado
- **Severidade:** média
- **Categoria:** exceção-engolida
- **Local:** `web/src/App.tsx:76` (`useRef(localStorage.getItem(LS_KEY))` no render), `:152,178,237,269,314,590,614`; `pendingOperation.ts:35`
- **Evidência:** só `loadPending` tem try/catch. `localStorage.getItem` no corpo do componente lança `SecurityError` com "bloquear todos os dados de site"; `setItem` em `onTurn` idem.
- **Reprodução:** hipótese (sem browser aqui); caminho: `App()` lança no 1º render → React desmonta a árvore (não há ErrorBoundary).
- **Impacto:** app não abre / `handleAction` sempre falha ("Ação não confirmada") em navegadores com storage bloqueado. `preparePending` lança de propósito ("não enviar se persistir falhar"), mas sem fallback em memória o jogo fica inutilizável.
- **Correção sugerida:** helper `safeStorage` (try/catch + Map em memória) em todos os acessos; no pending, degradar para memória da aba.
- **Confiança:** hipótese
- **Testes existentes relacionados:** nenhum

### BUG-07-06 — 404/409 não-recuperável deixa o pending preso (memorial, arquivado, jogo apagado)
- **Severidade:** baixa
- **Categoria:** ui-estado
- **Local:** `web/src/App.tsx:540-544`
- **Evidência:** `clearPending` só para 400/422; 404 (save apagado) e 409 memorial/arquivado mantêm o pending, e o botão "Consultar / retomar ação pendente" reaparece a cada abertura do save, sem ação possível.
- **Reprodução:** por leitura — enviar ação num save `game_over` (outro dispositivo); o evento `error` code 409 deixa o pending em localStorage.
- **Impacto:** botão persistente enganoso; novo texto bloqueado (mesmo mecanismo do BUG-07-01).
- **Correção sugerida:** limpar pending para 404/409 de memorial/arquivado/jogo inexistente; ou oferecer "Descartar".
- **Confiança:** provável
- **Testes existentes relacionados:** nenhum

### BUG-07-07 — Typewriter cortado em 300 ms quando o turno chega pelo caminho POST (sem chunks)
- **Severidade:** baixa
- **Categoria:** ui-estado
- **Local:** `web/src/App.tsx:317-326` (`onTurn`), `web/src/hooks/useTypewriter.ts`
- **Evidência:** `onTurn` marca `streaming:false` após 300 ms; com `enabled=false` o hook faz `setDisplayedText(text)` (texto completo) — a animação leva ~30 ms por 1-8 chars (vários segundos para 1 000 chars). Vale para fallback POST, `/game/new` e simulador. Entradas de histórico também renderizam "" por 1 frame.
- **Impacto:** cosmético — animação some após 0,3 s.
- **Correção sugerida:** derivar `streaming:false` do fim do typewriter (callback) ou `useState(enabled ? "" : text)`.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum

### BUG-07-08 — Chip da Carga do Abismo do Médico mostra "algo se acumula…" mesmo com Carga 0
- **Severidade:** baixa
- **Categoria:** ui-estado
- **Local:** `api.py:1188-1195` (`_abyss_tier_view`), `web/src/components/Hud.tsx:604-616`
- **Evidência:** classe com `abyss.hidden` devolve sempre tier `"?"`; `AbyssChip` só oculta `"nenhum"`, então o chip aparece desde o nível 1 afirmando acúmulo inexistente.
- **Correção sugerida:** `_abyss_tier_view` retornar `"nenhum"` quando `abyss_charge == 0` e `"?"` só com carga > 0.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum (checar `tests/test_classes_refactor.py`)

### BUG-07-09 — `backstory: null` vira o texto "None" no resumo narrativo inicial
- **Severidade:** baixa
- **Categoria:** contrato-api
- **Local:** `api.py:842,2705`
- **Evidência:** `backstory: Optional[str] = Field("", ...)` aceita `null`; `f"... {req.backstory}"` gera `"A jornada de X começa em R. None"`, e `char_input["backstory"]=None` segue para creator/prólogo.
- **Reprodução:** por leitura (o cliente web sempre envia `""`).
- **Correção sugerida:** `backstory: str = Field("", max_length=2000)` ou `req.backstory or ""`.
- **Confiança:** confirmado por leitura
- **Testes existentes relacionados:** nenhum

---

## Descartados / falsos positivos / cobertos por outras specs
- **types.ts × payload:** `GameResponse`, `PlayerStats`, World/Combat/Enemy/Card/Death/Continuity/Party/Faction/Save/LevelUp/Visual* conferidos campo a campo; só há campos extras do servidor sem tipo (`QuestBlock.main.objective_source/objective_quest_id`, `WorldBlock.weather_global`, `NpcView.home_location_id/in_scene/knowledge_source/revealed_traits`, `CombatBlock.initiative`, `ChronicleChapter.entry_count`) — sem impacto de runtime.
- **`xp_next_level` no nível máximo:** `progression.xp_to_next` devolve `None` no cap e o Hud trata `!= null`; não existe barra de XP (só texto) — OK.
- **Duplo clique em "Agir":** `busy` é setado antes dos awaits e `preparePending` reaproveita `operation_id` — sem 2º turno.
- **Replay de `action_id` no perfil legacy** devolve `format_response(state)` atual (não o recibo original): só diverge se o id for reenviado após outros turnos — não alcançável pelo cliente.
- **`rpg_sse_first_event_seconds` medido no mesmo instante:** coberto por SPEC-200.
- **Select "Alvo" do CardHand ignorado em ataque básico/manobras e cura sem alvo curando inimigo (`target_id` default = 1º inimigo):** cobertos por SPEC-205 / SPEC-199 R12.
- **Rascunho do composer, mdLite/dangerouslySetInnerHTML, `/data/map` com locais não descobertos, codex com ocultos:** SPEC-204 / 211 / 210 / 206.
- **`record_history` (chave game+epoch+turn+role):** `turn_count` avança em todo turno e `epoch` muda no restore — sem colisão observada.
- **`_reject_archived` duplicado em `/game/death`:** redundância inofensiva.
- **Rate-limit 429:** corpo `{"detail": "..."}` string, entendido por `errorFor`.
- **Modais:** `showLevelUp` exclui `blocked`/`fighting`; DeathModal precede level-up (levelup 409 em `death_pending`); botão "⬆ Nível!" é no-op em combate (UX, não estado).
- **Voice controller:** geração/abort corretos; sem setState pós-unmount (cleanup `cancel(false)`).
- **`player_reaction_card_id` stale entre combates:** limpo em `agents/combat.py:1051`.
- **Saves arquivados listados como jogáveis em `SaveScreen`** (`list_saves` não expõe `archived`): possível melhoria, abrem e recebem 409 com mensagem clara — não registrado como bug.
