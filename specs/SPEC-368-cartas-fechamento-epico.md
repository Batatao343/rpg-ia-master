# SPEC-368 — Cartas: fechamento do épico (bug do rollback, conteúdo faltante, métricas nunca medidas e smoke dos §6 não verificados)

> **Status:** `approved` (coordenador, autorização do dono 02/11 "manda bala" e "corrija tudo e garanta que está tudo correto")
> **Criada:** 2026-11-02 · **Atualizada:** 2026-11-02
> **Depende de:** SPEC-364 `done`; SPEC-367 (achados do smoke final) pode correr em paralelo — arquivos disjuntos exceto `agents/combat.py` (rebase)
> **Desbloqueia:** fechar como `done` as specs 327–333, 335, 336, 345–347, 352, 355 e 357 do épico de cartas

---

## 1. Contexto & Objetivo

O épico de cartas (327–364) está na `main` e `on` no staging desde 02/11. A auditoria de fechamento de 02/11
(coordenador, só leitura, contra §5/§6 de cada spec, revisões em `handoffs/` e os smokes
`docs/spec363/achados-smoke3.md`, `docs/spec364/achados-smoke4.md`, `docs/spec364/smoke-final.md`) fechou
334/342/353/354/362/363/364 e deixou 15 specs abertas por quatro motivos:

1. **Um bug ainda aberto** — R-4 da revisão da 328 (`handoffs/SPEC-328-sol-review.md:63`): o rollback
   `RPG_CARD_DECK` `on → off` só roda dentro do nó de combate (`agents/combat.py:2184`,
   `services/card_piles.py:122` `deactivate_deck`). Fora de combate, com a flag já `off`, `api._cards_block`
   (`api.py:~2550`) e `set_prepared` ainda veem as Preparadas derivadas do baralho até o próximo conflito.
   (R-1, R-2, R-3 e R-5 da mesma revisão foram conferidos corrigidos em 02/11: `apply_pact` debita Entropia,
   `undo_pact` desfaz só o delta, recusa não rerrola o Presságio em `agents/combat.py:2916`.)
2. **Conteúdo faltante declarado nas próprias specs** — 332: 4 facções do bestiário sem baralho
   (`tribos_devoradores_sol`, `bandos_nomades`, `colmeia_hospedeiros`, `mercadores_escravos_pradaria`);
   333: "Dor Surda" sem a opção "1 Fôlego para descartar" e `essencia_de_cinza` sem fonte de drop;
   330 D-13: escolha do descartar na UI, `_bump` (335) e Fardo por evento do Abismo.
3. **Métricas de aceite nunca medidas** — 327 §6 (≥ 2 Cartas por rodada, ≥ 60 % das rodadas com ≥ 3 escolhas,
   uso > 60 %, p95 ≤ 10 rodadas), 331 (p95 ≤ 10 rodadas), 329 ("arena `on`: dano recebido cai" — só `shadow`
   medido), 355 item 19 (319 P2-1, `replace` do stream medido).
4. **Itens de §6 que nenhum smoke real viu** — listados no §6 desta spec.

Objetivo: corrigir 1 e 2 com TDD, medir 3 de forma determinística (arena/bot, sem LLM), executar 4 num smoke real
único e roteirizado, e então fechar as 15 specs com evidência. Princípio: **mecânica é Python, não LLM**; a medição
é do motor; o smoke real só confirma o que o motor já prova.

## 2. Requisitos

### A. Rollback `on → off` fora de combate (328 R-4)

- **R1** — Com `RPG_CARD_DECK=off`, todo ponto que lê Preparadas fora de combate (`api._cards_block`,
  `set_prepared`, carregamento de save) vê as Preparadas de antes do baralho (`prepared_cards_pre_deck`), nunca as
  derivadas do baralho. Implementação idempotente: `deactivate_deck` chamado no load do save e no `_cards_block`
  quando `mode() == "off"` e o jogador ainda tem marca de baralho ativo.
- **R2** — `off → on → off` fora de combate é round-trip exato das Preparadas (save/load incluído).
- **R3** — Com `on`, nada muda (teste de não-regressão do caminho `on`).

### B. Conteúdo faltante (332, 333, 330 D-13)

- **R4** — As 4 facções sem baralho ganham baralho próprio em `data/cards/` no formato dos baralhos de facção
  existentes, cada uma com ≥ 1 Carta que nenhuma outra família/facção tem, passando `card_lint`, orçamento
  (`fx.budget_error is None`) e a gramática da 330. Voz das Cartas: aprovação em bloco do dono de 27/10
  (memória `cartas-autorizacao-dono`). Tema de cada facção a partir do Codex/bestiário (Grep, nunca Read inteiro).
- **R5** — Critério da 332 "cada família e facção com ≥ 1 Carta exclusiva" vira teste sobre o catálogo real
  (11 famílias, 14 facções), sem lista de exceção.
- **R6** — "Dor Surda" ganha a jogada "1 Fôlego para descartar" (contrato aditivo na view da mão; botão na UI do
  combate; sem LLM). Fôlego insuficiente → recusa explicada sem gasto.
- **R7** — `essencia_de_cinza` ganha ≥ 1 fonte de drop determinística (tabela de espólio existente), coberta por
  teste de que é obtível.
- **R8** — 330 D-13: (a) escolha do descartar na UI (o mesmo mecanismo do R6, generalizado para efeitos que pedem
  descarte); (b) `_bump` da 335 — confirmar no source; se já resolvido, registrar com arquivo:linha, senão corrigir;
  (c) Fardo por evento do Abismo — confirmar se algum evento do Abismo deve gerar Fardo pela 330; implementar se a
  spec prometeu, ou registrar a decisão de não fazer com motivo.

### C. Métricas medidas (327, 329, 331, 355)

- **R9** — Script determinístico `docs/spec368/metricas_epico.py` (sobre o bot/arena existentes; sem tocar em
  `scripts/cards/sim.py`, `docs/spec3*/arena_*.py`, orçamento nem golden — integridade de eval) mede nas sementes
  0–19 com cartas `on`: Cartas jogadas por rodada (média e p50), % de rodadas com ≥ 3 escolhas válidas, % de
  Cartas da mão usadas, p95 de rodadas por conflito, por Postura e total. Saída em
  `docs/spec368/metricas-0-19.json`.
- **R10** — 329: dano recebido pelo herói por conflito `on` (Presságio visível) vs `off`, mesmas sementes; registrar
  Δ. Se `on` não reduzir, registrar o número e abrir follow-up (não ajustar balanço nesta spec).
- **R11** — 355 item 19: medir o `replace` do stream (319 P2-1) com o harness de latência existente e registrar.
- **R12** — Os números do R9–R11 vão para o §9 das specs 327/329/331/355 como evidência; meta não atingida →
  registrar o número e o follow-up, sem mudar o critério (o critério é do dono).

### D. Smoke real dos §6 não verificados

- **R13** — Fixtures de cenário determinístico (estado montado, sem LLM) que colocam o jogo em cada situação do §6
  abaixo, reutilizáveis pelo smoke (`tests/fixtures/spec368_scenarios.py`) e testadas offline.

### Fora de escopo

- Balanço (Arcanista/Sangromante/`bomba_estopim`) — follow-ups próprios.
- Achados A1–A7 do smoke final → SPEC-367.
- SPEC-359/360/361 (bestiário/criaturas) — outra sessão.

## 3. Design técnico

- **Alterados:** `services/card_piles.py` (rollback idempotente exposto p/ API), `api.py` (`_cards_block`, load),
  `persistence.py` só se o load for o ponto certo (confirmar na Etapa 0), `data/cards/<faccao>.json` ×4 (ou o
  diretório onde vivem os baralhos de facção — confirmar), `data/cards/status_e_maldicoes.json` (Dor Surda),
  tabela de espólio de `essencia_de_cinza`, view da mão + `web/src/combat/*` (botão "Descartar (1 Fôlego)").
- **Novos:** `docs/spec368/metricas_epico.py`, `docs/spec368/metricas-0-19.json`,
  `tests/fixtures/spec368_scenarios.py`, `tests/test_spec368_*.py`, `docs/spec368/smoke-final.md` (coordenador).
- **Contrato:** aditivo; `web/e2e/contracts` e golden da 330 intocados; nenhuma flag nova.

## 4. Plano passo a passo

### Etapa 0 — Confirmação (sem código de produto)
Confirmar no source e anotar no §9: pontos de leitura de Preparadas fora de combate; onde vivem os baralhos de
facção; estado de `_bump` e do Fardo por evento do Abismo; harness de latência do R11.

### Etapa 1 — Rollback (R1–R3)
Testes primeiro: `test_off_outside_combat_restores_pre_deck`, `test_round_trip_off_on_off_with_save`,
`test_on_path_unchanged`.

### Etapa 2 — Conteúdo (R4–R8)
Testes primeiro: `test_every_family_and_faction_has_exclusive_card`, `test_new_faction_decks_lint_and_budget`,
`test_dor_surda_discard_costs_one_folego`, `test_dor_surda_discard_refused_without_folego`,
`test_essencia_de_cinza_obtainable`. Depois Cartas e UI (node test do botão).

### Etapa 3 — Métricas (R9–R12)
Script + JSON; teste que o script roda em 2 sementes e produz o schema esperado.

### Etapa 4 — Cenários (R13)
Uma fixture por item do §6; teste offline de cada uma (estado chega à situação pedida).

## 5. Critérios de aceite

- [ ] Etapa 0 anotada em §9
- [ ] R1–R3 com testes verdes, incluindo save/load
- [ ] R4–R8 com testes verdes; lint e orçamento limpos; voz conferida pelo revisor
- [ ] R9–R12: JSON gerado e números registrados nas specs 327/329/331/355
- [ ] R13: fixtures testadas offline
- [ ] 0 LLM por rodada; golden da 330 sem diff; `web/e2e/contracts` sem diff; sem flag nova; saves antigos carregam
- [ ] Guard de FallbackLLM mantido; nenhum `with_structured_output` novo
- [ ] `uv run pytest` verde (suíte completa, coordenador, no pouso); `npm run typecheck`, `typecheck:e2e`, `lint`, `test` verdes; `ruff format --check .` limpo
- [ ] Revisão independente `Sol` sem achado aberto
- [ ] **Smoke real §6 (coordenador)** registrado em `docs/spec368/smoke-final.md`

## 6. Smoke test com LLM real (coordenador; usar as fixtures do R13 para chegar a cada cena)

Local `legacy` com o preset do staging (cartas `on`) salvo onde indicado. Registrar provider/modelo/custo.

1. **328 §6.2** — Pacto do Abismo: emprestar Fôlego debita Entropia e soma Carga 1×/rodada; recusa não rerrola o
   Presságio. **R1–R3** ao vivo: desligar `RPG_CARD_DECK` fora de combate e ver as Preparadas antigas.
2. **329 §6.2/§6.3** — família estudada mostra faixa e nome; presságio frustrado.
3. **330 §6** — combo Eco; Rachadura + golpe com número igual ao texto.
4. **331 §6.2** — escolta com `proteger`.
5. **332 §6** — assinatura da Legião, padrão visível, troca de fase do chefe; 1 combate com facção nova do R4.
6. **333 §6.1/§6.3** — espólio da Mão Sombria com Carta da facção; descanso longo para Esquecer; Dor Surda
   descartada por 1 Fôlego (R6).
7. **335 §6** — 1 conflito com Corruptor e 1 com Médico.
8. **336 §6** — `draft.py` com chave real → lint → sim → promover → jogar (1 Carta; custo registrado).
9. **345 §6.1** — modo `off` no staging (deploy com cartas `off` só para este item, depois volta `on`) — ou local
   com o preset `off`, registrando a escolha.
10. **346 §6.5/§6.6/§6.7** — router esgotado (provider forçado a falhar), CLASSIFY só no Groq, rodada `off`; morte
    real vista ao vivo.
11. **347 §6.5 / 352 §6.1/§6.4/§6.5** — importar imagem pelo script; "Agora não" sem cotação e sem request; chefe
    `unico:{game}` isolado entre duas contas; duas confirmações concorrentes (só uma cobra). Custo do provedor da
    imagem registrado. `image_generation` ligado só durante o item e desligado no fim (conferir com `list`).
12. **354** — toast a 1440 no instante da vitória.
13. **355 §6** — Voto em Ketil, Leitura de Pressão, Armadura Comprometida, Renegado, vitória com Reação.
14. **357 §6.5** — quest de lore `justa` entregando técnica.

## 7. Riscos & compatibilidade

- Saves: R1 é idempotente e só restaura um campo já existente (`prepared_cards_pre_deck`); saves sem baralho não mudam.
- Integridade de eval: R9 é ferramenta nova em `docs/spec368/`; avaliadores, orçamento, golden e arenas antigas ficam intocados.
- Custo: smoke ~40 turnos + 1 Carta por `draft.py` + 1–2 imagens; dentro do teto diário (R$ 5) se feito em 1 dia — senão em 2.

## 8. Decisões

- **D-368-1 (coordenador):** métricas que não atingirem a meta são registradas com número e follow-up; o critério
  numérico não muda sem o dono.
- **D-368-2 (coordenador):** o item 9 do §6 pode rodar local com preset `off` em vez de um deploy `off` no staging.

## 9. Registro de implementação
