"""Registro in-process com nomes e cardinalidade de labels fechados."""

from __future__ import annotations

import threading
import re
import math
from collections import Counter, defaultdict
from typing import Mapping


LABELS = {
    "rpg_lease_renewals_total": {"outcome"},
    "rpg_http_requests_total": {"route", "status_class"},
    "rpg_http_duration_seconds": {"route"},
    # DEPRECATED (SPEC-200 R7): mede o enfileiramento do evento `accepted`, nao a latencia
    # percebida. Mantida para nao abrir buraco em series; use rpg_sse_ack_seconds.
    "rpg_sse_first_event_seconds": {"route"},
    # SPEC-200: latencia percebida (labels fechados; nunca ids).
    "rpg_sse_ack_seconds": {"route"},
    "rpg_turn_phase_seconds": {"route", "phase"},
    "rpg_turn_first_content_seconds": {"route", "source"},
    "rpg_turn_last_content_seconds": {"route", "source"},
    "rpg_turn_duration_seconds": {"route", "outcome", "simulated"},
    "rpg_turn_commits_total": {"outcome"},
    "rpg_operation_lease_age_seconds": {"kind"},
    "rpg_db_duration_seconds": {"operation", "outcome"},
    "rpg_db_pool": {"state"},
    "rpg_llm_attempts_total": {"provider", "tier", "outcome"},
    "rpg_llm_duration_seconds": {"provider", "tier", "outcome"},
    "rpg_llm_cost_usd_total": {"provider", "tier", "basis"},
    "rpg_rag_duration_seconds": {"scope", "outcome"},
    "rpg_rag_degraded_total": {"source"},  # SPEC-234 R10 (source fechado: lore|session|npc|...)
    # SPEC-223 R8: proposta de evento rejeitada (type = EventType|other; reason_class
    # fechado: unproven|rate_limited|engine_only|duplicate|malformed|invalid).
    "rpg_world_events_rejected_total": {"type", "reason_class"},
    "rpg_memory_embedding_backlog": {"status"},
    "rpg_jobs": {"kind", "status"},
    "rpg_job_oldest_age_seconds": {"kind"},
    "rpg_blob_operations_total": {"operation", "outcome"},
    "rpg_backup_age_seconds": {"component"},
    "rpg_auth_email_delivery_failures_total": {"action", "status_class"},
    # SPEC-196: closed, low-cardinality FinOps labels (never user/game/order ids).
    # SPEC-195: unresolved reconciliation events by closed status (parked | orphaned).
    "rpg_reconciliation_events": {"status"},
    "rpg_finops_alert_active": {"kind", "channel", "sku_id", "provider", "model"},
    "rpg_finops_margin_ratio": {"channel", "sku_id"},
    "rpg_finops_unit_cost_usd": {"kind"},
    "rpg_finops_kill_switch_off": {"kind"},
    "rpg_finops_evaluation_age_seconds": {"kind"},
    "rpg_kill_switch_load_errors_total": {"error"},
}


MetricKey = tuple[str, tuple[tuple[str, str], ...]]


class Metrics:
    def __init__(self) -> None:
        self._values: Counter[MetricKey] = Counter()
        self._gauges: dict[MetricKey, float] = {}
        self._observations: dict[MetricKey, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    @staticmethod
    def _key(name: str, labels: Mapping[str, object]) -> MetricKey:
        allowed = LABELS.get(name)
        if allowed is None:
            raise ValueError(f"métrica não registrada: {name}")
        if set(labels) != allowed:
            raise ValueError(f"labels de {name} devem ser {sorted(allowed)}")
        normalized = tuple(sorted((key, str(value)[:60]) for key, value in labels.items()))
        return name, normalized

    def increment(self, name: str, labels: Mapping[str, object], amount: float = 1) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._values[key] += amount

    def observe(self, name: str, labels: Mapping[str, object], value: float) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._observations[key].append(max(0.0, float(value)))

    def set_gauge(self, name: str, labels: Mapping[str, object], value: float) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = float(value)

    def clear_gauge(self, name: str, labels: Mapping[str, object]) -> None:
        """Drop a gauge series (e.g. a SKU that left the report window)."""
        key = self._key(name, labels)
        with self._lock:
            self._gauges.pop(key, None)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            result: dict[str, float] = {
                f"{name}{dict(labels)}": value
                for (name, labels), value in self._values.items()
            }
            result.update({
                f"{name}{dict(labels)}": value
                for (name, labels), value in self._gauges.items()
            })
            for (name, labels), values in self._observations.items():
                prefix = f"{name}{dict(labels)}"
                result[f"{prefix}.count"] = len(values)
                result[f"{prefix}.sum"] = sum(values)
                result[f"{prefix}.max"] = max(values, default=0.0)
            return result

    @staticmethod
    def _labels(labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        escaped = [
            f'{key}="{value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'
            for key, value in labels
        ]
        return "{" + ",".join(escaped) + "}"

    def render_prometheus(self) -> str:
        """Formato texto sem IDs/payloads; suficiente para Prometheus local."""
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._values.items()):
                safe_name = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
                lines.append(f"{safe_name}{self._labels(labels)} {value}")
            for (name, labels), value in sorted(self._gauges.items()):
                safe_name = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
                lines.append(f"{safe_name}{self._labels(labels)} {value}")
            for (name, labels), values in sorted(self._observations.items()):
                safe_name = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
                rendered = self._labels(labels)
                ordered = sorted(values)
                p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
                lines.append(f"{safe_name}_count{rendered} {len(values)}")
                lines.append(f"{safe_name}_sum{rendered} {sum(values)}")
                lines.append(f"{safe_name}_max{rendered} {max(ordered, default=0.0)}")
                lines.append(
                    f"{safe_name}_p95{rendered} "
                    f"{ordered[p95_index] if ordered else 0.0}"
                )
        return "\n".join(lines) + "\n"


metrics = Metrics()
