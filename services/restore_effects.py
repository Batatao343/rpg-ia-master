"""Invalidate abandoned timeline derivatives inside the restore transaction."""

from __future__ import annotations


def restore_effects(connection, *, principal, game_id, document: dict) -> None:
    checkpoint = connection.execute(
        "select game_version,memory_commit_version,timeline_epoch,canonical_turn "
        "from app.game_checkpoints where game_id=%s and owner_id=%s",
        (game_id, principal.user_id),
    ).fetchone()
    if not checkpoint:
        return  # no earlier snapshot: no history was actually rolled back
    epoch = int(checkpoint["timeline_epoch"])
    cutoff = int(checkpoint["memory_commit_version"] or checkpoint["game_version"])
    connection.execute(
        """update app.memory_documents set discarded_at=now(),embedding_status='discarded'
        where game_id=%s and owner_id=%s and discarded_at is null and
          (timeline_epoch > %s or (timeline_epoch=%s and
            (commit_version > %s or (commit_version is null and source_turn > %s))))""",
        (game_id, principal.user_id, epoch, epoch, cutoff, checkpoint["canonical_turn"]),
    )
    connection.execute(
        """update app.jobs set status='cancelled',lease_token=null,lease_until=null,
        lease_owner=null,updated_at=now() where game_id=%s and owner_id=%s
        and status in ('queued','retry','running') and
          (kind='compress_chronicle' or
           (payload->>'commit_version')::bigint > %s or
           payload->>'memory_id' in
            (select id from app.memory_documents where game_id=%s and discarded_at is not null))""",
        (game_id, principal.user_id, cutoff, game_id),
    )
    retained = [
        str(row["generation_id"])
        for row in document.get("art_generation_ledger", [])
        if row.get("generation_id")
    ]
    # Quote reservations are historical finance, not checkpoint state. Release
    # only a proven pre-ticket hold; a dispatched effect stays reconciliable.
    rows = connection.execute(
        """select g.image_quote_id,g.wallet_reservation_id from app.art_generations g
        where g.game_id=%s and g.owner_id=%s and g.image_quote_id is not null
        and not(g.generation_id=any(%s::uuid[])) for update""",
        (game_id, principal.user_id, retained),
    ).fetchall()
    if rows:
        from infrastructure.db_roles import system_scope
        from infrastructure.wallet import PostgresWallet

        wallet = PostgresWallet(None)
        with system_scope(
            connection
        ):  # SPEC-224: wallet e vetada a rpg_api; owner filtrado em Python
            _release_abandoned_holds(connection, wallet, principal, rows)
    connection.execute(
        """update app.art_generations set status='superseded',updated_at=now()
        where game_id=%s and owner_id=%s and not(generation_id=any(%s::uuid[]))""",
        (game_id, principal.user_id, retained),
    )
    connection.execute(
        """update app.jobs set status='cancelled',lease_token=null,lease_until=null,
        lease_owner=null,updated_at=now() where game_id=%s and owner_id=%s
        and kind='generate_dynamic_art' and status in ('queued','retry','running')
        and not((payload->'generation'->>'generation_id')::uuid=any(%s::uuid[]))""",
        (game_id, principal.user_id, retained),
    )
    # Derived digests can be rebuilt from the restored canonical chronicle.
    connection.execute(
        "delete from app.chronicle_digests where game_id=%s and owner_id=%s",
        (game_id, principal.user_id),
    )


def _release_abandoned_holds(connection, wallet, principal, rows) -> None:
    for row in rows:
        reservation = wallet._locked_reservation(
            connection, principal, row["wallet_reservation_id"]
        )
        if reservation["status"] == "reserved":
            wallet.release_pre_effect(
                principal,
                row["wallet_reservation_id"],
                fence_token=row["image_quote_id"],
                connection=connection,
            )
        else:
            wallet.mark_uncertain(
                principal,
                row["wallet_reservation_id"],
                reason="image_timeline_abandoned",
                connection=connection,
            )
