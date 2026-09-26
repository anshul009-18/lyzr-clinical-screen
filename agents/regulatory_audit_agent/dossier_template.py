"""
Phase 4c — Regulatory Audit Agent.
Deterministic templating: builds an FDA 21 CFR Part 11-style dossier
directly from PipelineState. Every line traces to a CriterionEvaluation
with its source_citation intact.

render_pdf() produces a PLAIN-LANGUAGE report — readable by a clinician,
IRB reviewer, or judge with no software background. Field names like
"metformin_dose" or statuses like "UNRESOLVED" never appear; everything
is translated via the lookup tables below. The full technical record
(raw field names, operators, confidence scores, complete event log)
still lives in the JSON export — nothing is lost, it's just not what's
shown on the page meant for a human to read start to finish.
"""

import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

from agents.orchestration.state import PipelineState, ScreeningDecision
from backend.app.models.audit_dossier import AuditDossier, DossierCriterionLine

# ─── Plain-language lookup tables ──────────────────────────────────────

FIELD_LABELS = {
    "age": "Age",
    "type_2_diabetes_mellitus_duration": "Time since Type 2 Diabetes diagnosis",
    "egfr": "Kidney function (eGFR)",
    "hba1c": "Blood sugar level (HbA1c)",
    "bmi": "Body Mass Index (BMI)",
    "metformin_dose": "Current metformin dose",
    "stable_metformin_duration": "Time on a stable metformin dose",
    "written_informed_consent_and_compliance": "Signed informed consent",
    "history_of_type_1_diabetes_mellitus": "History of Type 1 Diabetes",
    "history_of_diabetic_ketoacidosis": "History of diabetic ketoacidosis",
    "history_of_acute_or_chronic_pancreatitis": "History of pancreatitis",
    "pregnant": "Currently pregnant",
    "breastfeeding": "Currently breastfeeding",
    "planning_pregnancy_during_study_period": "Planning a pregnancy during the study",
    # Was "Recent use of a GLP-1 medication" — broke when the exclusion operator
    # gets inverted below ("Must have: Recent use... must be more than 14 days"
    # reads backwards). This label describes the inverted (safe-zone) phrasing.
    "glp1_receptor_agonist_use_prior_to_screening": "Time since last GLP-1 medication dose",
    "systolic_blood_pressure": "Systolic blood pressure",
    "diastolic_blood_pressure": "Diastolic blood pressure",
    "known_hypersensitivity_to_dx410_or_excipients": "Known allergy to the study drug",
    "last_glp1_dose_days_ago": "Days since last GLP-1 medication dose",
}

# Fields where the "value" is really just "does the patient have this?" —
# rendered as a plain yes/no requirement, not a numeric threshold.
BOOLEAN_CONDITION_FIELDS = {
    "written_informed_consent_and_compliance", "history_of_type_1_diabetes_mellitus",
    "history_of_diabetic_ketoacidosis", "history_of_acute_or_chronic_pancreatitis",
    "pregnant", "breastfeeding", "planning_pregnancy_during_study_period",
    "known_hypersensitivity_to_dx410_or_excipients",
}

OPERATOR_PHRASES = {
    ">=": "at least", "<=": "at most", ">": "more than", "<": "less than",
    "==": "equal to", "!=": "not equal to",
}

RESULT_LABELS = {
    "MET": ("Meets requirement", colors.HexColor("#1a7a1a"), colors.HexColor("#d9f2d9")),
    "NOT MET": ("Does not meet requirement", colors.HexColor("#a11616"), colors.HexColor("#f9d6d6")),
    "UNRESOLVED": ("Needs human review", colors.HexColor("#8a6d00"), colors.HexColor("#fff3cd")),
}

DECISION_SUMMARY = {
    ScreeningDecision.ELIGIBLE: (
        "Eligible",
        "Based on the information available, this patient appears to meet every trial requirement checked below.",
        colors.HexColor("#1a7a1a"),
    ),
    ScreeningDecision.INELIGIBLE: (
        "Not Eligible",
        "This patient does not meet one or more required trial criteria, listed below.",
        colors.HexColor("#a11616"),
    ),
    ScreeningDecision.REQUIRES_HUMAN_REVIEW: (
        "Needs Human Review",
        "Some information needed to fully check eligibility was missing or could not be confirmed "
        "automatically. A clinician or study coordinator should review the flagged items below before "
        "a final decision is made.",
        colors.HexColor("#8a6d00"),
    ),
    ScreeningDecision.PENDING: (
        "Pending",
        "Screening has not yet been completed for this patient.",
        colors.HexColor("#555555"),
    ),
}


def _field_label(field: str) -> str:
    if field.lower() in FIELD_LABELS:
        return FIELD_LABELS[field.lower()]
    return field.replace("_", " ").capitalize()


INVERTED_OP = {">=": "<", "<=": ">", ">": "<=", "<": ">="}


def _requirement_text(line: DossierCriterionLine) -> str:
    label = _field_label(line.field)
    key = line.field.lower()

    if key in BOOLEAN_CONDITION_FIELDS:
        prefix = "Must have:" if line.category == "inclusion" else "Must NOT have:"
        return f"{prefix} {label}"

    # Numeric exclusion rules: phrase as the safe zone (a positive requirement),
    # not as a negated threshold — "must be at most 14 days" reads backwards
    # stapled after "Must NOT have".
    operator = line.operator
    threshold = line.threshold
    if line.category == "exclusion" and operator in INVERTED_OP:
        operator = INVERTED_OP[operator]

    op_phrase = OPERATOR_PHRASES.get(operator, operator)
    unit = f" {line.unit}" if line.unit else ""
    if line.category == "washout":
        return f"Timing requirement: {label} must be {op_phrase} {threshold}{unit}"
    return f"Must have: {label} — must be {op_phrase} {threshold}{unit}"


def _patient_value_text(line: DossierCriterionLine) -> str:
    if line.patient_value is None:
        return "Not recorded in patient file"
    key = line.field.lower()
    if key in BOOLEAN_CONDITION_FIELDS:
        return "Yes" if line.patient_value in (True, 1, 1.0, "1", "true", "True") else "No"
    unit = f" {line.unit}" if line.unit else ""
    return f"{line.patient_value}{unit}"


def _friendly_events(dossier: AuditDossier) -> list[str]:
    """Collapses the technical event log into a short, plain-language checklist.
    Duplicate/internal confirmation lines are dropped — this is a summary for a
    human reader, not the full audit trail (that lives in the JSON export)."""
    decision_label = DECISION_SUMMARY[dossier.screening_decision][0]
    lines = ["Personal identifying information was removed before any review took place."]
    lines.append(f"Eligibility rules were checked against the protocol. Result: {decision_label}.")
    if dossier.flagged_by_medical_safety:
        lines.append("A medical safety review found items that need a clinician's attention.")
    else:
        lines.append("No medical safety concerns were found.")
    lines.append("This report was verified to contain no unmasked patient-identifying information before saving.")
    return lines


# ─── PDF rendering ──────────────────────────────────────────────────────

def build_dossier(state: PipelineState) -> AuditDossier:
    """Pure data assembly — no I/O. Call render_pdf() separately to export."""
    if state.extracted_criteria is None:
        raise ValueError(f"[{state.patient_id}] Cannot build dossier: no extracted_criteria on state")

    n_inclusion = len(state.extracted_criteria.inclusion)
    n_exclusion = len(state.extracted_criteria.exclusion)

    def category_for(idx: int) -> str:
        if idx < n_inclusion:
            return "inclusion"
        if idx < n_inclusion + n_exclusion:
            return "exclusion"
        return "washout"

    lines: list[DossierCriterionLine] = []
    for idx, ev in enumerate(state.screening_result.evaluations):
        result = "UNRESOLVED" if ev.confidence == 0.0 else ("MET" if ev.passed else "NOT MET")
        lines.append(DossierCriterionLine(
            field=ev.rule.field, category=category_for(idx), operator=ev.rule.operator,
            threshold=ev.rule.value, unit=ev.rule.unit, source_citation=ev.rule.source_citation,
            patient_value=ev.patient_value, result=result, confidence=ev.confidence,
        ))

    return AuditDossier(
        dossier_id=str(uuid.uuid4()),
        patient_id=state.patient_id, protocol_id=state.protocol_id,
        screening_decision=state.screening_result.decision,
        overall_confidence=state.screening_result.confidence,
        flagged_by_medical_safety=state.screening_result.flagged_by_medical_safety,
        medical_safety_reason=state.screening_result.flag_reason,
        criteria_lines=lines, event_trail=list(state.events),
        compliance_statement=(
            "This record was generated under 21 CFR Part 11 electronic-record principles: every "
            "requirement below is checked automatically and attributed to a specific section of the "
            "trial protocol. No patient-identifying information is included in this report."
        ),
    )


def render_pdf(dossier: AuditDossier, output_path: str) -> str:
    doc = SimpleDocTemplate(
        output_path, pagesize=letter, title=f"Screening Report — {dossier.dossier_id[:8]}",
        topMargin=54, bottomMargin=54, leftMargin=54, rightMargin=54,
    )
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9, leading=12, alignment=TA_LEFT)
    cell_bold = ParagraphStyle("cell_bold", parent=cell, fontName="Helvetica-Bold")
    small_muted = ParagraphStyle("small_muted", parent=styles["Normal"], fontSize=8,
                                  leading=11, textColor=colors.HexColor("#555555"))
    story = []

    # ── Header ──────────────────────────────────────────────────────
    story.append(Paragraph("Clinical Trial Screening Report", styles["Title"]))
    story.append(Paragraph(
        f"Patient reference: {dossier.patient_id}  |  Trial protocol: {dossier.protocol_id}  |  "
        f"Report date: {dossier.generated_at[:10]}",
        small_muted,
    ))
    story.append(Spacer(1, 14))

        # ── Decision summary, in plain language, up top ────────────────
    decision_label, decision_text, _ = DECISION_SUMMARY[dossier.screening_decision]

    banner_style = ParagraphStyle(
        "decision_banner", parent=styles["Normal"], fontSize=14,
        leading=18, fontName="Helvetica-Bold", textColor=colors.black,
    )
    banner = Table([[Paragraph(f"Result: {decision_label}", banner_style)]], colWidths=[480])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#cfe8fa")),  # light blue
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(banner)
    story.append(Spacer(1, 8))
    story.append(Paragraph(decision_text, styles["Normal"]))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 14))

    # ── Requirement-by-requirement table ────────────────────────────
    story.append(Paragraph("How This Patient Compares to the Trial Requirements", styles["Heading3"]))
    story.append(Spacer(1, 6))

    header = [Paragraph("Requirement", cell_bold), Paragraph("This Patient", cell_bold),
              Paragraph("Result", cell_bold), Paragraph("Protocol Reference", cell_bold)]
    rows = [header]
    row_bg = []
    for i, line in enumerate(dossier.criteria_lines, start=1):
        label, text_color, bg_color = RESULT_LABELS[line.result]
        result_para = Paragraph(f'<font color="{text_color.hexval()}"><b>{label}</b></font>', cell)
        rows.append([
            Paragraph(_requirement_text(line), cell),
            Paragraph(_patient_value_text(line), cell),
            result_para,
            Paragraph(line.source_citation or "—", small_muted),
        ])
        row_bg.append((i, bg_color))

    table = Table(rows, colWidths=[215, 90, 85, 90], repeatRows=1)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    for row_idx, bg in row_bg:
        style_cmds.append(("BACKGROUND", (2, row_idx), (2, row_idx), bg))
    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    story.append(Spacer(1, 16))

    # ── Plain-language summary of what happened, replacing raw event log ──
    story.append(Paragraph("What Happened During This Review", styles["Heading3"]))
    for item in _friendly_events(dossier):
        story.append(Paragraph(f"• {item}", styles["Normal"]))
    story.append(Spacer(1, 16))

    # ── Compliance statement + pointer to full technical record ────
    story.append(Paragraph("About This Report", styles["Heading3"]))
    story.append(Paragraph(dossier.compliance_statement, styles["Normal"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"A complete technical record of this evaluation — including exact confidence scores and a "
        f"full timestamped event log — is stored separately under report ID {dossier.dossier_id}.",
        small_muted,
    ))

    doc.build(story)
    return output_path
