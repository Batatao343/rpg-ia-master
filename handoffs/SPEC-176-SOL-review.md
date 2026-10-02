# SPEC-176 — review-pending: Sol High independente

## Execução local atual (2026-10-02)

O coordenador atestou a seleção deste executor pelos parâmetros reais do
`collaboration.spawn_agent`: `model: gpt-6.1-sol`, `reasoning_effort: high`.
Identificador canônico da tarefa/sessão: `/root/spec176_executor`. Nenhum run ID
adicional foi fornecido ou inventado. O bloqueio de preflight registrado abaixo
é histórico e foi resolvido por essa seleção explícita.

```yaml
spec_id: SPEC-176
executor:
  model: sol
  actual_model: gpt-6.1-sol
  effort: high
  actual_effort: high
  session_id: /root/spec176_executor
  run_id: null
  provenance: coordinator attestation of spawn_agent parameters
review:
  required: true
  model: sol
  effort: high
  session_id: /root/spec176_reviewer
  run_id: null
  decision: APPROVED
  scope: technical_local_patch_and_gates
head_sha_before: 1beefc432cce5ded4e3468e42c5e583aa4431a44
head_sha_after_workspace: 1beefc432cce5ded4e3468e42c5e583aa4431a44
verification_snapshot_sha: d988991fc35f2f4532131eb8c748b7f6609b5d55
status: review-pending
human_eval_governance_approval: PENDING
remote_ci: NOT_RUN
```

Implementação e provas: `docs/spec176/README.md` e `dataset-audit.json`.
O clone inicial reproduziu o vermelho. Causa **STALE_LOCK por LF/CRLF**;
27 IDs/expected coincidem com baseline v1 e bytes LF reconstruem exatamente
o hash CRLF aprovado. `.gitattributes` fixa bytes de checkout; o relock canônico
mudou somente um hash. Nenhum dataset/evaluator/expected/baseline/workflow mudou.
O Project Index foi regenerado do source final, continuando selective-only.

Focused ampliado: 80 verdes; CLI sete suites: 86/86; backend offline: 14 × 3
turnos, zero error/warning. Suíte completa final no clone: **1.898 passed,
35 skipped, 15 deselected**, 1 warning, 317,92 s. O workspace principal tem
arte preexistente inacessível, e as execuções Windows precisaram de tempdir
ASCII e identidade Git transitória restrita ao clone conhecido.

Revisor deve conferir: diff protegido de um único hash, provas pré-relock,
byte hashing estrito (tamper CRLF ainda falha), checkout Git true/false,
freshness em LF, scopes/workflows preservados, baseline histórica intocada e
incompatível (incluindo hashes de artifacts CRLF), e ausência de delta A/B.
A revisão independente Sol High retornou **APPROVED técnico local** para
`d988991`; parecer autoral em `SPEC-176-SOL-independent-review.md`.
O approval real `eval-governance` e push/CI verde são gates restantes.
Bloqueio externo confirmado pelo coordenador: connector GitHub com
`push:false` e token `gh` inválido; requer acesso de escrita/reautenticação.
SPEC-177 não foi iniciada; não marcar `done`.

## Preflight histórico em 2026-10-02

- Pacote: `rpg-ia-next-jev-golive-v5.zip`, extraído em `rpg-next-jev-golive-plan/`.
- Integridade: 50 arquivos do `PACKAGE_MANIFEST.json` conferidos por SHA-256 e tamanho; zero divergências.
- HEAD: `1beefc432cce5ded4e3468e42c5e583aa4431a44`, exatamente o snapshot exigido.
- `SPEC-163` a `SPEC-175`: `done` no índice; `SPEC-176` ainda livre.
- Árvore preexistente com exclusões em `web/public/art/v1/`; não foram alteradas nesta sessão.

## Bloqueio de modelo no preflight histórico

O contrato `rpg-next-jev-golive-plan/11_HARNESS_MODEL_CONTRACT.md` exige executor **Sol High** verificável e reviewer **Sol High** em contexto independente para a SPEC-176. Esta sessão não fornece atestação de `actual_model`, `actual_effort` ou `run_id/session_id`. Não é correto declarar equivalência de modelo por inferência. Nenhuma implementação da SPEC-176 foi iniciada, nenhuma spec foi marcada `done` e nenhuma revisão foi inventada.

```yaml
spec_id: SPEC-176
executor_model_required: sol
executor_effort_required: high
actual_model: unverified
actual_effort: unverified
run_id: unavailable
head_sha_before: 1beefc432cce5ded4e3468e42c5e583aa4431a44
status: MODEL_HANDOFF_REQUIRED
review_model_required: sol
review_effort_required: high
review_status: PENDING
```

## Plano de retomada registrado no preflight histórico

1. Abrir executor Sol High com identidade/esforço atestáveis; registrar `run_id/session_id`.
2. Ler o pacote e importar `SPEC-176` a `SPEC-198` no índice sem renumerar.
3. Executar SPEC-176 isoladamente conforme seus gates em checkout limpo, classificando o drift do dataset antes de qualquer relock.
4. Submeter diff, resultados e causa raiz a outra sessão Sol High para revisão independente. Preservar a aprovação humana `eval-governance` quando aplicável.
5. Só avançar para SPEC-177 após SPEC-176 `done` e CI verde.

## Diagnóstico reproduzido antes da implementação (histórico)

- Clone local limpo do HEAD em `.tmp/spec176-clone/`, com `core.autocrlf=false` e `git status --porcelain` vazio.
- `uv run python -m evals.core.governance check --root .` falha em `dataset hash mismatch: datasets/regression/narrative_npc.jsonl`.
- `uv run python -m project_index check` falha em `project index is stale`.
- `uv run pytest tests/test_eval_governance.py tests/test_eval_harness.py -x -q` no clone, com tempdir dentro do workspace, reproduz o mesmo erro de governance no primeiro teste. Uma primeira tentativa sem tempdir local falhou por permissão do sandbox em `%TEMP%`; não é falha do produto.
- O dataset tem 27 objetos JSON idênticos no checkout limpo e no workspace. Os bytes só diferem em LF/CRLF: blob LF `fa831fd0...`, workspace CRLF `30e96c26...`; o hash CRLF é o que consta no lock e na baseline v1. Classificação preliminar: `STALE_LOCK` causado por terminação de linha, não `UNAPPROVED_DATASET_DRIFT` semântico. Ainda exige revisão Sol independente.
- O Project Index registra `source_tree_hash` `c1149edc...`; a geração read-only no clone limpo calcula `f374d4a4...`, com a mesma lista de 434 arquivos e 5.507 nós/14.056 arestas. Artefatos versionados não foram regenerados após mudanças de source. Além disso, 168 arquivos incluídos aparecem com CRLF no workspace Windows e LF nos blobs Git; a correção precisa preservar freshness em ambos os ambientes sem relaxar o check.
- Nenhum lock, evaluator, dataset, index, workflow ou produto foi alterado nesta retomada. Nenhum provider, long-run ou recurso remoto foi acionado.
