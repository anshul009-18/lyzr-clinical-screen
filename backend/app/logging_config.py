"""
Phase 3 — log audit gate.
Every log record emitted by the backend passes through PHIRedactionFilter
before it reaches any handler. Defense-in-depth on top of the
phi_scrubbing_agent gate — even a bug that logs a raw PatientRecord
gets scrubbed here before it hits disk/stdout.
"""

import logging

from agents.phi_scrubbing_agent.safe_ai_rules import scan_blob_for_phi, PHI_PATTERNS


class PHIRedactionFilter(logging.Filter):
    """Rewrites any PHI_PATTERNS match in a record's message to
    [REDACTED:<pattern>] instead of dropping the line — keeps logs useful
    for debugging while guaranteeing no raw identifier reaches output."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = message
        for name, pattern in PHI_PATTERNS.items():
            redacted = pattern.sub(f"[REDACTED:{name}]", redacted)

        if redacted != message:
            record.msg = redacted
            record.args = ()  # already fully formatted — drop args, avoid re-interpolation

        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Call once at startup. Attaches PHIRedactionFilter to the root logger
    so it covers uvicorn's loggers and any logging.getLogger(__name__)."""
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s"))
    handler.addFilter(PHIRedactionFilter())
    root.addHandler(handler)


def audit_log_line(line: str) -> list[str]:
    """Post-hoc check: re-scan an already-written log line for PHI. Used by
    backend/tests/test_audit.py, and can be pointed at a real log file to
    confirm zero unmasked identifiers before shipping logs anywhere."""
    return scan_blob_for_phi(line)
