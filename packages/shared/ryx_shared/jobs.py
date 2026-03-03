"""RYX Jobs — Suivi des tâches asynchrones (idempotence + retry)."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class JobType(str, Enum):
    PREPROCESS = "preprocess"
    PILLAR0 = "pillar0"
    MEDGEMMA = "medgemma"
    PREDICTION = "prediction"
    EVIDENCE_VALIDATE = "evidence_validate"
    INDEX_UPDATE = "index_update"
    INTEGRATION_SYNC = "integration_sync"
    NOTIFICATION = "notification"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


class JobLocation(str, Enum):
    EDGE = "edge"
    HUB = "hub"


class Job(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    type: JobType
    status: JobStatus = JobStatus.QUEUED
    payload: dict = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    last_error: str | None = None
    location: JobLocation = JobLocation.HUB
    priority: int = Field(default=5, ge=1, le=10)  # 1=highest, 10=lowest
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def start(self) -> "Job":
        return self.model_copy(update={
            "status": JobStatus.RUNNING,
            "started_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

    def complete(self) -> "Job":
        return self.model_copy(update={
            "status": JobStatus.DONE,
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

    def fail(self, error: str) -> "Job":
        new_retry = self.retry_count + 1
        new_status = JobStatus.FAILED if new_retry >= self.max_retries else JobStatus.QUEUED
        return self.model_copy(update={
            "status": new_status,
            "retry_count": new_retry,
            "last_error": error,
            "updated_at": datetime.utcnow(),
        })

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries
