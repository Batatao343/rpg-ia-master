# SPEC-230 — NPC: guard de geração, ciclo de vida (morte/party/cena) e relação como mecânica Python

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-028 npcs-3-camadas-traits, SPEC-040 encontros-dedupe, SPEC-041 npc-fallback-sem-alvo e SPEC-055 aliados-em-combate `done` são corrigidas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-202, SPEC-212, SPEC-215, SPEC-223 (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-01-02, 01-07, 06-11, 06-12, 06-07/02-17, 06-08, 01-09 (`achados/01-grafo-turno.md`, `06-mundo.md`, `02-combate.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false` — escopo pequeno e determinístico; mas toca a convenção CRÍTICA de guard
> **EVAL_AUTHORING_REQUIRED:** `false` — o corpus narrative/NPC (SPEC-171) já cobre "NPC morto em cena" como caso; registrar regressão em handoff (§9)

---

## 1. Contexto & Objetivo

Fatos reproduzidos no HEAD `d6af933` (re-executados pelo orquestrador onde marcado):

- [F] **Único site de `with_structured_output` sem guard** — `agents/npc.py:252-266` `generate_new_npc`:
  `res = designer.invoke(...)`; `data = res.model_dump()`. `AIMessage` também é Pydantic, então o `except` nunca
  dispara: com providers esgotados/`FallbackLLM` o NPC nasce com `role: None, persona: None, content: "erro: todos os
  providers falharam"` e **é gravado em `npc_database` (runtime)** — cache hit futuro reutiliza o NPC quebrado
  (`find_existing_entity` por nome). Repro executada: `saved: 1`. Viola a convenção CRÍTICA do CLAUDE.md.
- [F] **NPC morto segue vivo para o jogo** — `services/event_processor.py:71-73` (`npc_killed` só marca
  `projection.entities[id].alive=False`); `services/npc_layers.py:91-139` (`is_in_scene`, `npcs_in_scene`,
  `npcs_for_context`) e `party.scene_allies` não consultam `status`/`dead`; `agents/router.py:205-221` e
  `agents/npc.py:315-349` idem. Repro: `{"Grum": {status:"morto", in_scene:False, home:"nova_arcadia"}}` →
  `npcs_for_context == ["Grum"]`; com `in_scene:True` → `npcs_in_scene == ["Grum"]`; `npc_actor` responde "Grum não
  está aqui. Foi visto pela última vez em…" (cadáver tratado como ausente). Só `combat._reflect_scene_allies` marca
  `status:"morto"`, e só para aliados transitórios.
- [F] **Party ignora estado** — `agents/npc.py:340-349`: `in_party` é verdadeiro para qualquer entrada de
  `state["party"]`, inclusive `active=False, waiting_at=<outro local>` e `dead=True` → companheiro esperando em
  Brekmar responde no Pântano; companheiro morto fala; re-recrutar morto bloqueado por `already_member`.
- [F] **`relationship == 0` vira 5** — `party.py:268,291` `int(npc.get("relationship", 5) or 5)` (0 é falsy). Repro:
  NPC rel 0 + trait `pele_de_febre` (DC −3 → `required 5`) → `recruitment_decision ok True, relationship 5`.
- [F] **`relationship_change` sem teto** — `agents/npc.py:114` `relationship_change: int = 0` sem `ge/le`; só clamp
  final `[0,10]` (`:549`). Um turno do LLM pode ir de 0 a 10 e abrir recrutamento (≥7) / aliado de cena (≥6).
- [F] **`npc_fallback_hint` nunca limpo** — gravado em `agents/npc.py:327`, lido em `agents/storyteller.py:174`; sem
  reset e fora do whitelist de persistência → na CLI e no harness, todo turno STORY seguinte injeta "SEM INTERLOCUTOR…".

Objetivo: geração de NPC resiliente (fallback nunca persiste); um único predicado `npc_alive(npc)` respeitado por
cena/contexto/rota/aliados/party; relação como mecânica Python com teto por turno; estado transitório limpo por turno.

## 2. Requisitos

- **R1** — [R] `generate_new_npc`: `if not isinstance(res, NPCSchema): raise TypeError("structured output inválido")`
  → cai no fallback seguro; o fallback (`id == "fallback"`) NUNCA é passado a `save_npc_template`. Teste de
  reprodução: `get_llm` stub devolvendo `AIMessage` → NPC com `role "Desconhecido"`, `saved == 0`; segunda chamada com
  LLM válido gera e salva normalmente (cache não envenenado).
- **R2** — [R] Teste anti-regressão da convenção: varredura estática (`tests/test_structured_output_guards.py`) de
  todo `with_structured_output(` em `agents/`, `services/`, `character_creator.py`, `api.py` exigindo `isinstance(`
  ou `try:` envolvendo o uso do resultado na mesma função (allowlist explícita e justificada para exceções).
- **R3** — [R] `services/npc_layers.npc_alive(npc) -> bool` (`not dead and status != "morto" and not
  projection.alive is False`) usado por `is_in_scene`, `npcs_in_scene`, `npcs_for_context`, `visible_npc_view`
  (expõe `status: "morto"`), `party.scene_allies`, router (`active_npc_name` nunca aponta para morto) e
  `npc_actor` (morto → narração própria "X está morto." sem gerar diálogo). Teste de reprodução: os dois casos
  `Grum` → listas vazias; "Falo com Grum" → storyteller com nota de morte, sem `npc_actor`.
- **R4** — [R] `event_processor` ao aplicar `npc_killed` (qualquer fonte) sincroniza `state.npcs[nome]`:
  `status="morto"`, `in_scene=False`, `died_turn`, e remove/desativa na `party` (`dead=True, active=False`). Teste:
  `npc_killed` aceito → `npcs[...]["status"] == "morto"`, party sem o membro ativo.
- **R5** — [R] `in_party` no `npc_actor` = membro `active` e vivo; membro `waiting_at` só conversa no próprio
  `waiting_at`; morto não conversa e pode ter o slot liberado (`already_member` falso). Teste: companheiro `waiting_at=
  brekmar` + jogador no Pântano → gate camada 3 ("não está aqui").
- **R6** — [R] `relationship` lido com `None`-check (`rel = npc.get("relationship"); rel = 5 if rel is None else
  int(rel)`) em `party.py` (2 sites) e em todo `or 5` equivalente (`grep "relationship.*or 5"`). Teste: rel 0 + DC
  reduzido → `ok False`.
- **R7** — [R] `relationship_change` clampado em Python a `[-1, +1]` por turno (D-A permite ±2) antes de aplicar, com
  telemetria `rpg.npc.relationship_clamped` quando o LLM excede. Teste: `relationship_change=+5` → aplica +1.
- **R8** — [R] `npc_fallback_hint` é transitório: zerado em `_base_route_payload` (router) e no retorno do storyteller;
  adicionado ao `state.py` como transitório documentado. Teste: 2 turnos CLI-like (estado em memória) → o 2º prompt
  do storyteller não contém "SEM INTERLOCUTOR".

### Fora de escopo

- Conhecimento/propagação por NPC (SPEC-215), interlocutor automático (SPEC-202), taxonomia visível (SPEC-206).
- Traits/seeds, qualidade de persona, dedupe semântico do librarian (qualidade de prompt).
- Combate de aliados (spec `SPEC-231`).

## 3. Design técnico

### Arquivos alterados

- `agents/npc.py` — guard R1; `in_party` por estado (R5); clamp R7; `npc_alive` no gate (R3).
- `services/npc_layers.py` — `npc_alive` + uso nos 4 helpers (R3).
- `services/event_processor.py:71-73` — sincronização de `state.npcs`/`party` em `npc_killed` (R4).
- `party.py:268,291` — leitura de `relationship` (R6); `scene_allies` com `npc_alive` (R3).
- `agents/router.py` — `active_npc_name` só vivo (R3); `_base_route_payload` zera `npc_fallback_hint` (R8).
- `agents/storyteller.py` — retorno zera `npc_fallback_hint` (R8).
- `state.py` — documentar `npc_fallback_hint` transitório; `NpcRecord.status/died_turn`.
- `tests/test_structured_output_guards.py` — varredura estática (R2).

### Assinaturas

```python
def npc_alive(npc: dict, *, projection: dict | None = None) -> bool
def apply_npc_death(state_npcs: dict, party: list, name_or_id: str, turn: int) -> tuple[dict, list]
```

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
`tests/test_bug_npc_ciclo_de_vida.py`: `test_generate_new_npc_aimessage_not_persisted` (R1),
`test_all_structured_output_sites_guarded` (R2 — falha hoje em `npc.py`), `test_dead_npc_not_in_scene_or_context`
(R3), `test_npc_killed_syncs_state_npcs_and_party` (R4), `test_waiting_companion_only_talks_at_waiting_location`
(R5), `test_relationship_zero_is_zero` (R6), `test_relationship_change_clamped` (R7), `test_npc_fallback_hint_cleared` (R8).
### Etapa 1 — guard + varredura (R1, R2)
### Etapa 2 — `npc_alive` e sincronização de morte (R3, R4, R5)
### Etapa 3 — relação (R6, R7) + hint transitório (R8)
### Etapa 4 — regressão `uv run pytest` + playtest offline `npc_only`/`recrutador`/`quester` 40 turnos: zero diálogo com
NPC `status == "morto"` (grep no transcript), zero "SEM INTERLOCUTOR" fora de turno NPC.

## 5. Critérios de aceite

- [ ] 8 testes vermelhos → verdes; `tests/test_npc_fallback.py`, `test_encontros_dedupe.py`, `test_aliados_combate.py`,
      `test_fase28.py`, `test_fase33.py`, `test_npcs_3_camadas*.py` verdes ou diff justificado.
- [ ] `uv run pytest` verde; playtest offline com run_id.
- [ ] Guard de FallbackLLM em TODO `with_structured_output` (R2 passa a ser teste permanente).
- [ ] Saves antigos carregam (campos novos opcionais).

## 6. Smoke test com LLM real

1. Sem chave (ou `RPG_NO_MOCK=1` com providers inválidos — cuidado com custo): introduzir NPC novo → fallback
   "Desconhecido", `data/runtime/npc_database.json` sem entrada quebrada.
2. Matar NPC canônico em combate → "Falo com X" → narração de morte, sem diálogo.
3. Conversa amistosa 1 turno → relação sobe no máximo +1.

## 7. Riscos & compatibilidade

- NPCs já persistidos com `role: None` no cache de runtime: adicionar varredura no load (`load_npc_db` descarta
  entradas inválidas) — one-shot, documentado no README.
- Clamp de relação torna o recrutamento mais lento (≥ 2 turnos de relação 5 → 7): intencional (mecânica Python).
- `apply_npc_death` em evento vindo do LLM só roda após validação (já existente) — não mata por alucinação.

## 8. Pontos de decisão do dono

- **D-A (teto de relação por turno):** ±1 (default) ou ±2.
- **D-B (companheiro morto na party):** remover da lista (default) ou manter com `dead=True` para memorial/crônica.

## 9. Evidência requerida

- `uv run pytest` completo; testes antes/depois; run_ids do playtest.
- `docs/<spec>/README.md` com `repro6.py` transcrito, lista de sites varridos por R2 e handoff ao corpus SPEC-171
  (caso "NPC morto responde" como regressão).
