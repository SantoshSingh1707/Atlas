import pytest
from pydantic import ValidationError

from app.schemas import (
    CapabilityResult,
    ResearchOptions,
    ResearchRequest,
    RunEvent,
    RunStatus,
)


def test_options_defaults():
    assert ResearchRequest(question="how do transformer work").options is None
    assert ResearchOptions().max_sub_queries== 5

def test_short_question_rejected():
    with pytest.raises(ValidationError):ResearchRequest(question="hi")

def test_result_roundtrip_and_status_enum():
    r = CapabilityResult(run_id="r",capability_id="research",status=RunStatus.finished)
    assert r.citations ==[]
    assert CapabilityResult.model_validate(r.model_dump()).run_id == "r"

def test_run_event_literal_rejects_unknown_step():
    with pytest.raises(ValidationError):
        RunEvent(run_id="r",step="nope",status="started")