"""Tracing, with or without Azure Monitor.

Wathiq already has an audit trail: every case carries an append-only event log in PostgreSQL,
and that is the record a bank's auditor reads. Tracing answers a different question — *why was
this slow*, *which tool call hung*, *how often does the critic disagree across all cases* — and
it answers it across cases rather than within one. Both exist; neither replaces the other.
(DECISIONS #75)

The whole module is built around one rule: **`span()` must work everywhere**. It is called from
graph nodes, MCP tool calls and guardrail decisions, and those all have to keep running on a
laptop with no OpenTelemetry installed and no connection string set. So when tracing is off,
`span()` is a context manager that does nothing at all, and no call site ever has to ask.

What gets traced:

* every LangGraph node, entry to exit;
* every MCP tool call, with the server it went to;
* every guardrail decision, with the verdict;
* the Conductor task poll;
* the core-banking post, with its idempotency key.

`APPLICATIONINSIGHTS_CONNECTION_STRING` absent → nothing is exported and the spans cost a
dictionary lookup each.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Set once by `configure()`. `None` means tracing is off, which is the default.
_tracer: Any | None = None
_configured = False


def configure() -> bool:
    """Turn on Azure Monitor export if a connection string is set. Returns whether it is on.

    Safe to call more than once — the API and each worker call it at startup, and a second
    call must not install a second exporter.
    """
    global _tracer, _configured
    if _configured:
        return _tracer is not None
    _configured = True

    if not settings.azure_monitor_enabled:
        logger.info("tracing: off (no APPLICATIONINSIGHTS_CONNECTION_STRING)")
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry import trace
    except ImportError:
        # Configured but not installed. A warning, not a crash: losing telemetry must never
        # take down a case that is mid-flight.
        logger.warning(
            "tracing: APPLICATIONINSIGHTS_CONNECTION_STRING is set but "
            "azure-monitor-opentelemetry is not installed — tracing stays off"
        )
        return False

    try:
        configure_azure_monitor(
            connection_string=settings.azure_monitor_connection_string.strip(),
            # The name every span is grouped under in Application Insights.
            service_name=f"wathiq-{settings.environment}",
        )
        _tracer = trace.get_tracer("wathiq")
        logger.info("tracing: exporting to Azure Monitor")
        return True
    except Exception as exc:  # pragma: no cover - depends on the connection string
        logger.warning("tracing: could not start Azure Monitor export: %s", exc)
        _tracer = None
        return False


def enabled() -> bool:
    return _tracer is not None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Record one span, or do nothing at all when tracing is off.

    Attributes are the small facts worth querying across cases — a document type, a tool name,
    a verdict, a count. **Never** a document's text, a field's value or anything from the PII
    vault: a trace leaves the building, and the guardrails layer draws that line by producing a
    tokenised `log_text` that is the only text allowed anywhere near a log or a trace.
    """
    if _tracer is None:
        yield
        return

    with _tracer.start_as_current_span(name) as current:
        try:
            for key, value in attributes.items():
                if value is not None:
                    current.set_attribute(f"wathiq.{key}", value)
            yield
        except Exception as exc:
            # Record the failure on the span, then let it propagate untouched. Swallowing an
            # exception to keep a trace tidy would be a bug that hides bugs.
            current.record_exception(exc)
            try:
                from opentelemetry.trace import Status, StatusCode

                current.set_status(Status(StatusCode.ERROR, str(exc)))
            except ImportError:  # pragma: no cover - only if the SDK vanished mid-run
                pass
            raise


def annotate(**attributes: Any) -> None:
    """Add attributes to the span already running, or do nothing when tracing is off.

    For facts that are only known *after* the work — a verdict, a count, whether a fallback
    was used. The same rule about what may be recorded applies: no document text, no field
    values, nothing from the PII vault.
    """
    if _tracer is None:
        return
    try:
        from opentelemetry import trace

        current = trace.get_current_span()
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(f"wathiq.{key}", value)
    except Exception:  # pragma: no cover - telemetry must never break a case
        logger.debug("tracing: could not annotate the current span", exc_info=True)


def reset() -> None:
    """Forget the configuration, so a test can call `configure()` again."""
    global _tracer, _configured
    _tracer = None
    _configured = False


__all__ = ["annotate", "configure", "enabled", "reset", "span"]
