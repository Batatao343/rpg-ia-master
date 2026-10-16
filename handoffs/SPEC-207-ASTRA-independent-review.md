# SPEC-207 — parecer Astra (revisão independente e adversarial)

**Data:** 2026-10-16 · **Revisor:** Astra (≡ Opus, contexto separado) · **Veredito:** APPROVED_WITH_FIXES

## Escopo atacado
Isolamento entre donos (404 indistinguível, filtros `owner_id`), CSRF/POST, prova recente (ausente,
de outro dono, expirada), rate limit por dono, nomes no ZIP (zip slip), limites 500 turnos/25 MiB,
scrubber de PII com payloads adversariais, segredos só rotulados, ausência de prompt/resposta bruta,
pseudônimos de owner/game/action/operation, tamanho do `audit_trace` no save, falha do trace não
derruba turno, perfil legacy 404, determinismo do ZIP e `verify_audit_zip`.

## Achados e correções (aplicadas no WT)
1. **ALTA — PII escapava do scrubber.** CPF (mascarado e cru), CNPJ, celular BR cru de 11 dígitos,
   cartão, IPv6 comprimido, chaves AWS `AKIA/ASIA`, GitHub `ghp_`, Slack `xox*`, `senha:`/`cookie=`/
   `api_key=` passavam intactos e o scan final não os detectava (fail-closed cego).
   Correção: novos padrões em `services/audit_redaction.py` (bordas excluem letras/`_` para não casar
   hashes hex e ids `*_content_<hex>`); o scan passou a usar todos os padrões exceto o de telefone
   formatado (que segue separado). Testes parametrizados em `tests/test_audit_redaction.py`
   (14 payloads + 300 hashes hex sem falso positivo).
2. **ALTA — `audit_trace` inflava o save.** Medido em turno real (MockLLM): ~94 refs/turno →
   **~19 KB por linha** (≈4 MB no ring de 200, regravado a cada commit de turno). O teste de cap
   existente usava `context_refs=[]` e não pegava. Correção em `services/audit_trace.py`: refs
   agrupadas por atributos (só chaves não nulas) e, a partir da 2ª linha do ring, cada grupo guarda só
   o delta de `source_ids` em relação ao grupo de mesma seção/visibilidade/selo da linha anterior
   (`ids_prev` + `ids_add`/`ids_drop`); chaves nulas de `timing` omitidas. `expand_trace` reconstrói
   sem perda (lê também os formatos item-a-item/agrupado); o corte do ring é feito sobre linhas
   expandidas, então a nova 1ª linha volta a ser completa. Medido: 1ª linha ~4,1 KB, demais ~1,1 KB;
   **ring de 200 turnos reais ≈ 208 KB (≤ 400 KB da spec)**. Teste `test_real_turn_trace_fits_size_budget`
   (200 linhas, ≤ 400 KB, round-trip sem perda, idempotência, re-materialização no corte).
   Limite: troca de local a cada turno deixa linhas maiores (sem base comum) — pior caso não medido.
3. **MÉDIA — `game_id` cru não era valor sensível.** A forma hex (sem hífens) sobrevivia ao ZIP.
   Correção: builder/scan/verify tratam `game_id` como valor do dono (`_sensitive_values`).
   Teste `test_adversarial_player_text_and_raw_game_id_never_in_zip`.
4. **ALTA — IPv4 seguido de ponto final escapava** (`ip 192.168.0.10.`): achado ao regenerar a
   evidência; lookahead corrigido + caso no teste parametrizado.
5. **BAIXA — prova expirada sem teste.** `proof_owner` já impõe 300 s (SPEC-190); asserção adicionada
   ao teste Postgres local.

## Sem defeito (verificado)
404 idêntico alheio×inexistente (mesmo caminho `store.get`), 401 conta em exclusão, 403 sem prova/
prova de outro dono/expirada, CSRF 401, 429 por pseudônimo do dono, legacy 404, nomes de arquivo
fixos (sem zip slip), allowlist por arquivo (chave desconhecida cai), erros só por enum fechado,
zero LLM/`usage_events` no export, trace em `try/except` (não derruba turno), replay não duplica.

## Riscos aceitos / follow-ups
- Resposta não é streaming real (ZIP ≤ 25 MiB montado em memória; truncagem por bytes reconstrói
  o ZIP a cada 10% removido). Aceitável com rate limit 3/10 min.
- `generated_at` muda entre chamadas: bytes idênticos só com o mesmo `generated_at` (teste usa fixo).
- Nomes de exibição da conta não existem como campo próprio hoje; o nome do personagem é conteúdo
  de jogo e sai no ZIP por design.
- `verify_audit_zip` lê todas as entradas em memória (zip bomb só relevante para ZIP de terceiros).
