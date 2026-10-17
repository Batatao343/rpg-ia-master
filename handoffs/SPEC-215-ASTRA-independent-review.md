# SPEC-215 — parecer Astra independente

**Data:** 2026-10-16 · **Revisor:** Astra (Opus, contexto separado) · **Escopo:** diff não commitado
do worktree `rpg-spec-215` sobre `main` (`39eeb67`).

**Veredito:** **APPROVED_WITH_FOLLOWUPS** (código/testes). A spec continua `in-progress`:
o §5 exige o dataset `npc_knowledge` verde como critério de aceite, e ele ainda não foi autorizado.

## Ataques e resultado

| Vetor | Resultado |
|---|---|
| Segredo via fala do jogador (R9) | OK: só eventos da crônica do jogador, tipos de §3.3 (sem `secret_revealed`), `find_strict_unrevealed` no texto. |
| Segredo via herança local (R10) | **DEFEITO corrigido (A1).** `secret_revealed` entrava em `location_heard`; um NPC criado depois no local herdava o segredo revelado como `[BOATO]`, o que viola R7 (o tipo é só testemunhável). |
| Segredo via boato / memória privada | OK: `npc_claim` com assinatura não revelada não gera link, fila nem linha; resumo, ledger e sessão do jogador saem do pack com `on` (D2). |
| Teleporte (save/reload, fuga, viagem, restore) | Entrega por `due_clock` persistido; o checkpoint usa o mesmo `_state_to_save_data` (o restore volta o ledger junto). Invariante `knowledge.teleport` sem violação. **DEFEITO corrigido (A2):** com `on`, as arestas dinâmicas de `location_control_changed` remoto (`X —controls→ Y`) ainda entravam em `relations`; um NPC distante sabia na hora. Agora uma aresta com `created_by_event` só entra se o evento estiver no filtro do NPC. |
| Boato → fato | OK: nenhuma escrita em event_log, projection ou `MemoryFact`; entrega de rumor = só `told_to`; rótulo `[BOATO]`. |
| Ledger sem teto | Tem teto: 2000 links, 200 na fila, 100×100 em `location_heard`. Medido offline com `on`, 200 turnos: `npc_only` → 392 links (119 KB), fila **saturada** em 200 (63 KB), save total de 440 KB; `normal` → 0 links, fila vazia, 1,5 KB. Pior caso teórico ≈ 0,6 MB de links. |
| Determinismo | `sha256(game_id\|subject\|from\|to\|hop)`; ordenação estável; replay coberto por teste. |
| `off` byte-idêntico | Snapshot do HEAD verde; o filtro de aresta só age com `knowledge_filter` (só `on`). |
| Custo de prompt | ≤ 8 linhas (`NPC_KNOWLEDGE_CONTEXT_MAX`) dentro do budget atual; zero LLM novo. |
| NPC morto (SPEC-230) | `_residents` usa `npc_alive`; `npcs_in_scene`/`is_in_scene` excluem mortos, então o morto não recebe nem testemunha. |
| API | `format_response` (estado + SSE `state`), codex e `visible_npc_view` não têm as chaves (testado). O audit-export usa allowlist. `/account/export` é o export do próprio dono (dados pessoais), não um export público. |

## Decisão: as 4 chaves no save com `off`

**Aceito, mantido.** O custo é de ~90 bytes. Omitir as chaves vazias faria um jogo novo recarregar
como `legacy_knowledge=true`, quebrando a simetria entre save e checkpoint e a idempotência do
round-trip. Com `off`, um ledger herdado de uma sessão `on` precisa sobreviver.

## Correções aplicadas (com teste de regressão, vermelho → verde)

- A1 `services/npc_knowledge.py`: `turn_updates` não grava `WITNESS_ONLY_TYPES` em
  `location_heard`; `inherit_local` ignora esses tipos (protege também saves adulterados).
  Teste: `test_witness_only_secret_never_heard_nor_inherited`.
- A2 `services/context_builder.py`: com `knowledge_filter`, uma aresta com `created_by_event`
  fora do filtro é descartada. Teste: `test_on_remote_control_change_edge_needs_knowledge`.

## Follow-ups (não bloqueiam; o flag é `off` por default)

1. **Fila saturada por rumores de diálogo:** cada fala de NPC vira um `npc_claim` com até 4
   destinos. Com o relógio parado, a fila bate 200 em ~50 turnos, e o corte por `due_clock` pode
   descartar notícia importante (`npc_killed`). Ajustar em `shadow` (D3): reservar fila por tipo,
   ou não propagar `npc_claim` de diálogo comum.
2. `_event_origin` cai no local ATUAL quando o evento não tem `location_id`. Se houver kill e
   fuga/viagem no mesmo turno, a origem vira o destino. Caso raro; o ideal é gravar
   `location_id` no payload de `npc_killed`.
3. A linha "Quem controla <local atual>" não é filtrada (é conhecimento local, aceito);
   `legacy_knowledge` é só um marcador e não muda comportamento.
4. Tamanho do ledger no snapshot hosted: medir em `shadow` antes de promover a `on`.

## Evidência

Focados SPEC-215: 53 passed. Ruff verde. Playtest offline `--all --turns 3` (`off`):
`20261016-215038-055748`, 14 perfis, 0 erro, 0 violação. 200 turnos com `on`:
`20261016-214918-891000` (normal) e `20261016-214930-940717` (npc_only), 0 erro, 0 violação.
Suíte completa (`pytest -q -p no:warnings --ignore=tests/test_project_index.py`, sem pipe): **exit 0**, 3.217 passed, 188 skipped.
