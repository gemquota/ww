# Jev UI decision controller

WW can optionally use TypeSafe Jev (System One) to make fast, typed judgments about
which UI action should be considered next. This is a decision-support service, not
a browser driver: it does not click, type, navigate, or execute any action.

## Enable

Set the key in the backend environment only:

~~~bash
export TYPESAFE_API_KEY="..."
export WW_JEV_MODEL="jev-latest"
export WW_JEV_TIMEOUT=8
~~~

Do not put the key in chat.html, browser storage, a URL, or a committed file. The objective, UI observation and candidate descriptions are sent to TypeSafe for evaluation; send only the minimum context needed and redact passwords, cookies, API keys, personal data and private page content before calling this endpoint.
The feature is unavailable when the key is absent. It adds no dependency to WW's
core terminal install; the integration uses Python's standard library.

## API

Authenticated endpoint:

~~~http
POST /api/v1/ui/decide
X-API-Key: <WW dashboard API key>
Content-Type: application/json
~~~

Example body:

~~~json
{
  "objective": "Open the settings menu",
  "observation": {
    "screen": "home",
    "visible_controls": ["settings", "new_chat"]
  },
  "candidates": [
    {"id": "open-settings", "description": "Open settings", "risk": "low"},
    {"id": "new-chat", "description": "Start a new chat", "risk": "low"}
  ]
}
~~~

Jev returns a candidate choice and a deliberation judgment. WW validates the choice
against the supplied candidate IDs. Low-confidence, ambiguous, medium-risk and
high-risk decisions are escalated. The response always has
execution_permitted=false: a separate controller must enforce permissions,
execute the action and verify the resulting UI state.

## Policy

- Jev only sees the objective, bounded UI observation and supplied candidates.
- Candidate IDs are an allowlist; an answer outside it is rejected.
- Only low-risk suggestions above the configured confidence floor can be returned
  as suggest.
- Medium/high-risk actions and deliberation requests return escalate.
- Missing credentials, transport failures and malformed answers fail closed.
- The API key never leaves the backend and is never returned in responses.

Configuration:
- TYPESAFE_API_KEY: enables the integration.
- WW_JEV_MODEL: model alias/version (default jev-latest).
- WW_JEV_TIMEOUT: request timeout in seconds (default 8).
- WW_JEV_MIN_CONFIDENCE: minimum choice confidence (default 0.75).
- WW_JEV_DELIBERATION_THRESHOLD: Noul threshold (default 0.35).

Tune confidence thresholds against a labelled UI-interaction evaluation set before
allowing any controller to execute suggestions. Jev is not a substitute for the
existing WW approval and tool-policy systems.


## Two-system controller and learning

See [Two-System UI Controller](jev-two-system-controller.md). The controller routes Jev suggestions to a deliberation-needed state when confidence/risk is insufficient or repeated outcomes indicate failure. Feedback is recorded locally. These endpoints do not execute input.
