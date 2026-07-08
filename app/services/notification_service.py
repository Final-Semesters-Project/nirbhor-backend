from uuid import UUID
from firebase_admin import messaging
from loguru import logger

from app.repositories.booking_repository import BookingFollowupData


class NotificationService:

    # TODO: Not used in urgent broadcast service/job
    @staticmethod
    async def send_urgent_broadcast(
        tokens: list[str],
        broadcast_id: UUID,
        skill_name: str,
    ) -> None:
        """
        Send high-priority FCM to all nearby providers simultaneously.
        Uses MulticastMessage for batch delivery (up to 500 tokens per call).
        """
        if not tokens:
            return

        message = messaging.MulticastMessage(
            tokens=tokens,
            data={
                # 'data' payload (not 'notification') so Flutter/React can handle
                # it even when app is in background, and extract broadcast_id
                "type": "URGENT_BROADCAST",
                "broadcast_id": str(broadcast_id),
                "skill_name": skill_name,
            },
            notification=messaging.Notification(
                title=f"জরুরি কাজ! / Urgent Job!",
                body=f"আপনার কাছে কেউ {skill_name} চাইছেন। / Someone needs {skill_name} urgently.",
            ),
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"}
            ),
        )

        try:
            response = messaging.send_each_for_multicast(message)
            logger.info(
                f"Urgent broadcast FCM: {response.success_count} sent, "
                f"{response.failure_count} failed out of {len(tokens)} tokens"
            )
        except Exception as e:
            # FCM failure must never crash the booking flow
            logger.error(f"FCM urgent broadcast failed: {e}")

    @staticmethod
    async def send_booking_followup(
        data: BookingFollowupData,
        attempt: int,
    ) -> None:
        """
        2-hour and 24-hour follow-up: 'Did you hire [provider]?'

        Why data-only (no notification block)?
        The notification text needs localization. The OS shows the `notification`
        block immediately without running app code. By using `data` only,
        the Flutter app handles display using its own locale setting.

        Flutter side: onBackgroundMessage reads data['type'] == 'BOOKING_FOLLOWUP'
        and shows a flutter_local_notifications notification in the correct language.

        Why not skip if no FCM token?
        We log and return cleanly. The seeker will still see the status when
        they 
        """

        if not data.fcm_token:
            logger.warning(
                f"No FCM token for {data.seeker_id}, "
                f"Skipping booking followup for {data.booking_id}"
            )
            return

        message = messaging.Message(
            token=data.fcm_token,
            data={
                "type": "BOOKING_FOLLOWUP",
                "booking_id": str(data.booking_id),
                "attempt": str(attempt),
                # send both language, flutter picks the correct one
                "provider_name_en": data.provider_name_en,
                "provider_name_bn": data.provider_name_bn,

                # send preferred_lang as a hint for Flutter
                "preferred_lang": data.preferred_lang,
            },
            # Minimal notification block as iOS background fallback
            # Flutter overrides this when app is in foreground/background
            notification=messaging.Notification(
                title="Booking Update",
                body=f"Did you hire {data.provider_name_en}?",
            ),
        )

        try:
            messaging.send(message)
            logger.info(
                f"Booking followup FCM sent: booking={data.booking_id} attempt={attempt} seeker={data.seeker_id}"
            )
        except messaging.UnregisteredError:
            # Token is stale — device uninstalled app or token rotated
            # TODO: delete this token (data.fcm_token) from fcm_tokens table
            logger.warning(
                f"Stale FCM token for seeker {data.seeker_id}, "
                f"booking {data.booking_id}"
            )
        except Exception as e:
            logger.error(f"FCM booking followup failed: {e}")

    @staticmethod
    async def send_completion_prompt(
        data: BookingFollowupData,
    ) -> None:
        """'Your job with [provider] should be done. Tap to review!'"""
        if not data.fcm_token:
            logger.warning(
                f"No FCM token for {data.seeker_id}, "
                f"Skipping completion prompt for booking: {data.booking_id}"
            )
            return

        message = messaging.Message(
            token=data.fcm_token,
            data={
                "type": "COMPLETION_PROMPT",
                "booking_id": str(data.booking_id),
                "provider_name_en": data.provider_name_en,
                "provider_name_bn": data.provider_name_bn,

                # send preferred_lang as a hint for Flutter
                "preferred_lang": data.preferred_lang,
            },
            notification=messaging.Notification(
                title="Job Done?",
                body=f"Was your job with {data.provider_name_en} completed? Tap to review!",
            ),
            android=messaging.AndroidConfig(priority="normal"),
        )

        try:
            messaging.send(message)
            logger.info(
                f"Completion prompt FCM sent: booking={data.booking_id} seeker={data.seeker_id}"
            )
        except messaging.UnregisteredError:
            logger.warning(f"Stale FCM token for seeker {data.seeker_id}")
        except Exception as e:
            logger.error(f"FCM completion prompt failed: {e}")

    # TODO: Not used in urgent broadcast service/jobs
    @staticmethod
    async def send_broadcast_expired(seeker_fcm_token: str) -> None:
        """'No one responded. Please try a manual search.'"""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={"type": "BROADCAST_EXPIRED"},
            notification=messaging.Notification(
                title="কোনো সাড়া নেই / No Response",
                body="কেউ সাড়া দেননি। ম্যানুয়াল অনুসন্ধান করুন। / No one responded. Try manual search.",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM broadcast expired notification failed: {e}")

    # TODO: Not used in urgent broadcast service/jobs
    @staticmethod
    async def send_broadcast_claimed(
        seeker_fcm_token: str,
        provider_name: str,
    ) -> None:
        """Notify seeker that a provider accepted their urgent request."""
        if not seeker_fcm_token:
            return

        message = messaging.Message(
            token=seeker_fcm_token,
            data={"type": "BROADCAST_CLAIMED", "provider_name": provider_name},
            notification=messaging.Notification(
                title="প্রোভাইডার পাওয়া গেছে! / Provider Found!",
                body=f"{provider_name} আপনার অনুরোধ গ্রহণ করেছেন। / {provider_name} accepted your request.",
            ),
        )

        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM broadcast claimed notification failed: {e}")

    # TODO: Not used in admin service after provider verification
    @staticmethod
    async def send_verification_approved(provider_fcm_token: str) -> None:
        message = messaging.Message(
            token=provider_fcm_token,
            data={"type": "VERIFICATION_APPROVED"},
            notification=messaging.Notification(
                title="যাচাইকরণ সম্পন্ন! / Verified!",
                body="আপনার অ্যাকাউন্ট যাচাই হয়েছে। এখন আপনি ব্লু টিক পাবেন।",
            ),
        )
        try:
            messaging.send(message)
        except Exception as e:
            logger.error(f"FCM verification approved failed: {e}")
