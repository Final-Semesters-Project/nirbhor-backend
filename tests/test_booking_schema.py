from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.booking_schema import BookingRespondFromNotificationSchema


def test_cancelled_booking_does_not_require_work_schedule():
    response = BookingRespondFromNotificationSchema(hired=False)

    assert response.work_schedule is None


def test_hired_booking_requires_work_schedule():
    with pytest.raises(ValidationError, match="work schedule is required"):
        BookingRespondFromNotificationSchema(hired=True)


def test_hired_booking_accepts_future_work_schedule():
    work_schedule = datetime.now(timezone.utc) + timedelta(days=1)

    response = BookingRespondFromNotificationSchema(
        hired=True,
        work_schedule=work_schedule,
    )

    assert response.work_schedule == work_schedule
