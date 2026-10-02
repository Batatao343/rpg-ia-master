# SPEC — Normalização de excesso de beats do provider

> **Status:** `done`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A1 DeepSeek `20260820-180632-012432`
> **Depende de:** `matriz-a-capacidade-provider`

## 1. Contexto & objetivo

No segundo turno da primeira campanha A1, o DeepSeek devolveu seis beats
semanticamente válidos para uma solicitação de três a cinco. O limite
`max_length=5` no schema Pydantic rejeitou toda a resposta antes que o motor
pudesse normalizá-la, encerrando corretamente o experimento LLM-only por meio
do fail-closed.

O contrato de produto continua sendo de três a cinco beats. Como o excesso é
recuperável sem inventar conteúdo, a borda deve aceitar a resposta e preservar,
em ordem, somente os cinco primeiros beats não vazios. Respostas com menos de
três beats válidos continuam inválidas.

## 2. Requisitos

- **R1:** `CampaignPlanModel` aceita mais de cinco beats vindos do provider.
- **R2:** a normalização remove espaços e entradas vazias e retém, na ordem,
  no máximo os cinco primeiros beats válidos.
- **R3:** após a normalização, menos de três beats continua causando erro de
  validação; nenhum beat narrativo é fabricado pelo código.
- **R4:** `_build_plan` produz entre três e cinco `CampaignBeat` e preserva o
  grounding mecânico no local atual.
- **R5:** a mudança não altera prompts, rotas, custo nem fallback do produto.

### Fora de escopo

- Retry adicional para structured output.
- Preenchimento determinístico de beats ausentes.
- Alterações na cadência de replanejamento.

## 3. Design técnico

- **Alterado:** `agents/campaign_manager.py` — remove o teto declarativo que
  rejeita o payload antes da normalização e limita a saída do validator a cinco.
- **Alterado:** `tests/test_replan_grounding_regional.py` — cobre excesso,
  limpeza, ordem e mínimo obrigatório.

## 4. Plano passo a passo

1. Escrever regressões para seis beats, entradas vazias e menos de três válidos.
2. Implementar a normalização determinística na borda Pydantic.
3. Rodar testes focados e a suíte offline completa.
4. Reiniciar A1 desde o par 1 com o mesmo manifesto lógico.

## 5. Critérios de aceite

- [x] Seis beats válidos resultam nos cinco primeiros, na mesma ordem.
- [x] Espaços e entradas vazias são removidos antes do teto.
- [x] Menos de três beats válidos continua inválido.
- [x] `_build_plan` recebe o modelo normalizado sem acionar fallback.
- [x] `uv run pytest` verde.
- [x] A1 não voltou a falhar por `too_long` em 150 turnos e 21 replans.

## 6. Smoke test com LLM real

O próprio reinício da matriz A1 é o smoke real. O aceite desta spec exige que
nenhuma invocação termine pelo erro de excesso de beats observado no run de
origem.

## 7. Riscos & compatibilidade

- Saves antigos não mudam: o schema é apenas da resposta transitória do LLM.
- Payloads curtos seguem fail-closed; não há fallback narrativo novo.
- A truncagem é estável e não acrescenta chamadas, latência ou custo.
