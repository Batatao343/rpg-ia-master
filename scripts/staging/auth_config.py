"""Plan/apply Supabase Auth hosted config for staging (Management API).

Field names verified against https://api.supabase.com/api/v1-json
(UpdateAuthConfigBody): mailer_autoconfirm, security_captcha_enabled,
security_captcha_provider, security_captcha_secret, site_url, uri_allow_list,
rate_limit_{email_sent,verify,token_refresh,otp,anonymous_users}.
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Mapping

import httpx

from scripts.staging import common

API = "https://api.supabase.com/v1"
TURNSTILE_TEST_SECRET = "1x0000000000000000000000000000000AA"  # Cloudflare documented always-pass TEST secret
# Conservative staging defaults. The backend shares one egress IP, so per-IP limits
# (verify/token_refresh/otp) leave headroom for the A/B smoke; email_sent protects SMTP quota.
RATE_LIMITS = {
    "rate_limit_email_sent": 10,
    "rate_limit_verify": 60,
    "rate_limit_token_refresh": 150,
    "rate_limit_otp": 30,
    "rate_limit_anonymous_users": 10,
}
SECRET_FIELDS = {"security_captcha_secret"}
# SPEC-220 R9 (INFRA-07): política de senha/sessão declarada e diffada, nunca default implícito.
SESSION_POLICY = {
    "password_min_length": 10,
    "refresh_token_rotation_enabled": True,
    "security_refresh_token_reuse_interval": 10,
    "jwt_exp": 3600,
    "security_update_password_require_reauthentication": True,
    "disable_signup": False,
}


def validate_redirects(redirects: list[str]) -> None:
    """Allow-list de redirect sem curinga e sem http:// fora de localhost."""
    for url in redirects:
        if "*" in url:
            raise common.GuardError(f"uri_allow_list com curinga recusado: {url}")
        if url.startswith("http://") and not url.startswith(("http://localhost", "http://127.0.0.1")):
            raise common.GuardError(f"uri_allow_list http:// fora de localhost recusado: {url}")


def desired_config(env: Mapping[str, str], turnstile_test_keys: bool = False) -> dict[str, Any]:
    secret = env.get("RPG_STAGING_TURNSTILE_SECRET") or (TURNSTILE_TEST_SECRET if turnstile_test_keys else "")
    if not secret:
        raise common.GuardError("RPG_STAGING_TURNSTILE_SECRET ausente (ou use --turnstile-test-keys)")
    site = env.get("RPG_STAGING_SITE_URL")
    if not site:
        raise common.GuardError("RPG_STAGING_SITE_URL ausente")
    redirects = [u.strip() for u in env.get("RPG_STAGING_REDIRECT_URLS", site).split(",") if u.strip()]
    validate_redirects(redirects)
    cfg: dict[str, Any] = {
        "mailer_autoconfirm": False,
        "security_captcha_enabled": True,
        "security_captcha_provider": "turnstile",
        "security_captcha_secret": secret,
        "site_url": site,
        "uri_allow_list": ",".join(redirects),
    }
    cfg.update(RATE_LIMITS)
    cfg.update(SESSION_POLICY)
    return cfg


def diff_config(current: Mapping[str, Any], desired: Mapping[str, Any]) -> dict[str, dict]:
    """Changed fields only. The captcha secret is write-only (the API never returns it)."""
    out = {}
    for key, want in desired.items():
        if key in SECRET_FIELDS:
            out[key] = {"from": "<write-only>", "to": want}
        elif current.get(key) != want:
            out[key] = {"from": current.get(key), "to": want}
    return out


def redacted_diff(diff: Mapping[str, dict]) -> dict:
    return {k: {"from": v["from"], "to": common.REDACTED if k in SECRET_FIELDS else v["to"]}
            for k, v in diff.items()}


class AuthConfigClient:
    def __init__(self, ref: str, token: str, client: httpx.Client | None = None):
        self.url = f"{API}/projects/{ref}/config/auth"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.client = client or httpx.Client(timeout=30)

    def get(self) -> dict:
        r = self.client.get(self.url, headers=self.headers)
        r.raise_for_status()
        return r.json()

    def patch(self, payload: dict) -> dict:
        r = self.client.patch(self.url, headers=self.headers, json=payload)
        r.raise_for_status()
        return r.json()

    def try_patch(self, payload: dict) -> tuple[int, str]:
        """PATCH without raising; returns (status, short redacted error text)."""
        r = self.client.patch(self.url, headers=self.headers, json=payload)
        return r.status_code, "" if r.is_success else common.redact(r.text[:300])


def run(mode: str, ref: str, env: Mapping[str, str], client: httpx.Client | None = None,
        turnstile_test_keys: bool = False) -> dict:
    api = AuthConfigClient(ref, common.env_required("SUPABASE_ACCESS_TOKEN", env), client)
    want = desired_config(env, turnstile_test_keys)
    diff = diff_config(api.get(), want)
    result: dict[str, Any] = {"project_ref": ref, "mode": mode, "diff": redacted_diff(diff),
                              "turnstile_test_keys": bool(turnstile_test_keys), "applied": False}
    if mode == "apply" and diff:
        # Field groups are applied separately so one plan-gated field (e.g. an
        # email rate limit that requires custom SMTP) cannot block the rest.
        failures: dict[str, Any] = {}
        captcha = [k for k in diff if k.startswith("security_captcha")]
        groups = [captcha] if captcha else []
        groups += [[k] for k in diff if k not in captcha]
        for group in groups:
            status, err = api.try_patch({k: want[k] for k in group})
            if status >= 400:
                failures[",".join(group)] = {"status": status, "error": err}
        result["failures"] = failures
        remaining = sorted(k for k in diff_config(api.get(), want) if k not in SECRET_FIELDS)
        result.update(applied=True, verified=not remaining, remaining=remaining)
    return result


def main(argv: list[str] | None = None) -> int:
    common.load_dotenv_quietly()
    p = argparse.ArgumentParser(description="Supabase Auth config plan/apply (staging)")
    p.add_argument("mode", choices=["plan", "apply"])
    common.add_guard_args(p)
    p.add_argument("--turnstile-test-keys", action="store_true")
    p.add_argument("--out")
    a = p.parse_args(argv)
    ref = common.require_staging(a.confirm_staging)
    result = run(a.mode, ref, os.environ, turnstile_test_keys=a.turnstile_test_keys)
    print(common.write_evidence(f"auth_config_{a.mode}", result, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
