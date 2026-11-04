# rpg-ia-master

RPG de texto com IA — motor LangGraph multi-agente com RAG híbrido e memória por sessão.
Stack: Python 3.13 · FastAPI · LangGraph · FAISS · Google Gemini · uv

> **Fonte única de instruções** para Codex (lê este arquivo) e Claude Code (`CLAUDE.md`
> importa este arquivo e acrescenta só o específico do Claude Code).
> **AO RETOMAR:** leia `ESTADO_ATUAL.md` (≤ 8 KB: estado, próximos passos, bloqueios
> no dono, como rodar). Plano: `ROADMAP.md`. Histórico (`docs/historico/`,
> `CHANGELOG.md`) só sob demanda — nunca leia ESTADO/ROADMAP antigos inteiros.

---

## Operação de specs e evals

Ao retomar trabalho spec-driven:

1. leia `ESTADO_ATUAL.md`; status de spec = o cabeçalho da própria spec
   (`specs/index.yaml` é **gerado** por `scripts/spec_index.py build`; consulte com
   `spec_index.py summary`/`check` em vez de abrir o arquivo de 158 KB);
2. identifique a `SPEC-ID` ativa e confirme que suas dependências estão `done`;
3. o Project Index não entra no contexto ou fluxo padrão e não é versionado: gere com
   `python -m project_index build` antes de consultar. Use
   `project_index/domains.yaml`, `repo_graph`, `state_ownership` ou `eval_map`
   somente em uma consulta explícita e seletiva, com hipótese cross-file clara;
4. confirme qualquer achado de índice no source real antes de modificar
   comportamento; o source permanece a verdade;
5. consulte `docs/evals-plan-v4/12_MODEL_EXECUTION_POLICY.md` e use o menor tier
   suficiente;
6. rode primeiro a menor suíte determinística que prove a mudança.

Integridade de eval: quem otimiza o produto não altera evaluator, expected,
dataset de regressão, denominador, baseline ou exclusões na mesma tarefa. O
fluxo é deterministic-first; LLM-as-judge não substitui um oráculo estruturado.
O contrato completo fica em `docs/evals-plan-v4/08_CONTRATO_CODING_AGENT.md`.

Antes de criar um writer persistente, consulte o mapa de ownership quando ele
existir e confirme canonical owner, invariantes e round-trip save/load.

Roteamento mínimo: Luna para inventário, transformações e relatórios; Terra para
implementação bounded; Sol para trabalho cross-domain, concorrência, estado e
revisão técnica; Astra somente para checkpoints conceituais e semântica de
evaluators. Se o modelo ou reviewer mínimo não estiver disponível, registre
`MODEL_HANDOFF_REQUIRED`, prepare `handoffs/SPEC-xxx-<model>-review.md` e não
autoaprove a revisão independente.

Long-runs, campanhas de 100/200 turnos e a matriz 10×200 são estritamente
opt-in. Só execute por pedido explícito do usuário ou por spec de horizonte longo
explicitamente aprovada; baseline, release e regressão não constituem permissão.

### Fluxo de spec em 8 linhas

1. Reserve o ID na `main`: `scripts/spec_index.py next-id --slug <slug> --create` +
   `build` + commit "spec: reserve SPEC-NNN" (skill `/spec-new`).
2. Worktree por spec, fora do OneDrive: `bash scripts/dev/wt.sh new NNN`.
3. TDD no worktree; Python sempre via `bash scripts/dev/py.sh …` (raiz, UTF-8, venv).
4. Testes do escopo durante o trabalho (camadas em `docs/guias/TESTES.md`).
5. Status final só no cabeçalho da spec; revisão independente por outro agente.
6. Pouso (`/spec-land`): `wt.sh sync` (rebase + `specs/index.yaml` na
   branch) → suíte completa 1× (`-n auto`) → `wt.sh land` (ff da `main`).
7. `ESTADO_ATUAL.md` via `/estado`: substituir, nunca anexar (≤ 8 KB).
8. Commit em inglês (Conventional Commits) com a linha `Co-Authored-By` do sistema.

Subagentes: regras comuns em `docs/guias/BRIEF_SUBAGENTE.md`; não editam
`ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml` nem `project_index/` — devolvem
um parágrafo no hand-back e o coordenador integra.

---

## Comandos essenciais

> Use sempre `uv run` (o `python` global deste Windows é 3.14 — errado; o projeto
> exige 3.13). `uv` fica fora do PATH: `$env:Path="$env:APPDATA\Python\Python314\Scripts;$env:Path"`.
> Detalhes do ambiente: `ESTADO_ATUAL.md`.

```bash
uv sync                                   # cria .venv (Python 3.13)
uv run python game_engine.py              # CLI — jogar no terminal
uv run uvicorn api:app --port 8000        # API REST + frontend web (http://localhost:8000)
uv run python rag.py                      # re-indexar lore (data/codex/) + regras (data/rules.txt)
uv run pytest                             # suíte offline (força MockLLM, não precisa de chave)
bash scripts/smoke_api.sh [porta]         # smoke da API (health, /data/map, /game/new, /game/action)
uv run python -m playtest run --all --turns 50   # Fase 5: harness — 14 perfis (MockLLM, offline)
uv run python -m playtest report <run_id>        # relatório agregado (per-perfil/violações/custo)
uv run python -m playtest transcript <run_id>    # transcrito ação→narração por turno (julgar prompt)
```

**Playtest agêntico (Fase 5):** 14 perfis sobre o mesmo grafo, invariantes por turno, telemetria e
`--real` com teto de custo — detalhe em `docs/guias/ARQUITETURA.md` § Playtest.

**Feature flags (SPEC-340):** toda `RPG_*` é registrada em `config/flags.yaml` (kind/validade); o gate roda na suíte default — ver `docs/guias/TESTES.md` § Flags.

**Autoria de conteúdo:** `docs/guias/AUTORIA.md` (entidades, Codex, Cartas e classes; lint
`scripts/validate_content.py`; curadoria em `data/codex_overrides.yaml` + `curated: true`).

**Modo simulado:** sem chave, `get_llm()` devolve `MockLLM` (jogável offline); `RPG_FORCE_MOCK=1`
força o mock (suíte), `RPG_NO_MOCK=1` força o `FallbackLLM` de erro.

**Frontend:** React + Vite + TS em `web/`; a API serve `web/dist` na raiz quando existe. Build e dev:

```bash
cd web && npm install          # uma vez (Node ≥22.12, ver web/.nvmrc)
npm run build                  # gera web/dist (servido por uvicorn na raiz)
npm run dev                    # dev server :5173 com proxy p/ a API :8000
npm run test:e2e               # Playwright; porta derivada do checkout (RPG_E2E_PORT força; CI = 4173)
```

---

## Arquitetura (resumo — detalhe em `docs/guias/ARQUITETURA.md`)

- **Grafo LangGraph** (`main.py`): `campaign_manager` → `dm_router` → `storyteller` | `combat_agent` |
  `npc_actor` | `loot_agent` → `archivist` → END. Todo nó novo termina no `archivist`.
- **LLM** (`llm_setup.get_llm(temperature, tier)`, nunca provider direto): tiers `CLASSIFY`/`FAST`/`SMART`,
  cada um com candidatos `ROUTES` (DeepSeek primário; fallback por provider; `RPG_ROUTES` sem deploy).
  Esgotou tudo → `AIMessage` de erro, nunca exceção: o guard de `FallbackLLM` é obrigatório.
- **RAG** (`rag.query_rag`): índice global do Codex/regras + memória FAISS por sessão (`archivist`).
- **Persistência** (`persistence.py`): `saves/{game_id}.json`; memória vetorial em `data/saves_memory/`.
- **Estado** (`state.py`, fonte da verdade): `GameState` TypedDict; atributos com chaves curtas.
- **Pastas**: núcleo na raiz, `agents/` (nós), `services/` (determinístico), `web/` (React),
  `data/` (conteúdo), `specs/`, `tests/`, `evals/` (protegido), `playtest/`, `scripts/dev/`.

---

## Desenvolvimento spec-driven

Toda feature/fase nova segue o fluxo de `specs/`:

1. **Spec antes de código.** Feature nova recebe o próximo ID nunca utilizado e
   começa como `specs/SPEC-NNN-<slug>.md` (copiar `specs/TEMPLATE.md`), status
   `draft`, com registro correspondente em `specs/index.yaml`. Nada de
   implementar direto do ROADMAP nem criar spec canônica sem ID/índice.
2. **Aprovação.** O usuário revisa; spec vira `approved`. Só então implementar.
3. **Implementação segue o plano da spec** (testes primeiro); desvio → atualizar a spec no mesmo commit.
4. **Conclusão:** critérios marcados + `uv run pytest` verde + smoke real → `done` no cabeçalho →
   `/spec-land` → `/estado`. ROADMAP só se o plano mudou.
5. **ROADMAP.md é resumo + link;** o detalhe técnico mora SÓ na spec (fonte única).

Estado das specs: `uv run python scripts/spec_index.py summary`; histórico em `docs/historico/`.

---

## Convenções de código

- Python 3.13+ com type hints em tudo
- Pydantic v2 para structured output do LLM (`llm.with_structured_output(Model)`)
- Async não usado — LangGraph roda síncrono neste projeto
- `httpx` se precisar HTTP externo (nunca `requests`)
- Prefixo `test_` em todos os arquivos e funções de teste
- Cada agente retorna dict parcial do GameState — nunca retornar o estado completo
- **Guard de resiliência (CRÍTICO):** `FallbackLLM.with_structured_output(X).invoke()` devolve um
  `AIMessage`, **não** uma instância de `X`. Acessar `resultado.campo` fora de `try/except` ou sem
  `isinstance(resultado, X)` estoura. Todo nó novo com structured output precisa desse guard.
- **Mecânica é Python, não LLM.** A IA só identifica/narra; números (combate, dados, economia)
  resolvem em código determinístico (`combat_mechanics.py`, `world_utils.py`).
  Não confiar em sinal/valor vindo do LLM sem validar (ex.: sinal do ouro em `loot.py`).
- **MockLLM esconde bugs de mapeamento:** ele devolve instâncias Pydantic válidas, então acesso a
  campo nunca quebra no mock. Bug de nome/tipo de campo só aparece no Gemini real. Validar caminhos
  novos de structured output com a chave real (ver harness/quota em `ESTADO_ATUAL.md`).
- **Ao FINALIZAR qualquer tarefa (SEMPRE, sem exceção):**
  1. Rodar `uv run pytest` e garantir verde antes de declarar a tarefa concluída — nunca afirmar
     que funcionou sem a saída dos testes.
  2. **`ESTADO_ATUAL.md`: substituir, nunca anexar** (teto 8 KB; `/estado` gera o bloco de
     decisões recentes). **`ROADMAP.md`: só quando o plano muda.** Detalhe de entrega vai
     para `CHANGELOG.md` (`## AAAA-MM-DD`). Em onda paralela, só o coordenador edita os dois.

### Qualidade, revisão e evidência (SPEC-386)

- **Menor mudança correta.** Toque só o contrato afetado; refatoração fora do escopo vira spec
  própria. Duas tentativas falharam pelo mesmo motivo → pare de editar e investigue a causa.
- **Tamanho:** função nova ≤ 60 linhas. Arquivo > 1.000 linhas e função > 100 não crescem
  (gate `tests/test_size_budget.py`): código novo vai em módulo próprio.
- **Helper:** antes de criar, `Grep "def <nome>"`; na revisão, `scripts/dev/dup_helpers.py --diff main...HEAD`.
- **Lint:** `ruff format` + `ruff check` rodam a cada edição (hook) e antes do hand-back;
  `except Exception` só com log ou `# silent-ok: motivo`; `noqa` só de regra ativa no `select`.
- **Revisão proporcional ao risco** (campo `Risco` da spec): `alto` (combate, persistência,
  auth/pagamento, API pública, estado, evals) → `spec-reviewer` obrigatório; `médio` → revisor
  Sonnet; `baixo` (docs, conteúdo com lint, tooling) → testes + lint bastam. Onda 375–385: W7 vale.
- **Evidência antes de mexer:** a spec declara como provará o comportamento (teste que falha
  antes; em refatoração pura, oráculo de equivalência — W2 da auditoria 03/11).

---

## O que NÃO fazer

- Não instanciar `ChatGoogleGenerativeAI` direto — usar sempre `get_llm()`
- Não ler FAISS com `allow_dangerous_deserialization=False` — vai quebrar load
- Não commitar `.env` ou `saves/` com dados reais
- Não adicionar agentes ao grafo sem conectar ao `archivist` no final
- Não usar `requests` — projeto usa `httpx` se necessário
- Não editar os arquivos `faiss_*_index/` à mão — sempre re-gerar via `rag.py`
- **Não ler inteiro** lore (`lore_nova/*.txt`, `data/codex/**`) nem `data/*.json` grandes: `Grep` +
  `Read` com offset/limit (o hook nega arquivo > 40 KB sem recorte).
- Não editar `specs/index.yaml` à mão — é gerado no pouso (`project_index/` curado — yaml — segue editável por spec).
- Não ler `docs/historico/`, `ESTADO`/`ROADMAP` antigos, transcritos `.jsonl` ou
  `tool-results/` de outros agentes sem necessidade explícita.

> Sob demanda (não carregados): `REFERENCE.md` (porquês arquiteturais), `docs/guias/ARQUITETURA.md`
> (grafo, tiers, RAG, estado, pastas) e `CHANGELOG.md` (histórico).
