"""SPEC-234 R9: migra memory_documents de `local-1024` para o perfil do provider atual."""
from __future__ import annotations

import rag
from infrastructure.runtime import get_runtime


def main() -> int:
    store = get_runtime().memory_store
    changed = store.migrate_legacy_profile()
    print(f"perfil {rag.embedding_profile_id()}: {changed} documento(s) migrado(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
