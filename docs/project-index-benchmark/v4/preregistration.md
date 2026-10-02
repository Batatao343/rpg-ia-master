# SPEC-175 — pré-registro v4 final

Registrado antes de qualquer sessão v4. V1 foi bloqueada pela revisão Sol; v2
falhou antes de quatro runs completos; v3 completou os runs, mas o material de
reveal ficou indisponível após compactação, portanto nenhum resultado v3 será
comparado ao ground truth. Todas as tentativas anteriores ficam fora do cálculo.

O ground truth factual v4 foi escrito antes dos runs em
`sealed/ground-truth.json`. Esse caminho está sob `docs/`, bloqueado pelo
harness, e os prompts também proíbem sua leitura. Depois dos quatro runs, o
reveal copiará os mesmos bytes para `ground-truth.json`; o arquivo selado e seu
hash não serão modificados.

## Desenho

- Duas réplicas Terra High por condição, agentes novos sem histórico: A1/B2 em
  B01→B08 e A2/B1 em B08→B01.
- Prompt exato por sessão em `session-prompts/`, com hash na attestation e no
  arquivo de sessão.
- Budget simétrico: 12 discovery calls, 50.000 source bytes e 300 segundos por
  tarefa. Wall time é observacional.
- A usa search/read do harness. B consulta o índice primeiro e confirma no
  source. Git, docs, specs, instruções e benchmark são bloqueados.
- Calls, bytes e wall time vêm somente dos traces automáticos. Nenhum run edita
  produto ou executa testes.

Tarefas: B01 morte falsa após `player_downed`; B02 aliases/identidade de NPC;
B03 reward versus receipt; B04 ação em inconsciência/`death_pending`; B05 JSON
raw structured; B06 persistência de arte; B07 replay/payload divergente; B08
logout mobile.

Métricas: `resolved` exige core file e os dois sinais; localization exige core
file entre os três primeiros; irrelevantes excluem tests; recall normaliza
`::test_name`; calls/bytes/wall vêm do trace. Usa-se média das réplicas por
tarefa e mediana das 16 observações por condição. `cost_win`: B reduz calls ou
bytes sem piorar a outra dimensão mais de 10%. Redução global: pelo menos 20%
em uma mediana, sem piora acima de 10% na outra.

Decisão congelada:

- **Obrigatório:** B não reduz resolved/localization, não aumenta irrelevantes,
  reduz uma mediana em ≥20% e vence custo em 6/8 tarefas.
- **Seletivo:** B não reduz resolved e vence custo em ≥4/8 tarefas, sem cumprir
  todo o critério obrigatório.
- **Remover do fluxo padrão:** B reduz resolved, ou vence menos de 4/8 tarefas
  sem ganho de localização suficiente para justificar a complexidade.
