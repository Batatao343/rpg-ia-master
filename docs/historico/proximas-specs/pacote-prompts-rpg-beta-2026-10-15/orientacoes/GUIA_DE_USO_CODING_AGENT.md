# Como operar este pacote sem gastar contexto demais

**Primeira mensagem ao agent:** “Leia `README_COMECE_AQUI.md`, `DECISOES_PRODUTO.md`, `prompts/00-*.md`. Audite o HEAD real e mostre a sequência das specs existentes/necessárias. Não implemente nada. Não rode provider real ou long-run.”

**Segunda etapa:** escolher só UM `prompts/NN-*.md` e fornecer arquivos de referência relevantes. Exigir scope/draft, não abrir múltiplas specs numa única execução gigante.

**Revisar:** conferir que (i) não duplicou spec `done`/`approved`, (ii) ID obtido de HEAD, (iii) mecânicas derivadas do backend, (iv) não mudou evaluator/expected/dataset no mesmo trabalho, (v) metas observáveis, (vi) modelo/tier de execução correto, (vii) nada pago sem permissão.

**Depois de aprovar spec:** só então pedir implementação em novo contexto/tarefa, usando a spec aprovada; o executor não altera evaluator protegido para conseguir passar.

**Distinguir**: os HTMLs têm texto ilustrativo e podem contradizer escolhas fechadas posteriores. Por exemplo, o `v01` demonstra seletor explícito de interlocutor, **mas a decisão final é roteamento automático**. O `v03` remove confirmação redundante no combate e substitui o `v02`.
