import asyncio
from uuid import UUID
from firebase_admin import messaging
from loguru import logger

from app.repositories.booking_repository import BookingFollowupData


class NotificationService:

    @staticmethod
    async def _send(message: messaging.Message) -> None:
        """
        Sends a Firebase message without blocking the event loop.

        messaging.send() is a synchronous blocking HTTP call.
        run_in_executor() moves it to a thread pool, releasing the
        event loop while waiting for the FCM HTTP response.

        All public methods call this instead of messaging.send() directly.
        """
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, messaging.send, message)
        except messaging.UnregisteredError:
            # Token is stale — app was uninstalled or token rotated
            # Logged here; callers don't need to handle this case
            logger.warning("Stale FCM token — message not delivered")
        except Exception as e:
            logger.opt(exception=e).error("FCM send failed")

    # ── Booking followup ──────────────────────────────────────────────────────

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

        # Pick the correct language for the visible notification text
        title = "বুকিং আপডেট" if data.preferred_lang == "bn" else "Booking Update"
        body = (
            f"আপনি কি {data.provider_name_bn} কে নিয়োগ করেছেন?"
            if data.preferred_lang == "bn"
            else f"Did you hire {data.provider_name_en}?"
        )

        await NotificationService._send(
            message=messaging.Message(
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
                    title=title,
                    body=body,
                ),
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(headers={"apns-priority": "10"}),
            ))
        logger.info(
            f"Booking followup FCM sent: booking={data.booking_id} attempt={attempt} seeker={data.seeker_id}")

    # ── Completion prompt ─────────────────────────────────────────────────────

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

        # Pick the correct language for the visible notification text
        title = "কাজ সম্পন্ন?" if data.preferred_lang == "bn" else "Job Done?"
        body = (
            f"{data.provider_name_bn} এর সাথে কাজ শেষ? রিভিউ দিন।"
            if data.preferred_lang == "bn"
            else f"Was your job with {data.provider_name_en} completed? Tap to review."
        )

        await NotificationService._send(
            message=messaging.Message(
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
                    title=title,
                    body=body,
                ),
                android=messaging.AndroidConfig(priority="normal"),
                apns=messaging.APNSConfig(headers={"apns-priority": "5"}),
            ))

        logger.info(
            f"Completion prompt FCM sent: booking={data.booking_id} seeker={data.seeker_id}")

    # ── Broadcast expired ─────────────────────────────────────────────────────

    @staticmethod
    async def send_broadcast_expired(seeker_fcm_token: str, preferred_lang: str) -> None:
        """'No one responded. Please try a manual search.'"""
        if not seeker_fcm_token:
            return

        # Pick the correct language for the visible notification text
        title = "কোনো সাড়া নেই" if preferred_lang == "bn" else "No one responded"
        body = (
            "কেউ সাড়া দেননি। ম্যানুয়াল অনুসন্ধান করুন।"
            if preferred_lang == "bn"
            else "No one responded. Try manual search."
        )

        await NotificationService._send(
            message=messaging.Message(
                token=seeker_fcm_token,
                data={
                    "type": "BROADCAST_EXPIRED",
                    "preferred_lang": preferred_lang
                },
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(headers={"apns-priority": "10"}),
            )
        )
        logger.info(f"Broadcast expired FCM sent: {seeker_fcm_token}")

    # ── Broadcast claimed (called from request handler) ───────────────────────
    # TODO: Not used in urgent broadcast service/jobs

    @staticmethod
    async def send_broadcast_claimed(
        seeker_fcm_token: str,
        provider_name_en: str,
        provider_name_bn: str,
        preferred_lang: str,
    ) -> None:
        """
        Called from urgent_service.claim_broadcast() during an HTTP request.
        MUST use run_in_executor (via _send) — blocking here delays the
        HTTP response and all concurrent requests.
        """
        if not seeker_fcm_token:
            return

        title = "প্রোভাইডার পাওয়া গেছে!" if preferred_lang == "bn" else "Provider Found!"
        body = (
            f"{provider_name_bn} আপনার অনুরোধ গ্রহণ করেছেন।"
            if preferred_lang == "bn"
            else f"{provider_name_en} accepted your request."
        )

        await NotificationService._send(
            message=messaging.Message(
                token=seeker_fcm_token,
                data={
                    "type":             "BROADCAST_CLAIMED",
                    "provider_name_en": provider_name_en,
                    "provider_name_bn": provider_name_bn,
                    "preferred_lang":   preferred_lang,
                },
                notification=messaging.Notification(
                    title=title,
                    body=body,
                )
            ))
        logger.info(
            f"Broadcast for FCM token: {seeker_fcm_token} claimed by {provider_name_en}")

    # ── Urgent broadcast (called from request handler) ────────────────────────
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
        Still uses run_in_executor because send_each_for_multicast is also sync.
        """
        if not tokens:
            return

        message = messaging.MulticastMessage(
            tokens=tokens,
            data={
                "type": "URGENT_BROADCAST",
                "broadcast_id": str(broadcast_id),
                "skill_name": skill_name,
            },
            notification=messaging.Notification(
                title="জরুরি কাজ!" if True else "Urgent Job!",
                # For MulticastMessage we can't personalize per-token language
                # Use Bangla as default since majority of providers are Bangla-speaking
                # The data payload lets the app override this if needed
                body=f"কেউ {skill_name} চাইছেন। এখনই গ্রহণ করুন।",
            ),
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"}
            ),
        )
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                messaging.send_each_for_multicast,
                message
            )
            logger.info(
                f"Urgent broadcast FCM: {response.success_count} sent, "
                f"{response.failure_count} failed out of {len(tokens)} tokens"
            )
        except Exception as e:
            # FCM failure must never crash the booking flow
            logger.error(f"FCM urgent broadcast failed: {e}")

    # ── Verification approved (called from request handler) ───────────────────
    # TODO: Not used in admin service after provider verification

    @staticmethod
    async def send_verification_approved(
        provider_fcm_token: str,
        preferred_lang: str
    ) -> None:
        """Called from admin_service.handle_verification() during an HTTP request."""
        if not provider_fcm_token:
            return

        title = "যাচাইকরণ সম্পন্ন!" if preferred_lang == "bn" else "Verified!"
        body = (
            "আপনার অ্যাকাউন্ট যাচাই হয়েছে। এখন আপনি ব্লু টিক পাবেন।"
            if preferred_lang == "bn"
            else "Your account is now verified. You have a blue tick."
        )

        await NotificationService._send(
            message=messaging.Message(
                token=provider_fcm_token,
                data={
                    "type": "VERIFICATION_APPROVED",
                    "preferred_lang": preferred_lang
                },
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                android=messaging.AndroidConfig(priority="normal"),
                apns=messaging.APNSConfig(headers={"apns-priority": "5"}),
            ))
        logger.info(f"Verification approved FCM sent: {provider_fcm_token}")
