# SPEC — Fix: perfil Explorador entra em loop de navegação (cidade ↔ interior)

> **Status:** `done` (2026-07-20 — memória anti-backtrack + fronteira; +6 testes)
> **Criada:** 2026-07-20 · **Origem:** run `20260720-093014` (logs `explorador_*.jsonl`)
> **Tipo:** correção de bug do harness de playtest (perfil determinístico)
> **Desbloqueia:** medição real de exploração + `loot-exploracao` (recompensa de 1ª visita nunca dispara com o bounce)

---

## 1. Contexto & Objetivo

No run `20260720-093014`, todos os perfis `explorador` entraram num **loop
degenerado** de ~7 turnos antes de morrer. Trecho cru (`explorador_arcanista_cinzento_42`):

```
t8  Viajo para Skallgard.
t9  Entro em Salão do Jarl.
t10 Viajo para Skallgard.
t11 Entro em Salão do Jarl.
t12 Viajo para Skallgard.
t13 Entro em Salão do Jarl.
t14 Viajo para Skallgard.
t15 Viajo para Fortaleza de Vorr.   ← finalmente sai, e morre one-shot (Yeti)
```

**Causa (em `playtest/profiles.py`, `Explorador.next_action`):** quando todas as
conexões próximas já estão em `world.visited`, `nao_visitados` fica vazio e o
perfil cai em `pool = conns` (todas visitadas) → escolha aleatória. Como o
interior (`Salão do Jarl`) tem **uma única saída** (de volta a Skallgard), o par
skallgard↔salão vira um pêndulo: de Skallgard há 25% de reentrar no interior;
de dentro, a única conexão é voltar. O perfil não tem memória anti-backtrack.

**Efeito colateral no produto:** com o explorador preso quicando, a recompensa de
1ª visita (`loot-exploracao`, fog of war) NUNCA é exercitada — o harness não mede
o que a spec entregou. Também mascara o teste de letalidade por exploração.

**Objetivo:** o perfil Explorador **avança** por fronteira (nós/interiores não
visitados) e **não faz backtrack imediato** quando há alternativa, exaurindo o
mapa em vez de oscilar. É correção de POLÍTICA de teste — determinística, sem LLM.

## 2. Requisitos

- **R1 — Sem backtrack imediato.** O explorador não retorna ao nó de onde
  ACABOU de vir quando existe qualquer outra conexão. Mantém memória curta
  (`_recent` deque por instância/run, tamanho ~4) das últimas localizações.
- **R2 — Fronteira primeiro.** Prioridade de destino: (a) conexões não visitadas
  → (b) interiores não visitados → (c) conexão visitada menos-recentemente
  (nunca a última). Só cai em "Observo os arredores" se for genuíno beco sem saída.
- **R3 — Determinismo preservado.** `(profile, seed)` continua reproduzível: a
  memória é interna, ordenação estável, `rng` é a única fonte de aleatoriedade.
  A cadeia de decisão nova é pura sobre `(state, _recent, rng)`.
- **R4 — Sem regressão nos outros perfis.** Só `Explorador` muda; `_Base` e
  helpers compartilhados (`_connections`) intactos ou aditivos.
- **R5 — Invariante/telemetria de loop (opcional, barato):** telemetria do
  harness conta “oscilações A→B→A” por campanha; um teste assegura que o
  explorador não repete o mesmo par de locais > K vezes seguidas num mapa com
  fronteira aberta.

### Fora de escopo

- **Game-side "o mundo não puxa o jogador"** — que interior tenha só 1 saída e
  que exploração não ofereça gancho de avanço é observação de design (imersão),
  não bug do harness. Spec própria se o usuário quiser puxar o jogador via
  narração/quest. Aqui só a política de teste.
- **Letalidade por entrar em zona high-danger** — é a spec C (checkpoints) +
  `letalidade-early-game-v2`.

## 3. Design técnico

`playtest/profiles.py` — `Explorador`:

- Guardar `self._recent: deque[str]` (maxlen ~4), atualizada a cada `next_action`
  com `_current_id(state)` (ou registrar o destino escolhido).
- Reescrever a cascata de escolha:
  1. `interiors_nao_visitados` → entrar (probabilidade mantida, mas só se houver
     interior novo).
  2. `conns_nao_visitadas` (exclui `_recent`) → viajar.
  3. `conns_visitadas` menos-recentes, **excluindo o nó anterior** → viajar.
  4. Fallback: "Observo os arredores com atenção."
- `_recent` reseta junto com o reset de estado por campanha (o runner instancia o
  perfil por campanha — confirmar; se o perfil for singleton entre campanhas,
  resetar no início de cada run).

## 4. Plano passo a passo

1. **Teste primeiro** (`tests/test_playtest_profiles.py` ou
   `test_playtest_harness.py`): montar `state` com Skallgard (conns visitadas +
   interior visitado) e assertar que o explorador NÃO produz o par
   skallgard→salão→skallgard em 6 chamadas; que prioriza um nó não visitado
   quando existe; que reseta memória entre campanhas.
2. **Implementação:** memória `_recent` + cascata R2.
3. **Verificação:** `uv run pytest` verde; run mock `--profile explorador
   --turns 50` mostra `locations_visited` subindo (não travado em 1–2).

## 5. Critérios de aceite

- [ ] Explorador não oscila A→B→A com fronteira aberta (teste)
- [ ] Prioriza nó/interior não visitado; sem backtrack imediato
- [ ] Determinismo `(profile, seed)` preservado (mesma seed → mesma trilha)
- [ ] Outros perfis inalterados
- [ ] Run mock: `locations_visited` do explorador sobe vs baseline (1–13 → maior cobertura)
- [ ] `uv run pytest` verde

## 6. Smoke / validação

- `uv run python -m playtest run --profile explorador --turns 50` (mock) →
  `report` mostra `locais` maior e sem carrossel; nenhum turno "Observo" em loop.
- (Opcional, com a spec `loot-exploracao`) confirmar que agora a recompensa de
  1ª visita dispara durante o run do explorador.

## 7. Riscos & compatibilidade

- **Baixo risco:** muda só um perfil de teste, sem tocar no motor de jogo.
- **Determinismo:** memória interna pode alterar a trilha exata de runs antigos
  do explorador — esperado (o objetivo é justamente mudar a trilha). Seeds
  continuam reproduzíveis dali pra frente.
