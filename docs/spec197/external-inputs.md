# Itens externos que so o usuario pode fornecer (SPEC-197 / SPEC-198)

Nenhum segredo vai neste arquivo; entregar por canal seguro (dashboard/CLI/`.env.production` fora do git).

## Infra de producao (R1)
1. **Projeto Supabase de producao** em sa-east-1. A org Free ja tem 2 projetos ativos: pausar/excluir outro ou subir para **Pro**
   (necessario tambem para backups/PITR - R-03). Fornecer: aprovacao explicita para criar, ref do projeto, plano.
2. **Projeto Vercel de producao** (`rpg-ia-master`) em plano **Pro** (Hobby e nao comercial - R-06), dominio escolhido, token/escopo.
3. **Dominio** e DNS (app + e-mail transacional SPF/DKIM/DMARC).
4. Aprovar a role de banco de menor privilegio (R-05) e a lista de refs protegidos para `--confirm-prod`.

## Auth e e-mail (R4)
5. **SMTP customizado** (Resend, Postmark, SES, etc.): host, porta, usuario, senha/API key, remetente verificado. Ou aceite explicito de risco (R-02).
6. **Cloudflare Turnstile** real: site key e secret key para o dominio de producao (R-01).

## Pagamentos (R2, R9)
7. **Stripe live**: chaves live (`STRIPE_SECRET_KEY`), `STRIPE_WEBHOOK_SECRET` do endpoint de producao, SKUs/precos live aprovados.
8. **Valor explicito e aprovado** para o smoke live de valor pequeno (ex.: R$ `<...>`), SKU usado e aprovacao de estornar depois.
9. **Google Play (SPEC-198/Android; fora do beta web se adiado)**: conta Play Console, package id definitivo (`dev.rpgia.valoria`?), nome do app,
   service account JSON (`GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`), `GOOGLE_PLAY_PACKAGE_NAME`, chave HMAC `RPG_PLAY_ACCOUNT_KEY` (>=32 chars aleatorios, segredo; gerar uma vez e NAO rotacionar sem plano: muda os account ids ofuscados), licence testers, keystore de assinatura com **custodia definida** (backup offline, quem guarda) e
   confirmacao do tier de taxa do Google.

## Juridico (R3)
10. **Titular**: razao social/nome, CNPJ/CPF, endereco, encarregado (DPO).
11. **E-mail de suporte** real e dominio (`suporte@...`), prazo de resposta, canal de status.
12. Revisao juridica dos rascunhos de `legal/`, decisoes marcadas `<...>` (idade minima, prazo de retencao financeira, validade das Estilhas, foro) e **URLs publicadas** de privacidade/termos/reembolso/suporte.

## Orcamento e provedores (R7)
13. **Limites de gasto** (ver `runbooks/budget.md`): teto mensal por provedor (DeepSeek, Groq, OpenAI/STT/imagem, Jina), spend cap Supabase/Vercel, valores em R$/US$ e quem recebe os alertas (e-mail/telefone).
14. Chaves de producao de LLM/STT/imagem/embeddings separadas das de staging.
15. Valor de `RPG_DAILY_SPEND_CAP_BRL` (corte automatico diario ja implementado; vazio = desligado) e quem recebe os alertas.

## Operacao
16. Lista de convidados do beta (limite de usuarios) e 2 contas de teste para o smoke de isolamento.
17. Reautenticar `gh` (token invalido), push da branch, e approval do Environment `eval-governance`.
18. Assinatura dos aceites P2 em `risk-register.md` e aprovacao final humana para abrir o beta.
