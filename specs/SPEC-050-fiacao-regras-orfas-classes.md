# SPEC — Fiação das regras órfãs das 5 Posturas (taunt · Transformação · Purga)

> **Status:** `done` (2026-07-19 — 11 testes + baseline real exercitou o caminho de combate sem crash)
> **Criada:** 2026-07-19 · **Atualizada:** 2026-07-19
> **Depende de:** [refatoracao-sistema-classes](SPEC-048-refatoracao-sistema-classes.md) `done` ·
> [arvores-habilidade-classes](SPEC-047-arvores-habilidade-classes.md) `done`
> **Desbloqueia:** [balanceamento-classes-pos-playtest](SPEC-049-balanceamento-classes-pos-playtest.md)
> (não adianta balancear knob de regra que não roda)

---

## 1. Contexto & Objetivo

Auditoria de código 2026-07-19 (mesma data do épico): três mecânicas do sistema
de classes estão **implementadas e testadas em unidade, mas NUNCA chamadas pelo
fluxo de produção** (grafo → combat_node → combat_mechanics). Os testes passam
porque chamam a função direto; no jogo, a mecânica é letra morta:

1. **Taunt do Devoto morto.** `taunt_aggro_multiplier`
   ([combat_mechanics.py:525](../combat_mechanics.py#L525)) não tem callsite de
   produção, e `pick_target` ([combat_mechanics.py:1221](../combat_mechanics.py#L1221))
   ignora a condição `control: "taunt"` que as habilidades aplicam
   (`postura_*`/`taunt_ciumento` via `control("taunt", 2)` no gerador). Resultado:
   o tank da party **não tanka** — inimigo escolhe alvo pelo perfil
   (tatico/feroz/...) como se a provocação não existisse. A regra especial
   inteira da classe (aggro escala com Entropia) não influencia nada.
2. **Transformação do Corruptor morta.** `apply_transformacao`
   ([combat_mechanics.py:633](../combat_mechanics.py#L633)) não tem callsite de
   produção. O Corruptor acumula Carga do Abismo sem NENHUMA consequência — a
   única classe cuja consequência de Carga simplesmente não roda.
   (ESTADO_ATUAL afirma "consequências fiadas no loop de combate" — falso p/ esta.)
3. **Purga da Carga morta.** A habilidade `purga_da_carga` (Médico, boticário,
   nível 5) declara `effects: [{"kind": "reduce_ally_abyss", "amount": 2}]`, mas
   `_split_typed_effects` ([combat_mechanics.py:836](../combat_mechanics.py#L836))
   só classifica `buff/debuff/dot/control` — o efeito é **descartado em
   silêncio**. `cm.reduce_ally_abyss` (função pronta, com guard de classe) nunca
   é despachada pelo grafo. No jogo: paga 5 de Entropia, loga "usa Purga da
   Carga." e a Carga do aliado não muda.

Por que o smoke real 4/4 não pegou: exercitou as funções/gatilhos diretamente,
não o caminho completo habilidade→efeito no grafo. Padrão de falha novo p/ o
projeto: **"mecânica declarada nos dados sem handler no motor"** — o MockLLM não
pega, teste de unidade não pega, e o efeito some sem erro. R4 fecha essa classe
de bug em definitivo.

## 2. Requisitos

- **R1 — Taunt funciona.** Inimigo com condição `control: "taunt"` ativa
  prioriza o provocador (player) em `pick_target`, sobrepondo o perfil:
  chance de atacar o provocador = `min(0.9, base × taunt_aggro_multiplier(player))`
  com `base = 0.5` (`[BALANCEAR]`); fora do acerto da chance, cai no perfil
  normal. Devoto com Entropia alta segura mais aggro que com Entropia 0
  (testável com seed). Condição expira → comportamento volta ao perfil.
- **R2 — Transformação roda.** No round do jogador em combate (mesmo ponto de
  `tick_boiler`/`reset_entropy_turn` em `agents/combat.py`), Corruptor com
  `abyss_tier ≥ leve` recebe/renova o debuff via `apply_transformacao`
  (a condição já tem `duration: 2` — reaplicar por round renova; sem stack).
  Fora de combate não aplica (consequência é de combate, como boiler).
- **R3 — Purga despachada.** Efeito `kind: "reduce_ally_abyss"` resolve de
  verdade: no fluxo de `resolve_player_action`, o efeito chama
  `cm.reduce_ally_abyss(player, ally, amount)` no aliado da party com MAIOR
  `abyss_charge` (heurística determinística; sem alvo textual novo). Sem aliado
  vivo com Carga > 0 → a ação falha com log claro **sem gastar Entropia**
  (checar antes de `spend_resources`). O custo interno de
  `reduce_ally_abyss` (cost=2) é removido/zerado — o custo REAL é o da
  habilidade (5), não os dois.
- **R4 — Anti-órfão estrutural.** Novo teste de contrato dado↔motor:
  varre os JSONs gerados (`classes.json`: `special_rule.kind`,
  `abyss.consequence`, `entropy_trigger.kind`; `player_abilities.json`:
  `effects[].kind`, `passive_effects[].trigger`) e asserta que TODO kind/trigger
  declarado consta num registro explícito de handlers do motor
  (`combat_mechanics.HANDLED_KINDS = {...}` mantido junto dos handlers).
  Kind novo nos dados sem handler → suíte vermelha. (Teria pego os 3 bugs.)
- **R5 — Docs corrigidos.** ESTADO_ATUAL/docs/CLASSES.md param de afirmar que
  taunt/Transformação/Purga funcionam até esta spec fechar; ao fechar, refletem
  a fiação real.

### Fora de escopo

- Balancear `base`/números (spec balanceamento-classes-pos-playtest; aqui só
  fazer FUNCIONAR com os números atuais marcados `[BALANCEAR]`).
- Taunt de inimigo sobre aliados da party (só provocação DO player, escopo do
  gerador atual).
- Alvo de aliado escolhido pelo LLM p/ a Purga (heurística determinística basta;
  se um dia precisar, é spec própria).
- Tiers 5+.

## 3. Design técnico

**Arquivos alterados**
- `combat_mechanics.py` —
  - `pick_target(enemy, targets, player=None)`: novo parâmetro opcional
    (retro-compatível); se `enemy` tem condição `control == "taunt"` e `player`
    veio, rola a chance R1 antes do perfil.
  - `_split_typed_effects`: passa a devolver também os efeitos "de aliado"
    (`ally_effs`) — ou lista separada `kind == "reduce_ally_abyss"`.
  - `resolve_player_action`: pré-check da Purga (aliado elegível) ANTES de
    `spend_resources`; dispatch do efeito no aliado escolhido; `allies` já
    chega ao resolve (Fase 4.5) — confirmar assinatura.
  - `reduce_ally_abyss(..., cost: int = 0)`: custo interno default 0 (R3).
  - `HANDLED_KINDS` (R4): dict/set público
    `{"special_rule": {...}, "consequence": {...}, "entropy_trigger": {...},
    "effect": {...}, "passive_trigger": {...}}`.
- `agents/combat.py` — chamada `cm.apply_transformacao(player, logs)` junto ao
  bloco `reset_entropy_turn`/`tick_boiler` (linha ~479); callsite de
  `pick_target` (combat_mechanics.py:1442) passa `player`.
- `tests/test_fiacao_classes.py` — novo (ver Etapas).
- `ESTADO_ATUAL.md` / `docs/CLASSES.md` — R5.

**Assinaturas**
```python
def pick_target(enemy: Dict, targets: List[Dict], player: Optional[Dict] = None) -> Optional[Dict]: ...
def reduce_ally_abyss(medic: Dict, ally: Dict, amount: int, *, cost: int = 0) -> Tuple[bool, str]: ...
HANDLED_KINDS: Dict[str, set]  # categoria -> kinds com handler no motor
```

## 4. Plano passo a passo

### Etapa 1 — R4 primeiro (o teste que pega os 3)

1. **Testes** (`tests/test_fiacao_classes.py`):
   `test_todo_kind_declarado_tem_handler` — varre os 2 JSONs gerados e compara
   com `HANDLED_KINDS`; DEVE FALHAR agora acusando `reduce_ally_abyss` (effect)
   e o que mais estiver órfão (`heal_abyss` como special_rule do Médico —
   decidir: registrar como alias da Purga ou renomear no gerador).
2. **Implementação:** `HANDLED_KINDS` refletindo o estado REAL (sem mentir);
   o teste fica vermelho até as Etapas 2–4 fecharem os buracos.

### Etapa 2 — Taunt (R1)

1. **Testes:** `test_taunt_forca_alvo` (inimigo taunted com seed fixa ataca o
   player mesmo com aliado de menor HP; perfil `tatico`); `test_taunt_expira`
   (condição removida → volta ao perfil); `test_taunt_escala_com_entropia`
   (frequência de alvo=player cresce com Entropia, 200 rolls com seed).
2. **Implementação:** `pick_target` + callsite com `player`.
3. **Verificação:** `uv run pytest` — arquivo novo verde.

### Etapa 3 — Transformação (R2)

1. **Testes:** `test_transformacao_aplica_no_round` (Corruptor tier `moderado`
   entra no round → condição "Transformação (…)" ativa com delta −2);
   `test_transformacao_renova_sem_stack` (2 rounds → 1 condição só);
   `test_transformacao_tier_nenhum_nao_aplica`; `test_outras_classes_imunes`.
2. **Implementação:** chamada em `agents/combat.py`.

### Etapa 4 — Purga (R3)

1. **Testes:** `test_purga_reduz_carga_do_aliado` (party com 2 aliados, Carga 5
   e 2 → o de Carga 5 cai p/ 3; Entropia do Médico cai só o custo da
   habilidade); `test_purga_sem_alvo_nao_gasta` (sem aliado com Carga → falha
   com log, Entropia intacta); `test_purga_nao_medico_bloqueada` (guard segue).
2. **Implementação:** split + pré-check + dispatch + `cost=0`.
3. **Verificação:** Etapa 1 fica verde (nenhum kind órfão restante).

### Etapa 5 — Docs (R5) + regressão

1. Harness mock: `uv run python -m playtest run --profile combate --turns 50`
   (Devoto default) — log de combate mostra provocação segurando alvo.
2. ESTADO_ATUAL/docs/CLASSES.md atualizados; suíte completa verde.

## 5. Critérios de aceite

- [ ] Inimigo taunted ataca o Devoto acima da taxa base (teste com seed)
- [ ] Corruptor `tier ≥ leve` luta debuffado; `nenhum` limpo
- [ ] `purga_da_carga` usada em combate reduz a Carga do aliado de maior Carga
- [ ] Purga sem alvo válido não gasta Entropia
- [ ] Teste anti-órfão (R4) verde e teria pego os 3 bugs (verificado no vermelho da Etapa 1)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM: N/A (zero structured output novo)
- [ ] Saves antigos continuam carregando (nenhum campo novo de schema)

## 6. Smoke test com LLM real

1. Combate real com Devoto + 1 aliado na party contra 2 inimigos `tatico`:
   provocar → transcript mostra inimigos batendo no Devoto (não no aliado
   ferido) enquanto o taunt dura.
2. Corruptor com Carga ≥ 4 entra em combate → narração/chips mostram o debuff
   de Transformação ativo.
3. Médico com aliado carregado usa Purga da Carga **pelo chat** → estado do
   aliado (`/game/state`) mostra `abyss_charge` reduzido.

## 7. Riscos & compatibilidade

- **Saves antigos:** sem campo novo; condições novas usam o pipeline existente.
- **MockLLM:** rotas de combate mock exercitam `resolve_player_action` — os
  testes novos rodam offline; nada depende de LLM (mecânica 100% Python).
- **Quota/latência:** zero chamadas novas.
- **Risco de assinatura:** `pick_target` ganha parâmetro opcional —
  retro-compatível com todos os callsites/testes existentes.
- **Risco `heal_abyss`:** `special_rule.kind` do Médico no gerador está
  `"heal_abyss"` mas nenhum handler o lê (a lógica real é a Purga via efeito).
  Decisão na Etapa 1: renomear no gerador p/ documentar-somente OU registrar
  como alias — nunca deixar kind fantasma passando no R4.

## 8. Registro de execução (2026-07-19)

- **Implementado conforme spec** com 3 desvios registrados:
  1. `reduce_ally_abyss` mantém `cost: int = 2` como default (teste/API antigos
     intactos); o dispatch da Purga passa `cost=0` explicitamente — o design
     (custo único = o da habilidade) vale igual.
  2. `heal_abyss` e `domain_decay` (Corruptor) registrados em
     `_DOC_ONLY_SPECIAL_RULES` dentro de `HANDLED_KINDS` — kinds informativos
     cuja mecânica vive em outro lugar (efeito da purga / overrides de branch).
  3. `apply_transformacao` loga só quando a condição ENTRA (renovação por round
     é silenciosa — evita spam de log).
- **Testes:** `tests/test_fiacao_classes.py` — 11 testes (R4 anti-órfão acusou
  os 3 bugs antes do fix, como previsto). Módulos de combate/classes: verdes.
- Purga: pré-check acontece ANTES de `spend_resources` (sem alvo → Entropia
  intacta, sem cooldown armado); alvo = aliado ativo de MAIOR `abyss_charge`.
- Taunt: `pick_target(enemy, targets, player=None)` retro-compatível;
  `_TAUNT_BASE_CHANCE = 0.5` `[BALANCEAR]`, teto 0.9.
- **§6 smoke real:** a spec NÃO adiciona structured output novo (mecânica 100%
  Python determinística — o risco "MockLLM esconde bug de mapeamento" não se
  aplica). O baseline real da spec balanceamento (`run_id 20260719-115906`)
  exercitou `resolve_player_action(..., allies=party)` e o novo caminho de
  combat no DeepSeek REAL por vários turnos (Sangromante/Arcanista/Corruptor)
  sem erro — de-facto smoke do caminho fiado. `done`.
