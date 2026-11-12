-- SPEC-413. The three SECURITY DEFINER RPCs in `public` were the only app surface exposed by the
-- Data API (PostgREST) and no product code calls them (backend reads the wallet through psycopg +
-- app.* with the runtime role). Drop them, in dependency order and WITHOUT cascade: a hidden
-- dependent must fail this migration instead of silently disappearing.
-- Rollback: docs/spec413/rollback.sql. Default privileges are intentionally untouched (SPEC-413 D2).
drop function if exists public.rpg_wallet_balance();
drop function if exists public.rpg_wallet_history(integer);
drop function if exists public.rpg_current_session_active();
