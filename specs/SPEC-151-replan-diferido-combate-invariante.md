# SPEC — Replanejamento diferido durante combate

> **Status:** `done` ? aceite local e smoke real DeepSeek verdes em 2026-09-28.
> **Criada:** 2026-08-28 · **Atualizada:** 2026-09-17
> **Depende de:** `latencia-turno-caminho-critico-concorrente`, `replan-grounding-troca-regiao`
> **Desbloqueia:** matriz B sem falso positivo de grounding

---

## 1. Contexto & Objetivo

Na B `20260828-170359-458364`, turnos 22–26 em combate em Ophidia emitiram
`campaign.region_grounding`: o plano ainda apontava Brekmar. Isso é esperado
durante combate porque o manager evita uma chamada SMART que não pode afetar a
rota de conflito e mantém `needs_replan=True`. O invariante antigo não conhecia
esse protocolo.

O objetivo é tolerar somente a janela causal do diferimento, sem permitir que
um plano stale fique pendente depois que o combate acabou.

## 2. Requisitos

- **R1** — Plano stale + `needs_replan=True` é válido enquanto combate está ativo.
- **R2** — O turno que encerra combate recebe uma única janela de graça se o
  snapshot anterior estava em combate.
- **R3** — No turno não-combate seguinte, stale + pendente continua sendo erro.
- **R4** — Stale sem `needs_replan` continua sendo erro imediato.
- **R5** — Viagem entre regiões marca `needs_replan` no produtor, inclusive
  quando dispara encontro ou a narração falha. A janela de viagem exige a flag.

## 3. Design técnico

`playtest/invariants.py` aplica a janela causal. A revisão de 17/09 também
altera `agents/storyteller.py`: a flag faltava em caminhos de viagem, embora o
manager já consumisse o contrato. Testes modelam ativo, saída, viagem sem flag
e pendência órfã; os smokes do harness exercitam a viagem pelo grafo completo.
`tests/test_grounding_boundaries.py` cobre diretamente narração, encontro,
resposta estruturada inválida e exceção do provider, sem campanha longa.

## 4. Plano passo a passo

1. Reproduzir os três estados em teste curto.
2. Aplicar janela causal no invariante.
3. Rodar suíte completa e reiniciar a B.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

Sem nova mudança de mecânica: rodar as regressões de combate/viagem junto ao
corpus pré-matriz. Aceite técnico local e smoke dirigido são separados da
certificação global. Ver [adendo pré-matriz](SPEC-162-remediacao-local-contratos-pre-matriz.md).

- [x] Combate ativo não gera falso positivo.
- [x] Saída de combate recebe uma única janela.
- [x] Pendência órfã no turno seguinte falha.
- [x] Suíte completa offline verde.
- [x] Guard LLM: N/A; invariante puro.
- [x] Saves antigos: nenhum schema novo.
- [x] Smoke real dirigido de viagem/combate/replan valida integração; B integral é gate global separado.

## 6. Smoke real

Reiniciar a matriz B; os cinco turnos de Ophidia não podem reincidir.
Gate bloqueado por saldo DeepSeek, conforme
[fechamento local](../docs/fechamento-local-2026-09-17.md).

## 7. Riscos & compatibilidade

A tolerância exige simultaneamente `needs_replan` e causa observável. Não é uma
exceção genérica para qualquer plano stale.


## Fechamento real ? 2026-09-28

Viagem, combate e replans reais completaram sem recorr?ncia dos casos de Ophidia ou viola??o de replan.
Evid?ncia consolidada: [matriz B](../docs/playtest-matriz-b-2026-09-28.md), `20260927-214549-731406` e `20260928-084057-102826`. A matriz global incompleta permanece responsabilidade exclusiva da SPEC-128.
