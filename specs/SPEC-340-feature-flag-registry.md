# SPEC-340 — Registro de feature flags com validade

> **Status:** `done`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Depende de:** —
> **Desbloqueia:** limpeza de flags de rollout vencidas (specs futuras)
> **Aprovação:** dono, 27/10 ("faz aí", após a proposta de registro com validade).

---

## 1. Contexto & Objetivo

O produto lê cerca de 200 variáveis `RPG_*` (feature flags de rollout, ajustes de operação,
kill switches, configuração de ambiente e chaves só de teste). Elas ficam espalhadas: docstrings
de `services/latency_flags.py` e `services/combat_flags.py`, `.env.example`, o preset
`scripts/staging/staging_flags.json` e o corpo das specs. Nada diz quais flags são temporárias,
de quem são e quando deveriam sumir. Por isso flag de rollout vira código morto permanente, e o
caminho `off` deixa de ser testado.

Esta spec cria um **registro único** de toda variável `RPG_*` lida pelo código e um **quality
gate** na suíte default. O gate falha quando:
- surge uma flag nova sem registro;
- o registro aponta para uma flag que não existe mais;
- uma flag de rollout passa da validade.

Não muda o comportamento de nenhuma flag.

## 2. Requisitos

- **R1** — O arquivo `config/flags.yaml` lista cada nome `RPG_*` com os campos `kind`, `default`,
  `spec`, `note` e, só para `kind: release`, `expires`.
- **R2** — `kind` ∈ {`release`, `ops`, `kill_switch`, `config`, `dev`}:
  - `release`: rollout temporário de feature (sai depois de estabilizar);
  - `ops`: ajuste operacional permanente (timeouts, tetos, políticas);
  - `kill_switch`: desligamento permanente de emergência;
  - `config`: ambiente, perfis, URLs e segredos (nunca o valor do segredo);
  - `dev`: só teste, CI ou desenvolvimento (`RPG_FORCE_MOCK`, `RPG_API_FUZZ_REQUIRED` etc.).
- **R3** — Campos:
  - `expires` (data `AAAA-MM-DD`) é obrigatório em `release` e proibido nos demais;
  - `spec` é `SPEC-NNN` ou `null`;
  - `default` é string, ou `null` quando não há default.
- **R4** — Cobertura: todo nome `RPG_[A-Z0-9_]+` que aparece literal em arquivo **rastreado** no
  git (`git ls-files`) de código de produto deve estar no registro. Código de produto é todo
  `*.py` fora de `tests/`, mais `.github/workflows/*.yml`. Também entram as chaves de
  `scripts/staging/staging_flags.json` e de `.env.example`. A lista de faltantes sai no
  assert.
- **R5** — Sem órfãos: todo nome registrado aparece em pelo menos uma das fontes do R4.
- **R6** — Validade: flag `release` com `expires` anterior à data de hoje falha o gate. A
  mensagem diz "remova a flag ou renove `expires` com justificativa no `note`". A função
  recebe `today` por parâmetro (testável).
- **R7** — Nomes montados em runtime (ex.: `f"RPG_{x}_TIMEOUT"`) entram como entrada com
  `pattern: true` e um regex em `name`. O scanner do R4 aceita quem casar o padrão. A spec só
  exige isso se o executor achar nomes dinâmicos reais.
- **R8** — `scripts/flag_registry.py` expõe as funções puras `load`, `scan_sources`,
  `validate` e `check`, e a CLI `check` (exit 1 com a lista de erros), `list [--kind K]` e
  `expiring --days N`. O teste `tests/test_flag_registry.py` roda na suíte default (sem
  marker), então o job `validate` já o executa.
- **R9** — Carga inicial: toda flag existente é classificada. As `release` recebem
  `expires: 2027-01-25` (90 dias a partir de 27/10) e o `spec` de origem quando ele for
  identificável. O executor lista no hand-back as que ficaram com `spec: null`.
- **R10** — `docs/guias/` ganha uma seção curta "Flags" em `TESTES.md` ou num guia
  existente (não um guia novo). Cobre como registrar flag nova e como renovar ou remover.
  `AGENTS.md` ganha 1 linha apontando para o registro.

### Fora de escopo

- Serviço de flags em runtime, painel, percentual de rollout ou flag por usuário.
- Mudar default, comportamento ou leitura de qualquer flag; remover flag.
- Flags do frontend (`VITE_*`) e do Vercel fora de `RPG_*`.
- Ler o registro em runtime: o registro é só documentação verificada, e os módulos de flags
  continuam lendo `os.getenv`.

## 3. Design técnico

- **Novo `config/flags.yaml`** — mapa `name → campos`, ordenado por nome. Exemplo:

```yaml
RPG_ARCHIVE_POLICY:
  kind: ops
  default: legacy
  spec: SPEC-318
  note: "gate do arquivista; staging usa lean"
RPG_NPC_TWO_PHASE:
  kind: release
  default: "on"
  spec: SPEC-318
  expires: 2027-01-25
  note: "ficha de NPC em duas fases"
RPG_FORCE_MOCK:
  kind: dev
  default: null
  spec: null
  note: "suíte offline força MockLLM"
```

- **Novo `scripts/flag_registry.py`**:
  - `load(path) -> dict[str, dict]`;
  - `scan_sources(root) -> dict[str, set[str]]` (nome → arquivos), via `git ls-files`;
  - `validate(registry, found, today) -> list[str]` (erros legíveis);
  - `check(root, today=None) -> int`.
  - Usa `yaml` (já é dependência do `spec_index.py`) e não importa nada do produto.
- **Novo `tests/test_flag_registry.py`**:
  - unidade de `validate` com registros sintéticos: faltante, órfão, `release` sem
    `expires`, `expires` em não-`release`, vencida, `kind` inválido, padrão dinâmico;
  - um teste de integração `check(ROOT) == 0` contra o repositório real.
- **Alterados** — `docs/guias/TESTES.md` (ou o guia equivalente) e `AGENTS.md` (1 linha cada).
  Os docstrings de `latency_flags.py` e `combat_flags.py` ficam como estão.

Cuidado (`scripts/ci_docs_only.py`): o registro fica em `config/` e não em `docs/`, para que
mudar uma flag nunca seja tratado como "só docs" e pule os testes.

## 4. Plano passo a passo

### Etapa 1 — validador puro (TDD)
1. **Testes**: os casos sintéticos de `validate` (R2, R3, R5, R6, R7) ficam vermelhos.
2. **Implementação**: `load`/`validate` em `scripts/flag_registry.py`.

### Etapa 2 — scanner e carga inicial
1. **Teste**: `test_repo_registry_is_complete` (`check(ROOT) == 0`) fica vermelho.
2. **Implementação**: `scan_sources`, CLI e `config/flags.yaml` com todas as flags
   classificadas (R9). Para classificar: docstrings dos módulos de flags, `.env.example`,
   `staging_flags.json` e grep do nome nas specs.

### Etapa 3 — docs
1. Seção curta no guia e linha no `AGENTS.md` (R10).

## 5. Critérios de aceite

- [x] R1–R3: schema validado por teste.
- [x] R4/R5: `check` verde no repositório real; adicionar `os.getenv("RPG_FOO_NOVO")` num
      arquivo de produto faz o teste falhar (provado em teste com fonte sintética).
- [x] R6: flag `release` vencida falha com a mensagem pedida (teste com `today` fixo).
- [x] R8: `uv run python scripts/flag_registry.py check` exit 0; `expiring --days 120` lista as
      `release`.
- [x] R9: hand-back lista contagem por `kind` e as `release` sem spec.
- [x] R10: guia e `AGENTS.md` atualizados.
- [x] Suíte completa verde (a cargo do coordenador no pouso; escopo: 10 testes verdes).

## 6. Smoke test com LLM real

Não se aplica: não há LLM nem mudança de runtime. O smoke é a CLI `check`/`list`/`expiring`
no checkout real.

## Histórico

- 2026-10-27 · spec escrita pelo coordenador; aprovada pelo dono na conversa.
