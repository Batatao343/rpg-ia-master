"""SPEC-207: redaction fail-closed do pacote de auditoria.

Allowlist por arquivo: só chaves declaradas no `spec` sobrevivem (chave
desconhecida é descartada, nunca copiada). Toda string passa por `scrub_text`
(e-mail, telefone, IP, UUID com hífens, token/JWT/chave de API, URL assinada) e
pela substituição dos valores reais do dono (`owner_values`).

Não reusa `observability.telemetry.redact`: seu `_SENSITIVE_KEYS` apaga
`action`/`narrative`/`state`, que aqui são justamente o conteúdo desejado.
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple
from collections.abc import Iterable, Mapping

PRIVATE_LABEL = "privado — referência de auditoria"

# Ordem importa: URL assinada e tokens antes de e-mail/UUID (que podem estar dentro deles).
_SIGNED_URL = re.compile(
    r"(?i)https?://\S*(?:[?&](?:token|signature|sig|expires|access_token|key|x-amz-[a-z-]+)=|"
    r"/storage/v1/object/sign/)\S*")
_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b")
_API_KEY = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{20,}|"
    r"sk_(?:live|test)_[A-Za-z0-9]{10,}|rk_(?:live|test)_[A-Za-z0-9]{10,}|"
    r"whsec_[A-Za-z0-9]{10,}|jina_[A-Za-z0-9]{16,}|(?:AKIA|ASIA)[A-Z0-9]{16}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abposr]-[A-Za-z0-9-]{8,})\b")
# Revisão Astra: `nome=valor` / `nome: valor` de credencial (cookie, senha, chave, token).
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(?:set-cookie|cookie|rpg_[a-z_]+|password|passwd|senha|secret|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|client[_-]?secret)\s*[:=]\s*[^\s;,]+")
_EMAIL = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
# Ponto final de frase depois do IP não pode impedir o casamento (revisão Astra).
_IPV4 = re.compile(r"(?<!\d)(?<!\d\.)(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?!\d|\.\d)")
_IPV6 = re.compile(r"(?i)(?<![0-9a-f:])(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}(?![0-9a-f:])")
_UUID = re.compile(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
# Telefone exige forma de telefone (+DDI, (DDD) ou separadores): número cru de
# 8-9 dígitos colidiria com custo/latência serializados no JSON.
_PHONE = re.compile(
    r"(?<![\w+.,])(?:\+\d{1,3}[\s.-]?(?:\(?\d{2,3}\)?[\s.-]?)?\d{4,5}[\s.-]?\d{4}"
    r"|\(\d{2,3}\)\s?\d{4,5}[\s.-]?\d{4}"
    r"|\d{2,3}[\s.-]\d{4,5}[\s.-]\d{4}"
    r"|\d{4,5}-\d{4})(?!\w)")
_URL_WITH_CREDENTIALS = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@\S+")
# Documentos BR, cartão e número cru de 11 dígitos (celular/CPF sem máscara). As bordas
# excluem letras/_ para não casar trechos de hashes hex nem ids `*_content_<hex>`.
_CPF = re.compile(r"(?<![\w.])\d{3}\.\d{3}\.\d{3}-\d{2}(?!\w)")
_CNPJ = re.compile(r"(?<![\w.])\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\w)")
_CARD = re.compile(r"(?<![\w.])(?:\d{4}[ -]){3}\d{1,7}(?![\w])|(?<![\w.])\d{13,19}(?![\w]|\.\d)")
_RAW_DIGITS = re.compile(r"(?<![\w.])\d{11}(?![\w]|\.\d)")
_IPV6_COMPRESSED = re.compile(
    r"(?i)(?<![0-9a-f:])(?:(?:[0-9a-f]{1,4}:){1,7}|:):(?:[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){0,6})?(?![0-9a-f:])")

_SCRUBBERS: tuple[tuple[re.Pattern, str], ...] = (
    (_URL_WITH_CREDENTIALS, "url"),
    (_SIGNED_URL, "url"),
    (_BEARER, "token"),
    (_JWT, "token"),
    (_API_KEY, "api_key"),
    (_SECRET_ASSIGN, "token"),
    (_EMAIL, "email"),
    (_UUID, "uuid"),
    (_IPV6, "ip"),
    (_IPV6_COMPRESSED, "ip"),
    (_IPV4, "ip"),
    (_CNPJ, "document"),
    (_CPF, "document"),
    (_CARD, "card"),
    (_RAW_DIGITS, "phone"),
    (_PHONE, "phone"),
)


class AuditRedactionError(RuntimeError):
    """Falha fechada: o pacote não pode ser entregue."""


def scrub_text(text: Any) -> str:
    out = str(text or "")
    for pattern, kind in _SCRUBBERS:
        out = pattern.sub(f"[REDACTED:{kind}]", out)
    return out


def _owner_forms(owner_values: Iterable[str]) -> list[str]:
    forms: set[str] = set()
    for value in owner_values or ():
        raw = str(value or "").strip()
        if len(raw) < 6:
            continue
        forms.add(raw)
        if len(raw) == 36 and raw.count("-") == 4:
            forms.add(raw.replace("-", ""))
    return sorted(forms, key=len, reverse=True)


def _clean_string(value: Any, owner_forms: list[str]) -> str:
    out = str(value)
    for form in owner_forms:
        out = re.sub(re.escape(form), "[REDACTED:owner]", out, flags=re.IGNORECASE)
    return scrub_text(out)


# Spec de allowlist:
#   dict[str, spec]      -> mapping só com essas chaves
#   "scalar"             -> str/int/float/bool/None (string limpa); outros tipos caem
#   "projected"          -> JSON produzido pela projeção do motor (strings/chaves limpas)
#   ("list", spec)       -> lista de itens validados por spec
#   ("map", spec)        -> dict de chaves arbitrárias (chave limpa) e valores por spec
Spec = Any


def _scalar(value: Any, owner_forms: list[str]) -> Any:
    if value is None or isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return _clean_string(value, owner_forms)
    return None


def _projected(value: Any, owner_forms: list[str], depth: int = 0) -> Any:
    if depth > 6:
        return None
    if isinstance(value, Mapping):
        return {_clean_string(k, owner_forms): _projected(v, owner_forms, depth + 1)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_projected(v, owner_forms, depth + 1) for v in value]
    return _scalar(value, owner_forms)


def _apply(value: Any, spec: Spec, owner_forms: list[str]) -> Any:
    if spec == "scalar":
        return _scalar(value, owner_forms)
    if spec == "projected":
        return _projected(value, owner_forms)
    if isinstance(spec, tuple) and len(spec) == 2 and spec[0] == "list":
        if not isinstance(value, (list, tuple)):
            return None
        return [_apply(item, spec[1], owner_forms) for item in value]
    if isinstance(spec, tuple) and len(spec) == 2 and spec[0] == "map":
        if not isinstance(value, Mapping):
            return None
        return {_clean_string(k, owner_forms): _apply(v, spec[1], owner_forms)
                for k, v in value.items()}
    if isinstance(spec, Mapping):
        if not isinstance(value, Mapping):
            return None
        return {key: _apply(value[key], sub, owner_forms)
                for key, sub in spec.items() if key in value}
    raise AuditRedactionError(f"spec de allowlist inválida: {spec!r}")


def redact_record(obj: Any, *, spec: Spec, owner_values: Iterable[str] = ()) -> Any:
    """Aplica a allowlist + limpeza de strings. Nunca devolve chave não declarada."""
    return _apply(obj, spec, _owner_forms(owner_values))


_SCAN: tuple[tuple[re.Pattern, str], ...] = tuple(
    (pattern, kind) for pattern, kind in _SCRUBBERS if pattern is not _PHONE)
_AUDIO_MARKERS = re.compile(r"(?i)data:audio/|\b(?:RIFF....WAVE|OggS|ftypM4A)")


def scan_pii(text: str, *, owner_values: Iterable[str] = ()) -> list[str]:
    """Achados (tipos) de PII em `text`. Vazio = limpo."""
    findings: list[str] = []
    for pattern, kind in _SCAN:
        if pattern.search(text):
            findings.append(kind)
    if _PHONE.search(text):
        findings.append("phone")
    if _AUDIO_MARKERS.search(text):
        findings.append("audio")
    low = text.casefold()
    for form in _owner_forms(owner_values):
        if form.casefold() in low:
            findings.append("owner_value")
            break
    return sorted(set(findings))
