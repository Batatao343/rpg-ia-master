# SPEC-399 — Dependabot: triagem e pouso dos 8 PRs de versão major

> **Status:** `approved` (07/11, dono: "ok defaults" → D-399-1 = (a) fechar #42 e adiar; D-399-2 = (a) adiar ESLint 10 até o jsx-a11y aceitar; D-399-3 = (b) pousar motion 14; D-399-4 = (a) reexport manual pelo coordenador; D-399-5 = (a) sem `ignore:`; D-399-6 = (a) mergear o #44 direto após CI verde; #45 (a) se o lock deduplicar o `framer-motion`, senão (b))
> **Criada:** 2026-11-05 · **Atualizada:** 2026-11-07
> **Origem:** pedido do dono, "escreve os PRs do dependabot". São 8 PRs major abertos: #42 typescript 7, #44 actions/setup-node 7, #45 motion 14, #46 @eslint/js 10, #47 eslint 10, #49 uuid-utils 1.0 (pip), #50 multidict 7 (pip), #51 websockets 17 (pip).
> **Depende de:** nada (SPEC-396 `done` já pousou o lote npm minor do PR #55)
> **Desbloqueia:** fila do Dependabot vazia de majors; os próximos PRs `uv` saem no formato certo
> **Risco:** `médio` (toolchain de CI e lint; dependência transitiva do runtime; nenhuma mudança de jogo, estado ou API) → revisor Sonnet. Se D-399-3 escolher (b), a etapa de motion sobe para revisão `spec-reviewer` (UI pública + animação de troca de tela).
> **Evidência:** cada etapa tem um oráculo de antes e depois: `npm ci` + `npm run lint`/`typecheck`/`build`/`npm test` + e2e afetados, ou `uv lock --check` + `tests/test_spec192_vercel_packaging.py` + escopo pytest. Os PRs pip, mergeados como estão, **reprovam** `test_requirements_vercel_utf8_subset_of_lock` (prova de que não se mergeiam).

---

## 1. Contexto & Objetivo

O `.github/dependabot.yml:2` agrupa minor e patch e deixa cada major num PR próprio, para revisão
(o teste `tests/test_ci_docs_only.py:98-104` trava esse formato). Há 8 majors parados. Eles caem em
três situações diferentes:

1. **Mergeável depois de checar** (#44 setup-node): só troca o pin por SHA em 4 `uses:`.
2. **Bloqueados por dependência de terceiro** (#42 TS 7, #46/#47 ESLint 10, #49 uuid-utils 1.0): o
   pacote que depende deles declara faixa que exclui a major nova. Mergear quebraria `npm ci`
   (conflito de peer) ou é impossível de resolver no `uv.lock`.
3. **Formato errado** (#49/#50/#51 pip): foram abertos pelo ecossistema `pip`, que editava só o
   `requirements.txt`. Em 04/11 (commit `d2eae458`) o ecossistema virou `uv`
   (`.github/dependabot.yml:14`). O `requirements.txt` é **exportado** do `uv.lock`
   (`requirements.txt:1-2`: `uv export --frozen --no-dev --no-hashes --no-emit-project --format
   requirements-txt -o requirements.txt`), e o teste
   `tests/test_spec192_vercel_packaging.py:41-50` exige que cada pin do `requirements.txt` seja
   igual à versão no `uv.lock`. Mergear esses PRs reprova a suíte. O bump certo é
   `uv lock --upgrade-package X` + reexport.

Objetivo: dar um destino a cada PR (mergear, refazer no lock e fechar como superseded, ou fechar e
adiar com um gatilho escrito). Pousar o que dá, provado por testes. Não deixar nenhum PR "aberto
sem dono".

### Insumo: o que cada major quebra e o que usamos (evidência)

| PR | Pacote | Quem usa no repo | Restrição de terceiro | Breaking changes relevantes |
|---|---|---|---|---|
| #42 | typescript 5.9.3 → 7.0.2 (`web/package.json:39` `^5.6.3`; lock `web/package-lock.json:5924-5925` 5.9.3) | `tsc -b` no `build` (`web/package.json:12`), `typecheck`/`typecheck:e2e` (`:13-14`), parser do `typescript-eslint` | `typescript-eslint` 8.72.1 declara peer `typescript: ">=4.8.4 <6.1.0"` (`web/node_modules/typescript-eslint/package.json:51,59`) | TS 7 é o compilador nativo em Go (`typescript-go`); a API JS que o `typescript-eslint` consome não é compatível. As notas do PR só linkam o blog (`pr42.md:11`). Este PR também traz troca de publicador no npm (`pr42.md:75`: "new releaser `microsoft1es`") |
| #44 | actions/setup-node v4.4.0 → v7.1.0 | `.github/workflows/audit-local.yml:37`, `eval-gates.yml:137`, `validate.yml:76`, `validate.yml:142`; todos com `node-version-file: web/.nvmrc`, `cache: npm`, `cache-dependency-path: web/package-lock.json` | — | v7.0: migração para ESM e mudança de comportamento do `NODE_AUTH_TOKEN` (`pr44.md:24,59`). Não usamos `registry-url`, `always-auth` nem `NODE_AUTH_TOKEN` (grep nos workflows: zero ocorrências). v5/v6 (notas truncadas; a Etapa 0 lê na íntegra): runtime da action em Node 24 e cache automático ligado pelo campo `packageManager`. Não temos `packageManager` em `web/package.json` e já passamos `cache: npm` explícito |
| #45 | motion 12.42.0 → 14.3.0 (`web/package.json:22` `^12.42.0`; lock `:4620-4621`; `framer-motion`/`motion-dom` 12.43.0 em `:3230,:4646`) | 5 arquivos importam de `motion/react`: `web/src/App.tsx:2` (`AnimatePresence mode="wait"` `:825`, `MotionConfig reducedMotion="user"` `:782`, `useReducedMotion` `:56`, `motion.main`/`motion.div` `:827-898`); `web/src/components/SceneArtwork.tsx:1,11,19-20` (`AnimatePresence`, `useReducedMotion`, `motion.img`); `web/src/design/primitives.tsx:5,29` (`layoutId`); `DeathModal.tsx:2,30`; `LevelUpModal.tsx:3,49` | — | 14.0 só remove APIs **internas** que o 13.5.1 tinha restaurado para compatibilidade com `framer-motion` 13.0–13.4 (`pr45.md:52`). O changelog do **13.0** está truncado no insumo (`pr45.md:57`): a Etapa 0 lê na íntegra antes de decidir. 14.1–14.3 só adicionam e corrigem (`AnimatePresence popLayout`, `useTransform` em Strict Mode, aceleração por hardware de `x`/`y`/`scale`, `pr45.md:25,33,45`). Este último pode mudar o timing visual |
| #46 + #47 | @eslint/js 9.39.5 → 10.0.1; eslint 9.39.5 → 10.13.0 (`web/package.json:29,35`; lock `:931,:2902`) | `web/eslint.config.js:2,26` (`js.configs.recommended`), `npm run lint` (`web/package.json:15`), bloqueante no CI (`validate.yml:88`) | `eslint-plugin-jsx-a11y` 6.10.2 declara peer `eslint: "^3 \|\| … \|\| ^9"` (`web/node_modules/eslint-plugin-jsx-a11y/package.json:52,95`), **sem 10**. `typescript-eslint` (`…/package.json:50`) e `eslint-plugin-react-hooks` 7.1.1 (`…/package.json:39`) já aceitam `^10` | ESLint 10 (`pr46.md:37-58`): exige Node `^20.19 \|\| ^22.13 \|\| >=24` (nosso `engines` é `>=22.12`, `web/package.json:51`, e `.nvmrc` = `22`, travado em `tests/test_ci_docs_only.py:112`); `eslint:recommended` muda (`pr46.md:55`, regras novas podem acusar código atual); remove o eslintrc (já usamos flat config); comentário `eslint-env` vira erro (grep em `web/{src,e2e,tests}`: 0); `minimatch` 10 interno. Isso pode bater no shim de minimatch da SPEC-365 (`web/eslint.config.js:8-20`) e no override `"minimatch": "^11.0.1"` (`web/package.json:48`). O `@eslint/js` 10 passa a ter `eslint` como peer (`pr46.md:32`): os dois PRs só pousam **juntos** |
| #49 | uuid-utils 0.17.0 → 1.0.0 (transitivo; `uv.lock:3093-3094`; `requirements.txt:283-286` "via langchain-core, langsmith") | nenhum import direto (grep `import uuid_utils`: 0) | `langchain-core` 1.7.0 exige `uuid-utils<1.0,>=0.12.0` (`.venv/…/langchain_core-1.7.0.dist-info/METADATA:36`); `langsmith` 0.14.14 idem (`…/langsmith-0.14.14.dist-info/METADATA:34`) | Assinaturas de `uuid6`/`uuid7`/`uuid8` mudam (`pr49.md:25-41`). O `uv lock --upgrade-package uuid-utils` **não consegue** subir para 1.0 enquanto os pais travarem `<1.0` |
| #50 | multidict 6.9.1 → 7.1.0 (transitivo; `uv.lock:1626-1627`; `requirements.txt:147-149` "via aiohttp, yarl") | nenhum import direto; `aiohttp` vem do `langchain-community` (`uv.lock:1313-1317`, `requirements.txt:5-6`) | `aiohttp` 3.14.5 aceita `multidict<8.0,>=4.5` (`…/aiohttp-3.14.5.dist-info/METADATA:39`); `yarl` 1.25.1 aceita `>=4.0` (`…/yarl-1.25.1.dist-info/METADATA:38`) | `keys()`/iteração passam a devolver cada chave uma vez só; `upstr` fica deprecated (`pr50.md:15-20`). Os pais já declaram 7 compatível |
| #51 | websockets 16.1.1 → 17.2 (transitivo; `uv.lock:3158-3159`; `requirements.txt:289-291`) | nenhum import direto; vem de `langgraph-sdk` (`uv.lock:1466-1474`) e `langsmith` (`uv.lock:1497`) | `langgraph-sdk` 0.4.10: `websockets>=14` (`…/langgraph_sdk-0.4.10.dist-info/METADATA:16`); `langsmith`: `>=15.0` (`…METADATA:35`) | As notas só linkam o changelog (`pr51.md:11-17`). Nenhum caminho nosso abre websocket: o `uvicorn` está sem o extra `[standard]` (`pyproject.toml:25`) e o `langgraph-sdk` (cliente remoto) não é usado em runtime |

### Pins e testes que travam versões (não editar sem motivo da etapa)

- `tests/test_eval_frontend.py:139-143`: trava `@playwright/test ^1.64.1` e `@axe-core/playwright ^4.14.0`. Nenhum dos 8 PRs mexe nisso. Se o `npm install` de uma etapa mexer, isso é regressão.
- `tests/test_ci_docs_only.py:98-104`: formato do `dependabot.yml` (3 ecossistemas `github-actions`/`uv`/`npm`, um grupo minor+patch por ecossistema). Adicionar `ignore:` não quebra; adicionar grupo quebra.
- `tests/test_ci_docs_only.py:107-112`: nenhum workflow com `node-version:` (só `node-version-file: web/.nvmrc`) e `.nvmrc == "22"`. Vale para a Etapa 1.
- `tests/test_spec192_vercel_packaging.py:41-53`: `requirements.txt` em UTF-8 e subconjunto exato do `uv.lock`. É o oráculo dos PRs pip.
- `tests/test_api_fuzz_harness.py:115-120`: `requirements.txt` sem schemathesis/hypothesis. O reexport com `--no-dev` mantém isso.
- `.github/workflows/validate.yml:59-60`: `pip-audit -r requirements.txt` roda no CI. O reexport precisa estar no mesmo commit do lock.

## 2. Requisitos

- **R1** — Cada um dos 8 PRs termina **fechado ou mergeado**, com um comentário que diz o destino e o
  motivo (evidência arquivo:linha ou nome do teste). PR adiado é **fechado** com o gatilho escrito.
  Não fica aberto. Exceção: se D-399-1 escolher (b), o #42 continua aberto como sentinela.
- **R2** — Os 4 `uses: actions/setup-node@…` (`audit-local.yml:37`, `eval-gates.yml:137`,
  `validate.yml:76,142`) apontam o mesmo SHA de 40 caracteres da tag `v7.1.0`, com o comentário
  `# v7.1.0`. O SHA é conferido contra a tag (`gh api repos/actions/setup-node/git/ref/tags/v7.1.0`)
  e não copiado da lista de commits do PR. Os jobs `validate` (web + e2e), `audit-local` e
  `eval-gates` ficam verdes no PR ou no push.
- **R3** — Os bumps Python são feitos **no lock**: `uv.lock` com `multidict` 7.x e `websockets` 17.x,
  `requirements.txt` reexportado pelo comando exato de `requirements.txt:2`, no mesmo commit.
  `tests/test_spec192_vercel_packaging.py` e `tests/test_api_fuzz_harness.py` verdes. O
  `uv lock --check` passa.
- **R4** — O `uuid-utils` continua em 0.x no `uv.lock` enquanto `langchain-core` e `langsmith`
  declararem `<1.0`. A spec registra o gatilho de reabertura (R8).
- **R5** — O ESLint 10 só pousa com `@eslint/js` 10 **e** `eslint` 10 juntos, `npm ci` limpo **sem**
  `--legacy-peer-deps`/`--force` e **sem** `.npmrc` novo que afrouxe peers, e `npm run lint` com
  zero achados (o gate da SPEC-284 continua bloqueante). Com o `eslint-plugin-jsx-a11y` declarando
  peer `≤ ^9`, a etapa **não pousa** e cai em D-399-2.
- **R6** — O TypeScript continua em 5.x (ou 6.0.x, se D-399-1 escolher (c)) enquanto a peer do
  `typescript-eslint` excluir a versão nova. `npm run typecheck`, `typecheck:e2e`, `build` e `lint`
  continuam verdes.
- **R7** — Se o motion 14 pousar (D-399-3): os 5 consumidores de `motion/react` compilam sem
  mudança de API; `npm test`, `npm run build`, e2e `chromium-motion` (`effects.spec.ts`,
  `web/playwright.config.ts:69-70`) e e2e com `reducedMotion: "reduce"` (`:44,66`) ficam verdes; o
  tamanho do chunk de `motion` no `vite build` não cresce mais que 10 % (número de antes e depois
  no hand-back).
- **R8** — Para cada PR adiado, o gatilho fica escrito na seção 4 desta spec e no comentário de
  fechamento: versão do pacote pai que destrava e o comando que prova. O coordenador leva o gatilho
  ao `ESTADO_ATUAL.md` § Bloqueios **só** se depender do dono. Gatilho de terceiro não é bloqueio do
  dono.
- **R9** — Nenhum arquivo protegido (`evals/protected-paths.txt`) é tocado. O
  `.github/workflows/eval-gates.yml` não está na lista (`evals/protected-paths.txt:1-29`), mas
  muda só a linha 137.
- **R10** — Nenhum teste de pin (seção 1, "Pins") é afrouxado para caber num bump.

### Fora de escopo

- PRs minor e patch (grupos `*-minor-patch`) e qualquer major que apareça depois desta spec.
- Trocar o `eslint-plugin-jsx-a11y` por um fork (por exemplo `eslint-plugin-jsx-a11y-x`) ou remover o
  plugin. Se D-399-2 escolher isso, vira spec própria (mexe na cobertura de a11y do lint).
- Migrar para TS 7 ou `tsgo`. Também fica fora mudar a API de animação, reescrever componentes com
  motion ou trocar de biblioteca.
- Automatizar o reexport do `requirements.txt` nos PRs `uv` do Dependabot (workflow que commita no
  PR). Só fica registrado como D-399-4.
- Subir `engines.node`/`.nvmrc` para 24. Só entra se o ESLint 10 exigir, e então via D-399-2.
- Mexer em `langchain-core`, `langsmith` ou `langchain-community` para destravar o `uuid-utils`.

## 3. Design técnico

Nada de código de produto, a menos que D-399-3 traga um ajuste de motion. Os arquivos alterados
dependem da etapa:

- `.github/workflows/{audit-local,eval-gates,validate}.yml`: só a linha do `uses:` do setup-node (Etapa 1).
- `uv.lock` e `requirements.txt`: Etapa 2, regenerados por comando, nunca à mão.
- `web/package.json` e `web/package-lock.json`: Etapas 3 e 4, via `npm install <pkg>@<faixa>` no worktree.
- `web/eslint.config.js`: só se o ESLint 10 exigir. Por exemplo, o shim de minimatch
  (`:8-20`) deixar de ser necessário ou passar a quebrar.
- `.github/dependabot.yml`: opcional (D-399-5). Entradas `ignore:` para
  `uuid-utils` `>=1`, `typescript` `>=7` e `eslint`/`@eslint/js` `>=10`, com comentário do gatilho.
  Não pode criar grupo novo (`tests/test_ci_docs_only.py:98-104`).

Comandos canônicos (rodar no worktree, Python via `bash scripts/dev/py.sh`/`uv`):

```bash
# Etapa 2 (Python)
uv lock --upgrade-package multidict --upgrade-package websockets
uv export --frozen --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt
uv lock --upgrade-package uuid-utils --dry-run   # prova R4: continua 0.17.x
# Etapas 3 e 4 (web)
npm install motion@^14.3.0
npm install -D eslint@^10.13.0 @eslint/js@^10.0.1   # deve falhar com ERESOLVE enquanto jsx-a11y ≤ ^9
```

## 4. Plano passo a passo (risco crescente)

Um worktree só (`bash scripts/dev/wt.sh new 399`), com **um commit por etapa**, para que cada etapa
possa ser revertida sozinha. Os PRs do Dependabot são fechados pelo coordenador **depois** do pouso
(R1), com o texto pronto que o executor deixa no hand-back.

### Etapa 0 — Leitura e linha de base (sem alterar nada)

1. Ler na íntegra as notas truncadas: setup-node v5, v6 e v7.0 ("V7 ESM migration and
   NODE_AUTH_TOKEN behavior change"); o motion `CHANGELOG.md` 13.0–13.5; o changelog do websockets 17.0.
   Registrar na spec (seção 1) as breaking changes que tocam nosso uso, ou "nenhuma".
2. `gh pr checks 44 45 46 47` (um por vez, com teto de saída): anotar o que o CI do próprio PR
   já disse. Se #46/#47 reprovaram em `npm ci` por ERESOLVE, isso confirma R5.
3. Linha de base no worktree: `npm ci`, `npm run lint`, `npm run typecheck`,
   `npm run typecheck:e2e`, `npm test`, `npm run build` (anotar o tamanho do chunk do motion em
   `dist/assets`). Python: `tests/test_spec192_vercel_packaging.py`, `tests/test_api_fuzz_harness.py`,
   `tests/test_ci_docs_only.py`, `tests/test_eval_frontend.py`.
4. Conferir se as peers mudaram desde 05/11: `npm view eslint-plugin-jsx-a11y peerDependencies`,
   `npm view typescript-eslint peerDependencies`. Para uuid-utils: `requires_dist` de
   `langchain-core` e `langsmith` na versão mais nova (`uv pip compile`/`uv lock --dry-run`). Se algum
   bloqueio caiu, a etapa correspondente vira "pousar".

### Etapa 1 — #44 actions/setup-node 7.1.0 (risco baixo)

1. **Teste antes:** `tests/test_ci_docs_only.py` verde, o oráculo de forma. Não precisa de teste novo:
   a mudança é um SHA, e o oráculo de comportamento é o CI.
2. **Implementação:** nos 4 `uses:`, trocar o SHA e o comentário para `v7.1.0`, com o SHA
   resolvido da tag (R2). Comparar com o diff do PR #44: deve ser idêntico. Se for, a opção mais
   simples é **mergear o próprio #44** (D-399-6).
3. **Verificação:** `tests/test_ci_docs_only.py` + `tests/test_eval_frontend.py`; CI do PR/push:
   `validate` (web, e2e), `audit-local`, `eval-gates` verdes, e o passo de cache npm com hit no
   segundo run.
4. **Destino:** #44 **mergeado** (ou fechado como superseded pelo commit da etapa).

### Etapa 2 — #50 multidict 7 e #51 websockets 17, no lock (risco baixo)

1. **Teste que falha antes:** fazer checkout do PR #50 num diretório temporário e rodar
   `tests/test_spec192_vercel_packaging.py::test_requirements_vercel_utf8_subset_of_lock`. Deve
   **reprovar** (`requirements.txt` 7.1.0 contra `uv.lock` 6.9.1). Isso prova que o PR não se mergeia.
   Só se registra; nada é commitado.
2. **Implementação:** os comandos da seção 3 (Python). Conferir no diff do `uv.lock` que **só**
   `multidict` e `websockets` mudaram, mais o que o resolvedor exigir, listado no commit.
3. **Verificação:** `uv lock --check`; `bash scripts/dev/pt.sh tests/test_spec192_vercel_packaging.py
   tests/test_api_fuzz_harness.py`; smoke de import `uv run python -c "import aiohttp, yarl,
   langsmith, langgraph_sdk, langchain_community"`; escopo do RAG e do grafo (`tests/test_fase0.py` e
   os testes de `rag`) com `-n 2`. CI: `pip-audit` verde.
4. **R4 (#49):** `uv lock --upgrade-package uuid-utils --dry-run` continua em 0.17.x. Isso é a
   evidência para o comentário de fechamento.
5. **Destino:** #50 e #51 **fechados como superseded** pelo commit da etapa. #49 **fechado e
   adiado**, com o gatilho "langchain-core **e** langsmith liberarem `uuid-utils>=1`; prova:
   `uv lock --upgrade-package uuid-utils` resolve 1.x".

### Etapa 3 — #45 motion 14 (risco médio; condicionada a D-399-3)

1. **Testes antes:** linha de base da Etapa 0: e2e `chromium-motion` (`effects.spec.ts`), e2e das
   jornadas com troca de tela (`critical-journeys.spec.ts`, por causa do `AnimatePresence mode="wait"` em
   `App.tsx:825`), `visual-surfaces.spec.ts` só no Linux/CI, `web/tests/design.test.mjs`.
2. **Implementação:** `npm install motion@^14.3.0`. Conferir que o lock deduplica
   `framer-motion` e `motion-dom` (uma cópia de cada). Sem mudança de código esperada. Se o
   `typecheck` acusar API removida, a etapa para e volta para decisão (R7; o fora de escopo veta
   reescrever).
3. **Verificação:** `npm run typecheck`, `lint`, `npm test`, `build` (tamanho do chunk, R7), e2e
   `--project=chromium-motion` e jornadas críticas com `--workers=2`. CI e2e completo.
4. **Destino:** #45 **mergeado**, ou superseded pelo commit da etapa se o lock precisou de
   ajuste. Com D-399-3 = (a): **fechado e adiado** com o gatilho "spec de UI que já toque animação",
   e `ignore` opcional.

### Etapa 4 — #46 + #47 ESLint 10 (risco médio; esperado: não pousa)

1. **Prova do bloqueio:** no worktree, `npm install -D eslint@^10.13.0 @eslint/js@^10.0.1`. O
   esperado é ERESOLVE pela peer do `eslint-plugin-jsx-a11y` 6.10.2. Registrar a mensagem (3 linhas).
2. **Se a peer já aceitar 10** (Etapa 0.4): instalar; `npm run lint`. Achados das regras novas
   do `eslint:recommended` são corrigidos no código **só** se forem bug real. Se forem estilo, a
   decisão volta ao dono. Não se desliga regra em massa. Rever o shim de minimatch
   (`eslint.config.js:8-20`): se o plugin novo não precisar mais dele, remover. Conferir Node local e CI
   `>= 22.13` (`node -v`).
3. **Verificação:** `npm ci` limpo, `npm run lint` com zero achados, `npm run typecheck:e2e`, `npm test`.
4. **Destino (caso esperado):** #46 e #47 **fechados e adiados** juntos, com o gatilho "`eslint-plugin-jsx-a11y`
   publicar peer com `^10`; prova: `npm install -D eslint@^10` sem ERESOLVE", salvo D-399-2.

### Etapa 5 — #42 TypeScript 7 (sem instalação)

1. **Prova do bloqueio:** a peer do `typescript-eslint` (`<6.1.0`, Etapa 0.4) já basta.
   Nada é instalado.
2. **Destino:** conforme D-399-1. Recomendado (a): **fechar e adiar** com o gatilho
   "`typescript-eslint` declarar peer que inclua 7.x". Registrar no comentário a troca de publicador
   no npm (`pr42.md:75`), para conferir a procedência quando o gatilho disparar.

### Etapa 6 — Fechamento

1. Opcional (D-399-5): `ignore:` no `dependabot.yml` para as majors adiadas, com gatilho em comentário;
   `tests/test_ci_docs_only.py` verde.
2. O hand-back traz o texto de cada comentário de fechamento (PR, destino, motivo, gatilho). O
   coordenador fecha os PRs depois do pouso da branch.

## 5. Critérios de aceite

- [ ] Etapa 0 registrada na spec (notas lidas na íntegra, CI dos PRs, peers do dia, linha de base).
- [ ] R2: 4 pins do setup-node no SHA da tag v7.1.0; CI `validate`/`audit-local`/`eval-gates` verde.
- [ ] R3: `uv.lock` com multidict 7.x e websockets 17.x; `requirements.txt` reexportado no mesmo commit; `uv lock --check`; `test_spec192_vercel_packaging.py` e `test_api_fuzz_harness.py` verdes; `pip-audit` verde no CI.
- [ ] R4: uuid-utils em 0.x, com a saída do `--dry-run` anexada.
- [ ] R5/R6: ESLint 10 e TS 7 não pousaram com peer quebrada; `npm ci` sem flags de peer.
- [ ] R7 (se D-399-3 = b): motion 14 com typecheck/lint/test/build/e2e motion verdes; chunk ≤ +10 %.
- [ ] R1/R8: os 8 PRs com destino aplicado e comentário com gatilho.
- [ ] R9/R10: nenhum caminho protegido nem teste de pin alterado.
- [ ] `uv run pytest` verde (suíte completa offline, 1× no pouso, pelo coordenador).
- [ ] Saves antigos continuam carregando (sem mudança de schema; `tests/test_persistence*` no escopo da Etapa 2).

## 6. Smoke test real (infra)

Sem LLM novo. O smoke é de deploy, porque `multidict`/`websockets` entram no bundle da Vercel
(`requirements.txt`) e o motion entra no front servido:

1. `scripts/vercel_bundle_check.py` (instala `requirements.txt` com wheels Linux e soma o tamanho).
   Deve passar e ficar dentro do teto atual.
2. No próximo deploy de staging (`/staging-deploy`), `bash scripts/smoke_api.sh` contra o staging:
   health, `/data/map`, `/game/new`, `/game/action` (1 ação, 1 turno de narração real).
3. Se o motion pousou: abrir o staging no navegador, fazer login → criação → jogo (3 trocas de tela
   com `AnimatePresence`) e abrir um `LevelUpModal` ou `DeathModal` se aparecer. Sem tela presa
   em `opacity: 0`.
4. Registrar o resultado em uma linha na spec (data, sha do staging).

## 7. Riscos & compatibilidade

- **Saves:** nenhum impacto. Nada de schema ou estado. `multidict`/`websockets` não tocam
  `persistence.py`.
- **MockLLM/FallbackLLM:** sem mudança. Nenhum `with_structured_output` novo.
- **Quota/latência:** zero LLM a mais. O bundle da Vercel pode mudar alguns KB (multidict 7 diz ter
  ~45 % menos memória por dict, `pr50.md:29-32`).
- **multidict 7 `keys()`:** a semântica muda para chaves distintas. Afeta `aiohttp` (cabeçalhos), que
  já declara compatível `<8`. Nós não usamos o `aiohttp` direto. Risco residual em chamadas HTTP do
  `langchain-community`: coberto pelo smoke §6.2.
- **setup-node 7 em ESM, com runtime Node 24 da action:** os runners são self-pinned (não é
  `ubuntu-latest`, `tests/test_ci_docs_only.py:110`). Se a imagem fixa for antiga demais para o
  runtime da action, o job quebra na hora, o que é visível e fácil de reverter (1 commit).
- **PRs `uv` futuros do Dependabot:** o ecossistema `uv` atualiza o `uv.lock` mas **não** o
  `requirements.txt`. Todo PR `uv` vai reprovar `test_requirements_vercel_utf8_subset_of_lock` até
  alguém reexportar. Ver D-399-4.
- **motion:** a aceleração por hardware de transforms (14.2) e o "delay start when main thread held"
  (14.1) podem mudar o timing. Os e2e rodam quase todos com `reducedMotion: "reduce"`. Só o
  `chromium-motion` vê a animação real, então o smoke visual §6.3 é a rede de segurança.
- **Procedência:** o TS 7 mudou de publicador no npm (`pr42.md:75`). Conferir quando o gatilho disparar.

## Decisões do dono (D-399-n)

- **D-399-1 — TypeScript 7 (#42).** (a) **fechar e adiar** com o gatilho "typescript-eslint aceitar 7"
  (recomendado); (b) deixar aberto como sentinela; (c) subir agora para **TS 6.0.x**, que cabe na peer
  `<6.1.0`, como degrau, numa etapa extra com typecheck/build/lint. **Recomendação: (a)**. O 6.0 é
  versão de transição e não traz ganho para nós hoje. (c) só se o dono quiser adiantar a migração.
- **D-399-2 — ESLint 10 (#46/#47) travado pelo jsx-a11y.** (a) **fechar e adiar** até o
  `eslint-plugin-jsx-a11y` aceitar `^10` (recomendado); (b) pousar com `overrides` de peer no
  `package.json`, sem garantia do plugin; (c) spec própria para trocar o plugin por um fork
  compatível. **Recomendação: (a)**. O lint é bloqueante e cobre a11y (SPEC-284/396), e o ESLint 9 segue
  mantido.
- **D-399-3 — motion 14 (#45).** (a) adiar (sem ganho funcional para nós; risco visual); (b)
  **pousar** com a Etapa 3 e o smoke visual §6.3 (recomendado se a Etapa 0 não achar quebra no 13.0).
  **Recomendação: (b)**, para não acumular duas majors de atraso. Se a Etapa 0 achar API removida
  que usamos, vira (a) automaticamente.
- **D-399-4 — reexport do `requirements.txt` nos PRs `uv`.** (a) manual: o coordenador roda
  `uv export …` e commita no PR do Dependabot antes de mergear (recomendado agora, custo zero); (b) spec
  própria de um workflow que reexporta e commita no PR do Dependabot. **Recomendação: (a)** agora e
  (b) se a frequência incomodar.
- **D-399-5 — `ignore:` no `dependabot.yml` para as majors adiadas.** (a) não ignorar: o Dependabot
  reabre quando sair versão nova, e isso serve de lembrete (recomendado); (b) ignorar
  `typescript>=7`, `eslint/@eslint/js>=10` e `uuid-utils>=1` até o gatilho. **Recomendação: (a)**. O
  `uuid-utils` nem chega a abrir PR `uv` enquanto os pais travarem.
- **D-399-6 — forma do pouso do #44 (e do #45, se pousar).** (a) mergear o PR do Dependabot direto,
  depois de CI verde (recomendado, mantém a autoria do bot); (b) refazer na branch da spec e fechar
  como superseded. **Recomendação: (a)** para #44. Para #45, (a) se o lock do PR já deduplicar o
  `framer-motion`, senão (b).
