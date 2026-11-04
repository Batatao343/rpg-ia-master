# SPEC-397 — Cartas: arestas do smoke da SPEC-369 (corte do `draft.py`, `frequencia` fechada, emboscada na abertura narrada, arma na prosa final, passiva por recompensa)

> **Status:** `approved` (04/11, coordenador, sob a ordem permanente do dono "manda bala" e a política de zero pendência)
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Épico:** SPEC-327
> **Origem:** [docs/spec369/smoke.md](../docs/spec369/smoke.md) § Achados 1–5.
> **Depende de:** SPEC-369 (`main`).
> **Risco:** `médio` (texto de abertura de combate, script de autoria). Revisor Sol (Opus).

## 1. Contexto & Objetivo

O smoke real da SPEC-369 passou nos 4 itens, mas deixou 4 P3 e 1 observação. A política do dono é não deixar pendência.

## 2. Requisitos

- **R1 (achado 1).** `scripts/cards/draft.py` entrega no máximo `--n` Cartas por lote: o corte acontece depois da triagem e do reparo, e só entram as que passaram. Se entregar menos que `n`, o aviso continua. Teste: um LLM fake que devolve mais Cartas que `n`.
- **R2 (achado 4).** O campo `frequencia` do rascunho vira enum fechado no schema Pydantic do `draft.py`, com os mesmos valores aceitos pelo `card_lint`. O LLM não consegue mais inventar "rodada". Teste de schema, mais o guard de FallbackLLM intacto.
- **R3 (achado 2).** Quando o conflito abre com emboscada inimiga (`initiator="enemy"`, `reason="ambush"`), a abertura narrada diz que o inimigo atacou primeiro. Quando a emboscada é negada (`ambush_negated_vigilia`), ela diz que o herói percebeu a tempo. O texto é determinístico (frase fixa em voz "você", sem número nem id), anexado ou passado como fato à narração de abertura. A mecânica não muda. Teste pela API real (MockLLM) com as duas seeds do smoke (Carta preparada e Carta fora).
- **R4 (achado 3), investigação.** Confirmar se a "Serra Cirúrgica pesada na mão" na prosa final do item 3 era a arma equipada. Se a prosa cita uma arma que o herói não tem, a narração final passa a receber como fato a arma equipada e a Carta jogada. Se era a arma equipada, registrar no §9 e não mudar nada.
- **R5 (observação 5).** Provar que a passiva `cor1_tro_faro_do_abismo`, quando chega por recompensa (espólio ou loja), aparece em `player_stats.cards`, pode ser preparada e nega a emboscada. Teste pela API real. Se não aparecer, corrigir.
- **R6 (guardas).** Sem flag nova; golden 330, avaliadores, arenas, `sim.py`, `web/e2e/contracts` e arquivos da SPEC-369 Fase A intocados; `agents/combat.py` não cresce; `test_size_budget`, `test_no_silent_except`, `test_log_event_registry` e `test_error_envelope` verdes; ruff limpo.

### Fora de escopo

Balanço (SPEC-369), timeouts do DeepSeek (infra).

## 3. Plano

1. Testes vermelhos de R1, R2, R3 e R5 (para o R5, verde é aceitável se já funciona) e investigação do R4.
2. Implementar.
3. Guardas.
4. §9.

## 4. Critérios de aceite

- [x] R1: corte em `n`.
- [x] R2: `frequencia` em enum.
- [x] R3: abertura narrada coerente com a emboscada ou com a emboscada negada.
- [x] R4: causa registrada (e corrigida, se for bug).
- [x] R5: passiva por recompensa listada e efetiva.
- [ ] R6: guardas e suíte completa verdes no pouso.

## 5. Smoke real (curto, local)

Repetir os itens 2a e 2b do smoke da 369 (abertura narrada) e um lote do `draft.py` com `--n 4`. Registrar em `docs/spec397/smoke.md`.

## 6. Decisões

Nenhuma aberta. Regra registrada (P3-4): passiva de iniciativa conhecida (`known_cards`) anula a emboscada sem estar preparada, coerente com `learned_passives` e com "passiva não ocupa Preparação"; vale para Vigília, Remendo, Equação Persistente, Conta Memorizada e Faro.

## 7. Registro de implementação

Executada em 04/11 (branch `spec-397`).

- **R1** `scripts/cards/draft.py`: `aceitas[:n]` depois de triagem, reparo e ajuste. Teste `test_batch_is_cut_at_n`.
- **R2** `frequencia` com `json_schema_extra={"enum": sorted(card_lint.FREQUENCIAS)}` (mesma técnica do `alvo`: parse tolerante) e a triagem rejeita valor fora do vocabulário (cai em `rejeitadas`/reparo). Testes em `tests/test_card_draft.py`.
- **R3** novo `services/opening_ambush.py` (2 frases fixas, voz "você"); `agents/combat.py` só troca 2 linhas (3957 linhas, sem crescer): a frase é anexada à narração de abertura por `initiator_reason` (`ambush` / `ambush_negated_vigilia`). Testes em `tests/test_spec346_vigilia.py` (via `_combat_node` com MockLLM, não pelo HTTP).
- **R4** Não era bug. `data/classes.json` dá ao Médico de Campo `serra_cirurgica` como equipamento inicial (única arma) e `character_creator` a auto-equipa; a prosa citava a arma equipada. Teste `test_medico_starts_with_the_surgical_saw_equipped`. Nada mudou.
- **R5** Era bug real: passiva ganha por espólio/loja ficava só no Acervo e `_has_vigilia` (lia só `deck`+`prepared_cards`) não a via. Revisão Sol (P1-1) rejeitou pôr a passiva em `prepared_cards` (estoura 4/4). Final: `_add_to_deck` devolve "acervo" para passiva (não entra em baralho nem slot; `acervo_reason` None) e `_has_vigilia` delega a novo `services/initiative_cards.py`, que também lê passivas de `known_cards` (como `learned_passives`). `deactivate_deck` não tira o efeito (teste). Testes via API (`/game/espolio`) em `tests/test_card_smoke_edges.py`: nível 1 com 4/4 + `set_prepared(lista atual)` ok, baralho sem `deck`, `deactivate_deck`.
- **R1 (P3-3)** o corte em `n` agora avisa quantas aprovadas foram descartadas.
- **Desvio declarado (P3-1)**: o teste do R3 usa `_combat_node` com MockLLM, não o HTTP; o smoke real cobre.
- **Smoke real (§5)** não executado pelo executor (sem chave/serviço no worktree); fica para o coordenador.
- **Follow-ups da rodada 2 (P3-4/5/6):** regra no §6 e linhas datadas nas specs 346 e 355; `VIGILIA_CARD_ID` com fonte única em `services/initiative_cards.py` (combat importa); `acervo_reason` devolve `passiva_permanente` para passivas e a UI (`web/src/cardRewards.ts`, `types.ts`) mostra "sempre ativa: não ocupa Preparação".
