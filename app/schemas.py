from pydantic import BaseModel, EmailStr
from datetime import datetime


class ApplicationCreate(BaseModel):
    user_id: int
    name: str
    phone: str
    message: str


class ApplicationOut(BaseModel):
    id: int
    user_id: int
    name: str
    phone: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class SettingsOut(BaseModel):
    notification_email: EmailStr


class SettingsUpdate(BaseModel):
    notification_email: EmailStr
