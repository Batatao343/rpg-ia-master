# Brief comum de subagente (versionado)

Lido por todo subagente deste repo. O prompt do spawn deve ter só o específico:
`SPEC-NNN · worktree <caminho> · decisões do dono: … · entregue hand-back único.`
Os tipos em `.claude/agents/` já embutem o papel; este arquivo é a regra comum.

## Ambiente

- Trabalhe **só** no worktree indicado (fora do OneDrive). Nunca edite o checkout
  principal nem crie clones dentro do repo.
- Python: `bash scripts/dev/py.sh …` (raiz do repo, `PYTHONUTF8=1`, uv, venv certo).
  Nunca `python` global (3.14) nem `python -` fora da raiz.
- Node: `web/node_modules` é junção do checkout principal; se faltar, pare e avise.
- Fim de linha é LF em tudo (`.gitattributes`); não trate `\r\n` à mão.

## Ferramentas (hooks barram o que está em **negrito**)

- `Read` antes de `Edit`/`Write`, **inclusive** em arquivo que você criou ou mudou via Bash
  (295 erros "File has not been read yet" em subagentes até 03/11).
- **Arquivo > 40 KB: nunca inteiro** (`Read` sem `offset/limit` e `cat`/`Get-Content` são
  negados). `Grep` acha o trecho; `Read` com `offset/limit` lê. Spec grande:
  `bash scripts/dev/py.sh scripts/spec_index.py show NNN` (sumário) e `--section <título>`.
- Busca: ferramentas `Grep`/`Glob`, nunca `grep -r`/`find` via Bash (lento no OneDrive).
- Saída de comando: sempre com teto (`| tail -20`, `--jq`, `head`) ou
  `bash scripts/dev/cap.sh 40 <comando>` (grava o resto em arquivo).
- Sem `cd` antes de cada comando: o cwd já é o worktree; use `git -C <wt>` se precisar.
- CI é do `ci-watcher`/coordenador: não faça `gh run watch`/loop de `gh run view`.
- **Proibido** ler `tool-results/`, **transcritos `.jsonl`, `tasks/*.output`** de outros
  agentes, `.env*` (leia segredos só por nome de variável, dentro de scripts).
- Falha do Playwright: leia a mensagem de erro do reporter 1×; não abra o `test-failed-*.png` em loop.

## Qualidade do código (AGENTS.md § Qualidade, revisão e evidência)

- Antes de criar helper (fold de texto, leitor de flag, JSON com cache, parse de LLM):
  `Grep "def <nome>"` e reutilize. Criou helper genérico novo? Liste no hand-back.
- Função nova ≤ 60 linhas. Arquivo > 1.000 linhas não cresce: extraia para módulo novo
  (`tests/test_size_budget.py` reprova crescimento).
- O hook já roda `ruff format` + `ruff check --fix` a cada edição de `.py`; violação que
  sobrar aparece para você — corrija antes do hand-back.
- Menor mudança correta: nada de refatorar fora do escopo da spec. Duas tentativas falharam
  pelo mesmo motivo → pare, investigue a causa e registre a hipótese antes de editar de novo.

## Testes (camadas — `docs/guias/TESTES.md`)

- Iteração: `bash scripts/dev/pt.sh <testes> [--lf]` (`-n 2`, `-x`, só falhas + resumo; log
  completo em arquivo). Antes do hand-back: só os arquivos de teste do seu escopo.
- **Não** rode a suíte completa: o coordenador roda 1× no `/spec-land`.
- Teste novo: `tests/test_<modulo>.py` ou de feature, nunca `test_specNNN_*.py` novo (spec na docstring).
- Estado de jogo via `tests/factories.py` (`make_state`) e LLM via `tests/fakes/scripted_llm.py` (`ScriptedLLM`); helper local só com justificativa.
- Teste que lê código-fonte só no caso (c) do inventário. Regra completa: `docs/guias/TESTES.md` § "Onde mora um teste novo".
- **Nunca** `-n auto`; no máximo `-n 2` (**o hook nega** em subagente). Vários agentes rodam ao mesmo tempo numa
  máquina de 16 GB: em 24/10 cinco suítes `-n auto` paralelas esgotaram a RAM e
  derrubaram a sessão. Não deixe `pytest` em background ao entregar o hand-back.
- Comando > 2 min: `run_in_background: true` + `timeout` explícito, ou foreground com
  `timeout: 900000`. Espere com **uma** notificação/Monitor; nunca `sleep` em loop.

## Arquivos que você não edita

`ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml` (gerado), os curados de `project_index/`
(`domains.yaml` etc.; o grafo gerado é local, `python -m project_index build`) e, se você otimiza produto, nada de `evals/` protegido
(`evals/protected-paths.txt`). Status de spec = só o cabeçalho da sua spec.

## Commits

Na sua branch, mensagem em inglês (Conventional Commits), terminando com a linha
`Co-Authored-By` informada pelo sistema. Sem push, sem merge na `main`.

## Hand-back (único)

Uma única entrega, ≤ 20 linhas: branch + commits, testes rodados (contagem),
pendências/bloqueios, e um parágrafo ≤ 6 linhas pt-BR para o coordenador colar no
ESTADO. **Nunca** termine o turno "esperando" algo: bloqueou em decisão do dono →
registre no hand-back e termine. Não mande um segundo hand-back.
