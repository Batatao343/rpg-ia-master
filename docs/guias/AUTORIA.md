# AUTORIA.md — Como adicionar e curar conteúdo do mundo (Fase 7.2)

O conteúdo autoral vive em três camadas, cada uma com regras próprias de edição:

| Camada | Onde | Quem escreve | Sobrevive ao migrate? |
|---|---|---|---|
| Fonte do lore | `lore_nova/*.txt` | você (formato `[CATEGORIA:]`) | é a FONTE — sempre |
| Codex gerado | `data/codex/**/*.md` | `scripts/migrate_lore_nova.py` | **NÃO** (regenerado) |
| Curadoria | `data/codex_overrides.yaml`, arquivos `curated: true`, `data/graph/entities_extra.json`, `edges.json`, `relation_types.json`, `components.json` | você | **SIM** |
| Canônico de segunda camada | `data/codex/npcs/mundo_vivo/` (36 NPCs regionais, gerados por `scripts/gen_world_living_npcs.py` e mantidos com `curated: true`) | você | **SIM** — `lore_nova/` deixa de ser a "fonte única" para NPCs: estes vivem só aqui |

Validação em toda ponta: `uv run python scripts/validate_content.py` (lint 7.1)
roda também como teste (`tests/test_fase71.py::test_repo_content_sem_erros`) e
como gate do reindex — `uv run python rag.py` **aborta** se o lint achar ERRO.

Arte curada segue um pipeline separado, também coberto pelo mesmo lint. Consulte
`docs/guias/ARTE_VISUAL.md`: PNG/ZIP nunca é publicado diretamente; o importador
Python valida manifesto, visibilidade e SHA antes de gerar WebP versionado.

---

## Fluxo A — Adicionar entidade manual (ex.: NPC novo)

1. Copie o template do tipo em `docs/templates/codex/` (NPC de trama: `npc_trama.md`) para a
   pasta certa do Codex (ex.: `data/codex/npcs/npc_maera_dos_sais.md`).
   - Nome do arquivo = `id` do frontmatter (lint valida).
   - **`curated: true` é OBRIGATÓRIO** — sem ele o próximo migrate APAGA o arquivo.
   - Segredos NÃO vão no doc público: crie doc paralelo em
     `data/codex/npcs/segredos/{id}_segredo.md` com `type: npc_secret` e
     `visibility: hidden` (padrão da Fase 7.3). **O doc de segredo de entidade curada
     também leva `curated: true`** (SPEC-374): ele não sai de `lore_nova/` e o migrate
     apaga todo `.md` sem a marca. O lint dá ERRO se faltar.
2. Registre a entidade em `data/graph/entities_extra.json` (o migrate não toca
   nesse arquivo): `id`, `type`, `name`, `aliases`, `tags`, `visibility`,
   `components` — mesmo shape das entradas existentes. Sem isso o lint dá AVISO
   e `related_entities` de outros docs não podem apontar para ela.
3. (Opcional) Relações em `data/graph/edges.json` (`id` único, `type` existente
   em `relation_types.json`).
4. Valide: `uv run python scripts/validate_content.py` → 0 ERROs.
5. Reindexe: `uv run python rag.py` (precisa de `GOOGLE_API_KEY`; o lint roda
   antes e aborta se algo estiver quebrado).

## Fluxo B — Curar entidade GERADA (sem perder no próximo migrate)

Nunca edite um `.md` gerado diretamente (o migrate sobrescreve). Em vez disso,
adicione um patch em `data/codex_overrides.yaml`:

```yaml
npc_valerius:
  aliases: ["Lorde Protetor", "O Imortal de Arcádia"]
  tags_extra: ["governante_supremo"]   # ADICIONA às tags geradas
  visibility: public                    # sobrescreve
  related_entities: [nova_arcadia]      # SUBSTITUI a lista
  append_body: |
    Nota de curadoria anexada ao fim do corpo.
```

- O patch é aplicado pelo migrate DEPOIS da geração e reflete no `.md` e em
  `entities.json`.
- Id que não existe no Codex = ERRO de lint (typo não passa batido).
- Override apontando para arquivo `curated: true` é ignorado (AVISO de lint) —
  arquivo manual se edita direto.

## Fluxo C — Regerar o Codex (depois de editar `lore_nova/`)

```bash
uv run python scripts/migrate_lore_nova.py   # regenera data/codex/ + entities.json
uv run python scripts/gen_world_living_npcs.py # recoloca os NPCs de mundo_vivo em entities.json/edges.json
uv run python scripts/lore_reanchor.py --base <commit>  # reaponta as âncoras `arquivo.txt:N` dos dados de mundo
uv run python scripts/validate_content.py    # lint — 0 ERROs antes de seguir
uv run python rag.py                          # reindexa FAISS (gate de lint embutido)
uv run pytest -q                              # suíte offline (inclui gate de conteúdo)
```

O migrate preserva: arquivos `curated: true`, `codex_overrides.yaml` (reaplicado),
`entities_extra.json`, `edges.json`, `relation_types.json`, `components.json`.
Rodar 2× seguidas produz o mesmo resultado (idempotente).

---

## Regras que o lint garante (resumo da 7.1)

- Frontmatter completo (`id/type/name/tags/visibility`); `id` == nome do arquivo.
- Ids únicos (Codex, `entities.json` × `entities_extra.json`); `components.json`
  sem id órfão.
- `related_entities` e edges apontam para entidades existentes; edges respeitam
  as constraints de `relation_types.json`.
- Aliases não colidem entre entidades (normalização: minúsculas + sem acento).
- `type: secret` ⇒ `visibility: secret`; doc `public` não referencia entidade
  `secret`; doc de NPC público não contém rótulo de parágrafo secreto (7.3).
- Tudo UTF-8 estrito (mojibake vira AVISO).
- O catálogo visual aponta apenas para IDs canônicos/públicos; os derivados
  existem, batem hash/bytes e respeitam cobertura do onboarding/mapa e tetos.

---

## Fluxo D — Editar cards do onboarding (wizard de criação)

O wizard de criação de personagem (spec onboarding-valoria) lê `data/onboarding.json`:
`world_intro` (3 parágrafos) + 1 card por região/classe/raça dos JSONs canônicos.

1. Editar `data/onboarding.json` direto (conteúdo curado à mão, zero LLM).
2. Limites de campo (testados em `tests/test_onboarding.py`): `tagline` ≤ 90,
   `description` ≤ 400, `hook` (região) ≤ 200, `playstyle` (classe) ≤ 160.
3. Chaves: `regions.*`/`races.*` usam os **ids** de `origins.json`;
   `classes.*` usa os **nomes** exatos de `classes.json`.
4. `name`/`bonus` dos cards de região e `name` dos de raça devem espelhar
   `origins.json` (teste anti-drift falha se divergirem).
5. **Regra de visibilidade (R9):** os cards NÃO podem citar entidade cujo doc
   do Codex seja `visibility: hidden|secret` (ex.: reveals da timeline era-7).
   Testado por `test_onboarding_no_hidden_entities`; na dúvida, escrever
   conteúdo novo em vez de extrair do lore.
6. Região/classe/raça nova nos JSONs canônicos SEM card correspondente quebra
   a suíte (cobertura é bidirecional — drift ruidoso por construção).

---

## Fluxo E — Trama de região (SPEC-350)

Povoa uma região com tramas: catálogo curado em `data/world/plot_threads.json`
(tramas, portas, elenco `cast`, `waves`, `excluded`), lido por `services/plot_threads.py`
e validado por `validate_plot_threads` (roda em `validate_content.py` e no gate do `rag.py`).
Uma onda por spec (≤ 12–14 NPCs novos; qualidade > volume).

1. **Sondas.** Seção regional de `lore_nova/npcs.txt` (Grep + Read com offset), mundo vivo
   da região, facções, rumores (`rumor_seeds.json` por região), rotas de `lore_quests.json`.
2. **Mapa + nomes** (tabela: trama, pergunta, núcleo, borda, ≥ 3 portas em ≥ 2 locais) →
   aprovação antes de escrever texto.
3. **Autoria.** Doc público curado em `data/codex/npcs/tramas/` (template
   `docs/templates/codex/npc_trama.md`), doc de segredo em `segredos/`, entidade em
   `entities_extra.json`, arestas em `edges.json` (aresta de facção secreta com
   `visibility: hidden`), `agenda_by_npc` em `npc_world.json`, ficha no `cast`
   (desejo/medo ≤ 90, tópico de segredo ≤ 60, voz com fala ≤ 120). Canônico da lore entra
   só por ficha (campo `fonte` = arquivo:linha), sem reescrever a lore.
4. **Regras duras do lint:** âncora de porta nunca é núcleo/líder; nada de "escolhido"
   nem de "você" nos textos de mundo; sem termo `[proibidos]` do léxico de Valoria; sem
   assinatura de segredo nem frase de `data/world/leak_phrases.json` em campo público;
   palavra exclusiva do doc de segredo não pode aparecer na ficha; papéis de NPCs novos da
   mesma região com radicais diferentes; fichas com Jaccard < 0,35.
5. `uv run python scripts/validate_content.py` → 0 ERRO; `tests/test_spec350_*`.
6. Revisão independente (rubrica da SPEC-350 §3.8) → `handoffs/SPEC-<NNN>-review.md`.
7. `uv run python rag.py` (reindex) + smoke real na região; então `waves[...].status = "done"`.
8. Ligar em jogo: `RPG_PLOT_THREADS=on` (prompt do NPC + roster da região atual).


## Fluxo F — Cartas e classes (SPEC-376)

`data/` é a fonte. Não existe gerador: `gen_cards_v4.py` e `gen_classes_v2.py` foram removidos pela
SPEC-376 porque regravavam do zero e apagavam curadoria (`momento`, `raridade`, `reacao_inicial`;
medição em `docs/spec376/deriva.md`).

1. **Carta de classe:** editar `data/cards/{classe}.json` à mão. Carta publicada mudou de efeito →
   objeto novo com o mesmo `id` e `versao` + 1 (detalhes em `docs/design/CARTAS.md`).
2. **Onda de Cartas por Postura:** esteira da SPEC-336, `scripts/cards/draft.py` → `lint.py` →
   `sim.py` → `promote.py` (grava em `data/cards/posturas/`).
3. **Classe:** editar `data/classes.json` (`docs/design/CLASSES.md`). `gen_tiers_5_plus.py` só em
   `--check`; `--write` exige seleção humana (SPEC-355 R6).
4. **Bestiário legado:** `scripts/migrate_bestiary_v4.py` sobrescreve curadoria e só grava com `--write`.
5. Validar: `uv run python scripts/cards/lint.py` e `bash scripts/dev/pt.sh tests/test_conflito_autoria_cartas.py`.

**Arte de criatura do pool (`bst_<id>`):** `scripts/import_bestiary_art.py` avisa no stdout quando o id não está no pool conhecido localmente (o pool real é dinâmico); `--strict` transforma o aviso em erro.
