# SPEC-209 — evidência: menu Combate (deck fora de encontro) e Personagem

## O que mudou
Backend (`api.py`, `services/cards.py`)
- `POST /game/cards/prepare` `{game_id, prepared[], action_id}` -> `{ok, prepared_cards, cards, prepared_slots}`. Valida só em
  `services.cards.set_prepared` (fora de combate, perigo <= 3, sem tag `apex`, subconjunto do Acervo, limite do nível). 409 para
  combate/zona perigosa/apex/queda pendente/memorial/arquivado/laboratório; 400 para carta fora do Acervo ou acima do limite; save intocado em erro.
  A rota injeta `_location` numa cópia transitória (`cards.with_location`) — a restrição `apex`, antes inerte, agora vale — e `_location` nunca é persistido.
  Reaproveita o `kind="equip"` da operação (o CHECK do banco não ganhou kind novo; o hash do payload difere).
- `player_stats` ganhou (aditivo, sem bump de schema): `can_reorganize {allowed, reason}`, `prepared_slots`, `subclass`,
  `scars[]` (projeção de `player.scars`; sem turno), `virtue_cards[]`, `evolvable_card_ids[]`.

Frontend (`web/src/components/tabs/`)
- `CombatDeckTab` + `DeckCard`: Acervo, Preparação n/N, filtros por tipo e subclasse, "Passivas e Reações" (somente leitura), custo real
  (`base` quando difere), frequência, Gasta, Ruptura, Caminho A/B, atalho "Evoluir" (abre o `LevelUpModal`), preparação otimista com rollback e
  erro anunciado em `aria-live`, setas + Enter/Espaço, alvos >= 44px. Montado em `CombateTab` quando não há combate ativo.
- `CharacterTab` (substitui o corpo de `PersonagemTab`): subclasse/nível/turno, WoundTrack quando há Ferimentos, Cicatrizes (só se existirem),
  retrato canônico (`GeneratedPortrait`, com refetch único se a URL assinada falhar) ou capa de classe do catálogo / monograma, e a seção
  "Jornada · Missões" (QuestsTab + "Evolução do herói" derivada dos marcos públicos da crônica). `Hud.tsx` não mudou (os painéis continuam exportados).
- CSS próprio em `tabs/tabs.css` (tokens SPEC-208; só `transform`; sem loop; reduced-motion).

## Testes
- `tests/test_cards_prepare_api.py` (15): persistência+reload, fora do Acervo, limite, combate, zona perigosa, apex com `_location`,
  `_location` não persistido, laboratório, `death_pending`, replay de `action_id`, `can_reorganize`, scars, save sem scars, campos aditivos.
- `web/tests/deck.test.mjs` (4) + ajuste do inventário em `workspaceModel.test.mjs`; `web/e2e/deck-character.spec.ts` (7, Chromium 1440/390, axe).
- Fixture `web/e2e/fixtures.ts` ganhou `POST /game/cards/prepare`.

## Limites / desvios
- `reaction.present` (adiado pela SPEC-208) NÃO foi feito: exige janela de gatilho de reação emitida pelo backend; hoje a reação é declarada junto da ação.
- Jornadas F (eval): autoradas (F25–F29, abaixo).
- "Histórico de evolução" cobre nível e subclasse (marcos públicos da crônica); evoluções de Carta A/B aparecem como selo no deck, não na Jornada.
- R13: "atualizando…" no cabeçalho do deck (salvando ou turno em andamento) e da ficha (turno em andamento); preparar fica bloqueado nesse intervalo.
- Defaults de decisão do dono usados: reorganizar só em zona segura (perigo <= 3, sem apex); cicatrizes visíveis; apex ativado; histórico derivado sem log novo.

## Revisão Sol (2026-10-17)
- Rota `/game/cards/prepare` adicionada ao rate limit (teste `test_prepare_entra_no_rate_limit`).
- `kind="equip"` reaproveitado: seguro — recibo indexado por (owner, operation_id, game, kind, request_hash); payloads distintos → mesmo action_id em outra rota = 409 `operation_request_mismatch`. Teste `infra_local` `test_prepare_cards_shares_equip_kind_without_key_collision` (skip offline). Sem migration.
- Playwright (Chromium, `--workers=1`): axe 320/768 nas duas abas, split 50% com no máximo uma região rolável por aba, R13 com servidor atrasado; 65 testes verdes em deck-character/workspace-shell/combat-gesture/combat-outcome/critical-journeys.
- Evidência: `evidence/1440-split50-combate.png`, `evidence/1440-split50-personagem.png`, `evidence/390-combate.png`, `evidence/390-personagem.png`.

## Jornadas F (autoria de eval separada, 2026-10-17)
- `web/e2e/critical-journeys.{yaml,spec.ts}`: F25 `deck_prepare_persist` (1 request `POST /game/cards/prepare` com `prepared` completo, servidor
  confirma, custo base, reload persiste), F26 `deck_rejection_limit` (409: rollback `aria-pressed=false`, `.deck__msg`, save intocado; terceira carta
  `aria-disabled` com "limite de 2", zero request), F27 `deck_blocked_context` (`can_reorganize.allowed=false`: razao em `.deck__note`, zero request;
  combate ativo esconde o deck), F28 `deck_keyboard` (setas/Enter, sem overflow 320/390/768), F29 `character_sheet_journey` (subclasse, Cicatrizes so
  quando existem, retrato/fallback, Jornada com "Evolução do herói" so de marcos, reload). Guards console/pageerror/5xx/requestfailed e Axe serious/critical.
- Nao coberto: fluxo "Evoluir" (abre o `LevelUpModal` automaticamente com escolha pendente; ja coberto por F11 e `LevelUpModal`), `reaction.present`.
- `scripts/frontend_eval_report.py` reconhece F01-F29 (`JOURNEY_COUNT = 29`); evaluator 1.9.0 -> 1.10.0; lock refeito por `python -m evals.core.governance lock`
  (datasets inalterados); `governance check` verde. Publicar exige aprovacao do environment `eval-governance`.
- Playwright Chromium `--workers=1` (portas 4198/8198, config temporaria removida): critical-journeys 29/29 (F13 falhou uma vez por
  `fonts.googleapis.com` ERR_CONNECTION_CLOSED, passou na repeticao isolada) + deck-character 12/12.
