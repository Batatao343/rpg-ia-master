-- SPEC-185: the financial join key stays outside GameState/presentation_history.
alter table app.turns add column presentation_entry_id text;
create unique index turns_owner_history_entry_idx
  on app.turns (owner_id, game_id, presentation_entry_id, timeline_epoch)
  where presentation_entry_id is not null;
