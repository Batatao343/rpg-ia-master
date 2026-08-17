# SPEC — Direção social e origem causal dos combates

> **Status:** `done`
> **Criada:** 2026-08-13 · **Atualizada:** 2026-08-13
> **Depende de:** `combate-lifecycle` (`done`), `npc-fallback-sem-alvo` (`done`)
> **Desbloqueia:** tuning causal do ritmo de campanhas

---

## 1. Contexto & Objetivo

Quando não há NPC em cena, o narrador deve oferecer direção concreta sem inventar
presença. Além disso, a taxa agregada de combate não distingue iniciativa do
jogador, encontro de viagem, ameaça regional ou pressão do arco.

## 2. Requisitos

- **R1** — Sem interlocutor, o storyteller recebe uma direção social canônica:
  NPC conhecido na cena ou destino adjacente real; nunca um beat privado.
- **R2** — Todo combate novo registra uma origem causal de vocabulário fechado:
  `player_provoked`, `travel_encounter`, `regional_danger`, `arc_pressure`,
  `pursuit_recurrence` ou `unknown`.
- **R3** — A origem persiste em `combat.origin`, sobrevive aos turnos do conflito
  e aparece na telemetria.
- **R4** — A implementação não cria NPC nem combate por LLM.

### Fora de escopo

- Alterar dificuldade, chance de encontro ou política de fallback.

## 3. Design técnico

- `services/social_direction.py`: constrói orientação a partir do estado visível.
- `services/combat_origin.py`: classifica e normaliza a causa.
- `agents/router.py`, `agents/storyteller.py`, `agents/combat.py`: transportam o
  hint e materializam `combat.origin`.
- Playtest agrega distribuição de origens.

## 4. Plano passo a passo

1. Criar testes dos serviços e da persistência da origem.
2. Integrar prompts/updates sem novo schema de LLM.
3. Registrar origem por turno e no summary.
4. Rodar suíte focada e completa.

## 5. Critérios de aceite

- [x] Direção social referencia somente entidades/locais conhecidos pelo estado.
- [x] Combates novos têm causa auditável e conflitos ativos a preservam.
- [x] Relatório distingue as origens.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Inspecionar o transcript de uma campanha real existente e, havendo cota, executar
um smoke curto para confirmar que a diretiva permanece natural.

Smoke MockLLM `20260813-001000-370465`: combate iniciado com origem
`player_provoked`, preservada por sete turnos; zero erro/violação.

## 7. Riscos & compatibilidade

Combates antigos ou criados fora dos caminhos principais recebem `unknown`, sem
quebrar saves. O campo é diagnóstico e não altera a resolução mecânica.
