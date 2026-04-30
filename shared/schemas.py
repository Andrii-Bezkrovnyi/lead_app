from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=255, examples=["Олексій"])
    phone: str = Field(min_length=3, max_length=32, examples=["+380982342123"])
    country: str = Field(min_length=2, max_length=2, examples=["UA"])
    offer_id: UUID
    affiliate_id: UUID

    @field_validator("name", "phone", "country")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country must be ISO 3166-1 alpha-2")
        return value


class LeadAccepted(BaseModel):
    status: str = "accepted"
    stream: str
    message_id: str


class LeadSummaryLead(BaseModel):
    id: UUID
    name: str
    phone: str
    country: str
    offer_id: UUID
    affiliate_id: UUID
    created_at: datetime


class AuthTokenRequest(BaseModel):
    affiliate_id: UUID = Field(examples=["11111111-1111-1111-1111-111111111111"])


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    access_expires_in: int
    refresh_expires_in: int


class LeadGroupItem(BaseModel):
    group_key: str
    count: int
    leads: list[LeadSummaryLead]


class LeadsSummaryResponse(BaseModel):
    affiliate_id: UUID
    group: Literal["date", "offer"]
    date_from: date
    date_to: date
    total_count: int
    items: list[LeadGroupItem]
    model_config = ConfigDict(from_attributes=True)
