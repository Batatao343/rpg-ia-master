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

## Ferramentas

- `Read` antes de `Edit` (sempre). Arquivo > 400 linhas: `Read` com `offset/limit`
  depois de um `Grep` que localize o trecho.
- Busca: ferramentas `Grep`/`Glob`, nunca `grep -r`/`find` via Bash (lento no OneDrive).
- Saída de comando: sempre com teto (`| tail -20`, `--jq`, `head`). Logs remotos com limite.
- **Proibido** ler `tool-results/`, transcritos `.jsonl`, `tasks/*.output` de outros
  agentes, `.env*` (leia segredos só por nome de variável, dentro de scripts).
- Falha do Playwright: leia a mensagem de erro do reporter 1×; não abra o `test-failed-*.png` em loop.

## Testes (camadas — `docs/guias/TESTES.md`)

- Iteração: `-q --lf -x`. Antes do hand-back: só os arquivos de teste do seu escopo.
- **Não** rode a suíte completa: o coordenador roda 1× no `/spec-land`.
- Comando > 2 min: `run_in_background: true` + `timeout` explícito, ou foreground com
  `timeout: 900000`. Espere com **uma** notificação/Monitor; nunca `sleep` em loop.

## Arquivos que você não edita

`ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml` (gerado), `project_index/`
(gerado no pouso) e, se você otimiza produto, nada de `evals/` protegido
(`evals/protected-paths.txt`). Status de spec = só o cabeçalho da sua spec.

## Commits

Na sua branch, mensagem em inglês (Conventional Commits), terminando com a linha
`Co-Authored-By` informada pelo sistema. Sem push, sem merge na `main`.

## Hand-back (único)

Uma única entrega, ≤ 20 linhas: branch + commits, testes rodados (contagem),
pendências/bloqueios, e um parágrafo ≤ 6 linhas pt-BR para o coordenador colar no
ESTADO. **Nunca** termine o turno "esperando" algo: bloqueou em decisão do dono →
registre no hand-back e termine. Não mande um segundo hand-back.
