# Valoria — próximo pacote: CI integrity + Jev + go-live comercial v5

Este pacote continua diretamente a trilha de eval/index já entregue no `main` `1beefc432cce5ded4e3468e42c5e583aa4431a44`.

No estado observado, **SPEC-163..SPEC-175 estão `done` e SPEC-176 é o próximo ID livre**. A **SPEC-176 corrige primeiro a divergência entre o workspace local e o checkout limpo do GitHub Actions**. Nenhum experimento Jev começa enquanto os gates atuais não estiverem verdes. Depois, SPEC-177..180 testam Jev como decision layer; só então começa billing/cloud/app.

A v5 também fixa o **modelo exato por spec**. O harness deve ler `11_HARNESS_MODEL_CONTRACT.md` e `examples/spec-model-contract.yaml`; não pode trocar Terra por Sol/Astra nem Sol por Terra silenciosamente.

## Gate zero: corrigir CI antes de Jev


O push `1beefc4` mostrou que a governança está funcionando: o CI rejeitou um hash stale de `narrative_npc.jsonl`, exigiu aprovação para paths protegidos e encontrou o Project Index stale. A SPEC-176 deve corrigir a causa em checkout limpo **sem relaxar nenhum gate**.

## Ajuste importante para o Jev

A eval canônica de routing é deliberadamente offline: `run_eval()` força `RPG_FORCE_MOCK=1`. Logo, Jev NÃO deve ser encaixado dentro do runner protegido nem exigir mudança do evaluator. O A/B live usa o mesmo dataset/oráculo em read-only através de um runner experimental separado em `evals/experiments/`.

A SPEC-175 também congelou outra decisão: Project Index fica disponível apenas para consultas seletivas; não faz parte do fluxo/contexto padrão.

## Ordem

`SPEC-176 -> SPEC-198`, estritamente em sequência. Não avançar enquanto a atual não estiver `done` com seus gates/review.

## Decisões de produto já aprovadas

- Brasil / BRL.
- Compra avulsa, sem assinatura.
- Moeda da conta: **Estilhas de Éter**; Ouro permanece economia do personagem.
- Sem créditos grátis.
- Jogadas normais debitam custo real silenciosamente; saldo e custo ficam auditáveis na conta/turno.
- Imagem é exceção: quote explícito + confirmação antes de gerar.
- Entrada por voz antes do go-live; transcript editável e nunca autoenviado.
- Web: Stripe Checkout. Android: Google Play Billing. Wallet única.
- No Android v1, sem link para Stripe/alternate billing dentro do app.
- iOS/App Store fora do v1.
- Vercel beta pode ser usado se staging provar o contrato.
- Beta inicial pequeno/orgânico; segurança não pode depender de “menos de 20 usuários”.
- Meta econômica: taxa do canal + custos variáveis mensuráveis + **5% de margem-alvo**, sem imposto nesta primeira modelagem.
- Cascata LLM atual permanece invisível e pode continuar completa; fallback entra no custo real.
- Se Jev for promovido, seu uso/custo entra no mesmo metering.
- Long-run segue manual/opt-in.

Leia primeiro `START_HERE_PROMPT.md`, `SPEC_EXECUTION_ORDER.md`, `10_JEV_DECISION_LAYER.md`, `01_ARQUITETURA_ALVO.md`, `02_BILLING_E_MARGIN.md` e `03_MODEL_EXECUTION_POLICY.md`.

## Revisão v5 — modelos exatos e critérios de fechamento

A v5 foi revisada contra o source atual, não apenas contra o plano anterior. Principais correções: executor/reviewer exatos por spec; harness fail-closed em model mismatch; SPEC-176 movida para Sol; hosted-Supabase preserva perfis OIDC/S3; metering/wallet recebem spend ceiling; custo por mensagem não entra em GameState; triggers automáticos de arte não podem gerar imagem paga; Play Billing técnico não depende de Play Console; release/publicação ganharam reviews Sol e approvals humanos explícitos.
