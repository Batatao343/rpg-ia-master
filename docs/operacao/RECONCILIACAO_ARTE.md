# Reconciliação de geração de arte após crash

O resultado externo de uma geração não participa da transação Postgres. Timeout
ou morte do worker **não comprovam que o provider deixou de gerar/cobrar**.

## Identificar

Consulte o endpoint autenticado `GET /game/{game_id}/art/{generation_id}`.
`reconcile_required` significa resultado externo incerto: no banco pode ser
`failed` com `external_result_uncertain` ou `generating` sem lease ativa.
Preserve generation_id, epoch, trigger e metadados para a investigação; não
publique prompts privados, chaves ou URLs assinadas nos logs/relatórios.

## Conter e verificar

1. Pare novas reservas do worker de arte pelo mecanismo normal de shutdown.
   Deixe trabalhos em andamento terminarem; se for necessário matar o processo,
   identifique seu PID exato. Nunca encerre todos os processos Python.
2. Aguarde expiração da lease ou término confirmado. Não altere tokens nem
   estenda artificialmente uma reserva expirada.
3. Verifique os registros do provider e os objetos já enviados ao Storage,
   usando o identificador da geração. Ausência de objeto no Storage **não**
   prova ausência de geração/cobrança no provider.
4. Confira ownership, campanha, epoch e validade do gatilho antes de qualquer
   recuperação. Arte de timeline anterior não pode ser publicada na atual.

## Decidir sem cobrança automática

- Resultado ainda incerto: manter `reconcile_required` e arte-base/placeholder.
  Não retornar a `pending`/`failed_retryable`; reiniciar o worker não autoriza
  outra chamada ao provider.
- Resultado recuperável: preservar os arquivos e metadados. A importação precisa
  de ferramenta administrativa que valide os arquivos, epoch e fencing; essa
  ferramenta ainda não existe. Não publicar com SQL improvisado nem chamar
  `complete` fora de um job com lease válida.
- Perda confirmada: registrar a conclusão e solicitar autorização explícita de
  nova geração/custo. Não reutilizar silenciosamente a operação original.

Hoje o procedimento seguro termina em contenção e diagnóstico; recuperação
administrativa de uma imagem externa não é automatizada. Essa limitação mantém
aberto o aceite operacional integral da spec de leases, sem comprometer o jogo:
a campanha continua usando arte-base e não fica bloqueada pelo provider.

## Evidência local reproduzível

`tests/test_process_crash_local.py` mata somente subprocessos próprios: retomada
de job, rollback após INSERT de arte e crash após retorno de gerador falso.
`tests/test_art_worker_reconciliation.py` confirma ausência de segunda chamada
após resultado incerto. Não usar provider de imagem pago nesses testes.
