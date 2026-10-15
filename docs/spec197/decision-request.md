# O que eu preciso de você (pt-BR, 15/10/2026)

Tudo que dava para fazer sozinho foi feito (corte automático de gasto, drill de restore com carteira, páginas legais,
drill de incidente/rollback, smoke de 2 usuários no staging). O resto depende de conta, dinheiro ou decisão sua.
Preços conferidos hoje nas páginas oficiais; confirme antes de pagar.

| # | Decisão / entrega | Custo | Minha recomendação |
|---|---|---|---|
| 1 | **Vercel Pro** para produção. O plano Hobby é só uso pessoal/não comercial (regra oficial) e, medido no staging, só deixa fazer rollback para o deploy imediatamente anterior (402). | US$ 20 por usuário/mês | Sim, Pro (1 assento). |
| 2 | **Projeto Supabase de produção** (sa-east-1). Free = 2 projetos ativos, pausa após 1 semana parado, **sem backup automático**. Pro = backup diário por 7 dias, spend cap ligado por padrão. | Pro: a partir de US$ 25/mês (PITR é extra: US$ 100/mês) | Pro, sem PITR no beta (backup diário + export nosso). Autorize a criação. |
| 3 | **SMTP próprio** (e-mails de confirmação/reset). O embutido do Supabase tem limite baixo. Resend grátis: 3.000 e-mails/mês, 100/dia, 3 domínios. | Grátis no beta (Pro US$ 20/mês se crescer) | Resend grátis + domínio com SPF/DKIM. Me passe a API key. Ou aceite o risco R-02 (só convidados). |
| 4 | **Cloudflare Turnstile** real (hoje usamos chave de teste que sempre passa). | Grátis (plano Free; confirme no painel) | Criar site+secret para o domínio de produção e me passar. |
| 5 | **Stripe**: chaves live, webhook secret, e (antes) chaves de TESTE no staging para eu rodar a compra de teste. Compra real de valor pequeno só com sua aprovação explícita. | Taxa Stripe sobre a compra; o valor é estornável | Passe as chaves de teste já. Smoke live: **R$ 5,00**, 1 SKU, estorno depois. Você confirma o valor. |
| 6 | **Dados jurídicos**: titular (nome/CNPJ/CPF, endereço), e-mail de suporte, domínio, prazo de resposta, idade mínima, retenção, foro, revisão por advogado. As 4 páginas já existem em /privacidade /termos /reembolso /suporte com banner RASCUNHO. | Advogado: variável | Preencha os `<...>` e revise; eu publico e tiro o banner. |
| 7 | **Domínio** + DNS. | ~R$ 40-80/ano | Registrar um domínio próprio. |
| 8 | **Tetos de gasto**: limites nos dashboards (DeepSeek, Groq, OpenAI, Jina) e o valor de `RPG_DAILY_SPEND_CAP_BRL` (ex.: R$ 30/dia no beta). Sem o valor, o corte automático fica desligado. Também: quem recebe os alertas. | O teto que você escolher | Cap diário R$ 30 + recarga manual pequena nos provedores. |
| 9 | **Chaves de produção** de LLM/voz/imagem (separadas das de staging) e, se quiser testar voz/imagem paga, autorização de gasto de teste. | Centavos a poucos reais | Chaves novas só para produção. |
| 10 | **Reautenticar CI**: o CI do HEAD está vermelho (índice do Project Index desatualizado — eu corrijo no próximo commit) e falta o approval `eval-governance`. | Grátis | Autorize eu commitar/pushar o lote da SPEC-197 e aprovar o Environment. |
| 11 | **Aceite dos riscos P2** (R-15 a R-28, em `risk-register.md`): assinar nome/data. | Grátis | Leia a lista; são tolerâncias conhecidas, todas com mitigação. |
| 12 | **Lista de convidados** do beta (limite de usuários) e 2 contas de teste. | Grátis | Até 10-20 pessoas no início. |
| 13 | **Go / no-go final** para abrir o beta. | — | Só depois de 1-12 e do checklist `--strict` verde em produção. |

Resumo de custo mensal recorrente mínimo: Vercel Pro US$ 20 + Supabase Pro US$ 25 = **~US$ 45/mês** (+ LLM/voz/imagem pelo uso, limitado pelo cap).
