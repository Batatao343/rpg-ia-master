# SPEC-210 — Menu Mapa e viagem como turno

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-17
> **Depende de:** SPEC-204 `done` (shell), SPEC-208 `done` (tokens), SPEC-229 `done` (detecção de viagem), SPEC-233 `done` (perigo efetivo) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-212 (ordem final 2026-10-15)
> **Origem:** pacote `docs/historico/proximas-specs/pacote-prompts-rpg-beta-2026-10-15`, prompt 06 (parte Mapa)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `true` (corrigido na revisão) — F06 `map_travel` clica o nó "Brumalta" e espera viagem imediata, e F13 expira sessão concorrendo com `GET /data/map` (`web/e2e/critical-journeys.spec.ts` l.103/208); o `DeterministicBackend` (`web/e2e/fixtures.ts` l.180) só serve `/data/map`. Com `GET /game/map`, painel de detalhe e botão Viajar separado (R6/R10), F06/F13 e o backend determinístico precisam ser adaptados por tarefa de eval separada (handoff `handoffs/SPEC-210-eval-authoring.md`), sem relaxar asserts; o executor desta spec não edita esses arquivos.

---

## 1. Contexto & Objetivo

[D] Mapa é uma das 5 abas (Codex, Personagem, Combate, Bestiário, Mapa); mostra "regiões e interiores conhecidos, fog of war, viagens/risco/distância conforme estado canônico". Viajar acontece pelo chat: nunca teletransporte (`DECISOES_PRODUTO.md`, prompt 06).

[F] Estado atual: `web/src/components/WorldMap.tsx` recebe `visited`, `currentId`, `controlled`, `dangerOverrides`, `markers` (alvos de quest), `overlays`, `blockedRoutes` e `onTravel`; nós não visitados têm classe `.is-fog`, label `???`, `aria-label="Região inexplorada"`, `disabled`. Viajar = `PlayScreen.tsx` ~l.153: `onTravel={(name) => onAction(\`Viajo para ${name}\`)}` — texto livre que passa pelo grafo normal. O backend decide: `world_utils.find_travel_destination`/`apply_travel`/`travel_cost` (`travel_times` por nó, fallback simétrico, interior = 0), e `agents/router.py::_combat_gate` converte viagem em fuga com combate ativo (SPEC-038). Interiores (SPEC-027) não aparecem em `GET /data/map` (filtra `kind == "interior"`); são expostos como `world.interiors` ("Locais daqui") em `/game/state` (`_interiors_block`).

[F, **achado de privacidade**] `GET /data/map` (`api.py` ~l.1903) devolve **todos** os locais não interiores com `name`, `coords`, `danger`, `lore_seed` e `travel_times` para qualquer cliente; o fog é aplicado só no React. Nomes/perigo/lore de locais não descobertos trafegam pela rede. Para o beta ("sem revelar locais não descobertos"), isso é vazamento de conhecimento do jogador.

[F] `services/visual_catalog.py` expõe `scene_visual(world)` (arte do local **atual**, escopo `exact|regional|placeholder`) e `visual_for("location", id)`; não há hoje arte por local no mapa nem lista de locais descobertos com arte.

[F, revisão] Adjacência é o campo `connections` de cada nó de `data/world_map.json` (`gamedata.get_connections`). `world_utils.find_travel_destination` só aceita destino **conectado** ao local atual e casa o texto da ação pelo `name` (fold de acento/caixa) **ou** pelo `id`. Hoje o cliente desabilita o botão de qualquer nó não visitado (`WorldMap.tsx` l.118, `disabled={!known || …}`), então pelo mapa só se viaja a visitados; nó visitado mas não conectado gera uma ação que o backend não reconhece como viagem.

[F] Lacunas de UX: o botão do nó não mostra tempo de viagem (`travel_cost` não é exposto), não distingue rota inexistente/bloqueada/inalcançável a partir do local atual, e não há painel de detalhe do local.

Objetivo: aba Mapa utilizável em tela cheia e em 50%, com fog honesto (cliente só recebe o que o jogador descobriu), custo de viagem visível e viagem que continua sendo um turno normal do chat.

## 2. Requisitos

- **R1 — Fog server-side.** Nova view `GET /game/map?game_id=` (default [R]: endpoint dedicado, para não inflar todo `/game/state`; mesmo guard de `_resolve_save_file`, 404 sem save, sem `Cache-Control` público) devolve apenas: locais **visitados** com `id,name,region_id,coords,danger(efetivo),lore_seed`; locais **adjacentes** = `connections` do local atual ainda não visitados (`id` + `coords` + `name` apenas, ver §8.1; sem `lore_seed`/`danger`/`art`/`region_id`); nada de locais não alcançados. `GET /data/map` global permanece só por compatibilidade com CLI/legado e **deixa de ser usado** pelo cliente React do jogo (ver R12). [R] Decidir em §8 se adjacentes sem nome aparecem.
- **R2 — Estados de nó.** Cada nó é exatamente um de: `atual`, `visitado`, `adjacente` (alcançável, ainda não visitado), `desconhecido` (não enviado), `bloqueado` (rota em `blocked_routes`). Estado derivado do servidor; cliente só apresenta.
- **R3 — Custo de viagem.** Para o local atual, o servidor devolve `travel_options: [{location_id, name, periods, reachable, blocked, reason}]` **só para `connections` do local atual** (e para o pai, quando dentro de interior), computado com `world_utils.travel_cost`; nó visitado não conectado aparece no mapa com `reachable: false` e razão "sem rota direta daqui" (sem botão Viajar); interior/saída do interior = 0. UI mostra "N períodos" (rótulo pt-BR: 1 período ≈ avanço de `advance_clock`), nunca calculado no cliente.
- **R4 — Perigo e controle.** Perigo efetivo = `danger_overrides` quando houver (como `dangerOverrides` hoje); controle de facção via `controlled` (nome visível, `services.state_views.visible_controllers`); só para locais visitados. Alvo de quest via `markers` da view **pública** (SPEC-115). Ameaças/mudança de controle recentes via `map_overlays` já existentes.
- **R5 — Interiores/sublocais.** O painel de detalhe do local atual lista `interiors` ("Locais daqui") e, dentro de interior, o caminho de volta ao pai (`_interiors_block`); entrar/sair é ação de chat com custo 0, como hoje. Interiores nunca aparecem como nós do mapa-múndi.
- **R6 — Viajar = turno normal.** O botão "Viajar" envia **a mesma ação de chat** (`Viajo para <nome>`, usando o `name` de `travel_options`, que `find_travel_destination` reconhece) por `onAction`, passando por `/game/action` (ou stream) com `action_id`; nenhuma rota nova de teletransporte, nenhuma mutação de `current_location` fora do grafo. A UI mostra o turno no chat e a aba pode permanecer aberta (split) ou o shell volta ao chat em tela cheia (decisão SPEC-204; não definida aqui).
- **R7 — Gate de combate.** Com `combat.active` (ou `death_pending`/memorial/arquivado) o botão "Viajar" fica **desabilitado** com razão ("Em combate: fuga é uma ação do encontro") e, se ainda assim a ação for enviada, o backend continua convertendo em tentativa de fuga (SPEC-038, `_combat_gate`) sem mudança. A UI nunca declara viagem concluída antes da resposta do servidor.
- **R8 — Arte de local.** O painel de detalhe mostra arte por ID canônico via catálogo visual (SPEC-094): `visual_for("location", id)`; fallback `regional` (`location_fallbacks`) ou placeholder honesto, nunca arte de local não visitado. Carregamento progressivo com dimensões/alt; URL/asset expirado → um refetch e depois fallback; validado após reload. Campo `art` incluído na view de R1 **somente** para locais visitados.
- **R9 — Versão/atualização.** A view devolve `turn_count` e `map_version` (hash estável do conteúdo visível); o cliente refaz o fetch quando `turn_count` muda, mantendo o mapa anterior marcado "atualizando…" (nunca limpa para fog total durante refetch).
- **R10 — Layout.** Full e split 50%: mapa responsivo (viewBox/porcentagem de `coords`), painel de detalhe como região rolável única (sem scroll aninhado); zoom/pan simples opcional ([H] só se o mapa ficar ilegível em 50%); teclado: setas/Tab entre nós alcançáveis, Enter abre detalhe, botão Viajar separado.
- **R11 — Acessibilidade e movimento.** Estados comunicados por texto/ícone além da cor (símbolos já usados: ☗ controle, ◆ quest, ⚠ ameaça); `aria-label` por estado; `prefers-reduced-motion`; alvos ≥44px.
- **R12 — Compatibilidade.** Cliente novo usa a view de R1; se ela falhar (404/backend antigo), cai para o fog do cliente sobre `/data/map` com aviso interno apenas em log (degradação), preservando jogabilidade. Fog do cliente permanece como defesa em profundidade.

### Fora de escopo
Shell/split/resize (SPEC-204); mapa-múndi novo, novas regiões/locais, rebalanceamento de tempos; viagem em tempo real/animação de percurso entre nós além de efeito simples da SPEC-208; revelação por rumor/informação de NPC (SPEC-215); mobile (SPEC-216); geração de arte nova; mudar regras de encontros em viagem.

## 3. Design técnico

### 3.1 Arquivos
- **Backend alterado** `api.py`: rota `GET /game/map` (ou bloco `map` em `format_response`), modelo `MapView`/`MapNodeView`/`TravelOption`; reaproveita `gamedata.get_location`, `world_utils.travel_cost`, `services.state_views.visible_controllers`/`active_threats`, `services.visual_catalog.visual_for`.
- **Possível novo** `services/map_view.py` — função pura `build_map_view(state) -> dict` (testável sem FastAPI).
- **Frontend alterado** `web/src/components/WorldMap.tsx` (props passam a vir da view; estado de nó), `Hud.tsx`/shell (aba Mapa), `api.ts` (`getMap`), `types.ts` (`MapView`); CSS novo em arquivo próprio (ex.: `web/src/components/tabs/tabs.css`, padrão SPEC-204 R14 — `styles.css` não recebe regras novas, para reduzir conflito com SPEC-197), consumindo os tokens da SPEC-208.
- **Novo** `web/src/components/tabs/MapTab.tsx` — mapa + painel de detalhe + `TravelButton`.
- **Testes** `tests/test_map_view.py`; Node para `MapTab`; Playwright.

### 3.2 Contratos de dados
```
MapView {
  game_id, turn_count, map_version,
  current_id,
  nodes: [{ id, state: "atual|visitado|adjacente|bloqueado",
            name?, region_id?, coords{x,y}, danger?, ruler?, quest_target?,
            threatened?, contested?, lore_seed?, art? }],
  edges: [{ a, b, blocked }],           // só entre nós enviados
  interiors: [...],                     // reutiliza _interiors_block
  travel_options: [{ location_id, name?, periods, reachable, blocked, reason? }]
}
```
Regras: nó `adjacente` carrega só `id`/`coords`/`name` (o nome é necessário para a ação de chat de R6; ver §8.1 para a alternativa estrita); nunca `danger`/`lore_seed`/`art`; `visited` do estado vem de `world.visited`.

### 3.3 State ownership
Servidor: localização, `visited`, controle, perigo, tempo. Cliente: seleção de nó, painel aberto, zoom (UI efêmero). Viagem sempre muta estado apenas via grafo LangGraph; `onAction` é o único canal.

### 3.4 Degradação
Sem `art` → placeholder; sem `travel_options` → botão usa só o nome (comportamento atual); refetch falho → último mapa válido + "desatualizado"; erro de viagem do turno → mensagem do chat, mapa permanece na localização anterior até novo estado.

## 4. Plano (TDD)
1. `tests/test_map_view.py` (offline): `test_adjacente_e_connections`; `test_visitado_nao_conectado_unreachable`; `test_botao_texto_reconhecido_por_find_travel_destination` (para cada `travel_options[].name`, `find_travel_destination(world, f"Viajo para {name}")` devolve o mesmo id); fog (nós não visitados e não conectados ausentes do payload; adjacente só com `id/coords/name`, sem perigo/lore/arte); estados `atual/visitado/adjacente/bloqueado`; `travel_options` coerente com `travel_cost` (assimetria, interior=0, sem entrada=1); override de perigo; controle e quest só em visitados; arte só em visitados e fallback regional; `map_version` estável/mutável; save antigo sem campos.
2. Implementar `build_map_view` + rota; garantir que `GET /data/map` permanece intacto.
3. Teste de gate: com `combat.active`, enviar "Viajo para X" retorna fuga/combate sem mudar `current_location_id` (já coberto por SPEC-038; adicionar asserção de contrato na API).
4. Frontend: tipos/`getMap`, `MapTab`, estados de nó, painel de detalhe, botão com razão desabilitada, refetch por `turn_count`.
5. Teste do cliente: payload nunca renderiza nome de nó `adjacente`; botão desabilitado em combate.
6. Playwright 1440 full + 50% + reload; axe — após a tarefa de eval adaptar F06/F13 (Etapa 0 implícita, ver cabeçalho).
7. `/qa`, `uv run pytest`, `npm run build`; atualizar ESTADO_ATUAL/ROADMAP; evidência.

## 5. Critérios de aceite
- [x] Inspeção da rede: resposta do mapa de um jogo novo **não contém** nome/perigo/lore de locais não visitados nem não conectados; adjacentes só com `id/coords/name`.
- [x] `travel_options` só lista `connections` do local atual (+ pai de interior); nó visitado não conectado aparece sem botão Viajar.
- [x] Nós aparecem em exatamente um estado; atual, visitados, adjacentes e bloqueados distinguíveis sem depender de cor.
- [x] Tempo de viagem exibido bate com `world_utils.travel_cost` (teste em pares assimétricos e interior).
- [x] Clicar "Viajar" gera uma mensagem de chat e um turno normal; nenhuma mudança de localização ocorre sem resposta do turno.
- [x] Em combate/queda/memorial o botão está desabilitado com razão; ação forçada via API vira fuga (SPEC-038).
- [x] Arte de local aparece só para visitados; expiração/falha cai para regional/placeholder; reload preserva.
- [x] Mapa e detalhe usáveis a 50% sem scroll aninhado; navegação por teclado; reduced-motion respeitado.
- [x] Após turno, reload e troca de save, o mapa reflete o estado correto (sem dados do jogo anterior).

## 6. Smoke
- Offline: `uv run pytest tests/test_map_view.py` + suíte completa; `cd web && npm run build && npm test`; `bash scripts/smoke_api.sh` estendido com `GET /game/map`.
- Browser com API determinística: criar jogo → abrir Mapa → viajar a adjacente → verificar turno no chat, novo `visited`, custo exibido; repetir com combate ativo.
- Sem provider real; qualquer uso real é opt-in com teto explícito de 20 requests/US$ 0,20.

## 7. Riscos & compatibilidade
- **Saves:** nenhuma mudança (`world.visited` e `blocked_routes` já existem). Se `map_version` precisar de campo persistido, preferir derivar em tempo de request.
- Revelar "adjacentes sem nome" pode contradizer a narrativa ("Região inexplorada" é aceitável); ver §8.
- Merge: `WorldMap.tsx`/`Hud.tsx`/`styles.css` tocados por SPEC-204/197; executar após 204 `done`.
- [H] Locais descobertos por rumor/NPC (SPEC-215) precisarão de nova fonte de "descoberto"; esta spec modela só `visited` + adjacência.
- Remover dependência do cliente em `/data/map` quebra apenas o legado `frontend/` vanilla se ele reutilizar o mesmo endpoint — endpoint mantido.

## 8. Pontos de decisão do dono
1. **Adjacentes (`connections`) não visitados:** (a) default [R]: mostrar com **nome** e sem perigo/lore/arte — o nome é a "placa da estrada" e é obrigatório para que o botão gere `Viajo para <nome>` reconhecível por `find_travel_destination`; (b) estrito: não enviar adjacentes e manter o comportamento atual (viagem pelo mapa só a visitados conectados; destino novo só digitado no chat). [Correção da revisão: a versão anterior pedia adjacente **sem nome** e viagem a ele pelo botão — combinação impossível sem enviar o `id` cru na fala do jogador.]
2. **Viagem a adjacente não visitado pelo mapa:** permitir (default [R], com custo exibido) ou exigir ter sido visitado?
3. **Após clicar Viajar em split:** manter split (default [R]) ou voltar ao chat em tela cheia? (coordenar com SPEC-204).

## 9. Evidência requerida
Payload de `/game/map` de jogo novo e de jogo avançado (diff mostrando ausência de nomes não descobertos); saída de pytest/build/Node; screenshots Playwright full/50%/reload; trace de uma viagem (chat + turno + `visited`) e de uma tentativa em combate; relato de axe.

## 10. Execução (2026-10-17)

- **Defaults de decisão (§8):** 1(a) adjacentes com nome, sem perigo/lore/arte; 2 viagem a adjacente não visitado permitida, com custo; 3 split mantido (nada muda o modo).
- **Fog server-side:** `GET /game/map?game_id=` (`services/map_view.py::build_map_view`, mesmo guard de `/game/state`: UUID, 404 sem save, escopo do dono nos perfis com banco). Achado de privacidade fechado também no legado: `GET /data/map?game_id=` devolve o mesmo formato SÓ com visitados + adjacentes (adjacente sem lore/perigo/conexões); sem `game_id` segue o grafo global estático (CLI/smoke/`post_deploy_smoke`).
- **Desvios:** (1) R12: o fallback do cliente usa `/data/map?game_id=` (filtrado), nunca o grafo global; (2) `travel_gate` na view carrega a razão do gate de combate/queda/memorial/arquivado; (3) nó visitado não conectado leva `reachable:false` + `reason` no próprio nó (fora de `travel_options`); (4) interior: a âncora do mapa é o pai (`anchor_id`), interiores nunca viram nó; (5) R8: `VisualArtwork` cai para monograma em erro de imagem (sem refetch extra de URL); (6) `map_version` exclui `turn_count`.
- **Eval:** `EVAL_AUTHORING_REQUIRED` cumprido como handoff (`handoffs/SPEC-210-eval-authoring.md`); F06/F13/`DeterministicBackend` não foram editados (o fixture não serve `/game/map`, então a aba cai no fallback legado e F06 segue verde).
- Evidência: `docs/spec210/README.md`.

## 11. Revisão independente Sol (2026-10-17)

Veredito: aprovado com correções; status `in-progress` só porque F06/F13 (e, pelo 404 de `/game/map` no fixture, também F17/F18/F19) + `DeterministicBackend` dependem da tarefa de eval separada (`handoffs/SPEC-210-eval-authoring.md`). Parecer: `handoffs/SPEC-210-SOL-independent-review.md`.
- `/data/map?game_id=` devolvia o JSON cru dos visitados (`treasure` do baú curado e `travel_times` citando IDs não alcançados): agora whitelist.
- `/data/map?game_id=` ficava fora da fronteira de sessão dos perfis com banco (sem principal → 404 sempre, fallback R12 morto) e sem `no-store`: `_session_scoped_path` inclui a rota quando há `game_id`.
- Dentro de interior a saída (travel_option do pai, custo 0) ficava bloqueada por "Você já está aqui.": liberada.
- Razão de bloqueio/rótulo bloqueado em vermelho puro reprovavam contraste (axe) — mascarado porque o `allowConsole(404)` do `workspace-shell.spec.ts` deixava a aba no fallback legado; o spec agora serve `/game/map` derivado do estado do fixture (sem engolir console).
