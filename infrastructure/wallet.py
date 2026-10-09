"""SPEC-184 account wallet: locked, idempotent transfers and durable spend tickets.

No public purchase endpoint or production charging is enabled here. Only the
trusted backend DB connection may mutate these tables.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
from typing import Iterator
from uuid import UUID, uuid4

from infrastructure.contracts import Principal
from infrastructure.postgres import PostgresPool
from services.shard_pricing import (
    MAX_SHARD_MILLI, PricingUnavailable, quote_attempt_ceiling,
    quote_usage, version_from_record,
)
from services.usage_metering import UsageEvent, reserve_next_attempt


class WalletConflict(ValueError):
    pass


class InsufficientShards(WalletConflict):
    pass


class SpendCeilingExceeded(WalletConflict):
    pass


class UncertainEffect(WalletConflict):
    pass


@dataclass(frozen=True)
class WalletBalance:
    available_milli: int
    reserved_milli: int


@dataclass(frozen=True)
class WalletReservation:
    reservation_id: UUID
    owner_id: UUID
    reference_type: str
    reference_id: str
    pricing_version_id: str
    ceiling_milli: int
    settled_milli: int
    released_milli: int
    status: str
    fence_token: UUID
    usage_event_ids: tuple[UUID, ...]


def _positive_amount(amount: int) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= MAX_SHARD_MILLI:
        raise WalletConflict("shard_milli deve ser inteiro positivo dentro de bigint")
    return amount


def _reference(value: str, maximum: int = 160) -> str:
    if not isinstance(value, str) or not 0 < len(value) <= maximum or value != value.strip():
        raise WalletConflict("referência financeira inválida")
    return value


def _reservation(row) -> WalletReservation:
    return WalletReservation(
        row["reservation_id"], row["owner_id"], row["reference_type"],
        row["reference_id"], row["pricing_version_id"], int(row["ceiling_milli"]),
        int(row["settled_milli"]), int(row["released_milli"]), row["status"],
        row["fence_token"], tuple(row["usage_event_ids"]),
    )


class PostgresWallet:
    def __init__(self, pool: PostgresPool) -> None:
        self.pool = pool

    @staticmethod
    def _locked_account(connection, owner_id: UUID):
        connection.execute(
            "insert into app.wallet_accounts(owner_id) values (%s) on conflict do nothing",
            (owner_id,),
        )
        return connection.execute(
            "select * from app.wallet_accounts where owner_id=%s for update", (owner_id,),
        ).fetchone()

    @staticmethod
    def _post(connection, owner_id: UUID, entry_type: str, reference_type: str,
              reference_id: str, amount: int, available_delta: int,
              reserved_delta: int, *, reservation_id: UUID | None = None,
              pricing_version_id: str | None = None, sku_id: str | None = None,
              related_entry_id: UUID | None = None, reason: str | None = None,
              actor_id: UUID | None = None) -> None:
        connection.execute(
            """insert into app.wallet_entries
            (entry_id,owner_id,entry_type,reference_type,reference_id,reservation_id,
             related_entry_id,pricing_version_id,sku_id,amount_milli,available_delta,
             reserved_delta,reason,actor_id)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (uuid4(), owner_id, entry_type, reference_type, reference_id,
             reservation_id, related_entry_id, pricing_version_id, sku_id,
             amount, available_delta, reserved_delta, reason, actor_id),
        )

    def balance(self, principal: Principal) -> WalletBalance:
        with self.pool.connection() as connection:
            row = connection.execute(
                "select available_milli,reserved_milli from app.wallet_accounts where owner_id=%s",
                (principal.user_id,),
            ).fetchone()
        return WalletBalance(int(row["available_milli"]), int(row["reserved_milli"])) if row else WalletBalance(0, 0)

    def credit_verified_purchase(self, principal: Principal, *, channel: str,
                                 payment_id: str, sku_id: str, verified: bool) -> WalletBalance:
        """Credit an externally verified payment once, using server-side SKU units.

        Payment verification belongs to the future store/webhook integration;
        this method has no HTTP route and rejects unverified invocations.
        """
        if verified is not True:
            raise WalletConflict("compra sem prova verificada")
        source = "payment:" + _reference(channel, 30)
        key = _reference(payment_id)
        with self.pool.connection() as connection, connection.transaction():
            sku = connection.execute(
                "select sku_id,pricing_version_id,shard_milli,channel from app.purchase_skus where sku_id=%s",
                (sku_id,),
            ).fetchone()
            if sku is None or sku["channel"] != channel:
                raise WalletConflict("SKU publicado não corresponde ao canal")
            account = self._locked_account(connection, principal.user_id)
            prior = connection.execute(
                "select owner_id,sku_id,amount_milli from app.wallet_entries "
                "where entry_type='purchase' and reference_type=%s and reference_id=%s",
                (source, key),
            ).fetchone()
            if prior:
                if prior["owner_id"] != principal.user_id or prior["sku_id"] != sku_id or int(prior["amount_milli"]) != int(sku["shard_milli"]):
                    raise WalletConflict("payment id reutilizado com compra divergente")
                return WalletBalance(int(account["available_milli"]), int(account["reserved_milli"]))
            amount = _positive_amount(int(sku["shard_milli"]))
            self._post(connection, principal.user_id, "purchase", source, key,
                       amount, amount, 0, pricing_version_id=sku["pricing_version_id"],
                       sku_id=sku_id)
            row = connection.execute(
                "update app.wallet_accounts set available_milli=available_milli+%s,updated_at=now() "
                "where owner_id=%s returning available_milli,reserved_milli",
                (amount, principal.user_id),
            ).fetchone()
            return WalletBalance(int(row["available_milli"]), int(row["reserved_milli"]))

    def refund_purchase(self, principal: Principal, *, purchase_entry_id: UUID,
                        refund_id: str, kind: str = "refund") -> WalletBalance:
        """Full purchase refund/reversal once; fail if spent funds are unavailable."""
        if kind not in ("refund", "reversal") or not isinstance(purchase_entry_id, UUID):
            raise WalletConflict("refund/reversal inválido")
        refund_key = _reference(refund_id)
        with self.pool.connection() as connection, connection.transaction():
            account = self._locked_account(connection, principal.user_id)
            source = connection.execute(
                "select entry_id,amount_milli from app.wallet_entries "
                "where entry_id=%s and owner_id=%s and entry_type='purchase'",
                (purchase_entry_id, principal.user_id),
            ).fetchone()
            if source is None:
                raise WalletConflict("compra original não pertence ao owner")
            prior = connection.execute(
                "select entry_type,reference_id,related_entry_id from app.wallet_entries "
                "where related_entry_id=%s and entry_type in ('refund','reversal')",
                (purchase_entry_id,),
            ).fetchone()
            if prior:
                if (prior["entry_type"] != kind or prior["reference_id"] != refund_key
                        or prior["related_entry_id"] != purchase_entry_id):
                    raise WalletConflict("compra já devolvida por outra referência")
                return WalletBalance(int(account["available_milli"]), int(account["reserved_milli"]))
            amount = int(source["amount_milli"])
            if int(account["available_milli"]) < amount:
                raise InsufficientShards("refund exige saldo disponível; sem overdraft")
            self._post(connection, principal.user_id, kind, "purchase_refund", refund_key,
                       amount, -amount, 0, related_entry_id=purchase_entry_id)
            row = connection.execute(
                "update app.wallet_accounts set available_milli=available_milli-%s,updated_at=now() "
                "where owner_id=%s returning available_milli,reserved_milli",
                (amount, principal.user_id),
            ).fetchone()
            return WalletBalance(int(row["available_milli"]), int(row["reserved_milli"]))

    def adjust_admin(self, principal: Principal, *, adjustment_id: str,
                     signed_milli: int, actor_id: UUID, reason: str) -> WalletBalance:
        """Audited manual correction with a stable replay key and hard no-overdraft."""
        _reference(adjustment_id)
        if (isinstance(signed_milli, bool) or not isinstance(signed_milli, int)
                or signed_milli == 0):
            raise WalletConflict("ajuste inválido")
        amount = _positive_amount(abs(signed_milli))
        if (not isinstance(actor_id, UUID) or not isinstance(reason, str)
                or not 0 < len(reason) <= 500 or reason != reason.strip()):
            raise WalletConflict("ator/justificativa de ajuste ausente")
        with self.pool.connection() as connection, connection.transaction():
            account = self._locked_account(connection, principal.user_id)
            prior = connection.execute(
                "select available_delta,actor_id,reason from app.wallet_entries "
                "where owner_id=%s and entry_type='adjustment_admin' "
                "and reference_type='admin' and reference_id=%s",
                (principal.user_id, adjustment_id),
            ).fetchone()
            if prior:
                if (prior["available_delta"] != signed_milli or prior["actor_id"] != actor_id
                        or prior["reason"] != reason):
                    raise WalletConflict("ajuste replay divergente")
                return WalletBalance(int(account["available_milli"]), int(account["reserved_milli"]))
            if signed_milli < 0 and int(account["available_milli"]) < amount:
                raise InsufficientShards("ajuste consumiria reserva/saldo inexistente")
            self._post(connection, principal.user_id, "adjustment_admin", "admin",
                       adjustment_id, amount, signed_milli, 0,
                       reason=reason, actor_id=actor_id)
            row = connection.execute(
                "update app.wallet_accounts set available_milli=available_milli+%s,updated_at=now() "
                "where owner_id=%s returning available_milli,reserved_milli",
                (signed_milli, principal.user_id),
            ).fetchone()
            return WalletBalance(int(row["available_milli"]), int(row["reserved_milli"]))

    def reserve(self, principal: Principal, *, reference_type: str, reference_id: str,
                pricing_version_id: str, ceiling_milli: int, fence_token: UUID,
                usage_operation_id: UUID | None = None,
                at: datetime | None = None) -> WalletReservation:
        _positive_amount(ceiling_milli)
        if reference_type not in {"operation", "image", "speech_to_text", "embedding", "other"}:
            raise WalletConflict("tipo de referência inválido")
        _reference(reference_id)
        if not isinstance(fence_token, UUID):
            raise WalletConflict("fence token ausente")
        if reference_type == "operation":
            if UUID(reference_id) != usage_operation_id:
                raise WalletConflict("operation_id de usage divergente")
        at = at or datetime.now(timezone.utc)
        with self.pool.connection() as connection, connection.transaction():
            if usage_operation_id is not None:
                operation = connection.execute(
                    "select owner_id from app.operations where id=%s for key share",
                    (usage_operation_id,),
                ).fetchone()
                if operation is None or operation["owner_id"] != principal.user_id:
                    raise WalletConflict("operation não pertence ao owner")
            version_row = connection.execute(
                "select * from app.pricing_versions where version_id=%s", (pricing_version_id,),
            ).fetchone()
            if version_row is None:
                raise PricingUnavailable("versão de pricing ausente")
            version_from_record(version_row).require_fresh(at)
            account = self._locked_account(connection, principal.user_id)
            prior = connection.execute(
                "select * from app.wallet_reservations where owner_id=%s and reference_type=%s "
                "and reference_id=%s for update",
                (principal.user_id, reference_type, reference_id),
            ).fetchone()
            if prior:
                if (prior["pricing_version_id"] != pricing_version_id
                        or prior["ceiling_milli"] != ceiling_milli
                        or prior["fence_token"] != fence_token
                        or prior["usage_operation_id"] != usage_operation_id):
                    raise WalletConflict("reservation replay divergente")
                return _reservation(prior)
            if int(account["available_milli"]) < ceiling_milli:
                raise InsufficientShards("saldo disponível insuficiente")
            reservation_id = uuid4()
            connection.execute(
                """insert into app.wallet_reservations
                (reservation_id,owner_id,reference_type,reference_id,usage_operation_id,
                 pricing_version_id,fence_token,ceiling_milli)
                values (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (reservation_id, principal.user_id, reference_type, reference_id,
                 usage_operation_id, pricing_version_id, fence_token, ceiling_milli),
            )
            connection.execute(
                "update app.wallet_accounts set available_milli=available_milli-%s, "
                "reserved_milli=reserved_milli+%s,updated_at=now() where owner_id=%s",
                (ceiling_milli, ceiling_milli, principal.user_id),
            )
            self._post(connection, principal.user_id, "reserve", "reservation",
                       str(reservation_id), ceiling_milli, -ceiling_milli, ceiling_milli,
                       reservation_id=reservation_id, pricing_version_id=pricing_version_id)
            return _reservation(connection.execute(
                "select * from app.wallet_reservations where reservation_id=%s",
                (reservation_id,),
            ).fetchone())

    def _locked_reservation(self, connection, principal: Principal, reservation_id: UUID):
        self._locked_account(connection, principal.user_id)
        row = connection.execute(
            "select * from app.wallet_reservations where reservation_id=%s and owner_id=%s for update",
            (reservation_id, principal.user_id),
        ).fetchone()
        if row is None:
            raise WalletConflict("reserva não pertence ao owner")
        return row

    def admit_attempt(self, principal: Principal, reservation_id: UUID, *,
                      fence_token: UUID, attempt_key: str, provider: str,
                      model: str, at: datetime | None = None) -> int:
        """Commit a worst-case ticket before a network provider call."""
        _reference(attempt_key)
        _reference(provider, 100)
        _reference(model, 150)
        at = at or datetime.now(timezone.utc)
        with self.pool.connection() as connection, connection.transaction():
            row = self._locked_reservation(connection, principal, reservation_id)
            if row["fence_token"] != fence_token or row["status"] not in ("reserved", "effect_started"):
                raise UncertainEffect("fence inválido ou efeito em reconciliação")
            prior = connection.execute(
                "select * from app.wallet_attempt_tickets where reservation_id=%s and attempt_key=%s",
                (reservation_id, attempt_key),
            ).fetchone()
            if prior:
                if (prior["provider"] != provider or prior["model"] != model
                        or prior["fence_token"] != fence_token):
                    raise WalletConflict("attempt replay divergente")
                # A replayed ticket must never dispatch the network call again.
                raise UncertainEffect("attempt já tinha ticket; reconciliar antes de retry")
            max_usd = reserve_next_attempt(provider, model)
            if max_usd is None:
                raise SpendCeilingExceeded("modelo sem limite publicamente verificável")
            version_row = connection.execute(
                "select * from app.pricing_versions where version_id=%s",
                (row["pricing_version_id"],),
            ).fetchone()
            liability = quote_attempt_ceiling(max_usd, version_from_record(version_row), at=at)
            spent = connection.execute(
                "select coalesce(sum(max_liability_milli),0) as total "
                "from app.wallet_attempt_tickets where reservation_id=%s",
                (reservation_id,),
            ).fetchone()["total"]
            if int(spent) + liability > int(row["ceiling_milli"]):
                raise SpendCeilingExceeded("próxima tentativa excede teto da reserva")
            connection.execute(
                """insert into app.wallet_attempt_tickets
                (ticket_id,reservation_id,owner_id,attempt_key,provider,model,
                 max_liability_milli,fence_token)
                values (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (uuid4(), reservation_id, principal.user_id, attempt_key,
                 provider, model, liability, fence_token),
            )
            connection.execute(
                "update app.wallet_reservations set status='effect_started' "
                "where reservation_id=%s", (reservation_id,),
            )
            return liability

    def _terminal_transfer(self, connection, row, settled: int, usage_ids: Sequence[UUID],
                           *, status: str, reason: str | None = None) -> WalletReservation:
        ceiling = int(row["ceiling_milli"])
        if settled < 0 or settled > ceiling:
            raise SpendCeilingExceeded("settlement excede reserva")
        released = ceiling - settled
        owner_id = row["owner_id"]
        reservation_id = row["reservation_id"]
        if settled:
            self._post(connection, owner_id, "settle", "reservation", str(reservation_id),
                       settled, 0, -settled, reservation_id=reservation_id,
                       pricing_version_id=row["pricing_version_id"])
        if released:
            self._post(connection, owner_id, "release", "reservation", str(reservation_id),
                       released, released, -released, reservation_id=reservation_id,
                       pricing_version_id=row["pricing_version_id"], reason=reason)
        connection.execute(
            "update app.wallet_accounts set available_milli=available_milli+%s, "
            "reserved_milli=reserved_milli-%s,updated_at=now() where owner_id=%s",
            (released, ceiling, owner_id),
        )
        return _reservation(connection.execute(
            """update app.wallet_reservations set settled_milli=%s,released_milli=%s,
               status=%s,usage_event_ids=%s,reconciliation_reason=%s,finished_at=now()
               where reservation_id=%s returning *""",
            (settled, released, status, list(usage_ids), reason, reservation_id),
        ).fetchone())

    def settle_usage(self, principal: Principal, reservation_id: UUID, *,
                     fence_token: UUID, usage_event_ids: Sequence[UUID],
                     at: datetime | None = None) -> WalletReservation:
        """Atomically settle exact, persisted usage and release the remainder."""
        ids = tuple(usage_event_ids)
        if not ids or len(ids) != len(set(ids)) or any(not isinstance(v, UUID) for v in ids):
            raise WalletConflict("usage IDs ausentes, repetidos ou inválidos")
        with self.pool.connection() as connection, connection.transaction():
            row = self._locked_reservation(connection, principal, reservation_id)
            if row["fence_token"] != fence_token:
                raise UncertainEffect("worker perdeu fence financeiro")
            if row["status"] == "settled":
                if set(row["usage_event_ids"]) != set(ids):
                    raise WalletConflict("settlement replay divergente")
                return _reservation(row)
            if row["status"] == "released":
                raise WalletConflict("reserva já liberada")
            tickets = connection.execute(
                "select provider,model,max_liability_milli from app.wallet_attempt_tickets "
                "where reservation_id=%s order by created_at,ticket_id",
                (reservation_id,),
            ).fetchall()
            if not tickets or row["usage_operation_id"] is None:
                raise UncertainEffect("efeito sem ticket/operation auditável")
            events = connection.execute(
                "select * from app.usage_events where event_id=any(%s) and owner_id=%s "
                "and operation_id=%s order by event_id",
                (list(ids), principal.user_id, row["usage_operation_id"]),
            ).fetchall()
            if len(events) != len(ids) or len(events) != len(tickets):
                raise UncertainEffect("usage incompleto para os tickets emitidos")
            if Counter((e["provider"], e["model"]) for e in events) != Counter(
                    (t["provider"], t["model"]) for t in tickets):
                raise UncertainEffect("usage não corresponde aos tickets")
            readings = [UsageEvent(
                e["event_id"], e["operation_id"], e["component"],
                e["attempt_ordinal"], e["category"], e["provider"], e["model"],
                e["outcome"], e["input_units"], e["output_units"],
                e["cached_units"], e["audio_units"], e["image_units"],
                Decimal(e["cost_usd"]), e["cost_basis"],
                e["pricing_version"], e["billing_exact"],
            ) for e in events]
            version_row = connection.execute(
                "select * from app.pricing_versions where version_id=%s",
                (row["pricing_version_id"],),
            ).fetchone()
            quote = quote_usage(readings, version_from_record(version_row),
                                at=at or datetime.now(timezone.utc),
                                authorized_snapshot=True)
            if quote.shard_milli_debited > int(row["ceiling_milli"]):
                raise SpendCeilingExceeded("custo real excedeu teto confirmado")
            for event in events:
                connection.execute(
                    """insert into app.wallet_settled_usage
                    (usage_event_id,reservation_id,owner_id,event_sha256,cost_usd,
                     cost_basis,pricing_version) values (%s,%s,%s,%s,%s,%s,%s)""",
                    (event["event_id"], reservation_id, principal.user_id,
                     event["event_sha256"], event["cost_usd"],
                     event["cost_basis"], event["pricing_version"]),
                )
            return self._terminal_transfer(connection, row, quote.shard_milli_debited,
                                           ids, status="settled")

    def recover(self, principal: Principal, reservation_id: UUID, *,
                new_fence_token: UUID) -> WalletReservation:
        """Release only pre-dispatch holds; ticketed effects remain uncertain."""
        if not isinstance(new_fence_token, UUID):
            raise WalletConflict("novo fence token ausente")
        with self.pool.connection() as connection, connection.transaction():
            # Match the existing lock order: operation before wallet account.
            preliminary = connection.execute(
                "select usage_operation_id,owner_id from app.wallet_reservations "
                "where reservation_id=%s", (reservation_id,),
            ).fetchone()
            if preliminary is None or preliminary["owner_id"] != principal.user_id:
                raise WalletConflict("reserva não pertence ao owner")
            if preliminary["usage_operation_id"] is not None:
                operation = connection.execute(
                    "select status,lease_until,owner_id from app.operations where id=%s for update",
                    (preliminary["usage_operation_id"],),
                ).fetchone()
                if operation is None or operation["owner_id"] != principal.user_id:
                    raise UncertainEffect("operation ausente; reconciliação manual necessária")
                if (operation["status"] == "running" and operation["lease_until"] is not None
                        and operation["lease_until"] > datetime.now(timezone.utc)):
                    raise UncertainEffect("lease de operação ainda ativo")
            row = self._locked_reservation(connection, principal, reservation_id)
            if row["status"] in ("settled", "released"):
                return _reservation(row)
            tickets = connection.execute(
                "select 1 from app.wallet_attempt_tickets where reservation_id=%s limit 1",
                (reservation_id,),
            ).fetchone()
            if tickets:
                return _reservation(connection.execute(
                    "update app.wallet_reservations set fence_token=%s,status='uncertain' "
                    "where reservation_id=%s returning *",
                    (new_fence_token, reservation_id),
                ).fetchone())
            if row["status"] != "reserved":
                raise UncertainEffect("estado de efeito inconsistente")
            return self._terminal_transfer(connection, row, 0, (), status="released",
                                           reason="recovery_pre_dispatch")

    def release_pre_effect(self, principal: Principal, reservation_id: UUID, *,
                           fence_token: UUID) -> WalletReservation:
        with self.pool.connection() as connection, connection.transaction():
            row = self._locked_reservation(connection, principal, reservation_id)
            if row["fence_token"] != fence_token:
                raise UncertainEffect("worker perdeu fence financeiro")
            if row["status"] == "released":
                return _reservation(row)
            if row["status"] != "reserved":
                raise UncertainEffect("ticket emitido; liberação automática proibida")
            return self._terminal_transfer(connection, row, 0, (), status="released",
                                           reason="pre_dispatch_failure")

    def reconcile_proven_no_charge(self, principal: Principal, reservation_id: UUID, *,
                                   fence_token: UUID, actor_id: UUID,
                                   evidence_reference: str) -> WalletReservation:
        """Manual release only after an operator verifies provider no-charge proof.

        Never invoked from a failed operation, timeout or client request alone.
        The evidence reference and actor stay in the durable reservation receipt.
        """
        if not isinstance(actor_id, UUID):
            raise WalletConflict("reconciliação exige ator")
        evidence = _reference(evidence_reference)
        reason = f"provider_no_charge:{actor_id}:{evidence}"
        with self.pool.connection() as connection, connection.transaction():
            row = self._locked_reservation(connection, principal, reservation_id)
            if row["fence_token"] != fence_token:
                raise UncertainEffect("worker perdeu fence financeiro")
            if row["status"] == "released":
                if row["reconciliation_reason"] != reason:
                    raise WalletConflict("reconciliação replay divergente")
                return _reservation(row)
            if row["status"] not in ("effect_started", "uncertain"):
                raise WalletConflict("reconciliação só aceita efeito com ticket")
            if row["usage_operation_id"] is not None:
                observed = connection.execute(
                    "select 1 from app.usage_events where operation_id=%s and owner_id=%s "
                    "and billing_exact limit 1",
                    (row["usage_operation_id"], principal.user_id),
                ).fetchone()
                if observed:
                    raise WalletConflict("usage exato persistido; no-charge contraditório")
            return self._terminal_transfer(connection, row, 0, (),
                                           status="released", reason=reason)


@contextmanager
def wallet_spend_scope(wallet: PostgresWallet, principal: Principal,
                       reservation_id: UUID, fence_token: UUID) -> Iterator[None]:
    """Bind the durable ceiling to routed LLM dispatch, without enabling billing.

    The caller must reserve first and later settle/reconcile; ordinary API
    requests do not enter this scope until every paid effect is instrumented.
    """
    from llm_setup import llm_spend_guard_scope

    def admit(provider: str, model: str) -> None:
        wallet.admit_attempt(principal, reservation_id, fence_token=fence_token,
                             attempt_key=str(uuid4()), provider=provider, model=model)

    with llm_spend_guard_scope(admit):
        yield
