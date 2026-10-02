# SPEC — Fase 7.2 — Pipeline de autoria: curadoria preservada, templates e reindex com gate

> **Status:** `done` (2026-07-05)
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** 7.1 (validadores) `done`
> **Desbloqueia:** 7.3 (segredos de NPC), crescimento de conteúdo sem medo do migrate

---

## 1. Contexto & Objetivo

`migrate_lore_nova.py` regera `data/codex/` e `data/graph/entities.json` **do
zero**: qualquer curadoria manual feita nos `.md` gerados (aliases, tags,
`related_entities`, overrides de visibility) ou em `entities.json` é perdida na
próxima rodada. O docstring avisa, mas isso trava a evolução: ou nunca mais se
roda o script, ou nunca se cura. O projeto já tem o padrão certo para resolver:
**overlay migration-safe** — `entities_extra.json` (2.5b) e `components.json`
(2.7) sobrevivem ao script porque vivem em arquivos que ele não toca.

Esta spec fecha o débito da 2.5 com três entregas: (1) **overlay de curadoria**
`data/codex_overrides.yaml` aplicado pelo migrate script no fim da geração —
patches de frontmatter por id que sobrevivem à regeração; (2) **arquivos manuais
preservados** — `.md` com `curated: true` no frontmatter não são apagados pelo
script (entidade correspondente vive em `entities_extra.json`, padrão já
existente); (3) **templates de autoria** por tipo de entidade + doc de workflow
(`docs/AUTORIA.md`) + **gate de validação no reindex**: `rag.py` roda o lint da
7.1 antes de ingerir e aborta com erro — conteúdo inválido nunca entra no FAISS.

Critério de aceite da Fase 7 no ROADMAP: "Adicionar NPC novo segue template, é
validado automaticamente, entra em entities.json com IDs únicos."

## 2. Requisitos

- **R1 — Overrides de frontmatter:** `data/codex_overrides.yaml` mapeia
  `id → patch` (`aliases`, `tags_extra`, `visibility`, `related_entities`,
  `append_body`); `migrate_lore_nova.py` aplica os patches após gerar cada
  arquivo — reroda o script, curadoria permanece.
- **R2 — Overrides refletem no grafo:** patch de `aliases`/`visibility`/`tags_extra`
  também atualiza a entrada correspondente em `entities.json` antes do dump.
- **R3 — Override órfão é erro de lint:** id em `codex_overrides.yaml` que não
  existe no Codex gerado → `Finding` ERRO (novo check em
  `services/content_validator.py`, validador `overrides`).
- **R4 — Arquivo manual preservado:** `.md` em `data/codex/` com `curated: true`
  no frontmatter NÃO é apagado nem sobrescrito pelo migrate script; sua entidade
  (quando registrável) vive em `entities_extra.json`. Lint valida: arquivo
  `curated` cujo id de entidade não está em `entities_extra.json` nem
  `entities.json` → AVISO (docs agregadores tipo `story_*` não registram — ok).
- **R5 — Templates:** `docs/templates/codex/` com um template por tipo —
  `local.md`, `faccao.md`, `raca.md`, `npc.md`, `monstro.md`, `artefato.md` —
  frontmatter completo (com `curated: true`) + seções guiadas comentadas. Ficam
  FORA de `data/codex/` (o `os.walk` do loader ingere qualquer `.md` lá dentro).
- **R6 — Reindex com gate:** `uv run python rag.py` roda `validate_all()` antes
  de ingerir; qualquer ERRO → aborta sem tocar nos índices FAISS, exit 1.
- **R7 — Workflow documentado:** `docs/AUTORIA.md` — passo a passo para
  (a) adicionar entidade manual via template, (b) curar entidade gerada via
  override, (c) rerodar migrate + validar + reindexar. CLAUDE.md aponta pra ele.

### Fora de escopo

- Separar segredos de NPC → **7.3**.
- Editor/UI de autoria — só arquivos + CLI.
- Migrar curadoria retroativa perdida (não existe backup do que já foi perdido).
- Validação semântica de prosa.

## 3. Design técnico

### Arquivos novos

- `data/codex_overrides.yaml` — curadoria declarativa (começa vazio/exemplo comentado).
- `docs/templates/codex/{local,faccao,raca,npc,monstro,artefato}.md`
- `docs/AUTORIA.md`
- `tests/test_fase72.py`

### Arquivos alterados

- `scripts/migrate_lore_nova.py` — (a) loop de delete pula `.md` com
  `curated: true`; (b) etapa final `apply_overrides(entities)` lê o YAML,
  reescreve frontmatter/corpo dos arquivos alvo e patcha `entities` antes do
  `json.dump`.
- `services/content_validator.py` — validador novo `overrides` (R3) + check R4;
  entra no `validate_all()`.
- `rag.py` — bloco de ingestão de lore chama `validate_all()`; com ERRO imprime
  achados e `sys.exit(1)` antes de qualquer `FAISS.from_documents`.
- `CLAUDE.md` — 1 linha apontando `docs/AUTORIA.md` na seção de comandos.

### Formato do `codex_overrides.yaml`

```yaml
# Curadoria migration-safe — aplicada por migrate_lore_nova.py DEPOIS da geração.
# Chaves por id do Codex. Campos suportados:
#   aliases:          substitui a lista de aliases
#   tags_extra:       tags ADICIONADAS às geradas (nunca remove)
#   visibility:       sobrescreve (public|hidden|secret)
#   related_entities: substitui a lista
#   append_body:      markdown anexado ao fim do corpo
npc_valerius:
  aliases: ["Lorde Protetor", "O Imortal de Arcádia"]
  tags_extra: ["governante_supremo"]

skallgard:
  related_entities: ["costa_negra"]
```

### Assinaturas

```python
# scripts/migrate_lore_nova.py
def load_overrides(path: str = os.path.join("data", "codex_overrides.yaml")) -> dict: ...
def apply_overrides(entities: Dict[str, dict], overrides: dict,
                    codex_dir: str = CODEX_DIR) -> List[str]:
    """Aplica patches nos .md gerados e no dict de entidades.
    Retorna ids não encontrados (o main imprime; lint 7.1 acusa como ERRO)."""

def is_curated(path: str) -> bool:
    """True se o frontmatter tem curated: true (delete loop pula)."""

# services/content_validator.py
def validate_overrides(codex_dir: str = CODEX_DIR,
                       overrides_path: str = "data/codex_overrides.yaml") -> list[Finding]: ...
```

`apply_overrides` reusa `parse_codex_file` + `write_codex_file`: lê o gerado,
funde patch, regrava. Ordem determinística (ids ordenados) para diff estável.

Precedência clara: **gerado < override**. Arquivo `curated: true` nunca recebe
override (é 100% manual; se o id aparecer no YAML e o arquivo for curated →
AVISO de lint "override ignorado").

### Template (exemplo `npc.md`)

```markdown
---
id: npc_<slug_do_nome>           # ex.: npc_maera_dos_sais — precisa ser único (lint valida)
type: npc
name: <Nome Exato>
aliases: []                       # apelidos que o librarian usa p/ dedupe
tags: [<regiao>, <papel>]         # ex.: [pantano_melancolia, curandeira]
visibility: public                # public | hidden | secret
related_entities: [<location_id>] # ids existentes (lint valida)
curated: true                     # OBRIGATÓRIO em arquivo manual — migrate não apaga
---

# <NOME EM CAIXA ALTA>

Papel: <uma linha>
Aparência: <2-3 linhas>

<história pública, comportamento, ganchos — segredos vão para a 7.3, não aqui>
```

> Lembrete no `AUTORIA.md`: entidade manual registrável (npc/monster/faction...)
> precisa de entrada em `data/graph/entities_extra.json` (id, type, name,
> aliases, tags, visibility, components) — `load_entities()` já faz o merge.

### `rag.py` — gate

```python
from services.content_validator import validate_all

findings = validate_all()
errors = [f for f in findings if f.severity == "error"]
if errors:
    for f in errors:
        print(f"❌ [{f.validator}] {f.path}: {f.message}")
    sys.exit(1)
```

Só no caminho de ingestão de lore (`__main__` / função de reindex) — `query_rag`
em runtime NÃO valida (custo por turno desnecessário; índice já nasceu válido).

## 4. Plano passo a passo

### Etapa 1 — Overrides no migrate

1. **Testes** (`tests/test_fase72.py`): `test_override_aliases_sobrevive_regeracao`
   (roda `apply_overrides` numa árvore tmp gerada por `write_codex_file`, checa
   frontmatter final); `test_override_tags_extra_nao_remove`;
   `test_override_append_body`; `test_override_patcha_entities_dict`;
   `test_override_orfao_retornado`.
2. **Implementação:** `load_overrides`, `apply_overrides`, chamada no fim de
   `main()`; criar `data/codex_overrides.yaml` com cabeçalho comentado.
3. **Verificação:** `/qa` verde; rodar `uv run python scripts/migrate_lore_nova.py`
   duas vezes → diff de `data/codex/` estável (idempotente).

### Etapa 2 — `curated: true` preservado

1. **Testes:** `test_curated_sobrevive_ao_delete_loop` (arquivo curated em tmp
   codex dir não é removido); `test_gerado_sem_curated_e_apagado`;
   `test_override_em_curated_vira_aviso`.
2. **Implementação:** `is_curated` + filtro no loop de delete do `main()`.
3. **Verificação:** `/qa` verde.

### Etapa 3 — Lint de overrides (extensão da 7.1)

1. **Testes:** `test_validate_overrides_id_orfao_erro`;
   `test_validate_overrides_ok`; `test_curated_sem_entidade_gera_aviso`.
2. **Implementação:** `validate_overrides` + registro no `validate_all()`.
3. **Verificação:** `/qa` verde; `scripts/validate_content.py` exibe o grupo novo.

### Etapa 4 — Gate no reindex

1. **Testes:** `test_reindex_aborta_com_erro_de_lint` (monkeypatch
   `validate_all` devolvendo ERRO → função de reindex levanta `SystemExit` sem
   chamar embeddings — mockar `get_embeddings`).
2. **Implementação:** gate no `rag.py` (caminho de ingestão).
3. **Verificação:** `/qa` verde.

### Etapa 5 — Templates + AUTORIA.md

1. **Testes:** `test_templates_existem_e_tem_frontmatter_valido` (parseia cada
   template com `parse_codex_file` substituindo placeholders `<...>` por dummy —
   ou valida presença dos campos obrigatórios por regex);
   `test_templates_fora_do_codex_dir` (nenhum `.md` de template sob `data/codex/`).
2. **Implementação:** 6 templates + `docs/AUTORIA.md` (3 fluxos do R7) + linha
   no CLAUDE.md.
3. **Verificação:** `uv run pytest` completo verde; seguir o AUTORIA.md à mão
   criando 1 NPC de teste (depois remover) — template → lint → entra.

## 5. Critérios de aceite

- [x] `migrate_lore_nova.py` rodado 2× seguidas: idempotente (diff estável);
      arquivo `curated: true` sobreviveu ao migrate no smoke real
- [x] Override órfão → ERRO de lint; CLI exit 1 (validador `overrides`)
- [x] `uv run python rag.py` com conteúdo inválido aborta SEM tocar `faiss_*_index/`
      (`reindex_global()` — gate antes de qualquer embedding; testado com monkeypatch)
- [x] NPC novo criado via template passa no lint e (com entrada em
      `entities_extra.json`) aparece em `load_entities()` — smoke executado
      (`npc_teste_smoke` criado, validado, sobreviveu ao migrate, removido)
- [x] `docs/AUTORIA.md` cobre os 3 fluxos (manual, override, regeração)
- [x] `uv run pytest` verde (suíte completa offline — 581 testes)
- [x] Guard de FallbackLLM — N/A (zero structured output novo)
- [x] Saves antigos continuam carregando (nada de estado de jogo mudou)

**Desvios:** smoke §6 rodou sem o round-trip de `query_rag` do NPC de teste
(exigiria 2 reindexações completas de ~2600 chunks só p/ o teste — caminho de
ingestão idêntico já validado 2× na mesma sessão com o Codex real); `rag.py`
ganhou a função `reindex_global()` (testável) em vez de gate inline no
`__main__`; `validate_overrides` ganhou `graph_dir` como 3º parâmetro (o check
R4 de curated-sem-entidade precisa do grafo).

## 6. Smoke test com LLM real

(2 requests de embedding — fora dos buckets de flash/pro)

1. Criar NPC manual via template (ex.: `npc_teste_smoke` em `data/codex/npcs/`
   + `entities_extra.json`), rodar `uv run python rag.py` → lint verde,
   reindexação completa.
2. `query_rag("npc_teste_smoke <nome>", "lore")` → chunk do NPC novo volta.
3. Limpar: remover NPC de teste + reindexar de novo.

## 7. Riscos & compatibilidade

- **Idempotência do migrate:** overrides aplicados pós-geração garantem que
  rodar N vezes converge; teste da Etapa 1 cobre.
- **YAML curado à mão pode ter typo:** R3 transforma typo em ERRO de lint
  visível, não em curadoria silenciosamente ignorada.
- **`curated: true` esquecido** em arquivo manual → migrate apaga. Mitigação:
  templates já vêm com o campo + AUTORIA.md destaca em negrito; arquivos
  manuais também ficam no git (recuperável).
- **Gate no reindex** não afeta runtime do jogo (só o script); MockLLM/quota
  irrelevantes — validação é offline, embeddings só depois do lint verde.
- **Saves antigos:** intocados.
