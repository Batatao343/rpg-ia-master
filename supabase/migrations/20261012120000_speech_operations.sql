-- SPEC-186: account-scoped speech usage, no recording or transcript tables.
alter table app.operations drop constraint operations_kind_check,
  add constraint operations_kind_check check (
    kind in ('new_game','turn','death','equip','levelup','delete','account_delete',
             'art','embedding','prologue','chronicle_search','chronicle_compress',
             'speech_to_text')
  );
