# Segurança e release

Desenvolvimento técnico não deve ser bloqueado por domínio/store assets, mas publicação real exige gates.

## Antes de beta externo pago

- email confirmation ou decisão documentada equivalente;
- password reset;
- CAPTCHA/antiabuse nos fluxos apropriados;
- account deletion completa, incluindo dados de jogo/privados e tratamento separado do ledger obrigatório;
- política de retenção de transações;
- Privacy Policy / Terms / refund policy / support contact;
- secrets somente server-side;
- RLS/advisors verdes;
- Stripe webhook signature verification;
- Google purchase server verification;
- spend limits e kill switches;
- backup/restore remoto testado;
- error budget/cost alerts.

## Nunca

- creditar wallet a partir de `success_url` do Stripe;
- creditar compra Google apenas porque o app disse que pagou;
- permitir saldo negativo;
- guardar Stripe secret/Google service credential/Supabase service role em Vite/Capacitor;
- logar áudio, prompts privados, cartões, purchase tokens completos ou signed URLs.
