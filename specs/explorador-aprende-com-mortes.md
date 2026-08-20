# SPEC — Memória de perigo do perfil explorador após morte

> **Status:** `in-progress`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** matriz A1 `20260820-185627-750638`, par 2
> **Depende de:** `continuidade-memoria-morte`

## 1. Contexto & objetivo

O explorador nível 3 morreu nove vezes em 71 ações. As últimas cinco mortes
ocorreram na Fortaleza de Vorr; após cada restore para Skallgard, o perfil lia o
mapa restaurado, tratava Vorr como fronteira inédita e voltava ao mesmo local.
O motor de checkpoint estava correto, mas o agente não se comportava como uma
pessoa que lembra onde morreu.

`continuity.death_history` é metatempo preservado entre restores. O explorador
deve usar essa memória para não escolher novamente uma localização que já o
matou na sessão. Se todas as saídas conhecidas forem letais, ele observa/recupera
em vez de viajar deliberadamente para a morte.

## 2. Requisitos

- **R1:** registros de morte passam a incluir `location_id`, sem remover o nome.
- **R2:** o explorador resolve registros legados apenas com nome e forma um
  conjunto determinístico de locais fatais.
- **R3:** interiores, fronteiras e rotas exauridas excluem locais fatais.
- **R4:** destino de fuga continua priorizando uma saída válida; nunca bloqueia
  a evasão por o local atual constar no histórico.
- **R5:** sem saída não fatal, o perfil escolhe ação local prudente, não viagem.
- **R6:** reset de perfil limpa apenas memória efêmera; `death_history` do estado
  continua sendo a fonte de verdade entre restores.

### Fora de escopo

- Alterar dificuldade, inimigos ou fórmula de fuga.
- Impedir um jogador humano de revisitar o local.
- Mudar checkpoints do produto.

## 3. Design técnico

- `services/continuity.py` e `playtest/runner.py`: `location_id` aditivo.
- `playtest/profiles.py`: helper de locais fatais e filtro no `Explorador`.
- `tests/test_explorador_loop.py`: morte por id/nome, alternativa segura e
  ausência de alternativa.

## 4. Plano passo a passo

1. Escrever regressões para histórico moderno/legado e rota segura.
2. Adicionar `location_id` aos registros e filtro determinístico.
3. Rodar testes focados e suíte completa.
4. Reiniciar A1 e comparar mortes do mesmo par.

## 5. Critérios de aceite

- [x] Local que matou o explorador não é escolhido novamente após restore.
- [x] Histórico legado por nome produz o mesmo bloqueio.
- [x] Sem alternativa segura, não há viagem suicida.
- [x] Death log preserva nome e ID.
- [x] Suíte completa verde (1608 testes).
- [ ] A1 não repete o loop de mortes em Vorr.

## 6. Smoke real

O par explorador nível 3 da A1 é o smoke. O transcript/death log deve mostrar
que, após uma morte, o local fatal deixa de ser destino do perfil.

## 7. Riscos & compatibilidade

O campo é aditivo e saves antigos continuam válidos. A política afeta somente o
agente de playtest, não as escolhas do jogador nem a mecânica do mundo.
