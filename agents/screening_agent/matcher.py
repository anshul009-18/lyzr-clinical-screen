"""
Phase 4a — Screening Agent.
Deterministic eligibility evaluation. No LLM call — every decision
traces back to an explicit field lookup + operator comparison against
the Phase 2 criteria JSON. If a criterion's field can't be resolved
from the patient record schema, it is NEVER guessed at: it's marked
unresolved and forces REQUIRES_HUMAN_REVIEW. Silent guessing is exactly
the hallucination-risk this phase exists to eliminate.
"""

from agents.orchestration.state import (
    CriterionEvaluation,
    CriterionRule,
    ExtractedCriteria,
    ScreeningDecision,
    ScreeningResult,
)

# --- Deterministic field resolvers -----------------------------------
# Each resolver is a plain function over the scrubbed patient dict.
# Keys are lowercase, matched against CriterionRule.field.lower().
# Anything NOT in this map is unresolved by design — see module docstring.

FIELD_RESOLVERS = {
    "age": lambda p: p.get("age"),
    "sex": lambda p: p.get("sex"),
    "pregnant": lambda p: p.get("pregnant"),
    "egfr": lambda p: (p.get("labs") or {}).get("eGFR"),
    "hba1c": lambda p: (p.get("labs") or {}).get("HbA1c"),
    "last_glp1_dose_days_ago": lambda p: p.get("last_glp1_dose_days_ago"),
    "glp1_receptor_agonist_use_prior_to_screening": lambda p: p.get("last_glp1_dose_days_ago"),
}

# Boolean condition-history fields resolved by deterministic keyword match
# against the structured `conditions` list — NOT free-text NLP judgment,
# a plain case-insensitive substring check against a fixed vocabulary.
CONDITION_KEYWORD_FIELDS = {
    "history_of_type_1_diabetes_mellitus": "type 1 diabetes",
    "history_of_diabetic_ketoacidosis": "diabetic ketoacidosis",
    "history_of_acute_or_chronic_pancreatitis": "pancreatitis",
}

_OPS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def _resolve(field: str, patient: dict) -> tuple[object, bool]:
    """Returns (value, resolved). resolved=False means: don't evaluate this
    rule at all — route it to human review instead of guessing."""
    key = field.lower()

    if key in FIELD_RESOLVERS:
        value = FIELD_RESOLVERS[key](patient)
        return value, value is not None

    if key in CONDITION_KEYWORD_FIELDS:
        conditions = [c.lower() for c in (patient.get("conditions") or [])]
        keyword = CONDITION_KEYWORD_FIELDS[key]
        return any(keyword in c for c in conditions), True

    return None, False


def _evaluate_rule(rule: CriterionRule, patient: dict) -> CriterionEvaluation:
    value, resolved = _resolve(rule.field, patient)

    if not resolved:
        return CriterionEvaluation(
            rule=rule,
            patient_value=None,
            passed=False,
            confidence=0.0,
            notes=f"UNRESOLVED — '{rule.field}' not in patient record schema, cannot evaluate deterministically",
        )

    op = _OPS.get(rule.operator)
    if op is None:
        return CriterionEvaluation(
            rule=rule,
            patient_value=value,
            passed=False,
            confidence=0.0,
            notes=f"UNRESOLVED — unsupported operator '{rule.operator}'",
        )

    try:
        satisfied = bool(op(value, rule.value))
    except TypeError:
        return CriterionEvaluation(
            rule=rule,
            patient_value=value,
            passed=False,
            confidence=0.0,
            notes=f"UNRESOLVED — type mismatch comparing {value!r} against {rule.value!r}",
        )

    return CriterionEvaluation(rule=rule, patient_value=value, passed=satisfied, confidence=1.0)


def _evaluate_washout(criteria: ExtractedCriteria, patient: dict) -> CriterionEvaluation | None:
    """washout_days is separate metadata on ExtractedCriteria, not a CriterionRule —
    evaluated here as a synthetic rule so it isn't silently dropped."""
    if criteria.washout_days is None:
        return None
    days_since = patient.get("last_glp1_dose_days_ago")
    synthetic_rule = CriterionRule(
        field="last_glp1_dose_days_ago", operator=">=",
        value=float(criteria.washout_days), unit="days",
        source_citation="washout_days (protocol-level)",
    )
    if days_since is None:
        return CriterionEvaluation(
            rule=synthetic_rule, patient_value=None, passed=False, confidence=0.0,
            notes="UNRESOLVED — no last_glp1_dose_days_ago on patient record",
        )
    return CriterionEvaluation(
        rule=synthetic_rule, patient_value=days_since,
        passed=days_since >= criteria.washout_days, confidence=1.0,
    )


def evaluate_patient(patient: dict, criteria: ExtractedCriteria) -> ScreeningResult:
    """
    Entry point called by orchestration/pipeline.py::run_screening.
    Inclusion rules: passed=True means the patient satisfies the rule (good).
    Exclusion rules: passed=True means the patient does NOT trigger the
    exclusion (also good) — the rule itself is inverted at evaluation time
    so `passed` has one consistent meaning across the whole result.
    """
    evaluations: list[CriterionEvaluation] = []

    for rule in criteria.inclusion:
        evaluations.append(_evaluate_rule(rule, patient))

    for rule in criteria.exclusion:
        ev = _evaluate_rule(rule, patient)
        if ev.confidence > 0.0:  # only invert a rule that was actually evaluated
            ev = CriterionEvaluation(
                rule=ev.rule, patient_value=ev.patient_value,
                passed=not ev.passed, confidence=ev.confidence, notes=ev.notes,
            )
        evaluations.append(ev)

    washout_eval = _evaluate_washout(criteria, patient)
    if washout_eval is not None:
        evaluations.append(washout_eval)

    unresolved = [e for e in evaluations if e.confidence == 0.0]
    failed = [e for e in evaluations if e.confidence > 0.0 and not e.passed]

    if failed:
        decision = ScreeningDecision.INELIGIBLE
    elif unresolved:
        decision = ScreeningDecision.REQUIRES_HUMAN_REVIEW
    else:
        decision = ScreeningDecision.ELIGIBLE

    overall_confidence = min((e.confidence for e in evaluations), default=0.0)

    return ScreeningResult(
        decision=decision,
        confidence=overall_confidence,
        evaluations=evaluations,
    )
