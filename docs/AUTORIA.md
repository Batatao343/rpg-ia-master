# AUTORIA.md — Como adicionar e curar conteúdo do mundo (Fase 7.2)

O conteúdo autoral vive em três camadas, cada uma com regras próprias de edição:

| Camada | Onde | Quem escreve | Sobrevive ao migrate? |
|---|---|---|---|
| Fonte do lore | `lore_nova/*.txt` | você (formato `[CATEGORIA:]`) | é a FONTE — sempre |
| Codex gerado | `data/codex/**/*.md` | `scripts/migrate_lore_nova.py` | **NÃO** (regenerado) |
| Curadoria | `data/codex_overrides.yaml`, arquivos `curated: true`, `data/graph/entities_extra.json`, `edges.json`, `relation_types.json`, `components.json` | você | **SIM** |

Validação em toda ponta: `uv run python scripts/validate_content.py` (lint 7.1)
roda também como teste (`tests/test_fase71.py::test_repo_content_sem_erros`) e
como gate do reindex — `uv run python rag.py` **aborta** se o lint achar ERRO.

---

## Fluxo A — Adicionar entidade manual (ex.: NPC novo)

1. Copie o template do tipo em `docs/templates/codex/` (ex.: `npc.md`) para a
   pasta certa do Codex (ex.: `data/codex/npcs/npc_maera_dos_sais.md`).
   - Nome do arquivo = `id` do frontmatter (lint valida).
   - **`curated: true` é OBRIGATÓRIO** — sem ele o próximo migrate APAGA o arquivo.
   - Segredos NÃO vão no doc público: crie doc paralelo em
     `data/codex/npcs/segredos/{id}_segredo.md` com `type: npc_secret` e
     `visibility: hidden` (padrão da Fase 7.3).
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
