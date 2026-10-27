# SPEC-339 — Controle aplicado por oponente expira antes de valer (tick de duração)

> **Status:** `done`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Depende de:** SPEC-232 (`done`, expiração de buff/debuff no fim do turno), SPEC-329 (presságio), SPEC-330 (golden de equivalência das 308 Cartas). Para a Etapa 5, SPEC-335 com o lint provisório de `taunt`/`marca` já pousado na `main`.
> **Desbloqueia:** Cartas de onda (SPEC-335/336) com `taunt`/`marca` de `duracao` 1; rebalanceamento do Devoto (Provocar).

---

## 1. Contexto & Objetivo

A revisão Sol do Lote 5 da SPEC-335 achou o problema, e o coordenador o confirmou com `run_round`: um controle de `duracao` 1 que o jogador aplica num oponente **expira antes de valer**. No log, "X ganha Provocação" aparece seguido de "X: Provocação terminou", tudo antes de o inimigo agir.

Causa, no source:

- No laço da rodada, o tick roda **no início** do turno de quem carrega a condição (`services/conflict_orchestrator.py:2418`, `_tick_conditions_v4`). Ele desconta 1 de toda condição que não é stat puro e remove o que chega a 0 (`conflict_orchestrator.py:264-268`).
- **Stun** escapa porque é lido **antes** do tick (`conflict_orchestrator.py:2411-2414`; o comentário explica que o problema já tinha sido corrigido só para ele).
- Os outros controles são lidos **depois** do tick:
  - `taunt`: em `_enemy_decl` → `enemy_declaration` → `_taunt_target` (`conflict_orchestrator.py:505`, `:293-319`).
  - `silence`: `conflict_turn.py:405`, `conflict_orchestrator.py:561/591`.
  - `fear`: −2 de acerto em `combat_mechanics.py:422-423`, lido no ataque do portador.
  - `root`: `services/cards.py:725`, só esconde o chip "Fugir".
  - `marca`: lida quando **outro** ataca o portador (`conflict_turn.py:516`, `combat_preview.py:95`). Ela some no início do próximo turno do portador e, por isso, não chega ao próximo turno de quem a aplicou.

Na prática:

- **Provocar nunca vale.** São 21 Cartas de jogador, todas com `duracao` 1, entre elas a básica `bas_dev_voto` (`data/cards/basicas.json:43-56`, sem `duracao`, que vira 1 em `conflict_turn.py:745`).
- **A Marca de `duracao` 1 não chega ao próximo turno do jogador.** São 26 Cartas. Com o baralho `on`, ela ainda vale dentro da mesma rodada.
- Os inimigos também carregam `taunt`/`marca` (`data/cards/inimigos/*.json`, `bestiario.json`; 55 ocorrências de `"kind": "taunt"|"marca"` em `data/cards/`, somando jogador e inimigo). O bug é simétrico: a Marca do inimigo no jogador também morre no tick do jogador.
- Os testes atuais escondem o bug porque aplicam condição com `duration=2` (`tests/test_mecanica_orfa.py:492`).

**Objetivo:** fazer a duração valer a regra "**`duracao` d = o portador atravessa d turnos próprios que começam depois da aplicação**". Assim, um controle aplicado por outro ator pula o primeiro tick do portador. Junto disso:

- levantar todas as condições com o mesmo defeito;
- proteger o golden da SPEC-330 com protocolo explícito;
- remover o lint provisório da SPEC-335;
- rodar a arena de novo, porque Provocar e Marca passam a valer.

Princípio: **mecânica é Python** e o texto da Carta (`card_effects.py:1389-1392`, "Provoca o alvo…", "Marca o alvo…") é contrato com o jogador. Hoje o motor descumpre esse contrato.

## 2. Requisitos

### Regra de duração

- **R1 — Controle de leitura tardia aplicado por outro ator pula o 1º tick do portador.** São de leitura tardia `taunt`, `marca`, `fear`, `root` e `silence`, além de qualquer `control` novo que não seja `stun`. Quando uma dessas condições entra em X por um ator ≠ X (ou fora do turno de X, por exemplo numa reação), o **primeiro** `_tick_conditions_v4` de X depois da aplicação não desconta a duração, não remove a condição e não loga "terminou". Os ticks seguintes seguem iguais aos de hoje.
- **R2 — `stun` não muda.** O `stun` com `duracao` 1 aplicado por oponente nega **exatamente 1** turno do portador. O teste existente do comentário de `conflict_orchestrator.py:2411` continua verde, e um teste novo prova que não houve dupla negação.
- **R3 — DoT não muda.** Uma condição com `dot > 0` e sem `control` (Sangramento, Sangria, `dot` de Carta, `sangrando`) causa o mesmo número de ticks de dano e o mesmo total que hoje, porque o efeito dela **é** o tick. `decai` (Sangria) não muda.
- **R4 — Condição aplicada no próprio turno pelo próprio portador não muda.** Nada na `main` aplica controle em si mesmo de propósito, mas o caminho fica igual ao de hoje.
- **R5 — Compatibilidade de estado.** Condição sem o marcador do R1 (save antigo, teste unitário que chama `_tick_conditions_v4` direto, por exemplo `tests/test_conflito_orquestrador.py:241`, `tests/test_keywords_valoria.py:155`, `tests/test_mecanica_orfa.py:497`) tica exatamente como hoje. O marcador não aparece na view da API nem no front (`active_conditions` serializado). Se precisar de nome, use prefixo `_`, e um teste confere que a view o filtra.
- **R6 — Marca do Abismo.** `marca_abismo_condition` (`services/card_effects.py:612-622`, `duration: 3`, `control: "marca"`) segue o R1, como toda `marca`. O consumo no próximo dano (`consume_marca_abismo`, `:625`) não muda. Isso estende a Marca do Abismo aplicada por oponente de 2 para 3 turnos efetivos do portador. Ver D3.

### Levantamento das condições afetadas

- **R7 — Inventário executável.** Um teste parametrizado (`tests/test_spec339_duracao_condicoes.py`) roda `run_round` real nas duas ordens de iniciativa (lado do herói primeiro e lado inimigo primeiro). Para cada condição do catálogo (controles `stun/root/fear/silence/taunt/marca`, `NAMED_CONDITIONS` de `combat_mechanics.py:186-205`, `dot`, Marca do Abismo), aplica `duracao` 1 pelo jogador no inimigo e pelo inimigo no jogador. O teste asserta **em qual turno o efeito é lido**. A tabela esperada fica no próprio teste e copiada no §3.4. O levantamento preliminar, feito por leitura de código, está no §3.4 e o executor confirma cada linha.
- **R8 — Stat de leitura defensiva.** Ficam fora do R1: `exposto` (ac −2), `rachadura` (`dano_recebido_pct` +25), `armadura_comprometida` (protection −2), e `protection`/`ac` aplicados por aliado. Eles expiram no **fim** do turno do portador quando já estavam ativos no início (`_expire_stat_conditions`, `conflict_orchestrator.py:221-237`), então quem os aplicou no oponente não os aproveita no próprio turno seguinte. O mesmo vale para a `marca` hoje. O R7 tem de **medir** esse caso, e a correção dele depende da decisão D2. Se o dono aprovar, vale o **R8b**: stat de leitura defensiva aplicado por outro ator pula a 1ª expiração do portador, com a mesma mecânica de marcador do R1. Se o dono não aprovar, o teste do R7 congela o comportamento atual com `xfail(strict=True)` e um comentário que aponta a spec de follow-up.

### Presságio (SPEC-329)

- **R9 — Provocar entra no presságio da rodada seguinte.** Com `RPG_ENEMY_INTENT=on` (ou o nome da flag em vigor), a intenção de cada inimigo é congelada no início da rodada por `enemy_declaration` (`services/enemy_intent.py:186`). Um `taunt` com `duracao` 1 aplicado na rodada N está presente quando a rodada N+1 é congelada, e o `_taunt_target` é consultado. Teste com `rng` forçado (chance < 0,9) prova que o alvo congelado da rodada N+1 é o provocador. Com a flag `off`, a `_enemy_decl` tardia do turno N+1 (se o inimigo agir depois da aplicação) ou do turno N (se agir depois na mesma rodada) vê o `taunt`.

### Golden da SPEC-330 (integridade de eval)

- **R10 — Golden byte-idêntico no design recomendado.** O golden `tests/fixtures/spec330_legacy_golden.json` roda **um** `ct.resolve_turn` / `_resolve_reaction_effect` por Carta (`tests/spec330_equivalence.py:79-95`) e **não** passa por `_tick_conditions_v4` nem por `run_round`. Com o design A (§3.1, marcador posto pelo orquestrador), `test_card_effects_grammar.py:90-106` passa **sem tocar no golden**. A prova é um `git diff --exit-code tests/fixtures/spec330_legacy_golden.json` no pouso.
- **R11 — Se o golden tiver de mudar (design B ou desvio).** Vale o protocolo:
  1. O executor do produto **não** regenera o golden. Ele para e registra o desvio na spec.
  2. A regeneração é um commit **separado** (`test(golden): regenerate spec330 golden for SPEC-339`), feito pelo coordenador ou por um agente diferente do executor, rodando `bash scripts/dev/py.sh tests/spec330_equivalence.py`.
  3. O commit leva um relatório `docs/spec339/golden-diff.md` com a lista exata das Cartas cujo `sha` mudou. Cada uma precisa estar no inventário de Cartas que aplicam condição afetada (taunt/marca/fear/root/silence/Marca do Abismo, e as do R8b se aprovado), com o porquê. Toda mudança fora dessa lista **bloqueia**.
  4. A mudança passa por revisão independente (`spec-reviewer`, Sol) antes do pouso. O handoff fica em `handoffs/SPEC-339-sol-review.md`.
  5. `len(golden) == 308` e as chaves não mudam.
- **R12 — `router_off_golden.json` intocado.** `tests/fixtures/router_off_golden.json` não tem relação com combate e não muda.

### Lint provisório da SPEC-335

- **R13 — Remover o lint provisório.** A SPEC-335 (Lote 5) acrescenta ao lint de Cartas uma regra que recusa `taunt`/`marca` com `duracao < 2` em Carta de onda. Ela deve estar em `services/card_lint.py`, mas o código exato só existe depois que a 335 pousar e o executor localiza com `Grep "taunt" services/card_lint.py`. Esta spec remove a regra e os testes que a exigem, e acrescenta um teste que prova que uma Carta de onda com `taunt` de `duracao` 1 passa no lint. Se a 339 pousar **antes** do Lote 5, o hand-back avisa o coordenador para não pousar a regra.
- **R14 — Cartas que fugiram do lint.** Se, por causa do lint provisório, alguma Carta de onda foi escrita com `duracao: 2` só para escapar do bug, o executor lista essas Cartas no relatório (§R15). **Não** mexe nelas: o ajuste de número é de balanceamento e fica para a 335/336.

### Balanceamento

- **R15 — A arena roda de novo.** O executor roda `scripts/cards/sim.py` antes e depois da correção, nas mesmas seeds:
  - `--protocolo lote` para cada arquivo de Postura que tem `taunt`/`marca`/`fear`/`silence` (lista no §3.4);
  - o default (níveis 1,3,5) para o acervo legado.

  Grava `docs/spec339/arena-antes.json`, `docs/spec339/arena-depois.json` e `docs/spec339/RELATORIO-arena.md`. O relatório tem a tabela por Carta com o delta em pp, as bandeiras `dominante` novas e as que sumiram, e a variação de vitória por Postura (Devoto em destaque).
- **R16 — Nenhum número de Carta muda nesta spec.** Bandeira nova vira lista para o dono e follow-up na SPEC-336. Ver D4.
- **R17 — Testes de balanço.** `tests/test_balance_classes_v4_runtime.py` e `tests/test_balance_classes.py` rodam no escopo. Se algum limite falhar **só** por causa da correção, o executor **não** muda o limite (integridade de eval). Ele registra a falha, o número antes e depois, e para para o coordenador decidir.

### Fora de escopo

- Mudar números de Cartas (valor, `duracao`, custo, raridade). Fica com a 335/336.
- Mudar o momento do tick (início para fim de turno) para todas as condições. É uma reescrita maior; R1 e R8b são a correção mínima.
- DoT com tipo de dano e resistência (follow-up P2-4 da 335, já com a 330/336).
- Texto de `taunt` ("precisa atacar você" promete mais que 50%×multiplicador): está com a 336 (P2-5 da 335).
- Escolher quem é provocado quando o `taunt` vem como efeito extra (`corpo_entre`, P2-2 da 335).
- O caminho legado `cm.tick_conditions` do motor antigo, se ainda existir fora do laço v4.
- Front: a UI mostra a duração restante como já mostra. Mudar a contagem exibida exige outra spec.

## 3. Design técnico

### 3.1 Onde pôr o marcador: duas opções (decisão D1)

**Design A (recomendado): marcador posto pelo orquestrador.** Não toca no golden nem em saves antigos.

- Em `_run_round` (`conflict_orchestrator.py:2388-2444`), antes de cada passo que pode aplicar condição (turno de ator, ação extra, reação, Última Ação, `_sc.tick` de cena), tirar um snapshot `{actor_id: [refs das condições]}`. A comparação é por identidade (`is`), como `present_at_start` já faz em `:2417`.
- Depois do passo, toda condição **nova** de leitura tardia (R1), ou de leitura defensiva (R8b), num ator Y recebe `c["_pula_tick"] = True` quando:
  - Y ≠ ator do turno; ou
  - Y é o ator do turno e `c.get("source_actor_id")` existe e é ≠ Y (reação de outro).
- `_tick_conditions_v4`: se `c.pop("_pula_tick", False)` for verdadeiro e `not dot`, a condição sobrevive sem descontar. Uma condição com `dot` ignora o marcador (R3).
- `stun` nunca recebe marcador (R2).
- Função nova, pura e testável: `_mark_fresh_conditions(before: dict[str, list[dict]], actors_by_id: dict[str, dict], current_actor_id: str | None) -> int`, que devolve quantas marcou.
- Constante nova: `_LATE_READ_CONTROLS: frozenset[str] = frozenset({"taunt", "marca", "fear", "root", "silence"})`. Um teste falha se aparecer em `data/cards/` um `control` novo que não esteja nem nela nem em `{"stun"}`.

**Design B: marcador posto na aplicação** (`conflict_turn._apply_attack_card_effect` `:741-783`, os caminhos de `aplicar_condicao` e as Cartas de inimigo). A regra fica mais local, mas o `actors` serializado no golden muda para toda Carta que aplica condição afetada, o que obriga o R11. Também espalha a regra por vários pontos de escrita.

O executor implementa A, a menos que o dono escolha B em D1. Se A se mostrar inviável (por exemplo, uma condição aplicada fora de `_run_round` que precise do marcador), o executor para e atualiza a spec antes de seguir para B.

### 3.2 Arquivos alterados

- `services/conflict_orchestrator.py`: `_LATE_READ_CONTROLS`, `_mark_fresh_conditions`, snapshot e marcação no laço, consumo do marcador em `_tick_conditions_v4` e, se D2 aprovar, em `_expire_stat_conditions`.
- View da API das condições (localizar com `Grep "active_conditions" api.py services/*view*`): filtrar chaves que começam com `_`, se ainda não filtra.
- `services/card_lint.py` (depois da 335): remover a regra provisória (R13).
- Testes: `tests/test_spec339_duracao_condicoes.py` (novo); ajuste de `tests/test_card_lint.py` (remoção dos casos da regra provisória).
- `docs/spec339/`: `arena-antes.json`, `arena-depois.json`, `RELATORIO-arena.md` e, só no design B, `golden-diff.md`.

### 3.3 Exemplo de cena para os testes (IDs reais)

- Jogador Devoto do Abismo com `known_cards=["bas_dev_voto"]` contra 1 inimigo com `tactical_profile` default e um aliado `categoria="companheiro"`. O padrão é o de `tests/spec330_equivalence.py:47-71`.
- Ordem forçada pelo `init["order"]`: `["hero","enemy"]` e `["enemy","hero"]`.
- `rng` com `random()` fixo em 0,0 para a chance de `taunt` (`conflict_orchestrator.py:309-310`).

### 3.4 Levantamento preliminar (por leitura de código; o R7 confirma)

| Condição | Lida quando | Ticada/expirada | Aplicada por oponente com d=1 hoje | Depois (A) |
|---|---|---|---|---|
| `stun` | antes do tick, turno do portador (`orch:2414`) | tick no início | vale 1 turno: OK | igual (R2) |
| `taunt` | `_enemy_decl` depois do tick (`orch:505`) | tick no início | **nunca vale** | vale no próximo turno do portador e no congelamento do presságio N+1 |
| `fear` | ataque do portador (`cm:422`) | tick no início | **nunca vale** | vale no próximo turno |
| `silence` | turno do portador (`ct:405`, `orch:561/591`) | tick no início | **nunca vale** | vale no próximo turno |
| `root` | chips do jogador (`cards.py:725`) | tick no início | **nunca vale** (efeito só de UI) | vale no próximo turno |
| `marca` | ataque **contra** o portador (`ct:516`) | tick no início | vale só até o início do próximo turno do portador | vale até o início do 2º turno do portador: cobre o próximo turno do aplicador nas duas ordens |
| Marca do Abismo (d=3) | idem + consumo | tick no início | 2 turnos efetivos | 3 (D3) |
| `dot`, Sangria, `sangrando` | o próprio tick | tick no início | 1 tick de dano: OK | igual (R3) |
| `torpor`, `enfraquecido`, `desmoralizado`, `cego`, `desarmado_risco` (stat ofensivo do portador) | turno do portador | fim do turno, se presente no início (`orch:231`) | vale no próximo turno: OK | igual |
| `exposto`, `rachadura`, `armadura_comprometida`; `protection`/`ac` dados por aliado (stat defensivo) | ataque **contra** o portador | fim do turno do portador | some no fim do próximo turno do portador, antes do turno seguinte do aplicador | D2 (R8b) |
| `vigilia` | persistente | só ao consumir | OK | igual |

Arquivos de Postura com `taunt`/`marca` (para o R15, levantados por `Grep`): `posturas/devoto_zeloso.json`, `posturas/sangromante_exposto.json`, `posturas/sangromante_silencioso.json`, `posturas/sangromante_avaro.json`, `posturas/arcanista_cinzento_improvisador.json`, mais os legados `devoto.json`, `sangromante.json`, `corruptor.json`, `medico.json`, `arcanista.json` e `basicas.json`. O executor completa a lista com `fear`/`silence`/`aplicar_condicao` de controle.

## 4. Plano passo a passo

### Etapa 0 — Baseline (sem código de produto)

1. Rodar o R15 "antes" e gravar `docs/spec339/arena-antes.json`.
2. Rodar `tests/test_card_effects_grammar.py`, os dois testes de balanço e `tests/test_conflito_orquestrador.py` com `-n 2` e anotar as contagens.

### Etapa 1 — Testes que falham (TDD)

1. `tests/test_spec339_duracao_condicoes.py`:
   - `test_taunt_d1_do_jogador_redireciona_proximo_turno_inimigo[ordem]`: com `rng` 0,0, a declaração do inimigo no turno seguinte à aplicação mira o jogador, e o log **não** tem "Provocação terminou" antes da ação do inimigo.
   - `test_marca_d1_vale_no_proximo_turno_do_aplicador[ordem]`: o ataque do jogador na rodada N+1 tem `advantage` +1 vindo da Marca, e a vantagem não existe na N+2.
   - `test_marca_d1_do_inimigo_no_jogador_vale_no_proximo_turno_do_inimigo[ordem]` (simetria).
   - `test_fear_d1_reduz_acerto_no_proximo_ataque_do_portador`; `test_silence_d1_bloqueia_proxima_carta_do_portador`.
   - `test_stun_d1_nega_exatamente_um_turno[ordem]` (R2, deve passar já).
   - `test_dot_d1_mesmo_total_de_dano` e `test_sangria_decai_igual` (R3, devem passar já).
   - `test_tick_direto_sem_marcador_igual_hoje` (R5): condição sem `_pula_tick` em `_tick_conditions_v4` direto tem o comportamento atual.
   - `test_marcador_nao_vaza_na_view` (R5).
   - `test_reacao_aplica_taunt_no_turno_do_inimigo_vale_no_turno_seguinte`.
   - `test_presagio_on_congela_alvo_provocado_na_rodada_seguinte` (R9).
   - `test_todo_control_do_acervo_esta_classificado` (§3.1).
   - `test_inventario_duracao[condicao-aplicador-ordem]` (R7): tabela do §3.4. As linhas do R8 ficam `xfail(strict=True)` até D2.
2. **Verificação:** os testes de taunt/marca/fear/silence/reação/presságio falham pelo motivo certo, e os do R2/R3/R5 passam.

### Etapa 2 — Correção do motor (design A)

1. `_LATE_READ_CONTROLS`, `_mark_fresh_conditions` e o consumo em `_tick_conditions_v4`.
2. Snapshot e marcação em `_run_round` em todos os passos do §3.1.
3. Filtro da view, se preciso.
4. **Verificação:** a Etapa 1 fica verde; `tests/test_conflito_orquestrador.py`, `tests/test_keywords_valoria.py`, `tests/test_mecanica_orfa.py`, `tests/test_enemy_intent.py`, `tests/test_spec283_enemy_support_cards.py` e `tests/test_card_effects_grammar.py` ficam verdes com `-n 2`; e `git diff --exit-code tests/fixtures/spec330_legacy_golden.json` (R10).

### Etapa 3 — Stat defensivo (só se D2 = sim)

1. Tirar o `xfail` das linhas do R8 e implementar o R8b em `_expire_stat_conditions`.
2. **Verificação:** os mesmos arquivos da Etapa 2, verdes.

### Etapa 4 — Golden (só se o design B for escolhido ou se a Etapa 2 alterar o golden)

1. O executor para e registra o desvio na spec.
2. O coordenador, ou outro agente, segue o R11, e o Sol revisa.

### Etapa 5 — Lint provisório da SPEC-335

1. **Teste:** `test_carta_de_onda_taunt_d1_passa_no_lint` em `tests/test_card_lint.py` (falha enquanto a regra existir).
2. Remover a regra e os casos de teste dela.
3. Listar as Cartas do R14.
4. **Verificação:** `tests/test_card_lint.py` verde e `bash scripts/dev/py.sh scripts/validate_content.py` com 0 erros.

### Etapa 6 — Arena

1. R15 "depois", relatório e lista de bandeiras para o dono (R16).
2. R17: só registrar.

## 5. Critérios de aceite

- [x] R1: `taunt`, `marca`, `fear`, `silence` e `root` com `duracao` 1, aplicados por oponente, valem no próximo turno do portador nas duas ordens de iniciativa (testes da Etapa 1 verdes).
- [x] R2: `stun` com d=1 nega exatamente 1 turno.
- [x] R3: DoT/Sangria com o mesmo número de ticks e o mesmo dano total de antes.
- [x] R5: tick direto sem marcador igual ao de hoje; marcador ausente da view da API.
- [x] R6/D3: Marca do Abismo conforme a decisão do dono, com teste.
- [x] R7: inventário parametrizado verde, com tabela no teste igual à do §3.4 atualizada.
- [x] R8: D2 decidido; linhas `xfail(strict)` ou R8b implementado.
- [x] R9: presságio `on` congela o alvo provocado na rodada seguinte.
- [x] R10 ou R11: golden byte-idêntico, **ou** regenerado em commit separado por outro agente, com `golden-diff.md` e revisão Sol aprovada.
- [x] R13: lint provisório removido; Carta de onda com `taunt` d=1 passa no lint.
- [x] R15: `docs/spec339/RELATORIO-arena.md` com antes e depois, bandeiras listadas para o dono.
- [x] Herdado da SPEC-335 (critério 45–75 % por Postura): depois do bugfix, refazer a arena por Postura **por subclasse**, com o viés de ordem do `full_deck` corrigido e mais criaturas/sementes. Ponto de partida (27/10, `docs/spec335/RELATORIO-arena-posturas.md`): Sangromante ~80 % no padrão, Corruptor/alma ~34 % com elite. O ajuste de poder, se preciso, é uma spec de balanceamento à parte (R16).
- [x] `CONTROLE_DURACAO_PENDENTES` vazia (as 9 Cartas dos Lotes 2–3 validadas com o motor corrigido).
- [x] R16/R17: nenhum número de Carta nem limite de teste de balanço alterado nesta spec.
- [x] `uv run pytest` verde (suíte completa offline, 1× no pouso pelo coordenador).
- [x] Saves antigos continuam carregando (condição sem marcador tica como antes).
- [x] Guard de FallbackLLM: não se aplica, porque não há `with_structured_output` novo.

## 5.1 Desvios e notas da implementação (executor, 27/10)

- **Marcador de refresh.** `cm.apply_condition` (refresh de condição de mesmo nome) agora grava `_renovada` quando a condição tem `control` ou `stat`; o orquestrador consome a chave na passada de marcação e a transforma em `_pula_tick`. Sem isso, re-aplicar `taunt` d=1 a cada turno nunca valeria. O golden da 330 segue byte-idêntico (verificado).
- **R8b restrito.** Marca stat defensivo só como debuff (ac/protection com delta < 0, `dano_recebido_pct` > 0) aplicado dentro do turno de OUTRO ator, e Proteção/AC positivos só de aliado do mesmo lado. Buff de reação em si mesmo (turno do atacante) não é marcado: ambíguo sem `source_actor_id` no dict da condição, e gravar isso mudaria o golden.
- **Controle em reação sem `source_actor_id`** (ex.: `silenciado` aplicado no atacante) também é marcado quando o portador é o ator do turno; só é ignorado se a fonte for o próprio portador.
- **Passos marcados:** tick de cena (início/fim da rodada), turno de cada ator (inclui reações e a via do baralho), ação extra e Última Ação. Restrito a `_run_round`.
- **Viés de ordem do `full_deck`:** corrigido em `scripts/cards/sim.py` (hash estável no desempate de tier). Resultados anteriores da 335 não são comparáveis; ver `docs/spec339/RELATORIO-arena.md`.
- **Smoke §6.1** (taxa "Provocar efetivo" na arena) não se aplica: o bot de arena joga solo. Prova por teste de motor com aliado (`test_taunt_d1_do_jogador_redireciona_proximo_turno_inimigo`). §6.2–6.4 (API local) não rodados pelo executor.
- **Revisão Sol (CHANGES_REQUIRED) corrigida:** P1-1 `hero ∪ ally` como um time no R8b; P1-2 com presságio `on` o `taunt` é lido no congelamento (antes do tick), então quem já agiu na rodada não recebe marcador (exatamente 1 declaração afetada nas duas ordens); P2-1 `_renovada` só se a nova duração >= restante; P2-2 `_run_round` limpa `_renovada` no início; P2-3 testes mais fortes. P2-4 (controle autoaplicado sem `source_actor_id` é marcado como reação) fica registrado: se surgir Carta que se aplica controle, exigir `source_actor_id` no caminho de aplicação.

## 6. Smoke test real

Não há LLM no caminho: o tick é determinístico. O smoke real é sobre o motor e a API local, com MockLLM.

1. `bash scripts/dev/py.sh scripts/cards/sim.py` com o protocolo do R15 sobre `posturas/devoto_zeloso.json`. A taxa de "Provocar efetivo" (inimigo mira o Devoto no turno seguinte ao `taunt`) deve ser > 0. Hoje ela é 0.
2. API local (`uvicorn api:app`): criar um Devoto, entrar em conflito e jogar Voto Sussurrado (`bas_dev_voto`). O log da rodada **não** pode ter "terminou" para a Provocação antes da ação do inimigo. Repetir com `RPG_DECK` `on` e `off` (nomes das flags em vigor em `scripts/staging/staging_flags.json`).
3. Repetir o passo 2 com o presságio `on`: o presságio da rodada seguinte anuncia o Devoto como alvo (quando a chance passa).
4. Uma Carta de `marca` (por exemplo, uma de `posturas/sangromante_exposto.json`): o ataque do jogador na rodada seguinte mostra Vantagem no preview (`combat_preview.py:95`) e no log.

## 7. Riscos & compatibilidade

- **Muda o comportamento com as flags `off`.** É a correção de um bug do motor base, que vale em produção e no staging. Provocar e Marca passam a funcionar para jogadores **e inimigos**: o jogador vai sofrer a Marca dos inimigos que hoje é inerte. Isso pode subir a letalidade de encontros com `lider_matilha`, `predador`, `faccao_clas_combate` e outros. O R15 mede só Cartas de jogador. Ver D5 para incluir a arena de inimigos e D6 sobre flag.
- **Golden.** O design A não deve tocar no golden, porque o golden não passa pelo tick. Se tocar, o R11 é obrigatório, e o risco é o executor "consertar" o golden junto com o produto. Isso é proibido por AGENTS.md § Integridade de eval. Hoje o golden **não** está em `evals/protected-paths.txt` (verificado; nenhuma linha com `golden`/`fixtures`), então só o processo o protege. Ver D7.
- **Saves antigos.** No design A não há marcador em save antigo, e o tick fica igual ao de hoje (R5). Uma condição em voo no momento do deploy expira pela regra antiga, o que é aceitável. No design B a situação é a mesma.
- **Identidade de dict.** O snapshot por `is` depende de as condições não serem copiadas entre passos. `cm.apply_condition` pode substituir uma condição de mesmo nome (refresh). O teste "reaplicar `taunt` sobre `taunt`" precisa provar que o refresh também recebe o marcador.
- **Presságio e chance de `taunt`.** Com o R9, o `rng` de `_taunt_target` passa a ser consumido no congelamento da rodada seguinte. Seeds de testes de presságio que hoje não veem `taunt` não mudam. Testes com `taunt` + presságio podem mudar de sequência, e o executor lista quais.
- **Marca do Abismo mais longa (D3)** pode desbalancear o Corruptor (`corruptor_alma.json`), que a 335 já ajustou.
- **MockLLM / FallbackLLM:** nenhum impacto, porque não há LLM.
- **Quota/latência:** nenhum. O snapshot é O(condições) por passo de rodada.

## 8. Decisões que o dono precisa tomar

- **D1 — Design A (marcador no orquestrador, golden intacto) ou B (marcador na aplicação, golden regenerado pelo R11)?** Recomendação: A.
- **D2 — Corrigir também os stats de leitura defensiva** (`exposto`, `rachadura`, `armadura_comprometida`, Proteção dada por aliado), que têm o mesmo sintoma da Marca (R8b)? Recomendação: sim, na mesma spec, porque Rachadura é palavra-chave nova da 330 e é cedo para congelar o bug.
- **D3 — Marca do Abismo** (d=3) sobe de 2 para 3 turnos efetivos? Recomendação: sim, já que o texto diz "por 3 rodadas", com a arena do Corruptor no R15.
- **D4 — Bandeiras `dominante` novas** depois da correção: só listar (R16, recomendado) ou ajustar números já nesta spec?
- **D5 — Arena de inimigos:** incluir no R15 a medição de encontros com baralhos de inimigo que usam `taunt`/`marca` (SPEC-332)? Recomendação: sim, só medir.
- **D6 — Flag:** corrigir sem flag (recomendado, porque é bug e não feature) ou pôr atrás de `RPG_CONTROL_TICK_FIX` com default `on`, para poder reverter no staging?
- **D7 — Pôr `tests/fixtures/spec330_legacy_golden.json` em `evals/protected-paths.txt`?** Muda a governança de eval, então quem decide é o dono.

**Decisões do dono (27/10, "aprovado, siga esses passos"):** todas as recomendações.
D1 = design A (marcador no orquestrador, golden intacto). D2 = sim, R8b na mesma spec.
D3 = sim, Marca do Abismo vale 3 turnos efetivos. D4 = só listar as bandeiras novas (R16).
D5 = sim, só medir os baralhos de inimigo. D6 = sem flag. D7 = sim, golden em
`evals/protected-paths.txt` (commit próprio; publicação via `/eval-publish` se o gate pedir).

## 6.1 Resultado do smoke (executor, 27/10)

Feito por script em scratch chamando `orch.run_round` real (o caminho da rota), MockLLM, sem uvicorn:
criar Devoto e entrar em conflito pela API exige o fluxo de criação/encontro; o script usa a mesma `run_round`
(`bas_dev_voto` real, aliado de Agilidade 9 como alvo padrão, `rng` forçado). Nenhum processo deixado.

- **§6.1/6.2 Provocar** (`RPG_CARD_DECK` off/on × `RPG_ENEMY_INTENT` off/on × ordem hero/enemy): em todas as 8
  combinações exatamente 1 ataque do inimigo mira o jogador, e o resto mira o aliado.
  Ex.: `off/off hero_first: ['e → player','e → ally',None,None]`; `off/off enemy_first: ['e → ally','e → player','e → ally',None]`.
  Presságio off: nenhuma linha "terminou" antes da ação que usa a Provocação. Presságio on: o alvo é congelado
  antes do tick (`on/on hero_first: ['e → ally','e → player',...]`), então "terminou" aparece no tick da rodada
  de uso (a declaração já estava congelada); por desenho (P1-2).
- **§6.3** presságio on: o alvo congelado da rodada seguinte é o jogador (`e → player` na rodada 2), uma vez só.
- **§6.4 Marca** (`san_sil_fio`): log "e: ganha condição Fio sem Testemunha"; `combat_preview.preview` na rodada
  seguinte: `tem_marca=True`, `chance_acerto_pct` 91,6 (Vantagem) contra 76,0 sem a Marca (`hero_first`, rodada 3).
  Em `enemy_first` a Marca ainda vale na rodada 3 (o tick do inimigo vem antes do jogador).
- **Provocar efetivo na arena (§6.1 original):** não aplicável (bot solo, sem aliado para o desvio).

