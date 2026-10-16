# SPEC-209 — Menu Combate (deck fora de encontro) e menu Personagem (ficha/Jornada)

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-203 `done` (desfecho), SPEC-204 `done` (shell), SPEC-205 `done` (gesto), SPEC-208 `done` (tokens), SPEC-227 `done` (inventário/equipamento íntegros) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-212 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15`, prompt 06 (partes Combate e Personagem)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `true` — jornadas frontend novas (deck fora de combate: preparar/evoluir/rejeição; Personagem: ficha/Jornada/retrato/reload) em `evals/` e Playwright F-series; autoria em tarefa separada, nunca pelo executor desta spec.

---

## 1. Contexto & Objetivo

[D] O produto é chat-first; abas são superfícies de consulta/ação (`DECISOES_PRODUTO.md`). A SPEC-204 cria o shell (chat / uma aba / chat + uma aba, 5 abas) e a SPEC-205 faz o combate por gesto. Esta spec define o **conteúdo** de duas abas: **Combate** fora de encontro (coleção/Acervo, mão preparada, evolução, Ruptura, frequência) e **Personagem** (ficha completa + seção "Jornada").

[F] Hoje a ficha vive em `web/src/components/Hud.tsx` (`FichaTab`, ~l.125; Virtudes, Vitalidade, Entropia, `AbyssChip`, inventário com equipar/desequipar via `POST /game/equip`). `CombatTab`/`Combat` (~l.474/494) só renderiza durante encontro. `CardHand.tsx` mostra apenas cartas **preparadas** em combate. `LevelUpModal.tsx` escolhe Carta/evolução/Virtude via `POST /game/levelup`. `GeneratedPortrait.tsx` recebe `gameId`/`generationId`. `Hud` auto-troca de aba (`setTab("combate")` ao lutar, volta a `"ficha"`) — comportamento a ser substituído pelo shell da SPEC-204.

[F] Backend: `api.py::_cards_block(player, prepared_only=False)` já devolve, por carta conhecida: `id,name,type,description,effect_kind,target_kind,subclass,prepared,cost,base_cost,frequency,spent,ready,has_rupture,rupture_ready,trigger,evolved`. `GameResponse`/`/game/state` expõe `player_stats.cards` e `level_up` (`_levelup_block`: `prepared_slots`, `unlocked_tier`, `evolvable`, `virtue_cards`). `services/cards.py` tem `can_reorganize(state)` (fora de combate, perigo ≤3, sem tag `apex`), `set_prepared(state, prepared)` (valida subconjunto do Acervo e limite por nível) e `evolve_card`. **[F] Lacuna: não existe endpoint que chame `set_prepared` fora do level-up** (grep `prepar` em `api.py` não acha rota; `set_prepared` só é usado por testes/fluxos internos). Logo preparar cartas fora de combate exige contrato aditivo (R4).

[F] `wounds`/`ferimentos` (leve/grave/critico) saem em `format_response` (`api.py` ~l.1483–1500) e `WoundTrack.tsx` existe. [F] Cicatrizes: `services/death_flow.py::generate_scar` anexa em `participant['scars']` dicts `{id, consequencia_negativa, habilidade_positiva_relacionada, origem}` (**sem turno**); `api.py` **não** expõe `scars` hoje (grep `scars` em `api.py`/`web/src/types.ts` vazio).

[F, revisão] `can_reorganize` lê o perigo de `world.danger_level` e a tag `apex` de `state["_location"]`, mas **nenhum caminho de produção injeta `_location`** (grep em `api.py`/`agents/`/`services/` só acha `services/cards.py`). Logo hoje a restrição `apex` é inerte fora de testes; a rota R4 precisa injetar `state["_location"] = gamedata.get_location(world.current_location_id)` numa cópia antes de chamar `set_prepared`/`can_reorganize`.

Objetivo: duas abas completas, usáveis em tela inteira e em split 50/50, que mostram estado canônico e só alteram o que o backend autoriza.

## 2. Requisitos

### Aba Combate (fora de encontro)
- **R1** — Fora de encontro (`combat.active` falso) a aba Combate exibe: **Acervo** (todas as `known_cards`), **Preparação** (`prepared_cards` com `prepared_slots` usados/limite), filtro por tipo (ativa/reação/passiva) e por subclasse; carta mostra custo real (`cost`, `base_cost` se divergir por Dependência), frequência (`frequency`) e se está `spent`, Ruptura (`has_rupture`) e evolução (`evolved` A/B). Dados vêm exclusivamente de `player_stats.cards`/`level_up`; o cliente não recalcula custo nem frequência.
- **R2** — Em encontro ativo a aba Combate hospeda a UI tática da SPEC-205 (mão, zonas, reação; alvos por `participant_id` = `enemy.id` do manifesto da SPEC-203); esta spec não a redesenha. Ao término do encontro (SPEC-204 R10: a aba Combate permanece aberta), a aba mostra o painel de desfecho da SPEC-203 (`combat_result`) até o jogador navegar ou o próximo turno começar, e então volta à visão de deck; XP/nível ganho é lido de `turn_outcome` (SPEC-199), nunca da prosa. A transição fora→dentro de encontro não perde seleção de filtro nem posição de scroll da coleção (estado local, ver §3.3).
- **R3** — Passivas e reações de **Virtudes** (`virtue_cards`, `effective_stage`) e passivas de classe (`player_passives`, se expostas) aparecem em seção própria "Passivas e Reações", somente leitura.
- **R4** — Preparar/trocar cartas só é oferecido quando o servidor autoriza. Contrato aditivo `POST /game/cards/prepare` `{game_id, prepared: [card_id], action_id}` → chama `services.cards.set_prepared` (validação 100% Python: fora de combate, zona segura, subconjunto do Acervo, limite do nível) e responde `{ok, prepared_cards, cards, prepared_slots}`; erro → 400/409 com mensagem do motor, save intocado. A rota injeta `_location` (ver §1) numa cópia transitória do estado antes de validar, e o campo `_location` **não** é persistido no save (teste dedicado). Rejeitada por `death_pending`/arquivado/memorial também. Perfil `combat_simulation` (SPEC-090) → 409 (o laboratório não tem preparação persistente). Usa o mesmo padrão de `game_equip` (lock por `game_id`, `_begin_state_mutation`/`_commit_state_mutation`, `_reject_archived`, `_reject_memorial`, 409 se `death_pending`, idempotência por `action_id`).
- **R5** — `GET /game/state` ganha `player_stats.can_reorganize: {allowed: bool, reason: str}` (derivado de `can_reorganize`, com razão pt-BR: "em combate", "local perigoso") para a UI desabilitar controles com explicação, sem tentar-e-falhar. [H] precisa do local resolvido (`state["_location"]` é injetado em `can_reorganize`; verificar como `format_response` o obtém).
- **R6** — Evolução A/B (nível ≥4, única por carta) e escolhas de level-up continuam pelo `LevelUpModal`/`POST /game/levelup`; a aba Combate exibe `evolvable` com atalho "Evoluir" que abre o mesmo modal (sem segundo caminho de escrita). Evolução já feita aparece como selo A/B imutável.
- **R7** — Sem confirmação repetitiva: arrastar/clicar para preparar aplica direto (otimista com rollback visível se o servidor rejeitar); um toast/linha de erro explica a rejeição (`aria-live`).

### Aba Personagem
- **R8** — Ficha: nome, classe, subclasse, raça, nível, XP/`xp_next_level`; Virtudes (0–5); Vitalidade com `WoundTrack`; Ferimentos por gravidade; Entropia/`max_entropy`; Carga do Abismo por patamar (`abyss_tier`; Médico oculta valor — respeitar `"?"`); equipamento/inventário com equipar/desequipar (`POST /game/equip`, só fora de `death_pending`).
- **R9** — Cicatrizes (permanentes, morte rica): `player_stats.scars: [{id, origem, consequencia_negativa, habilidade_positiva_relacionada}]` projetado de `player.scars` (campo já persistido; projeção aditiva, sem migração). Sem cicatriz → seção ausente (nunca placeholder inventado). Turno de origem **não** existe no dado e não é exibido nem inventado.
- **R10** — Retrato: `GeneratedPortrait` identificado por ID canônico do jogador (`portrait_generation_id` do `GameResponse`); sem retrato gerado → capa de raça/classe do catálogo visual (`creation_visuals`, SPEC-094) ou placeholder honesto. Nunca inferir imagem inexistente; URL assinada expirada → refetch uma vez (`GET /game/{game_id}/art/{generation_id}`) e então fallback; testado após reload.
- **R11** — Seção **"Jornada"** (D1: Missões vira seção de Personagem): quest ativa/side quests (`data.quest`, componente `QuestsTab` reaproveitado), histórico de evolução (escolhas de level-up/subclasse/evoluções a partir do `event_log`/crônica via campos já públicos) e marcos recentes. Facções e Crônica **não** entram aqui (D1 → Codex, SPEC-211).
- **R12** — Visibilidade: nada de beats/climax privados (SPEC-115 já entrega objetivo público); a Jornada usa só a view pública da quest.
- **R13** — Ambas as abas: layout utilizável em tela inteira e em ~50% (sem scroll aninhado: uma única região rolável por aba, cabeçalho fixo); consistentes após turno, reload, troca de save e atualização assíncrona (versão/`turn_count` no cabeçalho da aba; dado atrasado nunca vira "fato inexistente" — mostra "atualizando…").
- **R14** — Acessibilidade: operável por teclado (preparar via Enter/Espaço + setas), foco visível, `aria-live` para erros/aplicação, `prefers-reduced-motion` respeitado (MotionConfig já global), alvo ≥44px.
- **R15** — Arte de carta: o catálogo visual (`services/visual_catalog.py`, 45 assets públicos) não tem arte de Carta; `DeckCard` usa só ícone/selo por `type`/`effect_kind`, sem placeholder de "ilustração" que sugira arte inexistente. Se um catálogo de cartas surgir, entra por ID canônico (`card_id`) em spec própria.

### Fora de escopo
Redesign da UI tática em encontro (SPEC-205); shell/split/resize (SPEC-204); manifesto/desfecho (SPEC-203); Codex/Bestiário/Facções/Crônica (SPEC-211); Mapa (SPEC-210); mobile single-pane (SPEC-216); novas cartas/balanceamento; nova mecânica de recuperação; geração de imagem nova (quote/confirm já existem, SPEC-188); editar evaluator/dataset.

## 3. Design técnico

### 3.1 Arquivos
- **Novo** `web/src/components/tabs/CombatDeckTab.tsx` — coleção/preparação/passivas; embute a UI tática da SPEC-205 quando `combat.active`.
- **Novo** `web/src/components/tabs/CharacterTab.tsx` — ficha + `JourneySection`.
- **Novo** `web/src/components/tabs/DeckCard.tsx` — carta (selo de frequência/Ruptura/evolução, estado `spent`/`ready`/`prepared`).
- **Alterados** `Hud.tsx` (extrair `FichaTab`/`CombatTab`/`Combat` para os novos arquivos; o shell da SPEC-204 monta as abas), `types.ts` (`can_reorganize`, `CardView` já existe), `api.ts` (`prepareCards`), CSS novo em arquivo próprio (ex.: `web/src/components/tabs/tabs.css`, padrão SPEC-204 R14 — `styles.css` não recebe regras novas, para reduzir conflito com SPEC-197), consumindo os tokens da SPEC-208.
- **Alterados backend** `api.py` (rota `POST /game/cards/prepare`, modelo `PrepareCardsRequest`, campo `can_reorganize`), eventualmente `services/cards.py` (helper `reorganize_status(state) -> (bool, str)` reutilizando `can_reorganize`).
- **Novos testes** `tests/test_cards_prepare_api.py`; Playwright em `web/` (jornadas, autoria separada).

### 3.2 Contratos de dados
- `PrepareCardsRequest {game_id: str, prepared: list[str], action_id: str}`; resposta `{ok: true, prepared_cards: list[str], cards: CardView[], prepared_slots: int}`; erros: 400 (carta fora do Acervo / acima do limite), 409 (combate/zona perigosa/queda pendente/arquivado/memorial), 404.
- `can_reorganize: {allowed: bool, reason: string}` aditivo em `player_stats`; clientes antigos ignoram.
- Sem mudança de schema de save (`prepared_cards` já existe). Se cicatrizes precisarem de campo novo, migração + round-trip (ver §7).

### 3.3 State ownership
- Fonte da verdade: servidor/save. Cliente guarda só estado de UI efêmero (filtro, seleção, scroll) por `game_id`, sem persistir dados de jogo; a edição de preparação é otimista e reconciliada com a resposta do servidor.
- Draft/histórico do chat pertencem ao shell (SPEC-204); trocar de aba não os toca.

### 3.4 Degradação
- Backend sem `can_reorganize` (versão antiga) → controles de preparar ocultos, coleção somente leitura. `cards` vazio → estado vazio explicativo. Falha de retrato → fallback R10. Falha de rede em `prepare` → rollback + mensagem; nenhum estado local divergente.

## 4. Plano (TDD)
1. Testes de API (`tests/test_cards_prepare_api.py`, MockLLM, offline): `test_prepare_ok_persiste_e_reload`; `test_carta_fora_do_acervo_400`; `test_excede_limite_400`; `test_em_combate_409`; `test_zona_perigosa_409`; `test_apex_409_com_location_injetada` (local com tag `apex` e `danger_level` ≤3 → 409); `test_location_transitoria_nao_persistida`; `test_simulacao_409`; `death_pending`; replay de `action_id` idempotente; save intocado em erro; `can_reorganize` no `/game/state`.
2. Implementar rota + `can_reorganize` + helper em `services/cards.py`.
3. Projetar `player.scars` em `player_stats.scars` (R9): `test_scars_projetadas`, `test_save_sem_scars_carrega_sem_secao`.
4. Testes Node/componentes de `DeckCard`/`CombatDeckTab`/`CharacterTab` (estados: preparada, `spent`, sem slot, não autorizado).
5. Extrair componentes do `Hud.tsx` sem mudar comportamento (refactor protegido por testes existentes: 18 Node + build).
6. Implementar abas, ligar ao shell da SPEC-204 (remover auto-troca antiga).
7. Playwright 390/1440 e split 50%: jornadas listadas em §6 (autoria de eval em tarefa separada).
8. `/qa`, `uv run pytest`, `npm run build`, atualizar ESTADO_ATUAL/ROADMAP, registrar evidência.

## 5. Critérios de aceite
- [ ] Fora de combate, Acervo e Preparação aparecem com custo/frequência/Ruptura/evolução idênticos ao payload do servidor.
- [ ] Preparar/trocar carta em local seguro persiste e sobrevive a reload; em combate/zona perigosa o controle está desabilitado com razão exibida e o servidor também rejeita (409).
- [ ] Preparar acima do limite ou carta fora do Acervo é rejeitado pelo servidor sem alterar o save.
- [ ] Evoluir A/B só via `LevelUpModal`; segunda evolução da mesma carta bloqueada (já coberto no motor).
- [ ] Personagem mostra Virtudes, Vitalidade/Ferimentos, Entropia/Carga (Médico oculto), equipamento funcional, retrato canônico com fallback.
- [ ] "Jornada" mostra quest pública e histórico de evolução; nenhum beat privado visível.
- [ ] Nenhum scroll aninhado em 50%; teclado completo; axe sem violações serious/critical em 320/390/768/1440.
- [ ] Troca de save e reload não mostram dados do jogo anterior.
- [ ] `POST /game/cards/prepare` rejeita local `apex` (com `_location` injetada) e não persiste `_location`.
- [ ] Pós-encontro, a aba Combate exibe `combat_result` (SPEC-203) e XP de `turn_outcome` (SPEC-199), sem número de XP vindo da prosa.
- [ ] `uv run pytest` verde; `npm run build` verde; saves antigos (sem `scars`) carregam.

## 6. Smoke
- Offline: `uv run pytest tests/test_cards_prepare_api.py` e suíte completa; `cd web && npm run build && npm test`.
- Browser (API determinística, sem provider): criar jogo → Combate → preparar/trocar carta → reload → persistiu; forçar `combat.active` → controles desabilitados; Personagem → equipar/desequipar → retrato após reload.
- Provider real: não necessário (mecânica determinística). Se desejado, opt-in com teto explícito de 20 requests/US$ 0,20.

## 7. Riscos & compatibilidade
- **Saves:** sem mudança obrigatória; cicatrizes só se campo novo — migração + teste round-trip com save antigo. API aditiva; frontend novo tolera backend antigo (R5/§3.4).
- Conflito de merge em `Hud.tsx`/`styles.css` com SPEC-197 (trabalho não commitado) e com SPEC-204/205: executar só após 204/205 `done` e rebase.
- [R] Preparar cartas em qualquer momento abriria exploit tático; por isso a regra `can_reorganize` do motor é mantida sem relaxar.
- Retratos: URL assinada expira (R10); `GeneratedPortrait` já trata, só validar no reload.

## 8. Pontos de decisão do dono
1. **Reorganizar fora de zona segura?** Default [R]: manter a regra atual (perigo ≤3, sem `apex`); a UI explica o bloqueio. Relaxar muda gameplay.
2. **Cicatrizes visíveis?** Default [R]: exibir (projeção aditiva de `player.scars`, já persistido; sem migração).
4. **Ativar a restrição `apex` (hoje inerte)?** Default [R]: sim, injetando `_location` na rota nova — é a regra já escrita no motor; não ativá-la equivale a relaxar gameplay sem decisão. Alternativa: manter só `danger_level ≤ 3` e registrar a divergência.
3. **Histórico de evolução:** default [R]: derivado de eventos públicos já existentes; sem novo log.

## 9. Evidência requerida
Saída de `uv run pytest` e `npm run build`/Node; relatório Playwright com screenshots 390/1440 e split 50% (aba Combate fora de encontro, Personagem); amostra de payload `/game/state` com `can_reorganize`; resposta 400/409 de `/game/cards/prepare`; handoff de eval (`EVAL_AUTHORING_REQUIRED`) registrado em `handoffs/`.
