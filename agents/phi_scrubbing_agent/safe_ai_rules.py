"""
Phase 3 — PHI Scrubbing Agent.
Deterministic regex-based redaction. No live Lyzr Safe AI network call —
Lyzr's Safe AI / Responsible AI protection is applied via an RAIPolicy
attached to an agent through the lyzr-adk SDK (studio.create_agent(...,
rai_policy=...) / agent.add_rai_policy(...)), not a standalone redact/detect
REST endpoint. An earlier version of this file called a fabricated
"/v1/redact/" URL that doesn't exist — removed. See README "Known
Limitations" for the stated path to real RAI SDK integration as a
stretch item.
"""

import re

# Direct identifiers — stripped wholesale, deterministically.
# Mirrors PatientRecord (backend/app/models/patient.py).
DIRECT_ID_FIELDS = ["name", "dob", "mrn", "address", "phone", "email"]

# Regex patterns for free-text fields (conditions, medications, notes) and
# for re-scanning logs/AIMS events. This IS the redaction/detection layer
# for MVP — not a fallback behind a real Safe AI call.
PHI_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),
    "mrn": re.compile(r"\bMRN[:\s]*\w+\b", re.IGNORECASE),
    "date": re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "name_prefix": re.compile(r"\b(Mr|Mrs|Ms|Dr)\.?\s+[A-Z][a-z]+\b"),
}


def redact_direct_identifiers(record: dict) -> dict:
    """Strip Phase-1 direct identifiers before the record goes near any LLM or log."""
    scrubbed = dict(record)
    for field in DIRECT_ID_FIELDS:
        if scrubbed.get(field) is not None:
            scrubbed[field] = None
    return scrubbed


def scan_for_leaked_phi(record: dict) -> list[str]:
    """Regex re-scan of free-text patient fields after direct-identifier redaction.
    Returns ['field:pattern_name', ...] for anything still matching."""
    hits = []
    for field in ("conditions", "medications"):
        value = record.get(field)
        blob = " ".join(value) if isinstance(value, list) else str(value or "")
        for pattern_name, pattern in PHI_PATTERNS.items():
            if pattern.search(blob):
                hits.append(f"{field}:{pattern_name}")
    return hits


def scan_blob_for_phi(text: str) -> list[str]:
    """Regex scan over ANY text blob — agent output, log line, dossier section,
    AIMS event detail. Returns matched pattern names."""
    if not text:
        return []
    return [name for name, pattern in PHI_PATTERNS.items() if pattern.search(text)]
