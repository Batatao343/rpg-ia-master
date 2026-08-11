# SPEC — Fonte única de Vitalidade, Ferimentos e terminal de conflito

> **Status:** `done` (2026-08-02)
> **Criada:** 2026-07-25 · **Atualizada:** 2026-08-02
> **Depende de:** `conflito-01`, `conflito-05`, `conflito-07` e
> `conflito-13` (cutover offline)
> **Desbloqueia:** smoke real confiável do motor v4 e
> `hardening-playtest-observabilidade`

---

## 1. Contexto & Objetivo

O smoke real `20260725-101933` revelou dois defeitos de domínio acoplados. Golpes
repetidos no mesmo Crítico removem e recriam o mesmo Ferimento, sem ocupar o
último espaço crítico; em paralelo, `hp` e `vitalidade` continuam recebendo
escritas independentes em criação, descanso, progressão, hazards, party,
persistência, API e frontend. Um ator pode aparecer morto numa camada e vivo em
outra.

Esta spec torna Vitalidade/Ferimentos a única fonte mecânica, mantém HP apenas
como alias derivado nas bordas durante a compatibilidade, e garante que todo
conflito termine em número limitado de golpes mesmo quando a região se repete.

## 2. Requisitos

- **R1 — Fonte única.** Apenas `vitalidade`, `max_vitalidade`, Ferimentos,
  `dead`, `death_pending` e `game_over` controlam vida/morte. `hp/max_hp`, quando
  expostos, são derivados e iguais à Vitalidade; nunca conduzem fluxo.
- **R2 — Migração v5.** Saves v4 preservam Vitalidade como autoridade e têm os
  aliases normalizados; saves pré-v4 continuam seguindo a política de arquivo.
- **R3 — Crítico progride.** Se uma região já tem Ferimento Crítico, novo
  Ferimento nessa região preserva o existente e ocupa outro espaço Crítico,
  sem ultrapassar a capacidade.
- **R4 — Região mecânica.** Ataque não direcionado escolhe região anatômica
  válida por RNG injetável/reprodutível; ataque direcionado valida a região e
  aplica sua penalidade. DoT e ataque de oportunidade não fixam `torso`.
- **R5 — Terminal completo.** Preencher o último espaço Crítico executa a
  Última Ação exatamente uma vez e só então Estado Terminal/estabilização,
  morte ou Cicatriz. Uma primeira estabilização falha continua pendente e recebe
  a segunda tentativa na rodada seguinte; um terminal não age nem foge.
- **R5b — Pós-Última Ação finito.** Sobreviver à Última Ação não concede
  imunidade. Com os Críticos ainda cheios, o próximo dano efetivamente sofrido
  mata/derruba pelo fluxo canônico sem redisparar a Última Ação; ausência de
  novo dano não mata por mera passagem de rodada.
- **R6 — Recuperação e hazards.** Descanso, item, armadilha, clima, Caldeira,
  condições e recuperação pós-combate usam o pipeline de Vitalidade/Ferimentos;
  descanso trata Ferimentos/Integridade e reseta Cartas conforme as specs.
  Qualquer hazard que preencher o último Crítico dispara o mesmo fluxo de Última
  Ação/terminal ou `death_pending`, mesmo fora de uma rodada de conflito.
- **R7 — Bordas.** API/CLI/HUD/party/playtest usam Vitalidade. A UI abre escolha
  em `death_pending` e memorial/bloqueio somente em `game_over`; Vitalidade zero
  por si só não é morte.
- **R8 — Persistência de Cicatriz.** Redução permanente de Vitalidade máxima
  sobrevive a recálculo por Corpo, level-up e save/load.

### Fora de escopo

- Rebalancear toda a curva de dano do jogo.
- Remover imediatamente os campos HP do contrato público; eles ficam como
  aliases de compatibilidade.
- Alterar a política já decidida de checkpoints/memorial.

## 3. Design técnico

- `gamedata.py` expõe `sync_vitality(actor)` e `sync_legacy_hp_aliases(actor)`.
  A fórmula de máximo inclui Corpo e `vitalidade_max_penalty`; HP é escrito
  apenas pelo helper de alias.
- `persistence.py` sobe para schema 5 e executa migração v4→v5 idempotente.
- `services/conflict_damage.py` ganha `select_hit_region(...)`; a combinação de
  Ferimentos distingue agravamento comum de trauma adicional sobre Crítico.
- `services/conflict_orchestrator.py` registra progressão mecânica e executa
  Última Ação uma vez antes do terminal.
- `world_utils.py`, `progression.py`, `party.py`, `combat_mechanics.py` e
  `agents/combat.py` deixam de tratar HP como estado mecânico.
- `api.py`, tipos/componentes React e playtest exibem Vitalidade e os estados
  terminais canônicos.

## 4. Plano passo a passo

### Etapa 1 — Contrato e migração

1. **Testes:** criação, descanso, level-up, Corpo, Cicatriz e save v4→v5
   preservam uma única vida canônica.
2. **Implementação:** helpers centrais, migration e adaptadores de borda.
3. **Verificação:** testes de persistência/progressão/estado.

### Etapa 2 — Ferimentos e terminal

1. **Testes:** Corpo 3/capacidade 2, Vitalidade zero e Críticos repetidos na
   mesma região encerram em rodadas limitadas; sem overflow; simetria entre
   jogador/inimigo; Última Ação ocorre exatamente uma vez; primeira falha de
   estabilização produz uma segunda tentativa na rodada seguinte; terminal não
   foge; sobrevivente recebe novo dano e morre sem nova Última Ação.
2. **Implementação:** região, combinação e fluxo terminal.
3. **Verificação:** testes `test_conflito_dano`, `test_death_flow` e
   `test_conflito_orquestrador`.

### Etapa 3 — Consumidores

1. **Testes:** descanso/item/trap/hazard/party/API/UI não divergem; HP zero
   legado com Vitalidade positiva não abre memorial; armadilha que fecha o
   último Crítico não deixa o ator vivo sem `last_stand_pending`,
   `estado_terminal` ou `death_pending`.
2. **Implementação:** migrar callsites e UI.
3. **Verificação:** suíte Python focada + `npm.cmd run build`.

## 5. Critérios de aceite

- [x] Vitalidade é a única fonte mecânica; aliases HP nunca divergem.
- [x] Crítico repetido preenche capacidade e dispara terminal.
- [x] Última Ação é resolvida exatamente uma vez.
- [x] Estabilização falha progride até sucesso ou segunda falha; terminal não foge.
- [x] Sobrevivente não fica imortal nem morre sem dano novo.
- [x] Save v4→v5, checkpoints e party preservam o estado.
- [x] Descanso/hazards/Cicatriz operam no domínio v4.
- [x] Hazard que fecha capacidade Crítica alcança o fluxo terminal canônico.
- [x] UI distingue Vitalidade zero, `death_pending` e `game_over`.
- [x] Invariantes `vitality.consistency`, `wound.capacity` e
  `combat.no_progress` cobrem regressões.
- [x] `uv run pytest` e `npm.cmd run build` verdes.

## 6. Smoke test com LLM real

1. Perfil de combate recebe dano até Vitalidade zero e progride por Ferimentos.
2. Críticos repetidos não deixam o conflito preso; fuga/morte/vitória terminam.
3. API, relatório e save apresentam os mesmos valores canônicos.

**Evidência (2026-08-02):** matriz offline `20260802-154317-705789` e matriz
real composta de 13 perfis × 30 turnos concluíram sem divergência
HP↔Vitalidade, `combat.no_progress` ou violação terminal. Detalhes em
[`docs/smoke-correcoes-conflito-v4-2026-08-02.md`](../docs/smoke-correcoes-conflito-v4-2026-08-02.md).

## 7. Riscos & compatibilidade

- A escala Vitalidade 6–16 é menor que o HP legado 26–40; hazards legados devem
  ser convertidos por categoria, não copiados numericamente.
- Saves v4 já divergentes escolhem Vitalidade deliberadamente; HP não vence a
  reconciliação.
- A escolha de região usa RNG recebido pelo motor para manter replay por seed.
