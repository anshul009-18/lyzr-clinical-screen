from pydantic import BaseModel
from typing import Optional, Union


class CriterionRule(BaseModel):
    field: str
    operator: str
    value: Union[float, str, list]
    unit: Optional[str] = ""
    source_citation: Optional[str] = None


class ExtractedCriteria(BaseModel):
    inclusion: list[CriterionRule] = []
    exclusion: list[CriterionRule] = []
    washout_days: Optional[int] = None
