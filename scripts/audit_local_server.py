"""Local authenticated API for audit smoke. Explicitly disables paid providers."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    import dotenv
    dotenv.load_dotenv = lambda *a, **kw: False
    from scripts.start_local_api import _supabase_status
    status = _supabase_status()
    from urllib.parse import urlsplit
    if urlsplit(status['API_URL']).hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('audit server only accepts local Supabase')
    os.environ.update({
        'RPG_RUNTIME_PROFILE': 'local',
        'DATABASE_URL': status.get('DB_URL', 'postgresql://postgres:postgres@127.0.0.1:55322/postgres'),
        'SUPABASE_URL': status['API_URL'],
        'SUPABASE_PUBLISHABLE_KEY': status.get('PUBLISHABLE_KEY') or status['ANON_KEY'],
        'SUPABASE_SERVICE_ROLE_KEY': status['SERVICE_ROLE_KEY'],
        'RPG_SESSION_SECRET': 'audit-local-synthetic-session-secret-32',
        'RPG_FORCE_MOCK': '1', 'RPG_RATE_LIMIT': '0', 'RPG_DYNAMIC_ART_ENABLED': '1',
        'RPG_RUNTIME_CACHE_DIR': tempfile.mkdtemp(prefix='valoria-audit-cache-'),
        'RPG_CORS_ORIGINS': f'http://127.0.0.1:{args.port}',
    })
    if urlsplit(os.environ['DATABASE_URL']).hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('audit server only accepts local Postgres')
    import api
    import rag
    rag.get_embeddings = lambda: None
    rag.get_embeddings_for = lambda *a, **kw: None
    rag._embeddings_for_index = lambda *a, **kw: None
    import uvicorn
    print(f'AUDIT_LOCAL_SERVER pid={os.getpid()} port={args.port}', flush=True)
    uvicorn.run(api.app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
