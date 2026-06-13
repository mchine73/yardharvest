"""Lightweight fire-and-forget background execution.

Notification fan-out (email + SMS to many recipients) used to run inside the
request handler — a 200-member announcement meant N sequential Twilio calls
blocking the POST, which could exceed the gunicorn worker timeout. This module
runs such work on a small thread pool with its own app context instead.

This is intentionally NOT a durable queue (no Celery/RQ/Redis). Tasks are
best-effort: if the process restarts mid-send, in-flight work is lost. That is
an acceptable trade for notifications (the in-app notification, which IS durable,
is written synchronously in the request). Graduate to a real queue when a
pilot network's volume justifies it.

Pass only plain values (strings, ids, lists) to run_async — never ORM objects,
which would be detached once the request's session closes.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

log = logging.getLogger(__name__)

# Small pool: notification sends are I/O-bound (HTTP to ZeptoMail/Twilio).
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='yh-task')


def run_async(fn, *args, **kwargs):
    """Run ``fn(*args, **kwargs)`` in a background thread under an app context.

    Any exception is logged (never raised back into the request). Returns
    immediately. Safe to call from a request handler; the caller does not wait.
    """
    app = current_app._get_current_object()

    # Under tests, run inline so assertions are deterministic (no thread race)
    # and the test's app context / patches apply directly.
    if app.config.get('TESTING'):
        try:
            fn(*args, **kwargs)
        except Exception:
            log.exception('Background task %s failed (inline/test)',
                          getattr(fn, '__name__', repr(fn)))
        return

    def _worker():
        with app.app_context():
            try:
                fn(*args, **kwargs)
            except Exception:
                log.exception('Background task %s failed',
                              getattr(fn, '__name__', repr(fn)))

    try:
        _executor.submit(_worker)
    except Exception:
        # Pool rejected the task (e.g. interpreter shutting down) — run inline
        # so the notification is still attempted rather than silently dropped.
        log.warning('Thread pool rejected task; running %s inline',
                    getattr(fn, '__name__', repr(fn)))
        _worker()
