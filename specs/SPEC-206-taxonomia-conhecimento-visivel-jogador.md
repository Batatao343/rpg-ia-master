# SPEC-206 — Taxonomia de conhecimento visível ao jogador

> **Status:** `draft`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** SPEC-234 `done` (mapa segredo↔entidade) · SPEC-007, SPEC-024, SPEC-028, SPEC-085, SPEC-149 e SPEC-171 `done` não reabertas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-207, SPEC-211, SPEC-212, SPEC-215 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 12 (parte a — só o que o JOGADOR vê; conhecimento por NPC fica na SPEC-215)
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — corpus novo de vazamento/certeza do Codex do jogador (`player_knowledge`), com evaluator próprio, autorado em tarefa separada antes da implementação; os datasets da SPEC-171 (`evals/datasets/regression/narrative_npc.jsonl`) não são tocados.

Rótulos: **[F]** fato observado no HEAD `6b94f66`; **[D]** decisão de produto fechada; **[H]** hipótese técnica; **[R]** recomendação.

---

## 1. Contexto & Objetivo

[D] `DECISOES_PRODUTO.md` define o Codex e o Bestiário como "dossiês vivos" que
distinguem fato, suspeita, rumor, percepção e visibilidade do jogador, sem abrir
segredos privados. A ordem fecha isso em P3 (consistência de memórias e segredos),
mas a SPEC-211 (dossiês) e a SPEC-207 (export) precisam do contrato antes.

[F] O repositório já tem as peças de autoridade, espalhadas:
- `services/memory_provenance.py:19-38` — `MemoryProvenance` fechado
  (`canonical_event | player_observation | npc_claim | inference | legacy_unverified`)
  e `_CONFIDENCE_BY_PROVENANCE` → `confirmed | reported | speculative`. A confiança
  é derivada por `MemoryFactRecord._derive_authority` e nunca vem da LLM.
- `accepted_secret_ids(state)` (`:154`) só aceita evento `secret_revealed` do
  `event_log`; `find_strict_unrevealed(text, state)` (`:170`) detecta assinatura de
  `SECRET_SIGNATURES` sem reveal aceito.
- `services/secret_signatures.py:45` `revealed_corpus` é **mais permissivo**: também
  considera `narrative_summary` (prosa) e `player.known_secrets` como reveal.
  [F] `player.known_secrets` é lido ali, mas não é declarado em `state.py` nem escrito
  por nenhum módulo de produção (grep em `api.py`, `services/`, `agents/`, `state.py`).
- `state.py:380` `RevealedFact` e `WorldProjection.revealed_facts` (`:405`), gravados
  só por `services/event_processor.py:75` a partir de `secret_revealed`, validado por
  `services/world_validators.py:41` (exige edge `hidden/secret` no grafo).
- `GET /game/codex` (`api.py:1936`) → `services/discovery.py:219 player_codex(state)`,
  com cinco blocos: `locations`, `factions`, `characters`, `creatures`, `secrets`.
  Corpos vêm de `codex_loader.codex_body` (`services/codex_loader.py:96`), que devolve
  `""` para documento não `public`. **Porém o nome da entrada continua aparecendo.**
- Bestiário: `discovery.BESTIARY_TIERS` (tier 1 "Rumores" via `seen`, tier 2 via
  `fought`...); `BestiaryKnowledge` tem `first_seen_turn`/`last_update_turn`
  (`state.py:284`). Em combate, `services/bestiary_knowledge.py:31 public_panel`
  expõe apenas os campos de `_PUBLIC_FIELDS`.
- NPC: `knowledge_source ∈ met | mentioned | lore` e `known_by_player`
  (`services/npc_layers.py:74-75`); `created_turn`/`last_seen_turn` vêm de
  `agents/storyteller.py:238-274`. Facções: `faction_intel` `{known, knows_goal,
  progress_seen, intel_turn}` (`state.py:270`, escrita em `world_utils.py:436`).
- `rag.vis_rank` (`rag.py:572`) falha fechado: visibilidade desconhecida = `secret`.
- `web/src/components/CodexTab.tsx` mostra contagens `codex[id].length` por categoria
  e a marca "ouviu falar" só para `knowledge_source === "mentioned"`; `web/src/types.ts:641-692`
  não tem campo de certeza.

[F] Lacuna: o jogador não sabe distinguir, em nenhuma entrada, se aquilo é fato,
relato, rumor, suspeita ou percepção. Também não há regra única de visibilidade da
**entrada** (nome, contagem, arte), apenas do corpo.

**Objetivo:** criar uma projeção player-facing **derivada em leitura**, sem
ontologia paralela, que anote cada entrada do Codex/Bestiário com
`knowledge_kind`, `certainty`, `source_kind`, `source_ref`, `first_seen_turn` e
`last_updated_turn`; e impor uma regra fail-closed de visibilidade de entrada,
verificada por oráculo determinístico.

## 2. Requisitos

- **R1 — Taxonomia fechada.** `KnowledgeKind = fact | report | rumor | suspicion | perception`
  (rótulos pt-BR: "Fato confirmado", "Relato", "Rumor", "Suspeita", "Percepção").
  Nenhum outro valor é serializado.
- **R2 — Sem ontologia paralela.** `source_kind` reutiliza literalmente
  `MemoryProvenance`. `certainty` reutiliza `MemoryConfidence` e é derivado de
  `_CONFIDENCE_BY_PROVENANCE`. `knowledge_kind` é função pura de
  (`source_kind`, origem estrutural) pela tabela da §3.2. Nenhum campo novo é
  persistido no save.
- **R3 — Proveniência por entrada.** Toda entrada projetada carrega
  `source_ref` (string estrutural, §3.3), `first_seen_turn: int | None` e
  `last_updated_turn: int | None`. Quando o save não tem o turno, o valor é `None`;
  nunca é inventado.
- **R4 — Fail-closed de entrada.** Uma entrada cuja entidade canônica tem
  visibilidade `hidden`/`secret` (ou desconhecida, via regra de `vis_rank`) e não
  está em `accepted_secret_ids(state)` é **omitida inteira**: nome, corpo, meta,
  tooltip, contagem de categoria e referência visual. O filtro é aplicado no
  servidor, antes da serialização.
- **R5 — Reveal estrito.** O reveal para o Codex do jogador usa apenas
  `accepted_secret_ids` (evento canônico). `revealed_corpus` (prosa e
  `known_secrets`) não autoriza exibição de entrada nem de texto.
- **R6 — Varredura de texto.** Todo texto projetado (`name`, `body`, `fact`, `goal`,
  `role`, `description`, `notes[].text`) passa por `find_strict_unrevealed`. Se
  houver acerto, aquele campo é substituído pelo rumor público de
  `PUBLIC_RUMOR[secret_id]` quando for `notes[].text`. Nos demais casos, a entrada
  inteira é omitida. O evento é contado em `redactions` (agregado, sem texto).
- **R7 — Promoção só por evento canônico.** Uma entrada só passa de
  `rumor`/`report`/`suspicion` para `fact` quando houver fonte estrutural do motor:
  `fought ≥ 1` no bestiário, `knowledge_source == "met"`, `revealed_facts`, ou
  `MemoryFact` com `provenance = canonical_event` e `source_is_applicable`. Repetir
  relato, ou ter vários relatos concordantes, nunca promove.
- **R8 — Legado.** `MemoryFact` com `legacy_unverified` aparece com
  `knowledge_kind = report`, `certainty = speculative` e `label = "Relato não verificado"`.
  Um save sem `memory_facts`, `last_seen_turn` ou `intel_turn` carrega e projeta
  sem erro.
- **R9 — Notas de memória ancoradas.** Entradas do ledger `memory_facts` só
  aparecem como `notes[]` de uma entrada já visível, ligadas por
  `canonical_entity_ids`. Nota sem âncora visível não é exibida.
- **R10 — Bestiário em combate.** `public_panel` permanece a única visão do
  inimigo durante o conflito. Esta spec não adiciona campos a ele e o oráculo prova
  que nenhum campo fora de `_PUBLIC_FIELDS` aparece.
- **R11 — Compatibilidade de API.** `GET /game/codex` mantém as cinco chaves e os
  campos atuais. Os novos campos são aditivos. O frontend antigo continua
  funcionando sem ler os novos campos.
- **R12 — Oráculo determinístico.** `assert_no_player_leak(codex_json, state)`
  falha se: (a) aparecer qualquer `entity_id` ou nome de entidade não revelada;
  (b) `find_strict_unrevealed` acertar o JSON serializado; (c) a contagem de
  categoria divergir da lista filtrada; ou (d) aparecer `knowledge_kind` fora de
  R1 ou `fact` sem fonte de R7.
- **R13 — UI.** `CodexTab` mostra um selo de `knowledge_kind` por entrada e por
  nota, e um tooltip montado só com `label`, `first_seen_turn` e
  `last_updated_turn`. A contagem usa a lista já filtrada. Nenhuma tela lê campos
  privados.
- **R14 — Zero LLM.** A projeção é Python puro, sem `get_llm`, RAG ou rede.

### Fora de escopo

- Conhecimento por NPC (`observed_by`, `told_to`, `believed_by`, propagação e
  mensageiro): SPEC-215.
- Layout de dossiê, retrato por entrada e seções novas do Codex: SPEC-211. Abas do
  shell: SPEC-204.
- Export para juiz: SPEC-207, que **consome** esta projeção.
- Mudança de `SECRET_SIGNATURES`/`PUBLIC_RUMOR`, de `validate_narrative`, de
  `revealed_corpus` (usado pelo guard de beat e pelo playtest), do archivist ou da
  escrita de `memory_facts`.
- Editar `evals/datasets/regression/narrative_npc.jsonl`, evaluators existentes ou
  `manifest.lock.json`.
- Migração de save ou novo `SCHEMA_VERSION` (continua `8`, `persistence.py:59`).
- Corrigir a escrita ausente de `player.known_secrets` (ver §8).

## 3. Design técnico

### 3.1 Arquivos

- **Novo** `services/player_knowledge.py`: taxonomia, derivação e filtro. Puro e
  determinístico.
- **Alterado** `services/discovery.py`: `player_codex` passa a chamar
  `project_player_knowledge(state, raw)` sobre os blocos atuais. Os blocos privados
  `_locations_block` e similares continuam sendo a fonte; nenhum é removido.
- **Alterado** `api.py:1936`: sem mudança de rota. A resposta ganha campos
  aditivos e `meta`.
- **Alterado** `web/src/types.ts` (interfaces `Codex*` com campos opcionais) e
  `web/src/components/CodexTab.tsx` (selo, tooltip e contagem filtrada).
- **Novo** `tests/test_player_knowledge.py`.
- **Handoff de eval**: `handoffs/SPEC-206-eval-authoring.md` descreve o corpus
  `player_knowledge` (§9). O implementador não cria nem edita o dataset ou o
  evaluator.

### 3.2 Tabela de derivação (única fonte)

| Origem estrutural no save | `source_kind` | `certainty` | `knowledge_kind` |
|---|---|---|---|
| `world.visited` (local) | `canonical_event` | confirmed | `fact` |
| `revealed_facts[event_id]` | `canonical_event` | confirmed | `fact` |
| `bestiary_knowledge` com `fought ≥ 1` | `canonical_event` | confirmed | `fact` |
| `bestiary_knowledge` só com `seen` (tier 1) | `npc_claim` | reported | `rumor` |
| NPC `knowledge_source == "met"` | `canonical_event` | confirmed | `fact` |
| NPC `knowledge_source == "mentioned"` | `npc_claim` | reported | `rumor` |
| NPC `knowledge_source == "lore"` | `npc_claim` | reported | `report` |
| `faction_intel.known` sem `knows_goal` | `npc_claim` | reported | `report` |
| `faction_intel.known` com `knows_goal` (`goal`) | `npc_claim` | reported | `report` (+ `stale` se `intel_turn` < turno atual) |
| `MemoryFact` `canonical_event` com fonte aplicável | `canonical_event` | confirmed | `fact` |
| `MemoryFact` `canonical_event` **sem** fonte aplicável (projetado como `inference`; o ledger não muda) | `inference` | speculative | `suspicion` |
| `MemoryFact` `player_observation` | `player_observation` | reported | `perception` |
| `MemoryFact` `npc_claim` | `npc_claim` | reported | `report`, ou `rumor` se o texto casar o marcador de boato (abaixo) |
| `MemoryFact` `inference` | `inference` | speculative | `suspicion` |
| `MemoryFact` `legacy_unverified` | `legacy_unverified` | speculative | `report` (rótulo "Relato não verificado") |

[H] O marcador de boato reutiliza o padrão `_QUALIFIED` de
`services/narrative_evidence.py:55`, extraído para uma constante pública
compartilhada, sem duplicar a regex. A escolha entre extrair a constante ou
importá-la cabe ao executor. O comportamento do guard narrativo não muda.
[F] `npc_claim` é a única proveniência de segunda mão disponível, então "rumor"
fica distinto de "relato" apenas por sinal estrutural ou pelo marcador. Não há
classificação por LLM.

### 3.2b Vocabulário compartilhado (contrato para SPEC-207/211/215)

[R] Esta spec é a dona dos nomes abaixo; specs consumidoras **reutilizam o objeto
`knowledge` (`KnowledgeStamp`) inteiro**, sem redefinir valores:

- `knowledge_kind` ∈ `fact | report | rumor | suspicion | perception` (ids em inglês,
  rótulos pt-BR só em `label`). Não usar `fato`/`suspeita`/`percepcao` como valor.
- `certainty` ∈ `confirmed | reported | speculative` (= `MemoryConfidence`). Não é o
  mesmo eixo de `knowledge_kind`.
- Turnos: `first_seen_turn`/`last_updated_turn` (não `source_turn`, exceto em
  `KnowledgeNote`, onde `last_updated_turn` = `MemoryFact.source_turn`).

Ponte com o prompt 12 (vocabulário do lado NPC, dono = SPEC-215): `world_truth` →
`fact` só se houver fonte de R7; `observed_by` com o jogador presente → `perception`
(ou `fact` se evento canônico); `told_to` o jogador → `report`; boato/`local_rumor`
→ `rumor`; `believed_by` sem fonte → `suspicion`; `unknown`/`secret_visibility`
não revelado → **omitido** (R4), nunca serializado com rótulo. A SPEC-215 não pode
promover para `fact` na visão do jogador sem passar por R7.

### 3.3 Schemas e assinaturas

```python
# services/player_knowledge.py
KnowledgeKind = Literal["fact", "report", "rumor", "suspicion", "perception"]
KIND_LABEL_PT = {"fact": "Fato confirmado", "report": "Relato", "rumor": "Rumor",
                 "suspicion": "Suspeita", "perception": "Percepção"}

class KnowledgeStamp(TypedDict):
    knowledge_kind: KnowledgeKind
    certainty: MemoryConfidence            # reuso de memory_provenance
    source_kind: MemoryProvenance          # reuso de memory_provenance
    source_ref: str                        # ver formatos abaixo
    label: str                             # pt-BR; "Relato não verificado" p/ legado
    first_seen_turn: Optional[int]
    last_updated_turn: Optional[int]
    stale: bool                            # só facções; default False

class KnowledgeNote(KnowledgeStamp):
    memory_id: str
    text: str

def derive_stamp(origin: str, record: Mapping, state: Mapping) -> KnowledgeStamp: ...
def entity_is_player_visible(entity_id: Optional[str], state: Mapping) -> bool: ...
def project_player_knowledge(state: Mapping, raw: Mapping[str, list]) -> dict: ...
def assert_no_player_leak(codex: Mapping, state: Mapping) -> list[str]:  # [] = ok
```

Formatos de `source_ref`: `visited:<location_id>`, `event:<event_id>`,
`bestiary:<creature_id>`, `npc:<entity_id|nome>`, `faction:<faction_id>`,
`memory:<memory_id>`. Isso segue os prefixos já aceitos por
`source_is_applicable` (`npc:`, `codex:`) e o `event_id` do `event_log`.

Turnos usam `world.turn_count`: `bestiary.first_seen_turn/last_update_turn`,
`revealed_at_turn`, `npc.created_turn/last_seen_turn`, `intel_turn` e
`MemoryFact.source_turn`. Para `visited`, ambos os turnos são `None` [F]
(`world.visited` é lista sem turno).

`entity_is_player_visible` usa a visibilidade da entidade no grafo
(`graph_resolver.get_entity`) ou o frontmatter do Codex. Ausência de metadado
conta como `public`, e valor desconhecido conta como `secret` (paridade com
`rag.vis_rank`). Uma entidade não `public` só é visível se seu id estiver em
`accepted_secret_ids(state)`. Um NPC sem `entity_id` resolvido usa só
`known_by_player`, como hoje.

### 3.4 Contrato de API (aditivo)

```json
{
  "locations": [{"id": "...", "name": "...", "body": "...",
                 "knowledge": {"knowledge_kind": "fact", "certainty": "confirmed",
                               "source_kind": "canonical_event", "source_ref": "visited:...",
                               "label": "Fato confirmado", "first_seen_turn": null,
                               "last_updated_turn": null, "stale": false},
                 "notes": []}],
  "factions": [...], "characters": [...], "creatures": [...], "secrets": [...],
  "meta": {"taxonomy_version": 1, "counts": {"locations": 1, "...": 0},
           "redactions": 0}
}
```

`meta.counts` é calculado após o filtro e é a fonte da contagem da UI.
`redactions` é um inteiro agregado, sem ids nem texto.

### 3.5 State ownership

[F] Esta spec **não escreve no estado**. Donos atuais, inalterados:
`event_processor` → `revealed_facts`; `discovery.record_*` → `bestiary_knowledge`;
`agents/npc.py` e `storyteller` → `npcs[*]`; `world_utils` → `faction_intel`;
archivist e `memory_provenance.commit_memory_facts` → `memory_facts`.
`player_knowledge` é somente leitura.

### 3.6 Degradação

- Falha ao derivar uma entrada (dado malformado) → a entrada é omitida
  (fail-closed). O log `rpg.player_knowledge` registra `reason` e categoria, sem
  texto. O endpoint nunca responde 500 por isso.
- Grafo ou Codex indisponível para resolver visibilidade → a entidade é tratada
  como `secret` e omitida.
- Sem `memory_facts` → `notes: []`.

## 4. Plano passo a passo (TDD)

### Etapa 0 — Handoff de eval (antes do código)
1. Escrever `handoffs/SPEC-206-eval-authoring.md` com os casos de §9. A autoria
   do dataset e do evaluator ocorre em tarefa separada, revisada por Astra.
   O implementador consome o corpus só depois de travado no manifesto.

### Etapa 1 — Derivação pura
1. **Testes** (`tests/test_player_knowledge.py`):
   - `test_derivation_table_is_total`: toda linha de §3.2 gera o stamp esperado.
   - `test_kind_values_closed`: R1.
   - `test_source_kind_reuses_memory_provenance`: `get_args` coincide com
     `MemoryProvenance` (R2).
   - `test_legacy_maps_to_unverified_report`: R8.
   - `test_turns_none_when_missing`: R3.
2. **Implementação:** `derive_stamp`, `KIND_LABEL_PT`.

### Etapa 2 — Visibilidade fail-closed
1. **Testes:**
   - `test_hidden_entity_omitted_without_reveal`: um NPC/local `hidden` some de
     nome, corpo e `meta.counts`.
   - `test_hidden_entity_shown_after_secret_revealed_event`: aparece após o
     evento.
   - `test_summary_or_known_secrets_do_not_reveal`: prosa em
     `narrative_summary` e `player.known_secrets` não liberam a entrada (R5).
   - `test_unknown_visibility_is_secret`.
   - `test_signature_in_text_redacts_entry`: R6 conta `redactions`.
2. **Implementação:** `entity_is_player_visible` e o filtro em
   `project_player_knowledge`.

### Etapa 3 — Notas e promoção
1. **Testes:**
   - `test_note_requires_visible_anchor`: R9.
   - `test_repeated_npc_claim_never_promotes`: R7.
   - `test_bestiary_rumor_becomes_fact_only_on_fought`: R7.
   - `test_canonical_without_applicable_source_is_suspicion`.
   - `test_rumor_marker_from_shared_pattern`.
2. **Implementação:** anexar `notes[]` por `canonical_entity_ids`.

### Etapa 4 — Oráculo e endpoint
1. **Testes:**
   - `test_oracle_flags_each_leak_class`: os quatro ramos (a)–(d) de R12, com
     fixture adversarial.
   - `test_codex_endpoint_additive`: as chaves antigas continuam presentes
     (`TestClient`, MockLLM).
   - `test_public_panel_unchanged`: R10.
   - `test_legacy_save_roundtrip_projects`: um save v8 sem os campos opcionais
     carrega, projeta e salva sem diff de schema.
2. **Implementação:** fiação em `player_codex`, `meta`, log.

### Etapa 5 — UI
1. Teste Node/Playwright: `CodexTab` mostra o selo e usa `meta.counts` quando
   presente, com fallback para `.length`. Viewports 390 e 1440 sem overflow.
2. **Verificação:** `uv run pytest` verde e `cd web && npm run build` verde.

## 5. Critérios de aceite

- [ ] R1–R14 cobertos pelos testes nomeados na §4.
- [ ] O corpus `player_knowledge` foi autorado em tarefa separada, travado e
      passa 100% com zero vazamento.
- [ ] O oráculo `assert_no_player_leak` passa em todos os saves-fixture de
      `tests/` que exercitam `/game/codex`.
- [ ] Nenhum arquivo de `evals/` protegido foi alterado pelo implementador
      (`git diff` limitado a `services/`, `api.py`, `web/`, `tests/`, `handoffs/`).
- [ ] Nenhum campo de imagem/retrato/URL de arte aparece para entidade omitida por R4 (assert no oráculo, ramo (a)).
- [ ] Sem novo `SCHEMA_VERSION`, e saves antigos continuam carregando.
- [ ] `uv run pytest` verde (suíte offline completa) e `npm run build` verde.
- [ ] Revisão Astra independente APPROVED, com foco em semântica da taxonomia e
      ausência de canal de vazamento.

## 6. Smoke

Offline, sem provider (R14 garante que não há LLM no caminho):
1. Criar um jogo MockLLM, jogar 5 turnos e chamar `GET /game/codex`. Conferir os
   stamps e `meta.counts`.
2. Injetar um evento `secret_revealed` válido num save de teste e conferir que a
   entrada aparece com `fact` e `source_ref=event:<id>`.
3. Injetar um `narrative_summary` com uma assinatura de `pacto_valerius` sem o
   evento. Conferir que nada aparece e que `redactions` fica em ≥ 0, sem texto.
4. Browser: abrir a aba Codex, verificar selo e tooltip, e confirmar que a
   contagem bate com a lista.

Provider real **não é necessário**. Se o dono quiser um smoke de campanha real,
ele é opt-in, com teto de 10 requests e US$ 0,05.

## 7. Riscos & compatibilidade

- **Saves:** derivação em leitura, sem migração. Risco baixo. Coberto por
  `test_legacy_save_roundtrip_projects`.
- **Regressão de UX:** entradas hoje visíveis com corpo vazio, por entidade
  `hidden`, passam a sumir por completo. Isso é intencional (R4), mas muda
  contagens. [H] Saves de playtest podem mostrar menos NPCs `lore`.
- **Divergência de reveal:** `revealed_corpus` (permissivo) continua sendo usado
  pelo guard de beat e pelo playtest. Esta spec adota o critério estrito só para
  a superfície do jogador. A divergência é documentada e não unificada aqui.
- **Rumor por regex:** o marcador pode gerar falso rumor ou falso relato. O
  impacto se limita ao rótulo, nunca à visibilidade, e o corpus de eval mede isso.
- **Performance:** `find_strict_unrevealed` é O(texto × assinaturas), com 4
  segredos hoje. O Codex é on-demand, fora do turno, então a latência do turno
  não muda.
- **MockLLM/FallbackLLM:** não se aplica, porque não há chamada LLM.

## 8. Pontos de decisão do dono

1. **Expor `memory_facts` ao jogador como notas (R9)?** Default recomendado [R]:
   sim, só ancoradas em entrada visível e só `report/perception/suspicion/fact`.
   A alternativa é adiar notas para a SPEC-211 e mostrar só os stamps das
   entradas.
2. **Corrigir `player.known_secrets` (lido e nunca escrito)?** Default [R]: fora
   desta spec. Registrar como achado para uma spec de higiene que decida entre
   remover a leitura ou criar um writer via `secret_revealed`.
3. **Selo "intel defasada" em facções (`stale`).** Default [R]: mostrar como
   sufixo discreto ("pode estar desatualizado"), sem número.

## 9. Evidência requerida

- Saída de `uv run pytest -q` (contagem) e de `npm run build`.
- Relatório do corpus `player_knowledge` (autoria separada), com pelo menos:
  entidade `hidden` sem reveal; reveal por evento; reveal só por prosa (deve
  falhar); relato repetido; legado; bestiário rumor→fato; NPC
  mentioned→met; facção sem e com objetivo; nota sem âncora; assinatura em nota;
  contagem vs lista. Métricas: `leak_count = 0` (hard gate), `kind_accuracy`,
  `count_consistency = 1.0`.
- `docs/spec206/README.md` com JSON de exemplo do `/game/codex` antes e depois
  (save sintético), lista de arquivos alterados e parecer Astra.
- Screenshot da aba Codex em 390 e 1440 px.
