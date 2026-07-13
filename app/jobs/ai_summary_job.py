import asyncio
from datetime import datetime, timezone, timedelta
import json
from anthropic.types import TextBlock
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.provider_profile_model import ProviderProfile
from app.models.review_model import Review
from app.core.config import settings


# ── Constants ──────────────────────────────────────────────────────────────────
MIN_REVIEWS_FOR_SUMMARY = 10
SUMMARY_COOL_DOWN_DAYS = 14    # don't regenerate within 2 weeks
# must have 3 NEW reviews since last summary to bother regenerating
REVIEWS_NEEDED_TO_REGENERATE = 5
# cheapest model, sufficient for summarization
ANTHROPIC_MODEL = "claude-haiku-4-5"
MAX_REVIEWS_TO_SEND = 30    # cap — don't send 500 reviews to the API
JOB_TIMEOUT_SECONDS = 300   # 5 minutes max for the entire job


async def generate_ai_review_summaries():
    """
    Weekly cron job — Sunday 2 AM — generates EN + BN AI review summaries for providers.
    Hard timeout of 5 minutes prevents the job from blocking the scheduler.

    Eligibility rules:
    1. Provider has at least 10 reviews (MIN_REVIEWS_FOR_SUMMARY)
    2. No existing summary → generate immediately
    3. Has existing summary → only regenerate if:
       a. At least 14 days since last summary generation (SUMMARY_COOLDOWN_DAYS)
       b. At least 5 new reviews since last generation (REVIEWS_NEEDED_TO_REGEN)
       This prevents wasting API calls when nothing meaningful has changed.
    4. Only sends the 30 most recent reviews to the API (lightweight)

    Why Haiku and not Sonnet?
    Summarization is a simple task. Haiku costs ~20x less than Sonnet
    and produces identical quality for "summarize these reviews in 2 sentences."
    """

    logger.info("AI summary job: starting")
    start_time = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        providers = await _get_eligible_providers(db)

        if not providers:
            logger.info("AI summary job: no eligible providers this run")
            return

        logger.info(f"AI summary job: processing {len(providers)} providers")

        for provider in providers:
            # Check if we've exceeded the job's total time budget
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

            if elapsed > JOB_TIMEOUT_SECONDS:
                logger.warning(
                    f"AI summary job: timeout after {elapsed:.0f}s, "
                    f"processed {providers.index(provider)}/{len(providers)} providers"
                )
                break

            try:
                await _generate_summary_for_provider(db, provider)
                # Small delay between providers to avoid hammering the API
                await asyncio.sleep(1)
            except Exception as e:
                logger.opt(exception=e).error(
                    f"AI summary job: failed for provider {provider.user_id}"
                )
                # Continue to next provider — one failure doesn't stop the job
                continue

        await db.commit()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"AI summary job: completed in {elapsed:.1f}s")


async def _get_eligible_providers(db: AsyncSession) -> list[ProviderProfile]:
    """
    Single query to find providers who need a summary generated or updated.
    Applies all eligibility filters in SQL to avoid loading unnecessary rows.

    Eligible if:
    - Has >= 10 reviews total
    - AND either:
        a) Has no summary yet
        b) OR last summary was >= 14 days ago AND has >= 5 new reviews since then
    """
    now = datetime.now(timezone.utc)
    cool_down_cutoff = now - timedelta(days=SUMMARY_COOL_DOWN_DAYS)

    # Subquery: total review count per provider
    total_reviews_sq = (
        select(
            Review.reviewee_id,
            func.count().label("total"),
        )
        .group_by(Review.reviewee_id)
        .subquery()
    )

    # Subquery: reviews added since last summary generation
    # Uses COALESCE so providers with no summary are treated as having
    # their summary generated in year 2000 — meaning all reviews are "new"
    new_reviews_sq = (
        select(func.count())
        .where(Review.reviewee_id == ProviderProfile.user_id)
        .where(
            Review.created_at > func.coalesce(
                ProviderProfile.ai_summary_generated_at,
                datetime(2000, 1, 1, tzinfo=timezone.utc),
            )
        )
        .correlate(ProviderProfile)
        .scalar_subquery()
    )

    result = await db.execute(
        select(ProviderProfile)
        .join(
            total_reviews_sq,
            ProviderProfile.user_id == total_reviews_sq.c.reviewee_id,
        )
        # Rule 1: minimum review threshold
        .where(total_reviews_sq.c.total >= MIN_REVIEWS_FOR_SUMMARY)
        # Rule 2: no summary yet OR (cool-down passed AND enough new reviews)
        .where(
            ProviderProfile.ai_review_summary_en.is_(None)
            | (
                (ProviderProfile.ai_summary_generated_at <= cool_down_cutoff)
                & (new_reviews_sq >= REVIEWS_NEEDED_TO_REGENERATE)
            )
        )
        .order_by(ProviderProfile.user_id)  # consistent order across runs
    )
    return list(result.scalars().all())


async def _generate_summary_for_provider(
    db: AsyncSession,
    profile: ProviderProfile,
) -> None:
    """
    Fetch reviews, call AI, update profile. 
    Does NOT commit — the outer loop commits after all providers are processed.
    """

    # Fetch the most recent reviews with comments
    result = await db.execute(
        select(Review.rating, Review.comment)
        .where(Review.reviewee_id == profile.user_id)
        .where(Review.comment.is_not(None))
        .where(Review.comment != "")
        .order_by(Review.created_at.desc())
        .limit(MAX_REVIEWS_TO_SEND)
    )
    reviews = result.all()

    if not reviews:
        logger.debug(
            f"AI summary: provider {profile.user_id} — "
            f"has reviews but no text comments, skipping"
        )
        return

    review_text = "\n".join(
        f"- ({row.rating}/5) {row.comment}"
        for row in reviews
    )

    summary_en, summary_bn = await _call_anthropic(
        provider_id=profile.user_id,
        review_text=review_text,
    )

    if not summary_en:
        return

    profile.ai_review_summary_en = summary_en
    profile.ai_review_summary_bn = summary_bn
    profile.ai_summary_generated_at = datetime.now(timezone.utc)
    logger.info(
        f"AI summary: generated for {profile.user_id} using {len(reviews)} reviews"
    )


async def _call_anthropic(
    provider_id,
    review_text: str,
) -> tuple[str | None, str | None]:
    """
    Calls Anthropic API synchronously via run_in_executor.
    Returns (summary_en, summary_bn) or (None, None) on any failure.
    """
    import anthropic

    prompt = f"""
    You are summarizing worker reviews for a labor marketplace in Bangladesh.

    Reviews:
    {review_text}

    Write exactly 2 sentences summarizing what customers commonly say.
    Be specific. Mention both strengths and any repeated concerns if present.

    Respond ONLY with valid JSON, no other text:
    {{"en": "English summary.", "bn": "বাংলা সারসংক্ষেপ।"}}
    """

    def _sync_call() -> str:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        # Safely find the first TextBlock in the content list
        # first_block = response.content[0]
        if response.content[0].type == "text":
            return response.content[0].text

        return ""  # Fallback if no text block was returned

    loop = asyncio.get_event_loop()
    raw = ""  # initialize before try so it's always bound
    try:
        raw = await loop.run_in_executor(None, _sync_call)
        data = json.loads(raw.strip())
        en = data.get("en", "").strip()
        bn = data.get("bn", "").strip() or None
        if not en:
            logger.warning(
                f"AI summary: empty response for provider {provider_id}")
            return None, None
        return en, bn
    except json.JSONDecodeError:
        logger.error(
            f"AI summary: invalid JSON for provider {provider_id}: {raw[:100]!r}"
        )
        return None, None
    except Exception as e:
        logger.opt(exception=e).error(
            f"AI summary: API call failed for provider {provider_id}"
        )
        return None, None
