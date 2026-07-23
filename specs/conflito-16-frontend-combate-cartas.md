# SPEC — Conflito v2 #16: Frontend — Interface Tática de Cartas

> **Status:** `draft`
> **Criada:** 2026-07-22 · **Atualizada:** 2026-07-22
> **Depende de:** `conflito-13-cutover-migracao-playtest` (`done` — motor precisa
> estar estável e validado antes de construir a UI em cima)
> **Desbloqueia:** nada (última spec do épico)
> **Épico:** Migração do Sistema de Conflitos de Valoria
> **Prioridade:** confirmada pelo usuário (2026-07-22) como a **menos
> prioritária** do épico — sequenciada por último, depois de todo o motor
> validado.

---

## 1. Contexto & Objetivo

O frontend atual (`web/src/`) representa combate como HP bar + chips de sugestão +
lista de condições (`Hud.tsx` `CombatTab`, `PlayScreen.tsx` chips de
`combat_suggestions`, `types.ts` `CombatBlock{active,round,order,enemies,
player_conditions,cooldowns,suggestions}`) — sem cartas, zonas ou reações
visuais. `docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md` descreve o
combate como "jogo tático de cartas" com interface própria.

Esta spec é a última do épico por decisão explícita do usuário: o motor
(specs 01-13) precisa estar validado em jogo real antes de investir na UI nova,
evitando retrabalho se o motor mudar durante o playtest de validação.

## 2. Requisitos

- **R1** — `types.ts`: `CombatBlock` reescrito pra refletir `ConflictScene`
  (`conflito-03`) + Cartas preparadas (`conflito-02`) + Vitalidade/Ferimentos
  localizados (`conflito-01`/`05`) + Cargas do Abismo visíveis (`conflito-01`
  R6) + informação revelada progressiva do inimigo (`conflito-08` R7-R9).
- **R2** — Mão de Cartas preparadas: componente novo mostrando as 4-7 Cartas do
  jogador, custo Entropia, frequência (disponível/gasta), Ruptura declarável.
- **R3** — Visualização de zonas: representação simplificada (não-grid, textual/
  cartão por zona conforme doc 01 §6) mostrando participantes por zona,
  distância/postura/ocultação/Engajamento.
- **R4** — Painel de Ferimentos localizados: substituindo a barra de HP simples
  por Vitalidade + espaços Leve/Grave/Crítico por região.
- **R5** — Prompt de Reação: interface de janela de reação (`conflito-06`) — o
  jogador precisa poder decidir usar/não usar reação dentro do tempo de resolução
  de uma ação inimiga.
- **R6** — Painel de inimigo com informação progressiva (`conflito-08` R7):
  campos públicos sempre visíveis, Cartas/resistências reveladas aparecem
  dinamicamente conforme usadas.
- **R7** — Tela de morte (`DeathModal.tsx`) estendida pra refletir Última Ação/
  Estado Terminal/estabilização (`conflito-07`) em vez do fluxo simplificado
  atual.
- **R8** — Fluxo de fuga/perseguição visual: trilha Pressionado/Afastado/Quase
  Livre/Escapou (`conflito-09`).

### Fora de escopo

Qualquer mudança de motor/backend (todas as specs 01-15 já fecharam isso);
retrabalho de telas não-relacionadas a combate (ficha fora de combate, mapa,
crônica — só tocar se a mudança de schema (Virtudes/Cartas) vazar pra lá, ex.
aba "Ficha" do `Hud.tsx` mostrando Virtudes em vez de atributos).

## 3. Design técnico

**Arquivos alterados:**
- `web/src/types.ts` — schema novo de `CombatBlock`/`ConflictScene`/`Carta`/
  `Wound`.
- `web/src/components/Hud.tsx` — aba "Ficha" mostra Virtudes (não mais 6
  atributos); aba "Combate" reescrita pra zonas/cartas/Ferimentos.
- `web/src/components/PlayScreen.tsx` — chips de sugestão viram mão de Cartas +
  manobras (Engajar/Guardar/Esconder-se/Procurar/Fugir).
- `web/src/components/DeathModal.tsx` — estados Última Ação/Terminal/
  estabilização.

**Arquivos novos:**
- `web/src/components/CardHand.tsx` — mão de Cartas preparadas.
- `web/src/components/SceneZones.tsx` — visualização de zonas/posições.
- `web/src/components/ReactionPrompt.tsx` — janela de reação.
- `web/src/components/WoundTrack.tsx` — Vitalidade + Ferimentos localizados.

## 4. Plano passo a passo

### Etapa 1 — `types.ts` + build verde
1. **Verificação:** `npm run build` verde com os novos tipos antes de tocar
   componentes visuais.

### Etapa 2 — Mão de Cartas
1. **Implementação:** `CardHand.tsx`.
2. **Verificação:** smoke Playwright (webapp-testing) — Carta aparece, custo/
   frequência corretos, Ruptura declarável.

### Etapa 3 — Zonas e Ferimentos
1. **Implementação:** `SceneZones.tsx` + `WoundTrack.tsx`.
2. **Verificação:** smoke Playwright.

### Etapa 4 — Reação + morte + perseguição
1. **Implementação:** `ReactionPrompt.tsx`, `DeathModal.tsx` estendido, trilha de
   perseguição.
2. **Verificação:** smoke Playwright cobrindo os 3 fluxos.

### Etapa 5 — Painel de inimigo progressivo
1. **Implementação:** revelação dinâmica de Cartas/resistências.
2. **Verificação:** smoke Playwright.

## 5. Critérios de aceite

- [ ] `npm run build` verde.
- [ ] Combate jogável ponta a ponta na UI nova (Cartas, zonas, reações,
  Ferimentos, morte, fuga) sem regressão de fluxo fora de combate.
- [ ] Smoke Playwright (skill `webapp-testing`) cobrindo os fluxos novos,
  incluindo mobile 390px (padrão já estabelecido no projeto).

## 6. Smoke test com LLM real

1. Campanha real ponta a ponta na UI nova: criação → combate completo (Carta,
   reação, Ferimento, fuga OU morte) → loot → retomada narrativa.

## 7. Riscos & compatibilidade

- Maior superfície de UI nova do projeto até hoje — considerar fatiar esta spec
  em sub-specs por etapa (04.1 Cartas, 04.2 Zonas, ...) se o escopo se mostrar
  grande demais numa sessão só, seguindo o padrão de fatiamento já usado em
  outras fases do projeto (ex. Fase 3/4/6).
- Depende inteiramente da API estabilizada pelo `conflito-13` — qualquer mudança
  de contrato depois desta spec começar gera retrabalho.
