# SPEC — Fase 7.1 — Validadores de conteúdo (lint do Codex + grafo) + CI

> **Status:** `done` (2026-07-05)
> **Criada:** 2026-07-05 · **Atualizada:** 2026-07-05
> **Depende de:** Fase 2.5 (Codex estruturado + grafo) `done`
> **Desbloqueia:** 7.2 (curadoria preservada), 7.3 (segredos de NPC), todo crescimento de conteúdo

---

## 1. Contexto & Objetivo

O Codex tem ~560 entidades geradas por script + curadoria manual em `edges.json`,
`relation_types.json`, `entities_extra.json` e `components.json`. Hoje a única
validação é em runtime e permissiva: `parse_codex_file` levanta `ValueError` de
frontmatter, `graph_resolver` imprime `⚠️` e **ignora** id órfão. Um edge apontando
para entidade que não existe, um alias duplicado ou um segredo marcado `public`
entram silenciosamente no jogo e só aparecem como inconsistência narrativa.

Esta spec cria o **lint de conteúdo**: funções puras que validam frontmatter,
referências, aliases, visibilidade e encoding de TODO o conteúdo autoral, um CLI
que roda o lint completo, testes que rodam o lint sobre os dados reais do repo
(o gate), e um workflow de GitHub Actions que roda a suíte em PR — fechando o
item "CI hook: validar novo conteúdo antes de merge" do ROADMAP.

Também paga o débito de encoding da Fase 2.5: os loaders já usam
`encoding="utf-8"` explícito (auditado 2026-07-05); o que falta é o **validador**
que garante que arquivos novos entram como UTF-8 válido (Windows default cp1252).

Princípio: **mecânica é Python, não LLM** — consistência de mundo é verificável
deterministicamente, então verificar sempre, antes de indexar e antes de mergear.

## 2. Requisitos

- **R1 — Frontmatter:** todo `data/codex/**/*.md` tem frontmatter YAML com
  `id`, `type`, `name`, `tags`, `visibility`; `id` == nome do arquivo (sem `.md`);
  `type` pertence ao conjunto canônico; `visibility` ∈ `{public, hidden, secret}`;
  `tags`, `aliases`, `related_entities` (quando presentes) são listas de strings.
- **R2 — IDs únicos:** nenhum `id` repetido entre arquivos do Codex; nenhum
  conflito entre `entities.json` e `entities_extra.json` (hoje warning em runtime
  → vira erro de lint); `components.json` só referencia ids existentes.
- **R3 — Referências:** todo `related_entities` de `.md` aponta para entidade em
  `load_entities()`; todo edge de `edges.json` tem `id` único, `source`/`target`
  existentes e `type` presente em `relation_types.json`; constraints do
  `relation_types.json` respeitadas (`target: "location"` → entidade target tem
  `type == "location"`; idem `source`).
- **R4 — Aliases:** normalizado (casefold + sem acento), nenhum alias se repete
  entre entidades distintas, nem colide com `name` ou `id` de OUTRA entidade.
- **R5 — Visibilidade:** doc com `type: secret` tem `visibility: secret`; doc
  `public` não lista em `related_entities` uma entidade/doc `secret` (vazaria a
  existência do segredo); `visibility` de entidade no grafo pertence ao conjunto.
- **R6 — Encoding:** todo `.md` de `data/codex/`, `.txt` de `lore_nova/` e
  `.json` de `data/graph/` decodifica como UTF-8 estrito (erro); heurística de
  mojibake (`Ã©`, `â€`, `Ã£` etc.) gera AVISO, não erro.
- **R7 — CLI:** `uv run python scripts/validate_content.py` imprime achados
  agrupados por validador com severidade `ERRO`/`AVISO`; exit code 1 se houver
  qualquer ERRO, 0 caso contrário (avisos não falham).
- **R8 — Gate nos dados reais:** teste offline roda o lint completo sobre os
  dados do repo e asserta zero ERROs — o repo atual precisa passar (violações
  existentes são corrigidas nesta spec ou entram numa whitelist documentada no
  próprio validador, com justificativa).
- **R9 — CI:** workflow GitHub Actions roda `uv run pytest` (suíte offline,
  `RPG_FORCE_MOCK=1` via conftest) em push/PR para `main` — conteúdo inválido
  não mergeia.

### Fora de escopo

- Templates de autoria e workflow de curadoria → **7.2**.
- Separação público/segredo dos NPCs → **7.3** (o R5 valida a regra; mover o
  conteúdo é a 7.3).
- Validação semântica por LLM (coerência de prosa) — só validação estrutural.
- Migrations/versionamento de saves — Fase 10.

## 3. Design técnico

### Arquivos novos

- `services/content_validator.py` — validadores puros, zero dependência de LLM/rede.
- `scripts/validate_content.py` — CLI fino sobre o service (print + exit code).
- `tests/test_fase71.py` — unit tests (fixtures em tmp_path) + gate sobre dados reais.
- `.github/workflows/validate.yml` — CI.

### Arquivos alterados

- Nenhum módulo de runtime muda de comportamento nesta fase (lint é aditivo).
  Se o gate R8 achar violação em dado real, o **dado** é corrigido (ex.: edge
  órfão em `edges.json`), não o validador afrouxado — exceto whitelist justificada.

### Schema

```python
from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning"]

@dataclass
class Finding:
    validator: str    # "frontmatter" | "ids" | "references" | "aliases" | "visibility" | "encoding"
    severity: Severity
    path: str         # arquivo onde foi achado (md/json)
    entity_id: str    # id envolvido ("" se não aplicável)
    message: str      # humano, em PT-BR

CODEX_TYPES = {
    "location", "faction", "npc", "race", "monster", "artifact",
    "items", "secret", "perspective", "world_story", "timeline",
}
VISIBILITIES = {"public", "hidden", "secret"}
```

### Assinaturas

```python
def validate_frontmatter(codex_dir: str = CODEX_DIR) -> list[Finding]: ...
def validate_ids(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> list[Finding]: ...
def validate_references(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> list[Finding]: ...
def validate_aliases(graph_dir: str = GRAPH_DIR) -> list[Finding]: ...
def validate_visibility(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> list[Finding]: ...
def validate_encoding(paths: list[str] | None = None) -> list[Finding]: ...

def validate_all(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> list[Finding]:
    """Roda todos os validadores; ordena por (severity, validator, path)."""
```

Todos recebem diretórios por parâmetro (default = dirs reais) para os testes
apontarem fixtures em `tmp_path`. Nenhum estado global novo; reutilizam
`parse_codex_file` (codex_loader) e leitura direta dos JSONs de `data/graph/`
(NÃO usar os caches de `graph_resolver` — lint lê disco fresco).

- Normalização de alias (R4): reutilizar padrão de `_strip_accents` +
  `casefold()` (mesma abordagem de `migrate_lore_nova.slugify`).
- Constraints de relação (R3): ler `relation_types.json`; chaves suportadas
  `source`/`target` com valor = `type` exigido; `symmetric` é ignorado pelo lint.
- Whitelist (R8): constante `_LINT_WHITELIST: set[tuple[str, str]]`
  (`(validator, entity_id)`) no topo do módulo, cada entrada com comentário
  explicando por quê — vazia é o ideal.

### CLI

```
uv run python scripts/validate_content.py
--- LINT DE CONTEÚDO ---
[frontmatter] OK (0 erros)
[references]  ERRO data/graph/edges.json (e_xyz): target 'porto_fantasma' não existe
[encoding]    AVISO data/codex/npcs/npc_grum.md: possível mojibake ('Ã©')
--- 1 ERRO · 1 AVISO ---
exit 1
```

Aplica o mesmo `sys.stdout.reconfigure(encoding="utf-8")` do migrate script
(console Windows).

### CI (`.github/workflows/validate.yml`)

```yaml
name: validate
on:
  push: {branches: [main]}
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run pytest -q
```

A suíte já é offline/determinística (`tests/conftest.py` força `RPG_FORCE_MOCK=1`);
o gate de conteúdo entra como teste comum — sem passo de CI separado para lint.

## 4. Plano passo a passo

### Etapa 1 — Schema + frontmatter

1. **Testes** (`tests/test_fase71.py`): `test_frontmatter_ok` (fixture mínima
   válida → sem findings); `test_frontmatter_id_diverge_do_arquivo`;
   `test_frontmatter_type_desconhecido`; `test_frontmatter_visibility_invalida`;
   `test_frontmatter_tags_nao_lista`.
2. **Implementação:** `Finding`, constantes, `validate_frontmatter`.
3. **Verificação:** `/qa` verde.

### Etapa 2 — IDs + referências

1. **Testes:** `test_id_duplicado_no_codex`; `test_extra_conflita_com_canonico`;
   `test_components_id_orfao`; `test_edge_target_inexistente`;
   `test_edge_type_desconhecido`; `test_edge_constraint_target_location`;
   `test_related_entities_orfao`; `test_edge_id_duplicado`.
2. **Implementação:** `validate_ids`, `validate_references`.
3. **Verificação:** `/qa` verde.

### Etapa 3 — Aliases + visibilidade

1. **Testes:** `test_alias_duplicado_entre_entidades` (com variação de acento:
   "Ermo Branco" vs "ermo branco"); `test_alias_colide_com_name_de_outra`;
   `test_secret_type_com_visibility_public_falha`;
   `test_public_referencia_secret_falha`.
2. **Implementação:** `validate_aliases`, `validate_visibility`.
3. **Verificação:** `/qa` verde.

### Etapa 4 — Encoding + validate_all + CLI

1. **Testes:** `test_arquivo_cp1252_falha` (escrever bytes latin-1 com `é`);
   `test_mojibake_gera_aviso_nao_erro`; `test_validate_all_agrega_e_ordena`;
   `test_cli_exit_code` (via `subprocess` ou chamando `main()` do script).
2. **Implementação:** `validate_encoding`, `validate_all`,
   `scripts/validate_content.py`.
3. **Verificação:** `/qa` verde.

### Etapa 5 — Gate nos dados reais + correções

1. **Testes:** `test_repo_content_sem_erros` — `validate_all()` nos dirs reais,
   asserta lista de ERROs vazia (AVISOs são impressos, não falham).
2. **Implementação:** rodar o CLI no repo; corrigir cada violação real achada
   (commits de dado); só usar `_LINT_WHITELIST` com justificativa escrita.
3. **Verificação:** `uv run pytest` completo verde.

### Etapa 6 — CI

1. **Implementação:** `.github/workflows/validate.yml` (acima).
2. **Verificação:** push da branch → Action verde no GitHub (checar manualmente).

## 5. Critérios de aceite

- [x] R1–R7 cobertos por testes unitários em fixtures (`tests/test_fase71.py`, 27 testes)
- [x] `test_repo_content_sem_erros` verde — dados reais do repo passam no lint
      (zero violações latentes; `_LINT_WHITELIST` ficou vazia)
- [x] `scripts/validate_content.py` exit 1 com erro, 0 sem; saída agrupada legível
      (smoke: edge quebrado de propósito → ERRO + exit 1; revertido)
- [x] Workflow `validate.yml` criado (`--ignore=tests/test_real_llm.py` além do
      spec — o conftest força mock mas o arquivo pede chave; verificar Action
      verde no primeiro push para o GitHub)
- [x] `uv run pytest` verde (suíte completa offline — 581 testes)
- [x] Guard de FallbackLLM — N/A (zero LLM nesta spec)
- [x] Saves antigos continuam carregando (nada de runtime mudou)

**Desvios:** nenhum estrutural. Extra: `validate_frontmatter` também acusa campo
obrigatório ausente (via `parse_codex_file`); smoke §6 item 2 (reindex + query)
executado na entrega da 7.3 (mesma sessão).

## 6. Smoke test com LLM real

Lint é 100% offline — smoke mínimo (1 request):

1. Quebrar de propósito um edge em `edges.json` (target inexistente) → CLI acusa
   ERRO e exit 1; reverter.
2. `uv run python rag.py` com chave real → reindexação segue funcionando após
   eventuais correções de dado da Etapa 5; 1 `query_rag` de sanidade
   (ex.: "quem governa Nova Arcádia") retorna chunk coerente.

## 7. Riscos & compatibilidade

- **Dados reais podem ter violações latentes** (edges escritos à mão): Etapa 5
  absorve — corrigir é entrega da spec, prazo elástico ali.
- **Falso positivo de mojibake** em prosa PT-BR legítima: por isso AVISO, nunca
  ERRO.
- **CI custa minutos de Action**: suíte é offline e rápida (~520 testes);
  aceitável. Sem chave no CI — `RPG_FORCE_MOCK=1` garante zero rede.
- **Saves antigos:** intocados. **MockLLM/FallbackLLM:** irrelevante (sem LLM).
- **OneDrive/Windows:** validadores só leem; sem risco de lock.
