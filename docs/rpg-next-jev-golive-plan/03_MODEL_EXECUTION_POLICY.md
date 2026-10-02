# Política de execução por modelo — v5

A política deste pacote não é “use o menor modelo suficiente” em abstrato. A análise do repo já escolheu **um executor exato por spec**. O harness deve obedecer `examples/spec-model-contract.yaml` e `11_HARNESS_MODEL_CONTRACT.md`.

Princípio econômico: Luna faz trabalho mecânico; Terra implementa escopo bounded quando o contrato já está fechado; Sol assume cross-domain, segurança, concorrência, provider/billing e decisões de rollout; Astra revisa somente as duas trust boundaries em que um erro pode criar/destruir dinheiro de modo sistêmico.

## Luna

Nunca é executor principal deste pacote. Pode ser delegada somente para inventário, logs, hashes, agregação, checklists e relatórios autorizados na matriz. Não decide arquitetura nem edita trust boundaries.

## Terra

Executor exato de: SPEC-177, 178, 183, 185, 187, 191, 193, 196, 197 e 198.

Essas tarefas são bounded quando seus contratos estão fechados: adapter HTTP isolado, runner experimental já governado, pricing aritmético com property tests, UI/read models, frontend de voz, provisioning/runbooks, shell Capacitor, FinOps e release mechanics. Reviews Sol permanecem obrigatórios onde há ownership/security/release.

## Sol

Executor exato de: SPEC-176, 179, 180, 181, 182, 184, 186, 188, 189, 190, 192, 194 e 195.

Motivo: essas specs mexem em evaluator governance, decisões dinâmicas de routing, auth/runtime hosted, metering cross-provider, concorrência/ledger, STT+wallet, efeitos externos pagos, webhooks, lifecycle de conta, worker topology, purchase verification e reconciliação.

## Astra

Somente reviewer obrigatório em:

- SPEC-184 — wallet/ledger/reserva/settlement e conservação financeira;
- SPEC-195 — refunds/revocations/debt/reconciliation cross-channel.

Não usar Astra em implementação ou em outras specs por padrão. Se Sol encontrar uma ambiguidade arquitetural fora dessas duas, parar e pedir aprovação antes de escalar.

## Revisores Sol

Reviews são contextos independentes e recebem um pacote bounded (`spec + diff + gates + source necessário`), não o repositório inteiro sem necessidade. Isso mantém qualidade alta e custo controlado.

## Proibição de substituição silenciosa

- Terra prescrito não pode virar Sol “porque está disponível”.
- Sol prescrito não pode virar Terra para economizar.
- Astra não pode ser simulado por Sol.
- Mesmo modelo em executor/reviewer exige contextos independentes.

Se o harness não consegue selecionar/verificar o modelo exato: `MODEL_HANDOFF_REQUIRED` e parar.
