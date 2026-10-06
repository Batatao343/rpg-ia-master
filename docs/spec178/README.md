# SPEC-178 — Jev vs CLASSIFY: estado de execução

Data: 2026-10-05. Status: `blocked-by-provider`.

## Autorização e escopo

O usuário autorizou Sol High como executor substituto de Terra High e o A/B
live com até 100 chamadas externas e US$ 1. A revisão Sol High é independente
do executor. Nenhuma rota de produção ou caminho protegido de eval foi alterado.

## Preflight offline

- Corpus read-only: `evals/datasets/regression/routing_actions.jsonl`.
- Hash SHA-256: `ad6f48be2a66f1e5f5b55c5f61bdd9f457dcb611c2568fa0008d35fbf2596bb4`,
  igual ao lock.
- 21 casos de classificação/route: 16 chegam ao backend, 5 terminam nos gates
  Python. Elegibilidade provada com sentinela em `agents.router.get_llm`, sem
  lista de exclusões manual.
- Runner experimental: `evals/experiments/jev_router_ab.py`; dados do candidato
  são apenas `AdapterCase` sanitizado / DTO Jev. O score lê `expected` somente
  após persistir `raw.json` completo.
- Protocolo selado no código: primeiro caso elegível como sanity por braço;
  3 réplicas pareadas dos 16 elegíveis, na ordem do dataset, e `pipeline_full`
  com os 21 casos na réplica 1. São no mínimo 98 chamadas externas (2 sanity +
  96 comparação), se não houver fallback ou regeneração.
- Verificação local: 8 testes focados verdes; suíte completa `uv run pytest`
  verde (1.928 passed, 35 skipped, 15 deselected); Ruff, governance e
  Project Index atualizado/verde. Revisão Sol independente aprova a
  implementação offline em `handoffs/SPEC-178-SOL-independent-review.md`.

## Bloqueio live

A única chamada Jev de sanity anterior à implementação do runner retornou
`JevAuthenticationError`/HTTP 401. O valor da chave nunca foi impresso, copiado
ou persistido. Uma checagem booleana local confirmou `JEVMODEL_API_KEY` presente
no `.env`, porém sem o prefixo `sk-` que a documentação do endpoint exige.
Nenhuma chamada CLASSIFY do A/B ou réplica comparativa foi realizada. O runner
não foi executado live com a credencial rejeitada. O corpus não tem score A/B;
nenhuma conclusão de qualidade ou promoção é válida.

O budget reserva US$ 0,01 por tentativa como regra conservadora de parada e
registra custo reportado quando existir. Essa reserva **não é custo medido** nem
garantia financeira: o adapter Jev e parte da cascata CLASSIFY podem omitir
custo. Os artifacts registram `unavailable` nesses casos. Para cumprir um teto
financeiro estrito, é necessário também limite de gasto na conta do provider ou
outra fonte confiável de cobrança antes de liberar o A/B live.

## Comandos

```powershell
uv run python -m evals.experiments.jev_router_ab --preflight
# Somente após corrigir a credencial e garantir o teto externo de gasto:
uv run python -m evals.experiments.jev_router_ab --output-dir evals/runs/jev-router-ab/<run-id>
```

O segundo comando deve ser executado uma vez por experimento; `raw.json`
persiste antes de `summary.json`. Se sanity ou qualquer réplica falhar, o run
fica `blocked-by-provider` e não produz summary. Runs completos não são
descartados após observar o score. `evals/runs/` é ignorado pelo Git.

## Próximos passos

1. Corrigir a credencial de jevmodel.org localmente, sem enviá-la no chat.
2. Confirmar um mecanismo de teto financeiro externo de US$ 1.
3. Executar o protocolo completo e anexar paths/identidade dos artifacts.
4. Obter revisão Sol independente do resultado, incluindo vazamento e seleção.
5. Só então marcar a SPEC-178 `done` e iniciar a SPEC-179.
