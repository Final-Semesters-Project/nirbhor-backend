import re


def parse_integrity_error(error_msg: str, lang: str = "en") -> str:
    """Parse PostgreSQL IntegrityError into readable message."""

    from app.core.i18n import t

    # ── Unique violations ──────────────────────────────────────────
    if "users_phone_en_key" in error_msg:
        return t("phone_already_exists", lang)

    if "uq_review_booking_reviewer" in error_msg:
        return t("duplicate_review_error", lang)

    if "fcm_tokens_token_key" in error_msg:
        return t("duplicate_fcm_token_error", lang)

    if "user_sessions_refresh_token_key" in error_msg:
        return t("duplicate_refresh_token_error", lang)

    if "app_versions_platform_key" in error_msg:
        return t("duplicate_version_platform_key_error", lang)

    # ── FK violations ──────────────────────────────────────────────
    if "provider_skill_links_skill_id_fkey" in error_msg:
        return t("invalid_skill", lang)

    if "provider_skill_links_provider_id_fkey" in error_msg:
        return t("user_not_found", lang)

    if "provider_profiles_user_id_fkey" in error_msg:
        return t("user_not_found", lang)

    if "skills_category_id_fkey" in error_msg:
        return t("invalid_category", lang)

    if "user_reports_booking_id_fkey" in error_msg:
        return t("booking_not_found", lang)

    if "user_reports_reported_user_id_fkey" in error_msg:
        return t("reported_user_not_found", lang)

    if "user_reports_reporter_id_fkey" in error_msg:
        return t("reporter_not_found", lang)

    if "user_sessions_user_id_fkey" in error_msg:
        return t("user_not_found", lang)

    if "urgent_broadcasts_claimed_by_provider_id_fkey" in error_msg:
        return t("provider_not_found", lang)

    if "urgent_broadcasts_seeker_id_fkey" in error_msg:
        return t("seeker_not_found", lang)

    if "urgent_broadcasts_skill_id_fkey" in error_msg:
        return t("skill_not_found", lang)

    if "teams_leader_id_fkey" in error_msg:
        return t("team_leader_not_found", lang)

    if "reviews_booking_id_fkey" in error_msg:
        return t("booking_review_not_found", lang)

    if "reviews_reviewee_id_fkey" in error_msg:
        return t("reviewee_not_found", lang)

    if "reviews_reviewer_id_fkey" in error_msg:
        return t("reviewer_not_found", lang)

    if "bookings_provider_id_fkey" in error_msg:
        return t("bookings_provider_not_found", lang)

    if "bookings_seeker_id_fkey" in error_msg:
        return t("bookings_seeker_not_found", lang)

    if "bookings_skill_id_fkey" in error_msg:
        return t("bookings_skill_not_found", lang)

    if "bookings_team_id_fkey" in error_msg:
        return t("bookings_team_not_found", lang)

    if "fcm_tokens_user_id_fkey" in error_msg:
        return t("fcm_token_user_not_found", lang)

    # ── Generic fallbacks ──────────────────────────────────────────
    if "ForeignKeyViolationError" in error_msg:
        return t("fk_violation", lang)

    if "UniqueViolationError" in error_msg:
        return t("unique_violation", lang)

    return t("integrity_error", lang)
