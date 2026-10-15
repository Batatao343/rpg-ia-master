# Politica de Reembolso - Valoria (RPG IA)

> **RASCUNHO - revisar com o titular (e assessoria juridica) antes de publicar.** Reflete
> `docs/spec195/refund-debt-policy.md`. Itens `<...>` a preencher.

1. **Direito de arrependimento (CDC art. 49).** Compras feitas online podem ser desistidas em ate 7 dias, **desde que as Estilhas da
   compra nao tenham sido consumidas**; Estilhas ja gastas em turnos/voz/imagens nao retornam (servico ja prestado). `<confirmar tratamento do consumo parcial com assessoria>`.
2. **Como pedir.** Web (Stripe): `suporte@<dominio-a-definir>` com e-mail da conta e data da compra; reembolso ao meio de pagamento original, prazo conforme a operadora.
   Android: reembolso conforme as regras do Google Play (pedido pela Play Store; o Google pode reembolsar automaticamente em alguns casos).
3. **Efeito no saldo.** Ao reembolsar, as Estilhas correspondentes sao retiradas do saldo disponivel (proporcional ao valor devolvido). Se parte ja foi gasta, o
   saldo nao fica negativo: o excedente vira **divida** registrada no extrato.
4. **Divida.** Enquanto houver divida, novos gastos pagos ficam bloqueados (leitura de campanhas continua gratis). Uma nova compra quita a divida primeiro.
   Em caso de erro nosso, podemos perdoar a divida manualmente (ajuste auditado).
5. **Disputas (chargeback).** Abrir disputa tem o mesmo efeito de reembolso; se a disputa for **ganha**, o credito retirado volta. Contate o suporte antes de abrir disputa: e mais rapido.
6. **Falhas nossas.** Cobranca duplicada, compra sem credito ou servico pago que falhou: corrigimos creditando ou reembolsando, sem custo.
7. **Beta.** Estilhas do beta: `<regra se o servico encerrar>`. Prazo de resposta do suporte: `<ex.: 2 dias uteis>`.
8. **Historico.** O extrato e imutavel; correcoes entram como lancamentos compensatorios.
