# SPEC-371 — smoke real (§6), 03/11

Rotas de hoje (DeepSeek no tier FAST/CLASSIFY/SMART; 0 `fell_back` em todos os turnos). Sem chave ou
segredo neste arquivo. Flags: `RPG_FAUNA`, `RPG_FAUNA_SINAIS`, `RPG_FAUNA_SABER`, `RPG_ENEMY_DECKS`,
`RPG_ENEMY_INTENT`, `RPG_WORLD_ENGINE` = `on` (e `off` só do saber na comparação do passo 7).

**Desvio de método.** Em vez de subir a API, o driver (scratch, não versionado) chama `main.app.invoke`
(o mesmo grafo que a API invoca) com um estado em memória (nada gravado em `saves/`): herói `explorador`
nível 3 em Nova Arcádia, Noite, perigo 4 em `na_anel_lama`, presença ativa de `mon_arame_vivo` com 1 sinal
mostrado (`rastro`), `bestiary_knowledge` vazio. Os dossiês saem de `discovery.bestiary_view` +
`dossiers.creature_dossier` (as funções que a rota usa); o chip do navegador foi conferido pelo JSON de
`combat.pressagios_publicos` (o e2e com payload sintético já passou na Etapa 5). 8 turnos, 19 chamadas LLM.
Duas execuções `on` deram a mesma trajetória.

| Passo | Resultado |
|---|---|
| 1 save scratch | OK. |
| 2 "sigo o rastro" | OK. Combate abriu na rodada 1 (`mon_arame_vivo` + Degolador da Mão Sombria). Com o `bk` do turno 0 (`sinais_vistos=["rastro"]`, `fought=1`) o dossiê mostra "Rastros lidos" com o texto do rastro e NÃO tem `contra_jogo`. |
| 3 chip com `prenuncio` | OK pelo JSON: rodada 3 traz `prenuncio` "Arame Vivo recolhe o arame das costas e abre os ganchos das mãos." na linha do Arame Vivo (e o do Degolador nas rodadas 2, 5, 8). Navegador não aberto (RAM). |
| 4 aguentar a assinatura | PARCIAL. Defendi na rodada com o `prenuncio`; no turno seguinte `bk.mon_arame_vivo` = `assinaturas_sobrevividas 1`, `telegrafos_vistos` com o texto, `saber_revelado {sobreviveu, turn 5}` (OK). **FALHA: a linha "Você aprendeu como enfrentar …: veja o Bestiário." (R14) não aparece em lugar nenhum do estado do turno** (varri o JSON inteiro: mensagens, `last_mech_log`, combate). Provável causa: `logs` entra no prompt do narrador e no `mech_log` estruturado, não como texto fixo ao jogador. Não corrigido (regra do smoke). |
| 5 "Você sabe:" | OK. Na rodada 6 a linha do Arame Vivo traz `prenuncio` + `contra_jogo` ("Manter distância e cortar o arame antes que feche…") + `carta_nome` "Gancho de Arame" + `valor_estimado 3`; `enemy.saber_jogador` carimbado. Observação: `carta_nome`/`valor_estimado` já vinham desde a rodada 1 (antes do saber), por regra anterior de conhecimento do ator, não por esta spec. |
| 6 preparação da cena | NÃO EXERCITADO. O encontro não era Elite/Abismo, então `_wants_prepared_scene` não chamou a LLM (0 prompts de preparação). Cobertura só pelo teste de prompt capturado. |
| 7 custo | Chamadas iguais: `on` 19 = `off` 19, por turno `[4,2,2,2,2,2,2,2]` nos dois (mesma sequência de textos). Latência: p50 do turno `on` 3,57–3,65 s vs `off` 3,29 s (Δ ≈ +0,3 s, contra o alvo de ≤ 100 ms). Medida dominada pela variância de rede/provedor (turnos de 3,0 a 4,1 s); não separa o custo de prompt. Tratar como NÃO CONCLUSIVO. |

Pendências para o coordenador: (a) R14 não chega ao jogador no fluxo real (decidir: linha fixa no
`mech_log`/registro, ou rebaixar o requisito); (b) passo 6 sem cobertura real; (c) latência: repetir com
mais turnos ou medir o custo de CPU do saber à parte.

## Fechamento das pendências (03/11, 2ª rodada)

- **R14 corrigido.** A linha "Você aprendeu como enfrentar …: veja o Bestiário." agora entra em `status_logs` (o caminho das linhas mecânicas visíveis: `combat.last_mech_log` e REGISTRO), não em `logs` (que só alimenta o prompt do narrador). Teste escrito antes e visto falhar: `test_r14_linha_chega_ao_registro_do_jogador` (uma linha no `last_mech_log`) e `test_r14_flag_off_sem_linha`. Golden de 30 turnos da 360 com a flag `off` e `test_spec371_flags_off` seguem verdes.
- **Passo 6 (real, Elite).** `mon_fila_de_grilhoes` (elite de Nova Arcádia) com `sinais_vistos=["rastro","som"]` e `aproximacao` no hint, `_prepare_scene` com a LLM real: 1 prompt de preparação com `Saber do herói: O herói leu antes: rastro, som. Aproximação: Do fundo do pátio vem uma fileira de troncos soldados pelos ombros, e todas as cabeças viram juntas para você.` (sem nome nem id da criatura); a cena validou (`validate_preparation` ok, 3 zonas, 2 objetos). O DeepSeek deu timeout (12 s) e o Groq respondeu (1 `fell_back`, caminho normal do `RoutedLLM`).
- **Passo 7 (CPU, MockLLM, offline).** `docs/spec371/custo_cpu_saber.py`: 242 rodadas por modo, mesmas lutas/sementes do `mon_arame_vivo`, bloco pós-rodada (`absorb` + `stamp_actor` por inimigo + `forecast_round` + `public_round` + `record_promise`): `off` p50 0,30 ms (p95 0,41), `on` p50 43,1 ms (p95 73,0). **Δ p50 = +42,8 ms por rodada (alvo ≤ 100 ms: OK).** O custo do `on` vem quase todo de `normalize_bestiary_id` → `load_bestiary` a cada ator em `absorb`/`stamp_actor`; um cache por rodada o derrubaria, mas não é necessário para o alvo. Com a LLM de ~3 s por turno, o Δ de CPU é ~1 %.
