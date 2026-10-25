# SPEC-310 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus / papel Sol (revisão independente; não escreveu o código) · **Data:** 2026-10-25 · **Commit revisado:** `8988bd07` (branch `spec-310` sobre `main` `005017e4`)

## Escopo

`git diff main...spec-310` (15 arquivos): `services/npc_self.py` (novo), `agents/npc.py`
(injeção após `</ROLE>`, `seed_motives_of`, `_submit_generated_npc`), `services/shared_pool.py`
(`materialize_npc`), `services/npc_knowledge.py` (`limit=None`, `exclude_ids`, `lines_cap`),
`services/content_validator.py` (lint R15), `data/npc_secret_topics.json`, telemetria
(`observability/events.py`, `EVENTOS_DE_LOG.md`), `.env.example`, os 4 testes `test_spec310_*` e a
§9 de desvios da spec. Fora: smoke real §6 (ainda não rodado), suíte completa (é do coordenador).

Conferido sem achado:
- **Regra de ouro.** `npc_self` não lê `world.news`, `perceived_ids`, `npc_beliefs`, pressões,
  bandas de região, crises nem `npc_sim` de outro NPC. O estado "envenenado" do R20 passa. O local
  usa só `public_label` do local atual (sem severity/cause/crisis_id). A exceção é o refugiado, que
  usa o rótulo público da casa (D3, aprovada).
- **Segredo.** O texto do segredo nunca vai ao prompt: entra só o tópico de
  `npc_secret_topics.json`. Segredo sem tópico, ou com id fora da tabela, não gera linha (falha
  fechada). O R21 testa os 44 segredos com o prompt inteiro capturado por spy. O lint (≤ 60
  caracteres, sem o label, sem palavra de ≥ 5 letras em comum, sem id órfão) entra em `validate_all`.
- **Fação secreta.** O gate `faction_intel[F].known` (o jogador conhece a fação) é o que a spec
  pede (R11/R12/D4). Para um prompt de NPC, ele é o gate conservador certo contra revelação: o
  limite é o que a LLM pode dizer ao jogador. Ele não modela o que o NPC sabe, mas falha para o
  lado de esconder. Ressalva (fora de escopo, pré-existente): `<FACÇÕES_DO_MUNDO>`
  (`agents/npc.py:1119-1125`) lista para todo NPC as 4 fações secretas (`mao_sombria`,
  `filhos_chama_azul`, `druidas_renegados`, `cultistas_destilacao`), com `plano`. O nome escondido
  pelo `<SOBRE_VOCE>` já está, portanto, no mesmo prompt (risco 1.6 da revisão orquestrada).
- **Compatibilidade com save antigo.** Sem `seed_motives`, o bloco de motivações fica vazio. Sem
  fação, sem `npc_sim` ou com `RPG_NPC_WORLD` ≠ `on`, a agenda cai para a casa ou fica vazia.
  Testei à mão o round-trip `save_game_state` → `load_game_state` no perfil legacy: `seed_motives`
  volta intacto.
- **Pool.** `seed_motives_of` copia só 5 ids das tabelas, sem dado do autor. O campo fica fora de
  `_POOL_DOC_KEYS` e da `DOCUMENT_ALLOWLIST`. `materialize_npc` só copia quando `entry.seed` existe.
  O campo não aparece em `api.format_response` nem no dossiê (R23).
- **Kill switch e guards.** Com `RPG_NPC_SELF=off`, o prompt é idêntico ao do módulo removido. Há
  `try` duplo (dentro do módulo e em `_npc_self_prompt`) com `log_fallback("npc",
  "self_block_failed")`. Nenhum `with_structured_output` novo; o guard do `npc_actor` está intacto.
  A telemetria registra só `sections`, `chars` e `truncated`, sem texto.
- **`<O_QUE_VOCE_SABE>`.** Só sai com a 215 em `on`. O `exclude_ids=pack.evidence_ids` casa com o
  `source_id=sid` do gate (`services/context_builder.py:774`). A faixa hostil dá teto 0. O único
  chamador antigo de `npc_knowledge_block` é `tests/test_npc_knowledge.py:410`, que passa sem
  alteração.
- `evals/` e os testes protegidos da 215 ficaram sem alteração.
- **Travamento com `-n 2`.** Não reproduzi. Rodei 3 lotes com `-n 2` (até 9 arquivos, mais de 115
  testes) e todos terminaram em menos de 1 min, com "bringing up nodes" normal. A causa é do
  ambiente (RAM/OneDrive/xdist na hora), não um teste novo: os testes da 310 são puros, sem rede,
  subprocess nem `supabase`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `services/npc_self.py:58`, `:26-28` | R4 diz que o total "nunca passa de 1.950". Com cada bloco no teto, `text()` soma 700+1+450+1+800 = 1.952, e `agents/npc.py:1077` ainda acrescenta 1 `\n` (1.953). O teste `test_orcamento_corta_por_prioridade` só mede um caso abaixo do teto. | Baixar `KNOWS_MAX_CHARS` para 798, ou cortar `o_que_sabe` pelo que sobra do total. Teste com os 3 blocos cheios. |
| P2-2 | P2 | `services/npc_self.py:142`, `:275` | `is_leader(ref)` não confere se o NPC lidera **a** fação resolvida. Se um líder trocar de lado pela projection (304), ele aparece como "Você lidera Y." e ganha o atalho de líder do R11 (fica sabendo no mesmo dia de uma mudança de relação). | `npc_world.leaders().get(ref) == faction_id`. |
| P2-3 | P2 | `services/npc_self.py:300` | O caminho (c) do R11 consulta o ledger por `ref` (`row.id` ou a chave do estado). O ledger usa `npc_id` (`_npc_id`: `row.id` ou `npc_<nome>`), que já é passado como `knowledge_id`. Num NPC sem `id`, os dois divergem e o caminho (c) nunca dispara. A falha é fechada (omite), mas é um bug. | Passar `knowledge_id` para `relation_lines` e usá-lo em `known_subject_ids`. |
| P2-4 | P2 | `services/npc_self.py:250`, `:211` | `place_lines` e o motivo do refugiado leem `location_states` sem olhar `world_engine.mode()`. A SPEC-309 (`services/perceived_world.py:147`) só emite o estado do local com o motor `on`. Num save com projection antiga e `RPG_WORLD_ENGINE=off`, o NPC ainda diz "Aqui, agora: sitiada". O kill switch do motor não vale para este bloco. | Gate `world_engine.mode() == "on"` no rótulo (a data continua). Junto, unificar a linha "Aqui, agora" com `<MUNDO_PERCEBIDO>`, o follow-up da §9. |
| P2-5 | P2 | `data/npc_secret_topics.json:39`, `:41` | Tópicos na 3ª pessoa num prompt em 2ª pessoa: "Há um assunto que você evita: de onde ele realmente vem." e "uma visão que o assombra" (gênero fixo). | "de onde você realmente vem" / "uma visão que não sai da sua cabeça". Entra na revisão D5 do dono. |
| P2-6 | P2 | `tests/test_spec310_npc_self.py:337-342` | O teste de round-trip do R24 só exercita `coalesce_runtime_npcs`, não `save_game_state`/`load_game_state`. A regra do repo para writer persistente pede round-trip real. Validei à mão no perfil legacy e passa. | Trocar por round-trip real com `persistence` em `tmp_path`. |
| P2-7 | P2 | `specs/SPEC-310-npc-sabe-de-si.md` §6 passo 2 | Com o desvio da §9 (Chama Azul é secreta), o passo 2 do smoke ("Como vão as coisas com a Chama Azul?") não mostra a guerra se o save não tiver `faction_intel.filhos_chama_azul.known = true`. Sem isso, o resultado parece bug. | Incluir esse `known` no preparo do smoke, ou usar um par de fações públicas. |

Nenhum P0/P1.

## Correções aplicadas

Nenhuma ainda. Os P2 podem ir num commit de review-fixes antes do pouso (P2-1 a P2-4 e P2-6 são
pequenos) ou virar follow-up.

## Pendências

- Smoke real §6 (coordenador) antes de `done`; atenção ao P2-7.
- D5: dono revisa os 44 tópicos junto com a D8 da 297 (inclui o P2-5).
- Follow-up pré-existente, fora do escopo: `<FACÇÕES_DO_MUNDO>` expõe as fações secretas a todo
  NPC (risco 1.6). Isso esvazia parte do gate R12. Candidato a spec própria.
- Follow-up da §9: unificar "Aqui, agora" com `<MUNDO_PERCEBIDO>` (audience npc).
- Risco já registrado na §7: a persona do pool pode conter o segredo literal (validador na 297).

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_spec310_npc_self.py tests/test_spec310_no_leak.py tests/test_spec310_npc_prompt.py tests/test_spec310_secret_topics.py → verde (serial)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_npc_knowledge.py tests/test_context_npc_gate.py tests/test_eval_npc_knowledge.py tests/test_npc_camadas.py tests/test_spec298_visibilidade.py tests/test_spec300_prompt.py tests/test_spec301_llm.py tests/test_npc_fallback.py [tests/test_spec310_npc_prompt.py] → verde, exit 0 (2x, < 1 min; sem travamento)
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 tests/test_spec310_{npc_prompt,npc_self,no_leak}.py tests/test_spec297_{generation,shared_pool_local,reuse,npc_seed,review_fixes}.py → verde, exit 0
bash scripts/dev/py.sh -c "<save_game_state/load_game_state com seed_motives em dir temporário>" → seed_motives preservado
```
