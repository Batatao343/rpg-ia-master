# Ordem oficial — CI íntegro, Jev, go-live

Pré-condição no snapshot analisado `1beefc432cce5ded4e3468e42c5e583aa4431a44`: SPEC-163..175 `done`; SPEC-176 livre. Se o HEAD divergir ou 176 já estiver ocupado, o harness deve parar antes de importar e recalcular IDs.

A coluna **Executor** é exata, não “mínima”. O harness deve obedecer `11_HARNESS_MODEL_CONTRACT.md` e `examples/spec-model-contract.yaml`.

| Ordem | Spec | Executor | Effort | Review independente |
|---:|---|---|---|---|
| 1 | SPEC-176 — clean-checkout eval/CI integrity | **Sol** | High | **Sol High** + approval humano `eval-governance` quando aplicável |
| 2 | SPEC-177 — Jev decision backend adapter | **Terra** | High | **Sol High** |
| 3 | SPEC-178 — Jev router A/B live | **Terra** | High | **Sol High** |
| 4 | SPEC-179 — Jev target/loot dynamic eval | **Sol** | High | **Sol High** |
| 5 | SPEC-180 — Jev selective promotion | **Sol** | High | **Sol High** |
| 6 | SPEC-181 — hosted-Supabase runtime contract | **Sol** | High | **Sol High** |
| 7 | SPEC-182 — real usage metering | **Sol** | High | **Sol High** |
| 8 | SPEC-183 — Estilhas pricing/margin | **Terra** | High | **Sol High** |
| 9 | SPEC-184 — wallet ledger/reservations | **Sol** | High | **Astra High** |
| 10 | SPEC-185 — account dashboard/cost attribution | **Terra** | High | **Sol High** |
| 11 | SPEC-186 — STT routing + wallet/metering | **Sol** | High | **Sol High** |
| 12 | SPEC-187 — voice input web/mobile | **Terra** | High | none |
| 13 | SPEC-188 — paid image quotes | **Sol** | High | **Sol High** |
| 14 | SPEC-189 — Stripe Checkout/webhooks | **Sol** | High | **Sol High** |
| 15 | SPEC-190 — account lifecycle/abuse/security | **Sol** | High | **Sol High** |
| 16 | SPEC-191 — Supabase remote staging | **Terra** | High | **Sol High** |
| 17 | SPEC-192 — Vercel staging/worker topology | **Sol** | High | **Sol High** |
| 18 | SPEC-193 — Capacitor Android foundation | **Terra** | High | **Sol High** |
| 19 | SPEC-194 — Google Play Billing consumables | **Sol** | High | **Sol High** |
| 20 | SPEC-195 — cross-channel reconciliation/refunds | **Sol** | High | **Astra High** |
| 21 | SPEC-196 — FinOps/margin guard | **Terra** | High | **Sol High** |
| 22 | SPEC-197 — closed paid beta gate | **Terra** | High | **Sol High** + aprovação humana de abertura |
| 23 | SPEC-198 — Google Play publication | **Terra** | High | **Sol High** + aprovação humana final |

## Regra de avanço

Não iniciar a próxima spec enquanto a atual não estiver `done`, com gates e reviews exigidos. `review-pending`, `MODEL_HANDOFF_REQUIRED`, `EXTERNAL_ACTION_APPROVAL_REQUIRED`, `EVAL_AUTHORING_REQUIRED` ou `PRODUCT_POLICY_APPROVAL_REQUIRED` bloqueiam avanço.

## Gate zero — SPEC-176

Os vermelhos atuais não são score ruim de IA. Primeiro restaura-se integridade de lock/index/CI em checkout limpo. Jev fica totalmente fora do escopo até novo push verde.

## Jev — SPEC-177..180

- SPEC-177 integra sem mudar produção.
- SPEC-178 mede route real A/B fora do runner protegido.
- SPEC-179 congela antes da primeira chamada um corpus experimental de target/loot baseado em contratos do source, incluindo `>20 candidates`/segredo/out-of-scene.
- SPEC-180 decide `NO_GO | SHADOW | PRIMARY_WITH_FALLBACK` por regra pré-declarada e rollout reversível. Primary nunca é habilitado por “feeling”.

## Cloud/payments

SPEC-181..190 permanecem local/test-first. SPEC-191+ podem mutar recursos externos somente após approval explícito. Stripe live e compras/release reais permanecem gates posteriores.

## Long-run

Nenhuma spec deste pacote exige 100/200 turnos ou matriz 10×200. Long-run continua manual-only.
