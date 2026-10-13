"""Owner-confirmed image quotes. Wallet and art repository remain canonical writers."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from psycopg.types.json import Jsonb

from infrastructure.contracts import Conflict, JobRequest, Principal
from infrastructure.wallet import PostgresWallet
from services.art_brief import render_image_prompt
from services.art_triggers import ArtGenerationRequest
from services.dynamic_art import DynamicArtRepository, lock_art_game
from services.job_fence import current_job, require_job_fence
from services.image_pricing import IMAGE_PRICING_VERSION, require_image_prices
from services.shard_pricing import PricingUnavailable, quote_attempt_ceiling, version_from_record


def public_quote(row: dict) -> dict:
    return {"quote_id": str(row["quote_id"]), "type": row["image_type"],
            "credits_milli": str(row["credits_milli"]),
            "pricing_version": row["pricing_version_id"],
            "expires_at": row["expires_at"].isoformat(),
            "reformulation": row["reformulation"]}


class ImageQuoteRepository:
    def __init__(self, pool, *, at: datetime | None = None) -> None:
        self.pool = pool
        self.at = at
        self.wallet = PostgresWallet(pool)

    def issue(self, principal: Principal, game_id: UUID, *, request: ArtGenerationRequest,
              brief: dict, model: str, profile_version: str, reformulation: bool = False) -> dict:
        now = self.at or datetime.now(timezone.utc)
        require_image_prices(model, now)
        with self.pool.connection() as connection, connection.transaction():
            game = connection.execute(
                "select coalesce((state->'continuity'->>'timeline_epoch')::integer,0) as timeline_epoch "
                "from app.games where id=%s and owner_id=%s for share",
                (game_id, principal.user_id),
            ).fetchone()
            if not game:
                raise Conflict("campanha não pertence ao owner")
            profile = connection.execute(
                "select * from app.image_price_profiles where profile_id=%s",
                (os.getenv("RPG_IMAGE_PRICE_PROFILE_SCENE" if request.subject_type == "scene"
                           else "RPG_IMAGE_PRICE_PROFILE_PORTRAIT",
                           os.getenv("RPG_IMAGE_PRICE_PROFILE", "")),),
            ).fetchone()
            if (not profile or profile["model"] != model or profile["size"] != brief["size"]
                    or profile["expires_at"] <= now):
                raise PricingUnavailable("image pricing não configurado ou expirado")
            version = connection.execute(
                "select * from app.pricing_versions where version_id=%s",
                (profile["pricing_version_id"],),
            ).fetchone()
            ceiling = quote_attempt_ceiling(profile["max_provider_usd"], version_from_record(version), at=now)
            row = connection.execute(
                """insert into app.image_quotes
                (quote_id,owner_id,game_id,timeline_epoch,image_type,credits_milli,
                 pricing_version_id,price_profile_id,image_rate_card_version,expires_at,model,profile_version,
                 prompt_hash,private_brief,trigger,reformulation)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
                (uuid4(), principal.user_id, game_id, game["timeline_epoch"], request.subject_type,
                 ceiling, profile["pricing_version_id"], profile["profile_id"], IMAGE_PRICING_VERSION,
                 min(now + timedelta(minutes=5), profile["expires_at"]), model, profile_version,
                 sha256(render_image_prompt(brief).encode()).hexdigest(),
                 Jsonb(brief), Jsonb(asdict(request)), reformulation),
            ).fetchone()
            return dict(row)

    def get(self, principal: Principal, game_id: UUID, quote_id: UUID, *, connection=None) -> dict:
        if connection is None:
            with self.pool.connection() as connection:
                return self.get(principal, game_id, quote_id, connection=connection)
        row = connection.execute(
            "select * from app.image_quotes where quote_id=%s and owner_id=%s and game_id=%s",
            (quote_id, principal.user_id, game_id),
        ).fetchone()
        if not row:
            raise Conflict("quote não pertence à campanha/owner")
        return dict(row)

    def confirm(self, principal: Principal, game_id: UUID, quote_id: UUID, *,
                connection, epoch: int, version: int, queue) -> dict:
        # Lock the immutable quote to serialize independent confirmation requests.
        connection.execute("select quote_id from app.image_quotes where quote_id=%s for update", (quote_id,))
        quote = self.get(principal, game_id, quote_id, connection=connection)
        prior = connection.execute("select * from app.art_generations where image_quote_id=%s", (quote_id,)).fetchone()
        if prior:
            return dict(prior)
        now = self.at or datetime.now(timezone.utc)
        if quote["expires_at"] <= now or quote["timeline_epoch"] != epoch:
            raise Conflict("quote expirado ou de outra linha temporal")
        generation_id = uuid5(NAMESPACE_URL, f"image-quote:{quote_id}")
        # The operation exists before the canonical wallet reservation checks ownership.
        connection.execute(
            """insert into app.operations (id,owner_id,game_id,kind,status,request_sha256,finished_at)
            values (%s,%s,%s,'art','completed',%s,now())""",
            (generation_id, principal.user_id, game_id, quote["prompt_hash"]),
        )
        reservation = self.wallet.reserve(principal, reference_type="image", reference_id=str(quote_id),
            pricing_version_id=quote["pricing_version_id"], ceiling_milli=quote["credits_milli"],
            fence_token=quote_id, usage_operation_id=generation_id, at=now, connection=connection)
        trigger = ArtGenerationRequest(**quote["trigger"])
        repository = DynamicArtRepository(self.pool, model=quote["model"], profile_version=quote["profile_version"])
        generation = repository.reserve(principal, game_id, timeline_epoch=epoch,
            generation_id=generation_id, request=trigger, brief=quote["private_brief"], connection=connection)
        if generation["generation_id"] != generation_id:
            raise Conflict("gatilho já confirmado por outro quote")
        connection.execute(
            "update app.art_generations set image_quote_id=%s,wallet_reservation_id=%s where generation_id=%s",
            (quote_id, reservation.reservation_id, generation_id),
        )
        asset_id = uuid5(NAMESPACE_URL, f"art-asset:{generation_id}")
        queue.enqueue(JobRequest("generate_dynamic_art", f"art:{generation_id}",
            {"generation": {"generation_id": str(generation_id)}, "asset_id": str(asset_id),
             "owner_id": str(principal.user_id), "game_id": str(game_id),
             "timeline_epoch": epoch, "commit_version": version},
            owner_id=principal.user_id, game_id=game_id, max_attempts=1), connection=connection)
        return generation

    def dispatch(self, generation_id: UUID, owner_id: UUID, game_id: UUID) -> dict:
        """Commit one ticket before network I/O, under the live job fence."""
        job = current_job()
        if (job is None or job.request.kind != "generate_dynamic_art"
                or job.request.dedupe_key != f"art:{generation_id}"
                or job.request.owner_id != owner_id or job.request.game_id != game_id):
            raise Conflict("imagem exige job confirmado e fence ativo")
        with self.pool.connection() as connection, connection.transaction():
            lock_art_game(connection, generation_id)
            require_job_fence(connection)
            row = connection.execute(
                """select g.* from app.art_generations g
                join app.image_quotes q on q.quote_id=g.image_quote_id
                join app.games game on game.id=g.game_id
                  and coalesce((game.state->'continuity'->>'timeline_epoch')::integer,0)=g.timeline_epoch
                where g.generation_id=%s and g.owner_id=%s and g.game_id=%s for update of g""",
                (generation_id, owner_id, game_id),
            ).fetchone()
            if not row or row["status"] != "pending":
                raise Conflict("imagem sem quote confirmado ou requer reconciliação")
            quote = self.get(Principal(owner_id, "worker", str(owner_id)), game_id,
                             row["image_quote_id"], connection=connection)
            require_image_prices(quote["model"], self.at or datetime.now(timezone.utc))
            if quote["image_rate_card_version"] != IMAGE_PRICING_VERSION:
                raise PricingUnavailable("image pricing changed; a new quote is required")
            if (row["model"] != quote["model"] or row["prompt_hash"] != quote["prompt_hash"]
                    or row["private_brief"] != quote["private_brief"]
                    or row["profile_version"] != quote["profile_version"]
                    or row["subject_type"] != quote["image_type"]
                    or row["subject_id"] != quote["trigger"]["subject_id"]
                    or row["timeline_epoch"] != quote["timeline_epoch"]
                    or sha256(render_image_prompt(row["private_brief"]).encode()).hexdigest() != quote["prompt_hash"]):
                raise Conflict("imagem divergiu do quote confirmado")
            principal = Principal(owner_id, "worker", str(owner_id))
            self.wallet.admit_image_attempt(principal, row["wallet_reservation_id"],
                quote_id=quote["quote_id"], generation_id=generation_id, connection=connection)
            connection.execute("update app.art_generations set status='generating',attempt_count=1 where generation_id=%s",
                               (generation_id,))
            return dict(row)

    def hold_or_release(self, generation_id: UUID) -> None:
        """Pre-dispatch failure releases; any ticket or observed effect retains funds."""
        with self.pool.connection() as connection, connection.transaction():
            lock_art_game(connection, generation_id)
            require_job_fence(connection)
            row = connection.execute("select * from app.art_generations where generation_id=%s for update", (generation_id,)).fetchone()
            if not row or not row["image_quote_id"]:
                return
            job = current_job()
            if (job is None or job.request.owner_id != row["owner_id"]
                    or job.request.game_id != row["game_id"]
                    or job.request.dedupe_key != f"art:{generation_id}"):
                raise Conflict("reconciliação de imagem exige job correspondente")
            principal = Principal(row["owner_id"], "worker", str(row["owner_id"]))
            reservation = self.wallet._locked_reservation(connection, principal, row["wallet_reservation_id"])
            if reservation["status"] == "reserved":
                self.wallet.release_pre_effect(principal, reservation["reservation_id"],
                    fence_token=row["image_quote_id"], connection=connection)
                code = "pre_dispatch_failure"
            elif reservation["status"] in {"effect_started", "uncertain"}:
                self.wallet.mark_uncertain(principal, reservation["reservation_id"],
                    reason="image_external_result_uncertain", connection=connection)
                code = "external_result_uncertain"
            else:
                return
            connection.execute("update app.art_generations set status='failed',error_code=%s where generation_id=%s",
                               (code, generation_id))
