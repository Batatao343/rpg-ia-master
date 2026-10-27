# SPEC-334 — revisão sol (review)

> **Veredito:** `APPROVED` (re-revisão de `1145b2e1`; a 1ª rodada sobre `b11be055` foi `CHANGES_REQUIRED`)
> **Revisor:** Sol (Opus, spec-reviewer) · **Data:** 2026-10-27 · **Commits revisados:** `b11be055`, `1145b2e1`

## Escopo

Branch `spec-334`, `main...HEAD` (1 commit, 27 arquivos): `api.py` (rota
`POST /game/combat/preview`, `GET /data/cards/glossario`, `mech_log` no `_combat_block`),
`services/combat_preview.py` (novo), `services/card_piles.py` (`public_view`),
`services/conflict_turn.py` (`atk["card_id"]`), `agents/combat.py` (`last_mech_log`),
códigos de erro (py/json/ts/doc), `web/src/components/combat/*`, `web/src/combat/deck.ts`,
`CombateTab.tsx`, `api.ts`, `types.ts`, CSS e testes (`tests/test_combat_preview.py`,
`web/tests/deck-*.test.mjs`). Conferido contra R1–R9, §5 e os desvios de §8.
Fora: Playwright/e2e (EVAL_AUTHORING_REQUIRED, tarefa separada), staging 390/1440.

Pontos pedidos pelo coordenador:
- (a) **off idêntico — ok na UI/API.** `deckMode = !!combat?.pilhas`; sem `pilhas` o
  `CombateTab` renderiza o mesmo `aimbar` + `CardHand` + `CardTooltip`, `ManeuverFold`
  devolve os filhos sem wrapper e o atalho 1–9 antigo continua. `mech_log`/`listas`/`texto`
  só saem dentro do ramo `pilhas` do `_combat_block`. Ressalva no save: P2-2.
- (b) **preview:** puro (cópias profundas de player/alvo/cena, `_Scripted` no lugar do
  `random`, `mechanics_trace.record_step` é no-op fora do bucket do turno, nada de
  `card_usage`/save; teste `state == before` + `save_game_state` monkeypatched). Ownership:
  igual às outras `/game/*` (fronteira `_session_boundary` + CSRF para POST, e
  `load_game_state` usa `store.get(principal, id)` no perfil com banco), então não há IDOR.
  **Rate limit ausente** (P1-1) e **500 com Vantagem/Desvantagem de condição** (P1-2).
  Não vaza resistência/imunidade/Proteção (dano bruto) nem cartas do inimigo; vaza a faixa
  de Corpo (P2-1).
- (c) `atk["card_id"]` só é lido pelo `mech_log`; a narração consome `out["logs"]`, que
  não mudou. `last_mech_log` é calculado também em `off` (P2-2).
- (d) `listas` ordenadas por nome (desempate por id); o teste cobre. Nunca a ordem do monte.
- (e) Teclado: sem conflito com SPEC-324 (lá tudo é Alt/Ctrl+Alt+dígito, `?`, setas fora de
  texto); dígitos/Enter/Esc ignoram campo de texto e modificadores. Ressalvas em P2-3.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `api.py:3785`; `services/abuse_policy.py:44-70` | `POST /game/combat/preview` não casa nenhuma `RouteClass` → sem limite por IP nem por owner (o `read_auth` só cobre GET). Cada request carrega o save do banco e roda até 1000× `resolve_attack`. **Quebra `tests/test_abuse_policy.py::test_every_money_route_in_api_has_a_class`** (falha confirmada: `[('POST', '/game/combat/preview')]`). | Nova classe (ex.: `_rc("preview", r"^/game/combat/preview$", ("POST",), 120, 60)`) ou incluir na `mutation`; caso em `test_classify`. |
| P1-2 | P1 | `services/combat_preview.py:41` | `n = 3 if advantage else 2` usa só o `advantage` passado; `resolve_attack` soma a Vantagem/Desvantagem de condições do atacante (`combat_modifiers(...)["advantage"]`, ex.: `cego`). Com kwarg 0 e condição ≠ 0 o `roll_kept` pede 3 dados e o `_Scripted` só tem 2 → `IndexError: pop from empty list` → **500** na rota. Reproduzido: jogador `cego` + `bas_san_golpe` → `CRASH IndexError`. | Sempre enumerar 3 dados (1000 combinações; com rede 0 o 3º é ignorado e a distribuição continua exata), ou calcular a rede igual ao motor antes de escolher `n`. Teste com `cego` (Desvantagem) e uma condição de Vantagem. |
| P2-1 | P2 | `services/combat_preview.py:129` | `ferimento_provavel` usa `target["virtudes"]["corpo"]`; Virtudes do inimigo estão fora do `public_panel` (SPEC-329/R7). A categoria leve/grave/crítico para o mesmo excedente revela a faixa de Corpo. | Usar o Corpo só se revelado; senão uma faixa padrão (ex.: Corpo 0 ou "provável ferimento" sem categoria). |
| P2-2 | P2 | `agents/combat.py:2265-2270` | `last_mech_log` é calculado e gravado no save também com `RPG_CARD_DECK=off`: chave nova no estado persistido e um caminho novo que pode levantar (`card['name']`, `int(...)`) dentro do nó de combate em `off`. | Gate em `card_piles.mode() == "on"` (o único consumidor é o ramo `pilhas` do `_combat_block`). |
| P2-3 | P2 | `web/src/components/combat/DeckCombat.tsx:93-109` | O listener global não checa `event.defaultPrevented` nem modal aberto: com um diálogo (`useModalFocus`) aberto, Esc fecha o modal **e** limpa a fila/desarma; dígitos 1–5 enfileiram cartas por trás do modal. O Enter ignora só `button, summary, a, [role=tab]`: um `[role=button]`/elemento com `tabindex` (ex.: tokens da Arena) dispara a ação dele e encerra o turno. Os atalhos também funcionam com `busy` (o `play` não checa). | `if (event.defaultPrevented \|\| modalOpen()) return;` (mesmo critério do `Workspace.tsx:200`); ampliar o seletor do Enter para `[role=button], [tabindex], input, select, textarea`; ignorar dígitos quando `busy`. |
| P2-4 | P2 | `services/combat_preview.py:51-66, 88-125` | Prévia ≠ motor em casos de borda: não considera `consume_tactical_attack_modifier` (só lido), passiva `on_attack` de Vantagem, `ruptura`, `consume_marca_abismo`, `dealt_pct`; `_base_damage` duplica `_damage_from`; não confere `tipo == "ativa"` nem que a carta está na mão. O critério "preview bate com o resultado" vai divergir nesses casos. | Reaproveitar `ct._damage_from` e uma função compartilhada de cálculo de vantagem (sem consumir); registrar as exceções restantes no §8. |
| P2-5 | P2 | `web/src/components/combat/FolegoPips.tsx:11` | `role="img"` torna os filhos apresentacionais: o aviso `role="status"` do Pacto do Abismo dentro dele não é anunciado. | Tirar o `folego__warn` de dentro do `role="img"` (irmão) ou usar `role="group"`. |
| P2-6 | P2 | `services/card_piles.py:451-456` | `alvo` é binário (`inimigo`/`si`): carta de suporte que mira aliado entra na fila sem alvo. | Follow-up: `alvo: "aliado"` quando o efeito pede alvo aliado (party). |

Sem P0. Sem segredo em log, sem mudança em `evals/`, sem writer persistente novo além de
`last_mech_log` (P2-2). Structured output/LLM: não há (preview e log são determinísticos).

## Correções aplicadas

Commit `1145b2e1` (re-revisado por Sol, mesmo dia):

| ID | Status | Conferência |
|---|---|---|
| P1-1 | corrigido | Classe `preview` (`^/game/combat/preview$`, POST, 120/IP, 60/owner) em `services/abuse_policy.py:55`; caso novo em `test_classify`; `test_every_money_route_in_api_has_a_class` verde. |
| P1-2 | corrigido | `exact_attack_distribution` sempre enumera 3 dados (o `_Scripted` só consome o que o caminho real pede; com saldo 0 cada desfecho conta 10× igual, a distribuição continua exata). O repro com jogador `cego` agora devolve 200 (56,8 %). |
| P2-1 | corrigido | Corpo só via `bestiary_knowledge.public_panel(target)`; como o painel não expõe Virtudes, `ferimento_provavel` fica `None` (conservador, sem vazamento). |
| P2-2 | corrigido | `store_mech_log` só grava com `card_piles.mode() == "on"`; save `off` idêntico. |
| P2-3 | corrigido | Atalhos ignoram `defaultPrevented`, `busy` e modal (`[aria-modal='true'], dialog[open]`); o Enter também ignora `[role=button]` e `[tabindex]`. |
| P2-4 | corrigido | Valida mão (`card_not_in_hand`) e `tipo == "ativa"` (`card_not_active`), as duas como `invalid_reason` de `preview_invalid` (não são códigos novos de topo, então o catálogo não muda); reusa `ct._damage_from`; inclui modificador tático, Marca do Abismo e `dealt`/`taken` pct; marca `aproximado` (passiva de gatilho, fórmula rolada) e o front mostra "≈". **Pureza confirmada:** com `attack_formula` + Marca do Abismo no alvo, `state == before` e `random.getstate()` igual (a fórmula é removida das cópias antes de `_damage_from`, então `roll_dice_numeric` não roda; a Marca e o tático são consumidos só nas cópias). |
| P2-5 | corrigido | `role="img"` só nos pips; o aviso do Pacto ficou como irmão com `role=status`. |
| P2-6 | corrigido | `alvo: "aliado"` para efeitos de suporte; o front escolhe alvo aliado sem prévia. |

Resíduo (P2, não bloqueia): `fx.damage_pct(target, "taken")` (`services/combat_preview.py`, cálculo de `pct`) usa `combat_modifiers`, que soma **passivas** do alvo às condições. Hoje o único `dano_recebido_pct` vem da Rachadura (condição pública); nenhum dado em `data/` usa esse stat em passiva. Se um inimigo ganhar uma passiva assim, a prévia passa a revelá-la. Correção futura: usar só `cm.condition_modifiers(target)`.

## Pendências

- Resíduo `taken` pct via passiva do alvo (acima): follow-up do épico 327.
- R9 parcial (fila resultante do texto livre): follow-up registrado no §8 da spec.
- Playwright (jornadas, 390/1440, ≤ 12 interativos em 390 px): EVAL_AUTHORING separado.

## Comandos rodados

```text
# 1ª rodada (b11be055)
py.sh -m pytest -n 2 <7 arquivos do escopo + governança> → 1 failed (test_every_money_route_in_api_has_a_class), 121 passed
py.sh scratchpad/repro334.py (jogador `cego` + preview bas_san_golpe) → IndexError pop from empty list
web: npm run lint → 0 · npm run build → ok · npm test → 226/226
# re-revisão (1145b2e1)
py.sh -m pytest -n 2 tests/test_abuse_policy.py tests/test_combat_preview.py tests/test_error_envelope.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_card_piles.py tests/test_deck_migration.py → 128 passed
py.sh scratchpad/repro334.py → 200, chance 56,8 %
py.sh scratchpad/pure334.py (attack_formula + Marca do Abismo) → state_equal True, random_equal True, aproximado True
web: npm run lint → 0 · npm run build → 0 · npm test → 226/226
```
