# Politica de Privacidade - Valoria (RPG IA)

> **RASCUNHO - revisar com o titular (e assessoria juridica) antes de publicar.** Reflete a implementacao
> verificada em SPEC-186/187/188/190/191/195. Itens entre `<...>` precisam ser preenchidos.

**Controlador:** `<razao social / nome do titular>`, CNPJ/CPF `<...>`. **Contato / encarregado (DPO):** `suporte@<dominio-a-definir>`.
Ultima atualizacao: `<data>`.

## 1. Dados que tratamos
- **Conta:** e-mail e senha (a senha e tratada pelo Supabase Auth, nunca armazenada por nos em texto). Sessao via cookies
  (access/refresh/CSRF) estritamente necessarios.
- **Jogo:** personagens, campanhas, historico de turnos, memoria narrativa (texto e vetores), cronica, preferencias.
- **Texto digitado** nos turnos: enviado a provedores de IA para gerar a narracao (secao 4).
- **Voz:** o audio gravado e enviado para transcricao e e **apagado imediatamente apos o processamento**; nao e gravado
  em banco, log ou armazenamento, e a transcricao nao e retida pelo recibo da operacao (apenas o tipo e a marca
  `result_retained=false`). O texto transcrito passa a ser um turno normal do jogo.
- **Imagens:** retratos/cenas geradas por IA a partir de descricoes do jogo ficam em armazenamento privado do usuario;
  voce nao envia fotos pessoais.
- **Pagamentos:** pedidos, saldo de "Estilhas", extrato (entradas append-only), identificadores de compra e eventos de
  pagamento sanitizados. **Dados de cartao nunca passam por nos**: sao tratados pelo Stripe (web) ou pelo Google Play (Android).
- **Tecnicos:** logs de erro e metricas de uso/custo sem conteudo de jogo e sem e-mail/token; limites de taxa por IP e
  por e-mail normalizado (hash) com expiracao em ate 24 h.

## 2. Finalidades e bases legais (LGPD, art. 7)
Executar o contrato/servico (conta, jogo, creditos); legitimo interesse (seguranca, antifraude, prevencao de abuso,
controle de custos); obrigacao legal/regulatoria (registros fiscais e financeiros); consentimento quando aplicavel
(ex.: acesso ao microfone, concedido no navegador/dispositivo).

## 3. Onde ficam os dados
Banco e armazenamento: Supabase, regiao **sa-east-1 (Sao Paulo)**. Aplicacao: Vercel (regiao `gru1`, Sao Paulo, quando
disponivel). Provedores de IA e pagamento podem processar dados fora do Brasil (transferencia internacional com as
salvaguardas do art. 33 da LGPD).

## 4. Compartilhamento (operadores)
| Operador | Para que | Dados |
|---|---|---|
| Supabase | banco, autenticacao, armazenamento | conta, jogo, arquivos |
| Vercel | hospedagem da aplicacao | requisicoes, logs tecnicos |
| Provedores de LLM (`<DeepSeek, Groq, ...>` - confirmar lista final) | gerar narracao | texto do turno e contexto da campanha |
| Provedor de transcricao (`<Groq/OpenAI>`) | voz para texto | audio temporario |
| Provedor de imagem (`<...>`) | gerar arte | descricao textual da cena |
| Jina | embeddings da memoria | trechos de texto da campanha |
| Cloudflare Turnstile | antibot em cadastro/login | sinais do navegador e IP |
| Stripe / Google Play | pagamentos | dados de compra (cartao fica com eles) |
| Provedor de e-mail transacional (`<definir SMTP>`) | confirmacao e recuperacao de conta | e-mail |
Nao vendemos dados pessoais. Nao usamos o conteudo das suas campanhas para treinar modelos proprios; verifique os
termos de retencao/treinamento de cada provedor de IA antes de publicar (`<confirmar>`).

## 5. Retencao e exclusao
- Dados de jogo e conta: mantidos enquanto a conta existir.
- **Exclusao de conta** (no app, exige senha recente): encerra sessoes, apaga usuario, jogos, memoria, cronica, jobs,
  arquivos e arte. Permanecem apenas, por obrigacao financeira e antifraude, o **extrato de creditos e eventos de pagamento
  vinculados a um identificador opaco (UUID)**, sem e-mail, que nao autentica nem recria a conta. Prazo: `<definir, ex. 5 anos fiscais>`.
- **Exportacao:** o app permite exportar seus dados (exige senha recente).
- Buckets de limite de taxa expiram em ate 24 h; logs conforme a plataforma (`<dias>`).

## 6. Seus direitos (LGPD art. 18)
Confirmacao e acesso, correcao, anonimizacao/bloqueio/eliminacao, portabilidade, informacao sobre compartilhamento,
revogacao de consentimento e oposicao. Exercicio pelo app (exportar/excluir) ou por `suporte@<dominio-a-definir>`;
resposta em ate 15 dias. Reclamacao a ANPD: gov.br/anpd.

## 7. Cookies
Apenas cookies essenciais: sessao de acesso, refresh e token CSRF (`HttpOnly`/`Secure` onde aplicavel). Sem cookies de
publicidade ou analytics de terceiros. Armazenamento local do navegador guarda preferencias e acoes pendentes.

## 8. Seguranca
Isolamento por usuario no banco (RLS), segredos fora do codigo, CAPTCHA, limites de taxa, trilha append-only de
creditos. Nenhum sistema e totalmente seguro; incidentes relevantes serao comunicados conforme a LGPD.

## 9. Menores
O servico e destinado a maiores de `<18/13?>` anos. `<definir>`.

## 10. Alteracoes
Mudancas relevantes serao avisadas no app/e-mail antes de entrar em vigor.
