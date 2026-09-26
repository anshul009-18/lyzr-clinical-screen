"""
Generates a realistic-looking multi-page clinical trial protocol PDF
for testing the ingestion + Protocol Criteria Agent pipeline.

Content follows standard clinical trial protocol structure/conventions
(as seen in real public ClinicalTrials.gov protocol summaries) but is
a fictional trial — no real sponsor, drug, or trial ID.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib import colors

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Section", fontSize=13, spaceAfter=8, spaceBefore=14, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="SubSection", fontSize=11, spaceAfter=6, spaceBefore=10, fontName="Helvetica-Bold"))
body = styles["Normal"]

doc = SimpleDocTemplate(
    "sample_protocols/protocol_001.pdf",
    pagesize=letter,
    topMargin=0.9 * inch,
    bottomMargin=0.9 * inch,
)
story = []

story.append(Paragraph("Clinical Trial Protocol", styles["Title"]))
story.append(Paragraph("Protocol ID: PROT-2026-001", body))
story.append(Paragraph(
    "Title: A Phase II, Randomized, Double-Blind, Placebo-Controlled Study "
    "Evaluating the Efficacy and Safety of Investigational Agent DX-410 in "
    "Adult Patients with Type 2 Diabetes Mellitus", body))
story.append(Spacer(1, 16))

story.append(Paragraph("1. Study Overview", styles["Section"]))
story.append(Paragraph(
    "This study evaluates the glycemic efficacy and safety of DX-410 versus "
    "placebo, administered once daily over a 24-week treatment period, in "
    "adult patients with inadequately controlled Type 2 Diabetes Mellitus "
    "(T2DM) despite stable background therapy.", body))

story.append(Paragraph("2. Inclusion Criteria", styles["Section"]))
inclusion_items = [
    "2.1 &nbsp; Male or female, age 18 to 75 years, inclusive, at time of screening.",
    "2.2 &nbsp; Confirmed diagnosis of Type 2 Diabetes Mellitus for at least 6 months prior to screening.",
    "2.3 &nbsp; Estimated glomerular filtration rate (eGFR) &gt; 60 mL/min/1.73m&sup2; at screening, calculated using the CKD-EPI equation.",
    "2.4 &nbsp; Glycated hemoglobin (HbA1c) between 7.0% and 10.0%, inclusive, at screening.",
    "2.5 &nbsp; Body Mass Index (BMI) between 25 and 40 kg/m&sup2;, inclusive.",
    "2.6 &nbsp; Stable dose of metformin (&ge; 1500 mg/day or maximum tolerated dose) for at least 8 weeks prior to screening.",
    "2.7 &nbsp; Willing and able to provide written informed consent and comply with study visit schedule.",
]
for item in inclusion_items:
    story.append(Paragraph(item, body))
    story.append(Spacer(1, 4))

story.append(Paragraph("3. Exclusion Criteria", styles["Section"]))
exclusion_items = [
    "3.1 &nbsp; HbA1c &gt; 10.0% at screening.",
    "3.2 &nbsp; History of Type 1 Diabetes Mellitus or history of diabetic ketoacidosis.",
    "3.3 &nbsp; History of acute or chronic pancreatitis.",
    "3.4 &nbsp; Currently pregnant, breastfeeding, or planning pregnancy during the study period.",
    "3.5 &nbsp; Use of a GLP-1 receptor agonist within 14 days prior to screening (washout period required: 14 days).",
    "3.6 &nbsp; eGFR &le; 60 mL/min/1.73m&sup2; at screening.",
    "3.7 &nbsp; Uncontrolled hypertension, defined as systolic blood pressure &gt; 160 mmHg or diastolic &gt; 100 mmHg at screening.",
    "3.8 &nbsp; Known hypersensitivity to DX-410 or its excipients.",
]
for item in exclusion_items:
    story.append(Paragraph(item, body))
    story.append(Spacer(1, 4))

story.append(PageBreak())

story.append(Paragraph("4. Study Design", styles["Section"]))
story.append(Paragraph(
    "This is a multi-center, randomized, double-blind, placebo-controlled, "
    "parallel-group study. Eligible participants will be randomized 1:1 to "
    "receive either DX-410 or matching placebo, administered once daily for "
    "24 weeks, in addition to background metformin therapy.", body))

story.append(Paragraph("5. Screening & Eligibility Assessment Schedule", styles["SubSection"]))
data = [
    ["Assessment", "Screening (Day -14 to -1)", "Baseline (Day 0)"],
    ["Informed Consent", "X", ""],
    ["Medical History", "X", ""],
    ["HbA1c", "X", "X"],
    ["eGFR / Renal Panel", "X", ""],
    ["Pregnancy Test (if applicable)", "X", "X"],
    ["Vital Signs", "X", "X"],
    ["Concomitant Medication Review", "X", "X"],
]
t = Table(data, colWidths=[2.6 * inch, 1.9 * inch, 1.6 * inch])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
]))
story.append(t)
story.append(Spacer(1, 14))

story.append(Paragraph("6. Primary Endpoint", styles["Section"]))
story.append(Paragraph(
    "Change from baseline in HbA1c at Week 24, compared between the DX-410 "
    "and placebo arms.", body))

story.append(Paragraph("7. Safety Monitoring", styles["Section"]))
story.append(Paragraph(
    "Adverse events will be monitored throughout the study. Participants "
    "meeting any exclusion criterion identified after enrollment will be "
    "flagged for immediate investigator review and possible discontinuation, "
    "consistent with 21 CFR Part 11 documentation requirements for all "
    "eligibility determinations.", body))

doc.build(story)
print("Wrote sample_protocols/protocol_001.pdf")
