from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from api.domain import Scenario


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SaveRequest(Model):
    scenario: Scenario
    selected_alternative_id: str | None = None


class VersionRequest(SaveRequest):
    expected_version: int = Field(ge=1)


class DecisionRequest(Model):
    expected_version: int = Field(ge=1)
    dependency_id: str
    alternative_id: str | None = None
    decision: Literal['accepted', 'rejected', 'counterproposal']
    party: str = Field(min_length=1, max_length=160)
    valid_until: date
    notes: str = Field(default='', max_length=2000)
    counterproposal_start: str | None = None
    source: Literal['self_report'] = 'self_report'


class Baseline(Model):
    start_date: date
    end_date: date
    worked_minutes: int | None = Field(None, ge=0)
    cost_grosz: int | None = Field(None, ge=0)
    organization_minutes: int | None = Field(None, ge=0)


class TrialRequest(Model):
    expected_version: int = Field(ge=1)
    alternative_id: str
    baseline: Baseline
    start_date: date | None = None
    end_date: date | None = None


class RepairTrialRequest(Model):
    expected_version: int = Field(ge=1)
    alternative_id: str


class OutcomeRequest(Model):
    expected_version: int = Field(ge=1)
    date: date
    worked_minutes: int | None = Field(None, ge=0, le=1440)
    cost_grosz: int | None = Field(None, ge=0)
    organization_minutes: int | None = Field(None, ge=0, le=1440)
    disruptions: str = Field(default='', max_length=2000)
    source: Literal['self_report'] = 'self_report'
    complete_trial: bool = False


class ExportRequest(Model):
    scenario: Scenario
    alternative_id: str | None = None
    recipient: Literal['employer', 'caregiver', 'advisor', 'personal'] = 'employer'
    format: Literal['preview', 'html', 'text', 'pdf', 'ics'] = 'preview'
    approved_fields: list[str] = Field(default_factory=lambda: ['schedule', 'period', 'paid_minutes'])
    preview_id: str | None = None
    input_version: str | int = 1
    plan_id: str | None = None
    result: dict | None = None  # Never trusted: server computes the authoritative result.
    event_kinds: list[Literal['work', 'course', 'care', 'travel', 'obligation']] = Field(default_factory=lambda: ['work'])


class ImportRequest(Model):
    backup: dict
