from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


BorrowerBucket = Literal["0-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"]
ProductType = Literal["credit_card", "bnpl", "personal_loan"]
Outcome = Literal["connected", "no_answer", "ptp_taken", "dispute", "failed_downstream"]


class CallEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    campaign_id: str = Field(min_length=1)
    borrower_bucket: BorrowerBucket
    timestamp: datetime
    outcome: Outcome
    product_type: ProductType | None = None
    call_duration_s: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)


class PipelineResult(BaseModel):
    status: Literal["ok"]
    transcript: str
    response_audio_ref: str
    latency_ms: float


class ProcessResponse(BaseModel):
    event_id: UUID
    success: bool
    outcome: Outcome
    retry_count: int
    circuit_state: str
    downstream_latency_ms: float | None = None
    total_latency_ms: float
    dlq_status: str | None = None
