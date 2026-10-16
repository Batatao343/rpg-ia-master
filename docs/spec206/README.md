# SPEC-206 — evidência (taxonomia de conhecimento visível ao jogador)

**Status:** `in-progress` — código + testes offline prontos; faltam corpus de eval
(autoria separada, ver `handoffs/SPEC-206-eval-authoring.md`), revisão Astra e
screenshots 390/1440 da aba Codex.

## O que mudou

- `services/player_knowledge.py` (novo, puro, zero LLM/RAG): `KnowledgeKind`,
  `KIND_LABEL_PT`, `KnowledgeStamp`/`KnowledgeNote`, `derive_stamp` (tabela §3.2),
  `entity_is_player_visible` (grafo + frontmatter do Codex, desconhecido = secret,
  reveal só por `accepted_secret_ids`), `project_player_knowledge` (fail-closed por
  entrada, notas ancoradas, `meta`) e o oráculo `assert_no_player_leak` (ramos a–d).
- `services/discovery.py`: blocos crus viram `_raw_codex`; `player_codex` passa pela
  projeção. Chaves internas `_npc_key`/`_entity_id`/`_event_id` são removidas antes
  da serialização.
- `services/narrative_evidence.py`: `QUALIFIED_MARKER` público (alias `_QUALIFIED`).
- `api.py`: inalterado (rota igual; resposta ganha `knowledge`, `notes`, `meta`).
- Web: `types.ts` (campos opcionais), `codexKnowledge.ts` (helpers puros),
  `CodexTab.tsx` (selo + tooltip label/turnos + notas + contagem por `meta.counts`),
  `styles.css` (`.codex-knowledge`, `.codex-notes`).
- Sem escrita no estado, sem `SCHEMA_VERSION` novo (continua 8).

## Testes

- `tests/test_player_knowledge.py` (novo): derivação total (16 linhas), taxonomia
  fechada, reuso de `MemoryProvenance`/`MemoryConfidence`, legado, turnos `None`,
  stale, omissão de entidade oculta (local e NPC), reveal por evento, prosa/
  `known_secrets` não revelam, visibilidade desconhecida/grafo indisponível = secret,
  redação por assinatura (entrada e nota), entrada malformada omitida, nota exige
  âncora, relato repetido não promove, bestiário rumor→fato, NPC mentioned→met,
  canonical sem fonte → suspicion, marcador compartilhado, D1, oráculo (4 ramos +
  URL de arte), endpoint aditivo, `public_panel` inalterado, round-trip de save
  legado, projeção somente leitura, zero LLM.
- `tests/test_fase32.py`: oráculo assertado nos dois fixtures que exercitam o Codex.
- `web/tests/codexKnowledge.test.mjs` (novo): contagem `meta.counts`/fallback,
  tooltip só com label+turnos, sufixo stale.

## JSON de exemplo (save sintético, corpos truncados)

Save: visitou `nova_arcadia` e `mon_verme_primordial_das_raizes_do_mundo` (hidden);
Grum `mentioned`; rato só `seen`; `narrative_summary` cita o pacto (sem evento);
uma observação do jogador ancorada em `nova_arcadia`.

Antes: `locations` trazia as 2 entradas (o Verme com nome e corpo vazio); contagem 2.

Depois (trecho):

```json
{"locations": [{"id": "nova_arcadia", "name": "Nova Arcádia", "body": "…",
   "knowledge": {"knowledge_kind": "fact", "certainty": "confirmed",
     "source_kind": "canonical_event", "source_ref": "visited:nova_arcadia",
     "label": "Fato confirmado", "first_seen_turn": null, "last_updated_turn": null, "stale": false},
   "notes": [{"knowledge_kind": "perception", "certainty": "reported",
     "source_kind": "player_observation", "label": "Percepção", "first_seen_turn": 5,
     "last_updated_turn": 5, "memory_id": "mem_…", "text": "A praça do mercado estava vazia."}]}],
 "characters": [{"name": "Grum", "knowledge": {"knowledge_kind": "rumor", "source_ref": "npc:npc_grum", "…": "…"}}],
 "creatures": [{"id": "enemy_rato_peste_anel_lama", "knowledge": {"knowledge_kind": "rumor", "…": "…"}}],
 "meta": {"taxonomy_version": 1, "counts": {"locations": 1, "factions": 0,
   "characters": 1, "creatures": 1, "secrets": 0}, "redactions": 0}}
```

`assert_no_player_leak` → `[]`.

## Limites / riscos

- Entradas antes visíveis com corpo vazio por entidade `hidden` agora somem (R4,
  intencional): contagens mudam.
- O nome do Verme é assinatura de `rei_subterraneo`; revelar só a entidade não basta
  (fail-closed). Mapa em `data/secret_entities.json` não foi alterado.
- `player.known_secrets` segue lido por `revealed_corpus` e nunca escrito (D2 — fora
  de escopo, achado para spec de higiene).
- Rótulo rumor/relato por regex (`QUALIFIED_MARKER`) pode errar o rótulo, nunca a
  visibilidade.

## Resultado da verificação

- Suíte Python completa (`pytest -q -p no:warnings --ignore=tests/test_project_index.py -x`): exit 0, zero falhas (a contagem final não aparece por causa do duplo `-q`).
- Focados: `tests/test_player_knowledge.py` + `tests/test_fase32.py` com 73 passed.
- `npm run build` verde; `npm test` 45/45 (2 novos).
- Ruff verde em todos os arquivos Python tocados.

## Revisão Astra (2026-10-16) — APPROVED

- Corrigido: evasão da varredura por acento/quebra de linha (normalização em
  `player_knowledge`; +2 testes). `find_strict_unrevealed` inalterado.
- Sem canal de vazamento encontrado em `/game/codex`, `GameResponse`, `public_panel`,
  catálogo visual; `/data/map` inalterado (achado da SPEC-210 não piora).
- Capturas (API determinística do e2e + resposta `/game/codex` mínima):
  `codex-locations-390.webp`, `codex-characters-390.webp`,
  `codex-locations-1440.webp`, `codex-characters-1440.webp` — selos, notas e
  contagem `meta.counts`, sem overflow horizontal.
- Gate restante p/ `done`: corpus `player_knowledge` (autoria separada).
