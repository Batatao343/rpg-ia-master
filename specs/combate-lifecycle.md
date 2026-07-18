# SPEC — Ciclo de vida do combate (viagem = fuga; combate órfão expira)

> **Status:** `approved` (2026-07-17 — ordem de dev: **3/8**; após playtest-stop-gameover — invariante R4 usa rota fiel)
> **Criada:** 2026-07-16 · **Atualizada:** 2026-07-16
> **Depende de:** fix-playtest-achados (fuga do jogador, `done`)
> **Desbloqueia:** pos-saque-recuperacao (estado de combate confiável)

---

## 1. Contexto & Objetivo

Playtest longo 2026-07-14 (achado C): o estado de combate não é resolvido nem
limpo quando a narrativa segue em frente. Evidências:

- **quester**: combate abriu no turno 42 e `combat.active` ficou `True` até o
  turno **100** (59 turnos!) enquanto o router mandava `storyteller`/`npc_actor`
  normalmente — inimigos "fantasma" no estado durante quests e diálogos.
- **explorador**: com um Zumbi Blindado ativo e sangramento (HP 3/37), o perfil
  emitiu 2 ações de viagem (t42/t43) que o storyteller processou como viagem
  normal — sem fuga, sem opportunity attack — e o golpe fatal chegou "à
  distância" 2 turnos depois.

Princípio violado: **mecânica é Python, não LLM**. O lock de combate hoje
depende do router/LLM escolher a rota certa; o estado precisa de regras
determinísticas de entrada/saída.

## 2. Requisitos

- **R1** — Com `combat.active`, ação classificada como viagem NÃO teleporta o
  jogador: é convertida em **tentativa de fuga** (mecânica existente de fuga do
  jogador, `combat_mechanics`). Fuga bem-sucedida → viagem prossegue no mesmo
  turno; falha → turno de combate normal (inimigos agem).
- **R2** — Com `combat.active`, rotas `npc_actor`/`loot` são bloqueadas
  deterministicamente: router é forçado a `combat_agent` (exceto ação de
  conversa DENTRO do combate — segue indo pro combate, que pode narrar).
- **R3** — Combate expira sozinho: se `combat.active` e o combate não recebe
  rota de combate há `N=3` turnos (contador em `combat["idle_turns"]`),
  `combat` é limpo (`active=False`, `enemies=[]`) com nota narrativa
  determinística ("os inimigos perdem seu rastro").
  *(R3 é rede de segurança; com R1+R2 corretos, quase nunca dispara.)*
- **R4** — Invariante nova (`playtest/invariants.py`):
  `combat.zombie` (severity `error`) se `combat.active` por mais de 5 turnos
  consecutivos sem rota `combat_agent`.
- **R5** — Fim de combate (vitória/fuga/expiração) SEMPRE zera
  `combat`, `enemies`, `combat_target` no mesmo turno.

### Fora de escopo

- Rebalancear dano/fuga (números atuais ficam).
- IA de perseguição entre locais.

## 3. Design técnico

- **`agents/router.py`** — gate determinístico ANTES do LLM: se
  `state["combat"]["active"]`: classificar só entre {fuga/viagem, combate,
  outro}; viagem → `next="combat_agent"` + flag `combat_flee_attempt=True` +
  destino pretendido em `combat_flee_destination`.
- **`agents/combat.py`** — se `combat_flee_attempt`: resolve fuga via
  `combat_mechanics` (mecânica da spec fix-playtest); sucesso → aplica a viagem
  (`world_utils.travel`) e limpa combate; falha → rodada normal.
  Incrementa/reseta `combat["idle_turns"]`; aplica R3 e R5.
- **`state.py`** — documentar chaves novas do dict `combat`
  (`idle_turns: int`) — sem migration (dict aberto, default 0 via `.get`).
- **`playtest/invariants.py`** — check `combat.zombie` (R4) usando o histórico
  de rotas do runner (depende da rota fiel da spec `playtest-stop-gameover`).

## 4. Plano passo a passo

### Etapa 1 — gate do router
1. **Testes** (`tests/test_combat_lifecycle.py`):
   `test_viagem_em_combate_vira_fuga` (router com combate ativo + ação "Viajo
   para X" → `next=="combat_agent"` e `combat_flee_attempt`);
   `test_npc_em_combate_e_bloqueado`.
2. **Implementação:** gate em `dm_router_node`.
3. `uv run pytest` verde.

### Etapa 2 — fuga-viagem no combate
1. **Testes:** `test_fuga_sucesso_viaja_e_limpa_combate` (RNG semeado);
   `test_fuga_falha_inimigos_agem`; `test_fim_de_combate_zera_estado` (R5).
2. **Implementação:** `combat_node` + `world_utils.travel` no sucesso.
3. `uv run pytest` verde.

### Etapa 3 — expiração + invariante
1. **Testes:** `test_combate_orfao_expira_em_3_turnos`;
   `test_invariante_combat_zombie_dispara`.
2. **Implementação:** `idle_turns` + check 5.2.
3. `uv run pytest` verde.

## 5. Critérios de aceite

- [ ] R1–R5 com testes
- [ ] Replay do cenário do quester (mock, combate + 10 turnos de story) termina
  sem `combat.active`
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Guard de FallbackLLM em todo `with_structured_output` novo
- [ ] Saves antigos continuam carregando (combat dict sem `idle_turns` → default 0)

## 6. Smoke test com LLM real

1. Provocar combate (perfil `combate`, `--real`, poucos turnos) e emitir "Viajo
   para <vizinho>" → narração de fuga (sucesso OU falha), nunca teleporte.
2. Vencer um combate e conferir `combat is None`/inactive no estado salvo.

## 7. Riscos & compatibilidade

- Saves antigos com `combat.active=True` órfão: R3 os limpa em ≤3 turnos.
- MockLLM: fuga é determinística (RNG semeado) — testável offline.
- Perfil `fujao` já exercita fuga — conferir que a suíte dele segue verde.
