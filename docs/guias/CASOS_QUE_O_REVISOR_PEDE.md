# Casos que o revisor pede

Lista curta de casos adversos que a revisão independente já pegou (SPEC-415 R12). Alimentada
pelo próprio revisor; um domínio por seção, no máximo 12 itens cada, fonte entre parênteses.

Regras:

1. O executor de spec `médio`/`alto` lê as seções dos `Domínios de revisão` da spec **antes**
   de escrever o primeiro teste e cobre cada item aplicável, ou o marca "não se aplica" no hand-back.
2. A cada `CHANGES_REQUIRED`, o revisor acrescenta **uma** linha no domínio do achado mais grave
   (neste arquivo, no worktree revisado).
3. Seção cheia (12 itens): o revisor funde dois itens parecidos em vez de passar do teto.

## concorrência

- Cancelamento durante cada `await to_thread(...)` com efeito (financeiro ou de arquivo): o thread termina sozinho; o `finally` não pode rodar em paralelo com ele. Teste: fake lento + cancelar no meio + afirmar ordem (SPEC-412 P1, `services/speech_to_text.py:326`)
- Flag "já começou" (`begun = True`) só depois do `await`: cancelado no meio, o efeito existe e o fechamento não roda. Teste do cancelamento em `begin` (SPEC-412 P2)
- Recurso de `with` (diretório temporário, arquivo) liberado enquanto o thread ainda o usa: shield-e-espera também no passo não financeiro (SPEC-412 rodada 2 P2, `prepare_audio`)
- Espera em teste (`while not evento: await sleep`) sempre com teto (`asyncio.timeout`): regressão não pode pendurar a suíte (SPEC-412 rodada 2 P3)
- Duplo cancelamento e exceção do thread durante a espera: um teste cada (SPEC-412 rodada 2 P3)
- Exceção do thread engolida no cancelamento: `logger.warning`, nunca silêncio (SPEC-412 rodada 2 P3)

## sql-rls

- `throws_ok(…, '42501')` não distingue RLS, falta de grant e trigger de tombstone: afirme a mensagem (`throws_like '%row-level security%'`) (SPEC-410 P3-2)
- Comentário de migração sobre roles/grants conferido contra os `grant` reais das migrações anteriores (SPEC-410 P3-1)
- Rollback é migração nova (ou `migration repair`), nunca SQL avulso: senão `schema_migrations` mente e um `db reset` reaplica (SPEC-410 P3-4, SPEC-413 P3-4)
- Migração e pgTAP que nunca rodaram em Postgres: listar em "Não rodou e por quê" e não chamar de "coberto pelo CI" se nenhum workflow roda (SPEC-413 P2-2, SPEC-410 P3-6)
- Modo `off` de flag nova tem de ser byte a byte o comportamento anterior; o que já muda em `off` vai na spec e no smoke (SPEC-410 P2-1)

## api

- Smoke de "não exposto" afirma o status e o código exatos (404 `PGRST202`), nunca `status >= 400` (SPEC-413 P2-1, `scripts/staging/smoke_ab.py:326`)
- Guard de boot/config de produção: o checklist de release recusa o marcador de staging também, não só a flag perigosa (defesa em duas camadas) (SPEC-411 P2-1)
- Guard mais largo que o uso documentado: um caso parametrizado com os valores "quase válidos" (`"true"`, `" 1 "`) (SPEC-411 P3-3)
- Rota nova num arquivo já inventariado pelo teste AST: o inventário chaveia por `arquivo::símbolo`, senão passa sem revisão (SPEC-410 P3-3)

## persistência

- Asserção vacuamente verdadeira (`balance == 0` de quem nunca teve conta): prove o gate pelo caminho que existe (SPEC-413 P3-1)
- "Trava" de allowlist = conjunto exato esperado, não só regex e unicidade (SPEC-411 P3-1)
- Writer persistente novo: round-trip save/load e save antigo carregando (AGENTS.md § Operação)

## llm-structured

- `with_structured_output(X).invoke()` pode devolver `AIMessage`: `isinstance` ou `try/except` antes de ler campo (AGENTS.md, guard de FallbackLLM)
- MockLLM devolve instância válida e esconde erro de nome/tipo de campo: o caminho novo tem smoke com chave real (AGENTS.md)
- Número vindo do LLM (ouro, dano, sinal) é validado em Python antes de mudar estado (AGENTS.md, mecânica é Python)
