# SPEC-303 + SPEC-307 — revisão sol (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / sol · **Data:** 2026-10-24 · **Commit revisado:** `6383910c`
> (branch `spec-307` = `3dca5fc8` SPEC-303 + `b490fd9a..6383910c` SPEC-307, diff vs `main`)

## Escopo

Revisão das duas specs juntas: `services/world_calendar.py` (novo), `data/world/calendar.json`,
`festivals.json`, `signals.json`, os hooks em `world_engine`/`world_pressures`/`location_states`/
`world_validators`/`event_processor`/`world_perception`/`economy`, `world_utils.py` (viagem, clima,
encontros, `clock_label`), `agents/storyteller.py`, `agents/world_simulator.py`, `api.py`
(`_world_block`, `_date_block`, `_news_date_label`, `_season_view`, `_create_game`),
`game_engine.py`, `state.py`, `playtest/{invariants,report,runner,telemetry}.py`, `web/src`
(`clockLabel.ts`, `heardNews.ts`, `PlayScreen.tsx`, `types.ts`) e os testes `test_spec303_*`/
`test_spec307_*`. Ficou fora: suíte completa, smoke real §6 (os dois continuam pendentes) e
M1/M2 da SPEC-285. `evals/` não foi tocado (diff vazio).

## Pontos de foco conferidos

1. **Data num ponto único.** `world_calendar.date_at` é a única derivação; `clock_label`,
   API (`_date_block`, `_news_date_label`), `world["date"]` (writers: só `calendar_day_hook` e
   `init_new_game`, só em `on`) e storyteller/world_simulator passam por ela. 7 meses × 20 dias,
   semana dos Cinco Sinos, `YEAR_BASE=112`, `ERA=7` → `"3º dia de Vorrnak, Sino de Cobre — Ano
   112 da Era 7"`. O digest de virada de estação diz "Começa o mês de X" + o texto sensorial (sem
   nome genérico). Nomes genéricos sobram só no narrador e num campo de API que a web não mostra
   (P2-4).
2. **Migração v1→v2.** `migrate_calendar` mapeia proporcionalmente dentro da mesma estação
   (`doy_new` fica no bloco da estação) e corrige o ano com `year_offset`; `season_at` devolve o
   ano interno, então o `festa_id` é o mesmo da v1. Teste: 56 dias × 3 offsets. Save sem
   calendário cria a v2 no próximo tick (`anchor = day-1`). Em `off`/`shadow`, `clock_date_label`
   devolve `""` e o texto legado `Dia N · Período` sai byte a byte (testado). Versão desconhecida
   fica neutra e nunca é recriada.
3. **Festas.** Crise vence festa nos dois sentidos: o início cancela se o local tem estado ou a
   região tem crise ativa/anunciada; `pick_crisis_target` aceita local em `festa`; o fim só limpa
   se `crisis_id == festa_id`. Anúncio `start_day - FESTIVAL_HERALD_DAYS(2)`. Na percepção,
   `seen_everywhere` exige `visibility == "global"` **e** `kind == "estacao"` (festa.inicio é
   local, festa.proxima/cancelada regionais). `festa_id = sha256(game|festival|ano interno)`, e o
   agendamento pula `festa_id` conhecido, então não repete após a migração (testado).
4. **Passo de Skallgard.** `pass_closed` é derivado de `world["season"]` (nunca gravado). A
   travessia soma `PASS_EXTRA_PERIODS=2`, força neve no destino e nunca recusa
   (`test_winter_crossing_never_refused`). `route_blocked` não é usado: o par fechado entra só como
   `extra_blocked` na escassez do comércio (D5). A nevasca não tem `rest_block`, então não há
   softlock em Skallgard (única saída: `montanhas_afiadas`).
5. **Estação não abre crise.** Os offsets somados à baseline batem no teto exato de SINAL=40 (sem
   passar): skallgard fome 25+15, deserto_zhur fome 30+10, pântano praga 30+10. Sim 120 d × 20
   seeds com calendário `on`: S2 = [] (nenhuma crise extra), S3/S4 ok, C1 = 10/16/10/12,5. Com
   20 seeds o brekmar dá 16, e o README da 307 mostra o mesmo 16 com `off` nessa amostra
   (ruído). Com 60 seeds o registrado é 10/15/10/11, dentro de [10,15].
6. **Seed 26 `combate`. Reproduzido:** com `RPG_CALENDAR=on`, 1 `combat.no_progress` no turno 93;
   com `off`, 0. **Diagnóstico:** a primeira divergência é no turno 64 (chegada ao Pântano da
   Melancolia na primavera). O multiplicador de clima `pantano_melancolia.primavera.miasma = 1.3`
   gera "Miasma denso", que tira 1 de Vitalidade (3→2). Daí em diante o RNG segue outro caminho.
   O empate dos turnos 89–93 (pm_profundezas, druida + espectro) é causado pelo **perfil**: ele
   repete "Liturgia da Espera", uma carta **1×/cena já gasta** (`'Liturgia da Espera' já foi
   usada (1×cena)`), enquanto os golpes dos dois lados erram. A causa é
   `playtest/profiles.py:386-393`: `payable_cards` filtra só pelo custo de entropia e não pela
   frequência de uso. **Não bloqueia** 303/307. O calendário só expõe um defeito latente do harness
   por efeito borboleta. Mexer no multiplicador de clima para zerar essa seed seria calibrar para
   uma seed só. A meta M5 = 0 fica quebrada nesta seed com o default (`on`) até o follow-up P2-1.
7. **API/web.** `date` sai por lista branca (`label, day_of_month, month, month_id, weekday,
   year, climate, season_chip`); `news[].date_label`; `season` só `{id,label}`;
   `epoch_offset`/`year_offset`/catálogo/`closed_in` não vazam (testado). `npx tsc --noEmit`
   exit 0; `node --test` clockLabel/heardNews 4/4.

Outros: hooks `pre` com `try/except` + `log_fallback` (um hook que falha não derruba o tick);
nenhum `with_structured_output` novo; nenhum valor do LLM entra no calendário (o validator rejeita
`cause="calendario"` fora do catálogo); nenhum segredo em log; round-trip save/load v1/v2/sem
calendário testado (`test_save_load_roundtrip_v1_v2_none`); invariantes novos (`params_changed`
com exceção da migração, `festa_over_crisis`, `season_regressed`, `date_regressed`/`date_stale`).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 (follow-up, fora do escopo) | `playtest/profiles.py:386-393` | `payable_cards` ignora a frequência da carta (1×cena/1×dia): o perfil `combate` repete carta gasta e gera `combat.no_progress` (seed 26, nível 5, 200 t, calendário `on`) | Filtrar cartas já usadas com a mesma regra de `services/cards.py:349` (ou expor um `card_usable(state, cid)` reutilizável); rerodar seeds 21–32 com `on`. Não ajustar `weather_mult` para isso |
| P2-2 | P2 | `specs/SPEC-307-calendario-de-valoria.md` R11, R12 e §1 | O texto diz `festa_id` com ano **exibido** e dá o exemplo "Eco — Ano 1"; o código usa o ano **interno** (`world_calendar.py:161-162`, `:448`), o que é correto para a continuidade com a v1. O formato real é Cinco Sinos / Ano 112 da Era 7 | Atualizar R11/R12/§1 para o comportamento implementado e as decisões D do dono |
| P2-3 | P2 | `api.py:2945` / `services/world_calendar.py:240-250` | A leitura de v1 converte por item usando o `day` do próprio item, e a migração real usa `day+1`. Resultado em save v1: rótulos das notícias não batem entre si e há um salto único de ~2–3 dias no dia do mês na migração. A estação é preservada. Impacto prático ~nulo: a 303 nunca pousou, então não há save v1 real | Aceitar e documentar, ou converter uma vez com o dia corrente e reaproveitar o mesmo `cal` nos itens |
| P2-4 | P2 (decisão do dono) | `agents/storyteller.py:588`; `api.py` `_season_view` | O narrador recebe `Estação: Primavera/Verão` nas regiões padrão (R18 manda manter), e `world.season.label` sai com o nome genérico (a web não renderiza). O LLM pode repetir "nesta primavera" ao jogador, o que contradiz "meses substituem as estações" | Confirmar no smoke §6 item 2. Se aparecer, trocar o rótulo default pelo clima do mês ou omitir a linha fora de Skallgard/Zhur |
| P2-5 | P2 (preexistente) | `tests/test_spec302_director.py:29-33` | `_PROJ` indexado por `id(sim)`: o id é reutilizado após o GC e `test_tiebreak_deterministic` falhou 1× em 4 rodadas com `-n 2` (passa em série). O arquivo não foi alterado pela branch | Criar a projeção por `run()` (sem cache global) ou guardar dentro do próprio `sim` |
| P2-6 | P2 | spec 303/307 §5 | Suíte completa, smoke real §6 e M1/M2 (R27/R29) ainda não foram executados | Fazer no pouso (`/spec-land`) e registrar no README da 307 |

Sem P0/P1.

## Correções aplicadas

Nenhuma (revisão só leitura).

## Pendências

- P2-1 → coordenador: spec/ticket de harness (SPEC-285 M5), antes de declarar M5 = 0 com calendário `on`.
- P2-2 → executor 307: ajuste de texto da spec no pouso.
- P2-4 e o smoke §6 → dono/coordenador (custo ≤ US$ 0,50).
- P2-5 → follow-up de teste (qualquer spec que toque `test_spec302_director.py`).

## Comandos rodados

```text
RPG_CALENDAR=on  py.sh -m playtest run --profile combate --turns 200 --seed 26 --start-level 5 → 200 t, 0 erros, 1/0 violação (combat.no_progress t93)
RPG_CALENDAR=off py.sh -m playtest run --profile combate --turns 200 --seed 26 --start-level 5 → 200 t, 0 erros, 0/0
diff on×off das JSONL (scripts no scratchpad) → 1ª divergência t64: "sofre 1 pelo clima (Miasma denso)"; empate t89-93 com "'Liturgia da Espera' já foi usada (1×cena)"
py.sh -m pytest -n 2 tests/test_spec303_* test_spec307_* test_spec302_* test_ambient* → 1ª rodada 1 falha (test_tiebreak_deterministic, flake P2-5); 3 rodadas seguintes 225 passed, exit 0
py.sh -m pytest tests/test_spec302_director.py (serial) → verde
RPG_WORLD_ENGINE=on RPG_CALENDAR=on py.sh docs/spec302/world_engine_sim.py --calendar on --seeds 20 --s303 → S2 [], S3/S4 ok, C1 10/16/10/12.5
cd web && npx tsc --noEmit → exit 0
node --test web/tests/clockLabel.test.mjs web/tests/heardNews.test.mjs → 4/4
git diff main...HEAD --stat -- evals/ → vazio
```
