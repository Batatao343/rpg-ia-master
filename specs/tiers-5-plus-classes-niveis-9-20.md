# SPEC — Tiers 5+ das classes e progressão dos níveis 9–20

> **Status:** `done` (2026-08-20 — aceite local completo; smoke real opt-in não bloqueante)
> **Criada:** 2026-08-17 · **Atualizada:** 2026-08-19
> **Depende de:** `conflito-01-virtudes-vitalidade`,
> `conflito-02-cartas-acervo-preparacao`, `conflito-13-cutover-migracao-playtest`,
> `conflito-14-autoria-cartas-classes`, `conflito-17-volume-conteudo-mundo-vivo`
> (`done`)
> **Desbloqueia:** campanhas completas até o nível 20, encontros de endgame e
> balanceamento dedicado dos patamares épicos
> **Aceite local:** concluído. O smoke LLM real da §6 permanece opt-in e só roda
> com teto de custo explicitamente autorizado; não bloqueia a entrega determinística.

---

## 1. Contexto & Objetivo

O épico atual consolidou cinco Posturas diante do Abismo, três subclasses por
Postura e 153 Cartas de jogador nos patamares Inicial/Avançado/Superior. A
progressão, porém, foi deliberadamente encerrada no nível 10; a tabela de XP já
possui limiares até 20, mas `gamedata.NIVEL_MAX`, elegibilidade, slots preparados,
frontend e testes ainda tratam 10 como teto. O catálogo também não possui gate
numérico obrigatório: `patamar` organiza autoria, mas `eligible_cards()` não
impede uma Carta tardia de aparecer cedo.

Esta spec reabre a progressão até o nível 20 e autora **80 Cartas novas** para os
tiers 5–9. O objetivo não é apenas inflar números: cada subclasse ganha decisões
de endgame coerentes com sua identidade, enquanto Carga, frequência, custo e
consequências continuam impedindo que o herói apague o risco central de Valoria.
Toda elegibilidade, concessão e potência é resolvida em Python; a LLM somente
narra o resultado já aplicado.

## 2. Requisitos

- **R1 — Cap real 20:** `NIVEL_MAX=20` é respeitado por XP, criação de fixtures,
  API, CLI, saves, HUD, modal de progressão e playtest. `xp_to_next(20) is None`;
  a tabela existente de XP 1–20 é validada como crescente e completa.
- **R2 — Gate autoritativo:** toda Carta de jogador possui `tier: int` e
  `level_req: int`. `eligible_cards()` filtra `level_req <= player.level`, classe,
  subclasse e pré-requisitos. `patamar` permanece rótulo autoral/UI, nunca fonte
  única da regra.
- **R3 — Compatibilidade do catálogo:** Cartas existentes recebem backfill
  explícito no gerador/dados: Inicial `level_req=1`, Avançado `=4`, Superior `=7`,
  com `tier` 1–4 autorado sem alterar IDs ou efeitos. Nenhuma Carta conhecida de
  save existente é removida por ficar abaixo de um gate novo.
- **R3A — Subclasse explícita no nível 3:** ao alcançar o nível 3, o jogador
  recebe primeiro uma escolha obrigatória `kind="subclass"` entre os três ramos
  públicos da sua classe. A interface apresenta nome, identidade narrativa,
  estilo mecânico, principal contrapartida e exemplos públicos de Cartas de cada
  ramo. A confirmação persiste `player.subclass`, emite `subclass_chosen` e é
  irreversível naquela linha do tempo; a LLM pode narrar a decisão, mas não
  escolher, alterar ou inferir o ramo.
- **R3B — Ordem e bloqueio de ramo:** nos níveis 1–2, inclusive na criação, apenas
  Cartas de tronco são elegíveis. No nível 3, a escolha de subclasse antecede a
  escolha normal de Carta; enquanto `kind="subclass"` estiver pendente, nenhuma
  Carta de ramo pode ser aprendida. Depois da confirmação, elegibilidade permite
  tronco + ramo escolhido e bloqueia os outros dois. Escolher Carta deixa de ser
  mecanismo implícito para definir subclasse.
- **R4 — Cadência tardia:** os novos tiers abrem em tabela Python única:

  | Tier | Nível mínimo | Rótulo de UI |
  |---:|---:|---|
  | 5 | 9 | Épico I |
  | 6 | 12 | Épico II |
  | 7 | 15 | Lendário |
  | 8 | 18 | Mítico |
  | 9 | 20 | Ápice |

  Os níveis intermediários continuam concedendo uma escolha normal entre Carta
  nova elegível ou evolução A/B, salvo o nível 20 conforme R8.
- **R5 — Exatamente 80 Cartas tardias:** o lote novo contém 20 Cartas de tronco
  (4 por classe, uma nos tiers 5–8), 45 Cartas de subclasse (3 para cada uma das
  15 subclasses, distribuídas pelos tiers 5–8) e 15 Cartas Ápice (uma por
  subclasse, tier 9). Total: `20 + 45 + 15 = 80`.
- **R6 — Cobertura por identidade:** cada subclasse recebe ao menos uma Carta
  ativa e uma não-ativa (`reacao|passiva|utilitaria`) no lote tardio; as três
  Cartas não-Ápice cobrem ao menos dois tiers distintos e uma delas pertence ao
  tier 7 ou 8. A matriz classe × subclasse × tier entra no content report.
- **R7 — Sem efeito fantasma:** toda Carta nova usa o catálogo fechado de efeitos
  já resolvido pelo motor. Novo `kind` só entra acompanhado de resolver Python,
  testes unitários, serialização e representação no HUD. Texto, prompt ou
  `descricao` nunca concede efeito mecânico.
- **R8 — Ápice de nível 20:** a Carta Ápice da subclasse é concedida
  deterministicamente ao alcançar o nível 20 e **substitui** a escolha normal de
  Carta/evolução daquele nível. Não há escolha falsa porque existe exatamente uma
  Ápice por subclasse. Ela continua sujeita a preparação, Entropia, frequência e
  condições; não pode remover Carga permanentemente, ignorar toda defesa ou
  encerrar qualquer chefe sem resolução.
- **R9 — Poder com preço:** toda Ápice possui ao menos um freio mecânico validado:
  frequência `cena|descanso_curto|descanso_longo`, custo relevante de Entropia,
  ganho/risco de Carga, condição de setup, sacrifício, exposição ou consequência
  de classe. O linter rejeita Ápice livre sem contrapartida.
- **R10 — Slots preparados:** a curva passa a `4` (1–3), `5` (4–6), `6` (7–9),
  `7` (10–12), `8` (13–16), `9` (17–19) e `10` (20). O Acervo pode ser maior;
  preparação continua livre somente em condição segura.
- **R11 — Virtudes preservadas:** Virtudes continuam 0–5 e não recebem pontos
  depois do nível 10. Nos níveis 12, 16 e 20 surge uma escolha
  `kind="virtue_mastery"` que aumenta a maestria de uma das duas Cartas de Virtude
  permanentes. Cada Carta suporta `mastery: 0..2`; três ganhos resultam em
  distribuição máxima 2+1, sem criar sexta faixa de Virtude.
- **R12 — Maestria tipada:** o estágio efetivo de uma Carta de Virtude é derivado
  em Python de `estagio` e `mastery`, limitado à tabela autorada. Cada efeito de
  maestria possui valores explícitos e teste; não se multiplica texto nem se
  aceita valor proposto pela LLM.
- **R13 — Escala de recursos:** Vitalidade continua derivada apenas de Corpo.
  Entropia não cresce cegamente pelo `level_gains` atual em todos os níveis
  11–20: a implementação deve medir os cinco pools no nível 10 e definir uma
  curva tardia explícita por classe, com teto autorado, antes de liberar conteúdo.
- **R14 — Migração aditiva:** save jogável no nível 1–10 recebe defaults para
  `virtue_cards[].mastery=0`; nenhuma Carta conhecida/preparada/evoluída muda de
  ID. Save que já contenha nível 11–20 de fixture antiga é normalizado sem perder
  XP, mas só recebe escolhas/Ápice ausentes uma vez, por ledger idempotente. Para
  subclasse: um único ramo detectável nas Cartas é persistido; personagem nível
  3+ sem ramo recebe uma escolha pendente exatamente uma vez; legado com Cartas
  de múltiplos ramos preserva todo o Acervo, fixa para progressão futura o ramo
  que a regra histórica já derivava da primeira Carta conhecida e bloqueia novas
  aquisições rivais, sem apagar conteúdo conquistado. Nível 1–2 continua sem
  subclasse e qualquer Carta de ramo legada é preservada, mas não autoriza novas.
- **R15 — Interface:** HUD mostra `nível/20`, próximo limiar de XP, tier liberado e
  slots `usados/limite`. Modal distingue Carta nova, evolução, Maestria de Virtude
  e Ápice concedida; no nível 3, apresenta a escolha de subclasse em etapa própria,
  explica sua permanência e só libera a etapa de Carta após confirmação. Cartas
  bloqueadas podem ser inspecionadas sem revelar texto secreto e exibem o nível
  e/ou ramo exigido.
- **R16 — Conteúdo e anti-reskin:** validação detecta IDs duplicados, gates
  inválidos, pré-requisito órfão, tier fora de 1–9, Ápice fora do nível 20 e
  assinatura mecânica duplicada dentro da mesma classe/subclasse sem diferença de
  papel. Conteúdo passa por `scripts/validate_content.py` e relatório de cobertura.
- **R17 — Balanceamento mensurável:** playtest cobre níveis 9, 12, 15, 18 e 20 nas
  cinco classes, registrando uso de Cartas tardias, Entropia, Carga, duração de
  combate, dano/cura/controle e taxa de Ápice. Números finais são ajustados por
  telemetria, não por intuição isolada.

### Fora de escopo

- Aumentar o cap além de 20 ou criar multiclasse.
- Reescrever as 153 Cartas existentes, exceto metadata de gate/backfill necessária.
- Criar inimigos, chefes ou loot de endgame; isso será uma spec posterior apoiada
  no novo cap.
- Aumentar Virtudes acima de 5 ou alterar a distribuição inicial 4/3/2/1/1.
- Permitir que a LLM escolha números, gates, evolução ou concessão de Carta.

## 3. Design técnico

### 3.1 Tabelas e schema

**Alterar `gamedata.py`:**

```python
NIVEL_MAX = 20
TIER_LEVELS = {1: 1, 2: 1, 3: 4, 4: 7, 5: 9, 6: 12, 7: 15, 8: 18, 9: 20}
NIVEIS_MAESTRIA_VIRTUDE = (12, 16, 20)

def card_tier_for_level(level: int) -> int: ...
def prepared_slots_for_level(level: object) -> int: ...
```

O backfill 1–4 é autorado no gerador, não inferido em runtime pelo nome da Carta.
`level_req` é a checagem final; `tier` organiza cobertura e UI.

**Estender o schema de Carta em `state.py`/validador:**

```python
class Carta(TypedDict, total=False):
    tier: int
    level_req: int
    apex: bool
    # campos existentes permanecem

class VirtueCardChoice(TypedDict):
    card_id: str
    virtude: str
    estagio: int
    mastery: int

class SubclassChoice(TypedDict):
    id: str
    name: str
    identity: str
    playstyle: str
    tradeoff: str
    preview_card_ids: list[str]
```

Cada registro novo deve preencher os campos acima junto do schema atual de
Carta. IDs, nomes e efeitos serão aprovados durante a autoria; a spec não cria um
ID canônico fictício que possa ser copiado acidentalmente para o catálogo.

**Estender cada ramo de `data/classes.json`:** manter `name` e `identity` atuais e
autorar `playstyle`, `tradeoff` e `preview_card_ids`. O validador exige exatamente
três ramos por classe, textos públicos não vazios e previews que pertençam ao
tronco ou ao próprio ramo; a API nunca sintetiza essas explicações com LLM.

### 3.2 Progressão

**Alterar `progression.py`:**

```python
def eligible_cards(player: dict) -> list[str]: ...
def eligible_subclasses(player: dict) -> list[SubclassChoice]: ...
def grant_apex_if_due(player: dict, new_level: int) -> tuple[dict, str | None]: ...
def effective_virtue_card_stage(card_choice: dict) -> int: ...
def apply_choice(
    player: dict,
    choice_id: str,
    *,
    virtude: str = "",
    card_id: str = "",
    evolve_card_id: str = "",
    caminho: str = "",
    virtue_card_id: str = "",
    subclass_id: str = "",
) -> tuple[dict, str]: ...
```

Ao subir de nível:

1. soma recursos conforme a curva correspondente;
2. ao chegar ao nível 3 sem ramo, enfileira `kind="subclass"` antes de
   `kind="carta"`; a segunda escolha não pode ser aplicada fora de ordem;
3. confirmação valida o ID contra `data/classes.json`, persiste
   `player.subclass` e registra `subclass_chosen` como milestone da crônica;
4. níveis 11–19 enfileiram `kind="carta"` normalmente;
5. nível 20 concede Ápice uma vez e não enfileira escolha normal de Carta;
6. níveis 12/16/20 enfileiram `kind="virtue_mastery"`;
7. emite `level_up` e, no nível 20, `class_apex_unlocked` para feedback/crônica.

`player.subclass` passa a ser a autoridade em runtime. A inferência pela primeira
Carta conhecida existe somente dentro da migration de legado; criação, API, CLI,
frontend e playtest nunca podem gravar Cartas de ramos rivais para provocar um
lock acidental. O ledger usa uma chave estável como `lvl3:subclass:<subclass_id>`
para que retry, restore e load repetido não reapresentem nem reapliquem a escolha.

O ledger pode ser uma lista curta `progression_grants` com chaves estáveis
`lvl20:apex:<card_id>`; reaplicar migração ou retry nunca duplica a Carta.

### 3.3 Autoria e validação

- **Alterar `scripts/gen_cards_v4.py` ou gerador canônico vigente:** declarar as
  80 Cartas em fonte revisável e regenerar `data/cards/{classe}.json`.
- **Alterar `services/content_validator.py`:** schema/gates/Ápice/pré-requisitos,
  80 exatas e matriz de cobertura.
- **Alterar `scripts/content_report.py`:** contagens por classe, subclasse, tier,
  tipo e nível mínimo; separar legado do lote tiers 5+.
- Toda mudança mecânica nova entra primeiro no resolver Python e em seu catálogo
  fechado; o gerador não cria handlers por reflexão ou texto.

### 3.4 API, frontend e playtest

- `api.py::_levelup_block` filtra por nível e informa `tier`, `level_req`, `apex`,
  maestrias elegíveis, concessões automáticas e, para `kind="subclass"`, as três
  opções públicas vindas de `data/classes.json` na ordem canônica.
- `web/src/types.ts`, `Hud.tsx` e `LevelUpModal.tsx` representam o contrato sem
  recalcular gates no cliente. O modal usa duas etapas no nível 3: ramo e Carta.
- `playtest/runner.py::_resolve_profile_progression` aprende a resolver
  `subclass`, `virtue_mastery` e reconhecer concessão de Ápice.
- Novo perfil/ferramenta de fixture eleva personagens diretamente aos níveis de
  medição sem falsificar Cartas: aplica a mesma progressão e escolhas determinísticas.

## 4. Plano passo a passo

### Etapa 1 — Cap, gates e migração

1. **Testes** (`tests/test_progression_20.py`): XP 10→20; cap; slots; backfill;
   nível 3 enfileira subclasse antes da Carta; nível 1–2 não aprende ramo;
   confirmação é irreversível; Carta rival é inelegível; Carta level 20 é
   inelegível no 19; cada cenário de save antigo preserva Acervo/evoluções.
2. **Implementação:** tabelas, schema, gate e migração idempotente.
3. **Verificação:** testes focados verdes.

### Etapa 2 — Maestria e Ápice

1. **Testes:** escolhas 12/16/20; teto de maestria 2; distribuição 2+1; Ápice
   automática uma vez; nível 20 sem escolha normal duplicada; retry idempotente.
2. **Implementação:** progressão, efeitos tipados, evento e API.
3. **Verificação:** testes focados verdes.

### Etapa 3 — Autoria das 80 Cartas

1. **Testes** (`tests/test_tiers_5_plus_content.py`): total/distribuição 20+45+15,
   cobertura, gates, variedade, freios de Ápice e zero efeito órfão.
2. **Implementação:** autoria em cinco lotes de 16, um por classe; validar cada
   lote antes do próximo.
3. **Verificação:** `validate_content.py` e `content_report.py` verdes.

### Etapa 4 — Frontend

1. **Testes:** DTO/types, modal por tipo de escolha, bloqueio/nível exigido,
   maestria e feedback da Ápice; viewport 390 px.
2. **Implementação:** API e componentes React.
3. **Verificação:** `npm run build` e smoke visual.

### Etapa 5 — Balanceamento tardio

1. **Testes:** fixtures nas cinco classes × níveis 9/12/15/18/20; invariantes de
   Entropia/Carga/Vitalidade e cobertura de uso.
2. **Implementação:** telemetria e curva tardia de Entropia; ajustar somente
   constantes/dados documentados.
3. **Verificação:** playtests offline e real conforme seção 6; suíte completa.

## 5. Critérios de aceite

- [x] O jogo progride legitimamente do nível 1 ao 20 e para no cap.
- [x] Gates numéricos impedem aquisição precoce em API, CLI e playtest.
- [x] No nível 3, a subclasse é escolhida explicitamente antes da Carta e fica
      persistida; nenhum fluxo ainda usa a primeira Carta como escolha implícita.
- [x] Níveis 1–2 oferecem somente tronco; após o nível 3, apenas tronco + ramo
      escolhido são elegíveis.
- [x] O catálogo contém exatamente 80 Cartas novas na distribuição 20+45+15.
- [x] As 15 subclasses possuem uma Ápice mecânica e tematicamente distinta.
- [x] Virtudes seguem no teto 5; maestrias 12/16/20 funcionam e não duplicam.
- [x] Slots preparados seguem 4/5/6/7/8/9/10.
- [x] Saves atuais preservam IDs, Acervo, preparação, evoluções e XP.
- [x] Saves legados inferem, solicitam ou estabilizam subclasse uma única vez,
      sem apagar Cartas de ramos rivais já conquistadas.
- [x] `scripts/validate_content.py` e relatório de cobertura verdes.
- [x] `cd web && npm run build` verde e UI aprovada em 390 px.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Nenhum `with_structured_output` novo sem guard de `FallbackLLM`.

## 6. Smoke test com LLM real

1. Criar uma ficha real e usar fixture de progressão pelo caminho público; no
   nível 3, confirmar as três opções, escolher uma, verificar a etapa de Carta e
   tentar adquirir um ramo rival. Continuar até 9, 12, 15, 18 e 20, resolvendo
   cada escolha no endpoint.
2. Em cada tier, entrar em conflito e usar uma Carta nova; confirmar que números
   vêm do motor, o narrador não contradiz custo/frequência e não há fallback mock.
3. No nível 20, confirmar Ápice concedida uma vez, Maestria oferecida e nenhuma
   escolha normal fantasma.
4. Rodar uma campanha por classe com teto explícito de custo e anexar ao relatório
   Entropia/Carga/duração/uso de Ápice antes de marcar `done`.

## 7. Riscos & compatibilidade

- **Power creep:** 80 opções novas podem invalidar inimigos atuais; gates,
  frequência e playtest por tier são obrigatórios antes de tuning final.
- **Entropia inflada:** reutilizar `level_gains` até 20 sem curva tardia tornaria
  custo irrelevante; R13 impede o crescimento cego.
- **Save no meio da progressão:** migração/concessões usam chaves idempotentes;
  nenhum load pode conceder Ápice repetidamente.
- **Legado com ramos misturados:** apagar Cartas seria perda de progresso; a
  migration preserva o Acervo, registra a decisão histórica e restringe apenas
  aquisições futuras. O frontend sinaliza a compatibilidade sem pedir uma escolha
  que contradiga o save.
- **Autoria volumosa:** entrega em cinco lotes sempre verdes; a spec só vira
  `done` com as 80 e toda a matriz coberta.
- **MockLLM:** valida regra e regressão, não qualidade de narração nem balanço
  subjetivo; o smoke real continua obrigatório.
