from __future__ import annotations

import os
from uuid import uuid4

import pytest


pytestmark = [pytest.mark.infra_local, pytest.mark.security_local]


def test_rls_isola_games_e_role_nao_tem_bypass():
    psycopg = pytest.importorskip("psycopg")
    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    owner_a, owner_b, game_a, game_b = uuid4(), uuid4(), uuid4(), uuid4()
    with psycopg.connect(dsn) as admin:
        admin.execute(
            """insert into app.games
            (id,owner_id,schema_version,state,state_sha256,status,player_name,class_name,
             player_level,location_name,world_day,game_over,combat_simulation)
            values (%s,%s,3,jsonb_build_object('game_id',%s::text),%s,'active','A','Devoto',1,'Teste',1,false,false),
                   (%s,%s,3,jsonb_build_object('game_id',%s::text),%s,'active','B','Devoto',1,'Teste',1,false,false)""",
            (game_a, owner_a, str(game_a), 'a' * 64,
             game_b, owner_b, str(game_b), 'b' * 64),
        )
        row = admin.execute("select rolbypassrls from pg_roles where rolname='rpg_api'").fetchone()
        assert row == (False,)
    try:
        with psycopg.connect(dsn) as connection:
            with connection.transaction():
                connection.execute("set local role rpg_api")
                connection.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(owner_a),))
                assert connection.execute("select id from app.games order by id").fetchall() == [(game_a,)]
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    connection.execute("update app.games set owner_id=%s where id=%s", (owner_b, game_a))
    finally:
        with psycopg.connect(dsn) as admin:
            admin.execute("delete from app.games where id in (%s,%s)", (game_a, game_b))
