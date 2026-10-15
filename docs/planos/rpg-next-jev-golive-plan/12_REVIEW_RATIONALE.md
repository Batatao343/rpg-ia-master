# Revisão arquitetural v5 — por que cada bloco está delimitado assim

Esta revisão foi feita contra o source do `main` observado, não apenas contra as specs anteriores.

## SPEC-176 — Sol

O failure atual não é mecânico puro: precisa distinguir stale lock de drift semântico em dataset protegido, além de checkout-clean e Project Index stale. Isso cruza governança da régua e trust boundary do CI. Sol executa; Luna só coleta logs/hashes; review Sol independente + environment humano.

## SPEC-177–180 — Jev

- 177 é adapter HTTP bounded: Terra implementa, Sol revisa.
- 178 é harness experimental com metodologia já fechada: Terra implementa; Sol valida leakage/cherry-picking.
- 179 exige construir options canônicas/seguras a partir de cena e aliases: Sol.
- 180 decide rollout/fallback/confidence e inventaria callsites semanticamente: Sol.

O runner canônico permanece offline/MockLLM. Live benchmark não pode “furar” a governança para parecer comparável.

## SPEC-181 — Sol

`RuntimeConfig` atual tem semântica clara: `local` Supabase; `portable/hosted` OIDC+S3. Alterar `hosted` permissivamente criaria regressão arquitetural. A spec passa a criar contrato hosted-Supabase explícito e mexe em auth, pooler e fail-closed; por isso Sol.

## SPEC-182–184 — dinheiro antes de UI

- 182 captura uso real em uma cascata que hoje só tem attempt telemetry sem tokens e playtest estimado 1200/400: Sol.
- 183 é aritmética bounded com Decimal/property tests: Terra + review Sol.
- 184 é a fonte de verdade financeira concorrente: Sol + Astra.

O desenho inclui `spend_ceiling`; settlement normal não pode ultrapassar reserva.

## SPEC-185 — Terra

É read model/UI sobre estruturas já fechadas. A revisão encontrou que `presentation_history` mora no GameState e não tem `operation_id`; por isso o custo por mensagem é enrichment vindo de `app.turns/usage`, não mutação do save. Terra implementa; Sol revisa ownership.

## SPEC-186–187 — voz

STT cruza provider fallback, arquivo temporário, wallet e metering: Sol. A UI de gravação é state machine bounded e fica com Terra. O áudio nunca é ação automática.

## SPEC-188 — Sol

O repo já tem geração automática por triggers. A decisão comercial atual exige consentimento antes de qualquer imagem paga. A spec agora audita todos os caminhos até `ImageGenerator.generate`; triggers só podem oferecer/cue. Isso cruza worker, wallet e efeito externo incerto, então Sol.

## SPEC-189–190 — pagamentos e conta

Stripe webhook/fulfillment e lifecycle/delete/auth são trust boundaries server-side: Sol. Não há Astra aqui porque a conservação financeira central já é revisada na wallet e a reconciliação cross-channel terá Astra depois; isso economiza custo sem deixar o caminho sem review independente.

## SPEC-191–193 — cloud/app

Supabase staging é execução de runbook com gates claros: Terra + review Sol. A escolha de worker/topologia Vercel é cross-domain/beta/runtime: Sol. Capacitor é bounded, mas cookies/resume/native boundary exigem review Sol.

SPEC-192 também precisa reconciliar a SPEC-104 histórica, que preferia Railway sob evidência de agosto de 2026; não apagar a decisão antiga, apenas registrar supersession se os gates atuais provarem Vercel.

## SPEC-194–195 — Play/reconciliation

Play Billing verification/fulfillment é Sol. A spec técnica não exige Play Console; a certificação real fica na publicação. Refund/revocation/debt cross-channel pode criar/destruir valor ou bloquear conta incorretamente: Sol + Astra e policy humana antes do código irreversível.

## SPEC-196–198 — observabilidade/release

FinOps é cálculo/report bounded: Terra + Sol review. Closed beta/publicação são execução de evidence/checklist, mas têm Sol review + approval humano. Luna só agrega o evidence bundle; não decide readiness.

## Resultado da política

Astra aparece em apenas 2/23 specs. Terra executa 10/23. Sol executa 13/23. Luna não executa spec principal; absorve trabalho mecânico para reduzir tokens dos modelos mais caros. Reviews Sol são bounded ao diff/evidência para controlar custo.
