"""Ask a typed decision model a closed question, and read back one declared option.

    client = SystemOneClient.from_environment()          # None without a key
    answers = client.choices(state, {"option": choice("Which option?", {"1": "…"})})
    answers["option"].choice, answers["option"].confidence

## Why a decision model, and not another headless agent

The lead's doctrine consultation used to be a `claude -p` call whose answer was free
text, parsed back by three regexes and a magic prefix. Every way that text could be
malformed needed its own refusal, and each consultation cost about USD 1.30. A
System One model answers a `choice` with one of the keys the caller declared and a
probability for each, so an answer outside the menu cannot be produced at all.
Measured on 2026-09-25 against a menu-shaped state: the same choice three times out
of three, confidence 0.95-0.96, USD 0.000016 and under one second per call.

## What this does NOT establish

**That the same input gets the same choice.** The schema guarantees the SHAPE; no
published document guarantees identical output for identical input. The model is
pinned (`MODEL`) so a silent upgrade cannot change behaviour, but repeated calls
were only observed to agree, not promised to.

**That the confidence is calibrated for our questions.** There is no labelled set of
doctrine menus to calibrate against, so the caller's threshold is a policy choice.

## Where the data goes

The state leaves the machine: OpenRouter routes it to TypeSafe. Callers send only
what the question needs — never a credential, never the key itself, which travels
in the Authorization header alone and is kept out of every error message.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

#: OpenRouter's TypeSafe-compatible System One endpoint. Not chat completions: that
#: API returns text, which is the thing this client exists to stop parsing.
ENDPOINT = "https://openrouter.ai/api/v1/systemone"
#: Pinned rather than `jev-latest`, so a model upgrade is a commit and not a surprise.
MODEL = "jev-1.13"
API_KEY_ENV = "OPENROUTER_API_KEY"

#: `post(url, headers, data, timeout) -> (status, body)`. Injected so tests never
#: reach the network; the default is `urllib`, so the kit adds no dependency.
Post = Callable[[str, dict, bytes, float], tuple[int, str]]


class DecisionModelUnavailable(Exception):
    """The model gave no usable answer. The caller falls back; it never guesses."""


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


def choice(instructions: str, criteria: Mapping[str, str]) -> dict:
    """One `choice` question: pick exactly one key of `criteria`."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def _urllib_post(url: str, headers: dict, data: bytes, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        # The scheme is refused unless https:// in `SystemOneClient.__init__`.
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        # An HTTP error status carries the provider's explanation in its body, and
        # that explanation is the useful half of the failure.
        return error.code, error.read().decode("utf-8", errors="replace")


class SystemOneClient:
    def __init__(self, api_key: str, *, model: str = MODEL, endpoint: str = ENDPOINT,
                 timeout: float = 30.0, post: Post | None = None) -> None:
        if not endpoint.startswith("https://"):
            # `urlopen` opens `file:` and custom schemes too; the key goes to HTTPS only.
            raise ValueError(f"the decision endpoint must be https://, got {endpoint.split(':', 1)[0]}:")
        self._api_key = api_key
        self.model = model
        self._endpoint = endpoint
        self._timeout = timeout
        self._post = post or _urllib_post

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> SystemOneClient | None:
        """A client when the key is set, None when it is not — absence is not an error."""
        key = (os.environ if environ is None else environ).get(API_KEY_ENV, "").strip()
        return cls(key) if key else None

    def choices(self, state: object, questions: Mapping[str, dict]) -> dict[str, ChoiceAnswer]:
        """Ask every `choice` question at once. Raises `DecisionModelUnavailable`."""
        body = json.dumps({"model": self.model, "state": state,
                           "questions": dict(questions)}).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json"}
        try:
            status, text = self._post(self._endpoint, headers, body, self._timeout)
        except (OSError, urllib.error.URLError) as error:
            raise DecisionModelUnavailable(f"{self.model} could not be reached: {error}") from error
        if status != 200:
            raise DecisionModelUnavailable(f"{self.model} answered HTTP {status}: {text[:200]}")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise DecisionModelUnavailable(
                f"{self.model} answered HTTP 200 with a body that is not JSON: {text[:120]}"
            ) from error
        answers = payload.get("answers") if isinstance(payload, dict) else None
        if not isinstance(answers, dict):
            raise DecisionModelUnavailable(f"{self.model} returned no `answers` object")
        return {name: self._read_choice(name, question, answers.get(name))
                for name, question in questions.items()}

    def _read_choice(self, name: str, question: dict, answer: object) -> ChoiceAnswer:
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise DecisionModelUnavailable(f"{self.model} gave no answer to `{name}`")
        picked = str(answer.get("choice", ""))
        if picked not in question["criteria"]:
            raise DecisionModelUnavailable(
                f"{self.model} chose {picked!r} for `{name}`, not one of "
                f"{sorted(question['criteria'])}")
        confidence = answer.get("confidence")
        if not isinstance(confidence, (int, float)):
            raise DecisionModelUnavailable(f"{self.model} gave `{name}` no confidence")
        probabilities = answer.get("probabilities") or {}
        return ChoiceAnswer(picked, float(confidence),
                            {str(k): float(v) for k, v in probabilities.items()})
