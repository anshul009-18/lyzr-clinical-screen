from pydantic import BaseModel
from typing import Optional


class PatientLabs(BaseModel):
    eGFR: Optional[float] = None
    HbA1c: Optional[float] = None


class PatientRecord(BaseModel):
    patient_id: str
    name: Optional[str] = None
    dob: Optional[str] = None
    mrn: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    labs: PatientLabs = PatientLabs()
    conditions: list[str] = []
    medications: list[str] = []
    pregnant: Optional[bool] = None
    last_glp1_dose_days_ago: Optional[int] = None
