-- Additive domain extension; preserves all existing rows and ownership policies.
alter table app.operations drop constraint operations_kind_check,
add constraint operations_kind_check check (
  kind in ('new_game','turn','death','equip','levelup','delete','account_delete','art')
);
