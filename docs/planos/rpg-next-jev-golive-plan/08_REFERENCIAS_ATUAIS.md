# Referências atuais para reverificar na execução

Consultadas em 28/09/2026. Preços/limites não são eternos: cada spec externa deve revalidar no dia.

## Vercel

- https://vercel.com/changelog/zero-config-fastapi-backends
- https://vercel.com/changelog/vercel-functions-can-now-run-up-to-30-minutes
- https://vercel.com/changelog/vercel-functions-can-now-be-up-to-5-gb-in-package-size
- https://vercel.com/blog/vercel-services-run-full-stack-on-vercel
- https://vercel.com/changelog/vercel-queues-now-in-public-beta
- https://vercel.com/templates/template/python-celery-starter

## Supabase

- https://supabase.com/docs/guides/deployment/going-into-prod
- https://supabase.com/docs/guides/database/connecting-to-postgres/serverless-drivers
- https://supabase.com/docs/guides/queues
- https://supabase.com/docs/guides/ai/going-to-prod

## Stripe Brasil

- https://stripe.com/br/pricing
- https://stripe.com/br/payments/checkout
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/api/idempotent_requests

A conta real/Balance Transaction vence tabelas estáticas na reconciliação.

## Google Play

- https://developer.android.com/google/play/billing
- https://support.google.com/googleplay/android-developer/answer/112622?hl=pt-BR
- https://support.google.com/googleplay/android-developer/answer/10632485?hl=pt-BR
- https://support.google.com/googleplay/answer/11174377?hl=pt-br

Em 28/09/2026, o Brasil ainda está no regime anterior ao rollout global de 2027; a taxa de 15% para o primeiro US$1M depende de inscrição/qualificação. Não hardcode.

## Capacitor

- https://capacitorjs.com/docs
- https://capacitorjs.com/docs/updating/8-0

Usar Capacitor 8 GA; não adotar major prerelease sem necessidade.

## Speech-to-text

- https://console.groq.com/docs/speech-to-text
- https://console.groq.com/docs/model/whisper-large-v3-turbo
- https://developers.openai.com/api/docs/pricing

Groq Whisper Turbo observado: US$0.04/h, multilíngue, 216x speed factor. OpenAI mini-transcribe observado: ~US$0.003/min. Revalidar antes de pricing production.


## Jev — verificar no dia

- https://jevmodel.org/docs/
- https://jevmodel.org/api/

Snapshot 02/10/2026: endpoint `POST /v1/systemone`; auth Bearer; env recomendada pela documentação `JEVMODEL_API_KEY`; tipos `choice`, `score`, `noul`; até 8 perguntas por request; Choice com 2–20 opções; `state` serializado até 8.000 caracteres; `Idempotency-Key` opcional e reutiliza cobrança em retry; response inclui `model` e `usage`. Revalidar modelo/preço/limites antes dos runs live.
