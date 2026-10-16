# SPEC-222 — handoff de texto legal (política de privacidade)

**Por que um handoff:** os textos legais da SPEC-197 (`web/legal/*.md`, renderizados em
`/privacidade/` e `/termos/`) não são editados por agentes. O código da SPEC-222 já faz o
que está abaixo; falta o titular revisar e aplicar o texto em `web/legal/privacy-policy.md`
(e manter `docs/spec198/data-safety.md` idêntico, que já foi alinhado ao código).

Fonte técnica dos prazos: `docs/spec222/retencao.md` (gerado do código; teste
`tests/test_spec222_transparency.py`). Defaults de decisão usados (spec §8): D-A URLs
assinadas de 300 s no export; D-B prazos abaixo; D-C fontes self-hosted; D-D idade 18.

## §4 Operadores — substituições propostas

| Operador | Para que | Dados |
|---|---|---|
| OpenAI (GPT Image 2) | gerar retratos/cenas | descrição textual da aparência/cena e o retrato de referência do herói |
| OpenAI (`gpt-4o-mini-transcribe`, fallback de transcrição) | voz para texto | áudio (retenção do provedor) |
| Provedor de e-mail transacional (`<definir SMTP>`) | confirmação e recuperação de conta | e-mail |

Remover o placeholder "Provedor de imagem (`<...>`)". Manter Supabase, Vercel, DeepSeek/Groq
(LLM), Groq (STT primário), Jina, Cloudflare Turnstile, Stripe/Google Play.

**Fontes:** não há mais requisição ao Google Fonts — as fontes (SIL OFL) são servidas pelo
próprio app. Nenhuma linha nova é necessária; se desejar, acrescentar em §7: "O site não
carrega recursos de terceiros para exibição, exceto o desafio antibot da Cloudflare no
cadastro/login."

## §5 Retenção e exclusão — texto proposto

- Dados de jogo e conta: mantidos enquanto a conta existir. Apagar uma campanha apaga também
  as imagens geradas para ela (até o próximo ciclo de limpeza automática).
- **Exclusão de conta:** encerra sessões e apaga usuário, jogos, memória, crônica, jobs,
  arquivos, arte e o histórico técnico de uso. Permanecem, por obrigação contábil/fiscal,
  antifraude e defesa em disputas, **por 5 anos**, apenas registros financeiros vinculados a
  um identificador opaco (UUID), sem e-mail: extrato de créditos, reservas e débitos,
  pedidos de pagamento, estado de reconciliação e compras Google Play (sem o token de
  compra, que é anulado após o consumo; apenas número do pedido, produto e estado
  financeiro). Um registro mínimo de que a exclusão ocorreu (UUID e data) é mantido por 5 anos.
- **Exportação:** o app exporta seus dados (exige senha recente), incluindo o extrato
  financeiro e links temporários (5 minutos) para baixar suas imagens.
- **Metadados técnicos:** recibos de operações 90 dias; tarefas internas concluídas 30 dias;
  registro de consumo de IA 13 meses; avaliações financeiras agregadas 180 dias; limites de
  taxa até 24 h; logs da plataforma `<dias>` (sem conteúdo de jogo, sem e-mail/token).

## §9 Menores — texto proposto

"O serviço é destinado a maiores de 18 anos. O cadastro exige a declaração de idade mínima."

## Pendências que continuam com o titular

- Controlador, CNPJ/CPF, domínio e e-mail de suporte (`<...>` do topo); SMTP real; dias de
  retenção de logs da Vercel; termos de retenção/treino de cada provedor de IA.
- Espelhar a idade mínima 18 na listagem do Play (SPEC-198).
