"""Esquemas Pydantic del módulo móvil."""

from mobile_api.schemas.device import (
    DeviceRegister,
    DeviceResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from mobile_api.schemas.auth_ext import LogoutRequest
from mobile_api.schemas.mobile import (
    MobileDashboardResponse,
    ApplicationBoardResponse,
    TicketDetailResponse,
    MemberWorkload,
    TicketAssignRequest,
)

__all__ = [
    "DeviceRegister",
    "DeviceResponse",
    "NotificationPreferencesResponse",
    "NotificationPreferencesUpdate",
    "LogoutRequest",
    "MobileDashboardResponse",
    "ApplicationBoardResponse",
    "TicketDetailResponse",
    "MemberWorkload",
    "TicketAssignRequest",
]
