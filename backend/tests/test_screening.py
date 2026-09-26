from agents.orchestration.state import ExtractedCriteria, CriterionRule, ScreeningDecision
from agents.screening_agent.matcher import evaluate_patient


def make_criteria() -> ExtractedCriteria:
    return ExtractedCriteria(
        inclusion=[
            CriterionRule(field="age", operator=">=", value=18, unit="years", source_citation="2.1"),
            CriterionRule(field="eGFR", operator=">", value=60, unit="mL/min", source_citation="2.3"),
            CriterionRule(field="HbA1c", operator=">=", value=7.0, unit="%", source_citation="2.4"),
        ],
        exclusion=[
            CriterionRule(field="pregnant", operator="==", value=1.0, source_citation="3.4"),
        ],
        washout_days=14,
    )


def base_patient(**overrides) -> dict:
    patient = {
        "age": 40,
        "labs": {"eGFR": 80, "HbA1c": 8.0},
        "pregnant": False,
        "last_glp1_dose_days_ago": 20,
        "conditions": [],
        "medications": [],
    }
    patient.update(overrides)
    return patient


def test_eligible_patient():
    result = evaluate_patient(base_patient(), make_criteria())
    assert result.decision == ScreeningDecision.ELIGIBLE


def test_ineligible_on_failed_inclusion():
    # HbA1c 6.0 fails the >= 7.0 inclusion rule
    patient = base_patient(labs={"eGFR": 80, "HbA1c": 6.0})
    result = evaluate_patient(patient, make_criteria())
    assert result.decision == ScreeningDecision.INELIGIBLE


def test_ineligible_on_triggered_exclusion():
    patient = base_patient(pregnant=True)
    result = evaluate_patient(patient, make_criteria())
    assert result.decision == ScreeningDecision.INELIGIBLE


def test_requires_human_review_on_unresolved_field():
    """
    A criterion field the matcher's FIELD_RESOLVERS doesn't know about
    (e.g. bmi) must NEVER be guessed at — it forces human review. This
    is the core hallucination-prevention behavior of the whole agent.
    """
    criteria = ExtractedCriteria(
        inclusion=[
            CriterionRule(field="bmi", operator=">=", value=25, unit="kg/m2", source_citation="2.5"),
        ],
        exclusion=[],
        washout_days=None,
    )
    patient = base_patient()  # no "bmi" field anywhere on this patient
    result = evaluate_patient(patient, criteria)
    assert result.decision == ScreeningDecision.REQUIRES_HUMAN_REVIEW
    unresolved = [e for e in result.evaluations if e.confidence == 0.0]
    assert len(unresolved) == 1
    assert "UNRESOLVED" in unresolved[0].notes


def test_washout_period_enforced():
    # last dose 5 days ago fails the 14-day washout requirement
    patient = base_patient(last_glp1_dose_days_ago=5)
    result = evaluate_patient(patient, make_criteria())
    assert result.decision == ScreeningDecision.INELIGIBLE


def test_failed_inclusion_takes_priority_over_unresolved():
    """
    Regression test for the exact bug found during manual review: a
    protocol with both a failed inclusion criterion AND an unresolved
    field must return INELIGIBLE, not REQUIRES_HUMAN_REVIEW — a real
    failure should never be softened into "needs review."
    """
    criteria = ExtractedCriteria(
        inclusion=[
            CriterionRule(field="HbA1c", operator=">=", value=7.0, unit="%", source_citation="2.4"),
            CriterionRule(field="bmi", operator=">=", value=25, unit="kg/m2", source_citation="2.5"),
        ],
        exclusion=[],
        washout_days=None,
    )
    patient = base_patient(labs={"eGFR": 80, "HbA1c": 6.1})  # fails HbA1c, bmi unresolved
    result = evaluate_patient(patient, criteria)
    assert result.decision == ScreeningDecision.INELIGIBLE
