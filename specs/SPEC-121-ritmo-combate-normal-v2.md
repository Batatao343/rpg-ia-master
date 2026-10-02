# SPEC — Ritmo de combate do perfil normal v2

> **Status:** `done`
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** `chase-progresso-e-fuga`, `quests-retomada-conversao`, `pos-fuga-roteamento-origem`

## 1. Contexto & Objetivo

O perfil normal gastou 90/200 turnos em combate (45%). O objetivo é representar
um jogador curioso sem alterar dificuldade, dano ou frequência global do jogo.

## 2. Requisitos

- **R1** — Cooldown prudente após conflito aumenta para 20 ações não-combate.
- **R2** — Normal tenta fugir a partir do round 3, sem esperar round 4.
- **R3** — Descanso em perigo busca primeiro um destino adjacente mais seguro.
- **R4** — Longrun mock normal 200t fica em até 35% de combate sem perder as
  quatro rotas principais quando o mundo as oferece.

### Fora de escopo

Balancear encontros, inimigos, HP, dano ou outros perfis.

## 3. Design técnico

Somente `playtest/profiles.py`; o jogo de produção permanece inalterado.

## 4. Plano passo a passo

1. Testar cooldown, retirada e descanso seguro.
2. Ajustar a política normal.
3. Rodar 200t mock e comparar participação.

## 5. Critérios de aceite

- [x] Comportamento prudente é determinístico.
- [x] Participação mock ≤35%.
- [x] `uv run pytest` verde.

## 6. Smoke test com LLM real

Smoke real dirigido confirmou as três bordas: ataque explícito em COMBAT;
investigação cautelosa e descanso em STORY. Aceite de 200 turnos
`20260816-113051-596798`: combate 41/200 (20,5%), quatro rotas, zero violação.

## 8. Resultado

Cooldown de 20 ações, retirada desde o round 3 e descanso em vizinho mais
seguro foram implementados apenas no harness. Dano, budget e frequência de
encontro do produto não mudaram.

## 7. Riscos & compatibilidade

Sem impacto no jogador real; apenas qualidade/cobertura do agente de teste.
