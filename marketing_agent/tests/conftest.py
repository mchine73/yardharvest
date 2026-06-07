"""Pytest fixtures for the marketing_agent test suite.

The agent module reads several env vars into module-level globals *at import
time* (CRM_BASE_URL, MARKETING_API_KEY, MODEL). To make tests deterministic and
independent of the host environment, we import the module once and patch those
globals per-test via the `agent_mod` fixture, rather than relying on
monkeypatch.setenv alone (which would not affect already-bound globals).
"""
import importlib
import os
import sys

import pytest

# Ensure the parent dir (which contains the `marketing_agent` package) is on the
# path so `import marketing_agent.agent` resolves regardless of where pytest is
# invoked from.
_PKG_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)


@pytest.fixture
def agent_mod(monkeypatch):
    """Import marketing_agent.agent and pin its config globals to test values.

    Yields the module with CRM_BASE_URL/MARKETING_API_KEY/MODEL set to known
    test values so URL/header/payload assertions are stable.
    """
    from marketing_agent import agent

    importlib.reload(agent)  # fresh state in case other tests mutated globals
    monkeypatch.setattr(agent, "CRM_BASE_URL", "https://crm.test")
    monkeypatch.setattr(agent, "MARKETING_API_KEY", "test-marketing-key")
    monkeypatch.setattr(agent, "MODEL", "claude-test-model")
    return agent


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, json_data=None, status_code=200, raise_exc=None):
        self._json = json_data if json_data is not None else {}
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc

    def json(self):
        return self._json


@pytest.fixture
def fake_response_cls():
    return FakeResponse
