# SPEC-205 — handoff EVAL_AUTHORING_REQUIRED

Jornadas frontend novas para `web/e2e/critical-journeys.yaml` (+ `critical-journeys.spec.ts`,
`evals/metrics-registry.yaml`, `evals/manifest.lock.json`). O executor NAO editou arquivos protegidos.

Jornadas sugeridas (a autoria deve travar seletores e metricas):
- carta com alvo: clicar `Jogar Carta <nome>` -> mira ("Mirando X: escolha um alvo") -> clicar `Alvo: <nome>`; 2 cliques, 1 request com `card_id`+`target_id`.
- carta sem alvo (suporte): 1 clique, `target_id` ausente.
- ataque basico no jogo real: botao `Ataque básico` (grupo "Manobras táticas"); 1 alvo = 1 clique; varios = mira.
- cancelar: Esc e clique fora, zero request, foco volta a carta.
- carta indisponivel: `aria-disabled`, motivo visivel ("Entropia insuficiente"), zero request.
- idempotencia: duplo clique no alvo => 1 request; retry reutiliza `action_id`.
- teclado puro: Enter na carta, setas entre alvos, Enter executa.
- HP/Entropia so mudam apos a resposta (stream atrasado).

Seletores novos: botao da carta tem nome acessivel `Jogar Carta <nome>, <custo> de Entropia, ...`;
chip de alvo `Alvo: <nome>, Vitalidade X de Y`; barra de mira `.aimbar`; detalhe `.card-detail`.

Impacto nas jornadas F existentes: F08 (`Jogar Carta` apos `/Aparar/`) segue verde porque, sem
`valid_targets` no payload (fixture de servidor antigo), a carta executa direto no 1o inimigo vivo
(degradacao documentada na spec). Se a fixture ganhar `valid_targets`, F08 passara a exigir o 2o gesto
(clicar o alvo) — ajustar na autoria.
