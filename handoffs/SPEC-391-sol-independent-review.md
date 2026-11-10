# SPEC-391 — revisão sol (independent-review, fechamento)

> **Veredito:** `APPROVED` (3 achados P3, nenhum bloqueante; os follow-ups já conhecidos seguem registrados na spec)
> **Revisor:** Opus (papel Sol, `spec-reviewer`, não escreveu o código) · **Data:** 2026-11-10 · **Commit revisado:** `22bedadb` (main; código da 391 = `f6e19cd1..85369ae3`)

## Escopo

Fechamento dos critérios abertos do §5 (R14, byte-identidade, flag/gate SPEC-340, revisão do diff).

- **Base de partida:** `28762b15`, pai do 1º commit da 391 com código (`0e0c7b1d`, avaliador). Para o produto vale também `0af27199`, pai do 1º commit de produto (`f6e19cd1`). Entre as duas só entraram o avaliador, o teste e a spec.
- **Intervalo de produto:** `0af27199..85369ae3` (10 commits contíguos, só da 391).
- **Arquivos:** `services/reinforcement_cards.py` (novo, igual na HEAD), `services/reinforcements.py`, `services/enemy_decks.py`, `services/enemy_intent.py`, `services/conflict_orchestrator.py`, `agents/combat.py`, `api_presenters.py`, `config/flags.yaml`, `observability/events.py`, `data/cards/inimigos/chamados.json` e web.
- **Pontos de integração na HEAD** (depois de 397/398): `agents/combat.py:413-441`, `api_presenters.py:1147` e `conflict_orchestrator.py:668` continuam ligados ao módulo.
- **Fora do escopo:** suíte completa (é do coordenador), web e o gate §8, que já foram revistos em 04/11 (`handoffs/SPEC-391-sol-review.md`).

## Resultado dos critérios abertos

**(a) R14, flag `off` com JSON das arenas idêntico à base.** Usei dois métodos.

- **Regeneração empírica.** Abri dois worktrees temporários (`0af27199` e `85369ae3`), rodei os mesmos comandos com o mesmo venv e comparei os JSON sem `elapsed_s`. Os 7 pares deram iguais:
  - 285, célula `lider_matilha`, 20 sementes, L3/5/8, bots `basico`+`cartas`, baralhos `on`, reforço `off`: 6 células;
  - 285 nas categorias default, com 1 semente, L3 e bot `cartas`: 4 células;
  - 332 default (2 sementes, L3/5, 3 por família): 22 células, stderr idêntico;
  - 332 só com `lider_matilha` e `predador`;
  - 368 default (sementes 0–19, L1/3/5, R9+R10);
  - 368 com sementes 0–1;
  - 355 `base` com sementes 0:2.
- **Limite:** o 285 completo default (todas as categorias × 2 sementes) passou de 5 min e foi interrompido. Esse caso fica coberto pelo método por código.
- **Equivalência pelo diff.** Com a flag `off`, nenhum caminho novo é alcançado:
  - `_advance_reinforcements` sai antes do módulo;
  - `pending_call` devolve `None` quando a flag não está `on`;
  - `declaration_plan` repete as condições do guard antigo (`active`, `blocked`, `trigger ∈ {None, sempre}`);
  - `chegou_na_rodada` só existe no fluxo `on` (chave ausente = 0);
  - em `rf.spawn`/`_template_for`, os defaults `slack=0`, `generic=False` e `deck_seed=None` vêm do único chamador legado;
  - `payload_fields` devolve `{}` quando a flag está inativa;
  - `CALL_CARD` não está em nenhum pool de família (`_EXTRA_FILES`);
  - os eventos só ganharam `via`.

**(b) Byte-identidade** de `sim.py`, das arenas e dos arquivos de família.

- `git diff 0af27199 85369ae3 -- scripts/cards/sim.py docs/spec285 docs/spec332 docs/spec355 docs/spec368 data/cards/inimigos`: só aparece `chamados.json`, que é um arquivo novo previsto no §3.2.
- Em `28762b15..HEAD` também mudam `abissal`, `conjurador`, `lider_matilha` e `predador_apice.json`. As quatro mudanças vêm de um só commit, `6aef46c0` (SPEC-369 B6), e não contam contra a 391.
- `_decks.json`, `evals/` e o avaliador congelado `docs/spec391/arena_reforco_cartas.py` (`d056c83d..HEAD`) não têm diff.

**(c) Flag e gate SPEC-340.**

- `config/flags.yaml:182-187` registra `RPG_COMBAT_REINFORCEMENTS` com `kind: release`, `default: "off"`, `spec: SPEC-391`, nota nova e `expires: 2027-01-25`.
- `tests/test_flag_registry.py` passou.
- O staging está com `on` desde `f7d19f82`, por "liga" do dono.

**(d) Revisão do diff.** Não achei P0, P1 nem P2.

- A máquina de estados, o despacho por `via` e o round-trip save/load já tinham sido conferidos em 04/11 e não mudaram desde `85369ae3`.
- `frequencia: cena` impede que o Chamado já jogado volte como proteção.
- Não há `with_structured_output`, LLM nem `random` novo.
- Os achados são todos P3, na tabela abaixo.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-9 | P3 | `services/reinforcement_cards.py:216-226` | Cenário: o líder joga o Chamado na rodada N+1 e cai na mesma rodada, e outro inimigo mantém a luta viva. Como `rf.acts(leader)` é falso, o ramo `telegraphed` vai para o `elif` e cancela com `cause="frustrado"`. O log diz "não chega a chamar o bando" logo depois de o jogador ver a Carta jogada. O certo seria `lider_caido`. O desfecho mecânico está correto: não chega reforço. | Na spec futura: se `played` casar com o líder, cancelar com `lider_caido` e sem essa linha de log. Teste de nó com 2 inimigos. |
| P3-10 | P3 | `tests/test_enemy_decks.py:311` | O R20 (D-391-7) pedia para trocar o comentário. Ele continua dizendo "o dono descartou reforços (SPEC-325 D)", o que ficou desatualizado. A asserção e o teste positivo (`test_family_pools_still_never_call_and_only_chamados_does`) estão corretos. | Trocar o comentário para "o chamado mora em `chamados.json`, SPEC-391". |
| P3-11 | P3 | `services/reinforcement_cards.py:73-78`, `:121-122` (é o P3-6 de 04/11) | Desde `f7d19f82` a flag está `on` no staging, então o rollback para `off` com um save em `stage == "telegraphed"` agora pode acontecer. Nesse caso `CALL_CARD` fica no baralho do líder e pode ser jogada como proteção avulsa. | Mesma correção do P3-6, na spec futura, antes de qualquer rollback da flag. |

Os follow-ups já conhecidos (P3 `stage=called` no payload encerrado; D-391-10, sem oferta de retrato pago para o `_r1`; P3-7 stun da L2; P3-8 alavancas pousadas) não bloqueiam e continuam com a spec futura.

## Correções aplicadas

Nenhuma (revisão de fechamento, só leitura).

## Pendências

- P3-9, P3-10, P3-11: spec futura de follow-up da 391, junto de D-391-10 e P3-6/7/8.
- Coordenador: suíte completa, que já está verde na main de hoje segundo o coordenador, e a marcação dos critérios do §5.

## Comandos rodados

```text
git log --oneline 0af27199..85369ae3 → 10 commits, todos da 391
git diff 0af27199 85369ae3 -- sim.py docs/spec285|332|355|368 data/cards/inimigos → só chamados.json (novo)
git log 28762b15..HEAD -- abissal|conjurador|lider_matilha|predador_apice.json → só 6aef46c0 (SPEC-369)
git diff d056c83d HEAD -- docs/spec391/arena_reforco_cartas.py evals → vazio
worktrees 0af27199 × 85369ae3, RPG_COMBAT_REINFORCEMENTS=off:
  285 lider_matilha 20 sem L3,5,8 (95 s) → igual; 285 default 1 sem L3 cartas → igual; 285 default 2 sem → >300 s, interrompido
  332 default (25 s) → igual; 368 default 0-19 (91 s) → igual (sem meta.elapsed_s); 355 base 0:2 → igual
pytest -n 2 test_reinforcement_cards test_enemy_decks test_flag_registry test_size_budget test_spec325_reinforcements → 122 passed (rc 0)
dup_helpers --diff 0af27199...85369ae3 → só colisões de nome
ruff check reinforcement_cards/reinforcements/enemy_decks → limpo
worktrees temporários removidos; processo de arena morto por PID (árvore)
```
