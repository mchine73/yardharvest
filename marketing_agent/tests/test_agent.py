"""Unit tests for marketing_agent.agent.

No network and no real API keys: all HTTP (requests.get/post) and the Anthropic
client are mocked. We assert on the exact URLs, X-API-Key header, query params,
and JSON payloads the agent constructs, and that it only ever creates *drafts*.
"""
import json
import types
from unittest import mock

import pytest
import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_anthropic_response(text, *, content_type="text"):
    """Build an object shaped like the anthropic SDK's messages.create result.

    The agent reads `.content[<block>].type`/`.text` and `.usage.*`.
    """
    block = types.SimpleNamespace(type=content_type, text=text)
    usage = types.SimpleNamespace(
        input_tokens=123,
        output_tokens=45,
        cache_creation_input_tokens=10,
        cache_read_input_tokens=0,
    )
    return types.SimpleNamespace(content=[block], usage=usage)


CAMPAIGN_JSON = json.dumps({
    "name": "Spring pilot — WI gardens",
    "subject": "Less admin this season, {{first_name}}?",
    "body": "Hi {{first_name}}, running {{company}} in {{city}} takes work...",
})


# ---------------------------------------------------------------------------
# _crm_headers
# ---------------------------------------------------------------------------
def test_crm_headers_includes_api_key_and_json(agent_mod):
    headers = agent_mod._crm_headers()
    assert headers["X-API-Key"] == "test-marketing-key"
    assert headers["Content-Type"] == "application/json"


def test_crm_headers_reflects_current_key(agent_mod, monkeypatch):
    monkeypatch.setattr(agent_mod, "MARKETING_API_KEY", "rotated-key")
    assert agent_mod._crm_headers()["X-API-Key"] == "rotated-key"


# ---------------------------------------------------------------------------
# crm_get
# ---------------------------------------------------------------------------
def test_crm_get_builds_url_headers_params(agent_mod, fake_response_cls):
    resp = fake_response_cls({"ok": True})
    with mock.patch.object(agent_mod.requests, "get", return_value=resp) as g:
        out = agent_mod.crm_get("/crm/api/marketing/segments", params={"limit": 10})

    assert out == {"ok": True}
    args, kwargs = g.call_args
    assert args[0] == "https://crm.test/crm/api/marketing/segments"
    assert kwargs["headers"]["X-API-Key"] == "test-marketing-key"
    assert kwargs["params"] == {"limit": 10}
    assert kwargs["timeout"] == agent_mod.HTTP_TIMEOUT


def test_crm_get_calls_raise_for_status(agent_mod):
    resp = mock.Mock()
    resp.json.return_value = {}
    with mock.patch.object(agent_mod.requests, "get", return_value=resp):
        agent_mod.crm_get("/crm/api/marketing/segments")
    resp.raise_for_status.assert_called_once()


def test_crm_get_non_2xx_raises(agent_mod, fake_response_cls):
    err = requests.HTTPError("500 Server Error")
    resp = fake_response_cls(status_code=500, raise_exc=err)
    with mock.patch.object(agent_mod.requests, "get", return_value=resp):
        with pytest.raises(requests.HTTPError):
            agent_mod.crm_get("/crm/api/marketing/segments")


# ---------------------------------------------------------------------------
# crm_post
# ---------------------------------------------------------------------------
def test_crm_post_builds_url_headers_and_json_body(agent_mod, fake_response_cls):
    resp = fake_response_cls({"id": 7})
    payload = {"name": "x", "subject": "s", "body": "b"}
    with mock.patch.object(agent_mod.requests, "post", return_value=resp) as p:
        out = agent_mod.crm_post("/crm/api/marketing/campaigns", payload)

    assert out == {"id": 7}
    args, kwargs = p.call_args
    assert args[0] == "https://crm.test/crm/api/marketing/campaigns"
    assert kwargs["headers"]["X-API-Key"] == "test-marketing-key"
    # Body is JSON-serialized via json.dumps into the `data` kwarg.
    assert json.loads(kwargs["data"]) == payload
    assert kwargs["timeout"] == agent_mod.HTTP_TIMEOUT


def test_crm_post_non_2xx_raises(agent_mod, fake_response_cls):
    err = requests.HTTPError("400 Bad Request")
    resp = fake_response_cls(status_code=400, raise_exc=err)
    with mock.patch.object(agent_mod.requests, "post", return_value=resp):
        with pytest.raises(requests.HTTPError):
            agent_mod.crm_post("/crm/api/marketing/campaigns", {"a": 1})


# ---------------------------------------------------------------------------
# get_segments / endpoint path strings
# ---------------------------------------------------------------------------
def test_get_segments_uses_consolidated_path(agent_mod):
    with mock.patch.object(agent_mod, "crm_get", return_value={"segments": []}) as g:
        out = agent_mod.get_segments()
    assert out == {"segments": []}
    g.assert_called_once_with("/crm/api/marketing/segments")


# ---------------------------------------------------------------------------
# get_audience — query param construction
# ---------------------------------------------------------------------------
def test_get_audience_default_only_limit(agent_mod):
    with mock.patch.object(agent_mod, "crm_get", return_value={"count": 0}) as g:
        agent_mod.get_audience()
    path, kwargs = g.call_args[0][0], g.call_args[1]
    assert path == "/crm/api/marketing/audience"
    assert kwargs["params"] == {"limit": 200}


def test_get_audience_maps_filters_and_omits_empty(agent_mod):
    with mock.patch.object(agent_mod, "crm_get", return_value={"count": 5}) as g:
        agent_mod.get_audience(state="WI", org_type="Independent", tag="urban",
                               limit=50)
    params = g.call_args[1]["params"]
    assert params == {
        "limit": 50,
        "state": "WI",
        "type": "Independent",   # org_type maps to the `type` query param
        "tag": "urban",
    }


def test_get_audience_omits_blank_values(agent_mod):
    with mock.patch.object(agent_mod, "crm_get", return_value={"count": 1}) as g:
        agent_mod.get_audience(state="MN", org_type="", tag="")
    params = g.call_args[1]["params"]
    assert params == {"limit": 200, "state": "MN"}
    assert "type" not in params
    assert "tag" not in params


# ---------------------------------------------------------------------------
# create_draft — POST payload construction
# ---------------------------------------------------------------------------
def test_create_draft_minimal_payload(agent_mod):
    with mock.patch.object(agent_mod, "crm_post", return_value={"id": 1}) as p:
        out = agent_mod.create_draft("Camp", "Subj", "Body")
    assert out == {"id": 1}
    path, payload = p.call_args[0]
    assert path == "/crm/api/marketing/campaigns"
    assert payload == {"name": "Camp", "subject": "Subj", "body": "Body"}


def test_create_draft_includes_optional_filters(agent_mod):
    with mock.patch.object(agent_mod, "crm_post", return_value={"id": 2}) as p:
        agent_mod.create_draft("Camp", "Subj", "Body",
                               state="WI", org_type="City-Sponsored", tag="parks")
    payload = p.call_args[0][1]
    assert payload == {
        "name": "Camp", "subject": "Subj", "body": "Body",
        "state": "WI", "type": "City-Sponsored", "tag": "parks",
    }


def test_create_draft_omits_blank_filters(agent_mod):
    with mock.patch.object(agent_mod, "crm_post", return_value={"id": 3}) as p:
        agent_mod.create_draft("Camp", "Subj", "Body", state="", org_type="",
                               tag="")
    payload = p.call_args[0][1]
    assert set(payload) == {"name", "subject", "body"}


# ---------------------------------------------------------------------------
# draft_campaign — Claude integration
# ---------------------------------------------------------------------------
def test_draft_campaign_parses_model_json(agent_mod):
    client = mock.Mock()
    client.messages.create.return_value = make_anthropic_response(CAMPAIGN_JSON)

    audience = {
        "count": 12,
        "filters": {"state": "WI"},
        "contacts": [
            {"first_name": "Jane", "company": "Sunrise Garden",
             "city": "Madison", "state": "WI", "org_type": "Independent"},
        ],
    }
    segments = {"WI": 12}

    result = agent_mod.draft_campaign(client, "spring pilot", segments, audience)

    assert result["name"] == "Spring pilot — WI gardens"
    assert result["subject"].startswith("Less admin")
    assert "{{first_name}}" in result["body"]


def test_draft_campaign_sends_brand_voice_cached_system_prompt(agent_mod):
    client = mock.Mock()
    client.messages.create.return_value = make_anthropic_response(CAMPAIGN_JSON)

    agent_mod.draft_campaign(client, "goal", {}, {"count": 1, "contacts": []})

    kwargs = client.messages.create.call_args[1]
    # Stable cached brand-voice system prompt.
    assert kwargs["model"] == "claude-test-model"
    system = kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["text"] == agent_mod.BRAND_VOICE
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_draft_campaign_includes_goal_and_audience_context(agent_mod):
    client = mock.Mock()
    client.messages.create.return_value = make_anthropic_response(CAMPAIGN_JSON)

    audience = {
        "count": 3,
        "filters": {"state": "MN"},
        "contacts": [{"first_name": "Sam", "company": "Lakeside",
                      "city": "St Paul", "state": "MN", "org_type": "Independent"}],
    }
    agent_mod.draft_campaign(client, "re-engage stalled MN gardens", {"MN": 3},
                             audience)

    user_msg = client.messages.create.call_args[1]["messages"][0]["content"]
    assert "re-engage stalled MN gardens" in user_msg
    assert "Sam" in user_msg
    assert "Lakeside" in user_msg


def test_draft_campaign_never_sends_email(agent_mod):
    """The agent has no send capability: only crm_post to /campaigns (drafts)."""
    client = mock.Mock()
    client.messages.create.return_value = make_anthropic_response(CAMPAIGN_JSON)

    with mock.patch.object(agent_mod.requests, "post") as post, \
         mock.patch.object(agent_mod.requests, "get") as get:
        agent_mod.draft_campaign(client, "g", {}, {"count": 1, "contacts": []})

    # draft_campaign only talks to Claude; it makes no HTTP calls itself.
    post.assert_not_called()
    get.assert_not_called()
    # No "send"-style attribute is ever touched on the anthropic client.
    assert not client.send.called if hasattr(client.send, "called") else True


def test_draft_campaign_handles_no_contacts(agent_mod):
    client = mock.Mock()
    client.messages.create.return_value = make_anthropic_response(CAMPAIGN_JSON)
    # Empty contacts -> "(no sample available)" in the prompt, no crash.
    agent_mod.draft_campaign(client, "g", {}, {"count": 0, "contacts": []})
    user_msg = client.messages.create.call_args[1]["messages"][0]["content"]
    assert "(no sample available)" in user_msg


# ---------------------------------------------------------------------------
# run() — orchestration
# ---------------------------------------------------------------------------
def _patch_anthropic(agent_mod):
    """Return a context manager patching anthropic.Anthropic to a Mock client."""
    fake_client = mock.Mock()
    fake_client.messages.create.return_value = make_anthropic_response(CAMPAIGN_JSON)
    return fake_client, mock.patch.object(agent_mod.anthropic, "Anthropic",
                                          return_value=fake_client)


def test_run_missing_marketing_key_exits(agent_mod, monkeypatch):
    monkeypatch.setattr(agent_mod, "MARKETING_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with pytest.raises(SystemExit) as exc:
        agent_mod.run("goal")
    assert "MARKETING_API_KEY" in str(exc.value)


def test_run_missing_anthropic_key_exits(agent_mod, monkeypatch):
    monkeypatch.setattr(agent_mod, "MARKETING_API_KEY", "test-marketing-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        agent_mod.run("goal")
    assert "ANTHROPIC_API_KEY" in str(exc.value)


def test_run_no_recipients_exits(agent_mod, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_client, patch_anthropic = _patch_anthropic(agent_mod)
    with patch_anthropic, \
         mock.patch.object(agent_mod, "get_segments", return_value={}), \
         mock.patch.object(agent_mod, "get_audience", return_value={"count": 0}):
        with pytest.raises(SystemExit) as exc:
            agent_mod.run("goal", state="WI")
    assert "No recipients" in str(exc.value)


def test_run_dry_run_does_not_create_draft(agent_mod, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_client, patch_anthropic = _patch_anthropic(agent_mod)
    audience = {"count": 5, "filters": {}, "contacts": []}
    with patch_anthropic, \
         mock.patch.object(agent_mod, "get_segments", return_value={}), \
         mock.patch.object(agent_mod, "get_audience", return_value=audience), \
         mock.patch.object(agent_mod, "create_draft") as create:
        result = agent_mod.run("goal", state="WI", dry_run=True)

    create.assert_not_called()
    assert result["subject"].startswith("Less admin")


def test_run_creates_draft_with_filters(agent_mod, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_client, patch_anthropic = _patch_anthropic(agent_mod)
    audience = {"count": 5, "filters": {"state": "WI"}, "contacts": []}
    with patch_anthropic, \
         mock.patch.object(agent_mod, "get_segments", return_value={}), \
         mock.patch.object(agent_mod, "get_audience", return_value=audience) as ga, \
         mock.patch.object(agent_mod, "create_draft",
                           return_value={"id": 99, "review_url": "u"}) as create:
        result = agent_mod.run("goal", state="WI", org_type="Independent",
                               tag="t")

    ga.assert_called_once_with("WI", "Independent", "t")
    create.assert_called_once()
    pos = create.call_args[0]
    # create_draft(name, subject, body, state, org_type, tag)
    assert pos[3] == "WI" and pos[4] == "Independent" and pos[5] == "t"
    assert result == {"id": 99, "review_url": "u"}


def test_run_name_override(agent_mod, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_client, patch_anthropic = _patch_anthropic(agent_mod)
    audience = {"count": 5, "filters": {}, "contacts": []}
    with patch_anthropic, \
         mock.patch.object(agent_mod, "get_segments", return_value={}), \
         mock.patch.object(agent_mod, "get_audience", return_value=audience), \
         mock.patch.object(agent_mod, "create_draft",
                           return_value={"id": 1}) as create:
        agent_mod.run("goal", name="Custom Name")
    assert create.call_args[0][0] == "Custom Name"


# ---------------------------------------------------------------------------
# main() — CLI / arg parsing
# ---------------------------------------------------------------------------
def test_main_positional_goal_and_flags(agent_mod):
    with mock.patch.object(agent_mod, "run") as run:
        agent_mod.main(["spring push", "--state", "WI", "--type", "Independent",
                        "--tag", "urban", "--name", "MyCamp", "--dry-run"])
    run.assert_called_once()
    args, kwargs = run.call_args
    assert args[0] == "spring push"
    assert kwargs == {"state": "WI", "org_type": "Independent", "tag": "urban",
                      "name": "MyCamp", "dry_run": True}


def test_main_falls_back_to_marketing_goal_env(agent_mod, monkeypatch):
    monkeypatch.setenv("MARKETING_GOAL", "weekly outreach")
    with mock.patch.object(agent_mod, "run") as run:
        agent_mod.main([])
    assert run.call_args[0][0] == "weekly outreach"


def test_main_errors_without_goal(agent_mod, monkeypatch):
    monkeypatch.delenv("MARKETING_GOAL", raising=False)
    with mock.patch.object(agent_mod, "run") as run:
        with pytest.raises(SystemExit):
            agent_mod.main([])
    run.assert_not_called()


def test_main_defaults_for_optional_flags(agent_mod):
    with mock.patch.object(agent_mod, "run") as run:
        agent_mod.main(["just a goal"])
    kwargs = run.call_args[1]
    assert kwargs["state"] == ""
    assert kwargs["org_type"] == ""
    assert kwargs["tag"] == ""
    assert kwargs["name"] is None
    assert kwargs["dry_run"] is False
