from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints
from uuid import UUID
from app.models.user_report_model import ReportStatus


class CreateUserReportSchema(BaseModel):
    reported_user_id: UUID
    booking_id: UUID | None = None
    reason: Annotated[str, StringConstraints(
        strip_whitespace=True,
        min_length=5,
        max_length=1000,
    )]


class UserReportResponse(BaseModel):
    report_id: UUID
    reported_user_id: UUID
    booking_id: UUID | None
    reason: str
    status: ReportStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserReportListItem(BaseModel):
    report_id: UUID
    reported_user_id: UUID
    booking_id: UUID | None
    reason: str
    status: ReportStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
