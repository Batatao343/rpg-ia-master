# SPEC-178 — Jev vs CLASSIFY: estado de execução

Data: 2026-10-05. Status: `blocked-by-provider` até rotação da credencial.

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
- Verificação local: 37 testes focados verdes após a correção TypeSafe;
  suíte completa `uv run pytest` verde (1.935 passed, 35 skipped,
  15 deselected); Ruff, governance e Project Index atualizado/verde. Revisões
  Sol independentes aprovam a implementação offline em
  `handoffs/SPEC-178-SOL-independent-review.md` e
  `handoffs/SPEC-177-SOL-typesafe-correction-review.md`.

## Correção de configuração e smoke live

A primeira chamada Jev retornou HTTP 401 porque foi enviada a `jevmodel.org`.
O usuário esclareceu que sua chave veio da TypeSafe. A documentação oficial
indica `api.typesafe.ai/v1/systemone` e `TYPESAFE_API_KEY`; o adapter passou a
aceitar a variável local `JEVMODEL_API_KEY` como alias compatível. Uma única
chamada sintética ao host oficial retornou `jev-1.13.0`, Choice `storyteller`,
usage 394 tokens de entrada e 58 de saída, latência 327 ms. A chave nunca foi
impressa, copiada para artifacts ou persistida. **A primeira chamada enviou a
chave TypeSafe como Bearer a um domínio diferente.** O usuário foi informado e
vai revogar/substituir a credencial no painel TypeSafe. Nenhuma outra chamada
live será feita até confirmar a rotação. Nenhuma amostra do corpus foi enviada
no smoke. Até o A/B terminar, não há score nem promoção válida.

Antes do A/B, ocorreram **2 chamadas externas**: a 401 ao host errado e a
sanidade oficial bem-sucedida. Restam **98 chamadas** do teto autorizado de
100; o runner deve ser invocado com `--max-calls 98 --max-cost-usd 0.98` e
interromper se qualquer fallback/regeneração consumir uma chamada extra.

O budget reserva US$ 0,01 por tentativa como regra conservadora de parada e
registra custo reportado quando existir. Essa reserva **não é custo medido** nem
garantia financeira: o adapter Jev e parte da cascata CLASSIFY podem omitir
custo. Os artifacts registram `unavailable` nesses casos. Para cumprir um teto
financeiro estrito, é necessário também limite de gasto na conta do provider ou
outra fonte confiável de cobrança antes de liberar o A/B live.

## Comandos

```powershell
uv run python -m evals.experiments.jev_router_ab --preflight
uv run python -m evals.experiments.jev_router_ab --output-dir evals/runs/jev-router-ab/<run-id> --max-calls 98 --max-cost-usd 0.98
```

O segundo comando deve ser executado uma vez por experimento; `raw.json`
persiste antes de `summary.json`. Se sanity ou qualquer réplica falhar, o run
fica `blocked-by-provider` e não produz summary. Runs completos não são
descartados após observar o score. `evals/runs/` é ignorado pelo Git.

## Próximos passos

1. Usuário revoga a chave TypeSafe antiga e avisa após substituir o valor local.
2. Executar o protocolo completo e anexar paths/identidade dos artifacts.
3. Obter revisão Sol independente do resultado, incluindo vazamento e seleção.
4. Só então marcar a SPEC-178 `done` e iniciar a SPEC-179.
