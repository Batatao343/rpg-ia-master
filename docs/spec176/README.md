# SPEC-176 — integridade de checkout (review-pending)

## Executor e fronteira de aprovação

Seleção atestada pelo coordenador: `collaboration.spawn_agent` com
`model: gpt-6.1-sol`, `reasoning_effort: high`. Identificador real de tarefa/
sessão: `/root/spec176_executor`. Não foi fornecido um run ID adicional.
Revisão independente Sol High **APPROVED técnico local** na tarefa
`/root/spec176_reviewer`, para o snapshot de código abaixo. Parecer de sua
própria sessão em `handoffs/SPEC-176-SOL-independent-review.md`. O approval
humano do Environment `eval-governance` e o
push/CI verde continuam pendentes. SPEC-177 não foi iniciada.

HEAD inicial do workspace: `1beefc432cce5ded4e3468e42c5e583aa4431a44`.
Snapshot corretivo commitado somente no clone local `.tmp/spec176-clone`:
`d988991fc35f2f4532131eb8c748b7f6609b5d55`. O workspace principal permanece
com as deleções/inacessibilidade preexistentes de `web/public/art/v1`, que não
integram esse snapshot.

## Causa raiz e auditoria antes do relock

Classificação: **STALE_LOCK por LF/CRLF**, sem drift semântico aprovado à força.
`dataset-audit.json` registra a prova antes da escrita:

- os 27 objetos JSON atuais são byte a byte iguais ao blob Git depois de
  substituir apenas CRLF por LF;
- o SHA-256 CRLF `30e96c262d5cadd2a3c5810044e44eb15d75d2d7b96824bf385639269d99f892`
  coincide com lock e baseline v1 congelados;
- o blob LF `fa831fd0f96b952fc0a384cbc6a928a4b2c65a49dfb7e3a6d3da4984ec634d58`
  contém os mesmos 27 IDs e expected presentes nos resultados da baseline;
- a SPEC-171 registra corpus de 27 casos, smoke v3 e aprovação Astra
  `SPEC-171-ASTRA-20260930-01`;
- o histórico Git disponível contém apenas o commit consolidado `1beefc4`
  para esse dataset; não há histórico anterior fabricado.

No clone inicial limpo (HEAD acima, `status --porcelain` vazio,
`core.autocrlf=false`), governance e primeiro teste focused falharam em
`dataset hash mismatch`; o Project Index falhou em `project index is stale`.
Os logs remotos vermelhos são os observados pelo pacote nos runs
`36955976005` e `36955975775`; nenhum novo run remoto foi disparado.

Auditoria dos 434 arquivos originalmente indexados: todos os blobs Git já
eram LF; 168 arquivos do workspace estavam CRLF. Normalizá-los fisicamente
para LF não criou diff de conteúdo versionado. O índice também estava
desatualizado no clone LF, portanto não era apenas efeito de Windows.

## Patch

- `.gitattributes` fixa LF nos tipos de texto usados pelos hashes e pelo
  Project Index. Binários continuam binários.
- O comando canônico `evals.core.governance lock` regravou schemas/lock para os
  seis datasets existentes. O diff protegido contém **apenas um hash** em
  `evals/manifest.lock.json`; zero alteração em evaluator, dataset, expected,
  registry, schema semântico, baseline, exclusão, denominador ou workflow.
- Project Index foi gerado depois da importação do source final: 5.516 nós,
  14.089 arestas, 436 arquivos; hash de source
  `6c8d3607912d46a5766868f8db7b90c23dbff6c4971423c3baf920b0d0d07bf7`.
  Continua selective-only; a política da SPEC-175 permanece vigente.
- As SPEC-176..198 foram importadas com IDs/dependências preservados. A 176
  permanece `review-pending`; 177..198 estão `approved`, sem implementação.
  O pacote original foi arquivado em `docs/rpg-next-jev-golive-plan/`;
  `specs/index.yaml` aponta exclusivamente para as specs canônicas em `specs/`.
  ZIP e pasta de staging permanecem presentes, agora ignorados pelo Git.

## Gates locais

- Governance e Project Index verdes no workspace e no clone corretivo.
  `fresh_commit_drift` é a política existente para o commit dos artefatos,
  mantendo o hash exato de source; não houve bypass.
- Focused ampliado: 80 testes verdes, incluindo governance/harness/index/CI,
  as quatro suítes backend e três regressões de checkout. Clones fixture com
  `core.autocrlf=true/false` mantêm régua válida e bytes de source idênticos;
  alterar LF para CRLF no dataset ainda falha fechado.
- CLI determinística `spec176-clean-deterministic`: sete suites, 86/86 casos,
  zero error/skip/hard failure, sem provider/judge.
- Smoke backend offline: 14 perfis × 3 turnos, zero erros/violações error ou
  warning; run real do harness `20261002-093517-155759`. Não é long-run.
- Ruff e validador da matriz de modelos verdes. `git diff --check` verde;
  `status --porcelain` vazio no snapshot de validação.
- Suíte completa no clone: **1.898 passed, 35 skipped, 15 deselected**,
+  1 warning, em 317,92 s; saída integral em `pytest-full-clean.txt`.

Comandos canônicos de validação:

```powershell
uv run python -m evals.core.governance check --root .
uv run python -m project_index check
uv run pytest tests/test_checkout_integrity.py tests/test_eval_governance.py tests/test_eval_harness.py tests/test_project_index.py tests/test_ci_eval_gates.py tests/test_eval_state_rules.py tests/test_eval_routing.py tests/test_eval_memory_context.py tests/test_eval_narrative_npc.py -q
uv run python -m evals run --suite state_rules --suite routing --suite memory_write --suite memory_retrieval --suite context_grounding --suite generation_boundary --suite narrative_claims --run-id spec176-clean-deterministic
uv run python -m playtest run --all --turns 3
uv run pytest -q
```

No clone foi usado `uv run --no-sync` com o ambiente Python 3.13 do workspace,
cache uv dentro do workspace e temp/cache pytest ASCII. Isso não altera seleção
de testes. O wrapper de suíte completa fixa `--verbosity=0` para registrar a
contagem e `PYTHONUTF8=1`. A execução escalada roda como o usuário guilh,
enquanto o clone foi criado pelo sandbox: por isso o processo recebe
`GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=safe.directory` e
`GIT_CONFIG_VALUE_0=<caminho exato do clone>`. Não é configuração global nem
wildcard; nenhuma regra de governance foi alterada. A primeira execução nessa
identidade falhou em 40 checks Git de ownership (1.858 passed), e os três
checks mínimos de identity/index passaram após corrigir somente o ambiente.

## Limites preservados

A baseline v1 mantém seu hash CRLF histórico. O comparador a rejeita por
`dataset_hashes` contra a régua LF atual. A revisão também identificou que
os hashes de artifacts `baseline-v1.json`, `baseline-v1.md` e `frontend.json`
no manifest v1 foram registrados com CRLF e divergem dos bytes LF do clone;
esse problema já existe no HEAD anterior e permanece explícito. Nenhum delta
de score A/B com v1 pode ser alegado. Qualquer nova baseline comparável
deve ser uma nova medição explicitamente identificada; este patch não
reescreve a evidência congelada nem aceita comparações incompatíveis.

A suíte no workspace foi executada e falhou por acesso às artes preexistentes,
FAISS sem suporte a path Unicode e limites de path Windows ao usar basetemp
sob `Área de Trabalho`. O gate completo usa o clone com os blobs de arte
originais do HEAD e tempdir ASCII, sem restaurar arte no workspace e sem
excluir testes. Frontend não foi alterado/selecionado pelo patch.

O `protected-evaluator-review` deve passar por approval humano real. Nenhum
`EVALUATOR_CHANGE_APPROVED=true` foi injetado em workflow/config de produção.
O coordenador confirmou um bloqueio externo adicional: o connector GitHub
tem `push:false` e `gh auth status` identificou token inválido. Push/CI remoto
exigem reautenticação ou acesso de escrita, além do approval humano. O patch
foi preparado na branch local `spec-176-clean-checkout-integrity`, no clone
isolado, sem incorporar as artes preexistentes. O root permanece reviewável,
sem commit ou troca de branch nesta execução.
Nenhum push, provider real, Jev, cloud, gameplay, prompt, modelo de produto ou
long-run foi executado/alterado.
