# SPEC-178 — Jev vs CLASSIFY: estado de execução

Data local: 2026-10-05. Status: `done`; evidência de desenvolvimento/regressão,
sem promoção do Jev.

## Resultado confirmatório

Após a recarga da DeepSeek, o usuário autorizou elevar o teto total da
avaliação para **120 chamadas e US$ 1,20**. Descontadas as quatro chamadas
anteriores, o run recebeu limites de 116 chamadas e reserva de US$ 1,16.
O run `SPEC-178-20261006T013715Z-bedc56c2` terminou `complete` com **98
chamadas**, 3 réplicas pareadas, nenhuma falha e nenhum fallback. No histórico
foram 102/120 chamadas; restam 18. A reserva interna acumulada equivale a
US$ 1,02, mas **custo real não foi reportado** pelos providers e não pode ser
certificado por esse número.

| Recorte | CLASSIFY atual (A) | Jev 1.13.0 (B) |
|---|---:|---:|
| `pipeline_full` (21 pares, réplica 1) | 21/21 (100%) | 20/21 (95,24%) |
| `classifier_eligible` (48 pares, 3 réplicas) | 48/48 (100%) | 46/48 (95,83%) |
| Latência p50 do backend, elegíveis | 1.367,5 ms | 265,5 ms |
| Latência p95 do backend, elegíveis | 1.607,45 ms | 319,65 ms |
| Falha/indisponibilidade | 0/48 | 0/48 |

Todas as 49 chamadas do braço A usaram `deepseek-v4-flash`; as 49 do braço B
resolveram `jev-1.13.0`. O uso, incluindo sanidades, foi A 29.846 tokens de
entrada/6.893 de saída e B 24.235/2.766. Custo por caso permanece
`unavailable` no raw. A única divergência foi `routing.npc.corvo.case` nas
réplicas 1 e 3: ação `FALO COM CORVO`, A escolheu `npc_actor` nas três, B
escolheu `combat_agent` em duas e `npc_actor` em uma. As probabilidades Jev
foram válidas; as escolhas divergentes tiveram confiança 0,30/0,27.

O corpus protegido permaneceu no hash
`sha256:ad6f48be2a66f1e5f5b55c5f61bdd9f457dcb611c2568fa0008d35fbf2596bb4`.
Produto avaliado: commit `ec68012d5291ccd5428053b5dc76f6694421334d`, árvore
limpa. O raw foi persistido antes do score; o resumo foi reproduzido offline
a partir dele. Artifacts copiados sem alteração para
`evals/runs/jev-router-ab/20261006T013714Z/` (gitignored):

- `raw.json` SHA-256 `590876391dd9a97aaad3ea147a672b7368ed3ba3af8eaa00b2380eb3dbaa22`;
- `summary.json` SHA-256 `7fcff90f9d73d190154ccf2d64dc2fe347bb9ad3b9013996f25f8ef0c4c958b`.

A revisão Sol High independente aprovou o resultado como evidência de
desenvolvimento/regressão: `handoffs/SPEC-178-SOL-result-review.md`. A régua
protegida e a produção não mudaram. Este A/B **não promove Jev** nem autoriza
ajustar prompt, limiar ou dataset após observar as divergências.

## Histórico da tentativa bloqueada

Os parágrafos abaixo registram a condição anterior ao run confirmatório acima.

## Tentativa após a rotação da chave

O usuário confirmou que substituiu a chave TypeSafe. A tentativa
`SPEC-178-20261006T012415Z-ba7f0fc4` parou na sanidade A, antes de chamar
Jev: DeepSeek `deepseek-v4-flash` retornou HTTP 402 `Insufficient Balance`;
a cascata produziu `combat_agent` via Groq `openai/gpt-oss-20b`, mas o protocolo
interrompe em falha de autenticação/quota/configuração mesmo com fallback.
Não houve réplica, score, resumo ou promoção. O budget registrou **2 chamadas**
nesta tentativa, **4 no total** desde o início do trabalho e **96 restantes**
do teto de 100. Um novo protocolo completo exige pelo menos 98 chamadas;
aguardam saldo DeepSeek e decisão do usuário sobre um novo teto.

O Windows/OneDrive bloqueou a substituição atômica final de `raw.json`.
`evals/runs/jev-router-ab/20261006T012413Z/raw.json` contém o registro
intermediário; `raw.json.tmp` contém o estado final `blocked-by-provider`
e foi copiado byte-identical para `raw-recovered.json` (SHA-256
`2c80eba8cb337ac13c4bc7cd5a62f07e7640a94399bcd7290921f1e72ae633aa`).
O runner ganhou retry limitado para bloqueio transitório de arquivo; o teste
focado dessa falha passou. Nove testes focados e a suíte completa ficaram
verdes (**1.936 passed, 35 skipped, 15 deselected**); governance, índice e
Ruff também passaram. Revisão Sol independente: `handoffs/SPEC-178-SOL-live-blocker-review.md`.
O próximo run deve gravar artifacts em um diretório
temporário local fora da pasta sincronizada e só depois copiá-los com hashes
conferidos. Nenhuma chamada externa adicional foi feita durante a correção.

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

A primeira chamada Jev histórica retornou HTTP 401 porque foi enviada a `jevmodel.org`.
O usuário esclareceu que sua chave veio da TypeSafe. A documentação oficial
indica `api.typesafe.ai/v1/systemone` e `TYPESAFE_API_KEY`; o adapter passou a
aceitar a variável local `JEVMODEL_API_KEY` como alias compatível. Uma única
chamada sintética ao host oficial retornou `jev-1.13.0`, Choice `storyteller`,
usage 394 tokens de entrada e 58 de saída, latência 327 ms. A chave nunca foi
impressa, copiada para artifacts ou persistida. **A primeira chamada enviou a
chave TypeSafe como Bearer a um domínio diferente.** O usuário foi informado e
informou que substituiu a credencial no painel TypeSafe. Nenhuma outra chamada
live foi feita até confirmar a rotação. Nenhuma amostra do corpus foi enviada
no smoke. Naquele ponto não havia score nem promoção válida.

Antes da tentativa A/B, ocorreram **2 chamadas externas**: a 401 ao host
errado e a sanidade oficial bem-sucedida. O teto então permitia 98 chamadas;
a tentativa CLASSIFY acima consumiu outras duas. O comando histórico abaixo
não deve ser reexecutado sob o teto original.

O budget reserva US$ 0,01 por tentativa como regra conservadora de parada e
registra custo reportado quando existir. Essa reserva **não é custo medido** nem
garantia financeira: o adapter Jev e parte da cascata CLASSIFY podem omitir
custo. Os artifacts registram `unavailable` nesses casos. Para cumprir um teto
financeiro estrito, é necessário também limite de gasto na conta do provider ou
outra fonte confiável de cobrança antes de liberar o A/B live.

## Comandos utilizados

```powershell
uv run python -m evals.experiments.jev_router_ab --preflight
uv run python -m evals.experiments.jev_router_ab --output-dir "$env:TEMP/rpg-spec178-ab-20261006T013714Z" --max-calls 116 --max-cost-usd 1.16
```

O segundo comando deve ser executado uma vez por experimento; `raw.json`
persiste antes de `summary.json`. Se sanity ou qualquer réplica falhar, o run
fica `blocked-by-provider` e não produz summary. Runs completos não são
descartados após observar o score. `evals/runs/` é ignorado pelo Git.

## Fechamento

As três réplicas e os gates de aceite da SPEC-178 estão completos. A
SPEC-179 pode começar após o gate final de testes/CI deste commit. Qualquer
experimento live da próxima spec exige orçamento específico; as 18 chamadas
restantes pertencem ao teto desta avaliação e não constituem autorização
automática para outra spec.
