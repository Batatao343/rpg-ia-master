# SPEC — Isolar cache runtime (bestiário/NPCs) da curadoria e dos testes

> **Status:** `done` (2026-07-19 — 8 testes + baseline real gravou no overlay sem sujar data/)
> **Criada:** 2026-07-19 · **Atualizada:** 2026-07-19
> **Depende de:** — (bug de infraestrutura; nenhuma spec pendente)
> **Desbloqueia:** playtests/smokes sem `git checkout` manual; commits limpos

---

## 1. Contexto & Objetivo

Pendência recorrente registrada em `ESTADO_ATUAL.md` (sessões 15 e 16):
`data/bestiary.json` e `data/npc_database.json` são gravados em runtime por
`agents/bestiary.py:save_enemy` e `agents/npc.py` (save do NPC gerado), direto
nos arquivos versionados. Consequências observadas:

- Suíte/smokes gravam entradas mock (HP regredido, "Unknown") no repo — hoje o
  fluxo é `git checkout` manual antes de cada commit.
- Run REAL gravou "Afogado" com região fora do grafo → 2 testes de
  `test_fase25b` vermelhos até o checkout (sessão 16).

A raiz é conceitual: `data/bestiary.json` mistura **curadoria** (84 entradas da
Fase 2.5b, validadas por teste contra o grafo) com **cache runtime** (inimigos
gerados pelo LLM) no mesmo arquivo. `data/npc_database.json` é 100% cache
runtime, mas está versionado. O projeto já resolveu o mesmo problema para
saves: `playtest/runner.py` isola em `saves_playtest/` via monkeypatch de
`persistence.SAVES_DIR`. Esta spec aplica o mesmo princípio aos caches.

Princípio (ROADMAP § Princípios): "Lore base ≠ Estado vivo" — curadoria é
canônica e read-only em runtime; o que o jogo gera é estado vivo e mora fora
do repo.

## 2. Requisitos

- **R1** — `data/bestiary.json` vira **base curada read-only em runtime**:
  nenhum caminho de produção/teste escreve nele. `save_enemy` grava num
  **overlay** gitignored (`data/runtime/bestiary_runtime.json`).
- **R2** — Leitura unificada: `load_bestiary()` devolve `curado ∪ overlay`,
  com a entrada **curada vencendo** em conflito de id (gerado nunca sombreia
  curadoria). Todos os leitores de bestiário que precisam ver criaturas
  geradas (ex.: `services/discovery.py` — bestiário progressivo) usam a view
  unificada; validadores de conteúdo (`test_fase25b`) validam SÓ o curado.
- **R3** — `data/npc_database.json` deixa de ser versionado (`git rm --cached`
  + `.gitignore`); o cache passa a morar em `data/runtime/npc_database.json`.
  Compat: se o overlay não existe e o arquivo legado existe, a primeira carga
  lê o legado (migração transparente, sem perder NPCs de jogos em andamento).
- **R4** — O diretório do overlay é resolvido **em tempo de chamada** (não de
  import) por `RPG_RUNTIME_CACHE_DIR` (default `data/runtime/`) — env var ou
  monkeypatch funcionam em qualquer ordem de import.
- **R5** — A suíte offline redireciona o overlay para `tmp_path` (fixture
  autouse em `tests/conftest.py`, mesmo padrão de `_no_real_embeddings`).
  Rodar `uv run pytest` deixa **zero diff** em `data/`.
- **R6** — O harness de playtest redireciona o overlay para dentro do run
  (ex.: `playtest_runs/<run_id>/runtime/`), como já faz com saves. Run mock ou
  `--real` deixa zero diff em `data/`.
- **R7** — Jogo normal (CLI/API) continua funcionando: inimigo/NPC gerado é
  cacheado (check-first do librarian continua vendo o overlay) e sobrevive a
  restart do processo.

### Fora de escopo

- Curadoria de conteúdo do bestiário (regiões inválidas já gravadas etc.) —
  o arquivo versionado atual é tratado como baseline curado.
- Promover criatura gerada a curada (fluxo `docs/AUTORIA.md` — manual, como hoje).
- Outros arquivos de `data/` (nenhum outro é gravado em runtime — verificado:
  só os 2 caches).

## 3. Design técnico

**Arquivos novos**
- `data/runtime/` (gitignored, criado on-demand) — overlay de caches:
  `bestiary_runtime.json`, `npc_database.json`.

**Arquivos alterados**
- `agents/bestiary.py` —
  - novo helper `def _runtime_cache_path(name: str) -> str` (lê
    `RPG_RUNTIME_CACHE_DIR` no call, default `data/runtime`; `os.makedirs` no
    write). Pode morar em `gamedata.py` se preferir 1 fonte p/ os 2 agentes.
  - `load_bestiary()` → merge: `{**overlay, **curado}` (curado vence).
  - `save_enemy(data)` → lê/grava SÓ o overlay.
- `agents/npc.py` — `load_npc_db`/`save_npc` (nomes atuais no módulo) usam
  `_runtime_cache_path("npc_database.json")`; fallback de leitura p/
  `data/npc_database.json` legado quando overlay ausente.
- `services/discovery.py` — conferir que a junção com o bestiário usa a view
  unificada (criatura gerada continua aparecendo no codex do jogador).
  `gamedata.BESTIARY` (snapshot de import, `gamedata.py:71`) segue curado-only;
  auditar callsites que precisem da view unificada e apontá-los p/
  `load_bestiary()`.
- `tests/conftest.py` — fixture autouse:
  `monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path / "runtime"))`.
- `playtest/runner.py` — setar `RPG_RUNTIME_CACHE_DIR` p/ o run dir (ao lado
  do monkeypatch de `SAVES_DIR` existente).
- `.gitignore` — `data/runtime/` + `data/npc_database.json`.
- Repo: `git rm --cached data/npc_database.json`.

**Assinaturas**
```python
def _runtime_cache_path(name: str) -> str: ...
def load_bestiary() -> Dict: ...      # curado ∪ overlay (curado vence)
def save_enemy(data: Dict) -> None: ...  # overlay only
```

## 4. Plano passo a passo

### Etapa 1 — Overlay do bestiário

1. **Testes** (`tests/test_runtime_cache.py`):
   - `test_save_enemy_nao_toca_curado` — `save_enemy` com env redirecionada
     não altera mtime/conteúdo de `data/bestiary.json`.
   - `test_load_bestiary_merge` — entrada só no overlay aparece; id em
     conflito devolve a versão curada.
   - `test_env_resolvida_no_call` — trocar `RPG_RUNTIME_CACHE_DIR` após o
     import muda o destino do write.
2. **Implementação:** helper + `load_bestiary`/`save_enemy` (R1/R2/R4).
3. **Verificação:** `uv run pytest` verde.

### Etapa 2 — NPC database no overlay + migração

1. **Testes:** `test_npc_db_escreve_overlay`; `test_npc_db_fallback_legado`
   (overlay ausente + legado presente → lê legado; write vai pro overlay).
2. **Implementação:** `agents/npc.py` (R3) + `.gitignore` + `git rm --cached`.
3. **Verificação:** suíte verde.

### Etapa 3 — Isolamento na suíte e no playtest

1. **Testes:** `test_suite_zero_diff_em_data` — após exercitar
   `save_enemy`/save de NPC nos testes, `data/bestiary.json` e
   `data/npc_database.json` (legado) intocados; teste do runner asserta
   overlay dentro de `playtest_runs/<run_id>/`.
2. **Implementação:** fixture no conftest (R5) + runner (R6).
3. **Verificação:** `uv run pytest` verde; `git status` limpo após a suíte.

### Etapa 4 — Leitores unificados

1. **Testes:** criatura só no overlay aparece no bestiário progressivo
   (`services/discovery.py`); `test_fase25b` segue validando só o curado.
2. **Implementação:** auditar callsites (`Grep bestiary`) e apontar os que
   precisam da view unificada p/ `load_bestiary()`.
3. **Verificação:** suíte completa verde.

## 5. Critérios de aceite

- [ ] `uv run pytest` (suíte inteira) → `git status` sem diff em `data/`
- [ ] `uv run python -m playtest run --all --turns 50` → sem diff em `data/`
- [ ] Inimigo/NPC gerado em jogo normal persiste entre restarts (overlay)
- [ ] `test_fase25b` valida só a curadoria; run real não o derruba mais
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Saves antigos continuam carregando (spec não toca em saves)

## 6. Smoke test com LLM real

1. Jogo real (API): provocar geração de inimigo desconhecido ("ataco o
   espectro das dunas") → entrada aparece em `data/runtime/bestiary_runtime.json`,
   `data/bestiary.json` intocado.
2. Conversar com NPC novo → cache em `data/runtime/npc_database.json`.
3. Reiniciar o servidor e reencontrar a criatura → check-first acha no overlay
   (sem 2ª geração).
4. `git status` limpo ao fim.

## 7. Riscos & compatibilidade

- **Saves antigos:** sem impacto (spec não altera schema de save).
- **MockLLM/FallbackLLM:** sem impacto no guard; mock passa a poluir só tmp.
- **Quota/latência:** zero chamadas novas de LLM.
- **Risco: leitor esquecido** usando `gamedata.BESTIARY` p/ criatura gerada —
  mitigado pela auditoria da Etapa 4 (Grep em todos os callsites).
- **Risco: jogos em andamento** com NPCs no arquivo legado — coberto pelo
  fallback de leitura (R3).

## 8. Registro de execução (2026-07-19)

- **Implementado conforme spec** com 3 desvios/achados:
  1. **3º cache achado na implementação:** `data/custom_artifacts.json`
     (`gamedata.save_custom_artifact`) também era gravado em runtime — entrou no
     escopo: write vai pro overlay, leitura no startup = legado ∪ overlay
     (já era gitignored; sem mudança de git).
  2. Overlay do playtest fica em `saves_playtest/runtime/` (context manager
     `_isolated_runtime_cache`, mesmo padrão do `_isolated_saves`) — não em
     `playtest_runs/<run_id>/` (o runner não conhece o run dir; o exemplo do R6
     era ilustrativo).
  3. Helper único `gamedata.runtime_cache_path(name)` (env resolvida no call)
     em vez de helper por agente.
- **Migração do NPC db:** 1º `save_npc_template` carrega o legado inteiro e
  grava tudo no overlay (migração transparente); `git rm --cached
  data/npc_database.json` executado + `.gitignore`.
- **Testes:** `tests/test_runtime_cache.py` — 8 testes. Fixture autouse na
  suíte (`RPG_RUNTIME_CACHE_DIR` → tmp). Validado: suíte + harness mock 10
  turnos → `git status data/` limpo (na rodada baseline PRÉ-fix, a suíte
  regrediu HP de Carniçal/Esqueleto no bestiary.json — exatamente o bug;
  restaurado via checkout e impossível de repetir pós-fix).
- Seam de `test_fase32::test_morte_registra_defeated` atualizado (fake ganha
  `**kwargs` — kwarg novo `allies` da spec fiacao-regras-orfas-classes).
- **§6 smoke real:** o baseline real da spec balanceamento (`run_id
  20260719-115906`) gerou inimigos/NPCs no DeepSeek real — cache foi p/ o
  overlay `saves_playtest/runtime/`, `git status data/` limpo ao fim (só as
  mudanças intencionais de curadoria/traits). `done`.
