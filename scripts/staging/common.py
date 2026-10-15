"""Guards, redaction and evidence output shared by the SPEC-191 staging tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
REDACTED = "[REDACTED]"
_SECRET_KEY = re.compile(
    r"(secret|token|password|passwd|apikey|api_key|authorization|service_role|dsn|database_url|"
    r"jwt|signedurl|signed_url|access_key|publishable)", re.I)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*")
_URL_CRED = re.compile(r"(postgres(?:ql)?://[^:/\s]+:)[^@\s]+(@)")
_SB_KEY = re.compile(r"\bsb_(?:secret|publishable)_[A-Za-z0-9_-]+")


class GuardError(SystemExit):
    pass


def email_hash(value: str) -> str:
    return "email:" + hashlib.sha256(value.strip().lower().encode()).hexdigest()[:12]


def redact_text(text: str) -> str:
    text = _URL_CRED.sub(r"\1" + REDACTED + r"\2", text)
    text = _JWT.sub(REDACTED, text)
    text = _SB_KEY.sub(REDACTED, text)
    return _EMAIL.sub(lambda m: email_hash(m.group(0)), text)


def redact(value: Any, key: str = "") -> Any:
    """Recursively scrub secrets; booleans/numbers under secret-like keys are kept."""
    if isinstance(value, Mapping):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, key) for v in value]
    if isinstance(value, str):
        if key and _SECRET_KEY.search(key) and value:
            return REDACTED
        return redact_text(value)
    return value


def protected_refs(env: Mapping[str, str] | None = None) -> set[str]:
    env = os.environ if env is None else env
    return {r.strip() for r in env.get("RPG_PROTECTED_PROJECT_REFS", "").split(",") if r.strip()}


def require_staging(confirm: str | None, env: Mapping[str, str] | None = None) -> str:
    """Return the staging ref or abort. Never talks to the network."""
    env = os.environ if env is None else env
    ref = (env.get("SUPABASE_PROJECT_REF") or "").strip()
    if not ref:
        raise GuardError("SUPABASE_PROJECT_REF ausente")
    if not confirm or confirm != ref:
        raise GuardError("--confirm-staging precisa ser igual a SUPABASE_PROJECT_REF")
    if ref in protected_refs(env):
        raise GuardError("ref consta em RPG_PROTECTED_PROJECT_REFS; recusado")
    return ref


def target_matches_ref(ref: str, value: str) -> bool:
    """Strict: hostname is `<ref>.supabase.co` (or a subdomain, e.g. db.<ref>.supabase.co) OR the DSN
    username is `<role>.<ref>` (Supavisor tenant form, e.g. postgres.<ref>). Substring matches are refused."""
    from urllib.parse import unquote, urlsplit
    try:
        u = urlsplit(value or "")
        host = (u.hostname or "").lower()
        user = unquote(u.username or "").lower()
    except ValueError:
        return False
    ref = ref.lower()
    if host == f"{ref}.supabase.co" or host.endswith(f".{ref}.supabase.co"):
        return True
    return bool(user) and user.endswith(f".{ref}") and user.count(".") == 1


def assert_ref_in(ref: str, **targets: str) -> None:
    """Every remote target (URL/DSN) must really point at the staging ref (host or tenant user), else abort."""
    bad = sorted(name for name, value in targets.items() if not target_matches_ref(ref, value))
    if bad:
        raise GuardError("alvo(s) nao correspondem ao ref de staging: " + ", ".join(bad))


def split_dsn_password(dsn: str) -> tuple[str, str | None]:
    """Return (dsn without password, password) so the secret never travels on argv."""
    from urllib.parse import quote, unquote, urlsplit, urlunsplit
    u = urlsplit(dsn)
    if u.password is None:
        return dsn, None
    host = u.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    netloc = (quote(unquote(u.username or ""), safe="") if u.username else "") + "@" + host
    if u.port:
        netloc += f":{u.port}"
    return urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment)), unquote(u.password)


def add_guard_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--confirm-staging", metavar="REF", required=True)


def write_evidence(name: str, payload: dict, out: str | Path | None = None) -> Path:
    path = Path(out) if out else ROOT / "docs" / "spec191" / "evidence" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(payload), ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
                    encoding="utf-8")
    return path


def env_required(name: str, env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    value = env.get(name)
    if not value:
        raise GuardError(f"variavel de ambiente ausente: {name}")
    return value


def load_dotenv_quietly() -> None:
    """Load .env.staging then .env into os.environ without printing anything.

    Staging connection settings live in the gitignored ``.env.staging`` so the
    default offline suite never sees remote SUPABASE_*/DATABASE_URL values.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env.staging", override=False)
        load_dotenv(ROOT / ".env", override=False)
    except Exception:  # noqa: BLE001 - optional convenience
        pass
