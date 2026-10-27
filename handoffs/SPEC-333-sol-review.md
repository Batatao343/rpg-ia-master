# SPEC-333 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Sol (Opus, revisor independente) · **Data:** 2026-10-27 · **Commit revisado:** `426a9951`

## Escopo

Branch `spec-333`, `main...HEAD` (1 commit, 38 arquivos, +2717/−29): `services/card_rewards.py`,
`services/card_status.py`, `services/cards.py`, `services/card_piles.py`, `services/card_effects.py`,
`services/card_lint.py`, `services/death_flow.py`, `world_utils.py`, `agents/combat.py`, `api.py`
(`/game/espolio`, `/game/forja`), `services/abuse_policy.py`, `services/error_codes.py`,
`data/cards/status_e_maldicoes.json`, `data/cards/_orcamento.json`, `data/artifacts.json`, front
(`EspolioPanel`, `ForjaPanel`, `cardRewards.ts`, ligação em `CombateTab`/`Workspace`/`App`), testes novos
e os testes alterados. Conferido contra R1–R9 e §8. Fora do escopo: smoke real §6 e jornadas e2e (a spec já
as marca como pendentes).

O que está correto:
- **Economia/idempotência:** as duas rotas reutilizam o esqueleto de `/game/cards/prepare`:
  `_resolve_save_file` (dono no perfil hosted), `_begin_state_mutation` (recibo por `action_id`, CAS por
  `base_version`, `_failed_pending_operation` para o kind `equip`), `_game_lock` no legacy. Repetir a
  requisição com o mesmo `action_id` devolve o recibo. Com outro `action_id`, o espólio já foi consumido
  (`accept` faz `pop`) e a resposta é 400. Duas requisições concorrentes esbarram no CAS. Carta fora das 3
  ofertas → 400. Espólio expirado (`expire_pending` no início do próximo conflito) → 400. Ouro só se move
  em `accept`/`forget`/`purge_curse`, com valores constantes do Python e checagem de saldo antes.
- `abuse_policy`: as duas rotas entram na classe `mutation`. Os códigos `espolio_rejected`,
  `forja_rejected` e `card_rewards_off` estão no backend, em `errorCodes.json`, com mensagem pt-BR e em
  `CODIGOS_DE_ERRO.md`.
- **(c)** O espólio só sai em `victory` (que já é falso com `objetivo_resultado=="falhou"`) ou com
  objetivo `cumprido`. Morte, fuga e laboratório ficam excluídos (`combat.py:2310-2325`).
- **(d)** A maldição da Cicatriz faz round-trip pelo save (teste com save/load). `set_deck` recusa
  tirá-la. `forget` recusa. `purge_curse` cobra 40 depois de checar o saldo. As Cartas de status vivem só
  nas pilhas e somem com elas. O Sussurro apodrece em `fardo_estilhaco` depois de 2 rodadas e, se for
  jogado, vai para `exaurida` (`frequencia: cena`) sem apodrecer.
- **Flag `off`:** loot, XP, ouro, ficha e API ficam iguais (`_card_reward_blocks` devolve vazio; a carta de
  Esquecer, o espólio e a Cicatriz não fazem nada). A exceção é a P2-1. As 9 Cartas novas ficam fora de
  `cards_for_class`, do espólio e do Acervo. `essencia_de_cinza` não entra em nenhuma loot table (os pools
  são explícitos) nem em loja.
- **(g)** O front só ganhou blocos novos, renderizados apenas se `espolio_pendente`/`forja` existirem.
  Botões travam durante a requisição; cada clique gera um `action_id` novo.
- Nenhuma mudança em `evals/`. Não há segredo em log.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/card_rewards.py:460`, `:298` | Com `shadow` o código altera o jogo. `register_scar_curse` só testa `mode()=="off"`, então em `shadow` grava `cicatriz_cartas`, põe a maldição no `deck` e em `prepared_cards`, e `set_deck`/`_starting_deck_ids` passam a impor a Carta. `on_long_rest` grava `forja_esquecer=1` na ficha. Reproduzido por script: `shadow register -> [{'scar_id': ..., 'card_id': 'mld_cicatriz_braco'}]` e `shadow long rest -> {'forja_esquecer': 1}`. Isso viola §8 ("`shadow` só mede"). | Nos dois pontos, usar `if mode() != "on": return` (em `shadow`, no máximo telemetria). Adicionar testes de `shadow` que não altera a ficha para `register_scar_curse` e `on_long_rest`. |
| P2-1 | P2 | `services/card_piles.py:190`, `:241` | `piles["comprou"]` é gravado sempre que o Baralho está `on`/`shadow`, mesmo com `RPG_CARD_REWARDS=off`. A chave nova vai para `combat.pilhas` no save e quebra o "off byte-idêntico em saves". Não aparece na API pública (`public_piles` lista chaves fixas), por isso não é P1. | Em `card_piles`, devolver a lista sem gravá-la (`drawn = draw(...)`) e deixar `combat.py` passá-la para `card_status.on_hand_drawn(piles, player, drawn)`. Outra opção é gravar só com `card_status.active()`. |
| P2-2 | P2 | `services/card_rewards.py:213-219` (e `services/cards.py` `set_deck`, mesmo `keep`) | `_set_prepared_from_deck` preserva os ids de `prepared_cards` cujo tipo não está em `_DECK_TIPOS`. Como `maldicao` não está, a maldição continua em `prepared_cards` depois do Purgar. Reproduzido: `after purge deck has curse: False prepared has curse: True`. Hoje é só resíduo (o `_starting_deck_ids` filtra), mas a Carta purgada continua listada como Preparada na ficha e no `_cards_block`. | Excluir `cards.STATUS_TIPOS` do `keep` nos dois lugares. Teste: depois de `purge_curse`, `mld_*` não está em `deck` nem em `prepared_cards`. |
| P2-3 | P2 | `services/card_rewards.py:535` | `public_pending` mostra o espólio com qualquer flag diferente de `off`. Em `shadow`, um pendente que sobrou de um período `on` aparece no painel, mas a rota responde `card_rewards_off`. | Trocar por `mode() != "on"`, igual a `public_forge`. |
| P2-4 | P2 | `agents/combat.py:1791`, `:2294-2297` | Os logs de `card_status.on_start`, `on_round_end` e `on_hand_drawn` ("O ferimento abre espaço no Baralho: Membro Falho", "o corpo cobra 1 de Fôlego", "O sussurro ignorado apodrece") são descartados. O jogador perde Fôlego ou fica Cego sem nenhuma explicação mecânica. | Encaminhar a lista para o log mecânico da rodada (`mech_log`/`pilhas_eventos`) ou para `messages`. |
| P2-5 | P2 | `data/cards/status_e_maldicoes.json` (`sus_sussurro_abismo`, `custo_entropia: -2`) | Neste sistema a Entropia é recurso do jogador (as Cartas a gastam; `apply_entropy_trigger` a ganha). "+2 Entropia" vira bônus: 10 de dano a 0 de Fôlego mais recurso de graça. A tentação perde o custo (o único risco é deixar apodrecer). A leitura literal de R9 foi seguida, mas a intenção ("tentação") parece ser cobrar Carga do Abismo. | Decisão de design para o dono/Astra: trocar por `+N` de Carga do Abismo, ou manter e registrar. Não bloqueia. |
| P2-6 | P2 | `tests/spec330_equivalence.py:132`, `tests/test_card_lint.py:338` | (e) O filtro por `origem` `cartas-333` só existe porque o golden ainda não filtra pelas chaves. Depois que SPEC-332 pousar na `main` (golden filtrado pelas chaves), a mudança fica desnecessária e deve sair no rebase (`wt.sh sync`). O teste de contagem passou de `== 323` para `>= 332`, o que enfraquece o guarda. | No rebase: descartar o hunk de `spec330_equivalence.py` e voltar a igualdade exata (`== 323 + Cartas das ondas já pousadas`). |
| P2-7 | P2 | testes | Falta cobertura HTTP para: (i) repetir o mesmo `action_id` em `/game/espolio` no perfil com banco (recibo, ouro creditado uma vez); (ii) `shadow` em `register_scar_curse`/`on_long_rest` (ver P1-1). A infraestrutura é compartilhada e está testada em outras rotas, mas o caminho econômico novo merece um teste próprio. | Adicionar um teste de replay (`action_id` igual → mesma resposta, `gold` +15 só uma vez) e os testes de `shadow`. |

**(f) `_orcamento.json` isentando `status`/`maldicao`:** aceitável. Essas Cartas não têm efeito
principal jogável. O efeito delas é `ao_comprar_status` ou Vazão `ao_descartar`, ambos de valor
fixo autorado, e elas nunca entram no espólio nem na progressão. O Sussurro é `ativa` e continua
dentro do orçamento (o `validate_content` passa).

**Desvios de §8 conferidos e aceitos como follow-up:** Dor Surda sem a opção "1 Fôlego para descartar";
`essencia_de_cinza` sem fonte (na prática Afiar fica inerte até existir drop ou loja); a fatia
"neutras/regionais" está vazia até SPEC-335; o lado positivo da Cicatriz é fixo por região (a frase do
LLM fica só como sabor).

Pergunta menor (sem achado): um objetivo `cumprido` com `hero_fled` (por exemplo, objetivo de escapar,
SPEC-331) não rende espólio por causa do guard `not hero_fled`. Confirmar se é intencional.

## Correções aplicadas

—

## Pendências

- P1-1 é obrigatório antes do pouso. P2-1 a P2-3 são baratos e recomendados no mesmo ciclo. P2-4 e P2-7
  podem virar follow-up do executor. P2-5 é decisão do dono/Astra. P2-6 se resolve no rebase depois de
  SPEC-332.
- Follow-ups da spec: jornadas e2e (EVAL_AUTHORING), smoke real §6, fonte de `essencia_de_cinza`,
  Dor Surda "pagar 1 Fôlego para descartar".

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_card_rewards.py tests/test_forge.py tests/test_wound_status_cards.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_error_envelope.py tests/test_abuse_policy.py tests/test_card_effects_grammar.py tests/test_card_lint.py → 201 passed
bash scripts/dev/py.sh scripts/validate_content.py → 0 erros, 0 avisos
web: npm run lint → exit 0 · npm run build → exit 0 · npm test → 229/229 pass
script de sondagem (scratchpad) → reproduziu P1-1, P2-1 e P2-2
```
