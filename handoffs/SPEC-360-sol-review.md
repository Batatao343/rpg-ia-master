# SPEC-360 — revisão sol (review)

> **Veredito:** rodada 1 `CHANGES_REQUIRED` (`31fdeee1`) → **rodada 2 `APPROVED_WITH_FOLLOWUPS`** (`eb5e3778`)
> **Revisor:** Opus 5.5 / papel Sol (técnico: motor, estado, determinismo, integridade de eval) · **Data:** 2026-11-02 · **Commits revisados:** `31fdeee1`, `eb5e3778`

## Escopo

Branch `spec-360` sobre `spec-349 @ 830fb496`, intervalo `830fb496..31fdeee1` (commits
`0bae0f3a` golden, `731f49ff` avaliador, `fa2fefbd` protected-paths, `25a2dc56`
schema/lint/build/fauna, `31fdeee1` motor/integração/flags). Lidos: `services/fauna.py`,
`world_utils.py` (pick/check_encounter/resolve_track), `agents/storyteller.py`,
`agents/combat.py`, `persistence.py`, `services/rumors.py`, `services/fauna_lint.py`
(E16), `playtest/invariants.py`, `config/flags.yaml`, `scripts/fauna/eval.py`,
`tests/test_spec360_*.py`, `data/world/fauna_config.json`, relatório do eval.
Fora: qualidade autoral dos sinais (é do revisor de fauna,
`handoffs/SPEC-360-independent-review.md`) e smoke real (§6, coordenador).

## Integridade de eval: conclusão

- **Ordem dos commits ok.** `git diff --stat 731f49ff..31fdeee1 -- scripts/fauna/eval.py tests/test_spec360_eval.py`
  está vazio: o avaliador e os limiares não mudaram depois do congelamento. A proteção
  D6 (`fa2fefbd`) vem logo em seguida. O golden `off` (`0bae0f3a`) também não foi tocado.
  Os limiares literais do teste batem com D4.
- **O avaliador não é trivial**, mas confia em estado do produto. O M2, o M3 e o M4 são
  exatos (pesos reais via `encounter_distribution`) e não dá para burlar sem mudar o
  sorteio. O M5 compara on×off com as mesmas sementes e confere `triggers` iguais (R9).
  O M6 tem lista de tokens própria (não usa o lint). Já o M1 "precedido" lê
  `presence.sinais_mostrados` e `enc["presence_id"]`, que são escritos pelo produto. Um
  `scene_block` que gravasse sinal sem emitir texto passaria. Hoje não é o caso (conferido
  no código), mas o M1 não tem oráculo próprio. Fica como P2 para o coordenador,
  porque o arquivo é protegido.
- **Calibração.** `HORARIO_FORA` 0,25→0,2 e `PREDADOR_FAMINTO` 0,5→0,45 são folga
  legítima. `TERRITORIO_FORA` 0,4→0,02 usa uma alavanca prevista (`[BALANCEAR]`), mas o
  efeito colateral é real (P1-1). Juntos, `P_PRESENCA` 1,0, `MAX_PRESENCAS_REGIAO` 2→4
  (1 por nó) e permanência +4 dias saturam Nova Arcádia: há presença ativa praticamente
  sempre em todo nó, e o eval mostra 2367 sinais em cena em 4800 ações (~49 %). Isso
  satisfaz o M1/M5 sem esvaziar o "sinal antes", mas enfraquece o "evitar" (R19), que
  nenhuma métrica guarda (P2-1). Não é gaming do avaliador. É Goodhart num eixo que não
  é medido, e a decisão é de design (coordenador/dono) antes de ligar a flag.
- **R16 estendido** (presença ativa sem sinal + `cedo` → mostra o 1º sinal, sem
  combate): é coerente com o pilar do dono ("o encontro é anunciado"). Sem ele, uma
  presença nascida no dia vira luta na 1ª chegada, sem anúncio, o que contradiz a
  intenção. O custo em combate fica dentro do M5 (−16 %). Aceito, e está registrado na §9.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `world_utils.py:1138` (+ `data/world/fauna_config.json:5`) | Criatura sem entrada em `fauna.json` recebe fator 1,0, enquanto a fauna fora do território recebe 0,02. O fator "neutro" vira um bônus de até 50×. Medido com `encounter_distribution` (on, perigo 3): `enemy_assassino_cinzeu` (retro da Pradaria, sem fauna) fica com 16 % das escolhas em `na_anel_dourado`, 12 % em `na_anel_lama` e 21–25 % no nó `nova_arcadia`, contra ~3 % com a flag `off`. Esses combates não têm sinal nem aproximação e ficam fora do denominador do M1 (`combats_with_entry`). Na 360-B/361 o mesmo vale para toda criatura gerada em runtime e todo migrante. | Normalizar o fator de quem não tem entrada pelo contexto: por exemplo, usar a média (ou a mediana) dos fatores ecológicos das candidatas com fauna naquele local e período. Assim a fatia relativa do legado se mantém. Isso também sobe o M4 e deve permitir voltar `TERRITORIO_FORA` para um valor mais macio. Teste: com a flag `on`, a fatia de quem não tem fauna no pool fica a ≤ 1,5× da fatia com `off`. Registrar na §9. |
| P1-2 | P1 | `tests/test_spec360_flags_off.py:55,99` (R26) e o playtest de R29 | O `explorador` com `seed=0` joga os 30 turnos em Skallgard (golden: `location: sk_fortaleza_vorr`), onde não existe fauna. A contagem de `invoke` on×off e o playtest de 50 turnos sem violação **não exercitam** presença, conversão, caça nem `scene_block`, então são verdes por vacuidade. Os critérios de R26 e R29 estão marcados `[x]` com essa evidência. Há ainda a ressalva de que, quando a fauna atuar, a conversão troca um turno de combate por narração e o total de chamadas muda. O R26 é "0 chamada nova **por turno**". | Novo teste (fora do arquivo protegido): campanha MockLLM curta que começa em `na_anel_lama` (save/estado inicial forçado, `RPG_WORLD_ENGINE=on`, flags `on`). Asserir que (a) houve ≥ 1 sinal, ≥ 1 conversão ou caça e ≥ 1 combate de fauna; (b) por rota/tipo de turno, `invoke` ≤ o do mesmo tipo com `off` (nenhum turno faz chamada extra). Rodar o invariante `fauna_presenca_valida` nessa campanha (R29). A mini-campanha scratch da §9 pode virar esse teste. |
| P2-1 | P2 | `data/world/fauna_config.json:14-15`; `services/fauna.py:465` | Saturação: com `P_PRESENCA` 1,0, 4 presenças por região (1 por nó) e TTL de ~1 semana, toda chegada em Nova Arcádia tem presença. O R19 "evitar" perde sentido e o regex de caça (`fauna.py:676`, que casa com "caçar"/"rastrear" em qualquer contexto) quase sempre acha presença com sinal, então "vou caçar coelhos" abre combate com surpresa. Além disso, a spec ainda diz "(2)" em R13 (`spec:76`) e "≤ 2 presenças por região" em §3.6 (`spec:277`). | Decisão do coordenador/dono antes de ligar a flag: aceitar a densidade ou baixar `P_PRESENCA` e escolher outra alavanca. Atualizar R13/§3.6 para o valor final. Medir no smoke §6 a fração de cenas com sinal. Para a 360-B, sugerir ao coordenador uma métrica de densidade (sinais/cena ≤ X) numa revisão do avaliador. |
| P2-2 | P2 | `world_utils.py:995-996` | A semente do sorteio ponderado com a flag `on` é `turn|loc|day|period`, sem `game_id`. Duas campanhas no mesmo turno, local e relógio sorteiam a mesma criatura. O hook diário usa `day_rng(game_id, …)`, então fica inconsistente. | Incluir `game_id` (via `world_sim`/`world` ou um parâmetro) na chave. O M7 continua determinístico. |
| P2-3 | P2 | `services/fauna.py:70`; `agents/combat.py:3238`; `services/fauna.py:666` | O modo `shadow` não é só log. Com `RPG_FAUNA=shadow` + `RPG_FAUNA_SINAIS=on`, as presenças, a conversão em sinal e a preferência por presença (via `ptheme`) mudam o jogo. E, mesmo com `SINAIS=off`, o `shadow` grava carcaças em `world_sim.fauna`. O R12 diz que `shadow` "usa o resultado legado e registra". | `sinais_mode()` deve tratar `shadow` como `off` (ou documentar o modo misto na spec), e `record_kill`/`_fauna_carcasses` devem gravar só com `mode()=="on"`. Teste: com `shadow` + `SINAIS=on`, `check_encounter` é igual ao `off`. |
| P2-4 | P2 | `services/fauna.py:148` | `_cap_presences` mantém `(active + rest)[:12]` na ordem de inserção. Acima de 12 ativas, a presença que acabou de nascer é descartada depois do log `presenca_nasce`. Com 1 região não acontece, mas na 360-B (12 regiões × 4) acontece. | Priorizar ativas mais novas ou a região atual. Ou limitar no `day_hook` pelo cap global antes de nascer. Follow-up da 360-B. |
| P2-5 | P2 | `services/fauna_lint.py:360-377` | O E16 lê `content_validator._default_leak_phrases` por `getattr` com `except: pass` silencioso, porque a fonte da 350 não existia na base `spec-349`. Na `main` ela existe (`services/leak_phrases.all_phrases()`, `data/world/leak_phrases.json`). Conferi `fauna.json` contra as 38 frases da `main`: **0 ocorrência**. | No rebase sobre a `main`, importar direto `services.leak_phrases.all_phrases()` (fonte única, sem `getattr`/`except`), rodar `lint.py --regiao nova_arcadia` e `tests/test_spec348_leaks.py`, e atualizar o desvio 6 da §9. |
| P2-6 | P2 | `world_utils.py:1457` | Se há presença no local mas o sorteio cai noutra criatura `cedo` (o `hunt_theme` não garante a da presença), o combate começa sem anúncio daquela criatura e sem conversão. É fiel à letra de R16 ("local sem presença"), mas não ao pilar. | Opcional: converter também quando `cid != presence.creature_id` e a criatura sorteada é `cedo`, ou forçar `entry` = criatura da presença quando ela cabe no porte (R15). Reavaliar com o eval. |
| P2-7 | P2 | `agents/combat.py:3234` | `_fauna_carcasses` (R11) não tem teste pelo `_combat_node`, só pelo `record_kill` unitário. R11 "carcaça arrastada" e o gatilho de rumor com `criatura_avistada` (R15) não foram feitos, e estão registrados na §9 (desvios 5 e 7). | Teste de integração: morte de `mon_*` no combate → `result["world_sim"]["fauna"]["carcacas"]`. Levar a carcaça arrastada e o R15-rumor para a 360-B ou a 360-C, com ID. |
| P2-8 | P2 | `scripts/fauna/eval.py:284-286` (protegido) | O M1 usa o estado do produto como oráculo (ver acima), e o M7 no teste roda só 3×12 dias. | Só o coordenador mexe: registrar os sinais emitidos por presença no próprio avaliador e rodar o M7 no tamanho do relatório. |

**Conferido sem achado:** writer único de `world_sim.fauna` (todas as mutações passam por
`services/fauna.py`; o combate devolve `world_sim` só com carcaça e o archivist não o
escreve); round-trip de save/load (`persistence._load_world_sim` + teste); save antigo
sem a chave; presença de criatura removida descartada com `log_fallback`; flags
`off` = mesmo caminho de antes (o storyteller só passa `world_sim` com `mode()!="off"`,
`scene_block` devolve `""`, combate devolve `None`); `config/flags.yaml` com as 2 flags
`release`, `off`, `expires: 2027-03-01`; telemetria só com ids (sem texto de sinal nem
segredo); nenhum `with_structured_output` novo; nenhum valor de LLM consumido pelo motor;
`bestiary.json` intocado; `rumor_seeds.json` regenerado só com `sinal_rumor`.

## Correções aplicadas

Executor (02/11, commit da rodada de correções): P1-1 (fator neutro = média das candidatas com fauna; teste ≤ 1,5× do `off`; `TERRITORIO_FORA` 0,02 → 0,05), P1-2 (campanha no Anel de Lama pelo grafo, comparação turno a turno com o mesmo estado `off`, invariante limpo), P2-1 (`P_SINAL_CENA` 0,35 e `P_PRESENCA` 0,6: sinais em cena 49 % → 25,1 % das ações), P2-2 (`game_id` na semente), P2-3 (`shadow` só registra; carcaça só com `on`), P2-5 (import direto de `services.leak_phrases` com fallback logado), P2-6 (conversão também com presença de outra criatura; a da presença vence a pressão de caça quando cabe no porte). P2-4 e P2-7 registrados para a 360-B/C. Eval M1–M7 verde sem tocar o avaliador; números na §9 da spec.

## Pendências

- P1-1 e P1-2 antes de `done`.
- P2-1 (densidade): decisão do coordenador/dono antes de ligar `RPG_FAUNA_SINAIS` em staging.
- P2-4, P2-6, P2-7 (R11 arrastada, R15 rumor): follow-ups da 360-B/C.
- P2-5 no rebase sobre a `main`.
- P2-8: coordenador (arquivo protegido).
- Revisão de fauna independente (38 entradas `revisao: pendente`). Deve conferir também as
  mudanças de conteúdo feitas por quem otimizou o eval (permanência +4 dias nas não-BOSS;
  nó central para `rato_peste`, `cao_rebite` e `degolador`) contra a prosa da ficha (P5).

## Comandos rodados

```text
git diff --stat 731f49ff..spec-360 -- scripts/fauna/eval.py tests/test_spec360_eval.py → vazio (avaliador intocado)
git log -- tests/fixtures/spec360_flags_off_golden.json → só 0bae0f3a
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_spec360_{schema_lint,build,eco,presenca,sinais,caca,rumor,saves,flags_off,eval}.py → 105 passed (163 s)
scratch encounter_distribution (RPG_FAUNA=on, perigo 3, 4 nós × Manhã/Noite) → assassino_cinzeu 6–25 % por nó (P1-1)
scratch fauna.json × main:data/world/leak_phrases.json (38 frases) → 0 ocorrência (P2-5)
```

## Rodada 2 (`32dfcc84`, `eb5e3778`): `APPROVED_WITH_FOLLOWUPS`

**Integridade.** `git diff --stat 731f49ff..eb5e3778 -- scripts/fauna/eval.py tests/test_spec360_eval.py tests/fixtures/spec360_flags_off_golden.json`
continua vazio. Os limiares e o golden estão intocados. Desta vez o executor mudou só
constantes `[BALANCEAR]`, conteúdo (o F-01…F-15 do revisor de fauna) e código de produto.
A edição que ele fez neste parecer se limitou à seção "Correções aplicadas" e ao nome do
handoff de fauna, o que está ok.

**P1-1 (fator neutro): resolvido, e a calibração está boa.** `world_utils.py:1138-1149`
dá a quem não tem fauna a média dos fatores das candidatas com fauna no mesmo contexto.
Nas contas, a fatia dele volta para ~1/(n+1), a mesma do `off`. O teste dos 4 nós × 2
períodos (≤ 1,5× do `off`) confirma. Na simulação do eval, quem não tem fauna caiu para
**3 de 601** combates (0,5 %), contra 6–25 % das escolhas antes. Com isso o
`TERRITORIO_FORA` voltou de 0,02 para 0,05, e o M4 subiu para 0,854.
Resta uma observação menor (P2-9): o migrante entra com peso fixo de 0,5, sem passar pelo
fator neutro, então fica relativamente mais pesado quando a fauna cai fora do território.
Em Nova Arcádia o limiar de migrante não dispara. Conferir na 360-B.

**P1-2 (custo): resolvido, e a comparação é honesta.** Rodei a campanha do teste com
sonda (cópia sem asserts, na scratchpad). Resultado:
- `extra` vazio: nenhum turno `on` chamou a LLM mais vezes que o mesmo turno `off`;
- 3 caças, com chamadas `on`/`off` de (4/2), (4/2) e (4/4);
- inícios de combate comuns no `off` custaram 3 chamadas cada;
- `fauna_presenca_valida` sem violação; 7 sinais, 3 encontros, todos precedidos.

A caça custa 4 contra 3 de um início de combate comum. A chamada a mais é a do roteador,
que classifica o texto livre "sigo o rastro". O "descanso aqui" segue o caminho
determinístico e não passa pela LLM. No turno de caça, o próprio `off` já paga essa
chamada do roteador (2 = roteador + narrador). Então a caça custa exatamente "texto livre
+ início de combate" e não acrescenta nenhuma chamada da fauna. O `+1` do assert
(`max(hunts) <= max(off_starts) + 1`) é justificado, embora frouxo. Melhoria sugerida
(P2-10): asserir `hunt_on == off_start + router`, medindo o roteador à parte.

**ANUNCIA_PRESENCA_NOVA desligada: medi quantas lutas acontecem sem sinal.** Sonda na
simulação do eval (20 seeds × 60 dias, `on`), 598 combates de criaturas com fauna:

| Antecedência | Situação | Combates |
|---|---|---|
| `cedo` | presença com sinal antes (dia 273 + conversão 166) | 439 |
| `cedo` | **presença nascida no dia, ainda sem sinal → luta direto** | **115** |
| `imediato` | com sinal antes | 12 |
| `imediato` | sem sinal (por design: emboscada) | 32 |

- M1 = 451/598 = 0,754.
- Das lutas contra criaturas `cedo`, **20,8 % (115/554) começam sem anúncio**. É
  exatamente o caso que o desvio da R16 cobria.
- Ligar o anúncio converteria essas 115 lutas e derrubaria o M5 para ~−0,25 (fora do piso
  de −0,20). Ou seja, há conflito real entre dois limiares que o dono aprovou: M1 ≥ 70 %
  ("sinal antes") e M5 ≥ −20 % ("não menos luta").

Parecer: **não contraria o pilar no nível que o dono quantificou**. O D4 aprovou M1 ≥ 70 %,
não 100 %, e o resultado fica dentro disso. Mas a folga é pequena (5,4 pp) e o pilar fica
mais fraco do que na rodada 1 (81 %).

Registro como decisão do coordenador/dono (P2-11), com três opções:
- (a) aceitar ~21 % das lutas `cedo` sem anúncio;
- (b) religar o anúncio e aceitar M5 ≈ −0,25. Isso exige que o coordenador reabra o
  limiar, nunca o executor;
- (c) alavanca intermediária: fazer o encontro cair num turno seguinte ao 1º sinal, por
  exemplo o 1º sinal da presença nova sair na cena **antes** do gatilho na mesma chegada.
  Isso muda a ordem do turno e pede spec.

A favor de (a): nenhuma luta com presença sem sinal acontece sem a `aproximacao`
(M1 aproximação = 1,0), então o jogador ainda vê a criatura chegar.

**Demais correções conferidas:**
- P2-2: o `game_id` entra na semente (`world_utils.py:997`), e o storyteller o passa.
- P2-3: `sinais_mode()` exige `on`; carcaça só com `on` (`fauna.py:674`, `combat.py:3238`).
- P2-5: import direto de `services.leak_phrases`, com fallback logado.
- P2-6: `_presence_entry` dá preferência à criatura da presença quando ela cabe no porte, e
  a criatura `cedo` de outra presença converte.
- P2-1: densidade de 49 % → 25 % (29,8 % com as conversões), com `P_SINAL_CENA`
  determinístico por (pid, turno). A spec R13/§3.6 está atualizada.

**Follow-ups:** P2-4, P2-7 e P2-9 vão para a 360-B; P2-10 é teste; P2-11 é decisão do
dono/coordenador antes de ligar a flag; P2-8 é do coordenador (avaliador protegido).

```text
git diff --stat 731f49ff..eb5e3778 -- eval.py, test_spec360_eval.py, golden → vazio
sonda P1-2 (campanha Lama, sem asserts) → extra=[], caças (on/off)=(4/2),(4/2),(4/4), off_starts=3, 0 violação
sonda M1 (eval on, 20×60) → 598 com fauna: 451 precedidos; 115 cedo sem sinal; 32 imediato sem sinal; 3 sem fauna
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 -q tests/test_spec360_*.py (10 arquivos) → 112 passed, exit 0
```
