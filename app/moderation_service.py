"""AI moderation for the public garden comment wall.

A single Claude call classifies each new comment as allow / flag / block:

  allow  -> post normally
  flag   -> post, but mark for garden-admin review (borderline)
  block  -> reject; the reason is shown to the commenter

``anthropic`` and ANTHROPIC_API_KEY are optional. When unavailable, moderation
is a graceful no-op (``allow``) so the wall keeps working without the AI — the
feature degrades, it does not break. Uses a Sonnet model by default (fast and
plenty for short-text classification); override with MODERATION_MODEL.
"""
import json
import logging
import os

log = logging.getLogger(__name__)

# Sonnet is the right tier for short-text classification, and this one is a
# safety gate on a public wall — worth not cheapening. James asked for Sonnet
# specifically; this is the current generation of it. Override with
# MODERATION_MODEL if needed.
DEFAULT_MODEL = os.environ.get('MODERATION_MODEL', 'claude-sonnet-5')

SYSTEM_PROMPT = """You moderate comments posted to a community-garden's public \
comment wall. Gardens are family-friendly community spaces. Classify the \
comment into exactly one of:

- "allow": friendly, on-topic, or harmless. The default for normal comments.
- "flag": borderline — mild profanity, light personal attacks, off-topic \
promotion/spam, or anything a human moderator should glance at. It will still \
post but a garden admin is notified.
- "block": clearly unacceptable — hate speech, harassment or threats, sexual \
content, doxxing, or aggressive spam/scams. It will be rejected.

Lean toward "allow" for ordinary garden chatter. Reserve "block" for content \
that genuinely violates community standards.

Respond with ONLY a JSON object, no other text:
{"decision": "allow"|"flag"|"block", "reason": "<short reason, <=160 chars>"}"""


def is_configured():
    """True when moderation can run (SDK importable and key set)."""
    if not os.environ.get('ANTHROPIC_API_KEY'):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def moderate_comment(text, *, model=None):
    """Classify a comment. Returns (decision, reason).

    decision is one of 'allow' | 'flag' | 'block'. On any failure (not
    configured, API error, unparseable response) returns ('allow', '') so a
    moderation outage never blocks legitimate comments.
    """
    text = (text or '').strip()
    if not text:
        return 'allow', ''
    if not is_configured():
        return 'allow', ''

    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            # Sonnet 5 thinks by default when `thinking` is omitted, and
            # max_tokens caps thinking + answer together — which would truncate
            # a 200-token JSON verdict. This is a one-line classification on a
            # latency-sensitive path, so turn it off and keep the budget small.
            thinking={'type': 'disabled'},
            max_tokens=400,
            system=[{
                'type': 'text',
                'text': SYSTEM_PROMPT,
                'cache_control': {'type': 'ephemeral'},
            }],
            messages=[{'role': 'user', 'content': f'Comment to moderate:\n\n{text}'}],
        )
        raw = next((b.text for b in resp.content if b.type == 'text'), '').strip()
        # The model may wrap JSON in prose or a code fence; extract the object.
        start, end = raw.find('{'), raw.rfind('}')
        if start == -1 or end == -1:
            log.warning('Moderation: no JSON in response; defaulting to allow')
            return 'allow', ''
        data = json.loads(raw[start:end + 1])
        decision = str(data.get('decision', 'allow')).lower().strip()
        if decision not in ('allow', 'flag', 'block'):
            decision = 'allow'
        reason = str(data.get('reason', ''))[:300]
        return decision, reason
    except Exception:
        log.exception('Comment moderation failed; defaulting to allow')
        return 'allow', ''
