-- operations.id is already globally unique through the primary key.
-- Keeping (owner_id, id) as a second arbiter makes ON CONFLICT races depend on
-- which unique index PostgreSQL reports first.
alter table app.operations
  drop constraint if exists operations_owner_id_id_key;
