# Fechamento local e gates restantes — 2026-09-17

## Situação auditada

O inventário contém 152 specs reais (TEMPLATE excluído): 140 `done`, 11
`in-progress` e uma `draft`. O fechamento local corrige as lacunas encontradas
na revisão, mas não transforma validação real incompleta em aceite.

## Matriz B preservada

Run `20260831-172359-833976`: **751/2.000 turnos registrados**, três campanhas
completas e uma parcial; zero violações `error`, um warning de abertura repetida,
um erro de turno e zero erros de observabilidade. Foram 1.954 tentativas LLM,
1.944 sucessos, dez falhas, uma invocação terminal e US$ 0,54712.

| Perfil | Turnos | Resultado |
|---|---:|---|
| normal, nível 1 | 200/200 | sem erros/violações |
| explorador, nível 3 | 200/200 | sem erros/violações; quatro quedas/restores |
| diplomático, nível 5 | 200/200 | um warning de abertura repetida |
| combate, nível 7 | 151/200 | DeepSeek HTTP 402, saldo insuficiente |
| perfis 5–10 | 0/1.200 | não iniciados |

A tentativa de retomada de 16/09 também falhou no preflight com HTTP 402, antes
de executar campanha. A indicação inicial de continuar do índice 4 foi revista:
R6 de `playtest-matrix-continuacao` exige B formal desde o índice 1, e as
correções adicionais mudaram o código. Os dados anteriores servem como histórico,
não certificam o build atual. Nenhum artefato anterior foi sobrescrito.

## Correções concluídas no código

- Referências de NPC por nome/chave/ID usam a mesma ficha no storyteller,
  ator e recrutamento. A invariante compara aliases; migração preserva a ficha
  de origem mais antiga quando há `created_turn` e a dinâmica mais recente.
  Sem datas confiáveis, preserva a primeira identidade, sem inferir qual prosa
  é verdadeira.
- Guard repara uma transição órfã uma única vez, sem avançar turno/local;
  finalizador recusa boundary inválido e inclui readiness no recibo.
  Combate e escolha de morte continuam com seus resolvedores próprios.
- Decisão de perseguição tipada; bloqueio por lifecycle não aparece como
  progresso de fuga. O teto de tentativas não supera inelegibilidade.
- Crônica de queda não afirma recuperação nem saque antes da escolha de morte.
- Viagem entre regiões marca replan inclusive em encontro e falha do narrador;
  a invariante exige essa flag para conceder a janela de viagem.
- Diálogo NPC recebe aberturas anteriores, normaliza aspas externas e varia
  abertura repetida sem request adicional. Memória mantém a fala original.
- Diplomático esgota suas quatro perguntas e muda de objetivo/local;
  outcome antigo de interação não emite warning em turnos posteriores.
- Vetor compartilhado verifica modelo e dimensão declarada; fontes degradam
  isoladamente. A spec de latência registra o experimento/no-go e seus limites
  reais, inclusive que cancelar `to_thread` não cancela HTTP em andamento.

## Specs que aguardam aceite real

As onze continuam `in-progress`, com critérios locais separados do gate externo:
`contrato-canonico-ciclo-vida-acoes`, `resultado-canonico-turno-apresentacao`,
`interacoes-progresso-elegibilidade`, `structured-output-evidencia-recuperacao`,
`protocolo-transicoes-criticas-checkpoint`, `semantica-queda-morte-memoria`,
`grounding-local-memoria-canonica`, `grounding-posse-inventario-memoria`,
`identidade-canonica-npc-memoria`, `replan-diferido-combate-invariante` e
`matriz-longrun-multiperfil-niveis`.

Após recarregar o provider, executar:

```text
uv run python -m playtest matrix-suite --label B --turns 200 --real --max-requests 800 --max-cost 0.25 --start-index 1 --routes-profile deepseek-paid
```

É necessário auditar os dez pares, escrever a comparação A/B e só então marcar
os critérios reais. O teto configurado é US$ 0,25/800 requests por campanha;
HTTP/quota permanece fail-closed. A matriz curta offline não substitui esse gate.

## Escopo externo e backlog conceitual

`fase-10b-certificacao-cloud-portavel` permanece `draft`: requer contas, região,
recursos e orçamento de Railway/Supabase remoto. Nenhum deploy foi realizado.
Sprites/som (Fase 9) não têm spec aprovada nem assets de áudio selecionados.
A substituição futura do wrapper FAISS descontinuado e a limpeza seletiva de
saves históricos permanecem débitos documentados; campanhas do usuário foram
preservadas. Checkboxes históricos de specs já entregues não foram marcados
automaticamente como se constituíssem nova validação.

As artes `web/public/art/v1` foram verificadas fora do sandbox: estão presentes
e sem exclusões no Git. `.claude/settings.local.json` é configuração local e
fica fora do fechamento.

## Verificação desta revisão

- Validador de conteúdo: zero erros e zero avisos, inclusive assets visuais.
- Frontend: TypeScript/Vite verde, 457 módulos.
- Ruff nos arquivos Python alterados: verde.
- `uv run pytest`: **1681 passed, 16 skipped, 14 deselected**, 399,43 s;
  único warning: descontinuação de `langchain-community` no import de FAISS.
  Os skips/opt-ins não equivalem a validação atual de cloud ou LLM real.
- Matriz curta offline: dez perfis × três turnos, **30/30**, zero erros e
  zero violações; manifesto `20260917-112524-245088` completo.
- Viagem entre regiões tem quatro regressões diretas: narração normal,
  encontro, resposta estruturada inválida e exceção do provider.
