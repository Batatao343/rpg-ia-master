# SPEC-178 — revisão Sol independente da tentativa live bloqueada

Data local: 2026-10-05. Revisor: `/root/spec176_reviewer`, Sol High, read-only.
Decisão: **APPROVED técnico local** para o retry de escrita e o bloqueio da
tentativa. A SPEC-178 permanece incompleta.

## Evidência examinada

- A sanidade A teve dois attempts externos: DeepSeek falhou e Groq respondeu.
  O log da execução mostrou DeepSeek HTTP 402 `Insufficient Balance`.
- `fatal_sanity_error=true` no artifact recuperado; nenhum sanity B, réplica,
  `summary.json`, score ou promoção.
- `raw.json` está stale (`in_progress`, `calls=0`); usar
  `evals/runs/jev-router-ab/20261006T012413Z/raw-recovered.json` como estado
  final. Seu SHA-256 é
  `2c80eba8cb337ac13c4bc7cd5a62f07e7640a94399bcd7290921f1e72ae633aa`,
  idêntico ao de `raw.json.tmp`.
- Nove testes focados e Ruff verdes. Prova offline do bloqueio permanente de
  arquivo confirmou 10 tentativas de replace/9 pausas, depois
  `PermissionError`, preservando destino anterior e `.tmp` final.
- Quatro chamadas externas ocorreram no total das 100 autorizadas; restam 96.
  Um run completo novo exige pelo menos 98 e é rejeitado antes de criar
  backend ou diretório sob o teto antigo.

O revisor não fez chamadas externas, não acessou segredos e não editou source.
Não reduzir as três réplicas nem reutilizar a sanidade fatal para caber no
saldo antigo. O raw não guarda o código HTTP 402 explicitamente; esse detalhe
vem do log da execução.
