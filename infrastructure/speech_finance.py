"""SPEC-186 finance orchestration; canonical writers remain coordinator/wallet."""
from __future__ import annotations
from infrastructure.db_roles import admin_connection

from datetime import datetime, timezone
import os
from uuid import UUID, uuid4

from infrastructure.contracts import Principal
from infrastructure.wallet import PostgresWallet
from services.shard_pricing import PricingUnavailable, quote_attempt_ceiling, version_from_record
from services.speech_pricing import require_speech_prices, speech_bound
from services.speech_to_text import Candidate, SpeechError
from services.usage_metering import UsageEvent


class PostgresSpeechFinance:
    def __init__(self, runtime, principal: Principal, *, at: datetime | None = None) -> None:
        self.pool = runtime.game_store.pool
        self.coordinator = runtime.turn_coordinator
        self.wallet = PostgresWallet(self.pool)
        self.principal = principal
        self.at = at
        self.claim = None
        self.reservation = None

    def begin(self, operation_id: UUID, request_hash: str, candidates: list[Candidate]) -> None:
        now = self.at or datetime.now(timezone.utc)
        require_speech_prices(now)
        version_id = os.getenv("RPG_SPEECH_PRICING_VERSION", "")
        with admin_connection(self.pool) as connection:
            record = connection.execute("select * from app.pricing_versions where version_id=%s",
                                        (version_id,)).fetchone()
        if record is None:
            raise PricingUnavailable("speech pricing não configurado")
        version = version_from_record(record)
        bounds = [speech_bound(c.provider, c.model) for c in candidates]
        if any(v is None for v in bounds):
            raise PricingUnavailable("speech model sem rate card")
        ceiling = sum(quote_attempt_ceiling(v, version, at=now) for v in bounds)
        if ceiling > int(os.getenv("RPG_SPEECH_MAX_RESERVE_MILLI", "100")):
            raise SpeechError("speech_spend_ceiling", 402)
        self.claim = self.coordinator.claim(self.principal, operation_id, game_id=None,
                                            kind="speech_to_text", request_hash=request_hash,
                                            base_version=None, exclusive=False)
        try:
            self.reservation = self.wallet.reserve(
                self.principal, reference_type="speech_to_text", reference_id=str(operation_id),
                pricing_version_id=version_id, ceiling_milli=ceiling,
                fence_token=self.claim.lease_token, usage_operation_id=operation_id, at=now)
        except BaseException:
            self.coordinator.fail(self.claim, "speech_reserve_failed")
            raise

    def admit(self, ordinal: int, candidate: Candidate) -> None:
        self.wallet.admit_attempt(self.principal, self.reservation.reservation_id,
                                  fence_token=self.claim.lease_token,
                                  attempt_key=f"speech:{ordinal}", provider=candidate.provider,
                                  model=candidate.model, at=self.at)

    def finish(self, events: list[UsageEvent], success: bool) -> str:
        # Metadata-only receipt: neither transcript nor original audio hash is returned/stored.
        if success:
            self.coordinator.complete(self.claim, committed_version=None,
                                      receipt={"kind": "speech_to_text", "result_retained": False},
                                      usage_events=events)
        else:
            self.coordinator.fail(self.claim, "speech_failed", usage_events=events)
        if not events:
            self.wallet.release_pre_effect(self.principal, self.reservation.reservation_id,
                                           fence_token=self.claim.lease_token)
            return "released"
        if all(e.billing_exact for e in events):
            try:
                self.wallet.settle_usage(self.principal, self.reservation.reservation_id,
                                         fence_token=self.claim.lease_token,
                                         usage_event_ids=[e.event_id for e in events], at=self.at)
                return "settled"
            except Exception:
                # Usage is already durable. Preserve funds/fence for reconciliation
                # if settlement failed; never resend audio or silently refund.
                pass
        recovered = self.wallet.recover(self.principal, self.reservation.reservation_id, new_fence_token=uuid4())
        return 'settled' if recovered.status == 'settled' else "pending_reconciliation"
