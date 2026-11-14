from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    kind: str
    message: str
    created_at: datetime
    read_at: datetime | None


class UnreadCountOut(BaseModel):
    count: int
