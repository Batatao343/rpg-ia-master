# Mecânica determinística do rpg-ia-master — relatório técnico

Escopo: tudo que o projeto resolve em Python sem LLM ("Mecânica é Python, não LLM"). Todas as referências são `arquivo:linha` do working tree em 2026-10-12. Os números foram conferidos executando as funções reais (scripts em `scratchpad/ex.py` e `ex2.py`, fora do projeto), não só lendo.

Convenção: a IA (LLM) só **identifica** a intenção do jogador e **narra** o resultado. Dados, dano, Ferimentos, economia, clima, luz, XP e níveis são código. O LLM entra em três pontos de combate: parse da fala em `TurnDeclaration` (`agents/combat.py:341`), geração de Cicatriz (`services/death_flow.py:267`) e preparação opcional de cena (hoje substituída por geometria Python mínima, `agents/combat.py:270-301`).

---

## 1. Visão geral do pipeline de combate v4 (Valoria v2)

O "cutover" do conflito-13 removeu o combate d20+AC. O núcleo atual é uma pilha de módulos puros compostos pelo orquestrador:

```
agents/combat.py::combat_node            (nó do grafo; parse, spawn, fuga, loot/XP, morte)
  └─ services/conflict_orchestrator.py::run_round     (uma RODADA inteira)
       ├─ iniciativa por lado             → conflict_resolution.roll_initiative_by_side
       ├─ por ator (ordem de Agilidade):
       │    ├─ tick de condições/DoT      → _tick_conditions_v4
       │    ├─ IA inimiga                 → enemy_declaration → tactical_profile.pick_action
       │    ├─ Ataque de Oportunidade     → reactions.trigger_opportunity_attack
       │    ├─ Janela de Reação           → _open_reaction_window / reactions.*
       │    └─ turno (Pré→Ação→Pós)       → conflict_turn.resolve_turn
       │         ├─ ataque                → conflict_resolution.resolve_attack
       │         └─ dano → Ferimentos     → conflict_damage.resolve_damage_and_wounds
       ├─ Última Ação (fora de ordem)     → _resolve_last_stands
       ├─ Estado Terminal/estabilização   → resolve_terminals → death_flow
       └─ fim de rodada: Entropia por kill, Recidiva, evento do Abismo
```

`run_round` é `services/conflict_orchestrator.py:1135`. O nó de combate chama-o em `agents/combat.py:~848` passando `declarations={player: decl}`, `prepared_abyss=scene["abyss_events"]`, `initiator` (surpresa) e o `rng` (módulo `random`, semeado pelo harness/persistência, portanto reprodutível por seed).

### 1.1 A ficha de combate (`ensure_combat_sheet`)

`services/conflict_orchestrator.py:59-125`. Idempotente: normaliza qualquer ator (jogador, inimigo, aliado) para o schema v4:

- `virtudes` (0-5; se ausentes, derivadas do `attributes` D&D legado via `actor_mods`, `conflict_resolution.py:34-44`).
- `max_vitalidade` = `vitalidade_para_corpo(corpo)` (+ bônus de classe, ver §5).
- `ferimento_espacos` por Corpo, `ferimentos {leve,grave,critico}`, `esquiva`.
- Inimigo: `categoria` canônica (lacaio/padrao/elite/chefe/nomeado/companheiro, `:39-47`), `tactical_profile` normalizado, `pursuit_policy`, e **Entropia própria** = `max(0, Mente×2)` (`:107-109`), mais a Carta universal `bst_defesa_instintiva` anexada a toda ficha inimiga não-companheiro (`:116-121`; removida do jogador, `:96-100`).

### 1.2 Tabelas-base (todas em `gamedata.py`)

| Tabela | Valor | Linha |
|---|---|---|
| Vitalidade por Corpo (0..5) | 6, 8, 10, 12, 14, 16 | `gamedata.py:278` |
| Espaços de Ferimento por Corpo | C0 2/1/1 · C1 3/1/1 · C2 3/2/1 · C3 4/2/2 · C4 4/3/2 · C5 5/3/3 (leve/grave/crítico) | `:281-288` |
| Limites de Gravidade (faixas de **excedente**) | C3: leve 1-6, grave 7-12, crítico 13+; C0: 1-3 / 4-6 / 7+; C5: 1-8 / 9-16 / 17+ | `:292-299` |
| Dano-base por categoria de arma | leve 3 · marcial 4 · versátil 6 · pesada 8 | `gamedata.py:196`, `cards.py` (DANO_BASE_ARMA), `conflict_turn.py:150` |
| Armadura | leve prot 1/integ 4/pen 0/reduz 1; média 2/6/1/2; pesada 3/8/2/3 | `:200-205` |
| Escudo | broquel 1/3; comum 2/5 (For≥2); pesado 3/7 (For≥3) | `:208-212` |
| Resist/Vuln | resistência −2, maior −4; vulnerabilidade +2, maior +4 | `:215` |
| Virtudes | 5 chaves (mente, agilidade, forca, carisma, corpo); teto 5; distribuição inicial (4,3,2,1,1) | `:176-180` |
| `NIVEL_MAX` | **20** | `:181` |

Obs.: o texto do cabeçalho de `progression.py:21` ("nível máximo passa de 20 para 10") está desatualizado — o código usa `gamedata.NIVEL_MAX = 20`.

---

## 2. Resolução de ataque: `2d10 + Virtude vs Esquiva`

Arquivo: `services/conflict_resolution.py`. Ordem de leitura:

### 2.1 Esquiva e Virtude

- **Esquiva** = `10 + Agilidade − esquiva_penalidade` (`:47-52`). A coluna `esquiva_penalidade` existe, mas nenhum código de produção a preenche a partir de armadura (ver §14, achado 2).
- **Virtude do ataque**: `virtude_value(actor, key)` clamp 0-5 (`:34-44`). A chave vem da Carta (`virtude_permitida[0]`), ou do tipo (`VIRTUDE_POR_TIPO`, `:15-20`: pesada→força, arco/adaga/rapieira→agilidade, magia/arcana/precisa→mente, comando/fé/medo/presença→carisma, sangue/carne/transformação→corpo), ou "forca" para ataque básico (`conflict_turn.py:228-238`).
- Ao valor da Virtude somam-se modificadores ambientais: `_env_attack_mod = clima.combat_attack_mod + luz.combat_mod` (`agents/combat.py:773-782`; para inimigos, `DARK_COMBAT_PENALTY` = −1 se o escuro é natural, mesmo se o herói tem tocha, `:775-777`).

### 2.2 Rolagem (`roll_kept`, `:59-69`)

- Normal: **2d10**, soma os dois.
- **Vantagem**: 3d10, mantém os 2 maiores. **Desvantagem**: 3d10, mantém os 2 menores. Vantagem e Desvantagem **se cancelam** e **não acumulam**: só o sinal importa (`:72-79`, e `roll_kept` colapsa o `advantage` para −1/0/+1, `:64`).
- **Ruptura** concede +1 de Vantagem (`resolve_attack:135-146`).

### 2.3 Crítico (`_crit_from_kept`, `:95-106`)

- Dupla nos dados **mantidos**, 1-9 = **Crítico** (multiplicador ×2 no efeito principal).
- Dupla 10 = **Supercrítico** (×3).
- Crítico/Supercrítico **acertam sempre**, mesmo abaixo da Esquiva (`resolve_attack:157-165`).
- Sem dupla: `acerto = total >= esquiva`.

### 2.4 Iniciativa por lado (`:116-132`)

Não é por indivíduo. Heróis+aliados formam um lado, inimigos o outro (`conflict_orchestrator.py:1197-1203`). Cada lado rola 2d10 + a maior Agilidade **consciente**; o maior total age primeiro. Se há `initiator` (surpresa — `encounter_surprise` "player"/"enemy" vira "heroes"/"enemy" em `agents/combat.py:783-785`), esse lado age primeiro sem disputa e só os outros rolam. Dentro de um lado, ordena por Agilidade desc, id (`:1205-1208`).

Regra extra (balanceamento early-game): nível ≤2, Vitalidade cheia, round ≤1, fora de zona apex → o lado dos heróis ganha a iniciativa do primeiro round (`agents/combat.py:248-267`).

### 2.5 Testes gerais (`general_test`, `:175-201`)

Fora de ataque: `Ímpeto (d10) + Presságio (d10) + Virtude` vs dificuldade. Dificuldades: fácil 9, comum 12, difícil 15, extremo 18, quase-impossível 21 (`:24`). Ímpeto > Presságio = consequência favorável; o inverso, desfavorável; empate, "puro". Ruptura: 2 dados de Ímpeto, mantém o maior. (Usado em armadilhas/estabilização e afins; o ataque **não** usa essa matriz.)

### 2.6 Exemplo numérico real (executado)

Personagem: Devoto do Abismo nível 1, criado por `create_player_character(...use_llm_flavor=False)`. Ficha gerada:

- Virtudes: Força 4, Corpo 3, Carisma 2, Mente 1, Agilidade 1.
- Vitalidade 18 (= C3 → 12, + `vitalidade_bonus` 6), espaços de Ferimento leve 4/grave 2/crítico 2, Entropia 14/14, Esquiva 11.
- Acervo: dev_golpe_convite, dev_muralha_viva, dev_conviccao, dev_aguentar, dev_ombro_porta, dev_vigiar_ruina; 4 preparadas.

Alvo: Rato da Peste (lacaio, `enemy_rato_peste_anel_lama`): Agilidade 3 → **Esquiva 13**, Vitalidade 12, sem armadura.

**Ataque básico (ou Golpe do Convite: marcial, dano_base 4)**, seed 1: dados `[3, 10]` → mantidos `[3, 10]`, sem dupla. Total = 13 + Força 4 = **17 ≥ 13 → acerto** (multiplicador ×1). Dano: carta marcial = 4, **+2 do bônus de early-game** (`combat_mechanics.early_game_damage_bonus`, nível 1-2) = 6 → Imunidade/Resistência: nenhuma → Armadura: nenhuma → Vitalidade 12 → **6**; excedente 0 → sem Ferimento. Região atingida sorteada ("torso").

**Crítico**, seed 13: dados `[5, 5]` → dupla 5 → **crítico**. Total = 10 + 4 = 14 (≥ 13, mas acertaria de qualquer forma). Multiplicador ×2 → dano = 6×2 = **12**; Vitalidade 12 → 0, excedente 0. O Rato fica com Vitalidade 0 e **ainda luta** (ver §5.2: a queda vem dos Ferimentos, não do zero de Vitalidade); como lacaio, qualquer Ferimento o derruba.

**Um golpe que fere (alvo com armadura média, C3, Vitalidade 3)**: `dano 8 cortante ×1 = 8` → Proteção −2 → 6 → Integridade gasta 2 e reduz 2 de dano (limite `reducoes_max` 2) → 4 → Vitalidade 3→0, excedente 1 → faixa leve de C3 (1-6) → **Ferimento leve no torso**; cortante e ferido → Sangramento (1 de dano, 1 turno). Saída real: `dano_final 4, excedente 1`.

**Caso crítico/terminal**: dano base 9 ígneo, crítico ×2 = 18, Vitalidade 2, C3 → ígneo +2 se atravessou → 20; Vitalidade 2→0, **excedente 18** → faixa crítica de C3 (13+) → Ferimento **crítico** no torso; como já havia um crítico no torso, o segundo é adicionado ocupando o próximo espaço (2/2 cheio → gatilho de Última Ação, §8).

---

## 3. Pipeline de dano → Ferimentos (`services/conflict_damage.py`)

`resolve_damage_and_wounds` (`:204-315`) aplica uma **ordem fixa** (R8):

1. **Dano × multiplicador de Crítico** (`dano = damage_base × crit_mult`).
2. **Imunidade → Resistência/Vulnerabilidade**. Imunidade zera tudo e retorna `resultado:"imune"`. Resist/vuln: `net_resistance` pega a mais forte de cada lado e soma (resistência −2/−4, vulnerabilidade +2/+4); fontes iguais não acumulam (`:167-181`).
3. **Proteção** da armadura **ou** escudo (um por ataque; não somam, `_active_defense` `:195-201`). Só vale se a defesa não está Comprometida e o tipo de dano é físico (cortante/perfurante/impactante) ou está em `resist_tipos` da defesa. Perfurante reduz a Proteção em 1; Impactante gasta 1 de Integridade extra se foi absorvido.
4. **Integridade**: pode converter Integridade em redução adicional de dano até `reducoes_max` por ataque (corrosivo custa 2×). Integridade 0 → armadura **Comprometida** (sem efeito).
5. **Ígneo**: +2 de dano se ≥1 atravessou.
6. **Vitalidade e Gravidade**: `excedente = max(0, dano − vitalidade)`; Vitalidade = `max(0, vit − dano)`.
7. **Ferimento** se `excedente > 0`: `categoria_ferimento(Corpo, excedente)` (tabela C0..C5 acima). Cortante e ferido → Sangramento (`_apply_sangramento`, 1 de DoT por 1 turno, não acumula).
8. **Efeitos secundários de tipo**: gélido → próximo ataque do alvo com Vantagem; elétrico → desvantagem no próximo ataque; abissal → "exposto" + ignora resistência; arcano → remove buff temporário.

**Regiões**: `anatomical_regions` (`:42-62`) lê `regioes_anatomicas` da ficha ou usa o fallback humanoide `cabeca/torso/braco/perna`. O jogador pode **mirar** (`params.regiao`), o que dá −1 de Vantagem no ataque (`conflict_turn.py:268-271`). Região inválida cai no sorteio.

**`apply_wound`** (`:114-164`): mesma região **agrava** (Leve+Leve = Grave, Leve+Grave = Crítico, teto Crítico, `combine_category` `:101-110`); categoria cheia **escala** para a seguinte; um Crítico existente na região **não** é combinado (preserva a sequela e ocupa o próximo espaço crítico). Se não há espaço na categoria final, o ferimento é "não aplicado" (`aplicado:false`).

**Sacrifício** (`sacrifice_vitality`, `:332`): Sangromante paga Vitalidade; o déficit além de 0 vira Ferimento pelas faixas de Gravidade; armadura **não** protege.

**Recuperação**: `recover_integrity` (curto = metade, longo = tudo, `:351`); `rest_treat_wounds` (`:366-401`): descanso remove Leves de graça; Grave exige kit (suprime e agenda); Crítico só o Médico com kit trata de fato (2 cargas), outros só estabilizam.

**DoT de condições** (`_apply_dot_v4`, `conflict_orchestrator.py:155-170`): passa pelo mesmo pipeline com `ignore_resistance=True, defensavel=False`, então armadura não protege e DoT que excede a Vitalidade também vira Ferimento.

### 3.1 Dano que o jogador e o inimigo realmente usam

`_damage_from` (`conflict_turn.py:163-190`), por precedência: `efeito.dano_base` da Carta → `categoria_arma` da Carta → fórmula legada → `step.params.dano_base` → `attack_formula` do ator → `dano_base_arma` do ator → **3 (default)**. No código atual, nenhum fluxo de produção preenche `dano_base_arma`/`attack_formula` do jogador; logo, o **ataque básico do jogador sem Carta = 3 flat** (+2/+1 de early-game, nível 1-2/3). Ataque por Carta usa o `dano_base` autoral (3/4/6/8 + excedente pago em Entropia).

---

## 4. Estrutura de um turno: `conflict_turn.py`

`TurnDeclaration` (`:44-52`): três slots — `pre_acao`, `acao`, `pos_acao` — mais `reaction_card_id` (reação escolhida antecipadamente). Cada `TurnStep.kind` ∈ `attack | card | item | maneuver | object | move | pass` (+ `tactic` só para IA). Orçamento por turno (`conflict_scene.py:33`): **1 Pré, 1 Ação, 1 Pós**.

`resolve_turn` (`:56-81`) reseta o orçamento e resolve os slots em ordem.

`_resolve_attack_step` (`:193-306`) para ataque/Carta:
1. Se tem `card_id`: `cards.effective_card` (aplica evolução A/B e Ruptura), exige `tipo == "ativa"` e `efeito.kind` no conjunto resolvível, gasta a economia (`use_card`/`use_ruptura` para o jogador; `use_enemy_card` para inimigos). Falha do jogador → turno inválido; falha do inimigo → cai para ataque básico.
2. Se o efeito é de **suporte** (`cura, estabilizar, protecao, reposicionar, esconder, purga_condicao, vantagem, buff_defesa/acerto/dano, reduzir_carga_aliado`) → `_resolve_support_card`, sem rolagem de ataque.
3. Senão, vantagem acumulada: ocultação (atacante escondido do alvo +1; alvo escondido com posição aproximada −1; sem posição → não pode mirar) + Guardar (`guard_offense_modifier` −1 se o atacante Guarda, `guard_defense_modifier` −1 se o alvo Guarda) + modificador tático consumível (apoio +1 / protegido −1) + mirar região (−1). Vantagem líquida colapsa em −1/0/+1.
4. `resolve_attack` → se acerta e a Carta é dano direto (`dano`, `contra_ataque`) ou não há Carta: dano pelo pipeline do §3. Se a Carta é de efeito (dot, condição, empurrão, taunt, marca) → `_apply_attack_card_effect` aplica a condição sem dano.
5. Atacar oculto revela o atacante **depois** da resolução (`reveal_after_attack`).

Cura de Carta de suporte: soma `valor` à Vitalidade, clamp ao máximo (`:309-336`). Os efeitos de buff (`protecao`, `buff_*`, `vantagem`) viram uma `Condition` no alvo com `stat`/`delta`/`duration` (`:353-362`); ver §14, achado 1 sobre quem as lê.

---

## 5. Cena posicional e reações

### 5.1 `conflict_scene.py`

Não há grade: a cena tem **zonas** e cada participante tem três eixos independentes (`:15-17`):
- **Distância**: `proximo → distante → separado` (3 estágios; mover custa 1 Pré OU 1 Pós, 1 estágio por chamada; mudar de estágio **encerra Escondido**, `move_distance:195-215`).
- **Postura**: `protegido / neutro / exposto` (momentânea expira após o próximo ataque; sustentada persiste enquanto a causa existir).
- **Ocultação**: `visivel / escondido`, **relativa por observador** (`hidden_from`, `approx_from`).

**Engajamento** é uma relação à parte da distância (`engaged_with`): Engajar custa Pré OU Pós; Desengajar custa a Ação e é "seguro" (sem Ataque de Oportunidade); Guardar custa a Ação (postura universal); Esconder-se custa a Ação e **exige fonte plausível**; Procurar custa a Ação e revela o alvo só para quem procurou; alertar a party custa Pré/Pós e propaga a posição aproximada.

**Objetos** têm catálogo fechado de efeitos (`EFFECT_KINDS`, `:20-24`): alter_terrain, block_route, unblock_route, damage, request_reaction, apply_condition, reposition, spawn_reinforcement, destroy_object, change_environment_condition. A cena congela (`freeze`, `:377`) depois da preparação; só gatilhos de reforço adicionam objetos depois.

**Estado tático** (`:64-155`): `round`, `modifiers` (`protected`, `attack_advantage`; duram até a rodada seguinte, não acumulam por participante) e `cooldowns` (máx. 2 rodadas; usado no "controle" tático).

### 5.2 Vitalidade 0 não é morte

`_alive` (`conflict_orchestrator.py:132-142`): a derrota é por **flag** (`dead/fled/surrendered/status/consciente`), não por Vitalidade. Vitalidade 0 é "muito ferido"; o ator segue lutando até encher espaços de Ferimento. O cadastro das saídas por categoria está em `_check_terminal` (`:726-750`):
- **Lacaio**: cai com **qualquer** Ferimento (`minion_defeated_by_wound`, `death_flow.py:47`).
- **Padrão**: é derrotado ao encher o último espaço crítico, sem Estado Terminal.
- **Elite/Chefe/Nomeado/companheiro/jogador**: fluxo completo (Última Ação → Estado Terminal), ver §7.
- Sobreviver ao fluxo terminal não dá imortalidade: se o ator tem todos os espaços críticos cheios e leva novo dano real depois, morre (`:733-740`).

### 5.3 Reações (`services/reactions.py`)

Uma ação **declarada** abre uma janela (`open_reaction_window`, `:60`). Cada candidato do lado oposto pode oferecer **uma reação COMUM por cadeia** (`offer_reaction:83-129`), validada nesta ordem: cadeia aberta → Carta existe e é `tipo=="reacao"` → gatilho casa (vocabulário fechado: sempre, ao_ser_atacado, ao_ser_alvo, aliado_atacado, inimigo_se_move, inimigo_ataca, ao_sofrer_dano) → o personagem ainda não usou a comum → a mesma Carta não repete (salvo `repetivel`) → Entropia suficiente. Reação pode responder reação (`respond_to_link`). Ordem: alvo direto → aliados do alvo → aliados do ator → maior Agilidade → id (`reaction_order`, `:142`).

**Ataque de Oportunidade** é universal e **fora** do limite de cadeia: quem abandona um Engajamento sem Desengajar (mover para `afastar`, ou a manobra tática `flee`) provoca um ataque básico de **cada** inimigo engajado, consciente e capaz (`:173-202`; fiação em `conflict_orchestrator.py:515-529` e detecção em `:501-512`).

Na prática, a janela é fiada em `_open_reaction_window` (`conflict_orchestrator.py:532-573`): reatores são o lado oposto; o jogador só reage pela Carta que escolheu na UI (`_player_reaction_card_id`, deve estar preparada); inimigos usam `_enemy_reaction_card`. Reação bem-sucedida **não** resolve o efeito da reação em si: concede o modificador tático `protected` ao reator (−1 de Vantagem no próximo ataque contra ele, uma vez, `grant_tactical_modifier`).

---

## 6. IA inimiga e perfis táticos (`services/tactical_profile.py`)

O perfil é uma lista **ordenada** de prioridades `{trigger, tipo, action_key, action_hint, resistance, blocks}`. `pick_action` (`:208`) devolve a **primeira** cujo gatilho é verdadeiro (`sempre` sempre vale; os demais são lidos de `scene_state[trigger]`). `action_key` pertence a um catálogo fechado: `attack, protect, stabilize, flank, control, support, flee, surrender` (`:22-25`). O texto `action_hint` é só apresentação.

`derive_tactical_scene_state` (`conflict_orchestrator.py:295-395`) calcula os únicos gatilhos reconhecidos, a partir do estado real da cena:

| Gatilho | Definição |
|---|---|
| `sozinho` | nenhum parceiro vivo |
| `muito_ferido` / `vitalidade_baixa` | Vitalidade ≤35% **ou** algum Ferimento grave/crítico |
| `cercado` | engajado com ≥2 oponentes |
| `matilha_quebrada` | parceiros vivos ×2 ≤ total de parceiros |
| `alvo_vulneravel` | algum oponente com ≤50% Vitalidade, algum Ferimento ou postura exposta |
| `descoberto` / `sem_flanco` | alvo mais próximo e o ator **não** está escondido dele |
| `plano_falhou` | muito ferido e (cercado ou sozinho) |
| `aliado_terminal / aliado_ferido / aliado_em_perigo / aliado_disponivel` | por busca de aliado em estado correspondente |
| `controle_disponivel` | cooldown de controle = 0 |

"Mais próximo" é um proxy: o oponente de maior Agilidade (`_nearest_target`, `:207`).

`enemy_declaration` (`:398-476`) resolve: alvo (Taunt tem prioridade, ver abaixo) → ação (`attack`, `flank`, `control`, `support`, `protect`, `stabilize` → `kind="tactic"`; `flee` → tactic/move; `surrender` → marca `surrendered` e passa) → se ataque, escolhe uma **Carta ofensiva** do inimigo se houver Entropia, senão ataque básico.

**Arquétipos**: `_ENEMY_ARCHETYPE_ACTIONS` (`tactical_profile.py:116-152`) mapeia arquétipo curado → gatilho→ação (ex.: `bruto`: muito_ferido→flee, sempre→attack; `covarde_oportunista`: sozinho→surrender, muito_ferido→flee, alvo_vulneravel→flank). Há 124 criaturas no bestiário: elite 54, lacaio 45, chefe 12, padrão 12, nomeado 1; arquétipos mais comuns: predador 21, covarde_oportunista 15, conjurador 15, morto_vivo_implacavel 15, bruto 14. Perseguição: `persegue` para predador, predador_apice, lider_matilha, morto_vivo_implacavel, emboscador, ágil e bruto (`:155-162`).

**Provocação (Taunt)** (`_taunt_target`, `:216-237`): se o inimigo tem condição `control:"taunt"` apontando para um alvo vivo, a chance de atacar o provocador é `min(0.9, 0.5 × multiplicador)`; o multiplicador do Devoto é `1 + min(0.6, 0.05 × Entropia)` (`combat_mechanics.taunt_aggro_multiplier:504`). Ex.: Entropia 10 → ×1,5 → 75%; Entropia ≥12 → 0,9 de teto.

**Ações táticas** (`_resolve_tactical_action`, `:765-868`), todas com validação de lado/estado: `protect` (concede `protected` ao aliado), `stabilize` (tentativa de `attempt_stabilization`), `flank` (esconde o ator só do alvo, sem custo), `control` (Atordoado, duração 2, cooldown 2, com save implícito via `apply_condition`), `support` (suporte cura 2 Vitalidade; outros dão `attack_advantage` ao aliado), `flee` (move 1 estágio; ao chegar em `separado`, o inimigo some do combate).

**Ordens a companheiros**: `validate_companion_order` (`:238`): uma Restrição cujos `blocks` batem com as tags da ordem só cede conforme a resistência: flexível cede; resistente cede com `leverage`; absoluta/autônoma nunca. A perda de comando é por condição explícita (medo, confusão, controle mental, separado…), ou consciência perdida (`loses_command`, `:265`).

---

## 7. Morte rica: `services/death_flow.py`

Quem usa o fluxo completo (`uses_full_death_flow:38`): o jogador, e as categorias elite, chefe, nomeado, companheiro. Lacaio e Padrão não.

1. **Gatilho** (`should_trigger_last_stand:69`): último espaço crítico preenchido, e o ator ainda não está morto/terminal/resolvido.
2. **Última Ação** (`trigger_last_stand`, `:90`; resolvida em `_resolve_last_stands`, `conflict_orchestrator.py:1011-1056`): acontece **fora da ordem**, exatamente uma vez. A implementação determinística é um ataque básico com **Vantagem extrema** (`advantage=1` → 3d10 manter 2) contra o oponente vivo de maior Agilidade, ignorando custo e Ferimentos. Pode "declarar Ruptura" (soma 1 Carga). Depois entra em Estado Terminal (`enter_terminal_state:134`).
3. **Estado Terminal → estabilização** (`attempt_stabilization`, `:171-209`):
   - Automático (sem rolagem): **Médico com kit** → reanima a **metade** da Vitalidade máxima; **poção adequada** → idem.
   - Sem aliado capaz → **morte imediata**.
   - Com aliado: rolagem `2d10` (ou 3d10-manter-2 se há kit/Médico) + **Mente do ajudante** vs **CD 12** (1ª tentativa) ou **15** (2ª); sucesso com kit → metade da Vitalidade; sucesso improvisado → 1 Vitalidade. **Duas falhas = morte.** Sobreviver marca `scar_pending`.
4. **Consciência pós-conflito** (`post_combat_consciousness:212`): só Leves → "acordado"; algum Grave → "tratável"; algum Crítico → "inconsciente" (o descanso longo com Vitalidade >0 promove inconsciente→tratável, `world_utils.py:228-237`).
5. **Cicatriz obrigatória** (`generate_scar:267`): via LLM (`ScarModel`) com o guard `isinstance` e fallback determinístico; anexa 1 consequência negativa + 1 habilidade positiva ligada ao trauma. Só aplicada ao jogador (`agents/combat.py:~890`).
6. **Golpe não-letal** (`can_be_nonlethal`, `apply_nonlethal_finish`): o golpe final pode ser declarado não-letal salvo forma `destruicao_total`/`queda_fatal`/`letal_forcado`.
7. **Rendição** (`resolve_surrender:318`): 100% determinística pelo perfil (líder caído, Vitalidade abaixo do limiar, aliados abaixo do mínimo, sem fuga + objetivo impossível, moral quebrada). `nunca_rende` bloqueia.
8. **Fim do combate** (`combat_should_end:352`): objetivo mecânico, gatilho preparado, ou todos os hostis inativos (mortos/fugidos/rendidos/inconscientes/incapacitados). Nunca por "perderam o interesse".

### 7.1 Morte do jogador no loop

Só a morte **real** do jogador (`out["player_dead"]`, após falha na estabilização) abre a tela de morte: o nó seta `death_pending`, bloqueia o loot e deixa a escolha para fora do grafo. Sobreviver ao Estado Terminal reanima e segue o combate (decisão R6 = Opção A do cutover, documentada em `ESTADO_ATUAL.md`).

### 7.2 Ciclo de vida / elegibilidade (`services/actor_lifecycle.py`)

`ActorPhase`: ACTIVE, UNCONSCIOUS, INCAPACITATED, LAST_STAND, TERMINAL, DEATH_PENDING, DEAD (`:12-19`). `classify_actor` (`:~67`) deriva a fase do estado. `evaluate_action` (`:~158`) **bloqueia** ações fora de combate quando o jogador não está ACTIVE: só descanso/socorro/tratamento (regex de intenção de recuperação) são permitidos para inconsciente/incapacitado; todas as outras ações devolvem mensagem de bloqueio por fase. `transition_readiness` diz se um estado pode virar checkpoint (nunca em combate ativo, Última Ação, Terminal, death pending ou morto). `sanitize_interturn_state` repara snapshots antigos órfãos (zera flags efêmeras e deixa crítico ferido inconsciente).

---

## 8. Fuga e perseguição (`services/chase.py`)

Fluxo no nó de combate: se a declaração é `flee`, `_attempt_flee` (`agents/combat.py:1068-1104`):
- Bloqueios: jogador não consciente/terminal/Última Ação → não foge; condição `root` (Enredado) → não foge.
- Cria ou retoma a perseguição (`chase.can_resume`: mesmo fugitivo, mesmos perseguidores, trilha não terminal) e rola **um round**.

**Trilha**: `pressionado → afastado → quase_livre → escapou` (`:20`). A posição inicial deriva da distância no momento da fuga (próximo→pressionado, distante→afastado, separado→quase_livre). Se nenhum perseguidor "persegue" (política fechada `pursuit_policy == "persegue"`), a trilha já nasce `escapou`.

**Round** (`resolve_chase_round:135-159`): teste `2d10` (ou 3d10-kept com Sorte) + Virtude do condutor vs **dificuldade = 10 + Agilidade do perseguidor principal**. O condutor é sempre o protagonista; a Virtude depende da abordagem (correr/desviar→agilidade, rotas/atalhos→mente, romper/obstáculos→força, resistência/prolongada→corpo, coordenar/mobilizar→carisma). No loop de combate hoje é fixo em **Agilidade** (`agents/combat.py:1091-1092`). Sucesso: avança 1 na trilha; falha: recua 1, e abaixo de `pressionado` = **alcançado** (combate retorna).

**Teste de Sorte** por companheiro (`luck_roll:117`): 1d10; 1-2 Complicação (−1), 3-8 neutro, 9-10 Ajuda (+1); saldo positivo → Vantagem, negativo → Desvantagem, sem acúmulo. (No loop atual `_attempt_flee` não passa `companion_luck`.)

**Abandono** (`abandon_companion` + `simulate_abandoned_companion:184-232`): o destino de um companheiro deixado é sorteado por **simulação determinística por seed**: pesos base 1 para {fuga, captura, rendição, esconderijo, combate, morte, reencontro_futuro} ajustados por razão de Vitalidade (≤25%: morte +2,5, captura +1,5; ≤50%: captura +1, combate +1), Agilidade (fuga +0,4×Ag; esconderijo +0,3×Ag, +1 se terreno favorável), número de perseguidores (captura +0,6/pers., combate +0,4/pers.), perfil rendição (+1,5) e reencontro (+0,5). Sacrifício voluntário só com traço (`can_volunteer_sacrifice:235`).

**Ataques em perseguição** (`chase_attack:260`): à distância é Ação normal; corpo a corpo em `pressionado` encerra a perseguição (reengajar).

**Limite de tentativas e destino** (`agents/combat.py:520-533`, `_enforce_flee_attempt_limit`, `_is_valid_flee_destination`): há teto local de tentativas de fuga e validação de destino conectado. Fuga bem-sucedida aplica `apply_travel` e reseta a cena transitória (NPC `in_scene`).

---

## 9. Evento do Abismo, preparação de encontro e resumo canônico

### 9.1 Eventos do Abismo (`services/abyss_events.py`)

Camada **complementar** aos gatilhos de classe. A LLM prepara os eventos antes do combate, cada um com `{gatilho, prioridade, cargas_necessarias, effect, usos_permitidos, base_na_cena}`. Em combate, **zero LLM**:
- `can_trigger` (`:96`): Cargas ≥ necessárias, usos restantes > 0, gatilho válido, e (se passados os objetos) `base_na_cena` referencia um objeto/tag **existente** na cena (substring), com `effect.kind` no catálogo fechado.
- `select_event` (`:112`): maior prioridade; empate decidido por seed (ou por id).
- `validate_abyss_effect` (`:133`): proibido desfazer sucesso resolvido, impor `controle_mental/dominado/enfeitiçado/possuído`, criar Ferimento direto, agravar Ferimento fora do combate normal.
- `trigger_event` (`:159`): decrementa usos e devolve a **assinatura visual fixa** (`ABYSS_SIGNATURE`: som abafa, cores perdem intensidade, fissura negra, pulso pálido…) e o gasto de Carga.
- Fim de rodada: `_maybe_abyss` (`conflict_orchestrator.py:1078`) só roda se `scene["abyss_events"]` existe; **debita** `cargas_gastas` de `player.abyss_charge` e aplica o efeito via `apply_effect_spec`.

Observação: `_prepare_scene` usa `fallback_safe_scene`, então na prática `scene["abyss_events"]` vem vazio e o Abismo em conflito só dispara se outro caminho popular a lista.

### 9.2 Preparação de encontro (`services/encounter_preparation.py`)

- **Nível do Encontro** (`compute_encounter_level:40-54`): perigo **absoluto** — `max(perigo do local, perigo da região) + bônus de tipo (comum 0, emboscada 1, caçada 1, ritual 2, invasão 2, apex 3, chefe 3) + bônus de importância (trivial −1, comum 0, importante +1, clímax +2) + ameaças únicas`, clamp 1..10. Nunca olha para a party.
- **Potência por categoria** (`data/potency_by_level.json`, `potency_value:66`): valor = `base + incremento × (nível−1)`. Dano: fraco [2,1], moderado [4,2], forte [6,3], devastador [9,4]; dificuldade 9/12/15/18 (+0/+1/+1/+1); duração; reforços. A LLM escolhe só a categoria; `materialize_effect` **descarta** qualquer número recebido (`_NUMERIC_EFFECT_PARAMS`) e recalcula.
- `validate_preparation`: catálogo fechado, base narrativa por objeto, região válida, alvos existentes.
- `build_npc_combat_sheet:335`: NPC ganha ficha completa.
- No grafo real, `_prepare_scene` (`agents/combat.py:270`) monta a cena em Python com uma zona e posições `proximo` — o segundo invoke da LLM foi eliminado (comentário `:288-289`).

### 9.3 Resumo canônico (`services/conflict_summary.py`)

Contrato único entre motor e LLM após o conflito (`ConflictSummary`, 21 campos, `:20-50`): participantes, sobreviventes, mortos, caídos, inconscientes, rendidos, fugitivos, capturados, ferimentos por participante, cicatrizes a gerar, recursos gastos, cartas e resistências descobertas, objetos usados, mudanças permanentes de cenário, companheiros separados, decisões morais, fatos de relação, loot e estado final da party. `conflict_id` determinístico (hash) por instância/epoch/turno. `loot_context` passa o **Nível do Encontro** como `danger` para `economy.roll_loot` (intacta). `validate_narrative_consistency` impede reverter morte→vivo, libertar capturado e restaurar cenário sem novo acontecimento. `summary_facts` gera fatos para o archivist. Ids consumidos são limitados a 64 (`CONSUMED_CONFLICT_IDS_LIMIT:53`) para idempotência de recompensa.

### 9.4 Origem do combate (`services/combat_origin.py`)

Vocabulário fechado: `player_provoked, travel_encounter, regional_danger, arc_pressure, pursuit_recurrence, unknown`. `from_encounter` classifica por `reason` do encontro (reinforcements/controlled/faction_pressure → regional_danger; arc/beat/scripted → arc_pressure; recurrence/chase ativo → pursuit_recurrence; descanso → regional_danger; senão travel_encounter). `materialize` prioriza a dica do estado, depois a origem já gravada.

### 9.5 Conhecimento revelado do inimigo (`services/bestiary_knowledge.py`)

Painel inicial só com campos **públicos** (`_PUBLIC_FIELDS:23-27`: vitalidade, esquiva, Proteção/Integridade, condições, posição…). Cartas usadas e resistências afetadas são **reveladas** e persistem num overlay de runtime por arquétipo (`reveal_card:104`, `reveal_resistance:120`, `apply_persisted_knowledge:140`); Cartas exclusivas de variante (`variant_exclusive_cards`) não propagam ao arquétipo.

---

## 10. Cartas (`services/cards.py`, `data/cards/`, `docs/design/CARTAS.md`)

**Catálogo**: `data/cards/{devoto,sangromante,corruptor,arcanista,medico}.json` (16 Cartas por classe: 7 tronco + 3×3 por subclasse), `tiers_5_plus.json` (80 Cartas tardias), `bestiario.json` (Cartas de inimigo `bst_*`), `exemplos*.json`, `virtude_sugeridas.json`. Gerados por `scripts/gen_cards_v4.py`. Schema (`docs/design/CARTAS.md:14-33`): `tipo` ∈ ativa/passiva/utilitária/reação, `patamar` inicial/avançado/superior, `custo_entropia`, `frequencia`, `virtude_permitida`, `efeito {kind, ...}`, `central` (1 por subclasse: tem Ruptura + Evolução A/B), `apex`.

**Catálogo fechado de efeitos** (`CARD_EFFECT_KINDS`, `cards.py:~28`): dano, dot, cura, estabilizar, protecao, taunt, empurrao, reposicionar, esconder, marca, aplicar_condicao, purga_condicao, contra_ataque, vantagem, buff_defesa/acerto/dano/cura/dot/iniciativa/esquiva, perception, utilitaria, reduzir_carga_aliado e os `bonus_*_por_estagio` das Cartas de Virtude. `mecanica_classe` (`auto_dano`, `pico`, `decadencia`, `resfria_caldeira`) é vocabulário fechado validado por `valid_class_mechanics`.

**Economia**:
- **Acervo** (`known_cards`): Cartas aprendidas. **Preparação** (`prepared_cards`): `prepared_slots_for_level` (`gamedata.py:243`): níveis 1-3 → 4; 4-6 → 5; 7-9 → 6; 10-12 → 7; 13-16 → 8; 17-19 → 9; 20 → 10. Reorganizar é livre **fora de combate** em zona com perigo ≤3 e sem tag apex (`can_reorganize:~232`).
- **Frequência**: livre, turno, cena, descanso_curto, descanso_longo (1 uso por escopo), com **reset em cascata** (descanso longo zera turno/cena/curto/longo) — `FREQ_COUNTER/_RESET_CASCADE`.
- **Custo**: Entropia, com **Dependência** do Arcanista (custo ×2 sem instrumento e Carga ≥ moderado, `combat_mechanics.dependencia_cost:618`).
- **Ruptura** (`use_ruptura:~420`): paga o custo normal, gera **+1 Carga do Abismo** mesmo se falhar; concede Vantagem no ataque (+1) e dá o efeito de `ruptura` da Carta (ou o da evolução). Só Cartas com `ruptura` podem.
- **Evolução A/B** (`evolve_card`): permanente, única por Carta, a partir do nível 4; troca `efeito` e `ruptura` (`effective_card`).
- **Cartas de Virtude** (2 por personagem, fora dos slots): bônus que escala por estágio da Virtude (1 para Virtude ≤2; 2 para ≤4; 3 para 5, `virtue_card_stage`), com Maestria (+até 2 de estágio, total máx. 3 pontos distribuídos).
- **Inimigos**: `use_enemy_card` tem economia própria (`enemy_card_usage`, Entropia do inimigo); `reset_enemy_card_usage("turno")` no início de cada rodada (`conflict_orchestrator.py:1176-1180`).
- **Parity**: guarda de teste `1.5 ≤ dano_base/custo ≤ 4.0` para Carta de dano puro custeada (`docs/design/CARTAS.md:37`).

Exemplo real de Carta central (Devoto/Consagrado, nível 4): *Liturgia da Espera*, ativa, custo 3 Entropia, 1×cena, `protecao` valor 4; Ruptura caminho_a `protecao 8`, caminho_b `taunt 4`; evolução A `protecao 6 / ruptura 10`, B `protecao 4 / ruptura taunt 6` (`data/cards/devoto.json`).

---

## 11. As cinco Posturas, Entropia e Carga do Abismo

Fonte de números: `data/classes.json` (consultado por grep/script). Lógica: `combat_mechanics.py:345-710`. `docs/design/CLASSES.md` agora se declara **histórico**; o catálogo jogável é de Cartas.

### 11.1 Recursos

- **Entropia** — pool único (mana/stamina do jogador = 0). Gastos: Cartas. Recompõe **integral** no descanso (`world_utils.apply_rest:263-264`). Gatilhos de classe a aumentam (ver abaixo), clamp em `max_entropy`.
- **Carga do Abismo** — longo prazo. Sobe por Ruptura (+1), pelos gatilhos de classe (`charge_per`, com `charge_cap` onde há) e por habilidades "de pico". **Não cai no descanso.** Patamares por thresholds `leve 1 / moderado 4 / severo 7` (`abyss_tier:421`).
- **Entropia máxima**: base da classe + `level_gains.entropy` por nível até o 10; do 11 ao 20 só `late_entropy_curve` (ganhos de +1 nos níveis 12, 15, 18, 20; `cap` 36-78 por classe), `progression._entropy_gain_for:73-79`.

### 11.2 Tabela (valores reais de `data/classes.json`)

| Classe | Papel/Postura | Base | Virtudes iniciais | Gatilho de Entropia | Regra especial | Consequência (Carga) |
|---|---|---|---|---|---|---|
| Devoto do Abismo | tank / ama | hp 40, bônus Vit +6, Entropia 14, def 16; +2 Entropia/nível | For 4, Corpo 3, Car 2, Men 1, Agi 1 | `on_damage_taken`: +1 por 4 de dano (mín. 1), +1 Carga/turno até 6 (`charge_cap`), máx. 1/turno | `taunt_scales_with_entropy`: +5% por Entropia, teto +60% | **Insônia**: descanso rende menos Vitalidade (−10%/−25%/−50% por patamar); aliado ativo mitiga (−1 Carga ao descansar) |
| Sangromante | dano cac / negocia | hp 30, +6, Entropia 16, def 12; +3/nível | Agi 4, Corpo 3, Car 2, For 1, Men 1 | `on_self_harm`: 1 Entropia por Vitalidade sacrificada, +1 Carga, máx. 2/turno | `blood_leak`: ao ser acertado, 25% da Entropia "de sangue" vaza | **Cicatriz**: Carta "de pico" reduz Vitalidade máx. permanente (−3) e soma Carga |
| Corruptor | controle/DoT / trabalha junto | hp 30, +6, Entropia 18, def 13; +4/nível | Men 4, Corpo 3, Agi 2, Car 1, For 1 | `on_decay_nearby`: +1 Entropia/+1 Carga, máx. 2/turno; `decay_kind` da subclasse | `domain_decay` (subclasse define o que conta) | **Transformação**: debuff por domínio e patamar (biologia: DoT extra; alma: −save; inorgânica: −defesa), magnitude 1/2/3 |
| Arcanista Cinzento | dano/controle à distância / manipula | hp 26, +6, Entropia 20, def 11; +6/nível | Men 4, Agi 3, Car 2, Corpo 1, For 1 | `on_channel`: +2 Entropia/+1 Carga, 1/turno | `boiler`: 3 turnos sem "vazão" → 2d6 de auto-dano arcano | **Dependência**: sem arma equipada e Carga ≥ moderado, custo de Cartas ×2 |
| Médico de Campo | suporte/cura / nega | hp 30, +6, Entropia 16, def 14; +3/nível | Men 4, Car 3, Corpo 2, Agi 1, For 1 | `on_ally_suffer`: +1 Entropia/+1 Carga até 6, máx. 2/turno | pode gastar 2 Entropia p/ purgar Carga de aliado | **Recidiva**: oculta; ao cruzar **severo**, UM colapso (Colapso: −4 de acerto por 3 turnos, evento de crônica) |

(`hp` e `defense` são campos legados; a Vitalidade real vem de Corpo + `vitalidade_bonus`, ver §12.)

### 11.3 Onde cada mecânica é acionada no loop v4

- `apply_entropy_trigger` (`combat_mechanics.py:442`): consulta a config da classe+overrides de subclasse (`entropy_config:401`, merge de `entropy_trigger/special_rule/abyss` com `branches[x].overrides`), aplica o ganho conforme `kind` (fórmulas acima), respeita `per_turn_cap` e `charge_cap`, aplica `charge_discount` das passivas, e acumula `_blood_entropy` para o Sangromante.
- Em `conflict_orchestrator`: `on_damage_taken` e `blood_leak` após o dano ao jogador (`_resolve_actor_turn:~918-925`); `on_ally_suffer` quando um herói/aliado leva dano e o jogador existe; `on_self_harm`, `on_decay_nearby` (via `mecanica_classe`), `on_channel` + `arm_boiler` e `apply_scar` em `_apply_player_card_mechanics` (`:660-710`); `tick_boiler` e `apply_transformacao` no **início** da rodada (`:1189-1203`); `apply_entropy_on_kill` e `check_recidiva` no **fim** (`:1240-1250`).
- `reset_entropy_turn` no início de cada rodada zera `_entropy_trigger_turn`.
- Insônia: `world_utils.apply_rest:196-205`. Dependência: `cards._entropy_cost`.

### 11.4 Registro anti-órfão

`HANDLED_KINDS` (`combat_mechanics.py:369-380`) lista os kinds de `entropy_trigger`, `special_rule`, `consequence`, `effect` e `passive_trigger` que o motor sabe tratar; um teste compara os JSONs gerados e fica vermelho se aparecer kind novo sem handler. `passive_trigger` inclui `always, damage_type, resist, initiative_attr, heal_bonus_low, melee_retaliate, basic_attack_dot, hp_as_mana, entropy_max_bonus, entropy_on_kill, entropy_cost_reduction, charge_discount, carga_embrace, perception, light`.

### 11.5 Passivas

`player_passives` (`:224`) = passivas de classe (`class_passives`, hoje `passive_effects` vazio em todas as 5 classes) + `learned_passives` (**retorna `[]`** desde o cutover) + passivas de itens equipados (`item_passives:203`). Ou seja, as passivas de "árvore de habilidade" da era anterior ao cutover foram aposentadas; as Cartas `tipo:"passiva"` seguem pelo motor de Cartas (mas ver o achado 1 em §14).

### 11.6 Bônus de early-game

`early_game_damage_bonus` (`combat_mechanics.py:75`): +2 no nível 1-2, +1 no nível 3, 0 depois. Somado apenas ao dano causado pelo **jogador**, tanto em `_resolve_attack_step` quanto em `_basic_attack`. Vem de `docs/` do playtest real `20260720-093014` e é marcado como "piso temporário de agência".

### 11.7 Luz

`world_utils.light_level` (`:888-909`): escuro = período `Anoitecer/Noite` ou tag `dark` no local, **e** o local não é abrigo (`cidade/urbano/abrigo/seguro`). Escuro sem fonte de luz: percepção −3 (`DARK_PERCEPTION_PENALTY`), acerto −1 (`DARK_COMBAT_PENALTY`). Fonte de luz = item com tag `luz` ou passiva `{trigger:"light"}` no equipamento **ou** inventário (tocha/lanterna): anula a penalidade. A penalidade de combate dos **inimigos** em escuro natural continua mesmo se o herói tem luz (`agents/combat.py:775-777`).

---

## 12. Progressão (`progression.py`, `gamedata.py`)

**XP** (`grant_xp:109-197`):
- Por kill: minion 50, elite 200, boss 1000 (`XP_BY_TIER:22`); por beat 150; por quest 200 (constantes). O `type` do inimigo no bestiário (`Minion/Elite/Boss`) é que é lido por `xp_for_kills`.
- Tabela: nível 2 = 300, 3 = 900, 4 = 2700, 5 = 6500, 6 = 14000, 7 = 23000, 8 = 34000, 9 = 48000, 10 = 64000, 11 = 85000, 12 = 100000 … 20 = 355000 (`gamedata.py:165-169`).
- Multi-level em sequência. Por nível: `max_entropy` sobe pela curva da classe (e a Entropia atual sobe o mesmo delta, "level up não é cura grátis"); **Vitalidade não escala com nível** — só Corpo altera o teto (Corpo via escolha de Virtude).

**Escolhas pendentes** (não bloqueiam o loop):
- Nível 3 sem subclasse: `lvl3-subclass` (escolha **irreversível**, `apply_choice:~310`). A subclasse bloqueia as demais escolhas até ser resolvida (`first_required`).
- A cada nível (exceto 20): `lvl{N}-carta` → nova Carta **ou** evolução A/B (`eligible_cards:222`: do tronco + da subclasse escolhida; subclasse só com nível ≥3; `apex` excluído).
- Níveis 2, 4, 6, 8, 10: `lvl{N}-virtude` → +1 numa Virtude, teto 5; escolher Corpo recalcula Vitalidade/espaços de Ferimento na hora.
- Níveis 12, 16, 20: `virtue_mastery` (Maestria; máx. 2 por Carta de Virtude, 3 no total).
- Nível 20: **Ápice** da subclasse concedido automaticamente (`grant_apex_if_due`, ledger `lvl20:apex:<id>`).
- Todo `progression_grants` é um ledger para idempotência; `normalize_player_progression` faz backfill de saves antigos.

**Vitalidade** (`gamedata.sync_vitality:378-415`): `max_vitalidade = max(1, VITALIDADE_POR_CORPO[corpo] + vitalidade_bonus_da_classe − vitalidade_max_penalty)`. O bônus de classe é `base_stats.vitalidade_bonus = 6` nas 5 classes (marcado `[BALANCEAR]` no código). Cicatrizes do Sangromante entram em `vitalidade_max_penalty`. Quando o teto sobe, a Vitalidade atual recebe só o delta; ao baixar, só é clampada.

**Criação**: distribuição fixa (4,3,2,1,1) entre as 5 Virtudes (livre pelo jogador); 6 Cartas no Acervo, 4 preparadas, 2 Cartas de Virtude.

---

## 13. Mundo determinístico (viagem, descanso, clima, encontros, economia)

### 13.1 Relógio e viagem (`world_utils.py`)

- Períodos: Amanhecer, Manhã, Tarde, Anoitecer, Noite (5 por dia, `:10`). `advance_clock` incrementa períodos e vira o dia (`:45-54`).
- `travel_cost` (`:132-151`): interior sempre **0**; sair do interior para o pai também 0; senão `travel_times` do nó atual, com fallback simétrico, default **1**. Viagem com custo >0 avança clima (`advance_weather`) e soma `travel_cost_extra` do clima.
- **Fog of war**: `visited[]` em `world`; destino só aparece se conectado (`find_travel_destination:119`).
- Intenção de viagem/descanso é detectada por palavras-chave PT (`is_rest`, `is_travel_intent`), em Python.

### 13.2 Descanso (`apply_rest:179-267`)

- Clima com `rest_block` (miasma) nega o descanso (só passa 1 período).
- Vitalidade: recupera `max(1, max_vitalidade//2)`, multiplicado pelo fator de Insônia (Devoto).
- `rest_treat_wounds(rest="longo")`: remove todos os Leves; Graves suprimidos; kit médico (`kit_medico`) suprime Graves; Médico trata Críticos.
- Integridade de armadura/escudo: recupera tudo (longo). Cartas: `descanso_longo` zera todos os contadores de uso. Consciência pós-combate recalculada.
- Entropia **integral**; Carga **intacta**; avança 2 períodos + clima.

### 13.3 Encontros (`check_encounter:712-789`)

Gatilho determinístico (sem LLM): alerta de fuga ativo (reforços); facção hostil dominando o local; `looming_threat` com perigo ≥3; ou perigo efetivo ≥4. Cooldown entre encontros = 2 turnos, **+2 no early-game** (nível ≤3). `forced_encounter_danger` (`:698`): a **força** do encontro escala com o nível — `min(perigo, (nível+3)//2)` — exceto zona apex (força cheia); o **trigger** usa o perigo real. Descanso de nível ≤3 em zona **não apex** com perigo ≤3 **não sorteia encontro** (`recovery_rest_safe:519`).

**Orçamento** (`encounter_budget.py`): custo por tier: minion 2, elite 5, boss 12; base por perigo {1:2, 2:4, 3:7, 4:10}; `budget = base + nível + 2×aliados`, com **teto de sobrevivência** `5 + 3×nível + 2×aliados` (`:18-36`). `clamp_encounter` nunca corta boss, prioriza variedade, no nível 1 mantém no máx. 1 elite; `fill_encounter` reforça encontros fracos até o piso `budget//2` com criaturas regionais.

**Tipos de encontro** (`roll_encounter_type`, `:978`): perigo ≤2: combate 50 / rastro 30 / social 20; perigo ≥3: combate 60 / armadilha 20 / social 10 / rastro 10. **Detecção** (`detection_check:958`): `d20 + mod(Mente) + bônus racial + passivas de percepção + mod do clima/luz` vs **CD = 8 + 2×perigo(1..4)**; percebeu → vantagem para você; falhou → surpreendido. **Armadilha** (`resolve_trap:987`): `d20 + mod` vs CD `10 + 2×perigo`; sucesso = +25 XP; falha = dano `{1:2,2:3,3:4,4:5}` pelo pipeline de dano + condição temática, com disparo do fluxo terminal se encheu o crítico.

(Observação: detecção e armadilha ainda rolam **d20**, ver §14, achado 4.)

### 13.4 Clima (`world_utils.py:795-950`)

Cadeia de Markov por região (`data/weather.json`), que avança sempre que o período muda. **Fenômeno global** (Tempestade de Éter, Noite Sem Estrelas…): sem evento ativo, a cada transição de período sorteia com chance `0,06 + 0,03×(perigo−1)` (`GLOBAL_WEATHER_*`); dura `duration_periods`. `weather_effects` agrega: `perception_mod`, `combat_attack_mod`, `travel_cost_extra`, `rest_block`, `dot_outdoor` (zerados em local abrigado). O combate aplica `combat_attack_mod` e `_apply_weather_hazard` (`agents/combat.py:1107`) aplica o DoT externo antes da rodada.

### 13.5 Economia (`services/economy.py`)

- **Preço-base**: `value_gold` do item; senão por raridade: comum 25, incomum 100, raro 400, épico 1500, lendário 6000 (`RARITY_BASE:45-51`).
- **Preço final** (`price:139-156`): `base × supply_factor × price_mult do mercador × (1,5 se comprador e a facção que controla o local é hostil) × (0,5 se venda)`, arredondado ao múltiplo de 5 (`_round5`). `supply_factor`: **0,6** se o local produz o item (`economy_tags` em comum); **1,0** se há produtor alcançável (BFS no mapa menos rotas bloqueadas); **1,8** se todas as rotas até produtores estão bloqueadas — e nesse caso o item **some** da prateleira (`merchant_stock:212-232`).
- **Mercadores**: estoque por `base_stock`, reposição determinística a cada `restock_days` (default 3) pelo relógio. Local hostil esconde itens raros+. Item único já reclamado some, exceto se o dono é o mercador (recomprável).
- **`execute_trade`**: Python decide sinal e quantidade do ouro (nunca o LLM); venda de único faz o mercador "segurar" o item e registra evento; compra de único registra posse.
- **Craft** (`execute_craft`): valida local (`craft_tag`), classe, ingredientes e ouro; recusa craft de único já existente.
- **Loot** (`roll_loot:436-462`): raridade sorteada por banda de perigo (1-2 vs 3-4), pools regionais, único já reclamado removido do pool ANTES do sorteio, drops de criaturas "suprimidas" somem, ouro `randint(3,12) × perigo`.

### 13.6 Exploração (`services/exploration.py`)

Ao chegar num **local novo** (fog of war): baú curado `treasure` do mapa tem prioridade (one-shot via `world.looted_locations`, pode ter único); senão achado ambiental com chance `min(0,5; 0,12 + 0,08×perigo)` via `roll_loot`, sem nunca conceder único (`discovery_chance:31`, `roll_discovery:36`). O RNG é estável por `sha256(game_id|local|turno)` (`arrival_rng:24`), logo reproduzível entre processos. O narrador só descreve o que a função concedeu.

### 13.7 Ecologia e descoberta

`ecology.hunt_pressure` (`:29-43`): pressão de caça [0,1..1,0] por criatura a partir de `defeated` e do tempo desde a última atualização: 6+ kills → 0,1; 3+ → 0,3; 1+ → 0,6; kills "quentes" (≤10 turnos) contam inteiros, entre 10-20 contam metade, >20 turnos: população volta a 1,0. Criatura com pressão ≤0,3 fica "suprimida" (sai do sorteio e seus drops somem do loot regional); facção que controla o local dá ×2 às suas criaturas; vagas abertas atraem migrantes (peso 0,5) de regiões conectadas sem rota bloqueada. `discovery.knowledge_tier` do bestiário do jogador: 1 Rumores (visto 1), 2 Encontrada (lutou 1), 3 Estudada (3 derrotas), 4 Dominada (7 derrotas).

### 13.8 Party e aliados (`party.py`)

- Recrutamento: relacionamento ≥ **7** (modulado por traço de persuasão, clamp 3..10) ∧ party ativa < **3** ∧ facção não hostil (`recruitment_decision:283`).
- **Aliado de cena** (`scene_allies:242-280`): NPC `in_scene` com relacionamento ≥ **6**, facção não hostil, vinculado ao local atual e ainda fora da party formal vira combatente **transitório** (máx. **2**), reflete dano no NPC e some no fim; não vira party permanente.
- `make_companion_from_npc` gera ficha de combate v4 completa; arquétipo derivado de palavras do papel (guerreiro/arqueiro/curandeiro/mago, `_ARCHETYPE_WORDS`).
- Comandos de party detectados por texto (`PARTY_COMMANDS`).

### 13.9 Inventário (`inventory.py`)

Entradas `{id, qty}`, empilhável por tipo (consumable/potion/material/currency), slots `weapon/armor/accessory`, único por `is_unique`. `use_item_in_combat` (`:178-262`) é a única parte ainda com `d20` de salvaguarda (alvo de debuff: `d20 + mod` vs `save_dc`, default CD 12, `inventory.py:253-255`) e a cura é uma fórmula de dados `XdY+Z` via `roll_dice_numeric`. Itens ofensivos (`debuff/dot/control`) vão para o inimigo; buffs para o próprio usuário.

---

## 14. Checkpoints e morte do jogador (`services/checkpoints.py`)

- **Cadência**: grava a cada **10 turnos** (`CHECKPOINT_EVERY`) ou ao entrar em zona segura (mudar de local e perigo ≤1). Nunca grava se o estado não está "pronto" (`transition_readiness`: combate ativo, Última Ação, Terminal, death pending ou morto).
- **Snapshot** inclui o estado profundo, marcador de continuidade e a memória FAISS da sessão (`capture_session_memory`) para que o restore reverta os fatos pós-checkpoint.
- **Slot único** por save (sobrescreve). `resolve_death_choice`:
  - `accept` → memorial: `game_over=True`, `death_pending=False`, adiciona `player_died` ao `event_log` (id hash determinístico) e marco de crônica.
  - `continue` → restaura do checkpoint (in-memory no harness, senão em disco; senão início da sessão), sanea transições órfãs, atualiza `continuity` (epoch de linha do tempo).
- Sem permadeath imposto: memorial é só a via voluntária "Aceitar".

---

## 15. Modo simulação de combate (`combat_simulation`)

Laboratório de combate para o frontend, sem LLM de campanha.

- **Opções** (`api.py:~1325-1335`, `GET /data/combat-simulator`): classes de `gamedata.CLASSES`, níveis **[1, 3, 5, 10]**, quantidade **[1, 2, 3]**, inimigos do bestiário.
- **Criação** (`_build_combat_simulator_state`, `api.py:1337-1470`; `POST /game/combat-simulator`): `create_player_character(... level=req.level, use_llm_flavor=False)` — personagem de produção, sem LLM —, cópias do inimigo do bestiário com id `{enemy}__sim_{n}`, cena com 1 zona "arena" (`distance_state="proximo"`, cena congelada), mundo `starting_world("Nova Arcádia", nível)` com perigo derivado da categoria (lacaio 1, padrão 2, elite 4, nomeado 5, chefe 6), `combat.active=True`, `idle_turns=0`. Estado marcado `combat_simulation: {enabled: true, enemy_id, quantity}`.
- **Curto-circuitos**: `campaign_manager` retorna cedo (sem plano/RAG, `agents/campaign_manager.py:256`); o grafo encerra após `combat_agent` (sem loot nem archivist, `main.py:122-131`); `combat_node` não faz XP/loot (`"next": "loot" if victory and not is_simulation`, `agents/combat.py:~987`); `_write_checkpoint_if_due` não grava (`api.py:2313`); texto livre vira ataque básico no primeiro alvo (`api.py:2354-2360`), sem consultar provider; save é listado com selo próprio (`persistence.py:325/347`).
- **O que roda de verdade**: o mesmo `run_round` de produção — Cartas, Reações, Ruptura, manobras, Vitalidade, Ferimentos, zonas, IA tática inimiga, Última Ação, Estado Terminal.

---

## 16. Inconsistências, mecânicas possivelmente mortas e riscos (achados verificados)

1. **Buffs de Carta aparentemente sem efeito na resolução v4.** `_resolve_support_card` (`conflict_turn.py:353-362`) grava condições com `stat` ∈ `{protection, advantage, ac, attack, damage}` e `delta`. Em produção, o único leitor de `stat/delta` é `condition_modifiers` (`combat_mechanics.py:233-249`), usado só por `compute_player_combat_stats` (exibição na API, `api.py:2667`) e pelo save de `use_item_in_combat`. Não encontrei consumidor de `ac/attack/damage/protection/advantage` em `resolve_attack`, `compute_esquiva` ou `resolve_damage_and_wounds`. Cartas de `protecao` (ex.: *Muralha Viva*, *Liturgia da Espera*), `buff_defesa`, `buff_acerto`, `buff_dano` e `vantagem` parecem ser pagas (Entropia, frequência) e narradas sem alterar números. Vale um teste de integração que prove (ou desminta) o efeito.
2. **Armadura/escudo do jogador não são instanciados no jogo.** `make_armor/make_shield` (`gamedata.py:224/234`) só têm chamadas em testes; `resolve_damage_and_wounds` lê `target["armor"]`/`["shield"]` dicts, e nenhum bestiário tem `armor` (0 de 124). O equipamento do jogador é por **id** com `ac_bonus` legado (`inventory.py`). Logo Proteção/Integridade/Comprometida só entram em fichas construídas manualmente (testes/sim). Também `penalidade_esquiva` da armadura (nome da chave em `ARMADURAS`) não é lida por `compute_esquiva`, que usa `esquiva_penalidade` (nome distinto).
3. **Ataque básico do jogador = 3 flat.** Como `dano_base_arma`/`attack_formula` não são populados em produção, o dano sem Carta ignora a arma equipada; só o bônus early-game (+2/+1) o destaca. As Cartas autorais carregam o dano real.
4. **Resíduos d20.** `detection_check`, `resolve_trap` e a salvaguarda de `use_item_in_combat` ainda usam d20 + modificador (e `attr_mods` com `(score−10)//2` para inimigos legados). Coerente com "não migrado", mas diferente da regra 2d10 + Virtude do restante do sistema.
5. **Fuga: abordagem e Sorte não ligados.** `chase.approach_virtude` e `luck_to_advantage` existem e são testados, mas `_attempt_flee` fixa Agilidade e não passa `companion_luck` (`agents/combat.py:1089-1093`).
6. **Evento do Abismo em combate depende de `scene["abyss_events"]`**, que `_prepare_scene` (geometria Python) deixa vazio; a camada de eventos preparados pela LLM existe e é testada, mas hoje não é alimentada no fluxo real.
7. **Documentação desatualizada.** `docs/design/CLASSES.md` (cabeçalho) se declara histórico; ainda cita `player_abilities.json`/`known_abilities`. `progression.py:21` diz "nível máximo 10" enquanto `NIVEL_MAX = 20`. `services/chase.py:10-13`, `reactions.py:11-13`, `abyss_events.py:15-16` descrevem "aditivo, fiação no cutover" embora o cutover tenha ocorrido (parte já fiada, ver itens 5 e 6).
8. **Taunt do inimigo**: a escolha de alvo ocorre em `enemy_declaration` (antes de rolar a condição de controle `taunt` do próprio turno), e a condição precisa vir de Carta `taunt` ou `marca` que passe `control: kind` (`conflict_turn.py:_apply_attack_card_effect`); funciona, mas só para inimigos que estejam sob a condição `taunt`.
9. **"Proximo" como proxy de alvo.** `_nearest_target` ordena por Agilidade e não por posição: como todos nascem em `proximo` na mesma zona (`_prepare_scene`), o eixo Distância e as zonas quase não alteram o resultado em combates reais (apenas em cenas preparadas por LLM ou no uso de manobras).
10. **Teto de nível 20 sem conteúdo equivalente em todas as partes**: níveis 11-20 usam `tiers_5_plus.json` (80 Cartas) e `late_entropy_curve`; `prepared_slots_for_level` chega a 10 (`docs/design/CARTAS.md` menciona até nível 10/7 slots — documentação antiga).

---

## 17. Mapa de arquivos relevantes (resumo)

| Tema | Arquivo | Ponto de entrada |
|---|---|---|
| Nó de combate | `agents/combat.py:607` | `combat_node` |
| Rodada | `services/conflict_orchestrator.py:1135` | `run_round` |
| Turno | `services/conflict_turn.py:56` | `resolve_turn` |
| Ataque/iniciativa | `services/conflict_resolution.py:135` | `resolve_attack`, `roll_initiative_by_side` |
| Dano/Ferimentos | `services/conflict_damage.py:204` | `resolve_damage_and_wounds` |
| Cena | `services/conflict_scene.py` | `place`, `engage`, `hide`, `guard` |
| Reações/AoO | `services/reactions.py:83,173` | `offer_reaction`, `trigger_opportunity_attack` |
| Fuga | `services/chase.py:135` | `resolve_chase_round` |
| Morte | `services/death_flow.py:171` | `attempt_stabilization` |
| IA inimiga | `services/tactical_profile.py:208` | `pick_action` |
| Abismo | `services/abyss_events.py:112` | `select_event`, `trigger_event` |
| Encontro | `services/encounter_preparation.py:40` | `compute_encounter_level` |
| Resumo | `services/conflict_summary.py:121` | `build_summary` |
| Cartas | `services/cards.py` | `use_card`, `use_ruptura`, `evolve_card` |
| Classes/Entropia | `combat_mechanics.py:442` | `apply_entropy_trigger` |
| Progressão | `progression.py:109,285` | `grant_xp`, `apply_choice` |
| Mundo | `world_utils.py` | `apply_rest`, `check_encounter`, `light_level` |
| Economia | `services/economy.py:139,311,436` | `price`, `execute_trade`, `roll_loot` |
| Orçamento | `encounter_budget.py:17` | `encounter_budget`, `clamp_encounter` |
| Checkpoints | `services/checkpoints.py` | `maybe_write`, `resolve_death_choice` |
| Simulação | `api.py:1337` | `_build_combat_simulator_state` |
