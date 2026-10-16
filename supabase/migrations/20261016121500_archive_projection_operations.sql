-- SPEC-213: projeção derivada do arquivista (job `project_archive`) registra o uso
-- de LLM sob uma operação própria, como a compressão da crônica.
alter table app.operations drop constraint operations_kind_check,
  add constraint operations_kind_check check (
    kind in ('new_game','turn','death','equip','levelup','delete','account_delete',
             'art','embedding','prologue','chronicle_search','chronicle_compress',
             'speech_to_text','archive_projection')
  );
