# SPEC-176 — revisão independente Sol High

## Identidade e decisão

```yaml
spec_id: SPEC-176
reviewer:
  model: gpt-6.1-sol
  effort: high
  task_session_id: /root/spec176_reviewer
  selection_evidence: collaboration.spawn_agent informado pelo coordenador
  independent_from_executor: true
executor_task_session_id: /root/spec176_executor
head_sha_before: 1beefc432cce5ded4e3468e42c5e583aa4431a44
reviewed_head_sha: d988991fc35f2f4532131eb8c748b7f6609b5d55
decision: APPROVED
decision_scope: technical_local_patch_and_gates
remote_ci_status: PENDING
human_eval_governance_approval: PENDING
spec_completion: review-pending
```

Revisão realizada em contexto separado do executor. A seleção de modelo e
effort foi informada pelo harness/coordenador; não foi disponibilizado um run
ID adicional. O reviewer não alterou código, specs, evaluators ou evidência
do executor. Este arquivo registra o parecer de sua própria sessão.

**APPROVED técnico local** para o snapshot acima, sem findings bloqueantes.
Isso não declara a SPEC-176 `done` nem substitui aprovação humana ou CI remoto.

## Escopo e provas independentes

- Foram lidos AGENTS.md, ESTADO_ATUAL.md, SPEC-176, o contrato de harness,
  a entrada SPEC-176 da matriz de modelos e a política de execução.
- Revisado o diff `HEAD^..HEAD` no clone `.tmp/spec176-clone`, incluindo
  `.gitattributes`, lock, teste de checkout, índice regenerado e importação.
- `narrative_npc.jsonl` mantém bytes idênticos ao parent. O hash LF é
  `fa831fd0f96b952fc0a384cbc6a928a4b2c65a49dfb7e3a6d3da4984ec634d58`.
  Converter somente LF para CRLF produz exatamente o hash histórico
  `30e96c262d5cadd2a3c5810044e44eb15d75d2d7b96824bf385639269d99f892`.
  Os 27 IDs e todos os expected coincidem com os resultados da baseline v1.
  A classificação **STALE_LOCK por LF/CRLF** foi confirmada independentemente.
- O único delta do lock é o hash desse dataset. Nenhum diff em evaluator,
  dataset, expected, registry, baseline, workflows ou protected-paths.
- A comparação dos objetos do índice encontrou zero nós/arestas removidos:
  +9 nós e +33 arestas referentes exclusivamente ao teste de checkout e ao
  validador de contrato importado. Freshness continua verificando bytes exatos.
- Os 50 arquivos arquivados conferem em SHA-256 e tamanho com o
  PACKAGE_MANIFEST. As 23 specs canônicas diferem das originais somente no
  status autorizado e no caminho da matriz de modelos.
- O scope seleciona backend e revisão protegida, sem selecionar frontend;
  o único path protegido alterado é `evals/manifest.lock.json`.
  A chamada `verify(scope, '')` foi rejeitada com PermissionError.
  Não foi identificado bypass do approval.

## Comandos e resultados

Checks executados pelo reviewer no clone, com Python 3.13 via `uv run`,
`--no-sync`, ambiente virtual do workspace e cache uv dentro do workspace:

| Comando/prova | Resultado |
| --- | --- |
| `uv run --no-sync python -m evals.core.governance check --root .` | exit 0; seis datasets válidos |
| `uv run --no-sync python -m project_index check` | exit 0; 5.516 nós/14.089 arestas; source hash `6c8d3607912d46a5766868f8db7b90c23dbff6c4971423c3baf920b0d0d07bf7` |
| Classificação por `scripts.ci_eval_scope.classify` do diff real | backend=true, frontend=false, protected=true |
| `scripts.verify_protected_eval_change.verify(scope, '')` | PermissionError esperado; approval ausente rejeitado |
| Auditoria Python dos bytes/hash/IDs/expected e manifest/importação | todas as verificações descritas acima passaram |
| `git rev-parse HEAD` | snapshot `d988991fc35f2f4532131eb8c748b7f6609b5d55` |
| `git status --porcelain` no clone após a suíte | vazio |
| `git diff --check HEAD^ HEAD` | exit 0 |

`fresh_commit_drift` no índice usa a política preexistente de aceitar diferença
de commit quando o source tree é byte a byte idêntico; o check não foi relaxado.

Evidência de execução do executor inspecionada pelo reviewer:

- Focused ampliado: 80 testes verdes, incluindo os três testes novos de
  portabilidade de checkout e rejeição de tampering CRLF.
- CLI determinística: sete suites, 86/86 casos, sem error/skip/hard failure.
- Smoke backend offline: 14 perfis × 3 turnos, sem erros/violações.
- Suíte completa final do snapshot: **1.898 passed, 35 skipped,
  15 deselected, 1 warning em 317,92s**. A saída foi conferida em
  `.tmp/spec176-final-full-clean.log`; o warning é a depreciação existente de
  langchain-community. O reviewer não repetiu a suíte completa.

A execução completa anterior com 40 falhas não foi aceita como gate. O
executor corrigiu somente o ambiente Git do processo com safe.directory
restrito ao clone, por diferença de ownership entre sandbox e usuário guilh,
e repetiu a suíte completa sem excluir testes ou alterar produto.

## Limites e gates restantes

A baseline v1 permanece congelada e incompatível com o hash LF atual.
Os hashes de artifacts baseline-v1.json, baseline-v1.md e frontend.json no
manifest v1 também representam CRLF e divergem dos bytes LF do clone; isso já
ocorria no parent. A limitação foi comunicada ao executor e está documentada
em docs/spec176/README.md. Nenhum delta A/B válido contra v1 foi alegado.

O parecer cobre o snapshot isolado, que não contém as deleções/inacessibilidade
de artes preexistentes no workspace principal. Não foram revisadas alterações
de gameplay fora desse snapshot.

Antes de concluir a SPEC-176, permanecem necessários:

- registrar a contagem final e este parecer na documentação de execução;
- preparar o commit final com somente as mudanças autorizadas e seus artifacts;
- obter aprovação humana explícita e auditável do environment eval-governance;
- fazer push e exigir verde nos jobs remotos aplicáveis;
- manter a SPEC-176 review-pending e a SPEC-177 sem início até cumprir os gates.

Nenhum provider real, Jev, cloud ou long-run foi executado nesta revisão.
