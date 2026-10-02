# Android / Google Play v1

## Tecnologia

Capacitor 8 GA sobre React/Vite existente. Não migrar para React Native/Flutter.

- app técnico de staging pode usar package id separado (`*.dev`);
- package id de produção só é fixado na SPEC-198 antes do primeiro upload definitivo;
- `Valoria` é working name técnico, não decisão de branding/store listing.

## Compras

Créditos são consumíveis digitais. No app Google Play v1:

- Google Play Billing é o caminho de compra;
- servidor valida purchase token antes de creditar;
- compra é idempotente por purchase/order token;
- consumo/acknowledgement só ocorre no momento correto após entrega confiável;
- refund/revocation reconcilia o ledger;
- não confiar em payload/client para preço, SKU ou quantidade de Estilhas.

Não implementar alternate billing/Stripe link dentro do Android v1. Brasil permite programas alternativos, mas adicionam compliance/reporting e não são necessários para validar o produto.

## Provider abstraction

`PurchaseProvider = stripe_web | google_play` desde o início. iOS futuro adiciona `apple_store` sem alterar a wallet.

## Delimitação de conta Play

A SPEC-194 implementa purchase lifecycle, adapter e server verification boundary com fake/fixtures e código feature-gated. Ela não fica bloqueada pela ausência de Play Console. Package ID definitivo, products reais, license/internal testing e certificação em device entram somente na SPEC-198.
