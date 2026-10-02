# SPEC — Fase 10b.4 — Autenticação local, RLS e isolamento por usuário

> **Status:** `done` (2026-08-20)
> **Criada:** 2026-08-16 · **Atualizada:** 2026-08-16
> **Depende de:** [Postgres transacional](SPEC-109-fase-10b-postgres-persistencia-transacional.md) `done` · [turnos duráveis](SPEC-111-fase-10b-turnos-duraveis-concorrencia-fila.md) `done`
> **Desbloqueia:** testes multiusuário, assets privados e exposição futura da API

---

## 1. Contexto & Objetivo

Hoje possuir um `game_id` equivale a autorização; `game_id=None` escolhe o save
mais recente global e `/game/saves` lista todas as campanhas. Isso é aceitável
somente em loopback. Adicionar uma tela de login sem aplicar ownership em cada
store manteria a vulnerabilidade.

Esta spec usa Supabase Auth local para exercitar signup/login/refresh/logout e
RLS, mas mantém a fronteira OIDC/JWT. O browser conversa apenas com FastAPI; o
backend usa um adapter de identidade e conecta ao Postgres com role sem
`BYPASSRLS`. Tokens ficam em cookies HttpOnly no fluxo web, e mutações usam
proteção CSRF. A service role nunca chega ao frontend.

## 2. Requisitos

- **R1 — identidade verificada:** `owner_id` vem exclusivamente de JWT válido
  (issuer, audience, assinatura, `exp`/`nbf`); nunca de body, query, header livre
  ou `user_metadata` editável.
- **R2 — sessão web segura:** access/refresh tokens em cookies `HttpOnly`,
  `Secure` no hosted, `SameSite` explícito e paths mínimos; nenhuma credencial
  substitui `cronicas_game_id` no `localStorage`.
- **R3 — CSRF:** toda mutação autenticada por cookie exige token CSRF vinculado
  à sessão; Origin/Host também são validados. GET não produz efeito colateral.
- **R4 — rotas Auth:** signup, login, refresh, logout e session funcionam contra
  Supabase Local; respostas e erros são sanitizados e rate-limited.
- **R5 — ownership total:** jogos, checkpoints, operações, turnos, eventos,
  catálogo, memória, jobs e assets aplicam owner no adapter e no banco.
- **R6 — RLS defesa em profundidade:** RLS habilitada em toda tabela tenant;
  policies têm `USING` e `WITH CHECK` quando aplicável; role da API não ignora RLS.
- **R7 — não enumeração:** acesso a game/operação/asset de outro usuário retorna
  404 na API; diferenças de tempo/corpo não revelam existência de UUID.
- **R8 — múltiplas campanhas:** cada campanha tem exatamente um owner; um usuário
  pode possuir várias campanhas, alinhado à tela de saves atual.
- **R9 — local sem auth restrito:** `RPG_AUTH_MODE=disabled` só funciona nos
  perfis `legacy`/test e em bind loopback, com principal UUID fixo explícito.
- **R10 — lifecycle:** logout revoga a sessão possível, limpa cookies e estado
  visual; deleção de conta é workflow autenticado com export/confirm/cleanup de
  objetos antes de remover a identidade.
- **R11 — secrets:** service/admin keys apenas em backend/worker/migrations;
  logs não contêm JWT, e-mail, cookie, narrativa ou reset link.
- **R12 — testes com dois usuários:** A e B exercitam todas as operações e
  queries, inclusive acesso SQL/RLS; zero row/object cruzado.
- **R13 — e-mail local:** confirmação/reset usam a caixa local da stack; OAuth,
  SMTP e deliverability reais ficam para certificação cloud.

### Fora de escopo

- OAuth social, MFA, SSO, domínio de e-mail, CAPTCHA e política comercial de senha.
- Acesso direto do frontend às tabelas de gameplay/PostgREST.
- Compartilhar campanha/co-op ou transferir ownership.
- Autorizações administrativas/moderação além de CLI local auditada.

## 3. Design técnico

### Arquivos novos

- `infrastructure/supabase_identity.py` — cliente Auth via `httpx` e verificação JWKS.
- `services/auth_sessions.py` — cookies, CSRF, refresh e principal FastAPI.
- `services/authorization.py` — helpers owner-scoped e erros não enumeráveis.
- `supabase/migrations/<ts>_rls.sql` — roles, grants, helper e policies.
- `web/src/components/AuthScreen.tsx` — signup/login/feedback sem token JS.
- `web/src/auth.ts` — session/CSRF/logout via mesma origem.
- `tests/test_auth_api.py` — contratos sem provider com fake IdP.
- `tests/test_rls_local.py` e `supabase/tests/rls.sql` — integração/pgTAP local.
- `tests/test_auth_browser.py` — browser Python opt-in.

### Arquivos alterados

- `api.py` — dependencies de principal/CSRF, rotas `/auth/*`, owner em todos endpoints.
- `web/src/api.ts` — `credentials: "include"`, CSRF e tratamento 401; sem bearer em storage JS.
- `web/src/App.tsx`/`SaveScreen.tsx` — sessão, logout e limpeza do game selecionado.
- `infrastructure/postgres*.py` — `SET LOCAL` do subject verificado por transação.
- `scripts/dev_stack.py`, `.env.example` — URLs/issuer/audience/cookies locais.

### Principal e cookies

```python
@dataclass(frozen=True)
class AuthPrincipal:
    user_id: UUID       # JWT sub verificado
    issuer: str
    audience: tuple[str, ...]
    session_id: str | None
    expires_at: datetime

def require_principal(request: Request) -> AuthPrincipal: ...
def require_csrf(request: Request, principal: AuthPrincipal) -> None: ...
```

Cookies sugeridos:

- `rpg_access`: HttpOnly; `SameSite=Lax`; curto; path `/`.
- `rpg_refresh`: HttpOnly; `SameSite=Strict`; path `/auth/refresh`.
- `rpg_csrf`: legível pelo cliente, valor opaco assinado; enviado em `X-CSRF-Token`.

O adapter de Auth recebe publishable key no backend. Service role só é usada em
operações administrativas/worker estritamente tipadas, nunca para login normal.

### RLS portátil

```sql
create or replace function app.current_owner_id()
returns uuid language sql stable security invoker
set search_path = ''
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

alter table app.games enable row level security;
alter table app.games force row level security;

create policy games_select_own on app.games
for select to rpg_api using (owner_id = app.current_owner_id());

create policy games_insert_own on app.games
for insert to rpg_api with check (owner_id = app.current_owner_id());

create policy games_update_own on app.games
for update to rpg_api
using (owner_id = app.current_owner_id())
with check (owner_id = app.current_owner_id());

create policy games_delete_own on app.games
for delete to rpg_api using (owner_id = app.current_owner_id());
```

O mesmo padrão cobre tabelas tenant. A conexão de migration é separada. A role
`rpg_api` não possui `BYPASSRLS`, `CREATE`, acesso a `auth.users` ou grants além
dos objetos necessários. `request.jwt.claim.sub` é configurado pela camada DB
somente depois da verificação do token e dentro de `SET LOCAL`.

### Contrato de rotas

```text
POST /auth/signup   {email,password} → 202/validation genérica
POST /auth/login    {email,password} → cookies + {authenticated:true, csrf_token}
POST /auth/refresh  CSRF/cookies     → cookies rotacionados
POST /auth/logout   CSRF/cookies     → 204 + cookies expirados
GET  /auth/session                   → {authenticated,user:{id},csrf_token}
```

E-mail não é retornado se o produto não precisa exibi-lo. Mensagens de signup e
reset não confirmam se uma conta existe.

## 4. Plano passo a passo

### Etapa 1 — Auth service com fake

1. **Testes** (`test_auth_api.py`): assinatura/iss/aud/exp, cookie flags, refresh
   rotation, logout, CSRF ausente/inválido, Origin, rate limit e logs sem token.
2. **Implementação:** adapters/dependencies/rotas sem tocar GameStore ainda.
3. **Verificação:** suíte offline com fake IdP.

### Etapa 2 — Ownership na API inteira

1. **Testes:** dois principals em state/codex/saves/export/action/SSE/death/
   equip/levelup/delete/operation; `None/latest` restrito ao owner.
2. **Implementação:** principal obrigatório e passagem a todos stores.
3. **Verificação:** UUID de B sempre 404 para A; zero mutação.

### Etapa 3 — RLS/grants

1. **Testes** (`test_rls_local.py`, pgTAP): SELECT/INSERT/UPDATE/DELETE own vs
   foreign, missing claim, forged owner, service/admin separation.
2. **Implementação:** migrations/policies/role sem bypass.
3. **Verificação:** testes tentam SQL direto com role da API.

### Etapa 4 — Supabase Auth local e frontend

1. **Testes:** signup/login/refresh/logout reais, confirmação/reset via mailbox
   local; browser continua campanha após refresh e não guarda JWT no storage.
2. **Implementação:** adapter httpx + AuthScreen/session flow.
3. **Verificação:** desktop/mobile, console limpo e dois usuários simultâneos.

### Etapa 5 — Lifecycle de conta

1. **Testes:** export antes da exclusão, confirmação recente, jobs/assets
   cancelados/removidos na ordem, sessão invalidada.
2. **Implementação:** workflow/CLI local; endpoint só após confirmação explícita.
3. **Verificação:** nenhuma row/objeto órfão e nenhuma conta alheia afetada.

## 5. Critérios de aceite

- [x] Tokens nunca aparecem em local/sessionStorage, logs ou respostas de jogo.
- [x] Cookies/CSRF/Origin bloqueiam mutação cross-site.
- [x] JWT inválido/expirado/issuer ou audience errada é 401.
- [x] A/B têm isolamento integral em API, SQL/RLS, jobs e export.
- [x] Role da API não possui BYPASSRLS nem privilégios de migration/admin.
- [x] Todas as policies de update possuem `USING` e `WITH CHECK`.
- [x] `game_id=None` e `/game/saves` operam somente no owner atual.
- [x] Login/refresh/logout e e-mail local passam sem serviço externo.
- [x] `legacy` loopback continua jogável com principal local fixo.
- [x] `uv run pytest -m infra_local` + pgTAP + suíte offline verdes.
- [x] Guard de FallbackLLM — N/A; nenhum invoke novo.
- [x] Saves importados recebem owner explícito sem alterar conteúdo mecânico.

## 6. Smoke test com LLM real

Zero LLM necessário. Smoke local com usuários A/B: A cria e joga via SSE; B
tenta todos os UUIDs de A e recebe 404; refresh da sessão de A preserva acesso;
logout bloqueia novo turno. Um turno MockLLM é suficiente.

## 7. Riscos & compatibilidade

- **Cookies em dev cross-port:** Vite deve usar proxy de mesma origem; não relaxar
  cookie/CORS para contornar configuração.
- **JWT/JWKS rotation:** cache respeita TTL/kid e refaz fetch uma vez; fail closed.
- **RLS falsa segurança:** frontend não ganha acesso direto; adapters continuam
  passando owner em toda query e testes cobrem os dois níveis.
- **User deletion + Storage:** cleanup de objetos ocorre antes de remover a
  identidade, com retry durável.
