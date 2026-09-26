"""Invalidate abandoned timeline derivatives inside the restore transaction."""
from __future__ import annotations


def restore_effects(connection, *, principal, game_id, document: dict) -> None:
    checkpoint = connection.execute(
        'select game_version,memory_commit_version,timeline_epoch,canonical_turn '
        'from app.game_checkpoints where game_id=%s and owner_id=%s',
        (game_id, principal.user_id),
    ).fetchone()
    if not checkpoint:
        return  # no earlier snapshot: no history was actually rolled back
    epoch = int(checkpoint['timeline_epoch'])
    cutoff = int(checkpoint['memory_commit_version'] or checkpoint['game_version'])
    connection.execute(
        """update app.memory_documents set discarded_at=now(),embedding_status='discarded'
        where game_id=%s and owner_id=%s and discarded_at is null and
          (timeline_epoch > %s or (timeline_epoch=%s and
            (commit_version > %s or (commit_version is null and source_turn > %s))))""",
        (game_id, principal.user_id, epoch, epoch, cutoff, checkpoint['canonical_turn']))
    connection.execute(
        """update app.jobs set status='cancelled',lease_token=null,lease_until=null,
        lease_owner=null,updated_at=now() where game_id=%s and owner_id=%s
        and status in ('queued','retry','running') and
          (kind='compress_chronicle' or
           (payload->>'commit_version')::bigint > %s or
           payload->>'memory_id' in
            (select id from app.memory_documents where game_id=%s and discarded_at is not null))""",
        (game_id, principal.user_id, cutoff, game_id))
    retained = [str(row['generation_id']) for row in document.get('art_generation_ledger', [])
                if row.get('generation_id')]
    connection.execute(
        """update app.art_generations set status='superseded',updated_at=now()
        where game_id=%s and owner_id=%s and not(generation_id=any(%s::uuid[]))""",
        (game_id, principal.user_id, retained))
    connection.execute(
        """update app.jobs set status='cancelled',lease_token=null,lease_until=null,
        lease_owner=null,updated_at=now() where game_id=%s and owner_id=%s
        and kind='generate_dynamic_art' and status in ('queued','retry','running')
        and not((payload->'generation'->>'generation_id')::uuid=any(%s::uuid[]))""",
        (game_id, principal.user_id, retained))
    # Derived digests can be rebuilt from the restored canonical chronicle.
    connection.execute('delete from app.chronicle_digests where game_id=%s and owner_id=%s',
                       (game_id, principal.user_id))
