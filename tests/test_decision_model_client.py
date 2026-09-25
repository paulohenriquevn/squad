"""A typed decision is read, or it is refused — never repaired.

The client exists so the lead can ask a closed question and get back one of the
options it declared. Everything here tests the boundary: an answer outside the
declared options, a failed request and a missing key all come back as ONE typed
error the caller can fall back on, and none of them carries the API key.
"""
from __future__ import annotations

import json
import urllib.error

import pytest
from decision_model import (
    API_KEY_ENV,
    ENDPOINT,
    MODEL,
    DecisionModelUnavailable,
    SystemOneClient,
    choice,
)

# The response OpenRouter returned on 2026-09-25 for a menu-shaped state, trimmed to
# the fields the client reads.
_REAL_RESPONSE = {
    "model": "typesafe/jev-1.13-20260917",
    "answers": {
        "option": {"type": "choice", "choice": "2",
                   "probabilities": {"1": 0.02, "2": 0.98, "3": 0}, "confidence": 0.96},
    },
    "usage": {"input_tokens": 391, "output_tokens": 58, "cost": 0.000016422},
    "id": "gen-dec-1790364190-7G2zmVpq7Z1yIEnxBazc",
    "provider": "TypeSafe",
}

_QUESTIONS = {"option": choice("Which option?", {"1": "retry", "2": "record", "3": "skip"})}


def _client(status: int = 200, body: object = _REAL_RESPONSE, sent: list | None = None,
            key: str = "sk-or-test-secret") -> SystemOneClient:
    def post(url, headers, data, timeout):
        if sent is not None:
            sent.append((url, headers, json.loads(data)))
        return status, body if isinstance(body, str) else json.dumps(body)
    return SystemOneClient(key, post=post)


def test_a_choice_answer_is_read_with_its_confidence() -> None:
    answers = _client().choices({"screen": "x"}, _QUESTIONS)
    assert answers["option"].choice == "2"
    assert answers["option"].confidence == 0.96
    assert answers["option"].probabilities["2"] == 0.98


def test_the_request_pins_the_model_and_authenticates_with_the_key() -> None:
    sent: list = []
    _client(sent=sent).choices({"screen": "x"}, _QUESTIONS)
    url, headers, body = sent[0]
    assert url == ENDPOINT
    assert headers["Authorization"] == "Bearer sk-or-test-secret"
    assert body["model"] == MODEL
    assert body["questions"]["option"]["criteria"] == {"1": "retry", "2": "record",
                                                       "3": "skip"}


def test_a_choice_outside_the_declared_criteria_is_refused() -> None:
    body = json.loads(json.dumps(_REAL_RESPONSE))
    body["answers"]["option"]["choice"] = "9"
    with pytest.raises(DecisionModelUnavailable, match="not one of"):
        _client(body=body).choices({"screen": "x"}, _QUESTIONS)


def test_a_question_left_unanswered_is_refused() -> None:
    body = json.loads(json.dumps(_REAL_RESPONSE))
    del body["answers"]["option"]
    with pytest.raises(DecisionModelUnavailable, match="no answer"):
        _client(body=body).choices({"screen": "x"}, _QUESTIONS)


def test_an_http_error_names_the_status_and_never_the_key() -> None:
    with pytest.raises(DecisionModelUnavailable) as caught:
        _client(status=402, body='{"error":{"message":"Insufficient credits"}}').choices(
            {"screen": "x"}, _QUESTIONS)
    assert "402" in str(caught.value)
    assert "Insufficient credits" in str(caught.value)
    assert "sk-or-test-secret" not in str(caught.value)


def test_a_body_that_is_not_json_is_refused() -> None:
    with pytest.raises(DecisionModelUnavailable, match="not JSON"):
        _client(body="<html>gateway timeout</html>").choices({"screen": "x"}, _QUESTIONS)


def test_a_transport_failure_is_unavailable_rather_than_raised_raw() -> None:
    def post(url, headers, data, timeout):
        raise urllib.error.URLError("connection refused")
    with pytest.raises(DecisionModelUnavailable, match="connection refused"):
        SystemOneClient("k", post=post).choices({"screen": "x"}, _QUESTIONS)


def test_no_key_in_the_environment_means_no_client() -> None:
    assert SystemOneClient.from_environment({}) is None
    assert SystemOneClient.from_environment({API_KEY_ENV: "   "}) is None


def test_a_key_in_the_environment_builds_a_client() -> None:
    assert SystemOneClient.from_environment({API_KEY_ENV: "sk-or-x"}) is not None
