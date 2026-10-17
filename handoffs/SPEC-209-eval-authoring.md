# SPEC-209 — handoff EVAL_AUTHORING_REQUIRED

Jornadas frontend novas para `web/e2e/critical-journeys.yaml` (+ `critical-journeys.spec.ts`,
`evals/metrics-registry.yaml`, `evals/manifest.lock.json`). O executor NAO editou arquivos protegidos.
Os testes do executor (nao substituem as jornadas F) estao em `web/e2e/deck-character.spec.ts`
e `web/tests/deck.test.mjs`, `tests/test_cards_prepare_api.py`.

Jornadas sugeridas:
- **Deck fora de combate**: aba Combate -> "Preparação n/N" -> clicar carta do Acervo (`<nome>, <tipo>, <custo> de Entropia, ...`,
  `aria-pressed`) -> 1 request `POST /game/cards/prepare` com `prepared` completo -> reload -> persistiu.
- **Rejeição**: servidor 409/400 -> rollback visual (`aria-pressed=false`), mensagem em `.deck__msg` (aria-live), save intocado.
- **Bloqueio por contexto**: `player_stats.can_reorganize.allowed=false` -> cartas `aria-disabled`, razão em `.deck__note`, zero request.
- **Limite**: terceira carta com `N=2` fica `aria-disabled` com "limite de 2 Cartas preparadas", zero request.
- **Evolução**: com `pending_choices` e carta em `evolvable_card_ids`, botão "Evoluir" abre o `LevelUpModal` (sem 2º caminho de escrita).
- **Personagem**: ficha (Virtudes, Vitalidade/Ferimentos, Entropia/Carga, equipamento), "Cicatrizes" só quando existem,
  retrato canônico (`GeneratedPortrait`) ou capa de classe/monograma; reload mantém; seção "Jornada · Missões" com "Evolução do herói".
- Troca de save: nenhum dado do jogo anterior no deck/ficha.

Seletores/contratos novos: `.deck`, `.deck__head`, `.deck__msg` (aria-live), `.deck__note`, `.deck-card__btn[data-deck-card]`,
`.deck-card__evolve`, `.char-scars`, `.char-journey`, `.char-portrait`. Payload aditivo em `player_stats`: `can_reorganize`,
`prepared_slots`, `subclass`, `scars`, `virtue_cards`, `evolvable_card_ids`. Fixture `web/e2e/fixtures.ts` ganhou `POST /game/cards/prepare`.

Impacto nas jornadas F existentes: o rótulo da seção segue "Jornada · Missões" (F07/F-quests usam `/Missões/`). A aba Combate fora de
encontro agora tem o deck acima do texto "Nenhuma ameaça à vista" (que continua).

`reaction.present` (adiado pela SPEC-208): nao implementado — exige janela de gatilho de reacao emitida pelo backend
(`combat.reactions` hoje so lista cartas elegiveis; a reacao e declarada junto da acao). Fica para uma spec de contrato de reacao.
